"""Generator for film/ganryujima-ep1.json (the authoring aid; the film JSON is the source of truth once written).
    python3 film/src/ganryujima-ep1.py [out.json]        (default: film/ganryujima-ep1.json)
then: node engine/validate.mjs film/ganryujima-ep1.json && node tools/timeline.mjs film/ganryujima-ep1.json &&
python3 tools/motion_check.py ganryujima-ep1
Coordinates: film three.js (x right, z toward the sea/sun, y up), origin = MARK_center (set (0, -3.2), sand 0.94 m),
staged with stage.origin so film (x, z) = set (x, -3.2 - z). Facing: ry 0 = +z (toward the sea)."""
import json
import math
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else 'film/ganryujima-ep1.json'


def face(a, b):
    """ry for a figure at a looking at b (ry 0 = +z)."""
    return round(math.atan2(b[0] - a[0], b[1] - a[1]), 3)


def lerp(a, b, u):
    return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)


def walk(keys, t0, t1, a, b, pose, step=0.5, ease_in=0.0, ease_out=0.0, **extra):
    """Root keys from a to b between t0 and t1 (the feet step by themselves: motion.lockFeet). ease_in / ease_out:
    seconds over which the pace builds from a stand / dies into a stop (a walker slows into a stop: with even keys the
    curve into the stop key SPED UP to 1.6 m/s before braking, 28 Nov, and the last step became a hop)."""
    ry = face(a, b)
    T, D = t1 - t0, 1.0
    A_, B_ = min(ease_in, T / 2), min(ease_out, T / 2)
    V = D / (T - (A_ + B_) / 2)

    def s(t):                                        # distance share covered after t seconds (trapezoid speed)
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


# ---- places (film coordinates) ----
K0 = (0.6, -0.3)                 # Kojiro's waiting spot on the duel ground
BOAT = (-8.0, 7.8)               # the boat (set (-8, -11)), bow toward MARK_hero
M_IN = (-7.75, 7.45)             # Musashi standing in the boat, a little fore of the middle
M_BOW = (-7.05, 6.55)            # at the bow
M_SAND = (-6.1, 5.3)             # over the bow into the surf (set (-6.1, -8.5), ankle-deep)
M_CUT = (-4.6, 4.0)              # after the cut (time compressed): walking up the beach
M_STOP = (-1.4, 1.5)             # stops, facing Kojiro
K_FACE = face(K0, M_STOP)
M_FACE = face(M_STOP, K0)

