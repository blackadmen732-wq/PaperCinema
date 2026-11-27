"""GANRYUJIMA world set: a reusable Lantern Origami island we build once and film inside.

Run (headless, deterministic for a given --seed):
  blender -b -P blender/world/build_world.py -- --out output/world/ganryujima.blend
  blender -b -P blender/world/build_world.py -- --out output/world/ganryujima.blend --preview output/world/preview.png
Options:
  --seed 1             layout seed (rocks, pines, ridges, clouds); same seed = same set
  --cams CAM_wide,...  anchors to render a preview from (one PNG each: preview.png, preview-CAM_x.png ...)
  --res 540x960        preview size (vertical by default)        --samples 24   Cycles samples (denoised)
  --sun-elev 4 --sun-az -7    dawn sun: elevation and azimuth in degrees (0 = +Y, positive toward +X)
  --fog                add a thin ground-fog volume (slower, see docs/BLENDER-WORLD.md)
  --no-standins        leave out the two faceted samurai stand-ins
  --frame 1            frame to render (the sea is animated over frames 1..240)

Layout (metres, Z up, sea level z = 0): the island is centred near the origin with its long axis on X; the
duel beach faces -Y (toward the default camera); mountains ring the strait from 160 m to 2 km; the sun rises
over an open-sea gap at --sun-az. Films use the empties in the MARKS and CAMERAS collections.
"""
import math
import os
import random
import sys
import time
import zlib

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.dont_write_bytecode = True      # keep blender/world free of __pycache__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paper_materials as pm  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(name, default=None):
    return argv[argv.index('--' + name) + 1] if '--' + name in argv else default


def flag(name):
    return '--' + name in argv


OUT = arg('out', 'output/world/ganryujima.blend')
PREVIEW = arg('preview')
SEED = int(arg('seed', 1))
CAMS = arg('cams', 'CAM_wide').split(',')
RES = [int(v) for v in arg('res', '540x960').split('x')]
SAMPLES = int(arg('samples', 24))
SUN_ELEV = float(arg('sun-elev', 4.0))
SUN_AZ = float(arg('sun-az', -7.0))
FOG = flag('fog')
STANDINS = not flag('no-standins')
FRAME = int(arg('frame', 1))

ISLAND_C = Vector((0.0, 6.0))       # island centre (x, y)
ISLAND_AX = (34.0, 15.0)            # semi-axes (m)
ISLAND_TOP = 1.5                    # plateau height (m)


def rng(section):
    """One seeded stream per section, so editing one part never reshuffles the others."""
    return random.Random(f'{SEED}:{section}')


# =========================================================================== scene + collections
scene = None
COLL = {}


def init_scene():
    """Fresh scene with the named collections (the CLI). blender/sets/kit.py imports this module instead and
    points `scene` / `COLL` at its own set (kit piece `ganryujima`)."""
    global scene
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = 'Ganryujima'
    for name in ('SKY', 'SEA', 'ISLAND', 'ROCKS', 'PINES', 'MOUNTAINS', 'CLOUDS', 'FOG', 'MARKS', 'CAMERAS', 'STANDINS'):
        c = bpy.data.collections.new(name)
        scene.collection.children.link(c)
        COLL[name] = c


def link(ob, coll):
    COLL[coll].objects.link(ob)
    return ob


def obj_from_bm(name, bm, material, coll, facet_seed=0):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    me.materials.append(material)
    pm.shade_flat(ob)
    pm.add_facet_attribute(ob, facet_seed)
    return link(ob, coll)


def jitter(bm, r, amt, z_amt=None):
    z_amt = amt if z_amt is None else z_amt
    for v in bm.verts:
        v.co += Vector((r.uniform(-amt, amt), r.uniform(-amt, amt), r.uniform(-z_amt, z_amt)))


def set_linear(ob):
    """Linear keys + linear extrapolation (works with 4.4+ slotted actions and older flat ones)."""
    act = ob.animation_data.action if ob.animation_data else None
    if act is None:
        return
    try:
        fcs = list(act.fcurves)
    except AttributeError:
        fcs = [fc for layer in act.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]
    for fc in fcs:
        for k in fc.keyframe_points:
            k.interpolation = 'LINEAR'
        fc.extrapolation = 'LINEAR'


def look_rot(src, dst):
    return (Vector(dst) - Vector(src)).to_track_quat('-Z', 'Y').to_euler()


# =========================================================================== sky + sun
def sun_dir():
    el, az = math.radians(SUN_ELEV), math.radians(SUN_AZ)
    return Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))


pm.SKY.update(sun_elevation=math.radians(SUN_ELEV), sun_rotation=math.radians(SUN_AZ),
              air_density=1.0, dust_density=1.3, ozone_density=1.0)
