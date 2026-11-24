"""BUILD SET: compose a Paper Cinema set from a JSON file (library/sets/<name>.json) out of kit pieces
(blender/sets/kit.py), light it, add camera anchors and fighter marks, optionally put origami samurai on the marks,
save a .blend and render preview stills.

  B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
  nice -n 15 $B -b -t 2 -P blender/sets/build_set.py -- --set castle-courtyard --out output/sets/castle.blend \
      --preview output/sets/castle.png [--cams CAM_wide,CAM_medium] [--with-character hero:wide-stance,foe:hasso:demon]

Options:
  --set NAME|PATH        library/sets/NAME.json or a path              --out PATH   .blend to save (default output/sets/NAME.blend)
  --preview PATH         render stills (first cam -> PATH, others -> PATH-CAM_x.png)
  --cams A,B             camera anchors to render (default: the set's "preview_cams", else its first camera)
  --with-character LIST  role:pose[:demon][:trellis[=model]] separated by commas; role = mark name without MARK_ (hero, foe, ...);
                         :trellis = the rigged TRELLIS character (hero: ronin_base, others: samurai_front) instead of the box origami
  --res WxH (540x960)    --samples N (set's render.samples or 32)    --quick (270x480, 12 samples)
  --seed N               override the set seed                       --exposure EV  override the grade
  --frame N              frame to render (particles and rain move)   --no-fog     skip fog pieces (fast look check)
  --no-post              skip the compositor (bloom, vignette)

The JSON format (see docs/SETS.md): name, seed, lighting {preset, sky, sun, exposure, look, fighter, bloom,
vignette}, materials {key: {overrides}}, pieces [{kit, name, pos, rot, scale, seed, params}], marks {MARK_x:
{pos, face}}, cameras {CAM_x: {pos, look | look_mark + look_z, lens, fstop, focus, note}}, preview_cams, render.
"""
import json
import math
import os
import sys
import time

import bpy
from mathutils import Vector

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
for p in (HERE, os.path.join(HERE, '..', 'world'), os.path.join(HERE, '..', 'character')):
    sys.path.insert(0, os.path.abspath(p))
import kit  # noqa: E402
import paper_materials as pm  # noqa: E402

ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(n, d=None):
    return ARGV[ARGV.index('--' + n) + 1] if '--' + n in ARGV else d


def flag(n):
    return '--' + n in ARGV


# =========================================================================== lighting presets
PRESETS = {
    'night': dict(sky={'type': 'night', 'zenith': [0.003, 0.005, 0.014], 'horizon': [0.018, 0.024, 0.04], 'stars': 1.0, 'strength': 1.0},
                  sun={'elev': 38, 'az': 150, 'color': [0.62, 0.72, 1.0], 'energy': 0.35, 'angle': 1.5},
                  exposure=0.0, look='AgX - Medium High Contrast', bloom=0.7, vignette=0.4),
    'dusk': dict(sky={'type': 'nishita', 'strength': 0.6}, sun={'elev': 2.0, 'az': -60, 'color': [1.0, 0.48, 0.25], 'energy': 2.2, 'angle': 1.5},
                 exposure=-1.2, look='AgX - Medium High Contrast', bloom=0.5, vignette=0.35),
    'dawn': dict(sky={'type': 'nishita', 'strength': 1.0}, sun={'elev': 4.0, 'az': -7, 'color': [1.0, 0.62, 0.38], 'energy': 3.2, 'angle': 1.2},
                 exposure=-2.3, look='AgX - Medium High Contrast', bloom=0.4, vignette=0.3),
    'day': dict(sky={'type': 'nishita', 'strength': 1.0}, sun={'elev': 38, 'az': 135, 'color': [1.0, 0.94, 0.86], 'energy': 4.0, 'angle': 0.8},
                exposure=-3.3, look='AgX - Medium High Contrast', bloom=0.3, vignette=0.3),
    'overcast': dict(sky={'type': 'color', 'color': [0.55, 0.6, 0.65], 'strength': 0.8}, sun={'elev': 60, 'az': 0, 'color': [0.9, 0.93, 1.0], 'energy': 0.3, 'angle': 20},
                     exposure=-0.5, look='AgX - Base Contrast', bloom=0.2, vignette=0.3),
}
FIGHTER = {'key': {'offset': [-1.8, 2.4, 2.8], 'energy': 0.0, 'color': [1.0, 0.82, 0.62], 'size': 1.6},
           'fill': {'offset': [2.4, 1.6, 1.4], 'energy': 0.0, 'color': [0.7, 0.78, 1.0], 'size': 2.0},
           'rim': {'offset': [1.2, -2.6, 2.6], 'energy': 0.0, 'color': [0.62, 0.74, 1.0], 'size': 0.8}}


