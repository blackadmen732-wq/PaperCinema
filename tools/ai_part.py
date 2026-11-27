"""AI PART PREPARE: turn a raw generated model (Tripo, TRELLIS, Meshy...) into a paper-ready rigid part, once.

    B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
    $B -b -P tools/ai_part.py -- <part id>            (reads library/ai-parts.json)

What a raw service model is: ~1M smooth triangles, one painted texture cut into hundreds of UV islands, posed
somewhere in its own space, often with extra things the prompt did not ask for (a bust under a head). What a
part is: a few thousand flat facets in the rig's rest space, sized to the body, in OUR paper sheets.
This script does the conversion and writes it to <prepared>/ (committed, small):

    part.glb      the reduced mesh, in rig rest space (metres, Z up, facing -Y), one UV map (`paint`),
                  two material slots named after the sheet classes ('skin' = light paint, 'hair' = dark paint)
    color.png     the original paint, baked onto the reduced mesh's own UVs (Cycles, selected-to-active)
    ink.png       mask: dark paint (brows, eye lines, hairline) -> printed ink on the light sheet
    glow.png      mask: warm saturated paint (eye slits) -> emission
    report.json   every number: faces before/after, the fit, class shares, timings

Steps, all driven by the manifest entry:
  1 import, one mesh, transforms applied
  2 weld the texture seams, cut: keep what is above `cut` (a fraction of the model's height), fill the hole
  3 reduce a copy: collapse to `faces`  -> big flat facets, the paper look
  4 fit both copies: the cut plane goes to fit.bottom_z, the kept height becomes fit.height metres, and the
    LIGHT paint just above the cut (the neck skin) is centred on fit.neck_xy, so the head sits on the neck
  5 unwrap the reduced copy (smart project) and bake the original paint onto it
  6 masks and per-facet classes from the baked paint; the cap is always 'skin'
"""
import json
import math
import os
import sys
import time

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
PID = ARGV[0] if ARGV else None
sys.path.insert(0, os.path.join(REPO, 'blender', 'character'))
import ai_manifest  # noqa: E402   (expands one-block "body" characters into their sections)
MAN = ai_manifest.load()
if PID not in MAN:
    raise SystemExit(f'{PID}: not in library/ai-parts.json (sections of a body are <body>_torso, <body>_sleeve_L, ...): '
                     + ', '.join(sorted(MAN)))
E = MAN[PID]
OUT = os.path.join(REPO, E['prepared'])
os.makedirs(OUT, exist_ok=True)
T0 = time.time()
REP = {'id': PID, 'raw': E['raw']}


def log(*a):
    print('[ai-part]', '%5.1fs' % (time.time() - T0), *a, flush=True)


def srgb_classes(px, dark_below, glow):
    """px: (..., 3) sRGB 0..1. Returns (dark, glow) boolean masks."""
    r, g, b = px[..., 0], px[..., 1], px[..., 2]
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    mx, mn = px.max(-1), px.min(-1)
    d = np.maximum(mx - mn, 1e-6)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    hue = np.where(mx == r, (60 * ((g - b) / d)) % 360, np.where(mx == g, 60 * ((b - r) / d) + 120, 60 * ((r - g) / d) + 240))
    is_glow = (sat > glow['min_sat']) & (mx > 0.5) & (hue > glow['hue'][0]) & (hue < glow['hue'][1])
    return (lum < dark_below) & ~is_glow, is_glow


# ---------------------------------------------------------------- 1 import
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=os.path.join(REPO, E['raw']))
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
if len(meshes) != 1:
    raise SystemExit(f'{PID}: expected one mesh in the raw model, found {len(meshes)}')
hi = meshes[0]
hi.data.transform(hi.matrix_world)
hi.matrix_world = Matrix()
for o in list(bpy.data.objects):
    if o is not hi:
        bpy.data.objects.remove(o, do_unlink=True)
REP['faces_raw'] = len(hi.data.polygons)
src_img = next(n.image for m in hi.data.materials if m and m.use_nodes for n in m.node_tree.nodes
               if n.type == 'TEX_IMAGE' and n.image and any(l.to_socket.name == 'Base Color' for l in n.outputs[0].links))
