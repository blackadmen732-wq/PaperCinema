# Kaggle job (free GPU): render a Paper Cinema Blender scene with Cycles on the T4 GPU.
# Inputs: the private dataset reviewboost/paper-cinema-blender (repo.tgz = blender/ scripts, assets/models, library/).
# Edit JOB below, then: bash gpu/kaggle_blender/run.sh push / status / get
import subprocess, os, time, glob
JOB = {
    'script': 'blender/character/trellis_shot.py',
    'args': ['--model', 'ronin_base', '--frames', '1-12', '--samples', '48', '--res', '720x1280', '--out', '/kaggle/tmp/frames/'],
    'mp4': '/kaggle/working/shot.mp4',
}
t0 = time.time()
def sh(c, show=1500, stream=False):
    print('$', c[:200], flush=True)
    if stream:                      # print as it happens, so a cancelled run still shows how far it got
        c = c + " 2>&1 | grep --line-buffered -E '^Saved:|\\[gpu\\]|Error'"
        p = subprocess.Popen(c, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, executable='/bin/bash')
        for line in p.stdout:                 # one line per finished frame only: Kaggle kills a kernel that floods its log
            if line.startswith('Saved:') or '[gpu]' in line or 'Error' in line:
                print(line.rstrip()[:140], flush=True)
        return p.wait()
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
sh(f'cd /kaggle/tmp/repo && {B} -b -P {JOB["script"]} -- {" ".join(JOB["args"])} > /kaggle/tmp/blender.log 2>&1; '
   f'grep -cE "^Saved:" /kaggle/tmp/blender.log; tail -3 /kaggle/tmp/blender.log')
n = len(glob.glob('/kaggle/tmp/frames/*'))
print(f'RENDERED {n} frames in {int(time.time() - t1)} s ({(time.time() - t1) / max(n, 1):.1f} s/frame)', flush=True)
sh(f'ffmpeg -loglevel error -y -framerate 24 -i /kaggle/tmp/frames/f%04d.jpg -c:v libx264 -crf 16 -pix_fmt yuv420p {JOB["mp4"]}')
sh('cp /kaggle/tmp/frames/f0001.jpg /kaggle/tmp/frames/f0048.jpg /kaggle/working/ 2>/dev/null; ls -la /kaggle/working')
print('ALL_DONE', int(time.time() - t0), 's')
