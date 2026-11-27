"""VILLAGE KIT: the pieces of an Edo-period street (Mark, 27 Nov: "a full village... detailed"; the look board's
night duel: lanterns, lit paper windows, red banners, blossom).

    minka         thatched farmhouse: posts on foundation stones, earthen walls, a doma entrance, shoji bays, veranda,
                  a thick steep straw hip roof with crossed ridge sticks
    machiya       two-storey town house: wooden lattice front, noren curtain, tiled pent roof, clay-slat upper windows,
                  tiled gable roof along the street, a paper lantern by the door
    well          wooden well crib (igeta), posts with a little tiled roof, a pulley, rope and bucket
    bamboo_fence  takegaki: 'kenninji' (solid split bamboo) or 'yotsume' (open lattice), tied with black cord
    stall         market stall (yatai): counter, board roof, noren, goods, a hanging paper lantern
    nobori        a tall street banner on a bamboo pole (cloth that sways in the film's wind via the set's pose)
    chochin       a hanging paper lantern that lights the ground under it
    ph_prop       a Poly Haven model (CC0, library/polyhaven.json "models") in the paper-craft look: reduced to flat
                  facets, its own photo textures kept; `count` copies scattered, kept off the fight marks

Registered into kit.KIT (kit.py imports this module at its end): local metres, Z up, the front faces -Y, built from
the same MB mesh builder and material keys (new keys: thatch, thatch_dark, thatch_edge, noren_indigo, banner_white).
"""
import math
import os

import kit as K
from kit import M4, MB, beam_between, gable_roof, piece, tile_patch

if K.HAVE_BPY:
    import bmesh
    import bpy
    from mathutils import Vector, noise
    import paper_materials as pm

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# --------------------------------------------------------------------------- materials
_base_M = getattr(K, '_M', None)


def _village_M():
    d = _base_M()
    d.update({
        # straw: grain down the slope (Z), the Poly Haven thatch photo over it when the set turns the layer on
        'thatch': (pm.wood_material, dict(color=(0.30, 0.22, 0.11), color2=(0.15, 0.10, 0.05), axis='Z', grain=1.4,
                                          rough=0.92, wear=0.0, ph='thatch')),
        'thatch_dark': (pm.wood_material, dict(color=(0.10, 0.075, 0.045), color2=(0.05, 0.035, 0.02), axis='X',
                                               rough=0.9, wear=0.0, ph='thatch')),
        'thatch_edge': (pm.wood_material, dict(color=(0.42, 0.33, 0.18), color2=(0.25, 0.18, 0.09), axis='Y', grain=2.0,
                                               rough=0.9, wear=0.0, ph='thatch')),
        'noren_indigo': (pm.paper_material, dict(color=(0.02, 0.035, 0.09), translucency=0.15, fibre_scale=60)),
        'banner_white': (pm.paper_material, dict(color=(0.78, 0.75, 0.68), translucency=0.35, fibre_scale=60)),
    })
    return d


if K.HAVE_BPY:
    K._M = _village_M


def _post(mb, rnd, x, y, h, wood='wood_post', w=0.15):
    """A post standing on its foundation stone (sesshi-ishi)."""
    mb.stone('stone_mossy', (0.36, 0.36, 0.22), M4((x, y, 0.07)), rnd, square=0.5, bulge=0.0, chip=0.06, flat_back=False)
    mb.box(wood, (w, w, h - 0.17), loc=(x, y, 0.17 + (h - 0.17) / 2))


