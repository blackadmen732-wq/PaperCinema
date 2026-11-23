# Effects catalogue: what each effect is for, and how to use `engine/fx.js`

The data is in `library/effects.json`: 42 named effects. Each one lists what it looks like, which story beat it
serves, how many frames it lasts, its parameters and defaults, which renderer can do it, and whether it is built,
new or planned. This guide explains the **FX** system (`engine/fx.js`), the post-processing module that both preview
pages can import. The demo is `engine/fx-demo.html` with `film/fx-demo.json`.

House rules apply to every effect: amber = human, crimson = demonic, paint and paper shards instead of blood,
vertical first.

## 1. What is in `engine/fx.js`

Everything is a pure function of film time `t`. There are no feedback buffers and nothing depends on the previous
frame, and particles and noise are seeded. So `renderAt(t)` gives the same picture in any order, and stills match the
video.

| Piece | How it works | Per-frame key |
|---|---|---|
| Bloom | three.js `UnrealBloomPass` (MIT) on the linear HDR image, before tone mapping | `bloom {strength, radius, threshold}` |
| Lens pass (one shader) | Chromatic aberration → grade (lift/gamma/gain, contrast, saturation, mono) → ink impact → speed lines → vignette → grain → flash/fade → letterbox, all in display space after `OutputPass` | `grade`, `ca`, `ink`, `speedLines`, `vignette`, `grain`, `flash`, `fade`, `letterbox` |
| Light shafts | Additive gradient cards from one light toward a target, each turned to face the camera around its own axis, with a slow flicker | `shafts {name: 0..1}` |
| Particles | One `Points` cloud per kind: `position = fract(seed + velocity·t)` inside a box, fading at the walls. Kinds: dust, ember, petal, snow, ash, shard | `particles {name: 0..1}` |
| Glint "ping" | Billboard 4-ray star with a diagonal pair and a core. It pops, peaks at 30% of its life, turns a little, and is sized in pixels | `glint {at, t0, dur, size}` |
| Shake | `shake(camera, t, {trauma})`: smooth seeded value noise, offset ∝ trauma², plus roll. `traumaAt(t, hits)` sums decaying hits | (call after placing the camera) |
| Timeline | `fxAt(t, track, base)` turns film events (`{t, effect, …}`) into the params above, with envelopes | — |

**Moods** (`MOODS`): `neutral`, `dawn`, `lantern` (warm human resolve), `moonlit` (cold dread), `demonic` (crimson
menace), `kurosawa` (black-and-white memory), `ash` (aftermath).

## 2. Wiring it into a page

1. In the page's import map, map `"three/addons/"` as `engine/lineup.html` and `engine/fx-demo.html` do:
   `"three/addons/": "/node_modules/three/examples/jsm/"`.
2. At load, after the renderer, scene and camera exist:
   ```js
   import { createFX, fxAt, shake, traumaAt } from './fx.js';
   const fx = createFX(renderer, scene, camera, { width: W, height: H, seed: 7, fps: FPS });
   fx.particles({ name: 'dust', kind: 'dust', center: [0, 1.5, 0], size: [4, 3, 4] });   // optional, once each
   fx.shafts({ name: 'key', origin: [-1.6, 5.2, -2.2], target: [0.4, 0, 0.8] });       // optional
   ```
3. In `renderAt(t)`, replace `renderer.render(scene, camera)` with:
   ```js
   shake(camera, t, { trauma: traumaAt(t, film.hits ?? []) });     // optional, after the camera is placed
   fx.render(t, fxAt(t, film.fx, film.fxBase, FPS));
   ```
   `fx.render` runs the whole stack, including tone mapping and sRGB, through `OutputPass`. Keep the renderer's
   `toneMapping` and `outputColorSpace` settings as they are.
4. A glint needs a world point. Resolve it before calling `fxAt`, for example
   `{ ...e, at: sword.localToWorld(new THREE.Vector3(len * 0.72, 0, 0)) }`.
5. To add effects to an existing render, put a custom pass in `fx.composer` (for example `BokehPass`) before
   `fx.bloomPass`.

**Note for `engine/motion.js`:** its ink impact frame draws the fighters with an override material and calls
`renderer.render` directly. Keep that path for the impact frame, or replace it with the post `ink-impact` event,
which works on any page. Its `#flash` and `#fade` overlays can become the `flash` and `fade` events.

