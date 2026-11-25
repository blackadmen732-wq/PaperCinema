# Phase 1 (paper material engine): already built, and the test it fails is a different one

The master specification's Phase 1 asks for a paper material engine with ten controls, and sets this
completion test: *"one object looks convincingly handcrafted from paper from every important camera
angle."*

## The engine exists

`blender/world/paper_materials.py` is 1,059 lines and `library/paper-materials/` holds seven sheets.
Every control the specification lists is already there:

| Specification | Ours |
|---|---|
| Paper Type | `paper_type` |
| Base Color | `color` |
| Fiber Scale | `fibre_density` |
| Fiber Direction | `fibre_direction` (lengthwise / vertical / crosswise / radial) |
| Roughness | `roughness` |
| Thickness | `thickness_mm` |
| Fold Strength | `fold_darkening` (driven by real geometry pointiness, not a texture) |
| Edge Wear | `edge_wear` |
| Stain Amount | `shimi` |
| Translucency | `translucency` + `translucent_color` + `inner_light` |

So Phase 1 does not need building. It needs **testing**, which is what the rest of this file is.

## Running the completion test

    B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
    $B -b -t 4 -P blender/character/modular_builder.py -- \
      --recipe library/character-recipes/ronin-reference.json \
      --turnaround output/engine-ab/turn/ronin.png --res 360x640 --samples 20

Four views: front, three-quarter, side, back. 23 seconds.

## The verdict: it passes from the front and fails from behind

| View | Verdict |
|---|---|
| front | **passes.** Layered kimono, crossed collar, proud obi, two-tier sleeves, knife-pleated hakama. |
| three-quarter | **passes.** |
| side | **fails.** The hakama reads as a smooth curved skirt; the pleats disappear. |
| back | **fails.** A flat slab from shoulders to waist, and the legs read as two plain tubes. |

**Why this matters more than it sounds.** The camera measurement in `docs/REQUIREMENTS.md` found that
`orbit` is the most-used rig in the whole project at 71.4 screen-seconds. The camera spends most of
its life *circling* the character, so the two angles that fail are the two it looks at most.

## The specific cause

`hakama_apron` does build a back panel and the stiff koshiita board — those are not missing.
What is missing is that **the knife pleats are front-only**: `hakama_pleated` and
`hakama_shin_pleated` cut three pleats per leg on the front with a widening front split, and leave
the back faces plain. A real hakama is pleated front *and* back (traditionally five and two).

That is why the side view loses its folds: from 90 degrees you are looking at the unpleated side of
a front-only pleat.

## What to do, in order

1. **Pleat the back of the hakama.** The cheapest fix with the largest effect, because it repairs
   both failing views at once.
2. **Give the kimono a back seam and a shoulder yoke**, so the torso is not one slab from behind.
3. **Four more sheets**: the specification names kraft, painted, embossed and weathered, and we have
   only washi and card. Sheets are JSON, so this is data, not code.
4. **Re-run the turnaround** after each, because the test is 23 seconds and the eye is unreliable.

## A bug this test found

`turnaround()` built each view's filename with `out.replace('.png', …)`. A path without `.png` had
nothing to replace, so all four views wrote to the same file and three renders were silently lost.
It now builds the name instead of patching it.
