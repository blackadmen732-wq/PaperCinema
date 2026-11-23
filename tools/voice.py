#!/usr/bin/env python3
"""VOICE: spoken character lines for a film (guide: docs/VOICE.md).
  nice -n 10 python3 tools/voice.py film/<name>.json [--refresh] [--list-voices]

Reads the film's "voice" list:
  "voice": [{"id": "v1", "who": "hero", "t": 1.2, "text": "Draw.", "voice": "am_onyx",
             "speed": 0.9, "style": "low, slow, menacing", "pitch": -2, "gain": 1.0, "inner": false}]
For each line it
  1. synthesises speech with Kokoro-82M (Apache-2.0 weights, runs on CPU through ONNX),
  2. applies the cinematic voice chain with ffmpeg (pitch, high-pass, low warmth, presence, light
     compression, loudness normalisation, subtle hall reverb; "inner" = inner-monologue treatment),
  3. caches the result as assets/voice/<film>/<id>.wav (re-made only when the text/voice/settings hash changes),
  4. measures its length and a 24 fps loudness envelope (0..1) for the eye-glow pulse.
Then writes output/<film>.voice.json: sound cues for engine/sound.mjs (mixed, with music/beds ducked ~8 dB under
speech) and one envelope per line {"who", "id", "t0", "fps", "env": [...]}.
Models live in ~/.cache/paper-cinema/kokoro/ (downloaded on first run, ~350 MB, not committed).
"""
import argparse, hashlib, json, math, os, re, subprocess, sys, urllib.request

import numpy as np
import soundfile as sf

MODEL_DIR = os.path.expanduser(os.environ.get('KOKORO_DIR', '~/.cache/paper-cinema/kokoro'))
MODEL_URL = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/'
MODEL_FILES = ['kokoro-v1.0.onnx', 'voices-v1.0.bin']
CHAIN_VERSION = 3          # bump when the ffmpeg chain changes, so cached lines are rebuilt
SR = 44100
ENV_FPS = 24

# Casting shortcuts: a role name may be used instead of a raw Kokoro voice id.
ALIASES = {
    'ronin': 'am_onyx',       # deep, dark US male: the default villain / ronin
    'warlord': 'am_fenrir',   # rougher, harder US male
    'elder': 'bm_george',     # deep, older British male narrator
    'narrator': 'bm_fable',   # British male storyteller
    'heroine': 'af_nicole',   # soft, breathy US female (good for inner monologue)
    'empress': 'bf_emma',     # cool, measured British female
    'onna': 'af_bella',       # warm US female
    'samurai-ja': 'jm_kumo',  # Japanese male
    'onna-ja': 'jf_alpha',    # Japanese female
}


def lang_of(voice):
    return {'a': 'en-us', 'b': 'en-gb', 'j': 'ja', 'e': 'es', 'f': 'fr-fr', 'h': 'hi', 'i': 'it', 'p': 'pt-br',
            'z': 'cmn'}.get(voice[0], 'en-us')


def ensure_models():
    os.makedirs(MODEL_DIR, exist_ok=True)
    for f in MODEL_FILES:
        p = os.path.join(MODEL_DIR, f)
        if not os.path.exists(p):
            print(f'downloading {f} → {p}')
            urllib.request.urlretrieve(MODEL_URL + f, p)
    from kokoro_onnx import Kokoro
    return Kokoro(os.path.join(MODEL_DIR, MODEL_FILES[0]), os.path.join(MODEL_DIR, MODEL_FILES[1]))


