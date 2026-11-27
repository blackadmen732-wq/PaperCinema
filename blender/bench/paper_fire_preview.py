"""PAPER FIRE preview (skill: pc-paper-fire), isolated from the episodes: a floating foxfire (kitsunebi motif; the scene
and timing are original) in cut paper, in front of a paper screen.

  blender -b -P blender/bench/paper_fire_preview.py -- --cam locked|moving [--emission 1.0] [--frames 1-60] [--out dir]

Layers (the existing paper shader, blender/world/paper_materials.paper_material):
  outer  opaque folded dark-red silhouettes, darker crease + worn edge (readable on dark)
  mid    warm orange sheets, a little glow
  core   a narrow ivory core, restrained glow
  embers drifting cut-paper triangles that rise, turn and shrink after the ignition
Each layer has 3 cut variants swapped on 2-4 frame accents (staggered per layer, like replacement animation), plus a
seeded lean/breath from FILM TIME. Ignition at frame 8 (one cue); a warm point light flickers with the flame and lights
the nearby screen. --emission scales every glow (the reduced-emission still).
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
BL = os.path.dirname(HERE)
REPO = os.path.dirname(BL)
sys.path.insert(0, os.path.join(BL, 'world'))
import paper_materials as PM                 # noqa: E402

ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(k, d=None):
    return ARGV[ARGV.index('--' + k) + 1] if '--' + k in ARGV else d


FPS, N = 24, 60
IGNITE = 8
EM = float(arg('emission', 1.0))
CAMK = arg('cam', 'locked')
OUT = arg('out', os.path.join(REPO, 'output', 'paper-fire', CAMK + ('' if EM == 1.0 else '-em%.2f' % EM)))
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = FPS
FLAME_AT = Vector((0.0, 0.0, 0.85))


def flame_outline(h, w, tongues, seed):
    """A cut-paper flame: wide in the lower third, tapering to a pointed tip, with sharp licks peeling off both sides
    (|sin|^3 peaks, not round bumps), in the XZ plane, base at z = 0."""
    rnd = random.Random(seed)

    def side(sign, tg, ph):
        out = []
        n = 34
        for i in range(n + 1):
            u = i / n
            body = w * (math.sin(math.pi * min(1.0, u * 1.6)) ** 0.7) * (1 - u) ** 1.25
            lick = 0.0
            if 0.18 < u < 0.95:
                lick = w * 0.75 * abs(math.sin(u * math.pi * tg + ph)) ** 3 * (1 - u) ** 0.6
            out.append((sign * (body + lick), h * u + (h * 0.10 * lick / max(w, 1e-6)) * 0.4))
        return out
    r = side(1, tongues, rnd.uniform(0, 3))
    l = side(-1, tongues + 1, rnd.uniform(0, 3))
    return r + l[::-1][1:-1]


def paper_sheet(name, outline, mat, fold=0.012):
    """The outline as a folded sheet: a crease down the middle (the centre line pushed back) and a paper thickness."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    vs = [bm.verts.new((x, fold * (1 - min(1.0, abs(x) / 0.05)), z)) for x, z in outline]
    c = bm.verts.new((0.0, fold, outline[len(outline) // 2][1] * 0.45))
    for a, b in zip(vs, vs[1:] + vs[:1]):
        bm.faces.new((a, b, c))
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = False
    o = bpy.data.objects.new(name, me)
    me.materials.append(mat)
    sol = o.modifiers.new('paper', 'SOLIDIFY')
    sol.thickness = 0.003
    sc.collection.objects.link(o)
    return o


# ------------------------------------------------------------------ materials (the existing paper shader)
outer_m = PM.paper_material('fire_outer', (0.16, 0.018, 0.015), translucency=0.04, fold_dark=0.45, edge_wear=0.6,
                            glow=((0.7, 0.08, 0.03), 0.06 * EM))   # opaque folded DARK red: the readable silhouette
mid_m = PM.paper_material('fire_mid', (0.95, 0.40, 0.08), translucency=0.45, fold_dark=0.2,
                          glow=((1.0, 0.45, 0.10), 1.2 * EM))
core_m = PM.paper_material('fire_core', (1.0, 0.93, 0.76), translucency=0.6, glow=((1.0, 0.86, 0.6), 3.0 * EM))
ember_m = PM.paper_material('fire_ember', (0.95, 0.45, 0.10), glow=((1.0, 0.5, 0.12), 2.0 * EM))
floor_m = PM.paper_material('floor_dark', (0.12, 0.11, 0.10), fibre_scale=6.0)
screen_m = PM.paper_material('screen_washi', (0.82, 0.76, 0.62), translucency=0.5, fibre_scale=10.0)
frame_m = PM.paper_material('screen_frame', (0.10, 0.07, 0.05), fibre_scale=8.0)

# ------------------------------------------------------------------ the set: dark floor, a paper screen catching the light
bpy.ops.mesh.primitive_plane_add(size=8, location=(0, 0, 0))
bpy.context.active_object.data.materials.append(floor_m)
for k in range(3):                                            # a three-panel shoji behind and to the side
    bpy.ops.mesh.primitive_plane_add(size=1, location=(-0.9 + k * 0.92, 0.85, 1.0), rotation=(math.radians(90), 0, 0))
    o = bpy.context.active_object
    o.scale = (0.44, 1.96, 1.0)                               # fills its frame (the plane's local y is up after the turn)
    o.data.materials.append(screen_m)
    for zz in (0.02, 1.98):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.9 + k * 0.92, 0.84, zz))
        bpy.context.active_object.scale = (0.46, 0.03, 0.03)
        bpy.context.active_object.data.materials.append(frame_m)
    for xx in (-0.44, 0.44):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.9 + k * 0.92 + xx, 0.84, 1.0))
        bpy.context.active_object.scale = (0.03, 0.03, 2.0)
        bpy.context.active_object.data.materials.append(frame_m)

