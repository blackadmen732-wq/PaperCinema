"""Sword-draw test: one swordsman draws from the scabbard, rendered as a short clip.

  blender -b -P blender/draw_test.py -- --recipe kojiro --out output/draw-test --res 360x640 [--blade 0.91]

The poses are the library's own nukitsuke keys (library/moves.json, library/poses.json) slowed so the
draw reads; the sword and scabbard come from blender/props/sword_draw.py. Prints the phase per frame.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
for p in ('character', 'world', 'props', ''):
    sys.path.insert(0, os.path.join(HERE, p))

import modular_builder as MB                         # noqa: E402
import swords as SW                                  # noqa: E402
import sword_draw as SD                              # noqa: E402
from render_engine import setup_render               # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(k, d=None):
    return argv[argv.index('--' + k) + 1] if '--' + k in argv else d


FPS = int(arg('fps', 30))                          # the delivery rate (1080x1920, 30 fps)
RECIPE = arg('recipe', 'kojiro')
BLADE = float(arg('blade', 0.91))
OUT = os.path.join(REPO, arg('out', 'output/draw-test'))

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = FPS

recipe = MB.load_recipe(os.path.join(REPO, 'library', 'character-recipes', RECIPE + '.json'))
ch = MB.build(recipe, name='PC_' + RECIPE)
rig = ch['rig']

SW.use(sc.collection)
import katana_real as KR                             # noqa: E402  the real sword + scabbard (one base)
K = KR.build('KATANA', sc.collection, blade_len=BLADE)
sword, saya = K['sword'], K['saya']
saya.name = 'SAYA'

# ---------------------------------------------------------------- the move, in seconds
POSES = json.load(open(os.path.join(REPO, 'library', 'poses.json')))
KEYS = [  # (time s, pose, overrides): the library's nukitsuke, slowed so the draw reads
    (0.00, 'standing', {}),
    (0.55, 'iai-ready', {}),                                   # right hand to the handle
    (0.95, 'iai-ready', {'crouch': 0.27, 'tx': 0.36, 'weight': 0.4}),   # the coil (koiguchi held)
    (1.30, 'nuki-draw-mid', {'fwd': 0.3}),                     # the tip leaves the mouth here
    (1.42, 'nukitsuke-contact', {'fwd': 0.5}),
    (1.54, 'nukitsuke-finish', {'fwd': 0.55}),
    (2.60, 'nukitsuke-finish', {'fwd': 0.55}),
]
GRAB, SLIDE, CLEAR = int(0.55 * FPS), int(0.95 * FPS), int(1.30 * FPS)


def full(name, over):
    p = dict(MB.BASE)
    p.update(POSES.get(name, {}))
    p.update({k: v for k, v in over.items() if k in MB.BASE})
    return p


def pose_at(t):
    for (t0, n0, o0), (t1, n1, o1) in zip(KEYS, KEYS[1:]):
        if t <= t1:
            u = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            u = u * u * (3 - 2 * u)
            a, b = full(n0, o0), full(n1, o1)
            return {k: a[k] + (b[k] - a[k]) * u for k in a}
    return full(KEYS[-1][1], KEYS[-1][2])


F = int(KEYS[-1][0] * FPS) + 1
draw = SD.Draw(rig, sword, saya, BLADE, grab=GRAB, slide=SLIDE, clear=CLEAR, R=K['R'])
_open = {s_: [o for o in ch['objects'] if o.get('pc_recipe') == 'hand_folded' and o.get('pc_socket') == 'hand.' + s_]
         for s_ in ('R', 'L')}
_skin = next((o.data.materials[0] for o in _open['R'] if o.data.materials), None)
if '--open-hands' not in argv:
    draw.add_hands(_open['R'], _open['L'], _skin, _skin)
print('[draw] open hand objects:', {k: [o.name for o in v] for k, v in _open.items()})
import body_capsules as BC                           # noqa: E402  the character's boundary
caps = BC.BodyCapsules(rig)
import cloth_springs as CS                           # noqa: E402  sleeves and hakama with weight
springs = None if '--stiff-cloth' in argv else CS.ClothSprings(rig, BC.BodyCapsules(rig), fps=FPS)
if '--no-keep-out' not in argv:
    draw.caps = BC.BodyCapsules(rig)
pen = []                                             # (frame, what, depth cm, capsule)
log = []
for f in range(1, F + 1):
    sc.frame_set(f)
    log.append(draw.step(f, pose_at((f - 1) / FPS)))
    if springs:
        springs.step()
    if '--debug' in argv and f % 2 == 0 and f >= 28:
        r = lambda v: [round(x, 2) for x in v]
        print('[dbg]', f, log[-1], 'guard', r(sword.matrix_world.translation), 'tip', r(sword.matrix_world @ Vector((BLADE, 0, 0))),
              'hand', r(rig.J['rH'].matrix_world.translation), 'saya', r(saya.matrix_world.translation))
    for e in rig.J.values():
        e.keyframe_insert('location', frame=f)
        e.keyframe_insert('rotation_euler', frame=f)
    if '--collide' in argv:
        bpy.context.view_layer.update()
        caps.update()
        # the drawn part of the blade (from the guard to the tip) and the scabbard, sampled every 5 cm
        worst = {}
        if log[-1] in ('drawing', 'drawn'):
            for i in range(1, 19):
                pt = sword.matrix_world @ Vector((BLADE * i / 18, 0, 0))
                d, who = caps.depth(pt, skip=('forearm.R', 'forearm.L'))
                if d > worst.get('blade', (-1, ''))[0]:
                    worst['blade'] = (d, who)
        for i in range(2, 18):
            pt = saya.matrix_world @ Vector(((BLADE + 0.035) * i / 18, 0, 0))
            d, who = caps.depth(pt, skip=('forearm.L', 'pelvis'))     # the scabbard is tied IN the obi
            if d > worst.get('saya', (-1, ''))[0]:
                worst['saya'] = (d, who)
        for what, (d, who) in worst.items():
            if d > 0:
                pen.append((f, what, round(d * 100, 1), who))
if '--collide' in argv:
    by = {}
    for f_, what, d, who in pen:
        by.setdefault(what, []).append((f_, d, who))
    for what in ('blade', 'saya'):
        rows = by.get(what, [])
        if rows:
            mx = max(rows, key=lambda r: r[1])
            print('[collide] %s inside the body on %d of %d frames, deepest %.1f cm (frame %d, %s)'
                  % (what, len(rows), F, mx[1], mx[0], mx[2]))
        else:
            print('[collide] %s never inside the body' % what)
    if draw.pushed:
        print('[collide] blade turned out of the body on frames', {k: v for k, v in sorted(draw.pushed.items())})
if springs:
    for j, rows in springs.depths.items():
        b = [r[0] for r in rows]
        a = [r[1] for r in rows]
        lag = [r[0] for r in springs.log[j]]
        print('[cloth] %-8s inside the body: before %d frames (deepest %.1f cm) -> after %d frames (deepest %.1f cm);'
              ' trails its old aim: median %.0f, max %.0f deg' % (j, sum(x > 0.005 for x in b), 100 * max(b), sum(x > 0.005 for x in a),
                                                         100 * max(a), sorted(lag)[len(lag) // 2], max(lag)))
print('[draw] phases:', ' '.join(f'{i+1}:{s[:2]}' for i, s in enumerate(log)), '| IK residual m:', draw.residual, '| left:', draw.residual_l)

for ob in [sword, saya] + list(rig.J.values()):
    ad = ob.animation_data
    if ad and ad.action:
        for fc in ad.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'

# armature follows the empties every frame (same as the films)
def _sync(scene, *_):
    rig.sync_bones()


bpy.app.handlers.frame_change_post.append(_sync)

# ---------------------------------------------------------------- camera, light, render
cd = bpy.data.cameras.new('cam')
cam = bpy.data.objects.new('cam', cd)
sc.collection.objects.link(cam)
sc.camera = cam
cd.lens = float(arg('lens', 38))
cam.location = Vector([float(v) for v in arg('cam', '1.9,-2.6,1.25').split(',')])
target = Vector([float(v) for v in arg('look', '-0.25,-0.4,1.0').split(',')])
cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
MB.studio(sc, 'cinematic')
# real metal needs something to reflect: the free Poly Haven dusk sky, low, under the studio lights
_hdr = os.path.join(REPO, 'assets', 'polyhaven', 'qwantani_dusk_2_puresky', 'qwantani_dusk_2_puresky_2k.hdr')
if os.path.exists(_hdr) and sc.world and sc.world.use_nodes:
    _nt = sc.world.node_tree
    _bg = next((n for n in _nt.nodes if n.type == 'BACKGROUND'), None)
    if _bg:
        _env = _nt.nodes.new('ShaderNodeTexEnvironment')
        _env.image = bpy.data.images.load(_hdr)
        _nt.links.new(_env.outputs['Color'], _bg.inputs['Color'])
        _bg.inputs['Strength'].default_value = 0.35
# a paper floor and a dim warm backdrop, so the blade and the scabbard read against something
bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 0, 0))
floor = bpy.context.active_object
floor.data.materials.append(SW._flat_mat('floor', (0.32, 0.27, 0.21, 1), 0.9))
bpy.ops.mesh.primitive_plane_add(size=12, location=(-1.5, 2.2, 3), rotation=(math.radians(90), 0, math.radians(-25)))
bpy.context.active_object.data.materials.append(SW._flat_mat('wall', (0.22, 0.2, 0.18, 1), 0.95))
setup_render(sc, arg('engine', 'eevee'), quality=arg('quality', 'draft'))
w, h = [int(v) for v in arg('res', '360x640').split('x')]
sc.render.resolution_x, sc.render.resolution_y = w, h
sc.frame_start, sc.frame_end = 1, F
os.makedirs(OUT, exist_ok=True)
sc.render.filepath = os.path.join(OUT, 'f')
sc.render.image_settings.file_format = 'PNG'
def saya_visible(f, n=24):
    """Share of points along the scabbard that the camera sees directly (first ray hit is the saya)."""
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    L = BLADE + 0.05
    seen = 0
    for i in range(n):
        p = saya.matrix_world @ Vector((L * (i + 0.5) / n, 0, 0.0))
        d = p - cam.matrix_world.translation
        hit, loc, nor, idx, ob, mat = sc.ray_cast(dg, cam.matrix_world.translation, d.normalized(), distance=d.length + 0.05)
        seen += bool(hit and ob and ob.parent is saya)
    return seen / n


if arg('measure'):
    for f in [int(v) for v in arg('measure').split(',')]:
        print('[measure] frame %d: scabbard visible %.0f%%' % (f, 100 * saya_visible(f)))
if arg('stills'):
    for f in [int(v) for v in arg('stills').split(',')]:
        sc.frame_set(f)
        sc.render.filepath = os.path.join(OUT, 'still_%03d.png' % f)
        bpy.ops.render.render(write_still=True)
elif '--no-render' not in argv:
    bpy.ops.render.render(animation=True)
print('[draw] done', F, 'frames ->', OUT)