HAZE_SKY = (None, 0, 1.0)            # haze tuple template: sky colour, distance filled per object


def build_sky():
    world = bpy.data.worlds.new('LO_DawnSky')
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    T = pm._NT(nt)
    sk = pm.sky_node(T)
    bg = nt.nodes['Background']
    bg.inputs['Strength'].default_value = 1.0
    nt.links.new(sk.outputs['Color'], bg.inputs['Color'])

    sun = bpy.data.lights.new('SUN_dawn', 'SUN')
    sun.energy = 3.2
    sun.angle = math.radians(1.2)
    sun.color = (1.0, 0.62, 0.38)
    so = link(bpy.data.objects.new('SUN_dawn', sun), 'SKY')
    so.rotation_euler = (-sun_dir()).to_track_quat('-Z', 'Y').to_euler()

    # the visible sun: a backlit cut-paper disc far away on the sun direction (sky disc is off)
    d = 3200.0
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, segments=14, radius=d * math.radians(2.2))
    disc_mat = pm.paper_material('LO_PaperSun', (1.0, 0.55, 0.25), translucency=0.0, facet_var=0.04,
                                 fibre_scale=0.05, glow=((1.0, 0.45, 0.15), 160.0))
    ob = obj_from_bm('SKY_paper_sun', bm, disc_mat, 'SKY', 3)
    ob.location = sun_dir() * d
    ob.rotation_euler = (-sun_dir()).to_track_quat('Z', 'Y').to_euler()
    ob.visible_shadow = False
    ob.visible_diffuse = False


# =========================================================================== sea (Ocean modifier)
def build_sea():
    sea_mat = pm.sea_material('LO_SeaPaper', haze=(None, 1400.0, 1.0))
    me = bpy.data.meshes.new('SEA_ocean')
    ob = link(bpy.data.objects.new('SEA_ocean', me), 'SEA')
    me.materials.append(sea_mat)
    m = ob.modifiers.new('Ocean', 'OCEAN')
    m.geometry_mode = 'GENERATE'
    m.spectrum = 'PIERSON_MOSKOWITZ'
    m.resolution = 6                 # 36 cells per tile -> ~1.1 m facets: visible folded planes
    m.viewport_resolution = 4
    m.spatial_size = 40
    m.repeat_x = 8
    m.repeat_y = 8
    m.wind_velocity = 5.0
    m.wave_scale = 0.55
    m.wave_scale_min = 0.05
    m.choppiness = 1.1
    m.wave_alignment = 0.4
    m.wave_direction = math.radians(70)
    m.random_seed = SEED
    m.use_normals = False
    m.use_foam = True
    m.foam_layer_name = 'foam'
    m.foam_coverage = 0.35
    m.time = 1.0
    # animate the waves: time in seconds, 24 fps, frames 1..240
    m.keyframe_insert('time', frame=1)
    m.time = 1.0 + 239 / 24
    m.keyframe_insert('time', frame=240)
    set_linear(ob)
    m.time = 1.0
    pm.facet_random_modifier(ob, SEED)
    # centre the tiled grid on the island (generated tiles start at the object origin)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    bb = [ev.matrix_world @ Vector(c) for c in ev.bound_box]
    cx = (min(v.x for v in bb) + max(v.x for v in bb)) / 2
    cy = (min(v.y for v in bb) + max(v.y for v in bb)) / 2
    ob.location = (-cx, -cy + 40.0, 0.0)

    # far sea to the horizon: a large faceted sheet just under the ocean tiles
    r = rng('farsea')
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=70, y_segments=70, size=3000)
    for v in bm.verts:
        v.co.z = -0.35 + r.uniform(-0.25, 0.25)
    far_mat = pm.sea_material('LO_SeaPaperFar', haze=(None, 1400.0, 1.0), foam_gain=0.0, foam_z=5.0)
    obj_from_bm('SEA_far', bm, far_mat, 'SEA', 5)


# =========================================================================== island
def island_radius(theta, r):
    """Irregular shoreline: normalised radius multiplier for direction theta."""
    k = 1.0
    for i, (amp, freq) in enumerate(((0.09, 2), (0.07, 3), (0.05, 5), (0.03, 9))):
        k += amp * math.sin(freq * theta + r[i])
    return k


ISL_PH = [rng('shore').uniform(0, 6.28) for _ in range(4)]


