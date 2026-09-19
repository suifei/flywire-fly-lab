#!/bin/bash
# 五子棋 v2 最终流水线：一条链顺序跑（训练 1.6 GB，其余都很轻）
cd /Volumes/Lexar/works/flywire.ai
source "$(conda info --base)/etc/profile.d/conda.sh"; conda activate flygym
set -e
python -u gomoku/train_lines.py --steps 300 --l2 1e-4 1e-3 > results/gomoku/train_final.log 2>&1
echo TRAIN_DONE
node gomoku/selfplay_rl.js 80 48 0.05 0.5 > results/gomoku/rl.log 2>&1
RL_TAG=_small node gomoku/selfplay_rl.js 120 96 0.01 0.5 > results/gomoku/rl_small.log 2>&1 &
node gomoku/play_lines.js 20 > results/gomoku/play_lines.log 2>&1
wait
node gomoku/side_experiments.js width > results/gomoku/side_width.log 2>&1
node gomoku/side_experiments.js vcf > results/gomoku/side_vcf.log 2>&1
node gomoku/side_experiments.js timing > results/gomoku/side_timing.log 2>&1
echo ALL_DONE
