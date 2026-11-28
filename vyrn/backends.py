"""Perception backends: every stage has a light CPU default and named alternatives, each with its licence.

A stage is swapped with an environment variable naming a Python function with the default's signature:
  VYRN_CUTS=mypkg.mymod:detect_cuts  VYRN_CAMERA=...  VYRN_ONSETS=...
The function must return the same shape as the default (see the default's docstring). Nothing else in VYRN
changes, and vyrn/bench/run.py grades the replacement on the same scene, so a neural model has to beat the light
default by a measured margin before it earns its GPU.

Licences: code and weights were checked separately (AGENTS.md rule 6). "no" means not usable in a monetised film.
"""
import importlib, os

STAGES = {
    'cuts': ('VYRN_CUTS', 'vyrn.video:detect_cuts'),
    'camera': ('VYRN_CAMERA', 'vyrn.video:camera_motion'),
    'onsets': ('VYRN_ONSETS', 'vyrn.audio:onsets'),
}


def stage(name):
    env, default = STAGES[name]
    ref = os.environ.get(env) or default
    mod, fn = ref.split(':')
    return getattr(importlib.import_module(mod), fn)


# (stage, name, gives, compute, code licence, weights licence, commercial, status)
CATALOG = [
    ('decode', 'FFmpeg', 'decode, scale, audio, seek for evidence', 'CPU', 'LGPL-2.1+ (binary, not linked)', '-', 'yes', 'used'),
    ('cuts', 'colour-histogram distance (ours, PySceneDetect "content" idea)', 'hard cuts', 'CPU', 'ours', '-', 'yes', 'default'),
    ('cuts', 'PySceneDetect', 'cuts, fades', 'CPU', 'BSD-3-Clause', '-', 'yes', 'drop-in option'),
    ('camera', 'Shi-Tomasi + pyramidal Lucas-Kanade + RANSAC (OpenCV)', 'camera pan per frame', 'CPU', 'Apache-2.0', '-', 'yes', 'default'),
    ('camera', 'FFmpeg motion vectors (codec side data)', 'block motion for free while decoding', 'CPU', 'LGPL-2.1+', '-', 'yes', 'candidate'),
    ('flow', 'Farneback dense optical flow (OpenCV)', 'per-pixel motion', 'CPU', 'Apache-2.0', '-', 'yes', 'candidate'),
    ('flow', 'RAFT', 'accurate dense flow', 'GPU (CPU slow)', 'BSD-3-Clause', 'BSD-3 (repo checkpoints)', 'yes', 'optional'),
    ('objects', 'median background + connected components + IoU tracker (ours, OpenCV)', 'moving subjects with ids', 'CPU', 'ours / Apache-2.0', '-', 'yes', 'default'),
    ('objects', 'SAM 2.1 (hiera-tiny)', 'promptable segmentation + video propagation', 'GPU (tiny runs on CPU, slowly)', 'Apache-2.0', 'Apache-2.0', 'yes', 'optional, next'),
    ('objects', 'Ultralytics YOLO', 'detection', 'CPU/GPU', 'AGPL-3.0', 'AGPL-3.0', 'no (or paid)', 'rejected'),
    ('points', 'TAPIR / BootsTAP (tapnet)', 'long-range point tracks through occlusion', 'GPU', 'Apache-2.0', 'Apache-2.0', 'yes', 'optional'),
    ('points', 'CoTracker 3', 'dense point tracks', 'GPU', 'CC-BY-NC-4.0', 'CC-BY-NC-4.0', 'no', 'rejected'),
    ('pose', 'MediaPipe Pose Landmarker (already in tools/mocap.py)', '33 body landmarks, 3D', 'CPU', 'Apache-2.0', 'Apache-2.0', 'yes', 'optional, reuse'),
    ('audio', 'spectral flux + attack refinement (ours, numpy)', 'hits vs swells, 1 ms timing', 'CPU', 'ours', '-', 'yes', 'default'),
    ('audio', 'librosa onset_detect', 'onsets, beats', 'CPU', 'ISC', '-', 'yes', 'drop-in option'),
    ('audio', 'aubio', 'onsets, pitch', 'CPU', 'GPL-3.0', '-', 'only if not distributed', 'avoid'),
    ('audio', 'madmom', 'onsets, beats (neural)', 'CPU', 'BSD (code)', 'CC-BY-NC-SA (models)', 'no for models', 'rejected'),
    ('audio', 'Silero VAD', 'speech regions', 'CPU', 'MIT', 'MIT', 'yes', 'candidate'),
    ('audio', 'faster-whisper (already in tools/listen.py)', 'speech with timestamps', 'CPU', 'MIT', 'MIT (Whisper)', 'yes', 'optional, reuse'),
    ('audio', 'PANNs (audioset_tagging_cnn)', 'sound-event classes', 'CPU', 'MIT', 'not stated on the repo page', 'check before use', 'candidate'),
    ('audio', 'CLAP (LAION clap-htsat-unfused)', 'text <-> sound similarity', 'CPU/GPU', 'CC0-1.0', 'Apache-2.0', 'yes', 'optional (shared with Sonic)'),
    ('audio', 'Microsoft CLAP', 'text <-> sound similarity', 'CPU/GPU', 'MIT', 'see model card', 'check', 'candidate'),
    ('scene', 'V-JEPA 2 (ViT-L)', 'video embeddings, action understanding', 'GPU', 'MIT', 'MIT', 'yes', 'research, later'),
    ('omni', 'Qwen3-Omni-30B-A3B', 'video+audio question answering', 'big GPU', 'Apache-2.0', 'Apache-2.0', 'yes', 'research, later'),
    ('omni', 'Qwen2.5-Omni-7B', 'video+audio question answering', 'GPU', 'Apache-2.0', 'Apache-2.0', 'yes', 'research, later'),
    ('omni', 'Qwen2.5-Omni-3B', 'video+audio question answering', 'GPU', 'Apache-2.0', 'Qwen Research licence', 'no', 'rejected'),
]


def table():
    rows = ['stage | backend | gives | compute | code | weights | commercial | status', '---|---|---|---|---|---|---|---']
    rows += [' | '.join(r) for r in CATALOG]
    return '\n'.join(rows)
