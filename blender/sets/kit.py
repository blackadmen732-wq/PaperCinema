"""SET KIT: reusable, procedural, seeded set pieces for Paper Cinema (Blender 4.5, Cycles).

A set is composed from pieces by a JSON file (library/sets/<name>.json, built by blender/sets/build_set.py).
Every piece is a function registered with @piece(name, **defaults): it receives a context (`ctx`), its params
(defaults merged with the JSON `params`) and a seeded random stream, and builds its geometry in LOCAL
coordinates (metres, Z up, the piece's front faces -Y). build_piece() places it with `pos` / `rot` / `scale`
under an empty named SET_<name>.

    import sys; sys.path.insert(0, 'blender/sets'); import kit
    ctx = kit.Ctx(bpy.context.scene, seed=1)
    kit.build_piece(ctx, {'kit': 'toro', 'name': 'lantern_L', 'pos': [-4, 2, 0], 'params': {'energy': 30}})

Look: realistic texture detail (stone grain, moss, grime, wood grain, plaster stains, tile lichen, AO, bump,
roughness variation; see the SET MATERIALS in blender/world/paper_materials.py) on geometry that stays in the
paper-craft family: flat facets (true-normal shading), folded edges, a faint washi-fibre bump everywhere.
All materials are procedural. List every piece and its parameters with:  python3 blender/sets/kit.py --list
"""
import math
import os
import random
import sys

try:
    import bmesh
    import bpy
    from mathutils import Euler, Matrix, Vector, noise
    HAVE_BPY = True
except ImportError:          # `python3 kit.py --list` outside Blender
    HAVE_BPY = False

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'world'))
if HAVE_BPY:
    import paper_materials as pm  # noqa: E402

KIT = {}


def piece(name, **defaults):
    """Register a set piece. Defaults double as the documented parameter list."""
    def deco(fn):
        KIT[name] = {'fn': fn, 'defaults': defaults, 'doc': (fn.__doc__ or '').strip()}
        return fn
    return deco


