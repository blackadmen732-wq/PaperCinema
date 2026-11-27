#!/usr/bin/env python3
"""POST FX on the Blender frames: the impact effects that exist only in the browser preview (engine/fx.js,
combat.renderInkFrame, the DOM flash) reach the final video here, on the same frame numbers.

  python3 tools/post_fx.py --timeline output/<film>.timeline.json --frames output/blender/<film> \
      [--events output/<film>.bake-events.json] [--out output/blender/<film>-fx] [--sheet out.png]

What it adds, all driven by data (no hand-placed frames):
  hit frames   = the contact on the FINAL bake (bake-events.json: contact.frame) + every timeline frame marked
                 impactFrame (the ink frames the film asked for). The bake contact wins: it is the one the sound
                 and the slash are synced to.
  ink frame    on each hit frame: the picture becomes black ink on washi for ONE frame (the anime "impact frame"),
                 then a white flash that pops and is gone within 3 frames (0.55, 0.18, 0.05).
  speed lines  radial lines toward the centre on frames where the lens zooms fast (a crash zoom: |d focal| >= 2.5
                 mm/frame) or for 4 frames after a hit, thinning as they fade.
  chromatic    a red/blue split of a few pixels on the hit and the 2 frames after (the browser's ca-flash).
  vignette     a soft constant edge darkening (film.effects.vignette, default 0.25; 0 = off).
Writes PNGs with the same names into --out, and fx.json (which effect landed on which frame) for the checks.
"""
import argparse
import glob
import json
import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ap = argparse.ArgumentParser()
ap.add_argument('--timeline', required=True)
ap.add_argument('--frames', required=True)
ap.add_argument('--events')
ap.add_argument('--out')
ap.add_argument('--sheet')
A = ap.parse_args()
TL = json.load(open(A.timeline))
F = TL['frames']
OUT = A.out or A.frames.rstrip('/') + '-fx'
os.makedirs(OUT, exist_ok=True)
FX = TL.get('effects') or {}
WASHI = np.array([236, 228, 210], np.float32)
INK = np.array([18, 16, 20], np.float32)

# ---------------------------------------------------------------- which frames get what (0-based timeline frames)
hits = sorted({r['f'] for r in F if r.get('impactFrame')})
if A.events and os.path.exists(A.events):
    c = (json.load(open(A.events)).get('contact') or {})
    if c.get('frame') is not None:
        hits = sorted(set(hits) | {int(c['frame'])})
cuts = {r['f'] for r in F if r.get('cut')}
focal = [r['camera']['focal_mm'] for r in F]
plan = {}
for i, r in enumerate(F):
    f = r['f']
    e = {}
    dz = abs(focal[i] - focal[i - 1]) if i and f not in cuts else 0.0
    if dz >= 2.5:
        e['speed'] = min(1.0, dz / 6.0)
    for h in hits:
        d = f - h
        if d == 0:
            e['ink'] = 1
        if 1 <= d <= 3:
            e['flash'] = (0.55, 0.18, 0.05)[d - 1]          # a sharp pop that is gone in 3 frames (no grey veil)
        if 0 <= d <= 2:
            e['ca'] = 6 - 2 * d
        if 0 <= d <= 4:
            e['speed'] = max(e.get('speed', 0), 1 - d / 5)
    plan[f] = e
VIG = float(FX.get('vignette', 0.25))


def ink(im):
    """Black ink on washi for one frame (renderInkFrame's look): the picture is denoised first (render grain made the
    old threshold speckle), then everything darker than the frame's median becomes solid ink, and strong edges are
    drawn as ink lines on the light parts."""
    sm = im.convert('L').filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(1.2))
    g = np.asarray(sm, np.float32)
    edges = np.asarray(sm.filter(ImageFilter.FIND_EDGES), np.float32)
    thr = max(np.percentile(g, 50), 40.0)
    m = ((g < thr) | (edges > 14)).astype(np.float32)
    m = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(3))
                   .filter(ImageFilter.GaussianBlur(0.7)), np.float32)[..., None] / 255
    return Image.fromarray((WASHI * (1 - m) + INK * m).astype(np.uint8))


def speed_lines(im, k, seed):
    w, h = im.size
    lay = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(lay)
    rnd = random.Random(seed)
    cx, cy, R = w / 2, h * 0.47, math.hypot(w, h) / 2
    for _ in range(int(70 * k) + 10):
        a = rnd.uniform(0, 2 * math.pi)
        r0 = R * rnd.uniform(0.42, 0.62)
        wd = rnd.uniform(0.004, 0.012) * w * (0.5 + k)
        p = lambda r, da=0: (cx + math.cos(a + da) * r, cy + math.sin(a + da) * r)
        d.polygon([p(R * 1.1, -wd / R), p(R * 1.1, wd / R), p(r0)], fill=int(170 * k + 60))
    m = np.asarray(lay.filter(ImageFilter.GaussianBlur(0.8)), np.float32)[..., None] / 255
    a_ = np.asarray(im, np.float32)
    return Image.fromarray((a_ * (1 - m) + 245 * m).astype(np.uint8))


def ca(im, px):
    r, g, b = im.split()
    return Image.merge('RGB', (r.transform(im.size, Image.AFFINE, (1, 0, -px, 0, 1, 0)), g,
                               b.transform(im.size, Image.AFFINE, (1, 0, px, 0, 1, 0))))


vig = None
done = []
files = sorted(glob.glob(os.path.join(A.frames, 'f*.png')))
for p in files:
    n = int(os.path.basename(p)[1:5])               # Blender writes 1-based frame numbers
    f = n - 1
    e = plan.get(f, {})
    im = Image.open(p).convert('RGB')
    if e.get('ink'):
        im = ink(im)
    if e.get('ca'):
        im = ca(im, max(1, round(e['ca'] * im.size[0] / 720)))
    if e.get('speed'):
        im = speed_lines(im, e['speed'], f)
    a = np.asarray(im, np.float32)
    if e.get('flash'):
        a = a + (255 - a) * e['flash']
    if VIG > 0:
        if vig is None or vig.shape[:2] != a.shape[:2]:
            h, w = a.shape[:2]
            yy, xx = np.mgrid[0:h, 0:w]
            rr = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)) / math.sqrt(2)
            vig = (1 - VIG * np.clip((rr - 0.45) / 0.55, 0, 1) ** 1.6)[..., None]
        a = a * vig
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(os.path.join(OUT, os.path.basename(p)))
    if e:
        done.append({'frame': n, **e})
json.dump({'hits_0based': hits, 'frames': done, 'vignette': VIG}, open(os.path.join(OUT, 'fx.json'), 'w'), indent=1)
print('[post-fx] %d frames -> %s · hits %s · effect frames %d' % (len(files), OUT, hits, len(done)))
if A.sheet and hits:
    h0 = hits[0] + 1
    names = [os.path.join(OUT, 'f%04d.png' % k) for k in range(h0 - 2, h0 + 5) if os.path.exists(os.path.join(OUT, 'f%04d.png' % k))]
    ims = [Image.open(x).convert('RGB') for x in names]
    if ims:
        w, h = ims[0].size
        s = 300 / h
        sheet = Image.new('RGB', (int(w * s) * len(ims), 300), (0, 0, 0))
        for k, x in enumerate(ims):
            sheet.paste(x.resize((int(w * s), 300)), (k * int(w * s), 0))
        sheet.save(A.sheet)
        print('[post-fx] sheet', A.sheet)
