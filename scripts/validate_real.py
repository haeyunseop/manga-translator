"""Render a real end-to-end output from our original Japanese test artwork."""
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.demo import make_demo
from backend.vision import recognize,translator,clean_image,typeset
from backend.config import MODEL_ID

def main():
    start=time.monotonic()
    out=ROOT/'artifacts';out.mkdir(exist_ok=True)
    image=make_demo();image.save(out/'demo-original.png')
    regions=recognize(image,'horizontal')
    translations=[]
    for region in regions:
        translated=translator.translate(region.text)
        if not any('\uac00'<=char<='\ud7a3' for char in translated):
            raise RuntimeError(f'Model output did not contain Korean: {translated!r}')
        translations.append(translated)
        print(f'{region.text} -> {translated}',flush=True)
    cleaned,mask=clean_image(image,regions)
    cleaned.save(out/'demo-cleaned.png');mask.save(out/'demo-mask.png')
    typeset(cleaned,regions,translations).save(out/'demo-translated.png')
    report={'engine':f'real local {MODEL_ID}','stub':False,'seconds':round(time.monotonic()-start,2),'texts':[{'source':r.text,'translation':t,'ocr_confidence':r.confidence} for r,t in zip(regions,translations,strict=True)]}
    (out/'real-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Full page saved. Elapsed: {report["seconds"]}s',flush=True)

if __name__=='__main__': main()
