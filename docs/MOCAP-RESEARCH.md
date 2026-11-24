# MOCAP RESEARCH: what the other markerless systems do that `tools/mocap.py` does not

Findings from reading two capture systems end to end, for the owner filming himself with one phone.
**Nothing here was applied to `tools/mocap.py`** (another agent owns that file). This page is the shopping
list, with the licence of each idea's source. The guide to our own tool stays `docs/MOCAP.md`.

Sources read: **RGB MoCap** (github.com/toyxyz/toyxyz_RGBMocap, app code MIT, models mostly NOT commercial —
see §3) and **FreeMoCap** (github.com/freemocap/freemocap, AGPL-3.0). Neither is installed as a dependency.

## 1. The seven techniques worth taking

Ordered by what they would buy us, on our 4-core CPU, with one phone.

### 1.1 One Euro filter on the raw landmarks (free, ~20 lines)
RGB MoCap's live path (PEAR) runs a **One Euro filter** on landmarks before anything else. It is an adaptive
low-pass: when a joint is nearly still it filters hard (kills tracker jitter), when a joint is moving fast it
barely filters at all (no lag on a cut). Our pipeline smooths after solving and then simplifies with
Douglas-Peucker at `--tol`, which removes jitter only by also removing real detail — a fast cut is exactly
where our tolerance hurts most. A One Euro pre-filter on the landmark stream would let `--tol` be tighter.
The algorithm is a published two-parameter filter (`min_cutoff`, `beta`); no code needs copying.

### 1.2 Fixed bone lengths before solving ("Reset Bones")
Both systems enforce **constant limb lengths across the whole take** before fitting a skeleton. A monocular
tracker's depth guess makes a forearm breathe by several centimetres per frame; every one of those
centimetres becomes rotation noise in a two-bone IK solve. Measure each limb once (median over the frames
where the limb is most side-on to the lens), then force it. This is the single cheapest accuracy win.

