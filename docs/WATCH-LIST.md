# What to watch, in order

Found 26 Nov with Agent Reach against YouTube and the open web. Ordered by what Paper Cinema needs
next, not by how good the video is in general — the fight ones matter more here than another pass
over the 12 principles.

Times are the video's own length. Watch the first three before the rest; everything below them
assumes you know what timing and spacing are.

## 1. The fundamentals (about 25 minutes, all three)

| | |
|---|---|
| **[The #1 Animation Principle (How To In-Between)](https://www.youtube.com/watch?v=6UXjRCORV44)** · 12m | Where the frames go *between* two poses. This is the whole thing, and it is the thing this project does automatically in `makeMotion`. Watch it to know whether the engine is doing it well |
| **[TIMING — The 12 Principles in Games](https://www.youtube.com/watch?v=rHEJZXvFc5I)** · 9m | Games, not film, so it is about *reads at speed* — which is what a 9:16 Short is |
| **[Spacing and Overlap](https://www.youtube.com/watch?v=LYcWJ-PB3wI)** · 4m | Overlap is `motion.overlap` in your film files. Four minutes to understand what that switch does |

## 2. Fight animation — the part this project is actually about

| | |
|---|---|
| **[How to ANIMATE SWORD COMBAT, Part 1](https://www.youtube.com/watch?v=sBNDzqO8ZT8)** · 77m | The longest and most directly on-topic thing found. Sword combat specifically |
| **[How to Animate a Fight Scene Step by Step](https://www.youtube.com/watch?v=tUde5QR9GAo)** · 35m | The whole sequence, start to finish — which is the gap between having 26 moves and having a fight |

## 3. Anime fight animation, which is a different craft

| | |
|---|---|
| **[The Genius Behind Naruto's Fight Scenes — Norio Matsumoto](https://www.youtube.com/watch?v=i6Z9m_0-DVo)** · 15m | Matsumoto is the reason anime fights look the way they do. If you watch one thing on this page, this |
| **[Hiroyuki Imaishi: Master of Sakuga](https://www.youtube.com/watch?v=ASXvAMPcjSE)** · 12m | Extremes pushed past anatomy, held, then snapped. The opposite of motion capture, and the reason captured motion alone will never look like this |
| **[How to (Actually) Make Anime in 3D, ft. Dillongoo](https://www.youtube.com/watch?v=4LhvcINgNxU)** · 33m | 3D posed to read as 2D. The exact problem this project has |

## 4. Blender, for the look

| | |
|---|---|
| **[Blender's animation tool you should always use](https://www.youtube.com/watch?v=5QAdQwCRbBM)** · 13m | |
| **[Setting Blender Up for Anime (EEVEE)](https://www.youtube.com/watch?v=c670_AonNjI)** · 3m | Short, and EEVEE is what the films render in |
| **[Photoreal textures into anime shaders](https://www.youtube.com/watch?v=5ajQHT6SIqM)** · 9m | Relevant to the paper surface problem, which is still open |

## 5. The technical ones behind today's fixes

| | |
|---|---|
| [Soft IK limbs in Blender](https://www.youtube.com/watch?v=F2RzZRaDrXU) | The knee fix, done by hand in a rig. Same idea as `engine/figure.js` `solveLegs` |
| [Eliminating knee pop in a walk cycle](https://blenderartists.org/t/how-to-eliminate-the-knee-pop-in-in-the-walk-cycle/1161294) | Animators hitting exactly the bug measured here |
| [Tool Chefs Soft IK Solver](https://www.toolchefs.com/?portfolio=soft-ik-solver) | The tool whose documentation states the mechanism plainly: velocity damped near full extension |

## 6. Reading, not watching

| | |
|---|---|
| **[Blender Studio — *Wing It!* lighting](https://studio.blender.org/blog/wing-it-from-concept-to-render/)** | Blender's own studio on an NPR short. Character shading decoupled from the environment, a rim light to lift figures off the background, shadows simplified to one caster, a depth gradient in comp. The source behind `docs/WHY-IT-LOOKS-FLAT.md` |
| [Smear frames](https://blog.cg-wire.com/smear-frames/) | One drawing, one frame at 24 fps. Hold it longer and the character goes rubbery |
| [r/blender: "it's all almost equally bright"](https://www.reddit.com/r/blender/comments/1bze347/tips_on_how_to_improve/) | A stranger diagnosing this project's exact lighting problem for somebody else |

## One thing to hold on to while watching

Captured motion and anime motion are **opposites**, and this project uses both. Capture gives weight,
balance and recovery — the things a human body does that are hard to key by hand. Anime gives a
three-frame slash and a six-frame freeze, which no human body does at all.

The Matsumoto and Imaishi videos are about the second kind. `library/mocap/` is the first. The fight
wants capture for the movement between the cuts and hand-keyed extremes for the cuts themselves —
which is why `docs/ANIMATION-SOURCES.md` ranks hand-authored moves alongside capture rather than
below it.
