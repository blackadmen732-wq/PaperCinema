"""SLASH FROM BLADE: build the paper slash from the sword's REAL path, not a typed crescent.

`blender/world/slash_fx.py` has had a good slash in it for weeks - a tapered folded crescent with an
ink edge, a reveal, a dying tail, torn paper shards and a light, amber for human and crimson for
demonic. `blender/film_modular.py` imported it ZERO times. So the effect existed and no film ever
had one. Same failure as the character, the fold darkening and the compositor: built, then not
connected.

This connects it, and connects it to the right thing. make_slash() takes a centre, a radius, a sweep
and a plane; those were meant to be typed by hand per shot. Every one of them is already in the
canonical timeline, measured: the weapon's transform is exported every frame AND at 4x sub-frame
resolution, precisely so the blade can be read between frames. So the arc is derived from where the
sword actually went:

  centre   the mean guard position over the swing - the hand, which is what the blade pivots around
  radius   the mean distance from guard to tip, which is the blade's own reach in that swing
  plane    fitted from the tip's path, so a kesa-giri comes out diagonal because the CUT was diagonal
  sweep    the real swept angle, signed, so the crescent travels the way the blade travelled
  frames   the window where the tip was actually moving fast

A slash that is a measurement of the swing cannot disagree with the swing. A typed one always
eventually does.
"""
import math

from mathutils import Matrix, Vector


def _v3(p):
    """three.js (+Y up, faces +Z) -> Blender (+Z up). The same conversion film_modular.py uses."""
    return Vector((p[0], -p[2], p[1]))


def _qrot(q, v):
    """Rotate v by the three.js quaternion [x, y, z, w], in three.js space.

    Done here rather than by converting the quaternion, because converting a POINT needs no
    convention argument and converting a rotation does. The tip is computed where the engine
    computed it, then the point is converted once."""
    x, y, z, w = q
    ux, uy, uz = x, y, z
    vx, vy, vz = v
    # t = 2 * (u x v); v' = v + w*t + (u x t)
    tx = 2 * (uy * vz - uz * vy)
    ty = 2 * (uz * vx - ux * vz)
    tz = 2 * (ux * vy - uy * vx)
    return (vx + w * tx + (uy * tz - uz * ty),
            vy + w * ty + (uz * tx - ux * tz),
            vz + w * tz + (ux * ty - uy * tx))


def blade_samples(tl, aid, blade_len):
    """Every guard/tip pair for one actor, frames and sub-frames together, in Blender space."""
    out = []
    for fr in tl['frames']:
        a = (fr.get('actors') or {}).get(aid)
        if a and a.get('weapon'):
            out.append((fr['t'], a['weapon']))
    for sf in tl.get('subframes') or []:
        a = (sf.get('actors') or {}).get(aid)
        if a and a.get('weapon'):
            out.append((sf['t'], a['weapon']))
    out.sort(key=lambda r: r[0])
    S = []
    for t, w in out:
        pos, q = w[:3], w[3:7]
        tip = _qrot(q, (blade_len, 0.0, 0.0))
        S.append({'t': t,
                  'guard': _v3(pos),
                  'tip': _v3((pos[0] + tip[0], pos[1] + tip[1], pos[2] + tip[2]))})
    return S


def find_swings(S, min_speed=5.0, min_frames=3, fps=24, gap=0.12):
    """Windows where the tip is moving fast enough to leave a trail.

    A sword is in motion most of a fight; a SLASH is the part an audience reads as a cut. 5 m/s at
    the tip is about the speed at which a real blade starts to blur, and below it a trail looks like
    a mistake rather than an effect."""
    if len(S) < 3:
        return []
    fast = []
    for i in range(1, len(S)):
        dt = S[i]['t'] - S[i - 1]['t']
        if dt <= 1e-6:
            continue
        v = (S[i]['tip'] - S[i - 1]['tip']).length / dt
        fast.append((i, v))
    runs, cur = [], None
    for i, v in fast:
        if v >= min_speed:
            if cur is None:
                cur = [i, i]
            else:
                cur[1] = i
        elif cur is not None:
            if S[i]['t'] - S[cur[1]]['t'] > gap:     # a short dip is still one swing
                runs.append(tuple(cur))
                cur = None
    if cur is not None:
        runs.append(tuple(cur))
    span = min_frames / fps
    return [(a, b) for a, b in runs if S[b]['t'] - S[a]['t'] >= span]


