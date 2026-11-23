# Anime fight craft: techniques, sound, motion tools, pipelines

Research note for Paper Cinema (Lantern Origami duels, vertical 9:16). Researched 2026-11-23.

**Confidence marks** (as in every `research/` file):
- **[D] documented**: a primary source says it (a studio interview, a manual, a licence file, a talk listing).
- **[C] commonly reported**: secondary press, fan wikis or player reports agree, but there is no primary source.
- **[I] our inference**: our own reading of how it applies to us.

We describe techniques only. We copy no frames, sounds or assets.

---

## 1. How anime studios animate sword fights

### 1a. The workflow
| Stage | What happens | Mark |
|---|---|---|
| Layout | Staging, camera and background for each shot | [D] Toei describes the stage order: <https://corp.toei-anim.co.jp/en/company/animation_production/animation_production-2.html> |
| Genga (key animation) | Key poses, with timing notes for the in-betweeners | [C] <https://somon.neocities.org/anime_guide/general_process>, ANN credits guide <https://www.animenewsnetwork.com/feature/2016-03-16/your-ultimate-guide-to-anime-ending-credits-part-i/.99852> |
| Ni-genga (second key) | Cleans up the rough keys | [C] same sources |
| Douga (in-betweens) | Fills the frames between keys, following the timing sheet | [C] |
| Satsuei (photography / compositing) | Characters, backgrounds and effects layered; glows, blur, light, camera moves added | [C] (After Effects is common) |

**Lesson for us [I]:** our film JSON is already a layout and timing sheet. KUROKO is our layout artist, `poses.json` and `moves.json` are our genga, the curve system is our douga, and the renderer plus Blender is our satsuei. The craft is in the keys and the timing, not in having more frames.

### 1b. Sakuga techniques
| Technique | What it is | Mark and source |
|---|---|---|
| Ones / twos / threes | Holding each drawing for 1, 2 or 3 frames of 24 fps. Action is mostly on twos (12 drawings/s), with ones saved for special moments | [C] <https://en.wikipedia.org/wiki/Smear_frame>; for Demon Slayer: "most action on twos, ones for slow-motion moments" <https://jbsiraudin.github.io/blog/demon-slayer-visual-grammar> |
| Smear frame | One in-between that stretches or multiplies the object along its path, standing in for motion blur | [C] <https://en.wikipedia.org/wiki/Smear_frame>, <https://garagefarm.net/blog/smear-frames-enhancing-motion-in-animation> |
| Impact frame | 1 to a few frames of extreme value contrast (black/white silhouettes, colour inversion) at the moment of contact | [C] <https://knowyourmeme.com/memes/cultures/impact-frames>; Demon Slayer analysis credits animator Nozomu Abe with silhouette contrast (jbsiraudin, above) |
| Strike rhythm | A long wind-up, a strike that is often a single frame, then a long relax | [C] jbsiraudin (above) |
| Camera shake on 24 over 12 | The shake is animated on ones over drawings on twos, and kicked in the direction of the strike | [C] jbsiraudin |
| Light flash / glint | A glint warns of the strike; light shapes and sparks reinforce it; colour-coded (blade vs enemy vs gold sparks) | [C] jbsiraudin |
| Hit-stop | Attacker and target freeze for the same time; longer for heavier hits, up to a cap. A "visual effect" separate from hitstun | [D] Sakurai, Famitsu column (fan translation) <https://sourcegaming.info/2015/11/11/thoughts-on-hitstop-sakurais-famitsu-column-vol-490-1/>. Refinements: shake the target more, keep the attacker moving a little, scale the shake with camera distance [C] <https://www.gonintendo.com/contents/13581-sakurai-s-latest-game-dev-video-features-8-hit-stop-techniques> |
| Hit pause, camera kick | The "Art of Screenshake" list: sleep on hit, camera kick opposite to the shot, screen shake | [C] <https://medienwissenschaft.uni-bayreuth.de/wp-content/uploads/GxD-10-Game-Feel.pdf> |
| Itano circus | Many fast projectiles on crossing 3D paths with trails, with the camera flying among them. Ichirō Itano, early 1980s, Macross | [C] fan wiki and author blog only: <https://zh.moegirl.org.cn/%E6%9D%BF%E9%87%8E%E9%A9%AC%E6%88%8F>, <https://www.goodreads.com/author_blog_posts/773828-entering-the-itano-circus> |
| 3D shown as limited animation | Guilty Gear Xrd posed 3D models with keyframes only, like cels, at a lowered, anime-like frame rate | [D] GDC 2015 talk <https://gdcvault.com/play/1022031/GuiltyGearXrd-s-Art-Style-The>; handout <https://www.ggxrd.com/Motomura_Junya_GuiltyGearXrd.pdf>; report <https://game.watch.impress.co.jp/docs/news/20150307_691725.html> |
| Background pans, held cels | A long pan or slide over one painted background under a held pose is a classic limited-animation tool | [I] standard practice; we found no single primary source in this pass |
| Eye close-ups, glowing eyes | The standoff cut to the eyes before the strike; a glow in the eyes to show a demon or a burst of will | [I] genre convention (Demon Slayer, Kurosawa standoffs); no primary source found |

