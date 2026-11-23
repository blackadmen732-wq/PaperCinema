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
