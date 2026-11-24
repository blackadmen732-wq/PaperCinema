---
name: scene-direction
description: Direct a Paper Cinema scene like a film director and anime layout artist - turn a story beat sheet into a shot list, then into KUROKO camera rigs (film shots[].rig) or motion-page camera beats (film.camera), with a direction style, lighting mood, cut rhythm and a taste review. Use whenever the task is choosing shots, camera moves, angles, lenses, cuts, pacing, coverage, lighting mood or "make it look cinematic / anime / like Kurosawa, Leone, ufotable...", or reviewing why a scene looks amateur. Sits between scene-writing (story, lines) and paper-cinema-film (build, check, render).
---

# Directing a Paper Cinema scene

You are the director, the layout artist and the editor. The story is already written (skill `scene-writing`); the
build, check and render steps are in skill `paper-cinema-film`. This skill decides **what the camera sees, from where,
for how long, and in what light**, and writes it as data.

Read once per session: `docs/DIRECTION.md` (the human guide: grammar, styles, sources), `library/shots.json`
(49 named shots with every rig tested in 9:16 and 16:9, 17 styles, 11 lighting moods, a beat map), `docs/CAMERA.md` §7 (KUROKO fields),
`library/effects.json` (effects and their status). The owner's quality bar: `research/reference-videos.md`.

Marks: **[D]** documented (our own code/tests or a primary source), **[C]** commonly reported, **[I]** our inference.
Sources are listed in `docs/DIRECTION.md` §9.

---

## 1. Procedure (do every step, in order)

1. **Read the beat sheet.** For every beat write one line: *what must the viewer feel, and what must they know?*
   ("feel: dread; know: the foe is faster"). A shot that serves neither is cut. Murch ranks a cut by emotion 51%,
   story 23%, rhythm 10%, eye-trace 7%, screen plane 5%, 3D space 4% [C]: emotion first, geography last.
2. **Pick one style** from `library/shots.json → styles` (plus at most one accent style for a single beat, e.g.
   `leone-standoff` for the standoff inside `ufotable-flow`). The style gives you the shot palette, the cut rhythm
   (`asl_s`), feels, lighting mood, grade and effects. Never mix more than two.
3. **Make the shot list** (a table, before any JSON): `# · time · beat · shot id · subjects · seconds · feel ·
   light · sound cue · why`. Draw candidates from `beat_map` for the beat and from the style's `shots`.
   Shot count = beat length ÷ the style's average shot length. A 30 s Short is usually 10–18 shots [I].
