#!/bin/bash
# 探索性沉默实验：先跑左侧 DM1 + 集合 A / B；某集合阻止了失控，才跑对应的右侧（判据见 dodge/v4_olfaction_silencing.py）
cd /Volumes/Lexar/works/flywire.ai
PY=~/miniconda3/envs/brain-fly-cpu/bin/python
run() {  # $1 = 侧别 L/R, $2 = 集合 A/B
  local side=$([ "$1" = L ] && echo left || echo right) f=$([ "$2" = A ] && echo silence_setA_core4 || echo silence_setB_excALLN)
  scratch/memguard.sh 6500 logs/v4olf_DM1_$1_20_sil$2.log $PY run_experiment.py --exc_type ORN_DM1:$side --rate 20 \
    --silence $(cat results/v2_ref/$f.txt) --t_run 0.5 --n_trials 4 --record --out results/v2_ref/DM1_$1_20_sil$2
  local act=$(grep -o '"active_neurons": [0-9]*' logs/v4olf_DM1_$1_20_sil$2.log | tail -1 | grep -o '[0-9]*$')
  echo "DM1_$1_20_sil$2 active=$act $(tail -1 logs/v4olf_DM1_$1_20_sil$2.log)"
  [ -n "$act" ] && [ "$act" -lt 2000 ]
}
run L A && run R A
run L B && run R B
echo done
