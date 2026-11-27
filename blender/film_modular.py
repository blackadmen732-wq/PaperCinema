"""FILM_MODULAR: render a film in Blender using the MODULAR PAPER CHARACTER.

  B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
  node tools/timeline.mjs film/sword-mocap.json
  $B -b -t 4 -P blender/film_modular.py -- --film sword-mocap --frames 0-191 --res 540x960

Why this file exists. The project had three character systems and the films used the worst one:
  * engine/figure.js      boxes and flat cards  -> EVERY film rendered so far
  * rig_trellis.py        a TRELLIS glb, one fused mesh whose arms cannot bend -> blender/film_blender.py
  * modular_builder.py    the real paper character: kasa, angular mask, layered kimono, knife-pleated
                          hakama, two-tier sleeves -> stills only, never a film
Every improvement made to the third one (back pleats, blotting, fold darkening) was invisible,
because it never appeared in a render anyone watched. This connects it.

It is short because nothing had to be invented. `tools/timeline.mjs` already writes, per frame and
per actor, a `pose` dict of 46 channels, and `Rig.pose()` already takes exactly those channel names
-- both sides descend from engine/figure.js, so the names never diverged. The work was noticing.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, 'character'))
sys.path.insert(0, os.path.join(HERE, 'world'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'props'))

ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def flag(n):
    return '--' + n in ARGV


def arg(n, d=None):
    return ARGV[ARGV.index('--' + n) + 1] if '--' + n in ARGV else d

import modular_builder as MB                                    # noqa: E402
from render_engine import setup_render                          # noqa: E402

# three.js -> Blender, the same conversion rig_trellis.py uses (v3 / q3)
def v3(p):
    return Vector((p[0], -p[2], p[1]))


def q3(q):
    """three.js quaternion -> Blender, for a BONE: the local axes rotate with the basis too."""
    return Quaternion((q[3], q[0], -q[2], q[1]))


# three.js is y-up and Blender is z-up, which is a +90 degree turn about X: (x, y, z) -> (x, -z, y).
BASIS = Quaternion((0.7071067811865476, 0.7071067811865476, 0.0, 0.0))


def qcam(q):
    """three.js quaternion -> Blender, for a CAMERA.

    Not the same conversion as a bone, and that difference is why the first render came out empty.
    q3 conjugates (B q B-1), which is right for a bone because its local axes are arbitrary and must
    turn with the basis. A camera's local axes already mean the same thing in both programs - both
    look down local -Z with +Y up - so only the world orientation changes: B q, no inverse. Using the
    bone conversion aimed the camera off into empty space while the cast stood correctly behind it.
    """
    return BASIS @ Quaternion((q[3], q[0], q[1], q[2]))


FILM = arg('film', 'sword-mocap')
TL = json.load(open(os.path.join(REPO, 'output', f'{FILM}.timeline.json')))
FPS = TL['clock']['fps'] if isinstance(TL.get('clock'), dict) else 24
FRAMES = TL['frames']
f0, f1 = (int(x) for x in arg('frames', f'0-{len(FRAMES) - 1}').split('-'))
f1 = min(f1, len(FRAMES) - 1)
import production_bake as PB                                    # noqa: E402  the ONE solve of body, props, paper
PB.check_pose_channels(TL, f0, f1, FILM)                        # before Blender builds anything
_FP = os.path.join(REPO, 'film', FILM + '.json')
FILMJ = json.load(open(_FP)) if os.path.exists(_FP) else {}
DRAWS = {aid: p['draw'] for aid, p in (FILMJ.get('performances') or {}).items() if isinstance(p, dict) and p.get('draw')}

if arg('set'):
    # A built set (docs/SETS.md). The timeline's world coordinates are kept as they are; the set is
    # expected to be built around the same origin the films use.
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(arg('set')))
    # STAGE (27 Nov): the set comes to the actors. Films are blocked around their own origin on flat ground; a
    # set has its fight on marks somewhere on its terrain (the beach: MARK_center at (0, -3.2), sand at +0.96 m,
    # so the fighters were buried 1.46 m). Every root object of the set is parented to one handle, and the handle
    # moves the set's mark (film.stage.mark, default MARK_center) under the film's action centre at ground 0,
    # turned by film.stage.turn degrees. A handle, not object by object, so animated set pieces keep working.
    _film_json = {}
    try:
        _film_json = json.load(open(os.path.join(REPO, TL['film']['path'])))
    except Exception:
        pass
    _stage = _film_json.get('stage') or {}
    _mk = bpy.data.objects.get(_stage.get('mark', 'MARK_center'))
    if _mk is not None and _stage.get('mark') != 'none':
        _roots = [A['root'] for A in TL['frames'][0]['actors'].values() if A.get('root') and not A.get('hidden')]
        _cx = sum(r[0] for r in _roots) / max(1, len(_roots))
        _cy = sum(-r[2] for r in _roots) / max(1, len(_roots))
        _hdl = bpy.data.objects.new('SET_STAGE', None)
        bpy.context.scene.collection.objects.link(_hdl)
        for _o in list(bpy.data.objects):
            if _o.parent is None and _o is not _hdl and _o.users_scene:
                _mw = _o.matrix_world.copy()
                _o.parent = _hdl
                _o.matrix_parent_inverse = Matrix()
                _o.matrix_world = _mw
        # stage.offset [dx, dy] (set metres from the mark): the action stands that far from the mark, on the ground
        # there (a slope above the waterline, a spot by a building) without a new mark in the set
        _spot = _mk.location.copy()
        _off = _stage.get('offset')
        if _off:
            _spot.x += float(_off[0])
            _spot.y += float(_off[1])
            _gs = PB.ground_sampler(bpy.context.scene, set())
            _gz = _gs(_spot.x, _spot.y, _mk.location.z + 30.0) if _gs else None
            if _gz is not None:
                _spot.z = _gz
            print('[stage] offset %s from %s: the action stands at (%.2f, %.2f), ground %.3f m'
                  % (list(_off), _mk.name, _spot.x, _spot.y, _spot.z))
        _M = (Matrix.Translation((_cx, _cy, 0.0)) @ Matrix.Rotation(math.radians(float(_stage.get('turn', 0.0))), 4, 'Z')
              @ Matrix.Translation(-_spot))
        _hdl.matrix_world = _M
        bpy.context.view_layer.update()
        print('[stage] %s moved under the action centre (%.2f, %.2f): set shifted by %s, turned %.0f deg'
              % (_mk.name, _cx, _cy, tuple(round(v, 3) for v in (_M @ Vector((0, 0, 0)))), float(_stage.get('turn', 0.0))))
else:
    bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = FPS

# ---------------------------------------------------------------- characters
# One recipe per actor. A film names a character (kojiro, musashi); map it to a recipe, falling
# back to the reference ronin so a new name never stops a render.
# kojiro / musashi have their own recipes since Nov 26 (the story bible's colours: crimson haori and dark red
# hakama; slate indigo, grey-brown hakama, white headband). Before that both were stand-ins: Kojiro wore the
# ronin's straw hat and Musashi the armoured warrior's plates, which neither had at Ganryujima.
try:
    FILM_CAST = json.load(open(os.path.join(REPO, TL['film']['path'])))['cast'] or {}
except Exception:                   # a timeline without its film file: production recipes only
    FILM_CAST = {}
RECIPES = {'kojiro': 'kojiro', 'musashi': 'musashi', 'ronin': 'ronin-reference', 'warrior': 'armoured-warrior'}
rigs = {}
chars = {}
char_meshes = []          # every built character mesh, for the look block (ink outline) further down
for a in TL['actors']:
    if a.get('hidden'):
        continue
    # a film may name a test recipe for one actor (film.cast.<id>.recipe), e.g. a generated head under review,
    # without touching the production character every other film uses
    rid = FILM_CAST.get(a['id'], {}).get('recipe') or RECIPES.get(a.get('character'), arg('recipe', 'ronin-reference'))
    path = os.path.join(REPO, 'library', 'character-recipes', rid + '.json')
    if not os.path.exists(path):
        path = os.path.join(REPO, 'library', 'character-recipes', 'ronin-reference.json')
    # load_recipe resolves `extends` / swap / add / drop; a bare json.load does not,
    # and the armoured warrior is defined as a diff against the ronin.
    recipe = MB.load_recipe(path)
    ch = MB.build(recipe, name='PC_' + a['id'])
    if a['id'] in DRAWS:
        # the recipe's old hip sword (a box scabbard + handle glued to the torso) would be a second sword
        _old = [o for o in ch['objects'] if o.get('pc_recipe') == 'katana_sheathed']
        ch['objects'] = [o for o in ch['objects'] if o.get('pc_recipe') != 'katana_sheathed']
        for _o in _old:
            bpy.data.objects.remove(_o, do_unlink=True)
    rigs[a['id']] = ch['rig']
    chars[a['id']] = ch
    char_meshes += [o for o in ch['objects'] if o.type == 'MESH']
    print(f"[film] {a['id']} -> {os.path.basename(path)}")

# ---------------------------------------------------------------- the sword
# NOBODY WAS HOLDING ONE. The only katana in part_registry.py is `katana_sheathed`, which sits on the
# hip; there is no drawn blade part at all. Every rendered fight so far has been two figures swinging
# EMPTY HANDS, with a glowing crescent appearing out of nothing beside them.
#
# The data was never missing. The canonical timeline exports each actor weapon transform every frame
# AND at 4x sub-frame resolution, with the frame written in its own metadata: blade along +x from the
# guard at x = 0, edge toward -y, handle along -x. So the blade is built once in that frame and keyed
# from the timeline, exactly like the camera.
import swords as _SW                                             # noqa: E402  blender/props/swords.py
_SW.use(sc.collection)
build_katana, build_bokken = _SW.build_katana, _SW.build_bokken

def _ai_weapon(name, part_id, blade_len, handle, canon=(0.33, 1.38)):
    """A generated weapon prepared in the weapon frame at its canonical size (handle end at -canon[0], length
    canon[1]) scaled to this film's handle + blade, its baked paint as matte wood; same root as build_bokken."""
    import katana_real as _KR
    bm_, mat_ = _KR.ai_fitting(part_id, metallic=0.0, rough=0.78)
    s_ = (handle + blade_len) / canon[1]
    for v_ in bm_.verts:
        v_.co.x = (v_.co.x + canon[0]) * s_ - handle
        v_.co.y *= s_
        v_.co.z *= s_
    me_ = bpy.data.meshes.new(name + '_m')
    bm_.to_mesh(me_)
    bm_.free()
    me_.materials.append(mat_)
    root_ = bpy.data.objects.new(name, None)
    root_.rotation_mode = 'QUATERNION'
    sc.collection.objects.link(root_)
    o_ = bpy.data.objects.new(name + '_part', me_)
    sc.collection.objects.link(o_)
    o_.parent = root_
    return root_


