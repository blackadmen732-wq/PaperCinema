# AUDIT: the automated studio QA

`tools/audit.mjs` checks any film against the measurable rules of `STUDIO-STANDARD.md`, so a problem that was found
once cannot come back unnoticed. **Run it before every full render** (it draws nothing, so it is fast) and again on
the rendered frames.

```bash
node tools/audit.mjs film/<name>.json                          # geometry + cue checks + pixels on ~14 rendered samples
node tools/audit.mjs film/<name>.json --pixels 0               # fastest: nothing is drawn
node tools/audit.mjs film/<name>.json --frames output/frames-x # after a render: pixel checks on the real frames
node tools/audit.mjs film/<name>.json --step 2                 # long films: measure every 2nd frame
node tools/audit.mjs film/<name>.json --strict                 # majors also fail (exit 1)
```
Output: a scored report on the terminal, `output/<name>.audit.md` (readable) and `output/<name>.audit.json` (every
finding, every number). **Exit code 1 = at least one critical finding** (2 = the page has no hooks or bad usage).
If `output/<name>-sound.mp4` exists (or `--sound file`), the mix is measured too.

## How it works
1. It opens the film's page in headless Chrome, like the renderer.
2. For every frame it calls `window.AUDIT.at(t)` (from `engine/audit-hooks.js`, installed by `engine/motion.js` and
   `engine/main.js`). The page poses everything and places the camera **without drawing** and returns: the camera;
   each fighter's 8 key joints in the world and on the screen; a screen box; the blade; ray casts from the lens to
   head, chest and hips (anything that is not a fighter in the way?); an 8 × 14 grid of rays (foreground blockers,
   nearest geometry); the ground under the camera; the speed-ramp rate; whether the frame is the ink frame.
3. Checks run on that data; pixel checks on rendered samples or on `--frames`; sound checks on the cue lists
   (`film.sounds` + `window.EVENTS`) and on the mixed audio (10 ms loudness envelope, EBU R128 loudness).
4. Each finding has a severity: **critical** (the film is broken: fix before rendering), **major** (a viewer will
   notice), **minor** (polish), info. Each category starts at 10; a finding costs 4 / 1.5 / 0.5 points, and repeats of
   the same check cost less each time.

## The checks
| Check | Category | Rule (numbers in `RULE` at the top of the tool) | Severity |
|---|---|---|---|
| `hook-black`, `hook-no-subject`, `hook-slow` | hook | first frame not black; subject on screen within 0.5 s; something moves within 2 s | major / major / minor |
| `subject-off-screen` | staging | a subject has ≥ 50% of its joints in frame (a close-up counts: figure larger than the frame with a key joint in it) | critical from 3 frames |
| `subject-tiny`, `subject-small` | staging | subject height ≥ 7% (12% for longer than 1 s) of the frame | major / minor |
| `subject-occluded`, `subject-part-hidden` | camera | head and chest not behind an object | critical from 3 frames / minor |
| `camera-under-ground`, `camera-in-geometry` | camera | lens ≥ 0.08 m above ground, ≥ 0.12 m from any geometry | critical |
| `camera-in-subject`, `blade-through-lens` | camera | lens ≥ 0.28 m from the body; blade ≥ 0.12 m | major / minor |
| `foreground-blocker` | camera | props in front of the subject cover ≤ 35% of the frame | major (critical > 60% for 6 frames) |
| `camera-pop`, `camera-swim` | camera | no turn > 35° in a frame without a cut; no pan > 12°/frame for 5 frames | major / minor |
| `no-lead-room`, `head-cropped`, `face-outside-safe-zone`, `always-centred` | composition | lead room, headroom, Shorts safe zone (6–82%), thirds | minor |
| `foot-slide` | animation | a planted foot moves < 1 m/s (a slide over 0.4 m needs dust) | major (minor with dust) |
| `joint-pop`, `body-flip` | animation | no single-frame jump of a hand or the head (> 0.45 m); no body turn > 100° in a frame | major |
| `dead-hold` | animation | something moves at least every 1.5 s | minor (major from 3 s) |
| `blade-teleport`, `fast-blade-no-smear` | slash/smear | tip step ≤ 3.2 m per frame; above 1.2 m per frame the smear is on | major |
| `no-dust`, `paper-smear`, `no-post-fx` | effects | dust on dash / skid / landing; the smear is light; post FX on | major / minor / minor |
| `black-frame`, `over-bright`, `clipping`, `blank-frame`, `low-contrast` | picture | luma 10–225, < 45% clipped (< 20% wanted), contrast | critical / major / minor / major / minor |
| `hit-without-sound`, `hit-inaudible`, `hit-not-above-whoosh` | sound | every hit has a transient on its frame, audible, ≥ 9 dB above what precedes it | major / major / minor–major |
| `no-whoosh-before-contact`, `same-whoosh-twice`, `too-many-whooshes`, `sound-mush` | sound | whoosh before a clash; rotate sources; ≤ 3 per second; transients ≥ 60 ms apart | minor |
| `silence-gap`, `loudness`, `sound-clipping`, `speech-over-action`, `sound-out-of-date` | sound | no digital silence; −14 ± 2 LUFS; peak < −0.4 dB; lines in the pauses; mix matches the cut | minor … major |
| `shot-too-short`, `shot-too-long`, `line-cross`, `direction-flip` | edit/rhythm | shots 0.33–8 s; 180° line; direction of travel | minor |
| `too-much-slow-motion`, `ramp-too-slow`, `ramp-without-moment` | edit/rhythm | slow motion < 25% of the film; rate ≥ 0.15; a key moment inside each ramp | minor (major > 35%) |

What it cannot judge (idea, silhouettes, line of action, taste) is printed as a checklist at the end of each report:
look at the stills for those.

## Deliberate exceptions
A film can waive a check for a time span, with a reason (it then shows as info):
```json
"audit": { "waive": [ { "check": "foreground-blocker", "from": 0, "to": 1.2, "why": "the tree wipes the frame on purpose" } ] }
```

## Adding a check, or hooks for a new page
- A new rule: add its number to `RULE`, write the check with `add(check, category, severity, t0, t1, message, fix)`,
  add a row above and the rule to `STUDIO-STANDARD.md`.
- A new page: `import { installAudit } from './audit-hooks.js'` and call it once with `scene`, `camera`, the fighters
  and a `stage(t)` that poses and places the camera without drawing (see the end of `engine/motion.js`). Meshes that
  are effects (sparks, dust, light) carry `userData.noAudit = true` so they do not count as obstacles.
