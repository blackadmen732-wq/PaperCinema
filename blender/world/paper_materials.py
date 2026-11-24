"""Lantern Origami materials for Blender (Cycles): reusable by the world set, the slash effects and characters.

    import sys; sys.path.insert(0, 'blender/world'); import paper_materials as pm
    m = pm.paper_material('Kimono', (0.55, 0.5, 0.42), translucency=0.35)
    pm.add_facet_attribute(obj)        # per-facet tone variation (each flat face a slightly different sheet)

Every paper surface is the same recipe:
  * flat facets: the shading normal is the TRUE face normal, so even smooth-shaded meshes (the Ocean modifier)
    read as folded planes;
  * washi fibre: noise + long stretched fibres drive a light bump, a speckle in the colour and the roughness;
  * per-facet tone: a face attribute `facet_rand` (0..1) shifts each facet's value a little;
  * light through the paper: Principled (with sheen) mixed with a Translucent BSDF;
  * optional extras: a second colour by height (`tint_z`), stripes (hakama pattern), interior glow (`glow`),
    and aerial haze (`haze`): the surface fades to a haze colour with camera distance. Haze is a cheap stand-in
    for a fog volume and gives the layered mountains their depth.
"""
import math
import random

import bpy

FACET_ATTR = 'facet_rand'


# --------------------------------------------------------------------------- small node helpers
class _NT:
    """Thin wrapper so recipes read top to bottom."""

    def __init__(self, nt):
        self.nt = nt
        self.x = -1600

    def node(self, kind, **inputs):
        n = self.nt.nodes.new(kind)
        n.location = (self.x, 0)
        self.x += 180
        for k, v in inputs.items():
            if isinstance(v, bpy.types.NodeSocket):
                self.nt.links.new(v, n.inputs[k])
            else:
                n.inputs[k].default_value = v
        return n

    def link(self, a, b):
        self.nt.links.new(a, b)

    def math(self, op, a, b=None, c=None, clamp=False):
        n = self.nt.nodes.new('ShaderNodeMath')
        n.operation = op
        n.use_clamp = clamp
        n.location = (self.x, -300)
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, bpy.types.NodeSocket):
                self.nt.links.new(v, n.inputs[i])
            else:
                n.inputs[i].default_value = v
        return n.outputs[0]

    def mix_rgb(self, fac, a, b, blend='MIX'):
        """ShaderNodeMix in RGBA mode (inputs 0 = factor, 6 = A, 7 = B; output 2)."""
        n = self.nt.nodes.new('ShaderNodeMix')
        n.data_type = 'RGBA'
        n.blend_type = blend
        n.location = (self.x, -500)
        for idx, v in ((0, fac), (6, a), (7, b)):
            if isinstance(v, bpy.types.NodeSocket):
                self.nt.links.new(v, n.inputs[idx])
            else:
                n.inputs[idx].default_value = v if idx == 0 else (*v[:3], 1.0)
        return n.outputs[2]


def _rgba(c):
    return (*c[:3], 1.0)


def new_material(name):
    m = bpy.data.materials.get(name)
    if m:
        bpy.data.materials.remove(m)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes.clear()
    return m


# --------------------------------------------------------------------------- the paper recipe
def fibre_height(T, scale=40.0, stretch=6.0, seed=0.0):
    """Washi fibre field (0..1): fine pulp noise plus long fibres stretched along object X."""
    tc = T.node('ShaderNodeTexCoord')
    mp = T.node('ShaderNodeMapping', Vector=tc.outputs['Object'])
    mp.inputs['Scale'].default_value = (scale, scale, scale)
    mp.inputs['Location'].default_value = (seed * 13.1, seed * 7.7, seed * 3.3)
    pulp = T.node('ShaderNodeTexNoise', Vector=mp.outputs['Vector'], Scale=4.0, Detail=10.0, Roughness=0.65)
    mf = T.node('ShaderNodeMapping', Vector=mp.outputs['Vector'])
    mf.inputs['Scale'].default_value = (1.0 / stretch, 1.0, 1.0)
    mf.inputs['Rotation'].default_value = (0.3, 0.2, 0.9 + seed)
    fib = T.node('ShaderNodeTexNoise', Vector=mf.outputs['Vector'], Scale=9.0, Detail=4.0, Distortion=0.8)
    ridge = T.math('PINGPONG', fib.outputs['Fac'], 0.5)              # thin bright fibre ridges
    ridge = T.math('POWER', T.math('SUBTRACT', 1.0, T.math('MULTIPLY', ridge, 2.0)), 8.0)
    h = T.math('MULTIPLY_ADD', ridge, 0.45, pulp.outputs['Fac'])
    return h


def paper_material(name, color, *, translucency=0.35, rough=0.82, sheen=0.25, fibre_scale=40.0,
                   fibre_strength=0.12, facet_var=0.10, flat=True, tint=None, tint_z=(0.0, 1.0),
                   stripes=None, glow=None, haze=None, translucent_color=None, seed=None):
    """Faceted washi paper.

    color            base RGB (linear, 0..1)
    translucency     0..1 share of Translucent BSDF (light passing through the sheet)
    fibre_scale      fibre density per metre of object space (characters ~60-200, world props 2-20)
    fibre_strength   bump strength of the fibres
    facet_var        +- tone change per facet, read from the `facet_rand` face attribute
    flat             use the true face normal (hard folded facets) even on smooth-shaded meshes
    tint             second RGB, mixed by world height between tint_z = (z_low, z_high): wet/dry sand, snow caps
    stripes          (rgb, bands_per_metre, width 0..1): woven stripes along object Z (hakama, kimono)
    glow             (rgb, strength): emission from inside the paper (lantern glow; amber human, crimson demon)
    haze             (rgb, distance_m, strength): aerial perspective, fades to the haze colour with distance
    """
    m = new_material(name)
    T = _NT(m.node_tree)
    s = random.Random(name).random() if seed is None else seed
    out = m.node_tree.nodes.new('ShaderNodeOutputMaterial')
    geo = T.node('ShaderNodeNewGeometry')

    # colour: base (+ height tint) (+ stripes) x facet variation x fibre speckle
    col = _rgba(color)
    col_sock = None
    if tint is not None:
        sep = T.node('ShaderNodeSeparateXYZ', Vector=geo.outputs['Position'])
        mr = T.node('ShaderNodeMapRange', Value=sep.outputs['Z'])
        mr.inputs['From Min'].default_value, mr.inputs['From Max'].default_value = tint_z
        col_sock = T.mix_rgb(mr.outputs['Result'], tint, col)
    if stripes is not None:
        s_col, bands, width = stripes
        tc = T.node('ShaderNodeTexCoord')
        sep2 = T.node('ShaderNodeSeparateXYZ', Vector=tc.outputs['Object'])
        band = T.math('FRACT', T.math('MULTIPLY', sep2.outputs['X'], bands))
        is_s = T.math('LESS_THAN', band, width)
        col_sock = T.mix_rgb(is_s, col_sock if col_sock else col, s_col)
    attr = T.node('ShaderNodeAttribute')
    attr.attribute_type = 'GEOMETRY'
    attr.attribute_name = FACET_ATTR
    fv = T.math('MULTIPLY_ADD', T.math('SUBTRACT', attr.outputs['Fac'], 0.5), 2.0 * facet_var, 1.0)
    h = fibre_height(T, fibre_scale, seed=s)
    speck = T.math('MULTIPLY_ADD', h, -0.10, 1.04)
    k = T.math('MULTIPLY', fv, speck)
    kv = T.node('ShaderNodeCombineXYZ', X=k, Y=k, Z=k)
    base = T.mix_rgb(1.0, col_sock if col_sock else col, kv.outputs[0], blend='MULTIPLY')

    # normal: fibre bump on the flat facet normal
    bump = T.node('ShaderNodeBump', Strength=fibre_strength, Distance=0.02, Height=h)
    if flat:
        T.link(geo.outputs['True Normal'], bump.inputs['Normal'])
    rgh = T.math('MULTIPLY_ADD', h, 0.12, rough - 0.05, clamp=True)

    p = T.node('ShaderNodeBsdfPrincipled', **{'Base Color': base, 'Roughness': rgh, 'Normal': bump.outputs['Normal']})
    p.inputs['Sheen Weight'].default_value = sheen
    p.inputs['Sheen Roughness'].default_value = 0.6
    p.inputs['Specular IOR Level'].default_value = 0.35
    shader = p.outputs['BSDF']
    if translucency > 0:
        tcol = translucent_color if translucent_color else color
        tr = T.node('ShaderNodeBsdfTranslucent', Color=_rgba(tcol), Normal=bump.outputs['Normal'])
        mx = T.node('ShaderNodeMixShader', Fac=translucency)
        T.link(shader, mx.inputs[1]); T.link(tr.outputs['BSDF'], mx.inputs[2])
        shader = mx.outputs['Shader']
    if glow is not None:
        g_col, g_str = glow
        em = T.node('ShaderNodeEmission', Color=_rgba(g_col), Strength=g_str)
        ad = T.node('ShaderNodeAddShader')
        T.link(shader, ad.inputs[0]); T.link(em.outputs['Emission'], ad.inputs[1])
        shader = ad.outputs['Shader']
    if haze is not None:
        shader = _haze(T, shader, *haze)
    T.link(shader, out.inputs['Surface'])
    out.location = (T.x + 200, 0)
    return m


