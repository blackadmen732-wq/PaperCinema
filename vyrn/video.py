"""EXTERNAL perception: an ordinary video file -> the same store the native adapter fills, from pixels, on CPU.

The default backend ("light") uses classic algorithms only; every result carries a confidence and the method name,
so a neural backend (vyrn/backends.py) can replace one stage and be compared on the same benchmark.

Stages (each is replaceable):
  1 decode      ffmpeg, once, to a small RGB copy (analysis width 160 px by default) cached as a .npy file
  2 cuts        colour-histogram distance with an adaptive threshold (the PySceneDetect "content" idea)
  3 camera      phase correlation between consecutive frames -> pan in px/frame (OpenCV, Apache-2.0)
  4 foreground  per shot: a locked-off shot -> median background; a moving shot -> the same median on frames
                aligned by the measured pan. |frame - background| -> mask -> connected components (blobs)
  5 identity    blobs -> tracks: predicted box (constant velocity) + IoU + distance, gap bridging for 12 frames,
                merged-blob handling (two tracks share one blob = an overlap, confidence drops), and re-identification
                across a cut by colour histogram, so the same fighter keeps one id after the edit
  6 motion      per-frame motion energy (changed pixels) -> 'motion.freeze' (a hit-stop / impact: motion collapses
                after a fast move) and per-track foot contacts (the lowest band of a blob stops moving sideways)
"""
import json, math, os, subprocess
import numpy as np

try:
    import cv2
except ImportError:          # cuts and audio still work; foreground and tracking need OpenCV
    cv2 = None

AW = 160            # analysis width (px)


def probe(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-print_format', 'json', '-show_streams', '-show_format', path],
                         capture_output=True, check=True).stdout
    j = json.loads(out)
    v = next(s for s in j['streams'] if s['codec_type'] == 'video')
    num, den = (int(x) for x in v.get('avg_frame_rate', v['r_frame_rate']).split('/'))
    return dict(fps=num / den if den else 24.0, width=int(v['width']), height=int(v['height']),
                duration=float(j['format'].get('duration', 0)),
                audio=any(s['codec_type'] == 'audio' for s in j['streams']))


def decode_small(path, info, cache):
    """the whole video at analysis width, cached as .npy; later questions never decode the video again"""
    aw = AW
    ah = int(round(info['height'] * aw / info['width'] / 2)) * 2
    npy = os.path.join(cache, f'frames_{aw}x{ah}.npy')
    if os.path.exists(npy):
        return np.load(npy, mmap_mode='r')
    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', path, '-vf', f'scale={aw}:{ah}:flags=area',
                          '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'], capture_output=True, check=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, ah, aw, 3)
    np.save(npy, fr)
    return np.load(npy, mmap_mode='r')


def hist(fr):
    h = [np.bincount((fr[..., c] >> 3).ravel(), minlength=32) for c in range(3)]
    h = np.concatenate(h).astype(np.float32)
    return h / h.sum()


def detect_cuts(frames, fps):
    hs = [hist(f) for f in frames]
    d = np.array([0.0] + [0.5 * np.abs(hs[i] - hs[i - 1]).sum() / 3 * 3 for i in range(1, len(hs))])
    cuts = []
    w = max(3, int(fps))
    for i in range(1, len(d)):
        local = np.median(d[max(1, i - w):i + w + 1])
        thr = max(0.12, 4 * local)
        if d[i] > thr and d[i] == d[max(1, i - 2):i + 3].max():
            cuts.append((i, float(d[i]), float(min(1.0, (d[i] - thr) / thr + 0.5))))
    return cuts, d