def thatch_roof(mb, W, D, z0, *, pitch=50.0, overhang=0.95, thick=0.5, rnd=None, lump=0.06, sticks=True,
                key='thatch', edge='thatch_edge', under='wood_dark', cap='thatch_dark'):
    """A thick straw hip roof over a W x D plan (W along X), eave at z0: four slopes of one pitch to a ridge, a
    `thick` cut eave edge (trimmed straw ends), a dark underside, lumpy bundles that keep the hips and eaves
    straight, a ridge cap with crossed ridge sticks (karasu-odori)."""
    ow, od = W / 2 + overhang, D / 2 + overhang
    t = math.tan(math.radians(pitch))
    zr = z0 + od * t
    r = max(0.0, ow - od)
    E = [Vector((-ow, -od, z0)), Vector((ow, -od, z0)), Vector((ow, od, z0)), Vector((-ow, od, z0))]
    R0, R1 = Vector((-r, 0, zr)), Vector((r, 0, zr))
    seed = Vector((rnd.uniform(-50, 50), rnd.uniform(-50, 50), 0)) if rnd else Vector()
    slopes = [(E[0], E[1], R0, R1), (E[1], E[2], R1, R1), (E[2], E[3], R1, R0), (E[3], E[0], R0, R0)]
    for k, (a, b, c, d) in enumerate(slopes):
        nrm = (b - a).cross((c + d) / 2 - (a + b) / 2).normalized()

        def surf(u, v, a=a, b=b, c=c, d=d, nrm=nrm, sink=0.0):
            p = a.lerp(b, u).lerp(c.lerp(d, u), v)
            win = math.sin(math.pi * u) * math.sin(math.pi * min(1.0, v * 1.05))
            bump = noise.noise(p * 1.7 + seed) * lump + math.sin(v * 9 * math.pi) * lump * 0.25
            return p + nrm * (bump * win - sink)
        nu = max(6, int((b - a).length / 0.45))
        nv = max(5, int(((c + d) / 2 - (a + b) / 2).length / 0.45))
        mb.grid(key, surf, nu, nv, lambda i, j: (i * 31 + j * 17) % 97 / 97.0)
        # the underside: the same slope `thick` lower, facing down (rafters in shadow)
        mb.grid(under, lambda u, v, s=surf: s(1 - u, v) - Vector((0, 0, thick)), nu, nv)
    # the cut eave edge all round
    for i in range(4):
        a, b = E[i], E[(i + 1) % 4]
        dn = Vector((0, 0, thick))
        mb.poly(edge, [a - dn, b - dn, b, a])
    # ridge cap + crossed sticks
    L = 2 * r + 0.7
    mb.box(cap, (L, 0.55, 0.32), loc=(0, 0, zr + 0.06))
    mb.box(cap, (L + 0.1, 0.36, 0.2), loc=(0, 0, zr + 0.26))
    if sticks:
        n = max(2, int(L / 0.7))
        for i in range(n):
            x = -L / 2 + 0.25 + (L - 0.5) * i / max(1, n - 1)
            for s in (-1, 1):
                mb.box('wood_dark', (0.05, 0.05, 0.75), loc=(x, 0, zr + 0.38), rot=(s * 38, 0, 0))
    return zr


def _shoji_bay(mb, rnd, x0, x1, z0, z1, y, lit, axis='X', sign=-1):
    """A paper screen bay: glowing or plain paper card behind a wooden kumiko grid, flush with the wall face."""
    at = (lambda x, yy, z: (x, yy, z)) if axis == 'X' else (lambda x, yy, z: (yy, x, z))
    w, h = x1 - x0, z1 - z0
    key = 'window_glow' if rnd.random() < lit else 'shoji'
    mb.box(key, (w, 0.02, h) if axis == 'X' else (0.02, w, h), loc=at((x0 + x1) / 2, y, (z0 + z1) / 2))
    cols, rows = max(2, int(w / 0.3)), max(3, int(h / 0.32))
    yy = y + sign * 0.015
    for i in range(cols + 1):
        x = x0 + w * i / cols
        mb.box('wood_light', (0.03, 0.025, h) if axis == 'X' else (0.025, 0.03, h), loc=at(x, yy, (z0 + z1) / 2))
    for j in range(rows + 1):
        z = z0 + h * j / rows
        mb.box('wood_light', (w, 0.025, 0.025) if axis == 'X' else (0.025, w, 0.025), loc=at((x0 + x1) / 2, yy, z))


@piece('minka', width=9.0, depth=6.5, wall_h=2.6, pitch=50.0, overhang=0.95, thick=0.5, floor_h=0.5, bay=1.82,
       door_bays=1, lit=0.5, engawa=0.9, key='plaster_earth', wood='wood_post', sticks=True)