# Fight zones: [(x, y, r)] levelled to ONE height (the mean of the raw sand at their centres), blending back into the
# dunes over FLAT_FALLOFF metres. The 'ganryujima' kit piece fills it from the set's fighter marks. Without it the
# duel beach sloped 5-14 degrees under the marks (27 Nov), so a foot on the sand was either buried or floating.
FLAT = []
FLAT_FALLOFF = 2.5
_FLAT_Z = []


def flat_weight(x, y):
    """0 = untouched dune, 1 = inside a levelled fight zone."""
    w = 0.0
    for fx, fy, fr in FLAT:
        t = 1.0 - min(1.0, max(0.0, (math.hypot(x - fx, y - fy) - fr) / FLAT_FALLOFF))
        w = max(w, t * t * (3 - 2 * t))
    return w


def island_height(x, y):
    """Height of the sand: the raw dunes, levelled inside the fight zones (FLAT)."""
    h = _raw_island_height(x, y)
    if FLAT:
        if not _FLAT_Z:
            _FLAT_Z.append(sum(_raw_island_height(fx, fy) for fx, fy, _ in FLAT) / len(FLAT))
        h += (_FLAT_Z[0] - h) * flat_weight(x, y)
    return h


def _raw_island_height(x, y):
    """Height of the sand at (x, y): plateau, gentle duel beach on -Y, under water past the shoreline."""
    dx, dy = (x - ISLAND_C.x) / ISLAND_AX[0], (y - ISLAND_C.y) / ISLAND_AX[1]
    theta = math.atan2(dy, dx)
    rho = math.hypot(dx, dy) / island_radius(theta, ISL_PH)
    def smooth(a, b, t):
        t = min(1.0, max(0.0, (t - a) / (b - a)))
        return t * t * (3 - 2 * t)
    beach = 0.62 if dy < 0 else 0.8                       # wider, flatter beach on the duel side
    h = ISLAND_TOP * (1 - smooth(beach * 0.55, 1.0, rho))  # plateau -> beach -> waterline at rho ~ 1
    h -= 1.1 * smooth(0.95, 1.25, rho)                     # shelf under the water
    return h + 0.06


def build_island():
    r = rng('island')
    rings, segs = 30, 96
    bm = bmesh.new()
    grid = []
    for i in range(rings + 1):
        rho = 1.25 * (i / rings) ** 0.85
        row = []
        for j in range(segs if i else 1):
            th = 2 * math.pi * j / segs + (0.5 * (i % 2)) * 2 * math.pi / segs
            k = island_radius(th, ISL_PH) * rho
            x = ISLAND_C.x + ISLAND_AX[0] * k * math.cos(th)
            y = ISLAND_C.y + ISLAND_AX[1] * k * math.sin(th)
            if i:
                x += r.uniform(-0.25, 0.25); y += r.uniform(-0.25, 0.25)
            z = island_height(x, y) + (r.uniform(-0.05, 0.05) * (1.0 - flat_weight(x, y)) if i else 0)
            row.append(bm.verts.new((x, y, z)))
        grid.append(row)
    for j in range(segs):
        bm.faces.new((grid[0][0], grid[1][j], grid[1][(j + 1) % segs]))
    for i in range(1, rings):
        a, b = grid[i], grid[i + 1]
        for j in range(segs):
            bm.faces.new((a[j], b[j], b[(j + 1) % segs]))
            bm.faces.new((a[j], b[(j + 1) % segs], a[(j + 1) % segs]))
    sand = pm.paper_material('LO_PaperSand', (0.48, 0.37, 0.24), tint=(0.26, 0.19, 0.12), tint_z=(0.05, 0.45),
                             translucency=0.0, fibre_scale=1.4, fibre_strength=0.25, facet_var=0.12, rough=0.9)
    obj_from_bm('ISLAND_sand', bm, sand, 'ISLAND', 11)

    # beach grass: small folded-paper tufts on the plateau
    rg = rng('grass')
    gm = pm.paper_material('LO_PaperGrass', (0.16, 0.18, 0.07), translucency=0.35, fibre_scale=6, facet_var=0.15)
    bm = bmesh.new()
    for _ in range(140):
        th = rg.uniform(0, 2 * math.pi); rr = math.sqrt(rg.random()) * 0.62
        x = ISLAND_C.x + ISLAND_AX[0] * rr * math.cos(th); y = ISLAND_C.y + ISLAND_AX[1] * rr * math.sin(th)
        if y < ISLAND_C.y - 4:   # keep the duel beach clear
            continue
        s = rg.uniform(0.25, 0.6)
        # A tuft of thin folded blades, not a hollow cone: 140 cones read as little dark pyramids
        # all over the sand (Mark, Nov 26: "the tree, the branch, the environment"). Each blade is
        # a narrow paper strip with a crease, leaning out from the root and drooping at the tip.
        base = Vector((x, y, island_height(x, y) - 0.02))
        for b in range(rg.randint(5, 8)):
            a = rg.uniform(0, 2 * math.pi)
            out = Vector((math.cos(a), math.sin(a), 0))
            side = Vector((-out.y, out.x, 0)) * s * rg.uniform(0.035, 0.06)
            h = s * rg.uniform(1.1, 2.3)
            mid = base + out * h * rg.uniform(0.12, 0.25) + Vector((0, 0, h * 0.62))
            tip = base + out * h * rg.uniform(0.35, 0.7) + Vector((0, 0, h * rg.uniform(0.75, 1.0)))
            v = [bm.verts.new(p) for p in (base - side, base + side, mid + side * 0.6 + Vector((0, 0, 0.01)),
                                           tip, mid - side * 0.6)]
            bm.faces.new((v[0], v[1], v[2], v[4]))
            bm.faces.new((v[4], v[2], v[3]))
    obj_from_bm('ISLAND_grass', bm, gm, 'ISLAND', 12)

    # shoreline foam: two ragged cut-paper lace strips that follow the waterline
    fm = pm.paper_material('LO_PaperFoam', (0.86, 0.82, 0.74), translucency=0.45, fibre_scale=4, facet_var=0.06)
    rf = rng('foam')
    for band, (r0, w, z) in enumerate(((1.0, 0.03, 0.08), (1.035, 0.02, 0.03))):
        bm = bmesh.new()
        n = 220
        inner, outer = [], []
        for j in range(n):
            th = 2 * math.pi * j / n
            k = island_radius(th, ISL_PH)
            for target, rho in ((inner, r0 - w * 0.5), (outer, r0 + w * rf.uniform(0.2, 1.4))):
                x = ISLAND_C.x + ISLAND_AX[0] * k * rho * math.cos(th)
                y = ISLAND_C.y + ISLAND_AX[1] * k * rho * math.sin(th)
                target.append(bm.verts.new((x, y, z + rf.uniform(-0.03, 0.03))))
        for j in range(n):
            if rf.random() < (0.2 if band == 0 else 0.45):     # torn gaps in the lace
                continue
            bm.faces.new((inner[j], outer[j], outer[(j + 1) % n], inner[(j + 1) % n]))
        ob = obj_from_bm(f'ISLAND_foam_{band}', bm, fm, 'ISLAND', 20 + band)


