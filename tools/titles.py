#!/usr/bin/env python3
"""TITLES: a film's on-screen words burned into its frames, inside the vertical safe box.

    python3 tools/titles.py --film film/<name>.json --frames output/blender/<name>-fx --out output/blender/<name>-txt
    python3 tools/titles.py --film film/<name>.json --preview 4.5 --size 1080x1920 [--frames DIR]   (one still)

Reads `titles` [{start, end, style, jp, en, sub}] from the film file (seconds on the FILM clock: the frames as they
are encoded, hit-stop frames included, frame fNNNN at (NNNN - 1) / fps). Fades 0.5 s in and out (shorter titles fade
over a third of their length). Frames without words are hard-linked, not copied.

styles
  hero     the hook: big Japanese line, the English under it, upper third
  left     a place / date label, lower left
  bottom   narration: one or two lines centred low in the safe box
  quote    a spoken line: italic, in quotation marks, centred low
  endcard  series name: Japanese, English letter-spaced, the `sub` line under it, centred

Safe box (9:16 for TikTok / Reels / Shorts): x 8-92 %, y 10-78 % of the frame. The platform's own buttons and
caption sit outside it. Every title's ink is measured against the box and a title that leaves it stops the run.
Fonts: Noto Serif CJK JP (Japanese) and Caladea (English), both installed system fonts; a missing glyph (it would
draw as a box) stops the run too.
"""
import argparse
import json
import os
import shutil
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = {
    'jp_black': ('/usr/share/fonts/opentype/noto/NotoSerifCJK-Black.ttc', 0),
    'jp_bold': ('/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc', 0),
    'en_bold': ('/usr/share/fonts/truetype/crosextra/Caladea-Bold.ttf', 0),
    'en_reg': ('/usr/share/fonts/truetype/crosextra/Caladea-Regular.ttf', 0),
    'en_ital': ('/usr/share/fonts/truetype/crosextra/Caladea-Italic.ttf', 0),
}
SAFE = (0.08, 0.10, 0.92, 0.78)              # x0, y0, x1, y1 as fractions of the frame
INK = (243, 234, 216)                        # cream paper
SEAL = (178, 40, 34)                         # the red of the seal / Kojiro's haori
_cache = {}


def font(key, px):
    k = (key, int(px))
    if k not in _cache:
        path, idx = FONTS[key]
        _cache[k] = ImageFont.truetype(path, int(px), index=idx)
    return _cache[k]


def check_glyphs(key, text):
    """A character the font does not have draws as the .notdef box: compare with a code point no font has."""
    f = font(key, 48)

    def ink(ch):
        im = Image.new('L', (90, 90), 0)
        ImageDraw.Draw(im).text((4, 4), ch, font=f, fill=255)
        return im.tobytes()
    missing = ink('\U000FFFFD')
    bad = sorted({ch for ch in text if not ch.isspace() and ink(ch) == missing})
    if bad:
        raise SystemExit('titles: font %s has no glyph for %s (in %r)' % (os.path.basename(FONTS[key][0]), bad, text))


def wrap(draw, text, f, max_w):
    """Lines that fit max_w; a newline in the text is a line break the writer chose (a sentence end)."""
    lines = []
    for part in text.split('\n'):
        words, cur = part.split(), ''
        for w in words:
            t = (cur + ' ' + w).strip()
            if draw.textlength(t, font=f) <= max_w or not cur:
                cur = t
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
    return lines


def spaced(text, n):
    return (' ' * n).join(text)


