# Episode 1: Ganryūjima — the plan, the blockers, the order (Nov 26)

The first finished, postable Paper Cinema film. Nothing new is built until this exists (Mark, Nov 26:
"can you fix it, make it better"). Every line below was measured on 26 Nov; see "How we know".

## Done when (all measured, none claimed)
- `python3 tools/episode_check.py output/ganryujima-ep1-final.mp4` passes: 1080x1920, 45–60 s, H.264 + AAC, −14 LUFS.
- `node tools/promises.mjs --check-character` passes: the modular paper characters in every shot, no boxes.
- Staged on the `ganryujima-beach` set's marks, with cameras aimed for vertical.
- A hook (picture + words) in the first 2 s; captions inside the safe box; the signature end card.
- A music bed (CC0 or licensed, credited in `assets/`) under the existing sword sounds.
- History said the way `research/ganryujima.md` marks it: tradition is said as tradition.
- `engine/validate.mjs`, `tools/audit.mjs` and `tools/camera_check.mjs` pass; watched frame by frame before Mark sees it.

## Three blockers found on 26 Nov, and the way round each

| # | Blocker | How we know | Way round |
|---|---|---|---|
| 1 | **The story films cannot drive the paper character.** `ganryujima` and `kuroko-duel` run on `engine/index.html`; their timeline has `bones` but no `pose` channels, and `blender/film_modular.py` needs `pose`. | `node tools/timeline.mjs film/ganryujima.json`, then `film_modular.py --film ganryujima` stops on `KeyError: 'pose'`. Actor keys in that timeline: `hidden, root, ry, bones, weapon`. | Episode 1 is a **new film on `engine/motion.html`** (the engine `dash-test` uses, which exports `pose`), not a port of the teaser. The teaser's shot list and research are reused as the script. |
| 2 | **Films are not staged on set marks.** A film's coordinates and cameras belong to the browser world it was written in. | `dash-test` rendered inside `ganryujima-beach`: luma median 0–1 of 255 at 360x640 (frames 31 and 161) — the camera looks into a dark dune, away from the dawn. | Block every Episode 1 shot on the set's own marks — `MARK_hero (-1.8, -3.2)`, `MARK_foe (1.8, -3.2)`, `MARK_boat (-9, -14)`, `MARK_shore (6, -9)` (Blender metres) — and start from its cameras `CAM_wide` / `CAM_medium`. |
| 3 | **This machine is too slow for the final render.** No GPU, 4 CPU cores. | One 360x640 frame with the beach set: 33 s with 4 threads (Cycles, 16 samples). In the parallel pipeline, 3 workers × 1 thread: about 140 s per frame each. | Preview here at 360x640. The final 1080x1920 render goes to a rented GPU: budget up to $10/week (Mark, Nov 26), cost measured on the first render, always asked first. Needs the RunPod key and a way to move the job and the frames (pods answer on per-pod `*.proxy.runpod.net` hosts). |

Also seen: `blender/world/toon.py` (toon ramp + ink outline) is used only by `blender/character/trellis_shot.py`, never by a
film; the film renderer now takes an `outline` width (below). The bloom/vignette `post()` IS wired into films (it was not when
`docs/WHY-IT-LOOKS-FLAT.md` was written).

## The look knobs (added 26 Nov)
`blender/film_modular.py` reads `lighting.film` from the set file (`library/sets/<set>.json`); a flag of the same name overrides
it for one render. Every default is "no change", so a set without the block renders exactly as before.

| knob | what it does |
|---|---|
| `ambient` | multiplies the sky's LIGHT on the scene, not the sky the camera sees (Light Path mix): darker fill, brighter separation |
| `sun` | multiplies the set's sun lamp(s) |
| `key` | multiplies each performer's key / fill / rim (`lighting.fighter`) |
| `outline` | ink line width in metres round every character part (a blade gets half) |
| `look`, `exposure` | the AgX look and the exposure the film is graded at |

Tuned on Episode 1's first shot against `docs/LOOK-TARGET.md` (luma 1% < 10, median near 50, 95% > 195), not on a test film.

## The beats (60 s, vertical, dawn — the "Desert Duel" panel of the worlds board: dark figures against a low red sun)

| # | s | picture | words on screen | sound | history mark |
|---|---|---|---|---|---|
| 1 | 0–3 | close: Kojirō's long blade leaves the scabbard, sun on the edge | "1612. One strike." | blade ring | tradition (the long sword) |
| 2 | 3–12 | wide: dawn over the strait, Kojirō alone on the beach, waiting | "Sasaki Kojirō waited. Musashi was late." | wind, waves | tradition (late) |
| 3 | 12–22 | low over the water: the boat; Musashi shaping an oar into a wooden sword | "He came by boat, with a sword cut from an oar." | oars, knife on wood | tradition |
| 4 | 22–32 | Kojirō throws his scabbard into the sea; Musashi: "You have already lost." | "As tradition tells it…" | splash | tradition |
| 5 | 32–42 | the clash: one strike, slow motion, the headband cut, paper shards and red paint | — | hit, silence, hit | tradition |
| 6 | 42–55 | Kojirō falls, his lantern goes out; Musashi walks back to the boat | "Kojirō died. The island still bears his school's name." | wind, music swell | documented (he died; the island is named Ganryūjima) |
| 7 | 55–60 | the signature end card | channel name, "Next: …" | the sound logo | — |

## Parts to build (data first, code only where nothing exists)
1. Recipes `library/character-recipes/kojiro.json` (cream kosode, crimson haori) and `musashi.json` (dark indigo kosode,
   brown hakama, white headband), each `extends` the ronin; point `RECIPES` in `film_modular.py` at them.
2. Musashi's oar sword: a wooden blade chosen by the film's weapon data instead of steel in `build_katana`.
3. In the beach set: the boat at `MARK_boat` (static is fine for v1) and the thrown scabbard.
4. Captions and the hook text burned in after the render (ffmpeg), inside the safe box.
5. One music track, credited.

## Order
1. Shot 2 as one still (Kojirō waiting, vertical, dawn): tune the look knobs to the numbers → Mark sees it.
2. Recipes + the oar sword (parts 1–2), checked on a turnaround.
3. Choreography shot by shot on `engine/motion.html`; `validate`, `audit`, `camera_check` per shot.
4. Full preview here at 360x640 (stills first, `bash tools/shotsheet.sh`).
5. The GPU route (blocker 3), its cost measured on this film.
6. Captions, music, mix → `episode_check.py` → watched → Mark.
