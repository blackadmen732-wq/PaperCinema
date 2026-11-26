#!/usr/bin/env python3
"""COVER: a Paper Cinema cover / thumbnail / opening card, built from OUR parts only (Mark, Nov 26).

  python3 tools/cover.py --prop output/covers/katana.png --jp 紙の剣 --seal 紙剣 --out output/covers/cover.jpg

Layers, back to front (Mark: "the full screen white ... the letters in the back, bold ... an orange and white
design ... the red thing at the bottom, where the white is, where people can see it"):
  1. white washi paper, with its fibres
  2. our orange-and-white pattern: a rising sun, seigaiha waves (the sea) and kasumi mist bands - the same two
     shapes the katana guard carries (blender/props/katana_hero.py), so prop and page belong together
  3. the channel name in huge bold black kanji, top to bottom, BEHIND the prop
  4. the prop render (any transparent PNG from blender/props/), with a soft cast shadow, and a glint
  5. a white band at the bottom: the red seal (hanko) and PAPER CINEMA, where the eye lands last

Everything is drawn here or rendered by our own Blender scripts: no downloaded picture, no font outside the
system's Noto CJK (OFL), no stock pattern.
"""
import argparse
import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
SERIF = '/usr/share/fonts/opentype/noto/NotoSerifCJK-Black.ttc'
SANS = '/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc'
PAPER = (251, 248, 242)
ORANGE = (240, 106, 26)
ORANGE_PALE = (250, 196, 150)
INK = (14, 12, 12)
SEAL = (190, 30, 24)


def font(path, size):
    return ImageFont.truetype(path, size, index=0)


