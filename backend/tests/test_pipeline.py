import numpy as np
import pytest
from PIL import Image
from backend.demo import make_demo
from backend.vision import recognize,clean_image,typeset,translator

def test_actual_japanese_ocr_and_art_preserving_cleanup():
    image=make_demo()
    regions=recognize(image,'horizontal')
    assert [r.text for r in regions]==['こんにちは。','ありがとう。']
    assert min(r.confidence for r in regions)>80
    cleaned,mask=clean_image(image,regions)
    before=np.array(image);after=np.array(cleaned)
    # Text is removed while pixels outside the inpaint mask are exactly preserved.
    selected=np.array(mask)>0
    assert selected.sum()>1000
    assert np.array_equal(before[~selected],after[~selected])
    assert np.mean(after[selected])>230
    assert np.mean(before[selected])<150
    for region in regions:
        x1=min(b[0] for b in region.ink_boxes); x2=max(b[2] for b in region.ink_boxes)
        y1=min(b[1] for b in region.ink_boxes); y2=max(b[3] for b in region.ink_boxes)
        assert (after[y1:y2,x1:x2].mean(axis=2)<150).sum()==0

def test_blank_page_fails_instead_of_inventing_text():
    with pytest.raises(RuntimeError,match='인식하지 못했습니다'):
        recognize(Image.new('RGB',(500,700),'white'),'horizontal')

def test_text_does_not_silently_overflow():
    regions=recognize(make_demo(),'horizontal')
    with pytest.raises(RuntimeError,match='들어가지 않습니다'):
        typeset(make_demo(),regions,['너무 긴 문장 '*10000,'테스트'])

@pytest.mark.real_model
def test_real_japanese_to_korean_pipeline(tmp_path):
    if not translator.ready(): pytest.skip('Real local model weights not installed; this is not a translation pass.')
    image=make_demo();regions=recognize(image,'horizontal')
    results=[translator.translate(r.text) for r in regions]
    for result in results:
        assert any('\uac00'<=c<='\ud7a3' for c in result),result
    cleaned,_=clean_image(image,regions)
    output=typeset(cleaned,regions,results)
    output.save(tmp_path/'translated.png')
    assert output.size==image.size and not np.array_equal(np.array(output),np.array(image))
    print('ACTUAL MODEL OUTPUT:',results)

@pytest.mark.real_model
def test_real_two_page_upload_and_authenticated_images():
    if not translator.ready(): pytest.skip('Real local model weights not installed; not a translation pass.')
    import io
    import time
    from fastapi.testclient import TestClient
    from backend.app import app,login_attempts
    raw=io.BytesIO();make_demo().save(raw,format='PNG')
    login_attempts.clear()
    with TestClient(app) as client:
        assert client.post('/api/login',json={'password':'test-only-password-not-for-deployment'}).status_code==200
        response=client.post('/api/jobs/upload',files=[('files',('01.png',raw.getvalue(),'image/png')),('files',('02.png',raw.getvalue(),'image/png'))],data={'rights':'true','direction':'horizontal'})
        assert response.status_code==200,response.text
        ident=response.json()['id']
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            job=client.get(f'/api/jobs/{ident}').json()
            if job['status'] not in {'queued','running'}: break
            time.sleep(.1)
        assert job['status']=='done',job.get('error')
        assert job['completed']==2 and len(job['pages'])==2
        for page in job['pages']:
            assert page['status']=='ready' and len(page['texts'])==2
            for text in page['texts']:
                assert any('\uac00'<=c<='\ud7a3' for c in text['translation'])
            image=client.get(f'/api/jobs/{ident}/pages/{page["index"]}/translated')
            assert image.status_code==200
            with Image.open(io.BytesIO(image.content)) as rendered:
                assert rendered.size==(900,1280)
        client.cookies.clear()
        assert client.get(f'/api/jobs/{ident}/pages/0/translated').status_code==401