# =========================================================================== rocks
def rock_bm(bm, r, loc, size, squash=0.6):
    m = Matrix.Translation(loc) @ Matrix.Rotation(r.uniform(0, 6.28), 4, 'Z') @ \
        Matrix.Diagonal((size * r.uniform(0.8, 1.4), size * r.uniform(0.7, 1.1), size * squash * r.uniform(0.7, 1.2), 1))
    res = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0, matrix=m)
    for v in res['verts']:
        v.co += Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-1, 1))) * size * 0.18


def build_rocks():
    r = rng('rocks')
    mat = pm.paper_material('LO_PaperRock', (0.13, 0.115, 0.10), translucency=0.0, fibre_scale=2.5,
                            fibre_strength=0.3, facet_var=0.18, rough=0.9)
    bm = bmesh.new()
    # outcrop at the east point, scattered beach stones, and surf rocks just offshore
    for _ in range(14):
        th = r.uniform(-0.5, 0.4); k = r.uniform(0.85, 1.1)
        x = ISLAND_C.x + ISLAND_AX[0] * k * math.cos(th); y = ISLAND_C.y + ISLAND_AX[1] * k * math.sin(th)
        s = r.uniform(1.0, 3.2)
        rock_bm(bm, r, (x, y, island_height(x, y) - s * 0.2), s)
    for _ in range(18):
        th = r.uniform(0, 2 * math.pi); k = r.uniform(0.75, 1.0)
        x = ISLAND_C.x + ISLAND_AX[0] * k * math.cos(th); y = ISLAND_C.y + ISLAND_AX[1] * k * math.sin(th)
        if abs(x) < 7 and y < ISLAND_C.y:      # keep the duel ground clear
            continue
        s = r.uniform(0.25, 0.8)
        rock_bm(bm, r, (x, y, island_height(x, y) - s * 0.15), s)
    for _ in range(12):
        th = r.uniform(0, 2 * math.pi); k = r.uniform(1.12, 1.5)
        x = ISLAND_C.x + ISLAND_AX[0] * k * math.cos(th); y = ISLAND_C.y + ISLAND_AX[1] * k * math.sin(th)
        s = r.uniform(0.6, 2.0)
        rock_bm(bm, r, (x, y, -0.3), s, squash=0.8)
    obj_from_bm('ROCKS', bm, mat, 'ROCKS', 31)


