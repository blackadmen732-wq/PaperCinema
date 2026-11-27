"""The sword draw (nukitsuke): the blade really comes OUT of the scabbard.

Why this exists (Mark, 26 Nov: "when they remove it, it just doesn't feel real"). Before this, the hip
sword was one fixed part glued to the torso (part_registry.katana_sheathed: saya + handle + guard) and
the drawn katana was a second object keyed to the hand from the first frame. So a draw showed two swords,
or a blade that appeared in the hand while a full hilt stayed on the hip. Nothing ever slid out of
anything.

Now there is ONE sword and ONE scabbard per swordsman, and three phases:

  sheathed   the sword sits in the saya at the left hip (edge up), the saya rides the torso.
  drawing    the right hand holds the handle (the engine's own grip, figure.js holdInHand). The saya
             turns about its obi tie and slides a little so its mouth stays ON the blade line: the
             blade slides out of the mouth instead of passing through the cloth. That is the left-hand
             pull a real iaido draw makes (saya-biki). The moment the tip clears the mouth (the
             "saya-banare"), the saya eases back to the hip.
  drawn      the sword follows the hand; the saya hangs empty at the hip.

The grab is blended over a few frames so the sword never pops from the hip into the hand.
Units: metres, Blender world (Z up). The sword frame is the timeline's: guard at x = 0, blade +x,
edge -y, handle -x. The saya is built in the same frame: mouth at x = 0, tip at +x.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

# figure.js holdInHand, converted from three.js to Blender with the rig's own T(x, y, z) = (x, -z, y)
_A = math.sqrt(0.5)
_C = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))          # three -> Blender (a proper rotation)


def hand_holder(grip_x=-0.06):
    """The sword's frame in the right hand's frame (Blender axes), exactly as the engine holds it."""
    x3, y3 = Vector((0, -_A, _A)), Vector((0, _A, _A))
    z3 = x3.cross(y3)
    R3 = Matrix((x3, y3, z3)).transposed()                 # columns = the holder's axes (three)
    pos3 = x3 * (-grip_x) + Vector((0, -0.01, 0))
    R = _C @ R3 @ _C.transposed()
    M = R.to_4x4()
    M.translation = _C @ pos3
    return M


def frame(origin, x_dir, up=Vector((0, 0, 1))):
    """A sword-style frame: +x along x_dir, the edge (-y) toward `up` (edge up, as worn in the obi)."""
    x = x_dir.normalized()
    u = up - x * up.dot(x)
    if u.length < 1e-6:
        u = Vector((0, 1, 0)) - x * x.y
    y = -u.normalized()
    z = x.cross(y)
    M = Matrix((x, y, z)).transposed().to_4x4()
    M.translation = origin
    return M


def arc(s, R):
    """The sword's frame relative to its scabbard after sliding s metres out of the mouth. Blade and scabbard
    share one circle of radius R (centre at +y, the back), so the slide is a turn about that centre: every
    point of the blade stays on the scabbard's curve. R = 0: a straight slide."""
    if not R:
        return Matrix.Translation((-s, 0, 0))
    C = Vector((0, R, 0))
    return Matrix.Translation(C) @ Matrix.Rotation(-s / R, 4, 'Z') @ Matrix.Translation(-C)


def blend(A, B, t):
    """Blend two rigid frames (t = 0 -> A, 1 -> B)."""
    t = max(0.0, min(1.0, t))
    t = t * t * (3 - 2 * t)
    la, ra, _ = A.decompose()
    lb, rb, _ = B.decompose()
    q = ra.slerp(rb, t)
    M = q.to_matrix().to_4x4()
    M.translation = la.lerp(lb, t)
    return M


def build_saya(name, coll, length=0.95, mat_body=None, mat_mouth=None):
    """A folded-paper scabbard in the sword frame: mouth at x = 0, body along +x, a horn collar (koiguchi)
    at the mouth and a cap (kojiri) at the tip. A hexagonal section, slightly flattened like the blade."""
    me = bpy.data.meshes.new(name + '_m')
    bm = bmesh.new()
    rings = []
    for x, s in ((0.0, 1.18), (0.035, 1.18), (0.036, 1.0), (length - 0.05, 0.92), (length - 0.049, 1.12),
                 (length, 1.0)):
        ring = []
        for k in range(6):
            a = math.pi / 3 * k + math.pi / 6
            ring.append(bm.verts.new((x, 0.016 * s * math.cos(a), 0.024 * s * math.sin(a))))
        rings.append(ring)
    faces = []
    for i in range(len(rings) - 1):
        for k in range(6):
            a, b = rings[i][k], rings[i][(k + 1) % 6]
            c, d = rings[i + 1][(k + 1) % 6], rings[i + 1][k]
            f = bm.faces.new((a, b, c, d))
            f.material_index = 1 if i == 0 or i == len(rings) - 2 else 0
            faces.append(f)
    cap = bm.faces.new(list(reversed(rings[-1])))
    cap.material_index = 1
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = False
    for m in (mat_body, mat_mouth):
        if m:
            me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    ob.rotation_mode = 'QUATERNION'
    coll.objects.link(ob)
    return ob


# the left-hip tie point in the rest pose (part_registry SOCKETS['hip_side.L']) and the worn angle
LEFT_AT = 0.25                                            # the left hand's grip behind the mouth
TIE = 0.12                                                # mouth -> obi cord, along the saya


