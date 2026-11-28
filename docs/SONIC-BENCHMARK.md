# SONIC benchmark (28 Nov 2026, second pass)

Everything here is measured. The automated version is `npm test` (16 checks, about 10 s; `tests/sonic.test.mjs`).
The long run is `node tools/sonic_bench.mjs` (about 45 s; raw numbers go to `output/sonic-bench/results.json`).
The final-mix timing check is `node tools/sonic_verify.mjs --probe`.
All of it ran on the 4-core cloud container this branch was built in.

**Library:** 302 sounds:
- 38 existing files
- 12 new PaperAcoustics sounds (`tools/paper_sfx.mjs`, made in code)
- all 252 sounds of the Earshot bank (MIT; pinned commit 7a7f7c5 from `vendor/MANIFEST.json`; its licence file was checked before install)

## 1. Nothing that worked changed

- **Sonic off:** `engine/sound.mjs` gives bit-identical decoded audio to the version before Sonic. The bench checks this on the 16 s fight in both set-ups, and the test suite checks it on the probe.
- **Sonic on:** loudness -14.7 LUFS, true peak -1.3 dBFS (before: -14.6 to -14.7 LUFS and -1.4 dBFS). Both are inside the studio standard.

## 2. Timing, measured in the finished mix (the independent check)

`tools/sonic_verify.mjs --probe` mixes a probe with the real `engine/sound.mjs`, once with Sonic off and once with it on. The probe has 12 events 1.2 s apart (6 whooshes at blade speeds 10–30 m/s, 4 clashes at intensities 0.2–1.0, a dash and a landing) and no beds. The check then decodes the output and finds where each sound actually lands. It never reads Sonic's own numbers.

- **Hits** (clash, dash, land) are judged by their onset: the first moment they come within 6 dB of their loudest.
- **Whooshes** are judged by their loudest 5 ms.

| Final mix, 12 isolated events | Error median | Mean | Worst |
|---|---|---|---|
| Sonic off (engine sounds) | 21 ms | 52.6 ms | 153 ms (a whoosh peaking 3.7 frames late) |
| Sonic on | 5 ms | 6.8 ms | 23 ms (one whoosh played at 0.85× speed) |

**Second opinion from VYRN's own onset detector.** VYRN's detector (`vyrn/audio.py` on PR 4, commit 99cda49; spectral flux, numpy only) was run on the same two mixes. It is a separate code base with a different method. It agrees on the hits:
- **Sonic on:** 4.7–6.9 ms.
- **Sonic off:** 5.4–19 ms.

It marks the start of each attack, not the loudest moment, so it does not grade the whooshes. VYRN's full `sync --expect` command needs OpenCV, which was not approved for this thread, so I didn't install it.

**Fixes this check found** (each now covered by a test):
- **Onset for hits:** Sonic now lines up a hit by its onset, not its "loudest 5 ms". A low thud such as `land-thud` is a 44 Hz wave whose loudest 5 ms is just one crest in a long plateau, and the master limiter flattens a clash's top. Aligning those by their peak played the landing 65 ms early.
- **The 10 ms fade-in:** `engine/sound.mjs` fades every one-shot in over 10 ms. A clash's transient sits in that window, so the catalog now measures peaks with the same fade applied (`peakTPlay`, `onsetT`).

The fade itself is a finding for later. It softens the first 10 ms of every clash in every film. I left it alone because changing it would change every existing mix.

## 3. Picking

Measured on the 16 s fight fixture (8 whooshes, 7 clashes, ground events), Sonic before → after.

| | Earshot set-up | Plain set-up |
|---|---|---|
| Blade speed vs whoosh intensity (correlation) | 0.30 → 0.89 | -0.14 → 0.94 |
| Contact intensity vs clash intensity | 0.88 → 0.89 | 0.88 → 0.89 |
| Different whoosh sounds (of 8) | 4 → 7 | 3 → 7 |
| Different clash sounds (of 7) | 2 → 3 | 2 → 3 |
| Same whoosh twice within 1.5 s | 0 → 0 | 0 → 0 |

- **Whooshes improved a lot.** The Earshot bank added 66 whooshes to choose from.
- **Clashes are capped by the library.** There are still only three steel impacts (`clash-steel`, `clash-light`, `blade-clash`).
- **Physical events skip UI sounds.** The Earshot bank is mostly interface and motion-graphics sound (139 "synthetic", 115 "ui"), so a fight never picks those.

