"""SHIMI (染み, "stain"): Paper Cinema's own paint-bleeding-into-paper simulator.

When a blade cuts the paper, red paint wells up along the cut and soaks into the paper the way ink soaks
into washi: it races along the fibres (feathered, hairy edges), runs downward with gravity, piles pigment up
at the drying edge (dark rims, the "coffee-ring" effect) and dries from glossy-wet to matte.

Model (a simplified wet-paper simulation in the spirit of watercolour/ink research such as Curtis et al. 1997
"Computer-Generated Watercolor" and Chu & Tai 2005 "MoXi: real-time ink dispersion in absorbent paper"):
  fibres  : a random fibre map gives each pixel a permeability and a fibre direction
  water W : flows to neighbours ∝ conductivity × (W_i − W_j); conductivity is higher ALONG fibres (anisotropy),
            plus a gravity bias downward; wet fronts "pin" (stop) where the paper stays dry → crisp-but-feathered edges
  pigment : suspended pigment P moves with the water (upwind); it deposits into the fibres D as water evaporates,
            faster where the water is thin → pigment collects at the edges (dark rims)
  colour  : paper colour × exp(−absorption × pigment) per channel (subtractive, like real paint), plus a wet sheen

Deterministic (seeded). Output: an RGBA frame sequence (shimi_*.png) plus 16-bit data maps (wet_* soaked water, film_* glossy surface paint,
pigment_*, everwet_*) for 3D shaders. v2: two water layers (surface film + capillary), saturation-limited wicking,
edge-driven evaporation, and a gravity direction field (--gravity-dir / --gravity-map) for UV space on 3D parts.
    python3 engine/shimi.py --out output/shimi/demo --frames 72 --size 512 --cut "0.15,0.25,0.85,0.7"
"""
import argparse, json, math, os
import numpy as np
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument('--out', default='output/shimi/demo')
ap.add_argument('--size', type=int, default=512)
ap.add_argument('--frames', type=int, default=72)
ap.add_argument('--steps', type=int, default=8, help='simulation steps per frame')
ap.add_argument('--cut', default='0.15,0.22,0.85,0.72', help='cut line(s) x0,y0,x1,y1 in 0..1 (y down); several cuts: separate with ;')
ap.add_argument('--stab', default='', help='stab wound(s) x,y,radius in 0..1; several: separate with ;')
ap.add_argument('--preset', default='', help='named scenario from PRESETS below (overrides cut/stab/gravity/bleed/paint)')
ap.add_argument('--paper', default='#e4d8bf')
ap.add_argument('--paint', default='vermilion', help='vermilion | crimson | ink')
ap.add_argument('--gravity', type=float, default=0.35, help='0 = flat on a table, 0.35 = standing paper')
ap.add_argument('--seed', type=int, default=7)
ap.add_argument('--bleed', type=float, default=1.0, help='how much paint wells out of the cut')
ap.add_argument('--gravity-dir', default='0,1', help='gravity direction on the sheet "gx,gy" (0,1 = down the image)')
ap.add_argument('--gravity-map', default='', help='.npy (N,N,2) per-texel gravity direction, e.g. baked from a 3D part in UV space')
ap.add_argument('--wound', default='', help='KIZU wound layer: graze | shallow-cut | deep-cut | stab (time-varying welling, beads, brush smear)')
ap.add_argument('--region', default='torso', help='KIZU body region: face | hand | torso | limb')
ap.add_argument('--depth', type=float, default=0.5, help='KIZU wound depth 0..1')
ap.add_argument('--blade-speed', type=float, default=0.8, help='KIZU blade speed 0..1 (faster = longer, thicker brush smear)')
ap.add_argument('--sharpness', type=float, default=0.9, help='KIZU blade sharpness 0..1 (sharp = later onset, freer flow)')
ap.add_argument('--fps', type=float, default=24)
ap.add_argument('--mm-per-px', type=float, default=0.35, help='paper size of one pixel (bead spacing and sizes are in mm)')
ap.add_argument('--drips', type=int, default=3, help='number of beads that get heavy and run down as separate drips')
a = ap.parse_args()

