"""Local Japanese manga transcription, using the official Apache-2.0 weights.

Tesseract still proposes balloon regions. This model reads each full region rather
than stitching Tesseract's individual glyph guesses into the translation input.
"""
import re
import os
import threading
import cv2
import numpy as np
from PIL import Image
from .config import MANGA_OCR_PATH

class MangaOCR:
    def __init__(self):
        self.model=None
        self.processor=None
        self.tokenizer=None
        self.lock=threading.Lock()

    def ready(self):
        return all((MANGA_OCR_PATH/name).is_file() for name in ['config.json','pytorch_model.bin','preprocessor_config.json','vocab.txt','tokenizer_config.json'])

    def read(self,image,region):
        if not self.ready():
            raise RuntimeError('만화 OCR 모델이 없습니다. 업데이트 도우미로 무료 모델을 먼저 준비하세요.')
        import torch
        from transformers import VisionEncoderDecoderModel,ViTImageProcessorPil,AutoTokenizer
        with self.lock:
            torch.set_num_threads(min(4,os.cpu_count() or 1))
            if self.model is None:
                self.model=VisionEncoderDecoderModel.from_pretrained(MANGA_OCR_PATH,local_files_only=True).eval()
                self.processor=ViTImageProcessorPil.from_pretrained(MANGA_OCR_PATH,local_files_only=True)
                # OCR only decodes IDs; Japanese word segmentation is unnecessary
                # and would otherwise add MeCab/fugashi installation requirements.
                self.tokenizer=AutoTokenizer.from_pretrained(MANGA_OCR_PATH,local_files_only=True,do_word_tokenize=False)
            crop=image.crop(region.box).convert('RGB')
            if region.polygon:
                x,y=region.box[:2]
                mask=np.zeros((crop.height,crop.width),np.uint8)
                cv2.fillPoly(mask,[np.array(region.polygon,dtype=np.int32)-[x,y]],255)
                pixels=np.array(crop);pixels[mask==0]=255
                crop=Image.fromarray(pixels)
            values=self.processor(images=crop.convert('L').convert('RGB'),return_tensors='pt').pixel_values
            with torch.inference_mode():
                generated=self.model.generate(values,max_new_tokens=256,max_length=None)
            eos=self.model.generation_config.eos_token_id
            terminal=eos if isinstance(eos,list) else [eos]
            if generated[0,-1].item() not in terminal:
                raise ValueError('만화 OCR 출력이 중단되어 원문을 유지했습니다.')
            text=re.sub(r'\s+','',self.tokenizer.decode(generated[0],skip_special_tokens=True))
            if not re.search(r'[\u3040-\u30ff\u3400-\u9fff]',text) or len(text)>500:
                raise ValueError('만화 OCR의 일본어 문장을 확인하지 못해 원문을 유지했습니다.')
            return text

manga_reader=MangaOCR()
