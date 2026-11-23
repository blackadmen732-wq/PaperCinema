# Scene writing: how to write a Paper Cinema Short that moves people

The full procedure, the sources and three worked examples are in the skill
`.claude/skills/scene-writing/SKILL.md`. Reusable shapes are in `library/scene-templates.json`. This page is the short version.

## The idea in one breath
A scene is **a held breath that ends in one cut**. Slow, then a break, then fast: *jo-ha-kyū*, the pacing idea Zeami
took from court music into Noh. Our quality bar is the owner's references: 15–25 s voiced monologues over slow, dark
heroic shots (`research/reference-videos.md`).

## The steps
1. **Stake:** who wants what, and what it costs. If nothing can be lost, there is no scene.
2. **Logline:** one sentence with one concrete image.
3. **Template and length:** pick from `library/scene-templates.json`: standoff-and-single-cut, monologue-before-battle,
   cursed-blade-awakens, duel-in-the-rain, master-and-student, the-last-stand, iaido-draw, aftermath-zanshin or the-witness.
   Then pick 30, 45 or 60 s.
4. **Beats:** a hook in the first second, then world and want, obstacle and tension, a silence (*ma*), the cut, the aftermath (*zanshin*).
5. **One set-up, one pay-off:** the pay-off must change the meaning (the spare oar becomes "I kept the shavings").
6. **Lines:** 4–6 lines, about 2 words per second at a grave pace, one image per line, getting shorter toward the cut.
   Each line gets a playable verb ("to warn", "to plead"), a quality ("low, close") and a pause.
7. **Map every beat** to a move or pose, a shot type, a sound and an effect.
8. **History check:** documented, tradition or our choice. Label tradition on screen. Never caption invented words as a real person's quote.
9. **Checklist** (skill §10), then build it with the `paper-cinema-film` skill.

## Shot types
`eye-reveal` · `blade-slide` · `low-hero-push` · `whip-reveal` · `orbit-zanshin` · `silhouette-wide` ·
`over-shoulder-standoff` · `impact-zoom`. Each maps to a KUROKO rig (skill §7). Use one `impact-zoom` per scene.

## Taste rules
- Concrete beats abstract: write oar, salt, lantern, prayers. Avoid destiny, darkness and power.
- The subtext is never said aloud.
- The loudest beat is the silence before the blow.
- Amber means human, crimson means curse. Use paint and paper shards, never blood. Death is a light going out.
- The Ronin never speaks. His choices are his lines.
- Banned: "Prepare to die", "It ends now", "Is that all you've got?", explaining the colour code, slow motion on everything,
  a clash every second, reverb on every line.

## The 1-second hook and the signature opening
Every film opens on the 6-second paper-sea opening, which fades in from black. Put the hook **over** it: the first voiced
line starts at 0.2–0.4 s on the taiko hit, and the first frame is already lit. A cold open, or the planned 3-second Shorts
opening, needs the owner's OK.

## Voice, and what the engine can't do yet
Lines go in the film's `voice` list. `python3 tools/voice.py film/<name>.json` renders them (VOICE system), and
`engine/sound.mjs` mixes them. Delivery comes from the `voice` role and the `style` words. Use `[pause 0.6]` for a pause
inside a line. Add every line as a `bottom` subtitle as well. Fog, rain, a hand-lantern prop and the chiburi and nōtō
poses are planned. Mark them "planned" in the outline.