# Named scenarios: what a fight event produces on the paper. Any AI can call these by name.
PRESETS = {
    'kesa-cut':     dict(cut='0.15,0.22,0.85,0.72', stab='', gravity=0.35, bleed=1.0, paint='vermilion'),  # diagonal cut, standing body
    'heavy-drip':   dict(cut='0.2,0.3,0.8,0.36', stab='', gravity=0.45, bleed=1.1, paint='vermilion', drips=9),  # lots of paint: beads run down as drips
    'x-cut':        dict(cut='0.2,0.2,0.8,0.75;0.8,0.2,0.2,0.75', stab='', gravity=0.35, bleed=0.9, paint='crimson'),
    'tsuki-stab':   dict(cut='', stab='0.5,0.4,0.025', gravity=0.5, bleed=1.0, paint='vermilion', drips=2),           # thrust: point wound
    'table-flat':   dict(cut='0.15,0.5,0.85,0.5', stab='', gravity=0.0, bleed=1.0, paint='vermilion', drips=0),   # paper lying flat: spreads evenly
    'ink-wound':    dict(cut='0.25,0.25,0.75,0.75', stab='', gravity=0.3, bleed=1.0, paint='ink'),        # black sumi ink (cursed blade)
    'graze':        dict(cut='0.1,0.6,0.9,0.52', stab='', gravity=0.25, bleed=0.25, paint='vermilion', drips=0),
    # KIZU wound presets (time-varying, physically informed welling)
    'face-cut':     dict(cut='0.25,0.35,0.75,0.5', stab='', gravity=0.45, bleed=1.0, paint='vermilion', wound='shallow-cut', region='face', depth=0.45),
    'deep-kesa':    dict(cut='0.15,0.22,0.85,0.72', stab='', gravity=0.4, bleed=1.0, paint='vermilion', wound='deep-cut', region='torso', depth=0.8),
    'arm-graze':    dict(cut='0.1,0.55,0.9,0.45', stab='', gravity=0.2, bleed=1.6, paint='vermilion', wound='graze', region='limb', depth=0.45),
    'stab-wound':   dict(cut='', stab='0.5,0.4,0.02', gravity=0.45, bleed=1.0, paint='vermilion', wound='stab', region='torso', depth=0.7),   # light graze: thin line, little bleed
}
if a.preset:
    for k, v in PRESETS[a.preset].items():
        setattr(a, k, v)

rng = np.random.default_rng(a.seed)
N = a.size
os.makedirs(a.out, exist_ok=True)

# ------------------------------------------------------------------ paper: fibres
def blur(x, r):
    """Cheap separable box blur (repeated = Gaussian-like)."""
    for _ in range(3):
        k = 2 * r + 1
        c = np.cumsum(np.pad(x, ((r + 1, r), (0, 0)), mode='wrap'), axis=0)
        x = (c[k:] - c[:-k]) / k
        c = np.cumsum(np.pad(x, ((0, 0), (r + 1, r)), mode='wrap'), axis=1)
        x = (c[:, k:] - c[:, :-k]) / k
    return x

