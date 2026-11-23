"""Thumbnails for a film: the decisive-blow frame + kanji title + red brush swash.
    python3 engine/thumbnail.py film/<name>.json
Writes output/<name>-thumb.png (1280x720, YouTube) and output/<name>-thumb-vertical.png (1080x1920, Shorts/Reels/TikTok).
Uses the film's first "hero" title for the text and events.impact (or the last shake) for the frame.
"""
import json, os, random, subprocess, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = sys.argv[1] if len(sys.argv) > 1 else 'film/ganryujima.json'
film = json.load(open(os.path.join(ROOT, src)))
name = os.path.basename(src).replace('.json', '')
hero = next((t for t in film.get('titles', []) if t.get('style') == 'hero'), {})
jp, en = hero.get('jp', ''), hero.get('en', film.get('title', ''))
t = film.get('events', {}).get('impact')
if t is None or t < 0:
    t = (film.get('shakes') or [{'t': film['duration'] / 2}])[-1]['t']
t = f"{t + 0.1:g}"

FONT_JP = '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf'
FONT_EN = '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf'

def still(vertical):
    prefix = f'thumb-{"v-" if vertical else ""}'
    cmd = ['node', 'engine/render.mjs', '--film', src, '--still', t, '--prefix', prefix] + (['--vertical'] if vertical else [])
    subprocess.run(cmd, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    img = Image.open(os.path.join(ROOT, f'output/stills/{prefix}t{t}.png')).convert('RGB')
    if not vertical and film.get('letterbox'):          # drop the cinema bars
        bar = int(max(0, (img.height - img.width / film['letterbox']) / 2))
        img = img.crop((0, bar, img.width, img.height - bar))
    return img

def swash(draw, box, seed):
    """A dry-brush red stroke: many thin jittered strokes along a slanted band."""
    random.seed(seed)
    x0, y0, x1, y1 = box
    for i in range(140):
        off = random.uniform(-1, 1) * (y1 - y0) * 0.5
        a = (x0 + random.uniform(-20, 20), (y0 + y1) / 2 + off + 18)
        b = (x1 + random.uniform(-60, 0), (y0 + y1) / 2 + off * 0.8 - 22)
        draw.line([a, b], fill=(170 + random.randint(-25, 25), 12, 10), width=random.randint(2, 7))

def compose(img, w, h, vertical):
    # cover-crop to the target size
    s = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * s), int(img.height * s)))
    l, tp = (img.width - w) // 2, (img.height - h) // 2
    img = img.crop((l, tp, l + w, tp + h))
    shade = Image.new('L', (w, h), 0)
    sd = ImageDraw.Draw(shade)
    for y in range(h):                                   # darken the bottom for text
        sd.line([(0, y), (w, y)], fill=int(max(0, (y / h - 0.45)) * 330))
    img = Image.composite(Image.new('RGB', (w, h), (8, 6, 6)), img, shade.filter(ImageFilter.GaussianBlur(4)))
    d = ImageDraw.Draw(img, 'RGBA')
    band = (int(w * 0.04), int(h * (0.62 if not vertical else 0.66)), int(w * 0.96), int(h * (0.80 if not vertical else 0.76)))
    swash(d, band, 3)
    fj = ImageFont.truetype(FONT_JP, int(h * (0.16 if not vertical else 0.085)))
    fe = ImageFont.truetype(FONT_EN, int(h * (0.045 if not vertical else 0.026)))
    tw = d.textlength(jp, font=fj)
    y = band[1] - int(h * (0.05 if not vertical else 0.03))
    d.text(((w - tw) / 2 + 4, y + 4), jp, font=fj, fill=(0, 0, 0, 180))
    d.text(((w - tw) / 2, y), jp, font=fj, fill=(246, 238, 221, 255))
    ew = d.textlength(en, font=fe)
    d.text(((w - ew) / 2, band[3] + int(h * 0.02)), en, font=fe, fill=(240, 180, 110, 255))
    return img

for vertical, (w, h), suffix in [(False, (1280, 720), ''), (True, (1080, 1920), '-vertical')]:
    out = os.path.join(ROOT, f'output/{name}-thumb{suffix}.png')
    compose(still(vertical), w, h, vertical).save(out)
    print('wrote', os.path.relpath(out, ROOT))
