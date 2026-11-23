"""Slash effect library (Lantern Origami): a sharp tapered crescent of light with an ink-brush edge and a spray of
paper shards, keyframed over frames. Use it from any Blender script:

    import sys; sys.path.insert(0, 'blender/world'); import slash_fx
    slash_fx.make_slash('SLASH_kesa', center=(0, -3.2, 1.3), radius=1.0, sweep=150, thickness=0.18,
                        colour='amber', demonic=False, frame_start=10, frame_end=22, tilt=-35)

Test render (3 variants side by side, plus a 4-frame strip of the demonic one):
  blender -b -P blender/world/slash_fx.py -- --test output/world/slash-test.png [--strip output/world/slash-strip.png]
  blender -b -P blender/world/slash_fx.py -- --in-world output/world/ganryujima.blend --test output/world/slash-world.png

Animation (driven by three custom properties on the slash object, read by the shader):
  reveal 0 -> 1   the head races along the arc (first ~35% of the life, ease-out: fast, then settling)
  tail   0 -> 1   the ink tail erases from the start of the arc, ragged like a dry brush
  heat   1 -> 0   the emissive core cools
Colour code (AGENTS.md rule 4): amber = human, crimson = demonic. `demonic=True` also widens the black ink edge,
adds flicker and turns the shards to black paper with crimson glowing edges.
"""
import math
import os
import random
import sys
import time

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

sys.dont_write_bytecode = True      # keep blender/world free of __pycache__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paper_materials as pm  # noqa: E402

PALETTE = {
    #            core (hot)          body                ink edge
    'amber':   ((1.0, 0.62, 0.22), (0.95, 0.30, 0.03), (0.020, 0.014, 0.010)),
    'crimson': ((1.0, 0.30, 0.22), (0.85, 0.02, 0.01), (0.010, 0.000, 0.000)),
}