# =========================================================================== materials library
def _M():
    """Material recipes by key. JSON can override any keyword: "materials": {"plaster": {"color": [..]}}."""
    return {
        'stone': (pm.stone_material, dict()),
        'stone_dark': (pm.stone_material, dict(color=(0.13, 0.125, 0.115), color2=(0.24, 0.225, 0.20), moss=0.3)),
        'stone_mossy': (pm.stone_material, dict(color=(0.22, 0.21, 0.19), color2=(0.36, 0.34, 0.30), moss=0.85, grime=0.7)),
        'stone_dressed': (pm.stone_material, dict(color=(0.36, 0.35, 0.32), color2=(0.48, 0.46, 0.42), moss=0.15, grime=0.4, flecks=0.4)),
        'stone_lantern': (pm.stone_material, dict(color=(0.30, 0.29, 0.26), color2=(0.42, 0.40, 0.36), moss=0.6, grime=0.8, scale=2.5)),
        'backfill': (pm.stone_material, dict(color=(0.035, 0.033, 0.03), color2=(0.07, 0.065, 0.06), moss=0.0, grime=0.9, paper=0.0)),
        'plaster': (pm.plaster_material, dict()),
        'plaster_old': (pm.plaster_material, dict(color=(0.70, 0.66, 0.58), grime=0.9, cracks=0.7)),
        'plaster_earth': (pm.plaster_material, dict(color=(0.42, 0.31, 0.20), grime=0.4, cracks=0.2)),
        'wood': (pm.wood_material, dict()),
        'wood_dark': (pm.wood_material, dict(color=(0.045, 0.032, 0.025), color2=(0.02, 0.016, 0.013), rough=0.55, wear=0.35)),
        'wood_aged': (pm.wood_material, dict(color=(0.20, 0.18, 0.155), color2=(0.10, 0.09, 0.08), rough=0.85, wear=0.2)),
        'wood_light': (pm.wood_material, dict(color=(0.55, 0.40, 0.25), color2=(0.38, 0.25, 0.14), rough=0.55, wear=0.1)),
        'wood_floor': (pm.wood_material, dict(color=(0.36, 0.22, 0.12), color2=(0.20, 0.11, 0.055), polish=0.55, rough=0.42, wear=0.25)),
        'wood_floor_y': (pm.wood_material, dict(color=(0.36, 0.22, 0.12), color2=(0.20, 0.11, 0.055), polish=0.55, rough=0.42, wear=0.25, axis='Y')),
        'wood_post': (pm.wood_material, dict(color=(0.16, 0.095, 0.055), color2=(0.08, 0.045, 0.025), axis='Z', rough=0.55, wear=0.3)),
        'wood_dark_z': (pm.wood_material, dict(color=(0.045, 0.032, 0.025), color2=(0.02, 0.016, 0.013), axis='Z', rough=0.55, wear=0.35)),
        'tile': (pm.tile_material, dict()),
        'lacquer_red': (pm.lacquer_material, dict()),
        'lacquer_black': (pm.lacquer_material, dict(color=(0.018, 0.016, 0.015), under=(0.08, 0.05, 0.03), wear=0.2)),
        'shoji': (pm.shoji_material, dict()),
        'lantern_paper': (pm.shoji_material, dict(color=(0.95, 0.85, 0.65), translucency=0.75, glow=((1.0, 0.55, 0.2), 1.5), stains=0.2)),
        'tatami': (pm.tatami_material, dict()),
        'tatami_border': (pm.paper_material, dict(color=(0.02, 0.025, 0.04), translucency=0.0, fibre_scale=80, facet_var=0.02)),
        'gravel': (pm.gravel_material, dict()),
        'gravel_wet': (pm.gravel_material, dict(color=(0.22, 0.215, 0.20), wet=0.6)),
        'sand': (pm.gravel_material, dict(color=(0.50, 0.42, 0.31), scale=70.0)),
        'earth': (pm.earth_material, dict()),
        'forest_floor': (pm.earth_material, dict(color=(0.12, 0.09, 0.06), moss=0.6, leaves=0.5, leaf_color=(0.30, 0.25, 0.10))),
        'bamboo': (pm.bamboo_material, dict()),
        'bamboo_node': (pm.bamboo_material, dict(color=(0.22, 0.24, 0.08), age=0.7)),
        'bamboo_leaf': (pm.foliage_material, dict(color=(0.09, 0.14, 0.035), trans=(0.30, 0.42, 0.06), translucency=0.4)),
        'pine_needle': (pm.foliage_material, dict(color=(0.035, 0.06, 0.03), trans=(0.12, 0.2, 0.05), translucency=0.25)),
        'blossom': (pm.foliage_material, dict(color=(0.85, 0.55, 0.60), trans=(1.0, 0.62, 0.70), translucency=0.45, var=0.2)),
        'maple_red': (pm.foliage_material, dict(color=(0.45, 0.06, 0.02), trans=(0.9, 0.25, 0.05), translucency=0.4)),
        'bark': (pm.bark_material, dict()),
        'bark_cherry': (pm.bark_material, dict(color=(0.09, 0.055, 0.05), moss=0.35)),
        'iron': (pm.iron_material, dict()),
        'gold': (pm.gold_material, dict()),
        'window_glow': (pm.glow_window_material, dict()),
        'window_dark': (pm.paper_material, dict(color=(0.012, 0.011, 0.01), translucency=0.0, fibre_scale=20, facet_var=0.02)),
        'paper': (pm.paper_material, dict(color=(0.80, 0.76, 0.67), translucency=0.3, fibre_scale=60)),
        'cloth_dark': (pm.paper_material, dict(color=(0.03, 0.03, 0.035), translucency=0.0, fibre_scale=60)),
        'cloth_red': (pm.paper_material, dict(color=(0.35, 0.03, 0.02), translucency=0.2, fibre_scale=60)),
        'rain': (pm.rain_material, dict()),
        'ember': (pm.emission_material, dict(color=(1.0, 0.35, 0.08), strength=30.0)),
        'petal': (pm.foliage_material, dict(color=(0.92, 0.62, 0.68), trans=(1.0, 0.7, 0.75), translucency=0.5, var=0.15)),
        'dust': (pm.emission_material, dict(color=(1.0, 0.85, 0.6), strength=0.6)),
    }


