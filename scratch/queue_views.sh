#!/bin/bash
# 多视角特征：视角 2–4 × 9 个种子 × 两个臂。每批 6 个并行（每个 ~100 MB，不是全脑仿真）。已有的文件跳过。
cd /Volumes/Lexar/works/flywire.ai
jobs_list=()
for arm in intact shuffled; do for view in 2 3 4; do for seed in 777 778 779 780 781 782 783 784 785; do
  [ -f results/gomoku/linefeat_${arm}_v${view}b1_s${seed}.bin ] || jobs_list+=("$arm $view $seed")
done; done; done
echo "待提取 ${#jobs_list[@]} 份"
i=0
for j in "${jobs_list[@]}"; do
  set -- $j
  VIEW=$2 SEED=$3 node gomoku/line_features.js $1 160 300 1 > results/gomoku/lf_$1_v$2_s$3.log 2>&1 &
  i=$((i+1)); if [ $((i % 6)) -eq 0 ]; then wait; echo "完成 $i / ${#jobs_list[@]}  $(date +%H:%M)"; fi
done
wait; echo VIEWS_DONE