def minka(ctx, P, rnd):
    """Thatched farmhouse (minka): posts on foundation stones, earthen plaster walls with small lattice windows, a
    wide earth-floor entrance (doma) with sliding board doors half open, shoji bays (a share glowing), a raised
    veranda (engawa), and a thick steep straw hip roof with a ridge cap and crossed ridge sticks. Front faces -Y."""
    W, D, H, F = P['width'], P['depth'], P['wall_h'], P['floor_h']
    mb = MB(ctx, ctx.info['name'], rnd)
    nx, ny = max(2, round(W / P['bay'])), max(2, round(D / P['bay']))
    xs = [-W / 2 + W * i / nx for i in range(nx + 1)]
    ys = [-D / 2 + D * j / ny for j in range(ny + 1)]
    for x in xs:
        for y in (ys[0], ys[-1]):
            _post(mb, rnd, x, y, H, P['wood'])
    for y in ys[1:-1]:
        for x in (xs[0], xs[-1]):
            _post(mb, rnd, x, y, H, P['wood'])
    # top beams (keta) all round, and a dark board skirt under the raised floor
    for y in (ys[0], ys[-1]):
        mb.box('wood_dark', (W + 0.3, 0.2, 0.22), loc=(0, y, H - 0.11))
    for x in (xs[0], xs[-1]):
        mb.box('wood_dark', (0.2, D + 0.3, 0.22), loc=(x, 0, H - 0.11))
    # the dark interior: openings show shadow, not the sky
    mb.box('window_dark', (W - 0.4, D - 0.4, H - 0.3), loc=(0, 0.1, (H - 0.3) / 2 + 0.1))
    door = int(P['door_bays'])
    for side, y, sign in (('front', ys[0], -1), ('back', ys[-1], 1)):
        for i in range(nx):
            x0, x1 = xs[i] + 0.075, xs[i + 1] - 0.075
            if side == 'front' and i < door:              # the doma: dark opening, board doors slid apart
                mb.box('window_dark', (x1 - x0, 0.02, 1.95), loc=((x0 + x1) / 2, y + 0.12, 0.98))
                mb.box('wood_dark', (x1 - x0, 0.12, 0.14), loc=((x0 + x1) / 2, y, 2.0))
                w = (x1 - x0) / 2                        # two board doors, the second slid over the first
                mb.box('wood_aged', (w, 0.04, 1.9), loc=(x0 + w / 2, y - 0.03, 0.97), pr=rnd.random())
                mb.box('wood_aged', (w, 0.04, 1.9), loc=(x0 + 0.8 * w, y - 0.075, 0.97), pr=rnd.random())
                mb.box('wood_aged', (x1 - x0 + 0.1, 0.25, 0.1), loc=((x0 + x1) / 2, y - 0.12, 0.03))
                continue
            mb.box('wood_dark', (x1 - x0, 0.06, F), loc=((x0 + x1) / 2, y + sign * 0.02, F / 2))
            if side == 'front':
                _shoji_bay(mb, rnd, x0, x1, F + 0.04, H - 0.55, y - 0.01, P['lit'])
                mb.box(P['key'], (x1 - x0, 0.1, 0.32), loc=((x0 + x1) / 2, y, H - 0.38), pr=rnd.random())
            else:
                mb.box(P['key'], (x1 - x0, 0.12, H - 0.22 - F), loc=((x0 + x1) / 2, y, F + (H - 0.22 - F) / 2), pr=rnd.random())
    for x, sign in ((xs[0], -1), (xs[-1], 1)):
        for j in range(ny):
            y0, y1 = ys[j] + 0.075, ys[j + 1] - 0.075
            mb.box('wood_dark', (0.06, y1 - y0, F), loc=(x + sign * 0.02, (y0 + y1) / 2, F / 2))
            mb.box(P['key'], (0.12, y1 - y0, H - 0.22 - F), loc=(x, (y0 + y1) / 2, F + (H - 0.22 - F) / 2), pr=rnd.random())
            if j == ny // 2:                              # a small lattice window (renji-mado), sometimes lit
                zc = F + 1.0
                key = 'window_glow' if rnd.random() < P['lit'] else 'window_dark'
                mb.box(key, (0.03, 0.8, 0.6), loc=(x + sign * 0.075, (y0 + y1) / 2, zc))
                for k in range(6):
                    mb.box('bamboo', (0.04, 0.03, 0.62), loc=(x + sign * 0.095, (y0 + y1) / 2 - 0.35 + 0.14 * k, zc))
    # veranda along the shoji bays, on short posts, with a stepping stone
    e = P['engawa']
    if e > 0 and nx > door:
        xa, xb = xs[door], xs[-1]
        yv = ys[0] - e / 2
        x = xa
        while x < xb - 0.01:
            w = min(0.24, xb - x)
            mb.box('wood_aged', (w - 0.008, e, 0.045), loc=(x + w / 2, yv, F - 0.02), pr=rnd.random())
            x += w
        for x in (xa + 0.2, (xa + xb) / 2, xb - 0.2):
            mb.box('wood_dark', (0.1, 0.1, F - 0.06), loc=(x, ys[0] - e + 0.1, (F - 0.06) / 2))
        mb.stone('stone_dressed', (0.75, 0.45, 0.25), M4(((xa + xb) / 2, ys[0] - e - 0.35, 0.1)), rnd, square=0.35,
                 bulge=0.02, chip=0.03, flat_back=False)
    thatch_roof(mb, W, D, H, pitch=P['pitch'], overhang=P['overhang'], thick=P['thick'], rnd=rnd, sticks=P['sticks'])
    mb.finish()


