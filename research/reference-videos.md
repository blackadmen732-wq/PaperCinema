# Reference videos from the owner (what they do well)

Analysed with `tools/listen.py` (speech + sound timeline + frame sheet). Source: three vertical Shorts by an indie
3D animation channel (knights/paladins), shared by the owner as the quality bar. Technique notes only; nothing copied.

| Video | Content | Technique |
|---|---|---|
| A (23 s) | Knight in a dark hall, monologue ("I've entertained your authority longer than your judgment deserves…") | Low-key lighting, purple/gold rim light, slow push-in, **extreme close-up of a glowing eye slit in the helmet**, sword raised into a single shaft of light, ends on black with a small logo |
| B (29 s) | Creator talks to camera, then a war speech ("Forward! … For all we've lost!") over a battle montage | Silhouette against bright fog, low-angle hero, crowd of knights behind the leader, wide establishing shot of towers in haze; the voice drives the cut rhythm |
| C (21 s) | Paladin with cape and shield, monologue ("We rise as one… Courage is not the absence of fear") | Extreme low angle, red cape moving slowly, hard rim light on armour edges, darkness filling 70% of frame, final full-body shot small in the dark |

## Common recipe (our inference)
- **Voice first:** a 15–25 s monologue, 4–6 short lines, a pause between lines; music swells under the last line.
- **Light:** 70% darkness, one key light or shaft, strong rim light, volumetric fog. Glow (eyes, metal edges) is the brightest thing on screen.
- **Camera:** slow (push-in 2–5% per second, slow orbit), low angles, extreme close-ups on eyes/hands/blade, one wide shot to show scale.
- **Frame:** a letterboxed 2.39:1 strip inside the 9:16 frame, title text above, black below.
- **Motion:** little movement, but heavy (cape, cloth); one decisive gesture (sword raised) per video.
- **Ending:** cut to black + small logo.
- **Mapping to our style:** our paper characters' **eyes and seams glow from the inner lantern**: pulse the glow with the voice (like the helmet eye).

## Second batch (owner, 5 videos)
| Video | Lesson |
|---|---|
| Jellyfish "Creago" ad | Motion with no ease, no pull-back and no follow-through reads fake. Light: the eye goes to the brightest spot; cheap videos light everything the same (one key glow, the rest dark). Sound is half the experience; without it nothing has weight. **Movement, light, camera and sound are decided before frame one** (style presets). |
| Spider-Man breakdown (rmt.motion) | **2.5D compositing**: flat images cut into layers placed in 3D space, a 3D camera moves through them (parallax), with keyframed curves visible in the graph editor; newspaper/wall props as image planes; a figure moving across layers. Fast and cinematic. |
| Library of Alexandria (lumenline) | Same 2.5D method in DaVinci Resolve Fusion: image planes in 3D, camera dolly, fire/candle/feather particles, serif titles fading in per word, narration (2 lines, 14 s). |
| Earshot (Claude Code tool) | An existing free tool that lets Claude Code listen to the timeline and place sound effects from a 250+ library or synthesise new ones. Use it instead of building our own. |
| Blender Skills (arjun988/blender-skills, MIT) | 94 Blender skills for Claude Code (Blender MCP integrated). Use them for Blender work. |

**Takeaways for us:** our paper-cut style is ideal for 2.5D: layered paper sets as image planes in Blender with a real 3D camera, plus our 3D characters in front. Decide movement/light/camera/sound per scene in a style preset before rendering. One bright glow, the rest dark.
