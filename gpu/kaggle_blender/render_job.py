# Kaggle job (free GPU): render a Paper Cinema Blender scene with Cycles on the T4 GPU.
# Inputs: the private dataset reviewboost/paper-cinema-blender (repo.tgz = blender/ scripts, assets/models, library/).
# Edit JOB below, then: bash gpu/kaggle_blender/run.sh push / status / get
import subprocess, os, time, glob
JOB = {
    'script': 'blender/character/trellis_shot.py',
    'args': ['--model', 'ronin_base', '--frames', '1-96', '--samples', '48', '--res', '720x1280', '--out', '/kaggle/working/frames/'],
    'mp4': '/kaggle/working/shot.mp4',
}
t0 = time.time()
def sh(c, show=1500):
    print('$', c[:200], flush=True)
    r = subprocess.run(c, shell=True, capture_output=True, text=True, executable='/bin/bash')
    print((r.stdout + r.stderr)[-show:], flush=True)
    return r.returncode
sh('nvidia-smi -L')
# Kaggle gives two T4s; Cycles uses both (blender/gpu_setup.py turns on every CUDA device).
os.chdir('/kaggle/tmp') if os.path.isdir('/kaggle/tmp') else os.makedirs('/kaggle/tmp') or os.chdir('/kaggle/tmp')
sh('curl -sL https://download.blender.org/release/Blender4.5/blender-4.5.16-linux-x64.tar.xz | tar -xJ && ls')
sh('apt-get install -y -qq libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libxkbcommon0 libsm6 >/dev/null 2>&1; true')
src = glob.glob('/kaggle/input/**/repo.tgz', recursive=True)[0]
sh(f'tar xzf {src} -C /kaggle/tmp && ls /kaggle/tmp/repo')
B = '/kaggle/tmp/blender-4.5.16-linux-x64/blender'
print('setup', int(time.time() - t0), 's', flush=True)
t1 = time.time()
sh(f'cd /kaggle/tmp/repo && {B} -b -P {JOB["script"]} -- {" ".join(JOB["args"])} 2>&1 | grep -E "gpu|Fra:.*Time|Error|rror" | tail -40', show=6000)
n = len(glob.glob('/kaggle/working/frames/*'))
print(f'RENDERED {n} frames in {int(time.time() - t1)} s ({(time.time() - t1) / max(n, 1):.1f} s/frame)', flush=True)
sh(f'ffmpeg -loglevel error -y -framerate 24 -i /kaggle/working/frames/f%04d.jpg -c:v libx264 -crf 16 -pix_fmt yuv420p {JOB["mp4"]}')
sh('cd /kaggle/working && tar cf frames.tar frames && rm -rf frames')
print('ALL_DONE', int(time.time() - t0), 's')