@piece('machiya', width=5.4, depth=9.0, h1=2.9, h2=2.2, pitch=26.0, overhang=0.55, lit=0.55, key='plaster',
       wood='wood_dark_z', noren='noren_indigo', hisashi=0.95, door=1.2, door_side=1, lantern=True)
def machiya(ctx, P, rnd):
    """Town house (machiya): two storeys on a narrow street front, a dark wooden lattice (koshi) across the ground
    floor, a noren curtain at the door, a tiled pent roof (hisashi) over the street, a low upper storey with
    clay-slat windows (mushiko-mado), plaster sides with dark posts, a tiled gable roof with its ridge along the
    street, a paper lantern by the door that lights the street. Front faces -Y."""
    W, D, h1, h2 = P['width'], P['depth'], P['h1'], P['h2']
    mb = MB(ctx, ctx.info['name'], rnd)
    top = h1 + h2
    mb.box('stone_dressed', (W + 0.12, D + 0.12, 0.28), loc=(0, 0, 0.14))
    mb.box(P['key'], (W, D, top - 0.28), loc=(0, 0.04, 0.28 + (top - 0.28) / 2), pr=rnd.random())
    yf = -D / 2
    for x in (-W / 2, W / 2):                             # corner posts and the floor beam on the front
        mb.box(P['wood'], (0.16, 0.16, top - 0.28), loc=(x, yf, 0.28 + (top - 0.28) / 2))
    mb.box('wood_dark', (W + 0.2, 0.18, 0.22), loc=(0, yf - 0.02, h1 - 0.25))
    mb.box('wood_dark', (W + 0.2, 0.16, 0.16), loc=(0, yf - 0.02, top - 0.08))
    # ground floor: glowing or dark interior behind a dark lattice; the door without lattice, with a noren
    dw = P['door']
    dx = (W / 2 - 0.15 - dw / 2) * (1 if P['door_side'] > 0 else -1)
    glow = 'window_glow' if rnd.random() < P['lit'] else 'window_dark'
    mb.box(glow, (W - 0.3, 0.02, h1 - 0.65), loc=(0, yf - 0.012, 0.28 + (h1 - 0.65) / 2))
    mb.box('window_dark', (dw, 0.03, h1 - 0.62), loc=(dx, yf - 0.02, 0.28 + (h1 - 0.62) / 2))
    x = -W / 2 + 0.12
    while x < W / 2 - 0.12:
        if abs(x - dx) > dw / 2 + 0.02:
            mb.box(P['wood'], (0.035, 0.045, h1 - 0.62), loc=(x, yf - 0.06, 0.28 + (h1 - 0.62) / 2), pr=rnd.random())
        x += 0.075
    for z in (0.32, h1 - 0.36):
        mb.box('wood_dark', (W - 0.2, 0.06, 0.06), loc=(0, yf - 0.07, z))
    # noren: three cloth panels hanging from a rod, a little apart and swung
    mb.box('wood_dark', (dw + 0.15, 0.03, 0.03), loc=(dx, yf - 0.16, h1 - 0.42))
    for k in range(3):
        px = dx - dw / 2 + dw * (k + 0.5) / 3
        mb.box(P['noren'], (dw / 3 - 0.03, 0.012, 0.95), loc=(px, yf - 0.17, h1 - 0.42 - 0.48),
               rot=(rnd.uniform(-4, 4), 0, rnd.uniform(-3, 3)))
    # hisashi: a tiled pent roof over the street front
    hs = P['hisashi']
    tile_patch(mb, (-W / 2 - 0.2, yf - hs, h1 - 0.18), (W / 2 + 0.2, yf - hs, h1 - 0.18),
               (-W / 2 - 0.2, yf, h1 + 0.22), (W / 2 + 0.2, yf, h1 + 0.22), tile_w=0.26, tile_l=0.3, amp=0.05)
    mb.box('wood_dark', (W + 0.4, 0.05, 0.14), loc=(0, yf - hs - 0.01, h1 - 0.24))
    # upper storey: clay-slat windows (mushiko-mado), plaster bars over the glow
    zc = h1 + 0.35 + (h2 - 0.7) / 2
    for cx, ww in ((-W * 0.22, W * 0.32), (W * 0.22, W * 0.32)):
        g = 'window_glow' if rnd.random() < P['lit'] else 'window_dark'
        mb.box(g, (ww, 0.02, h2 - 0.9), loc=(cx, yf - 0.012, zc))
        n = max(4, int(ww / 0.11))
        for i in range(n):
            mb.box(P['key'], (0.06, 0.06, h2 - 0.9), loc=(cx - ww / 2 + ww * (i + 0.5) / n, yf - 0.035, zc), pr=0.5)
    gable_roof(mb, W, D, pitch=P['pitch'], overhang=P['overhang'], z0=top, axis='X', tile_w=0.28, tile_l=0.32)
    mb.finish()
    if P['lantern']:
        _chochin(ctx, ctx.info['name'] + '_lantern', (dx + (dw / 2 + 0.25) * (-1 if P['door_side'] > 0 else 1),
                                                      yf - 0.45, h1 - 0.55), 0.24, energy=22.0)


