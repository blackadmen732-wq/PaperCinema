# AUTOPILOT: the work queue when Mark is away (standing order, 27 Nov 2026)

Mark, 27 Nov: "Start working... you don't need my permission... use my credit every single time... every time
you reach the 5-hour limit, have something automatic to reset and keep working... by tomorrow I want the set
done... render, check the skeleton works, watch it frame by frame... katana... free 3D models into the style,
a full village... make it fight good, a system for groundbreaking sound and cool animation. Don't stop."

## How the autopilot runs
- An hourly scheduled task (minute 12, UTC) wakes this session with "continue the queue". After a usage-limit
  reset the next wake-up carries on; a wake-up during work simply waits for the turn to end.
- Every wake-up: read this file -> take the FIRST open item -> do it -> verify (render, watch frame by frame,
  measure) -> commit + push to `claude/first-episode` -> tick it here with the proof (file paths, numbers) -> next.
- Approved without asking: Tripo credits (ledger: `output/tripo/ledger.jsonl`, balance via `tools/tripo.py
  balance`), CPU renders here, research. Not without asking: new paid services, money beyond the Tripo credits.
- Rules that still hold: no claim without proof in the same note; experiments stay off production characters and
  Episode 1 until they pass; Mark's images stay out of the public repo unless already there; push often (the
  container can be rebuilt; output/ is not kept).

## Queue (top = next)
| # | item | done when | status |
|---|---|---|---|
| 1 | **Bending AI body**: whole Kojiro from one text concept (realistic proportions, rest pose) -> 3D -> Tripo auto-rig (mixamo) -> driven by our rig -> paper look; sections cut from it later | it bends in the 5-pose sweep and the draw without tearing; side by side with today's Kojiro | **done (sections, not Tripo's rig)**: Tripo's auto-rig was unusable (T-pose arm chains sticking out in the air, sleeves read as limbs) so the body is cut into 8 sections bound to OUR bones (tools/ai_part.py fit.mode body + keep boxes + per-section palettes): kojiro-ai2 bends through the 5-pose sweep (output/heads/poses-ai2-v2.png), validator 152/152 |
| 2 | **Kojiro outfit set from one concept** (consistent style): kimono torso, sleeves, hakama legs, obi, sandals, hands; rigid pieces on one bone, bending pieces skinned | `kojiro-ai` wears AI pieces in every slot that passes; pose sweep + validator + film frames checked | mostly done: `kojiro-ai2` = AI head + torso, 2 sleeves, hakama top, 2 legs, 2 feet; folded neck, forearm under-sleeves, hands, sword kept. Left: film frames |
| 3 | **Rigid library pieces like the look board**: kasa, hood, 2 kabuto helmets, 2 oni masks, fan, armour (do, sode, kote) | each prepared, in the catalogue sheet, on a test recipe | open |
| 4 | **Musashi from the same pieces** (his head + mix of the set) | `musashi-ai` recipe renders and passes the validator | **done**: one Tripo figure (35 credits) -> head (head mode, baked face) + 8 sections; `musashi-ai` validator 152/152, bends through the 5-pose sweep (`output/heads/poses-musashi-ai-*.png`). Found on the way: the black bakes were Tripo's METAL map (77% metallic) + the bake clearing the UV gaps black; palette now from the model's own paint + class zones (docs/AI-PARTS.md) |
| 5 | **Katana variants** (AI fittings on the procedural blade; the draw still works) | draw film frames checked frame by frame | open |
| 6 | **Feet on the ground** (foot IK in the bake against the set; fighters buried 1.46 m on the beach) | beach exchange renders with feet on the sand | **done (level + stage)**: beach levelled under the marks (0.941 m, slope 0.0 deg, was 5-14), the set staged under the action (film.stage), `--ground-report`: 120 samples, median 4.1 cm, 2 buried <= 2.4 cm (was 1.46 m); frames f9/f76 render on the sand. Left: foot IK for action off the level zone |
| 7 | **Village**: kit pieces (minka, machiya, well, fences, stall) + Poly Haven props converted to paper + a layout piece | a village set renders from 3 cameras; reopened .blend passes | open |
| 8 | **Fight + sound**: bake events for footsteps/landings feed the mixer and camera; better anticipation/impact timing | an exchange on the village set with synced foley, watched frame by frame | open |

## Log
- 27 Nov 08:40-09:40 UTC: Musashi done (item 4). Bake fix applies to every part: metal input cut, magenta gaps; Kojiro's sections re-prepared with the same code (less false black: torso 16.4 -> 8.5%). No Tripo spend.
- 27 Nov 08:10-08:40 UTC: body concept from TEXT (image edits kept the toy proportions), 3D 30, rig 25 (unusable),
  8 sections prepared (~10 s each), kojiro-ai2 152/152. Balance 785.
- 27 Nov 07:13-08:10 UTC: section-by-section images came out plain (a cone sleeve, a hanger): switched item 1 to
  whole body -> rig -> sections. Tripo spend so far 215 credits incl. 100 LOST (4 rig jobs queued by a bad probe,
  ids not captured); balance 785. Item 6 done (levelled fight ground + stage handle + ground report).
- 27 Nov 05:54 UTC: autopilot started (965 Tripo credits).