# Where the saya is worn, in the torso's REST space (metres, degrees). Chosen by measurement, not by eye:
# tools in draw_test.py (--measure) count how much of the scabbard each camera really sees.
# 26 Nov search over 384 placements x 4 cameras: the old wear (0.185, -0.155, 0.945 / 13 / -14) was 0%
# visible from a 3/4 front camera in the iai pose (inside the sleeve and hakama); this one is 56-69%.
WEAR = {'mouth': (0.25, -0.23, 0.96), 'swing': 10.0, 'tilt': -15.0}


def saya_rest_in_torso(wear=None):
    """The saya at the left hip: mouth at the obi in front, body running back (+Y), swung out (+X) by
    `swing` and down by `tilt`, edge up."""
    w = dict(WEAR, **(wear or {}))
    tilt = Matrix.Rotation(math.radians(w['tilt']), 3, 'X') @ Matrix.Rotation(math.radians(w['swing']), 3, 'Z')
    d = tilt @ Vector((0, 1, 0))
    return frame(Vector(w['mouth']), d)


# --------------------------------------------------------------------------- the gripping hands
# Mark, 26 Nov: "does the hand hold?" It did not: the hand part is one flat folded sheet with four straight
# fingers (part_registry.hand_folded), so even with the hand exactly on the handle it read as a paddle
# touching the sword. A holding hand is a different SHAPE, not more joints: four fingers folded round the
# handle like C-shaped paper bands, the back of the hand over them, the thumb across the top, a wrist block
# back to the forearm (the same design as the browser engine's grip hand, engine/figure.js). It is built in
# the SWORD's frame and rides the hand joint through the grip frame, so when the IK puts the hand on the
# handle the fingers wrap the real handle. It swaps with the open hand while the hand holds.
def build_grip_hand(name, coll, joint, H, mat, radius=0.019, x0=-0.100, x1=-0.022, thumb_side=1.0):
    bm = bmesh.new()
    n_f = 4
    w = (x1 - x0) / n_f
    gap = math.radians(70)                                # the open side of each C, where the thumb lies
    segs = 6
    for i in range(n_f):
        xa, xb = x0 + i * w + 0.0015, x0 + (i + 1) * w - 0.0015
        r = radius * (1.0 - 0.04 * i) + 0.004            # little finger slightly smaller
        ring_a, ring_b = [], []
        for k in range(segs + 1):
            a = gap / 2 + (2 * math.pi - gap) * k / segs + (math.pi / 2 if thumb_side > 0 else -math.pi / 2)
            ring_a.append(bm.verts.new((xa, r * math.cos(a), r * math.sin(a))))
            ring_b.append(bm.verts.new((xb, r * math.cos(a), r * math.sin(a))))
        for k in range(segs):
            bm.faces.new((ring_a[k], ring_b[k], ring_b[k + 1], ring_a[k + 1]))
    # the back of the hand: a plate over the fingers' knuckle side, running back toward the wrist
    wrist = H.inverted() @ Vector((0, 0, 0))              # the hand joint, in the sword frame
    out = Vector((0, -1, 0)) if thumb_side > 0 else Vector((0, 1, 0))
    kn = radius + 0.006
    plate = [Vector((x0, 0, 0)) + out * kn + Vector((0, 0, 0.018)), Vector((x1, 0, 0)) + out * kn + Vector((0, 0, 0.018)),
             Vector((x1, 0, 0)) + out * kn + Vector((0, 0, -0.018)), Vector((x0, 0, 0)) + out * kn + Vector((0, 0, -0.018))]
    pv = [bm.verts.new(v) for v in plate]
    bm.faces.new(pv)
    # palm/wrist: from the plate's middle to the joint
    mid = (plate[0] + plate[1] + plate[2] + plate[3]) / 4
    a0, a1 = mid + Vector((0, 0, 0.02)), mid + Vector((0, 0, -0.02))
    wv = [bm.verts.new(v) for v in (a0, a1, wrist + Vector((0, 0, -0.018)), wrist + Vector((0, 0, 0.018)))]
    bm.faces.new(wv)
    # the thumb across the top of the handle, toward the guard
    tz = radius + 0.004
    th = [Vector((x0 + 0.02, 0.006, tz)), Vector((x1 + 0.004, 0.004, tz)), Vector((x1 + 0.004, -0.010, tz)),
          Vector((x0 + 0.02, -0.012, tz))]
    if thumb_side < 0:
        th = [Vector((v.x, v.y, -v.z)) for v in th]
    bm.faces.new([bm.verts.new(v) for v in th])
    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges[:])
    bmesh.ops.triangulate(bm, faces=bm.faces[:])               # non-planar quads crashed scene.ray_cast in 4.5
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = False
    ob = bpy.data.objects.new(name, me)
    if mat:
        me.materials.append(mat)
    coll.objects.link(ob)
    sol = ob.modifiers.new('fold', 'SOLIDIFY')            # paper with a thickness, like every other part
    sol.thickness = 0.004
    ob.parent = joint
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = H
    return ob


def key_visible(ob, f, on):
    # render visibility only: keying hide_viewport crashed scene.ray_cast (the --measure probe) in 4.5
    ob.hide_render = not on
    ob.keyframe_insert('hide_render', frame=f)


# --------------------------------------------------------------------------- the right-arm IK
# The rig is posed by joint ANGLES (engine/figure.js), so nothing ever put a hand ON a handle: a draw
# showed the hand swinging one way while the blade, glued to the hand, cut through its own scabbard.
# This small solver turns the right arm's pose angles until the hand's grip frame sits on a target
# sword frame. Damped least squares on 7 angles, numeric Jacobian, plain Python (no scipy in Blender).
def arm_keys(side='r'):
    return tuple(side + k for k in ('sx', 'sy', 'sz', 'ex', 'fy', 'wx', 'wz'))


