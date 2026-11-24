"""PART REGISTRY: the Modular Origami Character Factory's library of folded paper parts.

One skeleton, many interchangeable parts, one material family. Every part is a function registered with
@part(...), which declares everything the builder and the validator need to know about it:

    slot          where it goes (hat, face, hair, torso, collar, obi, sleeve_upper, sleeve_hanging, forearm,
                  hand, thigh, shin, foot, armor, accessory)
    socket        the attachment point in the rig's REST pose (position + orientation, see SOCKETS)
    bone/bones    the bone it binds to (rigid) or the 2-3 bones it is weighted across (flexible)
    rigid         True = parented to one bone, False = skinned across `bones`
    size          the approved uniform scale range (min, max); a recipe may not go outside it
    layer         draw/layer order: a higher number sits OVER a lower one (skin 0 … hat 90)
    material      the sheet it wants from library/paper-materials/ (a recipe may override)
    proportions   the body proportions it is cut for

    python3 blender/character/part_registry.py            # the whole library as a table
    python3 blender/character/part_registry.py --slots    # the slot table only

Every part is built as a FOLDED SHELL: flat facets, real thickness (solidify, the rim gets its own material so
the cut edge of the sheet reads), neighbours that OVERLAP at the joints, and a dark seam gap (`seam_shadow`)
wherever two sheets meet — the three things that make the reference read as separate sheets of paper rather
than one fused blob.

Geometry is built in the rig's REST world space (metres, Z up, the character faces -Y), around the part's
socket. The builder (modular_builder.py) scales, binds and poses it.
"""
import math
import os
import random
import sys

try:
    import bmesh
    import bpy
    from mathutils import Matrix, Vector
    HAVE_BPY = True
except ImportError:                        # `python3 part_registry.py` outside Blender
    HAVE_BPY = False
    Vector = tuple

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(HERE, '..', 'world'))
if HAVE_BPY:
    import paper_materials as pm  # noqa: E402

# =========================================================================== the shared skeleton
# Joint rest positions in Blender world space (metres). Same joints and same names as engine/figure.js and
# blender/character/rig_trellis.py, so library/poses.json drives this rig directly.
REST = {
    'root': (0.00, 0.0, 0.00), 'hips': (0.00, 0.0, 0.92), 'torso': (0.00, 0.0, 0.92),
    'upper': (0.00, 0.0, 1.18), 'neck': (0.00, 0.0, 1.47), 'head': (0.00, 0.0, 1.53),
    'hakama': (0.00, 0.0, 0.92),
    'lC': (0.07, 0.0, 1.39), 'lS': (0.23, 0.0, 1.39), 'lE': (0.23, 0.0, 1.09),
    'lT': (0.23, 0.0, 1.09), 'lH': (0.23, 0.0, 0.80),
    'rC': (-0.07, 0.0, 1.39), 'rS': (-0.23, 0.0, 1.39), 'rE': (-0.23, 0.0, 1.09),
    'rT': (-0.23, 0.0, 1.09), 'rH': (-0.23, 0.0, 0.80),
    'lthigh': (0.10, 0.0, 0.92), 'lshin': (0.10, 0.0, 0.46), 'lfoot': (0.10, 0.0, 0.02),
    'rthigh': (-0.10, 0.0, 0.92), 'rshin': (-0.10, 0.0, 0.46), 'rfoot': (-0.10, 0.0, 0.02),
}
PARENT = {'hips': 'root', 'torso': 'hips', 'upper': 'torso', 'neck': 'upper', 'head': 'neck', 'hakama': 'hips',
          'lC': 'upper', 'lS': 'lC', 'lE': 'lS', 'lT': 'lE', 'lH': 'lT',
          'rC': 'upper', 'rS': 'rC', 'rE': 'rS', 'rT': 'rE', 'rH': 'rT',
          'lthigh': 'root', 'lshin': 'lthigh', 'lfoot': 'lshin',
          'rthigh': 'root', 'rshin': 'rthigh', 'rfoot': 'rshin'}

# --------------------------------------------------------------------------- sockets
# A socket is where a part clips on: a position in the rest pose, the direction the part grows in ('up',
# 'down', 'out', 'front'), the bone under it, and the body radius there (so a part can be cut to fit).
def _socket(pos, bone, grow='down', radius=0.12, side=0):
    return dict(pos=tuple(pos), bone=bone, grow=grow, radius=radius, side=side)


SOCKETS = {
    'head_top':   _socket((0, 0.00, 1.585), 'head', 'up', 0.11),
    'face':       _socket((0, -0.03, 1.625), 'head', 'front', 0.11),
    'hair_back':  _socket((0, 0.05, 1.63), 'head', 'back', 0.10),
    'neck':       _socket((0, 0.00, 1.47), 'neck', 'up', 0.055),
    'collar':     _socket((0, -0.06, 1.36), 'upper', 'down', 0.17),
    'chest':      _socket((0, 0.00, 1.18), 'upper', 'up', 0.22),
    'waist':      _socket((0, 0.00, 0.92), 'torso', 'up', 0.18),
    'obi':        _socket((0, 0.00, 0.94), 'torso', 'up', 0.20),
    'back':       _socket((0, 0.11, 1.22), 'torso', 'back', 0.10),
    'hip_side.L': _socket((0.185, -0.055, 0.945), 'torso', 'out', 0.06, side=1),
    'hip_side.R': _socket((-0.185, -0.055, 0.945), 'torso', 'out', 0.06, side=-1),
    'shoulder.L': _socket((0.23, 0.00, 1.39), 'lS', 'down', 0.085, side=1),
    'shoulder.R': _socket((-0.23, 0.00, 1.39), 'rS', 'down', 0.085, side=-1),
    'elbow.L':    _socket((0.23, 0.00, 1.09), 'lT', 'down', 0.075, side=1),
    'elbow.R':    _socket((-0.23, 0.00, 1.09), 'rT', 'down', 0.075, side=-1),
    'hand.L':     _socket((0.23, 0.00, 0.80), 'lH', 'down', 0.045, side=1),
    'hand.R':     _socket((-0.23, 0.00, 0.80), 'rH', 'down', 0.045, side=-1),
    'hip.L':      _socket((0.10, 0.00, 0.92), 'lthigh', 'down', 0.16, side=1),
    'hip.R':      _socket((-0.10, 0.00, 0.92), 'rthigh', 'down', 0.16, side=-1),
    'knee.L':     _socket((0.10, 0.00, 0.46), 'lshin', 'down', 0.17, side=1),
    'knee.R':     _socket((-0.10, 0.00, 0.46), 'rshin', 'down', 0.17, side=-1),
    'ankle.L':    _socket((0.10, 0.00, 0.02), 'lfoot', 'front', 0.07, side=1),
    'ankle.R':    _socket((-0.10, 0.00, 0.02), 'rfoot', 'front', 0.07, side=-1),
}

SLOTS = {   # slot: (what it is, default layer, is it usually flexible)
    'hat': ('head covering: kasa, hachigane, hood', 90, False),
    'face': ('the folded mask: nose ridge, eye slits, chin', 40, False),
    'hair': ('folded hair / topknot at the back of the head', 35, False),
    'neck': ('the neck column between collar and mask', 30, False),
    'torso': ('the kimono body: the sheets the rest layers onto', 20, False),
    'collar': ('eri: the crossed lapels, left over right', 45, False),
    'obi': ('the sash with its knot and cord', 50, False),
    'sleeve_upper': ('the upper arm sleeve', 25, False),
    'sleeve_hanging': ('tamoto: the wide hanging sleeve bag', 55, True),
    'forearm': ('the forearm sleeve or kote', 25, False),
    'hand': ('folded fingers', 15, False),
    'thigh': ('hakama upper leg', 22, True),
    'shin': ('hakama lower leg', 22, True),
    'foot': ('tabi + zori', 18, False),
    'armor': ('plates over the paper: sode, do, kusazuri', 60, False),
    'accessory': ('katana, cords, tassels, straps', 70, False),
}

