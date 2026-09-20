#!/bin/bash
# 多视角流水线：等特征齐 → 训练（带 _mv 后缀，不覆盖现用的表）→ 与单视角的表正面交锋 → 对弈测试
cd /Volumes/Lexar/works/flywire.ai
until grep -q VIEWS_DONE results/gomoku/queue_views.log; do sleep 60; done
source "$(conda info --base)/etc/profile.d/conda.sh"; conda activate flygym
set -e
# memguard 自己把命令的输出写进第二个参数指定的日志，并在末尾追加 exit= 与 peak_tree_rss_MB=
scratch/memguard.sh 7000 results/gomoku/train_mv.log python -u gomoku/train_lines.py --steps 300 --l2 1e-4 1e-3 --arms fly_intact fly_shuffled rand_relu --feat-sets "" _v2b1 _v3b1 _v4b1 --tag _mv
echo MV_TRAIN_DONE
node gomoku/compare_tables.js linetable_fly_intact_mv.json linetable_fly_intact.json 6 100 > results/gomoku/compare_mv.log 2>&1
TAG=_mv ARMS=fly_intact,fly_shuffled,rand_relu node gomoku/play_lines.js 20 > results/gomoku/play_lines_mv.log 2>&1
echo MV_ALL_DONE
