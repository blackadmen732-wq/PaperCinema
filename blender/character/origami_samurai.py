"""ORIGAMI SAMURAI: the hero character as folded washi paper lit from inside (owner's reference images).

  B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
  nice -n 10 $B -b -t 2 -P blender/character/origami_samurai.py -- --pose wide-stance --out output/character/wide.png
  ... -- --pose hasso --world output/world/ganryujima.blend --cam CAM_medium --out output/character/in-world.png
  ... -- --turnaround output/character/turn.png        (front / three-quarter / side / back)

Look (from the references):
  * every part is a folded shell: fluted pleats, crisp facets, a thin seam between panels
  * the inner lantern glows through the seams, the sleeve openings and the eye slits (amber = human, crimson = demonic)
  * pleated kasa hat with ribs and a rim, kite-folded face mask, crossed kimono lapels, rope obi with two tassels,
    wide hanging sleeves, lamellar shoulder plates (sode), very wide pleated hakama, pointed folded feet, folded fingers

Rig: the SAME joints as engine/figure.js (three.js), so library/poses.json drives it directly:
  root → hips → waist → chest → neck → head ; chest → clavicle → shoulder → elbow → twist → hand ; root → thigh → shin → foot
  three.js (x, y, z) with the figure facing +z  →  Blender (x, -z, y) facing -Y. Euler (rx, ry, rz) → (rx, -rz, ry), mode 'YZX'.
"""
import json
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'world'))
import paper_materials as pm  # noqa: E402

ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(n, d=None):
    return ARGV[ARGV.index('--' + n) + 1] if '--' + n in ARGV else d
def flag(n):
    return '--' + n in ARGV

REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
SEED = int(arg('seed', 3))
DEMON = flag('demon')
GLOW = (1.0, 0.13, 0.06) if DEMON else (1.0, 0.55, 0.18)
PAPER = (0.80, 0.76, 0.67)
rnd = random.Random(SEED)

# ---------------------------------------------------------------------------- scene
if arg('world'):
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(arg('world')))
    for c in bpy.data.collections:
        if 'stand' in c.name.lower():
            for o in list(c.objects):
                o.hide_render = True
                o.hide_viewport = True
else:
    bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
coll = bpy.data.collections.new('ORIGAMI_SAMURAI')
scene.collection.children.link(coll)

def T(x, y, z):
    """three.js coordinates → Blender."""
    return Vector((x, -z, y))

# ---------------------------------------------------------------------------- materials
M_PAPER = pm.paper_material('OS_Paper', PAPER, translucency=0.3, rough=0.8, fibre_scale=140, fibre_strength=0.18, facet_var=0.07)
M_PAPER_DARK = pm.paper_material('OS_PaperShade', tuple(c * 0.86 for c in PAPER), translucency=0.25, fibre_scale=140, facet_var=0.06)
M_SEAM = pm.emission_material('OS_SeamGlow', GLOW, 5.0)
M_EYES = pm.emission_material('OS_Eyes', GLOW, 22.0)
M_INNER = pm.emission_material('OS_InnerGlow', GLOW, 4.0)

def obj(name, bm, mats, parent=None):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    for m in mats:
        me.materials.append(m)
    coll.objects.link(ob)
    pm.add_facet_attribute(ob, seed=rnd.randint(0, 999))
    for p in me.polygons:
        p.use_smooth = False
    if parent:
        ob.parent = parent
        ob.matrix_parent_inverse = parent.matrix_world.inverted()
    return ob

def seams(bm, thickness=0.0035, depth=-0.0025, share=1.0):
    """Cut a thin glowing groove around every facet (material index 1 = seam glow)."""
    faces = [f for f in bm.faces if rnd.random() < share]
    res = bmesh.ops.inset_individual(bm, faces=faces, thickness=thickness, depth=depth, use_even_offset=True)
    inner = set(faces)
    for f in bm.faces:
        if f not in inner:
            f.material_index = 1