log('raw', REP['faces_raw'], 'faces, paint', src_img.name, tuple(src_img.size))
# we bake the PAINT, never the metal: a diffuse-colour bake is base colour x (1 - metallic), and a service can mark
# cloth as metal (Musashi's Tripo body, 27 Nov: 77% of his ORM texels metallic > 0.5, mean 0.705 - Kojiro's 0.09):
# his torso and head baked 45-75% black until this cut.
for m in hi.data.materials:
    bs = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None) if m and m.use_nodes else None
    for sock in ('Metallic', 'Transmission Weight') if bs else ():
        i = bs.inputs.get(sock)
        if i is not None:
            for l in list(i.links):
                m.node_tree.links.remove(l)
                REP.setdefault('cut_inputs', []).append(sock)
            i.default_value = 0.0

# ---------------------------------------------------------------- 1b which way does it face?
# A service puts its model in its own frame (the first Kojiro head looked down +X; the rig faces -Y). The eyes
# say where the front is: the glowing paint's centre, seen from the middle of the head, snapped to 90 degrees.
# A part without glow paint gives `facing` in the manifest ('+x', '-x', '+y', '-y').
W, H = src_img.size
paint = np.empty(W * H * 4, np.float32)
src_img.pixels.foreach_get(paint)
paint = paint.reshape(H, W, 4)[..., :3]


def poly_paint(me):
    """Per polygon: centre (n,3) and the paint at its first corner's UV (n,3)."""
    n = len(me.polygons)
    cen = np.empty(n * 3, np.float32)
    me.polygons.foreach_get('center', cen)
    ls = np.empty(n, np.int32)
    me.polygons.foreach_get('loop_start', ls)
    uvs = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers.active.data.foreach_get('uv', uvs)
    uv = uvs.reshape(-1, 2)[ls]
    xi = np.clip((uv[:, 0] * W).astype(int), 0, W - 1)
    yi = np.clip((uv[:, 1] * H).astype(int), 0, H - 1)
    return cen.reshape(-1, 3), paint[yi, xi]


FACING = {'+x': 0.0, '+y': 90.0, '-x': 180.0, '-y': -90.0}
if E.get('facing') or E.get('facing_deg') is not None:
    cen, eyes = None, np.zeros(0, bool)
    if E.get('glow'):                                      # still wanted: the eyes as an anchor (fit 'box')
        cen, pp = poly_paint(hi.data)
        _, eyes = srgb_classes(pp, E.get('dark_below', 0.3), E['glow'])
else:
    cen, pp = poly_paint(hi.data)
    _, eyes = srgb_classes(pp, E.get('dark_below', 0.3), E['glow'])
if E.get('facing_deg') is not None:                        # a three-quarter concept: the front at any angle
    ang = float(E['facing_deg'])
    REP['facing'] = {'from': 'manifest (deg)', 'deg': ang}
elif E.get('facing'):
    ang = FACING[E['facing']]
    REP['facing'] = {'from': 'manifest', 'deg': ang}
elif eyes.sum() >= 20:
    d = cen[eyes].mean(0) - cen.mean(0)
    raw = math.degrees(math.atan2(d[1], d[0]))
    ang = raw if E.get('facing_snap') is False else round(raw / 90.0) * 90.0
    REP['facing'] = {'from': 'eye paint', 'raw_deg': round(raw, 1), 'deg': ang, 'eye_faces': int(eyes.sum())}
else:
    raise SystemExit(f'{PID}: no glow paint to find the face by; give "facing" in the manifest')
turn = math.radians(-90.0 - ang)                   # bring the face round to -Y, the rig's front
hi.data.transform(Matrix.Rotation(turn, 4, 'Z'))
ROT = Matrix.Rotation(turn, 3, 'Z')
if E['fit'].get('rotate'):                         # then any turn the part needs on its socket (a fan held point-down)
    R3 = Euler([math.radians(a) for a in E['fit']['rotate']], 'XYZ').to_matrix()
    hi.data.transform(R3.to_4x4())
    ROT = R3 @ ROT
