"""Film a TRELLIS character (made from the owner's reference image) in a dark cinematic shot.

  B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
  nice -n 5 $B -b -t 3 -P blender/character/trellis_shot.py -- --model ronin_base --still 40 --out output/character/ronin-still.png
  nice -n 5 $B -b -t 3 -P blender/character/trellis_shot.py -- --model ronin_base --frames 1-96 --out output/character/ronin-shot/

What it does:
  * imports assets/models/<model>.glb, stands it up at 1.75 m, feet on the floor, facing the camera
  * adds a simple skeleton (hips → spine → chest → neck → head) with automatic weights, so the body breathes,
    the head lifts and turns, and the robe sways (the TRELLIS mesh is one piece, so arms stay as sculpted for now)
  * light from the owner's references: 70% darkness, one warm key, a strong cool rim, the inner lantern glow,
    volumetric fog with a light shaft, a paper floor that catches the glow
  * camera: slow push-in from a low angle with a slight arc (the "low-hero-push" shot)
"""
import math
import os
import sys

import bpy
from mathutils import Euler, Vector

ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(n, d=None):
    return ARGV[ARGV.index('--' + n) + 1] if '--' + n in ARGV else d

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
MODEL = arg('model', 'ronin_base')
FPS = 24
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = FPS

# ---------------- character ----------------
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=os.path.join(REPO, 'assets', 'models', MODEL + '.glb'))
new = [o for o in bpy.data.objects if o not in before]
mesh = [o for o in new if o.type == 'MESH'][0]
for o in new:
    if o.type != 'MESH':
        o.select_set(False)
bpy.context.view_layer.objects.active = mesh
mesh.select_set(True)
bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bb = [mesh.matrix_world @ Vector(c) for c in mesh.bound_box]
mn = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
mx = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
H = 1.75
s = H / (mx.z - mn.z)
mesh.scale = (s, s, s)
mesh.location = (-(mn.x + mx.x) / 2 * s, -(mn.y + mx.y) / 2 * s, -mn.z * s)
mesh.rotation_euler.z = math.radians(float(arg('face', 0)))   # turn the model if it does not face -Y
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# skeleton: spine chain only (arms and legs are sculpted into the robe in this model)
arm = bpy.data.armatures.new('rig')
rig = bpy.data.objects.new('RIG', arm)
sc.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='EDIT')
chain = [('hips', 0.0, 0.50), ('spine', 0.50, 0.62), ('chest', 0.62, 0.80), ('neck', 0.80, 0.86), ('head', 0.86, 1.0)]
prev = None
for name, a, b in chain:
    bn = arm.edit_bones.new(name)
    bn.head = (0, 0, a * H)
    bn.tail = (0, 0, b * H)
    if prev:
        bn.parent = prev
        bn.use_connect = True
    prev = bn
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='DESELECT')
mesh.select_set(True)
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
try:
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
except Exception as e:
    print('auto weights failed, using envelopes:', e)
    bpy.ops.object.parent_set(type='ARMATURE_ENVELOPE')

# performance: breathe, lift the head, turn toward the lens, robe sway (keys at 24 fps)
pb = rig.pose.bones
for b in pb:
    b.rotation_mode = 'XYZ'
def key(bone, f, x=0, y=0, z=0):
    pb[bone].rotation_euler = Euler((math.radians(x), math.radians(y), math.radians(z)))
    pb[bone].keyframe_insert('rotation_euler', frame=f)
key('head', 1, x=14, z=-10); key('head', 30, x=14, z=-10); key('head', 54, x=-2, z=6); key('head', 96, x=-4, z=4)
key('neck', 1, x=6); key('neck', 54, x=-2); key('neck', 96, x=-2)
for f, k in ((1, 0), (24, 1), (48, 0), (72, 1), (96, 0)):
    key('chest', f, x=-1.5 * k)
key('hips', 1, z=0); key('hips', 54, z=-3); key('hips', 96, z=-2)
for fc in (rig.animation_data.action.fcurves if rig.animation_data and rig.animation_data.action else []):
    for kp in fc.keyframe_points:
        kp.interpolation = 'BEZIER'
        kp.easing = 'EASE_IN_OUT'

# inner lantern: a warm point light inside the chest and the head
for nm, z, e in (('lantern_chest', 0.68, 25), ('lantern_head', 0.92, 6)):
    L = bpy.data.lights.new(nm, 'POINT'); L.color = (1.0, 0.55, 0.2); L.energy = e; L.shadow_soft_size = 0.05
    lo = bpy.data.objects.new(nm, L); sc.collection.objects.link(lo); lo.location = (0, 0.02, z * H)

