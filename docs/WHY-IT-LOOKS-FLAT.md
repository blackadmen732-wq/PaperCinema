# Why the renders look flat — what the people who do this for a living actually do

Researched 25 Nov with Agent Reach (`vendor/agent-reach`, MIT) against YouTube, Reddit and the open
web. Sources are named so the claims can be checked; none of this is from memory.

## The diagnosis, from a stranger on r/blender who nailed it

A poster put up a toon-shaded anime short and said something felt wrong. The reply
([r/blender, Apr 2024](https://www.reddit.com/r/blender/comments/1bze347/tips_on_how_to_improve/)):

> The problem is not that it is too bright, it's that it's **all almost equally bright**, and
> therefore the shadows don't pop from the highlights, and it looks less appealing because it lacks
> contrast. [...] make the sun's light a lot brighter than the skylight.

That is this project's frames exactly. In `output/blender/sword-mocap/f0017.png` the ronin's white
kimono, the mist and the bamboo all sit within a few per cent of each other in value. Nothing is
dark, so nothing is bright. The character does not come forward because there is nothing for it to
come forward *from*.

## What Blender Studio did on *Wing It!* — their own NPR short

[studio.blender.org, Jan 2025](https://studio.blender.org/blog/wing-it-from-concept-to-render/).
Primary source: Blender's own studio, non-photoreal, shipped. Their lighting artist's own words,
and the order matters because it is the order of leverage.

| what they do | what this project does today |
|---|---|
| **Character shading is decoupled from the environment.** Characters have their own shading controls — highlight colour and shadow colour set per shot, a *Tilt* to aim the light — "we could also completely decouple them" | the set's `lighting.fighter` rig, added today, is the first step of this. Highlight and shadow colour are not controllable at all |
| **"There was almost always some kind of rim light on the characters to lift them off the backgrounds."** Two separate rims, each colourable, placed with or against the key | the set files carry one `rim`. It is now applied. It is not tuned per shot |
| **Shadows are simplified on purpose.** The sun is generally the only shadow caster; most props and set elements are excluded from casting entirely; characters cast through a *shadow proxy* with a controllable gradient | everything casts everything. 1.2M faces of bamboo all casting is also why a frame costs two minutes |
| **Separate View Layers** for beauty and outlines, merged in comp | one layer |
| **A depth colour gradient in compositing** fades a uniform colour in with distance "to create better character separation" | **nothing.** The studio audit says it plainly: *"no post FX (no fxBase): no bloom on the eyes and the smear, no grade, no grain"* |
| **"Compositing was so integral to the final look of the shot that it happened directly in the lighting files."** | compositing is not in the pipeline at all |
| **12 iterations** on the one shot they broke down | this project has rendered each film roughly once |

Their closing line is the one to keep: *"it's all about flexible iteration."* Not a tool.

## The verified bug: the fold darkening has never once rendered

`blender/world/paper_materials.py` darkens every crease and wears every folded edge using
**Geometry &gt; Pointiness** (lines 169-171). Its own header says "(Cycles)". Films render in
**EEVEE Next** — the render log says so on every frame: `[engine] EEVEE Next, 32 TAA samples`.

Blender's manual, the Geometry node page:

> **Pointiness** — *Cycles Only.* An approximation of the curvature of the mesh per vertex.

So every valley of every fold and every worn edge on every part has been computing to nothing in
every film ever rendered. That is a large part of why "every facet is one flat tone": the thing that
was supposed to put a gradient and a dark line at each fold is not running.

Fix: bake pointiness to a face attribute at build time, in `PartCtx.add()` beside
`add_facet_attribute`, and read the attribute in the material instead of the Cycles-only node. Then
it works in both engines and costs nothing at render time.

Second verified gap: `post()` in `blender/sets/build_set.py` already builds bloom and a vignette as
compositor nodes. `blender/film_modular.py` never calls it — `grep -c 'post(' blender/film_modular.py`
returns 0. The bloom the audit keeps asking for is written and unwired.

## So the three things, in order of image-change per hour

1. **A compositing pass.** Free, no hardware, biggest single jump. Depth gradient for separation,
   bloom on the inner lantern and the blade smear, a grade that actually puts something at black and
   something at white, grain. Blender's compositor, in the render file, the way Blender Studio does
   it. This is also the audit's standing complaint.
2. **Value separation at the source.** Make the key much brighter than the ambient, and stop every
   piece of set geometry from casting. Faster *and* better — the two usually fight, and here they do
   not.
3. **Per-shot character light control** — highlight colour, shadow colour, two rims. The set's
   fighter rig is the hook; it needs to be addressable per shot rather than per set.

## One thing that did not work, so nobody repeats it

YouTube **search** works from this container; **subtitles do not**. `yt-dlp` gets
`Sign in to confirm you're not a bot` on a datacentre IP, so transcripts of the good tutorials
(Dillongoo's *How to (Actually) Make Anime in 3D*, 33 min, is the one worth reading) need a browser
login — `agent-reach login` on a normal machine, not here. Search, Reddit and web reading all work
unauthenticated.