PARTS = {}


def part(name, *, slot, socket, bone=None, bones=None, rigid=True, size=(0.9, 1.1), layer=None,
         material='washi_natural', rim='washi_shade', proportions=('standard',), tags=(), **defaults):
    """Register a part. `defaults` doubles as its documented parameter list."""
    def deco(fn):
        if slot not in SLOTS:
            raise KeyError(f'{name}: unknown slot {slot!r}')
        socks = socket if isinstance(socket, (list, tuple)) else [socket]
        for s in socks:
            if s not in SOCKETS:
                raise KeyError(f'{name}: unknown socket {s!r}')
        PARTS[name] = dict(
            name=name, fn=fn, slot=slot, socket=socks, bone=bone, bones=list(bones or []), rigid=rigid,
            size=tuple(size), layer=SLOTS[slot][1] if layer is None else layer, material=material, rim=rim,
            proportions=tuple(proportions), tags=tuple(tags), defaults={'material': material, **defaults},
            doc=(fn.__doc__ or '').strip().split('\n')[0])
        return fn
    return deco


# =========================================================================== folding tools
# Everything here makes CRISP PAPER: straight creases, flat facets, low vertex counts, no smooth shading.
def V(x, y, z):
    return Vector((x, y, z))


def poly_ring(n, r, z, *, cx=0.0, cy=0.0, flute=0.0, sy=1.0, phase=0.0, front_pull=0.0, lift=0.0):
    """One ring of a folded tube. `flute` pushes every second vertex in and `lift` pushes it up: together
    that is a real pleat (a fold with a ridge and a valley), not a wobble in a curve."""
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n + phase
        odd = i % 2
        rr = r * (1 - flute if odd else 1.0)
        z = z + lift if odd else z - (lift if lift else 0.0)
        x, y = cx + rr * math.cos(a), cy + rr * math.sin(a) * sy
        if front_pull and math.sin(a) < 0:
            y -= front_pull * -math.sin(a)
        out.append((x, y, z))
        if lift:
            z = z - lift if odd else z + lift
    return out


def skin_rings(bm, rings, *, close=True, cap_first=False, cap_last=False):
    """Bridge a stack of equal-length rings into a folded tube."""
    vs = [[bm.verts.new(p) for p in ring] for ring in rings]
    n = len(vs[0])
    for a, b in zip(vs, vs[1:]):
        for i in range(n if close else n - 1):
            j = (i + 1) % n
            try:
                bm.faces.new((a[i], a[j], b[j], b[i]))
            except ValueError:
                pass
    if cap_first:
        bm.faces.new(vs[0][::-1])
    if cap_last:
        bm.faces.new(vs[-1])
    return vs


def folded_sheet(rows, *, closed=False, flip=False):
    """Join fold lines and lay out the paper grain as one sheet, with a single seam on a closed wrap."""
    bm = bmesh.new()
    points = [[Vector(p) for p in row] for row in rows]
    verts = [[bm.verts.new(p) for p in row] for row in points]
    uv = bm.loops.layers.uv.new('PaperGrain')
    cols = len(verts[0])
    width_row = points[len(points) // 2]
    across = [0.0]
    for i in range(cols if closed else cols - 1):
        across.append(across[-1] + (width_row[(i + 1) % cols] - width_row[i]).length)
    along = [[0.0] * cols]
    for a, b in zip(points, points[1:]):
        along.append([v + (q - p).length for v, p, q in zip(along[-1], a, b)])
    for row in range(len(rows) - 1):
        for col in range(len(across) - 1):
            corners = [(row, col), (row, col + 1), (row + 1, col + 1), (row + 1, col)]
            if flip:
                corners.reverse()
            face = bm.faces.new([verts[j][i % cols] for j, i in corners])
            for loop, (j, i) in zip(face.loops, corners):
                loop[uv].uv = (across[i], along[j][i % cols])
        if closed:
            bm.edges.get((verts[row][0], verts[row + 1][0])).seam = True
    return bm


def shell(points, faces):
    """A folded shell straight from a vertex list: the honest way to make a crease you can point at."""
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in points]
    for f in faces:
        try:
            bm.faces.new([vs[i] for i in f])
        except ValueError:
            pass
    return bm


def panel(pts, *, bulge=0.0, normal=(0, -1, 0)):
    """A flat folded panel (an n-gon). `bulge` lifts its centre along the normal: one soft crease, no curve."""
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in pts]
    f = bm.faces.new(vs)
    if bulge:
        c = sum((Vector(p) for p in pts), Vector()) / len(pts)
        bmesh.ops.poke(bm, faces=[f])
        for v in bm.verts:
            if (Vector(v.co) - c).length < 1e-5:
                v.co += Vector(normal).normalized() * bulge
    return bm


def box(cx, cy, cz, sx, sy, sz, rot=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    m = Matrix.Rotation(rot[0], 3, 'X') @ Matrix.Rotation(rot[1], 3, 'Y') @ Matrix.Rotation(rot[2], 3, 'Z')
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=m)
    bmesh.ops.translate(bm, vec=(cx, cy, cz), verts=bm.verts)
    return bm


def join(bm, other):
    me = bpy.data.meshes.new('_tmp')
    other.to_mesh(me)
    other.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    return bm


def creases(bm, *, inset=0.004, depth=-0.0022, share=1.0, rnd=None):
    """Score a thin groove around facets: the valley the light catches at every fold. Material index 1."""
    rnd = rnd or random
    faces = [f for f in bm.faces if rnd.random() < share]
    if not faces:
        return
    bmesh.ops.inset_individual(bm, faces=faces, thickness=inset, depth=depth, use_even_offset=True)
    inner = set(faces)
    for f in bm.faces:
        if f not in inner:
            f.material_index = 1


# =========================================================================== build context
class PartCtx:
    """What a part builder is handed: the collection, the socket it hangs on, materials and a seeded stream."""

    def __init__(self, coll, *, seed=1, materials=None, glow=((1.0, 0.55, 0.18), 3.0), scale=1.0,
                 suffix='', proportion='standard'):
        self.coll = coll
        self.rnd = random.Random(seed)
        self.seed = seed
        self.glow = glow
        self.scale = scale
        self.suffix = suffix
        self.proportion = proportion
        self.overrides = materials or {}
        self._mats = {}
        self.socket = Vector((0, 0, 0))
        self.sock = None
        self.side = 1
        self.objects = []

    # ---- materials: one family, world-scale fibre, every sheet from library/paper-materials/
    def mat(self, key, *, glow=None, color=None):
        key = self.overrides.get(key, key)
        # The sheet reflects and transmits light. Only the narrow openings should read as emissive.
        if glow is True:
            glow = (self.glow[0], min(self.glow[1] * 0.018, 0.08))
        return pm.PC_Washi_Master(key, scale=1.0, suffix=self.suffix,
                                  glow=glow, color=color)

    def emit(self, key='glow', strength=None):
        nm = 'PC_Glow_' + key + self.suffix
        nm += '' if strength is None else '_%d' % round(strength * 10)
        m = bpy.data.materials.get(nm)
        if m is None:
            m = pm.emission_material(nm, self.glow[0], self.glow[1] if strength is None else strength)
            m.diffuse_color = (*self.glow[0], 1)
            m.metallic = 0.0
            m['pc_emission_color'] = self.glow[0]
            m['pc_emission_strength'] = self.glow[1] if strength is None else strength
        return m

    # ---- geometry
    def add(self, name, bm, mats, *, thickness=0.006, flat=True, rim_mat=True, to_camera=True):
        """Turn a bmesh into a part object: thickness, hard facets, per-facet tone, a cut paper edge."""
        me = bpy.data.meshes.new(name + self.suffix)
        bm.normal_update()
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(name + self.suffix, me)
        for m in mats:
            me.materials.append(m)
        self.coll.objects.link(ob)
        pm.add_facet_attribute(ob, seed=self.rnd.randint(0, 9999))
        if flat:
            for p in me.polygons:
                p.use_smooth = False
        if thickness:
            mod = ob.modifiers.new('fold', 'SOLIDIFY')
            mod.thickness = thickness
            mod.offset = 0.0
            mod.use_even_offset = True
            mod.thickness_clamp = 1.0
            if rim_mat and len(me.materials) > 1:
                mod.material_offset_rim = 1       # the cut edge of the sheet gets its own tone
        ob['pc_part'] = name
        if not to_camera:          # a lantern inside the paper: it LIGHTS, it is never seen as a white box
            ob.visible_camera = False
            ob.visible_shadow = False
            ob['pc_internal'] = 1
        self.objects.append(ob)
        return ob

    def gap(self, name, pts, push=(0, 0.006, 0), grow=0.008):
        """The dark slot behind an overlap: without it two sheets read as one moulded lump."""
        c = sum((Vector(p) for p in pts), Vector()) / len(pts)
        out = [tuple(Vector(p) + (Vector(p) - c).normalized() * grow + Vector(push)) for p in pts]
        return self.add(name, panel(out), [self.mat('seam_shadow')], thickness=0.0015, rim_mat=False)