log('facing %s -> turned %.0f deg so the face looks down -Y' % (REP['facing'], math.degrees(turn)))
eye_c = (ROT @ Vector(cen[eyes].mean(0).tolist())) if cen is not None and eyes.sum() else None
eye_x = float(eye_c.x) if eye_c is not None else None

# ---------------------------------------------------------------- 2 cut
MODE = E['fit'].get('mode', 'head')     # head: cut + fit to the neck; body: one figure -> sections; box: a prop
BODY, BOX = MODE == 'body', MODE == 'box'
HEAD = not BODY and not BOX
zs = [v.co.z for v in hi.data.vertices]
z0, z1 = min(zs), max(zs)
if BODY:
    # one fit for the whole figure (every section of one body shares it): feet to z 0, the shoulder line
    # (fit.shoulder_frac of the height) to fit.shoulder_z, centred on the waist band
    zsh = z0 + E['fit']['shoulder_frac'] * (z1 - z0)
    sb = E['fit']['shoulder_z'] / (zsh - z0)
    band = [v.co for v in hi.data.vertices if z0 + 0.45 * (z1 - z0) < v.co.z < z0 + 0.55 * (z1 - z0)]
    bcx = sum(c.x for c in band) / len(band)
    bcy = sum(c.y for c in band) / len(band)
    hi.data.transform(Matrix.Scale(sb, 4) @ Matrix.Translation((-bcx, -bcy, -z0)))
    REP['fit'] = {'mode': 'body', 'scale': sb, 'waist_centre_model': [bcx, bcy], 'height_m': (z1 - z0) * sb}
    log('body fit: scale %.4f, figure %.3f m tall, waist centre (%.3f, %.3f)' % (sb, (z1 - z0) * sb, bcx, bcy))
    zc = None
elif BOX:
    zc = z0 + E['cut'] * (z1 - z0) if E.get('cut') else None   # a prop keeps all of itself, or what is above `cut`
else:
    zc = z0 + E['cut'] * (z1 - z0)
bm = bmesh.new()
bm.from_mesh(hi.data)
# weld the texture seams first: a generated mesh is split into loose islands along every UV seam (30,724 open
# edges on the first Kojiro head), and reducing a mesh full of borders makes fans of spikes and holes. Welding
# keeps each corner's own UV, so the paint (baked from this copy) is untouched.
nv = len(bm.verts)
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6 * (z1 - z0))
REP['welded_verts'] = nv - len(bm.verts)
REP['open_edges_after_weld'] = sum(1 for e in bm.edges if e.is_boundary)
if BODY:
    # keep: the section's box in rig metres; each bound is one plane, everything outside it is cut away
    K = E['keep']
    for ax, i in (('x', 0), ('y', 1), ('z', 2)):
        lo_, hi_ = K.get(ax, [None, None])
        for val, sign in ((lo_, 1), (hi_, -1)):
            if val is None:
                continue
            co_ = [0.0, 0.0, 0.0]
            no_ = [0.0, 0.0, 0.0]
            co_[i] = val
            no_[i] = sign
            bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-5,
                                   plane_co=co_, plane_no=no_, clear_inner=True)
elif zc is not None:
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-5,
                           plane_co=(0, 0, zc), plane_no=(0, 0, 1), clear_inner=True)
# a cut can leave loose crumbs of the neighbouring section: keep the islands that hold most of the faces
islands, seen = [], set()
for f in bm.faces:
    if f.index in seen:
        continue
    stack, isl = [f], []
    seen.add(f.index)
    while stack:
        g = stack.pop()
        isl.append(g)
        for e in g.edges:
            for h in e.link_faces:
                if h.index not in seen:
                    seen.add(h.index)
                    stack.append(h)
    islands.append(isl)
bm.faces.index_update()
if len(islands) > 1:
    big = max(len(i) for i in islands)
    crumbs = [f for isl in islands if len(isl) < E.get('min_island_frac', 0.02) * big for f in isl]
    if crumbs:
        bmesh.ops.delete(bm, geom=crumbs, context='FACES')
    REP['islands'] = {'found': len(islands), 'crumb_faces_removed': len(crumbs)}