# =========================================================================== pines (folded-paper cones)
def build_pines():
    r = rng('pines')
    bark = pm.paper_material('LO_PaperBark', (0.11, 0.075, 0.05), translucency=0.0, fibre_scale=8, fibre_strength=0.3, facet_var=0.15)
    needle = pm.paper_material('LO_PaperPine', (0.05, 0.085, 0.045), translucency=0.3, fibre_scale=5,
                               facet_var=0.16, translucent_color=(0.2, 0.3, 0.08))
    spots = [(-22, 11), (-15, 15), (-8, 13.5), (-2, 16), (5, 12.5), (11, 16), (17, 13), (24, 10), (-27, 6)]
    for idx, (px, py) in enumerate(spots):
        px += r.uniform(-1.5, 1.5); py += r.uniform(-1, 1)
        h = r.uniform(6.5, 11.0)
        lean = Vector((r.uniform(-0.25, 0.25), r.uniform(-0.45, -0.15), 0))   # lean toward the sea (-Y)
        base = Vector((px, py, island_height(px, py) - 0.3))
        trunk = bmesh.new()
        rings = []
        pts = []
        for i in range(6):
            t = i / 5
            p = base + Vector((0, 0, h * 0.82 * t)) + lean * h * t * t + \
                Vector((r.uniform(-0.3, 0.3), r.uniform(-0.3, 0.3), 0)) * (i > 0)
            pts.append(p)
            rad = 0.32 * (1 - 0.7 * t) + 0.04
            rings.append([trunk.verts.new(p + Vector((rad * math.cos(a), rad * math.sin(a), 0)))
                          for a in [2 * math.pi * k / 5 + i for k in range(5)]])
        for i in range(5):
            for k in range(5):
                trunk.faces.new((rings[i][k], rings[i][(k + 1) % 5], rings[i + 1][(k + 1) % 5], rings[i + 1][k]))
        obj_from_bm(f'PINE_{idx}_trunk', trunk, bark, 'PINES', 40 + idx)
        crown = bmesh.new()
        tiers = r.randint(3, 5)
        for k in range(tiers):
            t = 0.45 + 0.55 * k / max(1, tiers - 1)
            c = pts[min(5, int(t * 5))] + (pts[5] - pts[4]) * (t * 5 % 1)
            side = Vector((r.uniform(-1, 1), r.uniform(-1, 1), 0)).normalized() * r.uniform(0.6, 2.0) * (1.1 - t)
            rad = r.uniform(1.4, 2.6) * (1.25 - 0.5 * t)
            # each tier: a flat folded cone plus a smaller cap, like cloud-pruned kuromatsu pads
            for j, (rr, dd, dz) in enumerate(((rad, rad * 0.45, 0), (rad * 0.6, rad * 0.4, rad * 0.3))):
                m = Matrix.Translation(c + side + Vector((0, 0, dz))) @ Matrix.Rotation(r.uniform(0, 6.28), 4, 'Z') @ \
                    Matrix.Rotation(r.uniform(-0.15, 0.15), 4, 'X') @ Matrix.Diagonal((1, r.uniform(0.7, 1.0), 1, 1))
                bmesh.ops.create_cone(crown, cap_ends=True, segments=r.choice((6, 7, 8)), radius1=rr, radius2=rr * 0.12,
                                      depth=dd, matrix=m)
        jitter(crown, r, 0.08)
        obj_from_bm(f'PINE_{idx}_crown', crown, needle, 'PINES', 60 + idx)


# =========================================================================== mountains (paper cut-out rings)
def ridge_loop(r, n_pow, start_pts, rough=0.55):
    """Closed fractal ridge (midpoint displacement): straight segments = cut-paper edges."""
    h = [r.uniform(0.2, 1.0) for _ in range(start_pts)]
    amp = 0.5
    for _ in range(n_pow):
        nh = []
        for i in range(len(h)):
            a, b = h[i], h[(i + 1) % len(h)]
            nh += [a, (a + b) / 2 + r.uniform(-amp, amp)]
        h = nh
        amp *= rough
    lo, hi = min(h), max(h)
    return [(v - lo) / (hi - lo) for v in h]