### 1c. Named examples (technique only)
- **Demon Slayer / ufotable.** Yūichi Terao heads ufotable's Digital Team and is the series' director of photography (compositing) [D] <https://www.animenewsnetwork.com/encyclopedia/people.php?id=58110>. The producer says the Water Breathing waves are "almost all hand-drawn", with a little 3DCG in the composite [D] <https://www.animenewsnetwork.com/feature/2019-08-28/interview-demon-slayer-producer-yuma-takahashi/.149177>. Another report describes 3D wave models with 2D keys drawn on top [C] (Animation Magazine, via search). The director names Hokusai's ukiyo-e as a motif [D] <https://www.thepopverse.com/movies-demon-slayer-kimetsu-no-yaiba-infinity-castle-ufotable-dynamic-anime-honors-koyoharu-gotouge>. The battle spaces are built in 3D, with 2D characters composited into them [C] <https://wrongeverytime.com/2019/05/06/why-it-works-the-digital-arenas-of-demon-slayers-battles>.
- **Sword of the Stranger (Bones, 2007).** Yutaka Nakamura was action animation director. He reworked the storyboard of the final duel and planned all of its action. His signature: luminous blade arcs and terrain (snow) bursting around the movement, with a fast camera following [C] <https://en.wikipedia.org/wiki/Yutaka_Nakamura>, <https://blog.alltheanime.com/sword-of-the-stranger/>, <https://slashfilm.com/1211879/where-to-stream-sword-of-the-stranger>.
- **Samurai Champloo.** Break-dance and capoeira-like swordplay; turntable scratches used as cuts and transitions [C] <https://en.wikipedia.org/wiki/Samurai_Champloo>, <https://www.netflix.com/tudum/articles/black-music-anime-connection-closer-look>.
- **Blade of the Immortal.** We found no production source in this pass, so we make no claims about it.
- **Ghost of Tsushima, Kurosawa Mode.** A black-and-white grade tuned against samurai films across times of day and weather, film grain, wind "cranked up", and an internal tool that makes the audio sound like 1950s speakers. Made with the Kurosawa estate's blessing [C] (secondary reports of developer interviews) <https://gamesradar.com/ghost-of-tsushima-kurosawa-mode-explained-how-it-changes-the-game-and-why>, <https://www.gamespot.com/articles/ghost-of-tsushima-consulted-with-filmmakers-estate/1100-6479468/>, <https://www.thegamer.com/ghost-of-tsushima-kurosawa-input/>.
- **Sekiro.** The deflect has a narrow timing window and is fed back by a bright, high "clang" with a large orange spark; a mistimed deflect becomes a block with a dull "ding". Blade deflects sound brighter than deflected punches or kicks [C] (players and guides; we found no FromSoftware audio talk) <https://steamcommunity.com/app/814380/discussions/0/1652169858542412174>, <https://www.superjumpmagazine.com/the-art-and-science-of-sekiros-combat/>. Miyazaki calls the constant "clang, clang, clang" a source of tension [D] <https://gameinformer.com/interview/2018/08/21/hidetaka-miyazaki-on-sekiro-shadows-die-twice>.

