#!/usr/bin/env bash
# TRELLIS.2-4B on Kaggle's free GPU (AGENTS.md rule 2). Guide: docs/TOOLS-EVALUATED.md.
#   bash gpu/kaggle_trellis2/run.sh push     → start the job (ONE push: a push cancels the run before it)
#   bash gpu/kaggle_trellis2/run.sh status
#   bash gpu/kaggle_trellis2/run.sh log      → the kernel's own log
#   bash gpu/kaggle_trellis2/run.sh get      → assets/models/origami_samurai_t2_s*.glb
cd "$(dirname "$0")"
case "$1" in
  push) kaggle kernels push -p . ;;
  status) kaggle kernels status reviewboost/paper-cinema-trellis2 ;;
  log) mkdir -p /tmp/kg2 && kaggle kernels output reviewboost/paper-cinema-trellis2 -p /tmp/kg2 >/dev/null 2>&1; cat /tmp/kg2/*.log 2>/dev/null ;;
  get) mkdir -p /tmp/kg2 && kaggle kernels output reviewboost/paper-cinema-trellis2 -p /tmp/kg2 && cp /tmp/kg2/*.glb ../../assets/models/ 2>/dev/null; ls -la /tmp/kg2 ;;
esac