def build_mountains():
    r = rng('mountains')
    sun_az = math.radians(SUN_AZ)
    layers = [  # radius, max height, colour, haze distance, partial arcs (headlands) or full ring
        (170, 14, (0.035, 0.04, 0.045), 6000, True),
        (380, 48, (0.045, 0.05, 0.06), 3800, False),
        (720, 115, (0.06, 0.06, 0.075), 3000, False),
        (1250, 200, (0.08, 0.075, 0.09), 2600, False),
        (2100, 320, (0.11, 0.095, 0.11), 2300, False),
    ]
    for li, (rad, hmax, col, hz, partial) in enumerate(layers):
        mat = pm.paper_material(f'LO_PaperMountain{li}', col, translucency=0.25, fibre_scale=0.08,
                                fibre_strength=0.2, facet_var=0.035, rough=0.95,
                                translucent_color=(0.5, 0.2, 0.1), haze=(None, hz, 1.0))
        hs = ridge_loop(r, 6, 8)
        n = len(hs)
        bm = bmesh.new()
        cols = []
        for j in range(n):
            th = 2 * math.pi * j / n            # th = compass angle, 0 = +Y, positive toward +X
            dsun = math.atan2(math.sin(th - sun_az), math.cos(th - sun_az))
            gap = min(1.0, (abs(dsun) / math.radians(16)) ** 2)          # open sea where the sun rises
            if partial:                                                   # headlands only to the sides
                gap *= max(0.0, math.sin(th * 2 + 0.6)) ** 0.6 * (abs(math.sin(th)) > 0.35)
            z = (0.12 + 0.88 * hs[j]) * hmax * gap - 4
            fold = rad * (1 + r.uniform(-0.012, 0.012))
            dir_ = Vector((math.sin(th), math.cos(th), 0))
            cols.append((bm.verts.new(dir_ * rad + Vector((0, 0, -8))),
                         bm.verts.new(dir_ * fold + Vector((0, 0, z * 0.55))),
                         bm.verts.new(dir_ * rad + Vector((0, 0, z)))))
        for j in range(n):
            a, b = cols[j], cols[(j + 1) % n]
            for k in range(2):
                if a[k + 1].co.z < -3.5 and b[k + 1].co.z < -3.5:
                    continue
                bm.faces.new((a[k], b[k], b[k + 1], a[k + 1]))
        ob = obj_from_bm(f'MOUNTAINS_{li}', bm, mat, 'MOUNTAINS', 80 + li)
        ob.visible_shadow = li == 0


# =========================================================================== clouds (folded paper)
def build_clouds():
    r = rng('clouds')
    mat = pm.paper_material('LO_PaperCloud', (0.80, 0.70, 0.62), translucency=0.55, fibre_scale=0.1,
                            facet_var=0.28, translucent_color=(1.0, 0.6, 0.4), haze=(None, 1600, 1.0))
    for i in range(16):
        far_side = i >= 12                       # a few clouds behind the island for reverse shots
        th = math.radians(SUN_AZ) + r.uniform(-0.7, 0.7) + (math.pi if far_side else 0)
        d = r.uniform(700, 1800)
        el = r.uniform(6, 26)
        if not far_side and abs(th - math.radians(SUN_AZ)) < math.radians(9) and el < SUN_ELEV + 9:
            el += 10                              # never cover the paper sun
        c = Vector((math.sin(th) * d, math.cos(th) * d, d * math.tan(math.radians(el))))
        w = r.uniform(70, 220)
        bm = bmesh.new()
        for k in range(r.randint(3, 6)):
            off = Vector((r.uniform(-0.5, 0.5) * w, r.uniform(-0.1, 0.1) * w, r.uniform(0, 0.12) * w))
            s = w * r.uniform(0.18, 0.35)
            m = Matrix.Translation(off) @ Matrix.Diagonal((s * r.uniform(1.4, 2.4), s * 0.6, s * r.uniform(0.35, 0.6), 1))
            bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0, matrix=m)
        jitter(bm, r, w * 0.02)
        ob = obj_from_bm(f'CLOUD_{i}', bm, mat, 'CLOUDS', 100 + i)
        ob.location = c
        ob.rotation_euler = (0, 0, -th)
        ob.visible_shadow = False


# =========================================================================== optional ground fog
def build_fog():
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 60, 6))
    ob = bpy.context.object
    ob.name = 'FOG_ground'
    for c in ob.users_collection:
        c.objects.unlink(ob)
    link(ob, 'FOG')
    ob.scale = (500, 400, 12)
    m = pm.new_material('LO_FogVolume')
    nt = m.node_tree
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    v = nt.nodes.new('ShaderNodeVolumePrincipled')
    v.inputs['Color'].default_value = (0.95, 0.78, 0.68, 1)
    v.inputs['Density'].default_value = 0.004
    v.inputs['Anisotropy'].default_value = 0.6
    nt.links.new(v.outputs[0], out.inputs['Volume'])
    ob.data.materials.append(m)
    ob.hide_render = not FOG
    ob.hide_viewport = not FOG


