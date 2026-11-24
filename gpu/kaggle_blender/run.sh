#!/usr/bin/env bash
# Free GPU render farm (AGENTS.md rule 2): Blender Cycles on Kaggle, ~5 s/frame at 720x1280/48 samples on two T4s.
#   bash gpu/kaggle_blender/run.sh pack film/<name>.json [--frames 0-95] [--samples 48] [--res 720x1280]
#                                        [--set output/sets/<x>.blend] [--probe]   → uploads the job as the dataset
#   bash gpu/kaggle_blender/run.sh push [--cpu]   → starts it. ONE push: a push CANCELS the run before it.
#   bash gpu/kaggle_blender/run.sh wait           → polls until the run ends, and explains an early cancel
#   bash gpu/kaggle_blender/run.sh get [dir]      → frames + mp4 + Blender's log (default output/kaggle-render)
# --probe renders the same few frames three times (CPU, CUDA, OPTIX) to find out what a machine will survive.
set -uo pipefail
cd "$(dirname "$0")"; R=$(cd ../.. && pwd)
KERNEL=reviewboost/paper-cinema-blender-render
cmd=${1:-}; shift || true
case "$cmd" in
  pack)
    FILM=${1:?usage: run.sh pack film/<name>.json [--frames a-b] [--samples n] [--res WxH] [--set blend] [--probe]}; shift
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
      printf '{"name": "%s", "script": "blender/film_blender.py", "fps": 24, "cores": "0-3", "stages": [
        {"name": "cpu",   "env": "BLENDER_GPU=0",     "args": [%s]},
        {"name": "cuda",  "env": "BLENDER_GPU=cuda",  "args": [%s]},
        {"name": "optix", "env": "BLENDER_GPU=optix", "args": [%s]}]}\n' "$NAME" "$ARGS" "$ARGS" "$ARGS" > "$S/job.json"
    else
      printf '{"name": "%s", "script": "blender/film_blender.py", "fps": 24, "cores": "0-3", "args": [%s]}\n' "$NAME" "$ARGS" > "$S/job.json"
    fi
    cat "$S/job.json"
    tar czf "$T/up/repo.tgz" --exclude=__pycache__ -C "$T/stage" repo
    echo '{"title": "paper-cinema-blender", "id": "reviewboost/paper-cinema-blender", "licenses": [{"name": "other"}]}' > "$T/up/dataset-metadata.json"
    du -h "$T/up/repo.tgz"
    kaggle datasets version -p "$T/up" -m "$NAME $(date -u +%H:%M)" | tail -2 ;;
  push)
    # --cpu asks for Kaggle's 4 CPU cores instead of the two T4s. Why that matters: once the account's weekly GPU
    # quota is spent, Kaggle still hands out a session WITH both T4s and then cancels it about a minute later
    # (CANCEL_ACKNOWLEDGED, failureMessage null) — which looks exactly like a Blender crash and is not one.
    # A CPU session is not capped that way. Measurements: docs/KAGGLE-RENDER.md
    GPUON=1; [ "${1:-}" = "--cpu" ] && GPUON=0
    python3 -c 'import json,sys; m=json.load(open("kernel-metadata.json")); m["enable_gpu"]=sys.argv[1]=="1"; m.pop("machine_shape",None); m.update({"machine_shape":"NvidiaTeslaT4"} if m["enable_gpu"] else {}); json.dump(m,open("kernel-metadata.json","w"),indent=1); print("accelerator:", "two T4 GPUs" if m["enable_gpu"] else "CPU only (4 cores)")' "$GPUON"
    kaggle kernels push -p . ;;
  status) kaggle kernels status $KERNEL ;;
  wait)
    for i in $(seq 1 1800); do
      s=$(kaggle kernels status $KERNEL 2>&1 | tail -1)
      case "$s" in
        *RUNNING*|*QUEUED*|*rror*) [ $((i % 3)) = 1 ] && echo "[$((i * 20))s] ${s##*status }"; sleep 20 ;;
        *) echo "[$((i * 20))s] ${s##*status }"; break ;;
      esac
    done
    case "$s" in *CANCEL*) if [ "$i" -lt 10 ]; then
      echo
      echo "The run was CANCELLED less than three minutes in. That is almost never Blender: when this account's"
      echo "weekly GPU quota is spent, Kaggle gives the session both T4s and then cancels it after about a minute."
      echo "Wait for the weekly reset, or render on Kaggle's CPUs:  bash gpu/kaggle_blender/run.sh push --cpu"
    fi ;; esac ;;
  get)
    D=${1:-$R/output/kaggle-render}; mkdir -p "$D"
    kaggle kernels output $KERNEL -p "$D" | tail -2
    if [ -f "$D/frames.tgz" ]; then mkdir -p "$D/frames"; tar xzf "$D/frames.tgz" -C "$D/frames"; fi
    ls "$D"; echo "frames: $(ls "$D"/frames/*.png 2>/dev/null | wc -l)" ;;
  *) sed -n 2,9p "$0" ;;
esac
