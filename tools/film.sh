#!/usr/bin/env bash
# ONE COMMAND: a finished vertical film with sound, rendered in Blender.
#
#   tools/film.sh film/<name>.json [--set <name>] [--gpu] [--frames a-b] [--res WxH] [--samples N] [--skip-audit]
#
# The chain (every step fails loudly and stops):
#   1 validate   node engine/validate.mjs            the film file itself
#   2 motion     node tools/export_motion.mjs        the engine's real joints and camera → output/<name>.motion.json
#   3 events     node engine/render.mjs --still 0    blade contacts, hit-stops, auto sound cues → output/<name>.events.json
#   4 audit      node tools/audit.mjs                studio QA, must pass (no CRITICAL finding)
#   5 render     blender -P blender/film_blender.py   → output/blender/<name>/f####.png   (--gpu: on Kaggle's free T4s)
#   6 encode     ffmpeg                              → output/<name>.mp4 (silent)
#   7 voice      python3 tools/voice.py               only when the film has a "voice" list
#   8 sound      node engine/sound.mjs               auto clash/whoosh cues + Earshot + voice, mixed and muxed
#                                                    → output/<name>-final.mp4
#   9 report     duration, size, frame count, audio levels
#
# --set <name>   stage the film inside a Blender set: output/sets/<name>.blend, built from library/sets/<name>.json
#                when it is not there yet (castle-courtyard, dojo-interior, bamboo-forest, ganryujima-beach, …)
# --gpu          pack the job, send it to Kaggle (gpu/kaggle_blender/run.sh), wait, fetch the frames
set -uo pipefail
R=$(cd "$(dirname "$0")/.." && pwd); cd "$R"
B=${BLENDER:-/opt/blender-dl/blender-4.5.16-linux-x64/blender}
FILM=${1:-}; shift || true
die() { echo; echo "FILM FAILED — $*" >&2; exit 1; }
step() { echo; echo "=== $* ==="; }
[ -n "$FILM" ] || die "usage: tools/film.sh film/<name>.json [--set <name>] [--gpu] [--frames a-b] [--res WxH] [--samples N]"
[ -f "$FILM" ] || die "no such film file: $FILM"
NAME=$(basename "$FILM" .json)

SET= GPU=0 FRAMES= RES=720x1280 SAMPLES=48 AUDIT=1
while [ $# -gt 0 ]; do
  case "$1" in
    --set) SET=${2:?--set needs a set name}; shift 2 ;;
    --gpu) GPU=1; shift ;;
    --frames) FRAMES=${2:?--frames needs a-b}; shift 2 ;;
    --res) RES=${2:?}; shift 2 ;;
    --samples) SAMPLES=${2:?}; shift 2 ;;
    --skip-audit) AUDIT=0; shift ;;
    *) die "unknown option: $1" ;;
  esac
done
for t in node ffmpeg ffprobe python3; do command -v $t >/dev/null || die "$t is not installed (needed by the pipeline)"; done
[ "$GPU" = 1 ] || [ -x "$B" ] || die "no Blender at $B — set BLENDER=/path/to/blender, or render on the free GPU with --gpu"
[ "$GPU" = 0 ] || command -v kaggle >/dev/null || die "the kaggle CLI is not installed, so --gpu cannot send the job"
DUR=$(python3 -c "import json;print(json.load(open('$FILM'))['duration'])") || die "the film file has no duration"
FPS=$(python3 -c "import json;print(json.load(open('$FILM')).get('fps',24))")
NF=$(python3 -c "print(int(round($DUR*$FPS)))")
echo "FILM $NAME · ${DUR}s · $FPS fps · $NF frames · $RES · $SAMPLES samples · $([ "$GPU" = 1 ] && echo 'Kaggle T4 GPU' || echo 'this machine')${SET:+ · set $SET}"
[ -n "$FRAMES" ] || FRAMES="0-$((NF - 1))"

step "1/9 validate"
node engine/validate.mjs "$FILM" || die "step 1 validate: the film file has errors above. Fix every ✗ and run again."

step "2/9 export motion"
node tools/export_motion.mjs "$FILM" || die "step 2 export motion: the engine could not play this film (see the error above)."
[ -s "output/$NAME.motion.json" ] || die "step 2 export motion: output/$NAME.motion.json was not written."

step "3/9 events (auto sound cues)"
node engine/render.mjs --film "$FILM" --still 0 || die "step 3 events: the film's page would not load in headless Chromium (needed for the auto clash/whoosh cues)."
[ -s "output/$NAME.events.json" ] || die "step 3 events: output/$NAME.events.json was not written — the page published no window.EVENTS."

if [ "$AUDIT" = 1 ]; then
  step "4/9 studio audit (must pass)"
  node tools/audit.mjs "$FILM" || die "step 4 audit: CRITICAL findings in output/$NAME.audit.md. Fix them (or waive them in the film's \"audit.waive\") and run again."
else
  step "4/9 studio audit — SKIPPED (--skip-audit)"
fi

