# KAGGLE RENDER FARM — free Blender renders, and the cancel that is not a crash

One command sends a film's Blender render to Kaggle and brings the frames back:

```bash
tools/film.sh film/dash-test.json --gpu            # the whole film, rendered on Kaggle
# or by hand:
bash gpu/kaggle_blender/run.sh pack film/dash-test.json --frames 0-191 --samples 48 --res 720x1280
bash gpu/kaggle_blender/run.sh push                # ONE push: a push cancels the run before it
bash gpu/kaggle_blender/run.sh wait
bash gpu/kaggle_blender/run.sh get output/kaggle-render/dash-test
```

The job is **data**: `pack` tars `blender/`, `assets/models`, `library/`, the film and its `output/<film>.motion.json`
into the private dataset `reviewboost/paper-cinema-blender` with a `job.json`
(`{name, script, fps, cores, args}`), so `render_job.py` never has to be edited to change a render.
`get` unpacks `frames.tgz` (every PNG), the MP4 and Blender's own log.

## The CANCEL_ACKNOWLEDGED mystery, measured

Every GPU run died the same way: setup fine (~30 s), the first frames fine, then the kernel ended as
`CANCEL_ACKNOWLEDGED` with `failureMessage: null`. It was blamed on Blender flooding the kernel log, on the
output folder, on OptiX. It was none of those. Measured runs, 24 November:

| run | accelerator | what it did | lifetime |
|---|---|---|---|
| v9–v12 | 2× Tesla T4 | Blender render, log to a file, frames to `/kaggle/tmp` or `/kaggle/working` | cancelled 45–90 s |
| v11 | 2× T4 | the same render forced onto the **CPU** (`BLENDER_GPU=0`, GPU 0 % and 0 MiB the whole time) | cancelled ~90 s |
| v12 | 2× T4 | niced, pinned to 2 of 4 vCPUs | cancelled ~50 s |
| v13 | 2× T4 | 2 frames at 270×480: finished, `ALL_DONE 39 s`, MP4 written | cancelled right after, so nothing could be fetched |
| v14 | **none** (`enable_gpu: false`) | sleep and print for 300 s | **COMPLETE** |

So the cancel follows the **GPU being attached**, not anything the render does — the session is killed about a
minute in whether Cycles uses the GPU, the CPU, one core or four. That is what an exhausted weekly GPU quota
looks like from inside: Kaggle still hands out a session with both T4s, then takes it away. Since downloading
Blender eats ~30 s of that minute, the render never got anywhere, which made it look like a Blender fault.

**What to do**
* `bash gpu/kaggle_blender/run.sh push --cpu` — a CPU session (4 cores, 12 h) is not capped and returns frames.
  `run.sh wait` prints this advice by itself when a run is cancelled in under three minutes.
* Or wait for the weekly GPU quota to reset (Kaggle resets it on Saturdays, UTC). Nothing in the code needs changing.
* Check it is really the quota: push the 300 s sleep probe with `enable_gpu: false`; if that completes and the same
  job with a GPU is cancelled in a minute, it is the quota.

## Also fixed while looking for it

* `blender/film_blender.py` never used the GPU at all: `rig_trellis.render_settings()` sets
  `cycles.device = 'CPU'`, so every "GPU" render was a CPU render. It now calls `gpu_setup.use_gpu()` after it.
* `blender/gpu_setup.py` tries **CUDA before OPTIX** and takes `BLENDER_GPU=0|cuda|optix|…`, so a backend can be
  forced or ruled out (`run.sh pack --probe` renders the same frames on CPU, CUDA and OPTIX in one run).
* `render_job.py` prints one line every 5 s (frames done, GPU use, Blender's last log line). Kaggle only persists
  a kernel's log in snapshots, so a killed run loses its tail; the heartbeat pins the death to within 5 s. That is
  what made this diagnosable at all.

## Measured speeds (720×1280, 48 samples, dash-test)

| machine | s/frame |
|---|---|
| this workstation, 2 of 4 shared cores, 360×640 / 12 samples | 9.5 |
| Kaggle 2× T4, Cycles CUDA (from the partial runs) | ~5 |
| Kaggle 4 CPU cores, 540×960 / 24 samples | ~25 |
