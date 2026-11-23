#!/usr/bin/env python3
"""Synthetic accuracy test for tools/mocap.py (docs/MOCAP.md §5).

Our own figure performs known moves (film/mocap-synth.json, locked camera). We know every channel on every
frame (tools/mocap_truth.mjs), so we can measure what the capture gets back:
  A. solver only: the figure's true joint positions -> solve() -> channels   (checks the maths and the signs)
  B. full chain:  rendered video -> MediaPipe -> solve() -> channels          (what a real clip gets)

    python3 tools/mocap_synth_test.py                 # A, and B if output/mocap/synth.mp4 exists
    python3 tools/mocap_synth_test.py --render        # renders the video first (~10 min on 4 CPU cores)
"""
import argparse
import json
import math
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mocap as M  # noqa: E402

FILM = 'film/mocap-synth.json'
TRUTH = 'output/mocap/synth-truth.json'
VIDEO = 'output/mocap/synth.mp4'
CAP = 'output/mocap/synth-capture.json'
ANG = ['ry', 'tx', 'ty', 'tz', 'cx', 'cy', 'cz', 'rsx', 'rsy', 'rsz', 'rex', 'rwx', 'lsx', 'lsy', 'lsz', 'lex', 'nx', 'ny', 'hx', 'hy']
LIN = ['x', 'z', 'y', 'stance', 'crouch', 'weight']
# joint names in the truth file -> MediaPipe landmark indices
MAP = {'nose': [M.NOSE], 'lear': [M.LEAR], 'rear': [M.REAR], 'lshoulder': [M.LSH], 'rshoulder': [M.RSH], 'lelbow': [M.LEL],
       'relbow': [M.REL], 'lwrist': [M.LWR], 'rwrist': [M.RWR], 'lhip': [M.LHIP], 'rhip': [M.RHIP], 'lknee': [M.LKN],
       'rknee': [M.RKN], 'lankle': [M.LAN, M.LHE], 'rankle': [M.RAN, M.RHE], 'ltoe': [M.LTO], 'rtoe': [M.RTO]}


def effective_arm(ch, side):
    """The direction the upper arm and forearm point in the chest frame is what a camera can see; Euler
    angles have twins (same arm, other angles), so arms are compared as directions (degrees)."""
    return M.euler_xyz(ch[side + 'sx'], ch[side + 'sy'], ch[side + 'sz'])


def arm_dir_errors(truth, rec, side):
    up, fo = [], []
    for a, b in zip(truth, rec):
        Ra, Rb = effective_arm(a, side), effective_arm(b, side)
        ua, ub = Ra @ [0, -1, 0], Rb @ [0, -1, 0]
        fa, fb = Ra @ M.Rx(a[side + 'ex']) @ [0, -1, 0], Rb @ M.Rx(b[side + 'ex']) @ [0, -1, 0]
        up.append(math.degrees(math.acos(np.clip(np.dot(ua, ub), -1, 1))))
        fo.append(math.degrees(math.acos(np.clip(np.dot(fa, fb), -1, 1))))
    return np.array(up), np.array(fo)


def report(title, truth, rec, skip=()):
    print(f'\n== {title}  ({len(rec)} frames)')
    print(f'{"channel":8} {"MAE":>8} {"RMS":>8} {"max":>8}  unit')
    rows = {}
    for c in ANG + LIN:
        if c in skip:
            continue
        a = np.array([f[c] for f in truth]); b = np.array([f.get(c, 0.0) for f in rec])
        if c in ('ry',):
            d = np.angle(np.exp(1j * (b - a)))
        else:
            d = b - a
        unit, k = ('deg', 180 / math.pi) if c in ANG else ('cm', 100) if c != 'weight' else ('', 1)
        rows[c] = (np.abs(d).mean() * k, math.sqrt((d ** 2).mean()) * k, np.abs(d).max() * k)
        print(f'{c:8} {rows[c][0]:8.2f} {rows[c][1]:8.2f} {rows[c][2]:8.2f}  {unit}')
    for side in ('r', 'l'):
        up, fo = arm_dir_errors(truth, rec, side)
        print(f'{side}-arm direction: upper arm {up.mean():.1f} deg mean ({np.percentile(up, 90):.1f} p90), forearm {fo.mean():.1f} deg mean ({np.percentile(fo, 90):.1f} p90)')
        rows[side + 'arm'] = (up.mean(), fo.mean())
    return rows