open_edges = [e for e in bm.edges if len(e.link_faces) == 1]
capped = bmesh.ops.holes_fill(bm, edges=open_edges, sides=0)['faces']
bmesh.ops.triangulate(bm, faces=capped)
bm.to_mesh(hi.data)
bm.free()
REP['cut_z_model'] = zc
REP['faces_cut'] = len(hi.data.polygons)
log('welded %d seam vertices (%d open edges left); kept %d faces, %d cap faces'
    % (REP['welded_verts'], REP['open_edges_after_weld'], REP['faces_cut'], len(capped)))
if not REP['faces_cut']:
    raise SystemExit(f'{PID}: the keep box / cut left nothing')

# ---------------------------------------------------------------- 4 fit (computed on the full-detail copy)
# fitted once for the whole body before the cut (BODY); a head is fitted here, from its own cut and eyes
if BOX:
    # a prop: one size (fit.size: {axis: metres}) and anchors (fit.anchor: {axis: [min|max|mid|eyes, metres]}) in
    # rig rest space, e.g. a helmet's lowest point at the neck, a mask's back on the face, a fan's pivot in the hand
    F = E['fit']
    co = np.empty(len(hi.data.vertices) * 3, np.float32)
    hi.data.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    mn, mx = co.min(0), co.max(0)
    (sax, size), = F['size'].items()
    if sax == 'x_at_eyes':                         # a head-like piece: its width across the eyes (a hood: 0.20 m)
        if eye_c is None:
            raise SystemExit(f'{PID}: size "x_at_eyes" needs glow paint (give "glow")')
        band = co[np.abs(co[:, 2] - eye_c.z) < 0.02 * float(mx[2] - mn[2])]
        s = size / float(band[:, 0].max() - band[:, 0].min())
    else:
        si = 'xyz'.index(sax)
        s = size / float(mx[si] - mn[si])
    t = [0.0, 0.0, 0.0]
    for ax, (where, val) in F['anchor'].items():
        j = 'xyz'.index(ax)
        if where == 'eyes' and eye_c is None:
            raise SystemExit(f'{PID}: anchor "eyes" needs glow paint (give "glow")')
        ref = {'min': mn[j], 'max': mx[j], 'mid': (mn[j] + mx[j]) / 2}.get(where, eye_c[j] if eye_c is not None else 0)
        t[j] = val - s * float(ref)
    hi.data.transform(Matrix.Translation(t) @ Matrix.Scale(s, 4))
    REP['fit'] = {'mode': 'box', 'scale': s, 'size_m': [round(float(x) * s, 4) for x in (mx - mn)],
                  'eyes': [round(float(eye_c[j]) * s + t[j], 4) for j in range(3)] if eye_c is not None else None}
    log('box fit: scale %.4f, size %s m, eyes at %s' % (s, REP['fit']['size_m'], REP['fit']['eyes']))
elif HEAD:
    uvl = hi.data.uv_layers.active.data
    band_top = zc + 0.03 * (z1 - z0)
    pts = []
    for p in hi.data.polygons:
        c = p.center
        if c.z > band_top or abs(p.normal.z) > 0.8:          # near the cut, and not a cap face
            continue
        u, v = uvl[p.loop_start].uv
        px = paint[min(H - 1, max(0, int(v * H))), min(W - 1, max(0, int(u * W)))]
        if 0.2126 * px[0] + 0.7152 * px[1] + 0.0722 * px[2] >= E['dark_below']:
            pts.append(c.copy())
    if not pts:
        raise SystemExit(f'{PID}: no light paint just above the cut: is `cut` below the neck?')
    neck = sum(pts, Vector()) / len(pts)
    # side to side: the middle of the eyes (a face is symmetric; the bounding box is not - hair hangs to one side and
    # a collar the service added pulls the light paint near the cut sideways). Front to back: the neck.
    xs = [v.co.x for v in hi.data.vertices]
    cx = eye_x if eye_x is not None else (min(xs) + max(xs)) / 2
    s = E['fit']['height'] / (z1 - zc)
    nx, ny = E['fit'].get('neck_xy', [0.0, 0.0])
    M = Matrix.Translation((nx, ny, E['fit']['bottom_z'])) @ Matrix.Scale(s, 4) @ Matrix.Translation((-cx, -neck.y, -zc))
    hi.data.transform(M)
    REP['fit'] = {'scale': s, 'centre_model_x': cx, 'neck_model_y': neck.y, 'neck_light_x': neck.x, 'neck_samples': len(pts)}
    log('fit: scale %.4f, centre x %.3f, neck y %.3f (light paint near the cut centres at x %.3f)' % (s, cx, neck.y, neck.x))