def fluted_frustum(r0, r1, z0, z1, n=12, flute=0.18, sx=1.0, sy=1.0, open_ends=True, hem_tilt=0.0, center=(0, 0)):
    """Pleated tube (hakama leg, kimono body, kasa): alternating in/out vertices = folded pleats."""
    bm = bmesh.new()
    rings = []
    for z, r in ((z0, r0), (z1, r1)):
        ring = []
        for i in range(2 * n):
            a = math.pi * i / n
            rr = r * (1 - flute if i % 2 else 1)
            zz = z + (hem_tilt * math.cos(a) if z == z0 else 0)
            ring.append(bm.verts.new((center[0] + rr * math.cos(a) * sx, center[1] + rr * math.sin(a) * sy, zz)))
        rings.append(ring)
    m = 2 * n
    for i in range(m):
        bm.faces.new((rings[0][i], rings[0][(i + 1) % m], rings[1][(i + 1) % m], rings[1][i]))
    if not open_ends:
        bm.faces.new(rings[0][::-1])
        bm.faces.new(rings[1])
    return bm

def box(cx, cy, cz, sx, sy, sz, rot=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(rot[0], 3, 'X') @ Matrix.Rotation(rot[1], 3, 'Y') @ Matrix.Rotation(rot[2], 3, 'Z'))
    bmesh.ops.translate(bm, vec=(cx, cy, cz), verts=bm.verts)
    return bm

def solidify(ob, t=0.006):
    mod = ob.modifiers.new('fold', 'SOLIDIFY')
    mod.thickness = t
    mod.offset = 0
    mod.material_offset_rim = 1      # the paper edge glows faintly (light leaking through the sheet edge)
    return ob

# ---------------------------------------------------------------------------- rig (empties = joints)
def joint(name, parent, pos_three_local):
    e = bpy.data.objects.new('J_' + name, None)
    e.empty_display_size = 0.05
    e.rotation_mode = 'YZX'
    coll.objects.link(e)
    if parent:
        e.parent = parent
    e.location = T(*pos_three_local)
    return e

J = {}
J['root'] = joint('root', None, (0, 0, 0))
J['hips'] = joint('hips', J['root'], (0, 0.92, 0))
J['torso'] = joint('torso', J['hips'], (0, 0, 0))
J['upper'] = joint('upper', J['torso'], (0, 0.26, 0))
J['neck'] = joint('neck', J['upper'], (0, 0.29, 0))
J['head'] = joint('head', J['neck'], (0, 0.06, 0))
J['hakama'] = joint('hakama', J['hips'], (0, 0, 0))
for s, sgn in (('r', -1), ('l', 1)):
    J[s + 'C'] = joint(s + 'C', J['upper'], (sgn * 0.07, 0.21, 0))
    J[s + 'S'] = joint(s + 'S', J[s + 'C'], (sgn * 0.16, 0, 0))
    J[s + 'E'] = joint(s + 'E', J[s + 'S'], (0, -0.30, 0))
    J[s + 'T'] = joint(s + 'T', J[s + 'E'], (0, 0, 0))
    J[s + 'H'] = joint(s + 'H', J[s + 'T'], (0, -0.29, 0))
    J[s + 'thigh'] = joint(s + 'thigh', J['root'], (sgn * 0.1, 0.92, 0))
    J[s + 'shin'] = joint(s + 'shin', J[s + 'thigh'], (0, -0.46, 0))
    J[s + 'foot'] = joint(s + 'foot', J[s + 'shin'], (0, -0.44, 0))
bpy.context.view_layer.update()

def W(name):
    """World position of a joint at rest."""
    return J[name].matrix_world.translation.copy()

# ---------------------------------------------------------------------------- body parts (built at rest, in world space)
hz = W('hips').z
# kimono body: pleated waist + broader chest, flattened front-to-back, glowing seams
bm = fluted_frustum(0.17, 0.19, hz - 0.02, hz + 0.30, n=9, flute=0.08, sy=0.72)
seams(bm, share=0.5)
obj('kimono_waist', bm, [M_PAPER, M_SEAM], J['torso'])
cz = W('upper').z
bm = fluted_frustum(0.19, 0.25, cz - 0.04, cz + 0.27, n=9, flute=0.07, sy=0.66)
seams(bm, share=0.45)
obj('kimono_chest', bm, [M_PAPER, M_SEAM], J['upper'])
# crossed lapels (eri): left over right, folded strips that meet in a V at the obi
for sgn, dz in ((1, 0.0), (-1, 0.004)):
    bm = box(sgn * 0.055, -0.155 - dz, cz + 0.12, 0.075, 0.012, 0.42, rot=(0.08, sgn * 0.36, 0))
    solid = obj(f'lapel_{sgn}', bm, [M_PAPER_DARK, M_SEAM], J['upper'])
