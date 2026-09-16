#!/usr/bin/env python
"""
第 5 步 C：腿部运动神经元发放率 → NeuroMechFly（FlyGym 1.2.1）腿部关节角，看腿怎么动。

映射（手写，逐项声明）：
  * 关节对应（BANC Function → NeuroMechFly 关节）：
      move_coxa_anterior / posterior      → joint_<leg>Coxa      （ThC，前移为“伸”）
      extend / flex_coxa_trochanter_joint → joint_<leg>Femur     （CTr）
      extend / flex_femur_tibia_joint     → joint_<leg>Tibia     （FTi）
      extend / flex_tibia_tarsus_joint    → joint_<leg>Tarsus1   （TiTa）
  * 角度 = 中性姿态角 + 幅度_j × tanh((伸肌群发放率 − 屈肌群发放率) / 20 Hz)
    幅度（rad）：ThC 0.5、CTr 0.6、FTi 0.8、TiTa 0.4；“伸 = 关节角增大”的方向约定未经验证。
  * 发放率来自 results/vnc/<条件>/mn_rates.npz（BANC 腹神经索 LIF，10 ms 分箱），逐 10 ms 更新目标角。
对照：FlyGym 自带 CPG 步态控制器（同一身体、同样 1 s），用来说明“真正迈步”时腿尖轨迹长什么样。
果蝇固定（Tethered），只看腿部运动；不渲染，只做物理并记录腿尖（Tarsus5）位置。
输出：results/vnc/legs_<条件>.npz 与 results/vnc/legs_summary.json
用法（fba 环境）：python vnc/drive_legs.py
"""
import json
from pathlib import Path

import numpy as np
import flygym
from flygym.arena import Tethered
from flygym.examples.locomotion import PreprogrammedSteps, CPGNetwork

ROOT = Path(__file__).resolve().parent.parent
VNCR = ROOT / "results" / "vnc"
LEG_CN = {"LF": "前L", "LM": "中L", "LH": "后L", "RF": "前R", "RM": "中R", "RH": "后R"}
JOINT_MAP = {"ThC": ("Coxa", 0.5), "CTr": ("Femur", 0.6), "FTi": ("Tibia", 0.8), "TiTa": ("Tarsus1", 0.4)}
DT = 1e-4
T = 1.0


def make_sim():
    fly = flygym.Fly(enable_adhesion=False, init_pose="stretch", control="position", actuated_joints=flygym.preprogrammed.all_leg_dofs)
    sim = flygym.SingleFlySimulation(fly=fly, arena=Tethered(), timestep=DT)
    obs, _ = sim.reset()
    return fly, sim, obs


def tip_indices(sim, fly):
    names = [sim.physics.model.id2name(i, "body") for i in range(sim.physics.model.nbody)]
    return {leg: next(i for i, n in enumerate(names) if n.endswith(f"{leg}Tarsus5")) for leg in LEG_CN}


def run_mn(cond):
    d = np.load(VNCR / cond / "mn_rates.npz")
    fly, sim, obs = make_sim()
    dofs = list(fly.actuated_joints)
    neutral = np.array(obs["joints"][0], dtype=float)
    tips = tip_indices(sim, fly)
    n_steps = int(T / DT)
    tip_log = {leg: [] for leg in LEG_CN}
    angle_log = []
    for step in range(n_steps):
        b = min(len(d["t_ms"]) - 1, int(step * DT * 1000 / 10))
        target = neutral.copy()
        for leg, cn in LEG_CN.items():
            for jt, (jname, amp) in JOINT_MAP.items():
                fl = d.get(f"{cn}|{jt}|flex"); ex = d.get(f"{cn}|{jt}|ext")
                diff = (ex[b] if ex is not None else 0.0) - (fl[b] if fl is not None else 0.0)
                name = f"joint_{leg}{jname}"
                if name in dofs:
                    target[dofs.index(name)] = neutral[dofs.index(name)] + amp * np.tanh(diff / 20.0)
        obs, *_ = sim.step({"joints": target})
        if step % 50 == 0:
            for leg, bi in tips.items():
                tip_log[leg].append(np.array(sim.physics.data.xpos[bi]))
            angle_log.append(np.array(obs["joints"][0]))
    sim.close()
    return {leg: np.array(v) for leg, v in tip_log.items()}, np.array(angle_log), dofs


def run_cpg():
    fly, sim, obs = make_sim()
    steps = PreprogrammedSteps()
    biases = flygym.preprogrammed.get_cpg_biases("tripod")            # flygym 官方三足步态相位偏置
    cpg = CPGNetwork(timestep=DT, intrinsic_freqs=np.ones(6) * 12, intrinsic_amps=np.ones(6),
                     coupling_weights=(biases > 0) * 10, phase_biases=biases, convergence_coefs=np.ones(6) * 20)
    tips = tip_indices(sim, fly)
    tip_log = {leg: [] for leg in LEG_CN}
    legs = steps.legs                                                  # ["LF","LM","LH","RF","RM","RH"]，与 all_leg_dofs 顺序一致
    for step in range(int(T / DT)):
        cpg.step()
        joints = np.concatenate([steps.get_joint_angles(leg, cpg.curr_phases[i], cpg.curr_magnitudes[i]) for i, leg in enumerate(legs)])
        obs, *_ = sim.step({"joints": joints})
        if step % 50 == 0:
            for leg, bi in tips.items():
                tip_log[leg].append(np.array(sim.physics.data.xpos[bi]))
    sim.close()
    return {leg: np.array(v) for leg, v in tip_log.items()}


def describe(tips, label):
    res = {}
    for leg, p in tips.items():
        p = p[20:]                                                     # 去掉前 100 ms
        x = p[:, 0] - p[:, 0].mean()
        span = float(np.ptp(p[:, 0]) * 1.0)                            # 前后方向摆动幅度（mm）
        P = np.abs(np.fft.rfft(x)) ** 2; f = np.fft.rfftfreq(len(x), 50 * DT)
        band = (f >= 4) & (f <= 30)
        res[leg] = dict(ap_span_mm=round(span, 3), rhythm_power=round(float(P[band].sum() / max(P[1:].sum(), 1e-12)), 2),
                        peak_hz=round(float(f[band][P[band].argmax()]), 1) if P[band].sum() > 0 else None)
    print(f"  {label:14s} " + "  ".join(f"{LEG_CN[l]} 摆幅{v['ap_span_mm']:.2f}mm 节律{v['rhythm_power']:.2f}@{v['peak_hz']}Hz" for l, v in res.items()))
    return res


def main():
    summary = {}
    print("腿尖（Tarsus5）前后方向摆幅与 4–30 Hz 节律功率占比（随机噪声约 0.52）：")
    cpg_tips = run_cpg(); summary["CPG_control"] = describe(cpg_tips, "CPG 步态对照")
    np.savez_compressed(VNCR / "legs_CPG_control.npz", **{k: v for k, v in cpg_tips.items()})
    for cond in ["FWD", "BDN2", "MDN"]:
        tips, angles, dofs = run_mn(cond)
        summary[cond] = describe(tips, f"运动神经元·{cond}")
        np.savez_compressed(VNCR / f"legs_{cond}.npz", angles=angles, dofs=np.array(dofs), **tips)
    json.dump(summary, open(VNCR / "legs_summary.json", "w"), ensure_ascii=False, indent=1)
    print("写入", VNCR / "legs_summary.json")


if __name__ == "__main__":
    main()
