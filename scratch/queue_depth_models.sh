#!/bin/bash
# 「推理 N 步」的模型：等主训练结束（两个训练进程同时跑内存不够）→ 训练 7 个读出层 → 实战评测
cd /Volumes/Lexar/works/flywire.ai
until grep -q "TRAIN_DONE\|TRAIN_FAILED" results/gomoku/queue_mv_final.log 2>/dev/null; do sleep 30; done
source "$(conda info --base)/etc/profile.d/conda.sh"; conda activate flygym
scratch/memguard.sh 6500 results/gomoku/train_depth.log python -u gomoku/train_lines.py --labels 1 2 3 4 5 6 8 --steps 300 --l2 1e-4 --feat-sets "" _v2b1 _v3b1 _v4b1
grep -q "exit=0" results/gomoku/train_depth.log || { echo DEPTH_TRAIN_FAILED; exit 1; }
node gomoku/depth_models.js > results/gomoku/depth_models.log 2>&1
echo DEPTH_DONE
