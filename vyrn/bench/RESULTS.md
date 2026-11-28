# VYRN v0.1 benchmark results (2026-11-28, measured on this machine: 4 CPU cores, no GPU)

Reproduce: `python3 -m vyrn.bench.synth --out output/vyrn-bench/duel && python3 -m vyrn.bench.run output/vyrn-bench/duel`
(full numbers land in `output/vyrn-bench/duel.results.json`).

Scene: 6.5 s, 24 fps, 360×640, two paper fighters, one hard cut to a panning camera, 21 placed sounds (16 footsteps,
4 steel clashes, 1 hit), 3 whoosh decoys, one clash sound planted 83 ms late. Truth comes from the same simulation,
written as a Paper Cinema timeline.

## Accuracy of the external (video-file) path

| What | Result |
|---|---|
| Hard cuts | 1 of 1, exact frame, no false cuts |
| Sound hits | 20 of 21 found (the missed footstep sits under the tail of the loud hit before it); timing error mean **0.73 ms**, worst 9.7 ms; no false hits |
| Whoosh decoys | 0 of 3 counted as hits (2 labelled `sound.swell`, 1 overlaps the real hit at 5.13 s) |
| Planted sync fault | found, the only one flagged: `blade-contact.01` sound **+82.9 ms** late (planted +83.3 ms) |
| Impacts (picture) | 3 of 5: every clash with a hit-stop on the locked-off shot, to the frame. Missed: the clash under the panning camera, and the final hit (no hit-stop by design). 1 false freeze (both fighters easing to a stop at 3.25 s; it has no sound, so it is not fused into an `av.impact`) |
| Identity | each fighter keeps **one id for the whole video, through the cut**, 0 id switches (before colour re-identification: 3 ids each) |
| Subject boxes vs projected skeleton | mean IoU 0.53 (orange, the box includes the raised sword, the truth box does not) and 0.65 (red); IoU ≥ 0.5 on 60 % and 85 % of frames |
| Entities found | 5 (2 fighters + 3 short-lived fragments) |
| Footsteps from pixels | weak: 5 of 16 within 2 frames, 9 false. The sound side times footsteps to 1 ms; the picture side needs a pose backend |
| For comparison, `tools/listen.py` | 7 of 21 sounds, in 50 ms steps; 1 of the 12 footsteps in the first 3 s |

## Cost of processing

| | Native (timeline) | External (video + audio) |
|---|---|---|
| Ingest time | 0.08 s | 3.5 s for 6.5 s of video (0.54× real time) |
| Peak memory | 49 MB | 259 MB (was 498 MB before the background stack went to float16 and 48 samples) |
| Second ingest of the same file | 0.045 s (cache hit by sha256) | 0.045 s |
| A real 2 s turntable (512×512, `assets/previews/samurai_front_turntable.mp4`) | | 1.45 s, 191 MB |

## Real token use: the same five questions, answered by an agent two ways

Both runs: Claude Haiku as a sub-agent in this session, same video, same five questions, same instructions to be
efficient. Run A could only use `python3 -m vyrn` commands; run B could use ffmpeg, its own numpy scripts, image
reads and `tools/listen.py`, but not VYRN. Token counts are the API usage records of every model call in each run
(not text-length estimates). Both runs start from the same ~167 k-token sub-agent context (tool definitions), so
"added by the work" is the honest per-task number.

| | VYRN, first run | VYRN, after fixes | Frame extraction |
|---|---|---|---|
| Model calls | 4 | 5 | 8 |
| Context added by the work | 18.8 k | 21.3 k | 35.5 k |
| Output tokens | 5.0 k | 5.1 k | 17.0 k |
| Total input billed (incl. cached base) | 0.72 M | 0.91 M | 1.53 M |
| Wall time | 26 s | 26 s | 90 s |
| Correct answers (of 5) | 2 fully, 2 partly | 4 | 5 (clashes: 3 of 4) |