ARM = arm_keys('r')
LIMITS = {'rex': (-2.7, -0.05), 'lex': (-2.7, -0.05)}


def _euler(rx, ry, rz):
    from mathutils import Euler
    return Euler((rx, -rz, ry), 'YZX').to_matrix().to_4x4()   # Rig.rot: three (x, y, z) -> Blender


def _arm_points(rig, p, side='r'):
    """World positions of shoulder, elbow and wrist for pose p (same chain as _hand_fk)."""
    J, s = rig.J, side
    M = J[s + 'C'].matrix_world.copy()
    pts = []
    for j, r in ((s + 'S', (p[s + 'sx'], p[s + 'sy'], p[s + 'sz'])), (s + 'E', (p[s + 'ex'], 0, 0)),
                 (s + 'T', (0, p[s + 'fy'], 0)), (s + 'H', (p[s + 'wx'], 0, p[s + 'wz']))):
        M = M @ Matrix.Translation(J[j].location) @ _euler(*r)
        if j[1:] in ('S', 'E', 'H'):
            pts.append(M.translation.copy())
    return pts


def _hand_fk(rig, p, H, side='r'):
    J, s = rig.J, side
    M = J[s + 'C'].matrix_world.copy()
    for j, r in ((s + 'S', (p[s + 'sx'], p[s + 'sy'], p[s + 'sz'])), (s + 'E', (p[s + 'ex'], 0, 0)),
                 (s + 'T', (0, p[s + 'fy'], 0)), (s + 'H', (p[s + 'wx'], 0, p[s + 'wz']))):
        M = M @ Matrix.Translation(J[j].location) @ _euler(*r)
    return M @ H


def _err(M, T, wr):
    """Position error, plus the turn that lines the hand's handle axis up with the target's. The twist ABOUT
    the handle is left free: a hand wraps round a handle at any roll, and the wrist cannot match a forced
    roll (that conflict alone left the hand 5-7 cm off the handle)."""
    e = list(T.translation - M.translation)
    a, b = M.to_3x3().col[0].normalized(), T.to_3x3().col[0].normalized()
    ax = a.cross(b)
    ang = math.atan2(ax.length, a.dot(b))
    ax = ax.normalized() if ax.length > 1e-9 else Vector((0, 0, 0))
    return e + [c * ang * wr for c in ax]


