#!/usr/bin/env bash
# Free GPU render farm (AGENTS.md rule 2): Blender Cycles on Kaggle's two T4s, ~14 s/frame at 720x1280/48 samples.
#   bash gpu/kaggle_blender/run.sh pack film/dash-test.json [--frames 0-95] [--samples 48] [--res 720x1280] [--set output/sets/dojo.blend]
#                                        → writes job.json and uploads the private dataset
#   bash gpu/kaggle_blender/run.sh push  → starts the job.  ONE push only: a push CANCELS the run before it.
#   bash gpu/kaggle_blender/run.sh wait  → polls status until it is not running (that is the whole wait)
#   bash gpu/kaggle_blender/run.sh get [dir]  → frames + mp4 + blender.log into dir (default output/kaggle-render)
set -euo pipefail
cd "$(dirname "$0")"; R=$(cd ../.. && pwd)
KERNEL=reviewboost/paper-cinema-blender-render
cmd=${1:-}; shift || true
case "$cmd" in
  pack)
    FILM=${1:?usage: run.sh pack film/<name>.json [--frames a-b] [--samples n] [--res WxH] [--set blend]}; shift
    NAME=$(basename "$FILM" .json)
    [ -f "$R/$FILM" ] || { echo "no such film: $FILM"; exit 1; }
    [ -f "$R/output/$NAME.motion.json" ] || { echo "missing $R/output/$NAME.motion.json — run: node tools/export_motion.mjs $FILM"; exit 1; }
    PROBE=0; case " $* " in *" --probe "*) PROBE=1 ;; esac
    T=$(mktemp -d); S=$T/stage/repo; mkdir -p "$S/assets" "$S/film" "$S/output" "$T/up"
    cp -r "$R/blender" "$S/"; cp -r "$R/assets/models" "$S/assets/"; cp -r "$R/library" "$S/"
    cp "$R/$FILM" "$S/film/"; cp "$R/output/$NAME.motion.json" "$S/output/"
    ARGS="\"--film\", \"film/$NAME.json\""
    while [ $# -gt 0 ]; do
      case "$1" in
        --set) B=$2; shift 2; mkdir -p "$S/$(dirname "$B")"; cp "$R/$B" "$S/$B"; ARGS="$ARGS, \"--set\", \"$B\"" ;;
        --probe) shift ;;
        --*) ARGS="$ARGS, \"$1\", \"$2\""; shift 2 ;;
        *) echo "unexpected argument: $1"; exit 1 ;;
      esac
    done
    if [ "$PROBE" = 1 ]; then
      # one run, three short renders: which Cycles backend survives on Kaggle (OPTIX took the session down)
      printf '{"name": "%s", "script": "blender/film_blender.py", "fps": 24, "cores": "0,1", "stages": [
        {"name": "cpu",   "env": "BLENDER_GPU=0",     "args": [%s]},
        {"name": "cuda",  "env": "BLENDER_GPU=cuda",  "args": [%s]},
        {"name": "optix", "env": "BLENDER_GPU=optix", "args": [%s]}]}\n' "$NAME" "$ARGS" "$ARGS" "$ARGS" > "$S/job.json"
    else
      printf '{"name": "%s", "script": "blender/film_blender.py", "fps": 24, "cores": "0,1", "args": [%s]}\n' "$NAME" "$ARGS" > "$S/job.json"
    fi
    cat "$S/job.json"
    tar czf "$T/up/repo.tgz" --exclude=__pycache__ -C "$T/stage" repo
    echo '{"title": "paper-cinema-blender", "id": "reviewboost/paper-cinema-blender", "licenses": [{"name": "other"}]}' > "$T/up/dataset-metadata.json"
    du -h "$T/up/repo.tgz"
    kaggle datasets version -p "$T/up" -m "$NAME $(date -u +%H:%M)" ;;
  push)   kaggle kernels push -p . ;;
  status) kaggle kernels status $KERNEL ;;
  wait)
    for i in $(seq 1 90); do
      s=$(kaggle kernels status $KERNEL 2>&1 | tail -1)
      echo "[$((i * 20))s] $s"
      case "$s" in *RUNNING*|*QUEUED*|*rror*) sleep 20 ;; *) break ;; esac
    done ;;
  get)
    D=${1:-$R/output/kaggle-render}; mkdir -p "$D"
    kaggle kernels output $KERNEL -p "$D"
    [ -f "$D/frames.tgz" ] && { mkdir -p "$D/frames"; tar xzf "$D/frames.tgz" -C "$D/frames"; }
    ls -la "$D"; ls "$D/frames" 2>/dev/null | wc -l ;;
  *) sed -n 2,9p "$0" ;;
esac
