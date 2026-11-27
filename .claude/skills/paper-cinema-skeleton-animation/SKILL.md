---
name: paper-cinema-skeleton-animation
description: Use when building or animating Paper Cinema folded-paper Blender characters, retargeting motion, attaching paper parts, staging prop contact, or reviewing production bakes frame by frame.
---

# Paper Cinema skeleton-first animation

## Establish the reusable rig

1. Read AGENTS.md and the current PaperCinema branch. Reuse blender/character/modular_builder.py, part_registry.py, library/mocap-bonemap.json, tools/mocap.py, tools/mocap_cmu.py and blender/production_bake.py. The current production layout has 25 bones and 23 sockets. Preserve joint names, rest axes and parent relationships used by existing motion data. Use the existing tracker for capture.
2. Display a bare rig with root, hips, chest, head, arm and leg controls. Check left and right, local axes, usable elbow and knee bends, and wrist orientation before fitting clothes. Use IK and pole controls where contact requires them. Verify the evaluated deform bone follows each control in the saved production bake.
3. Use named wrist, shoulder, waist, knee and other sockets for rigid folded parts. Parent each piece at its intended local socket transform. A folded hand can be one rigid piece. Give a held object an independent grip anchor so the wrist socket can remain the attachment for the hand mesh. Skin only pieces that need to bend. Keep sleeve and hem motion downstream of the final body solve.
4. Review two outfits on the same motion. Save an artist-facing Blender asset collection. Reuse the existing paper shader and existing character sheets. Organize set materials by wall, roof, floor, stone, screen and lantern. Keep light rigs separate as neutral, dawn and moonlit collections. Validate each asset after reopening the .blend.

## Author the first motion

Use Bodies in Motion for how weight transfers and where contacts occur, Animator Island for progressive rig exercises, and Sakugabooru for timing, framing and staging. Record the source and usage rights. Import only cleared motion data or owned capture. Use the existing CMU importer for supported recorded files. Preserve the authored contacts after retargeting.

Use this 54-frame, 24 fps toss as a starting benchmark, based on the existing scripted test. Frames are Blender 1-based. Timing is a proposed exercise, not measured from a reference clip.

| Frames | Body and prop | Control and review |
|---|---|---|
| 1–6 | Establish the hold and grounded stance. | Keep both present feet stable; ball inherits wrist grip anchor. Show face, hand and ball. |
| 7–12 | Lower and shift weight into anticipation. | Change hips and knees together. Keep shoulder and hand within reach. |
| 13–17 | Drive upward from the legs, then let chest and arm follow. | Check hand position and velocity each frame. Keep ball attached until release. |
| 18 | Release. | Switch ball to world-space flight with continuous position and a launch velocity derived from the final hand path. Check the transition for a jump. |
| 19–25 | Ball rises. Character follows with the eyes and chest. | Pose the arm independently. Camera can ease toward a point between ball and chest. |
| 26 | Approximate apex for the benchmark. | Check the trajectory and negative space above the ball. |
| 27–33 | Ball descends. Hand moves into a catch pose. | Use a hand IK target near the predicted catch point. Set the elbow pole so the silhouette reads. |
| 34 | Catch. | Match grip position and orientation before switching the ball to hand ownership. Start catch Foley here if contact reads. |
| 35–41 | Absorb the catch through wrist, elbow, torso and knees. | Let the sleeve trail and recover. Check for mesh intersections. |
| 42–54 | Settle into a held finish. | Let the camera and loose paper finish settling. Check the final grip and planted feet. |

Block stepped keys first. Add breakdowns before easing. Compare a locked camera and one tracking camera driven from the same bake. Use the existing KUROKO / Blender camera path. Keep the performer and prop readable through the ownership transitions.

## Verify every frame

Export a row for each frame with frame number, prop owner, grip position and angle error when held, planted-foot drift, ball screen position and edge margin, sampled ball visibility, and collision flags. Evaluate after final constraints and baking. Inspect consecutive renders around release, catch and the worst metric. Confirm that isolated and sequential renders agree. Render the same bake as bare rig, dressed character and mixed camera preview. Keep scripted-ball framing claims separate from physical contact or footage tracking. The existing 54-frame baseline kept nine sampled ball points visible throughout; it did not certify physical contact.

## References

- https://bodiesinmotion.photo/
- https://www.animatorisland.com/51-great-animation-exercises-to-master/
- https://www.sakugabooru.com/
- https://mocap.cs.cmu.edu/

## Where this lives in the repo (checked 27 Nov 2026)

- Rig: `blender/character/modular_builder.py` (`Rig`: 25 joint empties driving 25 deform bones; `Rig.key_bones()` bakes the
  deform bones, without it skinned paper freezes), sockets in `blender/character/part_registry.py` (`SOCKETS`: 23).
- Contact IK and the body boundary: `blender/props/sword_draw.py` (`ik_arm`, `arm_keep_out`, `hand_holder`),
  `blender/character/body_capsules.py`; cloth after the body: `blender/character/cloth_springs.py`.
- Production bake (solve once, every render reads it): `blender/production_bake.py`.
- The toss benchmark this skill describes: `blender/bench/toss_bench.py` (isolated from the episodes; outputs in
  `output/bench-toss/`).