# ---------- delivery: "style" words → numbers (Kokoro has no text prompt, so the style is mapped) ----------
STYLE_WORDS = {
    # word: (speed factor, pitch semitones, reverb wet, gain dB, compression ratio, extra)
    'slow': dict(speed=0.9), 'fast': dict(speed=1.1), 'measured': dict(speed=0.95),
    'low': dict(pitch=-1.0), 'deep': dict(pitch=-1.5), 'high': dict(pitch=1.0),
    'menacing': dict(pitch=-0.5, wet=-0.04, comp=4.0, warmth=1.5),
    'cold': dict(warmth=-1.5, wet=0.02),
    'whisper': dict(gain=-5, hp=140, comp=2.0), 'quiet': dict(gain=-4), 'soft': dict(gain=-2, comp=2.0),
    'shout': dict(gain=3, comp=6.0), 'roar': dict(gain=4, comp=8.0, pitch=-0.5),
    'distant': dict(wet=0.12, gain=-3, lp=5000), 'close': dict(wet=-0.06, warmth=1.0),
    'inner': dict(inner=True), 'thought': dict(inner=True), 'monologue': dict(inner=True),
    'dry': dict(wet=-1.0),
}


def delivery(line):
    """Explicit "speed" is the base that style words multiply; explicit "pitch"/"inner"/"reverb" override them."""
    d = dict(speed=float(line.get('speed', 1.0)), pitch=0.0, wet=0.14, gain=0.0, comp=3.0, warmth=3.0, hp=75,
             lp=14000, inner=False)
    for w in re.findall(r'[a-z]+', (line.get('style') or '').lower()):
        for k, v in STYLE_WORDS.get(w, {}).items():
            if k == 'speed': d[k] *= v
            elif k in ('inner', 'hp', 'lp', 'comp'): d[k] = v
            else: d[k] += v
    d['speed'] = round(min(1.5, max(0.6, d['speed'])), 3)
    if 'pitch' in line: d['pitch'] = float(line['pitch'])
    if 'inner' in line: d['inner'] = bool(line['inner'])
    if 'reverb' in line: d['wet'] = float(line['reverb'])
    d['wet'] = max(0.0, d['wet'])
    return d


# ---------- synthesis ----------
_ja = None


def synth(k, text, voice, speed, lang):
    """Text → mono float32 at 24 kHz. "[pause 0.6]" inserts silence (seconds) between phrases."""
    global _ja
    out = []
    for part in re.split(r'(\[pause[ =]?[\d.]*\])', text):
        m = re.match(r'\[pause[ =]?([\d.]*)\]', part)
        if m:
            out.append(np.zeros(int(24000 * float(m.group(1) or 0.5)), np.float32)); continue
        part = part.strip()
        if not part: continue
        if lang == 'ja':          # misaki's Japanese G2P (espeak reads kanji badly)
            if _ja is None:
                from misaki import ja
                _ja = ja.JAG2P()
            r = _ja(part); ph = r[0] if isinstance(r, tuple) else r
            s, sr = k.create(ph, voice=voice, speed=speed, is_phonemes=True)
        else:
            s, sr = k.create(part, voice=voice, speed=speed, lang=lang)
        out.append(s.astype(np.float32))
    return np.concatenate(out) if out else np.zeros(2400, np.float32)


def hall_ir(path, seconds=1.8, seed=7):
    """A synthetic stereo hall impulse: decorrelated noise with an exponential decay and darker tail."""
    if os.path.exists(path): return path
    rng = np.random.default_rng(seed)
    n = int(SR * seconds); t = np.arange(n) / SR
    ir = np.zeros((n, 2), np.float32)
    for ch in range(2):
        x = rng.standard_normal(n) * np.exp(-t * 6.9 / seconds)   # -60 dB at `seconds`
        x = np.convolve(x, np.ones(6) / 6, 'same')                 # soften the highs a little
        x[:int(SR * 0.018)] = 0                                    # 18 ms pre-delay
        ir[:, ch] = x
    ir /= np.abs(ir).max()
    sf.write(path, ir, SR)
    return path


