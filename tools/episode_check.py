#!/usr/bin/env python3
"""EPISODE CHECK: is a finished episode file actually a postable vertical Short?

  python3 tools/episode_check.py output/ganryujima-ep1-final.mp4 [--min 45] [--max 60]

Measures, never assumes: frame size 1080x1920, length inside [min, max] seconds, an H.264 video
stream and an AAC audio stream, and integrated loudness near -14 LUFS (the mix target in
tools/film.sh). Exit 0 only when every line passes; each line says what it measured.
Used by the `episode-1-ganryujima` promise in library/promises.json (docs/EPISODE-1.md).
"""
import json
import re
import subprocess
import sys


def opt(name, default):
    return float(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


def main():
    if len(sys.argv) < 2 or sys.argv[1].startswith('--'):
        print(__doc__)
        return 2
    path, lo, hi = sys.argv[1], opt('--min', 45.0), opt('--max', 60.0)
    try:
        info = json.loads(subprocess.check_output(
            ['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,codec_name,width,height:format=duration',
             '-of', 'json', path], stderr=subprocess.STDOUT))
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f'FAIL  cannot read {path}: {e}')
        return 1
    v = next((s for s in info.get('streams', []) if s.get('codec_type') == 'video'), {})
    a = next((s for s in info.get('streams', []) if s.get('codec_type') == 'audio'), {})
    dur = float(info.get('format', {}).get('duration', 0))
    rows = [
        (v.get('width') == 1080 and v.get('height') == 1920, f"size {v.get('width')}x{v.get('height')} (want 1080x1920)"),
        (lo <= dur <= hi, f'length {dur:.1f} s (want {lo:.0f}-{hi:.0f} s)'),
        (v.get('codec_name') == 'h264', f"video {v.get('codec_name')} (want h264)"),
        (a.get('codec_name') == 'aac', f"audio {a.get('codec_name') or 'none'} (want aac)"),
    ]
    if a:
        log = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', path, '-af', 'ebur128', '-f', 'null', '-'],
                             capture_output=True, text=True).stderr
        m = re.findall(r'I:\s+(-?[\d.]+) LUFS', log)
        lufs = float(m[-1]) if m else None
        rows.append((lufs is not None and abs(lufs + 14) <= 1.5, f'loudness {lufs} LUFS (want -14 +/- 1.5)'))
    for ok, line in rows:
        print(('PASS  ' if ok else 'FAIL  ') + line)
    return 0 if all(ok for ok, _ in rows) else 1


if __name__ == '__main__':
    sys.exit(main())