swords = {}
if not flag('no-sword'):
    for _a in TL['actors']:
        if _a.get('hidden'):
            continue
        _w = _a.get('weapon') or {}
        if _a['id'] in DRAWS:
            continue                                            # the real katana + scabbard (below)
        if _w.get('kind') == 'bokken':
            _wp = ((FILMJ.get('cast') or {}).get(_a['id']) or {}).get('weaponPart')
            if _wp:                                             # a generated weapon (library/ai-parts.json), real wood
                swords[_a['id']] = _ai_weapon('BOKKEN_' + _a['id'], _wp, blade_len=_w.get('bladeLen', 0.91) * 1.15,
                                              handle=_w.get('handle', 0.33))
            else:
                swords[_a['id']] = build_bokken('BOKKEN_' + _a['id'], blade_len=_w.get('bladeLen', 0.91) * 1.15,
                                                handle=_w.get('handle', 0.33))
            continue
        swords[_a['id']] = build_katana('KATANA_' + _a['id'],
                                        blade_len=_w.get('bladeLen', 0.91), handle=_w.get('handle', 0.33))
    print('[film] %d blade(s) built from the timeline weapon frame: %s' % (
        len(swords), ', '.join(f"{k} {v.name.split('_')[0].lower()}" for k, v in swords.items())))

