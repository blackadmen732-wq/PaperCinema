#!/usr/bin/env python3
"""Make a motion-page film (engine/motion.html) that plays a capture from tools/mocap.py on our character.

    python3 tools/mocap_film.py library/mocap/iaido-cut.json --out film/mocap-test.json [--character kojiro]
            [--lead 0.5] [--camera phone|side] [--tol 0.03] [--vertical]

camera "phone" puts the film camera where the phone was (needs the capture made with --facing keep or auto;
both carry the phone), so the film and the source clip can be compared side by side (tools/mocap_sheet.py).
"side" frames the hero side-on with the compose rig instead.

The motion page turns each fighter's head toward the other one (engine/motion.js poseOf: 40 % neck, 60 % head,
clamped to 0.7 rad). The opponent here is a hidden, still target; its pull is subtracted from the captured ny / hy
on every key, so the head does what the performer's head did.
"""
import argparse
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mocap as M  # noqa: E402


def simplify(cap, tol):
    keys = cap['keys']
    if tol is None or len(keys) < 3:
        return keys
    names = [c for c in cap['channels'] if c in keys[0]]
    ch = {c: np.array([k[c] for k in keys]) for c in names}
    idx = M.dp_keys(M.pose_matrix(ch, names), tol=tol)
    return [keys[i] for i in idx]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('capture')
    ap.add_argument('--out', required=True)
    ap.add_argument('--character', default='kojiro')
    ap.add_argument('--lead', type=float, default=0.5, help='seconds of the first pose before the capture plays')
    ap.add_argument('--tail', type=float, default=0.5)
    ap.add_argument('--camera', default='phone', choices=['phone', 'side'])
    ap.add_argument('--tol', type=float, default=0.03, help='key simplification (0 = every frame)')
    ap.add_argument('--vertical', action='store_true')
    ap.add_argument('--title')
    args = ap.parse_args()
    cap = json.load(open(args.capture))
    keys = simplify(cap, args.tol or None)
    cam = cap['camera']
    cp, cl = np.array(cam['pos']), np.array(cam['look'])
    d = cl - cp; d[1] = 0; d /= np.linalg.norm(d)
    target = cp + 3.0 * d                                     # the hidden opponent: 3 m in front of the lens, on the ground
    target[1] = 0.0
    out_keys = []
    for n, k in enumerate(keys):
        q = {kk: v for kk, v in k.items() if kk != 'pose'}
        q['t'] = round(k['t'] + args.lead, 4)
        yaw = math.atan2(target[0] - k['x'], target[2] - k['z']) - k['ry'] - k['ty'] - k['cy']
        yaw = max(-0.7, min(0.7, math.atan2(math.sin(yaw), math.cos(yaw))))
        if 'ny' in q:
            q['ny'] = round(q['ny'] - 0.4 * yaw, 3)
            q['hy'] = round(q['hy'] - 0.6 * yaw, 3)
        if 'pose' in k:
            q = {'t': q['t'], 'pose': k['pose'], **{kk: v for kk, v in q.items() if kk != 't'}}
        out_keys.append(q)
    first = dict(out_keys[0]); first['t'] = 0.0
    out_keys = [first] + out_keys
    dur = round(out_keys[-1]['t'] + args.tail, 3)
    aspect = cam.get('aspect', 16 / 9)
    vfov = math.degrees(2 * math.atan(math.tan(math.radians(cam['hfov']) / 2) / aspect))
    W = 960
    H = int(round(W / aspect / 2) * 2)
    if args.camera == 'phone':
        rel = cp - target
        beat = {'t': 0, 'rig': 'orbit', 'subjects': ['target'], 'deg0': round(math.degrees(math.atan2(rel[0], rel[2])), 2),
                'radius': round(float(math.hypot(rel[0], rel[2])), 3), 'height': round(float(cp[1]) - 0.15, 3),
                'fov': round(vfov, 2), 'feel': 'locked',
                'note': 'where the phone was (tools/mocap_film.py): a locked camera around the still, hidden target'}
    else:
        beat = {'t': 0, 'rig': 'compose', 'subjects': ['hero'], 'basis': 'world', 'az': -90, 'elev': 4, 'size': 0.8,
                'fov': 34, 'feel': 'dolly', 'note': 'side-on from the hero\'s right'}
    src = cap.get('source', {})
    film = {
        'title': args.title or f"Mocap test: {src.get('video', args.capture)} played on our figure",
        'note': f'Made by tools/mocap.py + tools/mocap_film.py from {os.path.basename(args.capture)} (docs/MOCAP.md). '
                f'The capture starts at t = {args.lead}. No twoHand window: the captured left arm plays as filmed.',
        'page': 'engine/motion.html', 'fps': 24, 'width': W, 'height': H,
        'format': 'vertical' if args.vertical else 'horizontal', 'duration': dur, 'mode': 'dawn',
        'motion': {'overlap': False},
        'cast': {'hero': {'character': args.character, 'face': 'eyes'}, 'target': {'character': 'musashi', 'hidden': True}},
        'effects': {'ground': False, 'afterimage': False, 'speedLines': False, 'glints': False, 'ribbon': {'minSpeed': 999, 'frames': 1}},
        'mocap': {'capture': args.capture, 'lead': args.lead, 'sourceStart': src.get('start') or 0},
        'performances': {
            'hero': {'keys': out_keys},
            'target': {'keys': [{'t': 0, 'pose': 'neutral', 'x': round(float(target[0]), 3), 'z': round(float(target[2]), 3), 'ry': 0},
                                {'t': dur, 'pose': 'neutral'}]},
        },
        'camera': [beat],
    }
    with open(args.out, 'w') as fh:
        json.dump(film, fh, indent=1)
    print(f'{len(out_keys)} keys, {dur}s -> {args.out}  (render stills: node engine/render.mjs --film {args.out} --still ...)')


if __name__ == '__main__':
    main()
