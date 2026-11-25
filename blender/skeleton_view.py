# SKELETON VIEW: the rig alone - bars and joints, no paper, no costume, no set.
#
#   B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
#   $B -b -P blender/skeleton_view.py -- --film sword-mocap --out output/skeleton/sword-mocap
#   ... -- --film mocap-test --actor hero --res 720x720
#
# Why this exists: the paper is something laid ON TOP of the skeleton, so a skeleton that trembles
# makes a character that trembles and no amount of material work will hide it. This renders the rig
# by itself, from the canonical timeline, so the motion can be judged with nothing in front of it.
#
# Workbench, flat colour, no lights: it draws in milliseconds a frame, because a technical view that
# costs an hour is a technical view nobody looks at. Measure the same motion with
# `node tools/jitter.mjs <film>`; this is the picture of that number.
import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(n, d=None):
    return ARGV[ARGV.index('--' + n) + 1] if '--' + n in ARGV else d


def flag(n):
    return '--' + n in ARGV


# Who joins to whom. The hakama bone is cloth, not bone, so it is left out of the stick figure.
PARENT = {
    'hips': 'root', 'waist': 'hips', 'chest': 'waist', 'neck': 'chest', 'head': 'neck',
    'clavicle.R': 'chest', 'shoulder.R': 'clavicle.R', 'elbow.R': 'shoulder.R',
    'twist.R': 'elbow.R', 'hand.R': 'twist.R',
    'clavicle.L': 'chest', 'shoulder.L': 'clavicle.L', 'elbow.L': 'shoulder.L',
    'twist.L': 'elbow.L', 'hand.L': 'twist.L',
    'thigh.R': 'root', 'shin.R': 'thigh.R', 'foot.R': 'shin.R',
    'thigh.L': 'root', 'shin.L': 'thigh.L', 'foot.L': 'shin.L',
}
LEFT = {k for k in PARENT if k.endswith('.L')}
RIGHT = {k for k in PARENT if k.endswith('.R')}


def v3(p):
    """three.js (+Y up) -> Blender (+Z up), the same conversion every other tool here uses."""
    return Vector((p[0], -p[2], p[1]))


FILM = arg('film', 'sword-mocap')
TL = json.load(open(os.path.join(REPO, 'output', f'{FILM}.timeline.json')))
ORDER = TL['bones']['order']
IDX = {n: i for i, n in enumerate(ORDER)}
FRAMES = TL['frames']
FPS = TL['clock']['fps'] if isinstance(TL.get('clock'), dict) else 24
ONLY = arg('actor')
ACTORS = [a['id'] for a in TL['actors'] if not a.get('hidden') and (not ONLY or a['id'] == ONLY)]
f0, f1 = (int(x) for x in arg('frames', f'0-{len(FRAMES) - 1}').split('-'))
f1 = min(f1, len(FRAMES) - 1)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = FPS


def mat(name, rgba):
    m = bpy.data.materials.new(name)
    m.use_nodes = False
    m.diffuse_color = rgba
    return m


M = {'L': mat('L', (0.25, 0.70, 1.0, 1)),       # left side cool, right side warm: the standard
     'R': mat('R', (1.0, 0.48, 0.20, 1)),       # read for a rig, so a flipped limb is obvious
     'C': mat('C', (0.90, 0.90, 0.90, 1)),      # spine and head
     'J': mat('J', (1.0, 1.0, 1.0, 1))}


def side_of(name):
    return 'L' if name in LEFT else 'R' if name in RIGHT else 'C'


# One sphere per joint and one bar per bone, per actor. Built once, moved every frame: a new mesh
# per frame would be correct and unwatchably slow.
rig = {}
for aid in ACTORS:
    joints, bars = {}, {}
    for name in ORDER:
        if name not in PARENT and name != 'root':
            continue
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.035, segments=12, ring_count=8)
        s = bpy.context.object
        s.name = f'J_{aid}_{name}'
        s.data.materials.append(M['J'] if name == 'root' else M[side_of(name)])
        joints[name] = s
    for name, par in PARENT.items():
        bpy.ops.mesh.primitive_cylinder_add(radius=0.018, depth=1.0, vertices=10)
        c = bpy.context.object
        c.name = f'B_{aid}_{name}'
        c.data.materials.append(M[side_of(name)])
        bars[name] = c
    rig[aid] = (joints, bars)

