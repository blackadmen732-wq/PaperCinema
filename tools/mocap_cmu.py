#!/usr/bin/env python3
"""CMU MOCAP -> Paper Cinema motion. Real recorded swordplay on our skeleton.

    python3 tools/mocap_cmu.py assets/mocap/cmu/02_07.amc --out library/mocap/sword-a.json
    python3 tools/mocap_cmu.py assets/mocap/cmu/02_08.amc --start 2.0 --end 6.0 --fps 24

This is RETARGETING, not training. A recorded motion is a list of joint rotations per frame; putting
it on our skeleton is a name-to-name copy plus a change of coordinates. No GPU, no model, no learning.
library/mocap-bonemap.json documents which CMU joint drives which of our bones.

How it works, and why it is short: tools/mocap.py already turns 3D joint POSITIONS into our channels
(stance, crouch, stride, phase, the arm and spine angles, ground contacts) and it is tested against
video capture. So this file does the one thing that was missing — read ASF/AMC and run forward
kinematics to get positions — then hands them to that same solver (AGENTS.md rule 00).

ASF/AMC forward kinematics, the standard formulation:
    C        = Rz(cz)Ry(cy)Rx(cx)          the bone's rest axis, from the ASF `axis` line
    M        = the frame's rotation, built from the AMC values in the bone's `dof` order
    R_global = R_parent . C . M . C-1
    tip      = base + R_global . (direction * length)      and each child's base is this tip

Scale: left in ASF units on purpose. solve() rescales by LEG_LEN / median(measured leg), so the
performer is fitted to our figure's proportions whatever the capture subject's height was.
"""
import argparse
import json
import math
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mocap  # the proven solver (tools/mocap.py)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --------------------------------------------------------------------------------------- ASF
def read_asf(path):
    """Bone table: name -> dict(direction, length, axis, axis_order, dof) plus the parent map."""
    txt = open(path, errors='replace').read()
    bones = {'root': dict(direction=np.zeros(3), length=0.0, axis=np.zeros(3),
                          axis_order='XYZ', dof=['tx', 'ty', 'tz', 'rx', 'ry', 'rz'])}
    sec = None
    cur = None
    for raw in txt.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith(':'):
            sec = line[1:].split()[0]
            continue
        if sec == 'root':
            k, *v = line.split()
            if k == 'order':
                bones['root']['dof'] = [t.lower() for t in v]
            elif k == 'axis':
                bones['root']['axis_order'] = v[0].upper()
        elif sec == 'bonedata':
            if line == 'begin':
                cur = {}
            elif line == 'end':
                bones[cur['name']] = cur
                cur = None
            elif cur is not None:
                k, *v = line.split()
                if k == 'name':
                    cur['name'] = v[0]
                elif k == 'direction':
                    cur['direction'] = np.array([float(x) for x in v])
                elif k == 'length':
                    cur['length'] = float(v[0])
                elif k == 'axis':
                    cur['axis'] = np.array([float(x) for x in v[:3]])
                    cur['axis_order'] = v[3].upper() if len(v) > 3 else 'XYZ'
                elif k == 'dof':
                    cur['dof'] = [t.lower() for t in v]
        elif sec == 'hierarchy' and line not in ('begin', 'end'):
            parts = line.split()
            for child in parts[1:]:
                bones.setdefault(child, {}).setdefault('parent', parts[0])
    for b in bones.values():
        b.setdefault('dof', [])
        b.setdefault('direction', np.zeros(3))
        b.setdefault('length', 0.0)
        b.setdefault('axis', np.zeros(3))
        b.setdefault('axis_order', 'XYZ')
    return bones


def read_amc(path):
    """-> list of frames, each {bone: [values]} in the bone's dof order."""
    frames, cur = [], None
    for raw in open(path, errors='replace'):
        line = raw.strip()
        if not line or line.startswith(('#', ':', '!')):
            continue
        if re.fullmatch(r'\d+', line):
            if cur is not None:
                frames.append(cur)
            cur = {}
            continue
        if cur is None:
            continue
        p = line.split()
        cur[p[0]] = [float(x) for x in p[1:]]
    if cur:
        frames.append(cur)
    return frames