# ---------------------------------------------------------------- camera
cd = bpy.data.cameras.new('cam')
# the timeline's lens contract (tools/timeline.mjs SENSOR): focal_mm = 12 / tan(fov / 2), a 24 mm sensor fitted
# VERTICALLY. Blender's default (36 mm, AUTO = the long side, the height in portrait) rendered every film 1.5x wider
# than the camera system designed it (27 Nov, beach f31: Kojiro filled 27-79% of the height; designed 15-94%).
cd.sensor_fit = 'VERTICAL'
cd.sensor_height = 24.0
cam = bpy.data.objects.new('cam', cd)
sc.collection.objects.link(cam)
sc.camera = cam
cam.rotation_mode = 'QUATERNION'

# ---------------------------------------------------------------- bake the timeline
# Keyframe every joint empty and the camera on every frame. The rig is empties driving a deform
# armature (modular_builder.Rig), so keying the empties is what moves the mesh.
# The real sword draw, the grips, the body boundary and the cloth springs for every actor: built here, SOLVED
# ONCE over the whole timeline (production_bake.py) and keyed from that bake, so every render process shows the
# same motion. --stiff-cloth turns the springs off; --bake-only writes the bake and stops (tools/film.sh runs
# it once before the render workers).
import sword_draw as SD                                         # noqa: E402
import katana_real as KR                                        # noqa: E402
import body_capsules as BC                                      # noqa: E402
import cloth_springs as CS                                      # noqa: E402
PACT = []
for aid, rig in rigs.items():
    ch = chars[aid]
    draw = None
    if aid in DRAWS:
        dd = DRAWS[aid]
        # draw.sword: a design in library/swords/ (its curve, handle, fittings, guard - generated or folded - and glow)
        K = KR.build('KATANA_' + aid, sc.collection, blade_len=float(dd.get('blade', 0.91)), design=dd.get('sword'))
        fr_ = lambda t: int(round(float(t) * FPS)) + 1
        draw = SD.Draw(rig, K['sword'], K['saya'], float(dd.get('blade', 0.91)), grab=fr_(dd['grab']),
                       slide=fr_(dd['slide']), clear=fr_(dd['clear']), R=K['R'])
        opens = {s_: [o for o in ch['objects'] if o.get('pc_recipe') == 'hand_folded' and o.get('pc_socket') == 'hand.' + s_]
                 for s_ in ('R', 'L')}
        skin = next((o.data.materials[0] for o in opens['R'] if o.data.materials), None)
        draw.add_hands(opens['R'], opens['L'], skin, skin)
        draw.caps = None if flag('no-keep-out') else BC.BodyCapsules(rig)   # --no-keep-out: the comparison run
        char_meshes += [o for o in K['sword'].children_recursive + K['saya'].children_recursive if o.type == 'MESH']
    springs = None
    if not flag('stiff-cloth'):
        tam = {'rSleeve': [o for o in ch['objects'] if o.get('pc_recipe') == 'tamoto_wide' and o.get('pc_socket', '').endswith('.R')],
               'lSleeve': [o for o in ch['objects'] if o.get('pc_recipe') == 'tamoto_wide' and o.get('pc_socket', '').endswith('.L')]}
        springs = CS.ClothSprings(rig, BC.BodyCapsules(rig), fps=FPS, panels=tam, body=BC.BodyCapsules(rig, shrink=0.035))
    PACT.append(PB.Actor(aid, rig, ch['objects'], draw=draw, springs=springs,
                         caps=None if (draw or flag('no-keep-out')) else BC.BodyCapsules(rig)))

# every switch that changes the solved motion is part of the cache key, so a comparison run can never load
# motion baked under other settings (and its own bake file, so the two never overwrite each other)
_variant = ''.join(s_ for s_, on in (('-stiff', flag('stiff-cloth')), ('-nokeep', flag('no-keep-out'))) if on)
_stamp = PB.bake_stamp(REPO, FILM) + _variant
BAKE_PATH = os.path.join(REPO, 'output', FILM + '.bake' + _variant + '.json')
BAKE = PB.load(BAKE_PATH, _stamp)
if BAKE is None:
    print(f'[bake] solving {len(FRAMES)} frames once (draw: {sorted(DRAWS) or "none"}, springs: {not flag("stiff-cloth")})')
    BAKE = PB.solve(TL, PACT, FPS, checks=True)
    PB.save(BAKE, BAKE_PATH, _stamp)
    for line in PB.report(BAKE, len(FRAMES)):
        print(line)
    print('[bake] ->', BAKE_PATH)
else:
    print('[bake] using', BAKE_PATH, '(stamp', _stamp + ')')
if flag('bake-only'):
    raise SystemExit(0)
if flag('report'):
    for line in PB.report(BAKE, len(FRAMES)):
        print(line)

# ---------------------------------------------------------------- lens: depth of field and motion blur
# film.effects.dof: true | f-stop number (true = the timeline's aperture, 2.8 by default); --no-dof turns it off.
# film.effects.motionBlur: shutter in frames (0.5 = a 180-degree shutter); --no-blur turns it off.
# Both used to stop at the timeline: it exported focus_m and aperture on every frame and nothing read them.
_EFX = TL.get('effects') or {}
_DOF = bool(_EFX.get('dof')) and not flag('no-dof')
if _DOF:
    cd.dof.use_dof = True
    _ap = _EFX['dof'] if isinstance(_EFX.get('dof'), (int, float)) and not isinstance(_EFX.get('dof'), bool) else \
        ((FRAMES[0].get('camera') or {}).get('aperture') or 2.8)
    cd.dof.aperture_fstop = float(_ap)
