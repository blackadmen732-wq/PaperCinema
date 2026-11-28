#!/usr/bin/env bash
# The blind planted-defect benchmark, reproducibly, CPU only, no full frame render.
# make.py plants the defects and keeps the clean film as an answer key the repairer never sees.
# run.py detects and repairs each film from measured evidence alone. score.py is the only reader of the
# answer key and grades detection, metadata-correct, perceptually-correct, preservation, plus a clean
# control and a stylization film. Camera repair renders shot geometry, so this takes several minutes.
#   bash tools/poc/all.sh
set -e; cd "$(git rev-parse --show-toplevel)"
python3 tools/poc/make.py                    # clean film + answer key, defect film, clean control, stylization film
python3 tools/poc/run.py poc-defect          # blind detect + repair
python3 tools/poc/run.py poc-control         # clean control: expect no findings
python3 tools/poc/run.py poc-style           # one real defect + one declared intentional silent beat
python3 tools/poc/score.py                   # independent evaluator (reads the answer key); writes output/poc/score.json