def swing_arc(S, a, b):
    """Fit a centre, radius, plane and signed sweep to one swing. None when it is not an arc."""
    pts = S[a:b + 1]
    if len(pts) < 3:
        return None
    centre = Vector((0, 0, 0))
    for p in pts:
        centre += p['guard']
    centre /= len(pts)
    d = [p['tip'] - centre for p in pts]
    radius = sum(v.length for v in d) / len(d)
    if radius < 0.3:
        return None
    # The plane the tip swept, as the summed turning of consecutive spokes. Summing (not averaging a
    # single cross product) keeps the dominant plane when the swing wobbles.
    n = Vector((0, 0, 0))
    for i in range(len(d) - 1):
        n += d[i].cross(d[i + 1])
    if n.length < 1e-6:
        return None
    n.normalize()
    # Basis in which increasing angle goes ex -> ez, matching crescent_bm's (cos a, 0, sin a).
    ex = (d[0] - n * d[0].dot(n))
    if ex.length < 1e-6:
        return None
    ex.normalize()
    ez = n.cross(ex).normalized()
    ey = ez.cross(ex).normalized()
    ang, prev, total = [], None, 0.0
    for v in d:
        a_i = math.atan2(v.dot(ez), v.dot(ex))
        if prev is not None:
            step = a_i - prev
            while step > math.pi:
                step -= 2 * math.pi
            while step < -math.pi:
                step += 2 * math.pi
            total += step
        prev = a_i
        ang.append(a_i)
    sweep = math.degrees(total)
    if abs(sweep) < 35:                              # a nudge, not a cut
        return None
    return {'centre': centre, 'radius': radius, 'sweep': max(-260.0, min(260.0, sweep)),
            'start': math.degrees(ang[0]), 'basis': Matrix((ex, ey, ez)).transposed(),
            't0': pts[0]['t'], 't1': pts[-1]['t'],
            'speed': max((pts[i + 1]['tip'] - pts[i]['tip']).length / max(1e-6, pts[i + 1]['t'] - pts[i]['t'])
                         for i in range(len(pts) - 1))}


def add_slashes(tl, fps, f0, f1, slash_fx, collection=None, min_speed=5.0, hold=6):
    """Put a slash on every real swing inside [f0, f1]. Returns what it made."""
    made = []
    for meta in tl.get('actors', []):
        aid = meta['id']
        if meta.get('hidden'):
            continue
        blade = (meta.get('weapon') or {}).get('bladeLen', 0.91)
        S = blade_samples(tl, aid, blade)
        for a, b in find_swings(S, min_speed=min_speed, fps=fps):
            arc = swing_arc(S, a, b)
            if not arc:
                continue
            start_f = int(round(arc['t0'] * fps))
            end_f = int(round(arc['t1'] * fps)) + hold
            if end_f < f0 or start_f > f1:
                continue
            r = slash_fx.make_slash(
                name=f'SLASH_{aid}_{start_f}',
                center=tuple(arc['centre']),
                radius=arc['radius'],
                sweep=abs(arc['sweep']),
                thickness=min(0.26, 0.10 + arc['radius'] * 0.10),
                colour='crimson' if meta.get('demonic') else 'amber',
                demonic=bool(meta.get('demonic')),
                frame_start=max(1, start_f + 1),
                frame_end=end_f + 1,
                start_angle=arc['start'],
                clockwise=arc['sweep'] < 0,
                strength=min(1.6, 0.6 + arc['speed'] / 25.0),
                collection=collection)
            # make_slash orients the arc from pitch/tilt/yaw; the plane was MEASURED, so the fitted
            # basis replaces those Euler angles outright.
            r['root'].rotation_euler = arc['basis'].to_euler('XYZ')
            made.append({'actor': aid, 'f0': start_f, 'f1': end_f,
                         'sweep': round(arc['sweep'], 1), 'radius': round(arc['radius'], 2),
                         'speed': round(arc['speed'], 1)})
    return made
