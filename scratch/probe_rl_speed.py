"""测本机 flybody 环境步进速度（随机动作，不训练），用来估算“从零做强化学习训练”要多久。
用法（flybody 环境）：python scratch/probe_rl_speed.py
"""
import time
from pathlib import Path

import numpy as np
from flybody.fly_envs import flight_imitation, walk_on_ball

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "external/flybody_data/flight-dataset_saccade-evasion_augmented.hdf5"
WPG = ROOT / "external/flybody_data/wing_pattern_fmech.npy"


def bench(name, env, n=2000):
    spec = env.action_spec()
    rng = np.random.default_rng(0)
    ts = env.reset()
    t0 = time.time()
    steps = 0
    while steps < n:
        a = rng.uniform(spec.minimum, spec.maximum, spec.shape).astype(spec.dtype)
        ts = env.step(a)
        steps += 1
        if ts.last():
            ts = env.reset()
    dt = time.time() - t0
    ctrl = env.control_timestep()
    print(f"{name}: {steps / dt:.0f} 环境步/秒（控制步长 {ctrl * 1000:.2f} ms，仿真 {steps * ctrl:.2f} s 用时 {dt:.1f} s）")
    return steps / dt


import json  # noqa: E402

sps_walk = bench("walk_on_ball", walk_on_ball())
sps_flight = bench("flight_imitation", flight_imitation(ref_path=str(REF), wpg_pattern_path=str(WPG)))
res = dict(walk_on_ball_steps_per_s=round(sps_walk), flight_imitation_steps_per_s=round(sps_flight), estimates=[])
for label, total, sps in [("行走 1e9 步", 1e9, sps_walk), ("飞行 1e8 步", 1e8, sps_flight)]:
    d1, d8 = total / sps / 86400, total / sps / 8 / 86400
    res["estimates"].append(dict(label=label, days_1proc=round(d1, 1), days_8proc=round(d8, 1)))
    print(f"{label}：单进程 {d1:.0f} 天；8 个并行进程（理想线性）{d8:.0f} 天（不含网络更新时间）")
(ROOT / "results/dodge/rl_speed.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
