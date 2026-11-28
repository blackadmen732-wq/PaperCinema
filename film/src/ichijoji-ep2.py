"""Generator for film/ichijoji-ep2.json: Episode 2, Musashi and the Yoshioka school at Ichijo-ji (1604).
    python3 film/src/ichijoji-ep2.py [out.json]        (default: film/ichijoji-ep2.json)
then: node engine/validate.mjs film/ichijoji-ep2.json && node tools/timeline.mjs film/ichijoji-ep2.json &&
python3 tools/motion_check.py ichijoji-ep2 && node tools/footslide.mjs film/ichijoji-ep2.json &&
node tools/gait_check.mjs film/ichijoji-ep2.json
Made the way Episode 1 was (film/src/ganryujima-ep1.py), from data only: the same walk() helper, poses from
library/poses.json, the compose camera, titles and the synthesised score. History and its confidence marks:
research/ichijoji.md. Set: library/sets/ichijoji-crossroads.json (render with --set ichijoji-crossroads).
Coordinates: film three.js (x right = east, z toward the south, y up), origin = MARK_center = the crossing of the two
roads, staged with stage.origin so film (x, z) = set (x, -z). Facing: ry 0 = +z.
Cast order matters: the engine tracks heads toward the first OTHER cast member and measures the blade contact between
the first two, so Musashi is first (every Yoshioka man looks at him) and the boy is second (the contact is his)."""
import json
import math
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else 'film/ichijoji-ep2.json'
DUR = 50.5


def face(a, b):
    """ry for a figure at a looking at b (ry 0 = +z)."""
    return round(math.atan2(b[0] - a[0], b[1] - a[1]), 3)


def lerp(a, b, u):
    return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)


def walk(keys, t0, t1, a, b, pose, step=0.5, ease_in=0.0, ease_out=0.0, **extra):
    """Root keys from a to b between t0 and t1 (the feet step by themselves: motion.lockFeet); ease_in / ease_out =
    seconds over which the pace builds from a stand / dies into a stop. Same helper as Episode 1's generator."""
    ry = face(a, b)
    T, D = t1 - t0, 1.0
    A_, B_ = min(ease_in, T / 2), min(ease_out, T / 2)
    V = D / (T - (A_ + B_) / 2)

    def s(t):
        if t < A_:
            return V * t * t / (2 * A_)
        if t > T - B_:
            return D - V * (T - t) ** 2 / (2 * B_)
        return V * (t - A_ / 2)

    n = max(1, int(round(T / step)))
    times = sorted({round(T * i / n, 4) for i in range(1, n + 1)} | ({round(A_, 4)} if A_ else set()) |
                   ({round(T - B_, 4)} if B_ else set()))
    for tt in times:
        p = lerp(a, b, s(tt))
        keys.append(dict({'t': round(t0 + tt, 3), 'pose': pose, 'x': round(p[0], 3), 'z': round(p[1], 3),
                          'ry': ry}, **extra))


def k(t, pose, p, ry, **extra):
    return dict({'t': t, 'pose': pose, 'x': round(p[0], 3), 'z': round(p[1], 3), 'ry': round(ry, 3)}, **extra)


# ---- places (film coordinates; the hanging pine's trunk at set (3.4, 3.6) = film (3.4, -3.6)) ----
PINE = (3.4, -3.6)
WEST = (-12.0, 0.0)                # down the Kyoto road, where the Yoshioka come from
SOUTH = (1.0, 12.0)                # down the hill road (the boy and C watch it)
NORTH = (-0.5, -14.0)              # up the hill road (A watches it)
M0 = (4.7, -4.5)                   # Musashi, waiting in the dark behind the trunk (he came early: tradition)
M1 = (2.5, -2.3)                   # out from behind the pine, behind the boy
M2 = (1.95, -1.95)                 # the step into the cut
M_END = (11.5, -0.4)               # walking away east along the road, into the mist
B0, B1 = (-11.0, 0.2), (1.0, -1.3)           # the boy: along the road to the foot of the pine
A0, A1 = (-12.0, -1.0), (-0.5, -2.3)         # retainer A (kabuto): on the boy's right
C0, C1 = (-12.4, 1.3), (0.2, 1.0)            # retainer C (hood): on his left
A_HIT = (0.95, -2.35)              # A's charge ends here
C_HIT = (1.85, -0.75)              # C's thrust ends here