## 3. Film data

Base look (held for the whole film or section):
```json
"fxBase": { "grade": "lantern", "bloom": { "strength": 0.6 }, "vignette": { "amount": 0.6 }, "grain": { "amount": 0.05 },
            "particles": { "dust": 1 }, "shafts": { "key": 0.8 } }
```
Events (times in film seconds):

| `effect` | Envelope | Main fields (defaults) |
|---|---|---|
| `ca-flash` | Peak on frame 1, exponential decay | `amount` 14 px, `dur` 0.25 |
| `flash` | Linear out | `amount` 0.85, `dur` 2 frames, `color` |
| `ink-impact` | Fully on for `dur` | `dur` 2 frames, `threshold` 0.42, `invert` 0, `accent` |
| `speed-lines` | In over 2 frames, out over 3, redrawn on twos | `dur` 0.6, `amount` 0.9, `center`, `inner`, `color` |
| `letterbox` | Slides in over `in`, out at `until` | `ratio` (strip w/h, 1.0 suits 9:16), `in` 0.6 |
| `bloom-pulse` | Added to the base strength, decays | `amount` 1.2, `dur` 0.4 |
| `glint` | Pops, peaks at 30%, dies | `at` (world point), `size` 140 px, `dur` 0.3 |
| `grade` | Cross-fades to the mood | `mood`, `in` 1.0 |
| `shafts` / `particles` | Fade in, hold, fade out | `name`, `amount`, `in`, `until`, `out` |
| `fade` | To a colour | `dur` 0.6, `color` |

The checker (`engine/validate.mjs`) checks `fxBase` and `fx`. Both `engine/main.js` and `engine/motion.js` run the stack when a film has `fxBase` or `fx`, and add a `ca-flash` and a `bloom-pulse` on every blade contact (`effects.contactFx: false` turns that off). In `main.js`, `"body": true` on an event times it to the action (it moves later with the hit-stops), and particle fields named in `fxBase.particles` are created around the duel (`fxParticles.<name>` sets `kind`, `center`, `size`).

## 4. Choosing effects by beat

| Beat / emotion | Use | Avoid |
|---|---|---|
| Monologue, standoff, hook | `lantern` or `moonlit` grade, vignette 0.6–0.8, grain 0.05, dust in one shaft, letterbox strip, eye glow with bloom | Speed lines, CA |
| Wind-up / warning | Glint on the edge 4–6 frames before contact, the eyes flare (bloom pulse) | Shake |
| Dash, lunge | Speed lines aimed at the target, smear ribbon | Long holds |
| Clash | Hit-stop, sparks, CA flash, 1–2 flash frames, shake (trauma 0.6–0.9), fov punch | An ink frame on every clash |
| Decisive blow | Ink impact frame (once or twice per film), then silence and a slow push | Particles changing at the same moment |
| Demonic presence | `demonic` grade, crimson embers, crimson-tinted vignette, stronger bloom | Amber on the demon |
| Aftermath, memory | `ash` or `kurosawa` grade, ash or petals, heavier grain | Bright flashes |

Stack in moderation. A hit reads well with 3–5 small effects firing within about 100 ms. Effects on every routine
action tire the eye.

## 5. The demo and its stills
```bash
nice -n 10 node engine/render.mjs --page engine/fx-demo.html --film film/fx-demo.json \
  --still 1.2,3.7,6.2,7.92,11.2,13.7,16.2,18.7,21.2,23.7,25.6,28.02,31.2,33.15,33.55 --prefix fx-
```
This makes 14 sections of 2.5 s each: raw, bloom + grade, vignette + grain + letterbox, impact CA + shake, speed
lines, light shafts, dust, embers + demonic, petals, snow + moonlit, glint, ink impact, kurosawa, and all together.
The dark sections use a demo-only paper hall with one hard key light (`HALL_X = -200` in `engine/fx-demo.js`), the
"70% darkness, one shaft" recipe from `research/reference-videos.md`. The stills go to `output/stills/fx-t*.png`.
On this CPU it takes about 6 s per still.

