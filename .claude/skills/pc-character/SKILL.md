---
name: pc-character
description: Build, judge and extend the folded-paper character - which of the four character systems is THE one, how parts and recipes work, how to bring in bought or AI-generated geometry, and why the paper reads as plastic. Use for anything about how the cast is made or how it looks.
---

# The paper character

## Four things can stand in for a person. One is the character.

| | use it for |
|---|---|
| **`blender/character/modular_builder.py` + `part_registry.py`** | **everything.** ~100 folded parts on sockets, 25-bone rig, 433-check validator |
| `engine/figure.js` | blocking and timing only. A storyboard. `node engine/render.mjs` |
| `blender/character/origami_samurai.py` | nothing. "crude boxes and frustums… the weakest element in every still" |
| `blender/character/rig_trellis.py` | nothing, for a character. One fused shell: heat drapes it, panels tears it, rigid holes it |

**Never propose a hybrid** (one system for wides, another for close-ups). Two silhouettes in one cut
reads instantly, and a wide is exactly where flat folded facets hold their shape. Full reasoning:
`docs/CHARACTER-BLENDER.md`.

## Parts are functions, not models

```python
@part('kasa_wide', slot='hat', socket='head_top', bone='head',
      size=(0.85, 1.15), material='washi_hat', radius=0.52, rise=0.34, ribs=20,
      proportions=('slim','standard','broad'))
```

A recipe supplies the arguments:

```json
{ "part": "kasa_wide", "scale": 1.0, "params": { "radius": 0.45, "ribs": 24 } }
```

So `kasa_wide` is not a hat — it is every hat across its parameter ranges × 7 papers × 3 proportions.
**32 parts across 16 slots** is a library of thousands. A whole new character is a recipe `extends`
plus a `swap` list; `armoured-warrior.json` is 40 lines and changes nothing in `blender/`.

```bash
blender -b -P blender/character/modular_builder.py -- --recipe library/character-recipes/<r>.json --still out.png
nice -n 10 blender -b -t 2 -P blender/character/part_validator.py -- --recipe <r> --report out.json
```

The validator must exit 0. It checks material, socket, scale, pivot, self-intersection, **joint gaps
across a pose sweep**, and silhouette. A part is not in the library until it passes.

## Bringing in bought or generated geometry

```python
reg.asset_part('kasa_bought', slot='hat', socket='head_top', bone='head',
               file='assets/models/kasa_hat.glb', height=0.22, material='washi_hat')
```

`asset_bmesh()` imports GLB/glTF/FBX/OBJ, joins, **decimates hard** (planar dissolve, then collapse to
~900 faces — measured 60,042 → 917), normalises to the socket, and hands it to the same `ctx.add()`
every folded part uses. **A bought mesh becomes paper on the way in.**

Buy what does not fold: hats, masks, helmets, plates, weapons, props. Fold cloth here. Never buy the
skeleton. Generating a whole character then **segmenting** it beats 16 separate generations, which
give 16 different characters. Services and licences: `.claude/skills/buy-the-geometry/SKILL.md`.

## Why the paper reads as plastic

Measured at 85 mm on the collar (`output/character/paper-closeup.png`): the geometry says paper, the
surface says plastic. The fibre field runs (`TexNoise`, object space, works in EEVEE) but is set to a
10% tone swing and a 0.12 bump — invisible.

**Do not tune the noise.** ×4 and ×8 give stucco; rebalancing pulp against fibre gives stucco too.
Both were tried and reverted. `PC_PAPER_FIBRE` scales both dials for a test render.

The answer is a **scanned sheet of real washi** through `_ph_triplanar()` — which this file already
has, uses for the world's wood and bamboo, and has never used for the character. One scan at the
right physical scale beats any noise tuning. Scale is the classic failure: *"fibres like rope on the
hat, invisible on the sleeves."* `WASHI_FIBRE = 150` repeats per **world** metre on every part.

And washi reads as paper because light comes **through** it. `translucency` is already 0.32 with a warm
`translucent_color`; it needs a light behind the sheet to show.

## Traps that cost real time here

- **Pointiness is Cycles-only.** Fold darkening computed to nothing in every EEVEE film ever rendered.
  Now baked to a per-vertex attribute at build time (`add_fold_attribute`). Darkest 1% of frame: 147 → 5.
- **A childless bone needs `reg.TAIL`**, or it gets a stub tail pointing up and its skin weights go to
  the arm instead of its own cloth.
- **Inverse distance cannot express "sewn".** A kimono sleeve is sewn at the shoulder and hangs free
  below; by distance the shoulder wins everywhere and the bag swings over the head. That is what
  `skin='hang'` is for — and only for the WIDE sleeve: the tight one measured *worse* when hung.
