---
name: scene-writing
description: Write the story of a Paper Cinema Short before any JSON is made — the idea, logline, beat sheet for a 30/45/60 s vertical Short with a 1-second hook, voiced monologue or dialogue lines with timing, pauses and voice-direction tags, and the mapping of every beat to fight moves, KUROKO shot types, sounds and effects, ending in a film-JSON outline. Use whenever the task is a new scene, episode, monologue, speech, voice-over, dialogue, hook, or "make it more moving / cinematic / tasteful", or when reviewing a script. Hand the outline to the paper-cinema-film skill to build and render it.
---

# Writing a Paper Cinema scene

A scene is written **before** it is built. This skill turns an idea into a script a renderer can follow. It sits
upstream of `.claude/skills/paper-cinema-film/SKILL.md` (which builds, checks and renders the JSON).

Read first, once per session: `AGENTS.md`, `docs/STORY-BIBLE.md` (world rules, characters, cursed swords),
`research/reference-videos.md` (the owner's quality bar), `docs/STYLE-AND-FIGHT-SYSTEM.md` (Strike Grammar).
Reusable shapes: `library/scene-templates.json`. Human summary: `docs/SCENE-WRITING.md`.

**Confidence marks used below:** **[D]** documented by a primary or authoritative source, **[C]** commonly reported
(practitioner blogs, critics, secondary sources agree), **[I]** our inference. Sources are listed in §12.

---

## 0. The quality bar in one paragraph

The owner's references are 15–25 s **voiced character monologues over slow, dark, heroic shots**: 4–6 short lines with
a pause between each, 70% darkness, one shaft of light, a glowing eye in extreme close-up, one decisive gesture, cut to
black (`research/reference-videos.md`). Our version: folded-paper samurai whose **eyes and seams glow from the lantern
inside** (amber = human, crimson = curse), paint and paper shards instead of blood, history marked honestly. Every
scene should feel like a held breath that ends in one cut.

---

## 1. Procedure (do every step, in order)

1. **Idea → stake.** Write one sentence: *who* wants *what*, and *what it costs*. If nothing can be lost, there is no scene.
2. **Logline** (§2). One sentence, under 30 words, with a concrete image in it.
3. **Pick a template** from `library/scene-templates.json` (or none) and a **length** (§3): 30, 45 or 60 s.
4. **Beat sheet** (§3): 3–6 beats with times. Beat 0 is the **1-second hook**.
5. **Set-up / pay-off ledger** (§4): list every set-up and the beat that pays it off. No orphan set-ups.
6. **Write the lines** (§5): voice, timing, pauses, direction tags, word budget. Read them aloud with a timer.
7. **Map each beat** (§6): move / pose (`library/moves.json`, `library/poses.json`), shot type (§7), sound, effect.
8. **History check** (§8): every historical claim is marked and labelled on screen if it is tradition.
9. **Run the checklist** (§10). Fix every "no".
10. **Film JSON outline** (§9). Then follow the `paper-cinema-film` skill: scaffold, validate, look at stills.

---

## 2. Logline and the three questions

**Logline formula [I]:** *When [situation], [character] must [action] or [cost], but [obstacle].* Then compress.

> "Rowed to the island by a man who never speaks, a boatman watches an oar become an answer." (Ganryūjima)

Answer three questions before writing a single line (want/obstacle is the engine of a scene [C]; Arc Studio, Brainscape):
- **Want:** what does the character want *in this scene* (not in life)? It must be playable: *to make him hand over the sword*, not *to be brave*.
- **Obstacle:** who or what stands in the way? The best obstacle is another person's want, or the character's own curse.
- **Subtext:** what is the scene *really* about that nobody says? (Subtext = the meaning under the words, the real subject unnamed [C].) Write it down; then never say it aloud.

---

## 3. Structure: jo-ha-kyū inside a Short

**Jo-ha-kyū** (序破急, "beginning, break, rapid"): actions begin slowly, speed up, then end swiftly. From gagaku court
music, adopted by Zeami for Noh, and applied to tea, martial arts, renga [D/C] (Wikipedia, Stanford Noh site). This is
exactly the Strike Grammar at story scale: long stillness, a break, one fast cut. **Kishōtenketsu** (introduction,
development, twist, reconciliation) is the other native shape: no central conflict, a third-act turn that shows a new
perspective [C] (Wikipedia, Poets & Writers). Use it for quiet, non-fight scenes (the twist is a revelation, not a blow).

### The 1-second hook (beat 0)
On Shorts, viewers decide in the first 1–2 seconds; YouTube Studio reports *viewed vs. swiped away*. Practitioner
targets are ~70%+ viewed [C] (vidIQ, Opus; the thresholds are third-party heuristics, not YouTube figures). So frame 1
must already be **image + sound + (often) a word**:
- **The glowing eye** in the dark (eye-reveal), lit from frame 1 — no fade from black longer than 4 frames.
- **A first line that names a stake or a wound**, concrete, under 8 words: "Every man who carried that sword is dead."
- **A contradiction**: "He was late. On purpose." / "The sword wanted her. He cut the lantern."
- **The decisive image, first** (in media res), then back to the start (use sparingly).

**House-rule conflict:** every film opens on the paper-sea opening (`library/openings/lantern-wave.json`, 6 s, fades
from black). Do not drop it on your own. Default: **hook-over-opening** — line 1 of the voice starts at 0.2–0.4 s over
the taiko hit, and the opening's first frame is already lit. A **cold open** (a 1 s flash of the hook image before the
paper sea) or the planned **3-second Shorts opening** (AGENTS.md "Next") need the owner's OK.

