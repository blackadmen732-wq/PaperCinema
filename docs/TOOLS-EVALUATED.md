# TOOLS EVALUATED: nine outside tools, their licences, and what we kept

Every tool from the owner's research plan, checked against AGENTS.md **rule 00** (use what exists), **rule 2**
(free compute first) and **rule 6** (commercial use is required — the owner monetises Shorts). Licences were
read from the repositories' own `LICENSE` / `THIRD_PARTY_NOTICES` files and from model cards, **code and
weights separately**. Nothing below was taken on trust from a README badge.

Evaluated 2026-11-24 on this machine (4 CPU cores, no GPU, Blender 4.5.16 LTS) plus one free Kaggle T4.

## The table

| # | Tool | Code licence | Weights / assets | Safe for monetised video? | Installed | Tested on | Result | Verdict |
|---|---|---|---|---|---|---|---|---|
| 1 | **Epic BlenderTools** (`send2ue`, `ue2rigify`) | MIT | none | **Yes** | **Yes** — `~/.config/blender/4.5/scripts/addons/` | `rig_trellis` ronin + the dash motion → 3 FBX files | 3 files, **VERIFY PASS**: 175 cm, Z up, `root` at origin, 7.58 m root motion, 24 UE5 bone names, skin intact. Its animation writer is broken on Blender 4.5 | **KEEP** — its settings; `docs/UNREAL-EXPORT.md` |
| 2 | **Rigger** | **GPL-3.0-or-later** | optional AI marker/depth models, downloaded on click — not used | Yes to **use** (same as Blender itself); never vendor its code | **Yes** — extension `bl_ext.user_default.rigger` | 2 TRELLIS GLBs + the 52-part factory character; 8 stills | Auto-weights = ours; **voxel bind is worse**; Quick Rig re-segments our skeleton; 2/6 limbs found on the factory character | **DROP as a rigger**, keep as a utility (§2) |
| 3 | **FreeMoCap** | **AGPL-3.0** | MediaPipe (Apache-2.0) | Yes to use; never vendor, never offer modified over a network | **Yes** — venv, v1.0.28 | import only | Needs **≥2 calibrated cameras + a ChArUco board**. One phone gives 2D, which we already have | **DROP** for one phone; revisit with two |
| 4 | **RGB MoCap** | MIT (app only) | GVHMR / PromptHMR / MAMMA / SMPL-X / VGGT-Omega: **non-commercial**; YOLO: AGPL | **No** — the whole model stack is research-only | No (deliberately) | read end to end | 7 techniques extracted | **STUDY ONLY** — `docs/MOCAP-RESEARCH.md` |
| 5 | **TRELLIS.2-4B** | MIT | **MIT** (model card confirmed) | **Yes** — *if* `nvdiffrast`/`nvdiffrec` are left out (NVIDIA Source Code Licence, non-commercial) | Kaggle job written + pushed | `research/ref-origami-samurai-standing.jpg` | see §5 | **KEEP the job** |
| 6a | **cinematic-skills** (`shot-director`) | MIT | — | Yes | read | against `docs/DIRECTION.md` + `library/shots.json` | 1 table genuinely new (§6) | **PARTIAL** |
| 6b | **cinematic-skills** (`still-to-film`) | MIT | — | Yes | read | — | For still-image/AI-video pipelines; we render real 3D | **DROP** |
| 6c | **cinematic-3d-production** | MIT | — | Yes | read | against `docs/STUDIO-STANDARD.md` + `docs/AUDIT.md` | 250 lines of generic production advice; one real idea (§6) | **PARTIAL** |
| 6d | **PrevisForge** | MIT | — | Yes | **Yes** — `pip install -e`, demo built | `space-station` demo → Blender | Broken on Blender 4.5 (one line); its purpose is control video for generative models | **DROP the tool, keep one idea** (§6) |
| 7 | **FilmAgent** | upstream Apache-2.0; **the `pillar/filmagent` mirror has NO LICENSE file** | — | Study only | No | read | Maps onto our skills almost 1:1 (§7) | **STUDY ONLY**, one addition |
| 8 | **Fab** | Fab Standard Licence (Personal / Professional) or CC-BY-4.0 | per product | Yes, **with five pitfalls** (§8) | n/a — nothing downloaded | — | Licence rules established from the EULA itself | **USE WITH THE CHECKLIST** |
| 9 | **Unreal_Tools** | MIT | — | Yes | No (needs Unreal) | read (228 lines) | Exactly the two UE pieces we will need | **KEEP as reference** (§9) |

---

