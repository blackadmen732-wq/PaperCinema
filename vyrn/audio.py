"""AUDIO perception: sound onsets (hits, steps, clashes) and loudness, from any media file with an audio track.

Method (no models, numpy only): log-magnitude spectral flux (Bello et al. 2005; the same family as librosa's and
aubio's onset detectors), an adaptive median threshold, then each onset is refined in the waveform to the first
sample whose 1 ms envelope reaches 10 % of the local peak, which is the same "attack" Sonic and the synth cue
alignment use. Replaces tools/listen.py's 50 ms RMS jump test where timing matters: that test cannot place a hit
closer than 50 ms and misses a hit that follows a loud one within 200 ms. listen.py stays for speech and the
picture sheet.
"""
import subprocess
import numpy as np

SR = 22050
N_FFT, HOP = 1024, 128          # 5.8 ms hop


def decode(path, sr=SR):
    p = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', path, '-vn', '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-'],
                       capture_output=True)
    if p.returncode != 0:
        return None
    x = np.frombuffer(p.stdout, np.float32)
    return x if x.size else None


def onsets(x, sr=SR, k=2.0, delta=0.02, min_gap=0.06):
    """-> list of dicts {t, strength_db, flux, conf}, and the rms curve (dB every 10 ms)"""
    if x is None or x.size < N_FFT:
        return [], np.zeros(0)
    win = np.hanning(N_FFT).astype(np.float32)
    n = 1 + (x.size - N_FFT) // HOP
    idx = np.arange(N_FFT)[None, :] + HOP * np.arange(n)[:, None]
    mag = np.abs(np.fft.rfft(x[idx] * win, axis=1))
    lm = np.log1p(100 * mag)
    lm = np.maximum(0, lm - np.median(lm, axis=0))          # remove the stationary floor (room tone, hum) per bin
    prev = np.maximum.reduce([np.roll(lm, s, axis=1) for s in (-1, 0, 1)])   # SuperFlux-style max filter
    flux = np.concatenate([[0], np.maximum(0, lm[1:] - prev[:-1]).sum(axis=1)])
    flux /= (flux.max() + 1e-9)
    # adaptive threshold: running median over 0.5 s
    w = int(0.25 * sr / HOP)
    pad = np.pad(flux, w, mode='edge')
    med = np.array([np.median(pad[i:i + 2 * w + 1]) for i in range(flux.size)])
    thr = k * med + delta
    loc = int(0.03 * sr / HOP)
    env = np.sqrt(np.convolve(x * x, np.ones(int(sr * 0.001)) / int(sr * 0.001), mode='same'))
    out = []
    for i in range(1, flux.size - 1):
        if flux[i] < thr[i] or flux[i] < flux[max(0, i - loc):i + loc + 1].max():
            continue
        tc = (i * HOP + N_FFT / 2) / sr
        if out and tc - out[-1]['tc'] < min_gap:
            continue
        # refine: the loudest point just after the flux peak, the quietest point before it (the gap after a
        # previous sound), then the first sample after that gap reaching 10 % of the rise
        a = max(0, int((tc - 0.045) * sr)); b = min(env.size, int((tc + 0.06) * sr))
        seg = env[a:b]
        if seg.size < 4:
            continue
        p = int(np.argmax(seg[int(0.025 * sr):])) + int(0.025 * sr) if seg.size > int(0.03 * sr) else int(np.argmax(seg))
        p = min(p, seg.size - 1)
        m0 = int(np.argmin(seg[:p + 1]))
        pk, base = seg[p], seg[m0]
        j = m0 + int(np.argmax(seg[m0:p + 1] >= base + 0.1 * (pk - base)))
        j90 = m0 + int(np.argmax(seg[m0:p + 1] >= base + 0.9 * (pk - base)))
        attack = max(0, (j90 - j) / sr)
        t = (a + j) / sr
        rise = 20 * np.log10((pk + 1e-9) / (base + 1e-9))
        conf = float(np.clip((flux[i] - thr[i]) / (thr[i] + 1e-9), 0, 1) * 0.5 + np.clip(rise / 30, 0, 1) * 0.5)
        # a hit has a sharp attack; a whoosh or a swell rises over tens of milliseconds
        kind = 'hit' if attack <= 0.040 else 'swell'
        # what kind of hit: power spectral centroid of the first 50 ms and the time to fall 30 dB below the peak
        i0 = a + j
        w50 = x[i0:i0 + int(0.05 * sr)]
        if w50.size > 64:
            sp = np.abs(np.fft.rfft(w50 * np.hanning(w50.size)))
            fr = np.fft.rfftfreq(w50.size, 1 / sr)
            pw = sp * sp           # power-weighted, so the room-noise floor does not pull the centroid up
            centroid = float((pw * fr).sum() / (pw.sum() + 1e-9))
        else:
            centroid = 0.0
        pk_i = a + p
        k10 = int(0.01 * sr)
        tail = np.convolve(env[pk_i:pk_i + int(1.0 * sr)], np.ones(k10) / k10, mode='valid')
        below = np.nonzero(tail < (tail[0] if tail.size else 0) * 0.0316)[0] if tail.size else np.array([])
        decay = (below[0] if below.size else tail.size) / sr
        if kind == 'swell':
            guess = 'whoosh/swell'
        elif centroid < 150:
            guess = 'thud (step, landing, body)'
        elif decay >= 0.2:
            guess = 'ringing (metal, clash)'
        elif centroid < 500:
            guess = 'thud (step, landing, body)'
        else:
            guess = 'hit'
        out.append({'t': round(t, 4), 'tc': tc, 'kind': kind, 'guess': guess, 'centroid_hz': round(centroid),
                    'decay_ms': round(decay * 1000), 'attack_ms': round(attack * 1000, 1),
                    'strength_db': round(float(rise), 1), 'flux': round(float(flux[i]), 3), 'conf': round(conf, 3)})
    hop10 = int(sr * 0.01)
    m = x[: x.size // hop10 * hop10].reshape(-1, hop10)
    rms = 20 * np.log10(np.sqrt((m * m).mean(axis=1)) + 1e-9)
    for o in out:
        o.pop('tc')
    return out, rms


def ingest(path, store, sha):
    x = decode(path)
    if x is None:
        return {'audio': False}
    from vyrn import backends
    ons, rms = backends.stage('onsets')(x)
    store.put_signal('audio.rms', 100.0, rms, 'dBFS', 'rms-10ms')
    for i, o in enumerate(ons):
        typ = 'sound.onset' if o['kind'] == 'hit' else 'sound.swell'
        store.put_event(f'{typ}.{i:03d}', typ, o['t'], None, None, [],
                        {'guess': o['guess'], 'centroid_hz': o['centroid_hz'], 'decay_ms': o['decay_ms'],
                         'strength_db': o['strength_db'], 'attack_ms': o['attack_ms'], 'flux': o['flux']},
                        o['conf'], 'spectral-flux', 'vyrn.audio')
    store.commit()
    return {'audio': True, 'onsets': len(ons), 'seconds': round(x.size / SR, 3)}