_BLUR = float(_EFX.get('motionBlur') or 0) if not flag('no-blur') else 0.0
if _BLUR > 0:
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = _BLUR
    # the shutter OPENS on the frame: a cut frame samples only the new shot, the frame before it only the old one
    sc.render.motion_blur_position = 'START'
_CUTS = {r['f'] for r in FRAMES if r.get('cut')}
print('[lens] dof %s · motion blur %s · %d cut(s)' % (('f/%.1f' % cd.dof.aperture_fstop) if _DOF else 'off',
                                                   ('%.2f frame' % _BLUR) if _BLUR else 'off', len(_CUTS)))

# ---------------------------------------------------------------- the camera on terrain (autopilot item 13)
# The timeline's camera is composed on flat ground (z 0 under everyone). On a set's terrain each body stands on its
# own ground (production_bake 'base'), so the camera rises or sinks with the shot's SUBJECTS (the camera beat's
# `subjects`: the mean of their ground) and the designed framing holds. And it never ends up under the sand or the
# sea at its own spot: there it is raised to a clearance and turned (pitch only) so the subjects' centre stays on the
# same point of the screen. 27 Nov: weighting by distance to every body sank the IMPACT camera into the shallows (a
# black frame) and dropped the MEDIUM on Kojiro by Musashi's slope (his head cut off).
_CAM_BEATS = sorted([b for b in (FILMJ.get('camera') or []) if isinstance(b, dict) and 't' in b], key=lambda b: float(b['t']))
_CAM_SKIP = set(char_meshes) | {o for _r in swords.values() for o in [_r] + list(_r.children_recursive)}
_cam_ground = PB.ground_sampler(sc, _CAM_SKIP) if arg('set') else None
_cam_sea0 = PB.sea_sampler(sc) if arg('set') else None                # the sea as built (one BVH, cheap)
_cam_sea = PB.sea_sampler(sc, live=True) if arg('set') else None       # this frame's waves: only for a low camera
_cam_log = []


def _beat_subjects(tb):
    """The subjects of the camera beat on screen at body time tb (a later beat without subjects keeps the shot's)."""
    subj = None
    for b in _CAM_BEATS:
        if float(b['t']) > tb + 1e-6:
            break
        if b.get('subjects'):
            subj = b['subjects']
    return subj


def _terrain_camera(i, fr, c, base):
    subj = [s for s in (_beat_subjects(float(fr.get('tb', fr.get('t', 0.0)))) or []) if s in base]
    if not subj:
        subj = [s for s in base if isinstance((fr['actors'].get(s) or {}).get('pose'), dict)]
    if subj:
        cam.location.z += sum(base[s] for s in subj) / len(subj)
    if _cam_ground is None and _cam_sea is None:
        return
    x, y = cam.location.x, cam.location.y
    # the first up-facing surface below a point 1 m over the lens (so a pine canopy high above is not the floor)
    g = _cam_ground(x, y, cam.location.z + 1.0) if _cam_ground else None
    s = _cam_sea0(x, y) if _cam_sea0 else None
    if s is not None and cam.location.z < s + 1.5:
        s = _cam_sea(x, y)                                  # near the water: the surface of this frame
    floor = max([v for v in (g, s) if v is not None], default=None)
    need = min(0.3, max(0.05, float(c['pos'][1])))          # a camera designed lower than 0.3 m keeps its own height
    if floor is None or cam.location.z >= floor + need:
        return
    P = Vector((0.0, 0.0, 0.0))
    for s_ in subj:
        p_ = fr['actors'][s_]['pose']
        P += Vector((float(p_.get('x', 0.0)), -float(p_.get('z', 0.0)), base[s_] + 1.0))   # chest height
    P /= max(1, len(subj))
    was = cam.location.copy()
    cam.location.z = floor + need
    d0, d1 = P - was, P - cam.location
    if subj and d0.length > 1e-3 and d1.length > 1e-3:
        cam.rotation_quaternion = d0.normalized().rotation_difference(d1.normalized()) @ cam.rotation_quaternion
    _cam_log.append((i + 1, round(cam.location.z - was.z, 3), 'sea' if s is not None and floor == s else 'ground'))

for i in range(f0, f1 + 1):
    fr = FRAMES[i]
    bpy.context.scene.frame_set(i + 1)      # ABSOLUTE timeline frame, 1-based
    PB.apply(BAKE, i, PACT)                 # joints, deform bones, real sword + scabbard, hands: from the bake
    # the terrain each body was put on (production_bake: the set's ground under it; 0 on the film's flat ground)
    _base = {_a: ((BAKE['actors'].get(_a) or {}).get('base') or [None] * (i + 1))[i] or 0.0 for _a in rigs}
    for _aid, _sw in swords.items():
        _act = fr['actors'].get(_aid)
        if _act and _act.get('weapon'):
            _w = _act['weapon']
            _sw.location = v3(_w[:3]) + Vector((0.0, 0.0, _base.get(_aid, 0.0)))   # in the hands on a slope too
            _sw.rotation_quaternion = q3(_w[3:7])
            _sw.keyframe_insert('location')
            _sw.keyframe_insert('rotation_quaternion')
    c = fr.get('camera')
    if c and not arg('lookat'):
        cam.location = v3(c['pos'])
        cam.rotation_quaternion = qcam(c['rot'])
        _terrain_camera(i, fr, c, _base)                       # the shot's subjects' ground, clear of sand and sea
        cd.lens = c.get('focal_mm', 40)
        cam.keyframe_insert('location')
        cam.keyframe_insert('rotation_quaternion')
        cd.keyframe_insert('lens')
        if _DOF and c.get('focus_m'):                           # depth of field / rack focus, keyed from the timeline
            cd.dof.focus_distance = float(c['focus_m'])
            cd.dof.keyframe_insert('focus_distance')
