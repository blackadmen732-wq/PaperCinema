"""Render one operator's view of the camera bench (tools/camera_bench.py solve writes output/camera-bench/bench.json).

  blender -b -P blender/bench/camera_bench_render.py -- --cam operator [--samples 8] [--frames 1-192]

Paper arena: the existing paper shader (blender/world/paper_materials.paper_material) on faceted boxes and the floor,
a folded paper ball. Isolated from the episodes.
"""
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
BL = os.path.dirname(HERE)
REPO = os.path.dirname(BL)
for p in ('world', 'character', ''):
    sys.path.insert(0, os.path.join(BL, p))
import paper_materials as PM                 # noqa: E402

ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(k, d=None):
    return ARGV[ARGV.index('--' + k) + 1] if '--' + k in ARGV else d


OUT = os.path.join(REPO, 'output', 'camera-bench')
B = json.load(open(os.path.join(OUT, 'bench.json')))
CAM = arg('cam', 'operator')
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = B['fps']

COLOURS = [(0.62, 0.48, 0.32), (0.86, 0.82, 0.72), (0.22, 0.27, 0.40), (0.55, 0.16, 0.13), (0.70, 0.62, 0.45),
           (0.35, 0.40, 0.33)]


def paper(name, rgb):
    try:
        return PM.paper_material(name, (*rgb, 1.0))
    except Exception:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*rgb, 1)
        return m


def box(name, c, s, mat):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=s, verts=bm.verts[:])
    bmesh.ops.bevel(bm, geom=bm.edges[:], offset=0.015, segments=1, affect='EDGES')   # a folded card edge, not a CG cube
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = False
    o = bpy.data.objects.new(name, me)
    o.location = c
    me.materials.append(mat)
    sc.collection.objects.link(o)
    return o


box('floor', (0, 0, -0.05), (24, 24, 0.1), paper('floor_washi', (0.80, 0.76, 0.66)))
for i, (c, s) in enumerate(B['boxes']):
    box('box%02d' % i, c, s, paper('box_paper_%d' % (i % len(COLOURS)), COLOURS[i % len(COLOURS)]))

# the ball: a folded (icosphere, flat facets) paper ball, two tones so its turn reads, a little lantern glow
me = bpy.data.meshes.new('ball')
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions=1, radius=B['ball_r'])
for f_ in bm.faces:
    f_.material_index = 0 if f_.calc_center_median().z > 0 else 1
bm.to_mesh(me)
bm.free()
ball = bpy.data.objects.new('ball', me)
me.materials.append(PM.emission_material('ball_glow', (1.0, 0.45, 0.12, 1), 6.0) if hasattr(PM, 'emission_material') else paper('ball_a', (0.95, 0.42, 0.12)))
me.materials.append(paper('ball_b', (0.97, 0.90, 0.75)))
sc.collection.objects.link(ball)
for k, p in enumerate(B['ball']):
    ball.location = p
    ball.rotation_euler = (k * 0.09, k * 0.05, 0)
    ball.keyframe_insert('location', frame=k + 1)
    ball.keyframe_insert('rotation_euler', frame=k + 1)

# light: a warm key, a cool fill, a soft sky
for nm, loc, e, col in (('key', (6, -8, 10), 900, (1.0, 0.92, 0.80)), ('fill', (-8, -4, 6), 220, (0.75, 0.85, 1.0)),
                        ('rim', (0, 10, 8), 400, (1.0, 0.85, 0.70))):
    L = bpy.data.lights.new(nm, 'AREA')
    L.energy, L.size, L.color = e, 4.0, col
    o = bpy.data.objects.new(nm, L)
    o.location = loc
    o.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    sc.collection.objects.link(o)
w = bpy.data.worlds.new('w')
w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.55, 0.58, 0.64, 1)
w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.35
sc.world = w

cd = bpy.data.cameras.new('cam')
cd.sensor_fit = 'VERTICAL'
cd.sensor_height = B['sensor_h']
cam = bpy.data.objects.new('cam', cd)
cam.rotation_mode = 'QUATERNION'
sc.collection.objects.link(cam)
sc.camera = cam
for k, c in enumerate(B['cams'][CAM]):
    cam.location = c['pos']
    cam.rotation_quaternion = Quaternion(c['rot'])
    cd.lens = c['lens']
    cam.keyframe_insert('location', frame=k + 1)
    cam.keyframe_insert('rotation_quaternion', frame=k + 1)
    cd.keyframe_insert('lens', frame=k + 1)
for ob in (cam, cd, ball):
    ad = ob.animation_data
    if ad and ad.action:
        for fc in ad.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'

sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = int(arg('samples', 8))
sc.cycles.use_denoising = True
sc.view_settings.view_transform = 'AgX'
sc.view_settings.look = 'AgX - Medium High Contrast'
sc.view_settings.exposure = -0.4
sc.render.resolution_x, sc.render.resolution_y = B['view']
a, b = [int(v) for v in arg('frames', '1-%d' % B['n']).split('-')]
sc.frame_start, sc.frame_end = a, b
out = os.path.join(OUT, CAM)
os.makedirs(out, exist_ok=True)
sc.render.filepath = os.path.join(out, 'f')
sc.render.image_settings.file_format = 'PNG'
bpy.ops.render.render(animation=True)
print('[bench] rendered', CAM, a, '-', b)
