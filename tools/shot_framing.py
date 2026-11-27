#!/usr/bin/env python3
"""SHOT FRAMING from the exported timeline, before any render: for every shot, on how many frames every visible
fighter's chest sits inside the frame, and how far apart (in frame widths) the fighters are, so one never hides the
other (27 Nov 2026: an over-the-shoulder impact shot kept both chests "in frame" while Musashi's back covered
Kojiro's cut; the separation test catches that).

  python3 tools/shot_framing.py output/<film>.timeline.json [--sep 0.30] [--margin 0.10] [--frames a-b] [--single B2]

A frame passes when every visible fighter's chest is inside [margin, 1 - margin] across and [0.15, 0.85] down, and
(with two or more fighters) the closest pair is at least --sep frame widths apart. Exit code 1 if any shot passes
on fewer than 80% of its frames. Projection: the timeline camera (three.js, vertical fov), the same numbers Blender
keys.
"""
import argparse
import json
import math
import sys

ap = argparse.ArgumentParser()
ap.add_argument('timeline')
ap.add_argument('--sep', type=float, default=0.30)
ap.add_argument('--margin', type=float, default=0.10)
ap.add_argument('--frames')
ap.add_argument('--single', default='', help='comma-separated shot ids framed on ONE fighter: pass = one chest inside')
A = ap.parse_args()
T = json.load(open(A.timeline))
F, BONES = T['frames'], T['bones']['order']
W, H = T['film']['width'], T['film']['height']
CH = BONES.index('chest')


def qrot(q, v):
    x, y, z, w = q
    vx, vy, vz = v
    ix, iy, iz = w * vx + y * vz - z * vy, w * vy + z * vx - x * vz, w * vz + x * vy - y * vx
    iw = -x * vx - y * vy - z * vz
    return (ix * w - iw * x - iy * z + iz * y, iy * w - iw * y - iz * x + ix * z, iz * w - iw * z - ix * y + iy * x)


def project(cam, p):
    v = qrot([-cam['rot'][0], -cam['rot'][1], -cam['rot'][2], cam['rot'][3]], [p[i] - cam['pos'][i] for i in range(3)])
    if v[2] >= -0.05:
        return None
    tv = math.tan(math.radians(cam['fov']) / 2)
    return 0.5 + v[0] / -v[2] / (tv * W / H) / 2, 0.5 - v[1] / -v[2] / tv / 2


a, b = (int(x) for x in A.frames.split('-')) if A.frames else (0, len(F) - 1)
shots = {}
for r in F[a:b + 1]:
    pts = {k: project(r['camera'], v['bones'][CH][:3]) for k, v in r['actors'].items() if not v.get('hidden')}
    inside = all(p and A.margin <= p[0] <= 1 - A.margin and 0.15 <= p[1] <= 0.85 for p in pts.values())
    xs = sorted(p[0] for p in pts.values() if p)
    sep = min((xs[i + 1] - xs[i] for i in range(len(xs) - 1)), default=None)
    ok = inside and (sep is None or sep >= A.sep)
    if (r.get('shot') or '-') in A.single.split(','):            # a single: one fighter cleanly framed is the shot
        ok = any(p and A.margin <= p[0] <= 1 - A.margin and 0.15 <= p[1] <= 0.85 for p in pts.values())
        inside = ok
    s = shots.setdefault(r.get('shot') or '-', {'n': 0, 'ok': 0, 'min_sep': 9.0, 'out': 0, 'f0': r['f'], 'f1': r['f']})
    s['n'] += 1
    s['ok'] += ok
    s['out'] += not inside
    s['f1'] = r['f']
    if sep is not None:
        s['min_sep'] = min(s['min_sep'], sep)
bad = 0
print('shot   frames    pass   outside  min separation (frame widths)')
for k, s in shots.items():
    pct = 100 * s['ok'] / s['n']
    bad += pct < 80
    print('%-5s  %3d-%-3d  %5.1f%%  %4d      %s%s' % (k, s['f0'], s['f1'], pct, s['out'],
          '%.2f' % s['min_sep'] if s['min_sep'] < 9 else '-', '   <- fix' if pct < 80 else ''))
sys.exit(1 if bad else 0)
