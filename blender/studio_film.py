"""Build an editable Blender scene and render a short from a studio scene file."""
import argparse
from bisect import bisect_right
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path[:0] = [str(HERE / 'character'), str(HERE)]
import modular_builder as mb
from gpu_setup import use_gpu
from rig_trellis import _fcurves

PROFILES = {'preview': (18, '360x640', 12), 'master': (24, '720x1280', 64)}
FEET = ('lfoot', 'rfoot')


def smooth(t):
    return t * t * (3 - 2 * t)


def ordered_times(items, key, end):
    times = [item[key] for item in items]
    if not times or times[0] != 0 or times != sorted(set(times)) or times[-1] > end:
        raise ValueError(f'{key} entries must start at zero, increase strictly and stay within the film')
    return times


def timeline(script, fps):
    duration = script['duration']
    count = round(duration * fps)
    if count < 2 or abs(count / fps - duration) > 1e-6:
        raise ValueError('Set a duration that contains a whole number of frames at the selected rate.')
    cuts = [round(t * fps) + 1 for t in ordered_times(script['shots'], 'start', duration)]
    if len(set(cuts)) != len(cuts) or cuts[-1] > count:
        raise ValueError('Every shot needs at least one frame.')
    if not script['cast']:
        raise ValueError('Cast at least one character.')
    for actor in script['cast'].values():
        ordered_times(actor['keys'], 't', duration)
        if 'plant_width' in actor and actor['plant_width'] <= 0:
            raise ValueError('plant_width must be positive.')
        channels = set(actor.get('base', ()))
        for key in actor['keys']:
            channels.update(key.get('over', ()))
        if channels - mb.BASE.keys():
            raise ValueError(f'Unsupported pose channels: {sorted(channels - mb.BASE.keys())}')
    for cue in script.get('sounds', []):
        if not 0 <= cue['t'] < duration or cue['len'] <= 0 or not cue.get('sfx'):
            raise ValueError(f'Invalid local sound cue {cue}')
    return count, cuts


def make_studio(scene, stage):
    """A seamless paper-stage floor with broad photographic lighting and controlled amber apertures."""
    palette = stage.get('palette', 'cool')
    if palette not in ('cool', 'warm'):
        raise ValueError(f'Unknown studio palette {palette!r}; use cool or warm.')
    warm = palette == 'warm'
    rows = [(-11.0, 0.0), (2.8, 0.0)]
    rows += [(2.8 + math.sin(a) * 2.2, (1 - math.cos(a)) * 2.2)
             for a in (i * math.pi / 28 for i in range(1, 15))]
    rows.append((5.0, 8.0))
    vertices = [(x, y, z) for y, z in rows for x in (-10.0, 10.0)]
    faces = [(i, i + 1, i + 3, i + 2) for i in range(0, len(vertices) - 2, 2)]
    floor_mesh = bpy.data.meshes.new('Seamless studio floor')
    floor_mesh.from_pydata(vertices, [], faces)
    floor = bpy.data.objects.new('Seamless studio floor', floor_mesh)
    scene.collection.objects.link(floor)
    for face in floor_mesh.polygons:
        face.use_smooth = True
    paper = bpy.data.materials.new('Soft gray backdrop')
    paper.use_nodes = True
    color = (.43, .35, .30) if warm else (.36, .41, .46)
    paper.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*color, 1)
    paper.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = .96
    floor_mesh.materials.append(paper)

    sky = bpy.data.worlds.new('Soft studio ambient')
    sky.use_nodes = True
    sky.node_tree.nodes['Background'].inputs['Color'].default_value = (.58, .67, .77, 1)
    sky.node_tree.nodes['Background'].inputs['Strength'].default_value = .17
    scene.world = sky
    lights = [
        ('Grazing key', (-3.10, -1.22, 3.27), (0, 0, 1.11), 270, 1.55, (1.0, .93, .84)),
        ('Soft fill', (1.88, -1.55, 1.87), (0, -.04, .87), 61, 2.7, (.84, .90, 1.0)),
        ('Cuff rim', (1.3, 2.05, 2.62), (0, 0, 1.02), 155, 1.6, (1.0, .82, .60)),
        ('Sweep wash', (-1.0, 1.72, 3.95), (.2, 4.85, 1.35), 285, 3.9, (.78, .86, 1.0)),
    ]
    for name, pos, aim, power, size, col in lights:
        data = bpy.data.lights.new(name, 'AREA')
        data.energy, data.size, data.color = power, size, col
        light = bpy.data.objects.new(name, data)
        light.location = pos
        light.rotation_euler = (Vector(aim) - light.location).to_track_quat('-Z', 'Y').to_euler()
        scene.collection.objects.link(light)
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.view_settings.exposure = -.25


