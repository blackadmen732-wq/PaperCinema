# Planted-defect proof of concept

One command, CPU only, no model calls, no frame render (~2 min, mostly two camera checks):

```
bash tools/poc/all.sh
```

It builds a clean 30-second film from the starter scaffold (`film/poc-clean.json`), a copy with five known
defects (`film/poc-defect.json`), and the answer key (`output/poc/truth.json`). Then for each defect it
**detects** the problem and cites the number it measured, **fixes** one field, **verifies** the fix, and
proves **preservation**: the repaired film is field-for-field the clean film, so nothing the defects did not
touch moved.

Every detector measures against the film's own declared intent (`film.poc.intent`: the director's hit times,
contacts and tempo), not against the clean copy, so it is a real check, not a diff.

| # | Planted defect | Detector (deterministic) | Evidence it cited |
|---|---|---|---|
| D1 | Camera pushed too close in shot S5 | `tools/camera_check.mjs` (geometry) | subject out of frame 24 of 32 frames |
| D2 | Foot lock off: feet slide | `tools/footslide.mjs` | 4 feet slide, worst 1.32 m in a run (threshold 0.30) |
| D3 | Final strike's sound 120 ms late | impact cue vs `intent.impact_at` | +120 ms |
| D4 | Second blade contact's clash dropped | each `intent.contact` needs a cue within 60 ms | contact at 12.59 s has no cue |
| D5 | Music starts late, downbeat misses the strike | CADENCE downbeat grid vs `intent.music_downbeat_at` | nearest downbeat 298 ms off |

Result (`output/poc/report.json`): **5 of 5 detected, 0 false positives, 0 remaining after the fix, repaired film
identical to the clean film on every untouched field.**

Limits, stated plainly:
- D3 and D5 are checked against the timeline's declared intent, which an editable production has. An independent
  check of the *rendered* mix (VYRN hearing the onset late) needs a full frame+audio render; that exceeds the
  time budget in this environment, so it is not part of this fast loop.
- D1 uses `camera_check`, which renders geometry in a headless browser (~25 s per film); it is run once per film
  into `output/poc/cc-<tag>.json`, so the detect/fix loop itself stays deterministic and instant.
- The defects are isolated and reversible by construction. A real correction loop must also diagnose defects it
  was not told about, and tell a real defect from deliberate style — the harder problem the FORGE plan scopes.
