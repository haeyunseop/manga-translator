import logging
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from .config import DATA, MAX_TOTAL_BYTES
from . import store
from .demo import make_demo
from .sources import fetch_public, resolve_source
from .vision import recognize, translator, clean_image, typeset, normalize_image

pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='mangatrans')
slots=threading.BoundedSemaphore(3)
log=logging.getLogger(__name__)

def reserve():
    if not slots.acquire(blocking=False):
        raise ValueError('대기열이 가득 찼습니다. 진행 중인 작업이 끝난 후 다시 시도하세요.')

def new_job(source,direction):
    ident=uuid.uuid4().hex
    return {'id':ident,'title':'나의 만화','source':source,'direction':direction,'created':time.time(),'status':'queued','stage':'대기 중','completed':0,'total':0,'pages':[],'error':None}

def submit(job,images=None,url=None,demo=False):
    try:
        directory=DATA/job['id']
        directory.mkdir(mode=0o700)
        if images:
            for i,image in enumerate(images):
                image.save(directory/f'{i}-original.png')
                job['pages'].append({'index':i,'status':'pending','texts':[]})
            job['total']=len(images)
        store.save(job)
        pool.submit(run,job,url,demo)
    except Exception:
        slots.release()
        raise
    return job

def run(job,url,demo):
    directory=DATA/job['id']
    try:
        job.update(status='running',stage='원본 불러오는 중')
        store.save(job)
        first=None
        urls=[]
        if url:
            manifest,first=resolve_source(url)
            urls=manifest['pages']
            job.update(title=manifest['title'],total=len(urls),pages=[{'index':i,'status':'pending','texts':[]} for i in range(len(urls))])
        if demo:
            make_demo().save(directory/'0-original.png')
            job.update(title='작은 인사 · 자체 제작 테스트',total=1,pages=[{'index':0,'status':'pending','texts':[]}])
        store.save(job)
        used_bytes=0
        for page in job['pages']:
            i=page['index']
            if url:
                job['stage']=f'{i+1}페이지 · 원본 불러오는 중'; store.save(job)
                raw=first if i==0 and first is not None else fetch_public(urls[i])[0]
                used_bytes+=len(raw)
                if used_bytes>MAX_TOTAL_BYTES: raise ValueError('작품 전체의 다운로드 용량이 100MB를 초과했습니다.')
                normalize_image(raw).save(directory/f'{i}-original.png')
            page['status']='processing'
            job['stage']=f'{i+1}페이지 · 일본어 인식'; store.save(job)
            from PIL import Image
            with Image.open(directory/f'{i}-original.png') as im:
                image=im.convert('RGB')
            regions=recognize(image,job['direction'])
            translated=[]
            for n,r in enumerate(regions):
                job['stage']=f'{i+1}페이지 · 번역 {n+1}/{len(regions)}'; store.save(job)
                translated.append(translator.translate(r.text))
            job['stage']=f'{i+1}페이지 · 원문 제거 및 배경 복원'; store.save(job)
            cleaned,mask=clean_image(image,regions)
            job['stage']=f'{i+1}페이지 · 한국어 식자'; store.save(job)
            rendered=typeset(cleaned,regions,translated)
            # Rename atomically: never serve an incompletely written output.
            rendered.save(directory/f'{i}-translated.part',format='PNG')
            (directory/f'{i}-translated.part').replace(directory/f'{i}-translated.png')
            page.update(status='ready',texts=[{**asdict(r),'translation':t} for r,t in zip(regions,translated,strict=True)])
            job['completed']+=1
            store.save(job)
        job.update(status='done',stage='번역 완료')
    except Exception as exc:
        log.exception('Job %s failed',job['id'])
        message=str(exc) if isinstance(exc,(ValueError,RuntimeError)) else '페이지 처리에 실패했습니다. 서버 로그와 설치 상태를 확인하세요.'
        job.update(status='error',stage='처리 중단',error=message[:600])
        for page in job['pages']:
            if page['status']=='processing': page['status']='error'
    finally:
        store.save(job)
        slots.release()