def actor_track(spec, recipe):
    times = [key['t'] for key in spec['keys']]
    rest = mb.BASE | mb.POSES[recipe.get('pose', 'neutral')] | recipe.get('pose_overrides', {}) | spec.get('base', {})
    samples = []
    for key in spec['keys']:
        samples.append(rest | (mb.POSES[key['pose']] if 'pose' in key else {}) | spec.get('base', {}) | key.get('over', {}))

    def at(t):
        i = min(max(1, bisect_right(times, t)), len(times) - 1)
        if i == 0 or t >= times[-1]:
            return dict(samples[-1])
        f = smooth((t - times[i - 1]) / (times[i] - times[i - 1]))
        return {k: (a + (samples[i][k] - a) * f) for k, a in samples[i - 1].items() if k in mb.BASE}
    return at


def linear_keys(objects):
    for obj in objects:
        if obj.animation_data and obj.animation_data.action:
            for curve in _fcurves(obj.animation_data.action):
                for key in curve.keyframe_points:
                    key.interpolation = 'LINEAR'


def bake_cast(script, fps, count):
    reports, built = {}, {}
    wind = script.get('stage', {}).get('paper_motion', .40)
    for name, spec in script['cast'].items():
        recipe = mb.cast_recipe(spec.get('recipe'), character=name, lead=not built)
        sample = actor_track(spec, recipe)
        character = mb.build(recipe, name=name, pose=sample(0))
        built[name] = character
        rig = character['rig']
        plant_width = spec.get('plant_width')
        for bone in rig.rig.pose.bones:
            bone.rotation_mode = 'QUATERNION'

        rig.pose(sample(0), plant_width=plant_width)
        feet = [o for o in character['objects'] if o.get('pc_recipe') == 'tabi_zori']
        sole = min(((o.matrix_world @ Vector(corner)).z for o in feet for corner in o.bound_box), default=0)
        floor_offset = script.get('stage', {}).get('floor_z', 0) - sole
        anchors, drift = {}, 0.0
        for frame in range(1, count + 1):
            t = (frame - 1) / fps
            pose = sample(t)
            lagged = sample(max(0, t - .095))
            pose['y'] += floor_offset
            pose['sway'] += wind * (.038 * math.sin(3.3 * t) + .085 * (pose['rsz'] - lagged['rsz']))
            pose['swayx'] += wind * .033 * math.sin(3.7 * t + .5)
            pose['rwz'] += wind * .035 * math.sin(4.3 * t)
            pose['lwz'] -= wind * .029 * math.sin(4.0 * t + .8)
            rig.pose(pose, plant_width=plant_width)
            for foot in FEET:
                point = rig.J[foot].matrix_world.translation
                anchors.setdefault(foot, point.copy())
                drift = max(drift, (point - anchors[foot]).length)
            for joint in rig.J.values():
                joint.keyframe_insert('location', frame=frame)
                joint.keyframe_insert('rotation_euler', frame=frame)
            for bone in rig.rig.pose.bones:
                bone.keyframe_insert('location', frame=frame)
                bone.keyframe_insert('rotation_quaternion', frame=frame)
                bone.keyframe_insert('scale', frame=frame)
        linear_keys([rig.rig, *rig.J.values()])
        if plant_width is not None and drift > .012:
            raise ValueError(f'{name}: planted foot drifted {drift:.3f} m; check stance, crouch and root motion.')
        reports[name] = {'recipe': recipe['id'], 'planted': plant_width is not None,
                         'max_foot_travel_m': round(drift, 5)}
    return built, reports


