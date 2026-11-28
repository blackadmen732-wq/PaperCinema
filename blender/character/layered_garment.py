"""LAYERED PAPER GARMENTS: a sleeve as a stack of stiff paper plates, each on its own small joint, each trailing
the one above (Mark, 28 Nov: "the sleeve has multiple different sections... build some part that will be able to
move"; docs/AUTOPILOT.md item 17).

Opt-in per recipe:   "layers": {"sleeve_R": 4, "sleeve_L": 4}
               or    "layers": {"sleeve_R": {"plates": 4, "from": 0.05, "overlap": 0.012}}
A recipe without "layers" builds exactly as before (nothing here runs).

What it does, at build time, in the REST pose (blender/character/modular_builder.build calls add_layers):
  1. the sleeve section's HANGING part is found in the sleeve's own frame: on the forearm (elbow to wrist), the
     direction the sleeve's mass hangs away from the arm axis (`hang`, the mean offset of its far vertices). A
     vertex's "height" is how far it hangs along that direction from the arm.
  2. that part is cut into N bands by height (from `from` m off the arm to the hem); each band becomes its own
     object, keeps the AI sleeve's mesh, UVs and paint, and is parented RIGIDLY to its plate joint. Each band also
     carries a thin strip of the band above it, tucked 2 mm under (an overlap, like scales), so a swing opens no
     gap. The part that wraps the arm stays skinned to the arm as before (its weights near the cut ramp to the
     forearm, so the seam does not open when the elbow bends).
  3. the plate joints are a CHAIN: plate 0 a child of the forearm joint (rT / lT) at the band's top edge, plate j a
     child of plate j-1 at the next cut. The parent carries the child, so a swing of plate 0 reaches plate 3 later:
     the ripple comes free.
Nothing new is needed downstream: cloth_springs.ClothSprings gives every plate joint (it carries `pc_plate`) its
own spring, stiffness falling down the chain; the bake records every joint's rotation (`rec['J']`) and the render
replays it.
"""
import bmesh
import bpy
from mathutils import Vector

import part_registry as reg

DOWN = Vector((0.0, 0.0, -1.0))
GARMENTS = {'sleeve': ('sleeve_upper', 'sleeve_hanging')}     # recipe key prefix -> the slots it layers


def _spec(v):
    return {'plates': int(v)} if isinstance(v, (int, float)) else dict(v)


def _garments(built, kind, side):
    slots = GARMENTS[kind]
    return [o for o in built if o.type == 'MESH' and o.vertex_groups
            and reg.PARTS.get(o.get('pc_recipe', ''), {}).get('slot') in slots
            and o.get('pc_socket', '').endswith('.' + side)]


def _plate(rig, name, parent, pos, rest_q):
    e = bpy.data.objects.new('J_' + name + '_' + rig.name, None)
    e.empty_display_size = 0.02
    e.rotation_mode = 'YZX'                                  # the mode cloth_springs._aim writes
    rig.coll.objects.link(e)
    e.parent = parent
    bpy.context.view_layer.update()
    e.matrix_world = rest_q.to_matrix().to_4x4()
    e.matrix_world.translation = pos
    bpy.context.view_layer.update()
    rig.J[name] = e
    return e


