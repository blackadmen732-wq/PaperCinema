"""Blender test: the "demon blood slash" in the Lantern Origami style.

Run (Blender stays closed, renders straight to files):
  blender -b -P blender/demon_slash_test.py -- --state impact --out output/blender/slash-impact.png
  states: before | impact | after      options: --samples 64 --res 960

Look: a folded-paper warrior cut diagonally in half. The cut faces show stacked red paper layers,
a crimson sumi-ink brush stroke hangs in the air where the blade passed, glossy red PAINT sprays and
drips (never blood), red and cream paper confetti flies, and warm light glows through layered paper.
"""
import bpy, bmesh, math, random, sys
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(name, default):
    return argv[argv.index('--' + name) + 1] if '--' + name in argv else default
STATE = arg('state', 'impact')
OUT = arg('out', f'output/blender/slash-{STATE}.png')
SAMPLES = int(arg('samples', 64))
RES = int(arg('res', 960))
random.seed(7)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---------------------------------------------------------------- render settings
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = SAMPLES
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.03
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 6
scene.cycles.transmission_bounces = 6
scene.cycles.sample_clamp_indirect = 5
scene.render.resolution_x = RES
scene.render.resolution_y = int(RES / 2.39)
scene.render.film_transparent = False
scene.view_settings.view_transform = 'AgX'
scene.view_settings.exposure = -0.4
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = OUT

world = bpy.data.worlds.new('World'); scene.world = world
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.012, 0.008, 0.008, 1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.4

# ---------------------------------------------------------------- materials
def mat(name, build):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    build(nt, out)
    return m

def paper_mat(name, color, translucency=0.38, bump=0.15, rough=0.85):
    """Washi: diffuse + translucent (light glows through), fibre bump."""
    def b(nt, out):
        noise = nt.nodes.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = 180; noise.inputs['Detail'].default_value = 8
        wave = nt.nodes.new('ShaderNodeTexWave'); wave.inputs['Scale'].default_value = 60; wave.inputs['Distortion'].default_value = 18
        mixf = nt.nodes.new('ShaderNodeMix'); mixf.data_type = 'FLOAT'; mixf.inputs['Factor'].default_value = 0.5
        nt.links.new(noise.outputs['Fac'], mixf.inputs['A']); nt.links.new(wave.outputs['Fac'], mixf.inputs['B'])
        bumpn = nt.nodes.new('ShaderNodeBump'); bumpn.inputs['Strength'].default_value = bump; bumpn.inputs['Distance'].default_value = 0.002
        nt.links.new(mixf.outputs['Result'], bumpn.inputs['Height'])
        p = nt.nodes.new('ShaderNodeBsdfPrincipled')
        p.inputs['Base Color'].default_value = (*color, 1); p.inputs['Roughness'].default_value = rough
        p.inputs['Sheen Weight'].default_value = 0.15
        nt.links.new(bumpn.outputs['Normal'], p.inputs['Normal'])
        tr = nt.nodes.new('ShaderNodeBsdfTranslucent'); tr.inputs['Color'].default_value = (*color, 1)
        nt.links.new(bumpn.outputs['Normal'], tr.inputs['Normal'])
        mx = nt.nodes.new('ShaderNodeMixShader'); mx.inputs['Fac'].default_value = translucency
        nt.links.new(p.outputs['BSDF'], mx.inputs[1]); nt.links.new(tr.outputs['BSDF'], mx.inputs[2])
        nt.links.new(mx.outputs['Shader'], out.inputs['Surface'])
    return mat(name, b)

def principled(name, color, rough=0.3, metal=0.0, emit=None, strength=0.0, coat=0.0, aniso=0.0):
    def b(nt, out):
        p = nt.nodes.new('ShaderNodeBsdfPrincipled')
        p.inputs['Base Color'].default_value = (*color, 1); p.inputs['Roughness'].default_value = rough
        p.inputs['Metallic'].default_value = metal; p.inputs['Coat Weight'].default_value = coat
        p.inputs['Anisotropic'].default_value = aniso
        if emit:
            p.inputs['Emission Color'].default_value = (*emit, 1); p.inputs['Emission Strength'].default_value = strength
        nt.links.new(p.outputs['BSDF'], out.inputs['Surface'])
    return mat(name, b)

def emission(name, color, strength):
    def b(nt, out):
        e = nt.nodes.new('ShaderNodeEmission'); e.inputs['Color'].default_value = (*color, 1); e.inputs['Strength'].default_value = strength
        nt.links.new(e.outputs['Emission'], out.inputs['Surface'])
    return mat(name, b)

