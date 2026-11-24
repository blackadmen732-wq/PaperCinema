# KAGGLE RENDER FARM — free Blender renders, and the cancel nobody has explained yet

**Status (24 November): the GPU farm does not work, and `tools/film.sh --gpu` refuses to start because of it.**
Render on this machine instead — the local path is the one that always finishes:

```bash
bash tools/film.sh film/dash-test.json                 # four niced Blender processes, resumable
bash tools/film.sh film/dash-test.json --from 96 --to 191   # just that stretch
bash tools/film.sh film/dash-test.json --full          # 720x1280 / 48 samples instead of the preview
```

The job packer is still there and still correct; only the Kaggle run dies. By hand:

```bash
bash gpu/kaggle_blender/run.sh pack film/dash-test.json --frames 0-191 --samples 48 --res 720x1280
bash gpu/kaggle_blender/run.sh push                # ONE push: a push cancels the run before it
bash gpu/kaggle_blender/run.sh wait
bash gpu/kaggle_blender/run.sh get output/kaggle-render/dash-test
```

The job is **data**: `pack` tars `blender/`, `assets/models`, `library/`, the film and its `output/<film>.motion.json`
into the private dataset `reviewboost/paper-cinema-blender` with a `job.json`
(`{name, script, fps, cores, args}`), so `render_job.py` never has to be edited to change a render.
`get` unpacks `frames.tgz` (every PNG), the MP4 and Blender's own log.

## The CANCEL_ACKNOWLEDGED mystery — what it is NOT

Every run of **our film render** ends as `CANCEL_ACKNOWLEDGED` with `failureMessage: null`, **11–18 seconds after
Blender starts rendering**, whatever else is true. The earlier note in this file blamed an exhausted weekly GPU
quota. That was wrong: a GPU session is handed out *and keeps both T4s happily for minutes*.

Measured, 24 November (each row is one `kernels push`, one run; the kernel was `pc-blender-diag` for the
bisections so the render kernel was left alone):

| what ran | accelerator | result |
|---|---|---|
| sleep + print, 300 s | none | **COMPLETE** |
| a Cycles **CUDA** render of Blender's own monkey, 720×1280 / 48 samples, 12 frames, log in `/kaggle/tmp` | 2× T4 | **COMPLETE**, 110 s, ~9 s/frame |
| the same monkey render **inside the dataset-attached kernel**, then our film render | 2× T4 | monkey fine for 110 s; **killed 11 s into the film render** |
| our film render with a CUDA keep-alive process holding the GPU at 45 % | 2× T4 | **killed 17 s in** |
| our film render, cgroup watched twice a second (limit 30 GiB, usage 3.5 GiB, `oom_kill 0`) | 2× T4 | **killed 18 s in**, no OOM event, 20 GB disk free, cpu.max = 4 cores |
| our film render with `--no-dust --no-slash --no-blur --no-glare`, 360×640 / 8 samples | 2× T4 | **killed 16 s in**, 3 frames written |
| our film render forced onto the CPU (`BLENDER_GPU=0`, GPU 0 %, 0 MiB) | 2× T4 | killed ~90 s in |
| our film render, frames to `/kaggle/working` vs `/kaggle/tmp`, log at source filtered, 8–96 frames | 2× T4 | killed every time |
| the reverse bisection in one kernel: **R1** bare scene + Blender's monkey, 8 frames · **R2** bare scene + **our TRELLIS character GLB** imported and rendered, 8 frames · **R3** the same film render through `film_blender.py` | 2× T4 | **R1 finished (28 s, rc=0)**, **R2 finished (28 s, rc=0)**, **killed ~15 s into R3** |

So it is **not** the quota, **not** the GPU being attached, **not** the GPU sitting idle, **not** the render
device, **not** memory (3.5 of 30 GiB, no cgroup OOM), **not** disk, **not** the CPU quota, **not** the attached
dataset, **not** the folder the frames or the log are written to, **not** the resolution or the sample count, and
**not** dust, the slash ribbon, motion blur or glare. A trivial Cycles render on the same GPUs in the same kernel
runs for minutes. Our film render, in any shape, is killed about fifteen seconds in, while Blender is in the
middle of an ordinary frame (`Fra:4 … Remaining:00:00.23` was the last line of the stripped-down run).

That last row is the sharpest one: on the same GPUs, in the same kernel, a bare Cycles scene renders 8 frames
and so does a bare scene with **our own origami character GLB** in it — the model, the importer, Cycles and CUDA
are all innocent. Only the render that goes through `blender/film_blender.py` is killed, and the session (not the
Blender process) dies: Blender never reports an exit code, it simply stops existing mid-frame.

What is left, and where to look next:
* Something `blender/film_blender.py` itself does. Everything it can be told to switch off is already cleared
  (`--no-dust --no-slash --no-blur --no-glare` dies too), so the next bisection is inside the file: the motion
  load, `rig_trellis` rigging and skinning, the materials, the backdrop, the per-frame light rig, the tree props.
  `gpu/kaggle_blender/diag_job.py` is the kernel that found all of this — add stages to it, one piece at a time.
* Kaggle support / the forums: a `CANCEL_ACKNOWLEDGED` with `failureMessage: null` is not documented anywhere,
  and the kernel's own log is the only evidence a killed run leaves (Kaggle snapshots it, so print a heartbeat —
  `render_job.py` prints frames done, GPU use, RAM and Blender's last line every 5 s; that is what pinned the
  death down to the second).

## Also fixed while looking for it

* `blender/film_blender.py` never used the GPU at all: `rig_trellis.render_settings()` sets
  `cycles.device = 'CPU'`, so every "GPU" render was a CPU render. It now calls `gpu_setup.use_gpu()` after it.
* `blender/gpu_setup.py` tries **CUDA before OPTIX** and takes `BLENDER_GPU=0|cuda|optix|…`, so a backend can be
  forced or ruled out (`run.sh pack --probe` renders the same frames on CPU, CUDA and OPTIX in one run).
* `render_job.py` counted `"cores": "0-3"` as **one** core and ran Cycles with a single thread. It counts ranges
  out now (4), and its heartbeat prints the container's free RAM beside the GPU figures.

## Measured speeds (dash-test)

| machine | picture | s/frame |
|---|---|---|
| Kaggle 2× T4, Cycles CUDA (from the runs before the kill) | 720×1280 / 48 | ~14 |
| this workstation, one of four shared cores | 540×960 / 32 | 52 |
| this workstation, four niced one-thread processes | 360×640 / 16 | ~7 wall per frame (~28 s each, four at once) |
| Kaggle 4 CPU cores (`run.sh push --cpu`, not capped the way a GPU session is) | 540×960 / 24 | ~25 |
