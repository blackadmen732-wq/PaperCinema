#!/usr/bin/env bash
# One reproducible regression report for this branch: every test suite, Paper Cinema's mixes against the base branch
# (bit-identical audio with the new features off), and old event files still read. Writes docs/REGRESSION-REPORT.md.
#   bash tools/regression-report.sh [BASE_REF] [SONIC_REF]
#   BASE_REF: Paper Cinema before this work (default origin/claude/relaxed-dirac-m3lm7k): every mix with the new
#   features off must match it. SONIC_REF: the integration branch before Sonic moved into its package (default 824a2e1):
#   the Sonic mix must match it.
set -u
BASE=${1:-origin/claude/relaxed-dirac-m3lm7k}; SREF=${2:-824a2e1}
ROOT=$(git rev-parse --show-toplevel); cd "$ROOT"
OUT=docs/REGRESSION-REPORT.md; T=$(mktemp -d); WT="$T/base"
HEAD_SHA=$(git rev-parse --short HEAD); BASE_SHA=$(git rev-parse --short "$BASE")
ok=1; row() { echo "| $1 | $2 | $3 |" >> "$T/rows"; [ "$3" = PASS ] || ok=0; }
: > "$T/rows"
# 1. test suites
s=$(date +%s); npm test > "$T/npm.log" 2>&1; rc=$?; secs=$(( $(date +%s) - s ))
counts=$(grep -E "^# (pass|fail) |^Ran [0-9]+ tests" "$T/npm.log" | tr '\n' ' ')
row "npm test (Node, new-film, VYRN, Aethern)" "$counts in ${secs}s" "$([ $rc = 0 ] && echo PASS || echo FAIL)"
# 2. same mixes as the base branch (features off), on the same inputs
git worktree add -q --detach "$WT" "$BASE" 2>/dev/null
ln -s "$ROOT/.cache" "$WT/.cache" 2>/dev/null; mkdir -p "$WT/output"
D=$(python3 -c "import json;print(json.load(open('film/dash-test.json'))['duration'])")
ffmpeg -v error -y -f lavfi -i "color=c=black:s=320x568:r=24:d=$D" -c:v libx264 -preset ultrafast "$T/v.mp4"
git worktree add -q --detach "$T/sonicref" "$SREF" 2>/dev/null
ln -s "$ROOT/.cache" "$T/sonicref/.cache" 2>/dev/null; mkdir -p "$T/sonicref/output"
for mode in off sonic; do
  F=""; [ $mode = sonic ] && F=--sonic
  REF=$WT; RNAME="$BASE_SHA"; [ $mode = sonic ] && REF="$T/sonicref" && RNAME=$(git rev-parse --short "$SREF")
  for side in base head; do
    dir=$ROOT; [ $side = base ] && dir=$REF
    (cd "$dir" && node engine/sound.mjs --film film/dash-test.json --events "$ROOT/output/dash-test.events.json" --video "$T/v.mp4" \
      --out "$T/$side-$mode.mp4" --offline $F > "$T/$side-$mode.log" 2>&1)
    ffmpeg -v error -i "$T/$side-$mode.mp4" -map 0:a -f md5 - > "$T/$side-$mode.md5" 2>/dev/null
  done
  b=$(cat "$T/base-$mode.md5"); h=$(cat "$T/head-$mode.md5")
  row "dash-test mix, Sonic $mode: $RNAME vs head" "${b#MD5=} / ${h#MD5=}" "$([ -n "$b" ] && [ "$b" = "$h" ] && echo PASS || echo FAIL)"
done
git worktree remove --force "$WT" 2>/dev/null; git worktree remove --force "$T/sonicref" 2>/dev/null
# 3. version-1 event files still read
python3 - "$T" <<'PY' > "$T/v1.txt"; rc=$?
import json, os, sys
sys.path.insert(0, 'packages/aethern')
from aethern import events
d = sys.argv[1]; p = os.path.join(d, 'v1.jsonl')
open(p, 'w').write(json.dumps({'id': 'sonic.pick.01', 'type': 'sonic.pick', 't': 1.0, 'source': 'sonic', 'conf': 0.6, 'data': {}}) + '\n')
assert events.check([p]) == {}, 'v1 line refused'
m = events.merge([p])
assert m[0]['v'] == 2 and m[0]['media'] == 'file:v1', m
print('v1 line valid; merged as', m[0]['media'])
PY
row "version-1 events still read and upgraded" "$(cat "$T/v1.txt" | tr '\n' ' ')" "$([ $rc = 0 ] && echo PASS || echo FAIL)"
{
  echo "# Regression report"
  echo
  echo "Branch head \`$HEAD_SHA\` against base \`$BASE_SHA\` ($BASE), $(date -u +%Y-%m-%dT%H:%MZ)."
  echo "Reproduce: \`bash tools/regression-report.sh\` (needs Node 18+, Python 3 with numpy and OpenCV, ffmpeg)."
  echo
  echo "| Check | Result | Verdict |"; echo "|---|---|---|"; cat "$T/rows"
  echo
  echo "Overall: $([ $ok = 1 ] && echo PASS || echo FAIL)"
} > "$OUT"
cat "$OUT"; rm -rf "$T"; [ $ok = 1 ]
