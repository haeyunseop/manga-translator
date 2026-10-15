"""Queue/progressive delivery tests use an explicitly stubbed translator.

These validate scheduling and storage, not machine translation quality. The separate
real_model test is the only inference test and skips if official weights are absent.
"""
import threading
import time
from backend import worker,store
from backend.config import DATA
from backend.demo import make_demo

def test_first_page_published_while_second_page_is_still_running(monkeypatch):
    waiting=threading.Event();release=threading.Event();calls=[]
    def stub(text):
        calls.append(text)
        if len(calls)==3:
            waiting.set()
            assert release.wait(10)
        return '테스트용 식자 문자열'
    monkeypatch.setattr(worker.translator,'translate',stub)
    job=worker.new_job('upload','horizontal')
    worker.reserve()
    worker.submit(job,images=[make_demo(),make_demo()])
    try:
        assert waiting.wait(15)
        snapshot=store.get(job['id'])
        assert snapshot['status']=='running' and snapshot['completed']==1
        assert snapshot['pages'][0]['status']=='ready'
        assert (DATA/job['id']/'0-translated.png').is_file()
        assert not (DATA/job['id']/'1-translated.png').exists()
    finally: release.set()
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        snapshot=store.get(job['id'])
        if snapshot['status'] not in {'queued','running'}: break
        time.sleep(.05)
    assert snapshot['status']=='done' and snapshot['completed']==2

def test_url_manifest_connects_multiple_pages_to_worker(monkeypatch):
    import io
    raw=io.BytesIO();make_demo().save(raw,format='PNG')
    urls=['https://owned.example/01.png','https://owned.example/02.png']
    fetched=[]
    monkeypatch.setattr(worker,'resolve_source',lambda _:({'title':'Authorized chapter','pages':urls},None))
    def fetch(url): fetched.append(url); return raw.getvalue(),'image/png'
    monkeypatch.setattr(worker,'fetch_public',fetch)
    monkeypatch.setattr(worker.translator,'translate',lambda _: '테스트용 식자 문자열')
    job=worker.new_job('url','horizontal');worker.reserve();worker.submit(job,url='https://owned.example/chapter.json')
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        snapshot=store.get(job['id'])
        if snapshot['status'] not in {'queued','running'}: break
        time.sleep(.05)
    assert fetched==urls and snapshot['completed']==2 and snapshot['status']=='done'
