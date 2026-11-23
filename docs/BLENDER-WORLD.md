# Blender world set: Ganryūjima (build once, film inside)

A reusable 3D location for the realistic Blender renders, in the Lantern Origami style: every surface is faceted
washi paper or card (flat folded planes, fibre texture, light through the paper), lit by a physical dawn sky.
One script builds the whole set from a seed, saves a `.blend`, and can render preview stills from named camera
anchors. Films then open that `.blend` and place characters on the marks.

The set is a stylised small island, not a survey of the real Ganryūjima (our choice). For history, see `research/`.

## 1. Run it

Blender 4.5 LTS, headless, Cycles on CPU (EEVEE needs `libEGL`, which this container does not have).
On a shared machine, always use `nice` and 2 threads:

```bash
B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
# build the set only (about 3 s)
nice -n 15 $B -b -t 2 -P blender/world/build_world.py -- --out output/world/ganryujima.blend
# build + preview stills (one PNG per anchor: preview.png, preview-CAM_medium.png, ...)
nice -n 15 $B -b -t 2 -P blender/world/build_world.py -- --out output/world/ganryujima.blend \
    --preview output/world/preview.png --cams CAM_wide,CAM_medium,CAM_hero_ots,CAM_low_sea --exposure -2.3
# slash effects: test sheet (3 variants) + a 4-frame strip of the demonic slash
nice -n 15 $B -b -t 2 -P blender/world/slash_fx.py -- --test output/world/slash-test.png --strip output/world/slash-strip.png
# a slash placed inside the saved world, seen from CAM_medium
nice -n 15 $B -b -t 2 -P blender/world/slash_fx.py -- --in-world output/world/ganryujima.blend --test output/world/slash-world.png
```

Quick look before a real preview: `--res 216x384 --samples 8` (about 5–8 s per anchor).

### Options of `build_world.py`

| Option | Default | Meaning |
|---|---|---|
| `--out` | `output/world/ganryujima.blend` | Where the set is saved |
| `--preview` | (none) | Render stills to this path (first anchor), others get `-CAM_x` suffixes |
| `--cams` | `CAM_wide` | Comma list of camera anchors to render |
| `--seed` | `1` | Layout seed: rocks, pines, ridges, clouds, foam. Same seed = identical set (checked: same geometry hash) |
| `--res` | `540x960` | Preview size (vertical first) |
| `--samples` | `24` | Cycles samples, with OpenImageDenoise |
| `--exposure` | `-2.0` | AgX exposure. `-2.3` suits the dawn previews |
| `--sun-elev`, `--sun-az` | `4`, `-7` | Dawn sun, degrees. Azimuth 0 = +Y, positive toward +X. The mountains open a sea gap where the sun rises |
| `--fog` | off | Thin ground-fog volume (about 1.75× render time) |
| `--no-standins` | off | Leave out the two stand-in samurai |
| `--frame` | `1` | Frame to render; the sea is animated over frames 1–240 (24 fps) |

## 2. What is in the set

Units are metres, Z is up, sea level is z = 0. Everything is in named collections:

| Collection | Contents |
|---|---|
| `SKY` | Nishita sky (world, sun disc off), `SUN_dawn` sun lamp, `SKY_paper_sun`: a backlit cut-paper sun disc 3.2 km away |
| `SEA` | `SEA_ocean`: Ocean modifier (Generate, 8×8 tiles of 40 m, about 1.1 m facets, waves keyed over 240 frames, foam attribute) + Geometry Nodes per-facet random; `SEA_far`: faceted sheet to the horizon |
| `ISLAND` | `ISLAND_sand` (plateau, flat duel beach on −Y, shelf under water; wet/dry sand by height), `ISLAND_grass` tufts, `ISLAND_foam_0/1` torn-paper lace on the waterline |
| `ROCKS` | East-point outcrop, beach stones (kept off the duel ground), surf rocks |
| `PINES` | 9 kuromatsu: bent 5-sided trunks, crowns of stacked folded-paper cones (cloud-pruned pads), leaning toward the sea |
| `MOUNTAINS` | 5 cut-paper rings at 170 m (headlands), 380 m, 720 m, 1.25 km, 2.1 km; fractal straight-edged ridges with a fold crease; colour and haze deepen with distance |
| `CLOUDS` | 16 folded-paper clouds (faceted low-poly blobs), most near the sunrise, a few behind the island for reverse shots |
| `FOG` | `FOG_ground` volume box, only renders with `--fog` |
| `MARKS` | Fighter marks (see below) |
| `CAMERAS` | Camera anchors (see below) and `KUROKO`, the scene camera |
| `STANDINS` | Two faceted samurai (straw hat, layered kimono and sleeves, striped hakama, amber inner light) for scale. Delete or hide for a real film |

### Marks (empties; local +Y = the direction the fighter faces; z is the sand height)

| Mark | Where | Role |
|---|---|---|
| `MARK_hero` | (−1.8, −3.2) | Hero, facing +X |
| `MARK_foe` | (1.8, −3.2) | Foe, facing −X (3.6 m apart: one step plus a cut) |
| `MARK_center` | (0, −3.2) | Midpoint of the duel line; the 180° line is the X axis |
| `MARK_boat` | (−9, −14) | A boat lands here, in the shallows |
| `MARK_shore` | (6, −9) | Waterline walk-on point |

### Camera anchors (empties pointing down their −Z like a camera; properties `lens_mm`, `look_at`, `note`)

