# Head-to-head: does an AI-native environment beat a plain one?

Status: **pilot done** (`docs/HEAD-TO-HEAD-PILOT.md`, $8.20 measured). Full runs wait for your yes.

## The question

Given the same hard scene, does Paper Cinema (and Paper Cinema on the Aethern core) produce a
better film for fewer resources than plain Claude Code? Only measured results go in the report.

## Three environments

| | what the agent gets | commit |
|---|---|---|
| A. Plain Claude Code | an empty repo with the same assets, three.js and ffmpeg (Blender too where it is installed; cloud sessions have none); no Paper Cinema code, docs or skills | new repo |
| B. Paper Cinema as it was | this repo before the core | `4a8c4cb` |
| C. Paper Cinema on the core | this repo with `packages/aethern/` | `claude/shared-core` |

Held identical: the model (Opus 5.5, same effort), the written brief (word for word), the assets
(the same character model, the same sound folder, the same reference stills), the machine (a fresh
cloud session of the same size), and the budget (a 2-hour wall-clock cap; the run stops there and
whatever exists is scored). No human messages after the brief; a permission prompt answered is
counted as an intervention.

## The scene (same brief for all three)

15 seconds, vertical 9:16, 24 fps. Two fighters, one sword clash exchange, a dodge, a decisive cut,
at least three camera changes (one hard cut on impact), one destruction beat (a prop or a paper
panel is cut and falls), and sound: a whoosh before every strike, a clash on every blade contact,
an impact on the cut, a bed under all of it. Deliverables: one MP4 with sound, and a cue list
(time and name of every sound).

## What is measured, and how (the same tool for all three)

| measure | how |
|---|---|
| Claude tokens and cost | the token-usage plugin's `session_cost` on each run's transcript (output, cached input, API-price estimate) |
| Wall time | session start to the final MP4 |
| Animation defects | MediaPipe pose (`tools/mocap.py`) run on **each output video**, then foot slide and jitter (`tools/footslide.mjs`, `tools/jitter.mjs`) on that skeleton, so A is judged by the same yardstick as B and C. B and C also get the full studio audit (`tools/audit.mjs`), reported separately because A cannot run it. |
| Sound sync error | `tools/listen.py` finds audio hits; the visual contact frames come from the pose track (wrist speed drop); the report gives the median and worst offset in ms |
| Physical accuracy | foot slide (m), joint limits past (`engine/limits.js` applied to the pose track), and whether bodies stay on the ground between jumps |
| Self-correction | from the transcript: checks that failed and were then fixed without a human message |
| Human interventions | count of messages or prompt answers after the brief |
| Total cost | Claude API-price estimate + any paid compute (none planned) |
| Quality (yours) | a blind page: the three films as X, Y, Z in random order, scored 1 to 10 on fight readability, timing, sound and look; labels revealed only after you submit |

## What it will cost (estimate, to be replaced by the pilot's real number)

This extraction session used about $16 at API prices (86.9k output tokens, 21.5M cached input).
A run that builds and renders a 15-second scene is likely similar or larger: **about $10 to $40 per
run**, so **$30 to $120 for one run of each environment**, double that for two runs each (two runs
make the result less of a coin toss). On a subscription this comes out of your usage, not a bill.

Before the full runs, a **pilot**: environment B only, capped at 30 minutes, to replace the estimate
with a real number (about $5 to $10).

## Known limits, stated up front

- In cloud sessions the free models are unreachable (403), so B and C cannot offload work there.
  The test then measures the environments without their biggest claimed saving. Running it where
  the free models answer would test that claim too.
- B and C need `npm install` (three, Playwright) and Python packages from the repo's files; that
  install needs your yes.
- C differs from B by tooling for reading and remembering, not by animation algorithms. Expect the
  difference between B and C to show mostly in tokens, not in picture quality.
- One run per environment shows a direction, not a proof.