# ---------------- set: dark paper floor, back wall, fog, shaft ----------------
def mat(name, rgb, rough=0.85):
    m = bpy.data.materials.new(name); m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']; p.inputs['Base Color'].default_value = (*rgb, 1); p.inputs['Roughness'].default_value = rough
    return m
bpy.ops.mesh.primitive_plane_add(size=30); floor = bpy.context.object; floor.data.materials.append(mat('floor', (0.05, 0.045, 0.04), 0.6))
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 6, 8), rotation=(math.radians(90), 0, 0)); wall = bpy.context.object
wall.data.materials.append(mat('wall', (0.02, 0.02, 0.025)))
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.006, 0.007, 0.01, 1)
# volumetric fog in a big box so the light shaft shows
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 3)); fog = bpy.context.object; fog.scale = (12, 12, 6)
fm = bpy.data.materials.new('fog'); fm.use_nodes = True; nt = fm.node_tree
nt.nodes.remove(nt.nodes['Principled BSDF'])
vol = nt.nodes.new('ShaderNodeVolumePrincipled'); vol.inputs['Density'].default_value = float(arg('fog', 0.035))
nt.links.new(vol.outputs[0], nt.nodes['Material Output'].inputs['Volume']); fog.data.materials.append(fm)
def spot(name, loc, target, energy, color, size_deg=30, blend=0.4, radius=0.2):
    L = bpy.data.lights.new(name, 'SPOT'); L.energy = energy; L.color = color; L.spot_size = math.radians(size_deg); L.spot_blend = blend; L.shadow_soft_size = radius
    o = bpy.data.objects.new(name, L); sc.collection.objects.link(o); o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
spot('key', (-2.2, -2.6, 3.8), (0, 0, 1.2), 900, (1.0, 0.86, 0.68), 32)          # warm key, high left
spot('rim', (2.4, 2.8, 2.6), (0, 0, 1.3), 1400, (0.62, 0.75, 1.0), 26, 0.3)       # cool rim from behind right
spot('shaft', (0.6, 3.5, 7.5), (0, 0, 0.2), 2200, (1.0, 0.9, 0.75), 12, 0.15, 0.05)  # the god-ray shaft through the fog

# ---------------- camera: low-hero push-in with a slight arc ----------------
cd = bpy.data.cameras.new('cam'); cd.lens = 50; cd.dof.use_dof = True; cd.dof.aperture_fstop = 2.0
cam = bpy.data.objects.new('cam', cd); sc.collection.objects.link(cam); sc.camera = cam
look = bpy.data.objects.new('look', None); sc.collection.objects.link(look)
tr = cam.constraints.new('TRACK_TO'); tr.target = look; tr.track_axis = 'TRACK_NEGATIVE_Z'; tr.up_axis = 'UP_Y'
cd.dof.focus_object = look
for f, pos, lk in ((1, (1.3, -4.6, 0.55), (0, 0, 1.15)), (96, (0.45, -2.5, 0.85), (0, 0, 1.45))):
    sc.frame_set(f)
    cam.location = pos; cam.keyframe_insert('location', frame=f)
    look.location = lk; look.keyframe_insert('location', frame=f)
for ob in (cam, look):
    for fc in ob.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'BEZIER'; kp.easing = 'EASE_OUT'

# ---------------- render ----------------
sc.render.engine = 'CYCLES'
sys.path.insert(0, os.path.join(REPO, 'blender'))
from gpu_setup import use_gpu  # noqa: E402
use_gpu(sc)
sc.cycles.samples = int(arg('samples', 48))
sc.cycles.use_denoising = True
sc.cycles.volume_bounces = 1
sc.render.resolution_x, sc.render.resolution_y = [int(v) for v in arg('res', '540x960').split('x')]
sc.render.use_motion_blur = True
try:
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
except Exception:
    pass
out = arg('out', 'output/character/shot.png')
if arg('still'):
    sc.frame_set(int(arg('still')))
    sc.render.filepath = os.path.abspath(out)
    bpy.ops.render.render(write_still=True)
else:
    a, b = [int(v) for v in arg('frames', '1-96').split('-')]
    sc.frame_start, sc.frame_end = a, b
    os.makedirs(out, exist_ok=True)
    sc.render.filepath = os.path.join(os.path.abspath(out), 'f')
    sc.render.image_settings.file_format = 'JPEG'
    bpy.ops.render.render(animation=True)
if arg('save'):
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(arg('save')))
