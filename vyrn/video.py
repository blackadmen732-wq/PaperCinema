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

AW = int(os.environ.get('VYRN_AW', 160))     # analysis width (px)


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
    """hard cuts from colour-histogram jumps with an adaptive threshold. A run of 1-3 jumping frames is one
    change; the cut is placed at the FIRST frame of the run (a cut often smears over two frames in a render).
    A run whose picture comes back afterwards is a flash (an ink impact frame, a white hit frame), not a cut;
    a run longer than 3 frames is a whip or a fast move unless one jump is very large.
    Returns ([(frame, score, confidence)], per-frame distance, [flash frames])."""
    hs = [hist(f) for f in frames]
    n = len(hs)
    dist = lambda a, b: 0.5 * float(np.abs(hs[a] - hs[b]).sum())
    d = np.array([0.0] + [dist(i, i - 1) for i in range(1, n)])
    w = max(3, int(fps))
    thr = np.array([max(0.12, 4 * np.median(d[max(1, i - w):i + w + 1])) for i in range(n)])
    above = d > thr
    cuts, flashes = [], []
    i = 1
    while i < n:
        if not above[i]:
            i += 1; continue
        j = i
        while j + 1 < n and above[j + 1]:
            j += 1
        peak = float(d[i:j + 1].max())
        after = range(j + 1, min(n, j + 5))
        back = min((dist(i - 1, k) for k in after), default=1.0)
        if back < 0.5 * peak:
            flashes.append(i)
        elif j - i <= 2 or peak > 0.5:
            c = float(min(1.0, (peak - thr[i]) / thr[i] + 0.5))
            cuts.append((i, peak, c))
        i = j + 1
    return cuts, d, flashes


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


def dense_flow(gray, bounds):
    """Farneback dense optical flow between consecutive frames of the same shot (OpenCV, Apache-2.0), float16"""
    n = len(gray)
    flows = [None] * n
    starts = set(bounds)
    for i in range(1, n):
        if i in starts:
            continue
        flows[i] = cv2.calcOpticalFlowFarneback(gray[i - 1], gray[i], None, 0.5, 3, 13, 3, 5, 1.1, 0).astype(np.float16)
    return flows


def articulation(t, masks, flows):
    """per frame: how much the subject changes shape, camera-independent. Optical flow inside the subject's mask
    minus its own median flow: a camera move, a pan or the whole body sliding moves every pixel alike and cancels;
    limbs and blades moving relative to the body do not. Unit: px/frame, divided by the subject's height in px."""
    out = {}
    for f in sorted(t.rows):
        fl = flows[f] if f < len(flows) else None
        if fl is None:
            continue
        x, y, w, h = [int(round(v)) for v in t.rows[f][0]]
        m = masks[f][max(0, y):y + h, max(0, x):x + w].astype(bool)
        if m.sum() < 8:
            continue
        F = fl[max(0, y):y + h, max(0, x):x + w][m].astype(np.float32)
        med = np.median(F, axis=0)
        out[f] = float(np.abs(F - med).sum(axis=1).mean()) / max(8.0, h) * 40
    return out


