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
1. ✅ (Nov 26) Recipes `kojiro.json` (crimson haori #9c2a25, dark red hakama #5c2220, topknot) and `musashi.json` (slate
   indigo, grey-brown hakama #4b3e34, white headband = `hachigane` with `spine: false`); new sheets `washi_crimson`,
   `card_oxblood`, `card_umber`; `RECIPES` in `film_modular.py` points at them. `part_validator`: 407/407 and 420/420.
2. ✅ (Nov 26) Musashi's oar sword: `build_bokken` in `film_modular.py`, chosen when the timeline's weapon `kind` is
   `bokken` (a film's cast `"weapon": "bokken"`); ~15% longer than the katana, one piece of wood, no guard.
3. ✅ boat (Nov 26): kit piece `boat` (kobune: flat bottom, flared sides, rising bow, thwarts, stern oar) at `MARK_boat`,
   static (landed); camera `CAM_boat` frames it from the shoreline. ⬜ the thrown scabbard.
4. ⬜ Captions and the hook text burned in after the render (ffmpeg), inside the safe box.
5. ⬜ One music track, credited.

Also done Nov 26 for the world: the beach pines are kit `pine` pieces with real branches (`pines: "kit"`), the beach
grass is tufts of thin folded blades, open-sea foam patches are off (`foam: 0`), and the set is graded for a low red
sun (`lighting.note` in the set file has the measured luma before and after). Set previews can show the film
characters: `build_set.py --with-character foe:hasso:recipe=kojiro`.


## The Blender route (27 Nov, autopilot item 12) - what is built and what is left
One film, `film/ganryujima-ep1.json` (60 s, 30 fps, 9:16, on `engine/motion.html`), staged with `stage.origin` on
MARK_center so the film's coordinates are the set's map (the boat 13 m away, the waterline, the duel ground). Authored
by a generator during drafting; the JSON is the source.

| beat | s | shots (camera beats) | parts it uses |
|---|---|---|---|
| S1 hook | 0-3 | the Shiokaze tsuba, fast push · Kojiro dark against the sun, rising | the draw rig's sword, the generated tsuba |
| S2 waiting | 3-11 | wide from behind toward the sun · medium, the wind, he sees the boat | cloth springs |
| S3 the boat | 11-20 | low over the water · Musashi against the sun steps over the bow into the surf | the boat kit piece (moved to land its bow), the oar bokken, terrain follow (boat floor, surf) |
| S4 the meeting | 20-32 | behind Kojiro, Musashi walks up from the sea · the draw · the throw · the line · anger | the draw, **the thrown scabbard** (new), the 180-degree line kept |
| S5 one strike | 32-42 | the charge · the impact in profile (slow motion, hit-stop) · Musashi in zanshin, the headband falling · the fall | **measured body impact** (new), **the headband cut** (new: the band's paint leaves the generated head) |
| S6 after | 42-55 | crane up over the fallen · Musashi walks back to the sea | walk on the slope |
| S7 end | 55-60 | the last shot lives, the end card | titles |

New parts (each a library feature, data-driven):
- `performances.<id>.throwSaya {grab, release, to, apex}`: sword_draw.Draw carries the scabbard in the left fist and throws
  it on a ballistic arc (spinning, slowed by speed ramps) onto the sea / sand; the bake records the splash.
- `performances.<id>.drop [{part, t, v, spin, drag, paint}]`: a part leaves the body and falls with air drag; with `paint`
  only the faces painted like that leave (the band baked into Musashi's generated head) and the head's paint shows hair there.
- `impacts[{t, at: "hero.head"}]`: tools/bake_events.py measures when the striker's weapon reaches that capsule; without
  a blade contact it drives the hit-stop, the slash and the score's silence.
- `titles[]` burned in by tools/titles.py (film.sh step 5c); `score{}` synthesized by tools/score_synth.py (step 8).
- `stage.origin`, `stage.offset`; the camera on terrain (item 13).

Left: the preview render (360x640 here, ~8 h CPU), watching it frame by frame, fixes, then the 1080x1920 final on a rented
GPU (a new paid service: Mark decides).

## Order
1. Shot 2 as one still (Kojirō waiting, vertical, dawn): tune the look knobs to the numbers → Mark sees it.
2. Recipes + the oar sword (parts 1–2), checked on a turnaround.
3. Choreography shot by shot on `engine/motion.html`; `validate`, `audit`, `camera_check` per shot.
4. Full preview here at 360x640 (stills first, `bash tools/shotsheet.sh`).
5. The GPU route (blocker 3), its cost measured on this film.
6. Captions, music, mix → `episode_check.py` → watched → Mark.