def _chochin(ctx, name, loc, r=0.22, energy=20.0, color=(1.0, 0.55, 0.22), key='lantern_paper'):
    """A paper lantern (chochin): ribbed paper body, black caps, a hook; a warm light inside."""
    mb = MB(ctx, name)
    x, y, z = loc
    h = r * 2.4
    rings = 9
    pts = [(x, y, z - h / 2 + h * i / rings) for i in range(rings + 1)]
    rad = [r * (0.55 + 0.45 * math.sin(math.pi * i / rings)) for i in range(rings + 1)]
    mb.tube(key, pts, rad, segs=12, cap=True)
    mb.cyl('lacquer_black', r * 0.6, r * 0.6, 0.05, 12, loc=(x, y, z + h / 2 + 0.02))
    mb.cyl('lacquer_black', r * 0.6, r * 0.6, 0.05, 12, loc=(x, y, z - h / 2 - 0.02))
    mb.box('iron', (0.01, 0.01, 0.25), loc=(x, y, z + h / 2 + 0.16))
    mb.finish(shadow=False)
    ctx.light('POINT', (x, y, z), energy, color, size=r * 0.6, name=name + '_light')   # in the piece's own space


@piece('chochin', radius=0.22, energy=20.0, color=[1.0, 0.55, 0.22], hang=0.0)
def chochin(ctx, P, rnd):
    """A hanging paper lantern with a warm light inside (eaves, stalls, gates). Its hook at z = 0 + hang."""
    _chochin(ctx, ctx.info['name'], (0, 0, -P['radius'] * 1.3 + P['hang']), P['radius'], P['energy'], tuple(P['color']))