# ---------------------------------------------------------------- 3 reduce a copy
lo = hi.copy()
lo.data = hi.data.copy()
lo.name = lo.data.name = PID
sc.collection.objects.link(lo)
co = lo.modifiers.new('collapse', 'DECIMATE')        # straight to the target: big flat facets ARE the fold
co.ratio = max(0.0005, E['faces'] / REP['faces_cut'])
dg = bpy.context.evaluated_depsgraph_get()
low_me = bpy.data.meshes.new_from_object(lo.evaluated_get(dg))
lo.modifiers.clear()
old = lo.data
lo.data = low_me
bpy.data.meshes.remove(old)
bmx = bmesh.new()
bmx.from_mesh(lo.data)
bmesh.ops.triangulate(bmx, faces=[f for f in bmx.faces if len(f.verts) > 4])
# face direction: each reduced facet points the same way as the original surface under it (recalc_face_normals
# only guesses from the shape, and a cut-up section is not a closed shape to guess from).
from mathutils.bvhtree import BVHTree
_hb = bmesh.new()
_hb.from_mesh(hi.data)
_tree = BVHTree.FromBMesh(_hb)
_hb.faces.ensure_lookup_table()
flipped_n = 0
bmx.normal_update()
for f in bmx.faces:
    loc, nrm, idx, dist = _tree.find_nearest(f.calc_center_median())
    if nrm is not None and f.normal.dot(nrm) < 0:
        f.normal_flip()
        flipped_n += 1
_hb.free()
REP['facets_turned_to_surface'] = flipped_n
bmx.to_mesh(lo.data)
bmx.free()
REP['faces_part'] = len(lo.data.polygons)
log('reduced to', REP['faces_part'], 'faces')

# ---------------------------------------------------------------- 5 paint for each reduced facet
def outer_paint(lo_me):
    """BODY sections: the paint on the OUTERMOST original surface over each reduced facet (5 points per facet).
    A section only needs one sheet per facet, so it needs no unwrap and no bake: a ray comes in from outside the
    section (away from its centre) and the first painted surface it meets is the one the camera sees. Cap faces
    (the cut) are skipped. 1.5 s for a 5000-facet torso."""
    from mathutils.bvhtree import BVHTree
    hb = bmesh.new()
    hb.from_mesh(hi.data)
    bmesh.ops.triangulate(hb, faces=[f for f in hb.faces if len(f.verts) > 3])
    hb.faces.ensure_lookup_table()
    uvh = hb.loops.layers.uv.active
    tree = BVHTree.FromBMesh(hb)
    cen0 = sum((v.co for v in lo_me.vertices), Vector()) / max(1, len(lo_me.vertices))
    # the faces that close the cut (holes_fill) have no paint of their own (their UVs are zero): never sample them
    K = E['keep']
    planes = [(i, val) for ax, i in (('x', 0), ('y', 1), ('z', 2)) for val in K.get(ax, [None, None]) if val is not None]
    cap = [any(all(abs(l.vert.co[i] - val) < 1e-4 for l in f.loops) for i, val in planes) for f in hb.faces]
    stats = {'ray': 0, 'nearest': 0, 'none': 0}

    def sample(p, n):
        n = n if n.dot(p - cen0) >= 0 else -n           # outward = away from the section's centre
        hit = tree.ray_cast(p + n * 0.25, -n, 0.6)
        kind = 'ray'
        if hit[0] is None or cap[hit[2]]:
            hit, kind = tree.find_nearest(p), 'nearest'
        loc, _, idx = hit[0], hit[1], hit[2]
        if loc is None or idx is None or cap[idx]:
            stats['none'] += 1
            return None
        stats[kind] += 1
        f = hb.faces[idx]
        a, b, c = (l.vert.co for l in f.loops)
        ua, ub, uc = (l[uvh].uv for l in f.loops)
        from mathutils.geometry import barycentric_transform
        w = barycentric_transform(loc, a, b, c, Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))
        u = ua * w.x + ub * w.y + uc * w.z
        return paint[min(H - 1, max(0, int(u.y * H))), min(W - 1, max(0, int(u.x * W)))]
    out = []
    for p in lo_me.polygons:
        vs = [lo_me.vertices[i].co for i in p.vertices]
        pts = [p.center] + [p.center.lerp(v, 0.6) for v in vs]
        out.append([q for q in (sample(Vector(x), p.normal.copy()) for x in pts) if q is not None])
    hb.free()
    REP['paint_samples'] = stats
    return out