def ink_stroke_mat():
    """Crimson sumi-ink brush stroke: glowing core, ragged dry-brush edges, fades toward the tail (u)."""
    def b(nt, out):
        tc = nt.nodes.new('ShaderNodeTexCoord')
        sep = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(tc.outputs['UV'], sep.inputs['Vector'])
        noise = nt.nodes.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = 14; noise.inputs['Detail'].default_value = 12
        nt.links.new(tc.outputs['UV'], noise.inputs['Vector'])
        # v across the stroke: 0..1 → distance from centre line
        edge = nt.nodes.new('ShaderNodeMath'); edge.operation = 'PINGPONG'; edge.inputs[1].default_value = 0.5
        nt.links.new(sep.outputs['Y'], edge.inputs[0])
        rag = nt.nodes.new('ShaderNodeMath'); rag.operation = 'MULTIPLY_ADD'; rag.inputs[1].default_value = 0.35; rag.inputs[2].default_value = -0.05
        nt.links.new(noise.outputs['Fac'], rag.inputs[0])
        body = nt.nodes.new('ShaderNodeMath'); body.operation = 'LESS_THAN'
        nt.links.new(rag.outputs['Value'], body.inputs[0]); nt.links.new(edge.outputs['Value'], body.inputs[1])   # inside the ragged edge
        tail = nt.nodes.new('ShaderNodeMapRange'); tail.inputs['From Min'].default_value = 1.0; tail.inputs['From Max'].default_value = 0.2
        nt.links.new(sep.outputs['X'], tail.inputs['Value'])
        alpha = nt.nodes.new('ShaderNodeMath'); alpha.operation = 'MULTIPLY'
        nt.links.new(body.outputs['Value'], alpha.inputs[0]); nt.links.new(tail.outputs['Result'], alpha.inputs[1])
        em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (0.9, 0.02, 0.01, 1); em.inputs['Strength'].default_value = 3.5
        dark = nt.nodes.new('ShaderNodeBsdfPrincipled'); dark.inputs['Base Color'].default_value = (0.25, 0.0, 0.0, 1); dark.inputs['Roughness'].default_value = 0.2
        glow = nt.nodes.new('ShaderNodeMixShader'); glow.inputs['Fac'].default_value = 0.6
        nt.links.new(dark.outputs['BSDF'], glow.inputs[1]); nt.links.new(em.outputs['Emission'], glow.inputs[2])
        tr = nt.nodes.new('ShaderNodeBsdfTransparent')
        mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(alpha.outputs['Value'], mix.inputs['Fac'])
        nt.links.new(tr.outputs['BSDF'], mix.inputs[1]); nt.links.new(glow.outputs['Shader'], mix.inputs[2])
        nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    m = mat('InkStroke', b)
    return m

M = {
    'cream': paper_mat('PaperCream', (0.72, 0.66, 0.55)),
    'crimson': paper_mat('PaperCrimson', (0.55, 0.05, 0.04), translucency=0.45),
    'indigo': paper_mat('PaperIndigo', (0.10, 0.11, 0.16), translucency=0.25),
    'char': paper_mat('PaperCharcoal', (0.035, 0.03, 0.03), translucency=0.15),
    'layer1': paper_mat('Layer1', (0.20, 0.03, 0.02), translucency=0.6),
    'layer2': paper_mat('Layer2', (0.08, 0.02, 0.02), translucency=0.5),
    'layer3': paper_mat('Layer3', (0.03, 0.015, 0.015), translucency=0.4),
    'cutface': paper_mat('CutFaceRedPaper', (0.62, 0.02, 0.02), translucency=0.5, bump=0.4),
    'paint': principled('RedPaint', (0.6, 0.0, 0.01), rough=0.08, coat=1.0),
    'steel': principled('BlackSteel', (0.05, 0.05, 0.06), rough=0.14, metal=1.0, aniso=0.6),
    'edge': principled('DemonEdge', (0.2, 0.0, 0.0), rough=0.3, emit=(1.0, 0.06, 0.02), strength=14),
    'gold': principled('Gold', (0.8, 0.55, 0.2), rough=0.25, metal=1.0),
    'wrap': paper_mat('HandleWrap', (0.03, 0.03, 0.035), translucency=0.1),
    'glow': emission('BackGlow', (1.0, 0.45, 0.12), 1.6),
    'glowred': emission('BackGlowRed', (1.0, 0.08, 0.03), 1.2),
    'ink': ink_stroke_mat(),
}