### 1d. Draw, switch and "after the cut" beats
- **Zanshin (残心, "remaining mind").** Alert posture held after the technique. In kendo a strike without zanshin does not score [C] <https://en.wikipedia.org/wiki/Zanshin>, <https://japanese-wiki-corpus.github.io/culture/Zan-Shin.html>.
- **Iaidō sequence.** Draw, cut, chiburi (shaking the blade clean), nōtō (re-sheathing) [C] <https://www.ittendojo.org/articles/zanshin>. For us, chiburi flicks **paint**, not blood (house rule).
- **Film grammar [I]:** stillness, then one unreadable flash, then the two fighters frozen apart; the loser's paper splits or the paint blooms late. This is the "delayed-reaction" beat that samurai films are known for. Blade-switch beats (a hand change, reverse grip, a second blade drawn) should get their own key pose and a sound tick, so they read on a phone.

---

## 2. How fight sound is made

### 2a. What is documented
- **Kurosawa, Yojimbo (1961).** Sound engineer Ichirō Minawa experimented with cutting different meats to create the sword-into-flesh sound, which became a template for later action films [D] TCM <https://www.tcm.com/articles/290066/sanjuro>. "Chicken stuffed with chopsticks" appears in one source only [C] <https://en.wikipedia.org/wiki/Filmmaking_technique_of_Kurosawa>. **For us:** we use no flesh sound. Our "cut" is torn or sliced paper plus a wet paint splat [I].
- **Zatoichi (Kitano, 2003).** Hoes, footsteps and rain fall into rhythm with the score, building to a tap-dance finale (The Stripes). Sound: Senji Horiuchi [C] <https://en.wikipedia.org/wiki/Zat%C5%8Dichi_(2003_film)>, <https://popmatters.com/blind-swordsman-zatoichi-2496228505.html>. **Lesson [I]:** put footsteps and clashes on the music's grid.
- **Library practice.** Recordists use metal bars, poles and planks because real swords don't always sound best [C] <https://designingsound.org/2011/11/08/making-of-boom-medieval-weapons/>. Commercial packs split sounds into swish, clang/"shing" ring tail, scrape, and sheathe/unsheathe [C] (product listings).
- **Weapon layering model.** Transient + body + sub + mechanical + tail [C] <https://splice.com/blog/?p=16617>. Whooshes are noise or air with a filter sweep plus volume and pitch curves, about 0.5 to 1 s [C] <https://violetrecording.com/how-to-make-whoosh-sounds/>. Charles Deenen's speed method [C] <https://designingsound.org/2010/02/26/charles-deenen-special-100-whooshes-in-2-minutes/>.

### 2b. Recipes for `engine/sound.mjs` [I unless marked]
**Blade clash (metal on metal), in five layers:**

| Layer | Start time | Content | Treatment |
|---|---|---|---|
| 1. Pre-whoosh | −120 to 0 ms | Air swish, pitch rising | High-pass at 300 Hz, fade in |
| 2. Transient | 0 ms | Short metal "tick" (bar or knife strike) | Very short; this is what sells it on phone speakers |
| 3. Body | 0 ms | Mid "clang" | Pitch ±3 semitones random per hit, so no two clashes match |
| 4. Ring tail | +10 ms | Long resonant "shing" | 1 to 3 s, or cut short by the hit-stop end; brighter for a perfect parry, duller for a block (the Sekiro contrast [C]) |
| 5. Scrape | +0 to 400 ms | Only on a bind or slide (blade on blade) | Pitch follows the slide speed |

**Unsheathe (iai):** a short wood-and-metal tick (koiguchi) → a scrape whose length matches the slide → a high "shing". Sheathe (nōtō): slow scrape → a firm wooden click (the tsuba meeting the scabbard) with **no reverb tail** for a "final" feel.

**Cut on a paper figure:** a whoosh, then a paper tear (crisp, short), then 80 to 200 ms later a soft wet splat for the paint (KIZU onset delay), then silence.

**Sync with hit-stop:** start the transient on the **first** frozen frame. Hold the ring through the freeze and release the follow-through whoosh on the first moving frame. The sound never freezes; only the bodies do. `engine/motion.js` already freezes fighters but not the camera, sparks or sound.

**Ducking:** sidechain the music under every impact (−6 to −10 dB, attack about 5 ms, release 250 to 400 ms). Before the decisive blow, drop to near-silence (wind only, the Kurosawa Mode idea [C]) for 0.5 to 1.5 s, then hit. Silence is the loudest layer on a phone.