# =========================================================================== marks + camera anchors
MARKS = {}


def build_marks():
    def mark(name, x, y, face_to, role):
        z = max(0.0, island_height(x, y))
        e = bpy.data.objects.new(name, None)
        e.empty_display_type = 'ARROWS'
        e.empty_display_size = 0.8
        e.location = (x, y, z)
        d = Vector(face_to) - Vector((x, y))
        e.rotation_euler = (0, 0, math.atan2(d.y, d.x) - math.radians(90))  # local +Y faces the target
        e['role'] = role
        link(e, 'MARKS')
        MARKS[name] = e
        return e
    mark('MARK_hero', -1.8, -3.2, (1.8, -3.2), 'hero stands here, facing the foe (+X)')
    mark('MARK_foe', 1.8, -3.2, (-1.8, -3.2), 'foe stands here, facing the hero (-X)')
    mark('MARK_center', 0.0, -3.2, (0.0, -30.0), 'midpoint of the duel line')
    mark('MARK_boat', -9.0, -14.0, (-1.8, -3.2), 'a boat lands here (shallows, sea level)')
    mark('MARK_shore', 6.0, -9.0, (0.0, -3.2), 'waterline walk-on point')


def anchor(name, loc, look, lens, note):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = 'CONE'
    e.empty_display_size = 0.6
    e.location = loc
    e.rotation_euler = look_rot(loc, look)
    e['lens_mm'] = lens
    e['look_at'] = list(look)
    e['note'] = note
    link(e, 'CAMERAS')
    return e


def build_cameras():
    c = Vector(MARKS['MARK_center'].location) + Vector((0, 0, 1.3))
    h = Vector(MARKS['MARK_hero'].location) + Vector((0, 0, 1.5))
    f = Vector(MARKS['MARK_foe'].location) + Vector((0, 0, 1.5))
    anchor('CAM_wide', (1.2, -22.0, 2.6), c + Vector((0, 10, 3.2)), 24, 'establishing: sea, beach, fighters, pines, mountains, sun')
    anchor('CAM_medium', (0.6, -11.0, 1.5), c + Vector((0, 0, 0.1)), 28, 'both fighters full body')
    anchor('CAM_hero_ots', h + Vector((-1.6, -1.4, 0.15)), f, 50, 'over the hero shoulder onto the foe')
    anchor('CAM_foe_ots', f + Vector((1.6, -1.4, 0.15)), h, 50, 'over the foe shoulder onto the hero')
    anchor('CAM_low_sea', (-6.0, -20.0, 0.45), c + Vector((0, 0, 0.6)), 28, 'low over the water toward the beach')
    anchor('CAM_high', (-14.0, -18.0, 16.0), c, 30, 'high wide, the island shape')
    anchor('CAM_profile', (0.0, -7.2, 1.1), c + Vector((0, 0, -0.2)), 22, 'side-on duel line, low (180-degree line is X)')
    anchor('CAM_reverse', (0.5, 30.0, 4.0), c, 30, 'reverse: from behind the pines toward the open sea')

    cd = bpy.data.cameras.new('KUROKO')
    cd.sensor_fit = 'AUTO'
    cd.clip_start = 0.05
    cd.clip_end = 8000
    cd.dof.use_dof = False
    cam = link(bpy.data.objects.new('KUROKO', cd), 'CAMERAS')
    scene.camera = cam
    return cam


def put_camera(cam, name):
    a = bpy.data.objects[name]
    cam.matrix_world = a.matrix_world.copy()
    cam.data.lens = a['lens_mm']


