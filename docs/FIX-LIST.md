# Fix list: why the fights felt stiff and silent, and the fixes (Fable review)

From a director / animator / sound-designer review of `film/kuroko-duel.json` (Fable). Status per item at the end.
Research background: `../research/anime-fight-craft.md`.

## Three root causes
1. **The main engine uses none of the new motion work**: no `overlap`, no `ease`/`settle`/`drag` in `library/moves.json`, no eyes, no hit-stop, ribbon, sparks or clash aim. These exist only on the motion-test page (`engine/motion.js`).
2. **Vertical framing is broken in KUROKO**: the `frame` rig fits `W = sep + 1.1` into a 19.5° horizontal view, so in 9:16 the camera sits ~16 m away and the fighters are ~17% of the frame. Fix: `W = sep·|cos(angle)| + 1.1`, over-the-shoulder angles 55–68°, fighter ≥ 45% of frame height.
3. **The clash had no picture and no sound**: the blades were ~1 m apart at the "clash", and `blade-clash.mp3` is really a slice sound (no low end, no ring). The whoosh 150 ms before it was 6 dB louder. `swing`, `swing-2` and `swing-3` were the same file.

## Sound
- **Clash** = tink (0 ms) + steel ring (+5 ms, 1.4 s) + low body + paper crinkle (+20 ms). Beds and whoosh dip 12 dB for 80 ms before the hit. Steel on wood (bokken): ring −14 dB, add a wood knock.
- **Whooshes**: ≥ 3 different sources, never the same twice in a row; pitch and level from tip speed; peak 2 frames before contact; always ≥ 9 dB under the clash; at most 2 per second.
- **Mix**: `alimiter=limit=0.89:attack=1:release=80:level=false`, then `loudnorm=I=-14:TP=-1.5:LRA=9`; beds ducked by the hits (`sidechaincompress`); pan the clash by its screen position (±0.6).
- **Draw**: koiguchi click (−100 ms) → slide → tip-clear "shing" → cloth.

## Jump-back (replacement beat sheet, 24 fps, 29 frames, 1.5 m)
| f | Beat | Key values |
|---|---|---|
| 3 | Anticipation: sink and lean in | crouch 0.30, weight 0.55, tx 0.22, cx 0.18, `ease: antic` |
| 5 | Push-off (stretch) | crouch −0.02, weight −0.6, stance 0.70, rax 0.5, `drag: 0`, `arc: 0.22` |
| 10 | Apex tuck | y 0.22, crouch 0.16, feet lifted (rfl 0.10, lfl 0.16), swayx 0.25 |
| 13 | Reach for the ground | stance 0.70, lax −0.35 |
| 15 | Touch, rear foot first | crouch 0.10, weight −0.7, `drag: 0` |
| 18 | Absorb (squash) | crouch 0.36, tx 0.30, cx 0.22, `ease: out` |
| 23 | Skid ends, rebound | crouch 0.18, `settle: 1` |
| 29 | Guard | chudan, `settle: 0.6` |

Needs: an `arc` field (parabolic height, constant horizontal speed in the air), foot lift/offset channels, a cloth spring.
Rigid paper never scales: squash = crouch + chest fold + shrug; stretch = negative crouch + toe + open chest.

## Camera techniques to add
1. Over-the-shoulder depth staging (vertical) · 2. Eye-to-blade slide (built on the motion page) · 3. Speed ramps (body
time 1 → 0.25 → 1.15) · 4. Whip-pan cuts with blur · 5. Dutch tilt per beat (bind 12–18°) · 6. Impact zoom (fov 34→24→16,
2 frames each) and shake in degrees with a per-frame sign flip · 7. "Kuroko cloth" foreground wipe · 8. Low-angle hero
(0.2 m, −14°) · 9. Orbit through the hit-stop · 10. Rack focus (BokehPass). Plus 6–10 frame inserts (eyes, hand tightening,
foot grinding) before each strike.

## Eyes
Glow idle 0.9 · focus 1.4 · anticipation 2.2 · "decide" flare 3.5 for one frame · struck 0.4. Blink every 3–5 s, never in
anticipation. Pupils lead the head by 3–4 frames. A glow trail when the head whips. Human rage: amber → orange.
Demonic only: → crimson with one flicker. Bloom pass (threshold 0.85, strength 0.6).

## Opening (keep the idea, faster hook for Shorts)
0–0.4 s flash-forward ink impact frame → 0.4–1.0 s eye close-up, lids snap open on a taiko hit → whip match-cut, the eye
glow becomes the lantern sun → 1.15–3.6 s fast wave skim (~20 m/s, low), one kanji per taiko hit → 3.6–4.8 s crane up to
the island and two silhouettes, full title → 4.8–6 s title burns to ash, push to the hand on the hilt, koiguchi click.

## Smaller problems
Left-hand pops (`reachHand` → use `solveArm`) · every key a full stop (add snap/drag/settle to every strike) · foot
skating (world-locked feet, step when the root moves > 0.35 m) · shoulder arcs not planar (slerp or tip-arc IK) · contact
should land ~60% through the swing (use clash aim) · `react()` steps (low-pass it) · lag can run backwards if drag
changes too fast (clamp) · strobing at 30 m/s (the ribbon).

## Status
| Item | Status |
|---|---|
| Synthesised clash / light clash / scrape / 3 whooshes / draw shing (`tools/synth_sfx.sh`) | ✅ built |
| `sfx` reuse and `rate` pitch in `sound.mjs`; automatic cues from `output/<film>.events.json` | ✅ built |
| Contact detection, clash aim, hit-stop, sparks, ribbon, ink impact frame, eyes, eye-to-blade slide | ✅ on the motion page |
| Port all of that into `main.js`; vertical framing fix in `kuroko.js` | next |
| Ducking, pan, limiter/loudnorm | next |
| Jump-back beat sheet (`arc`, foot channels, cloth spring) | next |
| Eye glow states, blink, trail, bloom | next |
| Camera pack 3–10 | next |
| New opening | next |
