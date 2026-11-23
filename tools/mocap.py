#!/usr/bin/env python3
"""MOCAP: motion capture from a phone video -> Paper Cinema motion data (docs/MOCAP.md).

    python3 tools/mocap.py clip.mp4 --out library/mocap/dash.json [--fps 24] [--start 1.2 --end 3.4]
            [--mirror] [--facing auto|keep|<deg>] [--tol 0.05 | --keys 8] [--as-move dash-cap] [--pose chudan]

Estimator: MediaPipe Pose Landmarker (BlazePose GHUM 3D), Apache-2.0 code and model (model card checked
2026-11, see docs/MOCAP.md). Runs on the CPU. It gives 33 landmarks per frame, both in the image and as
"world" landmarks in metres around the hip centre.

Pipeline (each step is a function below):
  1. estimate   run the landmarker on every source frame (VIDEO mode, temporal tracking)
  2. to_world   camera axes -> ours (y up, +z toward the camera); the pelvis position per frame is solved
                from the 2D/3D landmark pair (linear least squares, pinhole camera with --hfov)
  3. fix_flips  left/right swaps (whole body, arms, legs) against the previous frame
  4. smooth     one-euro filter run forward AND backward (zero phase: no lag at the hits)
  5. contacts   foot height + speed -> ground contact per foot; both off = airborne (root y)
  6. solve      landmarks -> our channels (figure.js): ry from the pelvis, waist/chest half each of the
                pelvis-to-shoulder rotation, shoulder rsx/rsy/rsz + elbow rex from the upper arm and forearm
                in the chest frame, wrist rwx, neck/head from ears + nose, crouch from the hip height,
                stance from the feet along the facing (left foot forward -> stride/phase, see MOCAP.md),
                weight from the hips over the feet, root x/z from the travel
  7. clamp      joint limits of engine/validate.mjs; Savitzky-Golay (small window) on the channels
  8. keys       every frame at --fps, or Douglas-Peucker in pose space (--tol) or exactly N keys (--keys)
"""
import argparse
import json
import math
import os
import sys
import urllib.request

import numpy as np
from scipy.signal import savgol_filter
from scipy.spatial.transform import Rotation

# ---------------------------------------------------------------------------------------------------------
# rig facts (engine/figure.js) and limits (engine/validate.mjs LIMITS)
LEG_LEN = 0.90                      # thigh 0.46 + shin 0.44
HIP_FOOT_REST = 0.86                # hip joint (0.92 - 0.02) to foot joint (0.04) when crouch = 0
LIMITS = {'rsx': (-3.1, 0.9), 'lsx': (-3.1, 0.9), 'rsz': (-1.6, 1.6), 'lsz': (-1.6, 1.6), 'rsy': (-1.2, 1.2), 'lsy': (-1.2, 1.2),
          'rex': (-2.6, 0), 'lex': (-2.6, 0), 'rwx': (-1.0, 1.4), 'lwx': (-1.0, 1.4),
          'tx': (-0.5, 1.2), 'ty': (-0.9, 0.9), 'tz': (-0.6, 0.6), 'cx': (-0.35, 0.5), 'cy': (-0.6, 0.6), 'cz': (-0.35, 0.35),
          'nx': (-0.5, 0.5), 'ny': (-0.7, 0.7), 'hx': (-0.6, 0.6), 'hy': (-0.9, 0.9), 'hz': (-0.4, 0.4),
          'stance': (0, 1.3), 'crouch': (-0.05, 0.6), 'weight': (-1, 1), 'stride': (0, 1.3), 'y': (0, 2.5)}
CHANNELS = ['x', 'y', 'z', 'ry', 'tx', 'ty', 'tz', 'cx', 'cy', 'cz', 'nx', 'ny', 'hx', 'hy', 'hz',
            'rsx', 'rsy', 'rsz', 'rex', 'rwx', 'lsx', 'lsy', 'lsz', 'lex', 'lwx', 'stance', 'crouch', 'weight', 'stride', 'phase']
POS = {'x', 'y', 'z', 'stance', 'crouch', 'stride'}      # metres (the rest are radians or unitless)

# MediaPipe landmark indices (person's own left / right)
NOSE, LEAR, REAR = 0, 7, 8
LSH, RSH, LEL, REL, LWR, RWR = 11, 12, 13, 14, 15, 16
LPI, RPI, LIN, RIN = 17, 18, 19, 20
LHIP, RHIP, LKN, RKN, LAN, RAN, LHE, RHE, LTO, RTO = 23, 24, 25, 26, 27, 28, 29, 30, 31, 32
PAIRS = [(1, 4), (2, 5), (3, 6), (7, 8), (9, 10), (11, 12), (13, 14), (15, 16), (17, 18), (19, 20), (21, 22),
         (23, 24), (25, 26), (27, 28), (29, 30), (31, 32)]