def chain(d):
    """ffmpeg filter for one line: [0] dry voice, [1] hall IR → [out]."""
    p = d['pitch']
    shift = f'asetrate={SR}*{2 ** (p / 12):.5f},aresample={SR},atempo={1 / 2 ** (p / 12):.5f},' if abs(p) > 0.01 else ''
    lp = 7000 if d['inner'] else d['lp']
    dry = (f'aresample={SR},{shift}highpass=f={d["hp"]},lowpass=f={lp},'
           f'equalizer=f=140:t=q:w=1.0:g={d["warmth"]:.1f},'          # low warmth
           f'equalizer=f=320:t=q:w=1.2:g=-1.5,'                       # less boxiness
           f'equalizer=f=3200:t=q:w=1.5:g=1.5,'                       # presence (intelligibility)
           f'acompressor=threshold=0.1:ratio={d["comp"]}:attack=8:release=160:makeup=1.5,'
           f'loudnorm=I=-18:TP=-2:LRA=7,aresample={SR},aformat=channel_layouts=stereo')
    wet = d['wet'] + (0.22 if d['inner'] else 0)
    f = [f'[0:a]{dry},apad=pad_dur=1.6,asplit=2[d][s]', f'[s][1:a]afir=dry=0:wet=1,volume={wet:.3f}[w]']
    if d['inner']:
        # inner monologue: close and intimate, slightly filtered, a soft double a few ms behind, more space
        f.append('[d]asplit=2[d1][d2]')
        f.append('[d2]adelay=14|22,volume=0.35[dd]')
        f.append('[d1][dd]amix=inputs=2:normalize=0[d]')
    f.append(f'[d][w]amix=inputs=2:normalize=0,volume={10 ** (d["gain"] / 20) * (0.85 if d["inner"] else 1):.3f},'
             'silenceremove=stop_periods=-1:stop_duration=0.3:stop_threshold=-60dB,alimiter=limit=0.95[out]')
    return ';'.join(f)


def envelope(x, sr, fps=ENV_FPS, range_db=24.0):
    """Loudness per video frame, 0..1. RMS in dB relative to the line's own loudest frame: 0 dB → 1,
    -24 dB or less → 0, squared for contrast so syllables pulse. Instant attack, ~2-frame release."""
    mono = x.mean(axis=1) if x.ndim > 1 else x
    hop = sr / fps
    n = int(math.ceil(len(mono) / hop))
    db = []
    for i in range(n):
        seg = mono[int(i * hop):int((i + 1) * hop)]
        r = math.sqrt(float(np.mean(seg ** 2))) if len(seg) else 0.0
        db.append(20 * math.log10(r + 1e-9))
    top = max(db) if db else 0
    env, prev = [], 0.0
    for v in db:
        v = min(1.0, max(0.0, (v - top + range_db) / range_db)) ** 2
        prev = v if v > prev else prev * 0.5 + v * 0.5
        env.append(round(prev, 3))
    while env and env[-1] < 0.02: env.pop()
    return env