### Beat sheets by length (times are of the published Short; the opening occupies its first 6 s)
| Beat | Purpose (jo-ha-kyū) | 30 s | 45 s | 60 s |
|---|---|---|---|---|
| 0 Hook | One image + one line that names the stake | 0–1 | 0–1 | 0–1 |
| 1 World / want (jo) | Who, where, what they want. Slow. The weapon as a character | 1–8 | 1–12 | 1–15 |
| 2 Obstacle / tension (ha) | The other want arrives; the standoff; the set-up planted | 8–17 | 12–26 | 15–34 |
| 3 Silence (ma) | 0.8–2 s of near-nothing: wind, breath, one eye. The loudest beat | 17–19 | 26–29 | 34–38 |
| 4 The cut (kyū) | One decisive action. Longest hit-stop, biggest burst | 19–22 | 29–33 | 38–43 |
| 5 Aftermath (zanshin) | The pay-off lands; the light goes out or stays; last line; end card | 22–30 | 33–45 | 43–60 |

Rules: the decisive moment never lands before **60%** of the runtime [I]; the last 2.6 s carry the end card
(`library/endcards/paper-cinema.json`). For a 60 s Short, beat 2 may hold a 2–4 move exchange that gets faster (Strike
Grammar §4 "Exchange"). A **loop ending** (last frame rhymes with the first) can push average-viewed past 100% because
replays count [C] (vidIQ, ContentStudio; anecdotal); our paper sea → end card → paper sea already rhymes.

---

## 4. Set-up and pay-off

A set-up is a prop, image or line planted early; the pay-off is when it returns with a deeper meaning. The pay-off
should **transform** the set-up, and the set-up should be quiet enough to be noticed only in hindsight [C] (Final
Draft; Penberth). In 30 s you get **one** strong pair, at most two.

Keep a ledger:
| Set-up (beat, time) | Pay-off (beat, time) | Transformation |
|---|---|---|
| Boatman's spare oar (1, 2 s) | "I kept the shavings." (5, 33 s) | wood → weapon → relic |
| "It cuts the light out of what it touches." (2) | He cuts her lantern, not her (4) | threat → choice |

Our world gives free set-ups the audience learns without words: **amber vs crimson glow**, **a lantern going out =
death**, **ink world = memory**, **a scabbard thrown away = no return** (tradition, Ganryūjima).

---

## 5. Writing the lines

### Rhythm and word budget
- A grave, slow delivery runs about **2 words per second** [I] (normal speech is faster). Budget:
  `words ≈ 2 × (voiced seconds − total pauses)`. A 20 s monologue with 5 pauses of 0.7 s ≈ **33 words**. Cut to fit.
- **4–6 lines**, each 3–12 words, one breath each, one image each (reference recipe).
- Lines get **shorter toward the cut**. The last line before the cut is the shortest; often one word, or none.
- **Rule of three:** three items, three clauses, or anaphora (repeating the opening words) make lines memorable —
  "we few, we happy few, we band of brothers" (Henry V) [C]. Use **one** triad per scene, not three.
- **Concrete over abstract.** Nouns you could fold out of paper: oar, shavings, scabbard, lantern, tide, prayers,
  winter, salt. Not: destiny, darkness, power, honour, fate.
- **End on a noun or a verb, not an adjective.** "Look for the light." not "It was beautiful."
- **Subtext:** the character talks about the oar, the tide, his mother — never about fear or death directly.
- **The Ronin never speaks** (story bible). His choices are his lines. The cursed sword may whisper (our choice).

### Voice direction (actors and TTS)
Direct with **playable verbs** (what the speaker is *doing to* the listener), not adjectives — *to warn, to plead, to
belittle, to confess, to dare* [C] (USC directing-with-action-verbs; voice-direction practice). Every line gets:

`SPEAKER [verb] [quality] "Line." {pause after, s}`

Quality tags (ours): `low` · `close` (mic-close, intimate) · `whisper` · `breath` · `cold` · `tired` · `rising` ·
`falling` · `smile` (heard, not seen) · `held back` (emotion under the line, not on it).

**Mapping to our VOICE system** (`tools/voice.py`, Kokoro-82M on CPU; read its header and `docs/VOICE.md` if present —
they win over this summary): each line is one entry in the film's `voice` list and is rendered as **one clip at its
`t`**. Kokoro takes no text prompt, so delivery comes from:
- `voice`: a role alias (`ronin`, `warlord`, `elder`, `narrator`, `heroine`, `empress`, `onna`, `samurai-ja`, `onna-ja`) or a Kokoro voice id.
- `style`: known words are mapped to numbers — `slow`, `fast`, `measured`, `low`, `deep`, `high`, `menacing`, `cold`,
  `whisper`, `quiet`, `soft`, `shout`, `roar`, `distant`, `close`, `inner`/`thought`/`monologue`, `dry`. Other words are
  ignored, so our quality tags (`tired`, `held back`, `rising`) stay as notes for a human or a better TTS.
- `speed` (base, multiplied by style words), `pitch` (semitones), `inner: true` (inner-monologue treatment), `gain`.
- Pauses inside a line: `[pause 0.6]` inserts that many seconds of silence. Pauses between lines live in the `t` values.
- The tool writes a loudness envelope per line for the eye-glow pulse, and ducks beds under speech (`engine/sound.mjs`).

**Mapping to ElevenLabs (v3/v4), if lines are made there instead** [D] (ElevenLabs prompting docs):
- Audio tags in square brackets work: `[whispers]`, `[sighs]`, `[exhales]`, `[curious]`, and voice-quality tags such as
  `[low, gravelly voice]`. Match tags to the voice; a serious voice may ignore playful tags.
- **v3/v4 do not support SSML `<break>`**; pauses come from ellipses, dashes and text structure (less consistent).
  Older models accept `<break time="1.0s" />` up to 3 s; many breaks in one generation cause instability.
- CAPITALS add emphasis; speed setting 0.7–1.2.
- **Our practice [I]:** generate **one clip per line**, pick the best of several takes, and place each clip at its
  `t` in the timeline. The pauses then live in the edit, frame-exact, and the music can breathe between lines.