ARM_PAIRS = [(13, 14), (15, 16), (17, 18), (19, 20), (21, 22)]
LEG_PAIRS = [(25, 26), (27, 28), (29, 30), (31, 32)]
NAMES = ['nose', 'l_eye_in', 'l_eye', 'l_eye_out', 'r_eye_in', 'r_eye', 'r_eye_out', 'l_ear', 'r_ear', 'mouth_l', 'mouth_r',
         'l_shoulder', 'r_shoulder', 'l_elbow', 'r_elbow', 'l_wrist', 'r_wrist', 'l_pinky', 'r_pinky', 'l_index', 'r_index',
         'l_thumb', 'r_thumb', 'l_hip', 'r_hip', 'l_knee', 'r_knee', 'l_ankle', 'r_ankle', 'l_heel', 'r_heel', 'l_toe', 'r_toe']

MODEL_DIR = os.path.expanduser('~/.cache/paper-cinema/mediapipe')
MODEL_URL = 'https://huggingface.co/litert-community/MediaPipe-PoseLandmarker-{V}/resolve/main/pose_landmarker_{v}.task'


def log(*a):
    print('[mocap]', *a, file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------------------------------------
# 1. ESTIMATE
def model_path(variant):
    os.makedirs(MODEL_DIR, exist_ok=True)
    p = os.path.join(MODEL_DIR, f'pose_landmarker_{variant}.task')
    if not os.path.exists(p):
        url = MODEL_URL.format(V=variant.capitalize(), v=variant)
        log('downloading', url)
        urllib.request.urlretrieve(url, p)
    return p


def estimate(video, start=0.0, end=None, mirror=False, variant='full'):
    """Run the pose landmarker on every source frame in [start, end].
    Returns t (N,), img (N,33,3: x,y in 0..1, visibility), world (N,33,3 metres, camera axes), size (w, h), fps."""
    import cv2
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python import vision
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        sys.exit(f'cannot open {video}')
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    opts = vision.PoseLandmarkerOptions(base_options=BaseOptions(model_asset_path=model_path(variant)),
                                        running_mode=vision.RunningMode.VIDEO, num_poses=1,
                                        min_pose_detection_confidence=0.3, min_pose_presence_confidence=0.3, min_tracking_confidence=0.3)
    det = vision.PoseLandmarker.create_from_options(opts)
    i0 = int(round(start * fps))
    cap.set(cv2.CAP_PROP_POS_FRAMES, i0)
    ts, imgs, worlds = [], [], []
    i = i0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t = i / fps
        if end is not None and t > end + 1e-6:
            break
        if mirror:
            frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = det.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)), int(round(t * 1000)))
        if res.pose_landmarks:
            lm, wl = res.pose_landmarks[0], res.pose_world_landmarks[0]
            imgs.append([[p.x, p.y, p.visibility if p.visibility is not None else 1.0] for p in lm])
            worlds.append([[p.x, p.y, p.z] for p in wl])
        else:
            imgs.append(np.full((33, 3), np.nan).tolist())
            worlds.append(np.full((33, 3), np.nan).tolist())
        ts.append(t)
        i += 1
        if (i - i0) % 60 == 0:
            log(f'frame {i - i0}  t={t:.2f}s')
    det.close()
    cap.release()
    return np.array(ts), np.array(imgs, float), np.array(worlds, float), (W, H), fps


def fill_gaps(t, a):
    """Linear interpolation over frames with no detection (NaN). a: (N, ...)."""
    flat = a.reshape(len(t), -1)
    bad = np.isnan(flat[:, 0])
    if bad.all():
        sys.exit('no person found in the clip')
    if bad.any():
        gaps = np.diff(np.flatnonzero(np.diff(np.r_[0, bad.astype(int), 0])))
        log(f'{bad.sum()} frames without a person (longest gap {gaps.max() if len(gaps) else 0} frames): interpolated')
        for j in range(flat.shape[1]):
            flat[bad, j] = np.interp(t[bad], t[~bad], flat[~bad, j])
    return flat.reshape(a.shape)