def merge(a, b):
    out = dict(a)
    for k, v in (b or {}).items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def sun_dir(elev, az):
    el, a = math.radians(elev), math.radians(az)
    return Vector((math.sin(a) * math.cos(el), math.cos(a) * math.cos(el), math.sin(el)))


def build_sky(scene, sky, sun):
    world = bpy.data.worlds.new('SET_sky')
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    T = pm._NT(nt)
    bg = nt.nodes['Background']
    bg.inputs['Strength'].default_value = sky.get('strength', 1.0)
    kind = sky.get('type', 'nishita')
    if kind == 'nishita':
        pm.SKY.update(sun_elevation=math.radians(sun['elev']), sun_rotation=math.radians(sun['az']),
                      dust_density=sky.get('dust', 1.3), air_density=sky.get('air', 1.0))
        sk = pm.sky_node(T)
        nt.links.new(sk.outputs['Color'], bg.inputs['Color'])
    elif kind == 'night':
        tc = T.node('ShaderNodeTexCoord')
        z = T.node('ShaderNodeSeparateXYZ', Vector=tc.outputs['Generated']).outputs['Z']
        g = pm._smooth(T, z, -0.05, 0.55)
        col = T.mix_rgb(g, sky['horizon'], sky['zenith'])
        vo = pm._voronoi(T, tc.outputs['Generated'], 380.0)
        r = T.node('ShaderNodeSeparateColor', Color=vo.outputs['Color']).outputs[0]
        star = T.math('MULTIPLY', T.math('LESS_THAN', vo.outputs['Distance'], 0.06), T.math('GREATER_THAN', r, 0.55))
        star = T.math('MULTIPLY', star, T.math('MULTIPLY', T.math('POWER', r, 6.0), 0.8 * sky.get('stars', 1.0)))
        star = T.math('MULTIPLY', star, pm._smooth(T, z, 0.08, 0.35))
        col = T.mix_rgb(1.0, col, T.node('ShaderNodeCombineXYZ', X=star, Y=star, Z=T.math('MULTIPLY', star, 1.15)).outputs[0], blend='ADD')
        nt.links.new(col, bg.inputs['Color'])
    else:
        bg.inputs['Color'].default_value = (*sky.get('color', [0.5, 0.5, 0.5])[:3], 1)
    if sun.get('energy', 0) > 0:
        L = bpy.data.lights.new('SET_sun', 'SUN')
        L.energy = sun['energy']
        L.color = sun['color'][:3]
        L.angle = math.radians(sun.get('angle', 1.0))
        ob = bpy.data.objects.new('SET_sun', L)
        ob.rotation_euler = (-sun_dir(sun['elev'], sun['az'])).to_track_quat('-Z', 'Y').to_euler()
        return ob
    return None


# =========================================================================== compositor
def _setp(node, name, value):
    if hasattr(node, name.lower().replace(' ', '_')):
        try:
            setattr(node, name.lower().replace(' ', '_'), value)
            return
        except Exception:
            pass
    if name in node.inputs:
        node.inputs[name].default_value = value


def post(scene, bloom, vignette):
    """Bloom (fog glow around lanterns, eyes, windows) and a soft vignette."""
    scene.use_nodes = True
    nt = scene.node_tree
    nt.nodes.clear()
    rl = nt.nodes.new('CompositorNodeRLayers')
    comp = nt.nodes.new('CompositorNodeComposite')
    sock = rl.outputs['Image']
    if bloom > 0:
        g = nt.nodes.new('CompositorNodeGlare')
        try:
            g.glare_type = 'BLOOM'
        except Exception:
            g.glare_type = 'FOG_GLOW'
        _setp(g, 'Quality', 'MEDIUM')
        _setp(g, 'Threshold', 0.8)
        _setp(g, 'Strength', bloom)
        _setp(g, 'Size', 0.6 if 'Size' in g.inputs else 8)
        if hasattr(g, 'mix'):
            g.mix = -1 + bloom
        nt.links.new(sock, g.inputs['Image'])
        sock = g.outputs['Image']
    if vignette > 0:
        em = nt.nodes.new('CompositorNodeEllipseMask')
        _setp(em, 'Width', 0.95)
        _setp(em, 'Height', 0.85)
        bl = nt.nodes.new('CompositorNodeBlur')
        _setp(bl, 'size_x', 160)
        _setp(bl, 'size_y', 160)
        if 'Size' in bl.inputs:
            try:
                bl.inputs['Size'].default_value = (160, 160)
            except Exception:
                pass
        nt.links.new(em.outputs['Mask'], bl.inputs['Image'])
        mr = nt.nodes.new('CompositorNodeMapRange')
        mr.inputs['From Min'].default_value = 0.0
        mr.inputs['From Max'].default_value = 1.0
        mr.inputs['To Min'].default_value = 1.0 - vignette
        mr.inputs['To Max'].default_value = 1.0
        nt.links.new(bl.outputs['Image'], mr.inputs['Value'])
        mx = nt.nodes.new('CompositorNodeMixRGB')
        mx.blend_type = 'MULTIPLY'
        nt.links.new(sock, mx.inputs[1])
        nt.links.new(mr.outputs['Value'], mx.inputs[2])
        sock = mx.outputs['Image']
    nt.links.new(sock, comp.inputs['Image'])


