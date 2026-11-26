# Camera grammar — words in, KUROKO rigs out

This is the layer between "shoot it like a Leone standoff" and a rig in `library/shots.json`. It
exists because the hard part is not having camera moves — there are **54** in that file, each with a
purpose, a duration, an emotion and a measured subject height — it is **choosing** one and getting
its numbers right.

**It does not add a camera system.** KUROKO is the camera director (`engine/kuroko.js`,
`docs/CAMERA.md`). Everything below resolves to a rig type and a feel KUROKO already has.

## The vocabulary KUROKO actually has

| rig | what it does |
|---|---|
| `frame` | one or two subjects, by `size` / `angle` / `elevation` / `dist` / `fov` |
| `orbit` | arc around a target; degrees are **world azimuth** |
| `track` | rides a moving subject by `offset` + `lookAhead` |
| `face` | close on a face |
| `anchor` | a list of beats the spring carries through — **one continuous take** |
| `blade` | rides the drawn sword |

| feel | spring | reads as |
|---|---|---|
| `locked` | 6 Hz, damping 1.0 | tripod, mechanical, no overshoot |
| `dolly` | 1.8 Hz, 1.0 | smooth track, slight lag |
| `crane` | 0.7 Hz, 1.1, tiny drift | heavy, graceful |
| `handheld` | 2.5 Hz, 0.7, ~5% overshoot | nervous, carried |
| `torpedo` | 4 Hz, 0.62, ~8% overshoot | fast attack, speed buzz |

A support style is a **feel**, not a rig. Steadicam ≈ `dolly`, shoulder ≈ `handheld`, jib ≈ `crane`,
tripod = `locked`. Do not add rigs for them.

## Words → move, with the numbers

Numbers that are not guesses, cross-checked against a working AI cinematographer (`vendor/anyshot`,
MIT, `agent/SHOTS.md`):

| they say | rig | numbers |
|---|---|---|
| push in / dolly in / pull back | `frame` with changing `dist`, or `anchor` 2 beats | "slow" = **0.2–0.4 m/s** |
| truck / crab / slide | `anchor`, two `frame` beats, angle sweeping, **aim parallel** | `crab-slide` |
| crane / jib / rise | `anchor`, elevation and height both moving | `crane-reveal`, `crane-out-end` |
| **pedestal** | `anchor`, height moves, **angle identical** | `pedestal-rise` — not a crane: no re-aim, the horizon drops |
| pan / tilt | `anchor`, position identical, aim moves | `slow-pan-reveal`; the fast one is `whip-reveal` |
| orbit / arc / circle | `orbit` with `deg0`→`deg1` | **10–20 °/s** deliberate, **>40 °/s** action |
| rack / pull focus | `focus_m` + `aperture` on the timeline | f/1.4–2.8 or it does not read |
| walkthrough / Steadicam | `track` or `anchor` | **0.4–0.6 m/s**, eye height **1.5–1.7 m**, feel `handheld` |
| POV | `track` on `<id>.head` | `pov-blade`; wide lens, 52° fov |
| vertigo / dolly zoom | `dist` and `fov` opposed in one `anchor` | — |
| locked off | `frame`, feel `locked` | — |
| lens words | `fov` | wide **18–24 mm**, normal **35–50 mm**, tight **85–135 mm** |

A duration stated in words beats any default.

## The three rules that break a scene, not a shot

1. **The 180° line.** Draw a line through the two fighters. Every camera stays on one side of it for
   an exchange. Cross it and the attacker appears to switch hands. In an `orbit`, keep `deg0` and
   `deg1` both inside `(-180, 0)` or both inside `(0, 180)`. `tools/audit.mjs` scores this.
   `pov-blade` breaks it by definition — cut out of it to the side the fighter was facing.
2. **Cut on action.** Cut while something is moving, on the same gesture, not between beats.
   `cut-on-action` is in the library for this.
3. **Eyeline.** Whoever looks left in one shot looks left in the next. A reversal reads as two people
   looking the same way.

## Shooting by scene type

The project is a duel, so combat is in full and the rest is what changes.

**Combat** — establish the geography once (`establishing-wide`), then stay inside it. Track footwork
low (`foot-grind`), show the weapon path square to the arc so it reads as an arc and not a line, and
**put the camera where the contact will be before it happens** — a camera that arrives after the hit
has missed it. Beat by beat: wind-up wants a slow push, the slash wants `blade` or a whip pan, the
hit-stop wants `locked` (a moving camera during a freeze reads as a bug), the reaction wants a
face-snap. Shots: `lunge-dolly`, `torpedo-track`, `handheld-clash`, `impact-close`, `ramp-hold`.

| scene | what changes |
|---|---|
| **dialogue** | master → two-shot → over-shoulder → reaction. The reaction is the shot, not the line |
| **chase** | forward and reverse tracking, one wide for geography every few cuts or the audience loses where |
| **horror** | lock the camera off and let the frame hide things. Movement spends the tension |
| **emotional** | slow push, negative space, restraint. The camera stops moving when it matters most |
| **establishing** | wide, aerial, crane; parallax is what sells scale, so something must be near |
| **montage** | repeated compositions, match cuts (`kon-match-cut`), rhythm over continuity |

## Before you render

Block every shot first and **look at it** — cheap frames at start, middle and end. The same tool
AnyShot uses, for the same reason: a camera fault is invisible in a plan and obvious in a frame.

```bash
bash tools/shotsheet.sh film/<name>.json --set <set>
blender -b -P blender/check_sight.py -- --film <name> --set output/sets/<set>.blend
node tools/camera_check.mjs film/<name>.json
```

Clearance means **solid** things. A real camera moves through dust, haze, light shafts and particles;
`check_sight` walks through anything that does not render, which is why it went from 73 false
warnings to 10 real ones.

## Grade in ffmpeg, not in the compositor

For the final grade (bloom and vignette stay in Blender via `post()`): lift blacks to about 0.03 with
teal shadows and warm highlights, `hue=s=0.88`, a slight `rgbashift`, a soft vignette, and a little
temporal noise for video. One grade across every shot of a film. Check the output frame count matches
the folder — a gap gives a short clip silently.

## Sources

`vendor/anyshot` (MIT) — a Claude agent directing Blender; its `agent/SHOTS.md` is the closest prior
art to KUROKO and the source of the speed and lens numbers above. `docs/WATCH-LIST.md` for the film
grammar. CineTechBench is **CC BY-NC-ND** — readable as research, never bundled or adapted here.