mus, boy, ra, rc = [], [], [], []
# ---------------- Musashi (hero) ----------------
mus += [
    k(0.0, 'stand-blade-low', M0, face(M0, B1) - 0.25, hy=0.1, note='S1 hook: his eyes in the dark under the pine'),
    k(2.6, 'stand-blade-low', M0, face(M0, B1) - 0.25, hy=0.05),
    k(6.5, 'stand-blade-low', M0, face(M0, B1) - 0.1, hy=-0.25, note='he hears them on the road'),
    k(10.5, 'stand-blade-low', M0, face(M0, B1), hy=-0.1, crouch=0.06),
    k(12.4, 'chudan', M0, face(M0, B1), settle=0.6, note='the blade comes up: he has decided'),
    k(13.6, 'chudan', M0, face(M0, M1), tx=0.08, note='a small lean before the first step (anticipation)'),
]
walk(mus, 13.7, 16.7, M0, M1, 'chudan', ease_in=0.7, ease_out=0.8)
mus += [
    k(17.1, 'chudan', M1, face(M1, B1), settle=0.4),
    k(17.45, 'kesa-windup', M2, face(M2, B1), note='S4 the step in, the blade high'),
    k(17.85, 'kesa-contact', M2, face(M2, B1), note='the cut: the boy first (tradition)'),
    k(18.2, 'kesa-finish', M2, face(M2, B1), settle=0.9),
    k(20.2, 'kesa-finish', M2, face(M2, B1)),
    k(21.4, 'chudan', M2, face(M2, A1), settle=0.6, note='S5 turns on the first retainer'),
    k(22.5, 'chudan', M2, face(M2, A_HIT), crouch=0.08),
    k(22.85, 'dodge-lean', M2, face(M2, A_HIT), note='slips the downcut'),
    k(23.15, 'yoko-contact', M2, face(M2, A_HIT), note='the side cut'),
    k(23.45, 'yoko-finish', M2, face(M2, A_HIT), settle=0.8),
    k(25.0, 'yoko-finish', M2, face(M2, A_HIT)),
    k(26.0, 'chudan', M2, face(M2, C1), settle=0.6, note='the last man'),
    k(27.0, 'chudan', M2, face(M2, C_HIT), crouch=0.1),
    k(27.45, 'low-dodge', M2, face(M2, C_HIT), note='under the thrust'),
    k(27.8, 'kiri-age-contact', M2, face(M2, C_HIT), note='the rising cut'),
    k(28.1, 'kiri-age-finish', M2, face(M2, C_HIT), settle=0.9),
    k(30.0, 'kiri-age-finish', M2, face(M2, C_HIT)),
    k(31.2, 'zanshin', M2, face(M2, C_HIT), settle=0.7, note='zanshin'),
    k(33.2, 'zanshin', M2, face(M2, B1), hy=-0.2, note='his eyes go to the boy'),
    k(34.2, 'chiburi-raise', M2, face(M2, B1)),
    k(34.6, 'chiburi-finish', M2, face(M2, B1), settle=0.8, note='the flick: paint off the blade'),
    k(35.8, 'stand-blade-low', M2, face(M2, M_END), tx=0.08, settle=0.5, note='turns east to the road, a lean before the step'),
]
walk(mus, 36.2, 43.4, M2, M_END, 'stand-blade-low', step=0.6, ease_in=0.8, ease_out=1.0)
mus += [
    k(44.2, 'stand-blade-low', M_END, face(M2, M_END), settle=0.4),
    k(45.6, 'stand-blade-low', M_END, face(M2, M_END) - 0.3, hy=-0.5, note='one look back at the pine'),
    k(DUR, 'stand-blade-low', M_END, face(M2, M_END) - 0.25, hy=-0.45),
]

