# Kaggle job (free GPU, AGENTS.md rule 2): render a Paper Cinema Blender shot with Cycles on the T4s.
# The job is DATA: gpu/kaggle_blender/run.sh pack writes job.json into the private dataset
# (reviewboost/paper-cinema-blender, repo.tgz = blender/ + assets/models + library/ + the film and its motion file).
# Then: bash gpu/kaggle_blender/run.sh push / wait / get      (ONE push: a push cancels the run before it)
# job.json: {"name", "script", "fps", "args": [...]} or {"stages": [{"name", "env", "args"}, ...]} for a probe run.
import glob
import json
import os
import shutil
import subprocess
import time

t0 = time.time()
WORK = '/kaggle/working'


def sh(c, show=1200):
    print('$', c[:220], flush=True)
    r = subprocess.run(c, shell=True, capture_output=True, text=True, executable='/bin/bash')
    txt = (r.stdout + r.stderr).strip()
    if txt:
        print(txt[-show:], flush=True)
    return r.returncode


sh('nvidia-smi -L; nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1')
sh('free -g | head -2')
os.makedirs('/kaggle/tmp', exist_ok=True)
os.chdir('/kaggle/tmp')
sh('curl -sL https://download.blender.org/release/Blender4.5/blender-4.5.16-linux-x64.tar.xz | tar -xJ')
sh('apt-get install -y -qq libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libxkbcommon0 libsm6 >/dev/null 2>&1; true')
src = sorted(glob.glob('/kaggle/input/**/repo.tgz', recursive=True))[0]
sh(f'tar xzf {src} -C /kaggle/tmp && ls /kaggle/tmp/repo')
JOB = json.load(open('/kaggle/tmp/repo/job.json'))
print('JOB', json.dumps(JOB)[:600], flush=True)
# the motion file is exported on the workstation; make it newer than the film file so Blender does not call node
sh('find /kaggle/tmp/repo/output -name "*.motion.json" -exec touch {} + 2>/dev/null; true')
B = '/kaggle/tmp/blender-4.5.16-linux-x64/blender'
FRAMES = '/kaggle/tmp/frames'
os.makedirs(FRAMES, exist_ok=True)
CORES = JOB.get('cores', '0,1')
THREADS = JOB.get('threads', len(CORES.split(',')))
print('setup', int(time.time() - t0), f's · cores {CORES} · {THREADS} Cycles threads', flush=True)


def render(stage, out):
    """Run Blender once. One short line every 5 s (frames done, GPU use, Blender's own last line): Kaggle only
       persists the log in snapshots, so this is what pins down where a killed kernel stopped."""
    t1 = time.time()
    os.makedirs(out, exist_ok=True)
    lg = f'{WORK}/blender-{stage["name"]}.log'
    # Kaggle kills a session whose container runs out of CPU for its own agent: Blender is niced and pinned to
    # CORES of the 4 vCPUs, with Cycles on the same number of threads, so the agent always gets a core.
    cmd = (f'cd /kaggle/tmp/repo && {stage.get("env", "")} nice -n 19 taskset -c {CORES} '
           f'{B} -b -t {THREADS} -P {JOB["script"]} -- {" ".join(stage["args"])} --out {out}/ > {lg} 2>&1')
    print(f'=== STAGE {stage["name"]} START', flush=True)
    print('$', cmd[:400], flush=True)
    p = subprocess.Popen(cmd, shell=True, executable='/bin/bash')
    ticks = 0
    while p.poll() is None:
        time.sleep(5)
        n = len(glob.glob(f'{out}/*.png'))
        if ticks < 900:
            g = subprocess.run('nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader',
                               shell=True, capture_output=True, text=True).stdout.split('\n')[0].strip()
            tail = subprocess.run(f'tail -c 4000 {lg} | tr "\\r" "\\n" | grep -v "^$" | tail -1',
                                  shell=True, capture_output=True, text=True).stdout.strip()[:100]
            print(f'  [{int(time.time() - t1):5d}s] {n} frames | gpu {g} | {tail}', flush=True)
            ticks += 1
    rc = p.wait()
    n = len(glob.glob(f'{out}/*.png'))
    dt = time.time() - t1
    sh(r'grep -aE "\[gpu\]|Cycles device|^Error|Error:" ' + lg + ' | head -4', 600)
    print(f'=== STAGE {stage["name"]} END rc={rc} · {n} frames in {int(dt)} s ({dt / max(n, 1):.1f} s/frame)', flush=True)
    return rc


STAGES = JOB.get('stages')
for st in (STAGES or [{'name': JOB['name'], 'env': '', 'args': JOB['args']}]):
    render(st, f'{FRAMES}/{st["name"]}' if STAGES else FRAMES)

files = sorted(glob.glob(f'{FRAMES}/*.png'))
if files:
    first = int(os.path.basename(files[0])[1:5])
    sh(f'ffmpeg -loglevel error -y -framerate {JOB.get("fps", 24)} -start_number {first} '
       f'-i {FRAMES}/f%04d.png -c:v libx264 -crf 16 -pix_fmt yuv420p {WORK}/{JOB["name"]}.mp4')
    sh(f'tar czf {WORK}/frames.tgz -C {FRAMES} .')              # one file, not hundreds, for kernels output
    shutil.copy(files[0], f'{WORK}/first.png')
    shutil.copy(files[-1], f'{WORK}/last.png')
sh(f'ls -la {WORK}')
print('ALL_DONE', int(time.time() - t0), 's', flush=True)