# =========================================================================== context
class Ctx:
    """Shared state while a set is built: scene, target collection, seed, material cache, lights, clear zones."""

    def __init__(self, scene, collection=None, seed=1, materials=None):
        self.scene = scene
        if collection is None:
            collection = bpy.data.collections.new('SET')
            scene.collection.children.link(collection)
        self.coll = collection
        self.seed = seed
        self.overrides = materials or {}
        self._mats = {}
        self.root = None
        self.clear = []          # [(x, y, r)] world-space zones kept free of scattered props (fighter marks)
        self.lights = []
        self.info = {}

    def rng(self, *keys):
        return random.Random(':'.join(str(k) for k in (self.seed,) + keys))

    def mat(self, key):
        if key in self._mats:
            return self._mats[key]
        recipes = _M()
        base = key.split('#')[0]                 # 'stone#2' = a second copy of the stone recipe (own overrides)
        if base not in recipes:
            raise KeyError(f'unknown material {key!r}; known: {", ".join(sorted(recipes))}')
        fn, kw = recipes[base]
        kw = dict(kw)
        for k, v in self.overrides.get(key, {}).items():
            kw[k] = tuple(v) if isinstance(v, list) else v
        if 'color' in kw and fn is pm.emission_material:
            m = fn('SET_' + key, kw['color'], kw.get('strength', 1.0))
        else:
            m = fn('SET_' + key, **kw)
        self._mats[key] = m
        return m

    def link(self, ob, parent=True):
        self.coll.objects.link(ob)
        if parent and self.root is not None:
            ob.parent = self.root
        return ob

    def light(self, kind, loc, energy, color=(1, 1, 1), size=0.1, look=None, spot=None, name='light', blend=0.3):
        L = bpy.data.lights.new(name, kind)
        L.energy = energy
        L.color = tuple(color)[:3]
        if kind in ('POINT', 'SPOT'):
            L.shadow_soft_size = size
        elif kind == 'AREA':
            L.shape = 'RECTANGLE' if isinstance(size, (list, tuple)) else 'SQUARE'
            if isinstance(size, (list, tuple)):
                L.size, L.size_y = size
            else:
                L.size = size
        elif kind == 'SUN':
            L.angle = math.radians(size)
        if kind == 'SPOT':
            L.spot_size = math.radians(spot or 40)
            L.spot_blend = blend
        ob = bpy.data.objects.new(name, L)
        ob.location = Vector(loc)
        if look is not None:
            ob.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        self.link(ob)
        self.lights.append(ob)
        return ob

    def world_xy(self, local):
        """Local point -> world (uses the current piece root's matrix)."""
        if self.root is None:
            return Vector(local)
        return self.root.matrix_world @ Vector(local)

    def is_clear(self, local_xy, pad=0.0):
        w = self.world_xy((local_xy[0], local_xy[1], 0))
        return all(math.hypot(w.x - x, w.y - y) > r + pad for x, y, r in self.clear)


# =========================================================================== mesh builder
def _rot(r):
    if r is None:
        return Matrix.Identity(3)
    if isinstance(r, Matrix):
        return r.to_3x3()
    return Euler(tuple(math.radians(a) for a in r), 'XYZ').to_matrix()


def M4(loc=(0, 0, 0), rot=None, scale=(1, 1, 1)):
    return Matrix.LocRotScale(Vector(loc), _rot(rot), Vector(scale))


