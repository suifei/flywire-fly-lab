#!/bin/bash
# 全突触 MANC（作者较新的 W_20260522_allSynapses）上重跑三项，严格串行；与步态相关的在前，电突触最后
cd /Volumes/Lexar/works/flywire.ai
export MANC_DATASET=all
E=~/miniconda3/envs
step() { echo "[$(date +%H:%M:%S)] $*"; }

step "1 全腹神经索条件"
scratch/memguard.sh 6000 logs/manc_all_run.log $E/vnc-sim/bin/python -u vnc/manc_full.py run
grep "振荡副本\|exit=" logs/manc_all_run.log

step "2 分析"
scratch/memguard.sh 4000 logs/manc_all_analysis.log $E/vnc-sim/bin/python -u vnc/analyze_manc_full.py
grep -v Warn logs/manc_all_analysis.log | grep -v "^$"

step "3 6 条腿"
scratch/memguard.sh 4000 logs/manc_all_legs.log $E/fba/bin/python -u vnc/drive_legs_manc.py
grep -v Warn logs/manc_all_legs.log | tail -30

step "4 导出闭环参数"
scratch/memguard.sh 4000 logs/manc_all_export.log $E/vnc-sim/bin/python -u vnc/export_manc_params.py
grep -v Warn logs/manc_all_export.log

step "5 闭环积分器 parity"
scratch/memguard.sh 4000 logs/manc_all_parity.log $E/fba/bin/python -u vnc/proprio_loop.py parity
grep -v Warn logs/manc_all_parity.log
if grep -q '"passed": false' results/vnc/manc_all/proprio_parity.json; then
  step "parity 未通过：跳过闭环"
else
  step "6 开环 + 相位性编码闭环"
  scratch/memguard.sh 4000 logs/manc_all_phasic.log $E/fba/bin/python -u vnc/proprio_loop.py run_phasic --with_open
  grep -v Warn logs/manc_all_phasic.log | grep "_rep[0-2]: \|exit="
fi

step "7 巨纤维 → TTMn（缩减网格）"
scratch/memguard.sh 6000 logs/manc_all_gap.log $E/vnc-sim/bin/python -u vnc/manc_full.py gap
grep -v Warn logs/manc_all_gap.log | tail -14
step "全部完成"
