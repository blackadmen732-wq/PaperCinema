# SONIC benchmark (28 Nov 2026)

Reproduce: `node tools/sonic_bench.mjs` (about 25 s; raw numbers in `output/sonic-bench/results.json`).
Machine: the 4-core cloud container this repo is developed in. Every number below was measured, none estimated,
except tokens, which are characters ÷ 4 (the usual rule of thumb; the real tokenizer differs a little).

## What was run

- **The fight:** `film/kuroko-duel.json` (16 s) with a fixture events file in the exact format `engine/combat.js` and
  `engine/groundfx.js` write: 8 whooshes (blade speeds 10.5–29 m/s), 7 steel clashes (intensity 0.15–0.95), one
  scrape, a dash, a skid, a take-off and a landing. A fixture, because real events need headless Chromium
  (`engine/render.mjs`), which is not installed here. The same fixture feeds every run.
- **Two whoosh set-ups:** the film as authored (automatic whooshes from the Earshot bank, `autoSounds.whoosh.earshot`)
  and a plain one (the whoosh-a/b/c files, as `film/sword-mocap.json` uses).
- **Three runs each:** HEAD (`engine/sound.mjs` before this change), OFF (today's, Sonic off), SONIC (`--sonic`).

## 1. Nothing that worked changed

| | Earshot set-up | Plain set-up |
|---|---|---|
| HEAD vs OFF, decoded audio (md5 of the PCM) | identical (`a11ab6ca…`) | identical (`962602576…`) |
| Loudness HEAD → SONIC | -14.7 → -14.8 LUFS | -14.6 → -14.8 LUFS |
| True peak HEAD → SONIC | -1.4 → -1.3 dBFS | -1.4 → -1.3 dBFS |

With Sonic off the mix is bit-for-bit the old one. With it on, the level stays inside the studio standard (-14 ± 2
LUFS under -1 dBTP) because each new sound's level is matched to the one it replaces.

## 2. Speed

| Step | Time |
|---|---|
| Catalog scan, cold (38 files decoded and measured) | 4.0–4.5 s |
| Catalog scan, cached (no file changed) | 14–18 ms |
| One query from the command line (node start-up included) | 64–80 ms |
| `engine/sound.mjs`, one full mix (HEAD / OFF / SONIC) | 2.0–2.6 s each; the three are within run-to-run noise (about ±0.2 s) |

Sonic adds no measurable time to a mix: the catalog is read, not rebuilt.

## 3. What an agent has to read

Task: "find a heavy steel impact" (with its length and loudness, so it can be chosen).

| | Tool calls | Text read (≈ tokens) |
|---|---|---|
| Without the catalog: list `assets/sfx`, read `credits.json`, measure each of the 34 mp3 files with ffmpeg | 36 | ≈ 14,800 |
| Without the catalog, cheapest possible: list + `credits.json` only (no lengths or loudness at all) | 2 | ≈ 2,650 |
| With it: `node tools/sonic.mjs query material=steel action=impact dur<2 --sort weight --limit 3` | 1 | ≈ 60 |

The catalog also answers the original request honestly: `query material=steel action=impact size=heavy dur<0.5`
returns **no match**. The library has no heavy steel impact shorter than 0.5 s (the only heavy one, `clash-steel`,
is 1.45 s). Finding that out by hand takes the full 36-call read.

## 4. Fit to the fight (Earshot set-up / plain set-up)

| Measure | HEAD | SONIC |
|---|---|---|
| Peak timing error: how far each sound's loudest moment lands from its event (mean / worst) | 8.8 / 70 ms · 50.1 / 188 ms | 0.1 / 0 ms · 0.1 / 0 ms |
| Whoosh: correlation of blade speed with the sound's measured intensity | 0.30 · -0.14 | 0.46 · 0.43 |
| Clash: correlation of contact intensity with the sound's measured intensity | 0.88 · 0.88 | 0.89 · 0.89 |
| Different whoosh sounds used (of 8 whooshes) | 4 · 3 | 5 · 6 |
| Different clash sounds used (of 7 clashes) | 2 · 2 | 3 · 3 |
| Same whoosh twice within 1.5 s (audit rule) | 0 · 0 | 0 · 0 |

What these mean, and their limits:

- **Timing is the clearest win.** The plain set-up starts every whoosh file 60 ms before the blade's fastest frame,
  but the files peak 120–220 ms in, so the loudest moment landed up to 188 ms late (4.5 frames). Sonic puts each
  measured peak on the event. The peak measurement was checked against ground truth: the four Earshot renders put
  their apex at 0.200 s by construction, and the analyzer finds 0.19–0.20 s. The timing error in the SONIC column is
  computed with the same measured peaks it aligns to, so it shows the placement is applied, not that the peaks are
  perfect; the Earshot check is what says the peaks are right to 10 ms.
- **Whooshes now follow the blade.** Faster swings get more intense sounds (correlation up from 0.30 / -0.14 to
  0.46 / 0.43). Eight whooshes is a small sample; the direction is real, the exact figure is not precise.
- **Clashes barely change, because the library is the limit.** There are three steel impacts (`clash-steel`,
  `clash-light`, `blade-clash`). The fixed rule (steel above intensity 0.4, light below) already tracked intensity
  well; Sonic adds `blade-clash` for mid-strength hits. More impacts in the library is what would move this number.
- **Not measured:** whether the result *sounds* better. That needs ears (or a listening model) on a real render;
  `tools/listen.py` and the studio audit are the next check once a film is rendered with `"sonic": true`.

## What the catalog says the library lacks (`node tools/sonic.mjs stats`)

38 sounds: 12 steel, 12 air, 5 earth, 4 wood, 4 water, 1 paper. No paper folds, crinkles or tears; one heavy steel
impact and nothing short and heavy; the 252-sound Earshot bank is not catalogued (only its 4 rendered whooshes),
because the `earshot` tool is not installed in this container.