- Subtitles always (`titles`, style `bottom`): many viewers watch with sound off [I].

### Banned clichés (rewrite on sight)
- Lines: "You're not ready." "It ends now." "Prepare to die." "I've been waiting for this." "Is that all you've got?"
  "Too slow." "Little did they know…" "Destiny / darkness / power awaits." "This is my fight." "Some say…" as filler.
- Exposition in dialogue ("As you know, brother…"); explaining the colour code; naming the theme ("This is about honour").
- A villain laughing; a speech that lists the plot; ending on a question to the viewer; "wait for the end" text.
- Craft: slow motion on everything (save it for the cut); a clash every second; reverb on every line; a trailer
  "BWAAM" under every beat; rain with no reason; three fake-outs before the cut; a smile after a kill.
- History: an invented aphorism captioned as a real person's quote; tradition shown as fact (§8).

---

## 6. Mapping beats to the film

For every beat write one row: **time · purpose · line · move/pose · shot type · sound · effect.**

### Moves and poses (must exist; the checker rejects unknown names)
- **Moves** (`library/moves.json`): `step-in`, `step-back`, `jump-back`, `dodge-left`, `parry-high`, `lunge-shomen`,
  `kesa-giri`, `tsuki`, `bind`, `stagger-back`.
- **Poses** (`library/poses.json`) most used in scenes: `neutral`, `rest-hand-on-hilt`, `iai-draw`,
  `blade-out-hand-on-saya`, `throw-scabbard`, `blade-out-recover`, `chudan`, `jodan`, `jodan-high`,
  `jodan-high-wind-up`, `shomen-strike`, `hasso`, `hasso-wind-up`, `low-ready`, `stand-blade-low`, `uke-high`,
  `zanshin`, `struck-reel`, `kneel-collapse`, `fallen`.
- **Missing (request a new pose before writing it in):** chiburi (blade flick — flicks *paint*), nōtō (re-sheathe),
  bow, kneel in seiza, walk with lantern. Until then: `zanshin` → `stand-blade-low`.
- Strike Grammar timing: ready 0.5–2 s · wind-up 0.2–0.4 s · slash 0.15–0.4 s · hit-stop (repeat the pose ~0.15 s
  later) · follow-through · reaction. When one fighter attacks, the other reacts.

### Sounds (`assets/sfx/`; reuse an id, or add a new `query`)
`wind-bed`, `sea-bed` (beds) · `title-taiko`, `reveal-gong`, `temple-bell` · `draw-shing`, `sword-draw-1/2` ·
`whoosh-a/b/c`, `swing`, `throw-whoosh` · `clash-steel`, `clash-light`, `blade-clash`, `steel-scrape` · `impact`,
`impact-drum` · `steps-in`, `steps-out`, `fall`, `splash`, `rowing`. Sound rules: before the decisive blow drop to
near-silence (wind only) for 0.5–1.5 s, then hit; duck music under impacts; on phones the weight is in the 1–4 kHz
transient (`research/anime-fight-craft.md` §2). A cut on paper = whoosh → paper tear → 80–200 ms later a soft wet splat.
Zatoichi (2003) makes the cuts louder than usual, as if heard by the blind hero [C] — a point-of-hearing mix is a tool.

### Effects (status matters: don't write what can't render without saying so)
| Effect | Status | How |
|---|---|---|
| Camera shake / impact punch | built | `shakes[]`, `events.impact` (7° punch-in, always on) |
| Hit-stop, smear ribbon, ink impact frame, clash sparks | built on the motion-test page | `engine/motion.js`; port pending (FIX-LIST) |
| Paper shards, paint | built (2D sim) | SHIMI presets `kesa-cut`, `face-cut` (`engine/shimi.py`) |
| Eye glow (with lids) | built (skeleton option) | VOICE writes a per-line loudness envelope for the pulse; check the engine reads it |
| Lantern goes out (death), crimson seam leak | style rule; per-shot control planned | note it in the outline |
| Flash-step, shadow-vanish, speed lines | planned / in progress | `docs/EFFECTS-PLAN.md`; check `engine/fx.js` for what exists now |
| Fog, rain, hand lantern prop | planned (Blender world has optional fog) | mark "planned" in the outline |

---

## 7. Shot types (names shared with `library/shots.json`) → KUROKO rigs

| Shot type | What it is | KUROKO rig (docs/CAMERA.md §7) | Use for |
|---|---|---|---|
| `eye-reveal` | Extreme close-up; the inner glow of the eyes is the brightest thing on screen | `face`, subject `<id>.head`, fov 18–24, feel `crane` | The hook; the beat before the cut; the curse flicker |
| `blade-slide` | Macro dolly along the blade (or armour folds), glow travelling the seam | `blade` rig, or `studio` mode keyframes sliding along the blade | Introducing the weapon as a character |
| `low-hero-push` | Low angle, slow push-in (2–5% per second) | `frame`, size `full`, negative `elevation` (−8…−15), feel `dolly` | The monologue's spine; resolve |
| `whip-reveal` | Fast whip pan that hides a cut or reveals who is there | `frame` + behaviour `whip`, feel `torpedo` | The draw; a surprise arrival |
| `orbit-zanshin` | Slow orbit around the still victor after the cut | `orbit`, `deg0`→`deg1` (≤ 60°, one side of the line), feel `crane` | Aftermath; the pay-off line |
| `silhouette-wide` | Tiny figure(s) against bright sky, fog or sea; 70% of frame empty | `frame`, size `wide`, backlit, feel `crane` or `locked` | Scale; the last image; ma |
| `over-shoulder-standoff` | Behind one fighter's shoulder, looking at the other | `frame`, `angle` 55–65, subjects [near, far], feel `crane` | Dialogue; the standoff; the threat |
| `impact-zoom` | Snap-in on contact with shake and hit-stop | `frame`, size `close`, feel `locked` + `shakes[]` at the hit | The decisive cut, once |

