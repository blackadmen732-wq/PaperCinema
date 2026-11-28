# Head-to-head pilot: real numbers (28 Nov 2026)

Environment B only (Paper Cinema as it was), in a Claude Code cloud session, with the brief in
`docs/HEAD-TO-HEAD-BRIEF.md`. The pilot measured the pipeline and its cost. It did **not** fix any
defect, so it says nothing yet about self-correction or final quality.

## What it cost

| | |
|---|---|
| Claude usage (token-usage plugin, this session, before vs after) | 31 requests · 11,205 output tokens · 15.2M cached input tokens read · **$8.20** at API prices |
| Wall time | 13.5 min (05:26:48 to 05:40 UTC) |
| of which setup | 4 min: `npm ci` (three), linking the cached Chrome headless shell where Playwright expects it (Playwright's own download is blocked here) |
| studio audit | 234 s |
| render, 15 s at 720×1280 | 692 s (360 frames, 1.9 s per frame) |
| sound mix | 1 s |

The cost is **not** what a clean run would spend per step: the pilot ran in the session that did the
extraction, so every request re-read a very long context (about 490k tokens). A fresh session starts
small, so its steps should be cheaper, but it will also need more steps to learn the repo.

## What came out

- `output/head-to-head.mp4`: 15 s, vertical, with sound, 5.2 MB (output/ is not committed).
- `output/head-to-head.cues.json`: 14 cues (13 inside the 15-second window).
- The scene is the new-film scaffold (`node engine/new-film.mjs`) cut to its 5 s–20 s window, untouched.

## What the existing tools found (no human looked yet)

- **Studio audit: FAIL, 8.9/10.** 1 critical: no subject in frame for 72 frames (6.00–8.96 s).
  4 major: both of one fighter's hands jump about 0.7 m in one frame at 10.71 s; a hit at 10.80 s has
  no sound. 4 minor (shot size, lead room).
- **Fight Director: the clashes never touch.** The fighters are 2.40 m apart at the planned clash and
  can reach only 1.66 m, so 0 blade contacts were detected and **no clash sound was placed**. The
  brief's "a clash on every blade contact" fails.
- **Destruction beat:** only a headband cut (10.8 s); nothing falls. The brief's prop or paper panel is
  not in the scaffold.
- So **the scaffold Paper Cinema gives every new film fails its own audit and its own Fight
  Director** before anyone edits it. That is worth fixing whatever the head-to-head shows.

## What the pilot showed about the test itself

1. **Sound mixing breaks with no network.** One cue (`sig-shakuhachi`) had no cached file, the mixer
   tried to search Openverse, the lookup failed, and the whole mix stopped. Removing that one cue from
   the pilot film made the mix pass (16/16 cues). The mixer should skip a cue it cannot fetch. That file
   belongs to the Sonic task, so it was not changed.
2. **My sound-sync measure is not reliable yet.** Detecting audio onsets and matching them to cue times
   gave a median offset of 214 ms and a worst of 728 ms, but whooshes swell up to their loudest point by
   design, so an onset is not where the cue is aimed. The full test needs the visual contact frames from a
   pose track of the video (MediaPipe, `tools/mocap.py`), which is not installed here.
3. **Blender is not installed in cloud sessions**, so environment A cannot be offered Blender there.

## What the full test would cost, revised

At the pilot's measured rate (about $0.26 per request), a run that also fixes its defects and
re-renders (likely 100 to 200 requests, 3 to 5 renders of 12 min each) would cost about **$25 to $50**,
so **$75 to $150 for one run of each environment**. A fresh session per environment should come in under
that, since its context starts small. This is still an estimate; only the $8.20 above is measured.
