"""Use the GPU for Cycles when one is available (Kaggle T4, RunPod, a local NVIDIA card); CPU otherwise.
   Any render script calls use_gpu(scene) right before rendering.
     BLENDER_GPU=0                force the CPU
     BLENDER_GPU=cuda|optix|hip|metal|oneapi   force one backend (and only that one)
   Kaggle note: OPTIX on Kaggle's T4 driver takes the whole session down (the kernel is CANCELLED a few seconds
   into the first GPU render), so CUDA is tried before OPTIX. docs/KAGGLE-RENDER.md has the measurements.
"""
import os
import bpy

ORDER = ('CUDA', 'OPTIX', 'HIP', 'METAL', 'ONEAPI')


def use_gpu(scene):
    want = os.environ.get('BLENDER_GPU', '1').strip().lower()
    if want in ('0', 'cpu', 'no', 'false'):
        scene.cycles.device = 'CPU'
        print('[gpu] BLENDER_GPU=0, using the CPU')
        return 'CPU'
    kinds = (want.upper(),) if want.upper() in ORDER else ORDER
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for kind in kinds:
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
        except Exception:                                      # noqa: BLE001
            continue
    scene.cycles.device = 'CPU'
    print('[gpu] no GPU found, using the CPU')
    return 'CPU'
