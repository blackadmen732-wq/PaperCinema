#!/usr/bin/env python3
"""BAKE EVENTS: picture, sound and camera cues from ONE contact measured on the FINAL bake.

    python3 tools/bake_events.py <film>        -> output/<film>.bake-events.json (+ output/<film>-sfx/*.wav)

Why: the mixer (engine/sound.mjs) took its automatic cues from output/<film>.events.json, written by the
browser engine from ITS motion, while the picture now comes from the production bake (blender/
production_bake.py), which differs by up to ~1 m during a cut. Here the contact is found on the swords that
are actually rendered: the drawing actor's baked katana (along its real curve) against the opponent's weapon
on its rendered path (the timeline weapon + sub-samples, which film_modular keys for a non-drawing actor).
Sampled 4x per frame. Everything that follows one blow reads this file:
  - the mixer:   node engine/sound.mjs --film film/<film>.json --events output/<film>.bake-events.json
  - the picture: contact frame for the hit-stop and the impact accent (tools/exchange_cut.sh)
Four separate sound layers, each placed from the bake, each triggered ONCE (no retrigger):
  draw scrape (slide -> clear), speed-apex whoosh (the tip's fastest moment before contact), contact
  transient (onset placed ON the contact), material tail (starts with the transient and rings on).
Every clip is trimmed to its own measured onset, so cue time = audible onset.
"""
import json
import math
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------- small vector/quaternion helpers
def qmul(a, b):
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return (w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2)


def qrot(q, v):                                  # q = (w, x, y, z)
    p = qmul(qmul(q, (0.0, *v)), (q[0], -q[1], -q[2], -q[3]))
    return p[1:]


def slerp(a, b, t):
    d = sum(x * y for x, y in zip(a, b))
    if d < 0:
        b, d = tuple(-x for x in b), -d
    if d > 0.9995:
        r = tuple(x + (y - x) * t for x, y in zip(a, b))
    else:
        th = math.acos(d)
        s = math.sin(th)
        r = tuple((math.sin((1 - t) * th) * x + math.sin(t * th) * y) / s for x, y in zip(a, b))
    n = math.sqrt(sum(x * x for x in r))
    return tuple(x / n for x in r)


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def seg_dist(p1, q1, p2, q2):
    """Closest distance between segments p1q1 and p2q2."""
    d1, d2, r = sub(q1, p1), sub(q2, p2), sub(p1, p2)
    a, e, f = sum(x * x for x in d1), sum(x * x for x in d2), sum(x * y for x, y in zip(d2, r))
    c, b = sum(x * y for x, y in zip(d1, r)), sum(x * y for x, y in zip(d1, d2))
    den = a * e - b * b
    s = 0.0 if den < 1e-12 else max(0.0, min(1.0, (b * f - c * e) / den))
    t = (b * s + f) / e if e > 1e-12 else 0.0
    if t < 0:
        t, s = 0.0, max(0.0, min(1.0, -c / a)) if a > 1e-12 else 0.0
    elif t > 1:
        t, s = 1.0, max(0.0, min(1.0, (b - c) / a)) if a > 1e-12 else 0.0
    c1 = add(p1, tuple(x * s for x in d1))
    c2 = add(p2, tuple(x * t for x in d2))
    return math.dist(c1, c2), c1


def three_to_blender(w):
    """Timeline weapon [x, y, z, qx, qy, qz, qw] (three.js) -> (pos, quat w,x,y,z) in Blender, as film_modular."""
    x, y, z, qx, qy, qz, qw = w
    return (x, -z, y), (qw, qx, -qz, qy)


# ---------------------------------------------------------------- audio helpers
def pcm(path, sr=48000):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-ac', '1', '-ar', str(sr), '-f', 's16le', '-'],
                         capture_output=True, check=True).stdout
    import array
    a = array.array('h')
    a.frombytes(raw)
    return a, sr


def onset(path, thresh_db=-30):
    """Seconds to the first 5 ms window louder than thresh_db relative to the file's peak."""
    a, sr = pcm(path)
    peak = max(1, max(abs(v) for v in a))
    lim = peak * 10 ** (thresh_db / 20)
    w = int(sr * 0.005)
    for i in range(0, len(a) - w, w):
        if max(abs(v) for v in a[i:i + w]) >= lim:
            return i / sr
    return 0.0


def cut(src, dst, start, length):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', '%.4f' % start, '-t', '%.4f' % length, '-i', src,
                    '-ac', '2', '-ar', '44100', dst], check=True)