hero, target = [], []
# ---------------- Kojiro (hero) ----------------
hero += [
    {'t': 0.0, 'pose': 'rest-hand-on-hilt', 'x': K0[0], 'z': K0[1], 'ry': 0.0, 'note': 'S1 hook: the hand on the hilt, facing the sea'},
    {'t': 3.0, 'pose': 'rest-hand-on-hilt', 'x': K0[0], 'z': K0[1], 'ry': 0.0},
    {'t': 5.5, 'pose': 'neutral', 'x': K0[0], 'z': K0[1], 'ry': 0.05, 'hy': 0.15, 'note': 'S2 waiting: weight shifts, the wind'},
    {'t': 8.0, 'pose': 'rest-hand-on-hilt', 'x': K0[0], 'z': K0[1], 'ry': 0.0, 'hy': -0.1},
    {'t': 10.0, 'pose': 'rest-hand-on-hilt', 'x': K0[0], 'z': K0[1], 'ry': -0.35, 'hy': -0.35, 'note': 'he sees the boat'},
    {'t': 18.5, 'pose': 'rest-hand-on-hilt', 'x': K0[0], 'z': K0[1], 'ry': -0.45},
    {'t': 20.9, 'pose': 'rest-hand-on-hilt', 'x': K0[0], 'z': K0[1], 'ry': -0.5, 'hy': -0.35, 'note': 'his eyes find Musashi first (the head leads the turn)'},
    {'t': 21.6, 'pose': 'rest-hand-on-hilt', 'x': K0[0], 'z': K0[1], 'ry': K_FACE, 'settle': 0.6, 'note': 'S4 the body follows: turns to face Musashi'},
    {'t': 23.6, 'pose': 'iai-ready', 'x': K0[0], 'z': K0[1], 'ry': K_FACE, 'note': 'the draw (draw block)'},
    {'t': 24.6, 'pose': 'iai-ready', 'x': K0[0], 'z': K0[1], 'ry': K_FACE, 'crouch': 0.25},
    {'t': 25.1, 'pose': 'blade-out-recover', 'x': K0[0], 'z': K0[1], 'ry': K_FACE, 'settle': 0.8},
    {'t': 25.6, 'pose': 'blade-out-hand-on-saya', 'x': K0[0], 'z': K0[1], 'ry': K_FACE, 'note': 'the left hand takes the scabbard'},
    {'t': 26.0, 'pose': 'blade-out-hand-on-saya', 'x': K0[0], 'z': K0[1], 'ry': K_FACE - 0.5, 'lsz': -0.6, 'note': 'wind-up'},
    {'t': 26.25, 'pose': 'throw-scabbard', 'x': K0[0], 'z': K0[1], 'ry': K_FACE - 0.9, 'note': 'release toward the sea'},
    {'t': 26.9, 'pose': 'blade-out-recover', 'x': K0[0], 'z': K0[1], 'ry': K_FACE - 0.3, 'settle': 0.8},
    {'t': 27.6, 'pose': 'stand-blade-low', 'x': K0[0], 'z': K0[1], 'ry': K_FACE, 'note': 'hears the line'},
    {'t': 28.9, 'pose': 'stand-blade-low', 'x': K0[0], 'z': K0[1], 'ry': K_FACE, 'tx': -0.12, 'rsx': -0.55, 'hx': 0.12,
     'note': 'the words land: he draws back, the grip tightens, the blade lifts a little'},
    {'t': 30.1, 'pose': 'stand-blade-low', 'x': K0[0], 'z': K0[1], 'ry': K_FACE, 'tx': -0.06, 'rsx': -0.7, 'crouch': 0.05},
    {'t': 31.2, 'pose': 'hasso', 'x': K0[0], 'z': K0[1], 'ry': K_FACE, 'settle': 0.7, 'note': 'anger: hasso'},
    {'t': 32.4, 'pose': 'hasso', 'x': K0[0], 'z': K0[1], 'ry': K_FACE},
]
k_in = lerp(K0, M_STOP, 0.34)
hero += [
    {'t': 32.95, 'pose': 'kesa-windup', 'x': round(k_in[0], 3), 'z': round(k_in[1], 3), 'ry': K_FACE, 'note': 'S5 the charge'},
    {'t': 33.3, 'pose': 'kesa-contact', 'x': round(k_in[0], 3), 'z': round(k_in[1], 3), 'ry': K_FACE, 'note': 'the cut passes the headband'},
    {'t': 33.45, 'pose': 'struck-reel', 'x': round(k_in[0], 3), 'z': round(k_in[1], 3), 'ry': K_FACE, 'note': 'the bokken lands (impact)'},
    {'t': 34.4, 'pose': 'stagger', 'x': round(k_in[0] + 0.2, 3), 'z': round(k_in[1] - 0.15, 3), 'ry': K_FACE},
    {'t': 37.5, 'pose': 'stagger', 'x': round(k_in[0] + 0.22, 3), 'z': round(k_in[1] - 0.16, 3), 'ry': K_FACE},
    {'t': 38.6, 'pose': 'kneel-collapse', 'x': round(k_in[0] + 0.22, 3), 'z': round(k_in[1] - 0.16, 3), 'ry': K_FACE, 'settle': 0.5, 'note': 'falls to his knees'},
    {'t': 40.2, 'pose': 'kneel-collapse', 'x': round(k_in[0] + 0.22, 3), 'z': round(k_in[1] - 0.16, 3), 'ry': K_FACE, 'tx': 0.6, 'hx': 0.4, 'note': 'the last breath: his head sinks'},
    {'t': 60.0, 'pose': 'kneel-collapse', 'x': round(k_in[0] + 0.22, 3), 'z': round(k_in[1] - 0.16, 3), 'ry': K_FACE},
]
# ---------------- Musashi (target) ----------------
target += [
    {'t': 0.0, 'pose': 'stand-blade-low', 'x': M_IN[0], 'z': M_IN[1], 'ry': face(M_IN, K0), 'note': 'in the boat, far off'},
    {'t': 11.0, 'pose': 'stand-blade-low', 'x': M_IN[0], 'z': M_IN[1], 'ry': face(M_IN, K0)},
    {'t': 12.6, 'pose': 'chudan', 'x': M_IN[0], 'z': M_IN[1], 'ry': face(M_IN, K0), 'note': 'S3 looks along the oar sword'},
    {'t': 14.6, 'pose': 'chudan', 'x': M_IN[0], 'z': M_IN[1], 'ry': face(M_IN, K0)},
    {'t': 15.4, 'pose': 'stand-blade-low', 'x': M_IN[0], 'z': M_IN[1], 'ry': face(M_IN, K0), 'hx': -0.12,
     'note': 'lowers it, looks up at the island (the step out happens on the cut: inside the boat the path crosses a thwart)'},
    {'t': 18.49, 'pose': 'stand-blade-low', 'x': M_IN[0], 'z': M_IN[1], 'ry': face(M_IN, K0)},
    {'t': 18.5, 'pose': 'stand-blade-low', 'x': M_SAND[0], 'z': M_SAND[1], 'ry': face(M_SAND, M_STOP), 'cut': True,
     'note': 'the cut into S4: already wading out of the shallows'},
]
walk(target, 18.5, 23.4, M_SAND, M_STOP, 'stand-blade-low', ease_out=0.9)
target += [
    {'t': 24.0, 'pose': 'stand-blade-low', 'x': M_STOP[0], 'z': M_STOP[1], 'ry': M_FACE, 'settle': 0.5},
    {'t': 24.9, 'pose': 'stand-blade-low', 'x': M_STOP[0], 'z': M_STOP[1], 'ry': M_FACE, 'crouch': 0.05, 'rsx': -0.4,
     'note': 'the blade comes out: his weight sinks a little, the oar comes up an inch'},
    {'t': 26.4, 'pose': 'stand-blade-low', 'x': M_STOP[0], 'z': M_STOP[1], 'ry': M_FACE, 'hy': 0.45, 'crouch': 0.05,
     'note': 'his eyes follow the scabbard out over the sea'},
    {'t': 27.4, 'pose': 'stand-blade-low', 'x': M_STOP[0], 'z': M_STOP[1], 'ry': M_FACE, 'hy': 0.0, 'note': 'back to Kojiro'},
    {'t': 27.9, 'pose': 'stand-blade-low', 'x': M_STOP[0], 'z': M_STOP[1], 'ry': M_FACE, 'hx': -0.06, 'note': '"You have already lost."'},
    {'t': 30.2, 'pose': 'waki-right', 'x': M_STOP[0], 'z': M_STOP[1], 'ry': M_FACE, 'settle': 0.6,
     'note': 'hides the bokken behind him, starting before Kojiro has finished rising into hasso (overlap)'},
    {'t': 32.4, 'pose': 'waki-right', 'x': M_STOP[0], 'z': M_STOP[1], 'ry': M_FACE},
    {'t': 32.62, 'pose': 'waki-right', 'x': M_STOP[0], 'z': M_STOP[1], 'ry': M_FACE, 'crouch': 0.24, 'tx': 0.14,
     'note': 'anticipation: he gathers, sinking, before the big rise of the oar'},
]
m_in = lerp(M_STOP, K0, 0.3)
target += [
    {'t': 32.95, 'pose': 'jodan-high-wind-up', 'x': round(m_in[0], 3), 'z': round(m_in[1], 3), 'ry': M_FACE, 'crouch': 0.12, 'note': 'S5 steps in, raises the oar'},
    {'t': 33.32, 'pose': 'jodan-high-wind-up', 'x': round(m_in[0], 3), 'z': round(m_in[1], 3), 'ry': M_FACE, 'crouch': 0.2, 'note': 'ducks under the cut: the headband is cut'},
    {'t': 33.45, 'pose': 'shomen-strike', 'x': round(m_in[0] + 0.1, 3), 'z': round(m_in[1] - 0.1, 3), 'ry': M_FACE, 'note': 'one strike: the head'},
    {'t': 33.7, 'pose': 'kiri-oroshi-finish', 'x': round(m_in[0] + 0.12, 3), 'z': round(m_in[1] - 0.12, 3), 'ry': M_FACE, 'settle': 1.0},
    {'t': 36.0, 'pose': 'kiri-oroshi-finish', 'x': round(m_in[0] + 0.12, 3), 'z': round(m_in[1] - 0.12, 3), 'ry': M_FACE},
    {'t': 37.5, 'pose': 'zanshin', 'x': round(m_in[0] + 0.12, 3), 'z': round(m_in[1] - 0.12, 3), 'ry': M_FACE, 'note': 'zanshin'},
    {'t': 43.0, 'pose': 'zanshin', 'x': round(m_in[0] + 0.12, 3), 'z': round(m_in[1] - 0.12, 3), 'ry': M_FACE},
    {'t': 44.5, 'pose': 'stand-blade-low', 'x': round(m_in[0] + 0.12, 3), 'z': round(m_in[1] - 0.12, 3), 'ry': M_FACE, 'tx': 0.3, 'note': 'a small bow'},
    {'t': 46.0, 'pose': 'stand-blade-low', 'x': round(m_in[0] + 0.12, 3), 'z': round(m_in[1] - 0.12, 3), 'ry': M_FACE},
    {'t': 47.0, 'pose': 'stand-blade-low', 'x': round(m_in[0] + 0.12, 3), 'z': round(m_in[1] - 0.12, 3), 'ry': face((m_in[0] + 0.12, m_in[1] - 0.12), (-5.2, 4.9)),
     'tx': 0.08, 'note': 'turns to the sea over a second, a small lean before the first step (anticipation)'},
]
m_end = (round(m_in[0] + 0.12, 3), round(m_in[1] - 0.12, 3))
M_BACK = (-5.2, 4.9)
walk(target, 47.3, 55.6, m_end, M_BACK, 'stand-blade-low', step=0.6, ease_in=0.7, ease_out=0.9)
target += [
    {'t': 56.4, 'pose': 'stand-blade-low', 'x': M_BACK[0], 'z': M_BACK[1], 'ry': face(m_end, M_BACK), 'settle': 0.4},
    {'t': 57.6, 'pose': 'stand-blade-low', 'x': M_BACK[0], 'z': M_BACK[1], 'ry': face(m_end, M_BACK) + 0.35, 'hy': 0.55,
     'note': 'one last look back at the island and the man on it'},
    {'t': 60.0, 'pose': 'stand-blade-low', 'x': M_BACK[0], 'z': M_BACK[1], 'ry': face(m_end, M_BACK) + 0.3, 'hy': 0.5},
]

