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


FPS = 24
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
sword = SW.build_katana('KATANA', blade_len=BLADE, handle=0.33)
paper = SW._flat_mat('saya_paper', (0.035, 0.05, 0.11, 1), 0.7)       # lacquered indigo card
horn = SW._flat_mat('saya_horn', (0.02, 0.02, 0.025, 1), 0.5)
saya = SD.build_saya('SAYA', sc.collection, length=BLADE + 0.05, mat_body=paper, mat_mouth=horn)

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
draw = SD.Draw(rig, sword, saya, BLADE, grab=GRAB, slide=SLIDE, clear=CLEAR)
log = []
for f in range(1, F + 1):
    sc.frame_set(f)
    log.append(draw.step(f, pose_at((f - 1) / FPS)))
    if '--debug' in argv and f % 2 == 0 and f >= 28:
        r = lambda v: [round(x, 2) for x in v]
        print('[dbg]', f, log[-1], 'guard', r(sword.matrix_world.translation), 'tip', r(sword.matrix_world @ Vector((BLADE, 0, 0))),
              'hand', r(rig.J['rH'].matrix_world.translation), 'saya', r(saya.matrix_world.translation))
    for e in rig.J.values():
        e.keyframe_insert('location', frame=f)
        e.keyframe_insert('rotation_euler', frame=f)
print('[draw] phases:', ' '.join(f'{i+1}:{s[:2]}' for i, s in enumerate(log)), '| IK residual m:', draw.residual)

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
if arg('stills'):
    for f in [int(v) for v in arg('stills').split(',')]:
        sc.frame_set(f)
        sc.render.filepath = os.path.join(OUT, 'still_%03d.png' % f)
        bpy.ops.render.render(write_still=True)
elif '--no-render' not in argv:
    bpy.ops.render.render(animation=True)
print('[draw] done', F, 'frames ->', OUT)
