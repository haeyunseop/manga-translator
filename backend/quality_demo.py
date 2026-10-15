"""Original multi-balloon vertical-print fixture; not a third-party manga page."""
from PIL import Image,ImageDraw,ImageFont
from .config import FONT_PATH

QUALITY_TEXTS=[
    'この町にはまだ知らない物語がたくさんある。',
    '明日は図書館で友達と会います。',
    '新しい一日をここから始めよう。',
]

def make_quality_demo(include_ruby=False):
    image=Image.new('RGB',(684,900),'#555555')
    draw=ImageDraw.Draw(image)
    font=ImageFont.truetype(FONT_PATH,17,index=0)
    dialogues=[
        (['新しい一日を','ここから始めよう。'],(45,40,205,340)),
        (['明日は図書館で','友達と会います。'],(245,40,420,340)),
        (['この町にはまだ','知らない物語が','たくさんある。'],(460,40,635,340)),
    ]
    # Background and a simple original character provide non-text line art.
    for x in range(20,684,40):
        draw.line((x,360,x-15,880),fill='#999999',width=2)
    draw.ellipse((230,450,450,680),fill='white',outline='black',width=4)
    draw.arc((265,520,415,630),0,180,fill='black',width=4)
    draw.line((280,520,300,520),fill='black',width=4)
    draw.line((380,520,400,520),fill='black',width=4)
    for columns,box in dialogues:
        draw.ellipse(box,fill='white',outline='black',width=2)
        x=box[2]-43
        for column in columns:
            y=box[1]+62
            for char in column:
                draw.text((x,y),char,font=font,fill='black',anchor='lt')
                y+=21
            x-=30
    if include_ruby:
        ruby=ImageFont.truetype(FONT_PATH,7,index=0)
        for i,char in enumerate('としょかん'):
            draw.text((398,167+i*9),char,font=ruby,fill='black',anchor='lt')
    return image
