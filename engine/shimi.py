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

Deterministic (seeded). Output: an RGBA frame sequence (shimi_*.png) plus 16-bit data maps (wet_*, pigment_*, everwet_*) for 3D shaders.
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
ap.add_argument('--cut', default='0.15,0.22,0.85,0.72', help='cut line x0,y0,x1,y1 in 0..1 (y down)')
ap.add_argument('--paper', default='#e4d8bf')
ap.add_argument('--paint', default='vermilion', help='vermilion | crimson | ink')
ap.add_argument('--gravity', type=float, default=0.35, help='0 = flat on a table, 0.35 = standing paper')
ap.add_argument('--seed', type=int, default=7)
ap.add_argument('--bleed', type=float, default=1.0, help='how much paint wells out of the cut')
a = ap.parse_args()

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
fib = np.clip(blur(fib, 1), 0, None)
fib = fib / (fib.max() + 1e-6)
perm = 0.35 + 0.65 * np.clip(fib * 1.6 + blur(rng.random((N, N)), 6) * 0.4, 0, 1)   # permeability
sizing = blur(rng.random((N, N)), 3)                                               # resists wetting (pinning)
pin = 0.0004 + 0.009 * (sizing > np.percentile(sizing, 55))

# ------------------------------------------------------------------ paint source: along the cut
x0, y0, x1, y1 = [float(v) * N for v in a.cut.split(',')]
yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
dx, dy = x1 - x0, y1 - y0
Lc = math.hypot(dx, dy)
u = ((xx - x0) * dx + (yy - y0) * dy) / (Lc * Lc)
dist = np.abs((xx - x0) * dy - (yy - y0) * dx) / Lc
on_cut = (u > 0) & (u < 1)
# the wound opens unevenly: more paint where the cut is deepest (middle)
depth = np.maximum(np.sin(np.clip(u, 0, 1) * math.pi), 0) ** 0.7 * (0.6 + 0.8 * blur(rng.random((N, N)), 10))
source = np.where(on_cut, np.exp(-(dist / 2.2) ** 2) * depth, 0.0).astype(np.float32)

PAINTS = {   # absorption per channel (R, G, B): high G/B absorption = red
    'vermilion': np.array([0.25, 3.2, 3.6], np.float32),
    'crimson':   np.array([0.9, 4.2, 3.4], np.float32),
    'ink':       np.array([3.2, 3.2, 3.0], np.float32),
}
absorb = PAINTS[a.paint]
paper = np.array([int(a.paper[i:i + 2], 16) / 255 for i in (1, 3, 5)], np.float32)

W = np.zeros((N, N), np.float32)   # water (wetness)
P = np.zeros((N, N), np.float32)   # suspended pigment
D = np.zeros((N, N), np.float32)   # deposited pigment (in the fibres)
EVERWET = np.zeros((N, N), bool)

# neighbour directions with their angle, for fibre anisotropy
DIRS = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]
cond = []
for (ddy, ddx) in DIRS:
    ang = math.atan2(ddy, ddx)
    along = np.cos(theta - ang) ** 2                           # 1 when the step follows the fibre
    c = perm * (0.06 + 2.4 * along * fib ** 1.5)               # fibres carry liquid much faster (hairy edges)
    c /= math.hypot(ddx, ddy)
    if ddy > 0: c *= (1 + a.gravity * ddy)                      # gravity: easier downhill (y down)
    if ddy < 0: c *= (1 - a.gravity * 0.6)
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
frames_meta = []
for frame in range(a.frames):
    for s in range(a.steps):
        k = frame * a.steps + s
        # 1. the cut wells paint for the first ~40% of the shot, in fading pulses
        well = a.bleed * max(0.0, 1 - k / (0.4 * total_steps)) ** 1.5   # smooth decay (no pulsing: pulses read as a heartbeat)
        W += source * 0.22 * well
        P += source * 0.09 * well
        # 2. water flows to neighbours (only where there is more water than the neighbour; wet fronts pin)
        conc = np.where(W > 1e-5, P / np.maximum(W, 1e-5), 0)
        dW = np.zeros_like(W); dP = np.zeros_like(P)
        for (ddy, ddx), c in zip(DIRS, cond):
            Wn = shift(W, -ddy, -ddx)                            # neighbour in direction (ddy, ddx)
            flow = c * np.maximum(W - Wn - pin, 0) * 0.2         # flow out of this cell toward that neighbour
            flow = np.minimum(flow, W * 0.11) * inside[(ddy, ddx)]
            dW -= flow; dW += shift(flow, ddy, ddx)
            pflow = flow * conc                                  # pigment rides with the water (upwind)
            dP -= pflow; dP += shift(pflow, ddy, ddx)
        # rivulets: where paint pools thicker than the paper can hold, gravity pulls it straight down
        if a.gravity > 0:
            run = np.maximum(W - 0.035, 0) * a.gravity * 0.35 * perm * inside[(1, 0)]
            prun = run * conc
            dW -= run; dW += shift(run, 1, 0)
            dP -= prun; dP += shift(prun, 1, 0)
        W += dW; P += dP
        np.maximum(W, 0, out=W); np.maximum(P, 0, out=P)
        EVERWET |= W > 0.004
        # 3. evaporation: thin water dries faster → pigment deposits at the edges (dark rims)
        thin = np.exp(-W / 0.05)
        evap = 0.0003 + 0.0035 * thin
        dep = P * np.clip(0.002 + 0.05 * thin, 0, 1)
        D += dep; P -= dep
        W = np.maximum(W - evap * (W > 0), 0)
    # ---- colour (subtractive pigment + wet sheen + fibre texture)
    pig = D + 0.6 * P
    col = paper[None, None, :] * np.exp(-absorb[None, None, :] * pig[..., None] * 1.6)
    tex = (0.94 + 0.06 * fib)[..., None]
    wet = np.clip(W * 6, 0, 1)[..., None]
    col = col * tex * (1 - 0.18 * wet) + 0.10 * wet * np.array([1, 0.9, 0.85], np.float32)   # wet = darker + glossy
    alpha = np.clip(pig * 3 + wet[..., 0] * 0.6, 0, 1)
    img = np.dstack([np.clip(col, 0, 1), alpha])
    Image.fromarray((img * 255).astype(np.uint8), 'RGBA').save(f'{a.out}/shimi_{frame:04d}.png')
    # data maps (16-bit) for the 3D paper shader: wetness → translucency/gloss, pigment → colour, everwet → tide line
    for nm, field, scale in (('wet', W, 6.0), ('pigment', pig, 3.0), ('everwet', EVERWET.astype(np.float32), 1.0)):
        Image.fromarray((np.clip(field * scale, 0, 1) * 65535).astype(np.uint16)).save(f'{a.out}/{nm}_{frame:04d}.png')
    frames_meta.append({'frame': frame, 'wet_area': float((W > 0.004).mean()), 'stain_area': float((pig > 0.05).mean())})

json.dump({'args': vars(a), 'frames': frames_meta}, open(f'{a.out}/shimi.json', 'w'), indent=1)
print(f'wrote {a.frames} frames to {a.out}/ (stain covers {frames_meta[-1]["stain_area"] * 100:.1f}% of the sheet)')
