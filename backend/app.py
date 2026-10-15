import hashlib
import hmac
import os
import re
import shutil
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import FileResponse, JSONResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from pydantic import BaseModel, Field
from .config import DATA, MODELS, MAX_PAGES, MAX_IMAGE_BYTES, MAX_TOTAL_BYTES, FONT_PATH, MODEL_KIND
from . import store, worker
from .vision import normalize_image, translator
from .sources import allowed_hosts

password=os.getenv('MANGATRANS_PASSWORD','')
session_key=os.getenv('MANGATRANS_SESSION_SECRET','')
secure=os.getenv('MANGATRANS_SECURE_COOKIE','false').lower()=='true'
signer=URLSafeTimedSerializer(session_key,salt='mangatrans-session-v1')
login_attempts=defaultdict(deque)
attempt_lock=threading.Lock()

@asynccontextmanager
async def lifespan(app):
    if len(password)<16 or len(session_key)<32:
        raise RuntimeError('16자 이상의 MANGATRANS_PASSWORD와 32자 이상의 MANGATRANS_SESSION_SECRET을 설정하세요. python scripts/init_env.py로 생성할 수 있습니다.')
    store.initialize()
    yield

app=FastAPI(title='MangaTrans',docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)

@app.middleware('http')
async def guard(request,call_next):
    if request.method not in ('GET','HEAD','OPTIONS'):
        # Reject unknown-length body streams before multipart parsing; uploads must be bounded.
        if request.url.path in {'/api/login','/api/jobs/upload','/api/jobs/url'}:
            try:
                length=int(request.headers.get('content-length','-1'))
            except ValueError:
                return JSONResponse({'detail':'Content-Length가 올바르지 않습니다.'},status_code=400)
            limit=MAX_TOTAL_BYTES+1024*1024 if request.url.path=='/api/jobs/upload' else 16*1024
            if length<0: return JSONResponse({'detail':'요청의 Content-Length가 필요합니다.'},status_code=411)
            if length>limit: return JSONResponse({'detail':'요청 크기 제한을 초과했습니다.'},status_code=413)
        origin=request.headers.get('origin')
        host=request.headers.get('host','')
        configured={'http://127.0.0.1:3000','http://localhost:3000'} | {v.strip() for v in os.getenv('MANGATRANS_ORIGINS','').split(',') if v.strip()}
        if request.headers.get('sec-fetch-site')=='cross-site' or (origin and origin not in configured and urlsplit(origin).netloc!=host):
            return JSONResponse({'detail':'다른 사이트에서의 요청은 허용하지 않습니다.'},status_code=403)
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    return response

def authenticated(request: Request):
    cookie=request.cookies.get('mangatrans_session','')
    try:
        value=signer.loads(cookie,max_age=7*86400)
        expected=hashlib.sha256(password.encode()).hexdigest()
        if not isinstance(value,dict) or not hmac.compare_digest(value.get('account',''),expected): raise BadSignature('account')
    except (BadSignature,SignatureExpired):
        raise HTTPException(401,'로그인이 필요합니다.')

class Login(BaseModel):
    password: str=Field(max_length=256)

@app.post('/api/login')
def login(body:Login,request:Request):
    # Backend is only exposed through loopback Next.js proxy. Use a global bucket so spoofed IP headers cannot evade limits.
    now=time.monotonic()
    with attempt_lock:
        bucket=login_attempts['global']
        while bucket and bucket[0]<now-300: bucket.popleft()
        if len(bucket)>=10: raise HTTPException(429,'로그인 시도가 많습니다. 5분 뒤 다시 시도하세요.')
        bucket.append(now)
    if not hmac.compare_digest(body.password.encode(),password.encode()):
        raise HTTPException(401,'비밀번호가 맞지 않습니다.')
    response=JSONResponse({'ok':True})
    response.set_cookie('mangatrans_session',signer.dumps({'account':hashlib.sha256(password.encode()).hexdigest()}),httponly=True,secure=secure,samesite='strict',max_age=7*86400,path='/')
    return response

@app.post('/api/logout')
def logout():
    response=JSONResponse({'ok':True}); response.delete_cookie('mangatrans_session',path='/'); return response

@app.get('/api/me',dependencies=[Depends(authenticated)])
def me(): return {'authenticated':True}

