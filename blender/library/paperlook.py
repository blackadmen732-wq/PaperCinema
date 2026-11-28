"""PAPERLOOK: turn any 3D model into folded paper, and give a paper model its paper surface (Mark, 28 Nov: "the test
we did with the bucket, put it in and transform it to paper: that's what I want the library for").

Two halves, both used by tools/paperize_model.py (one model -> paper.glb + preview.png) and by
blender/library/build_scene.py (library assets -> a whole scene):

  paperize(objs, asset_id, faces=1500, cards=24000)   meshes -> ONE clean faceted mesh of paper SHEETS:
      joined with transforms applied, merged by distance, collapsed to `faces` flat facets, near-flat neighbours
      dissolved into one larger facet (a sheet is folded, not tessellated), base at z=0 and centred in x/y, metres
      kept. Every face takes the colour of the model's own texture under it (several samples per face), and the
      faces of each source material are clustered into at most 4 sheets of paper (k-means on sRGB, weighted by
      area, a majority filter against confetti). Alpha-cut materials (leaf cards) are not collapsed: they are thinned
      to a `cards` triangle budget by dropping whole cards, and keep their silhouette as a cut-out mask.
      The result carries plain Principled materials (colour, a mask for cut sheets, a glow) that a glTF file can
      hold; custom properties pc_sheet / pc_cut / pc_glow mark them.
  paper_look(ob, size)                                 sheet materials -> the paper shader of the sets and the
      characters: blender/world/paper_materials.py paper_material (washi fibre, per-facet tone from facet_rand)
      plus paper_surface (ink in the valleys of the folds, a light edge on the ridges, mottle, occlusion), with the
      ink line and fibre scaled to the object's size. Cut sheets get their mask as alpha.
  studio(ob, png)                                      a neutral three-quarter studio still of one model.
"""
import math
import os
import random
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
for _d in ('blender/world', 'blender'):
    _p = os.path.join(REPO, _d)
    if _p not in sys.path:
        sys.path.insert(0, _p)
import paper_materials as pm  # noqa: E402

MAX_SHEETS = 4          # sheets of paper per source material
SPLIT_DIST = 0.075      # sRGB distance a new sheet must be from every other sheet of the same material
MIN_SHARE = 0.03        # share of the material's area a sheet must cover