# Sky used by haze=(None, ...): set once by the world builder so distant paper fades into the real sky colour.
SKY = {'sun_elevation': math.radians(4.0), 'sun_rotation': 0.0, 'altitude': 0.0, 'air_density': 1.0,
       'dust_density': 1.0, 'ozone_density': 1.0}


def sky_node(T, vector=None):
    sk = T.node('ShaderNodeTexSky')
    sk.sky_type = 'NISHITA'
    sk.sun_disc = False
    for k, v in SKY.items():
        setattr(sk, k, v)
    if vector is not None:
        T.link(vector, sk.inputs['Vector'])
    return sk


def _haze(T, shader, color, distance, strength=1.0):
    """Mix the surface toward an emissive haze colour: f = 1 - exp(-d / distance).
    color=None: the haze is the Nishita sky seen just above the horizon in the view direction (matches the
    background exactly, so far mountains melt into the sky)."""
    cam = T.node('ShaderNodeCameraData')
    f = T.math('SUBTRACT', 1.0, T.math('EXPONENT', T.math('DIVIDE', T.math('MULTIPLY', cam.outputs['View Distance'], -1.0), distance)))
    if color is None:
        geo = T.node('ShaderNodeNewGeometry')
        sep = T.node('ShaderNodeSeparateXYZ', Vector=geo.outputs['Incoming'])
        nx = T.math('MULTIPLY', sep.outputs['X'], -1.0)
        ny = T.math('MULTIPLY', sep.outputs['Y'], -1.0)
        nz = T.math('MAXIMUM', T.math('MULTIPLY', sep.outputs['Z'], -1.0), 0.035)
        v = T.node('ShaderNodeCombineXYZ', X=nx, Y=ny, Z=nz)
        vn = T.node('ShaderNodeVectorMath', Vector=v.outputs[0]); vn.operation = 'NORMALIZE'
        sk = sky_node(T, vn.outputs['Vector'])
        em = T.node('ShaderNodeEmission', Color=sk.outputs['Color'], Strength=strength)
    else:
        em = T.node('ShaderNodeEmission', Color=_rgba(color), Strength=strength)
    mx = T.node('ShaderNodeMixShader', Fac=f)
    T.link(shader, mx.inputs[1]); T.link(em.outputs['Emission'], mx.inputs[2])
    return mx.outputs['Shader']


def sea_material(name='LO_SeaPaper', deep=(0.03, 0.07, 0.10), shallow=(0.10, 0.22, 0.25), foam=(0.85, 0.80, 0.70),
                 haze=None, foam_attr='foam', foam_gain=6.0, foam_base=0.1, foam_z=0.4, crest_gain=3.0, foam_cells=0.2):
    """Faceted paper sea: true-normal facets, a sheen of wet card, colour by facet slope, foam from the Ocean
    modifier's foam attribute broken up like torn paper edges."""
    m = new_material(name)
    T = _NT(m.node_tree)
    out = m.node_tree.nodes.new('ShaderNodeOutputMaterial')
    geo = T.node('ShaderNodeNewGeometry')
    sep = T.node('ShaderNodeSeparateXYZ', Vector=geo.outputs['True Normal'])
    slope = T.math('POWER', T.math('SUBTRACT', 1.0, sep.outputs['Z'], clamp=True), 0.5)
    lay = T.node('ShaderNodeLayerWeight', Blend=0.35)
    fr = T.node('ShaderNodeAttribute'); fr.attribute_type = 'GEOMETRY'; fr.attribute_name = FACET_ATTR
    col = T.mix_rgb(T.math('ADD', T.math('MULTIPLY', slope, 1.8), T.math('MULTIPLY', lay.outputs['Facing'], 0.3), clamp=True), deep, shallow)
    kf = T.math('MULTIPLY_ADD', fr.outputs['Fac'], 0.9, 0.55)
    kfv = T.node('ShaderNodeCombineXYZ', X=kf, Y=kf, Z=kf)
    col = T.mix_rgb(1.0, col, kfv.outputs[0], blend='MULTIPLY')
    # foam = white paper caps on the highest facets (crest height) + the Ocean foam attribute (choppy seas),
    # broken up by noise like torn paper edges
    fa = T.node('ShaderNodeAttribute'); fa.attribute_type = 'GEOMETRY'; fa.attribute_name = foam_attr
    tc = T.node('ShaderNodeTexCoord')
    nz = T.node('ShaderNodeTexNoise', Vector=tc.outputs['Object'], Scale=1.2, Detail=6.0)
    pos = T.node('ShaderNodeSeparateXYZ', Vector=geo.outputs['Position'])
    crest = T.math('MULTIPLY', T.math('SUBTRACT', pos.outputs['Z'], foam_z), crest_gain)
    fv = T.math('MULTIPLY_ADD', T.math('SUBTRACT', fa.outputs['Fac'], foam_base), foam_gain, crest)
    fv = T.math('MULTIPLY_ADD', T.math('SUBTRACT', nz.outputs['Fac'], 0.5), 0.6, fv)
    cells = T.node('ShaderNodeTexVoronoi', Vector=tc.outputs['Object'], Scale=3.0)
    cell_r = T.node('ShaderNodeSeparateColor', Color=cells.outputs['Color'])
    fmask = T.math('MULTIPLY', T.math('GREATER_THAN', fv, 0.1), T.math('GREATER_THAN', cell_r.outputs[0], 1.0 - foam_cells))
    h = fibre_height(T, 3.0, seed=0.4)
    col = T.mix_rgb(fmask, col, foam)
    rough = T.math('MULTIPLY_ADD', fmask, 0.55, T.math('MULTIPLY_ADD', fr.outputs['Fac'], 0.22, T.math('MULTIPLY_ADD', h, 0.04, 0.04)))
    bump = T.node('ShaderNodeBump', Strength=0.08, Distance=0.05, Height=h)
    T.link(geo.outputs['True Normal'], bump.inputs['Normal'])
    p = T.node('ShaderNodeBsdfPrincipled', **{'Base Color': col, 'Roughness': rough, 'Normal': bump.outputs['Normal']})
    p.inputs['Sheen Weight'].default_value = 0.1
    p.inputs['Specular IOR Level'].default_value = 0.22
    shader = p.outputs['BSDF']
    if haze is not None:
        shader = _haze(T, shader, *haze)
    T.link(shader, out.inputs['Surface'])
    return m