if _cam_log:
    print('[camera] raised clear of the %s on %d frame(s) (frame, metres): %s' % (
        '/'.join(sorted({k for _f, _d, k in _cam_log})), len(_cam_log), [(f_, d_) for f_, d_, _k in _cam_log[:12]]))

if flag('camera-report'):
    # What the camera sees, frame by frame, measured without a render: its height over the sand / sea under it, the
    # object in the centre of the frame, and where a 9 x 16 grid of rays lands (a character, the set, the sea, the sky).
    # A frame whose grid is mostly 'set' at a short distance is a camera inside or behind something (27 Nov: f50 of
    # the shore film was the dark side of a sand bank seen from the water).
    _cm = set(char_meshes)
    _rows = []
    for i in range(f0, f1 + 1, int(arg('camera-step', 1))):
        sc.frame_set(i + 1)
        _dg = bpy.context.evaluated_depsgraph_get()
        _M = cam.matrix_world.copy()
        _o = _M.translation.copy()
        _tr, _br, _bl, _tl = cam.data.view_frame(scene=sc)
        _cnt = {'cast': 0, 'set': 0, 'sea': 0, 'sky': 0}
        _near = 0
        _centre = None
        for gy in range(17):
            for gx in range(9):
                u, v = (gx + 0.5) / 9, (gy + 0.5) / 17
                _p = (_bl.lerp(_tl, v)).lerp(_br.lerp(_tr, v), u)
                _d = (_M.to_3x3() @ _p).normalized()
                hit, loc, _n, _ix, ob, _mx = sc.ray_cast(_dg, _o, _d, distance=500.0)
                k = 'sky' if not hit or ob.name.startswith('SKY') else 'cast' if ob in _cm else 'sea' if ob.name.startswith('SEA') else 'set'
                _cnt[k] += 1
                if hit and k == 'set' and (loc - _o).length < 1.0:
                    _near += 1
                if gx == 4 and gy == 8:
                    _centre = (ob.name if hit else 'sky', round((loc - _o).length, 2) if hit else None)
        _g = _cam_ground(_o.x, _o.y, _o.z + 1.0) if _cam_ground else None
        _s = _cam_sea(_o.x, _o.y) if _cam_sea else None
        _fl = max([v for v in (_g, _s) if v is not None], default=None)
        _n = sum(_cnt.values())
        _row = {'frame': i + 1, 'cam': [round(v, 3) for v in _o], 'clearance': None if _fl is None else round(_o.z - _fl, 3),
                'over': None if _fl is None else ('sea' if _s is not None and _fl == _s else 'ground'),
                'centre': _centre, 'grid': {k: round(v / _n, 3) for k, v in _cnt.items()}, 'set_within_1m': round(_near / _n, 3)}
        _rows.append(_row)
        print('[camera-report] f%d cam %s clearance %s over %s · centre %s · cast %.0f%% set %.0f%% sea %.0f%% sky %.0f%%'
              ' · set within 1 m %.0f%%' % (_row['frame'], _row['cam'], _row['clearance'], _row['over'], _centre,
                                          100 * _row['grid']['cast'], 100 * _row['grid']['set'], 100 * _row['grid']['sea'],
                                          100 * _row['grid']['sky'], 100 * _row['set_within_1m']))
    json.dump({'film': FILM, 'set': arg('set'), 'rows': _rows},
              open(os.path.join(REPO, 'output', FILM + '.camera-report.json'), 'w'), indent=1)
    if flag('camera-report-only'):
        raise SystemExit(0)

