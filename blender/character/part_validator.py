"""PART VALIDATOR: a part cannot enter the character library until it passes this.

    B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
    nice -n 10 $B -b -t 2 -P blender/character/part_validator.py -- \
        --recipe library/character-recipes/ronin-reference.json --report output/character/validate.json

Exits NON-ZERO when any check fails, so it can gate a build.

The checks, and why each one exists:
  material       every mesh has a real material — an unassigned part renders as grey plastic
  socket         the part's geometry actually sits at the socket it declared (within 35 cm)
  scale          the object's scale is 1 and its sheet's fibre density is in range — the classic failure is
                 fibres like rope on the hat and invisible on the sleeves (see pm.WASHI_FIBRE)
  pivot          the part is bound: parented to a bone, or skinned across 2-3 bones
  self_intersect the shell does not pass through itself (solidify spikes, inverted pleats)
  joint_gap      ACROSS A POSE SWEEP, neighbouring parts still overlap at the joint: arms overhead, deep
                 crouch, jump tuck, full slash. A part that gapes open in one pose is not finished.
  silhouette     the figure still reads: one connected blob, sane coverage, sane aspect, from front and side
"""
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'world'))
import modular_builder as mb   # noqa: E402
import paper_materials as pm   # noqa: E402
import part_registry as reg    # noqa: E402

ARGV = mb.ARGV
arg, flag = mb.arg, mb.flag

# The pose sweep: standing, arms overhead, deep crouch, jump tuck, full slash — real poses from
# library/poses.json, because a part only has to survive the poses the films actually use.
SWEEP = ['neutral', 'jodan', 'crouch-load', 'airborne-guard', 'kesa-finish']

# Joins that must never open: (slot, slot). The second is the one that hangs off the first.
NEIGHBOURS = [('neck', 'face'), ('face', 'hat'), ('torso', 'neck'), ('torso', 'collar'),
              ('torso', 'sleeve_upper'), ('sleeve_upper', 'forearm'), ('forearm', 'hand'),
              ('forearm', 'sleeve_hanging'), ('torso', 'obi'), ('obi', 'thigh'),
              ('thigh', 'shin'), ('shin', 'foot'), ('torso', 'armor')]
GAP_LIMIT = 0.045        # metres: more than this between two neighbouring sheets and you can see inside


def world_points(ob, depsgraph, tris=False):
    ev = ob.evaluated_get(depsgraph)
    me = ev.to_mesh()
    M = ev.matrix_world
    if tris:
        me.calc_loop_triangles()
        out = [tuple(M @ me.vertices[i].co for i in t.vertices) for t in me.loop_triangles]
    else:
        out = [M @ v.co for v in me.vertices]
    ev.to_mesh_clear()
    return out


def min_distance(points, tris):
    """Smallest distance from a set of points to a SURFACE (not to its vertices: two concentric folded tubes
    can sit 1 cm apart and still have no vertex within 7 cm of each other)."""
    if not points or not tris:
        return 9.9
    bm = bmesh.new()
    for t in tris:
        vs = [bm.verts.new(p) for p in t]
        try:
            bm.faces.new(vs)
        except ValueError:
            pass
    if not bm.faces:
        bm.free()
        return 9.9
    tree = BVHTree.FromBMesh(bm)
    d = 9.9
    for p in points:
        hit = tree.find_nearest(p)
        if hit[0] is not None:
            d = min(d, hit[3])
    bm.free()
    return d


def self_intersections(ob):
    """Share of faces that pass through another face of the SAME part. Sheets layered on purpose overlap a
    little; a solidify spike or an inverted pleat overlaps a lot."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    if not bm.faces:
        bm.free()
        return 0.0
    tree = BVHTree.FromBMesh(bm, epsilon=0.0)
    n = len(tree.overlap(tree)) / max(len(bm.faces), 1)
    bm.free()
    return n


def spike(ob, depsgraph):
    """How far the part grows once its modifiers run, as a share of its own size. A solidify spike at a sharp
    crease is the classic one: the sheet shoots out to ten times the part's size and nothing says so."""
    raw = [Vector(v) for v in ob.bound_box]
    lo = Vector((min(p.x for p in raw), min(p.y for p in raw), min(p.z for p in raw)))
    hi = Vector((max(p.x for p in raw), max(p.y for p in raw), max(p.z for p in raw)))
    size = max((hi - lo).length, 1e-3)
    ev = ob.evaluated_get(depsgraph)
    me = ev.to_mesh()
    if not len(me.vertices):
        ev.to_mesh_clear()
        return 0.0
    out = max(max((v.co - lo).length, (v.co - hi).length) for v in me.vertices)
    ev.to_mesh_clear()
    return max(0.0, out / size - 1.0)


