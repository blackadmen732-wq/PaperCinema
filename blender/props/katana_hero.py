"""KATANA_HERO: our own close-up katana for covers, thumbnails and opening A ("the glint").

  B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
  $B -b -t 4 -P blender/props/katana_hero.py -- --out output/covers/katana.png [--res 1080x1920] [--samples 48]
     [--draw 0.11] [--angle 58] [--motif seigaiha]

Mark, Nov 26: "for the blade one, make it ours and make it literally ours". Every piece is built here from data,
nothing downloaded: a wrapped handle (white ray-skin under black cord crossing in diamonds), a black lacquer
pommel, brass collars, a four-lobed iron guard (mokko) carrying OUR motif in gold (seigaiha waves round a sun:
the same pattern the cover's background uses), a hand's width of drawn blade with a wavy temper line (hamon),
and the black lacquer scabbard with a vermilion cord. It renders on a transparent background so tools/cover.py
can put the big kanji BEHIND it.

The sword lies along +X (pommel at -X, tip side +X), the flat of the blade facing the camera; --angle tilts it
across the frame. --draw is how much blade shows between the guard and the scabbard, in metres.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(n, d=None):
    return ARGV[ARGV.index('--' + n) + 1] if '--' + n in ARGV else d


HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene


# ------------------------------------------------------------------ materials
def principled(name, rgb, rough, metal=0.0, coat=0.0, spec=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if 'Specular IOR Level' in b.inputs:              # matte cord and silk should not mirror the studio
        b.inputs['Specular IOR Level'].default_value = spec
    if coat and 'Coat Weight' in b.inputs:
        b.inputs['Coat Weight'].default_value = coat
        b.inputs['Coat Roughness'].default_value = 0.08
    return m


def bumpy(m, scale, strength):
    """Fine noise bump: the grain of ray skin, cord, paper."""
    nt = m.node_tree
    tex = nt.nodes.new('ShaderNodeTexNoise')
    tex.inputs['Scale'].default_value = scale
    tex.inputs['Detail'].default_value = 6
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = strength
    nt.links.new(tex.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], nt.nodes['Principled BSDF'].inputs['Normal'])
    return m


LACQUER = principled('lacquer', (0.012, 0.011, 0.013), 0.16, coat=0.7)
BRASS = principled('brass', (0.95, 0.60, 0.24), 0.28, metal=1.0)
STEEL = principled('steel', (0.86, 0.87, 0.89), 0.10, metal=1.0)
HAMON = principled('hamon', (0.93, 0.94, 0.96), 0.42, metal=0.55)
SAME = bumpy(principled('samegawa', (0.90, 0.87, 0.80), 0.75), 900, 0.35)
CORD = bumpy(principled('ito', (0.006, 0.006, 0.008), 0.8, spec=0.08), 400, 0.2)
SAGEO = bumpy(principled('sageo', (0.55, 0.05, 0.008), 0.75, spec=0.12), 380, 0.3)
HORN = principled('horn', (0.86, 0.82, 0.74), 0.35)


def iron_with_motif(name):
    """The guard: dark iron, OUR motif inlaid in brass from an image drawn here (gold where the image is white)."""
    motif = draw_motif(arg('motif', 'seigaiha'))
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    iron = nt.nodes.new('ShaderNodeBsdfPrincipled')
    iron.inputs['Base Color'].default_value = (0.035, 0.032, 0.032, 1)
    iron.inputs['Metallic'].default_value = 0.8
    iron.inputs['Roughness'].default_value = 0.48
    gold = nt.nodes.new('ShaderNodeBsdfPrincipled')
    gold.inputs['Base Color'].default_value = (0.97, 0.64, 0.25, 1)
    gold.inputs['Metallic'].default_value = 1.0
    gold.inputs['Roughness'].default_value = 0.25
    tc = nt.nodes.new('ShaderNodeTexCoord')
    img = nt.nodes.new('ShaderNodeTexImage')
    img.image = motif
    img.extension = 'CLIP'
    nt.links.new(tc.outputs['UV'], img.inputs['Vector'])
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(img.outputs['Color'], mix.inputs['Fac'])
    nt.links.new(iron.outputs[0], mix.inputs[1])
    nt.links.new(gold.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    return m


def draw_motif(motif):
    """Our tsuba design, drawn as an image (white = gold inlay): seigaiha waves (overlapping rows of concentric
    arcs, painted back to front so each row covers the lower half of the row behind) under a rising sun, inside a
    rim line. The cover's background uses the same two shapes, so guard and page belong together."""
    import numpy as np
    N = 1024
    yy, xx = np.mgrid[0:N, 0:N].astype('float32')
    u, v = xx / N * 2 - 1, 1 - yy / N * 2
    r = np.sqrt(u * u + v * v)
    img = np.zeros((N, N), 'float32')
    s_ = 0.19                                            # wave circle radius
    rows = np.arange(0.05, -1.2, -s_ * 0.5)              # from the horizon down, back to front
    for i, cy in enumerate(rows):
        off = (i % 2) * s_
        for cx in np.arange(-1.2 - off, 1.3, 2 * s_):
            d = np.sqrt((u - cx) ** 2 + (v - cy) ** 2)
            inside = d < s_
            ring = (np.mod(d, s_ / 3.4) < 0.022).astype('float32')
            img[inside] = ring[inside]
    img[v > 0.05] = 0
    sun = np.sqrt((u - 0.28) ** 2 + (v - 0.40) ** 2)
    img[sun < 0.18] = 1.0
    img[(sun > 0.225) & (sun < 0.25)] = 1.0
    img[r > 0.86] = 0
    img[(r > 0.86) & (r < 0.92)] = 1.0                   # the rim line
    rgba = np.ones((N, N, 4), 'float32')
    rgba[..., :3] = np.flipud(np.clip(img, 0, 1))[..., None]   # Blender rows start at the bottom
    im = bpy.data.images.new('tsuba_motif', N, N)
    im.pixels.foreach_set(rgba.ravel())
    im.pack()
    return im