def bake_cameras(scene, shots, cuts, count):
    cameras = []
    for shot, first, after in zip(shots, cuts, cuts[1:] + [count + 1]):
        camera = mb.camera(scene, shot['from']['camera'], shot['from']['target'], shot['lens'])
        camera.name = shot['id']
        camera.data.name = shot['id']
        camera.data.dof.use_dof = shot.get('fstop') is not None
        if camera.data.dof.use_dof:
            camera.data.dof.aperture_fstop = shot['fstop']
        camera.rotation_mode = 'QUATERNION'
        marker = scene.timeline_markers.new(shot['id'], frame=first)
        marker.camera = camera
        start, end = shot['from'], shot.get('to', shot['from'])
        for frame in range(first, after):
            p = smooth((frame - first) / max(1, after - first - 1))
            camera.location = Vector(start['camera']).lerp(Vector(end['camera']), p)
            target = Vector(start['target']).lerp(Vector(end['target']), p)
            direction = target - camera.location
            camera.rotation_quaternion = direction.to_track_quat('-Z', 'Y')
            camera.data.dof.focus_distance = direction.length
            camera.keyframe_insert('location', frame=frame)
            camera.keyframe_insert('rotation_quaternion', frame=frame)
            camera.data.keyframe_insert('dof.focus_distance', frame=frame)
        linear_keys([camera, camera.data])
        cameras.append(camera)
    scene.camera = cameras[0]
    return cameras


