#!/bin/bash
# 五子棋 v2 · 多视角（4 个视角）的最终流水线。单视角的结果已留档为 *_1view.json。
cd /Volumes/Lexar/works/flywire.ai
source "$(conda info --base)/etc/profile.d/conda.sh"; conda activate flygym
scratch/memguard.sh 6500 results/gomoku/train_final.log python -u gomoku/train_lines.py --steps 300 --l2 1e-4 1e-3 --feat-sets "" _v2b1 _v3b1 _v4b1 --cap-shuffled
grep -q "exit=0" results/gomoku/train_final.log || { echo TRAIN_FAILED; exit 1; }
echo TRAIN_DONE
node gomoku/selfplay_rl.js 80 48 0.05 0.5 > results/gomoku/rl.log 2>&1
RL_TAG=_small node gomoku/selfplay_rl.js 120 96 0.01 0.5 > results/gomoku/rl_small.log 2>&1 &
node gomoku/play_lines.js 20 > results/gomoku/play_lines.log 2>&1
wait
node gomoku/side_experiments.js width > results/gomoku/side_width.log 2>&1
node gomoku/side_experiments.js vcf > results/gomoku/side_vcf.log 2>&1
node gomoku/side_experiments.js timing > results/gomoku/side_timing.log 2>&1
echo ALL_DONE