def emission_material(name, color, strength):
    m = new_material(name)
    T = _NT(m.node_tree)
    out = m.node_tree.nodes.new('ShaderNodeOutputMaterial')
    em = T.node('ShaderNodeEmission', Color=_rgba(color), Strength=strength)
    T.link(em.outputs['Emission'], out.inputs['Surface'])
    return m


def metal_material(name, color=(0.6, 0.6, 0.62), rough=0.16, aniso=0.6):
    m = new_material(name)
    T = _NT(m.node_tree)
    out = m.node_tree.nodes.new('ShaderNodeOutputMaterial')
    p = T.node('ShaderNodeBsdfPrincipled', **{'Base Color': _rgba(color), 'Roughness': rough, 'Metallic': 1.0, 'Anisotropic': aniso})
    T.link(p.outputs['BSDF'], out.inputs['Surface'])
    return m


# --------------------------------------------------------------------------- mesh helpers
def add_facet_attribute(obj_or_mesh, seed=0):
    """Write a random 0..1 value per face (domain FACE) that paper materials read as facet tone."""
    me = obj_or_mesh.data if hasattr(obj_or_mesh, 'data') else obj_or_mesh
    rnd = random.Random(seed)
    a = me.attributes.get(FACET_ATTR) or me.attributes.new(FACET_ATTR, 'FLOAT', 'FACE')
    a.data.foreach_set('value', [rnd.random() for _ in range(len(me.polygons))])
    return me


def facet_random_modifier(obj, seed=0):
    """Geometry Nodes modifier that stores `facet_rand` per face on generated geometry (the Ocean modifier),
    so animated meshes get the same per-facet paper tone as built ones. Stable over time (face index)."""
    name = 'LO_FacetRandom'
    ng = bpy.data.node_groups.get(name)
    if ng is None:
        ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
        ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        ng.interface.new_socket('Seed', in_out='INPUT', socket_type='NodeSocketInt')
        ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        gi = ng.nodes.new('NodeGroupInput'); go = ng.nodes.new('NodeGroupOutput')
        rv = ng.nodes.new('FunctionNodeRandomValue'); rv.data_type = 'FLOAT'
        st = ng.nodes.new('GeometryNodeStoreNamedAttribute'); st.data_type = 'FLOAT'; st.domain = 'FACE'
        st.inputs['Name'].default_value = FACET_ATTR
        ng.links.new(gi.outputs['Geometry'], st.inputs['Geometry'])
        ng.links.new(gi.outputs['Seed'], rv.inputs['Seed'])
        val_out = [o for o in rv.outputs if o.enabled and o.type == 'VALUE'][0]
        val_in = [i for i in st.inputs if i.enabled and i.type == 'VALUE' and i.name == 'Value'][0]
        ng.links.new(val_out, val_in)
        ng.links.new(st.outputs['Geometry'], go.inputs['Geometry'])
    mod = obj.modifiers.new('FacetRandom', 'NODES')
    mod.node_group = ng
    for item in ng.interface.items_tree:
        if getattr(item, 'name', '') == 'Seed':
            mod[item.identifier] = int(seed)
    return mod


def shade_flat(obj):
    for p in obj.data.polygons:
        p.use_smooth = False


# =========================================================================== SET MATERIALS (blender/sets/kit.py)
# Realistic surfaces that stay in the paper-craft family: every recipe keeps a faint washi-fibre bump (`paper`)
# and reads the per-piece random `piece_rand` (one value per stone, plank, tile, culm: written by the kit's
# MeshBuilder) so neighbouring pieces never share a tone. Textures are procedural; an optional Poly Haven (CC0) photo
# layer (`ph=` role, see POLYHAVEN below) adds real surface detail on top when a set turns it on.
PIECE_ATTR = 'piece_rand'


def _attr(T, name):
    a = T.node('ShaderNodeAttribute')
    a.attribute_type = 'GEOMETRY'
    a.attribute_name = name
    return a.outputs['Fac']


def _map(T, kind='Object', scale=(1, 1, 1), loc=(0, 0, 0), rot=(0, 0, 0), vector=None):
    if vector is None:
        tc = T.node('ShaderNodeTexCoord')
        vector = tc.outputs[kind]
    mp = T.node('ShaderNodeMapping', Vector=vector)
    mp.inputs['Scale'].default_value = scale
    mp.inputs['Location'].default_value = loc
    mp.inputs['Rotation'].default_value = rot
    return mp.outputs['Vector']


def _noise(T, vec, scale=1.0, detail=4.0, rough=0.55, distortion=0.0):
    n = T.node('ShaderNodeTexNoise', Vector=vec, Scale=scale, Detail=detail, Roughness=rough, Distortion=distortion)
    return n


def _voronoi(T, vec, scale=1.0, feature='F1', rnd=1.0):
    v = T.node('ShaderNodeTexVoronoi', Vector=vec, Scale=scale, Randomness=rnd)
    v.feature = feature
    return v


def _ramp(T, fac, stops):
    """stops = [(pos, (r, g, b)), ...] -> colour socket."""
    r = T.node('ShaderNodeValToRGB', Fac=fac)
    el = r.color_ramp.elements
    while len(el) > 2:
        el.remove(el[-1])
    for i, (pos, col) in enumerate(stops):
        e = el[i] if i < 2 else el.new(pos)
        e.position = pos
        e.color = _rgba(col)
    return r.outputs['Color']


def _smooth(T, x, a, b):
    mr = T.node('ShaderNodeMapRange', Value=x)
    mr.interpolation_type = 'SMOOTHSTEP'
    mr.inputs['From Min'].default_value = a
    mr.inputs['From Max'].default_value = b
    return mr.outputs['Result']


def _scale_col(T, col, k):
    """colour * scalar socket/value."""
    kv = T.node('ShaderNodeCombineXYZ', X=k, Y=k, Z=k) if isinstance(k, bpy.types.NodeSocket) else None
    if kv is None:
        return T.mix_rgb(1.0, col, (k, k, k), blend='MULTIPLY')
    return T.mix_rgb(1.0, col, kv.outputs[0], blend='MULTIPLY')


def _ao(T, distance=0.3, samples=6, inside=False):
    ao = T.node('ShaderNodeAmbientOcclusion', Distance=distance)
    ao.samples = samples
    ao.inside = inside
    ao.only_local = True
    return ao.outputs['AO']


def _principled(T, out, base, rough, height=None, bump=0.2, bump_dist=0.01, flat=True, normal=None, spec=0.4,
                coat=0.0, coat_rough=0.1, sheen=0.0, sss=None, translucency=0.0, trans_color=None, emission=None,
                haze=None, metallic=0.0):
    geo = T.node('ShaderNodeNewGeometry')
    nrm = normal
    if height is not None:
        b = T.node('ShaderNodeBump', Strength=bump, Distance=bump_dist, Height=height)
        if flat and normal is None:
            T.link(geo.outputs['True Normal'], b.inputs['Normal'])
        elif normal is not None:
            T.link(normal, b.inputs['Normal'])
        nrm = b.outputs['Normal']
    elif flat:
        nrm = geo.outputs['True Normal']
    kw = {'Base Color': base, 'Roughness': rough}
    if nrm is not None:
        kw['Normal'] = nrm
    p = T.node('ShaderNodeBsdfPrincipled', **kw)
    p.inputs['Specular IOR Level'].default_value = spec
    p.inputs['Metallic'].default_value = metallic
    if coat:
        p.inputs['Coat Weight'].default_value = coat
        p.inputs['Coat Roughness'].default_value = coat_rough
    if sheen:
        p.inputs['Sheen Weight'].default_value = sheen
        p.inputs['Sheen Roughness'].default_value = 0.5
    shader = p.outputs['BSDF']
    if translucency:
        tr = T.node('ShaderNodeBsdfTranslucent', Color=_rgba(trans_color) if trans_color else base)
        if nrm is not None:
            T.link(nrm, tr.inputs['Normal'])
        mx = T.node('ShaderNodeMixShader', Fac=translucency)
        T.link(shader, mx.inputs[1]); T.link(tr.outputs['BSDF'], mx.inputs[2])
        shader = mx.outputs['Shader']
    if emission is not None:
        ecol, estr = emission
        em = T.node('ShaderNodeEmission', Color=ecol if isinstance(ecol, bpy.types.NodeSocket) else _rgba(ecol), Strength=estr)
        ad = T.node('ShaderNodeAddShader')
        T.link(shader, ad.inputs[0]); T.link(em.outputs['Emission'], ad.inputs[1])
        shader = ad.outputs['Shader']
    if haze is not None:
        shader = _haze(T, shader, *haze)
    T.link(shader, out.inputs['Surface'])
    return p


