"""Export a modular paper character's bind pose as a skeletal FBX and material manifest."""
import argparse
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import bpy
from mathutils import Matrix

sys.path.insert(0, str(Path(__file__).resolve().parent))
import modular_builder as mb


def material_info(material):
    key = material.get('pc_washi')
    return {
        'paper': dict(mb.pm.washi_spec(key)) if key else None,
        'base_color_linear': list(material.diffuse_color)[:3],
        'roughness': material.roughness,
        'grain_uv': 'PaperGrain',
        'radial_grain': bool(material.get('pc_grain_radial')),
        'emission_color_linear': list(material.get('pc_emission_color', (0, 0, 0))),
        'emission_strength': material.get('pc_emission_strength', 0),
    }


def export_character(recipe_path, output):
    recipe = mb.load_recipe(recipe_path)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    ch = mb.build(recipe, pose='neutral')
    rig = ch['armature']
    rig.name = 'Armature'
    rig.data.pose_position = 'REST'
    materials, parts = {}, []
    bpy.ops.object.select_all(action='DESELECT')
    for mesh in ch['objects']:
        if mesh.get('pc_internal'):
            continue
        kind, bone, _ = ch['bind'][mesh.name]
        mesh.parent = rig
        mesh.matrix_parent_inverse = Matrix.Identity(4)
        if kind == 'rigid':
            group = mesh.vertex_groups.new(name=bone)
            group.add(list(range(len(mesh.data.vertices))), 1.0, 'REPLACE')
            skin = mesh.modifiers.new('skin', 'ARMATURE')
            skin.object = rig
        mesh.select_set(True)
        names = [mat.name for mat in mesh.data.materials]
        for mat in mesh.data.materials:
            materials.setdefault(mat.name, material_info(mat))
        parts.append({'mesh': mesh.name, 'part': mesh['pc_recipe'], 'socket': mesh['pc_socket'], 'materials': names})
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.context.view_layer.update()

    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = output.with_suffix('.materials.json')
    with TemporaryDirectory(dir=output.parent) as directory:
        staging = Path(directory)
        staged_fbx = staging / output.name
        status = bpy.ops.export_scene.fbx(
            filepath=str(staged_fbx), use_selection=True, object_types={'ARMATURE', 'MESH'},
            apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
            axis_forward='-Y', axis_up='Z', add_leaf_bones=False, bake_anim=False, use_mesh_modifiers=True,
        )
        if status != {'FINISHED'} or not staged_fbx.is_file() or not staged_fbx.stat().st_size:
            raise RuntimeError(f'FBX export failed for {recipe_path}')
        staged_manifest = staging / manifest.name
        staged_manifest.write_text(json.dumps({
            'version': 1,
            'recipe': recipe['id'],
            'units': 'metres',
            'forward': '-Y',
            'up': '+Z',
            'skeleton': 'PC_Rig_v1',
            'bones': {bone.name: bone.parent.name if bone.parent else None for bone in rig.data.bones},
            'parts': parts,
            'materials': materials,
        }, indent=2) + '\n', encoding='utf-8')
        staged_fbx.replace(output)
        staged_manifest.replace(manifest)
    print(f'[FBX] {len(parts)} skinned pieces, {len(rig.data.bones)} bones → {output}')
    print(f'[FBX] material manifest → {manifest}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipe', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    if args.out.suffix.lower() != '.fbx':
        parser.error('--out must end in .fbx')
    export_character(args.recipe, args.out.resolve())


if __name__ == '__main__':
    main()
