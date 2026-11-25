# The look target — measured, not described

Mark supplied two concept boards for Paper Cinema on 25 Nov (`research/look-board-worlds.webp`,
`research/look-board-character.webp`). They are AI-generated concept art, so they are a
**destination and an art direction**, not a render anyone can match pixel for pixel. What makes them
useful is that the direction in them is measurable, and measuring it says exactly the same thing
three independent sources said the same day (`docs/WHY-IT-LOOKS-FLAT.md`).

## The one number that matters

Luma percentiles, 0–255, measured with PIL over the whole frame:

| image | 1% | 5% | median | 95% | 99% | 5→95 range |
|---|---|---|---|---|---|---|
| **target board, character** | **2** | 5 | **49** | 199 | 238 | 194 |
| **target board, worlds** | **6** | 14 | **55** | 215 | 245 | 201 |
| our film frame (bamboo set) | 38 | 46 | 83 | 198 | 208 | 152 |
| our character on studio grey | **147** | 187 | **188** | 214 | 220 | **27** |

Read the median column. **The target is a dark image with bright accents: half of every frame is
below 50.** Our film frame's median is 83 and its darkest 1% never goes below 38 — there is no black
in it anywhere. The studio character still has a 5→95 range of **27 levels out of 255**: it is, in
the literal sense, a flat grey card.

This is the same finding as the r/blender diagnosis ("it's all almost equally bright") and Fable
5.2's ("the hero is a pale cream shape against pale mist at the same value"), now with a number on
it. **Target for any finished frame: 1% below 10, median near 50, 95% above 195.**

## What else is extractable from the boards

Things that are art direction, that we can act on:

1. **The character owns the frame.** On both boards the figure is 60–80% of frame height. Ours is
   22% (`f0017`, 140 px of a 640 px frame).
2. **Warm practicals are in shot and they motivate the light.** Stone lanterns, paper lanterns,
   windows — visible, warm, blooming. They are *why* the key is warm. Our films light from nowhere.
3. **Light lives in cavities, not on sheets.** The paper reads cool and shaded; warm light appears
   at sleeve mouths, under the hat, in the eye slits. This is exactly Fable 5.2's note that
   `paper_material()` emits from the whole sheet and should emit from inside faces only.
4. **The hat is pitched forward** over the face, so the face sits in shadow and the eye glow is the
   brightest thing on the figure. Ours is level, which reads as a parasol.
5. **Folds are large, diagonal and asymmetric** — a few big planes per limb, not stacked
   rectangles.
6. **Red is the only saturated colour**, and only on the obi, cords and sash. Everything else is
   paper, charcoal and warm light.

Things that are scope, not direction, and should not be mistaken for a shot list: six worlds
(Feudal Japan, Snow, Forest, Desert, Fantasy, Space), an Unreal Engine integration, real-time
streaming. Those are decisions for later and none of them change how a frame looks.

## The boards specify the variant system we do not have yet

Board 2's own recipe example:

```json
{ "id": "ronin_007", "rig": "PC_HUMANOID_V1",
  "parts": { "hat": "kasa_wide_03", "face": "mask_angular_04",
             "torso": "kimono_layered_02", "sleeves": "sleeve_wide_05",
             "legs": "hakama_pleated_03" },
  "material": "PC_Washi_Ivory", "style": "elegant" }
```

That is `library/character-recipes/*.json` almost exactly — **with numbered variants per part.**
`kasa_wide_03` is `kasa_wide` at one set of parameters, saved under a name. We have the parameters
(`radius`, `rise`, `ribs`, `spread`, `reach`, `cuff`, `pleats`, a scale range and three proportion
presets per part); what we have no way to do is explore that space, look at it, or keep a good one.

Board 2's materials — Washi, Craft, Embroidered, Painted, Metallic, Weathered — are a *family* with
a colour input, not our seven fixed JSON files.

And board 2's top-left panel, parts laid out in a grid by slot, is a picture of the contact sheet
the variant explorer should print.