class MB:
    """Accumulates many parts into one mesh, with a material slot per key and a per-part random
    (`piece_rand` face attribute) so materials can vary stone by stone, plank by plank."""

    def __init__(self, ctx, name, rnd=None):
        self.ctx, self.name = ctx, name
        self.rnd = rnd or random.Random(name)
        self.bm = bmesh.new()
        self.pl = self.bm.faces.layers.float.new(pm.PIECE_ATTR)
        self.keys = []

    def mi(self, key):
        if key not in self.keys:
            self.keys.append(key)
        return self.keys.index(key)

    def tag(self, faces, key, pr=None):
        mi = self.mi(key)
        pr = self.rnd.random() if pr is None else pr
        for f in faces:
            f.material_index = mi
            f[self.pl] = pr
        return faces

    @staticmethod
    def faces_of(verts):
        return {f for v in verts for f in v.link_faces}

    def box(self, key, size, loc=(0, 0, 0), rot=None, pr=None, bevel=0.0, matrix=None):
        """Axis box of `size` centred on `loc`, optionally bevelled (folded edges catch the light)."""
        m = (matrix or Matrix.Identity(4)) @ M4(loc, rot, size)
        res = bmesh.ops.create_cube(self.bm, size=1.0, matrix=m)
        vs = res['verts']
        pr = self.rnd.random() if pr is None else pr
        faces = self.tag(self.faces_of(vs), key, pr)
        if bevel > 0:
            edges = list({e for v in vs for e in v.link_edges})
            out = bmesh.ops.bevel(self.bm, geom=list(vs) + edges, offset=bevel, segments=1, affect='EDGES', clamp_overlap=True)
            self.tag(set(out['faces']), key, pr)
        return faces

    def cyl(self, key, r1, r2, depth, segs=8, loc=(0, 0, 0), rot=None, pr=None, caps=True, matrix=None):
        m = (matrix or Matrix.Identity(4)) @ M4(loc, rot)
        res = bmesh.ops.create_cone(self.bm, cap_ends=caps, segments=segs, radius1=r1, radius2=r2, depth=depth, matrix=m)
        return self.tag(self.faces_of(res['verts']), key, pr)

    def poly(self, key, pts, pr=None):
        vs = [self.bm.verts.new(Vector(p)) for p in pts]
        f = self.bm.faces.new(vs)
        return self.tag({f}, key, pr)

    def stone(self, key, size, matrix, rnd, detail=1, square=0.42, bulge=0.12, chip=0.07, pr=None, flat_back=True):
        """One irregular stone: a squarified icosphere (boxy but rounded, chipped facets) of `size` (w, d, h),
        displaced by 3D noise. `square` < 1 squares it off (0.3 = dressed block, 0.6 = river stone)."""
        res = bmesh.ops.create_icosphere(self.bm, subdivisions=detail, radius=1.0)
        seed = Vector((rnd.uniform(-99, 99), rnd.uniform(-99, 99), rnd.uniform(-99, 99)))
        f1 = rnd.uniform(1.2, 2.2)
        for v in res['verts']:
            p = v.co
            q = Vector([math.copysign(abs(c) ** square, c) for c in p])
            n = noise.noise(p * f1 + seed) * chip + noise.noise(p * f1 * 2.7 + seed) * chip * 0.5
            q = q * (1.0 + n)
            if q.y < 0:                      # the visible face (-Y) bulges a little
                q.y -= bulge * (1 - min(1, q.x * q.x + q.z * q.z))
            elif flat_back:
                q.y = min(q.y, 0.85)
            v.co = matrix @ Vector((q.x * size[0] / 2, q.y * size[1] / 2, q.z * size[2] / 2))
        return self.tag(self.faces_of(res['verts']), key, pr)

    def grid(self, key, fn, nu, nv, pr_fn=None, closed_u=False):
        """Surface from fn(u, v) -> (x, y, z) on a (nu+1) x (nv+1) grid; pr_fn(i, j) gives per-face piece random."""
        rows = []
        for j in range(nv + 1):
            rows.append([self.bm.verts.new(Vector(fn(i / nu, j / nv))) for i in range(nu + (0 if closed_u else 1))])
        mi = self.mi(key)
        cols = nu if closed_u else nu
        for j in range(nv):
            for i in range(cols):
                i2 = (i + 1) % nu if closed_u else i + 1
                f = self.bm.faces.new((rows[j][i], rows[j][i2], rows[j + 1][i2], rows[j + 1][i]))
                f.material_index = mi
                f[self.pl] = pr_fn(i, j) if pr_fn else 0.5
        return rows

    def tube(self, key, pts, radii, segs=7, pr=None, cap=True, twist=0.0):
        """Tapered tube through points (trunks, branches, culms); flat facets like a folded paper tube."""
        rings = []
        up = Vector((0, 0, 1))
        for i, p in enumerate(pts):
            p = Vector(p)
            t = (Vector(pts[min(i + 1, len(pts) - 1)]) - Vector(pts[max(i - 1, 0)])).normalized()
            ref = up if abs(t.dot(up)) < 0.95 else Vector((1, 0, 0))
            a = t.cross(ref).normalized()
            b = t.cross(a).normalized()
            ring = []
            for k in range(segs):
                ang = 2 * math.pi * k / segs + twist * i
                ring.append(self.bm.verts.new(p + (a * math.cos(ang) + b * math.sin(ang)) * radii[i]))
            rings.append(ring)
        faces = []
        for i in range(len(rings) - 1):
            for k in range(segs):
                faces.append(self.bm.faces.new((rings[i][k], rings[i][(k + 1) % segs], rings[i + 1][(k + 1) % segs], rings[i + 1][k])))
        if cap:
            faces.append(self.bm.faces.new(rings[-1]))
        return self.tag(set(faces), key, pr)

    def finish(self, smooth=False, parent=True, shadow=True):
        me = bpy.data.meshes.new(self.name)
        self.bm.normal_update()
        self.bm.to_mesh(me)
        self.bm.free()
        ob = bpy.data.objects.new(self.name, me)
        for k in self.keys:
            me.materials.append(self.ctx.mat(k))
        for p in me.polygons:
            p.use_smooth = smooth
        pm.add_facet_attribute(ob, hash(self.name) & 0xffff)
        ob.visible_shadow = shadow
        return self.ctx.link(ob, parent)


# =========================================================================== tiled roofs (kawara)
def tile_profile(x, amp):
    """Cross profile of hongawara roofing, x in tile periods: a round cover tile (marugawara) then a concave pan."""
    f = x % 1.0
    if f < 0.32:
        return amp * math.sin(math.pi * f / 0.32) ** 0.7
    return -amp * 0.28 * math.sin(math.pi * (f - 0.32) / 0.68)