# inner glow core in the chest (seen through the collar gap) + the light itself
bm = box(0, -0.12, cz + 0.16, 0.05, 0.01, 0.16)
obj('collar_glow', bm, [M_INNER], J['upper'])
for nm, j, off, pw in (('chest', 'upper', (0, 0, 0.14), 4.0), ('belly', 'torso', (0, 0, 0.12), 0.4), ('head', 'head', (0, 0, 0.1), 0.6)):
    L = bpy.data.lights.new('OS_lamp_' + nm, 'POINT')
    L.color = GLOW
    L.energy = pw
    L.shadow_soft_size = 0.03
    lo = bpy.data.objects.new('OS_lamp_' + nm, L)
    coll.objects.link(lo)
    lo.parent = J[j]
    lo.location = Vector(off)

# obi + rope belt + tassels
bm = fluted_frustum(0.195, 0.195, hz + 0.0, hz + 0.1, n=10, flute=0.02, sy=0.74)
obj('obi', bm, [M_PAPER_DARK, M_SEAM], J['torso'])
rope = bpy.data.curves.new('rope', 'CURVE')
rope.dimensions = '3D'
rope.bevel_depth = 0.011
rope.bevel_resolution = 1
sp = rope.splines.new('POLY')
N = 40
sp.points.add(N)
for i in range(N + 1):
    a = 2 * math.pi * i / N
    sp.points[i].co = (0.205 * math.cos(a), 0.205 * 0.75 * math.sin(a), hz + 0.055 + 0.03 * math.sin(a * 1.0 + 1.2), 1)
ro = bpy.data.objects.new('rope_obi', rope)
ro.data.materials.append(M_PAPER)
coll.objects.link(ro)
ro.parent = J['torso']
ro.matrix_parent_inverse = J['torso'].matrix_world.inverted()
for k, x in enumerate((0.03, 0.075)):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=8, radius1=0.022, radius2=0.006, depth=0.12)
    bmesh.ops.translate(bm, vec=(x, -0.16, hz - 0.05 - k * 0.02), verts=bm.verts)
    obj(f'tassel_{k}', bm, [M_PAPER, M_SEAM], J['torso'])
    bm = box(x, -0.16, hz + 0.02 - k * 0.02, 0.006, 0.006, 0.08)
    obj(f'tassel_cord_{k}', bm, [M_PAPER], J['torso'])

# hakama: very wide pleated trouser legs, tilted hem, plus the front pleated apron
for s, sgn in (('r', -1), ('l', 1)):
    t0, t1 = W(s + 'thigh'), W(s + 'shin')
    bm = fluted_frustum(0.16, 0.21, t1.z - 0.02, t0.z + 0.04, n=8, flute=0.16, center=(t0.x, 0))
    seams(bm, share=0.12)
    obj(f'hakama_thigh_{s}', bm, [M_PAPER, M_SEAM], J[s + 'thigh'])
    f0 = W(s + 'foot')
    bm = fluted_frustum(0.27, 0.21, f0.z + 0.05, t1.z + 0.03, n=8, flute=0.2, center=(t0.x, 0), hem_tilt=0.04)
    seams(bm, share=0.12)
    obj(f'hakama_shin_{s}', bm, [M_PAPER, M_SEAM], J[s + 'shin'])
    # folded pointed foot (tabi as a paper wedge)
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in ((f0.x - 0.05, 0.05, 0.0), (f0.x + 0.05, 0.05, 0.0), (f0.x, -0.2, 0.0), (f0.x, 0.02, 0.09))]
    for f in ((0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3)):
        bm.faces.new([vs[i] for i in f])
    obj(f'foot_{s}', bm, [M_PAPER, M_SEAM], J[s + 'foot'])
