# MOCAP: motion capture from a phone video

Film a move with a phone (a dash, a cut, a jump, a kata) and turn it into our motion data: a performance key
list for any film, or a named move for `library/moves.json`. Everything runs on this machine's CPU, with an
Apache-2.0 pose estimator.

```bash
python3 tools/mocap.py clip.mp4 --out library/mocap/dash.json --start 1.2 --end 3.4 --tol 0.05
python3 tools/mocap_film.py library/mocap/dash.json --out film/dash-cap.json      # play it on our figure
python3 tools/mocap_sheet.py film/dash-cap.json clip.mp4 --times 0.3,0.8,1.5 --out output/stills/mocap-dash.png
```

## 1. Filming (tell the performer this)

| Do | Why |
|---|---|
| **Phone on a tripod (or propped), not moving, level** | Travel (root x/z) is measured against a still camera. A tilted phone tilts the floor: if you can't keep it level, measure the tilt and pass `--tilt <deg>` |
| **Side or 3/4 view** of the move (3/4 front from the sword side is best) | Straight-on views hide depth: a cut toward the lens is guessed, not seen |
| **Whole body in frame the whole time**, feet included, with a margin | Feet give stance, crouch, weight and jumps. A cut-off foot = a guessed foot |
| Performer 3–4 m away; nothing in front of them | The model is for one person within ~4 m (model card). Props in front (a bamboo stand) cause swaps |
| **60 fps** if the phone can (30 is fine) | Fast cuts last 3–4 frames at 24; more frames = cleaner smoothing |
| Plain background, **good even light**, fitted clothes in a colour that differs from the floor and the wall | The model finds limbs by contrast. Wide hakama hide the knees: the knees will then be guessed |
| One person in frame | The tool tracks one person |
| Hold still for half a second at the start and the end | Gives a clean first and last key, and the facing |
| Same handedness as our fighters (sword in the right hand, right foot forward), or use `--mirror` | Our rig's right foot leads (`stance`); a left-foot stance is stored as `stride` (§4) |

A real sword is not needed; a stick of the same length helps the arms look right. The blade angle itself is
not captured (see §4).

## 2. Running it

`tools/mocap.py <video> --out library/mocap/<name>.json [options]`

| Option | Meaning |
|---|---|
| `--start s --end s` | The part of the clip to capture |
| `--fps 24` | Output rate (film rate) |
| `--tol 0.05` | Simplify to keyframes: no channel may be off by more than 0.05 rad (metres count double). Without `--tol`/`--keys`: every frame |
| `--keys N` | Exactly N key poses (Douglas-Peucker in pose space: keeps the poses the motion turns on) |
| `--as-move NAME` | Also write a `library/moves.json`-style move (`dt`, relative `fwd`/`side`, `turn`) under `"move"` in the output |
| `--pose NAME` | Named pose under every key/beat: gives the channels mocap does not solve (wrist roll, clavicles). Moves default to `neutral` |
| `--mirror` | Mirror the performance (a left-handed take, or a mirrored selfie video) |
| `--facing auto` | `auto` (default) = starts at 0,0 facing +z; `keep` = as filmed (+z = toward the lens); a number = start facing that many degrees |
| `--at x,z` | Start position after `--facing` |
| `--model full` | `lite` / `full` / `heavy` (heavy is best and ~3x slower) |
| `--hfov 65` | The phone's horizontal field of view (main camera ~65°, 0.5x ultra-wide ~110°): used to measure travel |
| `--tilt 0` | Degrees the phone looks down; `auto` guesses from straight-leg frames (rough: check the stills) |
| `--floor-slope` | Fit a sloped floor (long walks toward/away from the lens) |
| `--jump-min 0.12` | Both feet must clear this (m) for a jump |
| `--no-root`, `--no-head`, `--no-wrists`, `--no-raw` | Leave those out |

Speed: about 17 frames/s with `full` on this 4-core CPU (a 7 s clip at 30 fps in ~15 s). The model downloads
once to `~/.cache/paper-cinema/mediapipe/` (Hugging Face, litert-community).

**Output** (`library/mocap/<name>.json`): `keys` (`{t, x, y, z, ry, tx…, rsx…, stance, crouch, weight, stride, phase}`,
ready for `film.performances.<id>.keys`: shift `t` to place it), `contacts` (per output frame: right foot, left
foot, airborne), `camera` (where the phone was, in the same world), `scale` (performer → our figure), `source`,
`move` (with `--as-move`) and `raw` (every source frame: image landmarks, world landmarks in our axes, pelvis path).

## 3. How it works (tools/mocap.py)

1. **Estimate**: MediaPipe Pose Landmarker (BlazePose GHUM 3D) on every source frame, video mode (tracking).
   33 landmarks: in the image, and "world" landmarks in metres around the hips.
2. **Camera → our world**: x right of the frame, y up, +z toward the lens. The pelvis position per frame is solved from
   the 2D/3D landmark pair with a pinhole camera (`--hfov`), linear least squares.
