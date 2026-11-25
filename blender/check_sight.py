# CAMERA SIGHT: does the audience actually SEE the fight?
#
#   B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
#   $B -b -P blender/check_sight.py -- --film sword-mocap --set output/sets/bamboo-forest.blend
#   $B -b -P blender/check_sight.py -- --film ganryujima --every 1 --json out.json
#
# Three ways a shot can fail that no other check in this project catches, because every other check
# looks at the ANIMATION and this one looks at the VIEW:
#
#   blocked    something in the set stands between the camera and the fighter. A bamboo culm across
#              the hero's face was in a finished frame on 25 Nov and nothing flagged it.
#   off-frame  the fighter is outside the camera's field of view.
#   too small  the fighter is in frame but too few pixels tall to read.
#
# A contact frame that fails any of these is a CRITICAL: the whole shot exists for that frame, and
# an audience that does not see the blade land has watched nothing. Everywhere else it is a warning.
#
# The set is loaded WITHOUT the characters on purpose. A fighter standing in front of the other
# fighter is staging, not obstruction, and is the director's business; a tree in front of both is a
# mistake. This isolates the mistake.
import json
import math
import os
import sys

import bpy
from mathutils import Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(n, d=None):
    return ARGV[ARGV.index('--' + n) + 1] if '--' + n in ARGV else d


def flag(n):
    return '--' + n in ARGV


# three.js (+Y up, figure faces +Z) -> Blender (+Z up). The same conversion film_modular.py uses,
# so a disagreement here would be a disagreement about where the camera is, not about geometry.
BASIS = Quaternion((0.7071067811865476, 0.7071067811865476, 0.0, 0.0))


def v3(p):
    return Vector((p[0], -p[2], p[1]))


def qcam(q):
    return BASIS @ Quaternion((q[3], q[0], q[1], q[2]))


FILM = arg('film', 'sword-mocap')
EVERY = int(arg('every', 2))                 # sample every Nth frame; contacts are always sampled
MIN_H = float(arg('min-height', 0.18))       # a fighter under this share of frame height cannot read
CLEAR = float(arg('clearance', 0.06))        # ignore a hit this close to the target (its own ground)

TL = json.load(open(os.path.join(REPO, 'output', f'{FILM}.timeline.json')))
FRAMES = TL['frames']
BONES = TL['bones']['order']
W, H = TL['film'].get('width', 540), TL['film'].get('height', 960)
ASPECT = W / H

bpy.ops.wm.read_factory_settings(use_empty=True)
SET = arg('set')
if SET:
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(SET))
sc = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()
if not SET:
    print('  no --set: nothing can block the view, checking framing only')

# The points that must be visible. The head is what an audience looks at; the chest is the body;
# the weapon tip is where a cut happens and the one thing a contact frame is about.
WATCH = [('head', BONES.index('head')), ('chest', BONES.index('chest'))]

# Contact frames, from the engine's own event list. These are the frames the shot exists for.
CONTACT = set()
for e in (TL.get('events') or {}).get('impacts', []) if isinstance(TL.get('events'), dict) else []:
    t = e.get('t')
    if t is not None:
        CONTACT.add(int(round(t * (TL['clock']['fps'] if isinstance(TL.get('clock'), dict) else 24))))
for fr in FRAMES:
    if fr.get('impactFrame'):
        CONTACT.add(fr['f'])


def blocks(ob):
    """Would this object actually appear in the render?

    ray_cast hits everything in the depsgraph, including things the camera never sees: particle
    emitters, render-hidden helpers, lights given a mesh. The first run of this check reported a
    dust-mote emitter standing in front of both fighters for half the film, which is true of the
    geometry and false of the picture. A check that cries wolf stops being read."""
    if ob is None or ob.hide_render or not ob.visible_camera:
        return False
    if ob.type != 'MESH':
        return False
    # An emitter whose instancer is hidden at render time shows only its particles, not itself.
    if ob.particle_systems and not ob.show_instancer_for_render:
        return False
    return True


