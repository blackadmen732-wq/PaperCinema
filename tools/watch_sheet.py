#!/usr/bin/env python3
"""WATCH SHEET: a rendered film as contact sheets, shot by shot, to watch it properly (every cut, every beat).

    python3 tools/watch_sheet.py <film> [--frames DIR] [--every 3] [--per-sheet 40] [--out output/watch/<film>]

Reads the shots from output/<film>.timeline.json (id, name, first and last frame) and the frames from DIR (default:
the encoded ones: output/blender/<film>-txt, -fx, or the raw render). Every `every`-th frame of every shot (and its
first and last frame) goes on the sheets in order, labelled with the frame number and the shot; a red bar marks each
cut. Hit-stop frames added by tools/post_fx.py shift the numbering after the contact: the labels are the file's own
frame numbers, the shot names come from the timeline (before the stop).
"""
import argparse
import json
import os

from PIL import Image, ImageDraw

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('film')
    ap.add_argument('--frames')
    ap.add_argument('--every', type=int, default=3)
    ap.add_argument('--per-sheet', type=int, default=40)
    ap.add_argument('--cols', type=int, default=8)
    ap.add_argument('--tile', type=int, default=150, help='tile width in px (height follows 9:16)')
    ap.add_argument('--out')
    a = ap.parse_args()
    TL = json.load(open(os.path.join(REPO, 'output', a.film + '.timeline.json')))
    fdir = a.frames
    if not fdir:
        for suf in ('-txt', '-fx', ''):
            d = os.path.join(REPO, 'output', 'blender', a.film + suf)
            if os.path.isdir(d) and any(f.endswith('.png') for f in os.listdir(d)):
                fdir = d
                break
    files = sorted(f for f in os.listdir(fdir) if f.startswith('f') and f.endswith('.png'))
    have = {int(f[1:5]): f for f in files}
    stops = 0
    try:
        ev = json.load(open(os.path.join(REPO, 'output', a.film + '.bake-events.json')))
        stops = sum(int(s.get('frames', 0)) for s in ev.get('stops') or [])
        stop_at = min((int(round(float(s['tb']) * TL['clock']['fps'])) + 1 for s in ev.get('stops') or []), default=None)
    except (OSError, ValueError, KeyError):
        stop_at = None
    picks = []                                   # (file frame, shot id, shot name, first of shot)
    for sh in TL['shots']:
        f0, f1 = sh['f0'] + 1, sh['f1'] + 1
        rng = list(range(f0, f1 + 1, a.every))
        if rng[-1] != f1:
            rng.append(f1)
        for k, f in enumerate(rng):
            ff = f + (stops if stop_at is not None and f > stop_at else 0)
            if ff in have:
                picks.append((ff, sh['id'], sh.get('name', ''), k == 0))
    out = a.out or os.path.join(REPO, 'output', 'watch', a.film)
    os.makedirs(out, exist_ok=True)
    W = a.tile
    H = int(W * 16 / 9)
    sheets = []
    for s0 in range(0, len(picks), a.per_sheet):
        chunk = picks[s0:s0 + a.per_sheet]
        rows = (len(chunk) + a.cols - 1) // a.cols
        sheet = Image.new('RGB', (a.cols * W, rows * (H + 14)), (16, 16, 16))
        d = ImageDraw.Draw(sheet)
        for k, (ff, sid, name, first) in enumerate(chunk):
            im = Image.open(os.path.join(fdir, have[ff])).convert('RGB').resize((W, H))
            x, y = (k % a.cols) * W, (k // a.cols) * (H + 14)
            sheet.paste(im, (x, y + 14))
            d.text((x + 3, y + 1), '%s f%d' % (sid, ff), fill=(255, 230, 90) if first else (200, 200, 200))
            if first:
                d.rectangle((x, y + 14, x + 3, y + 14 + H), fill=(220, 40, 40))
        p = os.path.join(out, 'sheet-%02d.png' % (len(sheets) + 1))
        sheet.save(p)
        sheets.append(p)
    with open(os.path.join(out, 'shots.txt'), 'w') as fh:
        for sh in TL['shots']:
            fh.write('%s  f%d-f%d  %s\n' % (sh['id'], sh['f0'] + 1, sh['f1'] + 1, sh.get('name', '')))
    print('[watch] %d frames from %s on %d sheet(s) -> %s' % (len(picks), os.path.relpath(fdir, REPO), len(sheets), out))


if __name__ == '__main__':
    main()