4. **Lay out geography.** Decide the line (the fighters' axis) and the camera side. Establish it with the first
   two-shot. Every later shot stays on that side unless a visible move (orbit, crane) carries the viewer across (§3).
5. **Choose cut points.** Inside action: cut on the fastest frame of a motion (cut on action), and change angle by
   ≥ 30° or size by ≥ 2 steps (30-degree rule) [C]. Between scenes: a match cut, a whip, a foreground wipe, or a
   J/L cut with sound (§5).
6. **Pick the lighting mood** (`library/shots.json → lighting`) per scene, not per shot. Map it to `mode`
   (`dawn` / `studio`), an fx `grade` mood and light shafts (`library/effects.json`).
7. **Time it** (§4): strike frames, hit-stops, silences, holds, the accelerating standoff.
8. **Write the data** (§2): paste the rig from `library/shots.json`, rename subjects, convert anchor beat times, add
   `shakes` / `events.impact` on every hit.
9. **Score the camera (required, before any still).** `node tools/camera_check.mjs film/<name>.json` — the camera
   evaluator (`docs/ARCHITECTURE.md` §Camera Director) measures every shot: subject / weapon / target visibility and
   occlusion, action clarity on the strike frame, framing size against the size the shot asks for, the 180° line and
   the 30° rule, cut timing against the verified strikes, camera motion (a whip without a cut, jerk, clearance from
   the set) and emotional fit per beat. **It exits 1 on a rejected shot**, prints the reason ("the orbit camera
   passes 0.42 m from the props during the strike at f268") and names the nearest passing alternative from
   `library/shots.json` — take it, or fix the rig and run it again. It also runs inside `node tools/audit.mjs` as the
   camera section, so the two can never disagree.
10. **Check and look:** `node engine/validate.mjs film/<name>.json`, then
   `node engine/render.mjs --film film/<name>.json --still auto` and **look at every still** with the review
   checklist (§7). Fix, repeat. Only then render a section or the film (skill `paper-cinema-film`;
   `node tools/render_supervisor.mjs film/<name>.json --plan` shows the shot-by-shot render plan).

---

## 2. Writing it in our data format

### Main engine (`film/<name>.json → shots[]`)
```json
{ "id": "S4", "name": "Standoff OTS", "mode": "dawn", "start": 6.0, "end": 8.4,
  "rig": { "type": "frame", "subjects": ["kojiro", "musashi"], "size": "full", "angle": 62, "elevation": 4,
           "dist": 0.52, "fov": 34, "feel": "dolly", "behaviours": ["lead"] } }
```
- Copy `rig` for a vertical film (9:16, the default) or `rig_16x9` (when present) for a horizontal one.
- Replace `hero` / `foe` with performer ids; parts: `.head .chest .hips .hand .root`. The first subject of a
  two-shot is the **near** fighter (whose shoulder we look over).
- **Anchor rigs:** library beat `t` values are seconds from the shot start. Add `shot.start` to each (the checker
  wants absolute times inside the shot).
- `pair` entries are the two sides of one cut: shot A's rig, then shot B's rig.
- Every hit: a `shakes` entry `{ "t", "dur": 0.35–0.5, "amp": 0.008 light / 0.015 strong }` and, for the decisive
  blow, `events.impact`. KUROKO adds a 7° punch-in over 2 frames on those times by itself.

### Motion page (`film.camera`, as in `film/motion-test.json`)
Copy `beat`. Its `t` (and a slide's `until`) are **absolute** seconds; `who` is the cast id; frame beats use `elev`
(not `elevation`); `slide` follows joints `eyes, shoulder, elbow, wrist, tsuba, tip, hips, head`; an `orbit` beat
sweeps until the **end of the film**, so use it last.

### Rig facts that bite (found by testing every library rig against `film/kuroko-duel.json`) [D]
| Fact | Do this |
|---|---|
| In 9:16 a `frame` two-shot at `dist` 1 puts the far fighter at only 17–20% of frame height (the narrow width drives the distance) | Use `angle` 50–65 (depth staging) and `dist` 0.5–0.75. Library `rig` values are already tuned: OTS 0.52 → 44%, lunge 0.52 → 40% |
| Single-subject `frame`: `angle` 0 = camera straight in front of the subject, i.e. on the duel line, behind the opponent | Use 20–70. **Hero: positive angle, foe: negative angle** to stay on the two-shots' side of the line |
| `orbit` `deg` is world azimuth (0 = camera on +z of the target), not relative to the fighters | Check the set's staging; our sets run the duel line along z, so keep both degrees in (−180, 0) or (0, 180) |
| An orbit around the midpoint of two fighters at radius < 4 m loses one of them in 9:16 | Orbit one fighter (`target`), or radius ≥ 5 near the duel axis (library `standoff-orbit` 9:16: −20 → −50, r 5) |
| Two `.hand` subjects: the hand-to-hand axis flips during a strike and the camera jumps the line | Frame chests (`hero`, `foe`), `size` close, `dist` ≈ 0.4–0.6 |
| Springs arrive in: `locked` ~0.1 s, `dolly` ~0.35 s, `crane` ~1 s; `torpedo` overshoots ~8%, `handheld` ~5% | Give a crane shot ≥ 2.5 s; anchor beats ≥ 0.35 s apart unless you want a snap |
| Behaviours default to `reveal, push, jump, dutch, lead` | Composed or still shots: `"behaviours": []`. Standoffs: `[]` or `["lead"]` |
| `roll` is clamped to ±10° | A bind wants 12–18° (docs/FIX-LIST.md); 10 is today's max |
| A rig shot opens settled (1 s pre-roll) | Do not fake an "arrival" with a rig; use an anchor with two beats |
| The blade rig needs the live blade frame (main engine); elsewhere it falls back to a frame rig | Test blade shots with stills, not with the resolver |

---

## 3. Geography: the rules and when to break them

- **180° rule.** All library rigs sit on the same side of the line (tested). Reverse shots use negative `angle` on
  two-shots (`reverse-over-shoulder`), not `"side": "right"`. Use `side: "right"` only for a deliberate line cross,
  and cross on a neutral shot (profile `angle` 0, an axial `kubrick-one-point`) or inside one visible move (orbit) [C].
- **Eyelines.** In a shot / reverse-shot pair keep the same `fov`, `elevation` and size so the eyelines match; the
  hero looks screen-left in one, the foe screen-right in the other (the rig does this if you keep the side).
- **30° rule.** Two consecutive shots of the same subject differ by ≥ 30° of angle or ≥ 2 size steps
  (wide/full/medium/close/extreme), or it reads as a jump cut [C]. Exception: Kurosawa's axial cut (same axis, a
  big size jump, on a sudden action) [C].
- **Screen direction.** A fighter who exits right enters the next shot from the left.
- **Depth over width in 9:16.** Stage fighters in depth (near/far), not side by side; side-by-side profile
  two-shots make figures tiny in vertical. Keep the profile for a held graphic beat (`silhouette-wide`,
  `delayed-reaction-hold`).

---

## 4. Timing and rhythm (24 fps)

| Thing | Number |
|---|---|
| Hook | The first frame is lit and readable; no fade from black longer than 4 frames; the most violent or most mysterious image within 1 s [C] |
| Standoff cutting (Leone build) | Shots shrink: 3.0, 2.0, 1.5, 1.0, 0.7, 0.5 s while sizes tighten wide → eyes; then the strike [C/I] |
| Insert before a strike | 6–10 frames (eyes, hand on hilt, foot grind) [D docs/FIX-LIST.md] |
| Strike | Prepare long (0.3–1 s) / strike 1–2 frames / relax long (0.5–1.5 s) [C] |
| Glint | 4–6 frames before contact, 6–8 frames long [C] |
| Hit-stop | 3–4 frames; the decisive blow gets the longest [D motion page] |
| Impact zoom | fov 34 → 24 → 16 in 2-frame steps [D docs/FIX-LIST.md] |
| Exchange shots | 0.6–1.6 s each (anime); hold 3–6 s if the choreography is good enough to show whole (Wick, Hong Kong) [C] |
| Pause-burst-pause | 0.5–1 s still → 3–6 moves → 0.5–1 s still (Hong Kong rhythm, Bordwell) [C] |
| Silence before the decisive cut | 0.5–1.5 s, wind only [I research/anime-fight-craft.md] |
| Hold after the decisive cut | 1.5–3 s frozen, then the paint blooms 80–200 ms late (KIZU) [C/I] |
| Monologue | One shot per voice line, cut in the pause; push-in 2–5% per second [I research/reference-videos.md] |
| Average shot length | Classic Hollywood 8–11 s; modern mainstream 3–5 s; fast action ~2–3 s [C Bordwell]. Shorts fight body: 1–2 s; monologue: 2.5–5 s [I] |

Speed up through the scene (jo-ha-kyū: slow, break, rapid), then stop dead [C]. Never cut at the same rate for
more than 4 shots in a row: vary 1.5 / 0.8 / 0.8 / 2.5 [I].

---

## 5. Cuts and transitions

- **Cut on action:** end shot A mid-swing, start shot B on the same swing from ≥ 30° away. Motion hides the cut.
- **Match cut (Satoshi Kon):** same shape, same screen position and size across the cut (eye glow → lantern sun).
  Check both stills; the shapes should line up within ~5% of frame width [C/I].
- **J cut:** the next shot's sound starts 4–12 frames before its picture (a koiguchi click before the hand insert,
  a voice line before the face). **L cut:** this shot's sound runs on under the next picture (the clash ring over
  the reaction) [C].