# =========================================================================== material
def slash_material(name, colour='amber', demonic=False, strength=1.0):
    core, body, ink = PALETTE[colour] if isinstance(colour, str) else (colour[0], colour[1], colour[2])
    m = pm.new_material(name)
    T = pm._NT(m.node_tree)
    out = m.node_tree.nodes.new('ShaderNodeOutputMaterial')

    def prop(nm):
        a = T.node('ShaderNodeAttribute')
        a.attribute_type = 'OBJECT'
        a.attribute_name = nm
        return a.outputs['Fac']

    reveal, tail, heat = prop('reveal'), prop('tail'), prop('heat')
    uv = T.node('ShaderNodeUVMap'); uv.uv_map = 'UVMap'
    sep = T.node('ShaderNodeSeparateXYZ', Vector=uv.outputs['UV'])
    u, v = sep.outputs['X'], sep.outputs['Y']          # u along the arc (0 start -> 1 head), v across (0 blade edge -> 1 inner)
    # brush noise: coarse rag + long dry-brush streaks along u
    st = T.node('ShaderNodeCombineXYZ', X=T.math('MULTIPLY', u, 14.0), Y=T.math('MULTIPLY', v, 2.5))
    rag = T.node('ShaderNodeTexNoise', Vector=st.outputs[0], Scale=1.0, Detail=8.0, Roughness=0.7).outputs['Fac']
    sk = T.node('ShaderNodeCombineXYZ', X=T.math('MULTIPLY', u, 2.0), Y=T.math('MULTIPLY', v, 38.0))
    streak = T.node('ShaderNodeTexNoise', Vector=sk.outputs[0], Scale=1.0, Detail=3.0).outputs['Fac']

    # alpha: head (sharp) x tail (ragged dry-brush erase) x inner edge (ragged)
    head = T.math('LESS_THAN', u, T.math('ADD', reveal, 0.002))
    tail_edge = T.math('MULTIPLY_ADD', T.math('SUBTRACT', rag, 0.5), 0.35, tail)
    tailm = T.math('GREATER_THAN', u, T.math('MULTIPLY_ADD', tail_edge, 1.15, -0.05))
    inner = T.math('LESS_THAN', v, T.math('MULTIPLY_ADD', T.math('SUBTRACT', rag, 0.5), 0.5, 0.97))
    dry = T.math('GREATER_THAN', streak, T.math('MULTIPLY_ADD', v, 0.35, 0.08))      # streaks open up toward the inner edge
    alpha = T.math('MULTIPLY', T.math('MULTIPLY', head, tailm), T.math('MULTIPLY', inner, dry))

    # colour across the stroke: white-hot blade edge -> body glow -> ink edge
    ink_start = 0.42 if demonic else 0.6
    inkf = T.node('ShaderNodeMapRange', Value=T.math('MULTIPLY_ADD', T.math('SUBTRACT', rag, 0.5), 0.3, v))
    inkf.inputs['From Min'].default_value = ink_start
    inkf.inputs['From Max'].default_value = ink_start + 0.08
    coref = T.node('ShaderNodeMapRange', Value=v)
    coref.inputs['From Min'].default_value = 0.0
    coref.inputs['From Max'].default_value = 0.4
    ecol = T.mix_rgb(coref.outputs['Result'], core, body)
    fib = pm.fibre_height(T, 30.0, seed=0.3)
    # the head is the hottest part: boost near u = reveal
    near_head = T.math('POWER', T.math('MAXIMUM', T.math('SUBTRACT', 1.0, T.math('MULTIPLY', T.math('SUBTRACT', reveal, u), 3.0)), 0.0), 2.0)
    estr = T.math('MULTIPLY_ADD', T.math('POWER', T.math('SUBTRACT', 1.0, coref.outputs['Result']), 3.0), 6.0, 0.9)
    estr = T.math('MULTIPLY', estr, T.math('MULTIPLY_ADD', near_head, 1.5, 1.0))
    estr = T.math('MULTIPLY', estr, T.math('MULTIPLY_ADD', fib, 0.5, 0.75))
    if demonic:   # flicker: noise in time-free space driven by heat
        fl = T.node('ShaderNodeTexNoise', Vector=st.outputs[0], Scale=0.4, Detail=2.0).outputs['Fac']
        estr = T.math('MULTIPLY', estr, T.math('MULTIPLY_ADD', fl, 0.9, 0.55))
    estr = T.math('MULTIPLY', T.math('MULTIPLY', estr, heat), strength)
    em = T.node('ShaderNodeEmission', Color=ecol, Strength=estr)
    inkb = T.node('ShaderNodeBsdfPrincipled', **{'Base Color': (*ink, 1), 'Roughness': 0.25})
    inkb.inputs['Coat Weight'].default_value = 0.5           # wet sumi ink
    mix_ink = T.node('ShaderNodeMixShader', Fac=inkf.outputs['Result'])
    T.link(em.outputs['Emission'], mix_ink.inputs[1]); T.link(inkb.outputs['BSDF'], mix_ink.inputs[2])
    tr = T.node('ShaderNodeBsdfTransparent')
    mx = T.node('ShaderNodeMixShader', Fac=alpha)
    T.link(tr.outputs['BSDF'], mx.inputs[1]); T.link(mix_ink.outputs['Shader'], mx.inputs[2])
    T.link(mx.outputs['Shader'], out.inputs['Surface'])
    return m


# =========================================================================== geometry
def crescent_bm(radius, sweep_deg, thickness, start_deg, segs=30, rows=4, seed=0, fold=0.35):
    """Sharp tapered crescent in the local XZ plane (facing -Y). u along the arc, v from the blade edge (outer)
    to the inner ink edge. Tapers to points at both ends, fattest past the middle (where the blade was fastest);
    a crease along the spine (fold) and per-vertex jitter make it a folded, faceted paper blade."""
    r = random.Random(seed)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    grid = []
    for i in range(segs + 1):
        u = i / segs
        a = math.radians(start_deg + sweep_deg * u)
        w = thickness * math.sin(math.pi * u ** 0.75) ** 0.8
        row = []
        for j in range(rows + 1):
            v = j / rows
            rr = radius - w * v
            crease = fold * w * math.sin(math.pi * v)                 # folded ridge toward the camera
            jit = r.uniform(-1, 1) * w * 0.08 if 0 < i < segs else 0
            row.append((bm.verts.new((rr * math.cos(a), -crease + jit, rr * math.sin(a))), (u, v)))
        grid.append(row)
    for i in range(segs):
        for j in range(rows):
            quad = (grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1])
            f = bm.faces.new([q[0] for q in quad])
            for loop, q in zip(f.loops, quad):
                loop[uvl].uv = q[1]
    return bm


def _key_props(ob, frames):
    for f, vals in frames:
        for k, val in vals.items():
            ob[k] = val
            ob.keyframe_insert(f'["{k}"]', frame=f)


