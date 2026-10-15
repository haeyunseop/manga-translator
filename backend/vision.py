"""Tesseract -> local NLLB -> OpenCV inpainting -> Korean Pillow typesetting."""
import os
import re
import threading
from dataclasses import dataclass
import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageDraw, ImageFont, ImageOps
from .config import MAX_PIXELS, MODELS, MODEL_PATH, MODEL_KIND, FONT_PATH

Image.MAX_IMAGE_PIXELS = MAX_PIXELS
JP = re.compile(r'[\u3040-\u30ff\u3400-\u9fff]')

def normalize_image(raw):
    import io
    try:
        with Image.open(io.BytesIO(raw)) as im:
            if im.format not in {'JPEG','PNG','WEBP'}:
                raise ValueError('PNG, JPEG, WebP 이미지만 지원합니다.')
            if im.width * im.height > MAX_PIXELS or min(im.size) < 100:
                raise ValueError('이미지 크기는 최소 100px, 최대 1,600만 화소입니다.')
            im.load()
            rgba=ImageOps.exif_transpose(im).convert('RGBA')
            bg=Image.new('RGBA',rgba.size,'white')
            return Image.alpha_composite(bg,rgba).convert('RGB')
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('이미지가 너무 큽니다.') from exc
    except (OSError, SyntaxError) as exc:
        raise ValueError('읽을 수 없는 이미지입니다.') from exc

@dataclass
class Region:
    text: str
    confidence: float
    box: tuple
    ink_boxes: list
    direction: str
    polygon: list | None = None

class TranslationQualityError(RuntimeError):
    """An output that must not replace the original text."""

def validate_translation(source,result):
    if not result or (JP.search(source) and not re.search(r'[가-힣]',result)):
        raise TranslationQualityError('한국어 번역을 확인하지 못해 원문을 유지했습니다.')
    compact=re.sub(r'[\s\W_]+','',result)
    words=re.findall(r'[가-힣]+',result)
    # Detect short loops even if a model alternates punctuation or spacing.
    repeating=any(re.search(r'(.{1,'+str(n)+r'})\1{5,}',compact) for n in (1,2,4,8))
    repeated_word=any(words.count(word)>=6 and words.count(word)>len(words)*.4 for word in set(words))
    if repeating or repeated_word or len(compact)>max(100,len(source)*4):
        raise TranslationQualityError('번역 모델의 반복·과도한 출력을 감지해 원문을 유지했습니다.')
    return result

def tess_config(psm):
    # pytesseract uses shlex(posix=False) on Windows, preserving literal quotes
    # in --tessdata-dir. The child environment passes this path without quoting.
    os.environ['TESSDATA_PREFIX']=str(MODELS / 'tessdata')
    return f'--psm {psm}'

