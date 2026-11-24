# Audit: the dash test (director / animation / camera / light / sound review)

Film: `film/dash-test.json` as first rendered (commit `9ec8ca9`, 163 frames, 6.8 s, vertical). Reviewed frame by
frame (contact sheets kept in `output/before/`), measured with `tools/audit.mjs`, listened to with `tools/listen.py`.
The rules this produced: `STUDIO-STANDARD.md`. The tool that now guards them: `AUDIT.md`. What was fixed: §4.

**Verdict on the first render: 4.1 / 10.** The idea is good (dash, the tree does not know it is cut, he turns, it
falls, he jumps and splits it), but the camera lost the hero in the two moments that matter, the cut itself was
never seen, and the effects and sound were thin. After the fixes: **7.9 / 10** (limits in §5).

## 1. What was good (keep)
- The idea and the order of events; the delayed reaction of the tree (it stands, then slides, then topples).
- Anticipation before the dash (the sink) and before the jump; the hang time at the top of the jump.
- The glowing eyes with a "decide" flare; the dawn grade and grain; the one-frame ink impact idea.
- The zanshin ending with chiburi: a calm last picture.

## 2. Problems found (frames are from the first render, 24 fps)
Severity: **C** critical (breaks the film), **M** major (a viewer notices), **m** minor.