# --------------------------------------------------------------------------- colour helpers
def srgb_to_lin(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(np.asarray(c, dtype=np.float64), 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def _upstream_image(sock, depth=0):
    """First Image Texture node feeding `sock` (through mix / multiply / separate nodes), or None."""
    if depth > 8 or not sock.is_linked:
        return None
    n = sock.links[0].from_node
    if n.type == 'TEX_IMAGE' and n.image is not None:
        return n
    for s in n.inputs:
        hit = _upstream_image(s, depth + 1)
        if hit is not None:
            return hit
    return None


def principled(mat):
    if not mat or not mat.use_nodes:
        return None
    return next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)


def base_info(mat):
    """(image texture node or None, constant linear base colour, alpha image node or None, emission (rgb, strength))."""
    p = principled(mat)
    if p is None:
        c = tuple(mat.diffuse_color)[:3] if mat else (0.6, 0.6, 0.6)
        return None, np.array(c), None, None
    bc = p.inputs['Base Color']
    tex = _upstream_image(bc)
    col = np.array(bc.default_value[:3])
    a = p.inputs['Alpha']
    atex = _upstream_image(a) if a.is_linked else None
    if atex is None and getattr(mat, 'blend_method', 'OPAQUE') in ('CLIP', 'HASHED', 'BLEND') and tex is not None \
            and tex.image.depth in (32, 64, 128) and tex.image.channels == 4:
        atex = tex
    em = None
    es = p.inputs.get('Emission Strength')
    ec = p.inputs.get('Emission Color')
    if es is not None and ec is not None and es.default_value > 0 and max(ec.default_value[:3]) > 0.01:
        em = (np.array(ec.default_value[:3]), float(es.default_value))
    return tex, col, atex, em


_PIX = {}


def image_array(img):
    """(H, W, 4) float32 of an image, LINEAR colour for sRGB images (Blender's pixels are not colour-managed)."""
    key = img.name
    if key in _PIX:
        return _PIX[key]
    w, h = img.size
    if w == 0 or h == 0:
        return None
    a = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    a = a.reshape(h, w, 4)
    if img.colorspace_settings.name.lower().startswith('srgb') and not img.is_float:
        a[..., :3] = srgb_to_lin(a[..., :3]).astype(np.float32)
    _PIX[key] = a
    return a


def _sample(arr, uv):
    h, w = arr.shape[:2]
    u = np.mod(uv[:, 0], 1.0)
    v = np.mod(uv[:, 1], 1.0)
    x = np.clip((u * w).astype(np.int64), 0, w - 1)
    y = np.clip((v * h).astype(np.int64), 0, h - 1)
    return arr[y, x]


# --------------------------------------------------------------------------- mesh helpers
def join_meshes(objs, name):
    """All mesh objects -> one object `name` (world transforms applied, materials kept in order)."""
    bm = bmesh.new()
    mats = []
    for o in objs:
        if o.type != 'MESH' or not len(o.data.polygons):
            continue
        idx = {}
        for i, m in enumerate(o.data.materials):
            if m not in mats:
                mats.append(m)
            idx[i] = mats.index(m)
        tmp = bmesh.new()
        tmp.from_mesh(o.data)
        tmp.transform(o.matrix_world)
        if o.matrix_world.determinant() < 0:
            bmesh.ops.reverse_faces(tmp, faces=tmp.faces[:])
        for f in tmp.faces:
            f.material_index = idx.get(f.material_index, 0)
        me2 = bpy.data.meshes.new('tmp')
        tmp.to_mesh(me2)
        tmp.free()
        bm.from_mesh(me2)
        bpy.data.meshes.remove(me2)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def _apply_decimate(ob, ratio):
    mod = ob.modifiers.new('fold', 'DECIMATE')
    mod.ratio = max(0.001, min(1.0, ratio))
    dg = bpy.context.evaluated_depsgraph_get()
    new = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    ob.modifiers.remove(mod)
    old = ob.data
    ob.data = new
    bpy.data.meshes.remove(old)


def _cut_mask_mats(ob):
    return {i for i, m in enumerate(ob.data.materials) if m is not None and base_info(m)[2] is not None}


def _split_cut(ob, cut_idx):
    """Move the faces of alpha-cut materials into their own object (they are thinned, not collapsed)."""
    if not cut_idx:
        return None
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    keep = bmesh.new()
    keep.from_mesh(ob.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index not in cut_idx], context='FACES')
    bmesh.ops.delete(keep, geom=[f for f in keep.faces if f.material_index in cut_idx], context='FACES')
    me_c = bpy.data.meshes.new(ob.name + '_cards')
    bm.to_mesh(me_c)
    keep.to_mesh(ob.data)
    bm.free()
    keep.free()
    for m in ob.data.materials:
        me_c.materials.append(m)
    oc = bpy.data.objects.new(ob.name + '_cards', me_c)
    bpy.context.scene.collection.objects.link(oc)
    return oc


def thin_cards(ob, budget, seed=0):
    """Keep at most `budget` triangles of leaf cards by dropping whole cards (connected islands) at random."""
    me = ob.data
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    if tris <= budget:
        return tris, tris
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    seen, islands = set(), []
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
    rnd = random.Random(seed)
    rnd.shuffle(islands)
    keep_frac = budget / tris
    drop, kept = [], 0
    for isl in islands:
        t = sum(len(f.verts) - 2 for f in isl)
        if kept + t <= budget:
            kept += t
        else:
            drop += isl
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    bm.to_mesh(me)
    bm.free()
    # thinner foliage reads sparse: grow the cards that remain a little around their own centres
    grow = min(1.6, (1.0 / max(keep_frac, 1e-3)) ** 0.25)
    if grow > 1.01:
        bm = bmesh.new()
        bm.from_mesh(me)
        seen = set()
        for f in bm.faces:
            if f.index in seen:
                continue
            stack, verts = [f], set()
            seen.add(f.index)
            while stack:
                g = stack.pop()
                verts.update(g.verts)
                for e in g.edges:
                    for h in e.link_faces:
                        if h.index not in seen:
                            seen.add(h.index)
                            stack.append(h)
            c = sum((v.co for v in verts), Vector()) / len(verts)
            for v in verts:
                v.co = c + (v.co - c) * grow
        bm.to_mesh(me)
        bm.free()
    return tris, kept


