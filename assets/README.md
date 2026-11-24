# 3D character assets

The production cast lives in [character recipes](../library/character-recipes/). Blender films and sets resolve
the cast through [the character catalog](../library/character-models.json). Each recipe builds a rigged
character with independent arms and legs and assigns paper materials separately from the geometry.

The seven GLBs in `models/` are the original Microsoft TRELLIS references. Their generated paint and
reconstructed silhouettes are useful for comparing against the modular rebuilds.

| Original GLB | Production replacement | What to check |
|---|---|---|
| `ronin_base.glb` | `ronin-reference` | Folded sleeves and collar, narrow amber eye openings, separate legs |
| `origami_samurai_s7.glb` | `ronin-reference` | This source is another seed of the same design |
| `origami_samurai_s21.glb` | `ronin-reference` | This source is another seed of the same design |
| `samurai_front.glb` | `front-samurai` | Indigo cloth, uncovered head, shorter cuffs |
| `gold_armor.glb` | `gold-armour` | Ochre card scales and no background paint geometry |
| `kimono_swordswoman.glb` | `kimono-swordswoman` | Teal and vermilion paper, hair ribbons and no sun disc |
| `kasa_hat.glb` | `kasa_wide` | Radial ribs, folded rim, suspended headband and stand-alone export |

Use the [character guide](../docs/CHARACTER-FACTORY.md) to render, pose or export the replacements.
The sculpting comparisons are under `previews/`. The original TRELLIS-generation scripts are in `gpu/`.