# ---------------------------------------------------------------- helpers
def obj_from_bm(name, bm, material):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); scene.collection.objects.link(ob)
    me.materials.append(material)
    for p in me.polygons: p.use_smooth = False
    return ob

def wave_card(name, y, top, amp, freq, phase, width, material, z0=-0.1):
    """A kirigami backdrop layer: flat paper card with a wavy cut top edge (in the XZ plane at depth y)."""
    bm = bmesh.new()
    n = 90
    verts_top, verts_bot = [], []
    for i in range(n + 1):
        x = -width / 2 + width * i / n
        z = top + amp * math.sin(x * freq + phase) + amp * 0.4 * math.sin(x * freq * 2.7 + phase * 1.3)
        verts_top.append(bm.verts.new((x, y, z))); verts_bot.append(bm.verts.new((x, y, z0)))
    for i in range(n):
        bm.faces.new((verts_bot[i], verts_bot[i + 1], verts_top[i + 1], verts_top[i]))
    return obj_from_bm(name, bm, material)

# ---------------------------------------------------------------- set: dark diorama with layered paper glowing from behind
bpy.ops.mesh.primitive_plane_add(size=14, location=(0, 0, 0))
ground = bpy.context.object; ground.data.materials.append(M['char'])
glow_back = bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 4.2, 1.4), rotation=(math.radians(90), 0, 0))
gb = bpy.context.object; gb.scale = (12, 4, 1); gb.data.materials.append(M['glow'])
wave_card('Layer1', 3.6, 1.9, 0.25, 2.1, 0.4, 12, M['layer1'])
wave_card('Layer2', 3.0, 1.45, 0.22, 2.6, 1.7, 12, M['layer2'])
wave_card('Layer3', 2.3, 0.95, 0.18, 3.1, 2.9, 12, M['layer3'])
wave_card('LayerRed', 3.3, 1.65, 0.2, 1.7, 5.1, 12, M['glowred']) .hide_render = STATE == 'before'

# ---------------------------------------------------------------- the paper warrior (faceted origami body)
def warrior_bm():
    bm = bmesh.new()
    # hakama / skirt: 6-sided flared prism
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.34, radius2=0.2, depth=0.9,
                          matrix=Matrix.Translation((0, 0, 0.45)))
    # torso: 5-sided prism
    bmesh.ops.create_cone(bm, cap_ends=True, segments=5, radius1=0.17, radius2=0.22, depth=0.55,
                          matrix=Matrix.Translation((0, 0, 1.18)))
    # shoulders / sleeves: folded wedges
    for sx in (-1, 1):
        bmesh.ops.create_cone(bm, cap_ends=True, segments=4, radius1=0.06, radius2=0.13, depth=0.36,
                              matrix=Matrix.Translation((sx * 0.3, 0, 1.25)) @ Matrix.Rotation(sx * 0.35, 4, 'Y'))
    # head: low icosphere
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.11, matrix=Matrix.Translation((0, 0, 1.6)) @ Matrix.Scale(1.15, 4, (0, 0, 1)))
    # straw hat (kasa): shallow pleated cone
    bmesh.ops.create_cone(bm, cap_ends=False, segments=16, radius1=0.36, radius2=0.0, depth=0.16,
                          matrix=Matrix.Translation((0, 0, 1.76)))
    for f in bm.faces:
        f.smooth = False
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm

# cut plane: a diagonal kesa-giri line from the right shoulder down through the left hip
cut_point = Vector((0.0, 0.0, 1.05))
cut_normal = Vector((0.55, -0.15, 0.82)).normalized()

def half(name, keep_upper):
    bm = warrior_bm()
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=cut_point, plane_no=cut_normal,
                                 clear_inner=keep_upper, clear_outer=not keep_upper)
    cut_edges = [e for e in res['geom_cut'] if isinstance(e, bmesh.types.BMEdge)]
    cap = bmesh.ops.holes_fill(bm, edges=cut_edges, sides=0)
    ob = obj_from_bm(name, bm, M['cream'])
    ob.data.materials.append(M['cutface'])
    for f in ob.data.polygons:                       # cap faces (on the cut plane) get the red paper layers
        c = ob.data.vertices[f.vertices[0]].co
        if abs((Vector(c) - cut_point).dot(cut_normal)) < 0.004 and abs(Vector(f.normal).dot(cut_normal)) > 0.95:
            f.material_index = 1
    return ob

if STATE == 'before':
    bm = warrior_bm(); body = obj_from_bm('Warrior', bm, M['cream'])
    halves = [body]
