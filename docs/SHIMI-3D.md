# SHIMI on moving 3D paper characters: design

From a technical-director design review (Fable). Constants marked *estimate* need calibrating. Status per milestone is at the end.

## 1. Space: simulate in each part's UV space, made by unrolling the part
- **Why UV:** a faceted paper prism or cone *is* a folded flat sheet, so its unrolled UV is the real sheet and a 2D sim
  there is physically correct with no stretch. The stain moves with the part automatically.
  - Camera projection is rejected: it swims and breaks on turn-arounds.
  - A 3D point-cloud sim is rejected: it's slower and loses the fibres.
- **Unwrap:** a UV layer named `shimi` per part, one seam down the back, folds are not seams, caps get their own island.
- **Sim window:** fixed at event start: the cut plus its expected reach.

| Shot | mm per texel | Window |
|---|---|---|
| Wide | 2 | 256² |
| Mid | 1 | 512² |
| Close | 0.5 | 1024² |
| Macro | 0.25 | 2048² |

- **Seams:** an island-ID mask plus a **barrier along the cut** (severed paper carries no flow).
- **Gravity in UV:** bake per part `M[H,W,2,3]` (pseudo-inverse of the face tangents). Per step `G = M @ g_local(t)`,
  where `g_local = R_part(t)⁻¹ · down`. A rigid part needs one 3-vector per frame and no rebake.
  **Built:** `--gravity-map` accepts a per-texel gravity field (`.npy`, N×N×2), and `--gravity-dir` a uniform one.
- **Skinned meshes later:** an event-local tangent-plane UV layer around the wound; rebake M every frame.

## 2. Mapping the cut
One mapper emits event data that both renderers read:
`{"id":"kesa-1","type":"cut","part":"torso","t":12.40,"seed":7,"window":[…],"mm_per_texel":0.5,"polyline":[{"u":…,"v":…,"depth":…,"t":…}]}`

- **Blender:** unwrap before cutting, then one `bmesh.ops.bisect_plane` (it interpolates UVs). Read the UVs of the cut edges from `res['geom_cut']`, order the chain, then split. Both halves keep the same UVs and texture.
- **Blade sweep:** sample at 240 Hz. A point's `t` is when the blade passes it; `depth = clamp(penetration / 30 mm)`.
- **Stab or touch:** `ob.ray_cast` gives a face, and its UVs are interpolated.
- **three.js:** plane–triangle intersection in part-local space (lerp `uv1`), and `Raycaster` for stabs and touches. Share geometry between the renderers via glTF.

## 3. Time and motion
- **Sim clock:** time integrated from the event: rate 1 normally, 0 in hit-stop, the timewarp factor in slow motion. Drying compression is an evaporation multiplier.
- **Cache:** `output/shimi/<film>/<event>/<part>/` with a `meta.json` hash. If the hash matches, skip the sim. A checkpoint lets a second event resume on the same part.
- **Fast motion:** the surface film sees `g − a` (the part's acceleration), so it sloshes for free.

## 4. Blender shading (`paper_mat_shimi`)
- **Textures:** image sequences (Non-Color, CLIP), `image_user.frame_start` = event frame, read through a `ShaderNodeUVMap('shimi')`.
- **Colour:**
  - Base = paper × T^(1.6·pigment) × (1 − 0.15·C) × tide line
  - Translucent colour = paper × T
  - Translucency mix 0.38 → 0.75 with wetness C. The amber halo and red core come from the interior light alone.
- **Surface film S:** coat weight = smoothstep(S), coat roughness 0.05, and a coat normal from S only.
- **Bump and cockle:**
  - Shared `fibre.png` bump, so the sim and the shader use the same fibres.
  - Cockle as bump for mid shots; real displacement for close shots (simple subdivision 5–6, displacement BOTH).
- **Plausibility:** Mix only, never Add. No Emission in the paper. The flash stays a separate strip.

## 5. three.js preview
Play back the same cache (not a GPU port, so both renderers match). Patch `paper.js` with `onBeforeCompile`: pigment tint, roughness from the film, glow × translucency.

## 6. 3D paint on top
- **Rule:** the texture carries anything under 0.5 mm or 2 screen pixels; 3D is only for silhouettes (beads, spurt arcs, drip heads, pools).
  - Wide shots: none.
  - Mid shots: up to 9 beads and 3 runs.
  - Close shots: everything.
- **Drinking:** SHIMI owns the volume. Beads shrink as the paper drinks them: `dV/dt = well − k·perm·(Cmax − C)·πr²`. Beads are written per frame to `beads.json` for Blender metaballs.
- **Drops** that detach make `drop-landed` events, which become new point sources.
- **Contact stains (`touch`)** use fingertip rays (*estimates*):
  - surface film: 50% transferred on first contact, then 10% per frame
  - capillary water: 5% per frame
  - dry paint: 0 (2% if the receiver is wet)

## 7. Realism test plan
- **Reference:** shoot vermilion ink and sumi on 30–40 g/m² kozo washi at 60 fps with a mm ruler.
- **Metrics** (`tools/shimi_measure.py`, planned):
  - wicking front ∝ t^0.5 ± 0.07
  - along/across-fibre reach 1.5–3
  - water ahead of pigment 1–4 mm
  - rim density ratio 1.3–2.0
  - water and pigment conserved
  - resolution independence
  - identical hashes for the same seed
- **Shader tests:** lights off → black; interior light only → halo brighter than paper, core red; white furnace test.
- **Typical failures:** swimming, seams, blur, the stain left behind after the bisect, drips running uphill.

## 8. Milestones
| # | Milestone | Status |
|---|---|---|
| M1 | SHIMI v2 core | **Partly built:** two water layers, saturation-limited wicking, edge evaporation (tide lines), gravity field (`--gravity-dir` / `--gravity-map`), `film` map. To do: Sheet class, mm and seconds, island mask and barrier, timed polyline sources, checkpoints |
| M2 | Blender stills of a stain on the warrior's cut torso | **Next** (not built yet) |
| M3 | Animated Blender clip | planned |
| M4 | three.js integration | planned |
| M5 | Film events (`cut`, `stab`, `touch`, `drop-landed`) | planned |
