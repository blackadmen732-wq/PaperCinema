---
name: pc-measure
description: The measurement discipline for Paper Cinema - every claim has a command that proves it. Use BEFORE and AFTER any change to motion, look, camera or character. If a number did not move, the fix did nothing and gets reverted.
---

# Measure it, or you did not fix it

The single most expensive habit in this project has been changing something, believing it is
better, and moving on. Every real win on 25-26 Nov came from a number; every wasted hour came from a
guess. These are the numbers.

## The five commands

```bash
node tools/promises.mjs                  # every promise, each with a command that proves it
node tools/jitter.mjs <film>             # tremble, per joint. Capture noise vs intentional snap
node tools/jitter.mjs --all              # every film at once
bash tools/shotsheet.sh film/<f>.json --set <set>   # 6 real frames, one page, minutes not an hour
blender -b -P blender/check_sight.py -- --film <f> --set output/sets/<s>.blend   # can it be SEEN?
blender -b -P blender/skeleton_view.py -- --film <f>                             # the rig alone
```

## What each number means, and what good looks like

| measure | what it catches | good | bad |
|---|---|---|---|
| `jitter` TREMBLE | a joint vibrating while barely moving | **8%** (`ganryujima`, hand-keyed) | over 35% on any joint |
| `jitter` all-reversals | tremble **plus** intentional settle | only read it beside TREMBLE | — |
| luma median (whole frame) | a flat, grey, lifeless picture | **~50**, 1% below 10, 95% above 195 | median 83+, nothing near black |
| `check_sight` | the set hiding the fight | nothing on a contact frame | any CRITICAL |
| `promises.mjs` | a stated fix that silently broke | all ✓ | any REGRESSION |

Measure the frame with PIL, not by eye:

```bash
python3 -c "
from PIL import Image; im=Image.open('F.png').convert('L'); h=im.histogram(); n=sum(h); c=0
for i,v in enumerate(h):
    c+=v
    for q in (1,50,95):
        if f'p{q}' not in dir() and c>=n*q/100: print(q,'%',i); globals()[f'p{q}']=i"
```

## The rules that came out of doing this wrong

1. **TREMBLE is not SNAP.** A damped settle reverses acceleration — that is what a settle is. Counting
   every reversal calls the anime overshoot a defect. The tell is speed: noise flips while a joint
   barely moves (under ~12 mm/frame), a settle flips while it is fast.
2. **Correlation is not cause, and the test is cheap.** The overlap layer correlated perfectly with
   tremble across every film. Turning it on for the clean film moved 8% → 7%. Dead hypothesis, one
   command.
3. **Check what a fix COSTS, not only what it buys.** A wider capture smoothing window bought a point
   of tremble; peak blade speed stayed at 12.3 m/s, so it cost nothing and was kept. Soft IK alone
   bought calmer knees and cost wandering feet, so it was *not* kept until the stretch fixed the cost.
4. **Revert what you cannot prove.** Two rounds of noise-tuning on the paper texture made stucco, not
   washi. Reverted, and the finding written down so nobody repeats it.
5. **A check that cries wolf stops being read.** `check_sight` first reported 73 blocked frames, mostly
   a dust emitter that never renders. 73 false → 10 real. Fix the check before trusting it.
6. **Grep is not proof.** `films-use-good-character` passed by grepping a filename while three films
   shipped with the wrong character. Every check now reads the pipeline's own output.