# =========================================================================== stand-in fighters (scale + look)
def build_standins():
    """Two faceted folded-paper samurai so previews read at the right scale. Delete or hide for real films."""
    def fighter(name, mark, kimono, hakama, stripe, hat, glow):
        mats = [pm.paper_material(f'LO_{name}_kimono', kimono, translucency=0.4, fibre_scale=60, glow=None),
                pm.paper_material(f'LO_{name}_hakama', hakama, translucency=0.3, fibre_scale=60, stripes=(stripe, 9.0, 0.35)),
                pm.paper_material(f'LO_{name}_hat', hat, translucency=0.15, fibre_scale=60, facet_var=0.15),
                pm.paper_material(f'LO_{name}_skin', (0.62, 0.46, 0.34), translucency=0.35, fibre_scale=80)]
        bm = bmesh.new()
        parts = []
        def add(fn, mi, **kw):
            res = fn(bm, **kw)
            for f in {f for v in res['verts'] for f in v.link_faces}:
                f.material_index = mi
        T = Matrix.Translation
        add(bmesh.ops.create_cone, 1, cap_ends=True, segments=7, radius1=0.36, radius2=0.2, depth=0.85, matrix=T((0, 0, 0.43)))
        add(bmesh.ops.create_cone, 0, cap_ends=True, segments=6, radius1=0.2, radius2=0.25, depth=0.62, matrix=T((0, 0, 1.15)))
        add(bmesh.ops.create_cone, 0, cap_ends=True, segments=6, radius1=0.24, radius2=0.18, depth=0.18, matrix=T((0, 0, 0.9)))
        for sx in (-1, 1):   # layered sleeves
            add(bmesh.ops.create_cone, 0, cap_ends=True, segments=4, radius1=0.08, radius2=0.17, depth=0.46,
                matrix=T((sx * 0.33, 0.04, 1.12)) @ Matrix.Rotation(sx * 0.3, 4, 'Y'))
        add(bmesh.ops.create_icosphere, 3, subdivisions=1, radius=0.12, matrix=T((0, 0, 1.6)) @ Matrix.Scale(1.15, 4, (0, 0, 1)))
        add(bmesh.ops.create_cone, 2, cap_ends=True, segments=12, radius1=0.42, radius2=0.03, depth=0.2, matrix=T((0, 0, 1.78)))
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new(name, me)
        for m in mats:
            me.materials.append(m)
        pm.shade_flat(ob); pm.add_facet_attribute(ob, zlib.crc32(name.encode()))
        link(ob, 'STANDINS')
        mk = MARKS[mark]
        ob.location = mk.location
        ob.rotation_euler = (0, 0, mk.rotation_euler.z)
        li = bpy.data.lights.new(name + '_glow', 'POINT')
        li.energy = 6; li.color = glow; li.shadow_soft_size = 0.1
        lo = link(bpy.data.objects.new(name + '_glow', li), 'STANDINS')
        lo.parent = ob; lo.location = (0, 0, 1.15)
    fighter('STANDIN_hero', 'MARK_hero', (0.62, 0.56, 0.46), (0.12, 0.13, 0.2), (0.22, 0.24, 0.33), (0.07, 0.055, 0.04), (1.0, 0.55, 0.2))
    fighter('STANDIN_foe', 'MARK_foe', (0.45, 0.12, 0.09), (0.16, 0.15, 0.14), (0.3, 0.27, 0.22), (0.06, 0.05, 0.04), (1.0, 0.55, 0.2))


# =========================================================================== render settings
def setup_render():
    scene.render.engine = 'CYCLES'
    cy = scene.cycles
    cy.device = 'CPU'
    cy.samples = SAMPLES
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.05
    cy.use_denoising = True
    cy.denoiser = 'OPENIMAGEDENOISE'
    cy.max_bounces = 4
    cy.diffuse_bounces = 2
    cy.glossy_bounces = 2
    cy.transmission_bounces = 4
    cy.transparent_max_bounces = 4
    cy.volume_bounces = 0
    cy.sample_clamp_indirect = 5
    cy.use_light_tree = True
    scene.render.use_persistent_data = True
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 2
    scene.render.resolution_x, scene.render.resolution_y = RES
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.frame_start, scene.frame_end = 1, 240
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.view_settings.exposure = float(arg('exposure', -2.0))
    scene.render.image_settings.file_format = 'PNG'


# =========================================================================== build
def main():
    init_scene()
    t0 = time.time()
    setup_render()
    build_sky()
    build_sea()
    build_island()
    build_rocks()
    build_pines()
    build_mountains()
    build_clouds()
    build_fog()
    build_marks()
    cam = build_cameras()
    if STANDINS:
        build_standins()
    put_camera(cam, CAMS[0])
    scene.frame_set(FRAME)
    scene['lantern_origami_world'] = 'ganryujima'
    scene['seed'] = SEED
    build_s = time.time() - t0
    print(f'BUILT in {build_s:.1f}s  objects={len(bpy.data.objects)}')

    out = os.path.abspath(OUT)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0      # no .blend1 backups
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print('SAVED', out)

    if PREVIEW:
        for i, name in enumerate(CAMS):
            put_camera(cam, name)
            base, ext = os.path.splitext(os.path.abspath(PREVIEW))
            scene.render.filepath = base + ('' if i == 0 else f'-{name}') + (ext or '.png')
            os.makedirs(os.path.dirname(scene.render.filepath), exist_ok=True)
            t = time.time()
            bpy.ops.render.render(write_still=True)
            print(f'RENDERED {name} -> {scene.render.filepath} in {time.time() - t:.1f}s '
                  f'({RES[0]}x{RES[1]}, {SAMPLES} spp, fog={FOG})')



if __name__ == '__main__':
    main()