def clean_facets(ob, faces, dissolve_deg=1.5):
    """Merge by distance, collapse to about `faces` facets, dissolve near-flat neighbours into one facet."""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0002)
    bm.to_mesh(me)
    bm.free()
    n0 = len(me.polygons)
    tri0 = sum(len(p.vertices) - 2 for p in me.polygons)
    if faces and tri0 > faces:
        _apply_decimate(ob, faces / tri0)
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    if dissolve_deg > 0:
        bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(dissolve_deg), use_dissolve_boundaries=False,
                                 verts=bm.verts[:], edges=bm.edges[:], delimit={'MATERIAL', 'SEAM', 'UV'})
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    return n0, tri0


def settle(objs):
    """Base at z = 0, centred on x/y (metres kept). Returns the offset applied and the size."""
    lo = Vector((1e9, 1e9, 1e9))
    hi = -lo
    for o in objs:
        for v in o.data.vertices:
            lo = Vector(map(min, lo, v.co))
            hi = Vector(map(max, hi, v.co))
    off = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    for o in objs:
        for v in o.data.vertices:
            v.co -= off
    return off, hi - lo


# --------------------------------------------------------------------------- face colours -> sheets
def face_colours(me):
    """(F, 3) linear colour of each face from its material's texture (centroid + one sample per corner, half way to
    the centroid), alpha per face for cut materials, and the face areas."""
    F = len(me.polygons)
    mi = np.empty(F, dtype=np.int64)
    me.polygons.foreach_get('material_index', mi)
    area = np.empty(F)
    me.polygons.foreach_get('area', area)
    ls = np.empty(F, dtype=np.int64)
    me.polygons.foreach_get('loop_start', ls)
    lt = np.empty(F, dtype=np.int64)
    me.polygons.foreach_get('loop_total', lt)
    col = np.zeros((F, 3))
    alpha = np.ones(F)
    uvl = me.uv_layers.active
    uv = None
    if uvl is not None and len(me.loops):
        uv = np.empty(len(me.loops) * 2)
        uvl.data.foreach_get('uv', uv)
        uv = uv.reshape(-1, 2)
    face_of_loop = np.repeat(np.arange(F), lt)
    for k, m in enumerate(me.materials):
        sel = mi == k
        if not sel.any():
            continue
        tex, c, atex, _ = base_info(m)
        col[sel] = c
        if tex is None or uv is None:
            continue
        arr = image_array(tex.image)
        if arr is None:
            continue
        cen = np.add.reduceat(uv, ls, axis=0) / lt[:, None] if F else uv[:0]
        loop_sel = sel[face_of_loop]
        pts = (uv[loop_sel] + cen[face_of_loop[loop_sel]]) / 2
        s_l = _sample(arr, pts)
        s_c = _sample(arr, cen[sel])
        acc = np.zeros((F, 4))
        np.add.at(acc, face_of_loop[loop_sel], s_l)
        acc[sel] += s_c
        acc[sel] /= (lt[sel] + 1)[:, None]
        tint = c if tex is not None else 1.0
        col[sel] = acc[sel, :3] * tint
        if atex is not None:
            alpha[sel] = acc[sel, 3]
    return col, mi, area, alpha


def _kmeans(x, w, k, iters=12):
    # farthest-point start, weighted Lloyd iterations
    cen = [x[np.argmax(w)]]
    for _ in range(1, k):
        d = np.min([((x - c) ** 2).sum(1) for c in cen], axis=0)
        cen.append(x[np.argmax(d * w)])
    cen = np.array(cen)
    for _ in range(iters):
        lab = np.argmin(((x[:, None, :] - cen[None]) ** 2).sum(2), axis=1)
        for j in range(k):
            s = lab == j
            if s.any():
                cen[j] = (x[s] * w[s, None]).sum(0) / w[s].sum()
    lab = np.argmin(((x[:, None, :] - cen[None]) ** 2).sum(2), axis=1)
    return cen, lab


def cluster(x, w, max_k=MAX_SHEETS):
    """The sheets of one material: grow k while the new sheet is a distinct colour covering enough area."""
    best = (x[:1] * 0 + (x * w[:, None]).sum(0) / max(w.sum(), 1e-12), np.zeros(len(x), dtype=np.int64))
    if len(x) < 8:
        return best
    for k in range(2, max_k + 1):
        cen, lab = _kmeans(x, w, k)
        share = np.array([w[lab == j].sum() for j in range(k)]) / max(w.sum(), 1e-12)
        dmin = min(np.linalg.norm(cen[a] - cen[b]) for a in range(k) for b in range(a + 1, k))
        if share.min() < MIN_SHARE or dmin < SPLIT_DIST:
            break
        best = (cen, lab)
    return best


