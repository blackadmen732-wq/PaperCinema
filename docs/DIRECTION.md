# DIRECTION: how to direct a scene (camera, cuts, light, rhythm)

The human guide to directing Paper Cinema films. The working procedure for an AI is the skill
`.claude/skills/scene-direction/SKILL.md`; the ready-to-paste data is `library/shots.json` (49 named shots, 17 direction
styles, 11 lighting moods, a story-beat map). Camera fields: `CAMERA.md` §7. Effects: `EFFECTS-CATALOG.md`.
Story and lines come first: `SCENE-WRITING.md`.

**Marks:** **[D]** documented (a primary source, or our own code and tests), **[C]** commonly reported (critics,
video essays, trade press, practitioner blogs agree), **[I]** our inference. We describe techniques only; we copy no
frames. Sources: §9. Researched 2026-11-23 with plain web search (Firecrawl was out of credits).

---

## 1. Film grammar in one page

### Shot sizes (KUROKO `size`)
| Size | Frames | Says | KUROKO |
|---|---|---|---|
| Extreme wide | World, figures tiny | Scale, fate, loneliness | `size: "wide"`, `dist` 1.2–1.4 |
| Wide / full | Head to toe | Geography, choreography | `"wide"` / `"full"` |
| Medium | Waist up | Conversation, intent | `"medium"` |
| Close-up | Head and shoulders | Emotion | `face` rig, `dist` 0.6–0.9, or `"close"` |
| Extreme close-up | Eyes, hand, blade edge | Decision, detail, the trigger | `face` `dist` 0.38–0.45, fov 18; `frame` on `.hand` `size: "extreme"` |

### Lenses (`fov` is vertical degrees)
Wide lenses close to the subject feel immediate and involving; long lenses flatten depth, stack layers and make a gap
look shorter [C]. Perspective comes from the camera's **distance**; the KUROKO frame rig moves the camera back
automatically when you narrow the fov, so a small fov gives real compression.

| fov | Full-frame lens, 9:16 (36 mm side vertical) | Full-frame lens, 16:9 | Use |
|---|---|---|---|
| 16 | 128 mm | 72 mm | Compression, Leone eyes, pressure |
| 20 | 102 mm | 57 mm | Kurosawa long lens, weather layers |
| 24 | 85 mm | 48 mm | Faces, impact |
| 28 | 72 mm | 41 mm | Close coverage, binds |
| 34 | 59 mm | 33 mm | Default coverage |
| 40 | 49 mm | 28 mm | Space, wide holds, cranes |
| 45–50 | 43–39 mm | 24–22 mm | Speed, tracking dives |

### Angles and height
Eye level = equals. Low (`elevation` −8 to −15, camera 0.2–0.5 m) = power, defiance. High (+25 to +40) = defeat,
exposure. Dutch (`roll`, max ±10 today) = imbalance, a bind, a demon's view [C].

### Blocking and coverage
- **Blocking** is where the fighters stand and move; the camera follows from it. Spielberg's "oners" get the wide,
  the two-shot and the close inside one take by moving the actors, not by cutting [C]. Stahelski (John Wick) blocks
  with the camera, starts wide and dollies in, and prefers few cuts so the viewer believes the performer [C].
- **Coverage** is the set of angles for one beat (a wide master, two over-the-shoulders, singles, inserts). In
  data that means several shots with different rigs on the same performances.

### Continuity rules
- **180° rule:** the camera stays on one side of the line between the fighters, so left and right never swap [C].
  Cross it only on purpose, on a neutral shot or inside one visible move.
- **30° rule:** consecutive shots of the same subject differ by at least 30°, or it reads as a jump cut [C].
- **Eyeline match:** a look off-screen, then what is seen (or the other person looking back the opposite way) [C].
- **Shot / reverse shot:** alternate matching angles of the two fighters; same fov, height and size on both sides [C].

### Editing
- **Cut on action:** cut mid-movement; the motion carries the eye across [C] (Kurosawa "tends to cut on movement").
- **Match cut:** a shape, motion or composition repeated across the cut [C]. Satoshi Kon used general match cuts,
  exact graphic matches and intercut mirrored time periods [C].
- **J cut / L cut:** the next scene's sound starts before its picture (J) or this scene's sound runs on under the next
  picture (L) [C].
- **Murch's Rule of Six:** a cut is judged by emotion 51%, story 23%, rhythm 10%, eye-trace 7%, screen plane 5%,
  3D space 4%; never give up emotion before story [C].
