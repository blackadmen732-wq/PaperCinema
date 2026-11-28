# Integration of Sonic (PR 2), Aethern (PR 3) and VYRN (PR 4)

Branch `claude/integration`, 28 Nov 2026. Every number below was measured in one Claude Code cloud
session (4 CPU cores, 15 GB RAM, no GPU). Time is wall-clock; peak memory is the largest child process.

## How the three systems talk (no AI calls anywhere in the loop)

```
engine (timeline.mjs) ──events──▶ VYRN (verify: heard sound vs picture events)
engine (combat.js) ──auto cues + event ids──▶ Sonic (picks a sound per event) ──▶ sound.mjs (mix)
Sonic ──<film>.sonic.events.jsonl──▶ VYRN sync ──<media>.events.jsonl──▶ aethern events merge/near
aethern map: SONIC, VYRN and AETHERN are rows in the one project map, with their connections
```

The shared language is **`aethern-event/1`** (`packages/aethern/schema/event-1.schema.json`):
`{id, type, t, t1?, f?, source, method?, conf?, entities?, data?}`, one per line. `v` is optional and
defaults to 1, so the files Sonic and VYRN already write are valid without changes.

## Conflicts resolved

- `tools/build_systems.py` is a thin wrapper now, so the connections Sonic and VYRN added there moved
  to `aethern.json` → `catalog.connections` (COMBAT→SONIC, GROUNDFX→SONIC, SONIC→SOUND, TIMELINE→VYRN,
  SOUND→VYRN, VYRN→SONIC). `systems.json` is regenerated, not hand-merged: 69 systems, 66 connections.
- `package.json`: one `test` script that runs Sonic's tests, the scaffold test and the Aethern tests.
- `SYSTEMS.md` merged cleanly with three new rows (SONIC, AETHERN, VYRN).

## Deterministic checks (all cheap, no model calls)

| check | result | time | peak memory |
|---|---|---|---|
| `npm test` (Sonic 16 checks, scaffold test, Aethern 21 Python + 6 JS) | **all pass** | 7.2 s | 93 MB |
| every film in `film/` through `engine/validate.mjs` | 16/16 valid | | |
| `systems.json` rebuilt, `SKILLS.md --check` | current | | |
| promise ledger | 6/7 kept; `sleeves-clear-the-head` fails because Blender is not installed here (same as before this work) | | |
| `node tools/test_new_film.mjs --browser` (blades meet, fighters in frame) | pass | 83 s | |
| offline sound mix (one cue with no cached file, no network) | **21/22 sounds mixed, the missing one skipped**; before Sonic's fix the whole mix stopped | 1.7 s | 72-86 MB |
| `aethern events check` on Sonic's and VYRN's real output | 3 files, 116 lines, all valid | | |

### VYRN on its synthetic duel (ground truth known; `python3 -m vyrn.bench.run`)

| measure | result |
|---|---|
| sound events heard within 100 ms of the picture event | 20/21 (footsteps 15/16, blade contacts 4/4, impact 1/1); median offset -0.2 ms |
| the clash planted 83 ms late | found as **+82.9 ms** |
| impacts from the picture | 3 of 5 hit, 1 false (4.54 s), 2 missed (4.63 s, 5.13 s) |
| footsteps from the picture | 4 of 16 within 2 frames, 3 false |
| tracking through a hard cut | hero IoU 0.53, villain 0.65, one id each, no switches |
| time / memory | 5.0 s for 6.5 s of video, 258 MB peak (OpenCV installed for this) |

### The three systems on a real Paper Cinema scaffold (sound only, picture from the timeline)

New film from `engine/new-film.mjs`, its timeline exported (61.7 s, 229 MB), the mix made with and
without Sonic, then `vyrn verify` comparing heard onsets with the film's picture events (ingest 6.4 s,
338 MB; verify 0.08 s):

| | without Sonic | with Sonic |
|---|---|---|
| picture events with a sound heard within 100 ms | 5/17 | 4/17 |
| blade contacts | 2/2 | 2/2 |
| footsteps | 3/14 | 2/14 |
| paper cut (10.80 s) | 0/1 | 0/1 |

So the clash fix works end to end (2/2 contacts now heard), but **the scaffold has almost no footstep
sounds and no sound on the headband cut**. These are leads: VYRN reports what it hears in the mix, and the
scaffold only places one `steps-in` cue.

## Leads from VYRN, not yet confirmed

- Every rendered cut lands **1 frame after** the timeline's cut frame (measured on dash-test).
- `engine/sound.mjs` once failed with **ffmpeg exit 183**; the rerun succeeded. Not reproduced here
  (two runs, both fine).
- dash-test `verify` flags: paper-cut sound 71 ms late, a landing 70 ms early, impacts at 4.30 s and
  4.92 s with no sound.

## Remaining weaknesses

- Footsteps: from pixels they are weak (4/16), and the scaffold gives them no sound.
- Picture impacts under a moving camera are missed (2 of 5 in the synthetic test).
- The Earshot bank is not vendored in cloud sessions; Sonic leaves its unrendered sounds out of picks.
- Blender and MediaPipe are not installed here, so the Blender checks and pose-based measures cannot run.
- Usage per task is still not recorded automatically (see `docs/TOKEN-INVESTIGATION.md`).
