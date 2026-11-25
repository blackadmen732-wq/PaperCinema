#!/usr/bin/env bash
# SHOT SHEET: a few frames from the REAL render path, in the real set, on one page.
#
#   bash tools/shotsheet.sh film/<name>.json [--set bamboo-forest] [--n 6] [--res 360x640] [--samples 24]
#
# Look at this before committing an hour to a render.
#
# Why it exists. Model turnarounds on a grey background hid every bug that mattered on 25 Nov: a
# studio lamp standing in shot (invisible in an empty studio, because nothing is ever in shot), a
# cast lit for the grove instead of for the shot, and a key light parented to the actor's root so it
# orbited with them - a flashlight, not a sun. None of the three can exist in a turnaround. All
# three are obvious in one frame of a character standing in a lit world and moving through it.
#
# So the review loop is frames from a real shot in a real set. This is that loop, cheap: n frames
# spread across the film, rendered the way the film renders, tiled into one picture.
set -eu

FILM=${1:?usage: bash tools/shotsheet.sh film/<name>.json [--set <name>] [--n 6] [--res WxH] [--samples N]}
shift
NAME=$(basename "$FILM" .json)
B=${BLENDER:-/opt/blender-dl/blender-4.5.16-linux-x64/blender}
SET=; N=6; RES=360x640; SAMPLES=24
while [ $# -gt 0 ]; do
  case $1 in
    --set) SET=$2; shift 2;;
    --n) N=$2; shift 2;;
    --res) RES=$2; shift 2;;
    --samples) SAMPLES=$2; shift 2;;
    *) echo "unknown option: $1" >&2; exit 2;;
  esac
done

TL="output/$NAME.timeline.json"
[ -s "$TL" ] || { echo "no $TL — run: node tools/timeline.mjs $FILM" >&2; exit 1; }
TOTAL=$(python3 -c "import json;print(len(json.load(open('$TL'))['frames']))")

SETARG=()
if [ -n "$SET" ]; then
  BLEND="output/sets/$SET.blend"
  [ -f "$BLEND" ] || { echo "no $BLEND — build it first (docs/SETS.md), or drop --set" >&2; exit 1; }
  SETARG=(--set "$BLEND")
fi

OUT="output/sheet/$NAME"
rm -rf "$OUT"; mkdir -p "$OUT"
echo "$NAME · $TOTAL frames · $N samples across it · $RES · ${SET:-no set}"

# Evenly spaced, skipping the very first and last frame: both are usually a fade and tell you nothing.
FRAMES=$(python3 -c "
n,t=$N,$TOTAL
print(' '.join(str(round((i+1)*(t-1)/(n+1))) for i in range(n)))")

for f in $FRAMES; do
  printf '  frame %s… ' "$f"
  nice -n 10 "$B" -b -t 4 -P blender/film_modular.py -- --film "$NAME" --frames "$f-$f" \
    --res "$RES" --samples "$SAMPLES" --out "$OUT/" "${SETARG[@]+"${SETARG[@]}"}" >"$OUT/blender.log" 2>&1 \
    || { echo "FAILED — tail of $OUT/blender.log:"; tail -20 "$OUT/blender.log"; exit 1; }
  echo 'ok'
done

SHEET="output/$NAME.shots.png"
montage "$OUT"/f*.png -tile "$N"x1 -geometry +4+4 -background '#111' -label '%f' "$SHEET"
echo
echo "wrote $SHEET — LOOK AT IT before rendering the film."
echo "  frames: $FRAMES"