| Anchor | Lens | Shot |
|---|---|---|
| `CAM_wide` | 24 | Establishing: sea, beach, fighters, pines, mountains, the paper sun |
| `CAM_medium` | 28 | Both fighters full body |
| `CAM_hero_ots` / `CAM_foe_ots` | 50 | Over one shoulder onto the other fighter |
| `CAM_low_sea` | 28 | Low over the water toward the beach |
| `CAM_high` | 30 | High wide: the island shape |
| `CAM_profile` | 22 | Side-on, low, on the duel line |
| `CAM_reverse` | 30 | From behind the pines toward the open sea |

To film from an anchor in your own script: `cam.matrix_world = anchor.matrix_world.copy(); cam.data.lens = anchor['lens_mm']`
(this is what `put_camera()` does).

## 3. Reusable materials: `blender/world/paper_materials.py`

Import it from any Blender script (`sys.path.insert(0, 'blender/world'); import paper_materials as pm`). The same
recipe is meant for characters, swords' paper parts and props.

- `paper_material(name, color, translucency, fibre_scale, fibre_strength, facet_var, flat, tint, tint_z, stripes, glow, haze, ...)`:
  faceted washi. Shading uses the **true face normal**, so facets stay hard even on smooth meshes; fibres (pulp
  noise + long stretched fibres) drive bump, colour speckle and roughness; each facet gets its own tone from the
  `facet_rand` face attribute; Principled (with sheen) is mixed with a Translucent BSDF so light passes through.
  Extras: `tint` (second colour by height), `stripes` (hakama bands), `glow` (inner lantern emission: amber human,
  crimson demonic), `haze` (aerial perspective, see below).
- `add_facet_attribute(obj, seed)`: writes `facet_rand` per face on built meshes.
- `facet_random_modifier(obj, seed)`: the same attribute through Geometry Nodes, for generated meshes (the Ocean).
- `sea_material(...)`: faceted sea: per-facet tone and gloss, colour by facet slope, foam = paper flecks on wave
  crests plus the Ocean foam attribute (which only rises on choppy seas).
- `haze=(None, distance_m, strength)`: the surface fades into the **Nishita sky seen in the view direction**, so far
  layers melt into the real sky colour. This is the cheap depth cue; the fog volume is the expensive one.
- `fibre_scale` is per metre of object space: about 60–200 for characters, 1–20 for world props, under 0.1 for mountains.

## 4. Slash effects: `blender/world/slash_fx.py`

`make_slash(name, center, radius, sweep, thickness, colour, demonic, frame_start, frame_end, start_angle, tilt, pitch, yaw, clockwise, shards, seed, light, strength, collection)`
builds one keyframed slash and returns `{'root', 'arc', 'shards', 'light'}`.

| Parameter | Meaning |
|---|---|
| `radius`, `sweep`, `thickness` | Arc radius (m), arc angle (degrees), max crescent width (m). Tapers to points at both ends |
| `colour` | `'amber'` (human) or `'crimson'` (demonic), or your own `((core), (body), (ink))` |
| `demonic` | Wider black ink edge, flicker in the glow, black paper shards with crimson glowing edges, more shards |
| `frame_start`, `frame_end` | Life of the effect. The head runs the arc in the first ~35% (ease-out), then the tail erases it |
| `tilt` / `pitch` / `yaw` | Orientation of the arc plane: `tilt=-35` kesa-giri diagonal; `pitch=68` near-horizontal yoko-giri |
| `strength` | Glow multiplier. Use 2–3 in the daylight world (the test sheet is a dark stage) |

The arc is a folded crescent mesh (crease along the spine, jittered facets). Its shader reads three keyed object
properties (`reveal`, `tail`, `heat`): white-hot blade edge → body glow → ragged sumi-ink inner edge with dry-brush
streaks; the tail dissolves like a dry brush. Paper shards (torn triangles and folded quads) spawn where the head
passes and fly off ballistically, tumbling and shrinking. A point light flares with the slash.

## 5. Render times (measured)

Container, 4 shared CPUs, `nice -n 15`, `-t 2`, another render running at the same time. Cycles CPU, OIDN.

| What | Size, samples | Time |
|---|---|---|
| Build the set and save the `.blend` | | about 3 s (script 0.4 s) |
| World preview, `CAM_wide` | 540×960, 24 | 63 s |
| World preview, `CAM_medium` / `CAM_hero_ots` / `CAM_low_sea` | 540×960, 24 | 63 s / 74 s / 54 s |
| World preview with `--fog` | 540×960, 24 | 110 s (1.75×) |
| Quick check per anchor | 216×384, 8 | 5–8 s |
| Slash test sheet (3 variants) | 1440×540, 24 | 82 s |
| Slash strip (4 frames) | 480×480, 24 | 77 s total |
| Slash inside the world, `CAM_medium` | 540×960, 24 | 66 s |

A full 1080×1920 frame would be about 4× the 540×960 time (4–5 min). Fine for stills; films should go to a GPU
(see `BLENDER-PLAN.md` §I).

## 6. Known weaknesses (v1)

- The sea reads as faceted from above but turns into a soft mirror at grazing angles; close foam flecks are large.
- The sand is lit mostly by the blue sky (the sun is behind the island in the wide shot), so it looks grey-beige.
- Mountains are single-sided cards: from `CAM_high` the near headland ring reads as a wall.
- Clouds are low-poly blobs; they read as paper only when lit from the side.
- The stand-ins are blocks for scale, not characters. The amber slash's ink edge is subtle.
- No character, sword or timeline import yet: the next step is `blender/build_film.py` from `BLENDER-PLAN.md` §A.