if BODY:
    FACE_PAINT = outer_paint(lo.data)
    R = 1
    px = np.zeros((1, 1, 3), np.float32)
    missed = np.zeros((1, 1), bool)
    dark = glow = np.zeros((1, 1), bool)
    REP['bake_missed_pct'] = 0.0
    REP['paint_source'] = 'outermost surface ray samples'
    log('painted %d facets from the outermost surface' % len(FACE_PAINT))
    if os.environ.get('AI_PART_DUMP'):                 # debug: the mean paint and centre of every facet
        np.save(os.path.join(OUT, 'face_paint.npy'), np.array(
            [list(np.mean(c, 0) if len(c) else [-1, -1, -1]) + list(lo.data.polygons[i].center)
             for i, c in enumerate(FACE_PAINT)], np.float32))
else:
    while lo.data.uv_layers:
        lo.data.uv_layers.remove(lo.data.uv_layers[0])
    lo.data.uv_layers.new(name='paint')
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = lo
    lo.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004)
    bpy.ops.object.mode_set(mode='OBJECT')
    R = int(E.get('bake_res', 1024))
    img = bpy.data.images.new(PID + '_color', R, R, alpha=False)
    # magenta = not reached by the bake (the gaps between UV islands too). The bake's own "clear" painted it black
    # (27 Nov), so the gaps counted as a failed bake (25% on the good Kojiro head) and fed the ink mask.
    img.pixels.foreach_set(np.tile(np.array([1, 0, 1, 1], np.float32), R * R))
    bake_mat = bpy.data.materials.new('bake_target')
    bake_mat.use_nodes = True
    tn = bake_mat.node_tree.nodes.new('ShaderNodeTexImage')
    tn.image = img
    bake_mat.node_tree.nodes.active = tn
    lo.data.materials.clear()
    lo.data.materials.append(bake_mat)
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 4
    hi.select_set(True)
    lo.select_set(True)
    bpy.context.view_layer.objects.active = lo
    sc.render.bake.use_pass_direct = False
    sc.render.bake.use_pass_indirect = False
    sc.render.bake.use_pass_color = True
    sc.render.bake.margin = 6
    sc.render.bake.use_clear = False            # keep the magenta: "clear" paints the image black before baking
    tb = time.time()
    # reach: how far a ray from the reduced surface may travel to find the original (2 cm for a head).
    CAGE, RAY = E.get('cage', 0.01 if BOX else 0.004), E.get('ray', 0.05 if BOX else 0.02)
    bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, use_selected_to_active=True,
                        cage_extrusion=CAGE, max_ray_distance=RAY, margin=6)
    REP['bake_s'] = round(time.time() - tb, 1)
    img.filepath_raw = os.path.join(OUT, 'color.png')
    img.file_format = 'PNG'
    img.save()
    log('baked %dx%d in %.1fs' % (R, R, REP['bake_s']))

    # ---------------------------------------------------------------- 6 masks + classes
    px = np.empty(R * R * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(R, R, 4)[..., :3]
    missed = (px[..., 0] > 0.95) & (px[..., 1] < 0.05) & (px[..., 2] > 0.95)
    dark, glow = srgb_classes(px, E.get('dark_below', 0.3), E.get('glow') or {'min_sat': 2.0, 'hue': [0, 0]})
    dark &= ~missed
    glow &= ~missed
    REP['bake_missed_pct'] = round(100 * float(missed.mean()), 2)
    # a ray that finds nothing bakes pure black: measure it against the source paint, and refuse a bad bake
    covered = ~missed
    black = covered & (px.max(-1) < 0.02)
    src_black = float((paint.max(-1) < 0.02).mean())
    REP['bake_black_pct'] = round(100 * float(black.sum()) / max(1, int(covered.sum())), 2)
    REP['source_black_pct'] = round(100 * src_black, 2)
    log('bake: %.1f%% of covered texels pure black (source paint: %.1f%%), cage %.3f ray %.3f'
        % (REP['bake_black_pct'], REP['source_black_pct'], CAGE, RAY))
    if REP['bake_black_pct'] > max(8.0, 2.0 * REP['source_black_pct'] + 5.0):
        raise SystemExit(f'{PID}: the bake missed: {REP["bake_black_pct"]}% black texels (the source paint has '
                         f'{REP["source_black_pct"]}%). Rays that found nothing: raise "ray" / "cage" in the manifest entry.')


    def save_mask(m, name):
        im = bpy.data.images.new(PID + '_' + name, R, R, alpha=False)
        a = np.zeros((R, R, 4), np.float32)
        a[..., 0] = a[..., 1] = a[..., 2] = m.astype(np.float32)
        a[..., 3] = 1
        im.pixels.foreach_set(a.ravel())
        im.filepath_raw = os.path.join(OUT, name + '.png')
        im.file_format = 'PNG'
        im.save()


if E.get('ink') and not BODY:
    save_mask(dark, 'ink')
if E.get('glow') and not BODY:
    save_mask(glow, 'glow')
uv = lo.data.uv_layers['paint'].data if not BODY else None
PAL = E.get('palette')                 # [{name, rgb: [[r,g,b] sRGB 0..1, ...]}]: each facet takes the nearest
if PAL:
    pal_c = np.array([c for e in PAL for c in e['rgb']], np.float32)
    pal_i = np.array([k for k, e in enumerate(PAL) for _ in e['rgb']])
NAMES = [e['name'] for e in PAL] if PAL else ['skin', 'hair']
ZONES = E.get('zones', {})              # class -> {'x'|'y'|'z': [lo, hi]} in rig metres (BODY sections)


def in_zone(c, zone):
    """zone: one box {'x'|'y'|'z': [lo, hi]} or a list of boxes (inside any one of them); none = anywhere"""
    if not zone:
        return True
    return any(all(lo_ <= c[i] <= hi_ for ax, i in (('x', 0), ('y', 1), ('z', 2))
                   for lo_, hi_ in [box.get(ax, [-1e9, 1e9])])
               for box in (zone if isinstance(zone, list) else [zone]))
cls = []
for p in lo.data.polygons:
    if HEAD and p.center.z < E['fit']['bottom_z'] + 0.004 and p.normal.z < -0.7:   # the cap: in the collar
        cls.append(0)
        continue
    if BODY:
        # zones: where on the body a class may be at all (rig metres). Colour alone cannot tell the darkest robe
        # fold from a black obi (Musashi, 27 Nov: 56% of his torso came out "obi"); the obi is a band at the waist.
        alw = np.array([in_zone(p.center, ZONES.get(n)) for n in NAMES])
        if not alw.any():
            alw[:] = True
        far = np.where(alw[pal_i], 0.0, np.inf)
        votes = np.zeros(len(PAL))
        for col in FACE_PAINT[p.index]:
            votes[pal_i[int((((pal_c - col) ** 2).sum(1) + far).argmin())]] += 1
        cls.append(int(votes.argmax()) if votes.sum() else -1)      # -1: no paint found, takes the main sheet
        continue
    us = [uv[i].uv for i in range(p.loop_start, p.loop_start + p.loop_total)]
    c = sum(us, Vector((0, 0))) / len(us)
    samples = [c] + [c.lerp(u, 0.6) for u in us]
    if PAL:
        votes = np.zeros(len(PAL))
        for q in samples:
            x, y = min(R - 1, max(0, int(q.x * R))), min(R - 1, max(0, int(q.y * R)))
            if missed[y, x]:
                continue
            votes[pal_i[int(((pal_c - px[y, x]) ** 2).sum(1).argmin())]] += 1
        cls.append(int(votes.argmax()))
    else:
        votes = 0
        for q in samples:
            x, y = min(R - 1, max(0, int(q.x * R))), min(R - 1, max(0, int(q.y * R)))
            votes += 1 if dark[y, x] else 0
        cls.append(1 if votes * 2 > len(samples) else 0)
if BODY:
    # the faces that close a cut have no paint of their own: they take the section's main sheet
    main = max(set(cls) - {-1}, key=cls.count)
    REP['unpainted_facets'] = cls.count(-1)
    cls = [main if c == -1 else c for c in cls]
    K = E['keep']
    for k, p in enumerate(lo.data.polygons):
        for ax, i in (('x', 0), ('y', 1), ('z', 2)):
            for val in K.get(ax, [None, None]):
                if val is not None and abs(p.normal[i]) > 0.95 and abs(p.center[i] - val) < 0.004:
                    cls[k] = main
# despeckle: any island of one sheet smaller than `min_island` facets (default 10) joins the sheet around it - a
# light chip inside the hair (an ear tip poking through), a dark chip on a cheek. Real regions (an ear, a lock, the
# eyes, which sit inside the face) are bigger and stay.
bmc = bmesh.new()
bmc.from_mesh(lo.data)
bmc.faces.ensure_lookup_table()
nbr = [{g.index for e in f.edges for g in e.link_faces if g.index != f.index} for f in bmc.faces]
bmc.free()
flipped, MIN_ISL = 0, int(E.get('min_island', 10))
for _ in range(2):
    seen = [False] * len(cls)
    for i0 in range(len(cls)):
        if seen[i0]:
            continue
        isl, stack, border = [], [i0], {}
        seen[i0] = True
        while stack:
            i = stack.pop()
            isl.append(i)
            for j in nbr[i]:
                if cls[j] == cls[i0]:
                    if not seen[j]:
                        seen[j] = True
                        stack.append(j)
                else:
                    border[cls[j]] = border.get(cls[j], 0) + 1
        if len(isl) < MIN_ISL and border:
            new = max(border, key=border.get)
            for i in isl:
                cls[i] = new
            flipped += len(isl)
REP['despeckled_faces'] = flipped
REP['classes_pct'] = {NAMES[k]: round(100 * cls.count(k) / len(cls), 1) for k in range(len(NAMES))}
REP['hair_faces_pct'] = REP['classes_pct'].get('hair', 0.0)
REP['ink_pct'] = round(100 * float(dark.mean()), 2)
REP['glow_pct'] = round(100 * float(glow.mean()), 3)
log('classes %s; ink %.2f%% of texels, glow %.3f%%, bake missed %.2f%%'
    % (REP['classes_pct'], REP['ink_pct'], REP['glow_pct'], REP['bake_missed_pct']))

# ---------------------------------------------------------------- write the part
if E.get('shift'):        # moved AFTER its paint is read (the cut planes stay where the paint sampler expects them):
    lo.data.transform(Matrix.Translation(E['shift']))   # a helmet seated on the folded neck (27 Nov: 5.5 cm gap)
    REP['shift'] = E['shift']
lo.data.materials.clear()
for nm in NAMES:
    lo.data.materials.append(bpy.data.materials.new(nm))
for p, c in zip(lo.data.polygons, cls):
    p.material_index = c
bpy.data.objects.remove(hi, do_unlink=True)
bpy.ops.object.select_all(action='DESELECT')
lo.select_set(True)
bpy.context.view_layer.objects.active = lo
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, 'part.glb'), use_selection=True, export_format='GLB',
                          export_normals=True, export_texcoords=True, export_materials='EXPORT', export_yup=True)
ps = [v.co for v in lo.data.vertices]
REP['bbox'] = {'min': [min(p[i] for p in ps) for i in range(3)], 'max': [max(p[i] for p in ps) for i in range(3)]}
REP['total_s'] = round(time.time() - T0, 1)
json.dump(REP, open(os.path.join(OUT, 'report.json'), 'w'), indent=1)
log('wrote', OUT, '| bbox', [round(x, 3) for x in REP['bbox']['min']], [round(x, 3) for x in REP['bbox']['max']])
