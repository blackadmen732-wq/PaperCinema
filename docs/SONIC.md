# SONIC: the sound catalog (SonicGraph v1)

Sonic turns every sound file into one record that a program or an AI agent can **query** instead of opening files:
measured attributes from the audio, semantic tags from its name and credits, and a hand-edit layer that no scan
overwrites. The existing pipeline (`engine/sound.mjs`: find → check → place → mix) is unchanged; Sonic is a layer
it can ask, and it only acts when a film opts in.

It is the first piece of Sonic, the sound-intelligence system. Nothing in it is specific to Paper Cinema: the words,
the event kinds and how an event maps to a sound live in a vocabulary file, so another project or agent can use the
same code with its own library and its own vocab.

Benchmark (real numbers, before and after): `docs/SONIC-BENCHMARK.md`.

## Commands

```bash
node tools/sonic.mjs scan                    # measure new or changed sounds, re-tag all → assets/sfx/sonic.catalog.json
node tools/sonic.mjs scan --fresh            # re-measure everything (after changing the analyzer)
node tools/sonic.mjs query material=steel action=impact dur<2 --sort weight --limit 3
node tools/sonic.mjs pick clash material=steel intensity=0.8 --n 4   # what an event gets; --n 4 shows what the next 3 such events would get
node tools/sonic.mjs show clash-steel        # every attribute of one sound
node tools/sonic.mjs tag clap material=wood weight=0.3    # hand edit → assets/sfx/sonic.tags.json (survives every scan)
node tools/sonic.mjs untag clap              # drop the hand edit
node tools/sonic.mjs stats                   # how many sounds per tag: what the library has and what it lacks
node tools/sonic.mjs schema                  # the record format, as JSON
node tools/sonic_bench.mjs                   # the benchmark (writes output/sonic-bench/results.json)
```

Add `--json` to any command for full records. Every query answer is one line per sound:

```
clash-steel  1.446s  w0.853 i0.736 b0.294  [steel,impact,heavy,transient,tonal,dark]
```
(`w` weight, `i` intensity, `b` brightness, all 0..1; then material, action, size, texture.)

**For agents:** run `query` or `pick` before reading any sound file, `credits.json` or ffmpeg output. The catalog
already holds what those would tell you.

## Query language

Terms are ANDed: `key=value`, `key!=value`, `key>n`, `key<n`, `key>=n`, `key<=n`, `key~text`; `a|b` means either
(`"material=steel|wood"`, quoted so the shell does not read the `|`). Tag keys: `material action texture size environment intent`, plus `id file source license`.
Number keys: every measured attribute below. `--sort <attr>` sorts high to low (`--sort -dur` low to high).

## The record (`assets/sfx/sonic.catalog.json`, schema `sonic-catalog/1`)

| Field | Meaning |
|---|---|
| `id` | path under its root without the extension (`clash-steel`, `earshot/swish_blade-0.6-0.2`) |
| `file`, `hash` | the file, and the sha1 of its bytes (16 hex): the cache key |
| `source`, `license` | `local`, `synth`, `earshot` or the credits source; licence from `credits.json` |
| `m.dur peakDb rmsDb bodyDb crest` | length (s), peak, overall RMS, loudness of the active part (-20 dB window), peak-to-RMS |
| `m.peakT attack decay` | seconds to the loudest 10 ms, from -20 dB up to it, from it down to -20 dB |
| `m.centroid low high flatness zcr` | spectral centroid (Hz), energy share under 250 Hz and over 4 kHz, spectral flatness, zero crossings |
| `m.brightness weight intensity sharpness tonal` | the 0..1 scales everything is matched on (formulas in `engine/sonic.mjs` `measure`) |
| `tags.material action environment intent` | from words in the name, credits title and search query (`library/sonic-vocab.json`) |
| `tags.texture size` | from the measurements: transient, sustained, tonal, noisy, ringing, bright, dark; light, medium, heavy |
| `edited`, `measured` | true when `assets/sfx/sonic.tags.json` changes the record; `measured` then keeps the analyzer's own numbers |

**Cache:** a file whose bytes and analyzer version (`ANALYZER` in `engine/sonic.mjs`) are unchanged is never
decoded again; a scan of the 38 current sounds takes about 4 s cold and under 20 ms cached. Tags are always
recomputed, so a vocab or hand edit applies on the next scan with no re-analysis.

## Events → sounds (`vocab.events`)

An engine event (a clash, a whoosh, a landing) becomes a request: what the sound must be (`need`), what scores a
bonus (`prefer`, `match`, a name that contains the event's word), and which measured attribute should sit near a
value computed from the event (`targets`, e.g. a clash's intensity 0..1 → sound intensity 0.3..0.95). Among the
sounds close to the best score (`margin`), the most recent picks of the same kind are skipped (`variety`), then a
seed from the cue id chooses, so the same film always gets the same mix. `align: "peak"` puts the sound's measured
loudest moment on the event's moment (allowing for the cue's playback rate).

`engine/combat.js` and `engine/groundfx.js` now write an `event` on each automatic cue
(`{ kind, material, intensity, speed, height, peakAt }`). Events files written before that still work: Sonic reads
the event back from the cue's id and its `why` text.

## Using it in a film (opt-in)

```json
"autoSounds": { "sonic": true }
```
or `node engine/sound.mjs --film film/x.json --sonic`. Every automatic cue then plays the best catalog match for its
event, keeps the engine's time, gain and rate, has its level matched to the sound it replaces (±9 dB at most), and
gets its peak placed on the event. What it chose and why: `output/<film>.sonic.json`. Options:
`"sonic": { "kinds": ["clash", "whoosh"], "matchLevel": false, "seed": "take-2" }`.

A single film cue can ask the catalog too: `{ "id": "door", "t": 4.2, "len": 1, "gain": 0.8, "sonic": "action=impact material=wood weight>0.6" }`
plays the most intense match.

**Off is the default, and off is identical:** with `sonic` absent, `engine/sound.mjs` produces bit-identical audio
to the version before Sonic (checked by `tools/sonic_bench.mjs`, which compares the decoded PCM).

## Adding sounds and words

- Drop a file under `assets/sfx/` (credit it in `credits.json` if it is CC-BY) and run `scan`.
- A word Sonic does not know: add it to a facet in `library/sonic-vocab.json`, run `scan`.
- A wrong tag on one sound: `node tools/sonic.mjs tag <id> material=paper`.
- A new kind of event: add it under `events` in the vocab; the engine only has to put `{ kind: "<it>" }` on the cue.
- Earshot's 252-sound bank: rendered Earshot sounds in `assets/sfx/earshot/` are catalogued now; cataloguing the
  whole bank needs the `earshot` tool installed (`node tools/vendor.mjs earshot`), which is not done yet.

## Next (not built)

- Tag the whole Earshot bank (needs the tool installed); a paper sound set (folds, crinkle, tears): `stats` shows
  `paper` has one sound.
- An MCP server over `engine/sonic.mjs` (`scan`, `query`, `pick` are plain functions returning JSON, so the wrapper
  is thin).
- Learned tags (a CLAP-style audio model) only if the word and measurement tags prove too coarse: it would be the
  first non-local, non-deterministic step, so it waits for a measured need.
