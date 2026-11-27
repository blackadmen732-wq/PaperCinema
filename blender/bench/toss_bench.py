"""TOSS BENCHMARK (skill: .claude/skills/paper-cinema-skeleton-animation): a 54-frame, 24 fps ball toss on the
production rig, isolated from the episodes. Original shot blocking from the skill's table; not extracted from any
reference footage. The ball is SCRIPTED (hand-owned, then ballistic, then hand-owned): its framing numbers say
nothing about physical contact or footage tracking.

  B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
  $B -b -P blender/bench/toss_bench.py -- --solve                     # the bake + output/bench-toss/frames.csv
  $B -b -P blender/bench/toss_bench.py -- --variant bare --cam locked --out output/bench-toss/bare-locked/
  $B -b -P blender/bench/toss_bench.py -- --variant kojiro --cam tracking --frames 18-18 ...

One bake (output/bench-toss/bake.json): per frame the 25 joint values, the ball (owner, position, rotation), and
both cameras. Every variant (bare rig = the body-capsule mannequin, kojiro / musashi outfits) and both cameras read
it, so they show the SAME motion.
"""
import csv
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
BL = os.path.dirname(HERE)
REPO = os.path.dirname(BL)
for p in ('character', 'world', 'props', ''):
    sys.path.insert(0, os.path.join(BL, p))
import modular_builder as MB                 # noqa: E402
import body_capsules as BC                   # noqa: E402
import sword_draw as SD                      # noqa: E402

ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(k, d=None):
    return ARGV[ARGV.index('--' + k) + 1] if '--' + k in ARGV else d


FPS, N = 24, 54
RELEASE, CATCH = 18, 34
G = 9.81
BALL_R = 0.06
OUT = os.path.join(REPO, 'output', 'bench-toss')
BAKE = os.path.join(OUT, 'bake.json')
os.makedirs(OUT, exist_ok=True)

# ------------------------------------------------------------------ the body: keyed poses (skill table)
# Blender frame -> overrides of the rig's pose channels. crouch = knees + hips together, tx = torso lean,
# cx = chest, hx = head (negative looks up), weight = hips forward.
BODY = [
    (1, {'crouch': 0.05, 'tx': 0.04, 'hx': 0.10}),                            # hold, grounded
    (6, {'crouch': 0.05, 'tx': 0.04, 'hx': 0.10}),
    (12, {'crouch': 0.24, 'tx': 0.18, 'weight': 0.10, 'hx': 0.05}),          # anticipation: lower, weight in
    (17, {'crouch': 0.02, 'tx': -0.06, 'cx': -0.06, 'hx': -0.25}),           # drive up: legs first, chest follows
    (18, {'crouch': 0.00, 'tx': -0.08, 'cx': -0.10, 'hx': -0.35}),           # release
    (26, {'crouch': 0.02, 'tx': -0.10, 'cx': -0.14, 'hx': -0.62}),           # eyes and chest follow to the apex
    (33, {'crouch': 0.06, 'tx': -0.02, 'cx': -0.06, 'hx': -0.30}),           # into the catch
    (34, {'crouch': 0.07, 'tx': 0.00, 'cx': -0.04, 'hx': -0.25}),            # catch
    (41, {'crouch': 0.22, 'tx': 0.14, 'cx': 0.06, 'hx': 0.02}),              # absorb through torso and knees
    (47, {'crouch': 0.08, 'tx': 0.06, 'cx': 0.02, 'hx': 0.08}),              # settle (slight overshoot back up)
    (54, {'crouch': 0.10, 'tx': 0.07, 'cx': 0.02, 'hx': 0.08}),              # held finish
]


def body_pose(f, stepped=False):
    p = dict(MB.BASE)
    p.update(MB.POSES.get('standing', {}))
    keys = BODY
    for (f0, o0), (f1, o1) in zip(keys, keys[1:]):
        if f <= f1:
            u = 0.0 if stepped else (f - f0) / (f1 - f0)
            u = u * u * (3 - 2 * u)
            for k in set(o0) | set(o1):
                a, b = o0.get(k, p.get(k, 0.0)), o1.get(k, p.get(k, 0.0))
                p[k] = a + (b - a) * u
            return p
    p.update(keys[-1][1])
    return p


# ------------------------------------------------------------------ the right hand's grip anchor path (world, m)
def hermite(p0, v0, p1, v1, u, T):
    h00, h10, h01, h11 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u, -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
    return p0 * h00 + v0 * (h10 * T) + p1 * h01 + v1 * (h11 * T)