**Material fallback is now hard:**
- **Wood clash:** picks a wood sound.
- **Paper clash:** picks `paper/paper-thump`. Before the fix it silently played a body fall.
- **A material the catalog lacks (glass):** no pick, and the engine keeps its own sound.
- **Fallbacks are allowed and reported:** wood → steel is used only when the library has no wood at all, and the report says so.

## 4. The offline mix failure (found by the pilot)

**Before:** a film cue whose file wasn't saved locally made `engine/sound.mjs` ask Openverse. With no network, that threw, and the whole mix stopped. This was reproduced with the pre-Sonic `sound.mjs`.

**Now:** the cue gets the closest local sound from the catalog, matched by the words of its query. If nothing matches, the cue is skipped and the mix goes on. Both are written to `output/<film>.sound-report.json`. In the regression test and a manual run:
- "wooden door slam" → `impact`
- "rain ambience" (a bed) → `sea-bed`
- a nonsense query → skipped

The test uses a real refused connection, not just the `--offline` switch.

## 5. Speed and memory

| Step | Time | Peak memory |
|---|---|---|
| Catalog scan, cold, 302 sounds (Earshot renders already cached) | 24–29 s | 164 MB (includes the Earshot listing) |
| Same, with the 252 Earshot renders made from scratch | 7 min 49 s | n/a |
| Catalog scan, nothing changed | 1.3–1.4 s (1.2 s of it is the `earshot sfx list` call) | |
| One query from the command line | 70–80 ms | |
| Probe (2 full mixes + decode + check) | 3.5 s | |
| `npm test` (16 checks) | about 10 s | |
| `engine/sound.mjs`, one 16 s mix | 2.0–2.9 s in every mode (run-to-run noise about ±0.3 s) | |

## 6. Tokens, measured not estimated

These are real token counts from this session's API usage records. Each sample's cost is the jump in new input tokens on the request after it, with the cost of the tool call itself measured separately as a control (6 tokens).

| Text an agent reads | Characters | Real tokens | Characters per token |
|---|---|---|---|
| `sonic query … --limit 3` answer | 287 | about 220 (309 measured, including a system note of about 90 that arrived with it) | about 1.3 |
| 4,000 characters of `credits.json` | 4,000 | 1,841 | 2.2 |
| 3,000 characters of ffmpeg `volumedetect` output | 3,000 | 1,766 | 1.7 |

Applied to the whole job ("find a heavy steel impact" without the catalog: list the folder, read `credits.json` (10,071 characters), measure the 34 mp3 files (48,680 characters of ffmpeg output)):

- **Without the catalog:** about 33,500 tokens over 36 tool calls. The earlier characters ÷ 4 estimate of 14,800 was about 2.3 times too low.
- **With it:** about 220–310 tokens in one call. That's roughly 110–150 times less.

**Where the real cost is.** Over its first 122 requests this thread read **52.5 million cached input tokens**, and wrote 0.46 million new ones and 0.14 million output tokens. Its very first request was already about 261,000 tokens (the fixed instructions and tool list), and every request re-reads that. So tool output is not where the money goes: re-reading a huge fixed context on every step is. It is the same pattern as the pilot's 15.2 million cached tokens over 31 requests (about 490,000 per request). Fewer, larger steps and sessions started with a small tool set cut this far more than any compression of tool output. I didn't run another agent to measure more, as Mark asked.

## What is still weak

- **Real films:** real fight events need headless Chromium (`engine/render.mjs`). The fight here is a fixture in the exact format `engine/combat.js` writes, so no real film has been mixed with Sonic yet.
- **Listening:** whether it *sounds* better has not been judged by ear or by a listening model.
- **Steel impacts:** the catalog has only 3. That limits clash variety more than anything else.
- **Tags:** tags come from words, so an odd name can still mislead (for example `pro_pop/tink` is tagged steel). The hand-edit layer (`node tools/sonic.mjs tag …`) is the fix for one-offs.
- **Rate-shifted whooshes:** a whoosh played at 0.85× speed still lands 23 ms late. The pitch change moves its shape a little, and that isn't modelled.
