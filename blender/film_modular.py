"""FILM_MODULAR: render a film in Blender using the MODULAR PAPER CHARACTER.

  B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
  node tools/timeline.mjs film/sword-mocap.json
  $B -b -t 4 -P blender/film_modular.py -- --film sword-mocap --frames 0-191 --res 540x960

Why this file exists. The project had three character systems and the films used the worst one:
  * engine/figure.js      boxes and flat cards  -> EVERY film rendered so far
  * rig_trellis.py        a TRELLIS glb, one fused mesh whose arms cannot bend -> blender/film_blender.py
  * modular_builder.py    the real paper character: kasa, angular mask, layered kimono, knife-pleated
                          hakama, two-tier sleeves -> stills only, never a film
Every improvement made to the third one (back pleats, blotting, fold darkening) was invisible,
because it never appeared in a render anyone watched. This connects it.

It is short because nothing had to be invented. `tools/timeline.mjs` already writes, per frame and
per actor, a `pose` dict of 46 channels, and `Rig.pose()` already takes exactly those channel names
-- both sides descend from engine/figure.js, so the names never diverged. The work was noticing.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, 'character'))
sys.path.insert(0, os.path.join(HERE, 'world'))
sys.path.insert(0, HERE)

ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(n, d=None):
    return ARGV[ARGV.index('--' + n) + 1] if '--' + n in ARGV else d

import modular_builder as MB                                    # noqa: E402
from render_engine import setup_render                          # noqa: E402

# three.js -> Blender, the same conversion rig_trellis.py uses (v3 / q3)
def v3(p):
    return Vector((p[0], -p[2], p[1]))


def q3(q):
    """three.js quaternion -> Blender, for a BONE: the local axes rotate with the basis too."""
    return Quaternion((q[3], q[0], -q[2], q[1]))


# three.js is y-up and Blender is z-up, which is a +90 degree turn about X: (x, y, z) -> (x, -z, y).
BASIS = Quaternion((0.7071067811865476, 0.7071067811865476, 0.0, 0.0))


def qcam(q):
    """three.js quaternion -> Blender, for a CAMERA.

    Not the same conversion as a bone, and that difference is why the first render came out empty.
    q3 conjugates (B q B-1), which is right for a bone because its local axes are arbitrary and must
    turn with the basis. A camera's local axes already mean the same thing in both programs - both
    look down local -Z with +Y up - so only the world orientation changes: B q, no inverse. Using the
    bone conversion aimed the camera off into empty space while the cast stood correctly behind it.
    """
    return BASIS @ Quaternion((q[3], q[0], q[1], q[2]))


FILM = arg('film', 'sword-mocap')
TL = json.load(open(os.path.join(REPO, 'output', f'{FILM}.timeline.json')))
FPS = TL['clock']['fps'] if isinstance(TL.get('clock'), dict) else 24
FRAMES = TL['frames']
f0, f1 = (int(x) for x in arg('frames', f'0-{len(FRAMES) - 1}').split('-'))
f1 = min(f1, len(FRAMES) - 1)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = FPS

# ---------------------------------------------------------------- characters
# One recipe per actor. A film names a character (kojiro, musashi); map it to a recipe, falling
# back to the reference ronin so a new name never stops a render.
RECIPES = {'kojiro': 'ronin-reference', 'musashi': 'armoured-warrior'}
rigs = {}
for a in TL['actors']:
    if a.get('hidden'):
        continue
    rid = RECIPES.get(a.get('character'), arg('recipe', 'ronin-reference'))
    path = os.path.join(REPO, 'library', 'character-recipes', rid + '.json')
    if not os.path.exists(path):
        path = os.path.join(REPO, 'library', 'character-recipes', 'ronin-reference.json')
    # load_recipe resolves `extends` / swap / add / drop; a bare json.load does not,
    # and the armoured warrior is defined as a diff against the ronin.
    recipe = MB.load_recipe(path)
    ch = MB.build(recipe, name='PC_' + a['id'])
    rigs[a['id']] = ch['rig']
    print(f"[film] {a['id']} -> {os.path.basename(path)}")

# ---------------------------------------------------------------- camera
cd = bpy.data.cameras.new('cam')
cam = bpy.data.objects.new('cam', cd)
sc.collection.objects.link(cam)
sc.camera = cam
cam.rotation_mode = 'QUATERNION'

# ---------------------------------------------------------------- bake the timeline
# Keyframe every joint empty and the camera on every frame. The rig is empties driving a deform
# armature (modular_builder.Rig), so keying the empties is what moves the mesh.
for i in range(f0, f1 + 1):
    fr = FRAMES[i]
    bpy.context.scene.frame_set(i - f0 + 1)
    for aid, rig in rigs.items():
        act = fr['actors'].get(aid)
        if not act:
            continue
        rig.pose(act['pose'])                                   # 46 channels, same names both sides
        for e in rig.J.values():
            e.keyframe_insert('location')
            e.keyframe_insert('rotation_euler')
    c = fr.get('camera')
    if c and not arg('lookat'):
        cam.location = v3(c['pos'])
        cam.rotation_quaternion = qcam(c['rot'])
        cd.lens = c.get('focal_mm', 40)
        cam.keyframe_insert('location')
        cam.keyframe_insert('rotation_quaternion')
        cd.keyframe_insert('lens')

# The engine's poses are already eased; Blender re-easing them would double the smoothing and the
# snap of a cut would soften into a drift. Hold every curve linear between the baked frames.
for ob in list(rigs.values()) + [cam, cd]:
    ad = getattr(ob, 'animation_data', None)
    act = getattr(ad, 'action', None) if ad else None
    if not act:
        continue
    for fc in getattr(act, 'fcurves', []):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'

# ---------------------------------------------------------------- light and render
# studio() takes 'neutral' or 'cinematic' only. 'dawn' fell through and rendered black.
MB.studio(sc, arg('light', 'neutral'))
setup_render(sc, engine=arg('engine'), quality=arg('quality', 'check'))
sc.render.resolution_x, sc.render.resolution_y = [int(v) for v in arg('res', '540x960').split('x')]
sc.frame_start, sc.frame_end = 1, f1 - f0 + 1
out = arg('out', os.path.join(REPO, 'output', 'modular', FILM))
os.makedirs(out, exist_ok=True)
sc.render.filepath = os.path.join(out, 'f')
sc.render.image_settings.file_format = 'JPEG'
if arg('lookat'):
    # Diagnostic: ignore the timeline's camera orientation and aim at the cast, to prove the
    # characters are in frame at all before trusting the quaternion conversion.
    look = bpy.data.objects.new('look', None); sc.collection.objects.link(look)
    look.location = (0, 0, 1.0)
    tr = cam.constraints.new('TRACK_TO'); tr.target = look
    tr.track_axis = 'TRACK_NEGATIVE_Z'; tr.up_axis = 'UP_Y'
    cam.animation_data_clear()
    cam.location = (3.5, -5.0, 2.0)
    cd.lens = 40

print(f'[film] {f1 - f0 + 1} frames -> {out}')
bpy.context.scene.frame_set(1)
print('[film] camera at', [round(v,2) for v in cam.location])
for aid, rig in rigs.items():
    print('[film]', aid, 'root at', [round(v,2) for v in rig.J['root'].location])
bpy.ops.render.render(animation=True)
