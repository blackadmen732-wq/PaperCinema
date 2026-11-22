# Runs ON the GPU pod: image → textured 3D model (GLB) with Microsoft TRELLIS (MIT licence).
#   python gen_trellis.py name1 name2 ...   reads /workspace/in/<name>.png, writes /workspace/out/<name>.glb
import os, sys, time
os.environ.setdefault('ATTN_BACKEND', 'xformers')
os.environ.setdefault('SPCONV_ALGO', 'native')
sys.path.insert(0, '/workspace/TRELLIS')
from PIL import Image
import imageio
from trellis.pipelines import TrellisImageTo3DPipeline
from trellis.utils import postprocessing_utils, render_utils

os.makedirs('/workspace/out', exist_ok=True)
pipe = TrellisImageTo3DPipeline.from_pretrained('microsoft/TRELLIS-image-large')
pipe.cuda()
for name in sys.argv[1:]:
    t = time.time()
    img = Image.open(f'/workspace/in/{name}.png')
    out = pipe.run(img, seed=7, sparse_structure_sampler_params={'steps': 12, 'cfg_strength': 7.5},
                   slat_sampler_params={'steps': 12, 'cfg_strength': 3})
    glb = postprocessing_utils.to_glb(out['gaussian'][0], out['mesh'][0], simplify=0.9, texture_size=2048)
    glb.export(f'/workspace/out/{name}.glb')
    frames = render_utils.render_video(out['gaussian'][0], num_frames=48)['color']
    imageio.mimsave(f'/workspace/out/{name}_turntable.mp4', frames, fps=24)
    print(f'DONE {name} in {time.time() - t:.0f}s', flush=True)
print('ALL_DONE')