Grammar: stay on one side of the line (180° rule) except on purpose; cut on action; one `impact-zoom` per scene; the
cut itself is either hidden (whip-reveal) or frozen (hit-stop), never shown at normal speed in a wide.

---

## 8. History honestly

- Every historical claim is **documented / tradition / our choice** in `research/<name>.md` (AGENTS rule 5).
- **Tradition on screen is labelled** in a subtitle: "As tradition tells it." / "(traditional date)".
- **Invented words in a historical person's mouth are drama, not quotation.** Prefer a fictional or minor witness as the
  voice (a boatman, a retainer, the sword). Never caption invented lines as "— Musashi". If you quote *Gorin no Sho* or a
  chronicle, quote a verified translation and cite it.
- A traditional line ("Kojirō, you have already lost") may be used, labelled as tradition.
- Cursed swords are fiction and are presented as legend.

---

## 9. The film JSON outline

Write the **body** as its own file starting at `t = 0` (`film/<name>-body.json`), then scaffold:
`node engine/new-film.mjs <name> --jp 漢字 --en TITLE --sub "…" --next "Next: …" --body film/<name>-body.json`
(adds the 6 s opening, shifts every time by +6, overlays the end card). The scene-specific parts:

```json
{
  "title": "…", "format": "vertical", "fps": 24, "width": 1280, "height": 720, "letterbox": 2.39, "duration": 24,
  "scene": { "logline": "…", "template": "standoff-and-single-cut", "want": "…", "obstacle": "…", "subtext": "…",
             "setups": [["oar", "shavings"]] },
  "voice": [ { "id": "L1", "who": "boatman", "t": 0.4, "text": "I rowed him to the island.",
               "voice": "elder", "style": "low, close, slow", "note": "to confess · tired · pause after 0.8" } ],
  "shots": [ { "id": "B1", "name": "eye-reveal: Musashi", "shotType": "eye-reveal", "mode": "dawn", "start": 0, "end": 4,
               "rig": { "type": "face", "subject": "musashi.head", "fov": 22, "feel": "crane" } } ],
  "performances": { "musashi": { "character": "musashi", "keys": [ { "t": 0, "pose": "stand-blade-low" } ] } },
  "events": { "impact": 13.6 }, "shakes": [ { "t": 13.6, "dur": 0.5, "amp": 0.015, "note": "the cut" } ],
  "titles": [ { "start": 0.4, "end": 2.6, "style": "bottom", "en": "I rowed him to the island." } ],
  "sounds": [ { "id": "wind-bed", "t": 0, "query": "wind ambience", "min": 20000, "max": 600000, "len": 24, "gain": 0.25, "bed": true } ]
}
```
- `voice` is read by VOICE: `python3 tools/voice.py film/<name>.json` renders each line, then `engine/sound.mjs`
  mixes them (beds ducked under speech). `who` is the performer id (its eye glow follows the line). Put the playable
  verb, extra quality tags and the intended pause in `note`; only `style` words change the sound.
- `scene` and `shots[].shotType` are **scene-writing fields** the checker ignores: they keep the intent next to the data.
- Lines also go in `titles` as `bottom` subtitles (sound-off viewers).
- Camera: `library/shots.json` holds a tested rig per shot type (and many more shot names); copy the rig from there
  when it exists — it wins over the table in §7.
- Sets: only `dawn` (island, sea) and `studio` (dark sword studio) exist. Another location needs a set builder
  (`docs/FILM-FORMAT.md` "Today's limit"); write it in the outline as "set: planned".

---

## 10. Quality checklist (every "no" is a rewrite)

**Story**
- [ ] One sentence says who wants what and what it costs.
- [ ] Frame 1 is lit; the first line or image names a stake within 1 s.
- [ ] One set-up, one pay-off, and the pay-off changes the meaning.
- [ ] The subtext is never said aloud.
- [ ] The decisive moment lands after 60% of the runtime and happens **once**.
- [ ] There is at least one 0.8 s+ silence (ma) before the cut.
- [ ] The ending lingers (zanshin / mono no aware: something beautiful is lost or almost lost).

**Lines**
- [ ] 4–6 lines, inside the word budget, read aloud to a timer.
- [ ] Each line has one concrete image; no banned cliché; no adjective endings.
- [ ] Lines shorten toward the cut. One triad at most.
- [ ] Every line has a playable verb and a pause value. The Ronin says nothing.

**Picture and sound**
- [ ] Every beat has a move or pose that exists, a shot type, a sound and (if any) an effect with its status.
- [ ] One `impact-zoom`, one slow-motion moment. 70% darkness in monologue shots; glow is the brightest thing.
- [ ] Amber = human, crimson = curse; paint and shards, never blood; death = light going out.
- [ ] Silence before the blow; music ducked under impacts; subtitles on.

**Honesty and house rules**
- [ ] Historical claims marked in `research/`; tradition labelled on screen; no invented quote captions.
- [ ] Signature opening and end card kept (or the owner approved a change).

---

## 11. Three worked examples (complete)

### Example A — historical: **"The Oarsman"** (Ganryūjima, 1612) · 42 s published (6 s opening + 36 s body)

**Logline:** Rowed to the island by a man who never speaks, a boatman watches an oar become an answer.
**Template:** `standoff-and-single-cut`, told by a witness. **Want:** Kojirō wants to end it with his long sword;
Musashi wants to end it with one blow; the boatman wants to understand what he carried. **Obstacle:** the long sword's
reach. **Subtext:** the duel was decided before it began — by waiting, by the oar, by the scabbard in the sea.
**Set-up → pay-off:** the spare oar (body 2 s) → "I kept the shavings" (body 33 s). The thrown scabbard → "you have
already lost" (tradition).
**History (research/ganryujima.md):** the duel and Kojirō's death are documented; lateness, the oar sword, the thrown
scabbard, the line, the headband and the single blow are tradition (labelled); the boatman's voice and words are our choice.