# ---------------- the boy, Matashichiro (target) ----------------
boy += [k(0.0, 'stand-blade-low', B0, face(B0, B1))]
walk(boy, 3.2, 11.6, B0, B1, 'stand-blade-low', step=0.55, ease_in=0.8, ease_out=1.0)
boy += [
    k(12.8, 'stand-blade-low', B1, face(B1, SOUTH), settle=0.6, note='turns to watch the south road for Musashi'),
    k(14.6, 'stand-blade-low', B1, face(B1, SOUTH) + 0.1, hy=0.15),
    k(15.9, 'stand-blade-low', B1, face(B1, SOUTH) + 0.25, hy=0.6, note='hears the step behind him: the head first'),
    k(16.9, 'chudan', B1, face(B1, M2), settle=0.5, note='turns, the blade up, too late'),
    k(17.6, 'chudan', B1, face(B1, M2), tx=-0.1),
    k(17.9, 'struck-reel', B1, face(B1, M2), note='struck'),
    k(18.9, 'stagger', lerp(B1, (B1[0] - 0.3, B1[1] + 0.25), 1), face(B1, M2)),
    k(19.8, 'kneel-collapse', (B1[0] - 0.3, B1[1] + 0.25), face(B1, M2), settle=0.5),
    k(20.8, 'fallen', (B1[0] - 0.35, B1[1] + 0.3), face(B1, M2), settle=0.6),
    k(DUR, 'fallen', (B1[0] - 0.35, B1[1] + 0.3), face(B1, M2)),
]

# ---------------- retainer A (kabuto) ----------------
ra += [k(0.0, 'stand-blade-low', A0, face(A0, A1))]
walk(ra, 3.0, 11.2, A0, A1, 'stand-blade-low', step=0.55, ease_in=0.8, ease_out=1.0)
ra += [
    k(12.4, 'chudan', A1, face(A1, NORTH), settle=0.6, note='on guard, facing the hill road north'),
    k(15.0, 'chudan', A1, face(A1, NORTH) - 0.15, hy=0.2),
    k(18.3, 'chudan', A1, face(A1, NORTH), hy=0.5, note='hears the cut'),
    k(19.5, 'chudan', A1, face(A1, M2), settle=0.5, note='turns on Musashi'),
    k(21.6, 'furikaburi', A1, face(A1, M2), settle=0.5, note='raises the blade'),
    k(22.6, 'furikaburi', A_HIT, face(A_HIT, M2), note='the charge'),
    k(22.9, 'shomen-strike', A_HIT, face(A_HIT, M2), note='the downcut misses'),
    k(23.25, 'struck-reel', A_HIT, face(A_HIT, M2), note='cut across the body'),
    k(24.2, 'stagger', (A_HIT[0] - 0.25, A_HIT[1] - 0.2), face(A_HIT, M2)),
    k(25.2, 'kneel-collapse', (A_HIT[0] - 0.25, A_HIT[1] - 0.2), face(A_HIT, M2), settle=0.5),
    k(26.4, 'fallen', (A_HIT[0] - 0.3, A_HIT[1] - 0.25), face(A_HIT, M2), settle=0.6),
    k(DUR, 'fallen', (A_HIT[0] - 0.3, A_HIT[1] - 0.25), face(A_HIT, M2)),
]

