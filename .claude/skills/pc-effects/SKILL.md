---
name: pc-effects
description: The look of Paper Cinema - the paper slash, light, compositing, paper damage and ground reaction, and the measured reason frames come out flat. Use for anything about how a finished frame looks rather than how it moves.
---

# The look

## The target is a NUMBER, not an adjective

Luma percentiles over the whole frame, measured against the owner's own concept boards:

| | 1% | median | 95% |
|---|---|---|---|
| **target** | **2–6** | **~50** | ~200 |
| a grey-void render | 38 | 83 | 198 |
| a character on studio grey | **147** | 188 | 214 |

**The target is a dark image with bright accents — half of every frame below 50.** A 5→95 range of 27
levels out of 255 is a flat grey card, in the literal sense. Full working: `docs/LOOK-TARGET.md`.

Also extractable from the boards: the figure owns **60–80% of frame height** (ours was 22%); warm
practicals are **in shot** and motivate the key; light lives **in cavities** (sleeve mouths, under the
hat, eye slits), not on whole sheets; the hat is **pitched forward** so the face is in shadow and the
eye glow is the brightest thing; red is the **only** saturated colour.

## Light

```python
MB.studio(scene, 'cinematic')   # the Lantern Origami key: dark, paper glowing from inside
MB.studio(scene, 'neutral')     # the flat studio the MODELS are audited under - never for a film
```

Films defaulted to `neutral` for weeks. An audit wants light that hides nothing; a film wants the
opposite. Fixing that one word moved the darkest 1% of frame from 147 to 5.

**Inside a set, the set lights it.** `studio()` replaces `scene.world` and adds three area lamps, so
calling it after loading a set throws away the sky and mist and stands a lamp in shot (a blown white
rectangle, in a finished frame). Studio lamps are now `visible_camera = False`.

But the set's sun alone leaves the cast dull, because the grove is lit for the grove. Every set file
carries `lighting.fighter` — key, fill, rim as offsets — written for exactly this. Attach it with a
**Copy Location constraint, not parenting**: parenting carries rotation, so a performer who turns
swings their own key light round behind them. That is a flashlight, not a sun.

## Compositing — half the image, and it was unwired

`post(scene, bloom, vignette)` in `blender/sets/build_set.py` has built bloom and a vignette since
the sets existed. `film_modular.py` called it **zero** times. Bloom is what makes the inner lantern
read as *light* rather than a patch of pale paint. Values come from the set's own `lighting` block.

Blender Studio's own NPR short (`docs/WHY-IT-LOOKS-FLAT.md`) adds the rest of the list, in order of
leverage: character shading **decoupled** from the environment with per-shot highlight and shadow
colour; *"almost always some kind of rim light to lift them off the backgrounds"*; shadows simplified
to **one caster**; a **depth colour gradient** in comp for separation. They ran **12 iterations** on the
one shot they broke down.

## The paper slash

Six layers on one frame. Four exist:

| layer | |
|---|---|
| blade arc | ✓ sampled at 240 Hz, sub-frame, in the timeline |
| **paper ribbon trail** | ✗ **the gap** |
| ink accent | ✓ `ink-impact` |
| contact flash | ✓ `flash`, `ca-flash`, `glint` |
| **torn paper fragments** | ✗ |
| surface damage | ✓ SHIMI, KIZU |

The two missing are the two that make it **paper** instead of generic anime, and both are mesh work.

`blender/slash_from_blade.py` drives `slash_fx.make_slash()` from the blade's real path: centre from
the mean guard position, radius from guard-to-tip reach, **plane fitted** from the tip's path, signed
sweep, and the frames where the tip was over 5 m/s. A kesa-giri comes out diagonal because the cut
*was* diagonal. **A slash that is a measurement of the swing cannot disagree with the swing.**

For the ribbon: no clearly-licensed tool exists (four Blender trail add-ons found, none with a usable
licence) — read the method, write it here. The hard half is done: the blade is already in the
timeline at 240 Hz, so the ribbon is geometry nodes over existing data. Sample the two tip positions
over the last N frames, skin a ribbon, taper the width, tear and fade the trailing edge. **Not a neon
streak** — a thin strip of washi with thickness, lit by the scene.

## Damage and ground

`tools/paper_damage.mjs` turns every contact into a SHIMI/KIZU wound contract — but its geometry step
is a **stub** by its own comment: the cut polyline is planned from the blade sweep, not measured on
the mesh. `engine/groundfx.js` does land/skid marks and dust; torn-paper shards are not there.

Damage must **persist across cuts**. If the camera cuts away and back, the broken ground is still broken.

## Can the audience see it?

```bash
blender -b -P blender/check_sight.py -- --film <f> --set output/sets/<s>.blend
```

Blocked by the set, off-frame, or too small to read. **CRITICAL on a contact frame** — the shot exists
for that frame. Make the ray walk *through* anything that does not render, or it reports a dust
emitter as an obstruction and stops being read.