# =========================================================================== render settings
def setup_render(scene, R, res, samples):
    scene.render.engine = 'CYCLES'
    cy = scene.cycles
    cy.device = 'CPU'
    cy.samples = samples
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = R.get('adaptive', 0.04)
    cy.use_denoising = True
    cy.denoiser = 'OPENIMAGEDENOISE'
    cy.max_bounces = R.get('bounces', 6)
    cy.diffuse_bounces = R.get('diffuse_bounces', 3)
    cy.glossy_bounces = 3
    cy.transmission_bounces = 6
    cy.transparent_max_bounces = 8
    cy.volume_bounces = R.get('volume_bounces', 0)
    cy.volume_step_rate = R.get('volume_step_rate', 2.0)
    cy.volume_max_steps = 256
    cy.sample_clamp_indirect = R.get('clamp', 4.0)
    cy.use_light_tree = True
    cy.blur_glossy = 1.0
    scene.render.use_persistent_data = True
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 2
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.frame_start, scene.frame_end = 1, 240
    scene.view_settings.view_transform = 'AgX'
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False


# =========================================================================== marks, cameras
def make_marks(scene, coll, marks, clear_r):
    out = {}
    for name, m in marks.items():
        e = bpy.data.objects.new(name, None)
        e.empty_display_type = 'ARROWS'
        e.empty_display_size = 0.8
        pos = Vector(m['pos'] + [0] * (3 - len(m['pos'])))
        e.location = pos
        if 'face' in m:
            d = Vector(m['face'][:2]) - pos.xy
            e.rotation_euler = (0, 0, math.atan2(d.y, d.x) - math.radians(90))
        elif 'yaw' in m:
            e.rotation_euler = (0, 0, math.radians(m['yaw']))
        e['role'] = m.get('role', '')
        coll.objects.link(e)
        out[name] = e
    return out


SKIP_SNAP = ('fog', 'mist', 'dust', 'emitter', 'rain', 'MOON', 'PI_', 'leaves', 'needles', 'blossom', 'crown')


def snap_marks(scene, marks, reach=2.5):
    """Put every mark on the surface below it (terrain, floor, sand), ignoring fog, particles and foliage. The
    search starts `reach` m above the mark, so roofs and ceilings over an interior mark are never hit."""
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    for name, m in marks.items():
        p = m.location + Vector((0, 0, reach))
        for _ in range(12):
            hit, loc, nrm, idx, ob, mx = scene.ray_cast(dg, p, Vector((0, 0, -1)))
            if not hit:
                break
            if any(k in ob.name for k in SKIP_SNAP):
                p = loc - Vector((0, 0, 1e-4))
                continue
            if abs(loc.z - m.location.z) > 0.005:
                print(f'  mark {name}: snapped z {m.location.z:.2f} -> {loc.z:.2f} ({ob.name})')
            m.location.z = loc.z
            break