film = {
    'title': 'Ganryujima: one strike (Episode 1)',
    'page': 'engine/motion.html', 'fps': 30, 'width': 1080, 'height': 1920, 'format': 'vertical', 'duration': 60.0,
    'mode': 'dawn',
    'motion': {'overlap': True, 'lockFeet': True},
    'stage': {'mark': 'MARK_center', 'origin': True, 'turn': 0},
    'cast': {
        'hero': {'character': 'kojiro', 'face': 'eyes', 'recipe': 'kojiro-ai2'},
        'target': {'character': 'musashi', 'face': 'eyes', 'weapon': 'bokken', 'recipe': 'musashi-ai', 'weaponPart': 'bokken_oar_t1'},
    },
    'performances': {
        # track: his head follows Musashi only from the cut at 18.5 s (they face each other); before it the keys do the
        # looking (ahead at the sea, then "he sees the boat" at 10 s). Tracking from frame 1 held his head at its
        # 40-degree limit toward the far boat for 11 s, and in the hook close-up his side lock crossed his face.
        'hero': {'keys': hero, 'life': [[0, 1.0], [39.6, 1.0], [40.4, 0.0]], 'track': [[0, 0.0], [17.6, 0.0], [18.4, 1.0]], 'draw': {'grab': 23.9, 'slide': 24.45, 'clear': 24.85, 'blade': 0.91, 'sword': 'shiokaze'},
                 'throwSaya': {'grab': 25.55, 'release': 26.2, 'to': [-3.6, 9.5], 'apex': 2.2}},
        'target': {'keys': target, 'life': [[0, 1.0]],
                   'gait': {'arms': [0.25, 1.0], 'note': 'walking: the oar low in the right hand swings a little, the free left arm swings'},
                   'drop': [{'part': 'musashi_head_t1', 't': 33.3, 'slot': 'band', 'becomes': 'hair', 'v': [-0.4, 2.0, 0.9], 'spin': 5.0, 'drag': 4.5, 'note': 'the headband cut (tradition): the band slot of the generated head leaves it'}]},
    },
    'fade': {'in': 0, 'out': 0.0},
    'paperSurface': {'angle': 36.0, 'ink': 0.85, 'width': 0.003, 'light': 0.55, 'mottle': 0.12, 'mottle_scale': 7.0, 'ao': 0.35,
                     'note': 'Mark, 27 Nov: turn on the paper upgrade (tested on Kojiro\'s arm, docs/AUTOPILOT.md)'},
    'wind': {'to': [0.15, -1.0], 'strength': 3.2, 'gust': 0.6, 'seed': 2,
             'note': 'the sea wind blows inland (film -z): the cloth springs breathe in it (blender/character/cloth_springs.py)'},
}

