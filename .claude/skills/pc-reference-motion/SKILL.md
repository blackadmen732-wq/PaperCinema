---
name: pc-reference-motion
description: Turn a reference video of real sword work into a verified Paper Cinema move - measure its real timing with reanimate instead of guessing frame counts, then prove the rebuilt move matches. Use whenever a move should look like a specific piece of footage.
---

# Steal the timing, prove you stole it

Two ways a reference video becomes motion here, and they are for different things.

| | gives you | use it for |
|---|---|---|
| **capture** — `tools/mocap.py`, `tools/mocap_cmu.py` | the performer's actual joint angles | the movement *between* the cuts: walks, turns, recoveries, weight |
| **reanimate** — `.claude/skills/reanimate/` | the reference's real **timing, easing, sequence and stagger**, measured | the cuts themselves, which are hand-keyed because anime timing is not human timing |

Capture answers *what the body did*. reanimate answers *when it happened and how it accelerated* — and then **records your copy and compares it frame by frame** until the two agree. Its own rule is the same as this project's: "code plus evidence, never 'it looks about right'." Motion-faithful means every step within **±80 ms**, which at 24 fps is two frames.

## Why this matters more than it sounds

`docs/STYLE-AND-FIGHT-SYSTEM.md` gives a cut as 6 beats with frame counts — ready 12-24, wind-up 6-10, slash 3-5, hit-stop 3-6, follow-through 8-12, reaction 12-24. Those are **ranges somebody wrote down**, not measurements of any particular shot. A move built from the middle of a range is a move that feels generic.

reanimate replaces the range with the number, for one specific reference you liked.

## The loop

```bash
bash .claude/skills/reanimate/scripts/setup.sh         # once; installs playwright, ffmpeg, pixelmatch
```

1. **Scope it.** One move, one time range: *"the diagonal cut from 0:12 to 0:14"*. Not a whole fight.
2. **Capture the reference** at a known fps and crop. Keep the file; it is the evidence.
3. **Read the timing off it** — when the wind-up starts, how many frames the blade is actually moving,
   where the freeze is, how long the recovery takes, what the easing looks like.
4. **Build it as a MOVE**, not as pose keys in a film: a new entry in `library/moves.json`, beats with
   `dt`, `pose`, `ease`, `fwd`. That way every film that uses it improves at once. Existing moves are
   the template; all seven real cuts are already there.
5. **Record the copy and compare.** Your engine is three.js with `window.renderAt(t)` and every frame
   a pure function of time, which is the easiest possible case for a frame-by-frame comparison: ask
   for the same instants twice and you get the same pixels.
6. **Iterate until it passes**, then check it did not break anything:

```bash
node engine/validate.mjs film/<name>.json
node tools/jitter.mjs <name>          # TREMBLE must not rise
node tools/promises.mjs
```

## Rules for this project specifically

- **Reference the licence, not just the footage.** A move's *timing* is not copyrightable, but the clip
  is. Record the source in `library/mocap/CREDITS.md` the way the iaido capture does, and use
  CC-licensed, public-domain or Mark's own footage. `docs/ANIMATION-SOURCES.md` has the clean list.
- **Do not copy the pose, copy the clock.** The character is folded paper with a 25-bone rig; a human
  reference has different proportions and will not map pose-for-pose. What transfers is timing,
  stagger, easing and the *shape* of the acceleration.
- **Anime timing is not human timing.** A real cut does not have a 6-frame freeze in it. Measure the
  reference, then push it: that is what the `anime` dial on a clip move is for (1.2-1.4 reads as
  animation, past ~1.8 limbs break).
- **YouTube subtitles do not work from this container** (bot check on a datacentre IP). For a tutorial
  you need the words of, `vendor/faster-whisper` transcribes the audio locally instead.

## Sibling tool

`vendor/code-motion` (MIT) does the same for a whole shot rather than one animation — video in, a
shot-by-shot rebuild as code, out to MP4. Read its breakdown method when the question is "how was this
*sequence* put together" rather than "how fast was that one move".
