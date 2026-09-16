#!/bin/bash
# 全腹神经索三项，严格串行：分析 → 6 条腿 → 电突触 → 闭环 parity →（通过才跑）闭环
cd /Volumes/Lexar/works/flywire.ai
E=~/miniconda3/envs
step() { echo "[$(date +%H:%M:%S)] $*"; }
while pgrep -f "vnc/manc_full.py run" >/dev/null; do sleep 10; done

step "1a 全腹神经索分析"
scratch/memguard.sh 4000 logs/manc_analysis.log $E/vnc-sim/bin/python -u vnc/analyze_manc_full.py
grep -v Warn logs/manc_analysis.log

step "1b 6 条腿"
scratch/memguard.sh 4000 logs/manc_legs.log $E/fba/bin/python -u vnc/drive_legs_manc.py
grep -v Warn logs/manc_legs.log | tail -40

step "2 巨纤维 → TTMn 电突触"
scratch/memguard.sh 6000 logs/manc_gap.log $E/vnc-sim/bin/python -u vnc/manc_full.py gap
grep -v Warn logs/manc_gap.log | tail -30

step "3a 闭环积分器 parity"
scratch/memguard.sh 4000 logs/proprio_parity.log $E/fba/bin/python -u vnc/proprio_loop.py parity
grep -v Warn logs/proprio_parity.log
if grep -q '"passed": false' results/vnc/manc_full/proprio_parity.json; then
  step "parity 未通过，停止（不跑闭环）"
  exit 0
fi

step "3b 本体感觉闭环"
scratch/memguard.sh 4000 logs/proprio_run.log $E/fba/bin/python -u vnc/proprio_loop.py run
grep -v Warn logs/proprio_run.log | tail -40
step "全部完成"