- **Whip:** cut on the fastest frame of a whip (motion blur is planned; the torpedo spring gives the snap).
- **Hong Kong double hit:** end shot A on the contact, start B 2–4 frames before it from ≥ 30° away; at most twice
  per film [C].
- **Hard cut to black** + small logo: the reference Shorts' ending [I].

---

## 6. Light and colour

Pick one mood per scene from `library/shots.json → lighting` and say it in the shot list.
- **Lantern Origami rules** (docs/STYLE-AND-FIGHT-SYSTEM.md §3): one warm key from behind or the side, never flat
  front light; light inside the paper is power; amber = human, crimson = demonic; dark soft background.
- **Low key** = key:fill ≥ 8:1 [C]; the reference look is ~70% of the frame in darkness, glow the brightest thing.
- **Silhouette:** no key on the subject, background ≥ 3 stops brighter, camera `elevation` ≤ 0, facing the light.
- **Rim:** the light source is behind the subject, so the camera faces toward it (dawn set: sun behind the fighters).
- **God rays** need haze plus an occluder (`light-shafts` cards are built; screen-space god rays are planned).
- Grades (`engine/fx.js` MOODS): `dawn`, `lantern` (warm resolve), `moonlit` (cold dread), `demonic`, `kurosawa`
  (mono memory), `ash` (aftermath). Cross-fade 24–48 frames, on a cut or a held moment.

---

## 7. Taste rules and review checklist
**The studio standard comes first:** `docs/STUDIO-STANDARD.md` (§3 has the beat → camera table: dash = side track with lead room or front-low pull-back, turn = behind then over the shoulder, jump = low looking up then circling above, slash = over the shoulder into the impact, landing = low wide; §3b the moves and their limits; §4 speed ramps). On the motion page use the `compose` framing solver (`docs/CAMERA.md` §8). Then measure your camera: `node tools/camera_check.mjs film/<name>.json` (every shot scored and rejected with a reason) and `node tools/audit.mjs film/<name>.json` (`docs/AUDIT.md`, which runs the same camera section).


