#!/usr/bin/env bash
# ONE COMMAND: a finished vertical film with sound, rendered in Blender.
#
#   tools/film.sh film/<name>.json [--set <name>] [--gpu] [--from A] [--to B] [--frames a-b]
#                                  [--res WxH] [--samples N] [--full] [--workers N] [--fresh] [--skip-audit]
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
#
# THE LOCAL RENDER (no --gpu) is the one that always works, so it is built to be lived with:
# --from A --to B   render only that stretch of frames (same thing as --frames A-B; either end may be left out)
# --workers N       N Blender processes side by side, each on its own core (default: one per core, max 4), all
#                   niced; four one-thread processes beat one four-thread process by about 2.5x on this machine
# --fresh           re-render frames that are already in output/blender/<name>/ (by default they are KEPT and the
#                   render resumes, so a stopped or part-finished render costs nothing to pick up again)
# --res / --samples the picture. Local default is a preview on this four-core machine: 360x640 at 16 samples
#                   (~4 s/frame over the four workers; 432x768 at 24 is ~3x that, 540x960 at 32 about 13 s/frame
#                   and 720x1280 at 48 about 30 s/frame — and all of it doubles when another agent is busy here).
# --full            the delivery picture instead: 720x1280 at 48 samples (what --gpu uses)
set -uo pipefail
R=$(cd "$(dirname "$0")/.." && pwd); cd "$R"
B=${BLENDER:-/opt/blender-dl/blender-4.5.16-linux-x64/blender}
FILM=${1:-}; shift || true
die() { echo; echo "FILM FAILED — $*" >&2; exit 1; }
step() { echo; echo "=== $* ==="; }
[ -n "$FILM" ] || die "usage: tools/film.sh film/<name>.json [--set <name>] [--gpu] [--frames a-b] [--res WxH] [--samples N]"
[ -f "$FILM" ] || die "no such film file: $FILM"
NAME=$(basename "$FILM" .json)

SET= GPU=0 FRAMES= RES= SAMPLES= AUDIT=1 FROM= TO= WORKERS= FRESH=0 FULL=0
while [ $# -gt 0 ]; do
  case "$1" in
    --set) SET=${2:?--set needs a set name}; shift 2 ;;
    --gpu) GPU=1; shift ;;
    --frames) FRAMES=${2:?--frames needs a-b}; shift 2 ;;
    --from) FROM=${2:?--from needs a frame number}; shift 2 ;;
    --to) TO=${2:?--to needs a frame number}; shift 2 ;;
    --res) RES=${2:?}; shift 2 ;;
    --samples) SAMPLES=${2:?}; shift 2 ;;
    --workers) WORKERS=${2:?--workers needs a number}; shift 2 ;;
    --fresh) FRESH=1; shift ;;
    --full) FULL=1; shift ;;
    --skip-audit) AUDIT=0; shift ;;
    *) die "unknown option: $1" ;;
  esac
done
# the picture: the GPU renders at delivery size, this machine at preview size unless --full or --res/--samples say otherwise
if [ "$FULL" = 1 ] || [ "$GPU" = 1 ]; then RES=${RES:-720x1280}; SAMPLES=${SAMPLES:-48}
else RES=${RES:-360x640}; SAMPLES=${SAMPLES:-16}; fi
case "$RES" in *x*) ;; *) die "--res wants WxH, for example 540x960 (got '$RES')" ;; esac
[ -z "$WORKERS" ] || case "$WORKERS" in *[!0-9]*|0) die "--workers wants a number of processes (got '$WORKERS')" ;; esac
for t in node ffmpeg ffprobe python3; do command -v $t >/dev/null || die "$t is not installed (needed by the pipeline)"; done
[ "$GPU" = 1 ] || [ -x "$B" ] || die "no Blender at $B — set BLENDER=/path/to/blender, or render on the free GPU with --gpu"
[ "$GPU" = 0 ] || command -v kaggle >/dev/null || die "the kaggle CLI is not installed, so --gpu cannot send the job"
DUR=$(python3 -c "import json;print(json.load(open('$FILM'))['duration'])") || die "the film file has no duration"
FPS=$(python3 -c "import json;print(json.load(open('$FILM')).get('fps',24))")
NF=$(python3 -c "print(int(round($DUR*$FPS)))")
echo "FILM $NAME · ${DUR}s · $FPS fps · $NF frames · $RES · $SAMPLES samples · $([ "$GPU" = 1 ] && echo 'Kaggle T4 GPU' || echo 'this machine')${SET:+ · set $SET}"
if [ -n "$FRAMES" ]; then
  [ -z "$FROM$TO" ] || die "use --frames a-b or --from/--to, not both"
  case "$FRAMES" in *-*) ;; *) die "--frames wants a-b, for example 24-47 (got '$FRAMES')" ;; esac
