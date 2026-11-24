"""Use the GPU for Cycles when one is available (Kaggle T4, RunPod, a local NVIDIA card); CPU otherwise.
   Any render script calls use_gpu(scene) right before rendering. Set BLENDER_GPU=0 to force the CPU."""
import os
import bpy


def use_gpu(scene):
    if os.environ.get('BLENDER_GPU', '1') == '0':
        scene.cycles.device = 'CPU'
        return 'CPU'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for kind in ('OPTIX', 'CUDA', 'HIP', 'METAL', 'ONEAPI'):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
            gpus = [d for d in prefs.devices if d.type == kind]
            if gpus:
                for d in prefs.devices:
                    d.use = d.type == kind
                scene.cycles.device = 'GPU'
                print(f'[gpu] Cycles on {kind}: {", ".join(d.name for d in gpus)}')
                return kind
        except Exception:
            continue
    scene.cycles.device = 'CPU'
    print('[gpu] no GPU found, using the CPU')
    return 'CPU'
