# Where fight motion can come from — and what you may legally sell

Researched 25 Nov. **Every licence below was read on the owner's own page, not recalled.** This
matters more than model quality here, because AGENTS.md rule 6 is that nothing in this project may
put a licence condition on work that gets sold, and Mark sells.

## The short version

Almost the entire modern motion-AI stack is **non-commercial**, because almost all of it depends on
SMPL or AMASS. The clean sources are the two this project already uses, plus one it does not.

| source | licence, verbatim from the owner | may you ship it? |
|---|---|---|
| **CMU Motion Capture Database** | *"This data is free for use in research projects. You may include this data in commercially-sold products, but you may not resell this data directly, even in converted form."* | **YES.** Already wired: `tools/mocap_cmu.py` |
| **MediaPipe Pose** | Apache-2.0 | **YES.** Already wired: `tools/mocap.py` |
| **Mixamo** (Adobe) | Free with an Adobe ID, royalty-free, no credit required; commercial use listed explicitly. You may not redistribute the raw files | **YES.** Not wired yet — the biggest clean win available |
| **SMPL** body model | *"This software/data and the associated license is for academic research purposes… also available for commercial licensing through Meshcapade.com"* | **NO**, unless you buy a Meshcapade licence |
| **AMASS** dataset | *"Dataset Copyright License for non-commercial scientific research purposes"* | **NO** |
| **HumanML3D** | MIT code, but the motion is AMASS-derived | **NO**, by inheritance |

## What that rules out, and why it is worth knowing

These are the impressive ones, and they are all research-licensed through the same two dependencies:

- **GVHMR** (ZJU3DV) — world-grounded motion from one camera, gravity-aware, the current best
  single-camera capture. Outputs **SMPL** parameters. Its checkpoints carry their own
  non-commercial terms.
- **WHAM**, **4D-Humans / HMR2** — same category, same dependency.
- **MoMask** (CVPR 2024, MIT code), **MDM**, **MoMADiff** — text → motion. The *code* is MIT; they
  are trained on HumanML3D, which is AMASS, which is non-commercial. MoMADiff's own authors say
  they cannot redistribute the datasets they trained on.

They are excellent and you may absolutely experiment with them. What you may not do is put their
output in a Short that earns money, without a commercial SMPL licence. If this project ever wants
that path, the one phone call is Meshcapade.

## The clean pipeline, in order of effort

1. **Mixamo — do this first.** A large library of combat and sword animations, free, royalty-free,
   commercial use explicit. Download as FBX, retarget to the 25-bone rig. `tools/mocap_cmu.py`
   already proves the retarget maths against this rig; an FBX/BVH importer is the same shape of job.
2. **CMU** — already working, already commercial-clean, and it has martial-arts and sword subjects.
   Underused: `library/moves/` is empty, so none of it is saved as a reusable move.
3. **Your own footage through MediaPipe** — Apache-2.0, no SMPL anywhere, and the motion is yours
   outright because you filmed it. The weakest capture quality of the three, and the only one with
   no licence question at all.
4. **Hand-authored moves** — the seven cuts in `docs/STYLE-AND-FIGHT-SYSTEM.md` (kesa-giri,
   shōmen-uchi, gyaku-kesa, kiri-age, yoko-giri, tsuki, iai). No licence, no capture, total control,
   and the only way the *anime* exaggeration gets in: real swordsmen do not move the way anime
   swordsmen do, which is the whole point of the style.

## What is actually blocking fights today

**Not the move library.** I claimed earlier that it was empty; that was wrong, and wrong because I
listed a directory `library/moves/` that does not exist instead of reading `library/moves.json`,
which does. It holds **26 moves**, and all seven cuts are among them:

| the cut | the move |
|---|---|
| kesa-giri | `kesa-giri` |
| shōmen-uchi | `lunge-shomen`, `kiri-oroshi` |
| gyaku-kesa | `spin-cut` |
| kiri-age | `rising-cut` |
| yoko-giri | `yoko-giri` |
| tsuki | `tsuki`, `rapid-thrusts` |
| iai | `nukitsuke`, `nuki-uchi`, `chiburi`, `noto` |

plus `step-in`, `step-back`, `jump-back`, `dodge-left`, `low-dodge`, `parry-high`, `bind`,
`stagger-back`, `linear-drive`, `calm-low-stance`, `sword-engage`, `sword-exchange`, `sword-press`,
`sword-recover`. A fight already can be written as a list of names.

**The gap is that the films barely use them.** Counted across the three real films:

| film | move keys | raw pose keys |
|---|---|---|
| `ganryujima` | **0** | 29 |
| `kuroko-duel` | 9 | 28 |
| `sword-mocap` | 4 | 4 |

The flagship film uses the move library **zero times** and is built entirely from hand-placed poses.
So the 26 moves have been written, tested and then bypassed, and every improvement to any of them -
the anime dial, the exaggeration clamp, the settle - reaches almost nothing anyone watches. It is
the same shape of failure as the character: a good system built and then not connected.

That is the work: rewrite the fights as move lists. It is not new capability, it is using what is
there, and it is the only way an improvement to one cut improves every film at once.
