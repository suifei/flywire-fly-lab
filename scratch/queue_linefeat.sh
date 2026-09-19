#!/bin/bash
# 一条链，顺序跑，绝不并行（CLAUDE.md：一次只跑一个仿真）
cd /Volumes/Lexar/works/flywire.ai
for arm in intact shuffled; do for seed in 777 778 779; do
  SEED=$seed node gomoku/line_features.js $arm 160 60 2 || { echo "FAILED $arm $seed"; exit 1; }
done; done
echo ALL_DONE