def tile_patch(mb, E0, E1, R0, R1, *, tile_w=0.30, tile_l=0.34, amp=0.07, v_max=1.0, sori=1.35, upturn=0.0,
               key='tile', end_caps=True, res=6, ridge_u=None):
    """A bilinear roof slope from the eave edge E0-E1 to the ridge edge R0-R1 (R0 == R1 for a hip triangle),
    with tile relief: round cover tiles in columns down the slope, a step at every tile course, a concave
    (sori) section and optional upturned corners. Returns a function P(u, v) giving surface points."""
    E0, E1, R0, R1 = Vector(E0), Vector(E1), Vector(R0), Vector(R1)
    elen = (E1 - E0).length
    slen = ((R0 + R1) / 2 - (E0 + E1) / 2).length
    U = (E1 - E0).normalized()

    def base(u, v):
        e = E0.lerp(E1, u)
        r = R0.lerp(R1, u)
        p = e.lerp(r, v)
        p.z = e.z + (r.z - e.z) * (v ** sori)
        if upturn:
            p.z += upturn * (abs(2 * u - 1) ** 3) * (1 - v) ** 2
        return p

    nu = max(4, int(elen / tile_w * res))
    nv = max(3, int(slen * v_max / tile_l * 3))
    n_up = Vector((0, 0, 1))

    def P(u, v):
        vv = v * v_max
        p = base(u, vv)
        um = (p - E0).dot(U) / tile_w
        vm = vv * slen / tile_l
        step = amp * 0.35 * (1 - (vm % 1.0))
        p = p + n_up * (tile_profile(um, amp) + step)
        return p

    def prf(i, j):
        um = int(i / res)
        vm = int(j / 3)
        return random.Random(um * 7919 + vm * 104729 + hash(mb.name) % 997).random()
    mb.grid(key, P, nu, nv, prf)
    if end_caps:                      # round end tiles (nokigawara) along the eave, facing out
        out = (E0 + E1) / 2 - (R0 + R1) / 2
        out.z = 0
        out = out.normalized()
        ncol = int(elen / tile_w)
        for c in range(ncol):
            u = (c + 0.16) * tile_w / elen
            if u > 1:
                break
            p = base(u, 0.0) + n_up * (amp * 0.55)
            rot = out.to_track_quat('Z', 'Y').to_matrix()
            mb.cyl(key, amp * 0.85, amp * 0.85, 0.04, 8, matrix=Matrix.Translation(p) @ rot.to_4x4())
    return base


def beam_between(mb, key, a, b, w, h, pr=None, up=Vector((0, 0, 1))):
    """Box beam from point a to b with cross-section w x h (ridges, hips, rafters, branches)."""
    a, b = Vector(a), Vector(b)
    d = b - a
    L = d.length
    if L < 1e-6:
        return set()
    q = d.normalized().to_track_quat('X', 'Z')
    return mb.box(key, (L, w, h), loc=(a + b) / 2, rot=q.to_matrix(), pr=pr)


def hip_roof(mb, W, D, *, pitch=30.0, overhang=1.2, upturn=0.35, sori=1.35, v_max=1.0, tile_w=0.30, tile_l=0.34,
             amp=0.07, ridge=True, soffit='plaster', fascia=0.22, z0=0.0, shachi=None, key='tile', hips=True):
    """Hip roof (yosemune) over a W x D footprint (W >= D) whose eave sits at z0; `v_max` < 1 truncates it into a
    pent roof (the skirt between castle storeys). Upturned corners, concave slopes, tiled, white plaster eaves."""
    o = overhang
    Wo, Do = W / 2 + o, D / 2 + o
    r = max(0.0, (W - D) / 2)
    rise = Do * math.tan(math.radians(pitch))
    z = z0
    corners = [Vector((-Wo, -Do, z)), Vector((Wo, -Do, z)), Vector((Wo, Do, z)), Vector((-Wo, Do, z))]
    rends = [Vector((-r, 0, z + rise)), Vector((r, 0, z + rise))]
    kw = dict(tile_w=tile_w, tile_l=tile_l, amp=amp, v_max=v_max, sori=sori, upturn=upturn, key=key)
    tile_patch(mb, corners[0], corners[1], rends[0], rends[1], **kw)                 # front
    tile_patch(mb, corners[2], corners[3], rends[1], rends[0], **kw)                 # back
    tile_patch(mb, corners[1], corners[2], rends[1], rends[1], **kw)                 # right (triangle)
    tile_patch(mb, corners[3], corners[0], rends[0], rends[0], **kw)                 # left
    up = Vector((0, 0, 1))

    def hip_pt(c, re, v):
        p = c.lerp(re, v)
        p.z = c.z + (re.z - c.z) * v ** sori + upturn * (1 - v) ** 2
        return p
    if hips:
        for c, re in ((corners[0], rends[0]), (corners[1], rends[1]), (corners[2], rends[1]), (corners[3], rends[0])):
            n = 6
            pts = [hip_pt(c, re, v_max * i / n) + up * (amp * 1.3) for i in range(n + 1)]
            for i in range(n):
                beam_between(mb, key, pts[i], pts[i + 1], 0.32, 0.26)
            mb.box(key, (0.34, 0.34, 0.42), loc=pts[0] + up * 0.12)          # end ornament at the corner
    if ridge and v_max >= 0.999:
        L = 2 * r + 0.5
        top = z + rise + amp * 1.3
        mb.box(key, (L, 0.42, 0.55), loc=(0, 0, top + 0.12), bevel=0.03)
        mb.box(key, (L - 0.1, 0.3, 0.16), loc=(0, 0, top + 0.47))
        for sx in (-1, 1):                                                     # onigawara end blocks
            mb.box(key, (0.3, 0.6, 0.8), loc=(sx * L / 2, 0, top + 0.3), bevel=0.04)
            if shachi:
                _shachihoko(mb, shachi, Vector((sx * (L / 2 - 0.15), 0, top + 0.65)), sx)
    # eave: fascia band + soffit back to the wall line (white plaster under the eaves, castle style)
    if soffit:
        n = 10
        ring_out, ring_in = [], []
        for side in range(4):
            a, b = corners[side], corners[(side + 1) % 4]
            for i in range(n):
                u = i / n
                p = a.lerp(b, u)
                p.z = z + upturn * abs(2 * u - 1) ** 3 - fascia
                ring_out.append(p)
                q = Vector((p.x * (W / 2) / Wo, p.y * (D / 2) / Do, z - fascia - o * 0.12))
                ring_in.append(q)
        N = len(ring_out)
        for i in range(N):
            j = (i + 1) % N
            mb.poly(soffit, [ring_out[i], ring_out[j], ring_in[j], ring_in[i]], pr=0.5)
            top_i = ring_out[i] + up * fascia
            top_j = ring_out[j] + up * fascia
            mb.poly(soffit, [ring_out[j], ring_out[i], top_i, top_j], pr=0.4)
    return rise