### Cinematic vs amateur
| Cinematic | Amateur |
|---|---|
| Every shot has one subject and one job | The camera "shows everything" in a medium-wide for 10 s |
| Stillness, then one fast thing | Constant motion, constant handheld, constant shake |
| Shake only on hits, 1 frame of punch, decays in ~10 frames | Shake under every move; `handheld` on a standoff |
| The decisive blow is hidden (whip, hit-stop, impact frame) or frozen, then a long hold | The decisive blow shown at normal speed in a wide and immediately cut away |
| Close-ups are earned: the eye insert comes after a wide has set the space | Starting on a close-up of nothing, or only close-ups so nobody knows where anyone is |
| Lenses tell the emotion: 16–24 fov for pressure and faces, 34–42 for space | Every shot at the same fov and the same height |
| Low angle for power, high for defeat, eye level for equals | Camera always at chest height |
| One impact zoom, one impact frame, one Dutch per scene | Every effect on every hit |
| Silence before the cut is the loudest sound | Music wall to wall, whooshes on every frame |
| The far fighter ≥ 45% of frame height in a 9:16 two-shot | Two 17%-tall figures in a vertical frame |

### Common mistakes (each seen in this repo's history or tests)
- A vertical two-shot at `dist` 1 → tiny fighters (use the library's 9:16 `rig`).
- Single-subject angle 0 → the opponent blocks the lens.
- Orbit degrees copied from another film with different staging → the camera ends up on the wrong side.
- Two shots in a row on the same subject at 15° apart → a jump cut.
- A crane rig in a 1 s shot → it never arrives.
- Default behaviours on a composed shot → it drifts and Dutch-rolls on a stagger you did not want.
- Effects that are `planned` in `library/effects.json` written into a film as if they render (check status).

### Review checklist (answer every line yes before rendering)
- [ ] Each shot in the list has a feel-or-know purpose; nothing is filler.
- [ ] Frame 1 of the Short is lit and readable; the hook image lands by 1 s.
- [ ] The line is established by the first two-shot; every shot stays on that side or crosses on purpose.
- [ ] No two consecutive shots of the same subject within 30° / one size step.
- [ ] Cuts inside action are on action; scene changes are match cuts, whips, wipes or J/L cuts.
- [ ] Rhythm varies; the standoff accelerates; there is a silence before the decisive cut and a hold after it.
- [ ] Every hit has a `shakes` entry and sound; the decisive one has `events.impact` and the longest hit-stop.
- [ ] In 9:16: far fighter ≥ 45% of frame height in two-shots; faces and eyes in the upper-middle; nothing important
      in the bottom 35% or the right 18% (Shorts UI) and the top 15% (§8).
- [ ] One lighting mood per scene; amber/crimson rule kept; no blood.
- [ ] Each effect used is `built` or `new` in `library/effects.json` (or the gap is reported to the owner).
- [ ] The stills were looked at, every one.

---

## 8. Shorts (vertical) rules

- **Format:** 1080×1920 (we render 720×1280), 9:16, `"format": "vertical"` [C].
- **Safe zone:** platform UI covers roughly the bottom 20–35% (title, channel, subscribe) and the right ~11–18%
  (like / comment / share). Conservative margins: top 288 px, bottom 672 px, left 48 px, right 192 px of 1920×1080
  [C, third-party guides disagree]. In our 720×1280 render: top 192, bottom 448, left 32, right 128. Keep eyes,
  blades at contact, titles and subtitles inside.
- **Hook:** viewers decide in about the first second [C]; start mid-action or on the eye; text readable on frame 1.
- **Subject size:** a phone is small. Faces ≥ 1/3 of frame width in close-ups; the far fighter ≥ 45% of frame height
  in two-shots [D docs/FIX-LIST.md].
- **Composition:** use the vertical: low angles that let the figure tower, cranes, sky tilts, depth staging; avoid
  wide side-by-side profiles except as one held graphic beat.
- **Letterbox strip inside 9:16** (reference look): fx `letterbox` (new, `engine/fx.js`); `main.js` drops the film
  `letterbox` in vertical, so use the fx version.
- **Loop:** the last frame may rhyme with the first (end card → paper sea) [C].

---

## 9. When something is missing
- A shot you need is not in the library: build it from the rig fields (`docs/CAMERA.md` §7), test it with stills,
  then add it to `library/shots.json` with purpose, when, emotion, numbers and `engine` status.
- A move the engine cannot do (rack focus, whip blur, foreground wipe, speed ramp): use the library's `approx`
  version and tell the owner the gap (`docs/FIX-LIST.md` camera pack, `library/effects.json` planned items).
- Never edit `engine/` code from this skill without the owner's request; directing is data.