def _start(name):
    m = new_material(name)
    T = _NT(m.node_tree)
    out = m.node_tree.nodes.new('ShaderNodeOutputMaterial')
    return m, T, out


# --------------------------------------------------------------------------- POLYHAVEN texture layer (optional)
# Real CC0 photo detail from Poly Haven (tools/polyhaven.py, manifest library/polyhaven.json) mixed INTO a recipe:
# the photo's light/dark pattern multiplies the procedural colour (`detail`), its hue pulls a little (`tint`), its
# displacement joins the procedural + washi-fibre bump (`bump`), its roughness varies the procedural roughness
# (`rough`) and its AO darkens crevices (`ao`). Facets (true normal), fibre and per-piece tone stay, so stone still
# reads as folded card stone. Kit meshes have no UVs: the photo is projected triplanar in object space (metres / `tile`),
# offset per piece (`piece_rand`) so neighbouring stones or planks never show the same patch. Off unless
# ph_enable() was called (build_set.py does it for sets with "polyhaven": true) and the files are cached;
# otherwise every recipe is exactly the procedural one.
PH = {'on': False, 'manifest': None, 'scale': 1.0, 'missing': set()}
_PH_STATS = {}
_PH_REPO = None


def _ph_repo():
    global _PH_REPO
    if _PH_REPO is None:
        import os
        _PH_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    return _PH_REPO


def ph_enable(on=True, manifest=None, scale=1.0):
    """Turn the Poly Haven layer on for recipes built from now on. `scale` multiplies every role's detail/tint/bump."""
    import json
    import os
    PH['on'] = bool(on)
    PH['scale'] = float(scale)
    path = manifest or os.path.join(_ph_repo(), 'library', 'polyhaven.json')
    PH['manifest'] = json.load(open(path)) if on and os.path.exists(path) else None
    return PH['manifest']


def ph_files(asset_id):
    """{map: abs path} for a cached Poly Haven asset (meta.json written by tools/polyhaven.py), or None."""
    import json
    import os
    mp = os.path.join(_ph_repo(), 'assets', 'polyhaven', asset_id, 'meta.json')
    if not os.path.exists(mp):
        if asset_id not in PH['missing']:
            PH['missing'].add(asset_id)
            print(f'  ! polyhaven: {asset_id} not cached (python3 tools/polyhaven.py sync); procedural only')
        return None
    meta = json.load(open(mp))
    return {k: os.path.join(_ph_repo(), v) for k, v in meta['files'].items() if os.path.exists(os.path.join(_ph_repo(), v))}


def ph_role(role):
    """Manifest entry for a texture role merged with an override dict ({'role': 'stone', 'tile': 2.0, ...})."""
    if not PH['on'] or not PH['manifest'] or not role:
        return None
    over = {}
    if isinstance(role, dict):
        over = dict(role)
        role = over.pop('role', None)
    ent = dict(PH['manifest'].get('textures', {}).get(role) or {})
    if not ent:
        return None
    ent.update(over)
    files = ph_files(ent['id'])
    if not files or 'diff' not in files:
        return None
    ent['files'] = files
    return ent


def _ph_image(path, non_color):
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = 'Non-Color' if non_color else 'sRGB'
    return img


def _ph_stats(img, srgb):
    """Mean of an image (linear RGB for colour maps), cached by path; used to normalise the photo to 1.0."""
    key = img.filepath
    if key in _PH_STATS:
        return _PH_STATS[key]
    import numpy as np
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(-1, 4)[::7, :3]
    if srgb and not img.is_float:
        px = np.where(px <= 0.04045, px / 12.92, ((px + 0.055) / 1.055) ** 2.4)
    m = tuple(float(v) for v in px.mean(axis=0))
    _PH_STATS[key] = m
    return m


def _ph_triplanar(T, img, vec, grain, interp='Linear'):
    """Three planar lookups blended by the object-space normal (sharp blend: facets stay crisp). `grain` = 'X'|'Y'|'Z'
    puts the image's V direction along that object axis on the faces that contain it (wood grain, bark, culms)."""
    tc = T.node('ShaderNodeTexCoord')
    nrm = T.node('ShaderNodeSeparateXYZ', Vector=tc.outputs['Normal'])
    p = T.node('ShaderNodeSeparateXYZ', Vector=vec)
    P = {'X': p.outputs['X'], 'Y': p.outputs['Y'], 'Z': p.outputs['Z']}
    pairs = {'X': ('Y', 'Z'), 'Y': ('X', 'Z'), 'Z': ('X', 'Y')}
    cols, ws = [], []
    for ax in 'XYZ':
        a, b = pairs[ax]
        if grain in (a, b) and b != grain:      # V must follow the grain axis
            a, b = b, a
        uv = T.node('ShaderNodeCombineXYZ', X=P[a], Y=P[b], Z=0.0)
        tx = T.node('ShaderNodeTexImage', Vector=uv.outputs[0])
        tx.image = img
        tx.interpolation = interp
        cols.append(tx.outputs['Color'])
        n = T.math('ABSOLUTE', nrm.outputs[ax])
        ws.append(T.math('POWER', n, 6.0))
    tot = T.math('ADD', T.math('ADD', ws[0], ws[1]), T.math('ADD', ws[2], 1e-5))
    out = None
    for c, w in zip(cols, ws):
        k = T.math('DIVIDE', w, tot)
        term = T.mix_rgb(1.0, c, T.node('ShaderNodeCombineXYZ', X=k, Y=k, Z=k).outputs[0], blend='MULTIPLY')
        out = term if out is None else T.mix_rgb(1.0, out, term, blend='ADD')
    return out


def _lum(T, col):
    """Luminance of a colour socket (Rec.709)."""
    s = T.node('ShaderNodeSeparateColor', Color=col)
    return T.math('ADD', T.math('MULTIPLY', s.outputs[0], 0.2126),
                  T.math('ADD', T.math('MULTIPLY', s.outputs[1], 0.7152), T.math('MULTIPLY', s.outputs[2], 0.0722)))


