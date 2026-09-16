#!/bin/bash
# 第 4 轮剩余实验，严格串行（一次只跑一个仿真）
cd /Volumes/Lexar/works/flywire.ai
E=~/miniconda3/envs
step() { echo "[$(date +%H:%M:%S)] $*"; }

step "1 腹神经索：MDN 剂量检查"
scratch/memguard.sh 5000 logs/pugliese_mdn_dose.log $E/vnc-sim/bin/python vnc/run_pugliese.py --reps 8 --conds MDN_I100,MDN_I150 --rtol 1e-4 --atol 1e-7
grep -v "副本 " logs/pugliese_mdn_dose.log | tail -3
$E/vnc-sim/bin/python vnc/analyze_pugliese.py > logs/pugliese_analysis.log 2>&1; cat logs/pugliese_analysis.log

step "2 发放率 → 前腿"
scratch/memguard.sh 5000 logs/legs_pugliese.log $E/fba/bin/python vnc/drive_legs_pugliese.py
tail -25 logs/legs_pugliese.log

step "3 嗅觉沉默（探索性）"
bash scratch/olf_silence.sh
$E/flygym/bin/python dodge/v4_olfaction_silencing.py > logs/v4olf_silencing_analysis.log 2>&1; cat logs/v4olf_silencing_analysis.log

step "4 强化学习速度探针"
scratch/memguard.sh 5000 logs/rl_speed.log $E/flybody/bin/python scratch/probe_rl_speed.py
grep -v Warning logs/rl_speed.log | tail -8

step "5 后退 v4（node）"
scratch/memguard.sh 3000 logs/backward_v4.log node dodge/backward_v4.js 8 3
tail -22 logs/backward_v4.log
step "全部完成"