def make_cameras(scene, coll, cams, marks):
    anchors = {}
    for name, c in cams.items():
        e = bpy.data.objects.new(name, None)
        e.empty_display_type = 'CONE'
        pos = Vector(c['pos'])
        if 'look_mark' in c:
            look = marks[c['look_mark']].location + Vector((0, 0, c.get('look_z', 1.2)))
        else:
            look = Vector(c['look'])
        e.location = pos
        e.rotation_euler = (look - pos).to_track_quat('-Z', 'Y').to_euler()
        if c.get('roll'):
            e.rotation_euler = (e.rotation_euler.to_matrix() @ __import__('mathutils').Matrix.Rotation(math.radians(c['roll']), 3, 'Z')).to_euler()
        e['lens_mm'] = c.get('lens', 35)
        e['look_at'] = list(look)
        e['fstop'] = c.get('fstop', 0)
        f = c.get('focus')
        if isinstance(f, str) and f in marks:
            e['focus_m'] = (marks[f].location + Vector((0, 0, 1.3)) - pos).length
        elif isinstance(f, (int, float)):
            e['focus_m'] = float(f)
        else:
            e['focus_m'] = (look - pos).length
        e['note'] = c.get('note', '')
        coll.objects.link(e)
        anchors[name] = e
    cd = bpy.data.cameras.new('KUROKO')
    cd.clip_start = 0.05
    cd.clip_end = 6000
    cd.sensor_fit = 'AUTO'
    cam = bpy.data.objects.new('KUROKO', cd)
    coll.objects.link(cam)
    scene.camera = cam
    return cam, anchors


def put_camera(cam, a):
    cam.matrix_world = a.matrix_world.copy()
    cam.data.lens = a['lens_mm']
    if a.get('fstop', 0) > 0:
        cam.data.dof.use_dof = True
        cam.data.dof.aperture_fstop = a['fstop']
        cam.data.dof.focus_distance = a['focus_m']
    else:
        cam.data.dof.use_dof = False


# =========================================================================== characters
def add_characters(scene, coll, specs, marks, fighter):
    import origami_samurai as osam
    made = []
    for spec in specs:
        parts = spec.split(':')
        role, pose = parts[0], parts[1] if len(parts) > 1 else 'standing'
        demon = 'demon' in parts[2:]
        mk = marks.get('MARK_' + role)
        if mk is None:
            print(f'  ! no mark MARK_{role}; skipping character')
            continue
        yaw = mk.rotation_euler.z + math.pi
        ch = bpy.data.collections.new('CHAR_' + role)
        coll.children.link(ch)
        tre = next((x for x in parts[2:] if x.startswith('trellis')), None)
        if tre:
            # the owner's TRELLIS character, rigged (blender/character/rig_trellis.py, docs/CHARACTER-BLENDER.md):
            # role:pose:trellis  (hero = ronin_base, any other role = samurai_front)  or  role:pose:trellis=<model>
            import rig_trellis as rtr
            model = tre.split('=')[1] if '=' in tre else ('ronin_base' if role == 'hero' else 'samurai_front')
            res = rtr.build_character(model, name='RIG_' + role, demonic=demon)
            rtr.apply_frame(res, rtr.pose_frame(pose if pose != 'standing' else 'chudan'))
            rtr.place(res, tuple(mk.location), yaw, collection=ch)
        else:
            res = osam.build(pose, tuple(mk.location), yaw, demon=demon, seed=3 + len(made), name='CHAR_' + role, collection=ch,
                             lamp_scale=fighter.get('lamp_scale', 0.12), seam_glow=fighter.get('seam_glow', 1.6),
                             eye_glow=fighter.get('eye_glow', 14.0), inner_glow=fighter.get('inner_glow', 1.5))
        M = mk.matrix_world
        aim = mk.location + Vector((0, 0, 1.25))
        for nm in ('key', 'fill', 'rim'):
            L = fighter[nm]
            if L.get('energy', 0) <= 0:
                continue
            ld = bpy.data.lights.new(f'LGT_{nm.capitalize()}_{role}', 'AREA')
            ld.energy = L['energy']
            ld.color = L['color'][:3]
            ld.size = L['size']
            lo = bpy.data.objects.new(ld.name, ld)
            lo.location = M @ Vector(L['offset'])
            lo.rotation_euler = (aim - lo.location).to_track_quat('-Z', 'Y').to_euler()
            ch.objects.link(lo)
        made.append(res)
        print(f'  character {role}: pose {pose}{" (demon)" if demon else ""} at {tuple(round(v, 2) for v in mk.location)}')
    return made


