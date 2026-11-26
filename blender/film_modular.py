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
from mathutils import Quaternion, Vector

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
RECIPES = {'kojiro': 'kojiro', 'musashi': 'musashi', 'ronin': 'ronin-reference', 'warrior': 'armoured-warrior'}
rigs = {}
chars = {}
char_meshes = []          # every built character mesh, for the look block (ink outline) further down
for a in TL['actors']:
    if a.get('hidden'):
        continue
    rid = RECIPES.get(a.get('character'), arg('recipe', 'ronin-reference'))
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

swords = {}
if not flag('no-sword'):
    for _a in TL['actors']:
        if _a.get('hidden'):
            continue
        _w = _a.get('weapon') or {}
        if _a['id'] in DRAWS:
            continue                                            # the real katana + scabbard (below)
        if _w.get('kind') == 'bokken':
            swords[_a['id']] = build_bokken('BOKKEN_' + _a['id'], blade_len=_w.get('bladeLen', 0.91) * 1.15,
                                            handle=_w.get('handle', 0.33))
            continue
        swords[_a['id']] = build_katana('KATANA_' + _a['id'],
                                        blade_len=_w.get('bladeLen', 0.91), handle=_w.get('handle', 0.33))
    print('[film] %d blade(s) built from the timeline weapon frame: %s' % (
        len(swords), ', '.join(f"{k} {v.name.split('_')[0].lower()}" for k, v in swords.items())))

# ---------------------------------------------------------------- camera
cd = bpy.data.cameras.new('cam')
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
        K = KR.build('KATANA_' + aid, sc.collection, blade_len=float(dd.get('blade', 0.91)))
        fr_ = lambda t: int(round(float(t) * FPS)) + 1
        draw = SD.Draw(rig, K['sword'], K['saya'], float(dd.get('blade', 0.91)), grab=fr_(dd['grab']),
                       slide=fr_(dd['slide']), clear=fr_(dd['clear']), R=K['R'])
        opens = {s_: [o for o in ch['objects'] if o.get('pc_recipe') == 'hand_folded' and o.get('pc_socket') == 'hand.' + s_]
                 for s_ in ('R', 'L')}
        skin = next((o.data.materials[0] for o in opens['R'] if o.data.materials), None)
        draw.add_hands(opens['R'], opens['L'], skin, skin)
        draw.caps = BC.BodyCapsules(rig)
        char_meshes += [o for o in K['sword'].children_recursive + K['saya'].children_recursive if o.type == 'MESH']
    springs = None
    if not flag('stiff-cloth'):
        tam = {'rSleeve': [o for o in ch['objects'] if o.get('pc_recipe') == 'tamoto_wide' and o.get('pc_socket', '').endswith('.R')],
               'lSleeve': [o for o in ch['objects'] if o.get('pc_recipe') == 'tamoto_wide' and o.get('pc_socket', '').endswith('.L')]}
        springs = CS.ClothSprings(rig, BC.BodyCapsules(rig), fps=FPS, panels=tam, body=BC.BodyCapsules(rig, shrink=0.035))
    PACT.append(PB.Actor(aid, rig, ch['objects'], draw=draw, springs=springs,
                         caps=None if (draw or flag('no-keep-out')) else BC.BodyCapsules(rig)))

BAKE_PATH = os.path.join(REPO, 'output', FILM + '.bake.json')
_stamp = PB.bake_stamp(REPO, FILM) + ('-stiff' if flag('stiff-cloth') else '')
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

for i in range(f0, f1 + 1):
    fr = FRAMES[i]
    bpy.context.scene.frame_set(i + 1)      # ABSOLUTE timeline frame, 1-based
    PB.apply(BAKE, i, PACT)                 # joints, deform bones, real sword + scabbard, hands: from the bake
    for _aid, _sw in swords.items():
        _act = fr['actors'].get(_aid)
        if _act and _act.get('weapon'):
            _w = _act['weapon']
            _sw.location = v3(_w[:3])
            _sw.rotation_quaternion = q3(_w[3:7])
            _sw.keyframe_insert('location')
            _sw.keyframe_insert('rotation_quaternion')
    c = fr.get('camera')
    if c and not arg('lookat'):
        cam.location = v3(c['pos'])
        cam.rotation_quaternion = qcam(c['rot'])
        cd.lens = c.get('focal_mm', 40)
        cam.keyframe_insert('location')
        cam.keyframe_insert('rotation_quaternion')
        cd.keyframe_insert('lens')

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
        cuts = SB.add_slashes(TL, FPS, f0, f1, slash_fx,
                              min_speed=float(arg('slash-speed', 5.0)))
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
