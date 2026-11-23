#!/usr/bin/env bash
# Free GPU route for TRELLIS (AGENTS.md rule 2): push the job to Kaggle, then fetch results.
#   bash gpu/kaggle_trellis/run.sh push      → starts the job
#   bash gpu/kaggle_trellis/run.sh status
#   bash gpu/kaggle_trellis/run.sh get       → assets/models/origami_samurai_s*.glb + turntables in output/
cd "$(dirname "$0")"
case "$1" in
  push) kaggle kernels push -p . ;;
  status) kaggle kernels status reviewboost/paper-cinema-trellis ;;
  get) mkdir -p /tmp/kg && kaggle kernels output reviewboost/paper-cinema-trellis -p /tmp/kg && cp /tmp/kg/*.glb ../../assets/models/ && mkdir -p ../../output/models && cp /tmp/kg/*.mp4 /tmp/kg/*.log ../../output/models/ 2>/dev/null; ls /tmp/kg ;;
esac
