"""Pinned, checksum-verified manga OCR and quantized CPU translation artifacts."""
from pathlib import Path
import hashlib
import json
import os
import platform
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.setdefault('HF_HOME',str(ROOT/'models/.hf-cache'))
os.environ['HF_HUB_DISABLE_XET']='1'
from backend.config import MODELS,MANGA_OCR_ID,MANGA_OCR_REVISION,MANGA_OCR_PATH,QWEN_REVISION,QWEN_FILE,QWEN_SHA256,LLAMA_PATH,LLAMA_RELEASE
from huggingface_hub import HfApi,hf_hub_download

def digest(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file,'sha256').hexdigest()

def download_manga():
    required={'config.json','pytorch_model.bin','preprocessor_config.json','tokenizer_config.json','vocab.txt','special_tokens_map.json'}
    MANGA_OCR_PATH.mkdir(parents=True,exist_ok=True)
    info=HfApi().model_info(MANGA_OCR_ID,revision=MANGA_OCR_REVISION,files_metadata=True)
    hashes={}
    for item in info.siblings:
        if item.rfilename not in required|{'README.md'}: continue
        path=Path(hf_hub_download(MANGA_OCR_ID,item.rfilename,revision=MANGA_OCR_REVISION,local_dir=MANGA_OCR_PATH))
        actual=digest(path)
        if item.lfs and actual!=item.lfs.sha256:
            path.unlink();raise RuntimeError('Manga OCR checksum mismatch; file removed.')
        hashes[item.rfilename]=actual
        print('Manga OCR verified:',item.rfilename,flush=True)
    if not required.issubset(hashes): raise RuntimeError('Manga OCR artifacts are incomplete.')
    (MANGA_OCR_PATH/'provenance.json').write_text(json.dumps({'model':MANGA_OCR_ID,'revision':MANGA_OCR_REVISION,'license':'apache-2.0','sha256':hashes},indent=2),encoding='utf-8')

def download_quantized():
    repo='unsloth/Qwen3-4B-Instruct-2507-GGUF'
    folder=MODELS/'Qwen3-4B-Instruct-2507-GGUF'
    folder.mkdir(parents=True,exist_ok=True)
    path=Path(hf_hub_download(repo,QWEN_FILE,revision=QWEN_REVISION,local_dir=folder))
    actual=digest(path)
    if actual!=QWEN_SHA256:
        path.unlink();raise RuntimeError('Quantized model checksum mismatch; file removed.')
    (folder/'provenance.json').write_text(json.dumps({'model':repo,'upstream':'Qwen/Qwen3-4B-Instruct-2507','quantization':'Unsloth Q4_K_M','revision':QWEN_REVISION,'license':'apache-2.0','sha256':{QWEN_FILE:actual}},indent=2),encoding='utf-8')
    print('Qwen3 4B Q4_K_M verified.',flush=True)

def download_runtime():
    if platform.machine().lower() not in {'amd64','x86_64'}:
        raise RuntimeError('The bundled CPU runtime supports Windows/Linux x64 only.')
    if sys.platform=='win32':
        name=f'llama-{LLAMA_RELEASE}-bin-win-cpu-x64.zip'
        expected='1283323272b04cd07905816a597a0da810918102de958f4ff6f7bbaa70ed2efe'
    elif sys.platform.startswith('linux'):
        name=f'llama-{LLAMA_RELEASE}-bin-ubuntu-x64.tar.gz'
        expected='f6d25dde8f51133143d1453da4fd5f73b145127177612a283bf7995957af3392'
    else:
        raise RuntimeError('The bundled CPU runtime supports Windows/Linux x64 only.')
    url=f'https://github.com/ggml-org/llama.cpp/releases/download/{LLAMA_RELEASE}/{name}'
    LLAMA_PATH.mkdir(parents=True,exist_ok=True)
    archive=LLAMA_PATH/name
    if not archive.exists() or digest(archive)!=expected:
        partial=archive.with_name(name+'.part')
        urllib.request.urlretrieve(url,partial)
        if digest(partial)!=expected:
            partial.unlink();raise RuntimeError('Official CPU runtime checksum mismatch; file removed.')
        partial.replace(archive)
    with tempfile.TemporaryDirectory(prefix='extract-',dir=LLAMA_PATH) as directory:
        stage=Path(directory)
        if name.endswith('.zip'):
            with zipfile.ZipFile(archive) as bundle:
                for item in bundle.infolist():
                    if not (stage/item.filename).resolve().is_relative_to(stage.resolve()):
                        raise RuntimeError('Unsafe runtime archive member.')
                bundle.extractall(stage)
        else:
            with tarfile.open(archive) as bundle:
                bundle.extractall(stage,filter='data')
        for source in stage.rglob('*'):
            target=LLAMA_PATH/source.relative_to(stage)
            if source.is_symlink():
                if target.is_symlink() and os.readlink(target)==os.readlink(source): continue
                target.parent.mkdir(parents=True,exist_ok=True)
                source.replace(target)
            elif source.is_dir():
                target.mkdir(parents=True,exist_ok=True)
            else:
                # Do not rewrite identical executable/DLL files in use. On Linux
                # direct writes fail with ETXTBSY; Windows also locks running DLLs.
                if target.is_file() and digest(target)==digest(source): continue
                target.parent.mkdir(parents=True,exist_ok=True)
                source.replace(target)
    (LLAMA_PATH/'provenance.json').write_text(json.dumps({'repository':'ggml-org/llama.cpp','release':LLAMA_RELEASE,'url':url,'sha256':expected,'license':'MIT'},indent=2),encoding='utf-8')
    print('Official llama.cpp CPU runtime verified.',flush=True)

if __name__=='__main__':
    try:
        from download_models import download_ocr
        download_ocr()
        download_manga()
        download_quantized()
        download_runtime()
    except Exception as exc:
        print(f'Quality model setup failed ({type(exc).__name__}). Check disk space and access to Hugging Face and official GitHub releases. Existing settings were not changed.',file=sys.stderr)
        raise SystemExit(1) from None