# ---------------- retainer C (hood) ----------------
rc += [k(0.0, 'stand-blade-low', C0, face(C0, C1))]
walk(rc, 3.4, 11.8, C0, C1, 'stand-blade-low', step=0.55, ease_in=0.8, ease_out=1.0)
rc += [
    k(12.9, 'low-ready', C1, face(C1, SOUTH), settle=0.6, note='watching the south road'),
    k(15.5, 'low-ready', C1, face(C1, SOUTH) + 0.15, hy=-0.15),
    k(18.4, 'low-ready', C1, face(C1, SOUTH), hy=-0.5, note='hears the cut'),
    k(19.7, 'chudan', C1, face(C1, M2), settle=0.5, note='turns; holds back while A goes in'),
    k(23.4, 'chudan', C1, face(C1, M2), tx=-0.08, note='flinches at A\'s fall'),
    k(25.9, 'tsuki-load', C1, face(C1, M2), crouch=0.12, settle=0.5, note='gathers for the thrust'),
    k(27.0, 'tsuki-load', lerp(C1, C_HIT, 0.55), face(C1, M2), crouch=0.15),
    k(27.45, 'tsuki-thrust', C_HIT, face(C_HIT, M2), note='the thrust'),
    k(27.85, 'struck-reel', C_HIT, face(C_HIT, M2), note='cut on the rise'),
    k(28.8, 'stagger', (C_HIT[0] - 0.1, C_HIT[1] + 0.3), face(C_HIT, M2)),
    k(29.9, 'kneel-collapse', (C_HIT[0] - 0.1, C_HIT[1] + 0.3), face(C_HIT, M2), settle=0.5),
    k(31.0, 'fallen', (C_HIT[0] - 0.12, C_HIT[1] + 0.35), face(C_HIT, M2), settle=0.6),
    k(DUR, 'fallen', (C_HIT[0] - 0.12, C_HIT[1] + 0.35), face(C_HIT, M2)),
]

def unwrap(keys):
    """ry continuous from key to key (the shorter way round): the engine interpolates ry as a number, so a turn from
    +170 to -170 degrees would spin 340 degrees the long way."""
    for a, b in zip(keys, keys[1:]):
        while b['ry'] - a['ry'] > math.pi:
            b['ry'] = round(b['ry'] - 2 * math.pi, 3)
        while b['ry'] - a['ry'] < -math.pi:
            b['ry'] = round(b['ry'] + 2 * math.pi, 3)
    return keys


for _keys in (mus, boy, ra, rc):
    unwrap(_keys)

GAIT = {'arms': [0.2, 0.9], 'note': 'walking with the drawn blade low in the right hand: the right arm barely swings'}
film = {
    'title': 'Ichijo-ji: the boy first (Episode 2)',
    'page': 'engine/motion.html', 'fps': 30, 'width': 1080, 'height': 1920, 'format': 'vertical', 'duration': DUR,
    'mode': 'studio',
    'motion': {'overlap': True, 'lockFeet': True},
    'stage': {'mark': 'MARK_center', 'origin': True, 'turn': 0},
    'set': 'ichijoji-crossroads',
    'cast': {
        'hero': {'character': 'musashi', 'face': 'eyes', 'recipe': 'musashi-ai'},
        'target': {'character': 'ronin', 'face': 'eyes', 'recipe': 'samurai-ai'},
        'retainerA': {'character': 'ronin', 'face': 'eyes', 'recipe': 'ronin-ai-kabuto'},
        'retainerC': {'character': 'ronin', 'face': 'eyes', 'recipe': 'assassin-ai'},
    },
    'performances': {
        'hero': {'keys': mus, 'life': [[0, 1.0]], 'track': [[0, 0.0]], 'gait': dict(GAIT)},
        'target': {'keys': boy, 'life': [[0, 1.0], [19.6, 1.0], [20.6, 0.0]], 'track': [[0, 0.0], [16.2, 0.0], [16.7, 1.0], [18.0, 0.0]],
                   'gait': dict(GAIT)},
        'retainerA': {'keys': ra, 'life': [[0, 1.0], [25.0, 1.0], [26.2, 0.0]], 'track': [[0, 0.0], [18.6, 0.0], [19.2, 1.0], [23.3, 0.0]],
                      'gait': dict(GAIT)},
        'retainerC': {'keys': rc, 'life': [[0, 1.0], [29.8, 1.0], [30.8, 0.0]], 'track': [[0, 0.0], [18.7, 0.0], [19.3, 1.0], [27.9, 0.0]],
                      'gait': dict(GAIT)},
    },
    'fade': {'in': 0, 'out': 0.0},
    'paperSurface': {'angle': 36.0, 'ink': 0.85, 'width': 0.003, 'light': 0.55, 'mottle': 0.12, 'mottle_scale': 7.0, 'ao': 0.35},
    'wind': {'to': [1.0, 0.2], 'strength': 1.6, 'gust': 0.4, 'seed': 4, 'note': 'a light night wind down the Kyoto road'},
}