| # | Frames | Category | Sev | Problem | Root cause (code / data) | Fix |
|---|---|---|---|---|---|---|
| 1 | 0–13 | story/idea, edit | M | Opens on black, then 1 s of a still wide shot: no hook. | `fadeEl` fade-in 0.6 s hard-coded in `motion.js`; first key holds 1.0 s | `film.fade { in: 0 }`; calm cut to 0.55 s; over-the-shoulder hook with a push-in |
| 2 | 5–25 | staging | m | Hero is 15% of the frame, the trunk in front covers a quarter of it. | `frame` rig, angle −68 puts the tree near and the hero far | `compose` rig over the hero's shoulder: hero big on the left third, target small ahead |
| 3 | 28 | camera | M | The camera whips 41° in one frame to the side track. | world-space spring between two rigs, no cut | `"cut": true` (solver 2) |
| 4 | 33, 36–38 | camera, dash | **C** | **The hero is out of frame during the dash**; frame 37 is empty sand, 38 is only the tree. | the camera is a world-space spring (`torpedo` 4 Hz); the hero does 21 m/s, the spring lags over a metre and the vertical frame is 1.4 m wide | solver 2: the spring works on the offset from the subject + an in-frame guard; `lag` 0.018 |
| 5 | 37–39 | slash, staging | **C** | **The cut is never seen**: blade through the trunk happens in 1 frame with the hero off screen. | 4.85 m in 0.31 s, contact between two frames; no slow motion | speed ramp 0.2× on the contact (`film.ramps`), side camera arcs to the front during it |
| 6 | 30–40 | dash, timing | M | The dash reads as a slide: upright pose, feet planted while the body skates 6.5 m at 26 m/s; the blade tip does 96 m/s (4 m per frame). | `waki-right` pose is a standing guard; no run cycle; root and pose share one ease | dash pose leaned to one diagonal (tx 0.5, stance 0.95), afterimages, dust wake, speed lines; slow motion makes the tip step visible |
| 7 | 28–47 | effects | M | No dust on the dash or the skid, no afterimage, no speed lines: nothing shows speed or weight. | did not exist | `engine/groundfx.js`: dust kick-up, wake line, skid spray, afterimages; speed lines from `fx.js` |
| 8 | 36–40 | slash/smear | M | The smear is a thin flat white strip, off screen anyway. | `combat.makeRibbons` paper strip | crescent of light: white core, amber glow, filaments, afterglow (owner's art direction) |
| 9 | 38–40 | colour, light | m | The trunk and crown bloom to white at the cut. | flash light 6 × intensity + bloom pulse on a pink crown | `impacts[].light`, `effects.sparkLight` 3, `contactFx.bloomI` 0.2 |
| 10 | 40–47 | posing | m | The skid has no weight shift: same pose slides and stops. | `yoko-finish` held, weight +0.6 (forward) | weight thrown back (−0.5), deeper crouch, front heel digs in, dust sprays forward |
| 11 | 48–63 | turn, staging | M | The turn is shown as a chest close-up from 2.5 m: arms fill the frame, the feet and the turn itself are not readable. | orbit radius 2.5 m at fov 36 = 1.6 m of picture height | full-figure framing (size 0.5), over the shoulder to the tree |
| 12 | 49–56 | turn, articulation | M | The body turns as one block; the head does not lead; no look over the shoulder. | one key rotates `ry` 0 → π | added key: head and chest turn first (hy 0.75, ny 0.45), hips follow, blade last; slow-motion breath 0.45× |
| 13 | 61–62 | camera | m | His own blade crosses the lens. | camera on the cutting plane | different angle |
| 14 | 64–67 | camera | M | Two 48° whips in two frames; the hero is cut by the frame edge. | spring whip between beats | cut |
| 15 | 73–74 | camera | **C**/M | The camera flies through the hero (137° in a frame) and touches the ground (3 cm). | orbit `camY −1` clamped at 0.12; the path between beats crosses the body | cut to a low side shot; ground-aware clamp (`world.groundAt` + 0.14) |
| 16 | 75–85 | jump, posing | M | In the air he is a stiff hanging figure: legs straight, no tuck, no arch. Seen from straight below, tiny, with no ground: no sense of height. | `airborne-guard` / `furikaburi` poses have crouch 0.1; camera under him | apex tucked (crouch 0.34), body arched back then folded over the blade (rx −0.18 → +0.3); low side camera with the ground in frame, then the circle |
| 17 | 86 | impact | m | The ink frame is one shapeless blob. | the tree is drawn as ink too and merges with him | ink frame draws fighters only |
| 18 | 87–92 | colour, light | M | Six frames of a white-hot chest: the flash light sits inside the figure. | impact point at the body, light 6 × 1.6 | impact point at the crown, `light` 0.35 |
| 19 | 93–115 | tree/props | **C**/M | The falling crown passes **through** the hero; the halves fall through the ground; he lands 0.45 m from the stump and stands inside the wreck. | `cut.dir` towards his landing spot; `split` moves halves in the toppled local frame with no ground | the top falls towards him, he jumps through it, halves fly apart sideways in world space, land and stay; he lands 1 m clear |
| 20 | 95 | effects | M | The landing has no dust, no ring. | did not exist | landing ring + 20 puffs + contact shadow |
| 21 | all | shadow/lighting | M | Shadows are hard and nearly black; figures have no contact shadow, so the jump has no height cue. | hemisphere ground colour dark blue, sun 3.2, one 2048 shadow map | `film.light` lifts the shadows to warm violet; contact shadow pool that widens with height |
| 22 | all | texture/material | m | Flat faces, little fold shading (the box figure is a stand-in). | preview figure | out of scope here: the origami samurai in Blender; rule written in the standard §8 |
| 23 | 100–163 | edit/rhythm | m | 2.6 s of ending with the stump through his silhouette. | staging | landing in front, stump as a frame edge, arc + crane up |
| 24 | whole | camera | M | The camera only follows; it never composes (always centre), never slows the moment. | only `orbit` / `frame` rigs, no ramps | `compose` framing solver, lead room, ramps, beat → camera table |
| 25 | 3.58 s, 3.95 s | sound | M | The aerial cut and the landing are almost silent: +0 dB and +1 dB over what comes before (rule: 9 dB). | `clash-light` at gain 0.6 under the whoosh; `fall` is a quiet file | `wood-chop` + ring on the cut, synthesised `land-thud`; `"body": true` so they follow the ramps |
| 26 | 1.0–2.0 s | sound | m | Four whooshes in a second; two transients 22 ms apart; no dash, skid or push-off sound. | `maxPerSec` not set; no ground cues | `maxPerSec: 2`; automatic `dash-burst`, `skid-dust`, `jump-push`, `land-thud` |
| 27 | whole | sound | m | −16.7 LUFS, thin; the tree makes one clap for the cut and one for the crack. | few layers | wood chop, creak before the slide, petal rustle, low impact when the halves land |

## 3. Scores
Director's scores (taste + numbers). "Tool" = `tools/audit.mjs` on the same film where the category is measurable.

| Category | Before | After | Note |
|---|---|---|---|
| Story / idea | 6 | 7.5 | same idea, now with a hook and a realisation beat |
| Staging | 4 | 8 | cut visible, pieces fall clear of him (tool: 7.8 → 10) |
| Camera | 3 | 8 | composed, cuts on beats, circles in slow motion (tool: 2.9 → 9.5) |
| Timing / spacing | 5 | 7.5 | ramps give the key frames time |
| Posing / line of action | 4 | 7 | dash diagonal, tucked apex, squash on landing |
| Articulation | 5 | 6.5 | head leads the turn; feet still slide in the dash |
| Dash | 3 | 7.5 | visible, with wake, afterimages, speed lines |
| Turn | 4 | 7 | full figure, look over the shoulder |
| Jump | 4 | 8 | reads from the side, tuck and arch, circle at the apex |
| Slash / smear | 3 | 7.5 | crescent of light with afterglow |
| Impact | 4 | 7.5 | ring, sparks, petals, readable ink frame, no burn-out |
| Tree / props | 3 | 7.5 | halves fly apart and land; rocks kept out of the lens |
| Shadow / lighting | 4 | 6.5 | lifted warm shadows, contact shadow; still one shadow map |
| Texture / material | 4 | 4.5 | unchanged stand-in figure |
| Colour / grade | 6 | 7 | no clipping on the hits |
| Effects | 3 | 7.5 | light-based set, all from data |
| Sound | 4 | 7 | every hit has a transient; ground cues |
| Edit / rhythm | 4 | 7.5 | 5 shots, fast–slow–fast |
| **Average** | **4.1** | **7.2** | |

## 4. What was built so it cannot come back
| Problem class | System fix | Guard |
|---|---|---|
| Subject lost, hidden or tiny | `cameraOpts.solver: 2` (subject-relative spring, in-frame guard), `compose` rig | audit `subject-off-screen`, `subject-occluded`, `subject-tiny` |
| Lens in props / ground / body | compose guards (`world.obstacles`, `world.groundAt`, tree solids, 3-point line of sight) | audit `camera-under-ground`, `camera-in-geometry`, `camera-in-subject`, `foreground-blocker` |
| Whips instead of cuts | `"cut": true`, `feel: "whip"` | audit `camera-pop`, `camera-swim` |
| Key moment too fast to see | `film.ramps` speed ramps (three clocks: film → world → body) | audit `blade-teleport`, `ramp-*` |
| No sense of speed or weight | `engine/groundfx.js` dust, wake, landing ring, contact shadow, afterimages; speed lines | audit `no-dust`, `foot-slide` |
| Paper smear, weak impact | light crescent, shock ring, glints, per-impact light / palette | audit `paper-smear`, `over-bright`, `clipping`, `fast-blade-no-smear` |
| Pieces through bodies and ground | world-space `split` with landing | standard §9 (taste check) |
| Silent or mushy hits | body-time cues through the ramps (`events.warp`), ground cues, new synthesised sounds | audit `hit-*`, `sound-mush`, `sound-out-of-date` |
| No hook | `film.fade` | audit `hook-*` |

Final check (`node tools/audit.mjs film/dash-test.json --frames output/frames-dt`, on the re-rendered film with its
new mix): **PASS, 0 critical, 0 major, 6 minor** (tool score 8.5 → 9.7; the first render: 1 critical, 7 major, 12 minor).
The same tool on the older films: `motion-test` FAILS (frames 39–42: the arm-slide camera shows an unreadable
close-up of a sleeve; a 150° whip without a cut at 2.88 s; the clash is 12 dB *under* the whoosh), `kuroko-duel` passes
with 9 majors (foot slides, one hand pop at 4.71 s, two clashes not above the whoosh). Those are real and are next.

## 5. Still open
- The dash is still a body sliding with planted feet (the audit keeps it as a minor: "dust covers it"). It needs a
  real sprint cycle or a two-key leap (feet off the ground).
- True motion blur is not built; the afterimages are flat boxes of light on the stand-in figure.
- The mix is quiet (−21.7 LUFS; target −14): `sound.mjs` has no loudness stage yet. The first cut is 8 dB over its
  whoosh (rule 9).
- The ending holds one standing pose for about 2.5 s; chiburi filaments draw straight lines through the figure.
- The stand-in figure: flat faces, no fold shading. The origami samurai is the real fix.
- One hard shadow map; a softer penumbra needs a second, blurred map or the Blender render.
- Rack focus needs depth of field (not in the preview).
- `main.js` films get the hooks, the light smear, the ring, and opt-in dust and contact shadows, but not yet ramps
  or the `compose` rig (KUROKO rigs are a separate solver).