else:
    lower = half('WarriorLower', keep_upper=False)
    upper = half('WarriorUpper', keep_upper=True)
    slide = 0.06 if STATE == 'impact' else 0.32
    tip = 0.05 if STATE == 'impact' else 0.38
    slide_dir = Vector((cut_normal.z, 0, -cut_normal.x)).normalized()   # down along the cut plane
    upper.location = slide_dir * slide + cut_normal * 0.01
    upper.rotation_euler = (0, -tip, 0)
    halves = [lower, upper]

# interior glow inside the paper body (amber lantern light)
light = bpy.data.lights.new('Inner', 'POINT'); light.energy = 4; light.color = (1.0, 0.55, 0.2); light.shadow_soft_size = 0.05
lo = bpy.data.objects.new('Inner', light); lo.location = (0, 0, 1.15); scene.collection.objects.link(lo)

# ---------------------------------------------------------------- the demonic blade (mid / after swing)
def blade_bm(length=0.95, w0=0.034, w1=0.024, sori=0.03):
    bm = bmesh.new()
    n = 30
    top, bot = [], []
    for i in range(n + 1):
        u = i / n
        x = u * length; yc = -4 * sori * u * (1 - u); w = w0 + (w1 - w0) * u
        if u > 0.93: w *= (1 - (u - 0.93) / 0.07 * 0.95)
        top.append(bm.verts.new((x, 0, yc))); bot.append(bm.verts.new((x, 0, yc - w)))
    for i in range(n):
        bm.faces.new((bot[i], bot[i + 1], top[i + 1], top[i]))
    bmesh.ops.solidify(bm, geom=bm.faces[:], thickness=0.005)
    return bm

blade = obj_from_bm('Blade', blade_bm(), M['steel'])
edge_bm = bmesh.new()                                  # glowing crimson temper edge (thin strip under the blade)
n = 30
a_, b_ = [], []
for i in range(n + 1):
    u = i / n; x = u * 0.95; yc = -4 * 0.03 * u * (1 - u); w = 0.034 + (0.024 - 0.034) * u
    a_.append(edge_bm.verts.new((x, 0.0032, yc - w + 0.001))); b_.append(edge_bm.verts.new((x, 0.0032, yc - w * 0.55)))
for i in range(n):
    edge_bm.faces.new((a_[i], a_[i + 1], b_[i + 1], b_[i]))
edge = obj_from_bm('DemonEdge', edge_bm, M['edge']); edge.parent = blade
bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.17, 0, -0.016)); hilt = bpy.context.object
hilt.scale = (0.32, 0.025, 0.032); hilt.data.materials.append(M['wrap']); hilt.parent = blade
bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.045, depth=0.006, location=(-0.004, 0, -0.016), rotation=(0, math.radians(90), 0))
tsuba = bpy.context.object; tsuba.data.materials.append(M['gold']); tsuba.parent = blade
if STATE == 'before':
    blade.location = (-0.75, -0.35, 1.75); blade.rotation_euler = (math.radians(90), math.radians(40), math.radians(-20))
else:
    blade.location = (0.55, -0.45, 0.55); blade.rotation_euler = (math.radians(90), math.radians(-35), math.radians(15))

# ---------------------------------------------------------------- the slash: crimson ink brush stroke in the air
if STATE != 'before':
    bm = bmesh.new()
    n = 64
    rows = []
    for i in range(n + 1):
        u = i / n
        # diagonal kesa-giri stroke along the cut: right shoulder (upper right) → left hip (lower left), slight arc
        A = Vector((0.62, -0.42, 1.72)); B = Vector((-0.58, -0.42, 0.42))
        dirv = (B - A).normalized(); perp = Vector((-dirv.z, 0, dirv.x))
        p = A + (B - A) * u + perp * (0.12 * math.sin(math.pi * u))
        width = 0.075 * math.sin(math.pi * min(1, u * 1.15 + 0.03)) ** 0.5 * (1.0 if STATE == 'impact' else 0.75)
        side = perp * width
        rows.append((bm.verts.new(p - side), bm.verts.new(p + side)))
    uv = bm.loops.layers.uv.new()
    for i in range(n):
        f = bm.faces.new((rows[i][0], rows[i + 1][0], rows[i + 1][1], rows[i][1]))
        coords = [(1 - i / n, 0), (1 - (i + 1) / n, 0), (1 - (i + 1) / n, 1), (1 - i / n, 1)]   # u = 0 at the newest end
        for loop, c in zip(f.loops, coords): loop[uv].uv = c
    stroke = obj_from_bm('InkSlash', bm, M['ink'])
    stroke.visible_shadow = False
    sl = bpy.data.lights.new('SlashLight', 'POINT'); sl.energy = 10; sl.color = (1.0, 0.08, 0.03); sl.shadow_soft_size = 0.3
    slo = bpy.data.objects.new('SlashLight', sl); slo.location = (0.1, -0.9, 1.1); scene.collection.objects.link(slo)