- **Shot length:** classic Hollywood averaged about 8–11 s per shot; mainstream films now average 3–5 s; some 1990s
  films hit 2.7 s [C, Bordwell]. Hong Kong action is built on **pause-burst-pause** and holds shots long enough to feel
  the rhythm instead of cutting on every hit [C].

---

## 2. Direction styles (presets in `library/shots.json → styles`)

| Style | Inspired by | Key shots | Cut rhythm (avg s) | Light / grade | Signature |
|---|---|---|---|---|---|
| `ufotable-flow` | ufotable (Demon Slayer) | eye-reveal, glint-insert, ufotable-glide, impact-zoom, freeze-orbit | 0.8–1.6 | rim-glow / moonlit | Action centred, smooth 3D glides, body on twos and camera on ones, glint → strike → sparks [C] |
| `mappa-kinetic` | MAPPA (Jujutsu Kaisen) | torpedo-track, leading-track, whip-reveal, handheld-clash | 0.6–1.2 | hard-contrast / demonic | Erratic mobile camera, strong 3D space, heavy blows [C] |
| `kurosawa-weather` | Kurosawa | telephoto-weather, telephoto-compress, wick-wide-oner, delayed-reaction-hold | 2.5–6 | overcast-grey / kurosawa | Weather in every frame, long lenses, cut on movement, long stillness then one instant [C] |
| `leone-standoff` | Leone | establishing-wide, leone-eyes, hand-on-hilt, foot-grind | 3.0 → 0.5 accelerating | hard-sun / dawn | Extreme wide vs extreme close-up, tighter on the eyes every cut [C] |
| `kubrick-symmetry` | Kubrick | kubrick-one-point, slow-push-monologue | 4–8 | practical-symmetry / neutral | Centred one-point perspective, slow mechanical moves, dread through order [C] |
| `wkw-smear` | Wong Kar-wai / Doyle | wkw-drift, handheld-clash | 1.5–4 | neon-lantern / lantern | Step-printed stutter with a smooth camera, saturated colour [C] |
| `deakins-low-key` | Villeneuve / Deakins | silhouette-wide, tiny-in-the-dark, walk-away | 3–7 | silhouette / moonlit | Few sources, silhouettes, big negative space [C] |
| `spielberg-oner` | Spielberg | anchor-oner, crane-reveal | 4–10 | dawn-gold / dawn | One invisible moving take per dramatic unit [C] |
| `stranger-nakamura` | Sword of the Stranger (Yutaka Nakamura) | torpedo-track, ufotable-glide, jump-back-reveal | 0.8–2 | snow-cold / moonlit | Bodies fly and the camera flies with them, blade arcs, terrain bursts [C] |
| `champloo-scratch` | Samurai Champloo | whip-reveal, hk-double-hit, kon-match-cut | 0.5–1.5 | hard-sun / dawn | Cuts on the beat, scratch transitions, abrupt endings [C] |
| `shinkai-light` | Makoto Shinkai | sky-tilt, crane-reveal, eye-reveal | 2–5 | god-rays / dawn | Light as subject: flares, god rays, bloom, clouds [C] |
| `kon-match` | Satoshi Kon | kon-match-cut, hook-flash-forward | 1–3 | match both sides | Every scene change is a match [C] |
| `itano-circus` | Ichirō Itano | itano-dive, torpedo-track | 0.5–1.2 | rim-glow / demonic | Many crossing trails, the camera dives among them [C] |
| `arcane-painterly` | Arcane (Fortiche) | over-shoulder-standoff, low-hero-push, impact-close | 1.5–3.5 | chiaroscuro / lantern | Hand-directed light and colour per shot, painted texture over 3D, 2D effects over 3D [C] |
| `hk-rhythm` | Hong Kong action | wick-wide-oner, hk-double-hit, profile-two-shot | 1.5–3 | dawn-gold / dawn | Pause-burst-pause, a big hit shown twice [C] |
| `wick-wide` | John Wick | wick-wide-oner, anchor-oner, walk-away | 3–6 | neon-lantern / lantern | Wide full-body frames, long takes [C] |
| `knightfall-dark-monologue` | Owner's reference Shorts | eye-reveal, leone-eyes, slow-push-monologue, low-hero-push, tiny-in-the-dark | 2.5–5 | chiaroscuro / lantern | 70% darkness, one shaft, glowing eye ECU, slow push, one gesture, cut to black [I] |

Each style in the JSON also lists feels, fov range, shake policy, colour, effects (`fx` ids from
`library/effects.json`), and sound. **One style per film, plus at most one accent.**

---