# =========================================================================== PARTS: head
@part('kasa_wide', slot='hat', socket='head_top', bone='head', size=(0.85, 1.15), material='washi_hat',
      ribs=22, radius=0.40, rise=0.255, brim_lift=0.075, rim_roll=0.008, tags=('reference',),
      proportions=('slim', 'standard', 'broad'))
def kasa_wide(ctx, P, rnd):
    """Wide pleated kasa: radial ribs from the apex, a folded brim break and a rolled rim (the reference hat)."""
    S = ctx.socket
    n, R = int(P['ribs']), P['radius']
    apex, zr = S.z + P['rise'], S.z + P['brim_lift']
    rings = [poly_ring(n, R * 0.018, apex),
             poly_ring(n, R * 0.66, apex - (apex - zr) * 0.65, flute=0.024, lift=0.005),
             poly_ring(n, R, zr, flute=0.030, lift=0.006)]
    bm = bmesh.new()
    skin_rings(bm, rings, cap_first=True)
    kasa = ctx.add('kasa', bm, [ctx.mat(P.get('material', 'washi_hat')), ctx.mat('washi_shade')],
                   thickness=0.0045)
    # Thin raised ribs follow the folded cone. Use the same straw paper as the shell.
    ribs = bmesh.new()
    for i in range(n):
        rows = []
        for ring, half_width in zip(rings, (0.0002, 0.0022, 0.0026)):
            p = Vector(ring[i]) + Vector((0, 0, 0.002))
            d = Vector((-p.y, p.x, 0)).normalized() * half_width
            rows.append([tuple(p - d), tuple(p + Vector((0, 0, half_width))), tuple(p + d)])
        skin_rings(ribs, rows, close=False)
    ctx.add('kasa_ribs', ribs, [ctx.mat('washi_bleached'), ctx.mat('washi_shade')], thickness=0.0015)
    # rolled rim: a low-poly ring of card folded back on itself, the crisp line the reference ends on
    rim = bmesh.new()
    skin_rings(rim, [poly_ring(n, R, zr + P['rim_roll'] * 0.45, flute=0.030, lift=0.006),
                     poly_ring(n, R + P['rim_roll'], zr, flute=0.030, lift=0.006),
                     poly_ring(n, R, zr - P['rim_roll'] * 0.45, flute=0.030, lift=0.006)])
    ctx.add('kasa_rim', rim, [ctx.mat('washi_shade'), ctx.mat('seam_shadow')], thickness=0.0028)
    # the shadow under the brim, so the mask sits in a dark cave like the reference
    ring = bmesh.new()
    skin_rings(ring, [poly_ring(n, R * 0.26, zr + 0.075, flute=0.0),
                      poly_ring(n, R * 0.86, zr + 0.008, flute=0.025)])
    ctx.add('kasa_under', ring, [ctx.mat('washi_shade')], thickness=0.002, rim_mat=False)
    # A shallow headband supports the brim and lets the mask sit underneath it.
    band = [poly_ring(12, .094, S.z + .050, cy=.015, sy=.89),
            poly_ring(12, .101, zr + .085, cy=.010, sy=.90)]
    ctx.add('kasa_headband', folded_sheet(band, closed=True),
            [ctx.mat('washi_shade'), ctx.mat('seam_shadow')], thickness=.0022)
    return kasa


@part('kasa_narrow', slot='hat', socket='head_top', bone='head', size=(0.85, 1.15), material='washi_hat',
      ribs=16, radius=0.29, rise=0.235, brim_lift=0.085, rim_roll=0.011, proportions=('slim', 'standard'))
def kasa_narrow(ctx, P, rnd):
    """Narrow travelling kasa: fewer, deeper ribs and a tight rim — reads in a close-up without hiding the face."""
    return kasa_wide(ctx, P, rnd)


@part('hachigane', slot='hat', socket='head_top', bone='head', size=(0.9, 1.1), material='card_charcoal',
      width=0.115, height=0.055, proportions=('standard', 'broad'), tags=('armour',))
def hachigane(ctx, P, rnd):
    """Folded iron-card brow band with a centre spine: the armoured head, no hat."""
    S = ctx.socket
    z = S.z + 0.099
    pts, faces = [], []
    n = 9
    for i in range(n):
        a = math.pi * (1 + i / (n - 1))
        x, y = P['width'] * math.cos(a), P['width'] * 0.92 * math.sin(a)
        pts += [(x, y, z), (x, y, z + P['height'] * (1.0 if i in (3, 4, 5) else 0.72))]
    for i in range(n - 1):
        faces.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
    band = ctx.add('hachigane', shell(pts, faces), [ctx.mat('card_charcoal'), ctx.mat('seam_shadow')],
                   thickness=0.008)
    ctx.add('hachigane_spine', box(0, -P['width'] * 0.90, z + P['height'] * 0.55, 0.018, 0.03, 0.075,
                                   rot=(0.3, 0, 0)), [ctx.mat('card_charcoal'), ctx.mat('seam_shadow')],
            thickness=0.006)
    return band


@part('mask_angular', slot='face', socket='face', bone='head', size=(0.9, 1.12), material='washi_natural',
      length=0.205, width=0.134, ridge=0.046, slit=0.014, tags=('reference',),
      proportions=('slim', 'standard', 'broad'))
def mask_angular(ctx, P, rnd):
    """Angular folded face: a nose ridge down the centre, flat cheek planes, a cut chin and two eye slits."""
    S = ctx.socket
    width, length, ridge = P['width'], P['length'], P['ridge']
    if not 0 < P['slit'] < length * 0.12:
        raise ValueError("Mask slit must be positive and narrower than 12 percent of the mask height.")
    front = S.y - ridge

    def point(x, y, z):
        return (x * width, front + y * ridge, S.z + z * length)

    for sign, side in ((1, 'L'), (-1, 'R')):
        def mirror(points):
            points = [(sign * x, y, z) for x, y, z in points]
            return points if sign > 0 else points[::-1]

        crown, temple = point(0, 1.35, 0.48), point(0.91, 1.65, 0.23)
        bridge, tip = point(0, 0.06, 0.18), point(0, -0.42, -0.17)
        jaw, chin = point(0.55, 0.64, -0.34), point(0, 0.32, -0.58)
        ear, cheek = point(0.86, 1.60, -0.15), point(0.62, 0.38, -0.18)
        inner, outer = Vector(point(0.16, 0.0, 0.22)), Vector(point(0.81, 1.02, 0.055))
        slit = Vector((0, 0, P['slit']))
        below, lower_outer = inner - slit, outer - slit * 0.62
        sheet = ctx.mat(P['material'])
        shade = ctx.mat('washi_shade')
        paper = bmesh.new()
        for pts in ((crown, temple, outer, inner, bridge), (temple, ear, lower_outer, outer),
                    (bridge, below, cheek, tip), (below, lower_outer, ear, cheek),
                    (tip, cheek, jaw, chin), (cheek, ear, jaw)):
            join(paper, panel(mirror(pts)))
        ctx.add('mask_' + side, paper, [sheet, shade], thickness=0.0028)
        # This is a layer behind a real opening between the two folded sheets.
        recess = Vector((0, 0.005, 0))
        opening = [inner + recess, outer + recess, lower_outer + recess, below + recess]
        ctx.add('eye_' + side, panel(mirror(opening)),
                [ctx.emit('eye', ctx.glow[1] * 3.0)], thickness=0.0)
        side_panel = [temple, point(0.66, 3.4, 0.32), point(0.53, 3.1, -0.26), jaw, ear]
        ctx.add('mask_side_' + side, panel(mirror(side_panel), bulge=0.003, normal=(sign, 0, 0)),
                [shade, ctx.mat('seam_shadow')], thickness=0.0035)