# the set, if one was asked for
SETARG=()
if [ -n "$SET" ]; then
  BLEND="output/sets/$SET.blend"
  if [ ! -f "$BLEND" ]; then
    [ -f "library/sets/$SET.json" ] || die "unknown set '$SET': no output/sets/$SET.blend and no library/sets/$SET.json (have: $(cd library/sets && ls *.json | sed 's/.json//' | tr '\n' ' '))"
    step "4b/9 build the set $SET"
    [ -x "$B" ] || die "the set $SET is not built yet and there is no Blender at $B to build it with"
    nice -n 10 "$B" -b -t 2 -P blender/sets/build_set.py -- --set "$SET" --out "$BLEND" || die "step 4b: building the set $SET failed."
  fi
  [ -f "$BLEND" ] || die "step 4b: $BLEND was not written."
  SETARG=(--set "$BLEND")
fi

FR=output/blender/$NAME
step "5/9 render in Blender ($FRAMES)"
if [ "$GPU" = 1 ]; then
  bash gpu/kaggle_blender/run.sh pack "$FILM" --frames "$FRAMES" --samples "$SAMPLES" --res "$RES" ${SET:+--set output/sets/$SET.blend} \
    || die "step 5 GPU: packing the job as a Kaggle dataset failed (is ~/.kaggle/kaggle.json in place?)."
  bash gpu/kaggle_blender/run.sh push || die "step 5 GPU: kaggle kernels push failed."
  bash gpu/kaggle_blender/run.sh wait
  S=$(kaggle kernels status reviewboost/paper-cinema-blender-render 2>&1 | tail -1)
  case "$S" in *COMPLETE*) ;; *) die "step 5 GPU: the Kaggle run ended as: $S. Logs: bash gpu/kaggle_blender/run.sh get" ;; esac
  rm -rf "$FR"; mkdir -p "$FR"
  bash gpu/kaggle_blender/run.sh get "output/kaggle-render/$NAME" || die "step 5 GPU: could not fetch the kernel output."
  cp "output/kaggle-render/$NAME/frames/"*.png "$FR/" 2>/dev/null || die "step 5 GPU: the run returned no frames (see output/kaggle-render/$NAME/blender.log)."
else
  mkdir -p "$FR"
  nice -n 10 "$B" -b -t 2 -P blender/film_blender.py -- --film "$FILM" --out "$FR/" --frames "$FRAMES" \
    --res "$RES" --samples "$SAMPLES" "${SETARG[@]+"${SETARG[@]}"}" || die "step 5 render: Blender failed (see the traceback above)."
fi
N=$(ls "$FR"/f*.png 2>/dev/null | wc -l)
[ "$N" -gt 0 ] || die "step 5 render: no frames in $FR."
WANT=$(python3 -c "a,b='$FRAMES'.split('-');print(int(b)-int(a)+1)")
[ "$N" = "$WANT" ] && echo "$N/$WANT frames" || echo "WARNING: $N of $WANT frames rendered — the film will be short"

step "6/9 encode"
FIRST=$(basename "$(ls "$FR"/f*.png | head -1)" .png); FIRST=${FIRST#f}
ffmpeg -loglevel error -y -framerate "$FPS" -start_number "$((10#$FIRST))" -i "$FR/f%04d.png" \
  -c:v libx264 -preset medium -crf 17 -pix_fmt yuv420p -movflags +faststart "output/$NAME.mp4" \
  || die "step 6 encode: ffmpeg could not build output/$NAME.mp4 from $FR."

if python3 -c "import json,sys;sys.exit(0 if json.load(open('$FILM')).get('voice') else 1)"; then
  step "7/9 voice"
  nice -n 10 python3 tools/voice.py "$FILM" || die "step 7 voice: tools/voice.py failed (see above)."
else
  step "7/9 voice — none in this film"
fi

step "8/9 sound"
node engine/sound.mjs --film "$FILM" --video "output/$NAME.mp4" --out "output/$NAME-final.mp4" \
  || die "step 8 sound: engine/sound.mjs failed (see above)."
[ -s "output/$NAME-final.mp4" ] || die "step 8 sound: output/$NAME-final.mp4 was not written."

step "9/9 report"
python3 - "$NAME" <<'PY'
import json, re, subprocess, sys
name = sys.argv[1]
f = f'output/{name}-final.mp4'
p = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', f],
                              capture_output=True, text=True).stdout)
v = next(s for s in p['streams'] if s['codec_type'] == 'video')
a = next((s for s in p['streams'] if s['codec_type'] == 'audio'), None)
txt = subprocess.run(['bash', '-c', f'ffmpeg -hide_banner -i "{f}" -af volumedetect -f null - 2>&1'],
                     capture_output=True, text=True).stdout
peak = re.search(r'max_volume: (-?[\d.]+)', txt); mean = re.search(r'mean_volume: (-?[\d.]+)', txt)
print(f'FILM READY  {f}')
print(f'  {float(p["format"]["duration"]):.2f} s · {v["width"]}x{v["height"]} · {v["r_frame_rate"]} fps · '
      f'{int(p["format"]["size"]) / 1e6:.1f} MB · {v["codec_name"]}'
      + (f' + {a["codec_name"]} {a["sample_rate"]} Hz' if a else '  (NO AUDIO TRACK)'))
if peak: print(f'  audio peak {peak.group(1)} dBFS · mean {mean.group(1)} dBFS')
print(f'  frames output/blender/{name}/ · silent cut output/{name}.mp4 · audit output/{name}.audit.md')
PY
echo
echo "Done: output/$NAME-final.mp4"
