# Blind planted-defect benchmark

Tests whether the pipeline can **independently** find and fix production defects — not whether it can copy
known-good settings back in. CPU only, no model calls, no full frame render. Camera repair renders shot
geometry in headless Chromium, so a full run takes several minutes.

```
bash tools/poc/all.sh
```

## What makes it blind

Three separate programs, with a wall between the one that repairs and the one that holds the answers:

- `tools/poc/make.py` builds a clean ~24 s film (`film/poc-clean.json`) and plants defects in copies. The
  clean film **is the answer key**. Only the evaluator opens it.
- `tools/poc/run.py` **detects and repairs**. It reads only the film under test and its measured events. It
  never opens `poc-clean.*`, and it is **not told where the defects are** — it scans every shot and every
  contact and decides from measured evidence. Each repair is computed from the production constraint, not
  copied from a known-good value.
- `tools/poc/score.py` is the **only** reader of the answer key. It grades detection, two separate notions of
  correctness, and preservation, plus a clean control and a stylization film.

## The four defects

| # | Planted | Detected by (deterministic) | Repaired by (from evidence, not copied) |
|---|---|---|---|
| D1 | Shot S8 camera distance cut 1.35 → 0.3, so the fighters overflow a shot that asks for "wide" | `camera_check` renders the geometry; S8's framing-size check fails (measures 0.99 of frame height vs the 0.1–0.4 the shot declares) | widen the distance step by step, re-render, stop when the shot frames its declared size |
| D2 | `motion.lockFeet` turned off, so planted feet skate | `footslide` poses the rig; a planted foot slides past the audit threshold | turn foot-lock back on (the known remedy), re-measure to confirm the skate drops |
| D3 | A clash cue nudged 120 ms off its blade contact | the contact is a measured picture event; a clash cue >40 ms off it is misaligned | snap the cue to the measured contact time |
| D4 | A clash cue removed entirely | a measured contact with no clash cue within 200 ms | synthesise a cue at the measured contact time |

## Result (last run, Nov 28)

| Check | Verdict | Detail |
|---|---|---|
| detection | **PASS** | all four located blind (camera S8, foot-lock, cue-shift, missing cue) |
| perceptually-correct | **PASS** | repaired film re-passes the detectors: S8 framing passes, foot-slide worst run 1.32 m → 0.21 m (unflagged), every contact cued |
| preservation | **PASS** | no field changed outside the defects; no other cue moved or was lost |
| clean control | **PASS** | the clean control film produced **zero** findings (no false positives) |
| stylization | **PASS** | the real defect (foot-slide) was caught; the declared intentional silent contact was **not** "repaired" |
| metadata-correct | **PARTIAL** | D2/D3/D4 match the clean answer; **D1 does not** — see below |

## Limits, stated plainly

- **D1 is perceptually correct but not metadata-correct, by design.** The blind repair widens S8 to distance
  0.89 — the nearest distance that satisfies the "wide" framing constraint — not the authored 1.35. Both frame
  the shot correctly; a repairer with no answer key legitimately lands on a different passing value. This is
  why the benchmark grades "satisfies the constraint" and "reproduces the authored number" as two different
  things and does not claim one as the other.
- **"Perceptually correct" here means the deterministic proxy detectors pass**, not that a human watched a
  rendered video or listened to mixed audio. Verification is geometry render + rig pose + event-timing, not a
  full pixel render and not a listening test. A real perceptual check still needs rendered frames and audio.
- **D2's repair is a known remedy, not a computed value.** The *detection* is independent (measured skate), but
  the fix is the one canonical toggle, so it proves less about repair reasoning than D1/D3/D4 do.
- **D4's repair is not byte-identical to clean.** The clean contact had a main + light cue pair; the repair
  synthesises one clash cue at the contact. It is perceptually cued, not a reproduction of the original pair.
- **Scale is a proof of mechanism, not a statistic.** One camera shot, two blade contacts, one short film. It
  shows the detect→repair→verify loop works blind on these defect classes; it is not a measured success rate.

## Files

`tools/poc/make.py` (plant), `tools/poc/run.py` (blind detect + repair), `tools/poc/score.py` (independent
evaluator), `tools/poc/all.sh` (run all three films + score). Outputs under `output/poc/`:
`truth.json` (answer key), `detections-*.json` (what the repairer found), `score.json` (the grade).