@part('mask_long', slot='face', socket='face', bone='head', size=(0.9, 1.12), material='washi_bleached',
      length=0.235, width=0.112, ridge=0.052, slit=0.012, proportions=('slim', 'standard'))
def mask_long(ctx, P, rnd):
    """A longer, narrower mask with a deeper nose ridge: the gaunt ronin read."""
    return mask_angular(ctx, P, rnd)


@part('hair_spikes', slot='hair', socket='hair_back', bone='head', size=(0.85, 1.15), material='washi_shade',
      blades=5, length=0.17, proportions=('slim', 'standard', 'broad'))
def hair_spikes(ctx, P, rnd):
    """Folded hair: flat paper blades fanning back off the crown, each one a single crease."""
    S = ctx.socket
    bm = bmesh.new()
    for k in range(int(P['blades'])):
        a = (k - (P['blades'] - 1) / 2) * 0.42
        L = P['length'] * (1.0 - 0.13 * abs(k - (P['blades'] - 1) / 2))
        root = Vector((math.sin(a) * 0.065, S.y - 0.01, S.z + 0.025))
        tip = root + Vector((math.sin(a) * 0.5, 0.80, -0.30)).normalized() * L
        w = 0.026
        side = Vector((math.cos(a), -math.sin(a) * 0.3, 0)) * w
        up = Vector((0, 0.25, 0.9)).normalized() * w * 0.8
        join(bm, shell([tuple(root - side), tuple(root + side), tuple(tip), tuple(root + up)],
                       [(0, 1, 2), (0, 2, 3), (1, 3, 2), (0, 3, 1)]))
    return ctx.add('hair', bm, [ctx.mat('washi_shade'), ctx.mat('seam_shadow')], thickness=0.004)


@part('topknot', slot='hair', socket='hair_back', bone='head', size=(0.85, 1.15), material='card_indigo',
      length=0.13, proportions=('standard', 'broad'), tags=('armour',))
def topknot(ctx, P, rnd):
    """A tight folded chonmage: a rolled card cylinder lying forward over the crown."""
    S = ctx.socket
    bm = bmesh.new()
    skin_rings(bm, [poly_ring(6, 0.030, 0, cx=0, cy=0), poly_ring(6, 0.034, P['length'] * 0.55),
                    poly_ring(6, 0.022, P['length'])], cap_first=True, cap_last=True)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(-1.15, 3, 'X'))
    bmesh.ops.translate(bm, vec=(0, S.y - 0.02, S.z + 0.045), verts=bm.verts)
    return ctx.add('topknot', bm, [ctx.mat('card_indigo'), ctx.mat('seam_shadow')], thickness=0.005)


@part('hair_ribbon_bun', slot='hair', socket='hair_back', bone='head', material='card_charcoal')
def hair_ribbon_bun(ctx, P, rnd):
    """A folded knot with layered paper ribbons hanging down the back of the neck."""
    S = ctx.socket
    bun = shell([(0, .038, S.z + .11), (-.075, .099, S.z + .087), (-.053, .167, S.z + .031),
                 (.054, .166, S.z + .030), (.074, .095, S.z + .083), (0, .076, S.z - .010)],
                [(0, 1, 2), (0, 2, 3), (0, 3, 4), (1, 5, 2), (2, 5, 3), (3, 5, 4)])
    ob = ctx.add('ribbon_bun', bun, [ctx.mat(P['material']), ctx.mat('washi_shade')], thickness=.003)
    for sign in (-1, 1):
        rows = [[(sign * .020, .119, S.z + .038), (sign * .048, .136, S.z + .025)],
                [(sign * .041, .145, S.z - .020), (sign * .078, .144, S.z - .055)],
                [(sign * .074, .107, S.z - .139), (sign * .121, .112, S.z - .096)]]
        ctx.add(f'hair_ribbon_{sign}', folded_sheet(rows, flip=sign > 0),
                [ctx.mat('washi_vermilion'), ctx.mat('washi_shade')], thickness=.002)
    return ob


@part('neck_column', slot='neck', socket='neck', bone='neck', size=(0.9, 1.1), material='washi_shade',
      radius=0.050, proportions=('slim', 'standard', 'broad'))
def neck_column(ctx, P, rnd):
    """The folded neck: a short five-sided column, deliberately dark so the collar gap glows around it."""
    S = ctx.socket
    bm = bmesh.new()
    skin_rings(bm, [poly_ring(5, P['radius'] * 1.40, S.z - 0.095),
                    poly_ring(5, P['radius'] * 1.1, S.z - 0.018, cy=-0.012),
                    poly_ring(5, P['radius'] * 0.92, S.z + 0.065, cy=-0.034)])
    return ctx.add('neck', bm, [ctx.mat('washi_shade', glow=True), ctx.mat('seam_shadow')], thickness=0.005)


# =========================================================================== PARTS: body
@part('kimono_layered', slot='torso', socket='chest', bone='torso', bones=['torso', 'upper'], rigid=False,
      size=(0.9, 1.15), material='washi_natural', shoulder=0.250, chest=0.205, waist=0.168, depth=0.56,
      tags=('reference',), proportions=('slim', 'standard', 'broad'))

def kimono_layered(ctx, P, rnd):
    """Wrap the jacket over the shoulders as one folded sheet, open at the neck and waist."""
    w, c, sh = P['waist'], P['chest'], P['shoulder']
    depth = P['depth']
    phase = math.pi / 2
    rows = [
        poly_ring(12, w * .94, .889, sy=depth * 1.1, phase=phase, flute=.04),
        poly_ring(12, w, 1.025, sy=depth * 1.2, phase=phase, flute=.12),
        poly_ring(12, c, 1.20, sy=depth * 1.30, phase=phase, flute=.12, front_pull=.018),
        poly_ring(12, sh, 1.365, sy=depth * .94, phase=phase, flute=.075, front_pull=.014),
        poly_ring(12, .111, 1.436, sy=.79, phase=phase, flute=.055),
    ]
    rows[-1] = [(x, y, z + (y * .80 if y < 0 else y * .30)) for x, y, z in rows[-1]]
    rows[-2] = [(x, y, z - .035 * abs(x) / sh + .050 * max(y, 0)) for x, y, z in rows[-2]]
    body = ctx.add('kimono_body', folded_sheet(rows, closed=True),
                   [ctx.mat(P['material']), ctx.mat('washi_shade')], thickness=.0034)
    # A dim warm liner behind the open neckline, independent of the paper's base color.
    ctx.add('kimono_neck_liner',
            panel([(-.048, -.077, 1.442), (.048, -.077, 1.442), (.023, -.133, 1.286), (-.022, -.133, 1.273)],
                  bulge=-.004),
            [ctx.mat('washi_shade', color=(.43, .27, .145), glow=True)], thickness=.0013)
    return body