def truth_frames():
    if not os.path.exists(TRUTH):
        subprocess.run(['node', 'tools/mocap_truth.mjs', FILM, '--who', 'hero', '--out', TRUTH], check=True)
    return json.load(open(TRUTH))['frames']


def test_solver(frames):
    """A: true joints -> solver (scale 1: the figure IS our figure)."""
    t = np.array([f['t'] for f in frames])
    P = np.zeros((len(frames), 33, 3))
    for n, f in enumerate(frames):
        j = f['joints']
        for name, idx in MAP.items():
            for i in idx:
                P[n, i] = j[name]
        # hands: no finger joints on the paper figure: put index/pinky along the forearm (wrist straight)
        for wr, el, pi, ix in ((M.RWR, M.REL, M.RPI, M.RIN), (M.LWR, M.LEL, M.LPI, M.LIN)):
            d = M.unit(P[n, wr] - P[n, el])
            P[n, pi] = P[n, ix] = P[n, wr] + 0.08 * d
        P[n, M.RHE] = P[n, M.RAN]; P[n, M.LHE] = P[n, M.LAN]
    pel = 0.5 * (P[:, M.LHIP] + P[:, M.RHIP])
    ch, cont, s = M.solve(t, P - pel[:, None, :], pel, {'scale': 1.0, 'head': True, 'nose_pitch': 0.0})
    rec = [{k: float(v[i]) for k, v in ch.items()} for i in range(len(t))]
    tr = [f['ch'] for f in frames]
    return report('A. solver only (true joints -> channels)', tr, rec, skip=('rwx',))


def test_video(frames, hfov):
    cap = json.load(open(CAP))
    keys = cap['keys']
    tt = np.array([k['t'] for k in keys])
    tr_t = np.array([f['t'] for f in frames])
    # align: --facing auto puts the start at 0,0 facing +z; the truth starts at its own place
    x0, z0, ry0 = frames[0]['ch']['x'], frames[0]['ch']['z'], frames[0]['ch']['ry']
    rec, tr = [], []
    for k in keys:
        i = int(np.argmin(np.abs(tr_t - k['t'])))
        if abs(tr_t[i] - k['t']) > 0.021:
            continue
        r = dict(k); r['x'] += x0; r['z'] += z0; r['ry'] += ry0
        rec.append(r); tr.append(frames[i]['ch'])
    return report(f'B. full chain (rendered video -> MediaPipe -> channels, hfov {hfov:.1f})', tr, rec)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--render', action='store_true', help='render output/mocap/synth.mp4 first')
    ap.add_argument('--model', default='full')
    args = ap.parse_args()
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    frames = truth_frames()
    test_solver(frames)
    film = json.load(open(FILM))
    # the film's camera: vertical fov 40 on a 960 x 720 frame -> horizontal fov
    vf = film['camera'][0].get('fov', 36)
    hfov = math.degrees(2 * math.atan(math.tan(math.radians(vf) / 2) * film['width'] / film['height']))
    if args.render:
        subprocess.run(['nice', '-n', '10', 'node', 'engine/render.mjs', '--film', FILM, '--out', VIDEO,
                        '--frames', 'output/mocap/synth-frames'], check=True)
    if os.path.exists(VIDEO):
        subprocess.run([sys.executable, 'tools/mocap.py', VIDEO, '--out', CAP, '--hfov', f'{hfov:.2f}', '--model', args.model,
                        '--facing', 'auto'], check=True)
        test_video(frames, hfov)
    else:
        print(f'\n(no {VIDEO}: run with --render for the full-chain test)')


if __name__ == '__main__':
    main()
