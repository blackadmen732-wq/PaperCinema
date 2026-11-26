"""BODY CAPSULES: the character's "boundary" (Mark, 26 Nov: "this don't listen to boundary ... their thing go
to their body and through their body").

Nothing in the rig knew where the body IS: parts ride joints, poses are angles, and a sword, a hand or a
scabbard could pass through the torso or the legs with nothing to notice. This is the boundary every studio
gives a character before animating it: a set of capsules (a cylinder with round ends) around the clothed body,
one per bone, recomputed from the rig's joints every frame. It measures (how deep, where, on which frame) and
it pushes a point back out to the surface, so the IK and the sword path can stay outside.

  caps = BodyCapsules(rig)                 # radii in metres, for the clothed paper body
  caps.update()                            # after rig.pose(...) + view_layer.update()
  depth, name = caps.depth(point)          # > 0 = inside by that many metres
  p_out = caps.push_out(point, margin)     # the nearest point on the surface (+ margin)
"""
from mathutils import Vector

# (name, joint a, joint b, radius m). Radii cover the CLOTHES (kimono, hakama), not the bare body:
# a blade that touches the hakama is already "in" the character.
CAPSULES = (
    ('pelvis', 'hips', 'upper', 0.15),
    ('chest', 'upper', 'neck', 0.16),
    ('head', 'neck', 'head', 0.11),
    ('thigh.R', 'rthigh', 'rshin', 0.12), ('shin.R', 'rshin', 'rfoot', 0.10),
    ('thigh.L', 'lthigh', 'lshin', 0.12), ('shin.L', 'lshin', 'lfoot', 0.10),
    ('upperarm.R', 'rS', 'rE', 0.055), ('forearm.R', 'rE', 'rH', 0.045),
    ('upperarm.L', 'lS', 'lE', 0.055), ('forearm.L', 'lE', 'lH', 0.045),
)


def _closest(p, a, b):
    ab = b - a
    t = 0.0 if ab.length_squared < 1e-12 else max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
    return a + ab * t


class BodyCapsules:
    def __init__(self, rig, capsules=CAPSULES, head_up=0.12):
        self.rig, self.spec, self.head_up = rig, capsules, head_up
        self.segs = []

    def update(self):
        J = self.rig.J
        self.segs = []
        for name, ja, jb, r in self.spec:
            a, b = J[ja].matrix_world.translation.copy(), J[jb].matrix_world.translation.copy()
            if name == 'head':                       # the head joint is at the skull base: reach up to the crown
                b = b + (b - a).normalized() * self.head_up if (b - a).length > 1e-6 else b + Vector((0, 0, self.head_up))
            self.segs.append((name, a, b, r))
        return self

    def depth(self, p, skip=()):
        """How far p is INSIDE the body (metres, > 0) and which capsule; <= 0 means outside."""
        best, who = -1e9, None
        for name, a, b, r in self.segs:
            if name in skip:
                continue
            d = r - (p - _closest(p, a, b)).length
            if d > best:
                best, who = d, name
        return best, who

    def push_out(self, p, margin=0.01, skip=(), iters=4):
        """The point moved out of every capsule it is in (to the surface + margin)."""
        q = p.copy()
        for _ in range(iters):
            moved = False
            for name, a, b, r in self.segs:
                if name in skip:
                    continue
                c = _closest(q, a, b)
                v = q - c
                if v.length < r + margin:
                    q = c + (v.normalized() if v.length > 1e-9 else Vector((0, -1, 0))) * (r + margin)
                    moved = True
            if not moved:
                break
        return q
