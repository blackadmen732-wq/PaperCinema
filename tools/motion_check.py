#!/usr/bin/env python3
"""MOTION CHECK: does a film's motion look alive, or robotic? Measured on the exported timeline (the poses the render
uses), against the three things that make AI animation look robotic (Mark, 27 Nov, from a reference short): bad
easing, one element finishing before the next starts, and no anticipation / follow-through.

    python3 tools/motion_check.py <film> [--json]        (reads output/<film>.timeline.json and film/<film>.json)

For every frame and actor: how much the body moves (joint speeds summed, rad/s, plus the root's travel). Then:
  statues       stretches where NO living body moves (both still > 1 s)         FAIL above 6 s in total
  frozen        one living actor still for more than 3 s                        FAIL (each stretch is listed)
  one at a time seconds where one actor acts while the other is a statue          reported (a story choice, in limits)
  hard starts   still -> fast within 2 frames (no ease-in, no anticipation)      FAIL if any
  hard stops    fast -> still within 2 frames (no ease-out, no settle)           FAIL if any
An actor whose performances.<id>.life is 0 (a dead body) is not "frozen": stillness is right for it. Hidden actors
and cuts (a teleport at a cut) are skipped.
"""
import json
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STILL = 0.15          # rad/s summed over the joints (+ m/s of the root x 4): below this a body reads as still


def life_at(L, t):
    if not L:
        return 1.0
    if t <= L[0][0]:
        return L[0][1]
    for (t0, a), (t1, b) in zip(L, L[1:]):
        if t <= t1:
            return a + (b - a) * (t - t0) / max(1e-6, t1 - t0)
    return L[-1][1]


def runs(mask, min_len):
    out, s = [], None
    for i, v in enumerate(list(mask) + [False]):
        if v and s is None:
            s = i
        if not v and s is not None:
            if i - s >= min_len:
                out.append((s, i - 1))
            s = None
    return out


def main():
    name = sys.argv[1]
    TL = json.load(open(os.path.join(REPO, 'output', name + '.timeline.json')))
    F = json.load(open(os.path.join(REPO, 'film', name + '.json')))
    fr = TL['frames']
    fps = float(TL['clock']['fps'])
    actors = list(F.get('cast') or {})
    cuts = {i for i, f in enumerate(fr) if f.get('cut')}
    speed, alive = {}, {}
    for a in actors:
        p0 = next((f['actors'][a]['pose'] for f in fr if isinstance((f['actors'].get(a) or {}).get('pose'), dict)), {})
        chs = [c for c, v in p0.items() if isinstance(v, (int, float)) and c not in ('x', 'y', 'z', 'stride', 'phase')]
        rows, vis = [], []
        for f in fr:
            act = f['actors'].get(a) or {}
            p = act.get('pose') if isinstance(act.get('pose'), dict) else {}
            vis.append(bool(p) and not act.get('hidden'))
            rows.append([float(p.get(c, 0.0)) for c in chs] + [float(p.get('x', 0.0)), float(p.get('z', 0.0))])
        A = np.array(rows)
        d = np.abs(np.diff(A, axis=0)) * fps
        sp = np.concatenate([[0.0], d[:, :-2].sum(1) + 4.0 * np.hypot(d[:, -2], d[:, -1])])
        for i in sorted(cuts):                           # a teleport hidden by a cut is not motion
            for k in range(-2, 3):
                if 0 < i + k < len(sp) and sp[i + k] > 8.0:
                    sp[i + k] = sp[i - 3] if i > 3 else 0.0
        L = ((F.get('performances') or {}).get(a) or {}).get('life')
        speed[a] = sp
        alive[a] = np.array([vis[i] and life_at(L, f.get('tb', f['t'])) > 0.05 for i, f in enumerate(fr)])
    rep = {'film': name, 'frames': len(fr), 'fps': fps}
    still = {a: (speed[a] < STILL) for a in actors}
    both = np.ones(len(fr), bool)
    for a in actors:
        both &= (still[a] | ~alive[a])
    both &= np.array([any(alive[a][i] for a in actors) for i in range(len(fr))])
    st = runs(both, int(fps))
    rep['statues'] = [(round(fr[s]['t'], 2), round(fr[e]['t'], 2)) for s, e in st]
    rep['statue_s'] = round(sum(e - s + 1 for s, e in st) / fps, 2)
    rep['frozen'] = {}
    for a in actors:
        fz = runs(still[a] & alive[a], int(3 * fps))
        rep['frozen'][a] = [(round(fr[s]['t'], 2), round(fr[e]['t'], 2)) for s, e in fz]
    if len(actors) == 2:
        x, y = actors
        rep['one_at_a_time_s'] = {x: round(float(((speed[x] > 1.0) & still[y] & alive[y]).sum()) / fps, 2),
                                  y: round(float(((speed[y] > 1.0) & still[x] & alive[x]).sum()) / fps, 2)}
    hs, hp = [], []
    for a in actors:
        sp = speed[a]
        for i in range(4, len(sp) - 5):
            if any((i - k) in cuts for k in range(-3, 7)):        # a cut, the teleport it hides, a cut into motion
                continue
            # a hard START: still for 3 frames, then fast; a hard STOP: fast, then still for 5 frames (a reversal at the
            # turning point of an overshoot passes through zero speed and is not a stop)
            if max(sp[i - 4:i - 1]) < 0.3 and sp[i] > 3.0:
                hs.append((a, round(fr[i]['t'], 2)))
            if sp[i - 2] > 3.0 and max(sp[i:i + 5]) < 0.3:
                hp.append((a, round(fr[i]['t'], 2)))
    rep['hard_starts'], rep['hard_stops'] = hs, hp
    fails = []
    if rep['statue_s'] > 6.0:
        fails.append('statues: %.1f s with no living body moving (limit 6 s)' % rep['statue_s'])
    for a, fz in rep['frozen'].items():
        for s, e in fz:
            fails.append('%s frozen %.1f-%.1f s (%.1f s)' % (a, s, e, e - s))
    if hs:
        fails.append('hard starts (no ease-in / anticipation): %s' % hs[:8])
    if hp:
        fails.append('hard stops (no ease-out / settle): %s' % hp[:8])
    rep['verdict'] = 'FAIL' if fails else 'PASS'
    rep['fails'] = fails
    if '--json' in sys.argv:
        print(json.dumps(rep, indent=1))
    else:
        print('[motion] %s: %s' % (name, rep['verdict']))
        print('  statues (no living body moves > 1 s): %.1f s %s' % (rep['statue_s'], rep['statues']))
        for a, fz in rep['frozen'].items():
            print('  %s frozen > 3 s: %s' % (a, fz or 'none'))
        if 'one_at_a_time_s' in rep:
            print('  one acts while the other is a statue: %s' % rep['one_at_a_time_s'])
        print('  hard starts: %s   hard stops: %s' % (hs[:6] or 'none', hp[:6] or 'none'))
        for f_ in fails:
            print('  FAIL', f_)
    json.dump(rep, open(os.path.join(REPO, 'output', name + '.motion-check.json'), 'w'), indent=1)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