@piece('well', size=1.2, height=0.75, post_h=2.3, key='wood_aged', roof=True)
def well(ctx, P, rnd):
    """Village well: a wooden crib of crossed planks (igeta, the '#'), dark water inside, two posts carrying a beam
    with a pulley, a little tiled roof, a rope down to a wooden bucket on the rim."""
    S, Hh = P['size'], P['height']
    mb = MB(ctx, ctx.info['name'], rnd)
    mb.stone('stone_mossy', (S + 0.5, S + 0.5, 0.22), M4((0, 0, 0.04)), rnd, square=0.3, bulge=0.0, chip=0.03,
             flat_back=False)
    n = max(3, int(Hh / 0.18))
    for i in range(n):
        z = 0.14 + (Hh - 0.14) * (i + 0.5) / n
        h = (Hh - 0.14) / n - 0.01
        if i % 2 == 0:
            for y in (-S / 2, S / 2):
                mb.box(P['key'], (S + 0.3, 0.1, h), loc=(0, y, z), pr=rnd.random())
        else:
            for x in (-S / 2, S / 2):
                mb.box(P['key'], (0.1, S + 0.3, h), loc=(x, 0, z), pr=rnd.random())
    mb.box('window_dark', (S - 0.1, S - 0.1, 0.02), loc=(0, 0, Hh - 0.35))
    ph = P['post_h']
    for x in (-S / 2 - 0.12, S / 2 + 0.12):
        mb.box('wood_post', (0.12, 0.12, ph), loc=(x, 0, ph / 2))
    mb.box('wood_dark', (S + 0.6, 0.12, 0.14), loc=(0, 0, ph - 0.05))
    mb.cyl('wood_dark', 0.11, 0.11, 0.06, 12, loc=(0, 0, ph - 0.25), rot=(0, 90, 0))
    mb.box('wood_dark', (0.025, 0.025, ph - 0.25 - Hh + 0.1), loc=(0.11, 0, (ph - 0.25 + Hh - 0.1) / 2))
    mb.cyl('wood_aged', 0.14, 0.12, 0.26, 12, loc=(0.35, S / 2 - 0.05, Hh + 0.13))
    mb.cyl('iron', 0.145, 0.145, 0.03, 12, loc=(0.35, S / 2 - 0.05, Hh + 0.2))
    if P['roof']:
        gable_roof(mb, S + 0.9, 1.0, pitch=32, overhang=0.25, z0=ph, axis='X', tile_w=0.24, tile_l=0.28)
    mb.finish()


@piece('bamboo_fence', length=6.0, height=1.5, style='kenninji', posts=1.8, cord='cloth_dark')
def bamboo_fence(ctx, P, rnd):
    """Bamboo fence (takegaki) along X: 'kenninji' = a solid wall of split bamboo held by split-bamboo rails tied
    with black cord; 'yotsume' = an open lattice of rails and poles. Thick posts every `posts` m."""
    L, H = P['length'], P['height']
    mb = MB(ctx, ctx.info['name'], rnd)
    n = max(1, round(L / P['posts']))
    for i in range(n + 1):
        x = -L / 2 + L * i / n
        mb.cyl('bamboo_node', 0.055, 0.05, H + 0.15, 8, loc=(x, 0, (H + 0.15) / 2))
    if P['style'] == 'yotsume':
        for z in (0.35, 0.75, 1.1, H - 0.08):
            if z < H:
                mb.cyl('bamboo', 0.025, 0.025, L, 7, loc=(0, -0.04, z), rot=(0, 90, 0))
        x = -L / 2 + 0.15
        while x < L / 2:
            mb.cyl('bamboo', 0.022, 0.022, H - 0.05, 7, loc=(x, 0, (H - 0.05) / 2))
            x += 0.3
    else:
        x = -L / 2
        while x < L / 2 - 0.01:
            w = min(rnd.uniform(0.055, 0.075), L / 2 - x)
            mb.box('bamboo', (w - 0.006, 0.018, H - 0.08), loc=(x + w / 2, 0, (H - 0.08) / 2 + 0.06), pr=rnd.random())
            x += w
        for z in (0.3, H * 0.5, H - 0.25):
            for s in (-1, 1):
                mb.box('bamboo_node', (L, 0.03, 0.045), loc=(0, s * 0.03, z))
            k = -L / 2 + 0.2
            while k < L / 2:
                mb.box(P['cord'], (0.035, 0.09, 0.06), loc=(k, 0, z))
                k += 0.45
        mb.box('bamboo_node', (L + 0.05, 0.12, 0.06), loc=(0, 0, H - 0.02))
    mb.finish()


@piece('stall', width=2.4, depth=1.2, height=2.3, counter=0.85, key='wood_aged', noren='noren_indigo', lantern=True,
       goods='cloth_red')