bm = fluted_frustum(0.16, 0.24, hz - 0.36, hz + 0.02, n=6, flute=0.25, sy=0.45, center=(0, -0.08))
obj('hakama_apron', bm, [M_PAPER_DARK, M_SEAM], J['hakama'])

# arms: upper sleeve, huge hanging kimono sleeve (open, glowing inside), forearm, folded hand
for s, sgn in (('r', -1), ('l', 1)):
    S, E, H = W(s + 'S'), W(s + 'E'), W(s + 'H')
    bm = fluted_frustum(0.07, 0.095, E.z, S.z + 0.03, n=5, flute=0.1, center=(S.x, 0))
    obj(f'upper_{s}', bm, [M_PAPER, M_SEAM], J[s + 'S'])
    # tamoto: the wide sleeve, an open folded bag hanging under the forearm
    bm = bmesh.new()
    x = E.x
    pts = [(x - 0.05, -0.08, E.z + 0.0), (x + 0.05, -0.08, E.z + 0.0), (x + 0.055, -0.14, E.z - 0.3), (x - 0.055, -0.15, E.z - 0.32),
           (x - 0.05, 0.08, E.z + 0.0), (x + 0.05, 0.08, E.z + 0.0), (x + 0.055, 0.11, E.z - 0.27), (x - 0.055, 0.1, E.z - 0.29)]
    v = [bm.verts.new(p) for p in pts]
    for f in ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (3, 2, 6, 7), (0, 3, 7, 4)):
        bm.faces.new([v[i] for i in f])
    so = obj(f'sleeve_{s}', bm, [M_PAPER, M_SEAM], J[s + 'T'])
    bm = box(x, -0.0, E.z - 0.27, 0.09, 0.18, 0.02)
    obj(f'sleeve_glow_{s}', bm, [M_INNER], J[s + 'T'])
    bm = fluted_frustum(0.05, 0.075, H.z + 0.02, E.z, n=4, flute=0.05, center=(E.x, 0))
    obj(f'fore_{s}', bm, [M_PAPER, M_SEAM], J[s + 'T'])
    # folded fingers: four thin paper blades fanning down from the palm
    bm = box(H.x, 0, H.z - 0.03, 0.05, 0.06, 0.07)
    for k in range(4):
        b2 = bmesh.new()
        fv = [b2.verts.new(p) for p in ((H.x - 0.01, -0.02 + k * 0.014, H.z - 0.06), (H.x + 0.01, -0.02 + k * 0.014, H.z - 0.06),
                                        (H.x + sgn * 0.01, -0.03 + k * 0.016, H.z - 0.15 + 0.01 * abs(k - 1.5)))]
        b2.faces.new(fv)
        tmp = bpy.data.meshes.new('t')
        b2.to_mesh(tmp)
        b2.free()
        bm.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
    obj(f'hand_{s}', bm, [M_PAPER, M_SEAM], J[s + 'H'])

# sode: lamellar shoulder plates on the left shoulder (rows of small folded scales)
S = W('lS')
for row in range(4):
    for k in range(5):
        bm = box(S.x + 0.01 + row * 0.004, -0.09 + k * 0.045, S.z + 0.02 - row * 0.05, 0.02, 0.046, 0.05, rot=(0, 0.25 + row * 0.05, 0))
        obj(f'sode_{row}_{k}', bm, [M_PAPER_DARK, M_SEAM], J['lS'])

# head: neck prism, kite-folded face mask with glowing seams, eye slits, spiky folded hair at the back
N0, H0 = W('neck'), W('head')
bm = fluted_frustum(0.045, 0.055, N0.z - 0.02, H0.z + 0.03, n=3, flute=0.0)
obj('neck', bm, [M_PAPER, M_SEAM], J['neck'])
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.11)
for v in bm.verts:
    x, y, z = v.co
    # a long, pointed mask: narrow chin, ridge down the nose, flat cheeks
    v.co = Vector((x * 0.78, y * 0.95 - (0.03 if y < -0.05 and abs(x) < 0.03 else 0), z * 1.25 - (0.02 if z < -0.06 else 0)))