@part('kimono_plain', slot='torso', socket='chest', bone='torso', bones=['torso', 'upper'], rigid=False,
      size=(0.9, 1.15), material='card_indigo', shoulder=0.285, chest=0.225, waist=0.17, depth=0.60,
      proportions=('standard', 'broad'), tags=('armour',))
def kimono_plain(ctx, P, rnd):
    """A tighter, broader under-kimono of heavy card: the body an armoured warrior straps plates onto."""
    return kimono_layered(ctx, P, rnd)


@part('eri_crossed', slot='collar', socket='collar', bone='upper', size=(0.9, 1.12), material='washi_bleached',
      width=0.105, drop=0.235, tags=('reference',), proportions=('slim', 'standard', 'broad'))

def eri_crossed(ctx, P, rnd):
    """Wrap each continuous folded lapel from nape to waist, with the left overlapping the right."""
    width = P['width']
    bottom = 1.18 - P['drop'] + .072
    for tag, side, lift in (('under', -1, 0.0), ('over', 1, .016)):
        spine = [
            ((side * .007, .084, 1.450), (side * .64, .35, -.82)),
            ((side * .054, .045, 1.493), (side * .78, .30, -.62)),
            ((side * .064, -.021, 1.490), (side * .86, -.05, -.64)),
            ((side * .044, -.101 - lift, 1.404), (side * .86, .12, -.46)),
            ((-side * .011, -.155 - lift, 1.241), (side * .86, .06, -.44)),
            ((-side * .095, -.142 - lift, bottom + .044), (side * .90, .07, -.37)),
        ]
        rows = []
        for point, outward in spine:
            p, tangent = Vector(point), Vector(outward).normalized()
            fold = Vector((0, -.008 if point[1] < 0 else .008, .005))
            rows.append([p, p + tangent * width * .28 + fold, p + tangent * width])
        key = P['material'] if tag == 'over' else 'washi_shade'
        ob = ctx.add(f'eri_{tag}', folded_sheet(rows, flip=(side < 0)),
                     [ctx.mat(key), ctx.mat('washi_shade')], thickness=.0030)
    return ob

@part('eri_narrow', slot='collar', socket='collar', bone='upper', size=(0.9, 1.12), material='card_indigo',
      width=0.055, drop=0.215, proportions=('standard', 'broad'), tags=('armour',))
def eri_narrow(ctx, P, rnd):
    """A narrow dark collar that disappears under armour, still crossed left over right."""
    return eri_crossed(ctx, P, rnd)


@part('obi_knot', slot='obi', socket='obi', bone='torso', size=(0.9, 1.1), material='washi_shade',
      height=0.125, knot=0.085, cord=True, tags=('reference',), proportions=('slim', 'standard', 'broad'))
def obi_knot(ctx, P, rnd):
    """The sash: a wrapped band of card, a folded knot on the left hip and a thin cord over it."""
    hz = REST['torso'][2]
    h = P['height']
    bm = bmesh.new()
    skin_rings(bm, [poly_ring(7, 0.188, hz + 0.015, flute=0.015, sy=0.62, phase=0.45),
                    poly_ring(7, 0.200, hz + 0.015 + h * 0.5, flute=0.02, sy=0.62, phase=0.45),
                    poly_ring(7, 0.186, hz + 0.015 + h, flute=0.015, sy=0.62, phase=0.45)])
    band = ctx.add('obi', bm, [ctx.mat('washi_shade'), ctx.mat('seam_shadow')], thickness=0.010)
    # a second wrap, offset, with a shadow slot: the reference's obi is clearly two passes of one strip
    bm2 = bmesh.new()
    skin_rings(bm2, [poly_ring(7, 0.197, hz + 0.030, flute=0.012, sy=0.615, phase=0.45),
                     poly_ring(7, 0.203, hz + 0.030 + h * 0.46, flute=0.012, sy=0.615, phase=0.45)])
    ctx.add('obi_wrap2', bm2, [ctx.mat('washi_natural'), ctx.mat('seam_shadow')], thickness=0.008)
    k = P['knot']
    ctx.add('obi_knot', box(0.175, -0.055, hz + h * 0.5, k, k * 0.55, k * 0.8, rot=(0, 0.25, -0.35)),
            [ctx.mat('washi_shade'), ctx.mat('seam_shadow')], thickness=0.008)
    ctx.add('obi_knot_tail', box(0.195, -0.075, hz - 0.03, 0.045, 0.02, 0.11, rot=(0.12, 0.1, -0.2)),
            [ctx.mat('washi_natural'), ctx.mat('seam_shadow')], thickness=0.005)
    if P['cord']:
        cord = bmesh.new()
        rings = [poly_ring(7, 0.206 + 0.004 * math.sin(i), hz + h * 0.74 + 0.012 * math.sin(i * 1.3),
                           flute=0.01, sy=0.68, phase=0.45) for i in range(2)]
        skin_rings(cord, rings)
        ctx.add('obi_cord', cord, [ctx.mat('card_indigo'), ctx.mat('seam_shadow')], thickness=0.009)
    return band


@part('obi_plain', slot='obi', socket='obi', bone='torso', size=(0.9, 1.1), material='card_charcoal',
      height=0.085, knot=0.06, cord=False, proportions=('standard', 'broad'), tags=('armour',))
def obi_plain(ctx, P, rnd):
    """A flat battle sash with no show knot: the armoured warrior's belt."""
    return obi_knot(ctx, P, rnd)


# =========================================================================== PARTS: arms
@part('sleeve_upper_folded', slot='sleeve_upper', socket=['shoulder.L', 'shoulder.R'], bone=None,
      size=(0.9, 1.15), material='washi_natural', radius=0.085, flare=1.22,
      proportions=('slim', 'standard', 'broad'))

def sleeve_upper_folded(ctx, P, rnd):
    """Creased upper sleeve tapers into the elbow, with an angled paper shoulder edge."""
    S, sg = ctx.socket, ctx.side
    r = P['radius']
    rows = [
        poly_ring(10, r * P['flare'], S.z + .055, cx=S.x - sg * .034, phase=.70, flute=.07, sy=.92),
        poly_ring(10, r * 1.16, S.z - .030, cx=S.x + sg * .012, cy=-.010, phase=.70, flute=.14, sy=1.03),
        poly_ring(10, r * 1.04, S.z - .150, cx=S.x + sg * .013, cy=-.024, phase=.70, flute=.13),
        poly_ring(10, r * .90, S.z - .331, cx=S.x - sg * .002, phase=.70, flute=.10),
    ]
    rows[0] = [(x, y, z - .036 * max(0.0, sg * (x - S.x) / r)) for x, y, z in rows[0]]
    return ctx.add(f'sleeve_upper_{"L" if sg > 0 else "R"}', folded_sheet(rows, closed=True, flip=True),
                   [ctx.mat(P['material']), ctx.mat('washi_shade')], thickness=.0027)

@part('kote_narrow', slot='sleeve_upper', socket=['shoulder.L', 'shoulder.R'], bone=None, size=(0.9, 1.1),
      material='card_indigo', radius=0.068, flare=1.05, proportions=('standard', 'broad'), tags=('armour',))
def kote_narrow(ctx, P, rnd):
    """A tight armoured sleeve: no flare, so the shoulder plate reads instead."""
    return sleeve_upper_folded(ctx, P, rnd)


@part('tamoto_wide', slot='sleeve_hanging', socket=['elbow.L', 'elbow.R'], rigid=False,
      bones=['lE', 'lS', 'lT'], size=(0.85, 1.2), material='washi_bleached',
      drop=0.40, width=0.150, mouth=0.125, tags=('reference',), proportions=('slim', 'standard', 'broad'))