# ---------------------------------------------------------------------------------------------------------
# 2. CAMERA -> OUR WORLD
def solve_translation(img, world, size, hfov_deg):
    """Pelvis position in camera space per frame: X + T projects onto the image points (pinhole, focal from hfov).
    u (Z + Tz) = X + Tx  ->  Tx - u Tz = u Z - X (same for y): linear least squares, visibility-weighted."""
    W, H = size
    f = (W / 2) / math.tan(math.radians(hfov_deg) / 2)
    T = np.zeros((len(img), 3))
    for n in range(len(img)):
        u = (img[n, :, 0] * W - W / 2) / f
        v = (img[n, :, 1] * H - H / 2) / f
        w = np.clip(img[n, :, 2], 0.05, 1.0)
        X, Y, Z = world[n, :, 0], world[n, :, 1], world[n, :, 2]
        A = np.zeros((66, 3)); b = np.zeros(66)
        A[:33, 0] = 1; A[:33, 2] = -u; b[:33] = u * Z - X
        A[33:, 1] = 1; A[33:, 2] = -v; b[33:] = v * Z - Y
        ww = np.r_[w, w][:, None]
        T[n] = np.linalg.lstsq(A * ww, b * ww[:, 0], rcond=None)[0]
    return T


def to_ours(p, tilt_deg=0.0):
    """Camera axes (x right, y down, z away) -> ours (x right of the frame, y up, z toward the camera).
    tilt: the phone looks down by this many degrees (rotates the world back to level)."""
    q = p * np.array([1.0, -1.0, -1.0])
    if tilt_deg:
        a = math.radians(tilt_deg)
        Rx = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
        q = q @ Rx.T
    return q


# ---------------------------------------------------------------------------------------------------------
# 3. LEFT / RIGHT FLIPS
def swap(frame, pairs):
    g = frame.copy()
    for a, b in pairs:
        g[[a, b]] = g[[b, a]]
    return g


def fix_flips(world, img):
    """Compare each frame (and its whole-body / arms / legs swaps) with a prediction from the frames before it."""
    n = len(world)
    fixed = 0
    for i in range(1, n):
        pred = world[i - 1] if i < 2 else world[i - 1] + 0.5 * (world[i - 1] - world[i - 2])
        for pairs in (PAIRS, ARM_PAIRS, LEG_PAIRS):
            idx = sorted({k for p in pairs for k in p})
            cur = np.linalg.norm(world[i][idx] - pred[idx], axis=1).sum()
            sw = swap(world[i], pairs)
            alt = np.linalg.norm(sw[idx] - pred[idx], axis=1).sum()
            if alt < 0.6 * cur and cur - alt > 0.08 * len(idx) / 2:
                world[i] = sw
                img[i] = swap(img[i], pairs)
                fixed += 1
    if fixed:
        log(f'left/right flips fixed: {fixed}')
    return world, img


# ---------------------------------------------------------------------------------------------------------
# 4. SMOOTHING
def one_euro(x, t, mincutoff=1.7, beta=0.4, dcutoff=1.0):
    """One-euro filter along axis 0 (x: (N, ...)). Adapts: smooth when slow, follows fast moves."""
    y = np.empty_like(x)
    y[0] = x[0]
    dx = np.zeros_like(x[0])
    alpha = lambda cut, dt: 1.0 / (1.0 + 1.0 / (2 * math.pi * cut * dt))
    for i in range(1, len(x)):
        dt = max(1e-4, abs(t[i] - t[i - 1]))
        d = (x[i] - y[i - 1]) / dt
        a_d = alpha(dcutoff, dt)
        dx = a_d * d + (1 - a_d) * dx
        cut = mincutoff + beta * np.abs(dx)
        a = 1.0 / (1.0 + 1.0 / (2 * math.pi * cut * dt))
        y[i] = a * x[i] + (1 - a) * y[i - 1]
    return y


def zero_phase_euro(x, t, **kw):
    """Forward + backward one-euro, averaged: the lags cancel, so a hit lands on its true frame."""
    f = one_euro(x, t, **kw)
    b = one_euro(x[::-1], t[::-1], **kw)[::-1]
    return 0.5 * (f + b)


# ---------------------------------------------------------------------------------------------------------
# rotation helpers (three.js conventions)
def Rx(a):
    c, s = math.cos(a), math.sin(a); return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def Ry(a):
    c, s = math.cos(a), math.sin(a); return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def Rz(a):
    c, s = math.cos(a), math.sin(a); return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def euler_xyz(a, b, c):
    """THREE.Euler(a, b, c, 'XYZ') as a matrix."""
    return Rx(a) @ Ry(b) @ Rz(c)