def _majority(me, labels, passes=2, ignore=10 ** 6):
    """A face whose label none of its neighbours share takes its neighbours' most common label."""
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    nb = [[g.index for e in f.edges for g in e.link_faces if g is not f] for f in bm.faces]
    bm.free()
    lab = labels.copy()
    for _ in range(passes):
        new = lab.copy()
        for i, n in enumerate(nb):
            if not n:
                continue
            vals = lab[n]
            vals = vals[vals != ignore]
            if lab[i] != ignore and len(vals) and (vals == lab[i]).sum() == 0:
                u, c = np.unique(vals, return_counts=True)
                new[i] = u[np.argmax(c)]
        lab = new
    return lab


def _sheet_material(name, lin, *, cut_img=None, glow=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = principled(m)
    p.inputs['Base Color'].default_value = (*[float(v) for v in lin], 1.0)
    p.inputs['Roughness'].default_value = 0.85
    m['pc_sheet'] = [float(v) for v in lin]
    if cut_img is not None:
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = cut_img
        t.interpolation = 'Closest'
        nt.links.new(t.outputs['Color'], p.inputs['Base Color'])
        nt.links.new(t.outputs['Alpha'], p.inputs['Alpha'])
        m.blend_method = 'CLIP' if hasattr(m, 'blend_method') else None
        m['pc_cut'] = 1
    if glow is not None:
        p.inputs['Emission Color'].default_value = (*[float(v) for v in glow[0]], 1.0)
        p.inputs['Emission Strength'].default_value = glow[1]
        m['pc_glow'] = [float(v) for v in glow[0]] + [float(glow[1])]
    return m


def _cut_image(tex_img, lin, name, size=512):
    """A cut-out mask: the sheet's flat colour, the source's alpha (so the glb holds the silhouette, not the photo)."""
    arr = image_array(tex_img)
    h, w = arr.shape[:2]
    ys = (np.arange(size) * h // size).astype(np.int64)
    xs = (np.arange(size) * w // size).astype(np.int64)
    a = arr[ys][:, xs, 3]
    a = (a > 0.5).astype(np.float32)
    out = np.empty((size, size, 4), dtype=np.float32)
    s = lin_to_srgb(lin)
    out[..., 0], out[..., 1], out[..., 2], out[..., 3] = s[0], s[1], s[2], a
    img = bpy.data.images.new(name, size, size, alpha=True)
    img.pixels.foreach_set(out.ravel())
    img.file_format = 'PNG'
    img.alpha_mode = 'STRAIGHT'
    img.pack()
    return img


def make_sheets(ob, asset_id):
    """Replace ob's source materials with sheets of paper in the model's own colours. Returns the sheet list."""
    me = ob.data
    col, mi, area, alpha = face_colours(me)
    src = list(me.materials)
    tag = asset_id.split('/')[-1]
    new_mats, sheets = [], []
    new_index = np.zeros(len(mi), dtype=np.int64)
    for k, m in enumerate(src):
        sel = np.where(mi == k)[0]
        if not len(sel):
            continue
        tex, c, atex, glow = base_info(m) if m else (None, np.array((0.6,) * 3), None, None)
        if atex is not None:
            w = area[sel] * np.clip(alpha[sel], 0.05, 1)
            lin = (col[sel] * w[:, None]).sum(0) / max(w.sum(), 1e-12)
            img = _cut_image(atex.image, lin, f'PC_cut_{tag}_{k}')
            mat = _sheet_material(f'PC_sheet_{tag}_{len(new_mats)}', lin, cut_img=img)
            new_index[sel] = len(new_mats)
            new_mats.append(mat)
            sheets.append({'name': mat.name, 'srgb': [round(float(v), 3) for v in lin_to_srgb(lin)], 'cut': True,
                           'share': float(area[sel].sum() / max(area.sum(), 1e-12)), 'from': m.name})
            continue
        x = lin_to_srgb(col[sel])
        cen, lab = cluster(x, area[sel])
        if len(cen) > 1:
            full = np.full(len(mi), -1, dtype=np.int64)
            full[sel] = lab
            sm = _majority(me, np.where(full < 0, 10 ** 6, full))
            lab = sm[sel]
        for j in range(len(cen)):
            s = sel[lab == j]
            if not len(s):
                continue
            lin = (col[s] * area[s, None]).sum(0) / max(area[s].sum(), 1e-12)
            mat = _sheet_material(f'PC_sheet_{tag}_{len(new_mats)}', lin, glow=glow)
            new_index[s] = len(new_mats)
            new_mats.append(mat)
            sheets.append({'name': mat.name, 'srgb': [round(float(v), 3) for v in lin_to_srgb(lin)], 'cut': False,
                           'share': float(area[s].sum() / max(area.sum(), 1e-12)), 'from': m.name if m else None})
    me.materials.clear()
    for m in new_mats:
        me.materials.append(m)
    me.polygons.foreach_set('material_index', new_index.astype(np.int32))
    flat_shade(ob)
    return sheets


def flat_shade(ob):
    """Every face flat: drop the source's custom (smooth) normals, which would override the flat flag on export."""
    me = ob.data
    if me.has_custom_normals:
        bpy.context.view_layer.objects.active = ob
        with bpy.context.temp_override(object=ob, active_object=ob):
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
    for p in me.polygons:
        p.use_smooth = False
    me.update()


def paperize(objs, asset_id, faces=1500, cards=24000, seed=0):
    """Imported objects -> one paper object (solid facets, plus the leaf cards if the model has any)."""
    name = 'PAPER_' + asset_id.split('/')[-1]
    ob = join_meshes(objs, name)
    for o in objs:
        bpy.data.objects.remove(o, do_unlink=True)
    stats = {'faces_in': len(ob.data.polygons), 'tris_in': sum(len(p.vertices) - 2 for p in ob.data.polygons)}
    oc = _split_cut(ob, _cut_mask_mats(ob))
    clean_facets(ob, faces)
    parts = [ob]
    if oc is not None:
        t0, t1 = thin_cards(oc, cards, seed)
        stats['card_tris_in'], stats['card_tris'] = t0, t1
        parts.append(oc)
    sheets = []
    for o in parts:
        sheets += make_sheets(o, asset_id + ('_cards' if o is oc else ''))
    if oc is not None:
        # one object: solids and cards share a mesh
        bpy.ops.object.select_all(action='DESELECT')
        for o in parts:
            o.select_set(True)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.join()
    off, size = settle([ob])
    me = ob.data
    stats.update(faces=len(me.polygons), tris=sum(len(p.vertices) - 2 for p in me.polygons),
                 size_m=[round(v, 4) for v in size], offset_m=[round(v, 4) for v in off], sheets=sheets,
                 flat=not any(p.use_smooth for p in me.polygons), materials=len(me.materials))
    ob['pc_asset'] = asset_id
    return ob, stats


# --------------------------------------------------------------------------- the paper surface
def paper_look(ob, size=None, seed=0, angle=30.0):
    """Give a paper model (sheet materials, from paperize or a paper.glb) its paper shader, in place. Mesh data
    shared by several objects is done once. Returns the number of folds marked."""
    me = ob.data
    if me.get('pc_paper'):
        return 0
    if size is None:
        size = max(ob.dimensions) / max(max(ob.scale), 1e-6) or 1.0
    width = min(0.06, max(0.0025, 0.007 * size))
    fibre = min(60.0, max(6.0, 60.0 / max(size, 1.0)))
    pm.add_facet_attribute(ob, seed)
    folds = pm.add_fold_lines(ob, angle)
    done = {}
    for i, m in enumerate(me.materials):
        if m is None:
            continue
        if m.name in done:
            me.materials[i] = done[m.name]
            continue
        p = principled(m)
        lin = tuple(m.get('pc_sheet', p.inputs['Base Color'].default_value[:3] if p else (0.6, 0.6, 0.6)))
        cut = m.get('pc_cut') or (p is not None and p.inputs['Alpha'].is_linked)
        img = None
        if cut and p is not None:
            t = _upstream_image(p.inputs['Alpha']) or _upstream_image(p.inputs['Base Color'])
            img = t.image if t else None
            if 'pc_sheet' not in m and img is not None:
                arr = image_array(img)
                msk = arr[..., 3] > 0.5
                lin = tuple(arr[..., :3][msk].mean(0)) if msk.any() else lin
        glow = None
        g = m.get('pc_glow')
        if g is None and p is not None and p.inputs['Emission Strength'].default_value > 0:
            ec = p.inputs['Emission Color'].default_value
            if max(ec[:3]) > 0.01:
                g = list(ec[:3]) + [p.inputs['Emission Strength'].default_value]
        if g is not None:
            glow = (tuple(g[:3]), float(g[3]))
        pmat = pm.paper_material('PCP_' + m.name, tuple(float(v) for v in lin), translucency=0.3 if cut else 0.0,
                                 fibre_scale=fibre, fibre_strength=0.10, facet_var=0.09, flat=True, glow=glow,
                                 seed=(seed + i) % 97 / 97.0)
        pm.paper_surface(pmat, ink=0.85, width=width, light=0.45, mottle=0.14, mottle_scale=max(0.8, 7.0 / size), ao=0.4)
        if cut and img is not None:
            nt = pmat.node_tree
            out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
            src = out.inputs['Surface'].links[0].from_socket
            t = nt.nodes.new('ShaderNodeTexImage')
            t.image = img
            t.interpolation = 'Closest'
            tr = nt.nodes.new('ShaderNodeBsdfTransparent')
            mx = nt.nodes.new('ShaderNodeMixShader')
            nt.links.new(t.outputs['Alpha'], mx.inputs['Fac'])
            nt.links.new(tr.outputs['BSDF'], mx.inputs[1])
            nt.links.new(src, mx.inputs[2])
            nt.links.new(mx.outputs['Shader'], out.inputs['Surface'])
            if hasattr(pmat, 'blend_method'):
                pmat.blend_method = 'HASHED'
        done[m.name] = pmat
        me.materials[i] = pmat
    me['pc_paper'] = 1
    return folds


# --------------------------------------------------------------------------- the studio still
def studio(ob, png, res=(512, 512), samples=48, az=-35.0, el=24.0, lens=50.0):
    """A neutral three-quarter still: pale paper floor, soft key from the front-left, fill, rim; the model framed."""
    sc = bpy.context.scene
    for o in list(sc.objects):
        if o is not ob and o.type in ('CAMERA', 'LIGHT') or o.name.startswith('STUDIO_'):
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.view_layer.update()
    corners = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    lo = Vector(map(min, *corners))
    hi = Vector(map(max, *corners))
    c = (lo + hi) / 2
    r = max((hi - lo).length / 2, 0.05)
    floor_mat = pm.paper_material('STUDIO_floor', (0.30, 0.29, 0.27), translucency=0.0, fibre_scale=30, facet_var=0.0)
    bpy.ops.mesh.primitive_plane_add(size=r * 40, location=(c.x, c.y, lo.z))
    fl = bpy.context.active_object
    fl.name = 'STUDIO_floor'
    fl.data.materials.append(floor_mat)
    w = sc.world or bpy.data.worlds.new('STUDIO_world')
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value = (0.36, 0.35, 0.34, 1)
    bg.inputs['Strength'].default_value = 0.25
    cam_d = bpy.data.cameras.new('STUDIO_cam')
    cam_d.lens = lens
    fov = 2 * math.atan(18.0 / lens)
    dist = r / math.sin(fov / 2) * 1.08
    cam = bpy.data.objects.new('STUDIO_cam', cam_d)
    sc.collection.objects.link(cam)
    a, e = math.radians(az), math.radians(el)
    d = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
    cam.location = c + d * dist
    cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam_d.clip_start, cam_d.clip_end = dist / 100, dist * 50
    sc.camera = cam

    def light(name, vec, energy, size, color=(1, 0.97, 0.92)):
        L = bpy.data.lights.new('STUDIO_' + name, 'AREA')
        L.energy = energy * r * r * 4
        L.size = size * r * 2
        L.color = color
        o = bpy.data.objects.new('STUDIO_' + name, L)
        o.location = c + Vector(vec).normalized() * r * 6
        o.rotation_euler = (c - o.location).to_track_quat('-Z', 'Y').to_euler()
        sc.collection.objects.link(o)
    light('key', (-1.0, -1.2, 1.4), 260, 2.0)
    light('fill', (1.4, -0.8, 0.5), 60, 3.0, (0.9, 0.95, 1.0))
    light('rim', (0.6, 1.4, 1.2), 160, 1.5)
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    try:
        sc.view_settings.view_transform = 'AgX'
    except TypeError:
        sc.view_settings.view_transform = 'Filmic'
    sc.render.filepath = os.path.abspath(png)
    os.makedirs(os.path.dirname(os.path.abspath(png)), exist_ok=True)
    bpy.ops.render.render(write_still=True)
    return png