**Mix for phones:** most Shorts are heard on phone speakers, so keep the weight in 1 to 4 kHz transients rather than sub bass.

**Sources for sounds:** Freesound CC0/CC-BY (credit the CC-BY ones). The Sonniss GDC bundles are royalty-free for commercial use with no attribution, but newer bundles forbid AI training; check each year's licence [C] <https://bedroomproducersblog.com/2024/06/27/sonniss-gdc-2024/>.

---

## 3. Procedural and AI motion tools

**Key fact [D]:** AMASS and SMPL forbid commercial use, including commercial use of networks trained on them. AMASS licence: "prohibits the use of the Dataset to train methods/algorithms/neural networks/etc. for commercial use" <https://amass.is.tue.mpg.de/license.html>. SMPL: "any use for commercial purposes is prohibited" <https://smpl.is.tue.mpg.de/modellicense.html>. So **MIT code with weights trained on HumanML3D/AMASS is not commercial-safe** (our inference, but it follows directly from those licences).

Licences were checked by reading each repo's actual LICENSE file on 2026-11-23.

| Tool | What it does | Licence (verified) | GPU | Fits a rigid-part paper rig? |
|---|---|---|---|---|
| **ProtoMotions 3** (NVIDIA) | Physics-simulated humanoids; MaskedMimic (motion from partial goals), tracking, retargeting (PyRoki), Newton/IsaacLab/IsaacGym/MuJoCo | **Apache-2.0** code [D] <https://github.com/NVlabs/ProtoMotions>. Its data (AMASS, BONES-SEED) has its own terms | Training: "AMASS in 12 h on 4 A100s" [D]; inference is light | **Yes in principle** [I]: the sim bodies are already rigid capsules and boxes, like our paper parts. Cost: weeks of setup; the data must be commercial-safe |
| **MaskedMimic** | One policy that fills in motion from sparse targets (a hand here, a path there) | Inside ProtoMotions (Apache-2.0) [D] <https://research.nvidia.com/labs/par/maskedmimic/> | As above | Good for "reach the hilt, step, cut" [I] |
| **MimicKit** (Peng) | DeepMimic, AMP, ASE, ADD, SMP; lightweight | **Apache-2.0** [D] <https://github.com/xbpeng/MimicKit> | Isaac Gym/Lab or Newton; one GPU, 4096 parallel envs | Best place to try ASE/AMP commercially [I] |
| **ASE** (original repo) | Adversarial skill embeddings | **NVIDIA licence: non-commercial, research only** [D] <https://github.com/nv-tlabs/ASE> | Isaac Gym | Not usable for commercial work; use the MimicKit version |
| **CALM** | Latent motion control | **NVIDIA licence: non-commercial** [D] <https://github.com/NVlabs/CALM> | Isaac Gym | Not usable |
| **MDM** | Text-to-motion diffusion; 50-step model at about 0.4 s per sample | **MIT** code [D] <https://github.com/GuyTevet/motion-diffusion-model>; weights trained on HumanML3D (AMASS) | One CUDA GPU | Code yes, released weights **no** (AMASS) |
| **MotionGPT** | Motion and language model | **MIT** code [D] <https://github.com/OpenMotionLab/MotionGPT>; same data issue | GPU | Same: weights no |
| **MoMask** | Masked-token text-to-motion; exports BVH; demo runs on CPU | **MIT** code [D] <https://github.com/EricGuo5513/momask-codes>; same data issue | CPU is enough for inference | Fine as a previs sketch only, never in a published film |
| **HumanML3D** | Text labels for AMASS | MIT scripts [D]; the motions are AMASS (non-commercial) | n/a | No |
| **Motion matching** (Clavet, For Honor) | Each frame, search a mocap database for the best next frame | Technique: GDC 2016 [D] <https://www.gdcvault.com/play/1022985/Motion-Matching-and-The-Road>. Holden's demo code **MIT**, but its LAFAN1 data is **CC BY-NC-ND** [D] <https://github.com/orangeduck/Motion-Matching> | CPU | Yes with our own data [I]; overkill for scripted films |
| **Inertialization** (Bollo, Gears of War) | Transitions as a post-process: carry the old pose's offset and velocity and decay them to zero, instead of cross-fading two animations | Technique: GDC 2018 [D] <https://gdcvault.com/play/1025165/Inertialization-High-Performance-Animation-Transitions>; write-up <https://theorangeduck.com/page/inertialization-transition-cost> | CPU, trivial | **Strong yes** [I]: about 30 lines in `figure.js`; smooths move-to-move changes in MOVES without pops |
| **LAFAN1** (Ubisoft) | High-quality locomotion and fight mocap | **CC BY-NC-ND 4.0** [D] <https://github.com/ubisoft/ubisoft-laforge-animation-dataset> | n/a | No |
| **Bandai Namco motion dataset** | Stylised motions | **CC BY-NC 4.0** [D] <https://github.com/BandaiNamcoResearchInc/Bandai-Namco-Research-Motiondataset> | n/a | No |
| **BONES-SEED** | 142k motions (288 h), SOMA BVH plus G1 CSV | Custom licence, which we could not load (server error); commercial terms "available" [C] <https://huggingface.co/datasets/bones-studio/seed> | n/a | Unknown: ask before use |
| **CMU Mocap** | 2,500+ clips (BVH/ASF) | "Free for all uses", including in commercial products, but the data may not be resold [C] (the CMU page was down; read via mirror) <https://mocap.cs.cmu.edu/resources.php>, <https://paperswithcode.com/dataset/cmu-motion-capture>. Third-party conversions may add CC BY-NC | n/a | **Yes**, the best commercial-safe base [I]; few sword clips |
| **Mixamo** | Auto-rig plus animation library | Royalty-free for commercial work including film [C] (official FAQ, read via search because the page returned 403) <https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html>. Community answers: do not redistribute raw files, do not use for ML training | n/a | Yes as reference keys, retargeted to our skeleton; never redistribute the FBX |
| **Cascadeur** | Keyframe tool with AutoPosing and AutoPhysics | Free and Educational: **no commercial use**. Indie: commercial under $100k a year. Pro: full [C] <https://cascadeur.com/education>, <https://cascadeur.com/blog/general/cascadeurs-new-licensing-structure-comprehensive-faq> | Desktop | Good for hand-keying a hero move, then exporting FBX into our poses (needs Indie) [I] |

