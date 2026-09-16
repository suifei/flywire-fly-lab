#!/usr/bin/env python
"""
全腹神经索发放率模型（vnc/manc_full.py 的输出）→ NeuroMechFly 6 条腿（FlyGym 1.2.1，身体固定）。

映射（运行前写定，与 vnc/drive_legs_pugliese.py 相同，推广到 6 条腿）：
  * 腿 = 运动神经元的 somaNeuromere（T1 前 / T2 中 / T3 后）× somaSide（LHS 左 / RHS 右）。
  * 模块 → 关节：coxa swing/stance → 胸-基节（ThC），femur/tr extend/flex → 基-转节（CTr），tibia extend/flex → 腿节-胫节（FTi）。
  * 具体用哪个自由度（数据驱动的规则）：在 FlyGym 预设步态（真实果蝇运动学）里，
    ThC 在 Coxa / Coxa_roll / Coxa_yaw 中、CTr 在 Femur / Femur_roll 中，取“摆动相平均角 − 支撑相平均角”绝对值最大的那个。
  * 方向与幅度：摆动极值 = 该自由度在步态周期里朝摆动相方向的极值，支撑极值为另一端；
    目标角 = 支撑极值 + u·(摆动极值 − 支撑极值)，u = r_swing/(r_swing + r_stance)，两者之和 < 0.5 Hz 时 u = 0.5；每 1 ms 更新。
  * 其余自由度固定在步态周期平均姿态。
对照：FlyGym CPG 三足步态（2 s）。
指标：每条腿腿尖前后摆幅、4–30 Hz 节律占比、峰值频率；腿间相位（腿尖前后轨迹在 |Xi|·|Xj| 峰值频率处的互谱相角，
  两条腿摆幅都 ≥ 0.05 mm 才算）：同体节左右、同侧相邻、同侧 T1–T3，三足步态预期分别为 180°、180°、0°。
输出 results/vnc/manc_full/legs_summary.json 与 legs_<条件>_rep<k>.npz
用法（fba 环境）：python vnc/drive_legs_manc.py
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
import os  # noqa: E402
DATASET = os.environ.get("MANC_DATASET", "20251006")
MF = ROOT / "results" / "vnc" / ("manc_all" if DATASET == "all" else "manc_full")
WT = ROOT / "external/Pugliese_cpg_2025/data/manc full vnc data" / ("wTable_20260522_allSynapses.feather" if DATASET == "all" else "wTable_20251006.feather")
T, DT = 2.0, base.DT
JOINTS = ["Coxa", "Coxa_roll", "Coxa_yaw", "Femur", "Femur_roll", "Tibia", "Tarsus1"]
GROUPS = {"ThC": (["Coxa", "Coxa_roll", "Coxa_yaw"], ("coxa swing", "coxa stance")),
          "CTr": (["Femur", "Femur_roll"], ("femur/tr extend", "femur/tr flex")),
          "FTi": (["Tibia"], ("tibia extend", "tibia flex"))}
LEG_OF = {("T1", "LHS"): "LF", ("T2", "LHS"): "LM", ("T3", "LHS"): "LH", ("T1", "RHS"): "RF", ("T2", "RHS"): "RM", ("T3", "RHS"): "RH"}
PAIRS = {"同体节左右": [("LF", "RF"), ("LM", "RM"), ("LH", "RH")], "同侧相邻": [("LF", "LM"), ("LM", "LH"), ("RF", "RM"), ("RM", "RH")],
         "同侧 T1–T3": [("LF", "LH"), ("RF", "RH")]}
RUNS = [("none", 0), ("DNg100_LR_350", 0), ("DNg100_LR_350", 1), ("DNg100_LR_350", 2), ("DNg100_LR_350", 3), ("DNg100_L_350", 0),
        ("DNg100_LR_600", 0), ("MDN_400", 0)]
if DATASET == "all":
    RUNS = [("none", 0), ("DNg100_LR_360", 0), ("DNg100_LR_360", 1), ("DNg100_LR_360", 2), ("DNg100_LR_360", 3), ("DNg100_L_360", 0), ("DNg100_LR_400", 0)]


def geometry():
    steps = PreprogrammedSteps()
    ph = np.linspace(0, 2 * np.pi, 721)[:-1]
    mean_pose, choice = {}, {}
    for leg in steps.legs:
        ang = np.array([steps.get_joint_angles(leg, p, 1.0) for p in ph])
        mean_pose[leg] = ang.mean(axis=0)
        sp = steps.swing_period[leg]
        sw = (ph >= sp[0]) & (ph < sp[1])
        diff = ang[sw].mean(axis=0) - ang[~sw].mean(axis=0)
        for g, (cands, _) in GROUPS.items():
            j = max(cands, key=lambda c: abs(diff[JOINTS.index(c)]))
            k = JOINTS.index(j)
            up = diff[k] > 0
            choice[(leg, g)] = (j, ang[:, k].max() if up else ang[:, k].min(), ang[:, k].min() if up else ang[:, k].max())
    return steps.legs, mean_pose, choice


def module_rates(cond, rep):
    d = np.load(MF / f"{cond}.npz")
    R, sel = d["R_sel"][rep].astype(np.float32), d["sel_index"]
    wt = pd.read_feather(WT)
    sub = wt.loc[sel]
    out, active = {}, []
    for (seg, side), leg in LEG_OF.items():
        for g, (_, mods) in GROUPS.items():
            for m in mods:
                rows = np.where((sub["class"].to_numpy() == "motor neuron") & (sub.somaNeuromere.to_numpy() == seg) &
                                (sub.somaSide.to_numpy() == side) & (sub["motor module"].to_numpy() == m))[0]
                out[(leg, m)] = R[rows].mean(axis=0) if len(rows) else np.zeros(R.shape[1], np.float32)
        legrows = np.where((sub["class"].to_numpy() == "motor neuron") & (sub.somaNeuromere.to_numpy() == seg) & (sub.somaSide.to_numpy() == side))[0]
        active.append((leg, int((R[legrows, 230:].max(axis=1) > 1).sum())))
    return out, dict(active)


def run_mn(cond, rep, legs, mean_pose, choice):
    rates, active = module_rates(cond, rep)
    fly, sim, obs = base.make_sim()
    dofs = list(fly.actuated_joints)
    tips = base.tip_indices(sim, fly)
    pose = np.concatenate([mean_pose[leg] for leg in legs])
    tip_log = {leg: [] for leg in base.LEG_CN}
    for step in range(int(T / DT)):
        b = min(2000, int(step * DT * 1000))
        target = pose.copy()
        for leg in legs:
            for g, (_, (msw, mst)) in GROUPS.items():
                rs, rt = float(rates[(leg, msw)][b]), float(rates[(leg, mst)][b])
                u = rs / (rs + rt) if rs + rt >= 0.5 else 0.5
                j, e_sw, e_st = choice[(leg, g)]
                target[dofs.index(f"joint_{leg}{j}")] = e_st + u * (e_sw - e_st)
        obs, *_ = sim.step({"joints": target})
        if step % 50 == 0:
            for leg, bi in tips.items():
                tip_log[leg].append(np.array(sim.physics.data.xpos[bi]))
    sim.close()
    return {leg: np.array(v) for leg, v in tip_log.items()}, active


def phases(tips, desc, fs=1 / (50 * DT)):
    out = {}
    for group, pairs in PAIRS.items():
        for i, j in pairs:
            if desc[i]["ap_span_mm"] < 0.05 or desc[j]["ap_span_mm"] < 0.05:
                out[f"{i}-{j}"] = None
                continue
            x, y = tips[i][20:, 0], tips[j][20:, 0]
            x, y = x - x.mean(), y - y.mean()
            X, Y = np.fft.rfft(x), np.fft.rfft(y)
            f = np.fft.rfftfreq(len(x), 1 / fs)
            band = (f >= 4) & (f <= 30)
            k = np.where(band)[0][np.argmax((np.abs(X) * np.abs(Y))[band])]
            out[f"{i}-{j}"] = round(float(np.degrees(np.angle(X[k] * np.conj(Y[k])))), 1)
    return out


def main():
    base.T = T
    legs, mean_pose, choice = geometry()
    print("自由度选择：", {f"{l}-{g}": v[0] for (l, g), v in choice.items()})
    summary = {"_dof_choice": {f"{l}-{g}": v[0] for (l, g), v in choice.items()}}
    cpg = base.run_cpg()
    d = base.describe(cpg, "CPG 三足步态")
    summary["CPG_control"] = dict(legs=d, phase=phases(cpg, d))
    print("   相位：", summary["CPG_control"]["phase"])
    for cond, rep in RUNS:
        if not (MF / f"{cond}.npz").exists():
            continue
        tips, active = run_mn(cond, rep, legs, mean_pose, choice)
        d = base.describe(tips, f"{cond}#{rep}")
        key = f"{cond}_rep{rep}"
        summary[key] = dict(legs=d, phase=phases(tips, d), active_mn=active)
        print("   相位：", summary[key]["phase"], "；各腿活跃运动神经元：", active)
        np.savez_compressed(MF / f"legs_{key}.npz", **tips)
        (MF / "legs_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print("写入", MF / "legs_summary.json")


if __name__ == "__main__":
    main()