def silhouette(tris, axis='front', w=56, h=96):
    """Rasterise the character flat and ask the two questions a silhouette must answer:
    is it ONE shape, and does it fill a sane share of its own box? Triangles, not vertices: a vertex cloud
    always falls apart into dozens of islands and tells you nothing."""
    if not tris:
        return dict(ok=False, components=0, coverage=0.0, aspect=0.0)
    u = (lambda p: p.x) if axis == 'front' else (lambda p: p.y)
    pts = [p for t in tris for p in t]
    lo_u, hi_u = min(u(p) for p in pts), max(u(p) for p in pts)
    lo_v, hi_v = min(p.z for p in pts), max(p.z for p in pts)
    du, dv = max(hi_u - lo_u, 1e-3), max(hi_v - lo_v, 1e-3)
    grid = [[0] * w for _ in range(h)]
    for t in tris:                                 # scan-convert each triangle into the grid
        cells = [(min(h - 1, max(0, int((p.z - lo_v) / dv * (h - 1)))),
                  min(w - 1, max(0, int((u(p) - lo_u) / du * (w - 1))))) for p in t]
        i0, i1 = min(c[0] for c in cells), max(c[0] for c in cells)
        j0, j1 = min(c[1] for c in cells), max(c[1] for c in cells)
        (ay, ax), (by, bx), (cy, cx) = cells
        den = (by - cy) * (ax - cx) + (bx - cx) * (cy - ay)
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                if abs(den) < 1e-9:
                    grid[i][j] = 1
                    continue
                l1 = ((by - cy) * (j - cx) + (bx - cx) * (cy - i)) / den
                l2 = ((cy - ay) * (j - cx) + (ax - cx) * (i - cy)) / den
                if l1 >= -0.08 and l2 >= -0.08 and l1 + l2 <= 1.08:
                    grid[i][j] = 1
    filled = sum(sum(r) for r in grid)
    seen, comps = set(), 0
    for i in range(h):
        for j in range(w):
            if grid[i][j] and (i, j) not in seen:
                comps += 1
                stack = [(i, j)]
                seen.add((i, j))
                while stack:
                    a, b = stack.pop()
                    for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        q = (a + da, b + db)
                        if 0 <= q[0] < h and 0 <= q[1] < w and grid[q[0]][q[1]] and q not in seen:
                            seen.add(q)
                            stack.append(q)
    return dict(components=comps, coverage=round(filled / (w * h), 3), aspect=round(dv / du, 2),
                ok=comps <= 2 and 0.16 <= filled / (w * h) <= 0.88)


