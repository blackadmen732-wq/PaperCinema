# VYRN: the perception engine (v0.1)

VYRN turns a piece of media into a **persistent, queryable store of timestamped observations** — things with an
identity, how they move, where they are relative to each other, what sounds happen, how sure each observation is,
and where the picture that proves it is — so an agent asks a narrow question and gets a few lines back, instead of
watching frames. Media is processed **once**; the store is cached by content hash and answers later questions
without decoding the video again.

It has two inputs that fill the same store:

| Input | Reads | Confidence |
|---|---|---|
| **Native** | what a source environment already knows: `output/<film>.timeline.json` from `tools/timeline.mjs` (every bone, the camera, cuts, verified events) | 1.0: it is the truth |
| **External** | any video file: pixels and sound, with light CPU algorithms (FFmpeg, OpenCV, numpy) | measured per method (below) |

The native side is also the grader: when the same scene exists as data and as a video, the external answers are
scored against it (`vyrn/bench/`).

It is **not** a model that "watches" video. Claude cannot take video in; anything that watches has to turn it into
numbers first. VYRN is that conversion, done once, kept, and made askable.

## Commands

```bash
python3 -m vyrn ingest output/x-final.mp4                 # process once → media id (cached: a second run takes 0.04 s)
python3 -m vyrn ingest output/x.timeline.json             # native: the film as data
python3 -m vyrn summary <media>                           # what is in it: shots, entities, event counts
python3 -m vyrn window <media> 2.0 3.5                    # what happened between two times
python3 -m vyrn when <media> av.impact                    # when does X happen (cut, footstep, sound.onset, contact…)
python3 -m vyrn track <media> obj.01 --from 5 --to 6.2    # how something moved (box, speed, confidence)
python3 -m vyrn track <media> hero --joint foot.L         # native: one joint, screen and world
python3 -m vyrn relation <media> obj.01 obj.03            # distance and overlap between two entities
python3 -m vyrn sync <media>                              # picture impacts vs sound onsets: which sound is off, by how much
python3 -m vyrn sync final.mp4 --expect output/x.timeline.json --visual   # final mix vs the engine's events
python3 -m vyrn verify final.mp4 --truth output/x.timeline.json   # independent: heard sound vs the film's PICTURE events
python3 -m vyrn evidence <media> 3.08 --entity obj.01     # one cached PNG crop; look at it only if needed
python3 -m vyrn inspect <media> motion.freeze.02          # a 3-frame strip around an event (cached)
python3 -m vyrn backends                                  # every stage's default and alternatives, with licences
python3 -m vyrn.bench.synth && python3 -m vyrn.bench.run output/vyrn-bench/duel   # the benchmark
```
`<media>` is the id `ingest` printed or the original file path. `--json` on any command gives the data.
Needs `ffmpeg` and `numpy`; the picture stages (cuts, camera, subjects) also need `opencv-python-headless`
(Apache-2.0). Without OpenCV a video is ingested for sound only, which is all `sync --expect` needs (0.6 s, 64 MB
for the 6.5 s test clip). `--expect` takes a timeline, Sonic's `output/<film>.sonic.json` (uses `peakAt`), or any
shared-format `.jsonl` such as `output/<film>.sonic.events.jsonl`.

## What is stored (`output/vyrn/<media>.sqlite`, schema in `vyrn/store.py`)

| Table | Holds |
|---|---|
| `media` | the file, its sha256, fps, size, which processors (and versions) made the store, ingest time and memory |
| `entities` | things with a persistent id: actors and weapons (native), tracked subjects `obj.NN` (video), the camera |
| `samples` | one row per entity per frame: screen box (0..1), world position when known, velocity, confidence |
| `joints` | per-joint screen and world positions (native skeletons; a pose backend later) |
| `events` | everything with a time: `cut`, `footstep`, `blade-contact`, `hit-stop`, `cue`, `contact.foot-ground`, `motion.freeze`, `sound.onset`, `sound.swell`, `av.impact` |
| `relations` | pairwise intervals: `near` (world, native), `overlap` (screen, video) |
| `signals` | dense curves: camera pan, motion energy, loudness, actor distances |
| `evidence` | crops and frames already extracted, so a picture is never decoded twice |
| `calibration` | each method's measured error from the benchmark, so an answer can state how far to trust it |

Every observation has a **confidence** (0..1) and the **method** that made it. Uncertain answers say so (`~0.62`):
two subjects merged into one blob drop to 0.35–0.6, a cut found by a narrow margin is below 1.

## The shared event format (with Sonic, and the shared core)

`output/vyrn/<media>.events.jsonl`, one object per line, a superset of the timeline's events
(`docs/TIMELINE-FORMAT.md` §10), so an id like `blade-contact.01` means the same moment in every tool:

