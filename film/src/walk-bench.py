#!/usr/bin/env python3
"""WALK BENCH: Musashi walking on the Episode 1 beach, to judge the walking gait (engine/footlock.js gait v2) where Mark
sees it, in the Blender render, next to the numbers of tools/gait_check.mjs.

    python3 film/src/walk-bench.py            # -> film/walk-bench.json
    node tools/gait_check.mjs film/walk-bench.json
    RENDER_CHUNK=25 tools/film.sh film/walk-bench.json --set ganryujima-beach --workers 2 --skip-audit --res 270x480

0-0.8 s he stands; 0.8-6.2 s he walks 6.2 m along the duel ground (1.25 m/s between a 0.7 s start and a 0.9 s
stop), seen from the side; he stops and turns; 6.8-10.1 s he walks 2.2 m back at about 0.73 m/s, seen three-quarter. The
same pose ('stand-blade-low': the oar low in the right hand), the same beach, the same light as the episode. Kojiro is
in the cast only because the engine wants two performers: hidden, far away.
"""
import json
import math
import os

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'walk-bench.json')


def face(a, b):
    return round(math.atan2(b[0] - a[0], b[1] - a[1]), 4)


def lerp(a, b, u):
    return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)


def walk(keys, t0, t1, a, b, pose, step=0.5, ease_in=0.0, ease_out=0.0):
    """Root keys from a to b between t0 and t1, the pace building over ease_in and dying over ease_out seconds (as
    film/src/ganryujima-ep1.py walk(); the feet step by themselves: motion.lockFeet)."""
    ry = face(a, b)
    T = t1 - t0
    A_, B_ = min(ease_in, T / 2), min(ease_out, T / 2)
    V = 1.0 / (T - (A_ + B_) / 2)

    def s(t):
        if t < A_:
            return V * t * t / (2 * A_)
        if t > T - B_:
            return 1.0 - V * (T - t) ** 2 / (2 * B_)
        return V * (t - A_ / 2)

    n = max(1, int(round(T / step)))
    times = sorted({round(T * i / n, 4) for i in range(1, n + 1)} | ({round(A_, 4)} if A_ else set()) |
                   ({round(T - B_, 4)} if B_ else set()))
    for tt in times:
        p = lerp(a, b, s(tt))
        keys.append({'t': round(t0 + tt, 3), 'pose': pose, 'x': round(p[0], 3), 'z': round(p[1], 3), 'ry': ry})


# along the levelled duel ground (film z 0, the sand flat at 0.94 m from x -3 to +4; Episode 1's own path starts in
# the surf, where the sea hid the legs for the first 3 s of the first bench render)
A, B = (-3.0, 0.0), (3.2, 0.0)                    # 6.2 m
C = lerp(B, A, 2.2 / math.dist(A, B))             # back, 2.2 m
POSE = 'stand-blade-low'
keys = [{'t': 0.0, 'pose': POSE, 'x': A[0], 'z': A[1], 'ry': face(A, B)},
        {'t': 0.8, 'pose': POSE, 'x': A[0], 'z': A[1], 'ry': face(A, B)}]
walk(keys, 0.8, 0.8 + math.dist(A, B) / 1.25 + 0.4, A, B, POSE, ease_in=0.7, ease_out=0.9)
t_stop = keys[-1]['t']
keys += [{'t': round(t_stop + 0.5, 3), 'pose': POSE, 'x': B[0], 'z': B[1], 'ry': face(A, B), 'settle': 0.4},
         {'t': 6.8, 'pose': POSE, 'x': B[0], 'z': B[1], 'ry': face(B, C)}]
walk(keys, 6.8, 6.8 + 2.2 / 0.73 + 0.3, B, C, POSE, ease_in=0.5, ease_out=0.6)
keys.append({'t': 10.6, 'pose': POSE, 'x': round(C[0], 3), 'z': round(C[1], 3), 'ry': face(B, C), 'settle': 0.4})

film = {
    'title': 'Walk bench: the walking gait on the Episode 1 beach',
    'page': 'engine/motion.html', 'fps': 30, 'width': 1080, 'height': 1920, 'format': 'vertical',
    'duration': 10.8, 'mode': 'dawn',
    'motion': {'overlap': True, 'lockFeet': True},
    'stage': {'mark': 'MARK_center', 'origin': True, 'turn': 0},
    'cast': {'hero': {'character': 'musashi', 'face': 'eyes', 'weapon': 'bokken', 'recipe': 'musashi-ai',
                      'weaponPart': 'bokken_oar_t1'},
             'target': {'character': 'kojiro', 'face': 'eyes', 'recipe': 'kojiro-ai2', 'hidden': True}},
    'performances': {
        'hero': {'keys': keys, 'gait': {'arms': [0.25, 1.0], 'note': 'the right hand carries the oar low: a small swing; the left arm is free'}},
        'target': {'keys': [{'t': 0.0, 'pose': 'neutral', 'x': 30.0, 'z': 30.0, 'ry': 0.0}]},
    },
    'paperSurface': {'angle': 36.0, 'ink': 0.85, 'width': 0.003, 'light': 0.55, 'mottle': 0.12, 'mottle_scale': 7.0, 'ao': 0.35},
    'wind': {'to': [0.15, -1.0], 'strength': 3.2, 'gust': 0.6, 'seed': 2},
    'cameraOpts': {'solver': 2, 'aperture': 4.0},
    'effects': {'dof': 4.0, 'motionBlur': 0.5, 'vignette': 0.3, 'postFx': True},
    'fade': {'in': 0, 'out': 0.0},
    'camera': [
        {'t': 0.0, 'rig': 'compose', 'subjects': ['hero'], 'basis': 'facing', 'az0': 88, 'az1': 92, 'elev': 3, 'size': 0.62,
         'screen': [0.5, 0.56], 'fov': 30, 'feel': 'dolly', 'note': 'SIDE: the whole body and the ground, the legs read in profile'},
        {'t': 6.5, 'cut': True, 'rig': 'compose', 'subjects': ['hero'], 'basis': 'facing', 'az0': 35, 'az1': 45, 'elev': 4,
         'size': 0.62, 'screen': [0.5, 0.56], 'fov': 30, 'feel': 'dolly', 'note': 'THREE-QUARTER: the slow walk, hips and arms'},
    ],
    'sounds': [], 'titles': [],
}
json.dump(film, open(OUT, 'w'), indent=1)
print('->', OUT, '%d keys, walk 1 ends at %.2f s' % (len(keys), t_stop))