**Recommendation [I]:** keep our hand-keyed MOVES as the source of truth. Add (1) inertialization between moves, (2) smear and stepped "on-twos" sampling in the renderer, and (3) CMU or Mixamo clips as reference for footwork only. Look at physics policies (MimicKit, ProtoMotions) later, only for "being cut and falling" reactions. Never use AMASS-trained weights in a published film.

---

## 4. Fast pipelines for many videos

| Topic | Finding | Mark |
|---|---|---|
| EEVEE vs Cycles | EEVEE needs OpenGL. On Linux, headless EEVEE works through EGL "surfaceless" (needs Mesa EGL); Cycles runs on CPU with no display at all | [D] commit <https://lists.blender.org/pipermail/bf-blender-cvs/2022-August/176810.html>; [C] <https://devtalk.blender.org/t/blender-2-8-unable-to-open-a-display-by-the-rendering-on-the-background-eevee/1436> |
| EEVEE Next speed | Depends heavily on the scene. Sometimes 10× faster than Cycles, sometimes slower than old EEVEE | [C] <https://projects.blender.org/blender/blender/issues/117246>, <https://80.lv/articles/blender-4-2-s-eevee-vs-cycles-performance-use-cases-explored/> |
| Our split | EEVEE for previs and stills on a free GPU (Kaggle), Cycles only for hero shots. Test both on one shot before choosing | [I] |
| Render farm | **Flamenco 3**: GPL-3, self-hosted, Go + SQLite, used at Blender Studio. One manager plus any number of workers (our machine, Kaggle) | [D] <https://flamenco.blender.org>, <https://projects.blender.org/studio/flamenco> |
| Ocean | Spectra: Phillips (turbulent), Pierson-Moskowitz (established), JONSWAP (sharp peaks), TMA (shallow). Animate Time; Choppiness gives sideways sharp crests; foam goes to a colour attribute; bake to EXR for speed | [D] <https://docs.blender.org/manual/en/latest/modeling/modifiers/physics/ocean.html> |
| Sky | Blender 5.0 adds a multiple-scattering sky. Nishita-style "single scattering" is now marked legacy. Both are very bright, so lower the Exposure | [D] <https://docs.blender.org/manual/en/5.0/render/shader_nodes/textures/sky.html>, <https://developer.blender.org/docs/release_notes/5.0/rendering/>. We run 4.5, where it is still "Nishita" [I] |
| Procedural worlds | **Infinigen** (Princeton): procedural nature in Blender, **BSD-3** [D] <https://github.com/princeton-vl/infinigen>. **BlenderProc**: scripted batch rendering, **GPL-3** [D] <https://github.com/DLR-RM/BlenderProc>. Using GPL tools is fine; only shipping their code changes things | [D]/[I] |
| One world, many films | Build one master `.blend` (island, sea, sky, lights) and link it read-only into each film. Each film file holds only cameras, figures and timing. Bake the ocean once per sea state and reuse it | [I] |
| Previs → final | 1) validate → 2) stills in the browser engine (already built) → 3) EEVEE low-sample animatic of the same camera data → 4) Cycles only on the frames that change → 5) composite | [I] |

