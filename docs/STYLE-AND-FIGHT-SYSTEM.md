# Lantern Origami: style and fight-cinema system

This is a build spec. Any person or AI should be able to read it and produce the same quality of film.

---

## 1. The style name

**House name: Lantern Origami** (提灯折り紙, *chōchin-origami*)

The real-world art terms it combines:

| Real term | What it means | Where it appears in your references |
|---|---|---|
| **Faceted origami sculpture** (also called low-poly origami or geometric papercraft) | Figures made of large flat paper planes with sharp folds, with no smooth curves | The straw-hat samurai, the windblown lady |
| **Backlit paper / lantern lighting** (like a Japanese *chōchin* or *andon* lantern) | Warm light glowing *through* thin paper and leaking out of the folds | The amber glow inside the samurai's sleeves and face |
| **Kirigami / layered paper-cut shadow box** | Flat cut-paper layers stacked in depth and lit from behind | The deer forest |
| **Washi texture** | Visible paper fibres and embossing | All of them |

**One-sentence definition (paste this into any AI tool):**
> "Lantern Origami: faceted folded washi-paper sculptures with sharp creases, off-white and muted tones, lit from inside so warm amber light leaks through the folds and seams, set in layered cut-paper dioramas with deep, soft shadows. Cinematic, shallow depth of field."

### The demonic sword fits the style
In Lantern Origami, **light inside the paper is power.** So a demonic blade doesn't need fantasy effects pasted on top:
- The blade is **black folded paper**. Its **seams glow crimson** from inside, like a lantern with a red candle.
- When the sword's power is used, the glow gets brighter and the light starts leaking through cracks in the paper.
- A slash leaves a **trail of torn red paper ribbon** instead of a digital glow trail.
- On a hit, the target **tears**: paper shards and confetti instead of blood. This also keeps the film suitable for all ages.

Rule: normal characters glow **amber**, and demonic power glows **crimson**. The audience learns this colour code without any explanation.

---

## 2. The fight system ("Strike Grammar")

Every attack is built from the same 6 beats. Real fight films and action games both use this structure.

| # | Beat | Length (24 fps) | Character | Camera |
|---|---|---|---|---|
| 1 | **Ready** | 12–24 frames | Stance (kamae), breathing | Wide or medium: show the distance between the fighters |
| 2 | **Wind-up** (anticipation) | 6–10 | Pulls the sword back, the body coils | Slow push-in, the lantern glow brightens |
| 3 | **Slash** | 3–5 | Very fast swing | **Blade-follow** camera or **whip pan** along the cut |
| 4 | **Hit-stop** | 3–6 frozen frames | Everything freezes on contact | Flash, paper burst, a small camera shake |
| 5 | **Follow-through** | 8–12 | The blade finishes its arc, cloth and hair keep moving | The camera keeps travelling past |
| 6 | **Reaction** | 12–24 | The defender reels, tears or blocks | **Face-snap**: the camera swings to the face of whoever matters now |

Hit-stop (beat 4) is what makes a hit feel strong. Fighting games use it on every hit.

### The move library (real Japanese sword cuts)
| Move | Japanese | Blade path |
|---|---|---|
| Vertical head cut | shōmen-uchi | Straight down |
| Diagonal cut | kesa-giri | Shoulder to opposite hip |
| Reverse diagonal | gyaku-kesa | Hip up to opposite shoulder |
| Rising cut | kiri-age | Low to high |
| Horizontal cut | yoko-giri / do-giri | Side to side, at waist or neck height |
| Thrust | tsuki | Straight forward |
| Draw-cut | iai / nukitsuke | Draw and cut in one motion |

Each move is stored once (a pose curve for the arms and body, plus the blade-tip path). A fight is then just a list: `[kamae, kesa-giri, block, kiri-age, hit, ...]`.

### Camera modes
| Mode | Use | How it works |
|---|---|---|
| **Orbit** | Standoffs | The camera circles the midpoint between the fighters |
| **Over-the-shoulder** | Dialogue, tension | Behind one fighter, looking at the other |
| **Blade-follow** | The slash itself | The camera is tied to a point just behind the blade tip, so it rides the cut |
| **Whip pan** | Fast hits | A very fast rotation with motion blur, often hiding a cut |
| **Face-snap** | Reactions | The camera swings round to frame a face (the game-finisher look) |
| **Crane** | Endings | Rises up and away |