def _shachihoko(mb, key, p, sx):
    """Golden tiger-fish ridge ornament (a few folded facets: tail up, head down)."""
    mb.box(key, (0.22, 0.18, 0.5), loc=p + Vector((0, 0, 0.1)), rot=(0, sx * 12, 0), bevel=0.03)
    mb.box(key, (0.16, 0.06, 0.38), loc=p + Vector((-sx * 0.12, 0, 0.45)), rot=(0, -sx * 35, 0))
    mb.box(key, (0.2, 0.2, 0.18), loc=p + Vector((sx * 0.08, 0, -0.12)), rot=(0, sx * 30, 0))


def gable_roof(mb, L, Wd, *, pitch=32.0, overhang=0.35, z0=0.0, tile_w=0.26, tile_l=0.3, amp=0.05, key='tile',
               fascia='wood_dark', ridge=True, axis='X'):
    """Two-slope roof along `axis` (wall caps, gates, gables): length L, span Wd, eave at z0."""
    o = overhang
    hl, hw = L / 2 + o * 0.6, Wd / 2 + o
    rise = hw * math.tan(math.radians(pitch))
    sw = (lambda x, y, z: Vector((x, y, z))) if axis == 'X' else (lambda x, y, z: Vector((y, -x, z)))
    kw = dict(tile_w=tile_w, tile_l=tile_l, amp=amp, sori=1.15, key=key)
    tile_patch(mb, sw(-hl, -hw, z0), sw(hl, -hw, z0), sw(-hl, 0, z0 + rise), sw(hl, 0, z0 + rise), **kw)
    tile_patch(mb, sw(hl, hw, z0), sw(-hl, hw, z0), sw(hl, 0, z0 + rise), sw(-hl, 0, z0 + rise), **kw)
    if ridge:
        a, b = sw(-hl, 0, z0 + rise + amp + 0.08), sw(hl, 0, z0 + rise + amp + 0.08)
        beam_between(mb, key, a, b, 0.3, 0.26)
        for e in (a, b):
            mb.box(key, (0.22, 0.4, 0.4) if axis == 'X' else (0.4, 0.22, 0.4), loc=e + Vector((0, 0, 0.12)))
    if fascia:
        for sy in (-1, 1):
            a, b = sw(-hl, sy * hw, z0 - 0.12), sw(hl, sy * hw, z0 - 0.12)
            beam_between(mb, fascia, a, b, 0.06, 0.16)
        for sx in (-1, 1):                 # barge boards on the gable ends
            for sy in (-1, 1):
                beam_between(mb, fascia, sw(sx * hl, sy * hw, z0 - 0.05), sw(sx * hl, 0, z0 + rise), 0.05, 0.2)
    return rise


# =========================================================================== stone walls (ishigaki)
def _profile(H, batter, curve):
    """Setback s(z) of a battered wall: shallow at the base, near vertical at the top (ogi-no-kobai)."""
    def s(z):
        t = min(1.0, max(0.0, z / H))
        return batter * (1 - (1 - t) ** curve)

    def ds(z):
        t = min(1.0, max(0.0, z / H))
        return batter * curve * (1 - t) ** (curve - 1) / H
    return s, ds