## 1. Epic BlenderTools — kept, and it produced a verified file

The full recipe, the settings table and the measured verification are in **`docs/UNREAL-EXPORT.md`**. The
short version:

* The add-on's value is `send2ue/resources/settings.json`: **Epic's own FBX export settings**. Those are now
  in `EPIC_FBX` in `blender/character/export_unreal.py`.
* The add-on's *patched exporter* is not the value. It monkey-patches `io_scene_fbx` to fix Blender-2.8-era
  scale bugs; on Blender 4.5 the settings alone already round-trip exactly right, and its vendored
  `fbx_animations_do` calls the pre-4.0 `add_keyframe()` API, so **any animated export through it crashes**.
  `--exporter epic` is therefore mesh-only; the default `--exporter blender` is what we use.
* Keep the add-on installed for the live **Pipeline > Send to Unreal** push, and `ue2rigify` for the
  Blender-side retarget, the day an Unreal machine exists.

Three files exist now and pass every check: `output/unreal/ronin_skeletal.fbx`, `ronin_dash.fbx` (root motion),
`ronin_apose.fbx` (retarget source), with `output/unreal/verify-*.json` beside them.

## 2. Rigger — it does not beat our rig, and here is the picture

GPL-3.0-or-later, like Blender. Using it to make a rig is fine and the rig is ours; **its code must never be
copied into this repo**, which is why it is installed as an extension and not vendored.

`output/rigger/rigger-compare.png` — **two** TRELLIS meshes (top row `ronin_base`, whose landmarks are hand-measured; bottom row `origami_samurai_s7`, the newest TRELLIS v1 model), one pose (`kiri-oroshi-contact`), one light. Both rows say the same thing:

| Panel | What | Result |
|---|---|---|
| A | ours: `rig_trellis` heat skin | the reference |
| B | our skeleton + Rigger **VOXEL** bind | **worse** — the shell tears into flying shards |
| C | our skeleton + Rigger **AUTO** (heat + proximity) | visually **the same as A** |
| D | Rigger's own rig (22-bone reference → **208-bone** control rig) + voxel bind | clean, but bind pose only (posing it needs its control rig or a retarget) |

Rigger's reference fitting (`fit_markers --fit_joints`, six markers placed from our own measured landmarks) produced the same 22-bone reference and the same 208-bone control rig on both meshes, and bound 39 vertex groups each time — so the auto-rig half is reliable. It is the *skinning* and the *bone topology* that do not pay.

Three measured findings:

1. **The voxel bind loses to our heat skin** on a TRELLIS mesh, despite being advertised exactly for "meshes
   that are not closed". Our `_clean_heat()` cleanup (rigid head and kasa, 4 bones per vertex) is doing real
   work.
2. **Quick Rig re-segments the skeleton.** Given our 24-bone rig it guessed 6 limbs and generated its own
   control rig whose `DEF-` bones do not map 1:1 onto ours (`DEF-shoulder` is our clavicle, `DEF-upper_arm`
   is our shoulder, and it merges our `hips`/`waist`). So its weights cannot simply be dropped back onto our
   skeleton — they need a retarget, which defeats the point.
3. **On the modular factory character** (23 deform bones, 52 separate meshes) Quick Rig found only **2 of 6
   limbs**. The factory character does not need auto-rigging anyway: parts are bound by construction
   (`docs/CHARACTER-FACTORY.md`).

The crumpled look in panel A is not a rigging failure, it is the mesh: one fused shell with no legs. No
auto-rigger fixes that, which is the whole argument for the part factory.

**What is worth keeping from Rigger** (as a tool on the shelf, not in the pipeline): `extract_root_motion`,
`apply_rest_pose` (keeps the animation), its retarget with auto bone mapping for Mixamo/Unreal/BVH skeletons,
its **FreeMoCap import**, and its game export (Universal/Humanoid, Rigger/Unreal/Unity/Godot names, UE IK
bones) if `export_unreal.py` ever needs more than it does now.

## 3. FreeMoCap — installed, and not useful with one phone

See `docs/MOCAP-RESEARCH.md` §4. AGPL-3.0 is not the blocker (using it and keeping its numbers is fine;
vendoring or serving a modified copy is not). The blocker is that its 3D output is multi-camera
triangulation: two or more cameras, a printed ChArUco board, automatic calibration. One phone yields 2D
landmarks, which `tools/mocap.py` already gets from the same family of model with no GUI and no AGPL.