def camera_motion(gray):
    """camera pan (dx, dy) px/frame between consecutive frames: corner features (Shi-Tomasi) tracked with pyramidal
    Lucas-Kanade, then a RANSAC similarity fit, so moving subjects are outliers and do not drag the estimate.
    The third value is the inlier share (0..1), used as the confidence of the pan."""
    n = len(gray)
    dx, dy, resp = np.zeros(n), np.zeros(n), np.ones(n)
    if cv2 is None:
        return dx, dy, resp * 0
    for i in range(1, n):
        a = gray[i - 1].astype(np.uint8); b = gray[i].astype(np.uint8)
        pts = cv2.goodFeaturesToTrack(a, maxCorners=200, qualityLevel=0.01, minDistance=4)
        if pts is None or len(pts) < 8:
            resp[i] = 0; continue
        nxt, ok, _ = cv2.calcOpticalFlowPyrLK(a, b, pts, None, winSize=(15, 15), maxLevel=2)
        ok = ok.ravel() == 1
        if ok.sum() < 8:
            resp[i] = 0; continue
        M, inl = cv2.estimateAffinePartial2D(pts[ok], nxt[ok], method=cv2.RANSAC, ransacReprojThreshold=0.7)
        if M is None:
            resp[i] = 0; continue
        resp[i] = float(inl.mean())
        tx, ty = M[0, 2], M[1, 2]
        # a shift under a third of a pixel is indistinguishable from noise at this resolution
        dx[i] = tx if abs(tx) > 0.33 else 0.0
        dy[i] = ty if abs(ty) > 0.33 else 0.0
    return dx, dy, resp


def foreground(frames, f0, f1, off, thresh=28):
    """masks for frames f0..f1 (inclusive) against the median background of the shot, aligned by offsets off[i]"""
    idx = list(range(f0, f1 + 1))
    sub = idx[:: max(1, len(idx) // 48)]
    ox, oy = off[:, 0], off[:, 1]
    H, W = frames.shape[1:3]
    mnx, mny = int(np.floor(ox[idx].min())), int(np.floor(oy[idx].min()))
    mxx, mxy = int(np.ceil(ox[idx].max())), int(np.ceil(oy[idx].max()))
    CH, CW = H + mxy - mny + 1, W + mxx - mnx + 1
    stack = np.full((len(sub), CH, CW, 3), np.nan, np.float16)
    for k, i in enumerate(sub):
        x0, y0 = int(round(ox[i])) - mnx, int(round(oy[i])) - mny
        stack[k, y0:y0 + H, x0:x0 + W] = frames[i]
    with np.errstate(all='ignore'):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)     # canvas corners no frame covered: NaN, ignored
            bg = np.nanmedian(stack, axis=0).astype(np.float32)
    masks = {}
    k3 = np.ones((3, 3), np.uint8); k5 = np.ones((5, 5), np.uint8)
    for i in idx:
        x0, y0 = int(round(ox[i])) - mnx, int(round(oy[i])) - mny
        b = bg[y0:y0 + H, x0:x0 + W]
        diff = np.nan_to_num(np.abs(frames[i].astype(np.float32) - b), nan=0).max(axis=2)
        m = (diff > thresh).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k3)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k5)
        masks[i] = m
    return masks


def blobs(mask, min_area):
    big = cv2.dilate(mask, np.ones((7, 7), np.uint8))
    n, lab, st, cen = cv2.connectedComponentsWithStats(big, connectivity=8)
    out = []
    for j in range(1, n):
        x, y, w, h, a = st[j]
        real = int((mask[y:y + h, x:x + w] & (lab[y:y + h, x:x + w] == j)).sum())
        if real < min_area:
            continue
        sub = mask[y:y + h, x:x + w] & (lab[y:y + h, x:x + w] == j)
        ys, xs = np.nonzero(sub)
        out.append(dict(box=(x + xs.min(), y + ys.min(), xs.max() - xs.min() + 1, ys.max() - ys.min() + 1),
                        area=real, label=j, lab=lab))
    return out


def iou(a, b):
    ax0, ay0, aw, ah = a; bx0, by0, bw, bh = b
    ix = max(0, min(ax0 + aw, bx0 + bw) - max(ax0, bx0)); iy = max(0, min(ay0 + ah, by0 + bh) - max(ay0, by0))
    inter = ix * iy
    return inter / (aw * ah + bw * bh - inter + 1e-9)


def colour_sig(frame, mask, box):
    x, y, w, h = box
    m = mask[y:y + h, x:x + w].astype(bool)
    px = frame[y:y + h, x:x + w][m]
    if px.size == 0:
        return None
    hh = np.concatenate([np.bincount(px[:, c] >> 4, minlength=16) for c in range(3)]).astype(np.float32)
    return hh / hh.sum()


def sig_sim(a, b):
    if a is None or b is None:
        return 0.0
    return float(np.sqrt(a * b).sum())            # Bhattacharyya coefficient, 0..1