def ph_layer(T, ph, col, rough, height, *, pr=None, axis='Z', base_color=None):
    """Mix a Poly Haven texture set into a recipe's colour / roughness / height sockets. Returns the three new
    sockets (unchanged when the layer is off or the asset is missing). `axis` = the recipe's grain axis."""
    ent = ph_role(ph)
    if ent is None:
        return col, rough, height
    k = PH['scale']
    detail, tint = min(1.0, ent.get('detail', 0.7) * k), min(1.0, ent.get('tint', 0.2) * k)
    bump, rdet, aok = ent.get('bump', 0.5) * k, ent.get('rough', 0.5), ent.get('ao', 0.5)
    tile = float(ent.get('tile', 2.0))
    grain = ent.get('grain')
    grain = axis if grain == 'axis' else grain
    F = ent['files']
    # object-space metres / tile, offset per piece so neighbouring stones / planks sample different patches
    tc = T.node('ShaderNodeTexCoord')
    vec = T.node('ShaderNodeVectorMath', Vector=tc.outputs['Object'])
    vec.operation = 'SCALE'
    vec.inputs['Scale'].default_value = 1.0 / tile
    vec = vec.outputs['Vector']
    if pr is not None:
        off = T.node('ShaderNodeCombineXYZ', X=T.math('MULTIPLY', pr, 7.31), Y=T.math('MULTIPLY', pr, 3.17), Z=T.math('MULTIPLY', pr, 5.53))
        va = T.node('ShaderNodeVectorMath', Vector=vec)
        va.operation = 'ADD'
        T.link(off.outputs[0], va.inputs[1])
        vec = va.outputs['Vector']
    dimg = _ph_image(F['diff'], False)
    dmean = _ph_stats(dimg, True)
    dl = max(1e-3, 0.2126 * dmean[0] + 0.7152 * dmean[1] + 0.0722 * dmean[2])
    diff = _ph_triplanar(T, dimg, vec, grain)
    # detail: procedural colour x (photo luminance / its mean), softened by `detail`
    ratio = T.math('DIVIDE', _lum(T, diff), dl)
    ratio = T.math('MINIMUM', T.math('MULTIPLY_ADD', T.math('SUBTRACT', ratio, 1.0), detail, 1.0), 2.5)
    ratio = T.math('MAXIMUM', ratio, 0.05)
    col2 = _scale_col(T, col, ratio)
    # tint: toward the photo's own colour, brought to the procedural brightness
    if tint > 0:
        base_l = 0.2126 * base_color[0] + 0.7152 * base_color[1] + 0.0722 * base_color[2] if base_color else dl
        photo = _scale_col(T, diff, max(0.05, min(4.0, base_l / dl)))
        col2 = T.mix_rgb(tint, col2, photo)
    if 'ao' in F and aok > 0:
        aimg = _ph_image(F['ao'], True)
        am = max(0.05, _ph_stats(aimg, False)[0])
        aov = T.node('ShaderNodeSeparateColor', Color=_ph_triplanar(T, aimg, vec, grain)).outputs[0]
        aov = T.math('MINIMUM', T.math('DIVIDE', aov, am), 1.15)        # normalised: crevices darken, mean stays
        col2 = _scale_col(T, col2, T.math('MULTIPLY_ADD', T.math('SUBTRACT', aov, 1.0), aok, 1.0))
    r2 = rough
    if 'rough' in F and rdet > 0:
        rimg = _ph_image(F['rough'], True)
        rmean = _ph_stats(rimg, False)[0]
        rv = T.node('ShaderNodeSeparateColor', Color=_ph_triplanar(T, rimg, vec, grain)).outputs[0]
        r2 = T.math('MULTIPLY_ADD', T.math('SUBTRACT', rv, rmean), rdet, rough if isinstance(rough, bpy.types.NodeSocket) else float(rough))
        r2 = T.math('MAXIMUM', T.math('MINIMUM', r2, 1.0), 0.05)
    h2 = height
    if 'disp' in F and bump > 0:
        dimg2 = _ph_image(F['disp'], True)
        dm = _ph_stats(dimg2, False)[0]
        dv = T.node('ShaderNodeSeparateColor', Color=_ph_triplanar(T, dimg2, vec, grain)).outputs[0]
        dd = T.math('MULTIPLY', T.math('SUBTRACT', dv, dm), bump * 2.0)
        h2 = dd if height is None else T.math('ADD', height, dd)
    return col2, r2, h2


def stone_material(name, color=(0.30, 0.29, 0.27), color2=(0.45, 0.43, 0.39), *, moss=0.35, moss_color=(0.07, 0.10, 0.03),
                   grime=0.55, scale=1.0, wet=0.0, rough=0.86, paper=0.5, ao=True, flecks=0.25, haze=None, ph=None):
    """Granite / andesite: per-stone tone (piece_rand), mottled grain, mineral flecks, chipped cracks, moss on
    up-facing surfaces, vertical rain grime and crevice dirt (AO). Faceted (true normal) like folded card stone."""
    m, T, out = _start(name)
    pr = _attr(T, PIECE_ATTR)
    geo = T.node('ShaderNodeNewGeometry')
    v = _map(T, 'Object', (scale, scale, scale))
    vw = _map(T, 'Generated') if False else v
    big = _noise(T, v, 1.3, 6, 0.6)
    mid = _noise(T, v, 6.0, 8, 0.6, 0.3)
    tone = T.math('ADD', T.math('MULTIPLY', pr, 0.8), T.math('MULTIPLY', big.outputs['Fac'], 0.6))
    col = T.mix_rgb(_smooth(T, tone, 0.35, 1.05), color, color2)
    col = T.mix_rgb(T.math('MULTIPLY', T.math('SUBTRACT', mid.outputs['Fac'], 0.3), 0.5, clamp=True), col, tuple(c * 0.7 for c in color), blend='MIX')
    fl = _voronoi(T, v, 55.0)
    fls = T.math('GREATER_THAN', T.node('ShaderNodeSeparateColor', Color=fl.outputs['Color']).outputs[0], 1.0 - 0.12 * flecks * 4)
    col = T.mix_rgb(T.math('MULTIPLY', fls, 0.35), col, (0.75, 0.73, 0.70))
    # cracks: thin voronoi edges, masked by noise
    cr = _voronoi(T, v, 3.2, 'DISTANCE_TO_EDGE')
    crack = T.math('MULTIPLY', T.math('LESS_THAN', cr.outputs['Distance'], 0.025),
                   T.math('GREATER_THAN', _noise(T, v, 2.0, 2).outputs['Fac'], 0.55))
    # grime: vertical streaks (world z) + crevice dirt
    vz = _map(T, 'Object', (scale * 7, scale * 7, scale * 0.5))
    streak = _smooth(T, _noise(T, vz, 1.0, 3).outputs['Fac'], 0.45, 0.75)
    dirt = T.math('MULTIPLY', streak, grime * 0.55)
    if ao:
        dirt = T.math('ADD', dirt, T.math('MULTIPLY', T.math('SUBTRACT', 1.0, _ao(T, 0.25)), grime * 1.2), clamp=True)
    col = T.mix_rgb(T.math('ADD', dirt, T.math('MULTIPLY', crack, 0.8), clamp=True), col, (0.035, 0.033, 0.03))
    # moss: up-facing + noise patches, also creeping into crevices
    nz = T.node('ShaderNodeSeparateXYZ', Vector=geo.outputs['True Normal']).outputs['Z']
    mn = _noise(T, v, 1.8, 6, 0.65)
    mmask = T.math('MULTIPLY', _smooth(T, nz, 0.25, 0.85), _smooth(T, mn.outputs['Fac'], 0.62 - 0.25 * moss, 0.72 - 0.2 * moss))
    mmask = T.math('MULTIPLY', mmask, min(1.0, moss * 2.5))
    mcol = T.mix_rgb(_noise(T, v, 14, 4).outputs['Fac'], moss_color, tuple(c * 1.9 for c in moss_color))
    col = T.mix_rgb(mmask, col, mcol)
    if wet:
        col = _scale_col(T, col, 1.0 - 0.45 * wet)
    h = T.math('ADD', T.math('MULTIPLY', mid.outputs['Fac'], 0.6), T.math('MULTIPLY', crack, -0.5))
    h = T.math('ADD', h, T.math('MULTIPLY', mmask, 0.4))
    if paper:
        h = T.math('MULTIPLY_ADD', fibre_height(T, 28.0 * scale), 0.25 * paper, h)
    rgh = T.math('ADD', T.math('MULTIPLY', mid.outputs['Fac'], 0.12), rough - 0.06 - 0.5 * wet)
    rgh = T.math('ADD', rgh, T.math('MULTIPLY', mmask, 0.15), clamp=True)
    col, rgh, h = ph_layer(T, ph, col, rgh, h, pr=pr, base_color=color)
    _principled(T, out, col, rgh, h, bump=0.35, bump_dist=0.02, spec=0.35, haze=haze)
    return m