def speech_end(env, fps=ENV_FPS, floor=0.12):
    """Last frame where the voice itself (not the reverb tail) is still audible."""
    idx = [i for i, v in enumerate(env) if v > floor]
    return (idx[-1] + 1) / fps if idx else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('film'); ap.add_argument('--refresh', action='store_true'); ap.add_argument('--list-voices', action='store_true')
    a = ap.parse_args()
    film = json.load(open(a.film))
    base = os.path.splitext(os.path.basename(a.film))[0]
    lines = film.get('voice') or []
    k = ensure_models()
    if a.list_voices:
        print('aliases:', json.dumps(ALIASES, indent=1)); print('kokoro voices:', ' '.join(sorted(k.get_voices()))); return
    if not lines: sys.exit(f'{a.film} has no "voice" list')
    vdir = f'assets/voice/{base}'; os.makedirs(vdir, exist_ok=True); os.makedirs('output', exist_ok=True)
    ir = hall_ir('assets/voice/hall-ir.wav')
    voices = set(k.get_voices())
    cues, envs, info, errors = [], [], [], []
    seen = set()
    for ln in lines:
        lid = ln.get('id'); who = ln.get('who')
        if not lid or lid in seen: errors.append(f'line without a unique "id": {ln}'); continue
        seen.add(lid)
        if 'text' not in ln or 't' not in ln: errors.append(f'{lid}: needs "text" and "t"'); continue
        voice = ALIASES.get(ln.get('voice', 'ronin'), ln.get('voice', 'ronin'))
        if voice not in voices: errors.append(f'{lid}: unknown voice "{voice}" (see --list-voices)'); continue
        lang = ln.get('lang') or lang_of(voice)
        d = delivery(ln)
        key = json.dumps([CHAIN_VERSION, ln['text'], voice, lang, d], sort_keys=True)
        h = hashlib.sha1(key.encode()).hexdigest()[:12]
        wav, meta = f'{vdir}/{lid}.wav', f'{vdir}/{lid}.json'
        cached = os.path.exists(wav) and os.path.exists(meta) and json.load(open(meta)).get('hash') == h
        if not cached or a.refresh:
            raw = synth(k, ln['text'], voice, d['speed'], lang)
            dry = f'{vdir}/_dry-{lid}.wav'
            sf.write(dry, raw, 24000)
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', dry, '-i', ir, '-filter_complex', chain(d),
                            '-map', '[out]', '-ar', str(SR), '-c:a', 'pcm_s16le', wav], check=True)
            os.remove(dry)
            json.dump({'hash': h, 'text': ln['text'], 'voice': voice, 'lang': lang, 'delivery': d}, open(meta, 'w'), indent=1)
            print(f'✓ {lid:6} {who:6} {voice:9} synthesised  "{ln["text"][:60]}"')
        else:
            print(f'· {lid:6} {who:6} {voice:9} cached       "{ln["text"][:60]}"')
        x, sr = sf.read(wav, dtype='float32')
        dur = len(x) / sr
        t0 = float(ln['t'])
        gain = float(ln.get('gain', 1.0))
        cues.append({'id': f'voice-{lid}', 'file': wav, 't': round(t0, 3), 'len': round(dur, 3), 'gain': gain,
                     'voice': True, 'who': who, 'why': f'{who}: {ln["text"][:40]}'})
        env = envelope(x, sr)
        envs.append({'who': who, 'id': lid, 't0': round(t0, 3), 'fps': ENV_FPS, 'env': env})
        info.append({'id': lid, 'who': who, 'text': ln['text'], 'voice': voice, 'lang': lang, 't0': round(t0, 3),
                     't1': round(t0 + speech_end(env), 3), 'tail': round(t0 + dur, 3), 'dur': round(dur, 3),
                     'file': wav, 'hash': h, 'delivery': d})
    # overlap + film-length warnings
    by_who = {}
    for i in sorted(info, key=lambda r: r['t0']):
        if i['who'] in by_who and by_who[i['who']] > i['t0'] + 0.05:
            errors.append(f'{i["id"]}: starts at {i["t0"]} s while {i["who"]} is still speaking (until {by_who[i["who"]]:.2f} s)')
        by_who[i['who']] = i['t1']
        if film.get('duration') and i['t1'] > film['duration'] - 0.75:
            errors.append(f'{i["id"]}: speech ends at {i["t1"]:.2f} s, deep in the final fade-out (film is {film["duration"]} s)')
    out = {'film': base, 'model': 'Kokoro-82M v1.0 (Apache-2.0) via kokoro-onnx', 'fps': ENV_FPS,
           'duck': {'db': float(film.get('voiceDuck', 8)), 'attack': 0.12, 'release': 0.45},
           'lines': info, 'cues': cues, 'envelopes': envs}
    path = f'output/{base}.voice.json'
    json.dump(out, open(path, 'w'), indent=1)
    for e in errors: print('✗', e)
    print(f'\nwrote {path}: {len(cues)} lines, {sum(i["t1"] - i["t0"] for i in info):.1f} s of speech')
    for i in info: print(f'  {i["id"]:5} {i["who"]:6} {i["t0"]:5.2f} → {i["t1"]:5.2f} s (tail {i["tail"]:.2f})')
    if errors: sys.exit(1)


if __name__ == '__main__':
    main()