@app.get('/api/health',dependencies=[Depends(authenticated)])
def health():
    import shutil
    return {'ocr':bool(shutil.which('tesseract')) and all((MODELS/f'tessdata/{lang}.traineddata').exists() for lang in ['jpn','jpn_vert']), 'translation':translator.ready(),'font':Path(FONT_PATH).is_file(),'engine':f'Tesseract · {"NLLB 600M" if MODEL_KIND=="nllb" else "M2M100 418M"} · OpenCV','supported_hosts':sorted(allowed_hosts())}

@app.get('/api/jobs',dependencies=[Depends(authenticated)])
def jobs(): return store.recent()

def checked_job(ident):
    if not re.fullmatch(r'[0-9a-f]{32}',ident): raise HTTPException(404,'작업을 찾을 수 없습니다.')
    job=store.get(ident)
    if not job: raise HTTPException(404,'작업을 찾을 수 없습니다.')
    return job

@app.get('/api/jobs/{ident}',dependencies=[Depends(authenticated)])
def job(ident:str): return checked_job(ident)

def direction_check(direction):
    if direction not in {'auto','horizontal','vertical'}: raise HTTPException(422,'글 방향이 올바르지 않습니다.')

@app.post('/api/jobs/upload',dependencies=[Depends(authenticated)])
async def upload(files:list[UploadFile]=File(...),rights:bool=Form(False),direction:str=Form('auto')):
    if not rights: raise HTTPException(422,'이용 권한 확인이 필요합니다.')
    direction_check(direction)
    if not 1<=len(files)<=MAX_PAGES: raise HTTPException(422,f'한 번에 1~{MAX_PAGES}페이지를 선택하세요.')
    try: worker.reserve()
    except ValueError as exc: raise HTTPException(429,str(exc))
    submitted=False
    try:
        images=[]; total=0
        for file in files:
            raw=await file.read(MAX_IMAGE_BYTES+1)
            total+=len(raw)
            if len(raw)>MAX_IMAGE_BYTES or total>MAX_TOTAL_BYTES: raise ValueError('페이지당 15MB, 전체 100MB까지 지원합니다.')
            images.append(normalize_image(raw))
        job=worker.new_job('upload',direction)
        job['title']=Path(files[0].filename or '업로드한 만화').stem[:100]
        submitted=True
        return worker.submit(job,images=images)
    except ValueError as exc: raise HTTPException(422,str(exc))
    finally:
        if not submitted: worker.slots.release()
        for file in files: await file.close()

class URLJob(BaseModel):
    url:str=Field(min_length=1,max_length=2048)
    rights:bool=False
    direction:str='auto'

@app.post('/api/jobs/url',dependencies=[Depends(authenticated)])
def url_job(body:URLJob):
    if not body.rights: raise HTTPException(422,'이용 권한 확인이 필요합니다.')
    direction_check(body.direction)
    try:
        from .sources import validate_url
        validate_url(body.url)
    except ValueError as exc: raise HTTPException(422,str(exc))
    try: worker.reserve()
    except ValueError as exc: raise HTTPException(429,str(exc))
    return worker.submit(worker.new_job('url',body.direction),url=body.url)

@app.post('/api/jobs/demo',dependencies=[Depends(authenticated)])
def demo():
    try: worker.reserve()
    except ValueError as exc: raise HTTPException(429,str(exc))
    return worker.submit(worker.new_job('demo','horizontal'),demo=True)

@app.get('/api/jobs/{ident}/pages/{index}/{variant}',dependencies=[Depends(authenticated)])
def page_image(ident:str,index:int,variant:str):
    job=checked_job(ident)
    if variant not in {'original','translated'} or not 0<=index<job['total']: raise HTTPException(404,'페이지를 찾을 수 없습니다.')
    path=DATA/ident/f'{index}-{variant}.png'
    if not path.is_file(): raise HTTPException(404,'아직 준비되지 않은 페이지입니다.')
    return FileResponse(path,media_type='image/png',headers={'Cache-Control':'no-store'})

@app.delete('/api/jobs/{ident}',dependencies=[Depends(authenticated)])
def delete_job(ident:str):
    job=checked_job(ident)
    if job['status'] in ('queued','running'): raise HTTPException(409,'진행 중인 작업은 완료된 후 삭제할 수 있습니다.')
    shutil.rmtree(DATA/ident,ignore_errors=False)
    with store.connect() as db: db.execute('DELETE FROM jobs WHERE id=?',(ident,))
    return {'ok':True}