HOLD = Vector((-0.20, -0.32, 1.05))          # in front of the right chest (character faces -y; right = -x)
DIP = Vector((-0.21, -0.28, 0.86))
REL = Vector((-0.14, -0.40, 1.50))
V_REL = Vector((0.06, -0.15, 2.97))          # chosen so the ball comes back to ~1.30 m at frame 34 (g = 9.81)
FOLLOW = Vector((-0.24, -0.30, 1.32))        # the arm, independent, while the ball flies


def anchor_target(f, catch_p=None, catch_v=None):
    """Where the right hand's grip anchor should be on frame f (the IK target)."""
    if f <= 6:
        return HOLD.copy()
    if f <= 12:
        u = (f - 6) / 6
        return HOLD.lerp(DIP, u * u * (3 - 2 * u))
    if f <= RELEASE:
        u = (f - 12) / (RELEASE - 12)
        return hermite(DIP, Vector((0, 0, 0)), REL, V_REL, u, (RELEASE - 12) / FPS)
    if f <= 26:
        u = (f - RELEASE) / (26 - RELEASE)
        return hermite(REL, V_REL * 0.35, FOLLOW, Vector((0, 0, 0)), u, (26 - RELEASE) / FPS)
    if f <= CATCH:
        u = (f - 26) / (CATCH - 26)                   # to the PREDICTED catch point, arriving with the ball's speed
        return hermite(FOLLOW, Vector((0, 0, 0)), catch_p, catch_v, u, (CATCH - 26) / FPS)   # meets it at its speed
    if f <= 41:
        u = (f - CATCH) / (41 - CATCH)                # absorb: starts with the ball's velocity, comes to rest lower
        low = catch_p + Vector((0.0, 0.03, -0.40))
        return hermite(catch_p, catch_v, low, Vector((0, 0, 0)), u, (41 - CATCH) / FPS)
    low = catch_p + Vector((0.0, 0.03, -0.40))
    fin = catch_p + Vector((0.0, 0.02, -0.20))
    u = min(1.0, (f - 41) / 6)
    return low.lerp(fin, u * u * (3 - 2 * u))


# ------------------------------------------------------------------ build the cast
def build(variant):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = FPS
    rid = 'musashi' if variant == 'musashi' else 'kojiro'
    ch = MB.build(MB.load_recipe(os.path.join(REPO, 'library', 'character-recipes', rid + '.json')), name='PC_toss')
    for o in [o for o in ch['objects'] if o.get('pc_recipe') == 'katana_sheathed']:
        ch['objects'].remove(o)
        bpy.data.objects.remove(o, do_unlink=True)
    me = bpy.data.meshes.new('BALL')
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=BALL_R)
    for f_ in bm.faces:                              # a folded paper ball, two-tone so its turn reads
        f_.material_index = 0 if f_.calc_center_median().x > 0 else 1
    bm.to_mesh(me)
    bm.free()
    for p_ in me.polygons:
        p_.use_smooth = False
    ball = bpy.data.objects.new('BALL', me)
    ball.rotation_mode = 'QUATERNION'
    sc.collection.objects.link(ball)
    import swords as SW
    me.materials.append(SW._flat_mat('ball_paper', (0.90, 0.30, 0.18, 1), 0.7))
    me.materials.append(SW._flat_mat('ball_paper2', (0.92, 0.86, 0.72, 1), 0.7))
    return sc, ch, ball