def tamoto_wide(ctx, P, rnd):
    """Taper a pleated sleeve into a diagonal opening with a pointed lower fold."""
    S, sign = ctx.socket, ctx.side
    drop, width, depth = P['drop'], P['width'], P['mouth']
    # Start the wrap on the inside of the arm, so the seam is hidden by the elbow.
    profile = [(-.57, .24), (-.58, -.39), (-.22, -.80), (.18, -.74), (.49, -1.00),
               (.77, -.52), (.71, -.12), (.91, .26), (.57, .77), (.04, .79), (-.30, .66)]
    roll = [.22, .19, .09, -.08, -.29, -.14, .04, .11, .24, .18, .16]
    rows = []
    for t, sx, sy, shift, turn in ((0, .92, .84, -.05, 0), (.26, 1.04, .94, .06, -.018),
                                  (.62, .98, 1.00, .15, -.023), (1, .65, .84, .26, -.045)):
        rows.append([(S.x + sign * (u * width * sx + width * shift), v * depth * sy + turn,
                      S.z + .132 - (drop + .032) * t + roll[i] * drop * (.30 + .70 * t))
                     for i, (u, v) in enumerate(profile)])
    side = 'L' if sign > 0 else 'R'
    ob = ctx.add(f'tamoto_{side}', folded_sheet(rows, closed=True, flip=sign > 0),
                 [ctx.mat(P['material']), ctx.mat('washi_shade')], thickness=.0028)
    # Small source set back inside the lower opening so the rim itself stays paper-colored.
    ctx.add(f'tamoto_glow_{side}',
            box(S.x + sign * width * .27, -.025, S.z + .146 - drop, width * .48, depth * 1.06, .009),
            [ctx.emit('sleeve', 1.65)], thickness=0.0, to_camera=False)
    return ob

@part('tamoto_narrow', slot='sleeve_hanging', socket=['elbow.L', 'elbow.R'], rigid=False,
      bones=['lE', 'lS', 'lT'], size=(0.85, 1.2), material='card_indigo',
      drop=0.17, width=0.075, mouth=0.07, proportions=('standard', 'broad'), tags=('armour',))
def tamoto_narrow(ctx, P, rnd):
    """A short cut-down sleeve for fighting: the same folded bag, half the drop."""
    return tamoto_wide(ctx, P, rnd)


@part('forearm_folded', slot='forearm', socket=['elbow.L', 'elbow.R'], bone=None, size=(0.9, 1.1),
      material='washi_natural', radius=0.062, proportions=('slim', 'standard', 'broad'))
def forearm_folded(ctx, P, rnd):
    """Forearm sleeve: a narrow folded tube that reaches up INSIDE the hanging sleeve (no gap at the elbow)."""
    S, sg = ctx.socket, ctx.side
    r = P['radius']
    bm = bmesh.new()
    skin_rings(bm, [poly_ring(5, r * 1.20, S.z + 0.145, cx=S.x, phase=0.6),
                    poly_ring(5, r, S.z - 0.14, cx=S.x, phase=0.6),
                    poly_ring(5, r * 0.88, S.z - 0.285, cx=S.x, phase=0.6)])
    return ctx.add(f'forearm_{"L" if sg > 0 else "R"}', bm,
                   [ctx.mat(P['material']), ctx.mat('washi_shade')], thickness=0.005)


@part('kote_plated', slot='forearm', socket=['elbow.L', 'elbow.R'], bone=None, size=(0.9, 1.1),
      material='card_charcoal', radius=0.060, plates=3, proportions=('standard', 'broad'), tags=('armour',))
def kote_plated(ctx, P, rnd):
    """Armoured forearm: the folded tube plus three lapped card plates down the outside."""
    S, sg = ctx.socket, ctx.side
    forearm_folded(ctx, P, rnd)
    last = None
    for k in range(int(P['plates'])):
        z = S.z - 0.02 - k * 0.075
        last = ctx.add(f'kote_plate_{k}_{"L" if sg > 0 else "R"}',
                       box(S.x + sg * 0.030, -0.012, z, 0.055, 0.075, 0.062, rot=(0.0, sg * 0.5, 0)),
                       [ctx.mat('card_charcoal'), ctx.mat('seam_shadow')], thickness=0.007)
    return last


@part('hand_folded', slot='hand', socket=['hand.L', 'hand.R'], bone=None, size=(0.9, 1.1),
      material='washi_natural', fingers=4, length=0.095, proportions=('slim', 'standard', 'broad'))
def hand_folded(ctx, P, rnd):
    """Folded-finger hand: ONE sheet — a creased palm with four blades folded out of its lower edge."""
    S, sg = ctx.socket, ctx.side
    x, z = S.x, S.z
    L = P['length']
    # the palm: a single plate, bowed slightly outward, hanging from the wrist
    t0, t1 = (x - sg * 0.010, -0.032, z + 0.028), (x + sg * 0.012, 0.032, z + 0.028)
    b0, b1 = (x - sg * 0.016, -0.038, z - 0.038), (x + sg * 0.016, 0.038, z - 0.038)
    mid = ((t0[0] + t1[0]) / 2 + sg * 0.012, 0.0, (t0[2] + b0[2]) / 2)     # the crease down the palm
    pts = [t0, t1, b1, b0, mid]
    F = [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)]
    n = int(P['fingers'])
    for k in range(n):
        u0, u1 = k / n + 0.03, (k + 1) / n - 0.03
        def on_edge(u):
            return tuple(b0[i] + (b1[i] - b0[i]) * u for i in range(3))
        r0, r1 = on_edge(u0), on_edge(u1)
        curl = L * (1.0 - 0.12 * abs(k - (n - 1) / 2))
        joint = Vector(r0).lerp(Vector(r1), 0.5)
        tip = joint + Vector((-sg * 0.025, 0.0, -curl * 0.72))
        half = (Vector(r1) - Vector(r0)) * 0.34
        p0, p1 = tuple(tip - half), tuple(tip + half)
        knuckle = (0.5 * (r0[0] + r1[0]) + sg * 0.011, 0.5 * (r0[1] + r1[1]), 0.5 * (r0[2] + r1[2]) - curl * 0.42)
        i = len(pts)
        pts += [r0, r1, p1, p0, knuckle]
        F += [(i, i + 1, i + 4), (i + 1, i + 2, i + 4), (i + 2, i + 3, i + 4), (i + 3, i, i + 4)]
    # the thumb: one more blade folded off the front edge of the palm, laid across
    th0 = (x - sg * 0.004, -0.040, z + 0.006)
    th1 = (x + sg * 0.016, -0.044, z - 0.012)
    th2 = (x + sg * 0.040, -0.052, z - 0.058)
    i = len(pts)
    pts += [th0, th1, th2, (x + sg * 0.030, -0.030, z - 0.050)]
    F += [(i, i + 1, i + 2, i + 3)]
    return ctx.add(f'hand_{"L" if sg > 0 else "R"}', shell(pts, F),
                   [ctx.mat('washi_natural', glow=True), ctx.mat('washi_shade')], thickness=0.005)


# =========================================================================== PARTS: legs
@part('hakama_pleated', slot='thigh', socket=['hip.L', 'hip.R'], rigid=False, bones=['lthigh', 'hips'],
      size=(0.85, 1.2), material='washi_natural', pleats=12, top=0.118, bottom=0.132, flute=0.26,
      tags=('reference', 'legs'), proportions=('slim', 'standard', 'broad'))