Install note for whoever tries again: `pip install freemocap` (1.0.28) pins `opencv-contrib-python==4.8.*`,
whose wheel is built against numpy 1.x, so on Python 3.13 + numpy 2 it fails at `import cv2`. Forcing
`opencv-contrib-python==4.10.0.84` makes `import freemocap` succeed with a resolver warning.

## 4. RGB MoCap — study only, seven techniques extracted

Its own code is MIT but `THIRD_PARTY_NOTICES.md` says plainly that the grant does not relicense the models,
and the models it exists to drive (GVHMR, ExMR, FootMR, PromptHMR, MAMMA, SMPL/SMPL-X, VGGT-Omega) are
research/non-commercial; Ultralytics YOLO is AGPL **including its weights**. It is also a Windows CUDA app.

The techniques — One Euro filtering of raw landmarks, fixed bone lengths, deriving root travel from the
planted foot instead of the pelvis, not smoothing after the contacts are solved, naming pelvis-lock vs
foot-lock, frame interpolation through a fast cut, and reading gravity from the image instead of guessing the
tilt — are written up in **`docs/MOCAP-RESEARCH.md`**. `tools/mocap.py` was **not** edited (another agent
owns it).

## 5. TRELLIS.2 — the job, and the licence trap in its own README

**Code MIT. Weights MIT** (confirmed on the Hugging Face model card for `microsoft/TRELLIS.2-4B`, not just
the README badge). But the install line the README gives is
`setup.sh --new-env --basic --flash-attn --nvdiffrast --nvdiffrec --cumesh --o-voxel --flexgemm`, and
**`nvdiffrast` and `nvdiffrec` are under NVIDIA's Source Code Licence, which is non-commercial.** They are
imported only by `trellis2/renderers/*` and `trellis2/pipelines/trellis2_texturing.py` — that is, by the
preview renderer and the separate texturing pipeline. The path we need
(`pipeline.run(image)` → `o_voxel.postprocess.to_glb`) does not touch them.

So `gpu/kaggle_trellis2/` installs **FlexGEMM, CuMesh and o-voxel only**, writes no preview video, and does
the clay renders in Blender afterwards. A comment at the top of the job says not to add those two flags.

```bash
bash gpu/kaggle_trellis2/run.sh push      # ONE push: a push cancels the run before it
bash gpu/kaggle_trellis2/run.sh status
bash gpu/kaggle_trellis2/run.sh log
bash gpu/kaggle_trellis2/run.sh get       # → assets/models/origami_samurai_t2_s*.glb
```

Known risks on a free T4, written into the job: a T4 is Turing (sm_75), so **no flash-attn** (needs sm_80+,
`ATTN_BACKEND=xformers` instead) and **no native bf16**; 4B parameters in 16 GB with a 512³–1536³ voxel grid
is tight. The job prints `torch.cuda.is_bf16_supported()` and a CUDA memory summary per seed so the next run
knows exactly where it stood. Unlike the GPU runs in `docs/KAGGLE-RENDER.md` this one was **not** cancelled
in the first minute, so the weekly GPU quota is not exhausted.

**The v1 baseline to compare against is already rendered**: `output/character/clay-trellis-v1-baseline.png`
— `origami_samurai_s7` (37,745 verts / 58,246 faces) and `origami_samurai_s21` (28,540 / 43,586), front /
three-quarter / side, under one grey clay material and flat even light so only the geometry is being judged:

```bash
B=/opt/blender-dl/blender-4.5.16-linux-x64/blender
nice -n 10 $B -b -t 2 -P blender/character/clay_compare.py -- \
    --models origami_samurai_s7,origami_samurai_t2_s7 --views front,q,side \
    --out output/character/clay-trellis-compare.png
```

What the baseline shows, and therefore what v2 has to beat: **one fused shell**. The sleeves melt into the
torso with no seam, the hands are inside the sleeve rather than separate, the skirt is a single blob to the
floor with no legs in it, and the folds read as a smooth low-poly drape rather than as folded sheets with
thickness and dark seams. That is the same verdict `docs/CHARACTER-FACTORY.md` reached.

**Status of the TRELLIS.2 run:** Comparison against
`assets/models/origami_samurai_s7.glb` (TRELLIS v1) with neutral-light clay renders is the next step —
`run.sh get`, then the turnaround in `blender/character/rig_trellis.py` / the clay sheets in
`output/character/`. The question to answer with those stills: does v2 give **separated parts and crisp
folds**, or another fused shell? If it is still one shell, the part factory stays the answer and v2 is only a
nicer reference mesh.

## 6. The three agent-skill repos — mostly redundant, three ideas kept