film['cameraOpts'] = {'solver': 2, 'aperture': 4.0}
film['camera'] = [
    # S1 HOOK (0-2.6 s): his eyes in the dark, then the pine over the crossing
    {'t': 0.0, 'rig': 'compose', 'subjects': ['hero'], 'basis': 'facing', 'aim': 'head', 'span': 0.5, 'az0': 18, 'az1': 8,
     'elev': 2, 'size0': 0.9, 'size1': 1.2, 'ease': 'out', 'screen': [0.5, 0.42], 'fov': 30, 'feel': 'dolly',
     'note': 'S1 HOOK: Musashi\'s eyes under the pine, waiting in the dark; a fast push'},
    {'t': 1.4, 'cut': True, 'rig': 'compose', 'subjects': ['hero'], 'basis': 'facing', 'az0': -20, 'az1': -10, 'elev0': -16,
     'elev1': -8, 'size': 0.5, 'screen': [0.5, 0.6], 'fov': 32, 'feel': 'crane', 'note': 'S1: low, his shape against the moonlit mist, the pine over him'},
    # S2 (2.6-11 s): they come up the Kyoto road
    {'t': 2.6, 'cut': True, 'rig': 'compose', 'subjects': ['target', 'retainerA', 'retainerC'], 'az0': -112, 'az1': -104, 'elev': 8,
     'size': 0.3, 'screen': [0.5, 0.62], 'fov': 34, 'feel': 'dolly', 'note': 'S2 WIDE: from ahead of them on the road, the three walk toward the crossing in the mist'},
    {'t': 6.8, 'cut': True, 'rig': 'compose', 'subjects': ['target'], 'basis': 'facing', 'az0': 28, 'az1': 20, 'elev': 2, 'size': 0.62,
     'aim': 'chest', 'screen': [0.48, 0.58], 'fov': 34, 'feel': 'dolly', 'note': 'S2 MEDIUM: the boy walking at the head of his men'},
    # S3 (11-17 s): the wait; Musashi comes out
    {'t': 10.6, 'cut': True, 'rig': 'compose', 'subjects': ['target', 'retainerA', 'retainerC'], 'az0': -60, 'az1': -66, 'elev': 6, 'size': 0.36,
     'screen': [0.5, 0.6], 'fov': 34, 'feel': 'crane', 'note': 'S3: the three at the foot of the pine, watching the road'},
    {'t': 13.2, 'cut': True, 'rig': 'compose', 'subjects': ['hero'], 'basis': 'facing', 'az0': 40, 'az1': 30, 'elev': -4, 'size': 0.6,
     'screen': [0.5, 0.56], 'fov': 32, 'feel': 'handheld', 'note': 'S3: Musashi steps out from behind the trunk'},
    # S4 (16-21 s): the boy first
    {'t': 15.9, 'cut': True, 'rig': 'compose', 'subjects': ['target'], 'basis': 'facing', 'az': 12, 'elev': 2, 'aim': 'head',
     'span': 0.6, 'size': 1.0, 'screen': [0.5, 0.45], 'fov': 30, 'feel': 'locked', 'note': 'S4: the boy hears him and turns'},
    {'t': 17.3, 'cut': True, 'rig': 'compose', 'subjects': ['hero', 'target'], 'az': 40, 'elev': 0, 'size': 0.5,
     'screen': [0.5, 0.52], 'fov': 34, 'feel': 'locked', 'note': 'S4 THE CUT: profile, slow motion'},
    {'t': 18.9, 'cut': True, 'rig': 'compose', 'subjects': ['target'], 'az': 140, 'elev': 14, 'size': 0.5,
     'screen': [0.5, 0.6], 'fov': 34, 'feel': 'crane', 'note': 'S4: the boy falls under the pine'},
    # S5 (21-31 s): his men
    {'t': 20.9, 'cut': True, 'rig': 'compose', 'subjects': ['retainerA', 'hero'], 'az0': 0, 'az1': -8, 'elev': 2, 'size': 0.42,
     'screen': [0.5, 0.56], 'fov': 34, 'feel': 'torpedo', 'note': 'S5: the first retainer charges'},
    {'t': 22.7, 'cut': True, 'rig': 'compose', 'subjects': ['hero', 'retainerA'], 'az': 180, 'elev': 2, 'size': 0.55,
     'screen': [0.5, 0.52], 'fov': 34, 'feel': 'locked', 'note': 'S5: the slip and the side cut'},
    {'t': 24.4, 'cut': True, 'rig': 'compose', 'subjects': ['retainerA'], 'basis': 'facing', 'az': 30, 'elev': -6, 'size': 0.55,
     'screen': [0.5, 0.58], 'fov': 34, 'feel': 'crane', 'note': 'S5: he goes down'},
    {'t': 25.8, 'cut': True, 'rig': 'compose', 'subjects': ['retainerC', 'hero'], 'az0': 120, 'az1': 128, 'elev': 4, 'size': 0.45,
     'screen': [0.5, 0.56], 'fov': 34, 'feel': 'dolly', 'note': 'S5: the last man gathers and thrusts'},
    {'t': 27.4, 'cut': True, 'rig': 'compose', 'subjects': ['hero', 'retainerC'], 'az': -70, 'elev': -4, 'size': 0.55,
     'screen': [0.5, 0.52], 'fov': 34, 'feel': 'locked', 'note': 'S5 the rising cut'},
    # S6 (29-45 s): after
    {'t': 29.2, 'cut': True, 'rig': 'compose', 'subjects': ['hero', 'target', 'retainerA', 'retainerC'], 'az': 200, 'elev0': 12, 'elev1': 28, 'size': 0.3,
     'screen': [0.5, 0.58], 'fov': 34, 'feel': 'crane', 'note': 'S6 ABOVE: Musashi alone among the fallen, the crane rises'},
    {'t': 33.0, 'cut': True, 'rig': 'compose', 'subjects': ['hero'], 'basis': 'facing', 'az': 20, 'elev': 0, 'size': 0.7,
     'aim': 'chest', 'screen': [0.5, 0.54], 'fov': 32, 'feel': 'locked', 'note': 'S6: the flick of the blade'},
    {'t': 36.0, 'cut': True, 'rig': 'compose', 'subjects': ['hero'], 'az0': 120, 'az1': 110, 'elev': 8, 'size': 0.34,
     'screen': [0.5, 0.6], 'fov': 34, 'feel': 'crane', 'note': 'S6 AWAY: he walks off east down the road, the pine and the fallen behind'},
    {'t': 41.8, 'cut': True, 'rig': 'compose', 'subjects': ['hero'], 'az0': 96, 'az1': 92, 'elev': 4, 'size0': 0.32, 'size1': 0.26,
     'screen': [0.5, 0.62], 'fov': 34, 'feel': 'crane', 'note': 'S7 THE LAST SHOT: into the mist; the end card'},
]
film['cameraMoves'] = [
    {'move': 'crash', 'zoom': 1.3, 'in': 0.05, 'hold': 0.2, 'out': 0.35, 't': 17.85, 'note': 'on the cut'},
    {'move': 'dutch', 'deg': 6, 'in': 0.08, 'hold': 0.4, 'out': 0.3, 't': 17.87},
    {'move': 'shake', 't': 23.15, 'amp': 0.9, 'dur': 0.3},
    {'move': 'shake', 't': 27.8, 'amp': 0.9, 'dur': 0.3},
    {'move': 'breath', 't': 29.2, 'until': DUR, 'amp': 0.3},
]
film['ramps'] = [{'t': 17.6, 'rate': 0.25, 'in': 0.05, 'hold': 0.6, 'out': 0.25}]
film['effects'] = {'dof': 4.0, 'motionBlur': 0.5, 'vignette': 0.3, 'postFx': True, 'hitStop': {'min': 3, 'max': 4}}
film['impacts'] = [
    {'t': 17.85, 'at': 'target.chest', 'intensity': 1.0, 'ink': True, 'shards': 14, 'colors': ['#b8322a', '#f3ead8'], 'note': 'the boy: paper shards and red'},
    {'t': 23.15, 'at': 'retainerA.chest', 'intensity': 0.8, 'shards': 10, 'colors': ['#b8322a', '#f3ead8']},
    {'t': 27.8, 'at': 'retainerC.chest', 'intensity': 0.8, 'shards': 10, 'colors': ['#b8322a', '#f3ead8']},
]
film['sounds'] = [
    {'id': 'night-bed', 't': 0, 'sfx': 'amb-night-village', 'len': DUR, 'gain': 0.35, 'note': 'crickets and the night'},
    {'id': 'cut-boy', 't': 17.85, 'body': True, 'sfx': 'swing', 'len': 0.6, 'gain': 1.0},
    {'id': 'cut-boy-thud', 't': 17.85, 'body': True, 'sfx': 'impact-drum', 'len': 1.2, 'gain': 0.8, 'layer': 'cut-boy'},
    {'id': 'fall-boy', 't': 20.8, 'body': True, 'sfx': 'fall', 'len': 1.0, 'gain': 0.6},
    {'id': 'cut-a', 't': 23.15, 'body': True, 'sfx': 'swing-2', 'len': 0.6, 'gain': 0.9},
    {'id': 'cut-a-hit', 't': 23.15, 'body': True, 'sfx': 'impact', 'len': 0.8, 'gain': 0.7, 'layer': 'cut-a'},
    {'id': 'fall-a', 't': 26.4, 'body': True, 'sfx': 'fall', 'len': 1.0, 'gain': 0.6},
    {'id': 'cut-c', 't': 27.8, 'body': True, 'sfx': 'swing-3', 'len': 0.6, 'gain': 0.9},
    {'id': 'cut-c-hit', 't': 27.8, 'body': True, 'sfx': 'impact', 'len': 0.8, 'gain': 0.7, 'layer': 'cut-c'},
    {'id': 'fall-c', 't': 31.0, 'body': True, 'sfx': 'fall', 'len': 1.0, 'gain': 0.6},
    {'id': 'score', 't': 0, 'file': 'output/ichijoji-ep2-score.wav', 'len': DUR, 'gain': 0.62, 'music': True,
     'note': 'tools/score_synth.py from film.score (film.sh renders it before the mix)'},
    {'id': 'end-bell', 't': 45.4, 'sfx': 'temple-bell', 'len': 4.6, 'gain': 0.5},
]
film['score'] = {'seed': 7, 'key': 'E', 'scale': 'in', 'reverb': 0.35, 'rt60': 2.8, 'gain': 0.9, 'cues': [
    {'t': 0.12, 'kind': 'odaiko', 'gain': 1.0},
    {'t': 0.5, 'kind': 'shaku', 'notes': [[0, 'B4', 2.4]], 'gain': 0.5},
    {'t': 1.4, 'kind': 'taiko', 'gain': 0.6},
    {'t': 2.6, 'until': 13.0, 'kind': 'drone', 'note': 'E2', 'gain': 0.5},
    {'t': 2.6, 'until': 11.0, 'kind': 'pulse', 'bpm0': 56, 'bpm1': 62, 'note': 'E2', 'gain': 0.35},
    {'t': 4.0, 'kind': 'koto', 'notes': [[0, 'E4'], [0.8, 'B3'], [1.6, 'E4'], [2.4, 'F4'], [3.6, 'E4'], [4.4, 'B3']], 'gain': 0.45},
    {'t': 11.0, 'kind': 'shaku', 'notes': [[0, 'E5', 2.2], [2.1, 'F5', 1.4]], 'gain': 0.4, 'vib': 0.4},
    {'t': 13.0, 'until': 17.6, 'kind': 'pulse', 'bpm0': 70, 'bpm1': 110, 'note': 'E2', 'gain': 0.55},
    {'t': 13.0, 'until': 17.7, 'kind': 'drone', 'note': 'F2', 'gain': 0.5},
    {'t': 16.4, 'until': 17.7, 'kind': 'roll', 'gain': 0.9},
    {'at': 'contact', 'dt': -0.06, 'until_dt': 0.86, 'kind': 'silence', 'fade': 0.03},
    {'at': 'contact', 'dt': 0.9, 'kind': 'odaiko', 'gain': 1.0},
    {'t': 20.8, 'until': 29.0, 'kind': 'pulse', 'bpm0': 120, 'bpm1': 132, 'note': 'E2', 'gain': 0.6},
    {'t': 23.15, 'kind': 'taiko', 'gain': 0.8},
    {'t': 27.8, 'kind': 'odaiko', 'gain': 0.9},
    {'t': 29.2, 'until': 45.0, 'kind': 'drone', 'note': 'E2', 'gain': 0.5},
    {'t': 30.0, 'kind': 'shaku', 'notes': [[0, 'B5', 3.6]], 'gain': 0.35, 'vib': 0.25},
    {'t': 36.2, 'kind': 'koto', 'notes': [[0, 'B4'], [1.2, 'A4'], [2.4, 'F4'], [3.6, 'E4'], [6.0, 'B3'], [7.2, 'E4']], 'gain': 0.5},
    {'t': 39.0, 'kind': 'shaku', 'notes': [[0, 'E5', 2.6], [2.5, 'B4', 2.0], [4.3, 'C5', 1.2]], 'gain': 0.42},
    {'t': 45.4, 'kind': 'rin', 'note': 'B5', 'gain': 0.5, 'len': 5.0},
    {'t': 45.4, 'kind': 'koto', 'notes': [[0, 'E4'], [0.3, 'B4'], [0.6, 'E5']], 'gain': 0.45},
]}
film['titles'] = [
    {'start': 0.15, 'end': 2.5, 'style': 'hero', 'jp': '一乗寺', 'en': '1604. One man. A whole school.'},
    {'start': 3.0, 'end': 6.4, 'style': 'left', 'en': 'Ichijō-ji, outside Kyoto', 'sub': '1604 (traditional date)'},
    {'start': 6.8, 'end': 10.4, 'style': 'bottom', 'en': 'Twice the Yoshioka school\nhad lost to Musashi.', 'sub': 'as tradition tells it'},
    {'start': 10.8, 'end': 13.6, 'style': 'bottom', 'en': 'Their new head was a boy.\nHis men came with him.', 'sub': 'as tradition tells it'},
    {'start': 13.9, 'end': 16.2, 'style': 'bottom', 'en': 'This time, Musashi came early.', 'sub': 'as tradition tells it'},
    {'start': 33.4, 'end': 37.4, 'style': 'bottom', 'en': 'He cut down the boy first,\nthen fought his way out.', 'sub': 'as tradition tells it'},
    {'start': 38.0, 'end': 44.6, 'style': 'quote', 'en': 'Respect the Buddhas and the gods,\nwithout counting on their help.', 'sub': 'Musashi, Dokkōdō (1645)'},
    {'start': 45.4, 'end': 50.35, 'style': 'endcard', 'jp': '紙の剣', 'en': 'PAPER CINEMA', 'sub': 'true duels, retold in paper'},
]

json.dump(film, open(OUT, 'w'), indent=1, ensure_ascii=False)
print('wrote', OUT, {i: len(v) for i, v in (('hero', mus), ('target', boy), ('retainerA', ra), ('retainerC', rc))})
