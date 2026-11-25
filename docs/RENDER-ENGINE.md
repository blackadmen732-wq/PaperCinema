# Render engine: measured, not assumed

`blender/render_engine.py` makes the engine one flag. `setup_render(scene)` gives EEVEE Next;
`PC_ENGINE=cycles` or `--engine cycles` gives the path tracer. Every render script calls it, so
switching the whole project is an environment variable, not an edit.

## The measurement that decided the default

One frame, `blender/character/trellis_shot.py --model ronin_base --still 40`, 480x854, `check`
quality, 4 threads, on this container (Intel Xeon 2.10 GHz, 4 cores, **no GPU**, no `/dev/dri`):

| Engine | Render | To first sample | Per sample | Look |
|---|---|---|---|---|
| Cycles, 24 samples | **17.2 s** | — | 0.71 s | face lit, glow reads warm, soft gradation |
| EEVEE Next, 32 TAA | 40.7 s | 22.5 s (shader compile) | 0.56 s | dark smear over the face, blotchy shadow |

Stills: `output/engine-ab/cycles.png`, `output/engine-ab/eevee.png`.

**On this machine Cycles wins on both speed and image.** That is not the usual result and it is worth
understanding why, because it flips the moment there is a GPU.

EEVEE is a rasterizer: its speed comes from the graphics hardware. This container has no GPU, so
Blender falls back to software OpenGL (the EGL errors in the log are that fallback). Two things follow:

1. **22.5 s of shader compilation** before the first sample. That is a fixed cost per Blender process,
   not per frame, so a 96-frame sequence pays it once.
2. **Screen-space effects degrade.** EEVEE's raytracing and fast GI are screen-space approximations;
   in software they are the source of the smear across the face.

Per sample EEVEE is already cheaper (0.56 s vs 0.71 s) even in software. With real hardware the gap
is not small, it is a different order: rasterizing 32 TAA samples is work a GPU is built for, while
Cycles still traces every path.

## So which do I use

| Where | Engine | Why |
|---|---|---|
| This container (no GPU) | **Cycles** | measured faster and cleaner above |
| Kaggle T4, RunPod, any NVIDIA box | **EEVEE** | the rasterizer finally has hardware |
| A laptop or desktop with any modern GPU | **EEVEE** | same reason; integrated graphics count |

The default in `render_engine.py` is EEVEE because that is right wherever there is a GPU, which is
every machine except this one. Here, pass `--engine cycles` or set `PC_ENGINE=cycles`.

## Sampling

Pass `quality` (`draft`/`check`/`final`), not a raw sample count: a Cycles sample is a traced path and
an EEVEE sample is a rasterized pass, so the same number means different work and different noise.

| quality | EEVEE TAA | Cycles |
|---|---|---|
| draft | 8 | 8 |
| check | 32 | 24 |
| final | 128 | 96 |

## Re-run the comparison

    B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
    $B -b -t 4 -P blender/character/trellis_shot.py -- --model ronin_base --still 40 \
       --engine eevee  --quality check --res 480x854 --out output/engine-ab/eevee.png
    $B -b -t 4 -P blender/character/trellis_shot.py -- --model ronin_base --still 40 \
       --engine cycles --quality check --res 480x854 --out output/engine-ab/cycles.png
