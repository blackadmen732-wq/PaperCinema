# Asset library: where every model, texture, motion, effect and sound comes from (checked 27 Nov 2026)

Rule: **the picture is built by our systems from data; outside assets are raw material.** A set is
`library/sets/<name>.json` over the kit (`blender/sets/kit.py`, 28 procedural pieces) with photo detail from CC0
textures; a character is the modular paper rig (`blender/character/modular_builder.py`); motion goes through
`tools/mocap.py` → the production bake. Anything downloaded is converted to our paper look (`paper_materials.py`) and
credited in `assets/*/CREDITS.md`.

Licence key: **CC0** = anything, no credit · **CC BY** = commercial OK, credit the author · **RF** = royalty-free use in
our videos, never resell/redistribute the raw files · **NC** = non-commercial: NOT for posted videos.
"Reach" = can this cloud container download it today (tested 27 Nov): ✅ yes · ⛔ blocked by the environment's network
list (a free settings change) · 👤 needs Mark's own login, download by hand.

## 1. Models (props, plants, rocks, buildings)

| Source | Licence | Reach | Use it for | Notes |
|---|---|---|---|---|
| [Poly Haven models](https://polyhaven.com/models) | CC0 | ✅ API (`api.polyhaven.com`) | Props for every set: barrels, wooden buckets, wicker baskets, wooden lantern, stools, ladders, axes, ceramic pots, stumps, rocks, boulders, firs, ferns, grass, moss, pier, katana | 522 models. **No Japanese buildings**: those come from our kit. |
| [Quixel Megascans on Fab](https://www.fab.com/sellers/Quixel) | Fab Standard (commercial OK) | 👤 Epic account | Photo-scanned rocks, cliffs, ruins, ground, plants | Made **free again, permanently, Nov 2026** ([CG Channel](https://cgchannel.com/2026/11/epic-has-made-megascans-free-again-for-good-this-time)). No API: Mark claims/downloads, puts the files in `assets/megascans/`. |
| [Quaternius](https://quaternius.com) | CC0 (free packs) | ⛔ | Low-poly props, nature, animals, base characters + animations | Paid bundles exist; every model is free one by one on the site. |
| [KayKit](https://kaylousberg.itch.io) | CC0 (free tier) | ⛔ | Modular dungeon/medieval/furniture bits | Paid tiers add source files only. |
| [Kenney](https://kenney.nl/assets) | CC0 | ⛔ | Modular kits (city, nature, furniture), UI, audio | |
| [Smithsonian 3D](https://3d.si.edu/collections/openaccesshighlights) | CC0 (open access items) | ⛔ | Real historical objects: armour, ceramics, tools | Check each item says CC0. |
| [Sketchfab](https://sketchfab.com/licenses) | per model: CC0 / CC BY / NC | 👤 login required by the download API | One-off hero props (a specific shrine bell, a boat) | Filter by licence; skip NC and "NoAI"; CC BY = add to CREDITS. |
| [BlenderKit](https://www.blenderkit.com) | RF or CC0 per asset | 👤 Blender add-on login | Interiors, furniture, materials | RF: fine in renders, never ship the files in the repo (public!). |
| [3D Valley](https://3dvalley.com/library) · [3D Asset Server](https://3d.shep.bot/search) | mixed (mostly CC0) | ⛔ | Search across libraries | Search tools, not sources: check the original licence. |
| [CGTrader free](https://www.cgtrader.com/free-3d-models) · [TurboSquid free](https://www.turbosquid.com/Search/3D-Models/free) | RF, per seller | 👤 | Last resort for a specific object | Many NC/editorial-only; read every licence. |
| [NASA 3D](https://science.nasa.gov/3d-resources/) | public domain (mostly) | ⛔ | Space only | Not needed for samurai films. |

## 2. Textures, materials, skies

| Source | Licence | Reach | Use it for |
|---|---|---|---|
| [Poly Haven textures](https://polyhaven.com/textures) | CC0 | ✅ | 873 sets. Village: `thatch_roof_angled`, `reed_roof_03/04`, `clay_plaster`, `japanese_stone_wall`, `bamboo_wall(_02/_03)`, `wood_planks(_dirt/_grey)`, `brown_mud*`, `cobblestone_*`, `tatami_mat`, `clay_roof_tiles*`, bark. 21 already in `assets/polyhaven/` |
| [Poly Haven HDRIs](https://polyhaven.com/hdris) | CC0 | ✅ | 999 skies: dawn, dusk, overcast, night (the light of every set) |
| [ambientCG](https://ambientcg.com) | CC0 | ⛔ ([API docs](https://docs.ambientcg.com/api)) | 2,000+ materials incl. paper, cardboard, fabric, ground |
| [ShareTextures](https://www.sharetextures.com) · [TextureCan](https://www.texturecan.com) | CC0 | ⛔ | Extra surfaces when the two above lack one |

## 3. Motion (for the paper rig, through `tools/mocap.py`)

| Source | Licence | Reach | Use it for | Notes |
|---|---|---|---|---|
| [Mixamo](https://www.mixamo.com) | RF (free with Adobe ID) | 👤 | Walks, runs, sword idles, reactions | Commercial videos OK; no raw-file redistribution; no ML training ([Adobe FAQ](https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html)). Needs a Mixamo→our-25-bone map (not built yet). |
| [CMU mocap](https://mocap.cs.cmu.edu) | free; sources disagree on commercial terms | ⛔ | Already imported by `tools/mocap_cmu.py` | Re-read CMU's own terms before a posted film uses a clip. |
| [Rokoko Vision](https://www.rokoko.com/products/vision) (video → motion) | free Starter: FBX, ~15–30 s/month; BVH only paid ($20/m) | 👤 | Mark films a move on a phone → a clip | The real-export fixture the BVH adapter is still waiting for. |
| [Rokoko free motion library](https://www.rokoko.com) | free moves, commercial OK (2020 terms) | 👤 | Extra combat moves | Confirm current terms. |
| Bandai Namco Research motion dataset | **NC** | — | Study only | Never in a posted video. |

## 4. Effects (2D and 3D)

| Source | Licence | Reach | Use it for |
|---|---|---|---|
| Our own: `tools/post_fx.py`, `engine/fx.js`, `blender/world/slash_fx.py`, `blender/bench/paper_fire_preview.py`, kit `particles`/`fog`/`rain` | ours | ✅ | Ink frame, flash, speed lines, slash, paper fire, embers, petals, fog, rain |
| [Unity Labs flipbooks](https://unity.com/blog/engine-platform/free-vfx-image-sequences-flipbooks) | CC0 | ⛔ | Smoke, explosions, fire as image sequences → cards in Blender |
| [ProductionCrate](https://www.productioncrate.com) | free tier, licence per plan | 👤 | 2D hits, dust, sparks | Read the free-tier licence. |
| [VFX Parlor](https://vfxparlor.com) | per pack | 👤 | Anime 2D effects | Per-pack licence. |

## 5. Sound (through `engine/sound.mjs` and `tools/bake_events.py`)

| Source | Licence | Reach | Use it for | Notes |
|---|---|---|---|---|
| [Sonniss GDC bundles](https://sonniss.com/gameaudiogdc) | RF, commercial, no credit | 👤 big zips (Mark downloads) | Sword swings, clashes, cloth, wind, ambience | Years 2015–2026, ~200 GB total. Read the [licence](https://sonniss.com/gdc-bundle-license) (reported: no AI training). |
| [Kenney audio](https://kenney.nl/assets/category:Audio) | CC0 | ⛔ | Footsteps, impacts, UI | |
| [Freesound](https://freesound.org) | per sound: CC0 / CC BY / NC | 👤 | Paper tear, fold, crumple, burn; foley | Use CC0/CC BY sounds by hand; the **API** is non-commercial only ([terms](https://freesound.org/docs/api/terms_of_use.html)). |
| [Pixabay sound effects](https://pixabay.com/sound-effects/) | Pixabay content licence (not re-checked) | 👤 | General | Read the licence before use. |
| [Mixkit](https://mixkit.co/free-sound-effects/) · [Zapsplat](https://www.zapsplat.com) | own free licences (not re-checked) | 👤 | Whooshes, transitions, foley | Read each licence; Zapsplat's free tier asks for credit. |
| [OpenGameArt](https://opengameart.org) · [3D Valley audio](https://3dvalley.com/sound-effects) | per item | ⛔ | Extra | |
| Our own: `assets/sfx/` (37 files + `earshot/`), synthesised layers in `tools/bake_events.py` | ours / credited | ✅ | Draw scrape, apex whoosh, contact transient, material tail | |

## 6. AI 3D generation (characters only as rigid PARTS)

| Tool | Cost | Licence of output | Verdict |
|---|---|---|---|
| **Tripo API** (`tools/tripo.py`, key saved on the environment) | concept image 5 credits, image-to-3D 30 credits (v3.0); 1,000 free credits, then $1 = 100 credits | commercial use with an API key | **Used**: Kojiro's head, 35 credits, `docs/AI-PARTS.md` |
| TRELLIS on our RunPod (`gpu/gen_trellis.py`) | ~$0.34/h (RTX 4090 community) | MIT model, outputs ours | **Use** for helmets, hats, armour plates, masks, sword fittings: rigid pieces on sockets. |
| [Meshy](https://www.meshy.ai/pricing) | free 100 credits/m; Pro $20/m | free = CC BY 4.0 | Only if TRELLIS fails on a part. |
| [Tripo](https://www.tripo3d.ai/pricing) | free 200 credits/m; Pro $20/m | free = **non-commercial** | Free tier unusable for posted films. |
| Whole AI character meshes | — | — | **Don't**: a fused mesh cannot bend at the elbow (why `film_blender.py` + TRELLIS was replaced by the modular rig). |

## 7. How a set gets built from these (the old-village example)

1. **Pieces from our kit** (code once, data forever): minka farmhouse (posts, beams, engawa, thatched hip roof),
   machiya row house, kura storehouse (plaster + tiled roof: exists), well, bamboo/wood fence, market stall, cart;
   reuse `roof`, `plaster_wall`, `shoji`, `floor_planks`, `paving`, `pine`, `cherry`, `bamboo_grove`, `rocks`,
   `fog`, `particles`, `light`, `layers`.
2. **Photo detail on them**: Poly Haven thatch, clay plaster, stone wall, planks, mud through the existing
   `ph=role` layer of `paper_materials.py` (`library/polyhaven.json` lists roles → texture ids).
3. **Props scattered by data**: Poly Haven barrels, buckets, baskets, lantern, ladders, stools, stumps, rocks, grass,
   downloaded once into `assets/polyhaven/models/`, re-materialed in the paper family.
4. **A `village` layout piece**: a street spline + seeded lots → houses, fences, props, trees along it; a cleared
   `marks` area for the action.
5. **Light**: a Poly Haven HDRI per mood (dawn / overcast / night) + kit lights.
6. **Check**: build → reopen the `.blend` → a still per preset camera; actors stand on the ground (foot IK, below).
Cost: $0. Time: about one session.