def to_euler_xyz(m):
    """Matrix -> THREE 'XYZ' Euler (same formula as Euler.setFromRotationMatrix)."""
    b = math.asin(max(-1.0, min(1.0, m[0, 2])))
    if abs(m[0, 2]) < 0.9999999:
        return math.atan2(-m[1, 2], m[2, 2]), b, math.atan2(-m[0, 1], m[0, 0])
    return math.atan2(m[2, 1], m[1, 1]), b, 0.0


def half(m):
    return Rotation.from_rotvec(Rotation.from_matrix(m).as_rotvec() / 2).as_matrix()


def unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v


def frame_from(xaxis, upish):
    """Right-handed frame with x = xaxis, y as close to upish as possible, z = x × y (forward)."""
    x = unit(xaxis)
    y = unit(upish - np.dot(upish, x) * x)
    z = np.cross(x, y)
    return np.stack([x, y, z], axis=1)


def arm_angles(u, f, prev_rsy=0.0):
    """Shoulder (rsx, rsy, rsz) and elbow rex so the upper arm points along u and the forearm along f
    (both unit vectors in the clavicle/chest frame). The rest arm hangs along -y; rex bends toward local +z."""
    cosb = float(np.clip(np.dot(u, f), -1, 1))
    rex = -math.acos(cosb)
    perp = f - np.dot(f, u) * u
    if np.linalg.norm(perp) > 0.12:                          # a clear bend: the bend plane fixes the twist
        Yc, Zc = -u, unit(perp)
        M = np.stack([np.cross(Yc, Zc), Yc, Zc], axis=1)
        _, b, _ = to_euler_xyz(M)
        w = min(1.0, (np.linalg.norm(perp) - 0.12) / 0.2)    # fade the twist in as the bend grows (no pops)
        b = w * b + (1 - w) * prev_rsy
    else:
        b = prev_rsy * 0.9
    b = float(np.clip(b, *LIMITS['rsy']))
    # exact upper-arm direction for this twist: R(a,b,c)·(0,-1,0) = u
    c = math.asin(float(np.clip(u[0] / max(1e-6, math.cos(b)), -1, 1)))
    Y, Z = -math.cos(c), -math.sin(c) * math.sin(b)
    a = math.atan2(u[2], u[1]) - math.atan2(Z, Y)
    a = math.atan2(math.sin(a), math.cos(a))
    if a > 1.6:                                              # keep rsx in its range (-3.1 … 0.9): same pose, other branch
        a -= 2 * math.pi
    return a, b, c, rex


def wrist_angle(R_fore, hand_vec):
    """rwx: hand flex in the forearm frame (rest hand along -y; +rwx swings it toward -z... see Rx)."""
    h = R_fore.T @ unit(hand_vec)
    return math.atan2(-h[2], -h[1])