## 3. Which shots for which fight beat

The Strike Grammar (ready → wind-up → slash → hit-stop → follow-through → reaction) and the story shape
(`STYLE-AND-FIGHT-SYSTEM.md` §4) map to shots like this (`beat_map` in the JSON):

| Beat | First choice | Alternatives | Rhythm |
|---|---|---|---|
| Hook (0–1 s) | `hook-flash-forward` or `eye-reveal` | `impact-silhouette`, `glint-insert` | 0.3–1 s, lit from frame 1 |
| World | `establishing-wide` | `crane-reveal`, `telephoto-weather`, `sky-tilt` | 2–4 s |
| Weapon | `draw-macro` | `blade-slide`, `glint-insert`, `hand-on-hilt` | 0.6–1.6 s |
| Arrival | `walk-away` (seen from behind) or `kubrick-one-point` | `silhouette-wide`, `low-hero-push` | 2–4 s |
| Tension / standoff | `standoff-orbit` → `over-shoulder-standoff` ↔ `reverse-over-shoulder` | `leone-eyes` (accelerating), `telephoto-compress`, `foot-grind` | 3 → 0.5 s, accelerating |
| Exchange | `lunge-dolly`, `handheld-clash`, `jump-back-reveal` | `torpedo-track`, `dutch-bind`, `stagger-dutch`, `wick-wide-oner`, `hk-double-hit`, `ufotable-glide` | 0.6–1.6 s, or one 3–6 s hold |
| Decisive blow | silence → `eye-reveal` → `leading-track` → `impact-zoom` + `impact-silhouette` | `freeze-orbit`, `anchor-oner` | insert 6–10 f, hit-stop longest |
| Aftermath | `delayed-reaction-hold` → `orbit-zanshin` | `high-vulnerable`, `crane-out-end`, `tiny-in-the-dark` | 1.5–3 s holds |
| Transitions | `cut-on-action`, `kon-match-cut` | `whip-reveal`, `foreground-wipe` (needs engine) | |

Typical 30 s fight Short (≈ 14 shots) [I]: hook 1 s → world 3 s → weapon 1.5 s → standoff 6 s (orbit, OTS, reverse, 3
accelerating eye inserts) → exchange 8 s (5–7 shots) → silence 1 s → decisive 2 s (eye, charge, impact zoom, ink
frame) → aftermath 5 s (frozen hold, zanshin orbit) → end card 2.6 s.

---

## 4. Lighting moods (`library/shots.json → lighting`)

| Mood | Key : fill | Key | Rim | Haze | Today |
|---|---|---|---|---|---|
| `chiaroscuro` | ≥ 8:1 | one hard side key | yes | light | studio mode + inner glow; Blender |
| `rim-glow` | no front fill | backlight above-behind | strong amber / crimson | medium | dawn mode, sun behind the fighters |
| `silhouette` | subject unlit, background ≥ 3 stops brighter | none | thin | medium-heavy | dawn mode, camera low facing the sun |
| `god-rays` | high | sun behind an occluder | yes | required | `light-shafts` cards (new); screen god rays planned |
| `dawn-gold` | 3:1 | low sun 10–20° | warm | sea haze | dawn mode (default set) |
| others | | | | | `hard-sun`, `overcast-grey`, `neon-lantern`, `snow-cold`, `hard-contrast`, `practical-symmetry`: sets not built yet |

Low-key lighting uses a dominant key and a high ratio such as 8:1, often one hard source; chiaroscuro keeps the face
partly visible while a silhouette removes it; a rim light sits behind the subject [C]. House rules: one warm key from
behind or the side, never flat front light; light inside the paper is power; amber = human, crimson = demonic.

---

## 5. Shorts (vertical 9:16) rules

1. **Hook in 1 s.** Viewers decide in about the first second; start mid-action or on the eye; the first frame is lit
   (no fade from black longer than 4 frames) [C].