# ------------------------------------------------------------------ geometry helpers
def obj(name, bm, mat, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = smooth
    sc.collection.objects.link(o)
    o.parent = ROOT
    return o


def ellipse_tube(name, x0, x1, ry, rz, mat, segs=28, rings=2, smooth=True, taper=1.0):
    bm = bmesh.new()
    rows = []
    for i in range(rings + 1):
        t = i / rings
        x = x0 + (x1 - x0) * t
        k = 1 + (taper - 1) * t
        rows.append([bm.verts.new((x, ry * k * math.cos(a), rz * k * math.sin(a)))
                     for a in (2 * math.pi * j / segs for j in range(segs))])
    for a, b in zip(rows, rows[1:]):
        for j in range(segs):
            bm.faces.new((a[j], a[(j + 1) % segs], b[(j + 1) % segs], b[j]))
    for row, flip in ((rows[0], True), (rows[-1], False)):
        f = bm.faces.new(row[::-1] if flip else row)
    return obj(name, bm, mat, smooth)


def helix_band(name, x0, x1, ry, rz, turns, phase, width, mat, lift=0.0016, steps=220):
    """A flat cord following a helix round an elliptical handle."""
    bm = bmesh.new()
    left, right = [], []
    for i in range(steps + 1):
        t = i / steps
        x = x0 + (x1 - x0) * t
        a = phase + 2 * math.pi * turns * t
        n = Vector((0, math.cos(a), math.sin(a)))
        p = Vector((x, (ry + lift) * math.cos(a), (rz + lift) * math.sin(a)))
        # the band's width runs across the cord: along the handle axis, tilted with the helix
        tang = Vector((x1 - x0, -(ry + lift) * math.sin(a) * 2 * math.pi * turns,
                       (rz + lift) * math.cos(a) * 2 * math.pi * turns)).normalized()
        side = tang.cross(n).normalized() * width / 2
        left.append(bm.verts.new(p - side))
        right.append(bm.verts.new(p + side))
    for i in range(steps):
        bm.faces.new((left[i], left[i + 1], right[i + 1], right[i]))
    return obj(name, bm, mat, True)


ROOT = bpy.data.objects.new('KATANA_HERO', None)
sc.collection.objects.link(ROOT)

# ------------------------------------------------------------------ handle (tsuka)
L_TSUKA, RY, RZ = 0.27, 0.0165, 0.0128
ellipse_tube('tsuka_core', -L_TSUKA, -0.012, RY, RZ, SAME, segs=32, rings=8)
pitch = 0.052
turns = L_TSUKA / pitch
for k in range(2):                                   # two cords each way: diamonds where they cross
    helix_band(f'ito_a{k}', -L_TSUKA + 0.02, -0.016, RY, RZ, turns, k * math.pi, 0.0105, CORD)
    helix_band(f'ito_b{k}', -L_TSUKA + 0.02, -0.016, RY, RZ, -turns, k * math.pi + math.pi / 2, 0.0105, CORD,
               lift=0.0021)
ellipse_tube('kashira', -L_TSUKA - 0.028, -L_TSUKA + 0.004, RY * 1.08, RZ * 1.08, LACQUER, segs=32)
ellipse_tube('kashira_ring', -L_TSUKA + 0.0, -L_TSUKA + 0.006, RY * 1.12, RZ * 1.12, BRASS, segs=32)
ellipse_tube('fuchi', -0.016, -0.0005, RY * 1.1, RZ * 1.1, BRASS, segs=32)
# menuki: a small brass ornament under the wrap on the face toward the camera
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=1.0,
                          matrix=Matrix.Translation((-0.13, -RY - 0.002, 0.0)) @ Matrix.Diagonal((0.022, 0.004, 0.008, 1)))