def _rows(rnd, H, stone):
    rows, z = [], 0.0
    while z < H - 0.05:
        k = 1.25 - 0.45 * z / H
        h = min(H - z, stone * k * rnd.uniform(0.75, 1.25))
        if H - z - h < stone * 0.35:
            h = H - z
        rows.append((z, h))
        z += h
    return rows


def stone_face(mb, rnd, L, H, rows, s, ds, *, stone=0.6, key='stone', detail=1, matrix=None, x_clip=None,
               corner_left=False, corner_right=False, fillers=0.5, style='nozura'):
    """Stones of one battered face (local: face toward -Y, x along the wall). x_clip(z) -> (x0, x1) limits each
    course (the inset corners of a battered base). corner_*: alternate long corner blocks (sangi-zumi)."""
    matrix = matrix or Matrix.Identity(4)
    gap = 0.035 * stone
    sq = {'nozura': 0.45, 'uchikomi': 0.33, 'kirikomi': 0.22}[style]
    for ri, (z0, h) in enumerate(rows):
        zc = z0 + h / 2
        x0, x1 = x_clip(zc) if x_clip else (-L / 2, L / 2)
        tilt = math.atan(ds(zc))
        y_face = s(zc)
        Db = h * 1.15                       # corner block depth seen from the other face
        xa, xb = x0, x1
        blocks = []
        if corner_right:
            if ri % 2 == 0:
                Lb = h * rnd.uniform(2.0, 2.6)
                blocks.append((x1 - Lb / 2, Lb, h * 1.15))
                xb = x1 - Lb - gap
            else:
                xb = x1 - Db - gap
        if corner_left:
            if ri % 2 == 1:
                Lb = h * rnd.uniform(2.0, 2.6)
                blocks.append((x0 + Lb / 2, Lb, h * 1.15))
                xa = x0 + Lb + gap
            else:
                xa = x0 + Db + gap
        x = xa
        joints = []
        while x < xb - 0.15 * stone:
            w = h * rnd.uniform(0.9, 2.1) * (1.15 if style == 'kirikomi' else 1.0)
            if xb - (x + w) < h * 0.55:
                w = xb - x
            xc = x + w / 2
            d = h * rnd.uniform(1.0, 1.5)
            pro = h * rnd.uniform(0.0, 0.1) if style == 'nozura' else h * rnd.uniform(0.0, 0.03)
            zj = zc + rnd.uniform(-0.05, 0.05) * h
            m = matrix @ M4((xc, y_face - pro + d / 2, zj), Euler((tilt + rnd.uniform(-0.04, 0.04), rnd.uniform(-0.05, 0.05), rnd.uniform(-0.04, 0.04))).to_matrix())
            mb.stone(key, (w - gap, d, h - gap), m, rnd, detail=detail, square=sq + rnd.uniform(-0.05, 0.08),
                     bulge=0.14 if style == 'nozura' else 0.05, chip=0.08 if style == 'nozura' else 0.04)
            joints.append(x + w)
            x += w + gap
        for xc, Lb, d in blocks:
            m = matrix @ M4((xc, y_face + d / 2 - 0.01, zc), Euler((tilt, 0, 0)).to_matrix())
            mb.stone(key, (Lb - gap, d, h - gap), m, rnd, detail=detail, square=0.25, bulge=0.04, chip=0.035)
        for xj in joints[:-1]:                # small wedge stones (aiishi) in the joints
            if rnd.random() < fillers:
                hs = h * rnd.uniform(0.18, 0.32)
                zz = z0 + rnd.uniform(0.15, 0.85) * h
                m = matrix @ M4((xj, s(zz) + hs * 0.3, zz), Euler((math.atan(ds(zz)), 0, rnd.uniform(0, 6))).to_matrix())
                mb.stone(key, (hs * 1.4, hs, hs), m, rnd, detail=1, square=0.5, bulge=0.05)


def backfill(mb, L, H, s, matrix, x_clip=None, key='backfill', inset=0.08, n=14):
    """The dark packed rubble seen in the gaps between stones."""
    def P(u, v):
        z = v * H
        x0, x1 = x_clip(z) if x_clip else (-L / 2, L / 2)
        return matrix @ Vector((x0 + (x1 - x0) * u, s(z) + inset, z))
    mb.grid(key, P, 8, n)


@piece('ishigaki', length=20.0, height=4.0, batter=1.6, curve=2.2, thickness=4.0, stone=0.6, detail=1, style='nozura',
       key='stone', top='earth', fillers=0.5, ends='cut')
