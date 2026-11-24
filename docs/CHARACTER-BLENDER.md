# The hero in Blender: rig, film render, motion capture, camera

Production casts use the [modular character catalog](CHARACTER-FACTORY.md). The TRELLIS rig below is available for source comparison with `--model ronin_base`.

The owner's reference character (TRELLIS model `assets/models/ronin_base.glb`) fights in Blender, driven by the same
film data as the browser preview. The box figures in `engine/*.js` are the preview; this is the picture.

| File | Job |
|---|---|
| `tools/export_motion.mjs` | Film → `output/<film>.motion.json`: what the preview engine really did on every frame |
| `blender/character/rig_trellis.py` | TRELLIS `.glb` → rigged character, katana, inner lantern; pose, film and BVH drivers |
| `blender/film_blender.py` | Renders a film (or a BVH take) with the character: light, slash, dust, camera |
| `library/blender-cameras.json` | Named camera moves and one camera plan per film |

## 1. Commands

```bash
B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
node tools/export_motion.mjs film/dash-test.json          # 13 s; run again after the film or the engine changes

# stills at film seconds: always look at these first
nice -n 10 $B -b -t 2 -P blender/film_blender.py -- --film film/dash-test.json --out output/blender/dash-test/ --times 0.3,1.15,4.2
# a short sequence (film frames, 24 fps)
nice -n 10 $B -b -t 2 -P blender/film_blender.py -- --film film/dash-test.json --out output/blender/dash-test/ --frames 24-35
# the Blender camera plan instead of the film's camera, or one named move
... --cam plan          ... --cam circle
# one library pose, or one film moment, on a plain dark stage
nice -n 10 $B -b -t 2 -P blender/character/rig_trellis.py -- --pose jodan --out output/character/rig-jodan.png
# motion capture (any BVH)
nice -n 10 $B -b -t 2 -P blender/film_blender.py -- --bvh take.bvh --cam circle --out output/blender/take/ --times 1.0,2.0
```

Measured on this machine (2 threads, shared CPU, 432x768, 16 samples, denoised): 30–40 s per still.
`film_blender.py` exports the motion itself when the file is missing or older than the film.

## 2. Which way to rig a TRELLIS mesh (tested on stills)

The mesh is one fused shell: robe, sleeves and the folded arms are a single surface with nothing under it, in
about 370 loose patches, with the reference image's light baked into the texture. Four ways were rendered in the
same two poses (`output/character/rig/attempts-sheet.png`, columns left to right; top row chudan, bottom row jodan):

| Mode | How | Result |
|---|---|---|
| `cloak` | Our own smooth region weights, no cuts | Stretched membranes between arm and chest |
| `heat` (**chosen, default**) | Weld the patches, Blender's automatic bone-heat weights, then a scripted cleanup (head and kasa rigid, 4 bones per vertex) | The robe hangs from the arms as one cloth. Cleanest silhouette, no holes |
| `rigid` | One bone per vertex, faces between panels removed | Most "origami", but full of holes and torn edges |
| `panels` | Knife cuts along the collar V, between the hands and under the sleeves; an under-robe core that glows in the gaps | Good idea (the inner light shows when a sleeve opens), but the cut edges look torn |

Rebuilding the hero with `origami_samurai.py` and projecting the texture (option c) was rejected on its existing
stills (`output/character/t5.png`): the procedural figure is boxy and does not look like the owner's character.

If bone heat fails on a mesh, the script falls back to `cloak` by itself.

**The texture is relit.** TRELLIS paints the unseen back and everything hidden behind the sleeves brown or black.
The material keeps the texture only as soft fold shading on clean paper, so our lights decide what is dark.
The orange areas of the texture (the lit collar and sleeve mouths) emit light: that is the inner lantern,
with two point lights on the chest and head bones. `rt.set_glow(ch, strength, frame)` pulses it.

## 3. The rig

Joints carry our names. Rest pose = the model's own pose (arms folded).