# ---------------------------------------------------------------------------------------------------------
# 5 + 6. CONTACTS AND SOLVE
def solve(t, P, root, opts):
    """P: (N,33,3) landmarks in our axes around the pelvis (metres, performer size); root: (N,3) pelvis
    position in our world. Returns dict channel -> (N,) and the per-frame contacts."""
    N = len(t)
    leg = np.r_[np.linalg.norm(P[:, LHIP] - P[:, LKN], axis=1) + np.linalg.norm(P[:, LKN] - P[:, LAN], axis=1),
                np.linalg.norm(P[:, RHIP] - P[:, RKN], axis=1) + np.linalg.norm(P[:, RKN] - P[:, RAN], axis=1)]
    s = LEG_LEN / float(np.median(leg)) if opts.get('scale') is None else opts['scale']
    G = (P + root[:, None, :]) * s                           # landmarks in our world, scaled to our figure
    # ground contact per foot: height above the ground (a low percentile of the lowest foot) and speed
    foot = {'r': [RAN, RHE, RTO], 'l': [LAN, LHE, LTO]}
    # The ground is a PLANE fitted to the lowest foot over the clip (robust lower envelope): monocular depth error
    # and a tilted phone both make a level floor look like a slope, which would otherwise read as jumps.
    low = np.stack([G[:, foot['r'] + foot['l'], 1].min(axis=1), G[:, RAN, 0] * 0 + G[:, [RAN, LAN], 0].mean(axis=1),
                    G[:, [RAN, LAN], 2].mean(axis=1)], axis=1)               # (y, x, z) of the lowest foot per frame
    A = np.c_[np.ones(N), low[:, 1], low[:, 2]]
    keep = np.ones(N, bool)
    for _ in range(4):
        coef = np.linalg.lstsq(A[keep], low[keep, 0], rcond=None)[0]
        res = low[:, 0] - A @ coef
        keep = res <= np.percentile(res, 40) + 0.02
    spread = np.ptp(low[:, 1:], axis=0)
    if spread[0] < 0.6: coef[1] = 0.0                                        # too little travel to fit a slope that way
    if spread[1] < 0.6: coef[2] = 0.0
    coef[0] = float(np.percentile(low[:, 0] - A[:, 1:] @ coef[1:], 5))
    gy = lambda x, z: coef[0] + coef[1] * x + coef[2] * z                     # ground height under (x, z)
    fh, contact = {}, {}
    for k, v in foot.items():
        pos = G[:, v].mean(axis=1)
        fh[k] = G[:, v, 1].min(axis=1) - gy(pos[:, 0], pos[:, 2])
        sp = np.r_[0, np.linalg.norm(np.diff(pos[:, [0, 2]], axis=0), axis=1) / np.maximum(1e-4, np.diff(t))]
        contact[k] = (fh[k] < 0.08) & (sp < 1.2)
    lift = np.minimum(fh['r'], fh['l'])
    # airborne: both feet clear 12 cm for at least 0.1 s, or it is depth noise (a real jump clears that easily)
    air = ~(contact['r'] | contact['l']) & (lift > opts.get('jump_min', 0.12))
    i = 0
    while i < N:
        if air[i]:
            j = i
            while j < N and air[j]:
                j += 1
            if t[min(j, N - 1)] - t[i] < 0.1:
                air[i:j] = False
            i = j
        else:
            i += 1
    ground = float(coef[0] + coef[1] * low[0, 1] + coef[2] * low[0, 2])

    ch = {c: np.zeros(N) for c in CHANNELS}
    prev = {'r': 0.0, 'l': 0.0}
    up = np.array([0.0, 1.0, 0.0])
    for i in range(N):
        g = G[i]
        pel = 0.5 * (g[LHIP] + g[RHIP])
        # facing: the pelvis line, helped by the shoulder line (hips are hard to see side-on)
        xh = g[LHIP] - g[RHIP]; xs = g[LSH] - g[RSH]
        hw = opts.get('hip_weight', 0.85)
        xl = unit(np.array([xh[0], 0, xh[2]])) * hw + unit(np.array([xs[0], 0, xs[2]])) * (1 - hw)
        fwd = unit(np.cross(xl, up))
        ry = math.atan2(fwd[0], fwd[2])
        Rroot = Ry(ry)
        # feet along the facing (rig: right foot leads by stance / 2, hips sit weight * stance * 0.35 ahead)
        ar, al = np.dot(g[RAN] - pel, fwd), np.dot(g[LAN] - pel, fwd)
        sep, mid = ar - al, 0.5 * (ar + al)
        stance = sep if sep >= 0 else 0.0
        stride = -sep if sep < 0 else 0.0
        weight = float(np.clip(-mid / (0.35 * max(stance, 0.15)), -1, 1)) * min(1.0, stance / 0.15)
        hipZ = weight * stance * 0.35
        rootp = pel - fwd * hipZ
        # crouch: hip joint height over the planted ankle; airborne: the lowest foot's lift is root y
        ank = min(g[RAN][1], g[LAN][1])
        crouch = HIP_FOOT_REST - (pel[1] - ank)
        y = float(lift[i]) if air[i] else 0.0
        # spine: chest frame from the shoulders; split the pelvis->chest rotation half waist, half chest
        sh = 0.5 * (g[LSH] + g[RSH])
        Rchest = frame_from(xs, sh - pel)
        Rrel = Rroot.T @ Rchest
        Hh = half(Rrel)
        e = to_euler_xyz(Hh)
        tx, ty, tz = e[0] - weight * 0.05, e[1], e[2]
        cx, cy, cz = e
        # clamp the chest, give the rest to the waist (small-angle: Euler angles add)
        cxc, cyc, czc = (float(np.clip(cx, *LIMITS['cx'])), float(np.clip(cy, *LIMITS['cy'])), float(np.clip(cz, *LIMITS['cz'])))
        tx, ty, tz = tx + (cx - cxc), ty + (cy - cyc), tz + (cz - czc)
        tx, ty, tz = (float(np.clip(tx, *LIMITS['tx'])), float(np.clip(ty, *LIMITS['ty'])), float(np.clip(tz, *LIMITS['tz'])))
        # the model's chest frame after clamping: the arms and head are solved inside it
        Rm = Rroot @ euler_xyz(tx + weight * 0.05, ty, tz) @ euler_xyz(cxc, cyc, czc)
        out = dict(x=rootp[0], z=rootp[2], y=y, ry=ry, tx=tx, ty=ty, tz=tz, cx=cxc, cy=cyc, cz=czc,
                   stance=stance, stride=stride, phase=-math.pi / 2, weight=weight, crouch=crouch)
        for side, S, E, Wr, Pi, In in (('r', RSH, REL, RWR, RPI, RIN), ('l', LSH, LEL, LWR, LPI, LIN)):
            u = unit(Rm.T @ (g[E] - g[S])); f = unit(Rm.T @ (g[Wr] - g[E]))
            a, b, c, rex = arm_angles(u, f, prev[side])
            a = float(np.clip(a, *LIMITS[side + 'sx'])); c = float(np.clip(c, *LIMITS[side + 'sz']))
            rex = float(np.clip(rex, *LIMITS[side + 'ex']))
            prev[side] = b
            Rf = Rm @ euler_xyz(a, b, c) @ Rx(rex)
            hand = 0.5 * (g[Pi] + g[In]) - g[Wr]
            wx = float(np.clip(0.7 * wrist_angle(Rf, hand), *LIMITS[side + 'wx'])) if opts.get('wrists', True) else 0.0
            out.update({side + 'sx': a, side + 'sy': b, side + 'sz': c, side + 'ex': rex, side + 'wx': wx})
        # head: ears give the side axis, the nose the front (the nose sits ~0.25 rad below the ear line)
        if opts.get('head', True):
            xe = g[LEAR] - g[REAR]
            fz = g[NOSE] - 0.5 * (g[LEAR] + g[REAR])
            x_ = unit(xe); z0 = unit(fz - np.dot(fz, x_) * x_)
            Rh = np.stack([x_, np.cross(z0, x_), z0], axis=1) @ Rx(-opts.get('nose_pitch', 0.25))
            hr = to_euler_xyz(Rm.T @ Rh)
            out.update(nx=hr[0] / 2, ny=hr[1] / 2, hx=hr[0] / 2, hy=hr[1] / 2, hz=hr[2])
        for k, v in out.items():
            ch[k][i] = v
    ch['ry'] = np.unwrap(ch['ry'])
    return ch, {'r': contact['r'], 'l': contact['l'], 'air': air, 'ground': ground}, s