bmesh.ops.translate(bm, vec=(0, 0, H0.z + 0.11), verts=bm.verts)
seams(bm, thickness=0.004, depth=-0.004, share=0.9)
obj('face_mask', bm, [M_PAPER, M_SEAM], J['head'])
for sgn in (1, -1):
    bm = box(sgn * 0.035, -0.096, H0.z + 0.125, 0.04, 0.008, 0.008, rot=(0, sgn * 0.25, sgn * -0.18))
    obj(f'eye_{sgn}', bm, [M_EYES], J['head'])
for k in range(5):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=3, radius1=0.03, radius2=0.0, depth=0.16)
    a = (k - 2) * 0.35
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(-1.9, 3, 'X') @ Matrix.Rotation(a, 3, 'Y'))
    bmesh.ops.translate(bm, vec=(math.sin(a) * 0.06, 0.09, H0.z + 0.16 - abs(k - 2) * 0.02), verts=bm.verts)
    obj(f'hair_{k}', bm, [M_PAPER_DARK, M_SEAM], J['head'])

# kasa: pleated conical straw hat with ribs and a rolled rim
bm = bmesh.new()
n = 28
apex = bm.verts.new((0, 0, H0.z + 0.36))
rim = []
for i in range(2 * n):
    a = math.pi * i / n
    r = 0.42 * (0.97 if i % 2 else 1.0)
    rim.append(bm.verts.new((r * math.cos(a), r * math.sin(a), H0.z + 0.20 + (0.012 if i % 2 else 0))))
for i in range(2 * n):
    bm.faces.new((apex, rim[i], rim[(i + 1) % (2 * n)]))
kasa = obj('kasa', bm, [M_PAPER, M_SEAM], J['head'])
solidify(kasa, 0.006)
rimc = bpy.data.curves.new('kasa_rim', 'CURVE')
rimc.dimensions = '3D'
rimc.bevel_depth = 0.008
sp = rimc.splines.new('POLY')
sp.points.add(63)
for i in range(64):
    a = 2 * math.pi * i / 63
    sp.points[i].co = (0.42 * math.cos(a), 0.42 * math.sin(a), H0.z + 0.2, 1)
rimo = bpy.data.objects.new('kasa_rim', rimc)
rimo.data.materials.append(M_PAPER)
coll.objects.link(rimo)
rimo.parent = J['head']
rimo.matrix_parent_inverse = J['head'].matrix_world.inverted()

# katana at the left hip: paper saya (scabbard) and tsuka (handle) in one line, mouth at the obi, tip low behind
mouth = Vector((0.2, -0.12, hz + 0.06))
tilt = Matrix.Rotation(math.radians(-22), 3, 'X') @ Matrix.Rotation(math.radians(10), 3, 'Z')
for nm, y0, y1, w, mat in (('saya', 0.0, 0.92, 0.034, M_PAPER_DARK), ('tsuka', -0.3, 0.0, 0.04, M_PAPER)):
    bm = box(0, (y0 + y1) / 2, 0, w, y1 - y0, w)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=tilt)
    bmesh.ops.translate(bm, vec=mouth, verts=bm.verts)
    obj(nm, bm, [mat, M_SEAM], J['torso'])
bm = box(0, 0, 0, 0.09, 0.012, 0.09)        # tsuba
bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=tilt)
bmesh.ops.translate(bm, vec=mouth, verts=bm.verts)
obj('tsuba', bm, [M_PAPER_DARK, M_SEAM], J['torso'])

# ---------------------------------------------------------------------------- poses (port of engine/figure.js applyPose)
POSES = json.load(open(os.path.join(REPO, 'library', 'poses.json')))
POSES['wide-stance'] = {   # second reference: deep side stance, lead arm reaching forward, rear arm back
    'stance': 0.75, 'crouch': 0.26, 'weight': 0.2, 'tx': 0.12, 'ty': 0.35, 'cy': 0.15, 'hy': -0.3, 'hx': -0.05,
    'lsx': -1.25, 'lsz': 0.25, 'lex': -0.25, 'lwx': 0.3, 'rsx': 0.35, 'rsz': 0.55, 'rex': -0.35, 'rcz': 0.05}