### "Continuous" camera (one take, no cuts)
For the unbroken, game-like camera:
1. Track one **anchor point**: the midpoint between the fighters (or the active blade tip during a slash).
2. Each beat sets a **target offset** around that anchor (for example: wide → behind the attacker's shoulder → riding the blade → in front of the defender's face).
3. The camera **springs** smoothly toward each new target instead of jumping, so it flows continuously.
4. **Rules:** stay on one side of the fighters' line (the 180° rule) except on purpose during a big move. Leave space in front of the person moving. Never let the camera pass through a body.

### Speed ramping
Run normally, slow to about 20% speed through the slash and hit-stop, then snap back to normal. Combined with the paper shards, this is the "movie fight" feeling.

---

## 3. Lighting rules (what makes it look like your references)
1. **One warm key light from behind or the side** (rim light). Never light the subject flat from the front.
2. **Light inside the characters**: a small warm light inside the sleeves, chest and face. In Blender this is **translucent paper material + interior lights**.
3. **Dark, soft background** with a glow behind layered paper (like the deer forest).
4. **Shallow depth of field**: the background blurs, like a macro photo of a real paper model.
5. **Colour:** off-white and beige paper, amber light. Crimson only for blood/demonic power and key accents.

---

## 4. Story structure (how to tell a short fight film)
1. **World**: an establishing shot, place and time (5–8s)
2. **Weapon**: introduce the sword like a character, with a macro shot and the glow (5–8s)
3. **Arrival**: the opponent appears (5s)
4. **Tension**: a standoff, one line of dialogue or tradition (6s)
5. **Exchange**: 2–4 Strike Grammar moves, getting faster (8–15s)
6. **Decisive blow**: the longest hit-stop, and the biggest burst and slow-down (3–5s)
7. **Aftermath**: silence, the camera rises, the title (5s)

---

## 5. Build pipeline: today versus the recommended upgrade

### What exists now (this repo)
`film/*.json` (shot list) → three.js paper world → headless Chrome renders frames → MP4. **Good for:** fast, free previews (previz) of camera moves and timing. **Limit:** simple box-shaped figures, no real paper translucency, basic animation.

### Recommended upgrade for reference-image quality
| Step | Tool | Why |
|---|---|---|
| Characters and props | **Blender**, controlled by AI through **[Blender MCP](https://github.com/ahujasid/blender-mcp)** (new name: mcp-for-blender) | Real modelling, translucent paper materials and proper lighting. The AI can build scenes by command. |
| Turn your reference images into 3D | **[TRELLIS.2](https://github.com/microsoft/TRELLIS.2)** (Microsoft, MIT licence) | Image → textured 3D model. Your samurai image is a good input. Needs an NVIDIA GPU with 24 GB or more of memory (for example a rented RunPod GPU). Then apply Blender's *Decimate → Planar* to get origami facets, and re-texture the model as washi. |
| Rigging | Blender Rigify, or Mixamo auto-rig | Proper skeletons for the arms, wrists and body |
| Motion | Mixamo sword animations as a base; or capture motion from real sword-fight video with a pose-estimation model (for example WHAM or 4D-Humans) | Real human motion looks far better than hand-posed keyframes |
| Camera | Keep **our shot-list JSON format**, and have a Python script build Blender cameras from it | The same storyboard works in both engines |
| Render | Blender **Cycles** on a GPU | Real light through paper, depth of field and motion blur |

**Not needed for this:** *Agent Reach* (from your screenshot) gives AI agents access to websites like YouTube or Reddit. It's useful for gathering reference clips, but it doesn't make animation.

---

## 6. Checklist for any AI or artist building a shot
- [ ] Style prompt from section 1 used
- [ ] Every attack has all 6 beats, with a hit-stop of 3–6 frames
- [ ] The camera mode is chosen per beat, and the 180° rule is respected
- [ ] Warm rim light plus interior glow; crimson only for power or blood
- [ ] Paper shards instead of blood
- [ ] Historical facts marked as documented, tradition or our choice (see `research/`)
