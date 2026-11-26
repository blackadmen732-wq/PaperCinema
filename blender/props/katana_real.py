"""KATANA_REAL: the one real sword and scabbard every scene uses (Mark, 26 Nov: "the blade have to be real,
like real metal ... the one that hold the blade have to be real 3D").

It is the cover katana (blender/props/katana_hero.py: wrapped handle, brass collars, the four-lobed iron
guard with OUR seigaiha-and-sun motif in gold) made whole and reusable:
  - a FULL-LENGTH blade with a real curve (sori), a ridge line (shinogi), a wavy temper line (hamon), a
    tapered body and a curved point (kissaki), in mirror steel;
  - a scabbard (saya) that follows the SAME curve, wide enough to hold the blade, with a horn mouth
    (koiguchi), a cord knob (kurikata) wrapped in the vermilion cord (sageo) and a horn end cap (kojiri).
Because blade and scabbard share one circle, the draw can slide the blade out ALONG ITS OWN CURVE
(sword_draw.arc), the way a real katana leaves its saya, instead of pushing a straight stick.

Frames (the timeline's weapon frame, metres): guard at x = 0, blade +x, edge -y, handle -x. The scabbard is
built in the same frame with its mouth at x = 0, so a sheathed sword has the SAME frame as its scabbard.
The curve bends toward +y (the back, mune), so the edge is on the outside of the curve.

  from katana_real import build
  k = build('KOJIRO', bpy.context.scene.collection, blade_len=0.91)
  k['sword'], k['saya'], k['R']        # two empties to place, and the curve's radius
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

_ROT = Matrix.Rotation(math.radians(-90), 4, 'X')   # built edge -z (as the cover sword), turned to edge -y


def _principled(name, rgb, rough, metal=0.0, coat=0.0, spec=0.5):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if 'Specular IOR Level' in b.inputs:
        b.inputs['Specular IOR Level'].default_value = spec
    if coat and 'Coat Weight' in b.inputs:
        b.inputs['Coat Weight'].default_value = coat
        b.inputs['Coat Roughness'].default_value = 0.08
    return m


def _bumpy(m, scale, strength):
    nt = m.node_tree
    if any(n.type == 'BUMP' for n in nt.nodes):
        return m
    tex = nt.nodes.new('ShaderNodeTexNoise')
    tex.inputs['Scale'].default_value = scale
    tex.inputs['Detail'].default_value = 6
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = strength
    nt.links.new(tex.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], nt.nodes['Principled BSDF'].inputs['Normal'])
    return m


def materials(cord=(0.006, 0.006, 0.008), sageo=(0.55, 0.05, 0.008), lacquer=(0.012, 0.011, 0.013)):
    return {
        'lacquer': _principled('kr_lacquer', lacquer, 0.16, coat=0.7),
        'brass': _principled('kr_brass', (0.95, 0.60, 0.24), 0.28, metal=1.0),
        'steel': _principled('kr_steel', (0.86, 0.87, 0.89), 0.09, metal=1.0),
        'hamon': _principled('kr_hamon', (0.93, 0.94, 0.96), 0.40, metal=0.6),
        'same': _bumpy(_principled('kr_samegawa', (0.90, 0.87, 0.80), 0.75), 900, 0.35),
        'cord': _bumpy(_principled('kr_ito', cord, 0.8, spec=0.08), 400, 0.2),
        'sageo': _bumpy(_principled('kr_sageo', sageo, 0.75, spec=0.12), 380, 0.3),
        'horn': _principled('kr_horn', (0.86, 0.82, 0.74), 0.35),
    }


def tsuba_material(motif='seigaiha'):
    """Dark iron with our motif inlaid in gold, from katana_hero's drawing (white = gold)."""
    name = 'kr_tsuba_' + motif
    m = bpy.data.materials.get(name)
    if m:
        return m
    im = _draw_motif()
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
    img.image = im
    img.extension = 'CLIP'
    nt.links.new(tc.outputs['UV'], img.inputs['Vector'])
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(img.outputs['Color'], mix.inputs['Fac'])
    nt.links.new(iron.outputs[0], mix.inputs[1])
    nt.links.new(gold.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    return m


def _draw_motif(N=512):
    """Seigaiha waves under a rising sun inside a rim line (the cover's design, see katana_hero.draw_motif)."""
    import numpy as np
    im = bpy.data.images.get('kr_motif')
    if im:
        return im
    yy, xx = np.mgrid[0:N, 0:N].astype('float32')
    u, v = xx / N * 2 - 1, 1 - yy / N * 2
    r = np.sqrt(u * u + v * v)
    img = np.zeros((N, N), 'float32')
    s_ = 0.19
    for i, cy in enumerate(np.arange(0.05, -1.2, -s_ * 0.5)):
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
    img[(r > 0.86) & (r < 0.92)] = 1.0
    rgba = np.ones((N, N, 4), 'float32')
    rgba[..., :3] = np.flipud(np.clip(img, 0, 1))[..., None]
    im = bpy.data.images.new('kr_motif', N, N)
    im.pixels.foreach_set(rgba.ravel())
    im.pack()
    return im


class _Kit:
    def __init__(self, coll, R):
        self.coll, self.R = coll, R

    def bend(self, p):
        """Built coordinates (edge -z) -> final frame (edge -y), bent onto the sword's circle for x > 0."""
        q = _ROT @ Vector(p)
        if q.x <= 0 or not self.R:
            return q
        R = self.R
        a = q.x / R
        r = R - q.y                                       # distance from the centre (0, R, 0)
        return Vector((r * math.sin(a), R - r * math.cos(a), q.z))

    def obj(self, name, bm, mats, parent, smooth=False):
        for v in bm.verts:
            v.co = self.bend(v.co)
        bm.normal_update()
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        o = bpy.data.objects.new(name, me)
        for m in (mats if isinstance(mats, (list, tuple)) else [mats]):
            me.materials.append(m)
        for p in me.polygons:
            p.use_smooth = smooth
        self.coll.objects.link(o)
        o.parent = parent
        return o

    def tube(self, name, x0, x1, ry, rz, mat, parent, segs=28, rings=2, smooth=True, taper=1.0, caps=True):
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
        if caps:
            bm.faces.new(rows[0][::-1])
            bm.faces.new(rows[-1])
        return self.obj(name, bm, mat, parent, smooth)

    def helix(self, name, x0, x1, ry, rz, turns, phase, width, mat, parent, lift=0.0016, steps=160):
        bm = bmesh.new()
        left, right = [], []
        for i in range(steps + 1):
            t = i / steps
            x = x0 + (x1 - x0) * t
            a = phase + 2 * math.pi * turns * t
            n = Vector((0, math.cos(a), math.sin(a)))
            p = Vector((x, (ry + lift) * math.cos(a), (rz + lift) * math.sin(a)))
            tang = Vector((x1 - x0, -(ry + lift) * math.sin(a) * 2 * math.pi * turns,
                           (rz + lift) * math.cos(a) * 2 * math.pi * turns)).normalized()
            side = tang.cross(n).normalized() * width / 2
            left.append(bm.verts.new(p - side))
            right.append(bm.verts.new(p + side))
        for i in range(steps):
            bm.faces.new((left[i], left[i + 1], right[i + 1], right[i]))
        return self.obj(name, bm, mat, parent, True)


def build(name, coll, blade_len=0.72, handle=0.27, sori=0.018, motif='seigaiha', with_saya=True,
          cord=(0.006, 0.006, 0.008), sageo=(0.55, 0.05, 0.008), lacquer=(0.012, 0.011, 0.013)):
    """Build the sword (and its scabbard). blade_len: from the guard to the tip, metres (a katana is about
    0.70-0.75; Kojiro's Monohoshizao about 0.91 by tradition). sori: the curve's height over the blade."""
    M = materials(cord, sageo, lacquer)
    L = blade_len
    R = (L * L) / (8 * sori) + sori / 2 if sori > 0 else 0.0     # the circle through the blade's chord
    kit = _Kit(coll, R)
    sword = bpy.data.objects.new(name + '_SWORD', None)
    sword.rotation_mode = 'QUATERNION'
    sword.empty_display_size = 0.05
    coll.objects.link(sword)

    # ---- handle (tsuka): ray skin under black cord crossing in diamonds, lacquer pommel, brass collars
    LT, RY, RZ = handle, 0.0165, 0.0128
    kit.tube('tsuka', -LT, -0.012, RY, RZ, M['same'], sword, segs=28, rings=6)
    turns = LT / 0.052
    for k in range(2):
        kit.helix(f'ito_a{k}', -LT + 0.02, -0.016, RY, RZ, turns, k * math.pi, 0.0105, M['cord'], sword)
        kit.helix(f'ito_b{k}', -LT + 0.02, -0.016, RY, RZ, -turns, k * math.pi + math.pi / 2, 0.0105, M['cord'],
                  sword, lift=0.0021)
    kit.tube('kashira', -LT - 0.028, -LT + 0.004, RY * 1.08, RZ * 1.08, M['lacquer'], sword, segs=28)
    kit.tube('kashira_ring', -LT, -LT + 0.006, RY * 1.12, RZ * 1.12, M['brass'], sword, segs=28)
    kit.tube('fuchi', -0.016, -0.0005, RY * 1.1, RZ * 1.1, M['brass'], sword, segs=28)

    # ---- guard (tsuba): four lobes, our motif on both faces, brass rim
    TR, T = 0.041, 0.006
    bm = bmesh.new()
    n = 72
    outline = []
    for j in range(n):
        a = 2 * math.pi * j / n
        rr = TR * (0.90 + 0.10 * abs(math.cos(2 * a)) ** 0.6) * (1 - 0.06 * (abs(math.sin(2 * a)) ** 8))
        outline.append((rr * math.cos(a), rr * math.sin(a)))
    front = [bm.verts.new((T, y, z)) for y, z in outline]
    back = [bm.verts.new((0.0, y, z)) for y, z in outline]
    bm.faces.new(front)
    bm.faces.new(back[::-1])
    for j in range(n):
        bm.faces.new((back[j], back[(j + 1) % n], front[(j + 1) % n], front[j])).material_index = 1
    uv = bm.loops.layers.uv.new()
    for f in bm.faces:
        for lp in f.loops:
            co = lp.vert.co
            lp[uv].uv = (0.5 + co.y / (2 * TR), 0.5 + co.z / (2 * TR))
    kit.obj('tsuba', bm, [tsuba_material(motif), M['brass']], sword)
    kit.tube('seppa', T, T + 0.003, 0.021, 0.0105, M['brass'], sword, segs=20)

    # ---- the blade: habaki, then the full blade on the curve
    W, TH = 0.031, 0.0072
    X0 = T + 0.035
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((T + 0.019, 0, 0)) @
                          Matrix.Diagonal((0.032, TH * 1.9, W * 1.12, 1)))
    kit.obj('habaki', bm, M['brass'], sword)
    KISS = 0.055                                          # the point's length

    def sect(x, side):
        t = (x - X0) / max(1e-6, L - X0)
        wb = W * (1 - 0.30 * t)                           # the blade narrows toward the point
        mune = W / 2 - (W - wb) * 0.5
        u = max(0.0, (x - (L - KISS)) / KISS)
        edge = mune - wb * math.sqrt(max(0.0, 1 - u * u))  # the kissaki curves the edge up to the back
        ham = edge + (mune - edge) * (0.30 + 0.06 * math.sin(x * 130) + 0.025 * math.sin(x * 330 + 1)) * (1 - u)
        shin = edge + (mune - edge) * 0.72
        th = TH * (1 - 0.35 * t) * (1 - 0.7 * u)
        return [Vector((x, 0.0, edge)), Vector((x, side * th * 0.38, max(edge, ham))),
                Vector((x, side * th * 0.50, max(edge, shin))), Vector((x, side * th * 0.30, mune))]
    steps = 90
    bm = bmesh.new()
    rows = []
    for i in range(steps + 1):
        x = X0 + (L - X0) * i / steps
        rows.append(([bm.verts.new(p) for p in sect(x, -1)], [bm.verts.new(p) for p in sect(x, 1)]))
    for (am, ap), (bm_, bp) in zip(rows, rows[1:]):
        for k, mi in zip(range(3), (1, 0, 0)):
            f = bm.faces.new((ap[k], bp[k], bp[k + 1], ap[k + 1]))
            f.material_index = mi
            f = bm.faces.new((am[k + 1], bm_[k + 1], bm_[k], am[k]))
            f.material_index = mi
        bm.faces.new((am[3], bm_[3], bp[3], ap[3]))       # the back (mune)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    kit.obj('blade', bm, [M['steel'], M['hamon']], sword, smooth=False)

    out = {'sword': sword, 'saya': None, 'R': R, 'L': L, 'name': name}
    if not with_saya:
        return out
    # ---- the scabbard on the same curve: horn mouth, lacquer body, cord knob + sageo wrap, horn end cap
    saya = bpy.data.objects.new(name + '_SAYA', None)
    saya.rotation_mode = 'QUATERNION'
    saya.empty_display_size = 0.05
    coll.objects.link(saya)
    SY, SZ = 0.0125, 0.0215                               # holds the blade (W/2 + wall, TH/2 + wall)
    LS = L + 0.035
    kit.tube('koiguchi', 0.0, 0.022, SY * 1.06, SZ * 1.04, M['horn'], saya, segs=28, rings=1)
    kit.tube('saya', 0.022, LS - 0.03, SY, SZ, M['lacquer'], saya, segs=28, rings=40, taper=0.88, caps=False)
    kit.tube('kojiri', LS - 0.03, LS, SY * 0.9, SZ * 0.9, M['horn'], saya, segs=28, rings=2, taper=0.8)
    xk = 0.09
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((xk, 0.0, -SZ - 0.004)) @
                          Matrix.Diagonal((0.024, 0.010, 0.009, 1)))
    kit.obj('kurikata', bm, M['lacquer'], saya)
    for k in range(3):
        kit.helix(f'sageo{k}', xk + 0.02 + k * 0.016, xk + 0.034 + k * 0.016, SY, SZ, 1.0, k * 0.7, 0.007,
                  M['sageo'], saya, lift=0.0022, steps=40)
    out['saya'] = saya
    return out