obj('menuki', bm, BRASS, True)

# ------------------------------------------------------------------ guard (tsuba): four-lobed, our motif
R, T = 0.041, 0.006
bm = bmesh.new()
n = 96
outline = []
for j in range(n):
    a = 2 * math.pi * j / n
    rr = R * (0.90 + 0.10 * abs(math.cos(2 * a)) ** 0.6) * (1 - 0.06 * (abs(math.sin(2 * a)) ** 8))
    outline.append((rr * math.cos(a), rr * math.sin(a)))
front = [bm.verts.new((T, y, z)) for y, z in outline]
back = [bm.verts.new((0.0, y, z)) for y, z in outline]
ff = bm.faces.new(front)
bm.faces.new(back[::-1])
for j in range(n):
    bm.faces.new((back[j], back[(j + 1) % n], front[(j + 1) % n], front[j])).material_index = 1   # the brass edge
uv = bm.loops.layers.uv.new()
for f in bm.faces:
    for lp in f.loops:
        co = lp.vert.co
        lp[uv].uv = (0.5 + co.y / (2 * R), 0.5 + co.z / (2 * R))
TSUBA = obj('tsuba', bm, iron_with_motif('tsuba_iron'))
TSUBA.data.materials.append(BRASS)

# ------------------------------------------------------------------ habaki + drawn blade
DRAW = float(arg('draw', 0.11))
W_BLADE, TH = 0.031, 0.0072
ellipse_tube('seppa', T, T + 0.003, 0.021, 0.0105, BRASS, segs=24)
bm = bmesh.new()                                    # habaki: a brass wedge round the blade base
bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((T + 0.019, 0, 0)) @
                      Matrix.Diagonal((0.032, TH * 1.9, W_BLADE * 1.12, 1)))
obj('habaki', bm, BRASS)


def blade(x0, x1):
    """The blade in strips along its length. Cross-section: the edge (both faces meet), the frosted temper up to a
    wavy hamon line, mirror steel up to the ridge (shinogi), then the back (mune), closed by a spine strip."""
    bm = bmesh.new()
    steps = 48

    def ham(x):
        return -W_BLADE / 2 + W_BLADE * (0.30 + 0.06 * math.sin(x * 130) + 0.025 * math.sin(x * 330 + 1))

    def section(x, side):
        return [Vector((x, 0.0, -W_BLADE / 2)),                       # edge
                Vector((x, side * TH * 0.38, ham(x))),                # hamon line
                Vector((x, side * TH * 0.50, W_BLADE * 0.22)),        # shinogi ridge
                Vector((x, side * TH * 0.30, W_BLADE / 2))]           # mune
    mats = (1, 0, 0)                                                  # frosted, steel, steel
    for i in range(steps):
        xa, xb = x0 + (x1 - x0) * i / steps, x0 + (x1 - x0) * (i + 1) / steps
        for side in (-1, 1):
            A = [bm.verts.new(p) for p in section(xa, side)]
            B = [bm.verts.new(p) for p in section(xb, side)]
            for k in range(3):
                q = (A[k], B[k], B[k + 1], A[k + 1])
                f = bm.faces.new(q if side > 0 else q[::-1])
                f.material_index = mats[k]
        ma, mb = section(xa, -1)[3], section(xb, -1)[3]
        pa, pb = section(xa, 1)[3], section(xb, 1)[3]
        bm.faces.new([bm.verts.new(c) for c in (ma, mb, pb, pa)])
    me = bpy.data.meshes.new('blade')
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new('blade', me)
    me.materials.append(STEEL)
    me.materials.append(HAMON)
    sc.collection.objects.link(o)
    o.parent = ROOT
    return o


X_BLADE0 = T + 0.035
blade(X_BLADE0, X_BLADE0 + DRAW)

# ------------------------------------------------------------------ scabbard (saya) with the vermilion cord
X_SAYA = X_BLADE0 + DRAW
ellipse_tube('koiguchi', X_SAYA, X_SAYA + 0.018, 0.0205, 0.0115, HORN, segs=32)
ellipse_tube('saya', X_SAYA + 0.018, X_SAYA + 0.75, 0.0195, 0.0110, LACQUER, segs=32, rings=6, taper=0.9)
# kurikata (cord knob) and the sageo wrapped round the scabbard, then hanging down in a loop
X_KURI = X_SAYA + 0.09
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((X_KURI, -0.0, -0.0145)) @ Matrix.Diagonal((0.024, 0.012, 0.008, 1)))
obj('kurikata', bm, LACQUER)
for k in range(3):
    helix_band(f'sageo_wrap{k}', X_KURI + 0.02 + k * 0.016, X_KURI + 0.034 + k * 0.016, 0.0195, 0.0110, 1.0, k * 0.7,
               0.007, SAGEO, lift=0.0022, steps=48)