### 1.3 Derive root travel from the planted foot, not from the pelvis
We measure travel by projecting the pelvis against a still camera, which is why `docs/MOCAP.md` needs
`--hfov`, `--tilt` and `--floor-slope` and still warns about guessed depth. RGB MoCap instead solves
**contacts first** (which foot is planted, when), then anchors the planted foot in world space and derives the
root from it. A planted foot cannot slide, so the travel comes out of the geometry instead of out of a lens
estimate. We already compute `contacts` per frame — the data is there, it is only used for reporting.
Its two ground modes are worth copying as a flag: **Flat Ground** (one floor height for the whole take) and
**Multi Level** (keep each contact's inferred height; it explicitly does *not* try to rebuild terrain).

### 1.4 Do not smooth after the contacts are solved
RGB MoCap's rule, stated plainly in its agent guide: *keep stance anchors, their timings and the source ankle
frames fixed; do not smooth the final output.* Smoothing after foot-locking puts the slide straight back in.
If we adopt 1.3, any post-smoothing must skip the root and the ankle channels.

### 1.5 Say which lock is which
It separates **pelvis locking** (hold the hips still, for an in-place loop) from **foot locking** (hold the
contact foot still, for travel) and warns that pelvis locking legitimately changes positions. Our `--no-root`
is really pelvis-locking; naming it that way would stop the next person expecting it to stop foot sliding.

### 1.6 Frame interpolation before tracking, for the fast frames
`docs/MOCAP.md` already says a fast cut lasts 3–4 frames at 24 fps. RGB MoCap offers optional **RIFE**
interpolation of the clip before detection, so the tracker sees 2× or 4× the frames through the fast part;
the result is resampled back to the film rate. Worth it only for the cut itself, and only if a licence-clean
interpolator is used — RIFE's code is MIT but **its weights are a separate grant**, so check the checkpoint,
or use `ffmpeg -vf minterpolate` (LGPL/GPL ffmpeg, no model weights at all) and measure whether it helps.

### 1.7 Horizon/gravity from the image instead of `--tilt auto`
It uses **GeoCalib** to get the gravity direction and the ground plane from the background before fitting,
rather than guessing the tilt from straight-leg frames as our `--tilt auto` does. Check GeoCalib's own licence
before use. Cheaper alternative with no model at all: ask the performer to lay a straight object (a shinai, a
broom) on the floor in the first frames and read the floor plane off it.

Two more, only if the owner ever films with two phones: **self-calibrating two-camera setup** (the calibration
comes from the person's own body across the two views, so no printed ChArUco board is needed) with **audio
sync** (a clap) and **automatic focal length**. FreeMoCap does the same job but the hard way — see §4.

## 2. What our tool already does better for this use

* Single camera, 4 CPU cores, ~17 frames/s with the `full` model — no GPU anywhere in the chain.
* Apache-2.0 model (MediaPipe via litert-community), which is the whole point: see §3.
* It outputs **our channels** (`stance`, `crouch`, `weight`, `stride`, `phase`, `ry`), not a generic skeleton,
  so `tools/mocap_film.py` plays it on our figure with no retarget step.
* `--as-move` writes a `library/moves.json` move directly.

## 3. Why RGB MoCap itself is not installable here (licence, then machine)

Its own code and docs are MIT, but `THIRD_PARTY_NOTICES.md` is explicit that the grant "does not relicense
third-party code, upstream-derived modifications, model weights or body data". The backends it exists to
drive are research-only:

| Component | Terms |
|---|---|
| GVHMR, ExMR, FootMR | educational / research / nonprofit only; derivatives must be noncommercial |
| PromptHMR | non-commercial scientific research licence |
| MAMMA | registered noncommercial/restricted software **and** weights |
| SMPL / SMPL-X / SMPL-H / MANO | registered body models, noncommercial Model & Software terms |
| VGGT-Omega | FAIR Noncommercial Research Licence |
| HTD-Refine | AGPL-3.0-only |
| Ultralytics YOLO | AGPL-3.0 including the pretrained weights, or a paid licence |
| Sapiens2, SAM 3D Body, SAM 3.1, DINOv3 | each its own Meta licence |

For monetised Shorts (AGENTS.md rule 6) that is a hard no on the whole stack. It is also a native **Windows**
app built around a CUDA GPU; the Linux route is an experimental AppImage tested under WSL. **Study only** —
which is all it was asked for. Two of its parts *are* clean if ever wanted on their own: **Kimodo
MotionCorrection** (Apache-2.0, the contact/foot correction backend) and **HandFlow/HaMeR** (MIT source,
weights separate).

## 4. FreeMoCap: installed, and why it still does not help one phone

AGPL-3.0. Installing and *using* it to produce motion data for a film is fine — the AGPL covers the program,
not the numbers it prints, and §13's network clause only bites if we offered a modified FreeMoCap as a
service. Vendoring any of it into this repo is not fine.

`pip install freemocap` (v1.0.28) resolves on this machine in a venv; it pins `numpy<2` against our system
numpy, so it needs its own environment. It is a GUI application (Qt) built around **SkellyCam**, which drives
several USB cameras at once.

The blocker is physical, not legal: FreeMoCap's 3D output is **multi-camera triangulation**. The documented
workflow is: connect two or more cameras → record a **ChArUco board** waved in front of all of them →
automatic intrinsic/extrinsic calibration → record → triangulate. With one phone there is nothing to
triangulate, so you get 2D landmarks — which is what `tools/mocap.py` already gets from the same family of
model, without a GUI, a board, or an AGPL dependency.

**Verdict for the owner filming himself with one phone: no.** It becomes interesting only the day there are
two phones on tripods and a printed ChArUco board, and even then its own add-on exports to Blender, so we
would import BVH — a path `rig_trellis.bvh_motion()` already has. Worth remembering: Rigger (see
`docs/TOOLS-EVALUATED.md`) has a one-click **FreeMoCap import**, so that route is free if it is ever wanted.