def layer(title, W, H):
    """One title as an RGBA layer the size of the frame (drawn once, faded per frame)."""
    s = W / 1080.0
    style = title.get('style', 'bottom')
    jp, en, sub = title.get('jp') or '', title.get('en') or '', title.get('sub') or ''
    L = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(L)
    x0, y0, x1, y1 = SAFE[0] * W, SAFE[1] * H, SAFE[2] * W, SAFE[3] * H
    cx, max_w = W / 2, (x1 - x0)
    items = []                                # (text, font key, px, y, anchor x, align)

    if style == 'hero':
        y = y0 + 0.07 * H
        if jp:
            check_glyphs('jp_black', jp)
            items.append((jp, 'jp_black', 150 * s, y, cx, 'mm'))
            y += 150 * s
        if en:
            check_glyphs('en_bold', en)
            for ln in wrap(d, en, font('en_bold', 64 * s), max_w):
                items.append((ln, 'en_bold', 64 * s, y, cx, 'mm'))
                y += 76 * s
        if sub:
            check_glyphs('en_ital', sub)
            items.append((sub, 'en_ital', 40 * s, y + 6 * s, cx, 'mm'))
    elif style == 'left':
        y = y1 - 0.06 * H
        for txt, key, px in ((jp, 'jp_bold', 46 * s), (en, 'en_bold', 46 * s), (sub, 'en_ital', 36 * s)):
            if txt:
                check_glyphs(key, txt)
                items.append((txt, key, px, y, x0 + 0.02 * W, 'lm'))
                y += px * 1.25
    elif style in ('bottom', 'quote'):
        key = 'en_ital' if style == 'quote' else 'en_bold'
        px = 58 * s
        txt = ('“%s”' % en) if style == 'quote' and en and not en.startswith('“') else en
        lines = wrap(d, txt, font(key, px), max_w * 0.92) if txt else []
        if txt:
            check_glyphs(key, txt)
        n = len(lines) + (1 if sub else 0) + (1 if jp else 0)
        y = y1 - 0.035 * H - (n - 1) * px * 1.2
        if jp:
            check_glyphs('jp_bold', jp)
            items.append((jp, 'jp_bold', px * 0.8, y, cx, 'mm'))
            y += px * 1.2
        for ln in lines:
            items.append((ln, key, px, y, cx, 'mm'))
            y += px * 1.2
        if sub:
            check_glyphs('en_ital', sub)
            items.append((sub, 'en_ital', px * 0.62, y - px * 0.1, cx, 'mm'))
    elif style == 'endcard':
        y = H * 0.42
        if jp:
            check_glyphs('jp_black', jp)
            items.append((jp, 'jp_black', 120 * s, y, cx, 'mm'))
            y += 128 * s
        if en:
            check_glyphs('en_bold', en)
            items.append((spaced(en, 1), 'en_bold', 62 * s, y, cx, 'mm'))
            y += 84 * s
        if sub:
            check_glyphs('en_ital', sub)
            for ln in wrap(d, sub, font('en_ital', 42 * s), max_w):
                items.append((ln, 'en_ital', 42 * s, y, cx, 'mm'))
                y += 52 * s
    else:
        raise SystemExit('titles: unknown style %r (hero, left, bottom, quote, endcard)' % style)

    # shadow (soft, slightly down), then the ink
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ds = ImageDraw.Draw(sh)
    for txt, key, px, y, x, anc in items:
        ds.text((x, y + 3 * s), txt, font=font(key, px), fill=(10, 6, 4, 235), anchor=anc,
                stroke_width=max(1, int(5 * s)), stroke_fill=(10, 6, 4, 235))
    sh = sh.filter(ImageFilter.GaussianBlur(max(1.0, 7 * s)))
    for txt, key, px, y, x, anc in items:
        d.text((x, y), txt, font=font(key, px), fill=INK + (255,), anchor=anc)
    if style == 'hero' and jp:                    # a small red seal (hanko) at the lower right of the kanji
        kb = d.textbbox((cx, y0 + 0.07 * H), jp, font=font('jp_black', 150 * s), anchor='mm')
        r = 15 * s
        sx, sy = kb[2] + 14 * s, kb[3] - 2 * r
        d.rounded_rectangle((sx, sy, sx + 2 * r, sy + 2 * r), radius=3 * s, fill=SEAL + (255,))
    out = Image.alpha_composite(sh, L)
    bb = L.getbbox()
    if bb and (bb[0] < x0 - 1 or bb[1] < y0 - 1 or bb[2] > x1 + 1 or bb[3] > y1 + 1):
        raise SystemExit('titles: %r (%s) leaves the safe box: ink %s, box %s' % (
            (en or jp)[:40], style, bb, tuple(int(v) for v in (x0, y0, x1, y1))))
    return out, bb


