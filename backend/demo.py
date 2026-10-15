"""Original, generated test artwork. No third-party manga or translation fixtures."""
from PIL import Image, ImageDraw, ImageFont
from .config import FONT_PATH

def make_demo():
    image = Image.new('RGB', (900, 1280), '#f5f2ed')
    d = ImageDraw.Draw(image)
    title_font = ImageFont.truetype(FONT_PATH, 25, index=0)
    d.text((40, 23), 'MangaTrans · original test page', font=title_font, fill='#333333')
    for y, text in [(85, 'こんにちは。'), (680, 'ありがとう。')]:
        d.rectangle((35, y, 865, y+550), fill='#dededc', outline='black', width=5)
        # Stylized original character and background, with enclosed white speech balloon.
        for x in range(60, 850, 75):
            d.line((x, y+25, x-25, y+525), fill='#bcbcbc', width=2)
        d.ellipse((110,y+170,350,y+410), fill='white', outline='black', width=6)
        d.polygon([(108,y+260),(140,y+145),(215,y+170),(270,y+140),(355,y+265),(310,y+220),(270,y+250),(220,y+210),(160,y+245)], fill='#333333', outline='black')
        d.line((165,y+298,190,y+298), fill='black', width=5)
        d.line((265,y+298,290,y+298), fill='black', width=5)
        d.arc((205,y+315,255,y+350),0,180,fill='black',width=4)
        d.polygon([(160,y+410),(300,y+410),(355,y+540),(90,y+540)], fill='white', outline='black', width=5)
        d.ellipse((385,y+75,825,y+295), fill='white', outline='black', width=5)
        d.polygon([(430,y+275),(400,y+340),(490,y+290)], fill='white')
        font=ImageFont.truetype(FONT_PATH, 46, index=0)
        box=d.textbbox((0,0),text,font=font)
        d.text((605-(box[2]-box[0])/2,y+145),text,font=font,fill='black')
    return image