# ---------------------------------------------------------------- red paint (not blood): spray, drips, pool
if STATE != 'before':
    mb = bpy.data.metaballs.new('Paint'); mb.resolution = 0.012; mb.render_resolution = 0.008
    mbo = bpy.data.objects.new('Paint', mb); scene.collection.objects.link(mbo); mb.materials.append(M['paint'])
    spread = 0.15 if STATE == 'impact' else 0.45
    for i in range(46 if STATE == 'impact' else 60):
        t = random.random()
        d = cut_normal * (0.05 + spread * t) + Vector((random.uniform(-0.25, 0.35), random.uniform(-0.25, -0.05), random.uniform(-0.1, 0.2))) * t
        e = mb.elements.new(); e.co = cut_point + d + Vector((0, 0, -0.9 * t * t if STATE == 'after' else 0))
        e.radius = random.uniform(0.012, 0.035) * (1.2 - t * 0.6)
        e.stiffness = 2.0
    for i in range(10):                                  # drips running down the lower half's cut edge
        x = random.uniform(-0.18, 0.18)
        top_z = cut_point.z - (x * cut_normal.x) / cut_normal.z
        for k in range(6):
            e = mb.elements.new(); e.co = (x, -0.18, top_z - 0.03 - k * (0.035 if STATE == 'impact' else 0.07))
            e.radius = 0.014 - k * 0.0015; e.stiffness = 2.0
    if STATE == 'after':                                  # paint pool on the ground
        for i in range(14):
            e = mb.elements.new(); e.co = (random.uniform(-0.1, 0.5), random.uniform(-0.45, 0.0), 0.0); e.radius = random.uniform(0.06, 0.12)
            e.type = 'ELLIPSOID'; e.size_x, e.size_y, e.size_z = 1.0, 1.0, 0.12

# ---------------------------------------------------------------- paper confetti (red + cream)
if STATE != 'before':
    bm = bmesh.new()
    for i in range(70):
        c = cut_point + Vector((random.uniform(-0.6, 0.8), random.uniform(-0.6, 0.1), random.uniform(-0.5, 0.6)))
        s = random.uniform(0.012, 0.03)
        rot = Matrix.Rotation(random.random() * 6.28, 3, Vector((random.random(), random.random(), random.random())).normalized())
        vs = [bm.verts.new(c + rot @ Vector(v) * s) for v in ((0, 0, 1), (0.9, 0, -0.5), (-0.9, 0, -0.5))]
        bm.faces.new(vs)
    conf = obj_from_bm('Confetti', bm, M['crimson'])
    conf.data.materials.append(M['cream'])
    for i, f in enumerate(conf.data.polygons): f.material_index = i % 2

# ---------------------------------------------------------------- lights + camera
key = bpy.data.lights.new('RimWarm', 'AREA'); key.energy = 140; key.size = 1.2; key.color = (1.0, 0.62, 0.32)
ko = bpy.data.objects.new('RimWarm', key); ko.location = (-1.8, 2.2, 2.6); scene.collection.objects.link(ko)
ko.rotation_euler = (Vector((0, 0, 1.0)) - ko.location).to_track_quat('-Z', 'Y').to_euler()
fill = bpy.data.lights.new('FillCool', 'AREA'); fill.energy = 35; fill.size = 2.0; fill.color = (0.55, 0.62, 0.9)
fo = bpy.data.objects.new('FillCool', fill); fo.location = (2.2, -2.6, 1.6); scene.collection.objects.link(fo)
fo.rotation_euler = (Vector((0, 0, 1.0)) - fo.location).to_track_quat('-Z', 'Y').to_euler()

cam_data = bpy.data.cameras.new('KUROKO'); cam_data.lens = 35; cam_data.clip_start = 0.01
cam_data.dof.use_dof = True; cam_data.dof.aperture_fstop = 1.6
cam = bpy.data.objects.new('KUROKO', cam_data); scene.collection.objects.link(cam); scene.camera = cam
cam.location = (1.35, -3.7, 1.2)
focus = cut_point + Vector((0.05, -0.1, 0))
cam.rotation_euler = (focus - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam_data.dof.focus_distance = (focus - cam.location).length

bpy.ops.render.render(write_still=True)
print('WROTE', OUT)