POSES['standing'] = {'tx': 0.06, 'hx': 0.22, 'nx': 0.1, 'rsx': -0.55, 'rsz': 0.35, 'rex': -1.4, 'lsx': -0.5, 'lsz': -0.4, 'lex': -1.45, 'stance': 0.18}
BASE = dict(x=0, y=0, z=0, ry=0, rx=0, rz=0, tx=0, ty=0, tz=0, hx=0, hy=0, hz=0, rsx=0.05, rsz=0.12, rex=-0.15, lsx=0.05,
            lsz=-0.12, lex=-0.15, rwx=0, lwx=0, rwz=0, lwz=0, sway=0, swayx=0, stance=0.12, crouch=0, weight=0,
            cx=0, cy=0, cz=0, nx=0, ny=0, rcy=0, rcz=0, lcy=0, lcz=0, rsy=0, lsy=0, rfy=0, lfy=0, rax=0, lax=0)

def rot(j, rx, ry, rz):
    J[j].rotation_euler = (rx, -rz, ry)

def apply_pose(p):
    J['root'].location = T(p['x'], p['y'], p['z'])
    rot('root', p['rx'], p['ry'], p['rz'])
    hipY = 0.92 - p['crouch']
    hipZ = p['weight'] * p['stance'] * 0.35
    J['hips'].location = T(0, hipY, hipZ)
    rot('torso', p['tx'] + p['weight'] * 0.05, p['ty'], p['tz'])
    rot('upper', p['cx'], p['cy'], p['cz'])
    rot('neck', p['nx'], p['ny'], 0)
    rot('head', p['hx'], p['hy'], p['hz'])
    rot('rC', 0, p['rcy'], -p['rcz']); rot('lC', 0, -p['lcy'], p['lcz'])
    rot('rS', p['rsx'], p['rsy'], p['rsz']); rot('lS', p['lsx'], p['lsy'], p['lsz'])
    rot('rE', p['rex'], 0, 0); rot('lE', p['lex'], 0, 0)
    rot('rT', 0, p['rfy'], 0); rot('lT', 0, p['lfy'], 0)
    rot('rH', p['rwx'], 0, p['rwz']); rot('lH', p['lwx'], 0, p['lwz'])
    rot('hakama', p['swayx'], 0, p['sway'])
    # legs: analytic two-bone IK in the side plane (same maths as solveLegs)
    L1, L2 = 0.46, 0.44
    hy, hzz = hipY - 0.02, hipZ
    for s, side in (('r', -1), ('l', 1)):
        front = side < 0
        fz, fy = (1 if front else -1) * p['stance'] / 2, 0.04
        dz, dy = fz - hzz, fy - hy
        d = math.hypot(dz, dy)
        mx = (L1 + L2) * 0.999
        if d > mx:
            dz *= mx / d; dy *= mx / d; d = mx
        phi = math.atan2(dz, -dy)
        a = math.acos(max(-1, min(1, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d))))
        th = phi + a
        kz, ky = hzz + L1 * math.sin(th), hy - L1 * math.cos(th)
        sh = math.atan2(hzz + dz - kz, -(hy + dy - ky))
        J[s + 'thigh'].location = T(side * 0.1, hy, hzz)
        rot(s + 'thigh', -th, 0, side * 0.04)
        rot(s + 'shin', -(sh - th), 0, 0)
        rot(s + 'foot', sh + (p['rax'] if front else p['lax']), 0, 0)

pose_name = arg('pose', 'standing')
pose = dict(BASE)
pose.update(POSES.get(pose_name, {}))
pose['ry'] = float(arg('ry', 0))
if arg('world'):
    mk = bpy.data.objects.get('MARK_hero')
    if mk:
        J['root'].location = mk.matrix_world.translation
apply_pose(pose)
if arg('world') and bpy.data.objects.get('MARK_hero'):
    J['root'].location = bpy.data.objects['MARK_hero'].matrix_world.translation
bpy.context.view_layer.update()