def plaster_material(name, color=(0.80, 0.78, 0.72), *, grime=0.5, cracks=0.35, scale=1.0, paper=0.7, splash=0.6,
                     ground_z=0.0, haze=None, ph=None):
    """White lime plaster (shikkui) as thick washi: soft value drift, hairline cracks, rain streaks running down,
    darker splash-back near the ground, faint fibre bump."""
    m, T, out = _start(name)
    pr = _attr(T, PIECE_ATTR)
    v = _map(T, 'Object', (scale, scale, scale))
    geo = T.node('ShaderNodeNewGeometry')
    wz = T.node('ShaderNodeSeparateXYZ', Vector=geo.outputs['Position']).outputs['Z']
    drift = _noise(T, v, 0.9, 5, 0.6)
    k = T.math('MULTIPLY_ADD', T.math('SUBTRACT', drift.outputs['Fac'], 0.5), 0.16, T.math('MULTIPLY_ADD', pr, 0.05, 0.97))
    col = _scale_col(T, color, k)
    vz = _map(T, 'Object', (scale * 9, scale * 9, scale * 0.35))
    streak = _smooth(T, _noise(T, vz, 1.0, 4, 0.6).outputs['Fac'], 0.5, 0.78)
    sp = T.math('SUBTRACT', 1.0, _smooth(T, T.math('SUBTRACT', wz, ground_z), 0.0, 0.9))
    sp = T.math('MULTIPLY', sp, _smooth(T, _noise(T, v, 5, 4).outputs['Fac'], 0.3, 0.7))
    dirt = T.math('ADD', T.math('MULTIPLY', streak, 0.35 * grime), T.math('MULTIPLY', sp, splash), clamp=True)
    col = T.mix_rgb(dirt, col, (0.30, 0.27, 0.22))
    cr = _voronoi(T, _map(T, 'Object', (scale * 1.5, scale * 1.5, scale * 1.5)), 2.0, 'DISTANCE_TO_EDGE')
    crack = T.math('MULTIPLY', T.math('LESS_THAN', cr.outputs['Distance'], 0.012),
                   T.math('GREATER_THAN', _noise(T, v, 1.3, 2).outputs['Fac'], 1.0 - 0.45 * cracks))
    col = T.mix_rgb(T.math('MULTIPLY', crack, 0.6), col, (0.25, 0.23, 0.2))
    h = T.math('ADD', T.math('MULTIPLY', _noise(T, v, 12, 6).outputs['Fac'], 0.3), T.math('MULTIPLY', crack, -0.6))
    h = T.math('MULTIPLY_ADD', fibre_height(T, 22.0 * scale), 0.5 * paper, h)
    rgh = T.math('MULTIPLY_ADD', drift.outputs['Fac'], 0.1, 0.84)
    col, rgh, h = ph_layer(T, ph, col, rgh, h, pr=pr, base_color=color)
    _principled(T, out, col, rgh, h, bump=0.12, bump_dist=0.01, spec=0.3, sheen=0.15, haze=haze)
    return m


def wood_material(name, color=(0.20, 0.12, 0.07), color2=None, *, axis='X', grain=1.0, rough=0.62, polish=0.0,
                  wear=0.3, paper=0.25, scale=1.0, flat=True, haze=None, ph=None):
    """Planed hinoki / sugi / dark-stained timber: long grain streaks along `axis` with growth rings and knots,
    per-plank tone and grain offset (piece_rand), roughness following the grain, optional polish (coat)."""
    m, T, out = _start(name)
    pr = _attr(T, PIECE_ATTR)
    c2 = color2 or tuple(c * 0.55 for c in color)
    sx, sy, sz = {'X': (0.22, 5.0, 5.0), 'Y': (5.0, 0.22, 5.0), 'Z': (5.0, 5.0, 0.22)}[axis]
    off = T.node('ShaderNodeCombineXYZ', X=T.math('MULTIPLY', pr, 41.0), Y=T.math('MULTIPLY', pr, 17.0), Z=T.math('MULTIPLY', pr, 7.0))
    tc = T.node('ShaderNodeTexCoord')
    vv = T.node('ShaderNodeVectorMath', Vector=tc.outputs['Object']); vv.operation = 'ADD'
    T.link(off.outputs[0], vv.inputs[1])
    vg = _map(T, vector=vv.outputs['Vector'], scale=(sx * grain * scale, sy * grain * scale, sz * grain * scale))
    rings = T.node('ShaderNodeTexWave', Vector=vg, Scale=1.6, Distortion=6.0, Detail=3.0)
    rings.wave_type = 'RINGS'
    rings.rings_direction = axis
    fine = _noise(T, _map(T, vector=vg, scale=(1, 6, 6) if axis == 'X' else (6, 1, 6) if axis == 'Y' else (6, 6, 1)), 3.0, 4, 0.5)
    g = T.math('ADD', T.math('MULTIPLY', rings.outputs['Fac'], 0.65), T.math('MULTIPLY', fine.outputs['Fac'], 0.5))
    tone = T.math('MULTIPLY_ADD', pr, 0.35, T.math('MULTIPLY', g, 0.75))
    col = T.mix_rgb(_smooth(T, tone, 0.25, 0.95), color, c2)
    big = _noise(T, _map(T, scale=(scale * 0.7,) * 3), 1.0, 3)
    col = _scale_col(T, col, T.math('MULTIPLY_ADD', big.outputs['Fac'], 0.3, 0.85))
    if wear:
        wmask = T.math('MULTIPLY', T.math('SUBTRACT', 1.0, _ao(T, 0.04, 4, inside=True)), wear * 2.0, clamp=True)
        col = T.mix_rgb(wmask, col, tuple(min(1, c * 1.8 + 0.05) for c in color))
    h = T.math('MULTIPLY', g, 0.5)
    if paper:
        h = T.math('MULTIPLY_ADD', fibre_height(T, 30.0 * scale), 0.25 * paper, h)
    rgh = T.math('ADD', T.math('MULTIPLY', g, 0.18), rough - 0.09 - 0.35 * polish, clamp=True)
    col, rgh, h = ph_layer(T, ph, col, rgh, h, pr=pr, axis=axis, base_color=color)
    _principled(T, out, col, rgh, h, bump=0.18, bump_dist=0.004, spec=0.45, coat=polish, coat_rough=0.12, flat=flat, haze=haze)
    return m


def tile_material(name, color=(0.085, 0.09, 0.10), *, lichen=0.25, rough=0.42, scale=1.0, haze=None, ph=None):
    """Fired kawara roof tile: dark blue-grey glaze-less clay, per-tile tone, soft sheen, pale lichen and
    run-off grime toward the eaves."""
    m, T, out = _start(name)
    pr = _attr(T, PIECE_ATTR)
    v = _map(T, 'Object', (scale,) * 3)
    k = T.math('MULTIPLY_ADD', pr, 0.5, 0.8)
    n = _noise(T, v, 3.0, 6)
    col = _scale_col(T, color, T.math('MULTIPLY_ADD', n.outputs['Fac'], 0.4, T.math('SUBTRACT', k, 0.2)))
    lm = T.math('MULTIPLY', _smooth(T, _noise(T, v, 1.6, 5, 0.7).outputs['Fac'], 0.66 - 0.2 * lichen, 0.75 - 0.2 * lichen),
                _smooth(T, _voronoi(T, v, 9).outputs['Distance'], 0.5, 0.15))
    col = T.mix_rgb(T.math('MULTIPLY', lm, 0.8), col, (0.33, 0.33, 0.24))
    rgh = T.math('ADD', T.math('MULTIPLY', n.outputs['Fac'], 0.2), T.math('ADD', rough - 0.1, T.math('MULTIPLY', lm, 0.4)), clamp=True)
    h = T.math('ADD', _noise(T, v, 18, 4).outputs['Fac'], T.math('MULTIPLY', lm, 0.6))
    col, rgh, h = ph_layer(T, ph, col, rgh, h, pr=pr, base_color=color)
    _principled(T, out, col, rgh, h, bump=0.15, bump_dist=0.005, spec=0.5, sheen=0.1, haze=haze)
    return m


