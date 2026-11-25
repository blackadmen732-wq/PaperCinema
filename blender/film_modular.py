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

if arg('set'):
    # A built set (docs/SETS.md). The timeline's world coordinates are kept as they are; the set is
    # expected to be built around the same origin the films use.
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(arg('set')))
else:
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
    bpy.context.scene.frame_set(i + 1)      # ABSOLUTE timeline frame, 1-based
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
# CINEMATIC by default. `neutral` is the flat studio the character models are audited under - it
# hides nothing, which is what an audit wants and the opposite of what a film wants. A film lit that
# way comes out as two grey figures in a grey void, and that is what every modular render looked
# like until this line. `cinematic` is the Lantern Origami key: dark, the paper glowing from inside.
# Pass --light neutral when you are inspecting a model, not shooting it.
if arg('set'):
    # A set brings its own world, its own sun and its own fighter key/fill/rim (library/sets/*.json
    # "lighting"). studio() REPLACES scene.world and adds three area lamps, so calling it here threw
    # away the set's sky and mist and then put a lamp in shot - the blown white rectangle in the
    # middle of the bamboo-forest test. Inside a set, the set lights it.
    #
    # But the set's SUN alone leaves the cast reading as two dull shapes against a lit world: the
    # grove is lit for the grove. Every set file carries a `lighting.fighter` rig - key, fill and
    # rim, as offsets from whoever is standing there - written for exactly this. It was only ever
    # applied by the set builder's own --with-character preview, so a film never got it. Each actor
    # now carries that rig, parented to its root, so it travels with the performer through the shot.
    print('[film] set supplied the world and sun; adding its fighter key/fill/rim per actor')
    sj = os.path.join(REPO, 'library', 'sets', os.path.splitext(os.path.basename(arg('set')))[0] + '.json')
    fighter = {}
    if os.path.exists(sj):
        fighter = (json.load(open(sj)).get('lighting') or {}).get('fighter') or {}
    for aid, rig in rigs.items():
        for role, spec in fighter.items():
            L = bpy.data.lights.new(f'{role}_{aid}', 'AREA')
            L.energy = spec.get('energy', 20)
            L.size = spec.get('size', 1.5)
            L.color = tuple(spec.get('color', (1, 1, 1)))[:3]
            o = bpy.data.objects.new(f'L_{role}_{aid}', L)
            o.visible_camera = False                 # a lamp in shot is a white rectangle
            off = Vector(spec.get('offset', (0, 2, 2)))
            o.location = off
            # aim at the actor's chest, about 1.2 m up from the root the offset is measured from
            o.rotation_euler = (Vector((0, 0, 1.2)) - off).to_track_quat('-Z', 'Y').to_euler()
            sc.collection.objects.link(o)
            o.parent = rig.J['root']                 # travels with the performer
            o.matrix_parent_inverse = rig.J['root'].matrix_world.inverted()
else:
    MB.studio(sc, arg('light', 'cinematic'))
setup_render(sc, engine=arg('engine'), quality=arg('quality', 'check'),
             samples=int(arg('samples')) if arg('samples') else None)
sc.render.resolution_x, sc.render.resolution_y = [int(v) for v in arg('res', '540x960').split('x')]
# Absolute frame numbers. tools/film.sh renders ranges in parallel into ONE folder, so f0001 must
# mean timeline frame 0 in every worker; numbering each range from 1 would have every worker
# overwrite the first frames of every other one and the film would come out as the last range only.
sc.frame_start, sc.frame_end = f0 + 1, f1 + 1
out = arg('out', os.path.join(REPO, 'output', 'modular', FILM))
os.makedirs(out, exist_ok=True)
sc.render.filepath = os.path.join(out, 'f')
sc.render.image_settings.file_format = arg('format', 'PNG').upper()
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
bpy.context.scene.frame_set(f0 + 1)
print('[film] camera at', [round(v,2) for v in cam.location])
for aid, rig in rigs.items():
    print('[film]', aid, 'root at', [round(v,2) for v in rig.J['root'].location])
bpy.ops.render.render(animation=True)