def _solve6(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        for r in range(n):
            if r != c and M[c][c]:
                k = M[r][c] / M[c][c]
                M[r] = [a - k * bb for a, bb in zip(M[r], M[c])]
    return [M[i][n] / M[i][i] if M[i][i] else 0.0 for i in range(n)]


def _ik(rig, pose, target, H, iters, wr, lam, side):
    p = dict(pose)
    keys = arm_keys(side)
    for _ in range(iters):
        M = _hand_fk(rig, p, H, side)
        e = _err(M, target, wr)
        if sum(c * c for c in e) ** 0.5 < 1e-3:
            break
        Jc = []
        for k in keys:
            q = dict(p)
            q[k] += 1e-3
            ek = _err(_hand_fk(rig, q, H, side), target, wr)
            Jc.append([(a - b) / 1e-3 for a, b in zip(e, ek)])   # -(d error)/dk = (d hand)/dk
        # J (6 x 7) = d hand / d angles ; dp = J^T (J J^T + lam^2 I)^-1 e
        Jm = [[Jc[k][i] for k in range(len(keys))] for i in range(6)]
        A = [[sum(Jm[i][k] * Jm[j][k] for k in range(len(keys))) + (lam * lam if i == j else 0)
              for j in range(6)] for i in range(6)]
        y = _solve6(A, e)
        for k, name in enumerate(keys):
            p[name] += sum(Jm[i][k] * y[i] for i in range(6))
            lo, hi = LIMITS.get(name, (-3.1, 3.1))
            p[name] = max(lo, min(hi, p[name]))
    return p


def ik_arm(rig, pose, target, H, side='r', wr=0.25):
    """Return (pose with that arm turned so the hand grips `target`, gap in metres). Two passes: first the
    hand goes TO the handle (position only, always reachable here), then it turns along the handle without
    leaving it. One weighted pass got stuck 5-7 cm off."""
    p = _ik(rig, pose, target, H, 40, 0.0, 0.06, side)
    p = _ik(rig, p, target, H, 40, wr, 0.06, side)
    M = _hand_fk(rig, p, H, side)
    ik_arm.last_angle = round(math.degrees(M.to_3x3().col[0].normalized().angle(
        target.to_3x3().col[0].normalized(), 0.0)), 1)
    return p, (target.translation - M.translation).length


def arm_keep_out(rig, pose, caps, side, hold=None, H=None, iters=30, lam=0.05, margin=0.008):
    """Swing the arm (shoulder + elbow + wrist angles) until it is out of the body, keeping the hand where
    it must be: ON the sword if `hold` (a grip frame) is given, near where it was otherwise. This is the
    animator's 'elbow out' fix, done on every frame. Returns (pose, deepest cm before, after)."""
    ar = 'R' if side == 'r' else 'L'
    skip = ('upperarm.' + ar, 'forearm.' + ar)
    keys = arm_keys(side)

    def depth_terms(p):
        sh, el, wr_ = _arm_points(rig, p, side)
        out, worst = [], 0.0
        for (a, b), rad in (((sh, el), 0.05), ((el, wr_), 0.04)):
            for t in (0.5, 0.75, 1.0):
                pt = a.lerp(b, t)
                q = caps.push_out(pt, margin + rad, skip=skip)
                d = (q - pt)
                out += list(d)
                worst = max(worst, d.length)
        return out, worst
    p = dict(pose)
    H = H or hand_holder()
    keep = hold if hold is not None else _hand_fk(rig, p, H, side)
    wk = 1.0 if hold is not None else 0.25
    _, before = depth_terms(p)
    if before <= 0:
        return p, 0.0, 0.0
    for _ in range(iters):
        def resid(pp):
            M = _hand_fk(rig, pp, H, side)
            e = [c * wk for c in (keep.translation - M.translation)]
            col, _w = depth_terms(pp)
            return e + col
        e = resid(p)
        if max(abs(c) for c in e[3:]) < 1e-3:
            break
        J = []
        for k in keys:
            q = dict(p)
            q[k] += 1e-3
            J.append([(b - a) / -1e-3 for a, b in zip(e, resid(q))])   # d(model)/dk = -(d resid)/dk
        m = len(e)
        Jm = [[J[k][i] for k in range(len(keys))] for i in range(m)]
        A = [[sum(Jm[i][k] * Jm[j][k] for k in range(len(keys))) + (lam * lam if i == j else 0) for j in range(m)]
             for i in range(m)]
        y = _solve6(A, e)
        for k, name in enumerate(keys):
            p[name] += sum(Jm[i][k] * y[i] for i in range(m))
            lo, hi = LIMITS.get(name, (-3.1, 3.1))
            p[name] = max(lo, min(hi, p[name]))
    _, after = depth_terms(p)
    return p, before, after


def _smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


class Draw:
    """One swordsman's sword + saya through a draw (nukitsuke), in frames:

      grab   the right hand reaches the handle (IK blends in over `reach` frames before it)
      slide  the blade starts to leave the mouth (between grab and slide: the koiguchi, a held beat)
      clear  the tip leaves the mouth; the arm hands back to the pose over `release` frames

    During the slide the scabbard turns about its obi cord (the left hand's saya-biki) and is pulled
    back up to `biki` metres, and the guard travels out along that line, slow then fast, curving toward
    `aim` (forward, right, up in the torso's frame) so the blade leaves the mouth already pointing at the
    opponent. The blade is ALWAYS on the scabbard's axis until it clears: it cannot cut through it.
    """

    def __init__(self, rig, sword, saya, blade_len, grab, slide, clear, reach=10, release=9, settle=14,
                 biki=0.25, aim=(0.6, 0.9, 0.3), turn=0.75, R=0.0, level=8.0, meet=30.0, min_elev=-15.0):
        self.rig, self.sword, self.saya = rig, sword, saya
        self.L = blade_len
        self.R = R                                          # the blade's curve (katana_real build()['R'])
        self.grab, self.slide, self.clear = grab, slide, clear
        self.reach, self.release, self.settle = reach, release, settle
        self.biki, self.aim, self.turn, self.level, self.meet = biki, aim, turn, level, meet
        self.min_elev = min_elev
        self.meet_q = None
        self.hands = {}                                     # side -> (open hand objects, grip hand object)
        self.caps = None                                    # body_capsules.BodyCapsules: the body's boundary
        self.pushed = {}                                    # frame -> degrees the blade was turned out
        self.arm_fix = {}                                   # side -> [(frame, cm before, cm after)]
        self._rel_prev = None
        self._arm_at_clear = None
        self._roll_off = None                               # the sword's turn in the hand at the clear
        self.let_go = 0                                     # frames after the clear the left hand lets go
        self.recover = 14                                    # frames to reach the recovery fist
        self.recover_at = Vector((0.33, -0.06, 0.93))       # torso rest space: left of the hip, a little forward
        self.release_l = 16                                 # the left hand lets go of the scabbard slowly
        self.unroll = 10                                    # frames to ease it out
        self._corr = {}                                     # side -> last frame's elbow-out correction
        self.max_corr_step = 0.25                           # rad per frame: the correction can't pop
        self.H = hand_holder()
        self.Mrest = saya_rest_in_torso()
        from part_registry import REST                     # noqa: the rig's rest joints
        self.torso_rest = Vector(REST['torso'])
        self.last_saya = None
        self.last_target = None
        self.residual = {}
        self.residual_l = {}
        self.throw = None                                   # set_throw(): the scabbard thrown away (Ganryujima)
        self.rate = 1.0                                     # this frame's speed-ramp rate (world time per film frame)
        self.surface = None                                 # (ground(x, y, z_from), sea(x, y)): where a thrown thing lands
        self.fps = 30.0
        self.events = []                                    # [{'kind': 'splash' | 'land', 'frame', 'pos'}]

    def set_throw(self, grab, release, to, apex=2.0, spin=9.0, reach=6, sink=0.6):
        """Kojiro throws the scabbard away (research/ganryujima.md, tradition): `reach` frames before `grab` the left
        hand goes to the scabbard's mouth at the obi; from `grab` it carries it (the pose throws the arm); at `release`
        it flies on a ballistic arc `apex` m above the release point to the place `to` (world x, y), turning `spin`
        rad/s end over end, and lands on the sea (a splash, then it sinks `sink` m over a second) or the sand. Times
        in frames. After the throw the left arm follows the pose (two hands on the hilt), no fist at the hip."""
        self.throw = {'grab': grab, 'release': release, 'to': Vector((float(to[0]), float(to[1]), 0.0)),
                      'apex': float(apex), 'spin': float(spin), 'reach': int(reach), 'sink': float(sink)}
        self._throw_arm = None
        self._flight = None

    def _D(self):
        return self.rig.J['torso'].matrix_world @ Matrix.Translation(-self.torso_rest)

    def step(self, f, pose):
        """Pose the rig for frame f from `pose` (a full pose dict), fix the right arm, place sword and saya.
        Returns the phase name."""
        rig = self.rig
        pose_in = dict(pose)
        rig.pose(pose)
        bpy.context.view_layer.update()
        D = self._D()
        worn = D @ self.Mrest                              # mouth frame, x toward the tip (back)
        # Once the left hand holds the scabbard it LEVELS it (the tip just below the mouth, `level` degrees)
        # about the obi cord, whatever the hips do: a crouched iai pose no longer points the handle at the floor.
        hold = _smooth((f - (self.grab - self.reach)) / self.reach)
        if f >= self.clear:
            hold *= 1.0 - _smooth((f - self.clear) / self.settle)
        hip = worn
        if hold > 0:
            d = worn.to_3x3().col[0]
            flat = Vector((d.x, d.y, 0)).normalized()
            lv = (flat * math.cos(math.radians(self.level)) - Vector((0, 0, 1)) * math.sin(math.radians(self.level)))
            pivot = worn @ Vector((TIE, 0, 0))
            q = d.rotation_difference(lv)
            Mq = Matrix.Translation(pivot) @ q.to_matrix().to_4x4() @ Matrix.Translation(-pivot)
            hip = blend(worn, Mq @ worn, hold)
            # ...and TURNS it to meet the right hand: the hand goes onto the handle (position only), the
            # scabbard swings about its cord (at most `meet` degrees) so its line runs along the hand's grip.
            # During the slide the last turn is kept, so nothing jumps when the blade starts to move.
            pivot = hip @ Vector((TIE, 0, 0))
            if f < self.slide:
                for _ in range(2):
                    pp = _ik(rig, pose, hip, self.H, 40, 0.0, 0.06, 'r')
                    a_h = _hand_fk(rig, pp, self.H, 'r').to_3x3().col[0].normalized()
                    d = hip.to_3x3().col[0].normalized()
                    q = d.rotation_difference(a_h)
                    ax, ang = q.to_axis_angle()
                    ang = min(ang, math.radians(self.meet)) * hold
                    from mathutils import Quaternion as _Q
                    Mq = Matrix.Translation(pivot) @ _Q(ax, ang).to_matrix().to_4x4() @ Matrix.Translation(-pivot)
                    hip = Mq @ hip
                    self.meet_q = (hip.to_3x3() @ worn.to_3x3().inverted()).to_quaternion()
            elif getattr(self, 'meet_q', None) is not None:
                R3 = self.meet_q.to_matrix()
                hip = Matrix.Translation(pivot) @ R3.to_4x4() @ Matrix.Translation(-(worn @ Vector((TIE, 0, 0)))) @ worn
                hip = blend(worn, hip, hold)
            # ...but never steeper than `min_elev` (the meet turn plus the coil pointed it -33 deg at the floor):
            # a held scabbard stays readable, near level, the tip a little below the mouth
            d = hip.to_3x3().col[0].normalized()
            el = math.degrees(math.asin(max(-1.0, min(1.0, d.z))))
            lo, hi = self.min_elev, 0.0
            if el < lo or el > hi:
                want = math.radians(max(lo, min(hi, el)))
                flat = Vector((d.x, d.y, 0)).normalized()
                lv = flat * math.cos(want) + Vector((0, 0, 1)) * math.sin(want)
                pivot = hip @ Vector((TIE, 0, 0))
                q = d.rotation_difference(lv)
                hip = Matrix.Translation(pivot) @ q.to_matrix().to_4x4() @ Matrix.Translation(-pivot) @ hip
        back = hip.to_3x3().col[0].normalized()
        tie0 = hip.translation + back * TIE
        target, w, phase = None, 0.0, 'sheathed'
        if f < self.slide:
            target = hip                                    # hand on the handle, guard at the mouth
            w = _smooth((f - (self.grab - self.reach)) / self.reach)
            Y = hip
            phase = 'sheathed' if w <= 0 else 'grab'
        elif f < self.clear:
            u = (f - self.slide) / (self.clear - self.slide)
            e = u * u                                       # slow out of the mouth, then fast
            tie = tie0 + back * self.biki * _smooth(u)
            fwd, right = -D.to_3x3().col[1].normalized(), -D.to_3x3().col[0].normalized()
            a = (fwd * self.aim[0] + right * self.aim[1] + Vector((0, 0, 1)) * self.aim[2]).normalized()
            out = (-back).slerp(a, self.turn * e) if (-back).angle(a) > 1e-4 else a
            mouth = tie + out * TIE
            Y = frame(mouth, -out)
            target = Y @ arc(e * (self.L + 0.03), self.R)   # the blade slides out ALONG ITS CURVE
            if self.caps is not None:
                # the part already out of the mouth must not run into the legs or the body: the left hand
                # tilts the scabbard about its cord (blade and all) until it is clear, as a real draw does
                caps = self.caps.update()
                s_out = e * (self.L + 0.03)
                turned = 0.0
                for _ in range(10):
                    worst, wpt = 0.0, None
                    for i in range(1, 13):
                        pt = target @ Vector((-0.0 + (s_out) * i / 12 - 0.0, 0, 0))
                        d, who = caps.depth(pt, skip=('forearm.R', 'forearm.L', 'belly', 'hips'))
                        if d > worst:
                            worst, wpt = d, pt
                    if worst <= 0:
                        break
                    away = caps.push_out(wpt, 0.02, skip=('forearm.R', 'forearm.L', 'belly', 'hips')) - wpt
                    axis = out.cross(away)                  # turns the FORWARD (exposed) part toward `away`
                    if axis.length < 1e-9:
                        break
                    Rt = Matrix.Translation(tie) @ Matrix.Rotation(math.radians(4), 4, axis.normalized()) @ Matrix.Translation(-tie)
                    Y, target = Rt @ Y, Rt @ target
                    out = -Y.to_3x3().col[0].normalized()
                    turned += 4
                if turned:
                    self.pushed[f] = turned
            self.last_saya, self.last_target = Y, target
            w, phase = 1.0, 'drawing'
        else:
            target = self.last_target
            w = 1.0 - _smooth((f - self.clear) / self.release)
            Y = blend(self.last_saya or worn, worn, (f - self.clear) / self.settle)
            phase = 'drawn'
        if phase == 'drawn' and w > 0 and self._arm_at_clear is not None:
            # RELEASE: blend the arm's ANGLES from where they were when the blade cleared to the pose's own.
            # (It used to keep an IK pull toward the last target - the sword lying back along the scabbard -
            # for `release` frames, which tipped the blade 54 deg down right at the cut's contact.)
            pose = dict(pose)
            for k in ARM:
                pose[k] = pose[k] + (self._arm_at_clear[k] - pose[k]) * w
            rig.pose(pose)
            bpy.context.view_layer.update()
        elif w > 0 and target is not None:
            solved, res = ik_arm(rig, pose, target, self.H)
            self.residual[f] = (round(res, 3), ik_arm.last_angle)
            pose = dict(pose)
            for k in ARM:
                pose[k] = pose[k] + (solved[k] - pose[k]) * w
            rig.pose(pose)
            bpy.context.view_layer.update()
        # THE LEFT HAND holds the scabbard just behind its mouth from the grab until the scabbard has
        # settled after the tip clears: it is what pulls the saya back (saya-biki) and turns it. Before,
        # it hung idle by the hakama while the blade came out of nowhere.
        wl = _smooth((f - (self.grab - self.reach)) / self.reach)
        if phase == 'drawn':
            # A DELIBERATE RELEASE: holding the scabbard while it settled dragged the left forearm through the
            # belly (5 cm, frames 50-58). The scabbard is tied in the obi and settles by itself; the left hand
            # lets go `let_go` frames after the clear and RECOVERS to a planted fist at the left hip, elbow out.
            wl = 1.0 - _smooth((f - self.clear - self.let_go) / self.recover)
        if wl > 0:
            lt = frame(Y @ Vector((LEFT_AT, 0, 0)), Y.to_3x3().col[0])
            solved, res = ik_arm(rig, pose, lt, self.H, side='l')
            self.residual_l[f] = round(res, 3)
            pose = dict(pose)
            for k in arm_keys('l'):
                pose[k] = pose[k] + (solved[k] - pose[k]) * wl
            rig.pose(pose)
            bpy.context.view_layer.update()
        if phase == 'drawn' and wl < 1.0 and not (self.throw is not None and f >= self.throw['grab'] - self.throw['reach']):
            # the recovery contact: a fist on the side of the left hip, a hand's width out from the obi
            D = self._D()
            spot = D @ self.recover_at
            fist = Matrix.Translation(spot) @ D.to_3x3().to_4x4()
            solved, _r = ik_arm(rig, pose, fist, self.H, side='l', wr=0.0)
            pose = dict(pose)
            for k in arm_keys('l'):
                pose[k] = pose[k] + (solved[k] - pose[k]) * (1.0 - wl)
            rig.pose(pose)
            bpy.context.view_layer.update()
        if self.caps is not None:
            # both arms out of the body: the elbow swings out, a holding hand stays on what it holds
            self.caps.update()
            for side, held in (('r', w > 0.85 or phase == 'drawing'), ('l', wl > 0.85)):
                hold = (rig.J[side + 'H'].matrix_world @ self.H) if held else None
                fixed, b_, a_ = arm_keep_out(rig, pose, self.caps, side, hold=hold, H=self.H)
                # rate-limit the correction so the elbow eases out instead of snapping on the frame it starts
                prev = self._corr.get(side, {})
                corr = {}
                for k in arm_keys(side):
                    want = fixed[k] - pose[k]
                    was = prev.get(k, 0.0)
                    corr[k] = was + max(-self.max_corr_step, min(self.max_corr_step, want - was))
                self._corr[side] = corr
                pose = dict(pose)
                for k, v in corr.items():
                    pose[k] += v
                if b_ > 0:
                    self.arm_fix.setdefault(side, []).append((f, round(b_ * 100, 1), round(a_ * 100, 1)))
            rig.pose(pose)
            bpy.context.view_layer.update()
            # SAYA-GAESHI: while the blade is still in the scabbard, the left hand turns the scabbard (and the blade in
            # it) about its own axis to follow how the right hand holds the handle, so the hand never turns ON the
            # handle. The handle lies on that axis, so both grips stay where they are.
            if phase == 'drawing':
                hm = (rig.J['rH'].matrix_world @ self.H).to_3x3()
                sm = target.to_3x3()
                ax = sm.col[0].normalized()
                hy = (hm.col[1] - ax * hm.col[1].dot(ax)).normalized()
                sy = (sm.col[1] - ax * sm.col[1].dot(ax)).normalized()
                ang = math.atan2(ax.dot(sy.cross(hy)), sy.dot(hy))
                piv = target.translation                       # about the HANDLE's line: the hilt stays put
                Rr = Matrix.Translation(piv) @ Matrix.Rotation(ang, 4, ax) @ Matrix.Translation(-piv)
                Y, target = Rr @ Y, Rr @ target
                self.last_saya, self.last_target = Y, target
            # GRIP LAST: the elbow-out pass may have moved a holding hand; put it back on what it holds so the
            # final pose has the grip exact (the elbow keeps what it gained where it can)
            final = []
            if phase in ('grab', 'drawing') and w > 0.85:
                final.append(('r', target))
            if wl > 0.85:
                final.append(('l', frame(Y @ Vector((LEFT_AT, 0, 0)), Y.to_3x3().col[0])))
            for side, tg in final:
                solved, res = ik_arm(rig, pose, tg, self.H, side=side)
                pose = dict(pose)
                for k in arm_keys(side):
                    pose[k] = solved[k]
                if side == 'l':
                    # planted contact: the hand stays ON the scabbard, the elbow swings out of the belly in the
                    # SAME solve (re-gripping after the elbow pass used to drop the elbow back in)
                    pose, _b, _a = arm_keep_out(rig, pose, self.caps.update(), 'l', hold=tg, H=self.H)
                self._corr[side] = {}
            if final:
                rig.pose(pose)
                bpy.context.view_layer.update()
        hand = rig.J['rH'].matrix_world @ self.H
        if phase in ('sheathed', 'grab'):
            S = hip                                         # in the scabbard until the slide: the hand comes TO it
        elif phase == 'drawing':
            S = target                                      # on the scabbard's axis, exactly
        else:
            # At the clear the blade leaves the scabbard's roll (edge up) for the hand's. Jumping straight to the
            # hand's frame twisted the sword 65 deg in ONE frame; keep the offset it had and ease it out.
            if self._roll_off is None:
                # keep EXACTLY the hand-to-sword turn of the last drawing frame: no change at the clear
                self._roll_off = self._rel_prev if self._rel_prev is not None else \
                    (hand.to_3x3().inverted() @ (self.last_target or hand).to_3x3()).to_quaternion()
            # The sword keeps the turn it had in the hand at the clear: the hand-to-hilt pose stays FIXED, so the
            # wrist and the sword turn together (easing it out was the sword twisting inside the hand).
            S = hand @ self._roll_off.to_matrix().to_4x4()
            if self.caps is not None:
                S, pose = self._keep_out(S, pose)
                # the sword rides the FINAL hand: if the arm could not reach the turned-out frame exactly, the
                # blade follows the hand (a few mm) instead of the hand slipping on the hilt
                S = (rig.J['rH'].matrix_world @ self.H) @ self._roll_off.to_matrix().to_4x4()
        if phase == 'drawing':
            self._rel_prev = (hand.to_3x3().inverted() @ S.to_3x3()).to_quaternion()
            self._arm_at_clear = {k: pose[k] for k in ARM}  # the last drawing frame's arm, for the release
        held_l = None
        if self.throw is not None and phase == 'drawn' and f >= self.throw['grab'] - self.throw['reach']:
            Y, pose, held_l = self._throw_step(f, Y, pose, pose_in)
        for ob, M in ((self.sword, S), (self.saya, Y)):
            loc, rot, _ = M.decompose()
            ob.location = loc
            ob.rotation_quaternion = rot
            ob.keyframe_insert('location', frame=f)
            ob.keyframe_insert('rotation_quaternion', frame=f)
        # the hands: the gripping shape while the hand is ON the sword / scabbard, the open one otherwise
        holding = {'r': w > 0.85 or phase == 'drawn',
                   'l': wl > 0.85 and not (phase == 'drawn' and f >= self.clear + self.let_go)}   # opens as it lets go
        if held_l is not None:
            holding['l'] = held_l
        for side, (opens, grip) in self.hands.items():
            for ob in opens:
                key_visible(ob, f, not holding[side])
            key_visible(grip, f, holding[side])
        return phase

    def _throw_step(self, f, Y, pose, pose_in):
        """The scabbard throw for frame f (see set_throw). Returns (saya frame, pose, left hand holding or None)."""
        T, rig = self.throw, self.rig
        g0 = T['grab'] - T['reach']
        if f < T['grab']:                                   # reach: the left hand to the mouth of the scabbard
            wl = _smooth((f - g0) / T['reach'])
            lt = frame(Y @ Vector((LEFT_AT, 0, 0)), Y.to_3x3().col[0])
            solved, _res = ik_arm(rig, pose, lt, self.H, side='l')
            pose = dict(pose)
            for k in arm_keys('l'):
                pose[k] = pose[k] + (solved[k] - pose[k]) * wl
            rig.pose(pose)
            bpy.context.view_layer.update()
            self._throw_arm = {k: pose[k] for k in arm_keys('l')}
            return Y, pose, wl > 0.85
        if f < T['release'] or self._flight is None and f == T['release']:
            # carried: the left arm eases from its grip at the obi into the authored throw (the pose's own left arm,
            # not the recovery fist the draw would hold it in), and the scabbard rides the fist
            u = _smooth((f - T['grab']) / max(1, T['reach']))
            pose = dict(pose)
            for k in arm_keys('l'):
                start = (self._throw_arm or {}).get(k, pose_in[k])
                pose[k] = start + (pose_in[k] - start) * u
            rig.pose(pose)
            bpy.context.view_layer.update()
            Yh = (rig.J['lH'].matrix_world @ self.H) @ Matrix.Translation((-LEFT_AT, 0, 0))
            self._last_held = (f, Yh)
            if f < T['release']:
                return Yh, pose, True
            Y = Yh
        if self._flight is None:                            # the release: a ballistic arc to the target place
            c0 = Y @ Vector((self.L * 0.5, 0, 0))          # the scabbard's middle
            g = 9.81
            vz = math.sqrt(2 * g * max(0.2, T['apex']))
            land = 0.0
            if self.surface:
                gr, sea = self.surface
                zs = [z for z in ((gr(T['to'].x, T['to'].y, c0.z + 5.0) if gr else None),
                                  (sea(T['to'].x, T['to'].y) if sea else None)) if z is not None]
                land = max(zs) if zs else 0.0
            tf = (vz + math.sqrt(vz * vz + 2 * g * max(0.0, c0.z - land))) / g
            vh = (T['to'] - Vector((c0.x, c0.y, 0.0))) / tf
            axis = Vector((vh.y, -vh.x, 0.0)).normalized() if vh.length > 1e-6 else Vector((1, 0, 0))
            self._flight = {'f0': f, 'c0': c0, 'v': Vector((vh.x, vh.y, vz)), 'tf': tf, 'land': land, 'axis': axis,
                            'R0': Y.to_3x3(), 't': 0.0, 'landed': None}
        Fl = self._flight
        if f > Fl['f0']:
            Fl['t'] += self.rate / self.fps                 # world time: slow motion slows the flight too
        t = min(Fl['t'], Fl['tf'])
        c = Fl['c0'] + Fl['v'] * t + Vector((0, 0, -0.5 * 9.81 * t * t))
        R = Matrix.Rotation(T['spin'] * t, 3, Fl['axis']) @ Fl['R0']
        if Fl['t'] >= Fl['tf']:
            if Fl['landed'] is None:
                Fl['landed'] = f
                kind = 'splash'
                if self.surface and self.surface[1] is not None:
                    s_ = self.surface[1](c.x, c.y)
                    kind = 'splash' if s_ is not None and s_ >= Fl['land'] - 0.02 else 'land'
                self.events.append({'kind': kind, 'frame': f, 'pos': [round(v, 3) for v in c]})
            u = min(1.0, (Fl['t'] - Fl['tf']) / 1.0)
            c = c + Vector((0, 0, -T['sink'] * _smooth(u)))  # it sinks (or settles in the sand)
            flat = Vector((R.col[0].x, R.col[0].y, 0.0))
            if flat.length > 1e-6:
                R = blend(R.to_4x4(), frame(Vector((0, 0, 0)), flat), min(1.0, u * 3)).to_3x3()
        M = R.to_4x4()
        M.translation = c - R @ Vector((self.L * 0.5, 0, 0))
        return M, pose, False

    def _keep_out(self, S, pose, step=4.0, max_turn=40.0):
        """If the drawn blade would pass INTO the body, turn it about the grip, a few degrees at a time, away
        from the deepest point until it is clear (or max_turn), then re-grip it with the arm IK so the hand
        still holds it. Returns (sword frame, pose)."""
        caps = self.caps.update()

        def deepest(M):
            best = (0.0, None)
            for i in range(1, 19):
                pt = M @ Vector((self.L * i / 18, 0, 0))
                d, who = caps.depth(pt, skip=('forearm.R', 'forearm.L'))
                if d > best[0]:
                    best = (d, pt)
            return best
        d, pt = deepest(S)
        if d <= 0:
            return S, pose
        grip = S.translation
        blade = S.to_3x3().col[0].normalized()
        turned = 0.0
        M = S
        while d > 0 and turned < max_turn:
            out = caps.push_out(pt, 0.02, skip=('forearm.R', 'forearm.L')) - pt
            axis = blade.cross(out)
            if axis.length < 1e-9:
                break
            R4 = Matrix.Translation(grip) @ Matrix.Rotation(math.radians(step), 4, axis.normalized()) @ Matrix.Translation(-grip)
            M = R4 @ M
            blade = M.to_3x3().col[0].normalized()
            turned += step
            d, pt = deepest(M)
        self.pushed[bpy.context.scene.frame_current] = turned
        solved, _ = ik_arm(self.rig, pose, M, self.H)
        pose = dict(pose)
        for k in ARM:
            pose[k] = solved[k]
        self.rig.pose(pose)
        bpy.context.view_layer.update()
        return M, pose

    def add_hands(self, open_r, open_l, mat_r=None, mat_l=None):
        """Give this swordsman gripping hands (swapped with the open-hand objects open_r / open_l)."""
        coll = self.sword.users_collection[0]
        gr = build_grip_hand('GRIP_R', coll, self.rig.J['rH'], self.H, mat_r, radius=0.017)
        gl = build_grip_hand('GRIP_L', coll, self.rig.J['lH'], self.H, mat_l, radius=0.023, thumb_side=-1.0)
        self.hands = {'r': (open_r, gr), 'l': (open_l, gl)}
        return gr, gl