def add_layers(rig, built, bind, layers):
    """Cut the recipe's layered garments into plate bands on a joint chain. Returns (new band objects, report)."""
    bands_all, report = [], []
    for key, v in layers.items():
        if key == 'note':
            continue
        kind, side = key.rsplit('_', 1)
        spec = _spec(v)
        n = max(1, int(spec.get('plates', 4)))
        h0 = float(spec.get('from', 0.05))                    # the arm's own radius + a little: that part stays skinned
        ov = float(spec.get('overlap', 0.012))
        tuck = float(spec.get('tuck', 0.002))
        s = side.lower()
        E, H = Vector(reg.REST[s + 'E']), Vector(reg.REST[s + 'H'])
        u = (H - E).normalized()
        zone_lo = -float(spec.get('above_elbow', 0.03))      # how far above the elbow the hanging part may start

        def along(p):
            return (p - E).dot(u)

        def perp(p):
            return p - (E + u * along(p))

        for ob in _garments(built, kind, side):
            M = ob.matrix_world
            P = [M @ vv.co for vv in ob.data.vertices]
            far = [perp(p) for p in P if along(p) >= zone_lo and perp(p).length > h0]
            if len(far) < 20:
                report.append(f'{key}: {ob.name} has no hanging part (skipped)')
                continue
            hang = sum(far, Vector()).normalized()
            hz = lambda p: perp(p).dot(hang)                  # noqa: E731  height in the sleeve's own frame
            top = max(hz(p) for p in P if along(p) >= zone_lo)
            dh = (top - h0) / n
            # clean cuts: bisect the mesh on every band edge (and the overlap strip's edge, and the elbow end of the
            # hanging part) so the bands are straight-edged plates, not a ragged triangle-by-triangle split
            bm = bmesh.new()
            bm.from_mesh(ob.data)
            Mi = M.inverted()
            hang_l = (Mi.to_3x3() @ hang).normalized()
            planes = [(E + u * zone_lo, u)]
            for j in range(n):
                for h_ in (h0 + j * dh, h0 + j * dh - ov):
                    planes.append((E + u * (along(E) + 0.0) + hang * h_, hang))
            for co, no in planes:
                no_l = (Mi.to_3x3() @ no).normalized()
                geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
                bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=Mi @ co, plane_no=no_l)
            bm.to_mesh(ob.data)
            bm.free()
            ob.data.update()
            del hang_l
            # every face: which band (or -1: stays skinned on the arm)
            centers = {f.index: M @ f.center for f in ob.data.polygons}
            band_of = {}
            for fi, c in centers.items():
                if along(c) < zone_lo or hz(c) < h0:
                    band_of[fi] = -1
                else:
                    band_of[fi] = min(n - 1, int((hz(c) - h0) / dh))
            mine = [fi for fi, b in band_of.items() if b >= 0]
            mid = sum((along(centers[fi]) for fi in mine), 0.0) / max(1, len(mine))
            A = E + u * mid                                    # the hinge line's point on the forearm axis
            rest_q = DOWN.rotation_difference(hang)
            plates = []
            for j in range(n):
                nm = f'{s}Plate{j}'
                parent = rig.J[s + 'T'] if j == 0 else plates[-1]
                e = _plate(rig, nm, parent, A + hang * (h0 + j * dh), rest_q)
                e['pc_plate'] = j
                e['pc_plates'] = n
                e['pc_plate_len'] = dh if j < n - 1 else max(dh, top - (h0 + j * dh))
                e['pc_plate_side'] = side
                e['pc_rest_rot'] = list(e.rotation_euler)
                plates.append(e)
            # the bands: band j's own faces + a strip of the band above it (or of the skinned part), tucked under
            for j, e in enumerate(plates):
                lo = h0 + j * dh
                own = {fi for fi in mine if band_of[fi] == j}
                strip = {fi for fi, c in centers.items() if along(c) >= zone_lo and lo - ov <= hz(c) < lo} - own
                bm = bmesh.new()
                bm.from_mesh(ob.data)
                bm.faces.ensure_lookup_table()
                keep = own | strip
                bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in keep], context='FACES')
                bm.normal_update()
                bm.verts.ensure_lookup_table()
                own_v = set()
                for f in bm.faces:                             # face indices shift after delete: re-classify by centre
                    if hz(M @ f.calc_center_median()) >= lo:
                        own_v.update(vv.index for vv in f.verts)
                for vv in bm.verts:
                    if vv.index not in own_v:
                        vv.co -= vv.normal * tuck
                me = ob.data.copy()
                me.name = f'{ob.name}_band{j}'
                bm.to_mesh(me)
                bm.free()
                me.transform(M)
                band = bpy.data.objects.new(me.name, me)
                for c_ in ob.users_collection:
                    c_.objects.link(band)
                for k_ in ('pc_recipe', 'pc_socket', 'pc_part'):
                    if k_ in ob:
                        band[k_] = ob[k_]
                band['pc_band'] = j
                band['pc_layered_from'] = ob.name
                band.parent = e
                band.matrix_parent_inverse = e.matrix_world.inverted()
                band['pc_bind'] = 'rigid'
                bind[band.name] = ('rigid', e.name, [e.name])
                bands_all.append(band)
            # the source keeps only the part on the arm; its weights ramp to the forearm next to the cut
            bm = bmesh.new()
            bm.from_mesh(ob.data)
            bm.faces.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if band_of.get(f.index, -1) >= 0], context='FACES')
            bmesh.ops.delete(bm, geom=[vv for vv in bm.verts if not vv.link_faces], context='VERTS')
            bm.to_mesh(ob.data)
            bm.free()
            gS, gT = ob.vertex_groups.get(s + 'S'), ob.vertex_groups.get(s + 'T')
            ramped = 0
            if gS and gT:
                for vv in ob.data.vertices:
                    p = M @ vv.co
                    wh = min(1.0, max(0.0, (hz(p) - (h0 - 0.04)) / 0.04))
                    wa = min(1.0, max(0.0, (along(p) - (zone_lo - 0.04)) / 0.04))
                    w = min(wh, wa)
                    if w <= 0:
                        continue
                    ws = {g.group: g.weight for g in vv.groups}
                    t_ = ws.get(gT.index, 0.0)
                    gT.add([vv.index], t_ + (1.0 - t_) * w, 'REPLACE')
                    gS.add([vv.index], ws.get(gS.index, 0.0) * (1.0 - w), 'REPLACE')
                    ramped += 1
            report.append(f'{key}: {ob.name} -> {n} plates on {s}T, hang {tuple(round(x, 2) for x in hang)}, '
                          f'bands {h0:.3f}-{top:.3f} m off the arm ({dh * 100:.1f} cm each), '
                          f'{len(mine)} faces moved, {ramped} seam weights ramped')
    bpy.context.view_layer.update()
    return bands_all, report