2. **Safe zone.** The Shorts UI covers roughly the bottom 20–35% and the right 11–18% [C; third-party guides
   disagree, YouTube's own diagram is an image]. Conservative margins on 1080×1920: top 288, bottom 672, left 48,
   right 192 px; on our 720×1280 render: top 192, bottom 448, left 32, right 128 px. Eyes, contact points and text
   go inside.
3. **Depth, not width.** Stage near/far (over-the-shoulder 50–65°), not side by side. The far fighter ≥ 45% of frame
   height in two-shots [D docs/FIX-LIST.md].
4. **Use the height.** Low angles, cranes, sky tilts, falling paper.
5. **Fewer, bigger moments.** One impact zoom, one impact frame, one Dutch per scene.
6. **Letterbox strip** (reference look) via the fx `letterbox` effect; the film `letterbox` field is dropped in vertical.

---

## 6. Using the library

1. Pick the style; list the shots by beat (§3).
2. For each shot copy `rig` (9:16) or `rig_16x9` (16:9) into `shots[]`; rename `hero`/`foe`; add `shot.start` to anchor
   beat times. For the motion page copy `beat` into `film.camera` and set absolute times.
3. Read the entry's `engine` field: `ready`, `approx: …` (works, with a stated compromise) or `needs engine: …`.
4. `measured` gives the far subject's height as % of frame and its margin (1 = centre, 0 = edge) from our tests.

### What the tests found (every rig, both formats, against the `kuroko-duel` choreography) [D]
- In 9:16, a `frame` two-shot at `dist` 1 keeps the far fighter at only 17–20% of frame height, because the narrow
  horizontal view sets the distance. The library's 9:16 rigs use angle 50–65 and `dist` 0.5–0.75 (OTS: 44%).
- Single-subject `frame` angle 0 points the camera at the subject's front, which is on the duel line behind the
  opponent: use 20–70, positive for the hero and **negative for the foe** to stay on the same side.
- Orbit degrees are world azimuth; an orbit around two fighters' midpoint at radius < 4 m loses one of them in 9:16.
- Framing two `.hand` points makes the camera jump the line when the hands cross.
- All 49 library rigs keep their main subject in frame in both formats and stay on one side of the line.

---

## 7. Taste: cinematic vs amateur
See the table and checklist in the skill (§7). The short version: one subject and one job per shot; stillness, then
one fast thing; shake only on hits; earn close-ups with a wide first; vary lens and height with the emotion; silence
before the cut; a long hold after it.

## 8. Gaps (engine work the owner may want)
Rack focus / depth of field, whip-pan blur, foreground wipe, speed ramps and stepped body time (on twos), Dutch beyond
±10°, a letterbox in vertical from the film field, extra sets (night, rain, snow). Status lives in
`library/effects.json` and `FIX-LIST.md`.

---

## 9. Sources (technique only)

| Topic | Mark | Source |
|---|---|---|
| 180° rule, reverse cut | C | <https://en.wikipedia.org/wiki/180-degree_rule>, <https://www.masterclass.com/articles/understanding-the-180-degree-rule-in-cinematography>, <https://blog.frame.io/2016/08/01/break-180-degree-rule/> |
| 30° rule | C | <https://en.wikipedia.org/wiki/30-degree_rule> |
| Shot / reverse shot, eyeline | C | <https://www.adobe.com/creativecloud/video/production/cinematography/camera-shots-and-angles/reverse-shot.html> |
| J / L / match cuts | C | <https://www.studiobinder.com/blog/what-is-a-j-cut/>, <https://www.adobe.com/creativecloud/video/discover/j-cut-and-l-cut>, <https://www.descript.com/blog/article/learn-the-10-best-video-cuts-every-pro-editor-should-know> |
| Murch Rule of Six | C | <https://studiobinder.com/blog/walter-murch-rule-of-six>, <https://nofilmschool.com/2016/11/6-rules-good-cutting-according-oscar-winning-editor-walter-murch> |
| Shot lengths (intensified continuity) | C | <https://www.artforum.com/features/david-bordwell-2-195241/>, <https://pmc.ncbi.nlm.nih.gov/articles/PMC3485803> |
| Lenses and emotion | C | <https://www.premiumbeat.com/blog/filmmaking-conveying-emotions-with-lenses>, <https://www.indepthcine.com/videos/focal-length> |
| Dutch angle, whip pan, rack focus | C | <https://en.wikipedia.org/wiki/Dutch_angle>, <https://en.wikipedia.org/wiki/Whip_pan>, <https://www.studiobinder.com/blog/dutch-angle/> |
| Kurosawa: weather, movement, long lens, axial cuts, wipes | C | <https://Www.Wikipedia.org/wiki/Filmmaking_technique_of_Kurosawa>, <https://www.bfi.org.uk/features/how-akira-kurosawa-films-command-weather>, <https://filmmakermagazine.com/?p=93558> (Every Frame a Painting, "Composing Movement") |
| Sanjuro's frozen duel | C | <https://bfi.org.uk/sight-and-sound/features/last-duel-ending-sanjuro>, <https://www.criterion.com/current/posts/61> |
| Leone close-ups and standoffs | C | <https://www.rogerebert.com/scanners/opening-shots-the-good-the-bad-and-the-ugly>, <https://www.premiumbeat.com/blog/how-to-shoot-close-up-shots-like-sergio-leone> |
| Kubrick one-point perspective | C | <https://filmmakermagazine.com/?p=85083>, <https://screencrush.com/kubrick-one-point-perspective-mashup/> |
| Wong Kar-wai step printing | C | <https://www.bfi.org.uk/sight-and-sound/features/poet-time-wong-kar-wai-chungking-express>, <https://www.bfi.org.uk/interviews/christopher-doyle-shooting-chungking-express> |
| Deakins / Villeneuve silhouettes, simple lighting | C | <https://theasc.com/articles/deakins-blade-runner-2049>, <https://theasc.com/blog/the-film-book/sicario-interview-with-roger-deakins-asc-bsc> |
| Spielberg oner | C | <https://nofilmschool.com/2014/05/study-steven-spielbergs-cinematography-help-you-master-long-take>, <https://nofilmschool.com/spielberg-oner-raiders> |
| Demon Slayer visual grammar (twos, glint, centre framing, shake on ones, 5 attacks in 8 s) | C | <https://jbsiraudin.github.io/blog/demon-slayer-visual-grammar> |
| ufotable 3D environments + 2D characters | C | <https://wrongeverytime.com/2019/05/06/why-it-works-the-digital-arenas-of-demon-slayers-battles> |
| Jujutsu Kaisen / Sunghoo Park action | C | <https://AnimeNewsNetwork.com/this-week-in-anime/2024-02-15/.207600>, <https://slashfilm.com/1019970/adapting-jujutsu-kaisens-fight-scenes-to-anime-was-the-easy-part> |
| Sword of the Stranger (Yutaka Nakamura) | C | <https://en.wikipedia.org/wiki/Yutaka_Nakamura>, <https://dotandline.net/the-greatest-sword-fight-ever-animated/> |
| Samurai Champloo (hip-hop, scratch transitions) | C | <https://en.wikipedia.org/wiki/Samurai_Champloo>, <https://animationobsessive.substack.com/p/the-music-of-samurai-champloo> |
| Shinkai light, flares, god rays | C | <https://vfxvoice.com/suzume-is-hardly-disastrous-for-makoto-shinkai/>, <https://www.nippon.com/en/articles/-/12665>, <https://colorculture.org/your-name-cinematography-analysis/> |
| Satoshi Kon editing | C | <https://cartoonbrew.com/anime/learn-how-satoshi-kon-edited-space-and-time-102014.html>, <https://kotaku.com/see-how-an-anime-master-manipulated-space-and-time-1611087301> |
| Itano circus | C | <https://www.goodreads.com/author_blog_posts/773828-entering-the-itano-circus> (fan/author blog only) |
| Arcane / Fortiche painterly 3D | C | <https://80.lv/articles/arcane-artists-show-how-they-combine-traditional-art-3d-for-backgrounds>, <https://www.creativebloq.com/art/2d-animation/how-the-creative-team-behind-netflixs-arcane-pushed-the-animation-even-further-for-the-second-season> |
| Hong Kong action rhythm | C | <https://nofilmschool.com/2014/12/jackie-chans-9-principles-action-comedy>, <https://www.davidbordwell.net/blog/2011/01/14/planet-hong-kong-the-dragon-dances/> |
| John Wick wide frames, long takes | C | <https://www.motionpictures.org/?p=31074>, <https://cinemablend.com/movies/john-wick-why-keanu-reeves-action-sequences-are-often-shot-in-the-wide>, <https://soc.org/project/john-wick-chapter-4-8/> |
| Low key, chiaroscuro, rim, silhouette | C | <https://www.wikipedia.org/wiki/Low-key_lighting>, <https://www.videomaker.com/article/12995-specialty-lighting/> |
| Shorts safe zones and hook | C | <https://reap.video/blog/short-form-video-safe-zones>, <https://www.kapwing.com/video-editor/youtube-shorts/safe-zone>, <https://services.google.com/fh/files/misc/universalsafezones-youtube.pdf> (Google's diagram, image only) |
| Our own camera and motion numbers | D | `CAMERA.md` §7, `FIX-LIST.md`, `engine/kuroko.js`, `engine/motion.js`, `../research/anime-fight-craft.md`, `../research/reference-videos.md` |

Limits: most style claims rest on critics and video essays, not studio documents, so they are [C]; frame-level numbers
for Leone's cutting and exact Shorts UI sizes were not found in a primary source.