## 6. Planned (see `status: "planned"` in the JSON)
Screen-space god rays, lens flare (three/addons `Lensflare`), depth of field / rack focus (`BokehPass`), eye glow
trail, aura (seam light + boil), afterimages (re-posed ghost copies, because `AfterimagePass` is feedback and not
frame-independent), flash-step, shadow-vanish, ink-splash wipes (a SHIMI-made matte through ffmpeg `maskedmerge`),
speed ramp and slow-mo (body-time tracks like hit-stop), on-twos body timing, whip-pan, dutch tilt, rain, motion blur.

## 7. Research sources (technique only)
Smear frames: <https://en.wikipedia.org/wiki/Smear_frame>, <https://garagefarm.net/blog/smear-frames-enhancing-motion-in-animation> ·
impact frames: <https://knowyourmeme.com/memes/cultures/impact-frames>, <https://80.lv/articles/learn-how-to-add-accents-to-your-animations-with-impact-frames> ·
Demon Slayer visual grammar (twos/ones, glints, contrast frames, shake): <https://jbsiraudin.github.io/blog/demon-slayer-visual-grammar> ·
ufotable compositing: <https://actionnews-89l.pages.dev/anime/ufotable-studio-deep-dive-demon-slayer-fate-animation-style> ·
trauma shake and hit-stop: <https://forum.godotengine.org/t/game-feel-effects-that-stack-without-fighting-your-code-trauma-shake-real-time-hit-stop-and-apply-the-difference/146379>, <https://bevy.org/examples/camera/2d-screen-shake/>, <https://gamejuice.pages.dev/articles/screen-shake-guide>, Sakurai on hitstop <https://sourcegaming.info/2015/11/11/thoughts-on-hitstop-sakurais-famitsu-column-vol-490-1/> ·
light scattering: GPU Gems 3 ch. 13 <https://developer.nvidia.com/gpugems/gpugems3/part-ii-light-and-shadows/chapter-13-volumetric-light-scattering-post-process>, pmndrs GodRaysEffect <https://pmndrs.github.io/postprocessing/public/docs/file/src/effects/GodRaysEffect.js.html> ·
lens effects (CA, cos⁴ vignette, grain): AMD FidelityFX Lens <https://gpuopen.com/manuals/fidelityfx_sdk/techniques/lens/>, Unreal <https://dev.epicgames.com/documentation/en-us/unreal-engine/post-process-effects-in-unreal-engine>, Unity HDRP <https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@16.0/manual/camera-and-lens-effects.html> ·
bloom: <https://threejs.org/docs/pages/UnrealBloomPass.html> ·
glints and flares: Sapphire Glint <https://borisfx.com/documentation/sapphire/avx/glint/>, anime lens-flare convention <https://tvtropes.org/pmwiki/pmwiki.php/Main/LensFlare>, anime star sparkle <https://www.blendswap.com/blend/29361> ·
speed ramping: <https://www.premiumbeat.com/blog/alter-the-flow-of-time-with-speed-ramping/>, <https://tvtropes.org/pmwiki/pmwiki.php/Main/Ramping> ·
grading: <https://shotkit.com/teal-orange-look/>, <https://www.masterclass.com/articles/how-to-color-grade-video-footage> ·
rack focus: <https://www.studiobinder.com/blog/rack-focus-shot-camera-movement-angles/>, <https://nofilmschool.com/rack-focus-shot-definition-examples> ·
atmosphere: dust motes <https://melies.co/cinematic-techniques/atmosphere/dust-motes>, volumetric light <https://www.studiobinder.com/blog/what-is-volumetric-lighting>, ASC smoke and fog <https://theasc.com/blog/shot-craft/smoke-and-fog>, Disney *Raya* atmosphere <https://media.disneyanimation.com/technology/publications/2021/the-atmosphere-of-raya-and-the-last-dragon.pdf> ·
ink wipes: <https://www.adobe.com/learn/premiere-pro/web/ink-transition> · letterbox: <https://www.adobe.com/au/creativecloud/video/discover/cinematic-black-bars.html> ·
aura and boil: <https://www.premiumbeat.com/blog/how-to-create-line-boil-animations>, <https://aejuice.com/blog/how-to-make-a-super-saiyan-aura-in-after-effects/>.
Firecrawl was out of credits, so this research used plain web search. Most sources are tutorials or blogs [C], not
primary studio documents.
