"""Real OCR/raster checks and explicit translation-output failure detection."""
import cv2
import numpy as np
import pytest
from PIL import Image,ImageDraw
from backend.quality_demo import make_quality_demo,QUALITY_TEXTS
from backend.vision import Region,recognize,typeset,validate_translation,TranslationQualityError

@pytest.mark.parametrize('ruby',[False,True])
def test_vertical_print_ocr_and_reading_order(ruby):
    regions=recognize(make_quality_demo(include_ruby=ruby),'auto')
    assert [r.text for r in regions]==QUALITY_TEXTS
    assert all(r.direction=='vertical' and r.polygon for r in regions)

@pytest.mark.parametrize('output',['이미, '*40,'안녕하세요 여러분. '*12,'','not a Korean translation'])
def test_bad_model_outputs_are_rejected(output):
    with pytest.raises(TranslationQualityError):
        validate_translation('明日は図書館に行きます。',output)

def test_normal_output_is_preserved_exactly():
    text='내일은 도서관에 갈 거야.'
    assert validate_translation('明日は図書館に行きます。',text)==text

def test_ellipse_layout_never_writes_over_art_or_outside_balloon():
    image=Image.new('RGB',(684,400),'#444444')
    draw=ImageDraw.Draw(image)
    draw.ellipse((240,30,440,350),fill='white',outline='black',width=3)
    polygon=cv2.ellipse2Poly((340,190),(95,155),0,0,360,4).tolist()
    region=Region('テスト',95,(240,30,441,351),[],'vertical',polygon)
    output=typeset(image,[region],['이 마을에는 아직 우리가 모르는 이야기가 많이 있어. 새로운 하루를 함께 시작하자.'])
    assert output.size==image.size
    changed=np.any(np.array(output)!=np.array(image),axis=2)
    assert changed.any()
    mask=np.zeros((image.height,image.width),np.uint8)
    cv2.fillPoly(mask,[np.array(polygon)],255)
    mask=cv2.erode(mask,np.ones((7,7),np.uint8))
    assert not np.any(changed & (mask==0))

def test_cleaning_respects_balloon_polygon():
    from backend.vision import clean_image
    image=Image.new('RGB',(160,160),'white')
    draw=ImageDraw.Draw(image)
    draw.rectangle((20,20,140,140),outline='black',width=3)
    draw.rectangle((60,60,90,90),fill='black')
    polygon=[(40,40),(120,40),(120,120),(40,120)]
    region=Region('日本語',95,(10,10,150,150),[(15,15,145,145)],'vertical',polygon)
    cleaned,mask=clean_image(image,[region])
    assert not np.array(mask)[:40].any()
    assert np.array_equal(np.array(cleaned)[:40],np.array(image)[:40])

def test_typeset_skips_untrusted_translation_without_changing_original():
    image=make_quality_demo()
    region=Region('日本語',95,(40,40,200,340),[],'vertical')
    assert np.array_equal(np.array(typeset(image,[region],[None])),np.array(image))

def test_manga_cleanup_removes_ruby_outside_legacy_token_boxes():
    from backend.vision import clean_image
    image=Image.new('RGB',(160,160),'white');draw=ImageDraw.Draw(image)
    draw.rectangle((60,65,80,90),fill='black')
    draw.rectangle((105,45,109,52),fill='black')  # ruby omitted by Tesseract
    draw.rectangle((10,10,25,25),fill='black')   # artwork outside balloon
    region=Region('日本語',90,(35,30,135,140),[(60,65,81,91)],'vertical',[(35,30),(134,30),(134,139),(35,139)],'manga-ocr')
    cleaned,mask=clean_image(image,[region])
    assert np.array(cleaned)[45:53,105:110].mean()>230
    assert np.array(mask)[45:53,105:110].all()
    assert np.array_equal(np.array(cleaned)[10:26,10:26],np.array(image)[10:26,10:26])
