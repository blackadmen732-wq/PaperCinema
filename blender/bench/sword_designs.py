"""SWORD DESIGNS: every design in library/swords/ built by blender/props/katana_real.py, side by side, drawn (blade
above its scabbard), so a design change is checked by eye before it reaches a film.

    $B -b -P blender/bench/sword_designs.py -- [--out output/swords/designs.png] [--designs shiokaze,yamikaze]
"""
import math
import os
import sys

import bpy
from mathutils import Euler, Vector

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender', 'props'))
import katana_real as KR  # noqa: E402

A = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
arg = lambda k, d=None: A[A.index('--' + k) + 1] if '--' + k in A else d
names = (arg('designs') or ','.join(['default'] + sorted(f[:-5] for f in os.listdir(os.path.join(REPO, 'library', 'swords'))
                                                         if f.endswith('.json')))).split(',')
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
coll = sc.collection
for i, nm in enumerate(names):
    k = KR.build('SW_' + nm, coll, blade_len=0.91, design=None if nm == 'default' else nm)
    y = -i * 0.30
    k['sword'].location = (0.0, y, 0.10)
    k['sword'].rotation_euler = Euler((math.radians(-90), 0, 0))       # the flat of the blade up, edge to the viewer
    k['saya'].location = (0.06, y - 0.11, 0.10)
    k['saya'].rotation_euler = Euler((math.radians(-90), 0, 0))
    t = bpy.data.objects.new('label_' + nm, bpy.data.curves.new('label_' + nm, 'FONT'))
    t.data.body = nm
    t.data.size = 0.045
    t.location = (-0.42, y - 0.05, 0.10)
    coll.objects.link(t)
    t.data.materials.append(KR._principled('label', (0.9, 0.9, 0.9), 0.5))
bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, 0))
bpy.context.object.data.materials.append(KR._principled('floor', (0.18, 0.17, 0.16), 0.8))
w = bpy.data.worlds.new('w')
w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.05, 0.05, 0.055, 1)
w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.6
sc.world = w
for loc, en in (((1.5, 1.5, 3.0), 600), ((-2.0, -1.0, 2.0), 250)):
    L = bpy.data.objects.new('L', bpy.data.lights.new('L', 'AREA'))
    L.data.energy, L.data.size = en, 2.0
    L.location = loc
    L.rotation_euler = (Vector((0, -0.6, 0.1)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    coll.objects.link(L)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
coll.objects.link(cam)
sc.camera = cam
mid = Vector((0.25, -0.15 * (len(names) - 1) - 0.05, 0.1))
cam.location = mid + Vector((0.0, -0.9, 1.9))
cam.rotation_euler = (mid - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = 34
if arg('guards'):            # --guards 1: every guard face-on, seen from past the blade tips (the blade points at us)
    for i, nm in enumerate(names):
        o = bpy.data.objects['SW_' + nm + '_SWORD']
        o.location = (0.0, -i * 0.11, 0.10)
        o.rotation_euler = (0.0, 0.0, 0.0)
        bpy.data.objects['SW_' + nm + '_SAYA'].hide_render = True
        bpy.data.objects['label_' + nm].location = (0.0, -i * 0.11 - 0.035, 0.035)
        bpy.data.objects['label_' + nm].rotation_euler = (math.radians(90), 0, math.radians(90))
        bpy.data.objects['label_' + nm].data.size = 0.014
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = 0.11 * len(names) + 0.04
    cam.data.clip_end = 10
    cam.location = (2.5, -0.11 * (len(names) - 1) / 2, 0.10)
    cam.rotation_euler = Vector((-1, 0, 0)).to_track_quat('-Z', 'Y').to_euler()
sc.render.engine = 'CYCLES'
sc.cycles.samples = int(arg('samples', 48))
sc.cycles.device = 'CPU'
sc.render.resolution_x, sc.render.resolution_y = (1600, 420) if arg('guards') else (1400, 1000)
sc.render.filepath = os.path.join(REPO, arg('out', 'output/swords/designs.png'))
bpy.ops.render.render(write_still=True)
print('[swords]', len(names), 'designs ->', sc.render.filepath)