def make_slash(name='SLASH', center=(0.0, 0.0, 1.2), radius=1.0, sweep=150.0, thickness=0.18, colour='amber',
               demonic=False, frame_start=1, frame_end=13, start_angle=None, tilt=0.0, pitch=0.0, yaw=0.0, clockwise=True,
               shards=None, seed=0, light=True, strength=1.0, collection=None):
    """Build one keyframed slash. Returns {'root', 'arc', 'shards', 'light'}.

    center       world position of the arc centre (roughly the swordsman's shoulder line)
    radius       arc radius in metres (blade + arm reach ~ 0.9-1.3)
    sweep        arc angle in degrees (100 = quick cut, 200+ = big demonic sweep)
    thickness    max width of the crescent in metres
    colour       'amber' (human) | 'crimson' (demonic) | ((core), (body), (ink)) RGB triplets
    demonic      wider black ink edge, flicker, black paper shards with crimson glow, more shards
    frame_start / frame_end   life of the effect; the head reaches the end of the arc at ~35% of the life
    start_angle  degrees in the arc plane where the cut starts (default: so the arc is centred on the top)
    tilt         roll of the arc plane around the view axis (Y): -35 = kesa-giri diagonal, 0 = vertical
    pitch        tip the arc plane around X: 70 = a near-horizontal yoko-giri sweep seen from slightly above
    yaw          turn of the arc plane around Z (0 = facing -Y)
    clockwise    direction of travel as seen from -Y
    shards       number of paper shards (default 28, demonic 44)
    """
    rnd = random.Random(f'slash:{name}:{seed}')
    coll = collection or bpy.context.scene.collection
    if start_angle is None:
        start_angle = 90 + sweep / 2 if clockwise else 90 - sweep / 2
    sw = -sweep if clockwise else sweep

    root = bpy.data.objects.new(name, None)
    root.empty_display_type = 'CIRCLE'
    root.empty_display_size = radius
    root.location = center
    root.rotation_euler = Euler((math.radians(pitch), math.radians(tilt), math.radians(yaw)), 'XYZ')
    coll.objects.link(root)

    bm = crescent_bm(radius, sw, thickness, start_angle, seed=rnd.randint(0, 9999))
    me = bpy.data.meshes.new(name + '_arc')
    bm.to_mesh(me); bm.free()
    arc = bpy.data.objects.new(name + '_arc', me)
    me.materials.append(slash_material(name + '_mat', colour, demonic, strength))
    pm.shade_flat(arc)
    arc.parent = root
    arc.visible_shadow = False
    coll.objects.link(arc)

    life = max(4, frame_end - frame_start)
    f_head = frame_start + max(2, round(life * 0.35))
    _key_props(arc, [(frame_start - 1, {'reveal': 0.0, 'tail': 0.0, 'heat': 1.0}),
                     (frame_start, {'reveal': 0.02}),
                     (f_head, {'reveal': 1.0, 'tail': 0.0, 'heat': 1.0}),
                     (frame_end, {'tail': 1.0, 'heat': 0.0})])
    _ease(arc)

    # ---- paper shards: torn triangles thrown off the blade edge as the head passes
    n = shards if shards is not None else (44 if demonic else 28)
    core, body, ink = PALETTE[colour] if isinstance(colour, str) else colour
    if demonic:
        smats = [pm.paper_material(name + '_shardA', (0.02, 0.015, 0.015), translucency=0.1, fibre_scale=120,
                                   glow=(body, 2.5)),
                 pm.paper_material(name + '_shardB', (0.35, 0.02, 0.02), translucency=0.4, fibre_scale=120, glow=(body, 1.0))]
    else:
        smats = [pm.paper_material(name + '_shardA', (0.78, 0.70, 0.58), translucency=0.5, fibre_scale=120, glow=(body, 0.4)),
                 pm.paper_material(name + '_shardB', (0.85, 0.55, 0.25), translucency=0.5, fibre_scale=120, glow=(body, 1.2))]
    shard_objs = []
    grav = -9.81
    fps = bpy.context.scene.render.fps or 24
    for k in range(n):
        u = rnd.random() ** 0.8
        a = math.radians(start_angle + sw * u)
        w = thickness * math.sin(math.pi * u ** 0.75) ** 0.8
        rr = radius - w * rnd.uniform(-0.1, 0.6)
        p0 = Vector((rr * math.cos(a), 0, rr * math.sin(a)))
        radial = Vector((math.cos(a), 0, math.sin(a)))
        tangent = Vector((-math.sin(a), 0, math.cos(a))) * (-1 if clockwise else 1)
        vel = radial * rnd.uniform(0.6, 2.2) + tangent * rnd.uniform(0.8, 3.0) + Vector((0, rnd.uniform(-1.6, 0.4), 0))
        s = rnd.uniform(0.018, 0.05) * (1.3 if demonic else 1.0)
        sb = bmesh.new()
        pts = [Vector((0, 0, 1)), Vector((0.9, 0, -0.5)), Vector((-0.8, 0, -0.6))]
        if rnd.random() < 0.4:
            pts.append(Vector((0.1, 0.25, -1.1)))                   # some shards are folded quads
        vs = [sb.verts.new(p * s) for p in pts]
        sb.faces.new(vs[:3])
        if len(vs) == 4:
            sb.faces.new((vs[0], vs[2], vs[3]))
        sme = bpy.data.meshes.new(f'{name}_shard{k}')
        sb.to_mesh(sme); sb.free()
        sh = bpy.data.objects.new(f'{name}_shard{k}', sme)
        sme.materials.append(smats[k % 2])
        pm.shade_flat(sh)
        sh.parent = root
        coll.objects.link(sh)
        spawn = frame_start + round((f_head - frame_start) * u)
        live = rnd.randint(int(life * 0.6), int(life * 1.4)) + 2
        spin = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * rnd.uniform(6, 18)
        g_local = root.rotation_euler.to_matrix().inverted() @ Vector((0, 0, grav))
        for key, f in enumerate((spawn - 1, spawn, spawn + live // 2, spawn + live)):
            t = max(0, f - spawn) / fps
            drag = 1.0 - 0.35 * min(1.0, t * 2)
            sh.location = p0 + vel * t * drag + 0.5 * g_local * t * t
            sh.rotation_euler = Euler(spin * t + Vector((rnd.random(), rnd.random(), rnd.random())) * (key == 0))
            sc = (0.0 if key == 0 else (1.0 if key < 3 else 0.25))
            sh.scale = (sc, sc, sc)
            for path in ('location', 'rotation_euler', 'scale'):
                sh.keyframe_insert(path, frame=f)
        shard_objs.append(sh)

    lo = None
    if light:
        li = bpy.data.lights.new(name + '_light', 'POINT')
        li.color = body
        li.shadow_soft_size = radius * 0.4
        lo = bpy.data.objects.new(name + '_light', li)
        mid = math.radians(start_angle + sw * 0.6)
        lo.location = (radius * 0.85 * math.cos(mid), -0.25, radius * 0.85 * math.sin(mid))
        lo.parent = root
        coll.objects.link(lo)
        peak = (90 if demonic else 60) * strength
        for f, e in ((frame_start - 1, 0.0), (f_head, peak), (frame_end, 0.0)):
            li.energy = e
            li.keyframe_insert('energy', frame=f)
    return {'root': root, 'arc': arc, 'shards': shard_objs, 'light': lo}


def _ease(ob):
    """Ease-out on the reveal (fast cut that settles), linear elsewhere."""
    act = ob.animation_data.action if ob.animation_data else None
    if act is None:
        return
    try:
        fcs = list(act.fcurves)
    except AttributeError:
        fcs = [fc for layer in act.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]
    for fc in fcs:
        for kp in fc.keyframe_points:
            if '"reveal"' in fc.data_path:
                kp.interpolation = 'EXPO'
                kp.easing = 'EASE_OUT'
            else:
                kp.interpolation = 'LINEAR'


# =========================================================================== test scene
def _argv():
    return sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def _arg(a, name, default=None):
    return a[a.index('--' + name) + 1] if '--' + name in a else default


def _render_settings(scene, res, samples):
    scene.render.engine = 'CYCLES'
    cy = scene.cycles
    cy.device = 'CPU'
    cy.samples = samples
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.05
    cy.use_denoising = True
    cy.max_bounces = 4
    cy.diffuse_bounces = 2
    cy.glossy_bounces = 2
    cy.transmission_bounces = 4
    cy.transparent_max_bounces = 12
    cy.sample_clamp_indirect = 5
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 2
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.render.image_settings.file_format = 'PNG'


VARIANTS = [   # name, offset x, make_slash kwargs: the three looks of the test sheet
    ('SLASH_amber_kesa', -2.4, dict(radius=0.95, sweep=140, thickness=0.17, colour='amber', tilt=-35, seed=1)),
    ('SLASH_crimson_demon', 0.0, dict(radius=1.1, sweep=210, thickness=0.26, colour='crimson', demonic=True, tilt=20, seed=2)),
    ('SLASH_amber_yoko', 2.4, dict(radius=0.9, sweep=120, thickness=0.09, colour='amber', pitch=68, tilt=8, seed=3)),
]


def build_test_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    world = bpy.data.worlds.new('SlashTestWorld'); scene.world = world
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.012, 0.009, 0.008, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.5
    # dark washi backdrop and floor, folded into a few facets
    back = pm.paper_material('LO_Backdrop', (0.05, 0.04, 0.035), translucency=0.0, fibre_scale=6, fibre_strength=0.3, facet_var=0.2)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=8, y_segments=4, size=1.0, matrix=Matrix.Translation((0, 1.6, 1.4)) @
                          Matrix.Rotation(math.radians(90), 4, 'X') @ Matrix.Diagonal((5, 2, 1, 1)))
    bmesh.ops.create_grid(bm, x_segments=8, y_segments=4, size=1.0, matrix=Matrix.Diagonal((5, 2.5, 1, 1)))
    r = random.Random(4)
    for v in bm.verts:
        v.co.y += r.uniform(-0.05, 0.05)
    me = bpy.data.meshes.new('Backdrop'); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new('Backdrop', me); me.materials.append(back); pm.shade_flat(ob); pm.add_facet_attribute(ob, 5)
    scene.collection.objects.link(ob)
    key = bpy.data.lights.new('Key', 'AREA'); key.energy = 60; key.size = 3; key.color = (1.0, 0.75, 0.55)
    ko = bpy.data.objects.new('Key', key); ko.location = (-2, -3, 4); scene.collection.objects.link(ko)
    ko.rotation_euler = (Vector((0, 0, 1)) - ko.location).to_track_quat('-Z', 'Y').to_euler()
    cd = bpy.data.cameras.new('KUROKO'); cd.lens = 32
    cam = bpy.data.objects.new('KUROKO', cd); scene.collection.objects.link(cam); scene.camera = cam
    cam.location = (0, -7.4, 1.6)
    cam.rotation_euler = (Vector((0, 0, 1.3)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    for name, dx, kw in VARIANTS:
        make_slash(name, center=(dx, 0, 1.3), frame_start=10, frame_end=26, **kw)
    return scene


def build_in_world(path):
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(path))
    scene = bpy.context.scene
    c = bpy.data.objects['MARK_center'].location
    coll = bpy.data.collections.new('FX'); scene.collection.children.link(coll)
    make_slash('SLASH_world_kesa', center=(c.x - 0.6, c.y - 0.3, c.z + 1.3), radius=1.1, sweep=150, thickness=0.2,
               colour='amber', tilt=-35, frame_start=10, frame_end=26, seed=7, collection=coll)
    cam = scene.camera
    a = bpy.data.objects['CAM_medium']
    cam.matrix_world = a.matrix_world.copy(); cam.data.lens = a['lens_mm']
    return scene


if __name__ == '__main__':
    a = _argv()
    test = _arg(a, 'test')
    strip = _arg(a, 'strip')
    world_path = _arg(a, 'in-world')
    samples = int(_arg(a, 'samples', 24))
    frame = int(_arg(a, 'frame', 17))
    if world_path:
        scene = build_in_world(world_path)
        res = [int(x) for x in _arg(a, 'res', '540x960').split('x')]
    else:
        scene = build_test_scene()
        res = [int(x) for x in _arg(a, 'res', '1440x540').split('x')]
    _render_settings(scene, res, samples)
    if world_path:
        scene.view_settings.exposure = float(_arg(a, 'exposure', -2.3))
    if test:
        scene.frame_set(frame)
        scene.render.filepath = os.path.abspath(test)
        os.makedirs(os.path.dirname(scene.render.filepath), exist_ok=True)
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print(f'RENDERED {scene.render.filepath} frame {frame} in {time.time() - t:.1f}s ({res[0]}x{res[1]}, {samples} spp)')
    if strip and not world_path:
        # 4 frames of the demonic variant: head racing, full arc, tail erasing, shards drifting
        for o in bpy.data.objects:
            if o.name.startswith(('SLASH_amber',)):
                o.hide_render = True
        scene.camera.location = (0, -4.2, 1.35)
        scene.camera.rotation_euler = (Vector((0, 0, 1.3)) - scene.camera.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.resolution_x, scene.render.resolution_y = 480, 480
        frames = [12, 15, 20, 25]
        paths = []
        t = time.time()
        for f in frames:
            scene.frame_set(f)
            scene.render.filepath = os.path.abspath(strip).replace('.png', f'-f{f:02d}.png')
            bpy.ops.render.render(write_still=True)
            paths.append(scene.render.filepath)
        print(f'RENDERED strip {len(frames)} frames in {time.time() - t:.1f}s: {paths}')
