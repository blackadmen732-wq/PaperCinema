#!/usr/bin/env python3
"""LISTEN: lets an AI 'watch and hear' a reference video.
  python3 tools/listen.py <video> [--out output/listen/<name>] [--model base]
Writes:
  transcript.txt  - speech with timestamps (faster-whisper, MIT; runs on CPU)
  sound.txt       - sound timeline: loudness every 50 ms + detected hits (sudden jumps), so sword hits,
                    whooshes and music beats can be timed against the picture
  sheet.jpg       - one frame per second, tiled, to look at the picture
  report.md       - all of it together
"""
import argparse, json, os, subprocess, sys, math, wave, struct

ap = argparse.ArgumentParser()
ap.add_argument('video'); ap.add_argument('--out'); ap.add_argument('--model', default='base')
a = ap.parse_args()
name = os.path.splitext(os.path.basename(a.video))[0]
out = a.out or f'output/listen/{name}'
os.makedirs(out, exist_ok=True)
wav = f'{out}/audio.wav'
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', a.video, '-ac', '1', '-ar', '16000', wav], check=True)
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', a.video, '-vf', 'fps=1,scale=180:-1,tile=8x6', '-frames:v', '1', f'{out}/sheet.jpg'], check=True)

# --- sound timeline: RMS per 50 ms, hits = frames 9 dB louder than the previous 200 ms
w = wave.open(wav); sr = w.getframerate(); n = w.getnframes()
data = struct.unpack(f'<{n}h', w.readframes(n))
hop = sr // 20
db = []
for i in range(0, n - hop, hop):
    seg = data[i:i + hop]
    r = math.sqrt(sum(x * x for x in seg) / len(seg)) / 32768 + 1e-9
    db.append(20 * math.log10(r))
hits = []
for i in range(4, len(db)):
    prev = max(db[i - 4:i])
    if db[i] - prev > 9 and db[i] > -40 and (not hits or i * 0.05 - hits[-1][0] > 0.15):
        hits.append((round(i * 0.05, 2), round(db[i], 1), round(db[i] - prev, 1)))
with open(f'{out}/sound.txt', 'w') as f:
    f.write('# time_s  loudness_dB (every 50 ms)\n')
    for i, v in enumerate(db): f.write(f'{i*0.05:.2f} {v:.1f}\n')

# --- speech
lines = []
try:
    from faster_whisper import WhisperModel
    m = WhisperModel(a.model, device='cpu', compute_type='int8')
    import numpy as np
    audio = np.array(data, dtype=np.float32) / 32768.0          # pass samples directly (avoids PyAV version issues)
    segs, info = m.transcribe(audio, vad_filter=True)
    for s in segs: lines.append(f'[{s.start:6.2f} → {s.end:6.2f}] {s.text.strip()}')
    lang = info.language
except Exception as e:
    lines.append(f'(speech recognition unavailable: {e})'); lang = '?'
open(f'{out}/transcript.txt', 'w').write('\n'.join(lines) + '\n')

# --- report
loud = sorted(range(len(db)), key=lambda i: -db[i])[:5]
rep = [f'# LISTEN report: {name}', '', f'Duration {n/sr:.1f} s · speech language: {lang}', '',
       '## Speech', *lines, '', '## Sound hits (sudden jumps ≥ 9 dB)', '| time s | level dB | jump dB |', '|---|---|---|',
       *[f'| {t} | {l} | +{j} |' for t, l, j in hits], '',
       '## Loudest moments', *[f'- {i*0.05:.2f} s: {db[i]:.1f} dB' for i in sorted(loud)], '',
       f'Picture: `{out}/sheet.jpg` (1 frame per second). Full loudness curve: `{out}/sound.txt`.']
open(f'{out}/report.md', 'w').write('\n'.join(rep) + '\n')
print('\n'.join(rep[:60]))