def alpha_at(t, title):
    a, b = float(title['start']), float(title['end'])
    if t < a or t > b:
        return 0.0
    fade = min(0.5, (b - a) / 3.0)
    return max(0.0, min(1.0, (t - a) / fade if fade > 0 else 1.0, (b - t) / fade if fade > 0 else 1.0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--film', required=True)
    ap.add_argument('--frames')
    ap.add_argument('--out')
    ap.add_argument('--fps', type=float)
    ap.add_argument('--preview', type=float, help='render one still at this film time (s)')
    ap.add_argument('--size', default=None, help='WxH for a preview without frames')
    a = ap.parse_args()
    F = json.load(open(a.film))
    titles = F.get('titles') or []
    fps = a.fps or float(F.get('fps', 30))
    frames = sorted(f for f in os.listdir(a.frames) if f.startswith('f') and f.endswith('.png')) if a.frames else []
    if frames:
        W, H = Image.open(os.path.join(a.frames, frames[0])).size
    else:
        W, H = (int(v) for v in (a.size or '%dx%d' % (F.get('width', 1080), F.get('height', 1920))).split('x'))
    layers = []
    for t_ in titles:
        L, bb = layer(t_, W, H)
        layers.append((t_, L))
        print('[titles] %5.2f-%5.2f s %-8s %-40s ink %s' % (float(t_['start']), float(t_['end']), t_.get('style', 'bottom'),
                                                            (t_.get('en') or t_.get('jp') or '')[:40], bb))
    if a.preview is not None:
        base = Image.open(os.path.join(a.frames, 'f%04d.png' % (int(round(a.preview * fps)) + 1))).convert('RGBA') \
            if frames else Image.new('RGBA', (W, H), (40, 34, 30, 255))
        for t_, L in layers:
            al = alpha_at(a.preview, t_)
            if al > 0:
                base = Image.alpha_composite(base, L if al >= 1 else _fade(L, al))
        out = a.out or os.path.join(REPO, 'output', 'titles-preview.png')
        base.convert('RGB').save(out)
        print('[titles] preview at %.2f s -> %s' % (a.preview, out))
        return
    if not frames or not a.out:
        raise SystemExit('titles: --frames and --out are needed (or --preview)')
    os.makedirs(a.out, exist_ok=True)
    for f in os.listdir(a.out):
        if f.endswith('.png'):
            os.remove(os.path.join(a.out, f))
    n_txt = 0
    for f in frames:
        t = (int(f[1:5]) - 1) / fps
        on = [(t_, L, alpha_at(t, t_)) for t_, L in layers]
        on = [(t_, L, al) for t_, L, al in on if al > 0]
        src, dst = os.path.join(a.frames, f), os.path.join(a.out, f)
        if not on:
            try:
                os.link(src, dst)
            except OSError:
                shutil.copyfile(src, dst)
            continue
        im = Image.open(src).convert('RGBA')
        for _t, L, al in on:
            im = Image.alpha_composite(im, L if al >= 1 else _fade(L, al))
        im.convert('RGB').save(dst)
        n_txt += 1
    print('[titles] %d of %d frames carry words -> %s' % (n_txt, len(frames), a.out))


def _fade(L, al):
    r, g, b, aa = L.split()
    return Image.merge('RGBA', (r, g, b, aa.point(lambda v: int(v * al))))


if __name__ == '__main__':
    sys.exit(main())