def washi(w, h, seed=3):
    """White paper with long soft fibres and a faint cloudy tone."""
    rnd = np.random.default_rng(seed)
    base = np.ones((h, w, 3), 'float32') * np.array(PAPER, 'float32')
    cloud = Image.fromarray((rnd.random((h // 24, w // 24)) * 255).astype('uint8')).resize((w, h), Image.BICUBIC)
    base -= (np.asarray(cloud, 'float32')[..., None] / 255 - 0.5) * 7
    img = Image.fromarray(np.clip(base, 0, 255).astype('uint8'))
    d = ImageDraw.Draw(img)
    r = random.Random(seed)
    for _ in range(900):                                  # fibres
        x, y = r.uniform(0, w), r.uniform(0, h)
        a = r.uniform(0, math.pi)
        L = r.uniform(12, 60)
        c = 236 + r.randint(-8, 6)
        d.line((x, y, x + math.cos(a) * L, y + math.sin(a) * L), fill=(c, c - 3, c - 8), width=1)
    return img


def seigaiha(img, top, bottom, s=64, color=ORANGE, fade=True):
    """Seigaiha waves: rows of overlapping concentric half-circles painted back to front, so each row covers the
    lower half of the row behind it; strongest at the bottom, fading out toward the top."""
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    rows = list(np.arange(top, bottom + s, s * 0.5))
    for i, cy in enumerate(rows):
        off = (i % 2) * s
        a = 255 if not fade else int(255 * min(1.0, 0.15 + 0.85 * (cy - top) / max(1, bottom - top)))
        for cx in np.arange(-s - off, img.width + 2 * s, 2 * s):
            d.ellipse((cx - s, cy - s, cx + s, cy + s), fill=PAPER + (255,))   # covers the row behind
            for k in (1.0, 0.74, 0.48, 0.22):
                rr = s * k
                d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=color + (a,), width=max(3, s // 12))
    a = np.asarray(layer).copy()
    a[:int(top), :, 3] = 0                                # only inside the band
    a[int(bottom):, :, 3] = 0
    out = img.convert('RGBA')
    out.alpha_composite(Image.fromarray(a))
    return out.convert('RGB')


def kasumi(d, y, x0, x1, h, color):
    """A kasumi mist band: a long bar with round ends, the stylised cloud of Japanese screens."""
    d.rounded_rectangle((x0, y - h / 2, x1, y + h / 2), radius=h / 2, fill=color)


def vertical_kanji(img, text, cx, y0, size, color=INK, shadow=ORANGE):
    d = ImageDraw.Draw(img)
    f = font(SERIF, size)
    y = y0
    for ch in text:
        small = ch in 'のノ'
        ff = font(SERIF, int(size * 0.80)) if small else f
        bb = d.textbbox((0, 0), ch, font=ff)
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        x = cx - w / 2 - bb[0]
        if shadow:
            d.text((x + size * 0.035, y - bb[1] + size * 0.035), ch, font=ff, fill=shadow)
        d.text((x, y - bb[1]), ch, font=ff, fill=color)
        y += (h if not small else size * 0.70) + size * 0.10
    return y


def hanko(text, size):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 12, fill=SEAL + (255,))
    d.rounded_rectangle((size * 0.06, size * 0.06, size * 0.94, size * 0.94), radius=size // 16,
                        outline=(255, 242, 232, 255), width=max(2, size // 36))
    f = font(SERIF, int(size * 0.40))
    for i, ch in enumerate(text[:2]):
        bb = d.textbbox((0, 0), ch, font=f)
        cw, chh = bb[2] - bb[0], bb[3] - bb[1]
        y = size * (0.12 + 0.40 * i) + (size * 0.36 - chh) / 2 - bb[1]
        d.text(((size - cw) / 2 - bb[0], y), ch, font=f, fill=(255, 245, 236, 255))
    # a stamp is never perfectly inked: knock a few flecks out of the red
    a = np.array(img)
    rnd = np.random.default_rng(7)
    fleck = rnd.random(a.shape[:2]) < 0.012
    a[fleck & (a[..., 3] > 0), 3] = 90
    return Image.fromarray(a)


def glint(img, cx, cy, r):
    layer = Image.new('RGB', img.size, (0, 0, 0))
    d = ImageDraw.Draw(layer)
    for k in range(10, 0, -1):
        a = k / 10
        c = (int(255 * (1 - a) ** 1.4), int(236 * (1 - a) ** 1.4), int(200 * (1 - a) ** 1.4))
        d.ellipse((cx - r * a, cy - r * a, cx + r * a, cy + r * a), fill=c)
    d.line((cx - r * 3.2, cy + r * 1.3, cx + r * 3.2, cy - r * 1.3), fill=(255, 250, 235), width=max(2, r // 10))
    d.line((cx - r * 0.4, cy - r * 2.0, cx + r * 0.4, cy + r * 2.0), fill=(255, 250, 235), width=max(2, r // 14))
    layer = layer.filter(ImageFilter.GaussianBlur(max(1, r // 12)))
    return Image.fromarray(np.clip(np.asarray(img, 'int16') + np.asarray(layer, 'int16'), 0, 255).astype('uint8'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prop', required=True, help='transparent PNG rendered by a blender/props/ script')
    ap.add_argument('--jp', default='紙の剣')
    ap.add_argument('--en', default='PAPER CINEMA')
    ap.add_argument('--seal', default='紙剣')
    ap.add_argument('--glint', default='0.795,0.235', help='glint position as a fraction of the frame, or "none"')
    ap.add_argument('--kanji-x', type=float, default=None, help='centre of the kanji column, fraction of the width')
    ap.add_argument('--size', default=None, help='kanji size in px (default by length)')
    ap.add_argument('--prop-scale', type=float, default=0.9)
    ap.add_argument('--prop-offset', default='150,40', help='dx,dy in px: room on the left for the name')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    img = washi(W, H)
    d = ImageDraw.Draw(img)
    # 2. the sun, the mist and the sea
    sun_c, sun_r = (742, 560), 300
    d.ellipse((sun_c[0] - sun_r, sun_c[1] - sun_r, sun_c[0] + sun_r, sun_c[1] + sun_r), fill=ORANGE)
    d.ellipse((sun_c[0] - sun_r - 26, sun_c[1] - sun_r - 26, sun_c[0] + sun_r + 26, sun_c[1] + sun_r + 26),
              outline=ORANGE, width=6)
    for y, x0, x1, h in ((300, -60, 520, 46), (930, 520, 1160, 40), (1010, -80, 360, 34), (190, 690, 1140, 30)):
        kasumi(d, y, x0, x1, h, ORANGE_PALE)
    img = seigaiha(img, 1070, 1520, s=62)
    # 3. the name, huge and bold, BEHIND the prop
    n = len(a.jp)
    size = int(a.size) if a.size else (370 if n <= 3 else 290)
    kx = a.kanji_x if a.kanji_x is not None else (0.21 if n <= 3 else 0.19)
    vertical_kanji(img, a.jp, int(kx * W), 95, size)
    # 4. the prop with a soft cast shadow, then the glint
    prop = Image.open(a.prop).convert('RGBA').resize((W, H), Image.LANCZOS)
    if a.prop_scale != 1.0 or a.prop_offset != '0,0':     # make room for the name: smaller and shifted
        k = a.prop_scale
        dx, dy = (int(v) for v in a.prop_offset.split(','))
        small = prop.resize((int(W * k), int(H * k)), Image.LANCZOS)
        prop = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        prop.alpha_composite(small, (int((W - W * k) / 2) + dx, int((H - H * k) / 2) + dy))
    alpha = np.asarray(prop)[..., 3].astype('float32') / 255
    sh = Image.fromarray((alpha * 120).astype('uint8')).filter(ImageFilter.GaussianBlur(22))
    shadow = Image.new('RGBA', (W, H), (60, 30, 10, 0))
    shadow.putalpha(sh)
    base = img.convert('RGBA')
    base.alpha_composite(shadow, (28, 40))
    base.alpha_composite(prop)
    img = base.convert('RGB')
    if a.glint != 'none':
        gx, gy = (float(v) for v in a.glint.split(','))
        img = glint(img, int(gx * W), int(gy * H), 70)
    # 5. the white band: the seal and the name, where people can see them
    d = ImageDraw.Draw(img)
    band = 1555
    d.rectangle((0, band, W, H), fill=PAPER)
    d.line((90, band, W - 90, band), fill=ORANGE, width=6)
    seal = hanko(a.seal, 190)
    img.paste(seal, (110, band + 50), seal)
    f = font(SANS, 78)
    x, y = 340, band + 70
    for ch in a.en:
        d.text((x, y), ch, font=f, fill=INK)
        x += d.textbbox((0, 0), ch, font=f)[2] + 8
    d.text((342, band + 178), a.jp + '  ·  ' + 'a paper sword-duel series', font=font(SANS, 30), fill=(120, 96, 80))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    img.save(a.out, quality=93)
    print('wrote', a.out)


if __name__ == '__main__':
    main()
