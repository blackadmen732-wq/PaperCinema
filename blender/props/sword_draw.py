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
LEFT_AT = 0.07                                            # the left hand's grip behind the mouth
TIE = 0.12                                                # mouth -> obi cord, along the saya


# Where the saya is worn, in the torso's REST space (metres, degrees). Chosen by measurement, not by eye:
# tools in draw_test.py (--measure) count how much of the scabbard each camera really sees.
# 26 Nov search over 384 placements x 4 cameras: the old wear (0.185, -0.155, 0.945 / 13 / -14) was 0%
# visible from a 3/4 front camera in the iai pose (inside the sleeve and hakama); this one is 56-69%.
WEAR = {'mouth': (0.25, -0.15, 0.96), 'swing': 10.0, 'tilt': -15.0}


def saya_rest_in_torso(wear=None):
    """The saya at the left hip: mouth at the obi in front, body running back (+Y), swung out (+X) by
    `swing` and down by `tilt`, edge up."""
    w = dict(WEAR, **(wear or {}))
    tilt = Matrix.Rotation(math.radians(w['tilt']), 3, 'X') @ Matrix.Rotation(math.radians(w['swing']), 3, 'Z')
    d = tilt @ Vector((0, 1, 0))
    return frame(Vector(w['mouth']), d)


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

    def __init__(self, rig, sword, saya, blade_len, grab, slide, clear, reach=6, release=4, settle=8,
                 biki=0.30, aim=(0.6, 0.9, 0.3), turn=0.75, R=0.0, level=8.0, meet=30.0):
        self.rig, self.sword, self.saya = rig, sword, saya
        self.L = blade_len
        self.R = R                                          # the blade's curve (katana_real build()['R'])
        self.grab, self.slide, self.clear = grab, slide, clear
        self.reach, self.release, self.settle = reach, release, settle
        self.biki, self.aim, self.turn, self.level, self.meet = biki, aim, turn, level, meet
        self.meet_q = None
        self.H = hand_holder()
        self.Mrest = saya_rest_in_torso()
        from part_registry import REST                     # noqa: the rig's rest joints
        self.torso_rest = Vector(REST['torso'])
        self.last_saya = None
        self.last_target = None
        self.residual = {}
        self.residual_l = {}

    def _D(self):
        return self.rig.J['torso'].matrix_world @ Matrix.Translation(-self.torso_rest)

    def step(self, f, pose):
        """Pose the rig for frame f from `pose` (a full pose dict), fix the right arm, place sword and saya.
        Returns the phase name."""
        rig = self.rig
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
            self.last_saya, self.last_target = Y, target
            w, phase = 1.0, 'drawing'
        else:
            target = self.last_target
            w = 1.0 - _smooth((f - self.clear) / self.release)
            Y = blend(self.last_saya or worn, worn, (f - self.clear) / self.settle)
            phase = 'drawn'
        if w > 0 and target is not None:
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
            wl = 1.0 - _smooth((f - self.clear - self.settle) / self.release)
        if wl > 0:
            lt = frame(Y @ Vector((LEFT_AT, 0, 0)), Y.to_3x3().col[0])
            solved, res = ik_arm(rig, pose, lt, self.H, side='l')
            self.residual_l[f] = round(res, 3)
            pose = dict(pose)
            for k in arm_keys('l'):
                pose[k] = pose[k] + (solved[k] - pose[k]) * wl
            rig.pose(pose)
            bpy.context.view_layer.update()
        hand = rig.J['rH'].matrix_world @ self.H
        if phase == 'sheathed':
            S = hip
        elif phase == 'drawing':
            S = target                                      # on the scabbard's axis, exactly
        else:
            S = hand
        for ob, M in ((self.sword, S), (self.saya, Y)):
            loc, rot, _ = M.decompose()
            ob.location = loc
            ob.rotation_quaternion = rot
            ob.keyframe_insert('location', frame=f)
            ob.keyframe_insert('rotation_quaternion', frame=f)
        return phase