def colour_split(frame, mask, blob, tracks, min_area):
    """two or more subjects in one blob: give each pixel to the track whose colour histogram explains it best
    (histogram back-projection), then box each track's pixels. Returns one box (or None) per track."""
    x, y, w, h = blob['box']
    m = mask[y:y + h, x:x + w].astype(bool)
    px = frame[y:y + h, x:x + w]
    q = [(px[..., c] >> 4).astype(np.int64) + 16 * c for c in range(3)]
    like = []
    for t in tracks:
        if t.sig is None:
            like.append(np.zeros((h, w))); continue
        like.append(t.sig[q[0]] * t.sig[q[1]] * t.sig[q[2]])
    like = np.stack(like)
    owner = like.argmax(axis=0)
    strong = like.max(axis=0) > 1e-6
    out = []
    for k in range(len(tracks)):
        mk = (m & strong & (owner == k)).astype(np.uint8)
        if mk.sum() < max(4, min_area // 3):
            out.append(None); continue
        mk = cv2.morphologyEx(mk, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(mk)
        j = 1 + int(np.argmax(st[1:, 4]))
        bx, by, bw, bh, _ = st[j]
        out.append((x + bx, y + by, bw, bh))
    return out


class Track:
    _n = 0

    def __init__(self, f, b, sig, shot):
        Track._n += 1
        self.id = f'obj.{Track._n:02d}'
        self.rows = {f: (b['box'], 1.0, False)}
        self.v = (0.0, 0.0)
        self.last = f
        self.sig = sig
        self.shot = shot
        self.feet = {}

    def predict(self, f):
        box = self.rows[self.last][0]
        g = f - self.last
        return (box[0] + self.v[0] * g, box[1] + self.v[1] * g, box[2], box[3])

    def add(self, f, box, conf, merged, sig):
        pb = self.rows[self.last][0]
        g = max(1, f - self.last)
        nv = ((box[0] + box[2] / 2 - pb[0] - pb[2] / 2) / g, (box[1] + box[3] / 2 - pb[1] - pb[3] / 2) / g)
        self.v = (0.6 * self.v[0] + 0.4 * nv[0], 0.6 * self.v[1] + 0.4 * nv[1])
        self.rows[f] = (box, conf, merged)
        self.last = f
        if sig is not None and not merged:
            self.sig = sig if self.sig is None else 0.9 * self.sig + 0.1 * sig


def track_shot(frames, masks, f0, f1, shot, min_area):
    tracks, live = [], []
    for f in range(f0, f1 + 1):
        bl = blobs(masks[f], min_area)
        cand = []
        for ti, t in enumerate(live):
            p = t.predict(f)
            diag = math.hypot(p[2], p[3]) + 1e-9
            for bi, b in enumerate(bl):
                bb = b['box']
                dc = math.hypot(bb[0] + bb[2] / 2 - p[0] - p[2] / 2, bb[1] + bb[3] / 2 - p[1] - p[3] / 2) / diag
                cost = (1 - iou(p, bb)) + dc
                if cost < 1.2:
                    cand.append((cost, ti, bi))
        cand.sort()
        used_t, used_b, share = set(), {}, {}
        for cost, ti, bi in cand:
            if ti in used_t or bi in used_b:
                continue
            used_t.add(ti); used_b[bi] = ti
        # a live track left without a blob whose predicted box sits inside an assigned blob: the two subjects have
        # merged into one blob (they overlap on screen)
        for ti, t in enumerate(live):
            if ti in used_t or f - t.last > 3:
                continue
            p = t.predict(f)
            for bi, b in enumerate(bl):
                if bi in used_b and iou(p, b['box']) > 0.1:
                    share.setdefault(bi, [used_b[bi]]).append(ti); used_t.add(ti); break
        for bi, ti in used_b.items():
            b = bl[bi]
            if bi in share:
                split = colour_split(frames[f], masks[f], b, [live[k] for k in share[bi]], min_area)
                for k, box in zip(share[bi], split):
                    if box is None:
                        live[k].add(f, live[k].predict(f), 0.3, True, None)
                    else:
                        live[k].add(f, box, 0.6, True, None)
            else:
                live[ti].add(f, b['box'], 1.0, False, colour_sig(frames[f], masks[f], b['box']))
        for bi, b in enumerate(bl):
            if bi not in used_b:
                t = Track(f, b, colour_sig(frames[f], masks[f], b['box']), shot)
                live.append(t); tracks.append(t)
        live = [t for t in live if f - t.last <= 12]
    keep = []
    for t in tracks:
        if len(t.rows) < 6:
            continue
        bx = np.array([t.rows[f][0] for f in t.rows], np.float32)
        if bx.std(axis=0).max() < 0.75 and len(t.rows) > 12:
            continue        # never moved and never changed shape: scenery the background model got wrong
        keep.append(t)
    return keep


def merge_tracks(tracks):
    """join a track that starts after another stopped being seen (an occlusion longer than the gap bridge, a
    merge the tracker gave up on, or a cut) when their colours match; the joined track keeps the earlier id.
    A short overlap is allowed because a lost track coasts on its prediction for a few frames."""
    tracks = sorted(tracks, key=lambda t: min(t.rows))
    out = []
    for t in tracks:
        t0 = min(t.rows)
        best, bs = None, 0.0
        for o in out:
            real = [f for f, r in o.rows.items() if not r[2]]
            last_real = max(real) if real else max(o.rows)
            if t0 > last_real - 3 and len([f for f in o.rows if f >= t0]) <= 14:
                s = sig_sim(o.sig, t.sig)
                if s > bs:
                    best, bs = o, s
        if best is not None and bs > 0.8:
            for f, r in t.rows.items():
                if f not in best.rows or best.rows[f][2] or best.rows[f][1] < r[1]:
                    best.rows[f] = (r[0], min(r[1], bs), r[2])
            best.reid = getattr(best, 'reid', []) + [(t0, round(bs, 3))]
            best.sig = t.sig if t.sig is not None else best.sig
        else:
            out.append(t)
    return out


def foot_contacts(t, masks, fps, scale):
    """footsteps from a blob: the lowest 12 % of the box split into left/right parts; a part that moved sideways
    and then holds still for 2 frames at the bottom has planted"""
    ev = []
    hist_x = {}
    for f in sorted(t.rows):
        box, conf, merged = t.rows[f]
        if merged:
            continue
        x, y, w, h = [int(round(v)) for v in box]
        band = masks[f][max(0, y + int(h * 0.88)):y + h, max(0, x):x + w]
        if band.size == 0:
            continue
        cols = np.nonzero(band.any(axis=0))[0]
        if cols.size == 0:
            continue
        # split the band's columns into runs: each run is a foot (or two feet together)
        runs = np.split(cols, np.nonzero(np.diff(cols) > 1)[0] + 1)
        cx = sorted((r.mean() + x) for r in runs if r.size >= 1)
        hist_x[f] = cx
    fs = sorted(hist_x)
    if len(fs) < 4:
        return ev
    # per frame: the speed of the fastest foot (px/frame), from the nearest-neighbour match of foot centres
    sp = {}
    for a, b in zip(fs, fs[1:]):
        if b - a != 1:
            continue
        pa, pb = hist_x[a], hist_x[b]
        if not pa or not pb:
            continue
        sp[b] = max(min(abs(p - q) for q in pa) for p in pb)
    moving_thr = 0.9 * scale
    still_thr = 0.35 * scale
    last_move = -99
    for f in sorted(sp):
        if sp[f] > moving_thr:
            last_move = f
        elif sp[f] < still_thr and f - last_move <= 3 and sp.get(f + 1, 0) < still_thr:
            ev.append((f, float(np.clip(1 - sp[f] / still_thr, 0.2, 0.9))))
            last_move = -99
    return ev


def ingest(path, store, media_id, sha, cache, verbose=False):
    if cv2 is None:
        raise RuntimeError('external perception needs OpenCV: pip install opencv-python-headless (Apache-2.0)')
    info = probe(path)
    fps = info['fps']
    frames = decode_small(path, info, cache)
    n, H, W = frames.shape[:3]
    gray = [cv2.cvtColor(np.ascontiguousarray(f), cv2.COLOR_RGB2GRAY).astype(np.float32) for f in frames]
    store.put_media(id=media_id, kind='video', source=path, sha256=sha, fps=fps, duration=info['duration'],
                    frames=n, width=info['width'], height=info['height'],
                    processors={'video': 'light/1', 'analysis': f'{W}x{H}', 'opencv': cv2.__version__},
                    stats={})

    from vyrn import backends
    cuts, cutd = backends.stage('cuts')(frames, fps)
    store.put_signal('cut.score', fps, cutd, 'hist L1', 'hist32x3')
    for k, (f, s, c) in enumerate(cuts):
        store.put_event(f'cut.{k:02d}', 'cut', f / fps, None, f, [], {'score': round(s, 3)}, c, 'hist32x3', 'vyrn.video')
    bounds = [0] + [c[0] for c in cuts] + [n]
    dx, dy, resp = backends.stage('camera')(gray)
    for b in bounds[1:-1]:
        dx[b] = dy[b] = 0
    store.put_signal('camera.dx', fps, dx / W, 'frame widths/frame', 'phaseCorrelate')
    store.put_signal('camera.dy', fps, dy / H, 'frame heights/frame', 'phaseCorrelate')
    off = np.zeros((n, 2))
    for s0, s1 in zip(bounds, bounds[1:]):
        # phaseCorrelate gives the shift of frame i relative to i-1; the background moves opposite to the camera
        off[s0:s1, 0] = -np.cumsum(dx[s0:s1]); off[s0:s1, 1] = -np.cumsum(dy[s0:s1])

    min_area = max(12, int(0.0015 * W * H))
    tracks, energy = [], np.zeros(n)
    masks_all = {}
    shots = []
    for si, (s0, s1) in enumerate(zip(bounds, bounds[1:])):
        moving = float(np.median(np.hypot(dx[s0 + 1:s1], dy[s0 + 1:s1]))) if s1 - s0 > 2 else 0.0
        shots.append(dict(i=si, f0=s0, f1=s1 - 1, pan_px_per_frame=round(moving, 3)))
        # locked-off or panning? build both backgrounds and keep the one the frames fit better
        zero = np.zeros_like(off)
        m_static = foreground(frames, s0, s1 - 1, zero)
        m_pan = foreground(frames, s0, s1 - 1, off) if np.abs(off[s0:s1]).max() > 0.5 else m_static
        fs_ = float(np.mean([m.mean() for m in m_static.values()])); fp_ = float(np.mean([m.mean() for m in m_pan.values()]))
        masks = m_pan if fp_ < fs_ else m_static
        shots[-1]['background'] = 'aligned' if fp_ < fs_ else 'static'
        masks_all.update(masks)
        tracks += track_shot(frames, masks, s0, s1 - 1, si, min_area)
        for i in range(s0 + 1, s1):
            # motion energy: share of pixels that changed between consecutive frames inside the foreground
            fg = masks[i] | masks[i - 1]
            if fg.any():
                prevg = gray[i - 1]
                if dx[i] or dy[i]:      # undo the pan first, so a panning camera does not count as motion
                    prevg = cv2.warpAffine(prevg, np.float32([[1, 0, dx[i]], [0, 1, dy[i]]]), prevg.shape[::-1],
                                           borderMode=cv2.BORDER_REPLICATE)
                d = np.abs(gray[i] - prevg)[fg.astype(bool)]
                energy[i] = float((d > 12).mean()) * fg.mean()
    tracks = merge_tracks(tracks)
    store.put_signal('motion.energy', fps, energy, 'changed foreground share', 'framediff')
    # subject motion: inside each track's box, aligned on the box itself, so camera moves and parallax cancel and
    # only the subject's own change of shape remains (what a hit-stop freezes)
    senergy = np.zeros(n)
    for t in tracks:
        fs = sorted(t.rows)
        for a_, b_ in zip(fs, fs[1:]):
            if b_ - a_ != 1:
                continue
            (xa, ya, wa, ha), _, ma = t.rows[a_]; (xb, yb, wb, hb), _, mb = t.rows[b_]
            w_, h_ = int(min(wa, wb)), int(min(ha, hb))
            if w_ < 4 or h_ < 4:
                continue
            ca = (int(xa + wa / 2 - w_ / 2), int(ya + ha / 2 - h_ / 2)); cb = (int(xb + wb / 2 - w_ / 2), int(yb + hb / 2 - h_ / 2))
            pa = gray[a_][max(0, ca[1]):ca[1] + h_, max(0, ca[0]):ca[0] + w_]
            pb = gray[b_][max(0, cb[1]):cb[1] + h_, max(0, cb[0]):cb[0] + w_]
            hh, ww = min(pa.shape[0], pb.shape[0]), min(pa.shape[1], pb.shape[1])
            if hh < 4 or ww < 4:
                continue
            mk = masks_all[b_][max(0, cb[1]):cb[1] + hh, max(0, cb[0]):cb[0] + ww].astype(bool)
            if mk.sum() < 8:
                continue
            senergy[b_] += float((np.abs(pa[:hh, :ww] - pb[:hh, :ww]) > 12)[mk].mean())
    store.put_signal('motion.subject', fps, senergy, 'changed share of subject boxes (summed)', 'box-aligned framediff')
    energy = senergy

    # ---- entities and samples ----
    rows = []
    for t in tracks:
        fs = sorted(t.rows)
        store.put_entity(t.id, 'object', label=t.id, source='vyrn.video', method='light/median-bg+iou-tracker',
                         first_f=fs[0], last_f=fs[-1],
                         confidence=round(float(np.mean([t.rows[f][1] for f in fs])), 3),
                         info={'frames': len(fs), 'reid': getattr(t, 'reid', []),
                               'shots': sorted({si for si, s in enumerate(shots) for f in fs if s['f0'] <= f <= s['f1']})})
        prev = None
        for f in fs:
            box, conf, merged = t.rows[f]
            x, y, w, h = box
            cx, cy = (x + w / 2) / W, (y + h / 2) / H
            vx = vy = sp = None
            if prev and prev[0] == f - 1:
                vx, vy = (cx - prev[1]) * fps, (cy - prev[2]) * fps
                sp = math.hypot(vx, vy)
            prev = (f, cx, cy)
            rows.append((t.id, f, f / fps, x / W, y / H, w / W, h / H, None, None, None, vx, vy, sp, 1, conf))
    store.put_samples(rows)

    # ---- overlaps between tracks (two subjects in one blob, or boxes intersecting) ----
    by_id = {t.id: t for t in tracks}
    ids = sorted(by_id)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            ta, tb = by_id[a], by_id[b]
            common = sorted(set(ta.rows) & set(tb.rows))
            run = []
            for f in common + [None]:
                ok = f is not None and (iou(ta.rows[f][0], tb.rows[f][0]) > 0.05 or ta.rows[f][2] and tb.rows[f][2])
                if ok and (not run or f == run[-1] + 1):
                    run.append(f)
                else:
                    if len(run) >= 2:
                        v = max(iou(ta.rows[g][0], tb.rows[g][0]) for g in run)
                        store.put_relation(a, b, 'overlap', run[0] / fps, run[-1] / fps, run[0], run[-1], v, 0.5,
                                           'box-iou')
                    run = [f] if ok else []

    # ---- motion freeze: a hit-stop or an impact stop (fast motion, then near nothing for >= 2 frames) ----
    k = 0
    for i in range(3, n - 2):
        before = energy[i - 3:i].max()
        if before > 0 and energy[i] < 0.2 * before and energy[i + 1] < 0.2 * before and \
                not any(b in (i, i - 1, i + 1) for b in bounds[1:-1]) and energy[i - 1] >= 0.2 * before:
            c = float(np.clip(1 - energy[i] / (0.2 * before), 0.3, 0.95))
            j = i
            while j + 1 < n and energy[j + 1] < 0.2 * before:
                j += 1
            # t0 = the impact (the last frame that still moved), t1 = the last frozen frame
            store.put_event(f'motion.freeze.{k:02d}', 'motion.freeze', (i - 1) / fps, j / fps, i - 1, [],
                            {'energy_before': round(float(before), 4), 'energy_after': round(float(energy[i]), 4),
                             'impact_t': round((i - 1) / fps, 4)},
                            c, 'framediff', 'vyrn.video')
            k += 1

    # ---- foot contacts ----
    k = 0
    for t in tracks:
        hs = np.median([t.rows[f][0][3] for f in t.rows])
        for f, c in foot_contacts(t, masks_all, fps, scale=max(1.0, hs / 40)):
            store.put_event(f'contact.foot-ground.{k:03d}', 'contact.foot-ground', f / fps, None, f, [t.id],
                            {'rule': 'bottom band stops moving'}, c, 'light/foot-band', 'vyrn.video')
            k += 1
    store.put_media(id=media_id, kind='video', source=path, sha256=sha, fps=fps, duration=info['duration'],
                    frames=n, width=info['width'], height=info['height'],
                    processors={'video': 'light/1', 'analysis': f'{W}x{H}', 'opencv': cv2.__version__},
                    stats={'shots': shots, 'tracks': len(tracks), 'audio': info['audio']})
    store.commit()
    return {'frames': n, 'shots': len(shots), 'tracks': len(tracks), 'cuts': len(cuts)}