else
  FRAMES="${FROM:-0}-${TO:-$((NF - 1))}"
fi
FA=${FRAMES%%-*}; FB=${FRAMES##*-}
case "$FA$FB" in *[!0-9]*) die "--frames/--from/--to want frame numbers (got '$FRAMES')" ;; esac
[ "$FB" -lt "$NF" ] || die "frame $FB is past the end of the film: it has $NF frames (0-$((NF - 1)))"
[ "$FA" -le "$FB" ] || die "the frame range runs backwards: $FRAMES"
FRAMES="$FA-$FB"

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
  [ "$FRESH" = 0 ] || rm -f "$FR"/f*.png
  CORES=$(nproc)
  W=${WORKERS:-$((CORES > 4 ? 4 : CORES))}
  # The work left to do: every frame of the range that has no PNG yet (so a stopped render just carries on),
  # split into contiguous blocks of about the same size — one Blender process per block, one core each.
  # Line 1 of the plan is how many frames are missing; then one line per worker: the ranges it renders.
  PLAN=$(python3 "$R/tools/render_plan.py" "$FR" "$FA" "$FB" "$W") \
    || die "step 5 render: could not work out which frames are missing from $FR."
  TODO=$(echo "$PLAN" | head -1)
  HAVE=$((FB - FA + 1 - TODO))
  if [ "$TODO" = 0 ]; then
    echo "all $((FB - FA + 1)) frames are already in $FR — nothing to render (--fresh re-renders them)"
  else
    NW=$(echo "$PLAN" | tail -n +2 | grep -c .)
    T=$((CORES / NW)); [ "$T" -ge 1 ] || T=1
    echo "$TODO frame(s) to render, $HAVE already there · $NW process(es) x $T thread(s), niced"
    i=0; PIDS=; LOGS=
    for runs in $(echo "$PLAN" | tail -n +2 | tr ' ' ','); do
      i=$((i + 1)); LOG="output/$NAME-render-w$i.log"; LOGS="$LOGS $LOG"
      ( for r in $(echo "$runs" | tr ',' ' '); do
          nice -n 10 "$B" -b -t "$T" -P blender/film_blender.py -- --film "$FILM" --out "$FR/" --frames "$r" \
            --res "$RES" --samples "$SAMPLES" "${SETARG[@]+"${SETARG[@]}"}" || exit 1
        done ) > "$LOG" 2>&1 &
      PIDS="$PIDS $!"
      echo "  worker $i: frames $(echo "$runs" | tr ',' ' ') -> $LOG"
    done
    BAD=0
    for pid in $PIDS; do wait "$pid" || BAD=$((BAD + 1)); done
    if [ "$BAD" -gt 0 ]; then
      for l in $LOGS; do echo; echo "--- tail of $l"; tail -25 "$l"; done
      die "step 5 render: $BAD of $i Blender process(es) failed (tails above; full logs:$LOGS)."
    fi
    grep -h "Cycles device:" $LOGS | head -1
  fi
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
# the two numbers the mix is judged by (docs/STUDIO-STANDARD.md): integrated loudness and true peak
eb = subprocess.run(['bash', '-c', f'ffmpeg -hide_banner -nostats -i "{f}" -af ebur128=peak=true -f null - 2>&1'],
                    capture_output=True, text=True).stdout
lufs = re.search(r'Integrated loudness:\s+I:\s+(-?[\d.]+)', eb)
tp = re.search(r'Peak:\s+(-?[\d.]+|-inf) dBFS', eb.split('True peak:')[-1]) if 'True peak:' in eb else None
print(f'FILM READY  {f}')
print(f'  {float(p["format"]["duration"]):.2f} s · {v["width"]}x{v["height"]} · {v["r_frame_rate"]} fps · '
      f'{int(p["format"]["size"]) / 1e6:.1f} MB · {v["codec_name"]}'
      + (f' + {a["codec_name"]} {a["sample_rate"]} Hz' if a else '  (NO AUDIO TRACK)'))
if peak: print(f'  audio peak {peak.group(1)} dBFS · mean {mean.group(1)} dBFS'
                + (f' · {lufs.group(1)} LUFS integrated' if lufs else '')
                + (f' · true peak {tp.group(1)} dBFS' if tp else ''))
if lufs and abs(float(lufs.group(1)) + 14) > 2:
    print(f'  WARNING: {lufs.group(1)} LUFS is outside the -14 ± 2 target')
print(f'  frames output/blender/{name}/ · silent cut output/{name}.mp4 · audit output/{name}.audit.md')
PY
echo
echo "Done: output/$NAME-final.mp4"