def audit_cameras(scene, cameras, shots, actors, cuts, count):
    """Check projected actor centers and measure how much of each silhouette is inside sampled shots."""
    report = []
    for cam, shot, first, after in zip(cameras, shots, cuts, cuts[1:] + [count + 1]):
        checks = []
        for frame in sorted({first, (first + after - 1) // 2, after - 1}):
            scene.frame_set(frame)
            dg = bpy.context.evaluated_depsgraph_get()
            for name, char in actors.items():
                head = char['joints']['head'].matrix_world.translation
                p = world_to_camera_view(scene, cam, head)
                if p.z <= 0 or not (0 <= p.x <= 1 and 0 <= p.y <= 1):
                    raise ValueError(f'{cam.name}, frame {frame}: {name} head is outside the camera.')
                points = []
                for obj in char['objects']:
                    if obj.get('pc_internal'):
                        continue
                    ev = obj.evaluated_get(dg)
                    points += [world_to_camera_view(scene, cam, ev.matrix_world @ v.co) for v in ev.data.vertices]
                coverage = sum(0 <= p.x <= 1 and 0 <= p.y <= 1 and p.z > 0 for p in points) / len(points)
                if shot.get('full_body') and coverage < .98:
                    raise ValueError(f'{cam.name}, frame {frame}: {name} is clipped in a full-body shot.')
                checks.append({'frame': frame, 'actor': name, 'visible_vertex_fraction': round(coverage, 3)})
        report.append({'shot': cam.name, 'start_frame': first, 'end_frame': after - 1, 'camera_samples': checks})
    scene.frame_set(1)
    return report


def complete_png(path):
    try:
        with path.open('rb') as image:
            image.seek(-12, os.SEEK_END)
            return image.read() == b'\x00\x00\x00\x00IEND\xaeB\x60\x82'
    except OSError:
        return False


def frame_manifest(args, fps, res, samples):
    files = [args.scene, Path(__file__), HERE / 'character' / 'modular_builder.py',
             HERE / 'character' / 'part_registry.py', HERE / 'character' / 'rig_trellis.py',
             HERE / 'world' / 'paper_materials.py', REPO / 'library' / 'poses.json',
             REPO / 'library' / 'character-models.json']
    for folder in ('character-recipes', 'paper-materials'):
        files.extend(sorted((REPO / 'library' / folder).glob('*.json')))
    if args.set:
        files.append(args.set)
    digest = hashlib.sha256()
    for file in files:
        with file.open('rb') as source:
            digest.update(hashlib.file_digest(source, 'sha256').digest())
    return {'inputs': digest.hexdigest(), 'fps': fps, 'resolution': res, 'samples': samples,
            'native_denoise': args.profile == 'master' and not (args.no_denoise or args.cpu_denoise),
            'blender': bpy.app.version_string}


def encode(script, fps, frames, out, count):
    missing = [n for n in range(1, count + 1) if not complete_png(frames / f'f{n:04d}.png')]
    if missing:
        raise RuntimeError(f'Missing rendered frames: {missing}')
    dry = out / 'picture.mp4'
    final = out / 'paper-film.mp4'
    temp = out / '.encoded-film.mp4'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(fps), '-start_number', '1',
                    '-i', str(frames / 'f%04d.png'), '-frames:v', str(count), '-threads', '3', '-c:v', 'libx264',
                    '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(dry)], check=True)
    if script.get('sounds'):
        audio = out / 'audio-cues.json'
        audio.write_text(json.dumps({'duration': script['duration'], 'sounds': script['sounds']}, indent=2) + '\n')
        subprocess.run(['node', 'engine/sound.mjs', '--local-only', '--film', str(audio), '--video', str(dry),
                        '--out', str(temp), '--events', str(out / '.no-events'), '--voice', str(out / '.no-voice')],
                       cwd=REPO, check=True)
        temp.replace(final)
        dry.unlink()
    else:
        dry.replace(final)
    return final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--set', type=Path, help='Use an existing Blender set with cameras authored in its world coordinates')
    parser.add_argument('--profile', choices=PROFILES, default='preview')
    parser.add_argument('--stills', action='store_true', help='Only render the middle frame of each shot')
    parser.add_argument('--build-only', action='store_true', help='Save the editable scene and audit, without rendering')
    parser.add_argument('--no-denoise', action='store_true')
    parser.add_argument('--cpu-denoise', action='store_true', help='Use the optional OIDN Python filter after rendering')
    parser.add_argument('--resume', action='store_true', help='Reuse complete frames from matching render settings')
    parser.add_argument('--res', help='Override the render profile dimensions, for example 360x640')
    parser.add_argument('--samples', type=int)
    parser.add_argument('--threads', type=int, default=min(8, os.cpu_count() or 2))
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    script = json.loads(args.scene.read_text(encoding='utf-8'))
    fps, res, samples = PROFILES[args.profile]
    count, cuts = timeline(script, fps)
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if not args.stills and not args.build_only:
        required = ('ffmpeg', 'node') if script.get('sounds') else ('ffmpeg',)
        for tool in required:
            if not shutil.which(tool):
                raise RuntimeError(f'Render encoding requires {tool}.')
        if args.cpu_denoise:
            subprocess.run(['python3', '-c', 'import oidn, PIL, numpy'], check=True)

    if args.set:
        bpy.ops.wm.open_mainfile(filepath=str(args.set.resolve()))
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.timeline_markers.clear()
    scene.render.fps = fps
    scene.frame_start, scene.frame_end = 1, count
    mb.render_settings(scene, args.res or res, args.samples or samples,
                       denoise=args.profile == 'master' and not (args.no_denoise or args.cpu_denoise))
    scene.render.threads = args.threads
    scene.cycles.max_bounces = 5
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = .09 if args.profile == 'preview' else .035
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = .24
    use_gpu(scene)

    if args.set:
        for obj in scene.objects:
            if any(coll.name.startswith('CHAR_') for coll in obj.users_collection):
                obj.hide_render = True
    else:
        make_studio(scene, script.get('stage', {}))
    actors, actor_report = bake_cast(script, fps, count)
    cameras = bake_cameras(scene, script['shots'], cuts, count)
    camera_report = audit_cameras(scene, cameras, script['shots'], actors, cuts, count)
    scene.render.filepath = '//frames/f'
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'paper-film.blend'))
    (out / 'film-audit.json').write_text(json.dumps({'title': script['title'], 'fps': fps, 'frames': count,
                                                     'cast': actor_report, 'shots': camera_report}, indent=2) + '\n')
    if args.build_only:
        return
    if args.stills:
        for shot in camera_report:
            scene.frame_set((shot['start_frame'] + shot['end_frame']) // 2)
            mb.render(scene, out / 'stills' / f'{shot["shot"]}.png')
        return
    frames = out / 'frames'
    frames.mkdir(exist_ok=True)
    manifest_path = frames / 'settings.json'
    signature = frame_manifest(args, fps, args.res or res, args.samples or samples)
    old = json.loads(manifest_path.read_text()) if manifest_path.is_file() else None
    if args.resume and old != signature:
        raise ValueError('There is no matching render to resume. Run the updated scene without --resume.')
    if not args.resume:
        for frame_path in frames.glob('f[0-9]*.png'):
            frame_path.unlink()
        manifest_path.write_text(json.dumps(signature, indent=2) + '\n')
    for frame in range(1, count + 1):
        path = frames / f'f{frame:04d}.png'
        if args.resume and complete_png(path):
            continue
        scene.frame_set(frame)
        path.unlink(missing_ok=True)
        mb.render(scene, path)
    if args.cpu_denoise:
        filtered = out / 'denoised'
        subprocess.run(['python3', str(REPO / 'tools' / 'denoise_frames.py'), str(frames), str(filtered)], check=True)
        frames = filtered
    print(f'Encoded {encode(script, fps, frames, out, count)}', flush=True)


if __name__ == '__main__':
    main()
