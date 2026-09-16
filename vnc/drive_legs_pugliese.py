#!/usr/bin/env python
"""
腹神经索发放率模型（Pugliese 2025，MANC T1，vnc/run_pugliese.py 的输出）→ NeuroMechFly 前腿（FlyGym 1.2.1，固定身体）。

映射（运行前写定，手写部分逐项声明）：
  * 运动模块 → 关节（模块名与“迈步贡献” swing/stance 标签来自作者发布的 MANC T1 表）：
      coxa swing / coxa stance           → joint_<腿>Coxa   （ThC）
      femur/tr extend / femur/tr flex    → joint_<腿>Femur  （CTr）
      tibia extend / tibia flex          → joint_<腿>Tibia  （FTi）
    femur reductor、substrate grip、tarsus control 不映射。左腿 = somaSide LHS，右腿 = RHS。
  * 角度方向不靠猜：取 FlyGym 自带、来自真实果蝇运动学的预设步态（PreprogrammedSteps），
    该关节在摆动相（swing_period）平均角 > 支撑相平均角时，“摆动极值” = 周期内最大角、“支撑极值” = 最小角，反之亦然。
  * 目标角 = 支撑极值 + u·(摆动极值 − 支撑极值)，u = r_swing / (r_swing + r_stance)（该侧该模块运动神经元平均发放率），
    两者之和 < 0.5 Hz 时 u = 0.5。每 1 ms 按发放率更新一次。
  * 不映射的关节、以及中腿和后腿：固定在预设步态整个周期的平均姿态。
对照：FlyGym 自带 CPG 三足步态（同一身体、同样 2 s）。
指标：腿尖（Tarsus5）前后方向摆幅、4–30 Hz 节律功率占比（随机噪声约 0.52）、峰值频率、左前腿与右前腿在峰值频率上的相位差。
输出 results/vnc/pugliese/legs_summary.json 与 legs_<条件>_rep<k>.npz
用法（fba 环境）：python vnc/drive_legs_pugliese.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import drive_legs as base  # noqa: E402
from flygym.examples.locomotion import PreprogrammedSteps  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PR = ROOT / "results" / "vnc" / "pugliese"
T = 2.0
DT = base.DT
JOINTS = ["Coxa", "Coxa_roll", "Coxa_yaw", "Femur", "Femur_roll", "Tibia", "Tarsus1"]
MOD = {"Coxa": ("coxa swing", "coxa stance"), "Femur": ("femur/tr extend", "femur/tr flex"), "Tibia": ("tibia extend", "tibia flex")}
SIDE = {"LF": "LHS", "RF": "RHS"}
RUNS = [("none", 0), ("DNg100_L", 0), ("DNg100_LR", 0), ("DNg100_LR", 1), ("DNg100_LR", 2), ("DNg100_LR", 3), ("MDN", 0), ("DNa02_L", 0)]


def step_geometry():
    steps = PreprogrammedSteps()
    ph = np.linspace(0, 2 * np.pi, 721)[:-1]
    mean_pose, ext = {}, {}
    for leg in steps.legs:
        ang = np.array([steps.get_joint_angles(leg, p, 1.0) for p in ph])
        mean_pose[leg] = ang.mean(axis=0)
        sp = steps.swing_period[leg]
        sw = (ph >= sp[0]) & (ph < sp[1])
        for j, name in enumerate(JOINTS):
            if name in MOD:
                up = ang[sw, j].mean() > ang[~sw, j].mean()
                ext[(leg, name)] = (ang[:, j].max() if up else ang[:, j].min(), ang[:, j].min() if up else ang[:, j].max())
    return steps.legs, mean_pose, ext


def module_rates(cond, rep):
    d = np.load(PR / f"{cond}.npz")
    R = d["R_mn"][rep].astype(np.float32)                       # (144, 2001)，1 ms
    tab = pd.read_csv(PR / "mn_table.csv", index_col=0)
    out = {}
    for leg, side in SIDE.items():
        for name, (sw, st) in MOD.items():
            for m in (sw, st):
                rows = np.where((tab.somaSide.to_numpy() == side) & (tab["motor module"].to_numpy() == m))[0]
                out[(leg, m)] = R[rows].mean(axis=0) if len(rows) else np.zeros(R.shape[1], np.float32)
    active = tab.assign(maxr=R[:, 230:].max(axis=1))
    active = active[active.maxr > 1][["somaSide", "motor module", "maxr"]]
    return out, active


def run_mn(cond, rep, legs, mean_pose, ext):
    rates, active = module_rates(cond, rep)
    fly, sim, obs = base.make_sim()
    dofs = list(fly.actuated_joints)
    tips = base.tip_indices(sim, fly)
    pose = np.concatenate([mean_pose[leg] for leg in legs])      # all_leg_dofs 顺序 = legs × JOINTS
    tip_log = {leg: [] for leg in base.LEG_CN}
    us = []
    for step in range(int(T / DT)):
        b = min(2000, int(step * DT * 1000))
        target = pose.copy()
        urow = []
        for leg in SIDE:
            for name, (sw, st) in MOD.items():
                rs, rt = float(rates[(leg, sw)][b]), float(rates[(leg, st)][b])
                u = rs / (rs + rt) if rs + rt >= 0.5 else 0.5
                e_sw, e_st = ext[(leg, name)]
                target[dofs.index(f"joint_{leg}{name}")] = e_st + u * (e_sw - e_st)
                urow.append(u)
        obs, *_ = sim.step({"joints": target})
        if step % 50 == 0:
            us.append(urow)
            for leg, bi in tips.items():
                tip_log[leg].append(np.array(sim.physics.data.xpos[bi]))
    sim.close()
    return {leg: np.array(v) for leg, v in tip_log.items()}, np.array(us), active


def lr_phase(tips, fs=1 / (50 * DT)):
    x, y = tips["LF"][20:, 0], tips["RF"][20:, 0]
    x, y = x - x.mean(), y - y.mean()
    X, Y = np.fft.rfft(x), np.fft.rfft(y)
    f = np.fft.rfftfreq(len(x), 1 / fs)
    band = (f >= 4) & (f <= 30)
    if (np.abs(X[band]) ** 2).sum() < 1e-12 or (np.abs(Y[band]) ** 2).sum() < 1e-12:
        return None
    k = np.where(band)[0][np.argmax((np.abs(X) * np.abs(Y))[band])]
    return round(float(np.degrees(np.angle(X[k] * np.conj(Y[k])))), 1)


def main():
    base.T = T
    legs, mean_pose, ext = step_geometry()
    summary = {}
    print("腿尖前后摆幅 / 4–30 Hz 节律占比 / 峰值频率（只看前腿；中后腿固定）")
    cpg = base.run_cpg()
    d = base.describe(cpg, "CPG 步态对照")
    summary["CPG_control"] = dict(legs={k: d[k] for k in ("LF", "RF")}, lf_rf_phase_deg=lr_phase(cpg))
    print(f"    左右前腿相位差 {summary['CPG_control']['lf_rf_phase_deg']}°")
    for cond, rep in RUNS:
        tips, us, active = run_mn(cond, rep, legs, mean_pose, ext)
        d = base.describe(tips, f"{cond}#{rep}")
        key = f"{cond}_rep{rep}"
        summary[key] = dict(legs={k: d[k] for k in ("LF", "RF")}, lf_rf_phase_deg=lr_phase(tips),
                            active_mn=[f"{r.somaSide} {r['motor module']} {r.maxr:.1f}Hz" for _, r in active.iterrows()],
                            u_std=us.std(axis=0).round(3).tolist())
        print(f"    左右前腿相位差 {summary[key]['lf_rf_phase_deg']}°；活跃运动神经元（>1 Hz）：{summary[key]['active_mn']}")
        np.savez_compressed(PR / f"legs_{key}.npz", u=us, **tips)
        (PR / "legs_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print("写入", PR / "legs_summary.json")


if __name__ == "__main__":
    main()