```json
{"id": "av.impact.01", "type": "av.impact", "t": 3.0833, "t1": 3.1667, "f": 74, "source": "vyrn.fuse",
 "method": "freeze+onset", "conf": 0.95, "entities": [], "data": {"offset_ms": 82.9, "sound_t": 3.1662}}
```
`source` is `engine` (the timeline), `vyrn.native`, `vyrn.video`, `vyrn.audio`, `vyrn.fuse` or `sonic`.
Sonic's cue event (`{kind, material, intensity, speed, height, peakAt}`) goes in `data` unchanged.
**What Sonic gets from VYRN:** `sync --expect` measures the onsets in the *final rendered audio* and compares them
with the cues, which is the independent peak-sync check Sonic needs, without a second onset detector.

## How the external path works (each stage swappable, `vyrn/backends.py`)

1. **Decode once** with FFmpeg to a 160-px-wide copy, cached as `.npy`.
2. **Cuts:** colour-histogram distance with an adaptive threshold (the PySceneDetect "content" idea).
3. **Camera:** Shi-Tomasi corners + pyramidal Lucas-Kanade + a RANSAC fit, so moving subjects are outliers.
   (Phase correlation was tried first and measured: walking fighters dragged it to a false 0.5 px/frame pan.)
4. **Subjects:** per shot, a median background (static, or aligned by the measured pan, whichever fits better),
   difference mask, connected components.
5. **Identity:** constant-velocity prediction + IoU tracking with gap bridging; when two subjects merge into one
   blob, each pixel goes to the track whose colour histogram explains it best (back-projection); across a cut or a
   long occlusion, tracks are re-joined by colour similarity, so a fighter keeps one id through the edit.
6. **Motion:** Farneback optical flow inside each subject minus that subject's own median flow ("articulation"):
   a pan, a dolly or the whole body sliding moves every pixel alike and cancels; limbs and blades do not. A collapse
   after fast motion, down to the shot's own noise floor, is a `motion.freeze` (hit-stop / impact), timed at the
   last moving frame.
6b. **Feet:** the lowest 15 % of each subject is split into parts; each part's flow is compared with the flow of the
   ground right around it, so pans and parallax cancel. A part that swung and then holds still for 2 frames has
   planted (`contact.foot-ground`). A plant and a thud within 0.1 s become an `av.footstep`.
7. **Sound:** SuperFlux-style spectral flux with an adaptive threshold, then each onset refined in the waveform to
   the attack (10 % of the rise); the 10→90 % rise time separates hits (`sound.onset`) from whooshes (`sound.swell`).
   Each hit also gets a `guess` from its power spectral centroid and its 30 dB decay: `thud` (step, landing, body),
   `ringing` (metal, clash) or `hit`. Tuned on one scene, so treat it as a hint; Sonic's catalogue knows its own
   sounds exactly.
8. **Fusion:** a freeze and a hit within 150 ms become one `av.impact` carrying the offset (sound late or early).
9. **Confidence fallback:** `window` and `when` list, under the answer, a cached 3-frame picture strip for each
   event below confidence 0.6 (up to 3). The agent opens a picture only when the numbers are unsure.
10. **Independent sync:** `verify --truth` compares the sound measured in a final render with the film's own
   picture events (contacts, impacts, footsteps, ground hits, paper cuts), not with the cue list, so a cue placed at
   the wrong time is caught rather than used as the reference. It reports the overall offset (a shifted track),
   per-type coverage, outliers and silent events; exit 1 when something is off.

Neural models are slots, not dependencies: a stage is replaced with `VYRN_CUTS`, `VYRN_CAMERA` or `VYRN_ONSETS`
naming a function with the default's signature, and `vyrn/bench/run.py` grades it on the same scene.

## Audit of what already existed (and what VYRN reuses)

| Existing | What it does | VYRN |
|---|---|---|
| `tools/timeline.mjs` | the engine's canonical timeline: bones, camera, cuts, events | **the native input**, read as is; nothing re-implemented |
| `engine/combat.js` (`window.EVENTS`) | verified blade contacts, hit-stops, cues | copied with their stable ids |
| `tools/footslide.mjs` | planted-foot rule (root ≤ 0.03 m, foot ≤ 0.12 m) | same rule for native `contact.foot-ground` |
| `tools/mocap_truth.mjs` | poses the rig in Node as ground truth for mocap | same idea as the bench: truth from data, test from pixels |
| `tools/listen.py` | speech (faster-whisper), 50 ms RMS hit list, 1 fps sheet | speech stays there (a backend slot); hit timing replaced: listen finds hits to 50 ms and missed 11 of 12 footsteps in the test scene, VYRN times them to ~1 ms |
| `tools/mocap.py` | MediaPipe pose (Apache-2.0) from a phone video | the planned `pose` backend for video joints; not wired yet (needs `mediapipe` installed) |
| `tools/audit.mjs`, `engine/audit-hooks.js`, `tools/camera_check.mjs` | studio QA and shot scoring from the browser engine | not duplicated; their reports can be ingested as observations later |
| `tools/jitter.mjs` | tremble per joint | could run on video tracks later |
| `research/reference-videos.md`, `.claude/skills/reanimate` | human notes on reference videos; frame-by-frame cloning of web/video animation | unchanged; VYRN makes those videos askable |

**Real gaps before VYRN:** nothing kept what was learned from a video (listen.py re-runs everything), nothing gave
objects an identity across frames or cuts, nothing timed sounds better than 50 ms, and nothing checked the final mix
against the picture.