def post(ch, t, window_s=0.15):
    """Small-window Savitzky-Golay (keeps the peaks, kills the jitter), then the joint limits."""
    dt = float(np.median(np.diff(t))) if len(t) > 1 else 1 / 30
    win = max(5, int(round(window_s / dt)) | 1)
    for k, v in ch.items():
        if k == 'phase':
            continue
        if len(v) > win and k not in ('y',):
            v = savgol_filter(v, win, 2)
        if k in LIMITS:
            v = np.clip(v, *LIMITS[k])
        ch[k] = v
    return ch


def orient(ch, mode, cam):
    """--facing: auto = start facing +z at the origin; keep = as filmed (+z = toward the camera); <deg> = start facing that.
    cam (the phone: pos, look) is moved with the performance, so a film can put its camera where the phone was."""
    if mode == 'keep':
        return ch, cam
    n0 = max(1, int(len(ch['ry']) * 0.05))
    ry0 = float(np.median(ch['ry'][:n0]))
    want = 0.0 if mode == 'auto' else math.radians(float(mode))
    d = want - ry0
    x0, z0 = ch['x'][0], ch['z'][0]
    dx, dz = ch['x'] - x0, ch['z'] - z0
    c, s = math.cos(d), math.sin(d)
    rot = lambda px, pz: (c * (px - x0) + s * (pz - z0), -s * (px - x0) + c * (pz - z0))
    ch['x'], ch['z'] = rot(ch['x'], ch['z'])                   # rotate about +y by d (same sense as ry)
    ch['ry'] = ch['ry'] + d
    cam = {k: [rot(v[0], v[2])[0], v[1], rot(v[0], v[2])[1]] for k, v in cam.items()}
    return ch, cam


# ---------------------------------------------------------------------------------------------------------
# 8. KEYS
def pose_matrix(ch, names):
    """(N, C) with metres x2 so 5 cm counts like ~0.1 rad."""
    return np.stack([ch[c] * (2.0 if c in POS else 1.0) for c in names], axis=1)


