"""Sword-draw test: one swordsman draws from the scabbard, rendered as a short clip.

  blender -b -P blender/draw_test.py -- --recipe kojiro --out output/draw-test --res 360x640 [--blade 0.91]

The poses are the library's own nukitsuke keys (library/moves.json, library/poses.json) slowed so the
draw reads; the sword and scabbard come from blender/props/sword_draw.py. Prints the phase per frame.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
for p in ('character', 'world', 'props', ''):
    sys.path.insert(0, os.path.join(HERE, p))

import modular_builder as MB                         # noqa: E402
import swords as SW                                  # noqa: E402
import sword_draw as SD                              # noqa: E402
from render_engine import setup_render               # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(k, d=None):
    return argv[argv.index('--' + k) + 1] if '--' + k in argv else d


FPS = int(arg('fps', 30))                          # the delivery rate (1080x1920, 30 fps)
RECIPE = arg('recipe', 'kojiro')
BLADE = float(arg('blade', 0.91))
OUT = os.path.join(REPO, arg('out', 'output/draw-test'))

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = FPS

recipe = MB.load_recipe(os.path.join(REPO, 'library', 'character-recipes', RECIPE + '.json'))
ch = MB.build(recipe, name='PC_' + RECIPE)
rig = ch['rig']

# the recipe's OLD hip sword (part_registry.katana_sheathed: a box scabbard + handle + guard glued to the
# torso) would be a second sword next to the real one: it goes
_old = [o for o in ch['objects'] if o.get('pc_recipe') == 'katana_sheathed']
ch['objects'] = [o for o in ch['objects'] if o.get('pc_recipe') != 'katana_sheathed']
for _o in _old:
    bpy.data.objects.remove(_o, do_unlink=True)
SW.use(sc.collection)
import katana_real as KR                             # noqa: E402  the real sword + scabbard (one base)
K = KR.build('KATANA', sc.collection, blade_len=BLADE)
sword, saya = K['sword'], K['saya']
saya.name = 'SAYA'

# ---------------------------------------------------------------- the move, in seconds
POSES = json.load(open(os.path.join(REPO, 'library', 'poses.json')))
# The body DRIVES the cut (review, 26 Nov: "the sword moves but the character barely moves with it"):
# coil back (weight back, hips and chest turned away), the slide, then the hips turn first, the chest
# follows a beat later, the arm last (overlap), with a step and a weight shift into the cut, an overshoot,
# and a settled hold (zanshin). ty = hips/torso turn, cy = chest turn (+ = right shoulder forward),
# z = step forward, weight = hips forward. The arms come from the library's nukitsuke poses.
KEYS = [  # (time s, pose, overrides)
    (0.00, 'standing', {}),
    (0.45, 'iai-ready', {'ty': 0.0, 'cy': 0.0}),                                   # hands to sword + scabbard
    (0.85, 'iai-ready', {'crouch': 0.30, 'weight': 0.22, 'tx': 0.32, 'ty': -0.25, 'cy': -0.10}),   # the coil
    (1.05, 'iai-ready', {'crouch': 0.31, 'weight': 0.22, 'tx': 0.33, 'ty': -0.28, 'cy': -0.12}),   # koiguchi held
    (1.30, 'nuki-draw-mid', {'crouch': 0.25, 'weight': 0.48, 'z': 0.14, 'ty': 0.05, 'cy': -0.15}), # hips lead
    (1.45, 'nukitsuke-contact', {'crouch': 0.20, 'weight': 0.66, 'z': 0.27, 'stance': 0.85, 'ty': 0.40, 'cy': 0.05}),
    (1.58, 'nukitsuke-finish', {'crouch': 0.19, 'weight': 0.73, 'z': 0.30, 'stance': 0.85, 'ty': 0.55, 'cy': 0.25}),  # overshoot
    (1.90, 'nukitsuke-finish', {'crouch': 0.23, 'weight': 0.66, 'z': 0.30, 'stance': 0.85, 'ty': 0.45, 'cy': 0.15}),  # settle
    (3.00, 'nukitsuke-finish', {'crouch': 0.23, 'weight': 0.66, 'z': 0.30, 'stance': 0.85, 'ty': 0.45, 'cy': 0.15}),  # zanshin
]
GRAB, SLIDE, CLEAR = int(0.45 * FPS), int(1.05 * FPS), int(1.30 * FPS)


def full(name, over):
    p = dict(MB.BASE)
    p.update(POSES.get(name) or MB.POSES.get(name, {}))
    p.update({k: v for k, v in over.items() if k in MB.BASE})
    return p


def pose_at(t):
    for (t0, n0, o0), (t1, n1, o1) in zip(KEYS, KEYS[1:]):
        if t <= t1:
            u = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            u = u * u * (3 - 2 * u)
            a, b = full(n0, o0), full(n1, o1)
            return {k: a[k] + (b[k] - a[k]) * u for k in a}
    return full(KEYS[-1][1], KEYS[-1][2])


F = int(KEYS[-1][0] * FPS) + 1
draw = SD.Draw(rig, sword, saya, BLADE, grab=GRAB, slide=SLIDE, clear=CLEAR, R=K['R'])
_open = {s_: [o for o in ch['objects'] if o.get('pc_recipe') == 'hand_folded' and o.get('pc_socket') == 'hand.' + s_]
         for s_ in ('R', 'L')}
_skin = next((o.data.materials[0] for o in _open['R'] if o.data.materials), None)
if '--open-hands' not in argv:
    draw.add_hands(_open['R'], _open['L'], _skin, _skin)
print('[draw] open hand objects:', {k: [o.name for o in v] for k, v in _open.items()})
# ---------------------------------------------------------------- camera (before the bake: the probe uses it)
cd = bpy.data.cameras.new('cam')
cam = bpy.data.objects.new('cam', cd)
sc.collection.objects.link(cam)
sc.camera = cam
cd.lens = float(arg('lens', 38))
cam.location = Vector([float(v) for v in arg('cam', '1.9,-2.6,1.25').split(',')])
target = Vector([float(v) for v in arg('look', '-0.25,-0.4,1.0').split(',')])
cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()

def saya_visible(f, n=24):
    """Share of points along the scabbard that the camera sees directly (first ray hit is the saya)."""
    dg = bpy.context.evaluated_depsgraph_get()      # the CURRENT state: called during the bake, no frame_set
    L = BLADE + 0.05
    seen = 0
    for i in range(n):
        p = saya.matrix_world @ Vector((L * (i + 0.5) / n, 0, 0.0))
        d = p - cam.matrix_world.translation
        hit, loc, nor, idx, ob, mat = sc.ray_cast(dg, cam.matrix_world.translation, d.normalized(), distance=d.length + 0.05)
        seen += bool(hit and ob and ob.parent is saya)
    return seen / n


import body_capsules as BC                           # noqa: E402  the character's boundary
caps = BC.BodyCapsules(rig)
import cloth_springs as CS                           # noqa: E402  sleeves and hakama with weight
_tam = {'rSleeve': [o for o in ch['objects'] if o.get('pc_recipe') == 'tamoto_wide' and o.get('pc_socket', '').endswith('.R')],
        'lSleeve': [o for o in ch['objects'] if o.get('pc_recipe') == 'tamoto_wide' and o.get('pc_socket', '').endswith('.L')]}
springs = None if '--stiff-cloth' in argv else CS.ClothSprings(
    rig, BC.BodyCapsules(rig), fps=FPS, panels=None if '--no-panel-check' in argv else _tam,
    body=BC.BodyCapsules(rig, shrink=0.035))
if '--no-keep-out' not in argv:
    draw.caps = BC.BodyCapsules(rig)
MEASURED = {}
body = BC.BodyCapsules(rig, shrink=0.035)            # the PERSON under the clothes
elbow_track, frame_out, grip_roll = {}, [], []
sleeve_objs = [o for o in ch['objects'] if o.get('pc_recipe') == 'tamoto_wide']
pen = []                                             # (frame, what, depth cm, capsule)
log = []
for f in range(1, F + 1):
    sc.frame_set(f)
    log.append(draw.step(f, pose_at((f - 1) / FPS)))
    if springs:
        springs.step()
    if arg('measure') and f in [int(v) for v in arg('measure').split(',')]:
        bpy.context.view_layer.update()
        for _opens, _grip in draw.hands.values():
            _grip.hide_viewport = True
        MEASURED[f] = saya_visible(f)
        for _opens, _grip in draw.hands.values():
            _grip.hide_viewport = False
    if '--debug' in argv and f % 2 == 0 and f >= 28:
        r = lambda v: [round(x, 2) for x in v]
        print('[dbg]', f, log[-1], 'guard', r(sword.matrix_world.translation), 'tip', r(sword.matrix_world @ Vector((BLADE, 0, 0))),
              'hand', r(rig.J['rH'].matrix_world.translation), 'saya', r(saya.matrix_world.translation))
    for e in rig.J.values():
        e.keyframe_insert('location', frame=f)
        e.keyframe_insert('rotation_euler', frame=f)
    if '--collide' in argv:
        bpy.context.view_layer.update()
        caps.update()
        body.update()
        rig.sync_bones()                                   # the skinned paper must be where the bones are
        # 1) the blade against the PERSON (body capsules) and against the GARMENT (capsules with the clothes)
        if log[-1] in ('drawing', 'drawn'):
            for i in range(1, 19):
                pt = sword.matrix_world @ Vector((BLADE * i / 18, 0, 0))
                for key, cc in (('blade/body', body), ('blade/garment', caps)):
                    d, who = cc.depth(pt, skip=('forearm.R', 'forearm.L'))
                    if d > 0:
                        pen.append((f, key, round(d * 100, 1), who))
        for i in range(2, 18):
            pt = saya.matrix_world @ Vector(((BLADE + 0.035) * i / 18, 0, 0))
            d, who = body.depth(pt, skip=('forearm.L', 'belly', 'hips'))     # the scabbard is tied IN the obi
            if d > 0:
                pen.append((f, 'saya/body', round(d * 100, 1), who))
        # 2) the arms against the PERSON
        for sd, ar in (('r', 'R'), ('l', 'L')):
            chain = [rig.J[sd + j].matrix_world.translation for j in ('S', 'E', 'H')]
            elbow_track.setdefault(ar, []).append(chain[1].copy())
            for (a_, b_), rad in zip(zip(chain, chain[1:]), (0.035, 0.03)):
                for t in (0.5, 0.75, 1.0):
                    d, who = body.depth(a_.lerp(b_, t), skip=('upperarm.' + ar, 'forearm.' + ar))
                    if d + rad > 0:
                        pen.append((f, 'arm.' + ar + '/body', round((d + rad) * 100, 1), who))
        # 3) the sleeve PAPER itself (every vertex of the deformed tamoto) against the person: a cloth bone
        #    can clear a capsule while a corner of the panel still cuts into the body
        dg = bpy.context.evaluated_depsgraph_get()
        for ob in sleeve_objs:
            ar = 'R' if ob.get('pc_socket', '').endswith('.R') else 'L'
            me = ob.evaluated_get(dg).to_mesh()
            mw = ob.matrix_world
            worst = (0.0, '')
            for v in me.vertices:
                d, who = body.depth(mw @ v.co, skip=('upperarm.' + ar, 'forearm.' + ar))
                if d > worst[0]:
                    worst = (d, who)
            ob.evaluated_get(dg).to_mesh_clear()
            if worst[0] > 0:
                pen.append((f, 'sleeve-paper.' + ar + '/body', round(worst[0] * 100, 1), worst[1]))
        # 4) framing: is the WHOLE blade in the picture?
        from bpy_extras.object_utils import world_to_camera_view as _w2c
        if log[-1] in ('drawing', 'drawn'):
            outside = sum(1 for i in range(0, 19) if not (0.0 <= _w2c(sc, cam, sword.matrix_world @ Vector((BLADE * i / 18, 0, 0))).x <= 1.0
                                                          and 0.0 <= _w2c(sc, cam, sword.matrix_world @ Vector((BLADE * i / 18, 0, 0))).y <= 1.0))
            if outside:
                frame_out.append((f, outside))
        # 5) grip slide: how far the hand turns ABOUT the handle from one frame to the next
        if log[-1] in ('drawing', 'drawn'):
            hm = (rig.J['rH'].matrix_world @ draw.H).to_3x3()
            sm = sword.matrix_world.to_3x3()
            ax = sm.col[0].normalized()
            hy = (hm.col[1] - ax * hm.col[1].dot(ax)).normalized()
            sy = (sm.col[1] - ax * sm.col[1].dot(ax)).normalized()
            import math as _m
            roll = _m.degrees(_m.atan2(ax.dot(sy.cross(hy)), sy.dot(hy)))
            grip_roll.append((f, roll))
if '--collide' in argv:
    by = {}
    for f_, what, d, who in pen:
        by.setdefault(what, []).append((f_, d, who))
    for what in ('blade/body', 'blade/garment', 'saya/body', 'arm.R/body', 'arm.L/body',
                 'sleeve-paper.R/body', 'sleeve-paper.L/body'):
        rows = by.get(what, [])
        if rows:
            fr = sorted({r[0] for r in rows})
            mx = max(rows, key=lambda r: r[1])
            print('[collide] %-20s on %2d of %d frames, deepest %.1f cm (frame %d, %s)' % (what, len(fr), F, mx[1], mx[0], mx[2]))
        else:
            print('[collide] %-20s never' % what)
    for ar, pts in elbow_track.items():                    # elbow pop: the biggest frame-to-frame acceleration
        acc = [((pts[i + 1] - pts[i]) - (pts[i] - pts[i - 1])).length * 100 for i in range(1, len(pts) - 1)]
        i = max(range(len(acc)), key=lambda k: acc[k])
        print('[motion] elbow.%s: biggest jolt %.1f cm/frame^2 at frame %d (median %.1f); frames over 3: %s' % (
            ar, acc[i], i + 2, sorted(acc)[len(acc) // 2], [(k + 2, round(v, 1)) for k, v in enumerate(acc) if v > 3]))
    print('[frame] whole blade in the picture on %d of %d drawn frames%s' % (
        len([1 for k in log if k in ('drawing', 'drawn')]) - len(frame_out), len([1 for k in log if k in ('drawing', 'drawn')]),
        (' (out: ' + ', '.join('f%d' % a for a, _ in frame_out[:12]) + ')') if frame_out else ''))
    if grip_roll:
        steps = [abs((grip_roll[i][1] - grip_roll[i - 1][1] + 180) % 360 - 180) for i in range(1, len(grip_roll))]
        k = max(range(len(steps)), key=lambda j: steps[j])
        print('[grip] the hand turns about the handle by at most %.1f deg in one frame (frame %d); total range %.0f deg'
              % (steps[k], grip_roll[k + 1][0], max(r for _, r in grip_roll) - min(r for _, r in grip_roll)))
if springs:
    for j, rows in springs.depths.items():
        b = [r[0] for r in rows]
        a = [r[1] for r in rows]
        lag = [r[0] for r in springs.log[j]]
        print('[cloth] %-8s inside the body: before %d frames (deepest %.1f cm) -> after %d frames (deepest %.1f cm);'
              ' trails its old aim: median %.0f, max %.0f deg' % (j, sum(x > 0.005 for x in b), 100 * max(b), sum(x > 0.005 for x in a),
                                                         100 * max(a), sorted(lag)[len(lag) // 2], max(lag)))
print('[draw] phases:', ' '.join(f'{i+1}:{s[:2]}' for i, s in enumerate(log)), '| IK residual m:', draw.residual, '| left:', draw.residual_l)

for ob in [sword, saya] + list(rig.J.values()):
    ad = ob.animation_data
    if ad and ad.action:
        for fc in ad.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'

# armature follows the empties every frame (same as the films)
def _sync(scene, *_):
    rig.sync_bones()


bpy.app.handlers.frame_change_post.append(_sync)

# ---------------------------------------------------------------- light, render
MB.studio(sc, 'cinematic')
# real metal needs something to reflect: the free Poly Haven dusk sky, low, under the studio lights
_hdr = os.path.join(REPO, 'assets', 'polyhaven', 'qwantani_dusk_2_puresky', 'qwantani_dusk_2_puresky_2k.hdr')
if os.path.exists(_hdr) and sc.world and sc.world.use_nodes:
    _nt = sc.world.node_tree
    _bg = next((n for n in _nt.nodes if n.type == 'BACKGROUND'), None)
    if _bg:
        _env = _nt.nodes.new('ShaderNodeTexEnvironment')
        _env.image = bpy.data.images.load(_hdr)
        _nt.links.new(_env.outputs['Color'], _bg.inputs['Color'])
        _bg.inputs['Strength'].default_value = 0.35
# a paper floor and a dim warm backdrop, so the blade and the scabbard read against something
bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 0, 0))
floor = bpy.context.active_object
floor.data.materials.append(SW._flat_mat('floor', (0.32, 0.27, 0.21, 1), 0.9))
bpy.ops.mesh.primitive_plane_add(size=12, location=(-1.5, 2.2, 3), rotation=(math.radians(90), 0, math.radians(-25)))
bpy.context.active_object.data.materials.append(SW._flat_mat('wall', (0.22, 0.2, 0.18, 1), 0.95))
setup_render(sc, arg('engine', 'eevee'), quality=arg('quality', 'draft'))
w, h = [int(v) for v in arg('res', '360x640').split('x')]
sc.render.resolution_x, sc.render.resolution_y = w, h
sc.frame_start, sc.frame_end = 1, F
os.makedirs(OUT, exist_ok=True)
sc.render.filepath = os.path.join(OUT, 'f')
sc.render.image_settings.file_format = 'PNG'
if arg('measure'):
    for f_, v_ in sorted(MEASURED.items()):
        print('[measure] frame %d: scabbard visible %.0f%%' % (f_, 100 * v_))
if arg('stills'):
    for f in [int(v) for v in arg('stills').split(',')]:
        sc.frame_set(f)
        sc.render.filepath = os.path.join(OUT, 'still_%03d.png' % f)
        bpy.ops.render.render(write_still=True)
elif '--no-render' not in argv:
    bpy.ops.render.render(animation=True)
print('[draw] done', F, 'frames ->', OUT)