# ------------------------------------------------------------------ solve once
def solve():
    sc, ch, ball = build('kojiro')
    rig = ch['rig']
    H = SD.hand_holder()
    # pass 1: the release velocity comes from the ACTUAL hand path (after IK), so solve frames 1-18 first
    rec = {'J': [], 'ball': [], 'owner': [], 'anchor': [], 'grip_rel': []}
    anchors = {}

    def pose_frame(f, target):
        p = body_pose(f)
        rig.pose(p)
        bpy.context.view_layer.update()
        tgt = Matrix.Translation(target) @ (rig.J['rH'].matrix_world @ H).to_3x3().to_4x4()
        solved, res = SD.ik_arm(rig, p, tgt, H, side='r', wr=0.0)
        rig.pose(solved)
        bpy.context.view_layer.update()
        return solved, res

    # pre-pass to get the release state
    for f in range(1, RELEASE + 1):
        sc.frame_set(f)
        pose_frame(f, anchor_target(f))
        anchors[f] = (rig.J['rH'].matrix_world @ H).translation.copy()
    p18 = anchors[RELEASE]
    v18 = (anchors[RELEASE] - anchors[RELEASE - 1]) * FPS          # launch velocity from the final hand path

    def ball_at(f):
        t = (f - RELEASE) / FPS
        return p18 + v18 * t + Vector((0, 0, -0.5 * G * t * t))

    catch_p = ball_at(CATCH)
    catch_v = (ball_at(CATCH) - ball_at(CATCH - 1)) * FPS
    caps = BC.BodyCapsules(rig)
    rows = []
    foot0 = {}
    prev_rot = None
    for f in range(1, N + 1):
        sc.frame_set(f)
        solved, res = pose_frame(f, anchor_target(f, catch_p, catch_v))
        grip = rig.J['rH'].matrix_world @ H
        owner = 'hand' if (f <= RELEASE - 1 or f >= CATCH) else ('hand->world' if f == RELEASE else 'world')
        if f < RELEASE:
            bpos, brot = grip.translation.copy(), grip.to_quaternion()
        elif f == RELEASE:
            bpos, brot = grip.translation.copy(), grip.to_quaternion()    # last hand-owned frame = launch point
            rel_rot = brot
        elif f < CATCH:
            bpos, brot = ball_at(f), rel_rot
        else:
            # caught: the ball keeps the turn it had in flight, carried by the hand from now on (switching straight to
            # the hand's own frame snapped it 72 deg on the catch frame)
            if f == CATCH:
                catch_off = grip.to_quaternion().inverted() @ rel_rot
            bpos, brot = grip.translation.copy(), grip.to_quaternion() @ catch_off
        # errors when held: the ball vs the grip anchor (position, orientation). In flight the ball keeps the release
        # orientation; on the catch frame it is the turn the ball snaps by when the hand takes it.
        flight_pos = ball_at(f) if RELEASE <= f <= CATCH else None
        gpos_err = (grip.translation - (flight_pos if f == CATCH else bpos)).length * 100 if owner != 'world' else ''
        gang_err = ''
        if f == CATCH:
            gang_err = math.degrees(rel_rot.rotation_difference(brot).angle)   # the ball's turn across the hand-over
        elif owner == 'hand':
            gang_err = 0.0
        for side in ('r', 'l'):
            fp = rig.J[side + 'foot'].matrix_world.translation
            foot0.setdefault(side, fp.copy())
        drift = {s: (Vector((rig.J[s + 'foot'].matrix_world.translation.x - foot0[s].x,
                             rig.J[s + 'foot'].matrix_world.translation.y - foot0[s].y, 0))).length * 100 for s in 'rl'}
        caps.update()
        ball_in = caps.depth(bpos, skip=('forearm.R',) if owner != 'world' else ())[0] + BALL_R
        hand_in = caps.depth(rig.J['rH'].matrix_world.translation, skip=('forearm.R', 'upperarm.R'))[0] + 0.03
        rec['J'].append({n: [*e.location, *e.rotation_euler] for n, e in rig.J.items()})
        rec['ball'].append([*bpos, *brot])
        rec['owner'].append(owner)
        rows.append({'frame': f, 'owner': owner, 'ik_residual_cm': round(res * 100, 2),
                     'grip_pos_err_cm': round(gpos_err, 2) if gpos_err != '' else '',
                     'grip_angle_err_deg': round(gang_err, 1) if gang_err != '' else '',
                     'foot_drift_R_cm': round(drift['r'], 2), 'foot_drift_L_cm': round(drift['l'], 2),
                     'ball_x': round(bpos.x, 4), 'ball_y': round(bpos.y, 4), 'ball_z': round(bpos.z, 4),
                     'collide_ball_body': int(ball_in > 0.005), 'collide_hand_body': int(hand_in > 0.005)})
    # cameras: LOCKED (fixed, frames body + apex) and TRACKING (aims at an eased point between ball and chest)
    chest = [Vector(r['J']['upper'][:3]) for r in [{'J': j} for j in rec['J']]]   # local; recomputed below
    cams = {'locked': [], 'tracking': []}
    cam_pos = Vector((2.35, -3.6, 1.35))
    look_fixed = Vector((-0.05, -0.20, 1.20))
    aim = None
    for f in range(1, N + 1):
        sc.frame_set(f)
        for n, e in rig.J.items():
            v = rec['J'][f - 1][n]
            e.location, e.rotation_euler = v[:3], v[3:6]
        bpy.context.view_layer.update()
        c = rig.J['upper'].matrix_world.translation
        b = Vector(rec['ball'][f - 1][:3])
        want = c.lerp(b, 0.5)
        aim = want if aim is None else aim.lerp(want, 0.22)            # eased (about 4 frames to settle)
        cams['locked'].append([*cam_pos, *(look_fixed - cam_pos).to_track_quat('-Z', 'Y')])
        cams['tracking'].append([*cam_pos, *(aim - cam_pos).to_track_quat('-Z', 'Y')])
    bake = {'fps': FPS, 'n': N, 'release': RELEASE, 'catch': CATCH, 'J': rec['J'], 'ball': rec['ball'],
            'owner': rec['owner'], 'cams': cams, 'launch_velocity': [*v18], 'launch_point': [*p18],
            'catch_point': [*catch_p], 'lens': 32}
    tmp = BAKE + '.tmp'
    json.dump(bake, open(tmp, 'w'))
    os.replace(tmp, BAKE)
    # continuity at release and catch (positions from the bake)
    P = [Vector(x[:3]) for x in rec['ball']]
    vin = (P[RELEASE - 1] - P[RELEASE - 2]) * FPS
    vout = (P[RELEASE] - P[RELEASE - 1]) * FPS
    cin = (P[CATCH - 1] - P[CATCH - 2]) * FPS
    cout = (P[CATCH] - P[CATCH - 1]) * FPS
    summary = {
        'release_position_jump_cm': round((P[RELEASE - 1] - anchors[RELEASE]).length * 100, 3),
        'release_velocity_in_mps': [round(v, 2) for v in vin], 'release_velocity_out_mps': [round(v, 2) for v in vout],
        'release_velocity_change_mps': round((vout - vin).length, 3),
        'catch_position_err_cm': rows[CATCH - 1]['grip_pos_err_cm'], 'catch_angle_snap_deg': rows[CATCH - 1]['grip_angle_err_deg'],
        'catch_velocity_in_mps': [round(v, 2) for v in cin], 'catch_velocity_out_mps': [round(v, 2) for v in cout],
        'catch_velocity_change_mps': round((cout - cin).length, 3),
        'apex_frame': 1 + max(range(N), key=lambda i: P[i].z if RELEASE <= i + 1 <= CATCH else -9),
        'apex_height_m': round(max(P[i].z for i in range(RELEASE - 1, CATCH)), 3),
        'max_ik_residual_cm': max(r['ik_residual_cm'] for r in rows),
        'max_foot_drift_cm': max(max(r['foot_drift_R_cm'], r['foot_drift_L_cm']) for r in rows)}
    json.dump({'rows': rows, 'summary': summary}, open(os.path.join(OUT, 'solve.json'), 'w'), indent=1)
    print('[toss] bake ->', BAKE)
    for k, v in summary.items():
        print('[toss] %s: %s' % (k, v))


