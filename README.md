# Paper Cinema

A system for making **cinematic paper-craft animated films**. Everything (characters, swords, sea, island, sky) is built from folded and layered "paper" in 3D, and a virtual camera moves through the world like a real film camera. Each frame is rendered and encoded into an MP4.

The first film is **Ganryūjima**: a 36-second teaser of the 1612 duel between Miyamoto Musashi and Sasaki Kojirō, grounded in historical sources (see `research/`).

## How the system works

```
research/*.md  →  film/*.json (shot list)  →  engine/ (paper 3D world + choreography)  →  output/*.mp4
```

1. **Research.** Facts and where they come from, each marked as *documented*, *tradition* or *our choice*.
2. **Shot list** (`film/ganryujima.json`). Like slides in a storyboard: each shot has a start/end time, camera keyframes (position, look-at point, lens/fov) and on-screen titles. **Edit this file to change camera moves or text. No code needed.**
3. **Engine** (`engine/`):
   - `paper.js`: washi paper textures and materials
   - `world.js`: layered cut-paper sea, island, pines, distant coasts, dawn sun, and the dark sword "studio"
   - `props.js`: the original sword "Shiokaze", Musashi's oar bokken, the boat and the oar
   - `figure.js`: rigged paper characters and the pose system
   - `main.js`: choreography (who moves when), camera, titles and effects
4. **Render** (`engine/render.mjs`). Opens the film in headless Chrome, renders frame by frame (deterministic) and pipes the frames to ffmpeg.

## Guides

- `docs/playbook.html`: the visual playbook (open in a browser): pipeline, live camera paths, fight beats, sound
- `AGENTS.md`: start here (for people and AI assistants): map, commands, rules
- `docs/CAMERA.md`: how to control the camera with data, plus recipes
- `docs/STYLE-AND-FIGHT-SYSTEM.md`: the Lantern Origami style and the fight system

## Commands

```bash
npm install
```

Render the full film (writes `output/ganryujima.mp4`):

```bash
npm run render
```

Render test stills at chosen seconds (writes `output/stills/t<sec>.png`):

```bash
node engine/render.mjs --still 2,11.5,25.7
```

Render only part of the film:

```bash
node engine/render.mjs --from 24 --to 30 --out output/clash.mp4
```

Add sound to the rendered film (writes `output/ganryujima-sound.mp4`):

```bash
node engine/sound.mjs
```

Live preview in a browser, then open the printed URL (add `?t=25.7` to freeze a frame):

```bash
npm run preview
```

## Shots in the Ganryūjima teaser

| Shot | Time | What happens | Camera |
|---|---|---|---|
| S1 | 0–6s | Dawn over the strait, title | Flies low over layered paper waves toward the island |
| S2 | 6–12.5s | The long sword | Macro dolly along the scabbard, then the blade is drawn |
| S3 | 12.5–17.5s | Musashi arrives late by boat | Tracks behind the boat through the waves |
| S4 | 17.5–24s | Kojirō draws and throws his scabbard; "you have already lost" | Moves around both fighters |
| S5 | 24–29.5s | One strike | Low close-up on the impact, paper-shard burst, camera shake |
| S6 | 29.5–36s | Musashi returns to the boat | Cranes up toward the sun, fade out |