All MIT. Said plainly, because the owner asked for it plainly:

**Redundant with what we already have.** Our `docs/DIRECTION.md` (shot sizes, an fov→lens table for 9:16 and
16:9, angles, the 180°/30° rules, 17 direction styles with sources and confidence marks), our
`library/shots.json` (49 named shots, each with `purpose`, `when`, `emotion`, `duration_s`, `fov`, and a
`beat_map`), our `.claude/skills/scene-writing/SKILL.md` (516 lines) and `docs/STUDIO-STANDARD.md` already
cover: camera-move vocabulary, choosing a shot by feeling or by beat, shot-list templates, pacing, a failure
checklist, intake/brief questions, delivery checks, contact sheets, and "watch the whole thing at normal
speed before you call it done". `cinematic-3d-production` is a 250-line generic production guide for someone
who has no pipeline; we have one. `still-to-film` is for turning stills into fake camera moves with a depth
renderer — we render real 3D, so it is not applicable at all. PrevisForge builds a whitebox to *steer a
generative video model*; our whitebox is the finished film.

**The three things genuinely worth having:**

1. **The look-alike pairs table** (`shot-director/references/moves.md`). Pan vs truck, tilt vs pedestal, zoom
   vs dolly, crane vs pedestal, barrel roll vs Dutch angle, POV vs FPV, dolly-zoom vs zoom, handheld vs
   gimbal, long take vs slow motion — each with the on-screen test that tells them apart ("near things
   sliding past the edges = dolly; everything enlarging together = zoom"). `docs/CAMERA.md` names the KUROKO
   rigs but never disambiguates the two moves that look alike, and that is exactly the mistake a model makes
   when it writes a camera. Worth a short table in `docs/CAMERA.md` §7.
2. **Scale needs a ruler** (`shot-director/references/time-and-space.md`). Every wide shot must carry a known
   size reference in frame or it does not read as big. For us: a lantern, a torii, a second figure.
   `docs/STUDIO-STANDARD.md` has staging rules but not this one.
3. **Overlap and camera-obstruction warnings at plan time** (PrevisForge's validator). `tools/audit.mjs`
   checks visibility on rendered frames; checking at *plan* time, before the render, from the shot's own
   numbers, is cheaper. A suggestion for whoever owns `tools/audit.mjs` / `engine/validate.mjs` — not edited
   here.

PrevisForge note for anyone who tries it: it hard-codes `scene.render.engine = "BLENDER_EEVEE"`, which
Blender 4.5 renamed to `BLENDER_EEVEE_NEXT` (its README says it was tested on Blender 5.1.2). With that one
line fixed it produced `scene.blend`, `scene.glb` and a poster from the `space-station` demo.

## 7. FilmAgent — the division of labour, mapped onto our skills

Study only (the `pillar/filmagent` mirror carries **no licence file**; the upstream HITsz-TMG repository is
Apache-2.0). Its three stages map onto what we already have:

| FilmAgent | Ours |
|---|---|
| idea development → casting, scene plan, lines (*director*, *screenwriter*) | `.claude/skills/scene-writing/SKILL.md` + `library/scene-templates.json` |
| `position_mark`, `action_mark`, `move_mark` (*actor* blocks on numbered marks in a fixed location) | `library/sets/*.json` marks + `blender/sets/build_set.py` (posed characters on marks) |
| `shot_mark` (*cinematographer* picks from a closed shot list, each shot carrying **usage conditions**) | `library/shots.json` — 49 shots, each already carrying `when` / `purpose` / `emotion` / `duration_s`, plus `beat_map` |
| Critique-Correct-Verify loops (3–4 rounds per stage) | `engine/validate.mjs` → `tools/audit.mjs` → the Fable review (AGENTS.md rule 01) |
| Debate-Judge (two agents argue, a third decides) | the Fable auditor as the judge |

**The one thing it has that we do not: hard sequencing rules between shots, written so a checker can enforce
them.** Not "this shot means intimacy" but "a Zoom may only follow a Long Shot", "a Track Shot may only be
the opening shot of a scene", "a Pan during dialogue must be used several times in a row", "no scene may be
mostly close and mid shots". We have per-shot conditions; we have no *between-shot grammar*. Adding a
`follows` / `only_at` / `max_per_scene` field to `library/shots.json` and a check in `engine/validate.mjs`
would catch the camera mistakes that today only a Fable review catches. Proposed, not built — `shots.json`
feeds systems owned by other agents.

## 8. Fab — what is actually free, and the five pitfalls

Nothing was downloaded, because a licence cannot be verified without opening each product page. What the Fab
EULA and Epic's own licensing documentation say (read 2026-11-24):

**Fab offers exactly two licence types.** *Creative Commons Attribution (CC-BY 4.0)*, always free; and the
*Fab Standard Licence*, free or paid, in two price tiers — **Personal** (buyers with **≤ $100,000 USD** gross
revenue from commercial activity in the last 12 months) and **Professional** (above that). **Both tiers are
commercial.** The Standard Licence lets you use assets commercially, distribute projects with the assets
incorporated, and use them **with any compatible tools — not only Unreal Engine**. You may not resell or
redistribute an asset standalone.

So for Japanese architecture and props: Fab's free Standard-licence and CC-BY listings **are usable in a
monetised Short, rendered in Blender**, and the Quixel Megascans library (17,000+ assets: stone, timber,
roof tile, moss, gravel, plaster — the surfaces a castle courtyard or a dojo needs) is on Fab under the
Standard Licence. Props and buildings are a per-listing question; there is no "free Japanese architecture"
category to point at.

**The five pitfalls, in the order they will bite:**

1. **The legacy UE Marketplace Licence.** Products migrated from the Unreal Engine Marketplace may still be
   under the old EULA, which restricts use to **Unreal Engine projects only** — fatal for our Blender
   pipeline. Epic notes this on the listing, in the Details panel on the right of the product page. Check it
   on every single product. Epic is phasing it out, but "phasing out" is not "gone".
2. **Megascans downloaded through Quixel Bridge are under the old Epic Content Licence** (Unreal only).
   **Adding the item to your Fab library is what applies the Fab Standard Licence** — downloading the files
   is not enough.
3. **The $100k threshold is yours, not the asset's.** It counts gross revenue from commercial activity in the
   last 12 months, for you *together with controlling and commonly-controlled entities*. Monetised Shorts
   count. Acquire at the wrong tier and the grant does not cover the use.
4. **"Personal — Reference Only"** (a UEFN tier) gives access to the asset **as a reference only**, not as a
   source asset to modify and ship. Read which version the product page actually offers.
5. **The NoAI meta tag.** An asset may be tagged NoAI, meaning it must not be used for generative AI data
   collection. Our pipeline feeds images to TRELLIS. A NoAI asset must never go near `gpu/`. (NoAI is only
   available on the Standard licence; CC-BY listings cannot carry it.)

**Plus the house rule:** CC-BY needs a credit line, like our CC-BY sounds (AGENTS.md rule 6). Anything taken
from Fab gets a row in `assets/` credits with its product URL, its licence type, its tier, and the date — the
licence shown on a page today is not evidence of the licence a year from now.

## 9. Unreal_Tools — small, and exactly the right two pieces

MIT, 228 lines, two files, and both are what we will need on the day:

* `Tools/Sequences/camera_and_sequences_creator.py` — spawns `CineCameraActor`s, creates a Level Sequence,
  adds a `MovieSceneCameraCutTrack`, and keys a `MovieScene3DTransformTrack` **frame by frame**
  (`tx/ty/tz`, `pitch/yaw/roll`). That is precisely the shape of a KUROKO camera export: our camera is already
  a per-frame transform in `output/<film>.motion.json`, so the port is a loop over our frames.
* `Tools/Sequences/MRQ_ue5.py` — allocates a `MoviePipelineExecutorJob`, sets map, sequence and
  `MoviePipelineOutputSetting.output_directory`, runs it with `MoviePipelinePIEExecutor` and takes a
  finished callback. That is headless rendering from a script, i.e. the Unreal equivalent of
  `engine/render.mjs`.

Nothing to install (it only runs inside the UE5 editor's Python). Kept as the reference implementation,
linked from `docs/UNREAL-EXPORT.md` §6.

---

## Where everything lives

| What | Where |
|---|---|
| The Unreal export recipe and its proof | `docs/UNREAL-EXPORT.md`, `blender/character/export_unreal.py` |
| The exported, verified FBX files | `output/unreal/*.fbx` + `verify-*.json` |
| Mocap techniques extracted from the research systems | `docs/MOCAP-RESEARCH.md` |
| The Rigger comparison stills | `output/rigger/rigger-compare.png`, `report-ronin_base.json` |
| The TRELLIS.2 Kaggle job | `gpu/kaggle_trellis2/` (`run.sh push / status / log / get`) |
| Installed Blender add-ons | `~/.config/blender/4.5/scripts/addons/{send2ue,ue2rigify}`, `~/.config/blender/4.5/extensions/user_default/rigger` |