# ------------------------------------------------------------------ the flame: 3 layers x 3 cut variants, + a crossed sheet
LAYERS = [  # name, material, height, width, depth offset (+y = behind), swap every n frames, phase, crossed copy
    ('outer', outer_m, 0.62, 0.16, 0.020, 3, 0, True),
    ('mid', mid_m, 0.46, 0.10, 0.000, 2, 1, True),
    ('core', core_m, 0.26, 0.045, -0.020, 4, 2, False),
]
groups = []
for li, (nm, mat, h, w, dy, every, phase, crossed) in enumerate(LAYERS):
    root = bpy.data.objects.new('FIRE_' + nm, None)
    sc.collection.objects.link(root)
    root.location = FLAME_AT + Vector((0, dy, 0))
    variants = []
    for v in range(3):
        sheets = [paper_sheet('%s_%d' % (nm, v), flame_outline(h * (1 + 0.06 * (v - 1)), w, 2 + v, 100 * li + v), mat)]
        if crossed:
            s2 = paper_sheet('%s_%dx' % (nm, v), flame_outline(h * 0.9, w * 0.85, 3 + v, 100 * li + v + 50), mat)
            s2.rotation_euler = (0, 0, math.radians(70))
            sheets.append(s2)
        for s in sheets:
            s.parent = root
        variants.append(sheets)
    groups.append((root, variants, every, phase, li))

light = bpy.data.lights.new('fire_light', 'POINT')
light.color = (1.0, 0.55, 0.22)
light.shadow_soft_size = 0.15
lo = bpy.data.objects.new('fire_light', light)
lo.location = FLAME_AT + Vector((0, -0.05, 0.15))
sc.collection.objects.link(lo)
moon = bpy.data.lights.new('moon', 'AREA')
moon.energy, moon.size, moon.color = 18, 4, (0.45, 0.55, 0.85)
mo = bpy.data.objects.new('moon', moon)
mo.location = (-3, -3, 4)
mo.rotation_euler = (Vector((0, 0, 0.8)) - Vector(mo.location)).to_track_quat('-Z', 'Y').to_euler()
sc.collection.objects.link(mo)

# embers
rnd = random.Random(7)
embers = []
for i in range(26):
    me = bpy.data.meshes.new('ember%d' % i)
    bm = bmesh.new()
    s = rnd.uniform(0.010, 0.022)
    vs = [bm.verts.new((s * math.cos(a), 0, s * math.sin(a))) for a in (0.3, 2.4, 4.3)]
    bm.faces.new(vs)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new('ember%d' % i, me)
    me.materials.append(ember_m)
    o.modifiers.new('paper', 'SOLIDIFY').thickness = 0.002
    sc.collection.objects.link(o)
    embers.append((o, IGNITE + 2 + rnd.uniform(0, N - IGNITE - 14), rnd.uniform(0.25, 0.55), rnd.uniform(-0.12, 0.12),
                   rnd.uniform(0, 6.28), rnd.uniform(18, 34)))


