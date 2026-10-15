"""Run real vertical OCR and inference; keep the complete diagnostic output locally."""
from pathlib import Path
import sys
import json

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.quality_demo import make_quality_demo,QUALITY_TEXTS
from backend.vision import recognize,translator,clean_image,typeset
from backend.config import MODEL_ID,OCR_KIND

def main():
    out=ROOT/'artifacts';out.mkdir(exist_ok=True)
    original=make_quality_demo(include_ruby=True)
    original.save(out/'quality-original.png')
    regions=recognize(original,'auto')
    if [region.text for region in regions]!=QUALITY_TEXTS:
        raise RuntimeError(f'Vertical OCR differs from the original fixture: {[r.text for r in regions]}')
    translated=[]
    for region in regions:
        translation=translator.translate(region.text)
        translated.append(translation)
        print(f'{region.text} -> {translation}',flush=True)
    cleaned,mask=clean_image(original,regions)
    rendered=typeset(cleaned,regions,translated)
    cleaned.save(out/'quality-cleaned.png')
    rendered.save(out/'quality-translated.png')
    report={'fixture':'original vertical-print illustration, not the user-uploaded page','real_model':True,'model':MODEL_ID,'ocr':OCR_KIND,'sources':[r.text for r in regions],'translations':translated,'directions':[r.direction for r in regions],'page_notes':rendered.height>original.height}
    (out/'quality-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Rendered:',rendered.size,'Page notes:',report['page_notes'])

if __name__=='__main__': main()
