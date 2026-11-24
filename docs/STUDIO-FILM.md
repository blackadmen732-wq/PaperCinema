# Studio films in Blender

The studio workflow turns a scene file into an editable Blender project, an MP4 with sound, and a framing
and foot-contact report. [Paper Awakens](../film/studio/paper-awakens.json) is a six-second example.
The supported workflow uses Blender, Node.js and FFmpeg on a render machine. A Chromebook can play the
result without running Blender.

## Build and render

```bash
blender -b --python-exit-code 1 -P blender/studio_film.py -- \\
  --scene film/studio/paper-awakens.json --out output/paper-awakens
```

The default profile renders a 360 × 640 preview at 18 fps. Add `--profile master` for 720 × 1280 at 24 fps
with native Cycles denoising. Use `--res` and `--samples` to tune the render for the available machine.
On builds without native denoising, pass `--no-denoise`. A render machine with the optional Python packages
`oidn==0.2.1`, Pillow and NumPy can use `--cpu-denoise` to clean the rendered frames before encoding.
The optional filter is independent of the Blender project.

Use `--stills` for one frame per shot or `--build-only` to bake the scene without rendering. Rerun a stopped
render with the same arguments and add `--resume`. The runner checks matching scene settings and input
files before reusing complete PNGs.

| Output | Contents |
|---|---|
| `paper-film.mp4` | Edited picture and timing-accurate local sound |
| `paper-film.blend` | Keyframed cast, camera-cut markers, lighting, backdrop and modular paper materials |
| `film-audit.json` | Frame ranges, sampled camera coverage, and travel for the foot joints |
| `audio-cues.json` | Scene cues used to mix the final audio |
| `frames/` | Picture frames used for the encode |

## Author the next scene

Copy the scene JSON and edit these parts of the timeline.

| Field | Use |
|---|---|
| `duration` | Total seconds. The selected frame rate must divide it into whole frames. |
| `stage.palette` | A cool or warm seamless background, with the same photographic lighting. |
| `stage.paper_motion` | Strength of the sway and sleeve follow-through. |
| `cast` | Character recipe by name, pose keys at seconds, and per-key channel overrides. Use poses from `library/poses.json`. |
| `cast.<actor>.plant_width` | Distance in metres across the feet for a grounded hold. Keep root orientation and stance fixed through a planted beat. |
| `shots` | Camera cut times, lens, aperture, world positions and camera targets for the beginning and end of each shot. Set `full_body` to check for framing cutoffs. |
| `sounds` | Timed cues from `assets/sfx`, with gain and playback rate. |

To shoot inside a built location, pass `--set output/sets/dojo.blend` and author camera and cast positions in
that location. Cast position channels use the existing animation axes. Camera positions and targets use
Blender coordinates in metres. Set `stage.floor_z` when the set floor is above or below the origin.

The sample uses the existing `ronin-reference` rig and shaded paper. Its pose is hand-keyed from the
reference silhouettes. The first and last shots use shallow depth of field. The floor, lights and material
grain stay separate from the rig, so changing the location or frame need not change the character.

Use the [character guide](CHARACTER-FACTORY.md) to change the model, and the [Blender film guide](CHARACTER-BLENDER.md)
for existing performance exports, motion capture and scripted effects.
