# Studio standard: what every Paper Cinema video must pass

The bar: a viewer asks "is that really code?". This page is the rule book (taste and numbers). The numbers are
checked by a machine: `node tools/audit.mjs film/<name>.json` (guide: `AUDIT.md`). The taste is checked by you, on
stills, with the checklist in §11. First audit that led to these rules: `AUDIT-dash-test.md`.

**One sentence of art direction (owner's decision):** the characters and the world are **paper**; the effects are
**light and energy**. The fighters are lanterns lit from inside, so the energy that leaves them (a slash, a dash, an
impact) is that light: amber for humans, crimson for demonic blades. Only dust (sand) and a few shards (paper) are
matter.

## 1. Idea and hook
- One sentence says the film ("He cuts the tree before it knows it is cut"). No sentence, no film.
- **Second 1 is the thumbnail of the scroll.** The first frame is a readable picture (no fade from black:
  `film.fade.in` ≤ 0.12 s), the subject is on screen within 0.5 s, and something happens within 2 s (a move, a cut, a
  line, a push-in). *Audit: `hook-black`, `hook-no-subject`, `hook-slow`.*
- Every film has one image people will remember (the decisive frame). Build the shots to arrive at it.
- A test film is still a film: give it a small story (calm → burst → realisation → answer → stillness).

## 2. Staging
- The subject is **always visible**: at least half of its key joints in the frame, head and chest never behind a prop
  for 3 frames or more. *Audit: `subject-off-screen`, `subject-occluded` (both critical).*
- **Size (vertical 9:16):** action 45–75% of the frame height, the widest establishing shot 12% or more, never under
  7%. *Audit: `subject-tiny`, `subject-small`.*
- Show the geography once, early: who, where, and what the target is (one shot with both in it).
- The action must happen where the camera can see it: **the blade meets the target on a visible frame**. If a prop
  hides the contact, move the prop, the camera or the cut.
- Keep the action on the middle of the island (in the dawn set the sand ends about 8 m from the centre) and clear of
  rocks and pines (`world.obstacles`).

## 3. Camera: behave like a cinematographer
Motion-page films use `"cameraOpts": { "solver": 2 }` and the `compose` rig (`CAMERA.md` §8): you say where the
subject sits in the frame and how big it is; the solver finds the camera, follows the subject, keeps it in frame,
keeps the lens above the ground and out of the props.

### 3a. Where the camera goes for each beat
| Beat | Camera | compose values | Why |
|---|---|---|---|
| Calm / stand-off | over the shoulder towards the target, slow push-in | `basis: "target"`, `az` 190–200, `size` 0.6→0.7, `screen` [0.36, 0.55] | hero and goal in one picture |
| Anticipation (sink) | hold, or cut to low three-quarter front | `elev` −4…−8, `size` 0.6 | weight, eyes |
| Dash | side track at knee height with lead room, **or** front-low pull-back | `az` ⟂ to the run, `elev` −4, `size` 0.5–0.6, `lead` 0.17, `feel: "torpedo"`, `lag` 0.02 | speed reads across the frame |
| Slash on the move | stay on the side, arc 30–40° towards the front during the slow motion | `az0→az1`, a ramp on the contact | the blade path stays flat to the lens |
| Skid / stop | front, low, pull-back | `size` 0.8→0.5, `elev` −6, `ease: "out"` | he comes at the lens, the result is behind him |
| Turn | start behind, end over the shoulder (or whip round to the front) | `basis: "target"`, `az` 196→204 | we see what he sees |
| Realisation | dolly-zoom | `fov0` 36 → `fov1` 24 with a fixed `size` | the world bends, he does not |
| Jump: squash and take-off | low side, looking up | `elev` −16, `size` 0.5 | height |
| Jump: apex | circle from below to above/behind during the slow motion | `az0→az1` 70–90°, `elev` −16→+24 | hang time |
| Aerial slash | over the shoulder into the impact | end of the circle | the cut and its target together |
| Landing | low, wide, from the front | `elev` −5, `size` 0.55–0.6, `feel: "handheld"` | weight; the result falls either side |
| Zanshin / chiburi | slow arc + crane up + push-in | `az` 40°, `elev` −5→+7, `size` 0.6→0.8, `feel: "crane"` | breath out |
| Duel clash (two fighters) | over-the-shoulder 55–68°, or profile two-shot | KUROKO `frame` | both blades readable |

Named shots for the main engine are in `library/shots.json` (`beatCamera` lists this table for both engines).

### 3b. Moves (each needs a reason)
| Move | How | Use | Limit |
|---|---|---|---|
| Push-in | `size0 → size1` up | attention, decision | 2–5% per second when calm; fast only on a beat |
| Pull-back | `size0 → size1` down | reveal, release | ends on a composed frame |
| Orbit / arc | `az0 → az1`, eased | slow motion, zanshin | under 90° per shot; starts and stops with ease; never through a prop |
| Crane | `elev0 → elev1` | rise after a landing, fall into a calm | lens stays 0.14 m above the sand |
| Whip pan | a new beat with `feel: "whip"` | joins two beats | 3–6 frames; longer = `camera-swim` |
| Dolly-zoom | `fov0 → fov1`, `size` fixed | one realisation per film | fov 22–45 |
| Handheld settle | `feel: "handheld"` + the impact punch | after impacts | amplitude under 1.5 cm |
| Hard cut | `"cut": true` | new angle on a beat | a cut needs a reason: new information or a new energy |
| Rack focus | not built (no depth of field in the preview) | | planned with the Blender renders |

### 3c. Composition
- **Thirds, not dead centre.** Lead room in front of motion and gaze (`"lead": 0.16`). *Audit: `no-lead-room`, `always-centred`.*
- **Headroom** 5–12% of the frame in full and medium shots. *Audit: `head-cropped`.*
- **Shorts safe zone:** faces between 6% and 82% of the height (the app covers the rest). *Audit: `face-outside-safe-zone`.*
- A foreground prop may frame the shot (up to 35% of the frame, at an edge); it never fills it. *Audit: `foreground-blocker`.*
- Lens never under the ground, never closer than 0.12 m to geometry, never through the body (0.28 m).
  *Audit: `camera-under-ground`, `camera-in-geometry` (critical), `camera-in-subject`.*
- 180° rule across cuts; the direction of travel survives a cut. *Audit: `line-cross`, `direction-flip`.*

## 4. Timing and spacing (24 fps)
Fast things are fast **and visible**: the eye needs a pose before (anticipation), 1–3 frames of smear, and a pose
after (overshoot → settle). Speed ramps give the key frame time to be seen.

| Action | Anticipation | Action | Contact | Follow-through | Settle |
|---|---|---|---|---|---|
| Dash (4–6 m) | sink 5–7 f (`ease: antic`) | 6–8 f, accelerating; tip and body with afterimages | (cut on the way) | skid 6–9 f, weight back, dust | 6–10 f |
| Turn (180°) | head 3–4 f ahead (look over the shoulder) | hips 4–6 f | | blade and sleeves arrive 2–3 f late | `settle` 4–6 f |
| Jump (1.5 m) | squash 8–12 f (crouch 0.35–0.42) | stretch 2 f, rise | apex hang (`hang` 0.5–0.7), knees tucked | fall = rise time | squash 4–6 f, rise 8–12 f |
| Slash | wind-up 4–8 f | 2–3 f (`ease: snap`) | hit-stop 3–4 f (blade on blade) | overshoot 2–3 f | 6–12 f |
| Landing | (reach for the ground 2–3 f) | touch | dust ring on the frame | squash 4–6 f | rebound 8–12 f |

- **Speed ramps** (`film.ramps: [{ t, rate, in, hold, out }]`, `t` in action time, the rest in screen seconds): rate
  0.2–0.35 for the key moment (blade through the target, apex), 0.45–0.6 for a breath (the look). Hold 0.3–0.8 s. At
  most 3 per film and under 25% of the running time. The camera keeps moving in real time; that is the point.
  *Audit: `too-much-slow-motion`, `ramp-too-slow`, `ramp-without-moment`.*
- A blade tip may not jump more than 3.2 m between two frames (77 m/s); above 1.2 m per frame it needs the smear.
  *Audit: `blade-teleport`, `fast-blade-no-smear`.*
- No single-frame pops (IK flips, angles wrapping), no 100° body turn in a frame. *Audit: `joint-pop`, `body-flip`.*
- A hold breathes (moving hold, cloth, slow push-in). 1.5 s with nothing moving is dead. *Audit: `dead-hold`.*
- Feet: planted means planted. A slide is allowed only as a dash or skid, and then it carries dust. *Audit: `foot-slide`.*

## 5. Posing
- **Silhouette test:** fill the pose black; you must still read head, both arms, the blade, the legs. The blade never
  hides in front of the body from the camera's angle.
- **One line of action** from the back foot through the hips to the blade tip (C or S). Lunge: back leg straight, body
  one diagonal. Jump apex: knees tucked, body arched **back** (wind-up) then folded **over** the blade (cut).
- Squash and stretch for rigid paper: squash = crouch + chest fold + shrug; stretch = negative crouch + open chest.
- Asymmetry: shoulders against hips, weight on one leg, never a mirror pose except in a ceremonial stand.
- The head leads every turn; the eyes lead the head.

## 6. Shots and rhythm
- A Short wants a new angle or a clear camera move every 2–4 s; inserts 6–10 frames, action shots 12 or more.
  *Audit: `shot-too-short`, `shot-too-long`.*
- Fast–slow–fast: calm, burst, slow motion on the key frame, burst, stillness. Never two slow sections back to back.
- Cut **on** action (the frame the move starts), not after it.

## 7. Effects: light and energy
All deterministic in time, set from film data (`film.effects`), shared by both engines (`engine/combat.js`,
`engine/groundfx.js`, `engine/fx.js`).

| Effect | Rule | Where |
|---|---|---|
| **Slash smear** | a **crescent of light**: white-hot core, amber outer glow (crimson when `cast.<id>.demonic`), wide at the blade and tapering to a point, three hair-thin filaments that outlive it, additive, blooms, afterglow 4–6 frames. Appears above 5 m/s tip speed. | `effects.ribbon { minSpeed, afterglow, color, gain, style }` (`style: "paper"` = the old strip) |
| **Afterimages** | 2–3 ghosts of amber light behind a body faster than 7–8 m/s, each weaker; they fade in slow motion | `effects.afterimage { minSpeed, count, gap, opacity, color }` |
| **Dust** | every dash start (kick-up backwards), dash (wake line + small puffs), skid (spray forwards), take-off and landing (ring) | `effects.ground` (motion page: on by default; main engine: `effects.ground: {}`) |
| **Speed lines** | on every dash, 0.3 s, amount 0.4–0.7 | `effects.speedLines { amount }` (needs `fxBase`) |
| **Impact** | flash light (1–2 frames, never a white frame), sparks, a **shockwave ring** of light, chromatic flash, bloom pulse; a few paper shards only as an accent; at most one ink impact frame per film | `impacts[]`: `intensity`, `light`, `shards`, `colors`, `life`, `ring`, `ink`; `effects.contactFx`, `effects.sparkLight` |
| **Blade glint** | a "ping" that travels along the steel on key frames (before a strike, at the start of each speed ramp) | `effects.glints [{ t, who, dur }]` (needs `fxBase`) |
| **Contact shadow** | a soft pool under every fighter; it widens and fades as he leaves the ground | `effects.contactShadow` |
| **Motion blur** | not built (it needs several renders per frame); afterimages + smear stand in for it | |

Limits: nothing burns out. Under 20% of a frame clipped white, except the one ink frame. *Audit: `over-bright`, `clipping`, `no-dust`, `paper-smear`, `no-post-fx`.*

## 8. Light, shadow and texture (the paper look)
- **One key light** (the low sun), a visible shadow side on every form, and glow (eyes, seams, the smear) as the
  brightest thing on screen.
- **Shadows are warm violet, never black holes.** A shadow on the sand keeps 25–45% of the lit sand's brightness
  (`film.light { hemi, fill, sun, ground }` lifts them; dash test: hemi ×1.35, fill ×1.5, ground `#6a5670`).
- Contact shadow under the feet always (§7): without it figures float.
- Paper: every flat face shows fibre grain; neighbouring facets differ in tone by 5–10% so folds read; edges catch a
  rim. A face is never one flat fill. (The box figure is a stand-in; the target is the folded origami samurai,
  `research/ref-origami-samurai-standing.jpg`.)
- Grade: `fxBase.grade` set, bloom threshold 0.85–0.9 and strength 0.3–0.45, vignette 0.35–0.5, grain 0.03–0.05.
  Average luma spread (contrast) 45–65. *Audit: `low-contrast`, `black-frame`, `blank-frame`.*
- Colour script: amber = human, crimson = demonic, pink only for sakura, the sea is the only blue.

## 9. Props that get cut
- Beat sheet: blade passes → **nothing moves** for 8–12 frames (only a glowing seam) → the top slides along the cut →
  topples slowly, then fast → lands with dust and a low sound.
- A falling piece never passes through a fighter or the ground; cut pieces fly **apart, away from the cutter's
  path**, land, slide a little and stay (`props.trees[].split { world: true, side, speed, up }`).
- The cut happens in frame; petals or chips are the accent.

## 10. Sound and mix
- Every hit the eye sees has a transient **on the same frame** (`"body": true` cues follow hit-stops and speed
  ramps). *Audit: `hit-without-sound`, `hit-inaudible`.*
- The hit is 9 dB or more above what comes just before it (whoosh, bed). *Audit: `hit-not-above-whoosh`.*
- Whoosh peaks 2 frames before contact; 3 or more sources, never the same twice in a row, at most 2 per second.
  *Audit: `no-whoosh-before-contact`, `same-whoosh-twice`, `too-many-whooshes`.*
- Two different transients are 60 ms or more apart, or declared layers of one hit (`"layer": "<id>"`). *Audit: `sound-mush`.*
- Ground: dash burst, skid, push-off and landing thud come automatically from the motion (`autoSounds.ground`).
- Speech sits in the pauses of the fight. *Audit: `speech-over-action`.*
- A bed (wind, sea) never drops to digital silence; −14 LUFS ± 2, peak under −1 dB. *Audit: `silence-gap`, `loudness`, `sound-clipping`.*
- After any re-timing, mix again. *Audit: `sound-out-of-date`.*

## 11. Taste checklist (look at the stills; the tool cannot)
- [ ] One sentence says the film, and second 1 promises it.
- [ ] Geography is clear after the first shot.
- [ ] Every key pose passes the silhouette test and has one line of action.
- [ ] Anticipation → action → follow-through → settle on every strike, jump and turn.
- [ ] The cut is visible on a frame; its result reads (the seam, the slide, the fall).
- [ ] Each camera move has a reason and ends on a composed frame.
- [ ] Shadows are soft and warm; glow is the brightest thing; nothing burns out.
- [ ] Effects are light; dust and shards are the only matter.
- [ ] The last frame is a picture you would hang up.

## 12. Gate
`node engine/validate.mjs` → `node tools/audit.mjs` (no critical; every major fixed or waived with a reason in
`film.audit.waive`) → stills → full render → sound → `node tools/audit.mjs --frames <frames dir>` again on the result.