def lacquer_material(name, color=(0.50, 0.06, 0.03), *, under=(0.05, 0.03, 0.02), wear=0.3, rough=0.28, scale=1.0, haze=None):
    """Urushi / vermilion lacquer: deep colour under a glossy coat, worn through on edges and in patches to the
    dark wood beneath, faint brush texture."""
    m, T, out = _start(name)
    v = _map(T, 'Object', (scale,) * 3)
    n = _noise(T, v, 2.0, 6, 0.6)
    worn = T.math('MULTIPLY', _smooth(T, n.outputs['Fac'], 0.72 - 0.2 * wear, 0.78 - 0.2 * wear), wear * 2.0, clamp=True)
    worn = T.math('ADD', worn, T.math('MULTIPLY', T.math('SUBTRACT', 1.0, _ao(T, 0.03, 4, inside=True)), wear * 2.5), clamp=True)
    col = _scale_col(T, color, T.math('MULTIPLY_ADD', _noise(T, v, 0.6, 3).outputs['Fac'], 0.35, 0.82))
    col = T.mix_rgb(worn, col, under)
    brush = _noise(T, _map(T, vector=v, scale=(1, 1, 30)), 6, 2)
    rgh = T.math('ADD', T.math('MULTIPLY', worn, 0.35), rough, clamp=True)
    _principled(T, out, col, rgh, brush.outputs['Fac'], bump=0.03, bump_dist=0.003, spec=0.5, coat=0.8, coat_rough=0.08, haze=haze)
    return m


def shoji_material(name, color=(0.90, 0.87, 0.78), *, translucency=0.62, glow=None, scale=1.0, stains=0.3):
    """Shoji washi: thin, fibrous, light shines through (Translucent BSDF; thicker fibres hold back light), a few
    age stains. `glow=(rgb, strength)` adds a faint self-light for night interiors without a lamp behind."""
    m, T, out = _start(name)
    h = fibre_height(T, 55.0 * scale)
    v = _map(T, 'Object', (scale,) * 3)
    st = T.math('MULTIPLY', _smooth(T, _noise(T, v, 1.4, 5).outputs['Fac'], 0.62, 0.8), stains)
    col = T.mix_rgb(st, color, (0.62, 0.52, 0.36))
    col = _scale_col(T, col, T.math('MULTIPLY_ADD', h, -0.12, 1.02))
    tr = T.math('MULTIPLY_ADD', h, -0.18, translucency)
    _principled(T, out, col, 0.85, h, bump=0.08, bump_dist=0.002, spec=0.2, sheen=0.3, translucency=tr,
                trans_color=(1.0, 0.86, 0.62), emission=glow)
    return m


def tatami_material(name, color=(0.46, 0.42, 0.22), *, axis='X', scale=1.0, ph=None):
    """Woven igusa rush: fine weave bands across `axis`, warp threads, per-mat tone, a little sheen."""
    m, T, out = _start(name)
    pr = _attr(T, PIECE_ATTR)
    v = _map(T, 'Object', (scale,) * 3)
    w = T.node('ShaderNodeTexWave', Vector=v, Scale=95.0, Distortion=0.6, Detail=1.0)
    w.wave_type = 'BANDS'
    w.bands_direction = axis
    w.wave_profile = 'TRI'
    n = _noise(T, _map(T, vector=v, scale=(0.3, 25, 1) if axis == 'X' else (25, 0.3, 1)), 4, 3)
    g = T.math('MULTIPLY_ADD', n.outputs['Fac'], 0.4, T.math('MULTIPLY', w.outputs['Fac'], 0.6))
    col = _scale_col(T, color, T.math('MULTIPLY_ADD', g, 0.35, T.math('MULTIPLY_ADD', pr, 0.25, 0.68)))
    col, rgh, h = ph_layer(T, ph, col, T.math('MULTIPLY_ADD', g, 0.2, 0.55), g, pr=pr, axis=axis, base_color=color)
    _principled(T, out, col, rgh, h, bump=0.25, bump_dist=0.002, spec=0.35, sheen=0.4)
    return m


def gravel_material(name, color=(0.34, 0.33, 0.30), *, scale=9.0, wet=0.0, moss=0.0, haze=None, ph=None):
    """Raked courtyard gravel / pebble ground: voronoi pebbles with their own tones, dark gaps, larger value
    drift and optional wetness (puddle gloss) and moss."""
    m, T, out = _start(name)
    v = _map(T, 'Object', (1, 1, 1))
    vo = _voronoi(T, v, scale)
    sm = _voronoi(T, v, scale * 2.7)
    cell = T.node('ShaderNodeSeparateColor', Color=vo.outputs['Color']).outputs[0]
    peb = T.math('SUBTRACT', 1.0, T.math('MULTIPLY', vo.outputs['Distance'], 1.6), clamp=True)
    peb2 = T.math('SUBTRACT', 1.0, T.math('MULTIPLY', sm.outputs['Distance'], 1.6), clamp=True)
    h = T.math('MAXIMUM', peb, T.math('MULTIPLY', peb2, 0.7))
    drift = _noise(T, v, 0.25, 4)
    col = _scale_col(T, color, T.math('MULTIPLY_ADD', cell, 0.6, T.math('MULTIPLY_ADD', drift.outputs['Fac'], 0.4, 0.45)))
    col = T.mix_rgb(_smooth(T, h, 0.35, 0.05), col, (0.03, 0.028, 0.025))
    puddle = T.math('MULTIPLY', _smooth(T, _noise(T, v, 0.35, 3).outputs['Fac'], 0.6, 0.66), wet)
    rgh = T.math('SUBTRACT', T.math('MULTIPLY_ADD', cell, 0.2, 0.75), T.math('ADD', T.math('MULTIPLY', puddle, 0.7), wet * 0.25), clamp=True)
    if moss:
        mm = T.math('MULTIPLY', _smooth(T, _noise(T, v, 0.6, 5).outputs['Fac'], 0.62 - 0.2 * moss, 0.7 - 0.2 * moss), _smooth(T, h, 0.3, 0.0))
        col = T.mix_rgb(mm, col, (0.06, 0.09, 0.03))
    col = _scale_col(T, col, T.math('SUBTRACT', 1.0, T.math('MULTIPLY', puddle, 0.35)))
    hb = T.math('MULTIPLY', h, T.math('SUBTRACT', 1.0, puddle))
    col, rgh, hb = ph_layer(T, ph, col, rgh, hb, base_color=color)
    _principled(T, out, col, rgh, hb, bump=0.6, bump_dist=0.02, flat=False, spec=0.4, haze=haze)
    return m