## Research and licences (rule 6: code and weights checked separately)

`python3 -m vyrn backends` prints the full table. The decisions:

| Candidate | Gives | Needs | Licence (code / weights) | Verdict |
|---|---|---|---|---|
| FFmpeg | decode, audio, seeking | CPU | LGPL-2.1+ binary | used |
| OpenCV (LK, RANSAC, components, Farneback) | camera, blobs, flow | CPU | Apache-2.0 | used |
| PySceneDetect | cuts, fades | CPU | BSD-3 | drop-in option |
| librosa | onsets, beats | CPU | ISC | drop-in option |
| SAM 2.1 (hiera-tiny) | segmentation + video propagation | GPU (CPU slow) | Apache-2.0 / Apache-2.0 | best next backend for subjects |
| TAPIR / BootsTAP | point tracks through occlusion | GPU | Apache-2.0 / Apache-2.0 | optional |
| RAFT | dense optical flow | GPU | BSD-3 | optional |
| MediaPipe Pose | 33 body landmarks | CPU | Apache-2.0 / Apache-2.0 | reuse from `tools/mocap.py` |
| faster-whisper, Silero VAD | speech, speech regions | CPU | MIT / MIT | reuse / candidate |
| CLAP (LAION) | text↔sound similarity | CPU/GPU | CC0 / Apache-2.0 | optional, shared with Sonic |
| V-JEPA 2 | video embeddings | GPU | MIT / MIT | research, later |
| Qwen3-Omni-30B-A3B, Qwen2.5-Omni-7B | video+audio Q&A | big GPU | Apache-2.0 / Apache-2.0 | research, later |
| Qwen2.5-Omni-3B | video+audio Q&A | GPU | Apache-2.0 / Qwen Research | **no** (non-commercial weights) |
| CoTracker 3 | dense point tracks | GPU | CC-BY-NC-4.0 | **no** |
| Ultralytics YOLO | detection | CPU/GPU | AGPL-3.0 | **no** (or paid) |
| madmom | neural onsets | CPU | BSD / CC-BY-NC-SA models | **no** for the models |
| aubio | onsets | CPU | GPL-3.0 | avoid |
| PANNs | sound-event classes | CPU | MIT / not stated | check the weights before use |

Weights licences were read from the Hugging Face model cards on 2026-11-28; code licences from each repo's LICENSE.

## Benchmark (measured, `vyrn/bench/`)

Ground truth: `vyrn/bench/synth.py` makes one scene twice from one simulation — as a Paper Cinema timeline (the
23-bone rig, camera, cuts, events) and as a 360×640 video with sound (two paper fighters, a set, sensor noise, a hard
cut to a panning camera, footsteps, four steel clashes from `assets/sfx`, a hit, three whoosh decoys, and **one clash
sound deliberately 83 ms late**). Full results: `vyrn/bench/RESULTS.md`. Headline (4 CPU cores, no GPU):

- cuts 1/1 to the frame; sound hits 20/21 with a mean timing error of 0.73 ms and no false hits; the planted
  83 ms sync fault found as +82.9 ms and nothing else flagged; each fighter one id through the cut;
- 6.5 s of video processed in 3.5 s at 259 MB peak; a cached re-ingest takes 0.045 s;
- real token use (API usage records, same five questions, Haiku sub-agents): with VYRN 5 model calls, 21 k
  context added, 5 k output, 26 s; with frame extraction 8 calls, 35 k added, 17 k output, 90 s. VYRN answered 4 of
  5 correctly (footstep counting is the gap), frame extraction 5 of 5.

## Limits (measured on a real film, `vyrn/bench/RESULTS.md` v0.2)

- **For Paper Cinema's own films, use the native input.** On `dash-test` (follow camera, large subject) the pixel
  path keeps the hero's identity but its boxes are poor (IoU 0.33) and impacts come out as flashes, not freezes.
  The pixel path is for videos that have no timeline: references, other people's films, a render to verify.
- **Next backend for subjects:** SAM 2.1 (Apache-2.0) through the `objects` slot; a follow camera needs
  segmentation, not background subtraction.

## Older limits (v0.1)

- **Moving camera + impacts:** a hit-stop under a moving camera is not detected (the camera keeps moving through the
  freeze); per-subject optical flow or a tracker backend is the fix.
- **Footsteps from pixels are weak** (bottom-of-blob rule); a pose backend (MediaPipe from `tools/mocap.py`) is
  the planned replacement. Footstep *sounds* are timed well.
- **Subjects that never move** become background (median model). A segmentation backend (SAM 2.1) fixes that.
- **Native from Paper Cinema needs a timeline**, which needs the browser engine (`npm install` for three.js);
  the benchmark uses a synthetic timeline in the same format. Blender and Unreal adapters are specified (they write
  the timeline shape, `vyrn/native.py`) but not built.
- **Long videos:** the analysis copy is held as one `.npy` (about 136 KB per frame at 160 px); fine for Shorts,
  chunking is needed beyond ~20 minutes.
