"""The paper swords every film uses, in the timeline's weapon frame: guard (or grip line) at x = 0,
blade +x, edge -y, handle -x. Moved out of film_modular.py (26 Nov) so the sword-draw test and any
other scene build the SAME sword (one base, varied by data)."""
import math

import bpy
from mathutils import Quaternion


class _Scene:
    collection = None


sc = _Scene()


def use(collection):
    """Where new swords are linked (a bpy Collection)."""
    sc.collection = collection


def _flat_mat(nm, rgba, rough, metal=0.0):
    m = bpy.data.materials.new(nm)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    if b:
        b.inputs['Base Color'].default_value = rgba
        b.inputs['Roughness'].default_value = rough
        if 'Metallic' in b.inputs:
            b.inputs['Metallic'].default_value = metal
    return m


def build_katana(name, blade_len=0.91, handle=0.33):
    """A folded-paper katana in the weapon frame: blade +x from the guard, edge -y, handle -x."""
    import bmesh as _bm

    def slab(cx, lx, ly, lz, mat):
        me = bpy.data.meshes.new(name + '_m')
        b = _bm.new()
        _bm.ops.create_cube(b, size=1.0)
        _bm.ops.scale(b, vec=(lx, ly, lz), verts=b.verts[:])
        _bm.ops.translate(b, vec=(cx, 0, 0), verts=b.verts[:])
        b.to_mesh(me)
        b.free()
        o = bpy.data.objects.new(name + '_part', me)
        me.materials.append(mat)
        for pg in me.polygons:
            pg.use_smooth = False
        sc.collection.objects.link(o)
        return o

    steel = _flat_mat(name + '_steel', (0.86, 0.88, 0.92, 1), 0.32, 0.35)   # silver card: a full mirror read black on dark sets
    dark = _flat_mat(name + '_dark', (0.045, 0.045, 0.055, 1), 0.55)
    wrap = _flat_mat(name + '_wrap', (0.10, 0.09, 0.12, 1), 0.72)
    root = bpy.data.objects.new(name, None)
    root.rotation_mode = 'QUATERNION'
    sc.collection.objects.link(root)
    # blade long in x, thin in y (the flat of the sheet), deeper in z (the edge): a katana reads from
    # its silhouette, so it is a touch deeper than it is thick.
    for ob in (slab(blade_len / 2, blade_len, 0.0075, 0.029, steel),
               slab(0.0, 0.012, 0.088, 0.088, dark),
               slab(-handle / 2, handle, 0.030, 0.038, wrap)):
        ob.parent = root
    return root


def build_bokken(name, blade_len=1.05, handle=0.30):
    """Musashi's oar sword (research/ganryujima.md, tradition: carved from a spare oar, ~110 cm, longer than
    Kojiro's blade): one piece of wood, no guard, a blade that thickens toward the grip and bends slightly
    toward the back, in the same weapon frame as the katana (blade +x from the grip line, edge -y, handle -x).
    Chosen by the timeline's weapon `kind` - the film's cast says `"weapon": "bokken"` - so it is data."""
    import bmesh as _bm
    wood = _flat_mat(name + '_wood', (0.30, 0.18, 0.09, 1), 0.82)
    root = bpy.data.objects.new(name, None)
    root.rotation_mode = 'QUATERNION'
    sc.collection.objects.link(root)
    n = 5
    pts = []                                   # the spine: straight handle, then a slight sweep toward +y
    for i in range(n + 1):
        t = i / n
        pts.append((-handle + (handle + blade_len) * t, 0.035 * max(0.0, t - 0.3) ** 2, 0.0))
    for i in range(n):
        (x0, y0, _), (x1, y1, _) = pts[i], pts[i + 1]
        t = (i + 0.5) / n
        w = 0.036 - 0.014 * max(0.0, t - 0.35)  # edge depth tapers toward the tip
        me = bpy.data.meshes.new(name + '_m%d' % i)
        b = _bm.new()
        _bm.ops.create_cube(b, size=1.0)
        L = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
        _bm.ops.scale(b, vec=(L * 1.02, 0.028, w), verts=b.verts[:])
        _bm.ops.rotate(b, cent=(0, 0, 0), matrix=Quaternion((0, 0, 1), math.atan2(y1 - y0, x1 - x0)).to_matrix(),
                       verts=b.verts[:])
        _bm.ops.translate(b, vec=((x0 + x1) / 2, (y0 + y1) / 2, 0), verts=b.verts[:])
        b.to_mesh(me)
        b.free()
        o = bpy.data.objects.new(name + '_part', me)
        me.materials.append(wood)
        for pg in me.polygons:
            pg.use_smooth = False
        sc.collection.objects.link(o)
        o.parent = root
    return root