film['cameraOpts'] = {'solver': 2, 'aperture': 4.0}
film['camera'] = [
    # S1 HOOK (0-3 s): two shots, a fast push then a rising silhouette
    {'t': 0.0, 'rig': 'compose', 'subjects': ['hero'], 'basis': 'facing', 'aim': 'head', 'span': 0.5, 'az0': 14, 'az1': 6,
     'elev': 2, 'size0': 0.85, 'size1': 1.15, 'ease': 'out', 'screen': [0.5, 0.42], 'fov': 30, 'feel': 'dolly',
     'note': 'S1 HOOK: Kojiro\'s face, the dawn glow and the pines behind him (the sun is over the island, north), a fast push'},
    {'t': 1.3, 'cut': True, 'rig': 'compose', 'subjects': ['hero'], 'basis': 'facing', 'az0': -12, 'az1': -4, 'elev0': -14,
     'elev1': -6, 'size': 0.6, 'screen': [0.5, 0.56], 'fov': 30, 'feel': 'crane', 'note': 'S1: low in front of him, dark against the glow, the camera rising'},
    # S2 (3-11 s): alone, waiting
    {'t': 3.0, 'cut': True, 'rig': 'compose', 'subjects': ['hero'], 'az0': 8, 'az1': 0, 'elev': 7, 'size': 0.24,
     'screen': [0.5, 0.64], 'fov': 34, 'feel': 'crane', 'note': 'S2 WIDE: from the beach below, Kojiro alone on the duel ground, the pines and the glow'},
    {'t': 6.8, 'cut': True, 'rig': 'compose', 'subjects': ['hero'], 'basis': 'facing', 'az0': 38, 'az1': 30, 'elev': 3, 'size': 0.66,
     'aim': 'chest', 'screen': [0.46, 0.6], 'fov': 34, 'feel': 'handheld', 'note': 'S2 MEDIUM: waiting, the wind; he turns to the boat'},
    # S3 (11-20 s): the boat
    {'t': 11.0, 'cut': True, 'rig': 'compose', 'subjects': ['target'], 'az0': 22, 'az1': 30, 'elev': -2, 'size0': 0.36, 'size1': 0.48,
     'screen': [0.5, 0.58], 'fov': 30, 'feel': 'dolly', 'guard': False, 'note': 'S3 LOW OVER THE WATER: the boat, Musashi, the island ahead'},
    {'t': 14.8, 'cut': True, 'rig': 'compose', 'subjects': ['target'], 'az0': 60, 'az1': 52, 'elev': -6, 'size': 0.75,
     'screen': [0.5, 0.55], 'fov': 32, 'feel': 'dolly', 'note': 'S3: Musashi in the boat from the south-east, looking up at the island, the glow beyond'},
    # S4 (20-32 s): the meeting. The line runs Kojiro -> Musashi at bearing -48 deg: every two-fighter camera stays on the
    # side az -48..132 (hero positive), so nobody swaps sides of the screen
    # (27 Nov: this shot framed Kojiro alone and started with the lens beside Musashi's shoulder: the camera report had
    # Musashi out of frame for 4.2 s of its 4.9 s. Now it FOLLOWS Musashi from behind, over his shoulder to Kojiro:
    # camera az 194-189 around Musashi from the Kojiro side = 14-9 deg off their line on the hero-positive side, so the
    # screen sides hold: Musashi left, Kojiro right, closing in as he wades up)
    {'t': 18.5, 'cut': True, 'rig': 'compose', 'subjects': ['target', 'hero'], 'basis': 'target', 'target': 'hero',
     'az0': 194, 'az1': 189, 'elev': 11, 'size': 0.39, 'screen': [0.37, 0.40], 'fov': 34, 'feel': 'dolly',
     'note': 'S4 WIDE: following behind Musashi as he wades up from the sea, over his shoulder Kojiro waits on the duel ground against the glow'},
    # (28 Nov, watched: aimed at the chest at size 1.3 it showed his face while his hands and the guard stayed below the
    # frame for the whole draw. Now the whole body, knees to above the head: the hands at the hip are in frame)
    {'t': 23.4, 'cut': True, 'rig': 'compose', 'subjects': ['hero'], 'basis': 'facing', 'az0': 32, 'az1': 26, 'elev': -4,
     'size0': 0.88, 'size1': 0.98, 'screen': [0.5, 0.5], 'fov': 32, 'feel': 'locked',
     'note': 'S4 THE DRAW: the long blade leaves the scabbard (his hands and the hilt at the hip in frame)'},
    {'t': 25.3, 'cut': True, 'rig': 'compose', 'subjects': ['hero'], 'az0': -26, 'az1': -32, 'elev': 6, 'size': 0.4,
     'screen': [0.55, 0.62], 'fov': 36, 'feel': 'dolly',
     'note': 'S4 THE THROW: from the sea side, the scabbard flies up over us against the glow (black lacquer vanished against the dark south)'},
    {'t': 27.95, 'cut': True, 'rig': 'compose', 'subjects': ['target'], 'basis': 'facing', 'az': -14, 'elev': 2, 'aim': 'head',
     'span': 0.55, 'size0': 0.9, 'size1': 1.1, 'screen': [0.5, 0.45], 'fov': 30, 'feel': 'locked',
     'note': 'S4 THE LINE: "Kojiro, you have already lost."'},
    # (28 Nov, watched: at az 10 his raised left forearm and sleeve hid his whole face for 1.2 s of this 1.7 s shot.
    # From his left (az 62-66, the hasso hands behind his head) the nearest forearm in front stays 0.177 frame-heights
    # from his face (half a face + half a sleeve: 0.175); measured on the exported bones every 6th frame. World bearing
    # about +18 deg: still on the hero side of the line)
    # (second pass, watched: at 62-66 his raised hand and its paper fingers still covered his face from 31.3 s: the
    # bones cleared, the hand mesh did not. At 96-100 both hands pass BEHIND his head: nothing stays in front of the
    # face closer than 0.33 frame-heights, the hand's 12 cm past its joint included)
    {'t': 30.5, 'cut': True, 'rig': 'compose', 'subjects': ['hero'], 'basis': 'facing', 'az0': 96, 'az1': 100, 'elev': -10, 'aim': 'chest',
     'size0': 0.5, 'size1': 0.58, 'screen': [0.5, 0.56], 'fov': 32, 'feel': 'handheld',
     'note': 'S4 ANGER: low medium from his left, he takes hasso against the glow, his face clear of his raised hands'},
    # S5 (32-42 s): one strike
    {'t': 32.2, 'cut': True, 'rig': 'compose', 'subjects': ['hero', 'target'], 'az0': 64, 'az1': 70, 'elev': -5, 'size': 0.34,
     'screen': [0.5, 0.58], 'fov': 36, 'feel': 'torpedo', 'note': 'S5 THE CHARGE: low, three-quarter from Kojiro\'s side'},
    {'t': 33.25, 'cut': True, 'rig': 'compose', 'subjects': ['hero', 'target'], 'az': 42, 'elev': 0, 'size': 0.5,
     'screen': [0.5, 0.5], 'fov': 34, 'feel': 'locked', 'note': 'S5 IMPACT: profile, the oar lands on the head (slow motion, hit-stop)'},
    {'t': 34.4, 'cut': True, 'rig': 'compose', 'subjects': ['target'], 'basis': 'facing', 'az': -158, 'elev': 2, 'size0': 0.74,
     'size1': 0.86, 'screen': [0.4, 0.55], 'fov': 34, 'feel': 'dolly', 'note': 'S5 AFTER: over Musashi in zanshin, the cut headband falling'},
    {'t': 37.2, 'cut': True, 'rig': 'compose', 'subjects': ['hero'], 'basis': 'facing', 'az': 50, 'elev': -8, 'size': 0.55,
     'screen': [0.5, 0.55], 'fov': 34, 'feel': 'crane', 'note': 'S5 THE FALL: Kojiro goes to his knees'},
    # S6 (42-55 s)
    {'t': 42.0, 'cut': True, 'rig': 'compose', 'subjects': ['target', 'hero'], 'az': 20, 'elev0': 10, 'elev1': 24, 'size': 0.44,
     'screen': [0.5, 0.56], 'fov': 34, 'feel': 'crane', 'note': 'S6 ABOVE: Musashi over the fallen Kojiro, the crane rises'},
    {'t': 46.4, 'cut': True, 'rig': 'compose', 'subjects': ['target'], 'az0': 44, 'az1': 52, 'elev': 9, 'size': 0.34,
     'screen': [0.5, 0.6], 'fov': 34, 'feel': 'crane', 'note': 'S6 AWAY: Musashi walks back toward the sea, the fallen Kojiro behind him, the glow'},
    {'t': 53.4, 'cut': True, 'rig': 'compose', 'subjects': ['target'], 'az0': 8, 'az1': 2, 'elev': 4, 'size0': 0.3, 'size1': 0.26,
     'screen': [0.5, 0.62], 'fov': 34, 'feel': 'crane', 'note': 'S7 THE LAST SHOT LIVES: from the water\'s edge, Musashi walks out of the dawn; the end card'},
]
film['cameraMoves'] = [
    {'move': 'rack', 't': 7.6, 'dur': 0.6, 'from': 'hero', 'to': 'hero', 'note': 'placeholder focus hold'},
    {'move': 'crash', 'zoom': 1.3, 'in': 0.05, 'hold': 0.2, 'out': 0.35, 't': 33.45, 'note': 'on the strike (re-timed to the bake contact)'},
    {'move': 'dutch', 'deg': 6, 'in': 0.08, 'hold': 0.4, 'out': 0.3, 't': 33.47},
    {'move': 'breath', 't': 42.0, 'until': 60.0, 'amp': 0.3},
]
film['ramps'] = [{'t': 33.2, 'rate': 0.25, 'in': 0.05, 'hold': 0.7, 'out': 0.25}]
film['effects'] = {'dof': 4.0, 'motionBlur': 0.5, 'vignette': 0.3, 'postFx': True, 'hitStop': {'min': 3, 'max': 4}}
film['impacts'] = [{'t': 33.45, 'at': 'hero.head', 'intensity': 1.0, 'ink': True, 'shards': 14,
                    'colors': ['#b8322a', '#f3ead8'], 'note': 'the oar on the head: paper shards and red'}]