def stall(ctx, P, rnd):
    """Market stall (yatai): four posts, a counter with a shelf, a sloping board roof, a short noren along the front
    eave, goods on the counter (bowls, bundles), and a paper lantern hanging at a front corner. Front faces -Y."""
    W, D, H, C = P['width'], P['depth'], P['height'], P['counter']
    mb = MB(ctx, ctx.info['name'], rnd)
    for x in (-W / 2, W / 2):
        for y, h in ((-D / 2, H), (D / 2, H - 0.3)):
            mb.box('wood_post', (0.09, 0.09, h), loc=(x, y, h / 2))
    mb.box(P['key'], (W + 0.1, D * 0.7, 0.06), loc=(0, -D * 0.12, C), pr=rnd.random())
    mb.box(P['key'], (W, 0.04, C - 0.1), loc=(0, -D / 2 + 0.05, (C - 0.1) / 2 + 0.05), pr=rnd.random())
    mb.box(P['key'], (W, D * 0.6, 0.04), loc=(0, -D * 0.1, 0.3), pr=rnd.random())
    # sloping board roof, front higher (shed roof toward the back)
    nb = max(6, int(W / 0.2))
    for i in range(nb):
        x = -W / 2 - 0.15 + (W + 0.3) * (i + 0.5) / nb
        beam_between(mb, 'wood_aged', (x, -D / 2 - 0.35, H + 0.03), (x, D / 2 + 0.25, H - 0.32), (W + 0.3) / nb - 0.01,
                     0.03, pr=rnd.random())
    for k in range(4):
        px = -W / 2 + W * (k + 0.5) / 4
        mb.box(P['noren'], (W / 4 - 0.04, 0.012, 0.45), loc=(px, -D / 2 - 0.3, H - 0.22), rot=(rnd.uniform(-5, 5), 0, 0))
    for k in range(5):                                    # goods: bowls and cloth bundles
        x = -W / 2 + 0.3 + (W - 0.6) * k / 4
        if k % 2:
            mb.cyl('wood_dark', 0.11, 0.07, 0.07, 10, loc=(x, -D * 0.2, C + 0.065))
        else:
            mb.box(P['goods'], (0.22, 0.16, 0.12), loc=(x, -D * 0.2, C + 0.09), rot=(0, 0, rnd.uniform(-20, 20)))
    mb.finish()
    if P['lantern']:
        _chochin(ctx, ctx.info['name'] + '_lantern', (W / 2 + 0.05, -D / 2 - 0.3, H - 0.55), 0.2, energy=16.0)


@piece('nobori', height=4.2, width=0.55, flag=2.8, key='cloth_red', crest='banner_white', pole='bamboo', sway=6.0)
def nobori(ctx, P, rnd):
    """A tall street banner (nobori): a bamboo pole with a top arm, a long vertical cloth hanging from it with a
    white crest disc, slightly swung. Faces -Y."""
    H, Wb, Lf = P['height'], P['width'], P['flag']
    mb = MB(ctx, ctx.info['name'], rnd)
    mb.cyl(P['pole'], 0.035, 0.03, H, 8, loc=(0, 0, H / 2))
    mb.cyl(P['pole'], 0.02, 0.02, Wb + 0.1, 7, loc=(Wb / 2, 0, H - 0.1), rot=(0, 90, 0))
    sw = math.radians(rnd.uniform(-P['sway'], P['sway']))
    rows = 8
    for j in range(rows):
        z0, z1 = H - 0.12 - Lf * j / rows, H - 0.12 - Lf * (j + 1) / rows
        off0, off1 = math.sin(sw) * (Lf * j / rows) * 0.3, math.sin(sw) * (Lf * (j + 1) / rows) * 0.3
        wav = 0.03 * math.sin(j * 1.3 + rnd.random())
        mb.poly(P['key'], [(0.05, wav + off0, z0), (Wb, wav + off0, z0), (Wb, wav + off1, z1), (0.05, wav + off1, z1)])
        mb.poly(P['key'], [(0.05, wav + off1 + 0.004, z1), (Wb, wav + off1 + 0.004, z1), (Wb, wav + off0 + 0.004, z0),
                           (0.05, wav + off0 + 0.004, z0)])
    cz = H - 0.12 - Lf * 0.28
    pts = [(Wb / 2 + 0.025 + 0.17 * math.cos(a), -0.012, cz + 0.17 * math.sin(a))
           for a in (2 * math.pi * k / 16 for k in range(16))]
    mb.poly(P['crest'], pts)
    mb.finish()


