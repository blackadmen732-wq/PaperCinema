# Every problem, and everything still missing

Measured against the repo on 2026-11-25. Nothing here is a guess: each line says how we know.
Ordered by how much it changes what you see, not by how hard it is.

**Legend** · 🔴 broken or missing · 🟡 works but weak · 🟢 fine · 💲 costs money · 🖥️ needs a GPU

---

## 1. Character

| | Problem | How we know | Fix |
|---|---|---|---|
| 🔴 | **The films use the wrong character.** Two character systems exist. The three.js one is boxes; the Blender modular one has real folds. **Every film renders the boxes.** | Compare `output/stills/blotwide4-t3.png` (films) with `output/engine-ab/ronin-design.png` (Blender). | Wire the Blender character into the film pipeline, or port the part shapes to three.js. **The single biggest visual jump available.** |
| 🔴 | **Hakama pleats are front-only.** From the side the folds vanish; from behind the legs are plain tubes. | Turnaround test, `docs/PHASE1-VERDICT.md`. Matters because `orbit` is the most-used camera at 71.4 screen-seconds. | Back pleats. *On the free worker now.* |
| 🔴 | **The kimono back is one flat slab.** No seam, no shoulder yoke. | Same turnaround, back view. | Add a back seam and yoke to `kimono_layered`. |
| 🟡 | Only two paper families: washi and card. | `library/paper-materials/` has 7 sheets, all washi or card. | Add kraft, painted, embossed, weathered. These are JSON, not code. |
| 🟡 | The sword reads as a grey rectangle from the side. | Turnaround, side view. | Give the blade a ridge (shinogi) and the guard real thickness. |
| 🟢 | The material engine itself | All ten controls the spec asks for already exist | — |

## 2. Movement

| | Problem | How we know | Fix |
|---|---|---|---|
| 🟡 | **Poses are still hand-typed numbers** for everything except the four recorded swordplay moves. | `film/*.json` keys are literal joint angles. | More capture. `tools/mocap.py` works on CPU today; `mixamo-llm-mocap` is far better 🖥️. |
| 🟡 | **The recorded swordplay barely moves its feet** (0.16 m) — it is fencing in place. | `docs/MOVES.md`, measured. | Keep authored moves for footwork; recorded ones drive the arms. |
| 🔴 | **No cloth cutting.** A blade passes through a sleeve and nothing happens. | No code path exists. | Blade contact already fires at 240 Hz; split the sleeve mesh at the contact point like the paper trees already do. |
| 🟢 | Feet planted, sleeves trail, anime timing, contact detection | measured: 81–95% less slide; drag adds 0–67° | — |

## 3. Ground

| | Problem | How we know | Fix |
|---|---|---|---|
| 🔴 | **The ground does not react.** Landings, skids and dashes are all detected and nothing happens to the floor. | `analyseGround` emits `land`, `skid`, `dash`, `wake` with position, direction and speed. Only dust listens. | Dent the ground on landing, spray a trail on skid. **The events are already there — this is the cheapest big win in the whole list.** |
| 🔴 | No footprints, no displaced snow or sand. | Same. | Same system. |
| 🟡 | The dune is low-poly with hard facet edges visible at close range. | `output/stills/blot5-t2.6.png`. | More subdivision near the camera, or accept it as a paper fold. |
| 🟢 | Paper blotting and real surface relief | — | — |

## 4. Water

| | Problem | How we know | Fix |
|---|---|---|---|
| 🟡 | **Water has no layers.** It is one sheet with a moving crest. Your pop-up card is four sheets and reads instantly. | `engine/world.js`; compare the cherry-blossom card photo. | Stack 3–4 cut sheets per wave with visible card edges. |
| 🔴 | Nothing splashes, ripples or foams when anything touches it. | No contact path to the sea. | Same event system as the ground. |
| 🔴 | No waterfalls, rivers or still ponds. | Only the Ganryūjima sea exists. | Build them from the same layered sheets. |
| 🟢 | The crest travels through the water instead of the sheet sliding | — | — |

## 5. Sky

| | Problem | How we know | Fix |
|---|---|---|---|
| 🔴 | **The moon is a flat disc.** No craters, no paper layering, no glow bleed. | `engine/world.js`, `kit.py` `moon`. | Layer it: a cut disc, a second sheet behind for the halo, cut craters as holes. This is where a paper moon beats a realistic one. |
| 🔴 | **Clouds are painted on the sky, not built.** | Sky is a gradient texture. | Cut-paper cloud cards at several depths, drifting at different speeds. The parallax is what sells distance. |
| 🟡 | One sky mood per film, no presets. | `mode: "dawn"` is the only control. | A sky preset family: dawn, noon, sunset, moonlit, storm, snow. |
| 🔴 | No stars, no birds, no falling petals. | None exist. | Cheap, drawn, event-free — pure time functions. |

## 6. Effects

| | Problem | How we know | Fix |
|---|---|---|---|
| 🔴 | **No sand, no cracks, no debris on impact.** | Only dust, sparks, ribbons and the ink frame exist. | Drawn effects on the existing event list. Grease Pencil is the right tool and the skill is now installed. |
| 🟡 | Sword trails are thin ribbons, not paper strips. | `engine/combat.js`. | Cut-paper trail shapes. |
| 🟢 | Contact detection, hit-stop, camera punch, ink frame, SHIMI | — | — |

## 7. Camera and sound

| | Problem | How we know | Fix |
|---|---|---|---|
| 🔴 | **No music at all.** | Nothing in the repo. | ACE-Step 1.5: MIT weights, commercial-safe, runs on CPU. |
| 🟡 | 38 sound effects, no foley variety by surface. | `assets/sfx/`. | Different footsteps for wood, sand, snow, stone. |
| 🟡 | Voice exists but is barely used. | ElevenLabs connected 💲. | — |
| 🟢 | Camera rigs, the evaluator that rejects bad shots, automatic clash sound | — | — |

## 8. Compute — the one wall behind half this list

| | Problem | How we know | Fix |
|---|---|---|---|
| 🔴 | **No GPU.** 4 CPU cores, no `/dev/dri`. | Measured. | A rented RTX 3090 is $0.07–0.18/hr with 24 GB. |
| 🔴 | **Kaggle's free T4 render fails.** 30 free hours a week, unused. | `docs/KAGGLE-RENDER.md`: the kernel cancels 11–18 s in. | Worth one more attempt. It is free. |
| 🟢 | The render farm now runs shots in parallel and prices the job first | — | — |

---

## The honest ranking

If only five things get done:

1. **Put the good character in the films.** Everything else is polish on boxes.
2. **Make the ground react.** The events exist; nothing listens.
3. **Layer the water and the moon.** Paper beats realism here, and it is free.
4. **Fix or retire the free Kaggle GPU.** It gates half the list.
5. **Music.** A silent duel feels unfinished no matter how good it looks.
