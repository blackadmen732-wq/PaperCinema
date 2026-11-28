#!/usr/bin/env bash
# The whole planted-defect proof of concept, reproducibly, CPU only, no frame render (~2 min, mostly two camera checks).
#   bash tools/poc/all.sh
set -e; cd "$(git rev-parse --show-toplevel)"
python3 tools/poc/make.py                                   # the clean 30 s film, the defective copy, the answers
cp output/poc-clean.events.json output/poc-defect.events.json
python3 tools/poc/run.py >/dev/null 2>&1 || true            # writes film/poc-fixed.json (D1 needs the camera checks below)
for tag in defect fixed; do
  node tools/camera_check.mjs film/poc-$tag.json --from 13.5 --to 15.0 --step 2 --json >output/poc/cc-$tag.json 2>/dev/null || true
done
python3 tools/poc/run.py                                    # detect, fix, verify, preserve; exit 1 if any check fails
