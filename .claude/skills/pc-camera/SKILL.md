---
name: pc-camera
description: Direct the camera in Paper Cinema - choose a shot from the 54-shot library by beat and emotion, map film language onto KUROKO rigs, keep continuity, and prove the audience can see it. Use for any question about where the camera goes or how it moves.
---

# Directing the camera

**Do not build a camera system. There is one.** KUROKO (`engine/kuroko.js`, `docs/CAMERA.md`) is a
deterministic spring-driven camera director integrated at 240 Hz with a 1 s pre-roll, built off real
fight-camera research. `library/shots.json` holds **54 shots**, **17 director styles**, **11 lighting
moods** and a **beat map**, each shot with a purpose, a `when`, an emotion, a duration in seconds and
frames, a fov, an angle, an elevation, a feel, a ready-made `rig`, a 16:9 variant and a **measured**
subject height. Anything you want the camera to do is a selection from that, or a sixth entry in it.

## Choosing, in four moves

1. **What beat is this?** `beat_map` in `shots.json` maps hook / world / weapon / arrival / standoff /
   exchange / impact / aftermath / transition to the shots that serve each. Start there, not from
   the full list.
2. **What should it feel like?** Every shot carries an `emotion`. Match that before you match the
   geometry.
3. **How long have you got?** `duration_s` and `frames_24` are ranges that work. A 0.8 s shot and a
   4 s shot are different shots, not the same shot held.
4. **Paste the `rig`.** It is a complete KUROKO rig. `rig_16x9` is there when the film is horizontal.

```json
{ "id": "S3", "start": 7.0, "end": 9.2, "mode": "dawn",
  "rig": { "type": "orbit", "subjects": ["hero","foe"], "radius": 5.0,
           "height": 0.45, "deg0": -20, "deg1": -50, "fov": 34, "feel": "crane" } }
```

## Language → rig, with numbers

`docs/cinematography/CAMERA_GRAMMAR.md` is the full table. The numbers worth memorising:

- slow push **0.2–0.4 m/s** · walk **0.4–0.6 m/s** at eye height **1.5–1.7 m**
- orbit **10–20 °/s** deliberate, **over 40 °/s** action
- wide **18–24 mm** · normal **35–50 mm** · tight **85–135 mm**
- rack focus needs **f/1.4–2.8** or it does not read

A support style is a **feel**, not a rig: steadicam ≈ `dolly`, shoulder ≈ `handheld`, jib ≈ `crane`,
tripod = `locked`. Never add a rig type for one.

## The rules that break a scene rather than a shot

**The 180° line** — every camera in an exchange stays one side of the line through the fighters. In an
`orbit` that means `deg0` and `deg1` both inside `(-180, 0)` or both inside `(0, 180)`.
`tools/audit.mjs` scores it. **Cut on action**, mid-gesture, not between beats. **Eyelines** stay
consistent across a cut.

In a fight specifically: **put the camera where the contact will be before it happens**, hold it
`locked` through the hit-stop (a moving camera during a freeze reads as a bug), and snap to the face
of whoever matters after.

## Prove it before you render an hour

```bash
node tools/camera_check.mjs film/<name>.json                       # scores every shot, exits 1 on a reject
bash tools/shotsheet.sh film/<name>.json --set <set>               # 6 real frames, one page
blender -b -P blender/check_sight.py -- --film <name> --set output/sets/<s>.blend
```

`check_sight` answers the question no other check asks: **can the audience see it?** Blocked by the
set, off-frame, or too small to read — and a failure on a **contact frame is CRITICAL**, because the
shot exists for that frame.

Clearance means solid things only. A real camera moves through dust, haze and light shafts; the ray
walks through anything that does not render.

## Prior art worth reading, and its limits

`vendor/anyshot` (MIT) is a Claude agent directing Blender — the closest thing to KUROKO anyone has
published, and the source of the speed and lens numbers above. Read `agent/SHOTS.md` for its shot
language and its block-then-look discipline. **Do not transplant it**: it targets Blender 5.0.1 and a
GPU farm, and this pipeline is 4.5.16 on CPU.

`library/shots.json` already covers rotational, physical, curved, lens and focus families. Added for
completeness after a gap check: `crab-slide` (truck), `pedestal-rise` (not a crane — no re-aim),
`slow-pan-reveal`, `pov-blade`, `ramp-hold`. Not added, deliberately: drone, gimbal, vehicle and
steadicam are feels; bullet-time is a feature, not a shot.

CineTechBench is **CC BY-NC-ND** — research to read, never to bundle or adapt into work that sells.