def rot(order, deg):
    """Rotation for an axis order string ('XYZ') and matching degrees, applied Rz.Ry.Rx style."""
    R = np.eye(3)
    fn = {'X': mocap.Rx, 'Y': mocap.Ry, 'Z': mocap.Rz}
    for ax, d in zip(order, deg):
        R = fn[ax](math.radians(d)) @ R
    return R


# --------------------------------------------------------------------------------- kinematics
def forward(bones, frame):
    """-> {bone: (base, tip)} world positions in ASF units, plus {bone: R_global}."""
    C = {}
    for n, b in bones.items():
        c = rot(b['axis_order'], b['axis'])
        C[n] = (c, c.T)                                   # C and C-1 (a rotation's inverse is its transpose)
    pos, rots = {}, {}
    root_v = frame.get('root', [0] * 6)
    dof = bones['root']['dof']
    t = np.array([root_v[dof.index(k)] if k in dof else 0.0 for k in ('tx', 'ty', 'tz')])
    rdeg = [root_v[dof.index(k)] if k in dof else 0.0 for k in ('rx', 'ry', 'rz')]
    rots['root'] = rot(bones['root']['axis_order'], rdeg)
    pos['root'] = (t, t)

    order, seen = [], {'root'}
    changed = True
    while changed:                                         # parents before children
        changed = False
        for n, b in bones.items():
            if n in seen or 'parent' not in b:
                continue
            if b['parent'] in seen:
                order.append(n)
                seen.add(n)
                changed = True
    for n in order:
        b = bones[n]
        p = b['parent']
        c, ci = C[n]
        vals = frame.get(n, [])
        deg = {k: v for k, v in zip(b['dof'], vals)}
        M = rot('XYZ', [deg.get('rx', 0.0), deg.get('ry', 0.0), deg.get('rz', 0.0)])
        R = rots[p] @ c @ M @ ci
        base = pos[p][1]
        rots[n] = R
        pos[n] = (base, base + R @ (b['direction'] * b['length']))
    return pos, rots


# ------------------------------------------------------------------------- CMU -> MediaPipe slots
# solve() expects MediaPipe's 33 landmarks. We fill the ones it reads; the face and finger slots it
# ignores are left at the head/hand position rather than invented.
def landmarks(pos, rots):
    P = np.zeros((33, 3))
    base = lambda n: pos[n][0]
    tip = lambda n: pos[n][1]

    P[mocap.LSH], P[mocap.RSH] = base('lhumerus'), base('rhumerus')
    P[mocap.LEL], P[mocap.REL] = base('lradius'), base('rradius')
    P[mocap.LWR], P[mocap.RWR] = base('lwrist'), base('rwrist')
    for side, hand in (('L', 'lhand'), ('R', 'rhand')):
        h = tip(hand)
        for i in ((mocap.LPI, mocap.LIN) if side == 'L' else (mocap.RPI, mocap.RIN)):
            P[i] = h

    P[mocap.LHIP], P[mocap.RHIP] = base('lfemur'), base('rfemur')
    P[mocap.LKN], P[mocap.RKN] = base('ltibia'), base('rtibia')
    P[mocap.LAN], P[mocap.RAN] = base('lfoot'), base('rfoot')
    P[mocap.LTO], P[mocap.RTO] = tip('ltoes'), tip('rtoes')
    # CMU has no heel marker: put it the same distance behind the ankle that the toe is in front.
    for an, to, he in ((mocap.LAN, mocap.LTO, mocap.LHE), (mocap.RAN, mocap.RTO, mocap.RHE)):
        P[he] = P[an] - (P[to] - P[an]) * 0.45

    head_b, head_t = base('head'), tip('head')
    P[mocap.NOSE] = head_t
    ear = rots['head'] @ np.array([1.0, 0.0, 0.0])          # head's own left/right axis
    half = 0.35 * np.linalg.norm(head_t - head_b)
    P[mocap.LEAR], P[mocap.REAR] = head_b + ear * half, head_b - ear * half
    for i in (1, 2, 3, 4, 5, 6, 9, 10):                     # eyes and mouth: unused by solve()
        P[i] = head_t
    return P