# ---------------------------------------------------------------------------- studio (when not in the world)
def studio():
    w = bpy.data.worlds.new('OS_World')
    scene.world = w
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs[0].default_value = (0.62, 0.64, 0.67, 1)
    w.node_tree.nodes['Background'].inputs[1].default_value = 0.12
    bm = bmesh.new()   # cyclorama: floor curving up into a wall
    prof = [(0, -4 + i * 0.3, 0) for i in range(20)] + [(0, 2 + 1.2 * math.sin(a / 10 * math.pi / 2), 1.2 - 1.2 * math.cos(a / 10 * math.pi / 2)) for a in range(1, 11)] + [(0, 3.2, 1.2 + i * 0.5) for i in range(1, 8)]
    left = [bm.verts.new((-5, y, z)) for _, y, z in prof]
    right = [bm.verts.new((5, y, z)) for _, y, z in prof]
    for i in range(len(prof) - 1):
        bm.faces.new((left[i], right[i], right[i + 1], left[i + 1]))
    cyc = obj('cyclorama', bm, [pm.paper_material('OS_Backdrop', (0.55, 0.57, 0.6), translucency=0, fibre_scale=10, facet_var=0)])
    for p in cyc.data.polygons:
        p.use_smooth = True
    key = bpy.data.lights.new('key', 'AREA'); key.energy = float(arg('key', 90)); key.size = 0.7; key.color = (1, 0.97, 0.92)
    k = bpy.data.objects.new('key', key); coll.objects.link(k); k.location = (-1.6, -2.0, 2.6)
    k.rotation_euler = (Vector((0, 0, 1.1)) - k.location).to_track_quat('-Z', 'Y').to_euler()
    rim = bpy.data.lights.new('rim', 'AREA'); rim.energy = float(arg('rimlight', 35)); rim.size = 0.8; rim.color = (0.85, 0.9, 1.0)
    r = bpy.data.objects.new('rim', rim); coll.objects.link(r); r.location = (1.4, 1.8, 2.2)
    r.rotation_euler = (Vector((0, 0, 1.2)) - r.location).to_track_quat('-Z', 'Y').to_euler()

def add_camera(pos, look, lens=60):
    cd = bpy.data.cameras.new('OS_cam'); cd.lens = lens
    cd.dof.use_dof = True; cd.dof.aperture_fstop = 2.8
    c = bpy.data.objects.new('OS_cam', cd); coll.objects.link(c)
    c.location = pos
    c.rotation_euler = (Vector(look) - Vector(pos)).to_track_quat('-Z', 'Y').to_euler()
    cd.dof.focus_distance = (Vector(look) - Vector(pos)).length
    scene.camera = c
    return c

if not arg('world'):
    studio()
cy_ = scene.render
scene.render.engine = 'CYCLES'
scene.cycles.samples = int(arg('samples', 32))
scene.cycles.use_denoising = True
scene.cycles.device = 'CPU'
res = arg('res', '540x960').split('x')
scene.render.resolution_x, scene.render.resolution_y = int(res[0]), int(res[1])
scene.render.resolution_percentage = 100
try:
    scene.view_settings.view_transform = 'AgX'
except Exception:
    pass
scene.view_settings.exposure = float(arg('exposure', -0.6))

def render(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    scene.render.filepath = os.path.abspath(path)
    bpy.ops.render.render(write_still=True)
    print('wrote', path)

center = J['root'].matrix_world.translation + Vector((0, 0, 1.05))
if flag('turnaround') or arg('turnaround'):
    out = arg('turnaround')
    views = [('front', 0), ('three-quarter', 40), ('side', 90), ('back', 180)]
    files = []
    for nm, deg in views:
        a = math.radians(deg)
        p = center + Vector((-math.sin(a) * 3.4, -math.cos(a) * 3.4, -0.15))
        add_camera(p, center, 55)
        f = out.replace('.png', f'-{nm}.png'); render(f); files.append(f)
    print('turnaround', files)
else:
    if arg('cam') and bpy.data.objects.get(arg('cam')):
        scene.camera = bpy.data.objects[arg('cam')]
    else:
        a = math.radians(float(arg('angle', 28)))
        dist = float(arg('dist', 4.4))
        add_camera(center + Vector((-math.sin(a) * dist, -math.cos(a) * dist, float(arg('elev', -0.35)))), center + Vector((0, 0, 0.1)), float(arg('lens', 55)))
    render(arg('out', 'output/character/origami.png'))
if arg('save'):
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(arg('save')))
