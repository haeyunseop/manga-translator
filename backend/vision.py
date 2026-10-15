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

def tess_config(psm):
    return f'--tessdata-dir "{MODELS / "tessdata"}" --psm {psm}'

def _read_region(image, box, direction, psm, isolation=None):
    crop=image.crop(box)
    if isolation is not None:
        pixels=np.array(crop)
        pixels[isolation==0]=255
        crop=Image.fromarray(pixels)
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
        ink.append((box[0]+x,box[1]+y,box[0]+x+w,box[1]+y+h))
    return Region(text,round(sum(c for _,_,c in words)/len(words),1),box,ink,direction)

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
            results.append(max(choices,key=lambda r: r.confidence))
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
                generated=self.model.generate(**encoded,forced_bos_token_id=target,max_new_tokens=256,max_length=None,num_beams=4)
            eos=self.model.generation_config.eos_token_id
            end_tokens=eos if isinstance(eos,list) else [eos]
            if generated[0,-1].item() not in end_tokens:
                raise RuntimeError('번역이 길이 한도에서 중단되었습니다. 이미지를 나눠 주세요.')
            result=self.tokenizer.batch_decode(generated,skip_special_tokens=True)[0].strip()
            if not result:
                raise RuntimeError('모델이 빈 번역을 반환했습니다.')
            if JP.search(text) and not re.search(r'[가-힣]',result):
                raise RuntimeError('모델의 출력에서 한국어를 확인하지 못했습니다. 원문 인식 결과를 확인하세요.')
            return result

translator=LocalTranslator()

def clean_image(image,regions):
    pixels=np.array(image)
    gray=cv2.cvtColor(pixels,cv2.COLOR_RGB2GRAY)
    mask=np.zeros(gray.shape,dtype=np.uint8)
    for r in regions:
        # Include gaps between OCR words: low-confidence glyphs can be omitted by TSV.
        # Mask all ink inside the recognized text envelope, not only accepted word boxes.
        envelope=(min(b[0] for b in r.ink_boxes),min(b[1] for b in r.ink_boxes),max(b[2] for b in r.ink_boxes),max(b[3] for b in r.ink_boxes))
        for x1,y1,x2,y2 in [envelope]:
            x1,y1=max(0,x1-2),max(0,y1-2)
            x2,y2=min(image.width,x2+2),min(image.height,y2+2)
            mask[y1:y2,x1:x2]=np.maximum(mask[y1:y2,x1:x2],(gray[y1:y2,x1:x2]<210).astype('uint8')*255)
    mask=cv2.dilate(mask,np.ones((3,3),np.uint8),iterations=1)
    return Image.fromarray(cv2.inpaint(pixels,mask,3,cv2.INPAINT_TELEA)),Image.fromarray(mask)

def _wrap(text,font,width):
    lines=[]
    line=''
    for char in text:
        if char=='\n':
            lines.append(line); line=''; continue
        if font.getlength(line+char)>width and line:
            lines.append(line.rstrip()); line=char.lstrip()
        else: line+=char
    if line: lines.append(line.rstrip())
    return lines

def typeset(image,regions,translations):
    result=image.copy()
    draw=ImageDraw.Draw(result)
    for region,text in zip(regions,translations,strict=True):
        if len(text)>1200:
            raise RuntimeError('번역문이 말풍선에 들어가지 않습니다. 페이지를 나눠 주세요.')
        x1,y1,x2,y2=region.box
        width,height=x2-x1-20,y2-y1-20
        selected=None
        for size in range(min(48,int(height*.7)),11,-1):
            font=ImageFont.truetype(FONT_PATH,size,index=1 if str(FONT_PATH).lower().endswith('.ttc') else 0)
            lines=_wrap(text,font,width)
            step=size*1.45
            if lines and len(lines)*step<=height:
                selected=(font,lines,step); break
        if selected is None:
            raise RuntimeError('번역문이 말풍선에 들어가지 않습니다. OCR 결과와 이미지를 확인하세요.')
        font,lines,step=selected
        cy=(y1+y2)/2-len(lines)*step/2
        for line in lines:
            draw.text(((x1+x2)/2,cy),line,font=font,fill='#171717',anchor='mt',stroke_width=0)
            cy+=step
    return result