def convert(asf, amc, fps_out=24, start=0.0, end=None, src_fps=120, mirror=False):
    bones = read_asf(asf)
    frames = read_amc(amc)
    i0 = int(start * src_fps)
    i1 = len(frames) if end is None else min(len(frames), int(end * src_fps))
    step = max(1, round(src_fps / fps_out))
    picked = list(range(i0, i1, step))
    if len(picked) < 2:
        raise SystemExit(f'only {len(picked)} frames in that range')

    # ANTI-ALIAS BEFORE DECIMATING. This used to take every `step`th frame (every 5th, for 120 Hz
    # CMU into a 24 fps film) and throw the other four away. That is textbook aliasing: anything in
    # the source above the output's Nyquist - 12 Hz here - folds down and comes back as
    # frame-to-frame jitter. It is why clean 120 Hz laboratory capture arrived in this project
    # trembling, with channels reversing direction 53-63% of frames (tools/jitter.mjs).
    #
    # So every source frame in the range is solved, the result is low-passed with a Hann window
    # about two output frames wide, and only then is it sampled. Timing is untouched - the samples
    # land on exactly the same instants as before - and the cost is solving 5x more frames, which
    # for an 18-second clip is 2250 instead of 451.
    full = list(range(i0, i1))
    Pf = np.zeros((len(full), 33, 3))
    for k, fi in enumerate(full):
        pos, rots = forward(bones, frames[fi])
        Pf[k] = landmarks(pos, rots)

    if step > 1 and len(full) > 2 * step + 1:
        n = 2 * step + 1                                   # ~2 output frames wide
        w = np.hanning(n + 2)[1:-1]
        w /= w.sum()
        pad = n // 2
        # Edge-replicated padding: a zero pad would drag the first and last frames toward the origin.
        Pp = np.concatenate([np.repeat(Pf[:1], pad, axis=0), Pf, np.repeat(Pf[-1:], pad, axis=0)], axis=0)
        Ps = np.empty_like(Pf)
        for j in range(33):
            for ax in range(3):
                Ps[:, j, ax] = np.convolve(Pp[:, j, ax], w, mode='valid')
        Pf = Ps

    P = Pf[[fi - i0 for fi in picked]]

    # CMU ASF is Y-up with the subject's forward along +Z; ours is Y-up with forward along -Z,
    # so Z flips. Flipping one axis mirrors handedness, so X flips too and left stays left.
    P = P * np.array([-1.0, 1.0, -1.0])
    if mirror:
        P[:, :, 0] *= -1.0
        P = mocap.swap(P, [(mocap.LSH, mocap.RSH), (mocap.LEL, mocap.REL), (mocap.LWR, mocap.RWR),
                           (mocap.LHIP, mocap.RHIP), (mocap.LKN, mocap.RKN), (mocap.LAN, mocap.RAN),
                           (mocap.LHE, mocap.RHE), (mocap.LTO, mocap.RTO), (mocap.LEAR, mocap.REAR)])

    pelvis = 0.5 * (P[:, mocap.LHIP] + P[:, mocap.RHIP])
    P = P - pelvis[:, None, :]                              # solve() wants landmarks around the pelvis
    t = np.arange(len(picked), dtype=float) / fps_out
    return t, P, pelvis, bones


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('amc', help='assets/mocap/cmu/02_07.amc')
    ap.add_argument('--asf', help='default: the 02.asf beside it')
    ap.add_argument('--out', help='library/mocap/<name>.json')
    ap.add_argument('--fps', type=int, default=24)
    ap.add_argument('--src-fps', type=int, default=120)
    ap.add_argument('--start', type=float, default=0.0)
    ap.add_argument('--end', type=float)
    ap.add_argument('--mirror', action='store_true', help='left-handed performer -> right-handed')
    ap.add_argument('--smooth', type=float, default=0.15,
                    help='Savitzky-Golay window in seconds on the solved channels (0.15 = the video '
                         'path default). Raise it for a calmer clip, lower it to keep a sharper hit.')
    ap.add_argument('--inspect', action='store_true', help='print measurements and write nothing')
    a = ap.parse_args()

    asf = a.asf or os.path.join(os.path.dirname(a.amc), '02.asf')
    t, P, pelvis, bones = convert(asf, a.amc, a.fps, a.start, a.end, a.src_fps, a.mirror)

    thigh = np.linalg.norm(P[:, mocap.LHIP] - P[:, mocap.LKN], axis=1)
    shin = np.linalg.norm(P[:, mocap.LKN] - P[:, mocap.LAN], axis=1)
    span = np.linalg.norm(P[:, mocap.LSH] - P[:, mocap.RSH], axis=1)
    up = (0.5 * (P[:, mocap.LSH] + P[:, mocap.RSH]) - 0.5 * (P[:, mocap.LAN] + P[:, mocap.RAN]))[:, 1]
    print(f'{len(t)} frames at {a.fps} fps = {t[-1]:.1f}s')
    print(f'  thigh {thigh.mean():.3f} shin {shin.mean():.3f} shoulders {span.mean():.3f} (ASF units, constant = FK is sound)')
    print(f'  bone-length wobble: thigh {thigh.std():.5f}  shin {shin.std():.5f}   (should be ~0)')
    print(f'  shoulders above ankles by {up.mean():.3f}  ({"upright" if up.mean() > 0 else "UPSIDE DOWN"})')
    if a.inspect:
        return

    ch, contacts, scale = mocap.solve(t, P, pelvis, {})
    # The SAME finishing pass the video capture path runs: a small-window Savitzky-Golay that keeps
    # the peaks and kills the jitter, then the joint limits. mocap.py has always called it and this
    # file never did, so every CMU clip in library/mocap/ skipped it. It matters most on the twist
    # and yaw channels - rsy, ny, rwx - which come from small differences between landmarks, so a
    # millimetre of position noise becomes degrees of angle noise.
    ch = mocap.post(ch, t, window_s=float(a.smooth))
    keys = [{'t': round(float(t[i]), 3), **{k: round(float(v[i]), 3) for k, v in ch.items()}}
            for i in range(len(t))]
    out = a.out or os.path.join(REPO, 'library', 'mocap', os.path.basename(a.amc).replace('.amc', '') + '.json')
    doc = {
        '_about': 'Retargeted from CMU motion capture by tools/mocap_cmu.py. keys = a performance key '
                  'list for film.performances.<id>.keys (shift t to place it).',
        'source': {'database': 'CMU Graphics Lab Motion Capture Database', 'subject': 2,
                   'file': os.path.basename(a.amc), 'motion': 'swordplay', 'src_fps': a.src_fps,
                   'licence': 'free for all uses, commercial included — see assets/mocap/CREDITS.md',
                   'bonemap': 'library/mocap-bonemap.json'},
        'fps': a.fps, 'duration': round(float(t[-1]), 3), 'scale': round(float(scale), 3),
        'facing': 'auto', 'channels': sorted(ch), 'keys': keys,
        'contacts': {k: (v.tolist() if hasattr(v, 'tolist') else v) for k, v in contacts.items()}
        if isinstance(contacts, dict) else (contacts.tolist() if hasattr(contacts, 'tolist') else contacts),
    }
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(doc, open(out, 'w'), indent=1)
    print(f'wrote {out}  ({len(keys)} keys, {len(ch)} channels, scale {scale:.3f})')


if __name__ == '__main__':
    main()
