"""Neat placeholder product pictures (so demo products do not look empty).

They are plain drawings made here, not photos. Replace them with real photos in the admin.
"""
import io

from PIL import Image, ImageDraw, ImageFont

SIZE = 800
PALETTES = {
    'phone': ((18, 38, 92), (33, 158, 188)), 'tablet': ((40, 30, 100), (120, 100, 220)),
    'watch': ((20, 70, 70), (60, 190, 160)), 'buds': ((90, 40, 60), (240, 120, 140)),
    'power': ((90, 60, 10), (255, 183, 3)), 'laptop': ((30, 40, 55), (110, 130, 160)),
    'accessory': ((50, 50, 70), (150, 150, 190)),
}


def kind_for(category_name):
    n = (category_name or '').lower()
    for key, words in [('buds', ('bud', 'headphone', 'audio')), ('watch', ('watch', 'band')),
                       ('laptop', ('laptop', 'macbook')), ('tablet', ('tab', 'ipad')),
                       ('phone', ('phone', 'mobile')), ('power', ('power', 'charger', 'battery'))]:
        if any(w in n for w in words):
            return key
    return 'accessory'


def _font(size):
    for path in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                 '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf'):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def _wrap(draw, text, font, width):
    lines, line = [], ''
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines[:3]


def _device(draw, kind, c1, c2):
    light = (255, 255, 255)
    if kind == 'phone':
        draw.rounded_rectangle((290, 120, 510, 540), 36, fill=light, outline=c2, width=8)
        draw.rounded_rectangle((308, 150, 492, 510), 20, fill=c1)
        draw.ellipse((390, 130, 410, 150), fill=c2)
    elif kind == 'tablet':
        draw.rounded_rectangle((200, 140, 600, 520), 30, fill=light, outline=c2, width=8)
        draw.rounded_rectangle((224, 164, 576, 496), 14, fill=c1)
    elif kind == 'laptop':
        draw.rounded_rectangle((210, 150, 590, 410), 18, fill=light, outline=c2, width=8)
        draw.rectangle((230, 170, 570, 390), fill=c1)
        draw.polygon([(150, 430), (650, 430), (610, 480), (190, 480)], fill=light, outline=c2)
    elif kind == 'watch':
        draw.rectangle((340, 90, 460, 240), fill=c2)
        draw.rectangle((340, 400, 460, 560), fill=c2)
        draw.rounded_rectangle((300, 210, 500, 430), 50, fill=light, outline=c2, width=8)
        draw.rounded_rectangle((322, 232, 478, 408), 34, fill=c1)
    elif kind == 'buds':
        draw.rounded_rectangle((260, 280, 540, 470), 70, fill=light, outline=c2, width=8)
        draw.ellipse((300, 150, 380, 270), fill=light, outline=c2, width=6)
        draw.ellipse((420, 150, 500, 270), fill=light, outline=c2, width=6)
    elif kind == 'power':
        draw.rounded_rectangle((300, 130, 500, 520), 34, fill=light, outline=c2, width=8)
        draw.polygon([(410, 220), (360, 340), (400, 340), (385, 430), (445, 300), (405, 300)], fill=c2)
    else:
        draw.rounded_rectangle((280, 190, 520, 470), 40, fill=light, outline=c2, width=8)
        draw.ellipse((360, 270, 440, 350), fill=c1)


def make_placeholder(name, brand='', category=''):
    """Return PNG bytes for a simple branded product picture."""
    kind = kind_for(category)
    c1, c2 = PALETTES[kind]
    img = Image.new('RGB', (SIZE, SIZE), (243, 245, 250))
    draw = ImageDraw.Draw(img)
    draw.ellipse((120, 60, 680, 620), fill=(228, 233, 245))
    _device(draw, kind, c1, c2)
    font, small = _font(40), _font(28)
    y = 600
    for line in _wrap(draw, name, font, SIZE - 120):
        draw.text((SIZE / 2, y), line, font=font, fill=c1, anchor='mt')
        y += 50
    if brand:
        draw.text((SIZE / 2, 740), brand.upper(), font=small, fill=c2, anchor='mt')
    buf = io.BytesIO()
    img.save(buf, 'PNG', optimize=True)
    return buf.getvalue()