# ------------------------------------------------------------------ render one variant from the bake
def render(variant, cam_kind, out, frames):
    bake = json.load(open(BAKE))
    sc, ch, ball = build(variant)
    rig = ch['rig']
    import production_bake as PB
    import swords as SW
    MB.studio(sc, 'neutral')
    fl = bpy.data.meshes.new('floor')
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=6)
    bm.to_mesh(fl)
    bm.free()
    flo = bpy.data.objects.new('floor', fl)
    fl.materials.append(SW._flat_mat('floor_paper', (0.36, 0.31, 0.25, 1), 0.9))
    sc.collection.objects.link(flo)
    cd = bpy.data.cameras.new('cam')
    cd.lens = bake['lens']
    cam = bpy.data.objects.new('cam', cd)
    cam.rotation_mode = 'QUATERNION'
    sc.collection.objects.link(cam)
    sc.camera = cam
    segs = []
    body = BC.BodyCapsules(rig, shrink=0.035)
    for f in range(1, bake['n'] + 1):
        for n, e in rig.J.items():
            v = bake['J'][f - 1][n]
            e.location, e.rotation_euler = v[:3], v[3:6]
            e.keyframe_insert('location', frame=f)
            e.keyframe_insert('rotation_euler', frame=f)
        bpy.context.view_layer.update()
        rig.sync_bones()
        rig.key_bones(f)
        body.update()
        segs.append([(n_, list(p_), list(q_), r_) for n_, p_, q_, r_ in body.segs] +
                    [('hand.r', list(rig.J['rH'].matrix_world.translation),
                      list((rig.J['rH'].matrix_world @ SD.hand_holder()).translation), 0.035)])
        b = bake['ball'][f - 1]
        ball.location, ball.rotation_quaternion = b[:3], b[3:7]
        ball.keyframe_insert('location', frame=f)
        ball.keyframe_insert('rotation_quaternion', frame=f)
        c = bake['cams'][cam_kind][f - 1]
        cam.location, cam.rotation_quaternion = c[:3], c[3:7]
        cam.keyframe_insert('location', frame=f)
        cam.keyframe_insert('rotation_quaternion', frame=f)
    for ob in list(rig.J.values()) + [rig.rig, ball, cam]:
        ad = ob.animation_data
        if ad and ad.action:
            for fc in ad.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
    if variant == 'bare':
        act = PB.Actor('toss', rig, ch['objects'])
        PB.build_mannequin({'actors': {'toss': {'segs': segs}}}, [act], None, sc, SW._flat_mat)
    # checks on the RENDER process: deform bones follow the controls; the ball's screen position, edge margin and
    # 9 sampled rays seen from this camera
    from bpy_extras.object_utils import world_to_camera_view as w2c
    rows = []
    worst_bone = 0.0
    for f in range(1, bake['n'] + 1):
        sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        for bname in ('rH', 'lfoot', 'head', 'upper'):
            if bname in rig.rig.pose.bones:
                pb = rig.rig.pose.bones[bname]
                worst_bone = max(worst_bone, ((rig.rig.matrix_world @ pb.matrix).translation -
                                              (rig.rig.matrix_world @ rig.rest_bone[bname]).translation -
                                              (rig.J[bname].matrix_world.translation - Vector(__import__('part_registry').REST[bname]))).length)
        bc = ball.matrix_world.translation
        s = w2c(sc, cam, bc)
        cp = cam.matrix_world.translation
        right = cam.matrix_world.to_3x3().col[0]
        up = cam.matrix_world.to_3x3().col[1]
        rr = (w2c(sc, cam, bc + right * BALL_R).x - s.x)
        margin = min(s.x - rr, 1 - s.x - rr, s.y - rr * 9 / 16, 1 - s.y - rr * 9 / 16)
        pts = [bc] + [bc + (right * math.cos(a) + up * math.sin(a)) * BALL_R * 0.85 for a in [k * math.pi / 4 for k in range(8)]]
        seen = 0
        for pt in pts:
            d = pt - cp
            hit, loc, nor, idx, ob, mat = sc.ray_cast(dg, cp, d.normalized(), distance=d.length + BALL_R)
            seen += bool(hit and ob is ball)
        rows.append({'frame': f, 'screen_x': round(s.x, 4), 'screen_y': round(s.y, 4), 'edge_margin': round(margin, 4),
                     'rays_visible_of_9': seen})
    json.dump({'cam': cam_kind, 'variant': variant, 'rows': rows, 'deform_follows_controls_max_m': worst_bone},
              open(os.path.join(OUT, 'screen-%s-%s.json' % (variant, cam_kind)), 'w'), indent=1)
    print('[toss] %s/%s: deform bones vs controls max %.5f m; rays visible min %d of 9; edge margin min %.3f' % (
        variant, cam_kind, worst_bone, min(r['rays_visible_of_9'] for r in rows), min(r['edge_margin'] for r in rows)))
    if out:
        from render_engine import setup_render
        setup_render(sc, 'cycles', quality='draft')
        sc.cycles.samples = int(arg('samples', 10))
        w, h = [int(v) for v in arg('res', '360x640').split('x')]
        sc.render.resolution_x, sc.render.resolution_y = w, h
        a, b = frames
        sc.frame_start, sc.frame_end = a, b
        os.makedirs(out, exist_ok=True)
        sc.render.filepath = os.path.join(out, 'f')
        bpy.ops.render.render(animation=True)


if '--solve' in ARGV:
    solve()
else:
    fr = [int(x) for x in arg('frames', '1-%d' % N).split('-')]
    render(arg('variant', 'bare'), arg('cam', 'locked'), arg('out'), fr)