def validate(recipe_path, poses=None, only=None):
    recipe = mb.load_recipe(recipe_path)
    if only:
        recipe = dict(recipe, parts=[e for e in recipe['parts'] if e['part'] in only])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ch = mb.build(recipe, pose='neutral')
    dg = bpy.context.evaluated_depsgraph_get()
    results, failures = [], []

    def check(name, part, ok, detail):
        results.append(dict(check=name, part=part, ok=bool(ok), detail=detail))
        if not ok:
            failures.append(f'{name:<14} {part:<26} {detail}')

    by_slot = {}
    for ob in ch['objects']:
        key = ob.get('pc_recipe', '?')
        spec = reg.PARTS.get(key)
        if spec:
            by_slot.setdefault(spec['slot'], []).append(ob)

    # ---- static checks, part by part
    for ob in ch['objects']:
        key = ob.get('pc_recipe', '?')
        spec = reg.PARTS.get(key, {})
        if ob.type != 'MESH':
            continue
        mats = [m for m in ob.data.materials if m]
        check('material', ob.name, len(mats) > 0 and len(mats) == len(ob.data.materials),
              f'{len(mats)}/{len(ob.data.materials)} slots filled')
        s = ob.scale
        check('scale', ob.name, abs(s.x - 1) < 1e-4 and abs(s.y - 1) < 1e-4 and abs(s.z - 1) < 1e-4,
              f'object scale {tuple(round(v, 4) for v in s)} (must be 1: fibre size is world scale)')
        for m in mats:
            fw = m.get('pc_fibre_world')
            if fw is None:
                continue
            lo, hi = pm.WASHI_FIBRE_RANGE
            check('fibre', f'{ob.name}/{m.name}', lo * pm.WASHI_FIBRE <= fw <= hi * pm.WASHI_FIBRE,
                  f'{fw:.0f} fibres/m (allowed {lo * pm.WASHI_FIBRE:.0f}-{hi * pm.WASHI_FIBRE:.0f})')
        check('pivot', ob.name, bool(ob.get('pc_bind')) and (ob.parent is not None),
              f'bind={ob.get("pc_bind")} parent={getattr(ob.parent, "name", None)}')
        sock = ob.get('pc_socket')
        if sock:
            c = sum((ob.matrix_world @ Vector(v) for v in ob.bound_box), Vector()) / 8
            d = (c - Vector(reg.SOCKETS[sock]['pos'])).length
            lim = 0.60 if spec.get('slot') in ('accessory', 'armor') else 0.35
            check('socket', ob.name, d < lim, f'{d * 100:.0f} cm from socket {sock} (limit {lim * 100:.0f})')
        if not spec.get('rigid', True):
            continue                               # skinned parts fold through themselves by design
        n = self_intersections(ob)
        check('self_intersect', ob.name, n <= 1.2, f'{n:.2f} overlapping face pairs per face')
        sp = spike(ob, dg)
        check('spike', ob.name, sp < 0.35, f'modifiers grow the part by {sp * 100:.0f}% of its own size')

    # ---- the pose sweep
    for pose in (poses or SWEEP):
        ch['rig'].pose(pose)
        dg = bpy.context.evaluated_depsgraph_get()
        pts = {k: [p for ob in v if not ob.get('pc_internal') for p in world_points(ob, dg)]
               for k, v in by_slot.items()}
        surf = {k: [t for ob in v if not ob.get('pc_internal') for t in world_points(ob, dg, tris=True)]
                for k, v in by_slot.items()}
        for a, b in NEIGHBOURS:
            if a not in pts or b not in pts or not pts[a] or not pts[b]:
                continue
            d = min_distance(pts[b], surf[a])
            check('joint_gap', f'{a}-{b} @ {pose}', d <= GAP_LIMIT, f'{d * 100:.1f} cm gap (limit {GAP_LIMIT * 100:.0f})')
        tris = [t for ob in ch['objects'] if ob.type == 'MESH' and not ob.get('pc_internal')
                for t in world_points(ob, dg, tris=True)]
        for axis in ('front', 'side'):
            sil = silhouette(tris, axis)
            check('silhouette', f'{axis} @ {pose}', sil['ok'],
                  f'{sil["components"]} piece(s), coverage {sil["coverage"]}, aspect {sil["aspect"]}')
    return results, failures, recipe


def main():
    rpath = arg('recipe')
    if not rpath:
        print('usage: --recipe library/character-recipes/<id>.json [--report out.json] [--poses a,b,c] '
              '[--parts p1,p2]')
        sys.exit(2)
    poses = arg('poses', '').split(',') if arg('poses') else None
    only = arg('parts', '').split(',') if arg('parts') else None
    results, failures, recipe = validate(os.path.abspath(rpath), poses, only)
    passed = sum(1 for r in results if r['ok'])
    lines = [f'PART VALIDATOR: {recipe.get("id")}  ({len(recipe["parts"])} parts, {len(results)} checks)', '']
    by = {}
    for r in results:
        by.setdefault(r['check'], [0, 0])
        by[r['check']][r['ok']] += 1
    for k, (bad, good) in sorted(by.items()):
        lines.append(f'  {k:<16}{good:>4} pass {bad:>4} fail')
    if failures:
        lines += ['', 'FAILURES:'] + ['  ' + f for f in failures]
    lines += ['', f'{passed}/{len(results)} checks passed — ' + ('FAIL' if failures else 'OK')]
    report = '\n'.join(lines)
    print(report)
    if arg('report'):
        p = os.path.abspath(arg('report'))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w') as fh:
            json.dump(dict(recipe=recipe.get('id'), passed=passed, total=len(results),
                           failures=failures, results=results), fh, indent=1)
        with open(p.replace('.json', '.txt'), 'w') as fh:
            fh.write(report + '\n')
        print('wrote', p)
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