film['sounds'] = [
    {'id': 'oar-on-head', 't': 33.45, 'body': True, 'sfx': 'wood-chop', 'len': 0.6, 'gain': 1.1,
     'note': 'the oar sword lands: a dry wooden crack (the score drops out under it)'},
    {'id': 'oar-on-head-thud', 't': 33.45, 'body': True, 'sfx': 'impact-drum', 'len': 1.2, 'gain': 0.8, 'layer': 'oar-on-head'},
    {'id': 'fall-knees', 't': 38.6, 'body': True, 'sfx': 'fall', 'len': 1.0, 'gain': 0.7},
    {'id': 'score', 't': 0, 'file': 'output/ganryujima-ep1-score.wav', 'len': 60, 'gain': 0.62, 'music': True,
     'note': 'tools/score_synth.py from film.score (film.sh renders it before the mix)'},
    {'id': 'end-bell', 't': 55.1, 'sfx': 'temple-bell', 'len': 4.6, 'gain': 0.5},
]
film['score'] = {'seed': 5, 'key': 'D', 'scale': 'in', 'reverb': 0.3, 'rt60': 2.6, 'gain': 0.9, 'cues': [
    {'t': 0.12, 'kind': 'odaiko', 'gain': 1.0},
    {'t': 0.5, 'kind': 'shaku', 'notes': [[0, 'A4', 2.6]], 'gain': 0.5},
    {'t': 1.3, 'kind': 'taiko', 'gain': 0.6},
    {'t': 3.0, 'until': 21.0, 'kind': 'drone', 'note': 'D2', 'gain': 0.55},
    {'t': 3.6, 'kind': 'shaku', 'notes': [[0, 'D5', 2.4], [2.3, 'Eb5', 1.2], [3.4, 'D5', 3.0], [7.0, 'A4', 3.2]], 'gain': 0.45},
    {'t': 11.0, 'kind': 'koto', 'notes': [[0, 'D4'], [0.8, 'A3'], [1.6, 'D4'], [2.4, 'Eb4'], [3.6, 'D4'], [4.4, 'A3'],
                                          [5.2, 'G3'], [6.4, 'A3']], 'gain': 0.5},
    {'t': 11.0, 'until': 20.0, 'kind': 'pulse', 'bpm0': 54, 'bpm1': 60, 'note': 'D2', 'gain': 0.35},
    {'t': 20.0, 'until': 27.0, 'kind': 'pulse', 'bpm0': 62, 'bpm1': 84, 'note': 'D2', 'gain': 0.5},
    {'t': 20.0, 'until': 33.0, 'kind': 'drone', 'note': 'Eb2', 'gain': 0.5},
    {'t': 24.4, 'kind': 'koto', 'notes': [[0, 'Bb4'], [0.12, 'A4']], 'gain': 0.5, 'bright': 0.8},
    {'t': 26.9, 'kind': 'odaiko', 'gain': 0.8},
    {'t': 27.4, 'kind': 'shaku', 'notes': [[0, 'Eb5', 3.4]], 'gain': 0.4, 'vib': 0.5},
    {'t': 30.6, 'until': 32.2, 'kind': 'pulse', 'bpm0': 96, 'bpm1': 120, 'note': 'D2', 'gain': 0.6},
    {'t': 32.2, 'until': 34.0, 'kind': 'roll', 'gain': 0.9},
    {'at': 'contact', 'dt': -0.06, 'until_dt': 0.86, 'kind': 'silence', 'fade': 0.03},
    {'at': 'contact', 'dt': 0.9, 'kind': 'odaiko', 'gain': 1.0},
    {'t': 37.0, 'kind': 'shaku', 'notes': [[0, 'A5', 4.0]], 'gain': 0.35, 'vib': 0.25},
    {'t': 42.0, 'until': 55.0, 'kind': 'drone', 'note': 'D2', 'gain': 0.5},
    {'t': 42.5, 'kind': 'koto', 'notes': [[0, 'A4'], [1.2, 'G4'], [2.4, 'Eb4'], [3.6, 'D4'], [6.0, 'A3'], [7.2, 'D4']], 'gain': 0.5},
    {'t': 47.0, 'kind': 'shaku', 'notes': [[0, 'D5', 2.8], [2.6, 'A4', 2.0], [4.4, 'Bb4', 1.4], [5.6, 'A4', 3.6]], 'gain': 0.45},
    {'t': 55.0, 'kind': 'rin', 'note': 'A5', 'gain': 0.5, 'len': 5.0},
    {'t': 55.0, 'kind': 'koto', 'notes': [[0, 'D4'], [0.3, 'A4'], [0.6, 'D5']], 'gain': 0.45},
]}
film['audit'] = {'waive': [
    {'check': 'foreground-blocker', 'from': 5.2, 'to': 6.6, 'why': 'the browser preview world has pines at (-4.6,-7.6)/(-2.1,-10) right behind the duel ground; the Blender beach set has none there (its nearest pine ~13 m back): measured on the set with film_modular --camera-report'},
    {'check': 'subject-occluded', 'from': 5.2, 'to': 6.6, 'why': 'same: the occluder is a browser-world pine that the Blender set does not have'},
    {'check': 'camera-in-geometry', 'from': 5.2, 'to': 6.6, 'why': 'same: a browser-world pine; the set clearance is checked by film_modular --camera-report'},
]}
film['titles'] = [
    {'start': 0.15, 'end': 2.9, 'style': 'hero', 'jp': '一撃', 'en': '1612. One strike.'},
    {'start': 3.4, 'end': 6.6, 'style': 'left', 'en': 'Funashima, the Kanmon Strait', 'sub': 'April 1612 (traditional date)'},
    {'start': 7.0, 'end': 10.8, 'style': 'bottom', 'en': 'Sasaki Kojirō waited.\nMusashi was late.', 'sub': 'as tradition tells it'},
    {'start': 11.6, 'end': 17.6, 'style': 'bottom', 'en': 'He came by boat,\nwith a sword cut from an oar.', 'sub': 'as tradition tells it'},
    {'start': 28.05, 'end': 30.45, 'style': 'quote', 'en': 'Kojirō, you have already lost.', 'sub': 'as tradition tells it'},
    {'start': 43.0, 'end': 47.6, 'style': 'bottom', 'en': 'Kojirō died.'},
    {'start': 48.2, 'end': 53.4, 'style': 'bottom', 'en': 'The island still bears\nthe name of his school.'},
    {'start': 55.0, 'end': 59.85, 'style': 'endcard', 'jp': '紙の剣', 'en': 'PAPER CINEMA', 'sub': 'true duels, retold in paper'},
]

json.dump(film, open(OUT, 'w'), indent=1, ensure_ascii=False)
print('wrote', OUT, len(hero), 'hero keys', len(target), 'target keys', 'K_FACE', K_FACE, 'M_FACE', M_FACE)
