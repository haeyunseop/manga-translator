import io
import time
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from backend.app import app,login_attempts
from backend import store,worker

@pytest.fixture
def client():
    login_attempts.clear()
    with TestClient(app) as client: yield client

def login(client):
    r=client.post('/api/login',json={'password':'test-only-password-not-for-deployment'})
    assert r.status_code==200
    return r

def test_auth_protects_jobs_health_and_images(client):
    for url in ['/api/jobs','/api/health','/api/jobs/'+'a'*32+'/pages/0/original','/api/jobs/'+'a'*32+'/diagnostics']:
        assert client.get(url).status_code==401
    assert client.post('/api/jobs/demo').status_code==401

def test_cookie_csrf_logout(client):
    response=login(client)
    assert 'HttpOnly' in response.headers['set-cookie'] and 'SameSite=strict' in response.headers['set-cookie']
    assert client.get('/api/me').status_code==200
    assert client.post('/api/jobs/demo',headers={'Origin':'https://evil.example'}).status_code==403
    assert client.post('/api/logout',headers={'Sec-Fetch-Site':'cross-site'}).status_code==403
    assert client.post('/api/logout').status_code==200
    assert client.get('/api/me').status_code==401

def test_login_rate_limit(client):
    for _ in range(10): assert client.post('/api/login',json={'password':'wrong'}).status_code==401
    assert client.post('/api/login',json={'password':'wrong'}).status_code==429

def test_oversize_body_denied_before_parsing(client):
    assert client.post('/api/login',content='x',headers={'Content-Length':'20000'}).status_code==413

def test_upload_rights_size_and_invalid_image(client):
    login(client)
    bad={'files':('bad.png',b'not an image','image/png')}
    assert client.post('/api/jobs/upload',files=bad).status_code==422
    assert client.post('/api/jobs/upload',files=bad,data={'rights':'true'}).status_code==422
    data=io.BytesIO();Image.new('RGB',(20,20)).save(data,format='PNG')
    assert client.post('/api/jobs/upload',files={'files':('small.png',data.getvalue(),'image/png')},data={'rights':'true'}).status_code==422

def test_unsupported_url_explicit_error(client):
    login(client)
    response=client.post('/api/jobs/url',json={'rights':True,'url':'https://unknown.example/manga'})
    assert response.status_code==422 and '지원하지 않는 사이트' in response.json()['detail']

def test_missing_job_and_path_traversal(client):
    login(client)
    assert client.get('/api/jobs/not-a-job').status_code==404
    assert client.get('/api/jobs/'+'a'*32+'/pages/-1/original').status_code==404

def test_restart_marks_inflight_jobs_as_interrupted():
    job=worker.new_job('upload','auto');job['status']='running';store.initialize();store.save(job)
    store.initialize()
    recovered=store.get(job['id'])
    assert recovered['status']=='error' and '재시작' in recovered['error']

def test_diagnostics_exports_only_selected_job_and_images(client):
    import json,zipfile
    from backend.config import DATA
    login(client)
    job=worker.new_job('upload','auto')
    job.update(status='done',total=1,completed=1,pages=[{'index':0,'status':'ready','texts':[]}])
    folder=DATA/job['id'];folder.mkdir()
    Image.new('RGB',(100,100),'white').save(folder/'0-original.png')
    (folder/'.env').write_text('must-not-export=this-file')
    store.save(job)
    response=client.get(f'/api/jobs/{job["id"]}/diagnostics')
    assert response.status_code==200 and response.headers['content-type']=='application/zip'
    with zipfile.ZipFile(io.BytesIO(response.content)) as bundle:
        assert set(bundle.namelist())=={'diagnostics.json','page-1-original.png'}
        report=json.loads(bundle.read('diagnostics.json'))
        assert report['job']['id']==job['id']
        assert 'MANGATRANS_PASSWORD' not in bundle.read('diagnostics.json').decode()
    assert not list(DATA.glob('diagnostics-*'))
    job['status']='running';store.save(job)
    assert client.get(f'/api/jobs/{job["id"]}/diagnostics').status_code==409