def hakama_pleated(ctx, P, rnd):
    """A REAL hakama leg, upper half: a deeply pleated tube around its own thigh bone (the models had no legs)."""
    S, sg = ctx.socket, ctx.side
    n = int(P['pleats'])
    z0, z1 = S.z + 0.045, REST['lshin'][2] - 0.032
    rows = [poly_ring(n, P['top'] * 0.98, z0, cx=S.x + sg * 0.030, flute=P['flute'] * 0.55, phase=0.2),
                    poly_ring(n, P['top'], z0 - 0.16, cx=S.x + sg * 0.034, flute=P['flute'], lift=0.008, phase=0.2),
                    poly_ring(n, P['bottom'], z1, cx=S.x + sg * 0.038, flute=P['flute'], lift=0.010, phase=0.2)]
    bm = folded_sheet(rows, closed=True, flip=True)
    return ctx.add(f'hakama_thigh_{"L" if sg > 0 else "R"}', bm,
                   [ctx.mat(P['material'], glow=True), ctx.mat('washi_shade')], thickness=0.0037)


@part('hakama_shin_pleated', slot='shin', socket=['knee.L', 'knee.R'], rigid=False, bones=['lshin', 'lthigh'],
      size=(0.85, 1.2), material='washi_natural', pleats=12, top=0.132, hem=0.145, flute=0.26, hem_tilt=0.050,
      tags=('reference', 'legs'), proportions=('slim', 'standard', 'broad'))
def hakama_shin_pleated(ctx, P, rnd):
    """The hakama leg below the knee: wider, with a tilted hem that catches the light like folded card."""
    S, sg = ctx.socket, ctx.side
    n = int(P['pleats'])
    z0, z1 = S.z + 0.02, REST['lfoot'][2] + 0.055
    bm = bmesh.new()
    rings = [poly_ring(n, P['top'], z0, cx=S.x + sg * 0.038, flute=P['flute'], lift=0.010, phase=0.2),
             poly_ring(n, P['hem'] * 0.94, z0 - 0.22, cx=S.x + sg * 0.040, flute=P['flute'], lift=0.012, phase=0.2),
             poly_ring(n, P['hem'], z1, cx=S.x + sg * 0.042, flute=P['flute'] * 1.1, lift=0.014, phase=0.2)]
    for i, p in enumerate(rings[-1]):                                 # tilt the hem: front corner drops
        a = 2 * math.pi * i / n + 0.2
        rings[-1][i] = (p[0], p[1], p[2] + P['hem_tilt'] * math.cos(a))
    bm = folded_sheet(rings, closed=True, flip=True)
    return ctx.add(f'hakama_shin_{"L" if sg > 0 else "R"}', bm,
                   [ctx.mat(P['material'], glow=True), ctx.mat('washi_shade')], thickness=0.0037)


@part('hakama_plain', slot='thigh', socket=['hip.L', 'hip.R'], rigid=False, bones=['lthigh', 'hips'],
      size=(0.85, 1.2), material='card_indigo', pleats=6, top=0.145, bottom=0.165, flute=0.05,
      proportions=('standard', 'broad'), tags=('armour', 'legs'))
def hakama_plain(ctx, P, rnd):
    """A plain narrow trouser leg of dark card: for armour, where the pleats would fight the plates."""
    return hakama_pleated(ctx, P, rnd)


@part('hakama_shin_plain', slot='shin', socket=['knee.L', 'knee.R'], rigid=False, bones=['lshin', 'lthigh'],
      size=(0.85, 1.2), material='card_indigo', pleats=6, top=0.165, hem=0.150, flute=0.05, hem_tilt=0.012,
      proportions=('standard', 'broad'), tags=('armour', 'legs'))
def hakama_shin_plain(ctx, P, rnd):
    """The plain leg below the knee: tucked into the boot, no hem flare."""
    return hakama_shin_pleated(ctx, P, rnd)


@part('hakama_apron', slot='armor', socket='obi', bone='hakama', size=(0.9, 1.15), layer=52,
      material='washi_natural', pleats=7, drop=0.38, width=0.118, top=-0.055, tags=('reference', 'legs'),
      proportions=('slim', 'standard', 'broad'))
def hakama_apron(ctx, P, rnd):
    """The hakama's front apron and back koshiita board: the two flat sheets that hang BETWEEN the legs."""
    hz = REST['torso'][2]
    n = int(P['pleats'])
    for tag, y, sheet in (('front', -1, 'washi_natural'), ('back', 1, 'washi_shade')):
        pts = []
        for i in range(n):
            t = i / (n - 1) - 0.5
            pts.append((t * 2 * P['width'] * 0.80, y * (0.112 + 0.010 * math.cos(t * 6)), hz + P['top']))
        for i in reversed(range(n)):
            t = i / (n - 1) - 0.5
            pts.append((t * 2 * P['width'], y * (0.140 + 0.014 * math.cos(t * 6)), hz - P['drop']))
        bm = panel(pts)
        creases(bm, inset=0.006, depth=-0.004, share=1.0, rnd=rnd)
        ob = ctx.add(f'hakama_apron_{tag}', bm, [ctx.mat(sheet, glow=True), ctx.mat('washi_shade')],
                     thickness=0.008)
        if tag == 'back':                            # koshiita: the stiff folded board at the small of the back
            ctx.add('koshiita', box(0, 0.135, hz + 0.075, 0.185, 0.03, 0.075, rot=(0.18, 0, 0)),
                    [ctx.mat('card_indigo'), ctx.mat('seam_shadow')], thickness=0.009)
    return ob


@part('tabi_zori', slot='foot', socket=['ankle.L', 'ankle.R'], bone=None, size=(0.9, 1.15),
      material='washi_bleached', length=0.26, tags=('reference',), proportions=('slim', 'standard', 'broad'))
def tabi_zori(ctx, P, rnd):
    """Pointed tabi over a flat zori sole: a folded wedge with a split toe and a dark sole plate under it."""
    S, sg = ctx.socket, ctx.side
    x, L = S.x, P['length']
    heel, toe = 0.075, -L + 0.075
    pts = [(x - 0.050, heel, 0.004), (x + 0.050, heel, 0.004),                      # 0 1 heel sole
           (x + 0.044, toe + 0.03, 0.004), (x - 0.044, toe + 0.03, 0.004),          # 2 3 toe sole
           (x - 0.046, heel - 0.01, 0.092), (x + 0.046, heel - 0.01, 0.092),        # 4 5 ankle top
           (x + 0.020, toe + 0.055, 0.036), (x - 0.020, toe + 0.055, 0.036),        # 6 7 instep
           (x + 0.006, toe, 0.012), (x - 0.006, toe, 0.012)]                        # 8 9 the split toe point
    F = [(0, 1, 2, 3), (0, 3, 7, 4), (1, 5, 6, 2), (4, 7, 6, 5), (3, 2, 8, 9), (2, 6, 8), (3, 9, 7),
         (7, 9, 8, 6), (0, 4, 5, 1)]
    bm = shell(pts, F)
    bmesh.ops.translate(bm, vec=(0, 0, S.z), verts=bm.verts)
    ob = ctx.add(f'tabi_{"L" if sg > 0 else "R"}', bm,
                 [ctx.mat(P.get('material', 'washi_bleached')), ctx.mat('washi_shade')], thickness=0.005)
    ctx.add(f'zori_{"L" if sg > 0 else "R"}',
            panel([(x - 0.058, heel + 0.015, S.z - 0.004), (x + 0.058, heel + 0.015, S.z - 0.004),
                   (x + 0.050, toe + 0.01, S.z - 0.004), (x - 0.050, toe + 0.01, S.z - 0.004)]),
            [ctx.mat('card_indigo'), ctx.mat('seam_shadow')], thickness=0.010)
    return ob


@part('boot_plated', slot='foot', socket=['ankle.L', 'ankle.R'], bone=None, size=(0.9, 1.15),
      material='card_charcoal', length=0.27, proportions=('standard', 'broad'), tags=('armour',))
def boot_plated(ctx, P, rnd):
    """A heavy folded war boot: the same wedge in charcoal card with a shin plate above it."""
    S, sg = ctx.socket, ctx.side
    ob = tabi_zori(ctx, dict(P, material='card_charcoal'), rnd)
    ctx.add(f'suneate_{"L" if sg > 0 else "R"}',
            box(S.x, -0.055, S.z + 0.16, 0.085, 0.035, 0.17, rot=(-0.08, 0, 0)),
            [ctx.mat('card_charcoal'), ctx.mat('seam_shadow')], thickness=0.008)
    return ob