# fibre direction: a smooth random angle field; fibre density: thousands of short strokes
theta = blur(rng.standard_normal((N, N)), N // 24) * 9.0
fib = np.zeros((N, N), np.float32)
for _ in range(int(N * N / 90)):
    x, y = rng.integers(0, N, 2)
    ang = theta[y, x] + rng.normal(0, 0.35)
    L = rng.integers(6, 26)
    xs = (x + np.cos(ang) * np.arange(L)).astype(int) % N
    ys = (y + np.sin(ang) * np.arange(L)).astype(int) % N
    fib[ys, xs] += rng.uniform(0.6, 1.0)
fib = np.clip(fib, 0, None)   # not blurred: fibre-scale detail makes hairy edges
fib = fib / (fib.max() + 1e-6)
perm = 0.35 + 0.65 * np.clip(fib * 1.6 + blur(rng.random((N, N)), 6) * 0.4, 0, 1)   # permeability
sizing = blur(rng.random((N, N)), 3)                                               # resists wetting (pinning)
pin = 0.0004 + 0.009 * (sizing > np.percentile(sizing, 55))

# ------------------------------------------------------------------ paint sources: cuts (lines) and stabs (points)
yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
source = np.zeros((N, N), np.float32)
S_POS = np.full((N, N), -1.0, np.float32)     # position along the cut (0..1) for KIZU timing
LINE_MASK = np.zeros((N, N), np.float32)
SEGS = []
for seg in [c for c in a.cut.split(';') if c.strip()]:
    x0, y0, x1, y1 = [float(v) * N for v in seg.split(',')]
    dx, dy = x1 - x0, y1 - y0
    Lc = math.hypot(dx, dy)
    u = ((xx - x0) * dx + (yy - y0) * dy) / (Lc * Lc)
    dist = np.abs((xx - x0) * dy - (yy - y0) * dx) / Lc
    dist = np.abs(dist + blur(rng.standard_normal((N, N)), max(2, N // 64)) * N * 0.004)   # ragged, not a ruler line
    on_cut = (u > 0) & (u < 1)
    # the wound opens unevenly: more paint where the cut is deepest (middle)
    depth = np.maximum(np.sin(np.clip(u, 0, 1) * math.pi), 0) ** 0.7 * (0.6 + 0.8 * blur(rng.random((N, N)), 10))
    width = N * 0.0057 * (0.7 + 0.6 * blur(rng.random((N, N)), max(2, N // 40)))            # width varies along the cut
    line = np.where(on_cut, np.exp(-(dist / width) ** 2), 0.0).astype(np.float32)
    source += line * depth
    S_POS = np.where(line > LINE_MASK, np.clip(u, 0, 1), S_POS); LINE_MASK = np.maximum(LINE_MASK, line)
    SEGS.append((x0, y0, x1, y1))
for st in [c for c in a.stab.split(';') if c.strip()]:
    sx, sy, sr = [float(v) for v in st.split(',')]
    ragged = 1 + 0.45 * blur(rng.standard_normal((N, N)), max(2, N // 80)) * 6
    d2 = ((xx - sx * N) ** 2 + (yy - sy * N) ** 2) / (sr * N * 1.6) ** 2 * np.maximum(ragged, 0.3)
    source += (np.exp(-d2) * 1.2).astype(np.float32)
source = np.minimum(source, 1.0)   # overlapping cuts do not add up to black

# ------------------------------------------------------------------ drips: beads that get heavy and run
# Each drip starts on the wound, waits until its bead "fills", then runs down in stick-slip, wandering a little
# along the fibres and thinning until the paper has drunk it. The paint it leaves is then soaked by the simulation.
# ================================================================== KIZU (傷): the wound layer
# Decides HOW paint leaves a cut (SHIMI decides how the paper drinks it). Informed by how minor cuts really bleed
# (stylised as paint, see docs/SHIMI.md "KIZU"): an onset delay (shallow cuts show nothing for a moment), beads first
# that merge into a line, welling rate rising with depth (face bleeds freely), a dry-brush "swipe" the blade drags
# along its path in the first frames, and drips only when a bead grows heavy. Monotone curves only: no rhythm.
WOUNDS = {   # tau0 onset (s), t_r rise, t_d0 decay, Q amount, ooze o/t_o, bead spacing mm, merge (s), smear, max drips, film share
    'graze':       dict(tau0=0.9, tr=0.5, td0=0.4, Q=0.25, o=0.10, to=2.0, lam=7, merge=None, smear=1.0, drips=0, film=0.15),
    'shallow-cut': dict(tau0=0.5, tr=0.25, td0=0.9, Q=0.6, o=0.06, to=3.0, lam=5, merge=1.1, smear=0.6, drips=1, film=0.45),
    'deep-cut':    dict(tau0=0.12, tr=0.12, td0=2.0, Q=1.1, o=0.08, to=4.0, lam=8, merge=0.3, smear=0.8, drips=3, film=0.75),
    'stab':        dict(tau0=0.3, tr=0.2, td0=1.5, Q=1.0, o=0.05, to=3.0, lam=0, merge=0.0, smear=0.2, drips=1, film=0.6),
}
REGIONS = {'face': (1.6, 1.3, 1), 'hand': (1.3, 1.0, 3), 'torso': (1.0, 1.0, 3), 'limb': (0.8, 0.8, 3)}   # rate R, duration ×, max drips
KZ = None
if a.wound:
    wp = WOUNDS[a.wound]; R, dur, rdrips = REGIONS[a.region]
    sp = np.clip(S_POS, 0, 1)
    dloc = np.minimum(1.0, a.depth * 1.9 * sp ** 0.6 * (1 - sp) ** 1.2) if a.wound != 'stab' else np.full((N, N), a.depth, np.float32)
    T_blade = 2.5 / a.fps
    onset = sp * T_blade + wp['tau0'] * (1 - 0.7 * dloc) * (0.7 + 0.6 * a.sharpness) / R
    onset = onset * (1 + 0.15 * blur(rng.standard_normal((N, N)), max(2, N // 50)) * 4)
    td = wp['td0'] * (0.5 + dloc) * dur
    tt = np.linspace(0, 6, 600)[:, None]                       # normalise the rise × decay peak to 1
    peak = float(((1 - np.exp(-tt / wp['tr'])) * np.exp(-tt / (wp['td0'] * 1.0))).max())
    # bead seeds along the cut (graze: 2-D scatter of pinpoint dots)
    bead_mask = np.zeros((N, N), np.float32)
    lam_px = max(3.0, wp['lam'] / a.mm_per_px) if wp['lam'] else 0
    if a.wound == 'graze':
        band = blur((LINE_MASK > 0.05).astype(np.float32), max(2, N // 40)) > 0.05
        pts = rng.random((N, N)) < (1.0 / max(lam_px, 4) ** 2) * 9.0
        bead_mask = np.minimum(blur((band & pts).astype(np.float32), 1) * 9, 1.0)   # pinpoint dots that never fully merge
    elif lam_px:
        for (x0, y0, x1, y1) in SEGS:
            n = max(2, int(math.hypot(x1 - x0, y1 - y0) / lam_px))
            for i in range(n):
                f = (i + 0.5 + rng.uniform(-0.25, 0.25)) / n
                bx, by = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
                bead_mask += np.exp(-(((xx - bx) ** 2 + (yy - by) ** 2) / (0.35 * lam_px) ** 2)).astype(np.float32)
        bead_mask = np.minimum(bead_mask, 1.0)
    else:
        bead_mask = np.ones((N, N), np.float32)
    base = np.maximum(LINE_MASK, (source > 0.05) * source) if a.wound != 'graze' else bead_mask
    if a.wound == 'graze': dloc = np.maximum(dloc, 0.35 * (bead_mask > 0.05))
    # dry-brush smear along the blade path: streaks across the width, constant along the path, matte (soaks at once)
    if SEGS:
        x0, y0, x1, y1 = SEGS[0]
        ddx_, ddy_ = (x1 - x0), (y1 - y0); Lb = math.hypot(ddx_, ddy_)
        ub = ((xx - x0) * ddx_ + (yy - y0) * ddy_) / (Lb * Lb)
        across = ((xx - x0) * ddy_ - (yy - y0) * ddx_) / Lb
        wpx = (1.5 + 1.5 * (1 - a.sharpness)) / a.mm_per_px
        streak = 0.5 + 0.5 * np.cos(across * 2.4 + 3 * blur(rng.standard_normal((N, N)), max(1, N // 128)))
        Ls = 0.25 + 0.5 * a.blade_speed
        past = np.clip(ub - 0.33, 0, None)
        smear = (wp['smear'] * (0.3 + 0.7 * a.blade_speed) * np.exp(-past / Ls) * streak * np.exp(-(across / wpx) ** 2)
                 * ((ub > -0.02) & (ub < 1.12))).astype(np.float32)
    else:
        smear = np.zeros((N, N), np.float32); ub = np.zeros((N, N), np.float32)
    KZ = dict(wp=wp, R=R, dloc=dloc, onset=onset, td=td, peak=peak, bead=bead_mask, base=base, smear=smear, ub=ub, T_blade=T_blade)
    a.drips = min(wp['drips'], rdrips) if a.drips == 3 else a.drips

drips = []
if a.gravity > 0 and a.drips > 0:
    ys_, xs_ = np.nonzero(source > 0.35 * source.max())
    for i in range(a.drips):
        j = rng.integers(0, len(ys_))
        col = xs_ == xs_[j]
        drips.append(dict(x=float(xs_[j]), y=float(ys_[col].max()) + N * 0.01, wx=0.0, v=rng.uniform(0.8, 1.4) * a.gravity * 1.6,
                          load=rng.uniform(0.7, 1.3), start=int(rng.uniform(0.08, 0.45) * a.frames * a.steps), slip=rng.uniform(0, 6.28)))
        if KZ is not None:                                      # a bead lets go only after it has grown heavy
            t_heavy = float(KZ['onset'][ys_[j], xs_[j]]) + 0.6 / (KZ['wp']['Q'] * KZ['R'] * max(float(KZ['dloc'][ys_[j], xs_[j]]), 0.2))
            drips[-1]['start'] = int(t_heavy * a.fps * a.steps)

PAINTS = {   # absorption per channel (R, G, B): high G/B absorption = red
    'vermilion': np.array([0.25, 3.2, 3.6], np.float32),
    'crimson':   np.array([0.3, 3.4, 2.9], np.float32),
    'ink':       np.array([3.2, 3.2, 3.0], np.float32),
}
absorb = PAINTS[a.paint]
paper = np.array([int(a.paper[i:i + 2], 16) / 255 for i in (1, 3, 5)], np.float32)

W = np.zeros((N, N), np.float32)   # capillary water INSIDE the paper (darkens it, lets light through)
S = np.zeros((N, N), np.float32)   # surface film ON the paper (glossy paint that beads, runs and drips)
P = np.zeros((N, N), np.float32)   # suspended pigment
D = np.zeros((N, N), np.float32)   # deposited pigment (in the fibres)
EVERWET = np.zeros((N, N), bool)

# gravity direction field (per texel). Uniform by default; a baked map lets a 3D part's UV space have its own "down".
if a.gravity_map:
    gm = np.load(a.gravity_map).astype(np.float32)
    gx, gy = gm[..., 0], gm[..., 1]
else:
    g0 = np.array([float(v) for v in a.gravity_dir.split(',')], np.float32); g0 /= (np.linalg.norm(g0) + 1e-9)
    gx, gy = np.full((N, N), g0[0], np.float32), np.full((N, N), g0[1], np.float32)
gl = np.sqrt(gx * gx + gy * gy) + 1e-9
gx, gy = gx / gl, gy / gl

# neighbour directions with their angle, for fibre anisotropy
DIRS = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]
cond = []
for (ddy, ddx) in DIRS:
    ang = math.atan2(ddy, ddx)
    along = np.cos(theta - ang) ** 2                           # 1 when the step follows the fibre
    c = perm * (0.02 + 2.6 * along * fib ** 2)                 # fibres carry liquid much faster (hairy edges)
    c /= math.hypot(ddx, ddy)
    gdot = (ddx * gx + ddy * gy) / math.hypot(ddx, ddy)          # how "downhill" this step is
    c = c * (1 + 0.5 * a.gravity * np.clip(gdot, 0, None)) * (1 - a.gravity * 0.3 * np.clip(-gdot, 0, None))
    cond.append(c.astype(np.float32))

def shift(x, ddy, ddx):
    """Move a field by (ddy, ddx) WITHOUT wrapping: what leaves the sheet is gone, nothing re-enters."""
    y = np.roll(np.roll(x, ddy, 0), ddx, 1)
    if ddy > 0: y[:ddy, :] = 0
    if ddy < 0: y[ddy:, :] = 0
    if ddx > 0: y[:, :ddx] = 0
    if ddx < 0: y[:, ddx:] = 0
    return y

# flow is only allowed toward neighbours that are on the sheet
inside = {}
for (ddy, ddx) in [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]:
    m = np.ones((N, N), np.float32)
    if ddy > 0: m[-ddy:, :] = 0
    if ddy < 0: m[:-ddy, :] = 0
    if ddx > 0: m[:, -ddx:] = 0
    if ddx < 0: m[:, :-ddx] = 0
    inside[(ddy, ddx)] = m

total_steps = a.frames * a.steps
CAP = 0.22 * perm                                  # how much liquid the paper itself can hold
edge = np.zeros((N, N), np.float32)
frames_meta = []
for frame in range(a.frames):
    for s in range(a.steps):
        k = frame * a.steps + s
        # 1. the cut wells paint onto the SURFACE (glossy film), fading smoothly (no pulse: it would read as a heartbeat)
        if KZ is None:
            well = a.bleed * max(0.0, 1 - k / ((0.15 + 0.25 * min(a.bleed, 1)) * total_steps)) ** 1.5
            S += source * 0.20 * well
            W += source * 0.04 * well
            P += source * 0.09 * well
        else:
            tsec = k / (a.fps * a.steps)
            wp = KZ['wp']
            tau = np.maximum(tsec - KZ['onset'], 0)
            on = tsec > KZ['onset']
            q = wp['Q'] * KZ['R'] * KZ['dloc'] ** 1.5 * ((1 - np.exp(-tau / wp['tr'])) * np.exp(-tau / KZ['td']) / KZ['peak'] + wp['o'] * np.exp(-tau / wp['to'])) * on
            if wp['merge'] is None: m = 0.0
            else: m = min(1.0, max(0.0, (tsec - float(KZ['onset'].min())) / max(wp['merge'], 1e-3)))
            mask = KZ['base'] * ((1 - m) * KZ['bead'] + m)
            liquid = q * mask * 0.2 * a.bleed
            S += liquid * wp['film']; W += liquid * (1 - wp['film']); P += liquid * 0.375 * 1.2
            # the blade's dry-brush swipe: f0–f3, advancing with the tip, absorbed at once (matte)
            if tsec < KZ['T_blade'] * 1.4:
                front = (tsec / KZ['T_blade']) * 1.12
                stamp = KZ['smear'] * (KZ['ub'] < front) * (0.08 / max(1, int(KZ['T_blade'] * 1.4 * a.fps * a.steps)))
                W += stamp * 4.0; P += stamp * 3.0
        # 2. soak-in: the paper drinks the surface film until it is saturated (CAP)
        soak = np.minimum(S, 0.045 * perm * np.maximum(CAP - W, 0))   # slower soak: beads and drips live long enough to run
        S -= soak; W += soak
        # 3. capillary flow inside the paper: dry paper resists (saturation-dependent) → fast front that slows down (≈ √t)
        sat = np.clip(W / CAP, 0, 1)
        conc = np.where(W + S > 1e-5, P / np.maximum(W + S, 1e-5), 0)
        dW = np.zeros_like(W); dP = np.zeros_like(P)
        for (ddy, ddx), c in zip(DIRS, cond):
            Wn = shift(W, -ddy, -ddx)
            flow = c * np.maximum(W - Wn - pin, 0) * (0.05 + 0.3 * sat ** 1.5)
            flow = np.minimum(flow, W * 0.11) * inside[(ddy, ddx)]
            dW -= flow; dW += shift(flow, ddy, ddx)
            pflow = flow * conc * 0.5 * (W > 0.012)              # pigment lags the water: a pale damp halo runs ahead
            dP -= pflow; dP += shift(pflow, ddy, ddx)
        # 4. rivulets: surface film thicker than it can hold runs DOWNHILL along the gravity field
        if a.gravity > 0:
            run = np.maximum(S - 0.03, 0) * a.gravity * 0.25
            prun = run * conc
            wsum = np.zeros_like(S)
            ws = []
            for (ddy, ddx) in DIRS:
                w_ = np.clip((ddx * gx + ddy * gy) / math.hypot(ddx, ddy), 0, None) ** 4 * inside[(ddy, ddx)]
                ws.append(w_); wsum += w_
            wsum = np.maximum(wsum, 1e-6)
            for (ddy, ddx), w_ in zip(DIRS, ws):
                f = run * w_ / wsum; pf = prun * w_ / wsum
                S -= f; S += shift(f, ddy, ddx)
                dP -= pf; dP += shift(pf, ddy, ddx)
        W += dW; P += dP
        # drips: run down, leaving a thin wet trail of paint
        for dr in drips:
            if k < dr['start'] or dr['load'] <= 0.02: continue
            dr['slipn'] = dr.get('slipn', 0.5) * 0.92 + rng.uniform(0, 1) * 0.08   # stick-slip: seeded, irregular (no rhythm)
            stick = 0.3 + 1.1 * dr['slipn']
            gyx = (gx[int(dr['y']) % N, int(dr['x']) % N], gy[int(dr['y']) % N, int(dr['x']) % N])
            dr['wx'] = dr['wx'] * 0.9 + rng.normal(0, 0.06)                # zero-mean, damped wander
            dr['y'] += dr['v'] * stick * gyx[1] - dr['wx'] * gyx[0]
            dr['x'] += dr['v'] * stick * gyx[0] + dr['wx'] * gyx[1]
            if not (0 <= dr['x'] < N - 1): dr['load'] = 0; continue
            if dr['y'] >= N - 3: dr['load'] = 0; continue
            iy, ix = int(dr['y']), int(dr['x'])
            r = max(1, int(N * 0.008 * (0.6 + 0.6 * dr['load'])))         # soft disc, fatter while loaded (bead head)
            ys0, ys1, xs0, xs1 = max(iy - r, 0), min(iy + r + 1, N), max(ix - r, 0), min(ix + r + 1, N)
            disc = np.exp(-(((yy[ys0:ys1, xs0:xs1] - dr['y']) ** 2 + (xx[ys0:ys1, xs0:xs1] - dr['x']) ** 2) / (r * r)))
            amt = 0.09 * dr['load']
            S[ys0:ys1, xs0:xs1] += amt * disc                              # a drip is surface paint
            P[ys0:ys1, xs0:xs1] += amt * 0.9 * disc
            dr['load'] *= 0.99                                            # the paper drinks the bead as it runs
            dr['v'] *= 0.997
            if dr['load'] <= 0.02:                                        # the bead stops: a final fat drop
                S[ys0:ys1, xs0:xs1] += 0.25 * disc; P[ys0:ys1, xs0:xs1] += 0.22 * disc
        np.maximum(W, 0, out=W); np.maximum(S, 0, out=S); np.maximum(P, 0, out=P)
        EVERWET |= W > 0.004
        # 3. evaporation: thin water dries faster → pigment deposits at the edges (dark rims)
        # 5. evaporation, faster at the EDGE of the wet area (the centre refills the edge and carries pigment out:
        #    the coffee-ring / tide line). Surface film dries slowly (it is paint, it mostly soaks in).
        if k % 4 == 0:
            edge = 1 - blur((W > 0.004).astype(np.float32), max(1, N // 100))
        thin = np.exp(-W / 0.05)
        evap = (0.0003 + 0.0026 * thin) * (1 + 1.2 * edge)
        dep = P * np.clip(0.002 + 0.05 * thin * (1 + edge), 0, 1) * (S < 0.01)
        D += dep; P -= dep
        W = np.maximum(W - evap * (W > 0), 0)
        S = np.maximum(S - 0.00015, 0)
    # ---- colour (subtractive pigment + wet sheen + fibre texture)
    pig_raw = D + 0.6 * P
    pig = 0.7 * (1 - np.exp(-pig_raw / 0.7))          # saturates like real paint: no black cores
    col = paper[None, None, :] * np.exp(-absorb[None, None, :] * pig[..., None] * 1.6)
    tex = (0.86 + 0.2 * fib)[..., None]                # fibre texture shows in the colour
    wet = np.clip(W * 6, 0, 1)[..., None]
    film = np.clip(S * 12, 0, 1)[..., None]
    col = col * tex * (1 - 0.18 * wet) * (1 - 0.1 * film) + 0.16 * film * np.array([1, 0.92, 0.9], np.float32)   # soaked = darker, surface film = glossy highlight
    alpha = np.clip(pig * 3 + wet[..., 0] * 0.6, 0, 1)
    img = np.dstack([np.clip(col, 0, 1), alpha])
    Image.fromarray((img * 255).astype(np.uint8), 'RGBA').save(f'{a.out}/shimi_{frame:04d}.png')
    # data maps (16-bit) for the 3D paper shader: wetness → translucency/gloss, pigment → colour, everwet → tide line
    for nm, field, scale in (('wet', W, 6.0), ('film', S, 12.0), ('pigment', pig, 3.0), ('everwet', EVERWET.astype(np.float32), 1.0)):
        Image.fromarray((np.clip(field * scale, 0, 1) * 65535).astype(np.uint16)).save(f'{a.out}/{nm}_{frame:04d}.png')
    front = float(np.sqrt((W > 0.004).sum() / max(1.0, float((source > 0.1).sum()) ** 0.5)))   # rough front distance (px)
    frames_meta.append({'frame': frame, 'wet_area': float((W > 0.004).mean()), 'stain_area': float((pig > 0.05).mean()), 'film_area': float((S > 0.01).mean()), 'front_px': front})

json.dump({'args': vars(a), 'frames': frames_meta}, open(f'{a.out}/shimi.json', 'w'), indent=1)
print(f'wrote {a.frames} frames to {a.out}/ (stain covers {frames_meta[-1]["stain_area"] * 100:.1f}% of the sheet)')