if flag('ground-report'):
    # Feet against the set's ground, frame by frame, measured (no render): the gap between each ankle joint and the
    # surface under it. Planted feet should sit at the ankle's rest height (~0.02 m); below 0 = buried.
    from mathutils.bvhtree import BVHTree
    _dg = bpy.context.evaluated_depsgraph_get()
    _char_objs = {o for o in char_meshes}
    _ground = [o for o in bpy.data.objects if o.type == 'MESH' and o not in _char_objs and o.visible_get()
               and not o.name.startswith(('SEA', 'SKY', 'PC_', 'MARK_')) and len(o.data.polygons)]
    _trees = [(o, BVHTree.FromObject(o, _dg)) for o in _ground]
    _sea_at = PB.sea_sampler(sc, live=True)                              # a foot under the sea surface is 'wet' (staged in the water)
    _wet = []
    rows = []
    for i in range(f0, f1 + 1, int(arg('ground-step', 1))):
        sc.frame_set(i + 1)
        _row = {'frame': i}
        for _aid, _rig in rigs.items():
            for _ft in ('lfoot', 'rfoot'):
                p = _rig.J[_ft].matrix_world.translation
                best = None
                for _o, _t in _trees:
                    inv = _o.matrix_world.inverted()
                    for d in ((0, 0, -1), (0, 0, 1)):
                        o_l = inv @ (p + Vector((0, 0, 0.6 if d[2] < 0 else -0.6)))
                        hit = _t.ray_cast(o_l, (inv.to_3x3() @ Vector(d)).normalized(), 3.0)
                        if hit[0] is not None:
                            gz = (_o.matrix_world @ hit[0]).z
                            if best is None or abs(p.z - gz) < abs(p.z - best):
                                best = gz
                _row[f'{_aid}.{_ft}'] = None if best is None else round(p.z - best, 4)
                _sz = _sea_at(p.x, p.y) if _sea_at else None
                if _sz is not None and _sz > p.z + 0.02:
                    _row[f'{_aid}.{_ft}.wet'] = round(_sz - p.z, 3)
                    _wet.append(_sz - p.z)
        rows.append(_row)
    _gaps = [v for r in rows for k, v in r.items() if k != 'frame' and not k.endswith('.wet') and v is not None]
    if _wet:
        print('[ground] WARNING %d foot samples are UNDER THE SEA surface (up to %.2f m deep): the film is staged in the '
              'water (film.stage) - only right for a wading shot' % (len(_wet), max(_wet)))
    _out = os.path.join(REPO, 'output', FILM + '.ground.json')
    json.dump({'set': arg('set'), 'rows': rows}, open(_out, 'w'), indent=1)
    if _gaps:
        print('[ground] %d foot samples: gap min %.3f m, median %.3f m, max %.3f m; buried (<-0.01): %d -> %s'
              % (len(_gaps), min(_gaps), sorted(_gaps)[len(_gaps) // 2], max(_gaps), sum(1 for g in _gaps if g < -0.01), _out))
    else:
        print('[ground] no ground found under the feet ->', _out)
    if flag('ground-report-only'):
        raise SystemExit(0)

if flag('mannequin'):
    import swords as _SWm                                       # noqa: E402
    PB.build_mannequin(BAKE, PACT, None, sc, _SWm._flat_mat)

# The engine's poses are already eased; Blender re-easing them would double the smoothing and the
# snap of a cut would soften into a drift. Hold every curve linear between the baked frames.
# (Review, 26 Nov: this loop used to visit the Rig WRAPPERS, which carry no animation, so the joint empties
# that are actually keyed kept Blender's Bezier easing and every cut was softened. Visit the joints.)
for ob in [e for r in rigs.values() for e in r.J.values()] + [r.rig for r in rigs.values()] + list(swords.values()) + \
        [x for a_ in PACT if a_.draw for x in (a_.draw.sword, a_.draw.saya)] + [cam, cd]:
    ad = getattr(ob, 'animation_data', None)
    act = getattr(ad, 'action', None) if ad else None
    if not act:
        continue
    for fc in getattr(act, 'fcurves', []):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
# A hard cut: the camera key on the frame BEFORE the cut holds (CONSTANT) until the cut frame, so neither motion
# blur nor a sub-frame sample ever sees the camera flying from one set-up to the next.
for ob in (cam, cd):                                           # cd carries lens and focus distance
    ad = getattr(ob, 'animation_data', None)
    act = getattr(ad, 'action', None) if ad else None
    for fc in (act.fcurves if act else []):
        for kp in fc.keyframe_points:
            if int(round(kp.co.x)) in _CUTS:        # Blender frame n = timeline frame n-1: the last frame of the old shot
                kp.interpolation = 'CONSTANT'

# ---------------------------------------------------------------- the paper slash
# blender/world/slash_fx.py has had a finished slash in it for weeks and no film ever had one,
# because nothing imported it. It is driven here from the blade's OWN path in the timeline - the
# weapon transform is exported every frame and at 4x sub-frame resolution precisely so this is
# possible - so a kesa-giri comes out diagonal because the cut was diagonal, not because someone
# typed a tilt. --no-slash turns it off.
# The slash (and anything else read off the timeline's weapon path) must follow the sword that is RENDERED.
# For an actor that draws the real katana, the baked sword differs from the engine's path by up to ~1 m during
# the cut (measured on kojiro-draw: frames 39-48), so its weapon path is rewritten from the bake, in three.js
# axes: position (X, Y, Z)_blender -> (X, Z, -Y); quaternion (w, a, b, c)_blender -> (a, c, -b, w)
# (the inverse of q3), and its engine sub-samples are dropped.
for _a in PACT:
    if not _a.draw:
        continue
    _rec = BAKE['actors'][_a.aid]
    _k = -1
    for _i, _fr in enumerate(FRAMES):
        _act = _fr['actors'].get(_a.aid)
        if _rec['J'][_i] is None or not _act:
            continue
        _k += 1
        _sx, _sy, _sz, _w, _qa, _qb, _qc = _rec['sword'][_k]
        _act['weapon'] = [_sx, _sz, -_sy, _qa, _qc, -_qb, _w]
    for _sf in TL.get('subframes') or []:
        if _a.aid in (_sf.get('actors') or {}):
            _sf['actors'][_a.aid].pop('weapon', None)

if not flag('no-slash'):
    try:
        sys.path.insert(0, os.path.join(HERE, 'world'))
        import slash_fx
        import slash_from_blade as SB
        _ev_p = os.path.join(REPO, 'output', FILM + '.bake-events.json')
        _ev = json.load(open(_ev_p)) if os.path.exists(_ev_p) else None
        _contact = None
        if _ev and _ev.get('contact', {}).get('touch'):
            _contact = {'t': _ev['contact']['t'], 'striker': _ev.get('striker'), 'blocker': _ev.get('blocker')}
            print(f"[film] slash cut at the bake contact: frame {_ev['contact']['subframe']} (t {_ev['contact']['t']} s)")
        cuts = SB.add_slashes(TL, FPS, f0, f1, slash_fx,
                              min_speed=float(arg('slash-speed', 5.0)), contact=_contact)
        for c in cuts:
            print(f"[film] slash {c['actor']} f{c['f0']}-{c['f1']}  {c['sweep']:+.0f} deg  "
                  f"r={c['radius']} m  {c['speed']} m/s")
        print(f'[film] {len(cuts)} slash(es) from the blade path')
    except Exception as e:
        print(f'[film] slash effect skipped ({type(e).__name__}: {e})')

# ---------------------------------------------------------------- light and render
# studio() takes 'neutral' or 'cinematic' only. 'dawn' fell through and rendered black.
# CINEMATIC by default. `neutral` is the flat studio the character models are audited under - it
# hides nothing, which is what an audit wants and the opposite of what a film wants. A film lit that
# way comes out as two grey figures in a grey void, and that is what every modular render looked
# like until this line. `cinematic` is the Lantern Origami key: dark, the paper glowing from inside.
# Pass --light neutral when you are inspecting a model, not shooting it.
if arg('set'):
    # A set brings its own world, its own sun and its own fighter key/fill/rim (library/sets/*.json
    # "lighting"). studio() REPLACES scene.world and adds three area lamps, so calling it here threw
    # away the set's sky and mist and then put a lamp in shot - the blown white rectangle in the
    # middle of the bamboo-forest test. Inside a set, the set lights it.
    #
    # But the set's SUN alone leaves the cast reading as two dull shapes against a lit world: the
    # grove is lit for the grove. Every set file carries a `lighting.fighter` rig - key, fill and
    # rim, as offsets from whoever is standing there - written for exactly this. It was only ever
    # applied by the set builder's own --with-character preview, so a film never got it. Each actor
    # now carries that rig, parented to its root, so it travels with the performer through the shot.
    print('[film] set supplied the world and sun; adding its fighter key/fill/rim per actor')
    sj = os.path.join(REPO, 'library', 'sets', os.path.splitext(os.path.basename(arg('set')))[0] + '.json')
    fighter = {}
    if os.path.exists(sj):
        fighter = (json.load(open(sj)).get('lighting') or {}).get('fighter') or {}
    for aid, rig in rigs.items():
        for role, spec in fighter.items():
            L = bpy.data.lights.new(f'{role}_{aid}', 'AREA')
            L['pc_fighter'] = role               # the look block's `key` factor finds these by this tag
            L.energy = spec.get('energy', 20)
            L.size = spec.get('size', 1.5)
            L.color = tuple(spec.get('color', (1, 1, 1)))[:3]
            o = bpy.data.objects.new(f'L_{role}_{aid}', L)
            o.visible_camera = False                 # a lamp in shot is a white rectangle
            off = Vector(spec.get('offset', (0, 2, 2)))
            o.location = off
            # aim at the actor's chest, about 1.2 m up from the root the offset is measured from
            o.rotation_euler = (Vector((0, 0, 1.2)) - off).to_track_quat('-Z', 'Y').to_euler()
            sc.collection.objects.link(o)
            # FOLLOW THE POSITION, KEEP THE WORLD DIRECTION. Parenting to the root would carry the
            # light's rotation too, so a performer who turns away would swing their own key light
            # round behind them and stay lit exactly as before - which reads as no light source at
            # all. The offsets in a set file are written in the SET's frame (the bamboo key sits
            # back and to the left, where the sun is), so they are world offsets from wherever the
            # performer is standing. Copy Location with an offset is that, exactly: it follows
            # through a dash, a turn or a cut, and the key stays where the sun is.
            cl = o.constraints.new('COPY_LOCATION')
            cl.target = rig.J['root']
            cl.use_offset = True
else:
    MB.studio(sc, arg('light', 'cinematic'))
setup_render(sc, engine=arg('engine'), quality=arg('quality', 'check'),
             samples=int(arg('samples')) if arg('samples') else None)

# COMPOSITING. blender/sets/build_set.py has built bloom and a vignette as compositor nodes since
# the sets existed, and no film has ever called it - grep said 0. So the studio audit's standing
# complaint ("no post FX: no bloom on the eyes and the smear, no grade, no grain") was not a missing
# feature, it was an unwired one. Bloom is also what makes the inner lantern read as LIGHT rather
# than as a patch of pale paint, which is the whole style.
# Values come from the set when there is one (library/sets/*.json "lighting"), since a set's author
# chose them for that world; otherwise the Lantern Origami default.
try:
    sys.path.insert(0, os.path.join(HERE, 'sets'))
    from build_set import post as _post
    _bloom, _vig = float(arg('bloom', 0.55)), float(arg('vignette', 0.35))
    if arg('set'):
        _sj = os.path.join(REPO, 'library', 'sets', os.path.splitext(os.path.basename(arg('set')))[0] + '.json')
        if os.path.exists(_sj):
            _lt = (json.load(open(_sj)).get('lighting') or {})
            _bloom, _vig = float(_lt.get('bloom', _bloom)), float(_lt.get('vignette', _vig))
    _post(sc, _bloom, _vig)
    print(f'[film] post: bloom {_bloom}, vignette {_vig}')
except Exception as e:                      # a film without bloom is worse, not broken
    print(f'[film] post FX unavailable ({e}); rendering without them')

# ---------------------------------------------------------------- look
# docs/LOOK-TARGET.md measured the gap: the target is a dark frame with bright accents (luma 1% < 10,
# median ~50, 95% > 195); ours had no black anywhere and the character sat at the same value as the
# world around it ("all almost equally bright", docs/WHY-IT-LOOKS-FLAT.md). These are the knobs that
# move those numbers. DATA FIRST: a set's `lighting.film` block holds them (library/sets/*.json), so a
# location carries its own mood; a flag of the same name overrides it for one render. Every default
# is "no change", so a set without the block renders exactly as before.
#   ambient  multiplies the sky's LIGHT on the scene but not the sky the camera sees: darker fill,
#            so the key and the inner lantern separate from it, without greying out the dawn
#   sun      multiplies the set's sun lamp(s)
#   key      multiplies each performer's key / fill / rim (the set's `lighting.fighter` rig)
#   outline  ink line width in metres round every character part and blade (blender/world/toon.py,
#            an inverted hull: no compositor pass, survives motion blur); 0 = none
#   look / exposure   the AgX look and the EV the film is graded at
_film_look = {}
if arg('set'):
    _lj = os.path.join(REPO, 'library', 'sets', os.path.splitext(os.path.basename(arg('set')))[0] + '.json')
    if os.path.exists(_lj):
        _film_look = (json.load(open(_lj)).get('lighting') or {}).get('film') or {}


def knob(name, default):
    v = arg(name)
    return float(v) if v is not None else float(_film_look.get(name, default))


_ambient, _sun, _key, _outline = knob('ambient', 1.0), knob('sun', 1.0), knob('key', 1.0), knob('outline', 0.0)
if _ambient != 1.0 and sc.world and sc.world.use_nodes:
    wnt = sc.world.node_tree
    wout = next((n for n in wnt.nodes if n.type == 'OUTPUT_WORLD' and n.is_active_output), None) \
        or next((n for n in wnt.nodes if n.type == 'OUTPUT_WORLD'), None)
    if wout and wout.inputs['Surface'].is_linked:
        orig = wout.inputs['Surface'].links[0].from_socket
        black = wnt.nodes.new('ShaderNodeBackground')
        black.inputs['Strength'].default_value = 0.0
        dim = wnt.nodes.new('ShaderNodeMixShader')                # orig * ambient
        dim.inputs['Fac'].default_value = max(0.0, min(1.0, 1.0 - _ambient))
        wnt.links.new(orig, dim.inputs[1])
        wnt.links.new(black.outputs[0], dim.inputs[2])
        lp = wnt.nodes.new('ShaderNodeLightPath')
        cam_mix = wnt.nodes.new('ShaderNodeMixShader')            # the camera still sees the full sky
        wnt.links.new(lp.outputs['Is Camera Ray'], cam_mix.inputs['Fac'])
        wnt.links.new(dim.outputs[0], cam_mix.inputs[1])
        wnt.links.new(orig, cam_mix.inputs[2])
        wnt.links.new(cam_mix.outputs[0], wout.inputs['Surface'])
for _ob in sc.objects:
    if _ob.type != 'LIGHT':
        continue
    if _sun != 1.0 and _ob.data.type == 'SUN':
        _ob.data.energy *= _sun
    if _key != 1.0 and _ob.data.get('pc_fighter'):
        _ob.data.energy *= _key
if _outline > 0:
    import toon
    _blades = [o for o in sc.objects if o.type == 'MESH' and o.parent and o.parent.name.startswith(('KATANA_', 'BOKKEN_'))]
    for _o in char_meshes + _blades:
        toon.ink_outline(_o, width=_outline * (0.5 if _o in _blades else 1.0))   # a blade takes a finer line
if arg('look') or _film_look.get('look'):
    sc.view_settings.look = arg('look') or _film_look['look']
if arg('exposure') is not None or 'exposure' in _film_look:
    sc.view_settings.exposure = float(arg('exposure') if arg('exposure') is not None else _film_look['exposure'])
print(f'[film] look: ambient {_ambient}, sun {_sun}, key {_key}, outline {_outline} m, '
      f'{sc.view_settings.look}, exposure {sc.view_settings.exposure:+.2f}')
sc.render.resolution_x, sc.render.resolution_y = [int(v) for v in arg('res', '540x960').split('x')]
# Absolute frame numbers. tools/film.sh renders ranges in parallel into ONE folder, so f0001 must
# mean timeline frame 0 in every worker; numbering each range from 1 would have every worker
# overwrite the first frames of every other one and the film would come out as the last range only.
sc.frame_start, sc.frame_end = f0 + 1, f1 + 1
out = arg('out', os.path.join(REPO, 'output', 'modular', FILM))
os.makedirs(out, exist_ok=True)
sc.render.filepath = os.path.join(out, 'f')
sc.render.image_settings.file_format = arg('format', 'PNG').upper()
if arg('lookat'):
    # Diagnostic: ignore the timeline's camera orientation and aim at the cast, to prove the
    # characters are in frame at all before trusting the quaternion conversion.
    look = bpy.data.objects.new('look', None); sc.collection.objects.link(look)
    look.location = (0, 0, 1.0)
    tr = cam.constraints.new('TRACK_TO'); tr.target = look
    tr.track_axis = 'TRACK_NEGATIVE_Z'; tr.up_axis = 'UP_Y'
    cam.animation_data_clear()
    cam.location = (3.5, -5.0, 2.0)
    cd.lens = 40

print(f'[film] {f1 - f0 + 1} frames -> {out}')
bpy.context.scene.frame_set(f0 + 1)
print('[film] camera at', [round(v,2) for v in cam.location])
for aid, rig in rigs.items():
    print('[film]', aid, 'root at', [round(v,2) for v in rig.J['root'].location])
if arg('probe'):
    # Diagnostic (no render): where are a SKINNED part (kimono/hakama, deformed by the armature) and a RIGID
    # part (parented to a control empty) on the asked frames, visited in the asked order? If the skinned
    # centroid does not move while the rigid one does, the deform bones are not following the controls.
    dg = None
    for f in [int(v) for v in arg('probe').split(',')]:
        bpy.context.scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        for aid in rigs:
            row = []
            for kind in ('skin', 'rigid'):
                obs = [o for o in char_meshes if o.get('pc_bind', 'skin' if o.parent and o.parent.type == 'ARMATURE' else '') == kind
                       or (kind == 'skin' and o.parent is not None and o.parent.type == 'ARMATURE')]
                obs = [o for o in obs if aid in o.name.lower() or True][:40]
                tot, n = Vector((0, 0, 0)), 0
                for o in obs:
                    me = o.evaluated_get(dg).to_mesh()
                    for v in me.vertices[:200] if len(me.vertices) < 400 else list(me.vertices)[::4]:
                        tot += o.matrix_world @ v.co
                        n += 1
                    o.evaluated_get(dg).to_mesh_clear()
                row.append('%s centroid %s' % (kind, [round(c, 3) for c in (tot / max(n, 1))]))
            print('[probe] frame %d %s: %s' % (f, aid, ' | '.join(row)))
    raise SystemExit(0)
bpy.ops.render.render(animation=True)
