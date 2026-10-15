"""Fetch official model artifacts with revision pinning and SHA-256 validation.

Run once online, then all image/text inference is local. No paid API, no auth tokens.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.setdefault('HF_HOME',str(ROOT/'models/.hf-cache'))
os.environ.setdefault('HF_HUB_DISABLE_XET','1')
from backend.config import MODELS, MODEL_ID, MODEL_PATH, MODEL_KIND
from huggingface_hub import HfApi, hf_hub_download

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def download_ocr():
    # Immutable upstream revision with checksums recorded from verified official HTTPS downloads.
    repo='https://github.com/tesseract-ocr/tessdata_fast.git'
    sha='87416418657359cb625c412a48b6e1d6d41c29bd'
    expected={'jpn.traineddata':'1f5de9236d2e85f5fdf4b3c500f2d4926f8d9449f28f5394472d9e8d83b91b4d','jpn_vert.traineddata':'bf1e2640954691797e2dc14f38533e601b59ee37958698ae0f0b81dc6f09c71b'}
    folder=MODELS/'tessdata'; folder.mkdir(parents=True,exist_ok=True)
    for name in ['jpn.traineddata','jpn_vert.traineddata']:
        url=f'https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/{sha}/{name}'
        temp=folder/f'{name}.part'
        urllib.request.urlretrieve(url,temp)
        checksum=digest(temp)
        if checksum!=expected[name]:
            temp.unlink()
            raise RuntimeError(f'SHA-256 mismatch: {name}')
        temp.replace(folder/name)
        print(f'OCR ready: {name} ({checksum[:12]})')
    (folder/'provenance.json').write_text(json.dumps({'repository':repo,'revision':sha,'sha256':{n:digest(folder/n) for n in ['jpn.traineddata','jpn_vert.traineddata']}},indent=2),encoding='utf-8')

def download_translation():
    MODEL_PATH.mkdir(parents=True,exist_ok=True)
    provenance=MODEL_PATH/'provenance.json'
    previous=json.loads(provenance.read_text(encoding='utf-8')) if provenance.exists() else None
    api=HfApi()
    info=api.model_info(MODEL_ID,revision=previous['revision'] if previous else 'main',files_metadata=True)
    keep={'config.json','generation_config.json','vocab.json','sentencepiece.bpe.model','tokenizer_config.json','special_tokens_map.json','pytorch_model.bin','tokenizer.json','README.md'}
    hashes={}
    for item in info.siblings:
        if item.rfilename not in keep: continue
        path=Path(hf_hub_download(MODEL_ID,item.rfilename,revision=info.sha,local_dir=MODEL_PATH))
        actual=digest(path)
        if item.lfs and actual!=item.lfs.sha256:
            path.unlink()
            raise RuntimeError(f'SHA-256 mismatch: {item.rfilename}; artifact removed')
        hashes[item.rfilename]=actual
        print(f'Model verified: {item.rfilename}')
    required={'pytorch_model.bin','config.json','sentencepiece.bpe.model','tokenizer_config.json'}
    if MODEL_KIND=='m2m100': required.add('vocab.json')
    if not required.issubset(hashes):
        raise RuntimeError('Required official model artifacts are missing.')
    provenance.write_text(json.dumps({'model':MODEL_ID,'revision':info.sha,'license':getattr(info.card_data,'license',None),'sha256':hashes},indent=2),encoding='utf-8')
    print('Translation model ready; subsequent inference uses local files only.')

if __name__=='__main__':
    try:
        download_ocr()
        if '--ocr-only' not in sys.argv: download_translation()
    except Exception as exc:
        # Hub errors can contain temporary signed CDN URLs. Do not dump them in logs.
        print(f'Download failed ({type(exc).__name__}). Check access to huggingface.co and us.aws.cdn.hf.co, free disk space, and official artifact checksums. No paid fallback was used.',file=sys.stderr)
        raise SystemExit(1) from None