What the runs taught us, and what changed between the two VYRN runs:
- Run 1 reported each clash one frame late (the event marked the first frozen frame) and counted a false freeze as a
  clash. Fixed: `motion.freeze` is now timed at the impact frame, and a freeze plus a sound hit become one
  `av.impact` with its offset, so "when do the blades clash" is one command.
- Both VYRN runs got the footstep question wrong: VYRN lists sound hits but does not yet say which are steps, and
  the agent trusted the weak picture-based foot contacts instead. Next fix: label hits with Sonic's catalogue
  classes (step, clash, hit) and only report picture footsteps above a confidence floor.
- The frame-extraction agent answered well because it wrote its own onset detector and colour tracker on the spot:
  that is the work VYRN does once and keeps. On a 6.5 s clip the saving is about 40 % of context and 70 % of output;
  it grows with video length and with the number of questions, because VYRN's answers do not grow with the video
  and its processing is never repeated.


## v0.2 (same day): weaknesses worked on, and the first test on a real Paper Cinema film

Changes measured below: optical-flow articulation (camera-independent motion), feet measured against the ground's
own flow, a sound `guess` per hit (thud / ringing / hit), `av.footstep` fusion, flash vs cut, low-confidence answers
that point to a cached 3-frame picture strip, and `verify --truth` (the heard sound against the film's own picture
events, not its cue list). No agents were run for v0.2; the token figures above are the last measured ones.

### Synthetic duel (exact truth)

| What | v0.1 | v0.2 |
|---|---|---|
| Footstep sounds recognised as thuds | not labelled | **15/16**, 0 false |
| Clash sounds recognised as ringing | not labelled | **5/5**, 0 false |
| Footsteps from pixels (±2 frames) | 5/16, 9 false | 4/16, 3 false; fused with sound: 3 found, 3 right |
| Impacts (picture + sound) | 3/5, 1 false | 3/5, 1 false (the pan-shot clash is still missed) |
| Independent sync check | n/a | 20/21 heard, overall offset -0.2 ms, the planted +83 ms fault flagged |
| Ingest | 3.5 s, 259 MB | 6.1 s, 256 MB (dense optical flow added) |

The thud/ringing thresholds were set on this scene, so these two rows are not an independent test; the real film
below is.

### Real film: `film/dash-test.json` (8 s, 720×1280, one hero, follow camera, 4 cuts, ink-flash impact frames)

Rendered here with `engine/render.mjs` (the preview engine, box-free motion page) and mixed with `engine/sound.mjs`;
truth from `tools/timeline.mjs` on the same film. `python3 -m vyrn.bench.run output/vyrn-real/dash-test`.

| What | Result |
|---|---|
| Native ingest (timeline) | 0.08 s, 53 MB |
| Video ingest | 9.8 s, 404 MB (0.8 s per second of 720p video); cached re-ingest 0.17 s |
| Cuts | 2 of 4, both **exactly 1 frame after** the timeline's cut frame; 3 false (a whip pan, the end card) |
| Hero identity | **one id for the whole film**, 0 switches |
| Hero box vs projected rig | mean IoU **0.33**, IoU ≥ 0.5 on only 13 % of frames: the follow camera and the large subject defeat the median-background model |
| Impacts from pixels | 0 of 4 (these impacts are ink flash frames, now labelled `flash`, not freezes) |
| Footsteps from pixels | 1 of 1 landing, but 10 false |
| Independent sync (`verify`) | 7 of 11 picture events heard within 100 ms, overall offset +8.6 ms; flags 3 sounds off by 34–71 ms and 4 picture events with no sound heard (see below) |

What `verify` reports on the real mix, to be checked by ear before anyone acts on it:
- `paper-cut.02` (3.13 s): sound 71 ms late. `footstep.00` (landing, 4.92 s): sound 70 ms early.
- No sound heard at `impact.02` (4.30 s) and `impact.03` (4.92 s); the only authored `impact` cue is at 3.90 s.
- All rendered cuts land one frame after `tools/timeline.mjs`'s cut frames (both matched cuts, and the
  histogram signal at all four: 18/41/77/114 vs 17/40/76/113). Either the render or the timeline is off by one, or
  the two count frames differently; worth one look before more tools rely on cut frames.
