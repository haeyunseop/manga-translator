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

def test_invalid_translation_keeps_original_balloon_and_reports_review(monkeypatch):
    import numpy as np
    from PIL import Image
    from backend.vision import TranslationQualityError,recognize
    store.initialize()
    image=make_demo()
    first=recognize(image,'horizontal')[0]
    calls=[]
    def stub(text):
        calls.append(text)
        if len(calls)==1:
            raise TranslationQualityError('반복 출력을 감지해 원문을 유지했습니다.')
        return '다른 말풍선은 번역했습니다.'
    monkeypatch.setattr(worker.translator,'translate',stub)
    job=worker.new_job('upload','horizontal')
    worker.reserve();worker.submit(job,images=[image])
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        snapshot=store.get(job['id'])
        if snapshot['status'] not in {'queued','running'}: break
        time.sleep(.05)
    assert snapshot['status']=='done' and '확인' in snapshot['stage']
    page=snapshot['pages'][0]
    assert page['warnings'] and page['texts'][0]['review']
    assert page['texts'][0]['translation']==''
    assert page['texts'][1]['translation']=='다른 말풍선은 번역했습니다.'
    with Image.open(DATA/job['id']/'0-translated.png') as rendered:
        assert np.array_equal(np.array(rendered.crop(first.box)),np.array(image.crop(first.box)))

def test_low_confidence_ocr_is_not_sent_to_translation(monkeypatch):
    import numpy as np
    from PIL import Image
    from backend.vision import Region
    store.initialize()
    image=make_demo()
    region=Region('不確かな文字',35,(400,170,810,360),[(430,210,700,260)],'vertical')
    monkeypatch.setattr(worker,'recognize',lambda *args:[region])
    def unexpected(_):
        raise AssertionError('Low confidence OCR must not be translated')
    monkeypatch.setattr(worker.translator,'translate',unexpected)
    job=worker.new_job('upload','auto')
    worker.reserve();worker.submit(job,images=[image])
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        snapshot=store.get(job['id'])
        if snapshot['status'] not in {'queued','running'}: break
        time.sleep(.05)
    assert snapshot['status']=='done'
    assert 'OCR 신뢰도' in snapshot['pages'][0]['warnings'][0]
    with Image.open(DATA/job['id']/'0-translated.png') as rendered:
        assert np.array_equal(np.array(rendered),np.array(image))