# --------------------------------------------------------------------------- Poly Haven models, paper look
def _ph_model_path(role):
    import json
    M = json.load(open(os.path.join(REPO, 'library', 'polyhaven.json')))
    ent = M.get('models', {}).get(role)
    if not ent:
        raise KeyError(f'ph_prop: no model role {role!r} in library/polyhaven.json (models: {sorted(M.get("models", {}))})')
    d = os.path.join(REPO, 'assets', 'polyhaven', ent['id'])
    g = [f for f in sorted(os.listdir(d)) if f.endswith('.gltf')] if os.path.isdir(d) else []
    if not g:
        raise FileNotFoundError(f'ph_prop: {ent["id"]} not downloaded (python3 tools/polyhaven.py sync)')
    return os.path.join(d, g[0]), ent['id']


_PH_CACHE = {}


def _ph_mesh(role, faces):
    """One reduced copy of a Poly Haven model as a mesh datablock (cached per role + face count): imported,
    joined, transforms applied, collapsed to `faces` flat facets."""
    key = (role, faces)
    if key in _PH_CACHE:
        return _PH_CACHE[key]
    path, aid = _ph_model_path(role)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == 'MESH']
    bm = bmesh.new()
    mats = []
    for o in meshes:
        me = o.data
        off = len(mats)
        for m in me.materials:
            mats.append(m)
        tmp = bmesh.new()
        tmp.from_mesh(me)
        tmp.transform(o.matrix_world)
        for f in tmp.faces:
            f.material_index += off
        me2 = bpy.data.meshes.new('tmp')
        tmp.to_mesh(me2)
        tmp.free()
        bm.from_mesh(me2)
        bpy.data.meshes.remove(me2)
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    me = bpy.data.meshes.new(f'PH_{aid}')
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    n0 = len(me.polygons)
    if faces and n0 > faces:
        ob = bpy.data.objects.new('tmp_dec', me)
        bpy.context.scene.collection.objects.link(ob)
        mod = ob.modifiers.new('fold', 'DECIMATE')
        mod.ratio = max(0.002, faces / n0)
        dg = bpy.context.evaluated_depsgraph_get()
        red = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        bpy.data.objects.remove(ob, do_unlink=True)
        red.name = f'PH_{aid}_{faces}'
        me = red
    for p in me.polygons:
        p.use_smooth = False                      # flat facets: the fold look of every set piece
    _PH_CACHE[key] = (me, n0)
    return _PH_CACHE[key]


@piece('ph_prop', role='bucket', faces=1500, count=1, spread=0.0, jitter=180.0, scale=1.0, sink=0.0)
def ph_prop(ctx, P, rnd):
    """A Poly Haven model (CC0) in the paper-craft look: collapsed to `faces` flat facets, its own photo textures
    kept, `count` copies scattered within `spread` m with random turns of up to `jitter` degrees, kept off the
    fight marks. Roles: library/polyhaven.json "models" (bucket, barrel, basket, lantern, crate, ladder, ...)."""
    me, n0 = _ph_mesh(P['role'], int(P['faces']))
    placed, tries = 0, 0
    while placed < int(P['count']) and tries < 40 * int(P['count']):
        tries += 1
        if placed == 0 and P['spread'] == 0:
            x = y = 0.0
        else:
            a, rr = rnd.uniform(0, 2 * math.pi), P['spread'] * math.sqrt(rnd.random())
            x, y = rr * math.cos(a), rr * math.sin(a)
        if not ctx.is_clear((x, y), 0.4):
            continue
        ob = bpy.data.objects.new(f'{ctx.info["name"]}_{placed}', me)
        ob.location = (x, y, -P['sink'])
        ob.rotation_euler = (0, 0, math.radians(rnd.uniform(-P['jitter'], P['jitter'])))
        s = P['scale'] * rnd.uniform(0.92, 1.08) if P['count'] > 1 else P['scale']
        ob.scale = (s, s, s)
        pm.add_facet_attribute(ob, rnd.randint(0, 0xffff))
        ctx.link(ob)
        placed += 1
    ctx.info['ph'] = {'role': P['role'], 'faces_before': n0, 'faces': len(me.polygons), 'placed': placed}