---

## 5. Checklist: what we should copy as technique

| # | Technique | Our system | Concretely |
|---|---|---|---|
| 1 | Stepped timing (on twos), with ones only for the slow-mo and decisive cut | MOTION / RENDER | Sample body poses every 2nd frame at 24 fps; camera and effects stay on ones (the Demon Slayer split [C]) |
| 2 | Strike rhythm: long wind-up, single-frame strike, long relax | STRIKE | Clamp the "slash" beat to 1 or 2 frames; lengthen the "ready" and follow-through beats |
| 3 | Smear on the slash frame | RENDER / BLENDER | One frame of stretched blade-and-arm paper ribbon along the arc; no motion blur on that frame |
| 4 | Impact frame | EFFECTS (planned) | 1 or 2 frames of a black/amber (or black/crimson) silhouette inversion at the decisive contact, at most once or twice per film |
| 5 | Hit-stop with shiver, scaled to weight | MOTION (built) | Keep min 3 / max 4. Add: the target shakes more than the attacker; the attacker creeps forward slightly |
| 6 | Camera kick in the strike direction, shake on ones | KUROKO | Impact punch along the blade vector; shake amplitude scaled by shot size |
| 7 | Glint before the strike | LOOKDEV / EFFECTS | A 2 to 4 frame specular star on the edge 4 to 6 frames before contact |
| 8 | Eye close-up and glow | KUROKO `face` rig | An eye-line shot before the draw; crimson inner glow through the paper eye slit for demons |
| 9 | Iai draw → cut → zanshin → chiburi (paint) → nōtō | DRAW / MOVES | Add `chiburi` and `noto` moves; hold zanshin 0.8 to 1.5 s before any reaction |
| 10 | Delayed reaction after the cut | SHIMI / KIZU | Paint onset 80 to 200 ms after the frozen pass, then the paper splits |
| 11 | Inertialization between moves | MOTION | Replace cross-fades; carry joint offset and velocity and decay them in about 0.15 s |
| 12 | Five-layer clash, separate parry and block timbres | SOUND | The table in 2b; random pitch per hit |
| 13 | Silence before the decisive blow; ducking | SOUND | Sidechain music −6 to −10 dB on hits; 0.5 to 1.5 s wind-only gap before the final cut |
| 14 | Rhythm grid (the Zatoichi idea) | SOUND / FILM | Put footsteps and clashes on the music's beat grid |
| 15 | One linked world plus a baked ocean | BLENDER | One master set file; per-film files link it |
| 16 | Licence gate | CHECK | Add a checker rule: refuse any motion source tagged AMASS, SMPL, LAFAN1 or Bandai |

---

### Limits of this note
- The Firecrawl search tool was out of credits, so the research used plain web search and page fetches.
- Some primary pages returned errors: the CMU FAQ (503), the Mixamo FAQ (403), the BONES-SEED licence (500) and the ufotable ANN interview (403). Those claims rest on mirrors or search snippets and are marked [C].
- We found no primary source for Sekiro's audio design or for Blade of the Immortal's production.