```
root ─ hips ─ waist ─ chest ─ neck ─ head
                        ├ clavicle.L ─ shoulder.L ─ elbow.L ─ twist.L ─ hand.L        (and .R)
                        │                            └ sleeve.L   (free sleeve end: hangs, swings late)
root ─ thigh.L ─ shin.L ─ foot.L                                                       (and .R)
```

| Ours | Standard humanoid (Mixamo, most BVH/FBX) | Engine joint (`figure.js`) | Engine channels |
|---|---|---|---|
| `root` | `Root` | root | `x y z ry rx rz` |
| `hips` | `Hips` | hips | `crouch weight stance` |
| `waist` | `Spine` | torso | `tx ty tz` |
| `chest` | `Spine1` | upper | `cx cy cz` |
| `neck` / `head` | `Neck` / `Head` | neck / head | `nx ny` / `hx hy hz` |
| `clavicle.L/R` | `LeftShoulder` / `RightShoulder` | lC / rC | `lcy lcz` / `rcy rcz` |
| `shoulder.L/R` | `LeftArm` / `RightArm` | lS / rS | `lsx lsy lsz` / `rsx rsy rsz` |
| `elbow.L/R` | `LeftForeArm` / `RightForeArm` | lE / rE | `lex` / `rex` |
| `twist.L/R` | `LeftForeArmRoll` / `RightForeArmRoll` | lT / rT | `lfy` / `rfy` |
| `hand.L/R` | `LeftHand` / `RightHand` | lH / rH | `lwx lwz` / `rwx rwz` |
| `thigh.L/R` | `LeftUpLeg` / `RightUpLeg` | legs.l/r.thigh | leg IK |
| `shin.L/R` | `LeftLeg` / `RightLeg` | legs.l/r.shin | leg IK |
| `foot.L/R` | `LeftFoot` / `RightFoot` | legs.l/r.foot | `lax` / `rax` |

The table is `HUMANOID` in `rig_trellis.py`.