# =========================================================================== PARTS: armour and accessories
@part('sode_lamellar', slot='armor', socket=['shoulder.L', 'shoulder.R'], bone=None, size=(0.85, 1.2),
      material='card_charcoal', rows=4, cols=5, plate=0.048, proportions=('standard', 'broad'),
      tags=('armour',))
def sode_lamellar(ctx, P, rnd):
    """Sode: rows of lapped card scales over the shoulder, each row overhanging the one below."""
    S, sg = ctx.socket, ctx.side
    last = None
    for row in range(int(P['rows'])):
        z = S.z + 0.035 - row * (P['plate'] * 0.92)
        r = P['plate'] * (1.0 + row * 0.10)
        for k in range(int(P['cols'])):
            t = (k / (P['cols'] - 1) - 0.5) * 2
            x = S.x + sg * (.067 + row * .011)
            y = t * r * 1.9
            plate = P['plate']
            coords = [(x - sg * .007, y - r * .44, z), (x + sg * .004, y + r * .44, z + .005),
                      (x + sg * .016, y + r * .41, z - plate * .60),
                      (x + sg * .011, y + r * .24, z - plate * .93),
                      (x + sg * .012, y - r * .35, z - plate * .92)]
            if sg < 0:
                coords.reverse()
            last = ctx.add(f'sode_{row}_{k}_{"L" if sg > 0 else "R"}',
                           panel(coords, bulge=.004, normal=(sg, 0, 0)),
                           [ctx.mat(P['material']), ctx.mat('washi_shade')], thickness=.0035)
    return last


@part('do_plates', slot='armor', socket='chest', bone='upper', size=(0.85, 1.15), layer=62,
      material='card_charcoal', rows=4, proportions=('standard', 'broad'), tags=('armour',))
def do_plates(ctx, P, rnd):
    """Wrap lamellar rows across the ribs, with thin folded lower lips."""
    cz = REST['upper'][2]
    last = None
    for row in range(int(P['rows'])):
        z = cz + .196 - row * .064
        w = .226 - row * .010
        ribs = [-1, -.79, -.38, 0, .38, .79, 1]
        crown = [(t * w, -.233 + .086 * t * t, z + .018 * abs(t)) for t in ribs]
        fold = [(t * w * 1.018, -.248 + .098 * t * t, z - .049 + .007 * abs(t)) for t in ribs]
        lip = [(t * w * .97, -.239 + .092 * t * t, z - .070 + .010 * abs(t)) for t in ribs]
        last = ctx.add(f'do_{row}', folded_sheet([crown, fold, lip], flip=True),
                       [ctx.mat(P['material']), ctx.mat('washi_shade')], thickness=.0040)
    return last


@part('katana_sheathed', slot='accessory', socket=['hip_side.L', 'hip_side.R'], bone='torso', size=(0.9, 1.1),
      material='card_indigo', length=0.80, tilt=-14.0, swing=13.0, tsuka=0.22, proportions=('slim', 'standard', 'broad'))
def katana_sheathed(ctx, P, rnd):
    """The sword at the hip: a folded paper saya and tsuka in one line, mouth at the obi, tip low behind."""
    S, sg = ctx.socket, ctx.side
    mouth = Vector((S.x, S.y, S.z))
    tilt = (Matrix.Rotation(math.radians(P['tilt']), 3, 'X')
            @ Matrix.Rotation(math.radians(P['swing'] * sg), 3, 'Z'))
    last = None
    for nm, y0, y1, w, key in (('saya', 0.0, P['length'], 0.030, 'card_indigo'),
                               ('tsuka', -P['tsuka'], 0.0, 0.036, 'washi_shade')):
        bm = box(0, (y0 + y1) / 2, 0, w, y1 - y0, w * 0.82)
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=tilt)
        bmesh.ops.translate(bm, vec=mouth, verts=bm.verts)
        last = ctx.add(nm, bm, [ctx.mat(key), ctx.mat('seam_shadow')], thickness=0.004)
    bm = box(0, 0, 0, 0.082, 0.010, 0.082)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=tilt)
    bmesh.ops.translate(bm, vec=mouth, verts=bm.verts)
    ctx.add('tsuba', bm, [ctx.mat('card_charcoal'), ctx.mat('seam_shadow')], thickness=0.004)
    return last


@part('tassels', slot='accessory', socket='obi', bone='torso', size=(0.9, 1.1),
      material='washi_natural', count=2, proportions=('slim', 'standard', 'broad'))
def tassels(ctx, P, rnd):
    """Two folded paper tassels on cords from the obi knot: the small bit of motion in a still frame."""
    hz = REST['torso'][2]
    last = None
    for k in range(int(P['count'])):
        x = 0.040 + k * 0.058
        ctx.add(f'tassel_cord_{k}', box(x, -0.150, hz + 0.02 - k * 0.02, 0.005, 0.006, 0.085),
                [ctx.mat('card_indigo'), ctx.mat('seam_shadow')], thickness=0.0)
        bm = bmesh.new()
        skin_rings(bm, [poly_ring(5, 0.020, hz - 0.030 - k * 0.02, cx=x, cy=-0.150),
                        poly_ring(5, 0.006, hz - 0.115 - k * 0.02, cx=x, cy=-0.150)], cap_first=True)
        last = ctx.add(f'tassel_{k}', bm, [ctx.mat('washi_natural', glow=True), ctx.mat('washi_shade')],
                       thickness=0.004)
    return last


# =========================================================================== reporting
def describe(slots_only=False):
    out = ['SLOTS (what goes where, and what covers what)',
           f'{"slot":<16}{"layer":>6}  what it is']
    for s, (what, layer, _flex) in sorted(SLOTS.items(), key=lambda kv: kv[1][1]):
        out.append(f'{s:<16}{layer:>6}  {what}')
    if slots_only:
        return '\n'.join(out)
    out += ['', f'PARTS ({len(PARTS)} in the library)',
            f'{"part":<22}{"slot":<16}{"socket":<22}{"bind":<10}{"size":<12}{"material":<16}what it is']
    for name, p in sorted(PARTS.items(), key=lambda kv: (SLOTS[kv[1]['slot']][1], kv[0])):
        bind = 'rigid' if p['rigid'] else 'skin:%d' % max(len(p['bones']), 2)
        sock = ','.join(s.split('.')[0] for s in dict.fromkeys(s.split('.')[0] for s in p['socket']))
        if len(p['socket']) > 1:
            sock += ' L/R'
        out.append(f'{name:<22}{p["slot"]:<16}{sock:<22}{bind:<10}'
                   f'{"%.2f-%.2f" % p["size"]:<12}{p["material"]:<16}{p["doc"]}')
    out += ['', 'SOCKETS (attachment points in the rest pose: x, y, z metres → bone)']
    for s, d in SOCKETS.items():
        out.append(f'  {s:<14}({d["pos"][0]:+.3f}, {d["pos"][1]:+.3f}, {d["pos"][2]:.3f})  '
                   f'grows {d["grow"]:<6} bone {d["bone"]}')
    by_slot = {}
    for n, p in PARTS.items():
        by_slot.setdefault(p['slot'], []).append(n)
    thin = [s for s in ('hat', 'face', 'torso', 'sleeve_hanging', 'thigh', 'shin') if len(by_slot.get(s, [])) < 2]
    out += ['', 'variants per slot: ' + ', '.join(f'{s}={len(v)}' for s, v in sorted(by_slot.items()))]
    if thin:
        out.append('WARNING: important slots with fewer than 2 variants: ' + ', '.join(thin))
    return '\n'.join(out)


if __name__ == '__main__':
    print(describe(slots_only='--slots' in sys.argv))
