#!/usr/bin/env bash
# Free GPU render farm (AGENTS.md rule 2): Blender Cycles on Kaggle's T4.
#   bash gpu/kaggle_blender/run.sh pack     → upload blender/ + assets/models + library/ as the private dataset
#   bash gpu/kaggle_blender/run.sh push     → start the render job (edit JOB in render_job.py first)
#   bash gpu/kaggle_blender/run.sh status
#   bash gpu/kaggle_blender/run.sh get      → output/kaggle-render/ (shot.mp4, log)
set -e
cd "$(dirname "$0")"
R=../..
case "$1" in
  pack) T=$(mktemp -d); mkdir -p $T/stage/repo/assets $T/stage/repo/library $T/up
        cp -r $R/blender $T/stage/repo/; cp -r $R/assets/models $T/stage/repo/assets/
        cp -r "$R"/library/{sets,poses.json,moves.json,character-models.json,character-recipes,paper-materials} "$T/stage/repo/library/"
        tar czf $T/up/repo.tgz --exclude=__pycache__ -C $T/stage repo
        echo '{"title": "paper-cinema-blender", "id": "reviewboost/paper-cinema-blender", "licenses": [{"name": "other"}]}' > $T/up/dataset-metadata.json
        kaggle datasets version -p $T/up -m "update" ;;
  push) kaggle kernels push -p . ;;
  status) kaggle kernels status reviewboost/paper-cinema-blender-render ;;
  get) mkdir -p $R/output/kaggle-render && kaggle kernels output reviewboost/paper-cinema-blender-render -p $R/output/kaggle-render && ls $R/output/kaggle-render ;;
esac
