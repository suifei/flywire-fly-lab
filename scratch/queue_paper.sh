#!/bin/bash
# 一条链，严格串行：等 ST4 官方名单版跑完 → Fig 3 剂量网格（共用同一编译目录）→ Fig 2A 充分性 → Fig 5G
cd /Volumes/Lexar/works/flywire.ai
source "$(conda info --base)/etc/profile.d/conda.sh"; conda activate brain-fly-cpu
until grep -q CHAIN_DONE results/screen/taste/notebook/analyze.log 2>/dev/null; do sleep 20; done
echo "[chain] ST4 官方名单版完成 $(date)"
scratch/memguard.sh 6500 results/screen/taste/grid_run.log python -u screen/taste_grid.py run
python screen/taste_grid.py analyze > results/screen/taste/grid_analyze.log 2>&1
echo "[chain] Fig 3 网格完成 $(date)"
scratch/memguard.sh 6500 results/screen/sufficiency_run.log python -u screen/sufficiency.py run
python screen/sufficiency.py analyze > results/screen/sufficiency_analyze.log 2>&1
echo "[chain] Fig 2A 充分性完成 $(date)"
scratch/memguard.sh 6500 results/screen/jon_ce_f_run.log python -u screen/jon_ce_f.py run
python screen/jon_ce_f.py analyze > results/screen/jon_ce_f_analyze.log 2>&1
echo "[chain] Fig 5G 完成 $(date)"
echo QUEUE_DONE