**Lines** (body times; published = +6 s)
| t | Speaker · direction | Line | Pause after |
|---|---|---|---|
| 0.4 | BOATMAN · *to confess* · low, close, tired | "I rowed him to the island." | 0.8 |
| 2.6 | BOATMAN · *to confess* · held back | "He did not speak. Not once." | 1.2 |
| 6.0 | BOATMAN · *to marvel* · close | "He carved my spare oar… into a sword. Longer than the other man's." | 1.5 |
| 11.0 | BOATMAN · *to warn* · falling | "The other man had waited since morning." | 6.0 (let the draw play) |
| 19.4 | MUSASHI · *to dismiss* · cold, quiet, no reverb | "Kojirō… you have already lost." | 4.0 (ma, then the cut) |
| 28.4 | BOATMAN · *to report* · flat | "One blow." | 1.0 |
| 30.2 | BOATMAN · *to confess* · tired, smile | "Then he asked me to row." | 2.0 |
| 33.0 | BOATMAN · *to keep* · whisper, close | "I kept the shavings." | — |
Words: 49 (budget for ~22 voiced seconds ≈ 44–50). Subtitle at 19.4: "As tradition tells it."

**Beat map** (body times)
| Beat | t | Move / pose | Shot type | Sound | Effect |
|---|---|---|---|---|---|
| 0 Hook (over the opening) | pub. 0.3 | — | paper sea (opening) | `title-taiko` + line 1 begins at pub. 0.4 | opening's first frame lit |
| 1 World | 0–5 | musashi `stand-blade-low` in the boat (`rideBoatUntil`) | `over-shoulder-standoff` (boat, behind Musashi toward the island) | `sea-bed`, `rowing` | — |
| 1 Weapon | 5–10 | — | `blade-slide` (studio macro along Kojirō's long sword) | `reveal-gong` (soft) | glow travels the seam |
| 2 Arrival | 10–15 | musashi walks ashore (`walk`) | `silhouette-wide` (Kojirō small, waiting) | `steps-in` | — |
| 2 Standoff | 15–21 | kojiro `rest-hand-on-hilt` → `iai-draw` → `blade-out-hand-on-saya` → `throw-scabbard`; musashi `stand-blade-low` | `over-shoulder-standoff` (behind Kojirō) | `draw-shing`, `throw-whoosh`, `splash` | events `kojiro-draw`, `kojiro-throws-scabbard`, `scabbard-splash` |
| 3 Ma | 21–23.5 | both hold; musashi → `jodan-high` | `eye-reveal` (Musashi's amber eyes) | wind only, music out | eye glow brightens |
| 4 The cut | 23.5–27 | kojiro `jodan-high-wind-up` → `shomen-strike` (cuts the headband); musashi `jodan-high-wind-up` → `shomen-strike` at 25.6 | `impact-zoom` | `whoosh-b`, `impact`, paper tear | `events.impact` 25.6, `headband-cut` 25.45, shake 0.015, hit-stop, shards |
| 5 Zanshin | 27–32 | musashi `zanshin`; kojiro `struck-reel` → `kneel-collapse` → `fallen` | `orbit-zanshin` (40°, crane) | silence → `temple-bell` low | Kojirō's inner light fades out |
| 5 Leaving | 32–36 | musashi walks to the boat | `silhouette-wide` (boat on the bright strait) | `sea-bed`, `rowing` | end card over the last 2.6 s |

**Outline:** start from `film/ganryujima.json` (it already has these events, poses and sets); retime the shots to the
table, change the shot rigs to the shot types above, add `voice` and `bottom` subtitles, make it `"format": "vertical"`.

---

### Example B — cursed-sword fiction: **"One Inch"** (Kurenai-oni) · 30 s published (6 + 24)

**Logline:** A swordswoman orders a silent ronin to surrender the blade that kills its owners; the blade wants her light,
and he has one cut to decide whose.
**Template:** `cursed-blade-awakens`. **Want:** Hana wants the sword sealed; Kurenai-oni wants her light; the Ronin wants
to stay human. **Obstacle:** his own hand. **Subtext:** he is already losing to the sword, and they both know it.
**Set-up → pay-off:** the legend "it cuts the light out of whatever it touches" (story bible), shown as the sword's hunger
for her glow (body 5 s) → he cuts her **lantern**, not her (body 15.6 s); its light goes out, hers stays.
**History:** none; early Edo setting is our choice; the sword is legend.
**Cast:** `ronin` (sword `kurenai-oni`), `hana` (the swordswoman who hunts cursed blades; check `hana.json` is her look).
Prop: hand lantern (chōchin) — **planned**; fallback: the cut takes her sword's tassel and her amber glow flickers but holds.

**Lines**
| t | Speaker · direction | Line | Pause after |
|---|---|---|---|
| pub. 0.3 | HANA · *to warn* · low, cold | "Every man who carried that sword… is dead." | 1.0 |
| 1.0 | HANA · *to bargain* · steady | "Give it to me. And you live." | 2.0 |
| 5.4 | KURENAI-ONI · *to tempt* · whisper, close, delighted (`inner`, on the Ronin so his eyes pulse) | "She is so bright." | 2.5 |
| 10.2 | HANA · *to plead* · whisper, held back | "Don't." | 3.5 (ma) |
| 18.6 | KURENAI-ONI · *to sulk* · whisper, falling | "…Next time." | — |
Words: 22. The Ronin says nothing; his line is the cut.

**Beat map** (body times)
| Beat | t | Move / pose | Shot type | Sound | Effect |
|---|---|---|---|---|---|
| 0 Hook | pub. 0–1 | — | opening; line over taiko | `title-taiko` | crimson glint in the first lit frame (our choice) |
| 1 Want | 0–5 | hana `hasso`; ronin `rest-hand-on-hilt` | `over-shoulder-standoff` (behind Hana) | `sea-bed`, `wind-bed` | Ronin amber; seam at his hip leaks crimson |
| 2 Temptation | 5–9 | — | `blade-slide` (macro along Kurenai-oni, studio) | low drone, whisper | crimson brightens along the seam |
| 2 The flicker | 9–13 | ronin holds `rest-hand-on-hilt` (stillness) | `eye-reveal` (Ronin) | wind only | eyes flicker crimson for 2 frames at 11.5 |
| 3 Ma | 13–15 | hana steps in (`step-in`, dist 0.5) | `low-hero-push` | silence | — |
| 4 The cut | 15–17 | ronin `iai-draw` at 15.2 → `blade-out-recover`; hana `uke-high` too late | `whip-reveal` (hides the draw) → `impact-zoom` on the lantern | `draw-shing`, `whoosh-a`, paper tear | `events.impact` 15.6, shake 0.012, crimson smear ribbon, ink impact frame, lantern light out (planned) |
| 5 Zanshin | 17–21 | ronin `zanshin`; hana holds `uke-high` | `orbit-zanshin` (30°) | silence → one `temple-bell` | Hana's amber glow steady; his eyes crimson → amber over 2 s |
| 5 Leaving | 21–24 | ronin `stand-blade-low`, walks away | `silhouette-wide` | `steps-out`, `sea-bed` | crimson seam dims; end card |

**Outline (body)**
```json
{ "title": "One Inch", "format": "vertical", "fps": 24, "width": 1280, "height": 720, "letterbox": 2.39, "duration": 24,
  "scene": { "logline": "A swordswoman orders a silent ronin to surrender the blade that kills its owners…",
             "template": "cursed-blade-awakens", "want": "Hana: seal the sword", "obstacle": "his own hand",
             "subtext": "he is already losing to the sword", "setups": [["it cuts the light out", "the lantern goes dark"]] },
  "voice": [ { "id": "L2", "who": "hana", "t": 1.0, "text": "Give it to me. [pause 0.3] And you live.", "voice": "empress", "style": "measured, cold", "note": "to bargain · pause after 2.0" },
             { "id": "L3", "who": "ronin", "t": 5.4, "text": "She is so bright.", "voice": "warlord", "style": "whisper, close, slow", "inner": true, "note": "the sword speaks, not the Ronin · to tempt, delighted" },
             { "id": "L4", "who": "hana", "t": 10.2, "text": "Don't.", "voice": "empress", "style": "whisper, soft", "note": "to plead · held back · then 3.5 s of ma" },
             { "id": "L5", "who": "ronin", "t": 18.6, "text": "Next time.", "voice": "warlord", "style": "whisper, close, slow", "inner": true, "note": "the sword · to sulk · falling" } ],
  "shots": [
    { "id": "B1", "name": "over-shoulder-standoff", "shotType": "over-shoulder-standoff", "mode": "dawn", "start": 0, "end": 5,
      "rig": { "type": "frame", "subjects": ["hana", "ronin"], "angle": 60, "elevation": 4, "fov": 32, "feel": "crane" } },
    { "id": "B2", "name": "blade-slide: Kurenai-oni", "shotType": "blade-slide", "mode": "studio", "start": 5, "end": 9,
      "camera": [ { "t": 5, "pos": [0.3, 1.2, 0.6], "look": [0, 1.1, 0], "fov": 24 }, { "t": 9, "pos": [-0.3, 1.15, 0.5], "look": [-0.2, 1.1, 0], "fov": 22 } ] },
    { "id": "B3", "name": "eye-reveal: Ronin", "shotType": "eye-reveal", "mode": "dawn", "start": 9, "end": 13,
      "rig": { "type": "face", "subject": "ronin.head", "fov": 20, "feel": "crane" } },
    { "id": "B4", "name": "low-hero-push", "shotType": "low-hero-push", "mode": "dawn", "start": 13, "end": 15,
      "rig": { "type": "frame", "subjects": ["ronin", "hana"], "size": "full", "elevation": -12, "fov": 34, "feel": "dolly" } },
    { "id": "B5", "name": "whip-reveal → impact-zoom", "shotType": "impact-zoom", "mode": "dawn", "start": 15, "end": 17,
      "rig": { "type": "frame", "subjects": ["ronin", "hana"], "size": "close", "fov": 30, "feel": "torpedo", "behaviours": ["whip", "push"] } },
    { "id": "B6", "name": "orbit-zanshin", "shotType": "orbit-zanshin", "mode": "dawn", "start": 17, "end": 21,
      "rig": { "type": "orbit", "subjects": ["ronin", "hana"], "radius": 4, "height": 1.4, "deg0": 20, "deg1": 50, "fov": 34, "feel": "crane" } },
    { "id": "B7", "name": "silhouette-wide", "shotType": "silhouette-wide", "mode": "dawn", "start": 21, "end": 24,
      "rig": { "type": "frame", "subjects": ["ronin"], "size": "wide", "elevation": 2, "fov": 40, "feel": "locked" } } ],
  "performances": {
    "ronin": { "character": "ronin", "keys": [ { "t": 0, "pose": "rest-hand-on-hilt", "x": 0, "z": 1.6, "ry": 3.14159 },
      { "t": 15.0, "pose": "rest-hand-on-hilt" }, { "t": 15.2, "pose": "iai-draw" }, { "t": 15.75, "pose": "iai-draw" },
      { "t": 16.4, "pose": "blade-out-recover" }, { "t": 17.2, "pose": "zanshin" }, { "t": 21.0, "pose": "zanshin" }, { "t": 21.8, "pose": "stand-blade-low" } ] },
    "hana": { "character": "hana", "keys": [ { "t": 0, "pose": "hasso", "x": 0, "z": -1.6, "ry": 0 }, { "t": 13.2, "move": "step-in", "dist": 0.5 },
      { "t": 15.45, "pose": "uke-high" }, { "t": 21.0, "pose": "uke-high" } ] } },
  "duels": [ { "a": "ronin", "b": "hana", "from": 0, "to": 21, "note": "they watch each other" } ],
  "events": { "impact": 15.6 },
  "shakes": [ { "t": 15.6, "dur": 0.4, "amp": 0.012, "note": "the lantern is cut" } ],
  "titles": [ { "start": 1.0, "end": 3.2, "style": "bottom", "en": "Give it to me. And you live." },
              { "start": 5.4, "end": 7.4, "style": "bottom", "en": "She is so bright." },
              { "start": 10.2, "end": 11.6, "style": "bottom", "en": "Don't." },
              { "start": 18.6, "end": 20.4, "style": "bottom", "en": "…Next time." } ],
  "sounds": [ { "id": "sea-bed", "t": 0, "query": "ocean waves shore calm", "min": 20000, "max": 600000, "len": 24, "gain": 0.3, "bed": true },
              { "id": "draw-shing", "t": 15.15, "query": "sword draw", "min": 300, "max": 4000, "len": 1.5, "gain": 0.9 },
              { "id": "whoosh-a", "t": 15.45, "query": "whoosh fast", "min": 200, "max": 3000, "len": 1, "gain": 0.8 },
              { "id": "temple-bell", "t": 18.0, "query": "temple bell", "min": 2000, "max": 30000, "len": 5, "gain": 0.4 },
              { "id": "steps-out", "t": 21.8, "query": "footsteps sand", "min": 1000, "max": 20000, "len": 2.5, "gain": 0.5 } ] }
```

---

### Example C — quiet monologue (like the references): **"Folded Prayers"** (Sekigahara, 1600) · 28 s published (6 + 22)

**Logline:** Before the fog lifts at Sekigahara, a general whose armour is folded from his mother's prayers counts how
many are left.
**Template:** `monologue-before-battle`. **Want:** to go into the battle whole. **Obstacle:** there are not enough prayers
left. **Subtext:** he knows he will not come home; he never says it. **Set-up → pay-off:** "one for every winter I came
home" → "there are not enough for today" (the arithmetic is the grief); the light in his chest → "look for the light."
**History:** the battle of Sekigahara, 21 October 1600, is documented; the morning fog is commonly reported in
secondary accounts (no detailed primary sources survive, per Nippon.com); the general and his armour are fiction (story bible).
**Cast:** the Gold Armoured Samurai — **no library character yet**; use `musashi`'s body as a stand-in with a gold
outfit, or add `library/characters/gold-general.json`. Set: `studio` (dark) for the close shots; fog **planned**.

**Lines** (one take per line, placed in the timeline)
| t | Direction | Line | Pause after |
|---|---|---|---|
| pub. 0.3 | *to confide* · low, close, [exhales] first | "My mother folded this armour from her prayers." | 1.2 |
| 3.6 | *to remember* · smile, close | "One for every winter I came home." | 1.5 |
| 7.6 | *to admit* · falling, held back | "There are not enough for today." | 2.0 |
| 12.0 | *to resolve* · rising | "So I will spend them slowly." | 2.5 (raise the sword) |
| 17.0 | *to order* · quiet, certain | "When the fog lifts… look for the light." | — |
Words: 34 (budget for ~16 voiced seconds ≈ 32). Music: one low drone, swells only under the last line, then cuts dead.

**Beat map** (body times)
| Beat | t | Pose | Shot type | Sound | Effect |
|---|---|---|---|---|---|
| 0 Hook | pub. 0–1 | — | opening (lit), line 1 over the taiko | `title-taiko` soft | — |
| 1 Want | 0–4 | `stand-blade-low` | `eye-reveal` (amber through the visor slit; 70% black) | `wind-bed` | eye glow pulses on each stressed word (planned) |
| 2 Memory | 4–8 | — | `blade-slide` along the folded armour plates (studio macro) | paper creak, breath | light leaks through the folds |
| 2 The admission | 8–12 | `stand-blade-low` | `low-hero-push` (3%/s) | drone enters | — |
| 3/4 The gesture | 12–17 | `stand-blade-low` → `jodan-high` at 14.0 (slow, speed 0.5) | `low-hero-push` continues; blade into one shaft of light | drone rises; `reveal-gong` at 14.6 | blade edge flares amber |
| 5 Last image | 17–22 | `jodan-high` held | `silhouette-wide` (small figure, fog, 70% empty) | music swells under the line, then silence at 20.5 | glow dims one step; cut to black; end card |

**Outline (shots only; the rest as in Example B)**
```json
[ { "id": "C1", "name": "eye-reveal: general", "shotType": "eye-reveal", "mode": "studio", "start": 0, "end": 4,
    "rig": { "type": "face", "subject": "general.head", "fov": 18, "feel": "crane" } },
  { "id": "C2", "name": "blade-slide: folded armour", "shotType": "blade-slide", "mode": "studio", "start": 4, "end": 8,
    "camera": [ { "t": 4, "pos": [0.4, 1.3, 0.7], "look": [0, 1.25, 0], "fov": 22 }, { "t": 8, "pos": [-0.35, 1.2, 0.65], "look": [0, 1.2, 0], "fov": 20 } ] },
  { "id": "C3", "name": "low-hero-push", "shotType": "low-hero-push", "mode": "studio", "start": 8, "end": 17,
    "rig": { "type": "frame", "subjects": ["general"], "size": "full", "elevation": -14, "fov": 30, "feel": "dolly" } },
  { "id": "C4", "name": "silhouette-wide", "shotType": "silhouette-wide", "mode": "dawn", "start": 17, "end": 22,
    "rig": { "type": "frame", "subjects": ["general"], "size": "wide", "elevation": 1, "fov": 42, "feel": "locked" } } ]
```
Performer `general`: `{ "character": "musashi", "keys": [ { "t": 0, "pose": "stand-blade-low" }, { "t": 13.0, "pose": "stand-blade-low" }, { "t": 15.0, "pose": "jodan-high" }, { "t": 22, "pose": "jodan-high" } ] }` (stand-in body until the gold character exists).

---

## 12. Sources (consulted 2026-11-23; marks as in §0)

**Shorts hooks and retention**
- [C] vidIQ, "Viral hooks for YouTube Shorts": https://vidiq.com/blog/post/viral-video-hooks-youtube-shorts/
- [C] Opus Clip, "YouTube Shorts hook formulas that drive 3-second holds": https://www.opus.pro/blog/youtube-shorts-hook-formulas
- [C] Opus Clip, "Ideal Shorts length and format for retention": https://www.opus.pro/blog/ideal-youtube-shorts-length-format-retention
- [C] vidIQ, "Double watch time by looping Shorts": https://vidiq.com/pt/blog/post/double-youtube-watch-time-looping-shorts
- [C] ContentStudio, "YouTube Shorts analytics": https://contentstudio.io/blog/youtube-shorts-analytics-guide
- [D] YouTube Help, audience retention / key moments: https://support.google.com/youtube/answer/9314415

**Screenwriting**
- [C] Final Draft, set-ups and pay-offs: https://www.finaldraft.com/blog/how-to-put-setups-and-payoffs-in-your-scripts
- [C] Penberth, "4 set-up and pay-off principles": https://jpenberth.substack.com/p/4-setup-and-payoff-principles-that
- [C] Arc Studio, scene structure (want → obstacle → outcome): https://www.arcstudiopro.com/blog/how-to-structure-a-scene-to-keep-readers-hooked
- [C] Filmdaft, beats as units of change: https://filmdaft.com/how-to-use-and-write-story-beats-in-a-screenplay/

**Speech and rhetoric**
- [C] Interesting Literature, Henry V "Once more unto the breach": https://interestingliterature.com/2021/09/henry-v-once-more-unto-breach-dear-friends-speech-summary-analysis/
- [C] Journal of the Northern Renaissance on the Crispin speech and memory: https://jnr2.hcommons.org/2010/1123/
- [C] O'Reilly, "The rule of three" (a principle, not a rule): https://www.oreilly.com/library/view/the-lost-art/0814470548/0814470548_ch09lev1sec1.html

**Japanese aesthetics and structure**
- [D] Stanford Encyclopedia of Philosophy, "Japanese Aesthetics" (mono no aware, wabi, sabi): https://plato.stanford.edu/entries/japanese-aesthetics/
- [C] Wikipedia, Jo-ha-kyū: https://en.wikipedia.org/wiki/Jo-ha-ky%C5%AB · Stanford Noh, form: https://noh.stanford.edu/form
- [C] Wikipedia, Kishōtenketsu: https://en.wikipedia.org/wiki/Kish%C5%8Dtenketsu · Poets & Writers: https://www.pw.org/content/the_joy_of_holding_back_the_east_asian_fouract_structure
- [C] Wikipedia, Ma (negative space): https://en.wikipedia.org/wiki/Ma_(negative_space) · Final Draft on Miyazaki and ma: https://www.finaldraft.com/blog/hayao-miyazaki-says-ma-is-an-essential-storytelling-tool

**Samurai film**
- [C] BFI Sight & Sound, "The last duel: the ending of Sanjuro" (about 20 s of motionless staring, then one flash): https://bfi.org.uk/sight-and-sound/features/last-duel-ending-sanjuro
- [C] Deep Focus Review, Sanjuro (clocks ~26 s of silence): https://deepfocusreview.com/definitives/sanjuro/
- [C] Criterion, "Harakiri: Kobayashi and History": https://www.criterion.com/current/posts/381-harakiri-kobayashi-and-history · Deep Focus Review, Harakiri (out-of-order revenge story; flashbacks expose the clan): https://deepfocusreview.com/definitives/harakiri/
- [C] PopMatters on Zatoichi (2003) sound: https://popmatters.com/blind-swordsman-zatoichi-2496228505.html
- Anime fight craft (hit-stop, impact frames, zanshin, iaidō sequence, sound layering): `research/anime-fight-craft.md`
- [C] Fight stakes before the clash (fan analysis, weak): https://www.gamesradar.com/entertainment/anime-movies/demon-slayer-infinity-castle-features-cinemas-best-fight-of-the-year-but-only-because-it-swaps-out-sword-strikes-for-gut-punches

**Voice direction**
- [D] ElevenLabs, Eleven v3 prompting (audio tags, no SSML breaks on v3/v4, ellipses, capitals, speed): https://elevenlabs.io/docs/best-practices/prompting/eleven-v3
- [D] ElevenLabs, TTS best practices (break tags on older models, instability): https://elevenlabs.io/docs/overview/capabilities/text-to-speech/best-practices
- [C] USC, "Directing with action verbs": https://scalar.usc.edu/works/experiments-in-game-based-pedagogy/media/directing-with-action-verbs
- [C] Radio Ranch, "Always find the playables": https://radio-ranch.com/directing-radio-spots-always-find-the-playables/

**History used in the examples**
- `research/ganryujima.md` (Ganryūjima marks)
- [C] Sekigahara fog: NPS https://www.nps.gov/articles/000/battle-of-sekigahara.htm · Britannica https://www.britannica.com/event/Battle-of-Sekigahara · Nippon.com (no detailed primary sources) https://www.nippon.com/en/articles/-/12684