def foot_contacts(t, masks, flows, fps):
    """footsteps from pixels: the lowest 15 % of the subject's mask is split into parts (feet). Each part's median
    optical flow is compared with the flow of the ground right around it (not the camera's global pan, so parallax
    and pans cancel). A foot that moved relative to the ground and then holds still for 2 frames has planted.
    Returns [(frame, confidence)]."""
    ev = []
    feet = {}          # frame -> list of (x_centre, rel_speed px/frame)
    hs = []
    for f in sorted(t.rows):
        fl = flows[f] if f < len(flows) else None
        if fl is None:
            continue
        box, conf, merged = t.rows[f]
        x, y, w, h = [int(round(v)) for v in box]
        hs.append(h)
        y0 = y + int(h * 0.85)
        band = masks[f][max(0, y0):y + h, max(0, x):x + w]
        if band.size == 0 or band.sum() < 3:
            continue
        # the ground around the feet: unmasked pixels in a slightly wider band
        gy0, gy1 = max(0, y0 - 2), min(masks[f].shape[0], y + h + max(2, h // 10))
        gx0, gx1 = max(0, x - w // 2), min(masks[f].shape[1], x + w + w // 2)
        gm = masks[f][gy0:gy1, gx0:gx1] == 0
        G = fl[gy0:gy1, gx0:gx1][gm].astype(np.float32)
        ground = np.median(G, axis=0) if G.size else np.zeros(2, np.float32)
        n_, lab = cv2.connectedComponents(band.astype(np.uint8))
        parts = []
        for j in range(1, n_):
            ys, xs = np.nonzero(lab == j)
            if xs.size < 2:
                continue
            F = fl[max(0, y0) + ys, max(0, x) + xs].astype(np.float32)
            rel = float(np.linalg.norm(np.median(F, axis=0) - ground))
            parts.append((x + xs.mean(), rel, conf))
        if parts:
            feet[f] = parts
    if len(feet) < 4:
        return ev
    H = float(np.median(hs))
    move_thr, still_thr = 0.025 * H, 0.009 * H
    # follow each foot by nearest x between frames; a planted event fires once per stride
    tracks = []        # [last_f, x, history of rel speeds, armed]
    for f in sorted(feet):
        for (fx, rel, conf) in feet[f]:
            best = None
            for tr in tracks:
                if 0 < f - tr[0] <= 2 and abs(tr[1] - fx) < max(3, 0.12 * H) and (best is None or abs(tr[1] - fx) < abs(best[1] - fx)):
                    best = tr
            if best is None:
                best = [f, fx, [], False, conf]; tracks.append(best)
            best[0], best[1] = f, fx
            best[2].append(rel)
            hist = best[2]
            if rel > move_thr:
                best[3] = True                      # armed: it swung
            elif best[3] and len(hist) >= 2 and hist[-1] < still_thr and hist[-2] < still_thr * 1.5:
                c = float(np.clip(0.5 + 0.5 * (1 - hist[-1] / still_thr), 0.3, 0.9)) * (0.6 if conf < 1 else 1.0)
                ev.append((f - 1, round(c, 3)))      # the first still frame is the contact
                best[3] = False
    return sorted(set(ev))


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
    cuts, cutd, *rest = backends.stage('cuts')(frames, fps)
    for k, f in enumerate(rest[0] if rest else []):
        store.put_event(f'flash.{k:02d}', 'flash', f / fps, None, f, [], {}, 0.8, 'hist32x3', 'vyrn.video')
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
        masks, mode = (m_pan, 'aligned') if fp_ < fs_ else (m_static, 'static')
        shots[-1]['background'] = mode
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
    # subject motion, camera-independent: optical flow inside each subject minus its own median flow
    flows = dense_flow(gray, bounds)
    senergy = np.zeros(n)
    for t in tracks:
        for f, v in articulation(t, masks_all, flows).items():
            senergy[f] += v
    store.put_signal('motion.subject', fps, senergy, 'articulation px/frame per 40 px of subject height (summed)',
                     'farneback flow minus subject median')
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

    # ---- motion freeze: a hit-stop or an impact stop. The subject's articulation collapses after fast motion.
    # Thresholds adapt per shot: under a moving camera the floor is not zero (parallax, compression), so "frozen"
    # means near the shot's own floor (10th percentile) and well below the motion just before.
    k = 0
    for s0, s1 in zip(bounds, bounds[1:]):
        seg = energy[s0 + 1:s1]
        nz = seg[seg > 0]
        if nz.size < 6:
            continue
        floor = float(np.percentile(nz, 10))
        frozen = lambda i, before: energy[i] < 0.25 * before and energy[i] <= 1.3 * floor
        i = s0 + 4
        while i < s1 - 1:
            before = energy[i - 3:i].max()
            if before >= 2.5 * max(floor, 1e-6) and frozen(i, before) and frozen(i + 1, before) and not frozen(i - 1, before):
                j = i
                while j + 1 < s1 and frozen(j + 1, before):
                    j += 1
                c = float(np.clip(1 - energy[i] / max(1e-6, 0.25 * before), 0.3, 0.95))
                # t0 = the impact (the last frame that still moved), t1 = the last frozen frame
                store.put_event(f'motion.freeze.{k:02d}', 'motion.freeze', (i - 1) / fps, j / fps, i - 1, [],
                                {'energy_before': round(float(before), 4), 'energy_after': round(float(energy[i]), 4),
                                 'shot_floor': round(floor, 4), 'impact_t': round((i - 1) / fps, 4)},
                                c, 'articulation-collapse', 'vyrn.video')
                k += 1
                i = j + 1
            else:
                i += 1

    # ---- foot contacts ----
    k = 0
    for t in tracks:
        for f, c in foot_contacts(t, masks_all, flows, fps):
            store.put_event(f'contact.foot-ground.{k:03d}', 'contact.foot-ground', f / fps, None, f, [t.id],
                            {'rule': 'foot part stops relative to the ground'}, c, 'flow/foot-vs-ground', 'vyrn.video')
            k += 1
    store.put_media(id=media_id, kind='video', source=path, sha256=sha, fps=fps, duration=info['duration'],
                    frames=n, width=info['width'], height=info['height'],
                    processors={'video': 'light/1', 'analysis': f'{W}x{H}', 'opencv': cv2.__version__},
                    stats={'shots': shots, 'tracks': len(tracks), 'audio': info['audio']})
    store.commit()
    return {'frames': n, 'shots': len(shots), 'tracks': len(tracks), 'cuts': len(cuts)}