3. **Left/right flips**: each frame is compared with a prediction from the frames before it, whole body / arms / legs
   swapped or not; the closer one wins.
4. **Smoothing**: one-euro filter run forward *and* backward and averaged (zero phase: a hit stays on its frame), then a
   small-window Savitzky-Golay (0.15 s, order 2) on the channels (keeps peaks).
5. **Ground contact**: lowest-foot height over a fitted floor + foot speed. Airborne = both feet up ≥ 12 cm for ≥ 0.1 s
   *and* the pelvis above its usual height (monocular depth makes deep crouches look like small jumps otherwise).
6. **Solve** (rig of `engine/figure.js`; scale = our leg 0.90 m / the performer's):
   - `ry` from the pelvis line (85 %) and the shoulder line (15 %); root `x/z` = pelvis travel minus the weight shift
     (our root sits between the feet).
   - `stance` = right-foot-ahead distance along the facing; `weight` from the hips over the feet
     (`hips z = weight × stance × 0.35`); `crouch` = 0.86 m − hip-over-ankle height; `y` = lift while airborne.
   - waist `tx/ty/tz` and chest `cx/cy/cz`: the pelvis→shoulders rotation split in half (each gets the half rotation),
     the chest clamped first, the rest to the waist; `tx` minus the `weight × 0.05` lean the rig adds.
   - arms in the solved chest frame: closed-form `rsx/rsy/rsz` (upper-arm direction + bend plane) and `rex` (elbow
     angle), then a bounded least-squares fit of both bone directions inside the joint limits, pulled lightly toward
     the previous frame (no flips between Euler twins). `rwx` from the knuckles (×0.7).
   - head from ears (side axis) + nose (front, 0.25 rad below the ear line): half to the neck `nx/ny`, half to `hx/hy`, roll `hz`.
7. **Limits**: the joint limits of `engine/validate.mjs`.
8. **Keys**: every frame, `--tol`, or `--keys N` (Douglas-Peucker on the pose curve).

## 4. Limits of the rig and the capture

- **Stance is front-to-back only.** Our legs bend in the facing plane: a wide side stance becomes a straight-legged
  narrow one. A **left-foot-forward** stance is written as `stance: 0, stride: d, phase: -1.5708` (the walking
  channels put the left foot ahead by `d`). `weight` has no effect then.
- **The blade angle is not captured**: wrist roll (`rfy`, `rwz`) and the grip can't be seen from body landmarks.
  Add them by hand on the cut keys (copy them from the cut poses in `library/poses.json`, docs/ANIMATION.md §11),
  or use `--pose <a cut pose>` so every key inherits them.
- **Both hands on the handle**: the capture keys the left arm as filmed. If you put the clip inside a `twoHand`
  window, the engine's IK replaces the left arm (good for two-handed cuts: it then truly holds the handle).
- **Depth**: travel toward/away from the lens is the weakest number (monocular). Film side-on for dashes.
- **Head pitch** on a real face uses a fixed nose offset; turned-away heads are guessed (`--no-head`).
- The motion page turns heads toward the opponent; `tools/mocap_film.py` subtracts that pull for its hidden
  target. In a real duel film the pull is wanted (eyes on the opponent).

## 5. Accuracy (synthetic test)

`python3 tools/mocap_synth_test.py --render` renders our own figure doing known moves
(`film/mocap-synth.json`: kiri-oroshi, kesa-giri, yoko-giri, jump-back, rising-cut, a turn; locked 3/4 camera),
captures the video and compares every channel with the truth from `tools/mocap_truth.mjs` (which poses the figure
exactly as `engine/motion.js` does, two-hand IK included).

Three tests, 277 frames (11.5 s) each. Mean absolute error (90th percentile or max in brackets):

| | A. solver only (true joints) | C. after the network (projected truth + MediaPipe-sized noise) | B. MediaPipe on our rendered paper figure |
|---|---|---|---|
| Upper arm direction (R / L) | 1.2° / 1.3° (p90 4°) | 5.7° / 6.7° (p90 10–12°) | 90° / 72°: fails |
| Forearm direction (R / L) | 1.5° / 1.4° (p90 5°) | 6.5° / 7.0° (p90 11–13°) | 64° / 83°: fails |
| `rex` / `lex` elbow | 0.03° / 0.1° | 5.2° / 7.3° | 67° / 62° |
| `rsx rsy rsz` | 1.4° 0.6° 0.5° | 4.9° 7.4° 4.1° | |
| `ry` facing | 1.5° (max 7.7°) | 4.8° (max 17°) | 12° |
| waist `tx ty tz` | 2.0° 2.2° 0.3° | 2.4° 4.3° 1.1° | 37° 13° 18° |
| chest `cx cy cz` | 1.8° 0.9° 0.3° | 2.8° 2.9° 1.1° | |
| neck/head `nx ny hx hy` | 0.8° 1.4° 0.7° 1.4° | 4.0° 3.2° 4.1° 3.7° | |
| root `x` / `z` travel | 0.3 / 0.2 cm | 5.1 / 3.5 cm | 38 / 97 cm |
| `stance` / `crouch` | 1.0 / 0.05 cm | 2.7 / 1.9 cm | 49 / 49 cm |
| jump `y` (true jump 22 cm) | max 8 cm | max 14 cm | |
| left/right swaps undone | | 7 of ~8 injected | |

`lsx/lsy/lsz` as Euler angles differ more (17°) only because the two-hand IK arm has Euler twins; as bone
directions (the rows above) the left arm is as good as the right. `rwx` is not scored (the paper hand has no fingers).

**B fails, and that is a finding:** MediaPipe does not see our faceless paper figure in wide hakama as a person:
the skeleton collapses into the hakama and the head is missed (`output/stills/mocap-synth-mediapipe.png`). So a
render of our own figure cannot measure the estimator; C measures everything after it, with errors of the size
MediaPipe makes on real people (2D ~2 px, 3D ~3 cm per joint). On a real person (the CC-BY iaido clip,
`output/stills/mocap-sheet-iaido.png`) facing, arm raises, cuts and crouch read correctly by eye, and the solved
arms follow MediaPipe's own 3D bones to 1.1° mean (max 15°).

**Reading it:** A checks the solver (maths, signs): with perfect joints it is near exact. C adds the camera solve,
flip fixing, smoothing and contacts under realistic noise: that is what a good real clip gets, plus the network's own
error on that clip. Run `python3 tools/mocap_synth_test.py` (A and C, 5 s) after changing the solver;
`--render` re-renders the video for B (~20 min on this CPU).

## 6. Clean-up and anime timing on top

Captured motion is real-time and evenly busy; anime is not. After capturing:

1. **Reduce**: `--keys 8` to `--keys 14` for a cut or a dash (or `--tol 0.06`). Few keys = the engine's monotone curves
   do the in-betweens, and the next steps get easy.
2. **Retime** the keys (edit `t`): shorten the strike to 2–4 frames, lengthen the anticipation, add a hold
   (repeat a key ~0.15 s later) after the hit: the Strike Grammar (docs/STYLE-AND-FIGHT-SYSTEM.md §2).
3. **Add the motion layer** (docs/ANIMATION.md §10): `"ease": "antic"` on the wind-up key, `"ease": "snap", "drag": 0`
   on the contact key, `"settle": true` on the finish; turn on `"motion": { "overlap": true }` for follow-through
   (`mocap_film.py` leaves it off so the raw capture can be judged as filmed).
4. **Exaggerate**: deepen `crouch` on the load, lengthen `stance` on the lunge, push `rsx` past the filmed angle on
   the wind-up; stay inside the checker's limits.
5. **Blade**: set `rwx/rwz/rfy` on the wind-up and contact keys from the matching cut pose.
6. **Make it a move**: `--as-move <name>` and paste the `"move"` object into `library/moves.json` (beats carry
   `dt`, `fwd`, `side`, `turn` and the joints, so it plays from wherever the fighter stands and faces; `speed`
   and `dist` scale it like any move). Then `node engine/validate.mjs`.

Check every step with stills: `python3 tools/mocap_film.py …` then `tools/mocap_sheet.py` (source | ours).

## 7. Files

| File | What |
|---|---|
| `tools/mocap.py` | The capture: video → landmarks → channels → keys / move |
| `tools/mocap_film.py` | Capture → a motion-page film (camera where the phone was, hidden still target, head-pull compensation) |
| `tools/mocap_sheet.py` | Contact sheet: source frame with landmarks / our figure (`output/stills/`) |
| `tools/mocap_truth.mjs` | Ground truth: effective channels and joint positions of a performer, posed as `engine/motion.js` does |
| `tools/mocap_synth_test.py` | The synthetic accuracy test (§5) |
| `film/mocap-synth.json` | Our figure doing known moves for the test |
| `film/mocap-test.json` | The CC-BY iaido capture played on Kojiro |
| `library/mocap/` | Captures + `CREDITS.md` (sources and licences) |

Test clip: [Iaido 2.webm](https://commons.wikimedia.org/wiki/File:Iaido_2.webm) (CC BY 4.0, Das Morton). To redo it:
`curl -L -o output/mocap/src/iaido2-480p.webm https://upload.wikimedia.org/wikipedia/commons/transcoded/7/7d/Iaido_2.webm/Iaido_2.webm.480p.vp9.webm`
then `python3 tools/mocap.py output/mocap/src/iaido2-480p.webm --start 59 --end 66 --out library/mocap/iaido-cut.json`.

Install (once): `pip install mediapipe opencv-python-headless scipy`; MediaPipe needs `libegl1 libgles2`
(`apt-get install -y libegl1 libgles2 libgl1`).