def wob(t, f, ph):
    return math.sin(2 * math.pi * f * t + ph)


for f in range(1, N + 1):
    t = f / FPS
    grow = 0.0 if f < IGNITE else min(1.15, (f - IGNITE) / 6.0)
    if f >= IGNITE + 6:
        grow = 1.0 + 0.15 * math.exp(-(f - IGNITE - 6) / 3.0) * math.cos((f - IGNITE - 6) * 1.3)   # settles after the flare
    for root, variants, every, phase, li in groups:
        # replacement swap on 2-4 frame accents, staggered per layer
        k = ((f + phase) // every) % 3
        for vi, sheets in enumerate(variants):
            for s in sheets:
                s.hide_render = (vi != k) or grow <= 0.0
                s.keyframe_insert('hide_render', frame=f)
        breath = 1 + 0.07 * wob(t, 1.7 + 0.4 * li, li) + 0.04 * wob(t, 3.9, 2 * li)
        root.scale = (grow * (1 + 0.05 * wob(t, 2.3, li)), grow, max(1e-3, grow * breath))
        root.rotation_euler = (0, 0.10 * wob(t, 0.9, li) + 0.05 * wob(t, 2.7, 1 + li), 0.25 * wob(t, 0.35, li))
        root.keyframe_insert('scale', frame=f)
        root.keyframe_insert('rotation_euler', frame=f)
    light.energy = (0.0 if f < IGNITE else 55.0 * grow * (1 + 0.12 * wob(t, 7.0, 0.3) + 0.06 * wob(t, 13.0, 1.1))) * max(EM, 0.25)
    light.keyframe_insert('energy', frame=f)
    for o, born, vz, vx, ph, life in embers:
        age = f - born
        if age < 0 or age > life:
            o.scale = (0, 0, 0)
            o.location = FLAME_AT
        else:
            u = age / life
            o.location = FLAME_AT + Vector((vx * age / FPS + 0.04 * math.sin(ph + age * 0.4), 0.03 * math.sin(ph),
                                            0.28 + vz * age / FPS))
            o.rotation_euler = (ph + age * 0.3, ph * 0.5, age * 0.21)
            sk = (1 - u) ** 0.7
            o.scale = (sk, sk, sk)
        o.keyframe_insert('location', frame=f)
        o.keyframe_insert('rotation_euler', frame=f)
        o.keyframe_insert('scale', frame=f)

# camera: locked (medium, slightly low) or moving (a slow arc + push in, eased)
cd = bpy.data.cameras.new('cam')
cd.lens = 40
cam = bpy.data.objects.new('cam', cd)
sc.collection.objects.link(cam)
sc.camera = cam
look = FLAME_AT + Vector((0, 0.15, 0.05))
for f in range(1, N + 1):
    u = (f - 1) / (N - 1)
    if CAMK == 'moving':
        e = u * u * (3 - 2 * u)
        a = math.radians(-28 + 36 * e)
        d = 2.6 - 0.6 * e
        cam.location = look + Vector((d * math.sin(a), -d * math.cos(a), 0.05 + 0.25 * e))
    else:
        cam.location = look + Vector((0.55, -2.35, 0.12))
    cam.rotation_euler = (look - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.keyframe_insert('location', frame=f)
    cam.keyframe_insert('rotation_euler', frame=f)

w = bpy.data.worlds.new('night')
w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.010, 0.012, 0.022, 1)
w.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
sc.world = w
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = int(arg('samples', 16))
sc.cycles.use_denoising = True
sc.view_settings.view_transform = 'AgX'
sc.view_settings.look = 'AgX - Medium High Contrast'
sc.render.resolution_x, sc.render.resolution_y = [int(v) for v in arg('res', '540x960').split('x')]
a, b = [int(v) for v in arg('frames', '1-%d' % N).split('-')]
sc.frame_start, sc.frame_end = a, b
os.makedirs(OUT, exist_ok=True)
sc.render.filepath = os.path.join(OUT, 'f')
bpy.ops.render.render(animation=True)
print('[fire] rendered', CAMK, 'emission', EM, a, '-', b, '->', OUT)