def ishigaki(ctx, P, rnd):
    """Castle stone wall (ishigaki): a battered, concave-curved face of individual irregular stones (nozura /
    uchikomi / kirikomi style), small wedge stones in the joints, dark rubble in the gaps, moss and grime from the
    stone material. Face toward -Y, x along the wall, base on z = 0, top plateau `thickness` deep."""
    L, H = P['length'], P['height']
    s, ds = _profile(H, P['batter'], P['curve'])
    rows = _rows(rnd, H, P['stone'])
    mb = MB(ctx, ctx.info['name'] + '_stones', rnd)
    stone_face(mb, rnd, L, H, rows, s, ds, stone=P['stone'], key=P['key'], detail=P['detail'], style=P['style'], fillers=P['fillers'])
    mb.finish()
    bf = MB(ctx, ctx.info['name'] + '_core', rnd)
    backfill(bf, L, H, s, Matrix.Identity(4))
    T = s(H)
    bf.box(P['top'], (L, P['thickness'], 0.2), loc=(0, T + P['thickness'] / 2, H - 0.08))
    bf.box('backfill', (L, P['thickness'], H), loc=(0, T + P['thickness'] / 2 + 0.1, H / 2 - 0.1))
    bf.finish()


def ishigaki_block(ctx, rnd, w, d, H, *, batter=1.6, curve=2.2, stone=0.7, detail=1, style='uchikomi', key='stone',
                   top='earth', name='base', faces=(0, 1, 2, 3)):
    """Closed four-sided battered stone base (under a keep or a gate tower), corners in sangi-zumi."""
    s, ds = _profile(H, batter, curve)
    rows = _rows(rnd, H, stone)
    mb = MB(ctx, name + '_stones', rnd)
    bf = MB(ctx, name + '_core', rnd)
    for k in range(4):
        side = w if k % 2 == 0 else d
        other = d if k % 2 == 0 else w
        ang = [0, 90, 180, 270][k]
        m = M4(rot=(0, 0, ang)) @ Matrix.Translation((0, -other / 2, 0))
        clip = (lambda L: (lambda z: (-L / 2 + s(z), L / 2 - s(z))))(side)
        if k in faces:
            stone_face(mb, rnd, side, H, rows, s, ds, stone=stone, key=key, detail=detail, matrix=m, x_clip=clip,
                       corner_left=True, corner_right=True, style=style)
        backfill(bf, side, H, s, m, x_clip=clip)
    T = s(H)
    bf.box(top, (w - 2 * T, d - 2 * T, 0.2), loc=(0, 0, H - 0.09))
    bf.box('backfill', (w - 2 * T - 0.2, d - 2 * T - 0.2, H), loc=(0, 0, H / 2 - 0.1))
    mb.finish()
    bf.finish()
    return T


@piece('ishigaki_base', width=16.0, depth=13.0, height=6.0, batter=1.8, curve=2.2, stone=0.7, detail=1,
       style='uchikomi', key='stone', top='earth')
def ishigaki_base(ctx, P, rnd):
    """Four-sided battered stone platform (tenshu-dai) with sangi-zumi corners. Top at z = height."""
    ishigaki_block(ctx, rnd, P['width'], P['depth'], P['height'], batter=P['batter'], curve=P['curve'], stone=P['stone'],
                   detail=P['detail'], style=P['style'], key=P['key'], top=P['top'], name=ctx.info['name'])


# =========================================================================== list (outside Blender too)
def describe():
    lines = []
    for name, k in KIT.items():
        lines.append(f"{name}: {k['doc'].splitlines()[0] if k['doc'] else ''}")
        lines.append('    ' + ', '.join(f'{p}={v!r}' for p, v in k['defaults'].items()))
    return '\n'.join(lines)


def build_piece(ctx, spec):
    """Place one piece from a JSON spec: {kit, name, pos, rot (deg about Z, or [x,y,z]), scale, seed, params}."""
    kind = spec['kit']
    if kind not in KIT:
        raise KeyError(f'unknown kit piece {kind!r}; known: {", ".join(sorted(KIT))}')
    k = KIT[kind]
    P = dict(k['defaults'])
    unknown = set(spec.get('params', {})) - set(P)
    if unknown:
        print(f'  ! {spec.get("name", kind)}: unknown params {sorted(unknown)} for {kind} (known: {sorted(P)})')
    P.update(spec.get('params', {}))
    name = spec.get('name', kind)
    root = bpy.data.objects.new('SET_' + name, None)
    root.empty_display_size = 0.5
    root.location = Vector(spec.get('pos', (0, 0, 0)))
    r = spec.get('rot', 0)
    root.rotation_euler = tuple(math.radians(a) for a in r) if isinstance(r, (list, tuple)) else (0, 0, math.radians(r))
    sc = spec.get('scale', 1.0)
    root.scale = tuple(sc) if isinstance(sc, (list, tuple)) else (sc, sc, sc)
    root['kit'] = kind
    ctx.coll.objects.link(root)
    bpy.context.view_layer.update()
    ctx.root = root
    ctx.info = {'name': name, 'kind': kind}
    seed = spec.get('seed', 0)
    k['fn'](ctx, P, ctx.rng(kind, name, seed))
    ctx.root = None
    return root