def _read_region(image, box, direction, psm, isolation=None):
    crop=image.crop(box)
    if isolation is not None:
        pixels=np.array(crop)
        pixels[isolation==0]=255
        crop=Image.fromarray(pixels)
    # Small print and ruby are otherwise close to Tesseract's minimum glyph size.
    scale=2 if max(crop.size)<900 else 1
    if scale>1:
        crop=crop.resize((crop.width*scale,crop.height*scale),Image.Resampling.LANCZOS)
    lang='jpn_vert' if direction=='vertical' else 'jpn'
    data=pytesseract.image_to_data(crop,lang=lang,config=tess_config(psm),output_type=pytesseract.Output.DICT,timeout=90)
    words=[]
    for i, word in enumerate(data['text']):
        conf=float(data['conf'][i])
        if word.strip() and conf>=20:
            words.append((i,word.strip(),conf))
    text=''.join(w for _,w,_ in words)
    if not JP.search(text):
        return None
    ink=[]
    for i,_,_ in words:
        x,y,w,h=(int(data[k][i]) for k in ['left','top','width','height'])
        ink.append((box[0]+x//scale,box[1]+y//scale,box[0]+int(np.ceil((x+w)/scale)),box[1]+int(np.ceil((y+h)/scale))))
    polygon=None
    if isolation is not None:
        contours,_=cv2.findContours(isolation,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            boundary=cv2.approxPolyDP(max(contours,key=cv2.contourArea),1.5,True).reshape(-1,2)
            polygon=[(box[0]+int(x),box[1]+int(y)) for x,y in boundary]
    return Region(text,round(sum(c for _,_,c in words)/len(words),1),box,ink,direction,polygon)

def recognize(image, direction='auto'):
    if not (MODELS/'tessdata/jpn.traineddata').exists():
        raise RuntimeError('일본어 OCR 데이터가 없습니다. python scripts/download_models.py를 실행하세요.')
    gray=cv2.cvtColor(np.array(image),cv2.COLOR_RGB2GRAY)
    # Enclosed white regions detect speech balloons without erasing their outlines.
    _,white=cv2.threshold(gray,242,255,cv2.THRESH_BINARY)
    count,labels,stats,_=cv2.connectedComponentsWithStats(white,8)
    candidates=[]
    for label,(x,y,w,h,area) in enumerate(stats[1:],1):
        if 2500<area<gray.size*.6 and w>=70 and h>=45 and area/(w*h)>.35:
            box=(int(x+6),int(y+6),int(x+w-6),int(y+h-6))
            component=(labels[y:y+h,x:x+w]==label).astype('uint8')*255
            contours,_=cv2.findContours(component,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            isolated=np.zeros_like(component)
            cv2.drawContours(isolated,contours,-1,255,cv2.FILLED)
            isolated=cv2.erode(isolated,np.ones((7,7),np.uint8))
            candidates.append((box,isolated[6:-6,6:-6]))
    if len(candidates)>80:
        raise RuntimeError('말풍선 후보가 너무 많습니다. 페이지를 나눠 주세요.')
    results=[]
    for box,isolation in candidates:
        directions=['horizontal','vertical'] if direction=='auto' else [direction]
        choices=[]
        for orient in directions:
            r=_read_region(image,box,orient,5 if orient=='vertical' else 6,isolation)
            # Short kana-like facial features are a common false positive in line art.
            if r and len(JP.findall(r.text))<4 and not re.search(r'[\u3400-\u9fff]',r.text):
                r=None
            if r: choices.append(r)
        if choices:
            def score(r):
                ix1=min(b[0] for b in r.ink_boxes);iy1=min(b[1] for b in r.ink_boxes)
                ix2=max(b[2] for b in r.ink_boxes);iy2=max(b[3] for b in r.ink_boxes)
                preferred='vertical' if iy2-iy1>(ix2-ix1)*1.2 else 'horizontal'
                return r.confidence+(12 if r.direction==preferred else 0)
            results.append(max(choices,key=score))
    if not results:
        # Fallback for borderless text. Group each Tesseract block independently.
        orient='vertical' if direction=='vertical' else 'horizontal'
        lang='jpn_vert' if orient=='vertical' else 'jpn'
        data=pytesseract.image_to_data(image,lang=lang,config=tess_config(5 if orient=='vertical' else 11),output_type=pytesseract.Output.DICT,timeout=90)
        groups={}
        for i,word in enumerate(data['text']):
            if word.strip() and float(data['conf'][i])>=20:
                groups.setdefault(data['block_num'][i],[]).append(i)
        for indices in groups.values():
            text=''.join(data['text'][i].strip() for i in indices)
            if not JP.search(text): continue
            boxes=[(data['left'][i],data['top'][i],data['left'][i]+data['width'][i],data['top'][i]+data['height'][i]) for i in indices]
            box=(max(0,min(b[0] for b in boxes)-8),max(0,min(b[1] for b in boxes)-8),min(image.width,max(b[2] for b in boxes)+8),min(image.height,max(b[3] for b in boxes)+8))
            results.append(Region(text,round(sum(float(data['conf'][i]) for i in indices)/len(indices),1),box,boxes,orient))
    if not results:
        raise RuntimeError('일본어를 인식하지 못했습니다. 선명한 이미지나 다른 글 방향으로 다시 시도하세요.')
    # Japanese reading order: upper row first, right to left within a row.
    return sorted(results,key=lambda r:(r.box[1]//120,-r.box[0]))

class LocalTranslator:
    def __init__(self):
        self.model=None
        self.tokenizer=None
        self.lock=threading.Lock()

    def ready(self):
        needed=['config.json','sentencepiece.bpe.model','tokenizer_config.json']
        if MODEL_KIND=='m2m100': needed.append('vocab.json')
        return all((MODEL_PATH/f).is_file() for f in needed) and any((MODEL_PATH/f).is_file() for f in ['pytorch_model.bin','model.safetensors'])

    def translate(self,text):
        if not self.ready():
            raise RuntimeError('로컬 번역 모델이 없습니다. python scripts/download_models.py로 내려받으세요. 유료 API로 대체하지 않습니다.')
        with self.lock:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            torch.set_num_threads(min(4,os.cpu_count() or 1))
            if self.model is None:
                self.tokenizer=AutoTokenizer.from_pretrained(MODEL_PATH,local_files_only=True,src_lang='jpn_Jpan' if MODEL_KIND=='nllb' else 'ja')
                self.model=AutoModelForSeq2SeqLM.from_pretrained(MODEL_PATH,local_files_only=True).eval()
            encoded=self.tokenizer(text,return_tensors='pt',truncation=False)
            if encoded.input_ids.shape[1]>512:
                raise RuntimeError('말풍선 텍스트가 모델 입력 한도를 초과했습니다. 이미지를 나눠 주세요.')
            with torch.inference_mode():
                target=self.tokenizer.convert_tokens_to_ids('kor_Hang') if MODEL_KIND=='nllb' else self.tokenizer.get_lang_id('ko')
                generated=self.model.generate(**encoded,forced_bos_token_id=target,max_new_tokens=min(256,max(48,len(text)*4)),max_length=None,num_beams=4,no_repeat_ngram_size=4,repetition_penalty=1.1)
            eos=self.model.generation_config.eos_token_id
            end_tokens=eos if isinstance(eos,list) else [eos]
            if generated[0,-1].item() not in end_tokens:
                raise TranslationQualityError('번역이 길이 한도에서 중단돼 원문을 유지했습니다.')
            result=self.tokenizer.batch_decode(generated,skip_special_tokens=True)[0].strip()
            return validate_translation(text,result)

translator=LocalTranslator()

def clean_image(image,regions):
    pixels=np.array(image)
    gray=cv2.cvtColor(pixels,cv2.COLOR_RGB2GRAY)
    mask=np.zeros(gray.shape,dtype=np.uint8)
    for r in regions:
        region_mask=np.zeros(gray.shape,dtype=np.uint8)
        # Include gaps between OCR words: low-confidence glyphs can be omitted by TSV.
        # Mask all ink inside the recognized text envelope, not only accepted word boxes.
        envelope=(min(b[0] for b in r.ink_boxes),min(b[1] for b in r.ink_boxes),max(b[2] for b in r.ink_boxes),max(b[3] for b in r.ink_boxes))
        for x1,y1,x2,y2 in [envelope]:
            x1,y1=max(0,x1-2),max(0,y1-2)
            x2,y2=min(image.width,x2+2),min(image.height,y2+2)
            region_mask[y1:y2,x1:x2]=(gray[y1:y2,x1:x2]<210).astype('uint8')*255
        region_mask=cv2.dilate(region_mask,np.ones((3,3),np.uint8),iterations=1)
        if r.polygon:
            boundary=np.zeros_like(mask)
            cv2.fillPoly(boundary,[np.array(r.polygon,dtype=np.int32)],255)
            region_mask=cv2.bitwise_and(region_mask,boundary)
        mask=cv2.bitwise_or(mask,region_mask)
    return Image.fromarray(cv2.inpaint(pixels,mask,3,cv2.INPAINT_TELEA)),Image.fromarray(mask)

def _wrap(text,font,width):
    lines=[]
    for paragraph in text.split('\n'):
        remaining=paragraph.strip()
        if not remaining:
            lines.append('')
        while remaining:
            line,rest=_take_line(remaining,font,width)
            if not line:
                # A single glyph wider than the available space is handled by
                # the layout validator, never by silently dropping the glyph.
                line,rest=remaining[0],remaining[1:]
            lines.append(line)
            remaining=rest
    return lines

def _take_line(text,font,width):
    text=text.lstrip()
    low,high=0,len(text.split('\n',1)[0])
    while low<high:
        middle=(low+high+1)//2
        if font.getlength(text[:middle])<=width:
            low=middle
        else:
            high=middle-1
    end=low
    if end<len(text) and end and not text[end].isspace():
        space=text.rfind(' ',0,end+1)
        if space>0: end=space
    return text[:end].rstrip(),text[end:].lstrip()

def _region_mask(image,region,padding):
    x1,y1,x2,y2=region.box
    mask=np.ones((y2-y1,x2-x1),dtype=np.uint8)*255
    if region.polygon:
        mask[:]=0
        points=np.array(region.polygon,dtype=np.int32)-[x1,y1]
        cv2.fillPoly(mask,[points],255)
    # Do not place Korean text over remaining line art, even for a fallback OCR
    # block whose bounding rectangle is wider than the actual speech balloon.
    pixels=np.array(image.crop(region.box).convert('RGB'))
    mask[np.min(pixels,axis=2)<225]=0
    return cv2.erode(mask,np.ones((padding*2+1,padding*2+1),np.uint8),borderType=cv2.BORDER_CONSTANT,borderValue=0)

def _span(mask,y,height):
    if y<0 or y+height>mask.shape[0]: return None
    valid=np.all(mask[y:y+height]>0,axis=0).astype(np.int8)
    edges=np.diff(np.pad(valid,(1,1)))
    starts=np.flatnonzero(edges==1);ends=np.flatnonzero(edges==-1)
    if not len(starts): return None
    index=np.argmax(ends-starts)
    return int(starts[index]),int(ends[index])

def _balloon_text(mask,text,font):
    width,height=mask.shape[1],mask.shape[0]
    step=int(np.ceil(font.size*1.4))
    for count in range(1,min(80,height//step)+1):
        top=(height-count*step)//2
        remaining=text.strip()
        layout=[]
        for row in range(count):
            span=_span(mask,top+row*step,step)
            if span is None: break
            line,remaining=_take_line(remaining,font,span[1]-span[0])
            if not line: break
            layout.append((span,top+row*step,line))
            if not remaining: break
        if remaining: continue
        overlay=Image.new('RGBA',(width,height))
        draw=ImageDraw.Draw(overlay)
        for (left,right),y,line in layout:
            draw.text(((left+right)/2,y),line,font=font,fill='#171717',anchor='mt')
        ink=np.array(overlay.getchannel('A'))>0
        # Raster check accounts for glyph bearings as well as advance widths.
        if ink.any() and not np.any(ink & (mask==0)):
            return overlay
    return None

def typeset(image,regions,translations):
    result=image.copy()
    draw=ImageDraw.Draw(result)
    overflow=[]
    for region,text in zip(regions,translations,strict=True):
        if text is None:
            continue
        if len(text)>1200:
            raise RuntimeError('번역문이 말풍선에 들어가지 않습니다. 페이지를 나눠 주세요.')
        x1,y1,x2,y2=region.box
        padding=max(2,min(10,int(min(x2-x1,y2-y1)*.08)))
        width,height=x2-x1-2*padding,y2-y1-2*padding
        mask=_region_mask(image,region,padding)
        selected=None
        # A wide balloon must not turn a short sentence into enormous type.
        target=max(14,min(32,round(image.width/40)))
        for size in range(target,max(10,round(target*.75))-1,-1):
            font=ImageFont.truetype(FONT_PATH,size,index=1 if str(FONT_PATH).lower().endswith('.ttc') else 0)
            selected=_balloon_text(mask,text,font)
            if selected is not None: break
        if selected is None:
            # Preserve the complete translation instead of clipping it or failing
            # the whole page when OCR returns a narrow column or a tiny region.
            overflow.append(text)
            if region.polygon:
                draw.line([tuple(p) for p in region.polygon]+[tuple(region.polygon[0])],fill='#97521d',width=1)
            else:
                draw.rectangle((x1,y1,x2-1,y2-1),outline='#97521d',width=1)
            marker=ImageFont.truetype(FONT_PATH,10,index=1 if str(FONT_PATH).lower().endswith('.ttc') else 0)
            label=str(len(overflow))
            if width>=marker.getlength(label) and height>=13:
                label_image=Image.new('RGBA',(x2-x1,y2-y1))
                ImageDraw.Draw(label_image).text(((x2-x1)/2,(y2-y1)/2),label,font=marker,fill='#97521d',anchor='mm')
                ink=np.array(label_image.getchannel('A'))>0
                if not np.any(ink & (mask==0)):
                    result.paste(label_image,(x1,y1),label_image)
            continue
        result.paste(selected,(x1,y1),selected)
    if overflow:
        size=max(12,min(22,image.width//35))
        font=ImageFont.truetype(FONT_PATH,size,index=1 if str(FONT_PATH).lower().endswith('.ttc') else 0)
        step=round(size*1.5)
        lines=_wrap('공간이 부족한 영역의 번역 (위 그림의 번호 순서)',font,image.width-24)
        for number,text in enumerate(overflow,1):
            lines.append('')
            lines.extend(_wrap(f'{number}. {text}',font,image.width-24))
        height=image.height+24+len(lines)*step
        if height*image.width>MAX_PIXELS*2:
            raise RuntimeError('번역문을 표시할 공간이 너무 큽니다. OCR 결과를 확인하거나 페이지를 나눠 주세요.')
        combined=Image.new('RGB',(image.width,height),'#fffaf0')
        combined.paste(result,(0,0))
        notes=ImageDraw.Draw(combined)
        for i,line in enumerate(lines):
            notes.text((12,image.height+12+i*step),line,font=font,fill='#171717',anchor='lt')
        result=combined
    return result