def main(film):
    bake = json.load(open(os.path.join(REPO, 'output', film + '.bake.json')))
    TL = json.load(open(os.path.join(REPO, 'output', film + '.timeline.json')))
    F = json.load(open(os.path.join(REPO, 'film', film + '.json')))
    fps = TL['clock']['fps']
    perf = F['performances']
    hero = next(a for a, p in perf.items() if isinstance(p, dict) and p.get('draw'))
    foe = next(a for a in perf if a != hero)
    dr = perf[hero]['draw']
    L = float(dr.get('blade', 0.91))
    sori = 0.018
    R = L * L / (8 * sori) + sori / 2                # katana_real's circle
    foe_meta = next(a for a in TL['actors'] if a['id'] == foe)
    foe_len = float((foe_meta.get('weapon') or {}).get('bladeLen', 0.91)) * (1.15 if (foe_meta.get('weapon') or {}).get('kind') == 'bokken' else 1.0)

    sw = bake['actors'][hero]['sword']               # per visible frame: x, y, z, qw, qx, qy, qz (Blender)
    n = len(sw)

    def hero_blade(t_frame):
        i = max(0, min(n - 2, int(math.floor(t_frame))))
        u = max(0.0, min(1.0, t_frame - i))
        a, b = sw[i], sw[i + 1]
        p = tuple(a[k] + (b[k] - a[k]) * u for k in range(3))
        q = slerp(tuple(a[3:7]), tuple(b[3:7]), u)
        pts = []
        for j in range(9):                           # along the curved blade, guard to tip
            s = L * j / 8
            ang = s / R
            local = (R * math.sin(ang), R - R * math.cos(ang), 0.0)
            pts.append(add(p, qrot(q, local)))
        return pts

    # the opponent's rendered weapon: frames + sub-samples of the timeline (film time t)
    samples = []
    for fr in TL['frames']:
        a = fr['actors'].get(foe)
        if a and a.get('weapon'):
            samples.append((fr['t'], a['weapon']))
    for sf in TL.get('subframes') or []:
        a = (sf.get('actors') or {}).get(foe)
        if a and a.get('weapon'):
            samples.append((sf['t'], a['weapon']))
    samples.sort(key=lambda r: r[0])

    def foe_blade(t):
        k = 0
        while k + 1 < len(samples) and samples[k + 1][0] <= t:
            k += 1
        t0, w0 = samples[k]
        t1, w1 = samples[min(k + 1, len(samples) - 1)]
        u = 0.0 if t1 == t0 else max(0.0, min(1.0, (t - t0) / (t1 - t0)))
        p0, q0 = three_to_blender(w0)
        p1, q1 = three_to_blender(w1)
        p = tuple(p0[i] + (p1[i] - p0[i]) * u for i in range(3))
        q = slerp(q0, q1, u)
        return p, add(p, qrot(q, (foe_len, 0.0, 0.0)))

    # sweep the cut, 4 samples per frame
    best = (1e9, None, None)
    first = None
    speed = []
    prev_tip = None
    slide_f = dr['slide'] * fps
    THICK = 0.025                                   # half the katana's width + half the bokken's
    for k in range(int(slide_f * 4), (n - 1) * 4):
        tf = k / 4.0                                 # 0-based frame index (Blender frame = tf + 1)
        t = tf / fps
        hb = hero_blade(tf)
        fa, fb = foe_blade(t)
        dmin, where = 1e9, None
        for p0, p1 in zip(hb, hb[1:]):
            d_, c_ = seg_dist(p0, p1, fa, fb)
            if d_ < dmin:
                dmin, where = d_, c_
        if dmin < best[0]:
            best = (dmin, tf, where)
        if first is None and dmin <= THICK:
            first = (tf, dmin, where)
        tip = hb[-1]
        if prev_tip is not None:
            speed.append((tf, math.dist(tip, prev_tip) * fps * 4))
        prev_tip = tip
    contact = first or (best[1], best[0], best[2])
    # after the contact: does the katana go THROUGH the bokken (more than its thickness), and does it ever
    # enter the opponent's body (his capsules, from the same bake)?
    through = []
    segs_foe = bake['actors'][foe]['segs']
    body_hits = []
    for k in range(int(slide_f * 4), (n - 1) * 4):
        tf = k / 4.0
        hb = hero_blade(tf)
        if first and tf > first[0] + 0.5:
            fa, fb = foe_blade(tf / fps)
            d_ = min(seg_dist(p0, p1, fa, fb)[0] for p0, p1 in zip(hb, hb[1:]))
            if d_ < 0.005:
                through.append(round(tf + 1, 2))
        if k % 4 == 0:
            fi = int(tf)
            for nm, a, b, r in segs_foe[fi]:
                if nm.startswith('hand'):
                    continue
                for pt in hb:
                    d_, _c = seg_dist(pt, pt, tuple(a), tuple(b))
                    if d_ < r:
                        body_hits.append((fi + 1, nm, round((r - d_) * 100, 1)))
                        break
    if contact[0] is None:
        raise SystemExit('[events] no approach between the blades at all')
    tf_c, d_c, where = contact
    t_c = tf_c / fps
    frame_c = int(math.floor(tf_c)) + 1              # the Blender frame on which the blades meet
    apex = max((s for s in speed if s[0] < tf_c), key=lambda s: s[1])
    print('[events] %s vs %s: blades meet at frame %d (film %.4f s, sub-frame %.2f), gap %.1f cm%s' % (
        hero, foe, frame_c, t_c, tf_c + 1, d_c * 100, '' if first else '  (NO CONTACT: closest approach only)'))
    print('[events] katana through the bokken after the contact (<0.5 cm): %s' % (through[:12] or 'never'))
    print('[events] katana inside the opponent\'s body: %s' % (sorted({(f_, n_) for f_, n_, _d in body_hits})[:12] or 'never'))
    print('[events] tip speed apex before contact: %.1f m/s at frame %.2f (film %.4f s)' % (apex[1], apex[0] + 1, apex[0] / fps))

    # the four layers: clips trimmed to their own onset
    sfx = os.path.join(REPO, 'output', film + '-sfx')
    os.makedirs(sfx, exist_ok=True)
    lib = os.path.join(REPO, 'assets', 'sfx')
    layers = []
    o = onset(os.path.join(lib, 'steel-scrape.mp3'))
    scrape_len = dr['clear'] - dr['slide'] + 0.08
    cut(os.path.join(lib, 'steel-scrape.mp3'), os.path.join(sfx, 'scrape.wav'), o, scrape_len)
    layers.append({'id': 'draw-scrape', 'file': os.path.join(sfx, 'scrape.wav'), 't': round(dr['slide'], 4),
                   'len': round(scrape_len, 3), 'gain': 0.45, 'why': 'blade slides out: slide -> clear'})
    o = onset(os.path.join(lib, 'clash-light.mp3'))
    cut(os.path.join(lib, 'clash-light.mp3'), os.path.join(sfx, 'transient.wav'), o, 0.14)
    layers.append({'id': 'contact-transient', 'file': os.path.join(sfx, 'transient.wav'), 't': round(t_c, 4),
                   'len': 0.14, 'gain': 1.0, 'why': 'onset ON the measured contact'})
    o = onset(os.path.join(lib, 'impact.mp3'))
    cut(os.path.join(lib, 'impact.mp3'), os.path.join(sfx, 'tail.wav'), o, 1.3)
    layers.append({'id': 'material-tail', 'file': os.path.join(sfx, 'tail.wav'), 't': round(t_c, 4),
                   'len': 1.3, 'gain': 0.55, 'why': 'steel on wood body/ring, rings through any hit-stop, one trigger'})
    whoosh = {'id': 'apex-whoosh', 'earshot': 'whoosh_fast/whip', 't': round(apex[0] / fps, 4), 'apex': 0.2,
              'len': 0.6, 'gain': 0.5, 'why': "the whoosh's loudest point on the tip's fastest moment"}
    cached = os.path.join(lib, 'earshot', 'whoosh_fast_whip-0.6-0.2.wav')
    if os.path.exists(cached):                       # earshot itself is not installed here; its cached render is
        whoosh = {'id': 'apex-whoosh', 'file': cached, 't': round(apex[0] / fps - 0.2, 4), 'len': 0.6, 'gain': 0.5,
                  'why': whoosh['why'] + ' (cached earshot render, apex at 0.2 s)'}
    layers.insert(1, whoosh)
    out = {'source': 'final bake (production_bake) - not the browser events file', 'striker': hero, 'blocker': foe,
           'film': film, 'fps': fps,
           'contact': {'frame': frame_c, 'subframe': round(tf_c + 1, 2), 't': round(t_c, 4), 'gap_cm': round(d_c * 100, 1),
                       'where': [round(v, 3) for v in where], 'touch': bool(first)},
           'apex': {'frame': round(apex[0] + 1, 2), 't': round(apex[0] / fps, 4), 'mps': round(apex[1], 1)},
           'draw': {'slide': dr['slide'], 'clear': dr['clear']},
           'cues': layers, 'contacts': [round(t_c, 4)], 'impacts': [], 'stops': []}
    path = os.path.join(REPO, 'output', film + '.bake-events.json')
    json.dump(out, open(path, 'w'), indent=1)
    print('[events] ->', path)
    for c in layers:
        print('[events]   %-18s t=%.3f s (frame %.2f)  %s' % (c['id'], c['t'], c['t'] * fps + 1, c['why']))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'kojiro-exchange')


def where_at(film, frames):
    """Diagnostic: the hero blade (guard, middle, tip) and the foe's weapon (grip, tip) on the given frames."""
    import types
    bake = json.load(open(os.path.join(REPO, 'output', film + '.bake.json')))
    TL = json.load(open(os.path.join(REPO, 'output', film + '.timeline.json')))
    F = json.load(open(os.path.join(REPO, 'film', film + '.json')))
    hero = next(a for a, p in F['performances'].items() if isinstance(p, dict) and p.get('draw'))
    foe = next(a for a in F['performances'] if a != hero)
    sw = bake['actors'][hero]['sword']
    for f in frames:
        a = sw[f - 1]
        g = tuple(a[:3]); tip = add(g, qrot(tuple(a[3:7]), (0.91, 0, 0)))
        w = TL['frames'][f - 1]['actors'][foe]['weapon']
        p, q = three_to_blender(w)
        print('f%d hero guard %s tip %s | foe grip %s tip %s' % (f, [round(v, 2) for v in g], [round(v, 2) for v in tip],
              [round(v, 2) for v in p], [round(v, 2) for v in add(p, qrot(q, (1.05, 0, 0)))]))