def visible(cam_pos, target):
    """Is `target` reachable from the camera, or does the set stand in the way?

    Walks THROUGH anything that does not render, rather than stopping at the first hit, so the
    answer is about the picture and not about the scene graph."""
    d = target - cam_pos
    dist = d.length
    if dist < 1e-4:
        return True, None
    dirn = d.normalized()
    start, travelled = cam_pos.copy(), 0.0
    for _ in range(12):                       # a handful of see-through hits is plenty
        remaining = dist - CLEAR - travelled
        if remaining <= 0:
            return True, None
        hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, start, dirn, distance=remaining)
        if not hit:
            return True, None
        if blocks(ob):
            return False, ob.name
        step = (loc - start).length + 1e-3    # step just past it and keep going
        travelled += step
        start = loc + dirn * 1e-3
    return True, None


def framing(cam_pos, cam_q, p, fov_deg):
    """Where the point lands on screen, and how tall the fighter reads.

    Blender cameras look down their own -Z with +Y up, so a point is in view when its camera-space
    z is negative and its x/y fall inside the frustum at that depth."""
    local = cam_q.inverted() @ (p - cam_pos)
    z = -local.z
    if z <= 0.01:
        return None
    half_h = math.tan(math.radians(fov_deg) / 2) * z
    half_w = half_h * ASPECT
    return (local.x / half_w, local.y / half_h, z)


rows = []
for fr in FRAMES:
    f = fr['f']
    if f % EVERY and f not in CONTACT:
        continue
    c = fr.get('camera')
    if not c:
        continue
    cp = v3(c['pos'])
    cq = qcam(c['rot'])
    fov = c.get('fov', 34)
    for aid, act in (fr.get('actors') or {}).items():
        if act.get('hidden') or not act.get('bones'):
            continue
        pts = {}
        for name, idx in WATCH:
            b = act['bones'][idx]
            pts[name] = v3(b[:3])
        head, chest = pts['head'], pts['chest']
        feet_y = min(v3(act['bones'][BONES.index(n)][:3]).z for n in ('foot.R', 'foot.L'))
        problems = []
        for name, p in pts.items():
            ok, by = visible(cp, p)
            if not ok:
                problems.append(f'{name} blocked by {by}')
        fr_head = framing(cp, cq, head, fov)
        fr_feet = framing(cp, cq, Vector((head.x, head.y, feet_y)), fov)
        if fr_head is None:
            problems.append('behind the camera')
        else:
            x, y, _z = fr_head
            if abs(x) > 1.0 or abs(y) > 1.0:
                problems.append(f'head outside the frame (x {x:+.2f}, y {y:+.2f})')
            elif fr_feet is not None:
                share = abs(fr_head[1] - fr_feet[1]) / 2.0
                if share < MIN_H:
                    problems.append(f'reads {share * 100:.0f}% of frame height (want {MIN_H * 100:.0f}%)')
        if problems:
            rows.append({'f': f, 't': round(fr['t'], 3), 'actor': aid, 'shot': fr.get('shot'),
                         'contact': f in CONTACT, 'problems': problems})

crit = [r for r in rows if r['contact']]
print(f'\nCAMERA SIGHT: {FILM} · {len(FRAMES)} frames · every {EVERY} · {len(CONTACT)} contact frame(s)'
      + (f" · set {os.path.basename(SET)}" if SET else ' · no set'))
if not rows:
    print('  every watched point is visible, in frame and big enough to read')
else:
    for r in rows[:40]:
        mark = 'CRITICAL' if r['contact'] else 'warning '
        print(f"  {mark} f{r['f']:<4} {r['t']:>6.2f}s  {r['actor']:<8} {'; '.join(r['problems'])}")
    if len(rows) > 40:
        print(f'  … and {len(rows) - 40} more')
print(f"\n  {len(rows)} frame(s) with a problem, {len(crit)} of them on a contact frame")

if arg('json'):
    json.dump({'film': FILM, 'set': SET, 'frames': len(FRAMES), 'rows': rows},
              open(arg('json'), 'w'), indent=1)
    print(f"  wrote {arg('json')}")

sys.exit(1 if crit else 0)