**How a frame is solved** (`rt.solve`): the driver receives the world transform of every engine joint.
1. Spine, neck, head and hands take the engine's world rotations.
2. Hips: the engine's hip travel, scaled to this model's legs (they are 0.60 m, the engine's are 0.90 m).
3. The katana takes the engine's rotation; its position is where the engine's right hand is, seen from the
   shoulder, at this model's arm length. So poses keep their meaning on any proportions.
4. Both arms: two-bone IK onto the handle (right hand at the guard, left hand 25 cm behind it while `twoHand`
   is on). Elbows point where the engine's elbows point.
5. Legs: two-bone IK to the engine's foot placement, knees forward.
6. Sleeve ends: 70% vertical, and they lean against the elbow's motion of two frames ago (follow-through).

Axes: three.js `(x, y, z)` → Blender `(x, -z, y)`; quaternion `(x, y, z, w)` → `(w, x, -z, y)`; Euler
`(rx, ry, rz)` → `(rx, -rz, ry)` in mode `YZX`.

**Katana** (`rt.make_katana`): polished steel blade with a ridge and a frosted hamon band, copper habaki, iron tsuba,
ray-skin handle with a crossed silk wrap, kashira. It is built in the engine's sword frame (blade +x, edge −y).

## 4. The three drivers

| Driver | Call | Source of truth |
|---|---|---|
| Library pose | `rt.apply_frame(ch, rt.pose_frame('jodan'))` | `library/poses.json` through a Python port of `applyPose` + `solveLegs` (checked against the engine: 0.000 m, 0.000 rad on root, spine, right arm, legs and sword) |
| Film | `rt.bake(ch, rt.load_motion('output/x.motion.json'), 'hero', f0, f1)` | The preview engine itself, via `tools/export_motion.mjs`: motion curves, follow-through, leg IK, two-hand grip, clash aim, hit-stop, speed ramps, camera |
| Motion capture | `rt.bake(ch, rt.bvh_motion('take.bvh'), 'hero', f0, f1)` | Any BVH file, through Blender's own BVH importer |

The export adds one line to the copy of `engine/motion.js` the browser receives (the file on disk is untouched) to
reach the page's private objects. If the page ever sets `window.PC = { cast, camera, stage, TREES }` itself, the
exporter uses that. Films on `engine/index.html` (main engine) are not supported yet.

### Motion capture (BVH)

The owner's direction: capture comes from an existing mocap app that exports BVH or FBX.

- `--bvh take.bvh` in `film_blender.py` (or `rig_trellis.py`) imports it with Blender's importer and re-targets it.
- Bone names are found by the standard names above plus common spellings (`BVH_ALIASES`: `LeftUpLeg`, `lThigh`,
  `LeftHip`, `Spine2`, `Chest`…). An unknown skeleton stops with the list of bones it found; add the spelling there.
- The retarget is by **world rotation change from the BVH's rest pose** (spine, head, feet) and by **limb
  directions** (arms and legs), so a T-pose file and an A-pose file both work, and limb lengths do not matter.
- Height is normalised from the rest pose (hips above feet). The figure should face −Y after import
  (`--bvh-forward Y|X|-X` if it does not). Frame time is read from the file and resampled to 24 fps.
- The katana rides in the right hand; `--two-hand` puts the left hand on the handle.
- FBX: convert to BVH in Blender (File → Import FBX, Export BVH) or in the mocap app.
- For other retarget tools (Rokoko, Auto-Rig Pro, game engines):
  `rig_trellis.py -- --a-pose --names humanoid --save output/character/ronin_rig.blend` writes the rig with an
  A-pose rest and the standard names. Do this last: after it, the drivers in this file no longer fit the rig.
- `tools/mocap.py` (phone video → our channels, `docs/MOCAP.md`) still feeds the film path.

## 5. What `film_blender.py` builds

- **Light** (`research/reference-videos.md`): about 70% of the frame dark. The lights are re-set for every frame
  from where the camera stands, like a crew per shot: a strong cool rim from behind, a second rim low on the other
  side, a warm key from the lens's left, a faint fill. The lantern and the slash are the brightest things.
- **Slash of light**: a ribbon swept by the real blade over the last 0.06 s of body time (4 samples per frame,
  interpolated): white-hot at the blade, amber behind it (crimson for a demonic fighter), streaked, fading. It
  appears only above 7 m/s tip speed, and a flare light on the blade lights the paper while it is fast.
- **Dust**: soft camera-facing puffs on the engine's ground events (dash, skid, take-off, landing).
- **Tree props** from `film.props.trees` with the engine's cut and split motion.
- **Depth**: three rows of torn-paper ridges far behind and in front of the action line (2.5D layers).
- Motion blur (off across hard cuts), a soft glare, depth of field focused on the chest.

### In a set (`docs/SETS.md`)

```bash
# the film inside a built set: the action line is laid on MARK_hero → MARK_foe, centred between the marks
... film_blender.py -- --film film/dash-test.json --set output/sets/castle.blend --out output/blender/dash-test-castle/ --times 1.167,4.208
# a set still with the TRELLIS characters on the marks in a pose (hero = ronin_base, other roles = samurai_front)
... blender/sets/build_set.py -- --set castle-courtyard --preview output/sets/castle_trellis.png --with-character hero:chudan:trellis,foe:hasso:trellis
```
In a set the set's own light stays and our fighter lights drop to 30% (`--light` scales them); `--at x,y,z,yaw`
places the action by hand. Tested on stills: `output/blender/dash-test-castle/sheet.png`, `output/sets/castle_trellis.png`.
`rt.place(ch, location, yaw, collection)` stands a character anywhere from your own script.

## 6. Camera: moves and the beat → camera table

`--cam film` uses the film's own camera (KUROKO beats, exported per frame). `--cam plan` uses the plan for the
film in `library/blender-cameras.json`; `--cam <move>` uses one move for all frames. Every move is an arc around
the hero: `az` (0 = in front of him, 90 = his left, 180 = behind), `dist`, `height`, `look`, `fov`; a pair
`[a, b]` travels during the beat. `breathe` moves the lens in with the blade's speed; `lead` aims ahead of travel.

| Fight beat | Move | What the lens does | Why |
|---|---|---|---|
| Stillness before the storm | `low-hero` | 16 cm above the ground, slow push-in, 30° lens | The reference videos' hero shot |
| Dash | `side-track` | Knee-height profile, racing with him, aims ahead | Speed reads as ground rushing past |
| Wind-up → strike | `go-front` | Swings from his side to straight in front, closes in | "Going front": the cut lands as the lens arrives |
| The cut in slow motion | `half-circle` | Behind him → his front, low → chest height | Shows the blade's whole arc |
| Impact, skid | `come-back` | Starts on the blade, pulls away fast, settles wide | "Coming back": the release after the hit |
| Look over the shoulder | `over-shoulder` | Behind his shoulder, target small ahead | His point of view |
| Jump | `jump-under` | Under the jump, turning, he passes over the lens | Height |
| Aerial cut in slow motion | `circle` | Full circle, rising from 0.3 m to 2.6 m | The owner's "circling" |
| Landing, aftermath | `high-crane` | Cranes up and away | Scale, loneliness |
| The line of a cut | `top-down` | Straight down, slowly rolling | The cut as a drawn line |
| Zanshin, chiburi | `push-pull` | The lens breathes with the blade | Life in a held shot |
| Hands and steel | `blade-close` | 1.25 m, 50° lens | Inserts |

The plan for `dash-test` uses these in order (see the file). Slow motion comes from the film's `ramps`
(they are in the export: the Blender frames are film frames).

## 7. New ideas

Built now: the 12 camera moves above; the lens that breathes with blade speed; light re-set per frame from the
camera; the slash as real swept light with a flare that lights the paper; sleeve follow-through; relit paper.

Next, in order of value:
1. **Cloth simulation on the robe hem and sleeves** (Blender cloth, pinned to the rig): the reference videos'
   "little movement, but heavy cloth". Bake per shot.
2. **Hat lag**: the kasa tips 2 frames after the head, and dips on landing.
3. **Lantern pulse on effort**: glow rises 30% through the wind-up, flashes on contact, dims in zanshin.
4. **Blade reflection card**: a long bright card off-screen so the steel always carries one clean highlight.
5. **Whip pan between two fighters** on a clash, with the motion blur doing the cut.
6. **Dolly-zoom on the realisation beat** (the film already does one; add `fov` pairs to `over-shoulder`).
7. **Ground-level wake**: dust that trails the whole dash, lit by the rim from behind.
8. **Silhouette frame**: one frame of pure black figure on a white flash at contact (the engine's ink frame).
9. **Shadow play**: a low key throws his shadow across a shoji wall in the dojo set while he cuts.
10. **Two-shot orbit lock**: the circle keeps both fighters on screen thirds, on the 180° line.

## 8. A new TRELLIS model

1. `rig_trellis.py -- --model <name> --pose rest --out x.png`. It starts from the hero's landmarks (`DEFAULT`).
2. If joints sit wrong, measure the mesh (shoulder, elbow, wrist, hip, knee, chin heights at 1.75 m) and add a
   `MODELS['<name>']` entry with only the values that differ.
3. Check `chudan`, `jodan` and one film moment on stills before a sequence.

## 9. What is still weak

- The robe is cloth, not origami panels: deep crouches crumple the skirt, and arms overhead pull the robe up.
- Legs are hidden; the paper feet under the hem are simple wedges.
- No visible hands: two paper fists sit on the handle.
- The model is 1.75 m to the hat tip with short legs, so strides are shorter than the preview's.
- The blade path is lower than the engine's (shoulders at 1.20 m, not 1.39 m): prop cut heights differ by that much.
- BVH: tested with a synthetic file only (`output/blender/bvh-test/sheet.png`); finger, toe and wrist rotations are ignored.
- `samurai_front` and the other models use the hero's landmarks until someone measures them (§8).
- In a set the film's camera can pass through walls or props: the KUROKO guards know the preview's world, not the set. Use `--cam plan` or check stills.
- Only motion-page films export; only the first fighter has been rendered.