def earth_material(name, color=(0.16, 0.12, 0.08), *, moss=0.3, leaves=0.0, leaf_color=(0.25, 0.12, 0.05), scale=1.0, wet=0.0, haze=None, ph=None):
    """Forest floor / packed earth: soil drift, moss patches, fallen-leaf litter speckle, small stones."""
    m, T, out = _start(name)
    v = _map(T, 'Object', (scale,) * 3)
    a = _noise(T, v, 0.4, 6, 0.6)
    b = _noise(T, v, 3.5, 8, 0.6)
    col = _scale_col(T, color, T.math('MULTIPLY_ADD', a.outputs['Fac'], 0.6, T.math('MULTIPLY_ADD', b.outputs['Fac'], 0.4, 0.5)))
    mm = T.math('MULTIPLY', _smooth(T, _noise(T, v, 0.5, 5).outputs['Fac'], 0.6 - 0.25 * moss, 0.68 - 0.25 * moss), 1.0 if moss else 0.0)
    col = T.mix_rgb(mm, col, T.mix_rgb(b.outputs['Fac'], (0.05, 0.08, 0.025), (0.12, 0.15, 0.04)))
    lf = _voronoi(T, v, 14.0)
    lmask = T.math('MULTIPLY', T.math('GREATER_THAN', T.node('ShaderNodeSeparateColor', Color=lf.outputs['Color']).outputs[1], 1.0 - 0.5 * leaves),
                   T.math('LESS_THAN', lf.outputs['Distance'], 0.35))
    col = T.mix_rgb(lmask, col, T.mix_rgb(T.node('ShaderNodeSeparateColor', Color=lf.outputs['Color']).outputs[2], leaf_color, tuple(c * 0.6 for c in leaf_color)))
    h = T.math('ADD', T.math('MULTIPLY', b.outputs['Fac'], 0.6), T.math('MULTIPLY', lmask, 0.15))
    rgh = T.math('SUBTRACT', 0.92, T.math('ADD', T.math('MULTIPLY', mm, -0.05), wet * 0.4))
    col, rgh, h = ph_layer(T, ph, col, rgh, h, base_color=color)
    _principled(T, out, col, rgh, h, bump=0.5, bump_dist=0.02, flat=False, spec=0.3, haze=haze)
    return m


def bamboo_material(name, color=(0.30, 0.36, 0.10), *, age=0.4, scale=1.0, haze=None, ph=None):
    """Bamboo culm skin: waxy green to yellowed, fine vertical streaks, darker lichen blotches on older culms,
    per-culm hue (piece_rand). Glossy but soft."""
    m, T, out = _start(name)
    pr = _attr(T, PIECE_ATTR)
    v = _map(T, 'Object', (scale,) * 3)
    streak = _noise(T, _map(T, vector=v, scale=(40, 40, 0.6)), 2.0, 3)
    col = T.mix_rgb(T.math('MULTIPLY', pr, age * 1.6, clamp=True), color, (0.48, 0.42, 0.18))
    col = _scale_col(T, col, T.math('MULTIPLY_ADD', streak.outputs['Fac'], 0.35, 0.8))
    bl = T.math('MULTIPLY', _smooth(T, _noise(T, v, 3.0, 4).outputs['Fac'], 0.66, 0.74), age)
    col = T.mix_rgb(bl, col, (0.10, 0.10, 0.07))
    col, rgh, h = ph_layer(T, ph, col, T.math('MULTIPLY_ADD', bl, 0.4, 0.36), streak.outputs['Fac'], pr=pr, axis='Z', base_color=color)
    _principled(T, out, col, rgh, h, bump=0.08, bump_dist=0.003, spec=0.55, sheen=0.1, haze=haze, flat=False)
    return m


def bark_material(name, color=(0.10, 0.075, 0.055), *, scale=1.0, moss=0.2, haze=None, ph=None):
    """Pine / cherry bark: plated cracks stretched along the trunk (object Z), moss on one side."""
    m, T, out = _start(name)
    v = _map(T, 'Object', (scale * 4, scale * 4, scale * 1.2))
    vo = _voronoi(T, v, 3.0, 'DISTANCE_TO_EDGE')
    plates = _smooth(T, vo.outputs['Distance'], 0.0, 0.12)
    n = _noise(T, v, 4, 6)
    col = _scale_col(T, color, T.math('MULTIPLY_ADD', plates, 0.7, T.math('MULTIPLY_ADD', n.outputs['Fac'], 0.4, 0.2)))
    geo = T.node('ShaderNodeNewGeometry')
    nx = T.node('ShaderNodeSeparateXYZ', Vector=geo.outputs['Normal']).outputs['Y']
    mm = T.math('MULTIPLY', _smooth(T, nx, 0.0, 0.9), _smooth(T, _noise(T, v, 1.0, 4).outputs['Fac'], 0.55 - 0.3 * moss, 0.65 - 0.3 * moss))
    col = T.mix_rgb(T.math('MULTIPLY', mm, 1.0 if moss else 0.0), col, (0.06, 0.09, 0.03))
    col, rgh, h = ph_layer(T, ph, col, 0.9, T.math('ADD', plates, T.math('MULTIPLY', n.outputs['Fac'], 0.3)), axis='Z', base_color=color)
    _principled(T, out, col, rgh, h, bump=0.6, bump_dist=0.02, flat=False, spec=0.3, haze=haze)
    return m


def foliage_material(name, color=(0.06, 0.10, 0.04), *, trans=(0.25, 0.35, 0.06), translucency=0.35, var=0.35, haze=None, sss=None):
    """Leaves / needles / blossoms as folded paper: per-facet and per-cluster tone, light passing through."""
    m, T, out = _start(name)
    pr = _attr(T, PIECE_ATTR)
    fr = _attr(T, FACET_ATTR)
    k = T.math('MULTIPLY_ADD', T.math('ADD', pr, fr), var, 1.0 - var)
    col = _scale_col(T, color, k)
    h = fibre_height(T, 30.0)
    _principled(T, out, col, 0.6, h, bump=0.1, bump_dist=0.004, spec=0.35, sheen=0.3, translucency=translucency,
                trans_color=trans, haze=haze)
    return m


def glow_window_material(name, color=(1.0, 0.55, 0.22), strength=6.0, *, var=0.5):
    """Lit interior seen through a window or lantern paper: warm emission with a soft uneven falloff."""
    m, T, out = _start(name)
    v = _map(T, 'Object', (1, 1, 1))
    n = _noise(T, v, 1.5, 3)
    pr = _attr(T, PIECE_ATTR)
    k = T.math('MULTIPLY', strength, T.math('MULTIPLY_ADD', T.math('ADD', n.outputs['Fac'], pr), var * 0.5, 1.0 - var * 0.5))
    em = T.node('ShaderNodeEmission', Color=_rgba(color), Strength=k)
    T.link(em.outputs['Emission'], out.inputs['Surface'])
    return m


def iron_material(name, color=(0.05, 0.048, 0.045), rust=0.3):
    """Black iron fittings (door studs, hinges): rough dark metal with rust bloom."""
    m, T, out = _start(name)
    v = _map(T, 'Object', (1, 1, 1))
    n = _noise(T, v, 8, 6)
    r = T.math('MULTIPLY', _smooth(T, n.outputs['Fac'], 0.6 - 0.2 * rust, 0.7 - 0.2 * rust), 1.0)
    col = T.mix_rgb(r, color, (0.16, 0.06, 0.025))
    _principled(T, out, col, T.math('MULTIPLY_ADD', r, 0.4, 0.45), n.outputs['Fac'], bump=0.3, bump_dist=0.003,
                metallic=T.math('SUBTRACT', 0.9, r) if False else 0.8, spec=0.5)
    return m


def gold_material(name, color=(0.85, 0.62, 0.25)):
    """Gilded metal (shachihoko, crests)."""
    m, T, out = _start(name)
    v = _map(T, 'Object', (1, 1, 1))
    n = _noise(T, v, 20, 4)
    _principled(T, out, _rgba(color), T.math('MULTIPLY_ADD', n.outputs['Fac'], 0.15, 0.22), n.outputs['Fac'], bump=0.1,
                bump_dist=0.002, metallic=1.0, spec=0.5)
    return m


def rain_material(name='LO_Rain'):
    """Rain streaks: mostly transparent, a little gloss and transmission so they catch backlight."""
    m, T, out = _start(name)
    lw = T.node('ShaderNodeLightPath')
    tr = T.node('ShaderNodeBsdfTransparent')
    gl = T.node('ShaderNodeBsdfGlass', Roughness=0.05, IOR=1.33)
    mx = T.node('ShaderNodeMixShader', Fac=0.18)
    T.link(tr.outputs['BSDF'], mx.inputs[1]); T.link(gl.outputs['BSDF'], mx.inputs[2])
    T.link(mx.outputs['Shader'], out.inputs['Surface'])
    m.blend_method = 'BLEND' if hasattr(m, 'blend_method') else None
    return m
