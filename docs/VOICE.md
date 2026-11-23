# VOICE: spoken character lines

Films can speak. A film lists its lines in a `"voice"` field; `tools/voice.py` turns each line into a treated,
cinematic WAV, and `engine/sound.mjs` mixes the lines over the picture with the beds and music ducked under the
speech. The same tool writes a loudness envelope per line so a character's glowing eyes can pulse with the words
(the owner's reference videos do this with a helmet eye slit; see `research/reference-videos.md`).

```bash
nice -n 10 python3 tools/voice.py film/<name>.json        # → assets/voice/<name>/<id>.wav + output/<name>.voice.json
node engine/sound.mjs --film film/<name>.json              # mixes voice.json automatically when it exists
python3 tools/listen.py output/<name>-sound.mp4            # check: the transcript must match the text
python3 tools/voice.py film/<name>.json --list-voices      # every voice id and casting alias
```
Test film: `film/voice-test.json` (the motion-test picture plus a three-line ronin monologue).

## 1. The model and the licences (checked on the model pages, November 2026)

**Chosen: Kokoro-82M v1.0** (hexgrad). Weights **Apache-2.0** (`huggingface.co/hexgrad/Kokoro-82M`: "Apache-licensed
weights … can be deployed anywhere from production environments to personal projects"; trained only on permissive
or non-copyrighted audio). 82 M parameters, about 3× faster than real time on this 4-core CPU, 54 voices including
deep English male and female voices and Japanese (`jm_kumo`, `jf_*`). Runtime: `kokoro-onnx` (MIT) + `onnxruntime`;
Japanese text goes through `misaki[ja]` (Apache-2.0) for correct kanji readings. The English phonemiser is espeak-ng
via `phonemizer` (both GPL-3): we only *run* them as tools, the audio we make is ours, and we do not ship them.

| Candidate | Code | Weights | Verdict |
|---|---|---|---|
| **Kokoro-82M** | Apache-2.0 | **Apache-2.0** | ✅ chosen: commercial-safe, good drama, fast on CPU, has Japanese |
| Piper (rhasspy) | MIT (old `rhasspy/piper`; the new `piper1-gpl` is GPL-3) | `piper-voices` repo tagged MIT, **but each voice has its own dataset licence**: `en_US-ryan` CC BY-NC-SA 4.0 ✗, `lessac` Blizzard 2013 licence (research) ✗, `joe` CC0 ✓ | ⚠ usable only voice by voice after reading its `MODEL_CARD`; flatter delivery |
| StyleTTS2 | MIT | pre-trained models carry a condition: tell listeners the speech is synthetic unless the speaker granted permission | ⚠ possible but with a disclosure duty; GPL phonemiser in the reference inference |
| XTTS-v2 (Coqui) | MPL | **Coqui Public Model Licence: non-commercial** | ✗ rejected |
| F5-TTS | MIT | **CC-BY-NC-4.0** (`SWivid/F5-TTS`) | ✗ rejected (non-commercial weights) |
| MeloTTS | MIT | MIT (`myshell-ai/MeloTTS-English`, `-Japanese`) | ✅ safe fallback; lighter, less dramatic voices |
| Parler-TTS | Apache-2.0 | Apache-2.0 (`parler-tts-mini-v1`, `-large-v1`) | ✅ safe; describes voice by text prompt, but large/slow on CPU and less stable |

**Paid, higher quality:** the ElevenLabs connector is attached to this workspace (voice design, very expressive
delivery). It spends the owner's credits, so it is **only used when the owner approves it**, with the expected cost
(AGENTS.md rule 1 applies in spirit). Nothing in the pipeline calls it.

The model files (~350 MB) download on first run to `~/.cache/paper-cinema/kokoro/` (not committed; override the
folder with `KOKORO_DIR`). Install once: `pip install kokoro-onnx soundfile "misaki[ja]"` (if `unidic-lite` fails to
build: `pip install --use-pep517 unidic-lite` first).

## 2. The schema (`"voice"` in `film/<name>.json`)

```json
"voice": [
  {"id": "v1", "who": "hero", "t": 0.1, "text": "Ten winters... I have walked toward this bridge.",
   "voice": "ronin", "speed": 0.9, "style": "low, slow, menacing", "pitch": -2},
  {"id": "v2", "who": "hero", "t": 2.75, "text": "One breath. [pause 0.25] One cut.",
   "voice": "ronin", "speed": 0.95, "style": "inner", "pitch": -2},
  {"id": "v3", "who": "foe", "t": 4.95, "text": "Then the river keeps your name.",
   "voice": "elder", "speed": 0.92, "style": "deep, cold", "pitch": -1}
]
```

| Field | Required | Meaning |
|---|---|---|
| `id` | ✓ | Unique per film; names the file `assets/voice/<film>/<id>.wav` |
| `who` | ✓ | Cast id (`hero`, `foe`…): whose eyes pulse |
| `t` | ✓ | Start, seconds of film time |
| `text` | ✓ | The words. Punctuation shapes delivery (`,` short breath, `.` stop, `...` hesitation). `[pause 0.4]` inserts an exact silence |
| `voice` | | A Kokoro voice id (`am_onyx`) or a casting alias (below). Default `ronin` |
| `speed` | | Base pace, 1 = normal (0.6–1.5). Style words multiply it |
| `pitch` | | Semitones (−2 = darker, bigger). Overrides the style words' pitch |
| `style` | | Direction in words; mapped to numbers (§4) |
| `inner` | | `true` = inner-monologue treatment (same as the style word `inner`) |
| `reverb` | | Hall send, 0–0.5 (default 0.14). Overrides style words |
| `gain` | | Mix level of the cue in `sound.mjs` (default 1) |
| `lang` | | Normally taken from the voice (`a`=US, `b`=UK, `j`=Japanese…) |

Optional film-level `"voiceDuck": 8` sets the ducking depth in dB.

`output/<film>.voice.json` (written by the tool, read by `sound.mjs` and the renderer):
- `cues`: sound cues in the `sound.mjs` format plus `file` and `voice: true`
  (`{"id": "voice-v1", "file": "assets/voice/voice-test/v1.wav", "t": 0.1, "len": 3.26, "gain": 1, "voice": true, "who": "hero"}`);
- `lines`: per line `t0`, `t1` (end of the speech itself), `tail` (end of the reverb), voice, delivery numbers, hash;
- `envelopes`: `{"who": "hero", "id": "v1", "t0": 0.1, "fps": 24, "env": [0, 0.27, 0.97, …]}`;
- `duck`: `{"db": 8, "attack": 0.12, "release": 0.45}`.

**Cache:** a line is re-synthesised only when its text, voice, language or delivery numbers change (hash in
`<id>.json`); moving `t` never re-synthesises. `--refresh` forces it.
**Checks:** the tool fails (exit 1, ✗ lines) on a missing id/text/t, an unknown voice, a character starting a line
while still speaking, or speech ending in the last 0.75 s fade.

## 3. Voices (casting)

| Alias | Voice id | Character |
|---|---|---|
| `ronin` | `am_onyx` | deep, dark US male; the default villain or ronin |
| `warlord` | `am_fenrir` | rougher, harder US male |
| `elder` | `bm_george` | deep, older British male; narrator or old master |
| `narrator` | `bm_fable` | British male storyteller |
| `heroine` | `af_nicole` | soft, breathy US female; good for inner monologue |
| `empress` | `bf_emma` | cool, measured British female |
| `onna` | `af_bella` | warm US female |
| `samurai-ja` | `jm_kumo` | Japanese male |
| `onna-ja` | `jf_alpha` | Japanese female (also `jf_gongitsune`, `jf_nezumi`, `jf_tebukuro`) |

Other useful raw ids: `am_michael`, `am_eric`, `bm_lewis`, `bm_daniel`, `af_heart`, `bf_isabella`. For a darker
male, add `"pitch": -1` to `-2.5`; below −3 it starts to sound processed.

## 4. Directing delivery

Kokoro has no text prompt, so **`style` words are mapped to numbers** (`STYLE_WORDS` in `tools/voice.py`; add words there):

| Word | Effect |
|---|---|
| `slow` / `measured` / `fast` | pace ×0.9 / ×0.95 / ×1.1 |
| `low` / `deep` / `high` | pitch −1 / −1.5 / +1 semitone |
| `menacing` | −0.5 st, harder compression, more low warmth, a little drier (closer) |
| `cold` | less warmth, a touch more hall |
| `whisper` / `quiet` / `soft` | quieter, thinner low end, gentler compression |
| `shout` / `roar` | louder, heavy compression (roar also −0.5 st) |
| `distant` | more hall, darker, quieter |
| `close` / `dry` | less hall / no hall |
| `inner` / `thought` / `monologue` | inner-monologue treatment |

The rest of the direction lives in the **text**: short sentences, `...` for a held breath, `[pause 0.5]` for a beat,
one idea per line. The reference bar: 4–6 short lines over 15–25 s, a pause between lines, music swelling under
the last one. Use the `scene-writing` skill to write the monologue first.

**The voice chain** (ffmpeg, every line): pitch shift → high-pass 75 Hz → +3 dB warmth at 140 Hz, −1.5 dB at 320 Hz
(boxiness), +1.5 dB presence at 3.2 kHz → compressor 3:1 → loudness-normalised to −18 LUFS → subtle hall
(synthetic 1.8 s stereo impulse, `assets/voice/hall-ir.wav`, 14% send) → limiter.
**Inner monologue:** low-passed at 7 kHz, a soft double 14/22 ms behind (L/R), +22% hall, slightly quieter.

## 5. Mixing and ducking (`engine/sound.mjs`)

`sound.mjs` reads `output/<film>.voice.json` the same way it reads `output/<film>.events.json` (`--voice <path>` to
choose another). Voice cues use their ready `file` (no Openverse search). Cues marked `"bed": true` or
`"music": true` are summed into a bed bus that is **ducked by 8 dB** under every speech window
(`t0 − 0.12 s` → `t1 + 0.45 s`, smooth ramps). Default is an exact volume curve from the known windows, because
the depth is then precise whatever the voice level; `--duck sidechain` uses ffmpeg `sidechaincompress` keyed by the
voice bus instead. Sword sounds are not ducked: a clash should cut through a line.

Measured on the test (`output/voice-test-sound.mp4`): whole mix mean −19.8 dB, peak −4.7 dB, −16.8 LUFS
integrated; wind bed alone 2–6 s: −35.9 dB plain, −43.9 dB ducked (exactly −8.0 dB). With the motion-test clashes
and whooshes (`--events output/motion-test.events.json` → `output/voice-test-full-sound.mp4`) mean −19.6 dB, peak −2.6 dB.
`tools/listen.py` transcript: "Ten winters, I have walked toward this bridge, one breath, one cut, then the river
keeps your name." (matches the text).

## 6. Eyes pulse with the voice

Each envelope is the line's loudness per video frame (24 fps), 0..1, relative to that line's loudest frame
(−24 dB → 0, squared for contrast), with an instant attack and a ~2-frame release, so syllables read as pulses.
`engine/voice-env.js` gives the level at any time:

```js
import { loadVoice, voiceLevel } from './voice-env.js';
const voice = await loadVoice(filmName);                       // output/<film>.voice.json, or null
// where the eye glow is set (motion.js poseOf / main.js):
c.fig.eyeMat.emissiveIntensity = e.g * (1 + 0.8 * voiceLevel(voice, c.id, t)) * (1 - 0.8 * p.lid);
```
`t` is film time, not body time (`tb`): speech does not freeze during hit-stop. Not wired into `motion.js`/`main.js` yet: that is the
next step for whoever owns those files. Keep the pulse subtle (0.5–1.0 extra) so the glow stays the brightest thing
on screen without strobing.
