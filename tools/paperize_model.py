"""PAPERIZE A MODEL: any glTF / GLB (a Poly Haven prop, a tree, a generated part) -> the same thing folded from paper
(Mark, 28 Nov: "the test we did with the bucket, put it in and transform it to paper").

  B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
  $B -b -P tools/paperize_model.py -- --in assets/polyhaven/wooden_bucket_01/wooden_bucket_01_1k.gltf \
      --out output/library/paper/wooden_bucket_01 [--id poly-haven/wooden_bucket_01] [--faces 1500] [--cards 24000]
      [--res 512] [--samples 48] [--no-still]
  $B -b -P tools/paperize_model.py -- --check output/library/paper/wooden_bucket_01/paper.glb   # re-import, print stats

Writes into --out:
  paper.glb     clean flat facets in sheets of paper of the model's own colours (sampled from its textures), base at
                z = 0, centred in x/y, metres kept; plain materials a glTF holds (colour, cut-out mask, glow) marked
                pc_sheet / pc_cut / pc_glow in their extras. blender/library/paperlook.py paper_look() turns them back
                into the paper surface (fold lines, ink, fibre) wherever the model is used.
  preview.png   a neutral three-quarter studio still WITH the paper surface (look at it).
  paper.json    faces/tris before and after, size_m, sheets (sRGB colour, share, cut), flat, materials.
How: blender/library/paperlook.py (paperize, paper_look, studio). Test: python3 tools/test_paperize_model.py.
"""
import json
import os
import sys

import bpy

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(REPO, 'blender', 'library'))
import paperlook as PL  # noqa: E402

ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(name, default=None):
    k = '--' + name
    return ARGV[ARGV.index(k) + 1] if k in ARGV else default


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_model(path):
    before = set(bpy.data.objects)
    ext = os.path.splitext(path)[1].lower()
    if ext in ('.gltf', '.glb'):
        bpy.ops.import_scene.gltf(filepath=os.path.abspath(path))
    elif ext == '.obj':
        bpy.ops.wm.obj_import(filepath=os.path.abspath(path))
    elif ext == '.fbx':
        bpy.ops.import_scene.fbx(filepath=os.path.abspath(path))
    else:
        sys.exit(f'[paperize] unknown model type {ext}')
    new = [o for o in bpy.data.objects if o not in before]
    bpy.context.view_layer.update()
    return new


def export_glb(ob, path):
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.gltf(filepath=os.path.abspath(path), export_format='GLB', use_selection=True,
                              export_extras=True, export_apply=True, export_yup=True, export_texcoords=True,
                              export_normals=True, export_materials='EXPORT', export_image_format='AUTO')


def check(path):
    reset()
    objs = import_model(path)
    meshes = [o for o in objs if o.type == 'MESH']
    me = meshes[0].data if meshes else None
    lo = [min((o.matrix_world @ v.co)[i] for o in meshes for v in o.data.vertices) for i in range(3)]
    hi = [max((o.matrix_world @ v.co)[i] for o in meshes for v in o.data.vertices) for i in range(3)]
    mats = [m for o in meshes for m in o.data.materials if m]
    # flat = the corners of a face share one normal (glTF has no flat flag: the importer marks faces smooth and
    # carries the facet normals as custom split normals; a triangle of a near-flat n-gon keeps the n-gon's normal)
    bent = 0
    for o in meshes:
        d = o.data
        cn = d.corner_normals
        for p in d.polygons:
            n0 = cn[p.loop_indices[0]].vector
            if any(cn[li].vector.dot(n0) < 0.9999 for li in p.loop_indices):
                bent += 1
    out = {'objects': len(meshes), 'faces': sum(len(o.data.polygons) for o in meshes),
           'tris': sum(len(p.vertices) - 2 for o in meshes for p in o.data.polygons),
           'size_m': [round(h - l, 4) for l, h in zip(lo, hi)], 'min_z': round(lo[2], 4),
           'materials': len(mats), 'sheets': sum(1 for m in mats if 'pc_sheet' in m),
           'smooth_faces': bent,
           'mesh': me.name if me else None}
    print('PC_CHECK ' + json.dumps(out))
    return out


def main():
    if arg('check'):
        check(arg('check'))
        return
    src, out = arg('in'), arg('out')
    if not src or not out:
        sys.exit(__doc__)
    aid = arg('id') or 'poly-haven/' + os.path.basename(os.path.dirname(os.path.abspath(src)))
    os.makedirs(out, exist_ok=True)
    reset()
    objs = [o for o in import_model(src)]
    meshes = [o for o in objs if o.type == 'MESH']
    if not meshes:
        sys.exit(f'[paperize] {src}: no meshes')
    for o in [o for o in objs if o.type != 'MESH']:
        bpy.data.objects.remove(o, do_unlink=True)
    ob, st = PL.paperize(meshes, aid, faces=int(arg('faces', 1500)), cards=int(arg('cards', 24000)))
    export_glb(ob, os.path.join(out, 'paper.glb'))
    st.update(id=aid, source=os.path.relpath(os.path.abspath(src), REPO), glb_mb=round(os.path.getsize(os.path.join(out, 'paper.glb')) / 1e6, 3))
    if '--no-still' not in ARGV:
        st['folds'] = PL.paper_look(ob, size=max(st['size_m']))
        r = int(arg('res', 512))
        PL.studio(ob, os.path.join(out, 'preview.png'), res=(r, r), samples=int(arg('samples', 48)))
    json.dump(st, open(os.path.join(out, 'paper.json'), 'w'), indent=1)
    print('[paperize] %s: %d -> %d faces (%d tris), %d sheets, size %s m -> %s'
          % (aid, st['faces_in'], st['faces'], st['tris'], len(st['sheets']), st['size_m'], out))


main()
