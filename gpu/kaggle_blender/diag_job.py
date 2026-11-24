# The bisection kernel that found out what the cancel is NOT (docs/KAGGLE-RENDER.md). Run it in its OWN kernel,
# never in paper-cinema-blender-render, so a push does not cancel a real render:
#
#   d=$(mktemp -d); cp gpu/kaggle_blender/diag_job.py $d/
#   cp gpu/kaggle_blender/diag-kernel-metadata.json $d/kernel-metadata.json
#   kaggle kernels push -p $d                    # ONE push, then wait
#   kaggle kernels status reviewboost/pc-blender-diag
#   kaggle kernels output reviewboost/pc-blender-diag -p /tmp/out    # the log is the result
#
# It needs the dataset the packer builds, so run `bash gpu/kaggle_blender/run.sh pack film/<name>.json` first.
# Keep every stage short and print a heartbeat: a cancelled kernel keeps only the log Kaggle has snapshotted.
# This copy is the last bisection (effects off -> on). The next one to try is the other direction: start from
# Blender's own monkey scene (which survives) and add our pieces one at a time until the kernel dies.
# Diagnostic 4. Ruled out: GPU quota, GPU attachment, the dataset mount, the log's folder, an idle GPU, the
# render device, memory (3.5 of 30 GiB, no cgroup oom events), disk and the CPU quota. A self-contained Cycles
# CUDA render in the same kernel ran 110 s; the repo's own film render is killed 11-18 s in, every time.
# So the trigger is in what OUR scene does. Bisect it by what film_blender.py can switch off, poorest first:
#   S1 no dust, no slash, no blur, no glare   S2 + dust   S3 + slash   S4 + blur   S5 everything (control)
# The stage we die in names the culprit; if S1 dies too it is the base scene (characters, set, backdrop).
import glob
import os
import subprocess
import time

t0 = time.time()


def say(m):
    print(f'[{time.time() - t0:6.1f}s] {m}', flush=True)


def sh(c, show=300):
    r = subprocess.run(c, shell=True, capture_output=True, text=True, executable='/bin/bash')
    say(f'$ {c[:110]} -> {((r.stdout + r.stderr).strip() or "(no output)")[-show:]}'.replace('\n', ' | '))


os.makedirs('/kaggle/tmp', exist_ok=True)
os.chdir('/kaggle/tmp')
sh('curl -sL https://download.blender.org/release/Blender4.5/blender-4.5.16-linux-x64.tar.xz | tar -xJ')
sh('apt-get install -y -qq libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libxkbcommon0 libsm6 >/dev/null 2>&1; true')
src = sorted(glob.glob('/kaggle/input/**/repo.tgz', recursive=True))[0]
sh(f'tar xzf {src} -C /kaggle/tmp >/dev/null && echo extracted')
B = '/kaggle/tmp/blender-4.5.16-linux-x64/blender'

STAGES = [
    ('S1-bare', '--no-dust --no-slash --no-blur --no-glare'),
    ('S2-dust', '--no-slash --no-blur --no-glare'),
    ('S3-slash', '--no-blur --no-glare'),
    ('S4-blur', '--no-glare'),
    ('S5-all', ''),
]
for tag, flags in STAGES:
    out = f'/kaggle/tmp/f-{tag}'
    lg = f'/kaggle/tmp/{tag}.log'
    say(f'=== {tag} START   flags: {flags or "(none: everything on)"}')
    p = subprocess.Popen(
        f'cd /kaggle/tmp/repo && {B} -b -t 4 -P blender/film_blender.py -- --film film/dash-test.json '
        f'--frames 0-7 --samples 8 --res 360x640 {flags} --out {out}/ > {lg} 2>&1',
        shell=True, executable='/bin/bash')
    t1 = time.time()
    while p.poll() is None:
        time.sleep(2)
        say(f'  {tag} {int(time.time() - t1):3d}s · {len(glob.glob(f"{out}/*.png"))} png · ' +
            subprocess.run(f'tail -c 2000 {lg} | tr "\\r" "\\n" | grep -v "^$" | tail -1',
                           shell=True, capture_output=True, text=True).stdout.strip()[:70])
    say(f'=== {tag} END rc={p.returncode} after {int(time.time() - t1)}s · {len(glob.glob(f"{out}/*.png"))} png')
say('ALL_DONE')
