---
name: paper-cinema-film
description: Make or change a Lantern Origami sword-duel film in this repo (Paper Cinema). Use whenever the task is a new film, a new fight, camera moves, character poses or motion, sound cues, titles, or rendering a film or stills. Covers the data files, the checker, the still-frame review loop and the render pipeline.
---

# Making a Paper Cinema film

Everything in a film is **data** in `film/<name>.json`. You direct it by editing JSON, then the engine renders.
Read `AGENTS.md` once per session (then `SYSTEMS.md` to find any system); this skill is the working procedure.

## Procedure (do every step, in order)

1. **Research** the story. Write `research/<name>.md`. Mark every fact *documented*, *tradition* or *our choice*.
2. **Scaffold:** `node engine/new-film.mjs <name> --jp 漢字 --en TITLE --sub "…" --next "Next: …"` (signature opening + fight body + end card). Field reference: `docs/FILM-FORMAT.md`.
3. **Cast:** pick characters, outfits and swords from `library/` (`characters/`, `outfits/`, `swords/`, `poses.json`).
4. **Choreography:** write `performances.<id>.keys` as `{ "t": seconds, "pose": "name" }` or `{ "t": seconds, "move": "jump-back" }` (moves: `library/moves.json`). When one fighter attacks, the other must react (parry, dodge, jump back). Follow the 6-beat
   Strike Grammar in `docs/STYLE-AND-FIGHT-SYSTEM.md`:
   - Ready: hold the stance 0.5–2 s
   - Wind-up: 0.2–0.4 s
   - Slash: 0.15–0.4 s
   - Hit-stop: repeat the same pose about 0.15 s later
   - Follow-through
   - Reaction

   Add `twoHand` windows while both hands hold the sword, and a `duels` entry so the fighters watch and react to each other.
5. **Camera:** direct it with the `scene-direction` skill (shot list, style, light, rhythm; tested rigs in `library/shots.json`, guide `docs/DIRECTION.md`). Prefer KUROKO rigs (`docs/CAMERA.md` section 7): match the feel to the move:
   - orbit + crane for standoffs
   - frame + dolly for cuts
   - track + torpedo for dashes
   - handheld for clashes and staggers
   - anchor for one-takes

   Keyframes are for hand-made moves. Add a `shakes` entry on every hit.
6. **Sound:** add `sounds` cues at the same seconds as the actions (swing, impact, steps, bed loops).
7. **Validate:** `node engine/validate.mjs film/<name>.json`. Fix every ✗ before rendering.
8. **Review stills (mandatory before any full render):** `node engine/render.mjs --film film/<name>.json --still auto`,
   then LOOK at every image in `output/stills/`. Check:
   - **Subject in frame:** fix `look`, `pos` or `fov`.
   - **Both hands on the handle:** check the `twoHand` window.
   - **Feet on the ground and knees bent in strikes:** check `stance`, `crouch` and `weight` (in the pose or as key overrides).
   - **The blade lands on target at the hit second:** adjust the pose angles, or check them in the pose gallery:
     `node engine/render.mjs --page engine/lineup.html --film film/lineup.json --query "show=poses&poses=a,b,c" --still 1 --prefix poses-`
9. **Render a section first** if the fight changed: `node engine/render.mjs --film film/<name>.json --from 24 --to 30 --out output/clip.mp4`.
10. **Vertical + thumbnails:** `node engine/render.mjs --film film/<name>.json --vertical --out output/<name>-vertical.mp4`, then `python3 engine/thumbnail.py film/<name>.json`.
11. **Full pipeline:** `node engine/make.mjs film/<name>.json` (check → stills → render → sound → playbook). It takes about 55 min per 36 s on this CPU.
12. **Commit and push.** Report what changed, where the video is, and which sounds need CC-BY credit (`assets/sfx/CREDITS.md`).

## Quality rules
- Amber glow = human, crimson = demonic power. Paper shards or red paint, never blood.
- Keep the camera on one side of the fighters' line unless crossing it on purpose.
- Every hit gets: a camera key on the hit second, a shake, an impact sound and a hit-stop (held pose).
- Never present tradition as documented history.
- Never start a paid GPU without the owner's explicit yes and a cost estimate (rule 1 in `AGENTS.md`).

## When something is missing
- **Where does X live?** `SYSTEMS.md` (or `systems.json`).
- **Cut wounds / paint stains:** `docs/SHIMI.md` (SHIMI presets and the frame-by-frame slash sequence).
- **A new pose:** add it to `library/poses.json`, then check it in the pose gallery.
- **A new location:** sets are still code in `engine/world.js`. Build one there, or ask the owner.
- **Realistic (Blender) renders:** follow `docs/BLENDER-PLAN.md`. Its scripts are not built yet (milestone M1 onward).

## Anime motion and clashes (new)
- Put `"motion": { "overlap": true }` in the film, and on strikes use `"ease": "snap"`, `"drag": 0` on the contact key, `"settle": true` after it, `"ease": "antic"` on the wind-up. Jumps: `"arc": <height m>` on the take-off key. See `docs/ANIMATION.md` §10.
- For a clash, add `"clashes": [{ "t", "until", "attacker", "defender", "s" }]`. Contacts are detected, then they drive hit-stop, sparks, the impact frame and the clash sound (`output/<film>.events.json`, read by `sound.mjs`). This runs in both engines (shared `engine/combat.js`): the main engine (example `film/kuroko-duel.json`: `cast` with `face: "eyes"`, `clashes`, `effects`, `autoSounds`, `fxBase`) and the motion page (`film/motion-test.json`). In `main.js` everything timed to the action is body time (hit-stops shift it); mark hand-placed sounds and fx events of an action with `"body": true`.
- Sounds: use our synthesised `clash-steel`, `clash-light`, `steel-scrape`, `whoosh-a/b/c`, `draw-shing` via `"sfx"`; never the old `blade-clash` (it is a slice). Known problems and fixes: `docs/FIX-LIST.md`.