# A ground grid, so a foot sliding or a root drifting has something to be judged against.
bpy.ops.mesh.primitive_grid_add(size=6, x_subdivisions=12, y_subdivisions=12)
grid = bpy.context.object
grid.name = 'GROUND'
gm = mat('G', (0.18, 0.18, 0.20, 1))
grid.data.materials.append(gm)
grid.display_type = 'WIRE'

UP = Vector((0, 0, 1))
for i in range(f0, f1 + 1):
    fr = FRAMES[i]
    sc.frame_set(i + 1)
    for aid in ACTORS:
        act = (fr.get('actors') or {}).get(aid)
        if not act or not act.get('bones'):
            continue
        P = {n: v3(act['bones'][IDX[n]][:3]) for n in IDX if n in PARENT or n == 'root'}
        joints, bars = rig[aid]
        for name, s in joints.items():
            s.location = P[name]
            s.keyframe_insert('location')
        for name, c in bars.items():
            a, b = P[PARENT[name]], P[name]
            d = b - a
            L = max(1e-4, d.length)
            c.location = (a + b) / 2
            c.rotation_mode = 'QUATERNION'
            c.rotation_quaternion = UP.rotation_difference(d / L)
            c.scale = (1, 1, L)
            c.keyframe_insert('location')
            c.keyframe_insert('rotation_quaternion')
            c.keyframe_insert('scale')

# Linear between baked frames: the engine already eased this motion, and letting Blender ease it
# again would smooth away the very tremble this view exists to show.
for ob in bpy.data.objects:
    ad = getattr(ob, 'animation_data', None)
    act = getattr(ad, 'action', None) if ad else None
    if not act:
        continue
    for fc in (act.fcurves if hasattr(act, 'fcurves') else []):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'

# Camera: frame everything the actors do across the whole range, so nothing walks out of shot.
lo = Vector((1e9, 1e9, 1e9))
hi = Vector((-1e9, -1e9, -1e9))
for i in range(f0, f1 + 1):
    for aid in ACTORS:
        act = (FRAMES[i].get('actors') or {}).get(aid)
        if not act or not act.get('bones'):
            continue
        for b in act['bones']:
            p = v3(b[:3])
            lo = Vector((min(lo.x, p.x), min(lo.y, p.y), min(lo.z, p.z)))
            hi = Vector((max(hi.x, p.x), max(hi.y, p.y), max(hi.z, p.z)))
mid = (lo + hi) / 2
span = max(1.6, (hi - lo).length)
cd = bpy.data.cameras.new('cam')
cam = bpy.data.objects.new('cam', cd)
sc.collection.objects.link(cam)
sc.camera = cam
ang = math.radians(float(arg('angle', 35)))
dist = span * float(arg('dist', 1.25))
cam.location = (mid.x + math.sin(ang) * dist, mid.y - math.cos(ang) * dist, mid.z + span * 0.25)
cam.rotation_euler = (Vector(mid) - cam.location).to_track_quat('-Z', 'Y').to_euler()
cd.lens = float(arg('lens', 50))

sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light = 'FLAT'
sh.color_type = 'MATERIAL'
sh.show_xray = False
sc.render.film_transparent = False
sc.world = bpy.data.worlds.new('W')
sc.world.color = (0.05, 0.05, 0.06)
W, H = (int(v) for v in arg('res', '720x720').split('x'))
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.frame_start, sc.frame_end = f0 + 1, f1 + 1
out = arg('out', os.path.join(REPO, 'output', 'skeleton', FILM))
os.makedirs(out, exist_ok=True)
sc.render.filepath = os.path.join(out, 'f')
sc.render.image_settings.file_format = 'PNG'
print(f'[skeleton] {FILM}: {len(ACTORS)} actor(s), frames {f0}-{f1} -> {out}')
bpy.ops.render.render(animation=True)
print('[skeleton] done')