# =========================================================================== main
def main():
    t0 = time.time()
    name = arg('set', 'castle-courtyard')
    path = name if name.endswith('.json') else os.path.join(REPO, 'library', 'sets', name + '.json')
    S = json.load(open(path))
    set_name = S.get('name', os.path.splitext(os.path.basename(path))[0])
    seed = int(arg('seed', S.get('seed', 1)))
    R = S.get('render', {})
    quick = flag('quick')
    res = [int(v) for v in arg('res', '270x480' if quick else R.get('res', '540x960')).split('x')]
    samples = int(arg('samples', 12 if quick else R.get('samples', 32)))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = set_name
    colls = {}
    for c in ('SET', 'LIGHTS', 'MARKS', 'CAMERAS', 'CHARACTERS'):
        colls[c] = bpy.data.collections.new(c)
        scene.collection.children.link(colls[c])
    setup_render(scene, R, res, samples)

    Lg = S.get('lighting', {})
    Lg = merge(PRESETS.get(Lg.get('preset', 'night'), PRESETS['night']), Lg)
    sun = build_sky(scene, Lg['sky'], Lg['sun'])
    if sun:
        colls['LIGHTS'].objects.link(sun)
    scene['set_sun'] = {'sun_elev': Lg['sun']['elev'], 'sun_az': Lg['sun']['az']}
    scene.view_settings.look = Lg.get('look', 'AgX - Medium High Contrast')
    scene.view_settings.exposure = float(arg('exposure', Lg.get('exposure', 0.0)))

    marks = make_marks(scene, colls['MARKS'], S.get('marks', {}), S.get('clear', 1.6))
    ctx = kit.Ctx(scene, colls['SET'], seed=seed, materials=S.get('materials', {}))
    ctx.clear = [(m.location.x, m.location.y, S.get('clear', 1.6)) for n, m in marks.items() if n in ('MARK_hero', 'MARK_foe', 'MARK_center')]
    ctx.clear += [(c['pos'][0], c['pos'][1], 0.8) for c in S.get('cameras', {}).values()]     # never grow a culm through a lens
    counts = {}
    for spec in S.get('pieces', []) + Lg.get('pieces', []):
        if flag('no-fog') and spec['kit'] in ('fog',):
            continue
        tp = time.time()
        kit.build_piece(ctx, spec)
        counts[spec.get('name', spec['kit'])] = round(time.time() - tp, 2)
    if S.get('snap_marks', True):
        snap_marks(scene, marks, S.get('snap_reach', 2.5))
    for i, L in enumerate(Lg.get('lights', [])):
        kit.build_piece(ctx, {'kit': 'light', 'name': L.get('name', f'light_{i}'), 'pos': L['pos'], 'params': {k: v for k, v in L.items() if k not in ('pos', 'name')}})
    cam, anchors = make_cameras(scene, colls['CAMERAS'], S.get('cameras', {}), marks)
    fighter = merge(FIGHTER, Lg.get('fighter', {}))
    chars = arg('with-character')
    if chars:
        add_characters(scene, colls['CHARACTERS'], chars.split(','), marks, fighter)
    if not flag('no-post'):
        post(scene, Lg.get('bloom', 0.5), Lg.get('vignette', 0.3))
    frame = int(arg('frame', 1))
    scene.frame_set(frame)
    scene['paper_cinema_set'] = set_name
    scene['seed'] = seed
    cams = (arg('cams') or ','.join(S.get('preview_cams', [])) or next(iter(anchors), '')).split(',')
    if cams and cams[0] in anchors:
        put_camera(cam, anchors[cams[0]])
    nfaces = sum(len(o.data.polygons) for o in bpy.data.objects if o.type == 'MESH')
    print(f'BUILT {set_name} in {time.time() - t0:.1f}s: {len(bpy.data.objects)} objects, {nfaces} faces; slowest pieces:',
          sorted(counts.items(), key=lambda kv: -kv[1])[:4])

    out = os.path.abspath(arg('out', os.path.join(REPO, 'output', 'sets', set_name + '.blend')))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print('SAVED', out)

    prev = arg('preview')
    if prev:
        for i, cn in enumerate(cams):
            if cn not in anchors:
                print('  ! unknown camera', cn, '; known:', ', '.join(anchors))
                continue
            put_camera(cam, anchors[cn])
            base, ext = os.path.splitext(os.path.abspath(prev))
            scene.render.filepath = base + ('' if i == 0 else f'-{cn}') + (ext or '.png')
            os.makedirs(os.path.dirname(scene.render.filepath), exist_ok=True)
            t = time.time()
            bpy.ops.render.render(write_still=True)
            print(f'RENDERED {cn} -> {scene.render.filepath} in {time.time() - t:.1f}s ({res[0]}x{res[1]}, {samples} spp)')


if __name__ == '__main__':
    main()