def dp_keys(Mx, tol=None, n_keys=None):
    """Douglas-Peucker on the pose curve: keep the frame that the straight line between kept keys misses most,
    until every frame is within tol (per channel) or there are n_keys keys."""
    N = len(Mx)
    keep = {0, N - 1}

    def worst(a, b):
        if b - a < 2:
            return 0.0, None
        k = np.arange(a + 1, b)
        lin = Mx[a] + (Mx[b] - Mx[a]) * ((k - a) / (b - a))[:, None]
        err = np.abs(Mx[a + 1:b] - lin).max(axis=1)
        j = int(err.argmax())
        return float(err[j]), a + 1 + j
    while True:
        ks = sorted(keep)
        best = (0.0, None)
        for a, b in zip(ks, ks[1:]):
            e, j = worst(a, b)
            if e > best[0]:
                best = (e, j)
        if best[1] is None:
            break
        if n_keys is not None and len(keep) >= n_keys:
            break
        if n_keys is None and best[0] <= tol:
            break
        keep.add(best[1])
    return sorted(keep)


def rnd(v, k):
    return round(float(v), 3 if k in POS or k in ('x', 'z') else 3)


def build(args):
    t, img, world, size, sfps = estimate(args.video, args.start or 0.0, args.end, args.mirror, args.model)
    img = fill_gaps(t, img)
    world = fill_gaps(t, world)
    world, img = fix_flips(world, img)
    T = solve_translation(img, world, size, args.hfov)
    P = to_ours(world, args.tilt)
    root = to_ours(T, args.tilt)
    # smoothing: landmarks (shape) and the pelvis path (noisier: monocular depth) separately
    P = zero_phase_euro(P, t, mincutoff=args.mincutoff, beta=args.beta)
    root = zero_phase_euro(root, t, mincutoff=args.mincutoff * 0.5, beta=args.beta * 0.5)
    if args.no_root:
        root[:] = root.mean(axis=0) * np.array([1, 0, 1]) + root * np.array([0, 1, 0])
    ch, cont, s = solve(t, P, root, {'head': not args.no_head, 'wrists': not args.no_wrists})
    ch = post(ch, t)
    # the phone in our world: at the origin of the camera axes, lifted so the ground is y = 0, looking along -z
    h = -cont['ground']
    cam = {'pos': [0.0, h, 0.0], 'look': [0.0, h, -1.0]}
    ch, cam = orient(ch, args.facing, cam)
    if args.at:
        ax, az = (float(v) for v in args.at.split(','))
        ch['x'] += ax; ch['z'] += az
        cam = {k: [v[0] + ax, v[1], v[2] + az] for k, v in cam.items()}
    cont['camera'] = cam
    return t, img, world, P, root, T, ch, cont, s, size, sfps


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('video')
    ap.add_argument('--out', required=True, help='library/mocap/<name>.json')
    ap.add_argument('--fps', type=float, default=24, help='output frame rate (default 24, the film rate)')
    ap.add_argument('--start', type=float, help='seconds into the clip')
    ap.add_argument('--end', type=float)
    ap.add_argument('--mirror', action='store_true', help='mirror the performance (left-handed take, or a selfie-mirrored video)')
    ap.add_argument('--facing', default='auto', help='auto (start facing +z at 0,0) | keep (as filmed: +z = toward the camera) | <degrees>')
    ap.add_argument('--at', help='start position x,z in metres (after --facing)')
    ap.add_argument('--tol', type=float, help='simplify to keyframes: max error per channel (rad; metres count double)')
    ap.add_argument('--keys', type=int, help='reduce to exactly N key poses (Douglas-Peucker in pose space)')
    ap.add_argument('--as-move', help='also write a library/moves.json-style move with this name (relative fwd/side/turn)')
    ap.add_argument('--pose', help='named pose under every key (gives the channels mocap does not solve: wrist roll, clavicles)')
    ap.add_argument('--model', default='full', choices=['lite', 'full', 'heavy'], help='landmarker size (heavy = best, ~3x slower)')
    ap.add_argument('--hfov', type=float, default=65.0, help='camera horizontal field of view in degrees (phone main camera ~65)')
    ap.add_argument('--tilt', type=float, default=0.0, help='degrees the phone looks down (0 = level tripod)')
    ap.add_argument('--mincutoff', type=float, default=1.7, help='one-euro: lower = smoother when slow')
    ap.add_argument('--beta', type=float, default=0.4, help='one-euro: higher = less lag on fast moves')
    ap.add_argument('--no-root', action='store_true', help='keep the root still (only the body moves)')
    ap.add_argument('--no-head', action='store_true', help='do not solve the head (faces turned away, hats)')
    ap.add_argument('--no-wrists', action='store_true')
    ap.add_argument('--no-raw', action='store_true', help='do not store the raw landmarks')
    args = ap.parse_args()

    t, img, world, P, root, T, ch, cont, s, size, sfps = build(args)
    # resample to the output rate
    t0 = t[0]
    tt = np.arange(0, (t[-1] - t0) + 1e-9, 1.0 / args.fps)
    R = {k: np.interp(tt, t - t0, v) for k, v in ch.items()}
    names = [c for c in CHANNELS if not (args.no_head and c in ('nx', 'ny', 'hx', 'hy', 'hz'))]
    if args.keys or args.tol:
        idx = dp_keys(pose_matrix(R, names), tol=args.tol, n_keys=args.keys)
    else:
        idx = list(range(len(tt)))
    keys = []
    for i in idx:
        k = {'t': round(float(tt[i]), 4)}
        if args.pose:
            k['pose'] = args.pose
        for c in names:
            k[c] = rnd(R[c][i], c)
        keys.append(k)
    on = lambda a: [round(float(x), 3) for x in np.interp(tt, t - t0, a.astype(float))]
    out = {
        '_about': 'Motion captured from video by tools/mocap.py (docs/MOCAP.md). keys = a performance key list for '
                  'film.performances.<id>.keys (shift t to place it). stance < 0 (left foot forward) is stored as stride with phase -pi/2.',
        'source': {'video': os.path.basename(args.video), 'fps': round(sfps, 3), 'size': list(size), 'start': args.start, 'end': args.end,
                   'mirror': args.mirror, 'model': f'MediaPipe Pose Landmarker {args.model} (Apache-2.0)', 'hfov': args.hfov},
        'fps': args.fps, 'duration': round(float(tt[-1]), 4), 'scale': round(s, 4), 'facing': args.facing,
        'camera': {'pos': [round(v, 3) for v in cont['camera']['pos']], 'look': [round(v, 3) for v in cont['camera']['look']],
                   'hfov': args.hfov, 'aspect': round(size[0] / size[1], 4),
                   'about': 'where the phone was, in the same world as the keys (tools/mocap_film.py puts the film camera here)'},
        'channels': names, 'keys': keys,
        'contacts': {'t': [round(float(x), 4) for x in tt], 'r': [int(v > 0.5) for v in on(cont['r'])],
                     'l': [int(v > 0.5) for v in on(cont['l'])], 'air': [int(v > 0.5) for v in on(cont['air'])]},
    }
    if args.as_move:
        out['move'] = {args.as_move: to_move(keys, args.pose or 'neutral')}
    if not args.no_raw:
        out['raw'] = {'about': 'per source frame: t; image = 33 x [x, y, visibility] (0..1 of the frame); world = 33 x [x, y, z] metres '
                               'around the pelvis in OUR axes (y up, +z toward the camera), smoothed; pelvis = camera-space pelvis [x, y, z] in our axes',
                      'names': NAMES, 't': [round(float(x - t0), 4) for x in t],
                      'image': np.round(img, 4).tolist(), 'world': np.round(P, 4).tolist(), 'pelvis': np.round(root, 4).tolist()}
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, 'w') as fh:
        json.dump(out, fh, separators=(',', ':'))
    log(f'{len(t)} source frames ({sfps:.1f} fps) -> {len(keys)} keys over {tt[-1]:.2f}s, scale {s:.3f} -> {args.out}')


def to_move(keys, pose):
    """Keys -> move beats: dt from the first key, fwd / side relative to the start position and facing,
    turn = yaw change (engine/moves.js), every solved joint as an override."""
    k0 = keys[0]
    ry0 = k0['ry']
    fx, fz = math.sin(ry0), math.cos(ry0)
    sx, sz = math.cos(ry0), -math.sin(ry0)
    beats = []
    for k in keys:
        dx, dz = k['x'] - k0['x'], k['z'] - k0['z']
        b = {'dt': round(k['t'] - k0['t'], 4), 'pose': pose, 'fwd': round(dx * fx + dz * fz, 3), 'side': round(dx * sx + dz * sz, 3)}
        turn = round(k['ry'] - ry0, 3)
        if abs(turn) > 1e-3:
            b['turn'] = turn
        for c, v in k.items():
            if c not in ('t', 'x', 'z', 'ry', 'pose'):
                b[c] = v
        beats.append(b)
    return beats


if __name__ == '__main__':
    main()