# the hanging loop: a cord tube from the knob down and back, ending in a tassel
pts = [Vector((X_KURI, 0.0, -0.018))]
for i in range(1, 13):
    t = i / 12
    pts.append(Vector((X_KURI - 0.05 * math.sin(t * math.pi) - 0.03 * t, -0.004 * math.sin(t * 6),
                       -0.018 - 0.16 * math.sin(t * math.pi * 0.85))))
bm = bmesh.new()
segs = 8
rings = []
for i, p in enumerate(pts):
    d = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
    q = d.to_track_quat('Z', 'Y')
    rings.append([bm.verts.new(p + q @ Vector((0.0032 * math.cos(a), 0.0032 * math.sin(a), 0)))
                  for a in (2 * math.pi * j / segs for j in range(segs))])
for a, b in zip(rings, rings[1:]):
    for j in range(segs):
        bm.faces.new((a[j], a[(j + 1) % segs], b[(j + 1) % segs], b[j]))
obj('sageo_loop', bm, SAGEO, True)
end = pts[-1]
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.0, radius2=0.011, depth=0.05,
                      matrix=Matrix.Translation(end + Vector((0, 0, -0.025))))
obj('tassel', bm, SAGEO)
for j in range(14):                                 # tassel threads
    a = 2 * math.pi * j / 14
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(end + Vector((0.009 * math.cos(a), 0.009 * math.sin(a), -0.075))) @
                          Matrix.Rotation(0.15 * math.cos(a), 4, 'Y') @ Matrix.Diagonal((0.0016, 0.0016, 0.055, 1)))
    obj(f'tassel_thread{j}', bm, SAGEO)

# ------------------------------------------------------------------ pose, camera, light
# The sword points AWAY from the camera, pommel nearest (the reference's view): the guard shows its face, the
# handle looms large, the scabbard runs off up and to the right. --axis is the pommel-to-tip direction (x right,
# y away, z up); --roll turns the blade about its own axis.
from mathutils import Quaternion
axis = Vector(tuple(float(v) for v in arg('axis', '0.40,0.62,0.68').split(','))).normalized()
ROOT.rotation_mode = 'QUATERNION'
ROOT.rotation_quaternion = axis.to_track_quat('X', 'Z') @ Quaternion((1, 0, 0), math.radians(float(arg('roll', 15))))
ROOT.location = (0, 0, 0)
cam_d = bpy.data.cameras.new('cam')
cam_d.lens = float(arg('lens', 45))
cam_d.sensor_fit = 'VERTICAL'
cam = bpy.data.objects.new('cam', cam_d)
sc.collection.objects.link(cam)
sc.camera = cam
cam.location = (0.0, -float(arg('dist', 0.62)), -0.035)
cam.rotation_euler = (math.radians(90), 0, 0)
for nm, loc, energy, size, col in (('key', (-0.6, -0.7, 0.8), 45, 0.5, (1.0, 0.95, 0.88)),
                                   ('rim', (0.6, 0.7, 0.5), 90, 0.35, (1.0, 0.72, 0.45)),
                                   ('fill', (0.5, -0.9, -0.5), 8, 1.0, (0.85, 0.9, 1.0)),
                                   ('glint', (0.18, -0.45, 0.30), 25, 0.03, (1.0, 1.0, 1.0))):
    L = bpy.data.lights.new(nm, 'AREA')
    L.energy, L.size, L.color = energy, size, col
    o = bpy.data.objects.new(nm, L)
    o.location = loc
    o.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    sc.collection.objects.link(o)
world = bpy.data.worlds.new('w')
world.use_nodes = True
bg = world.node_tree.nodes['Background']
bg.inputs['Color'].default_value = (0.92, 0.90, 0.88, 1)   # a soft white studio: what the metal reflects
bg.inputs['Strength'].default_value = 0.12
sc.world = world

sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = int(arg('samples', 48))
sc.cycles.use_denoising = True
sc.render.film_transparent = True
sc.view_settings.view_transform = 'AgX'
sc.view_settings.look = 'AgX - Medium High Contrast'
rx, ry = (int(v) for v in arg('res', '1080x1920').split('x'))
sc.render.resolution_x, sc.render.resolution_y = rx, ry
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGBA'
out = os.path.abspath(arg('out', os.path.join(REPO, 'output', 'covers', 'katana.png')))
os.makedirs(os.path.dirname(out), exist_ok=True)
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
print('[katana] wrote', out)
