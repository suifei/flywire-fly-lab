#!/usr/bin/env python
"""
第 3 项：本体感觉闭环（探索性；感受器编码是手写的，结论强烈依赖这些选择）。
全腹神经索发放率模型（numpy 定步长 RK4，Δt = 0.5 ms）与 NeuroMechFly（FlyGym 1.2.1，身体固定，Δt = 0.1 ms）每 1 ms 交换一次：
  运动神经元 → 关节目标角：与 vnc/drive_legs_manc.py 完全相同的映射。
  关节状态 → 本体感受器发放率：只用经腿神经进入的感受器（instance 的入口神经 ProLN/MesoLN/MetaLN，见 sensors.json），
    被编码的感受器发放率直接“钳制”为编码值（不经过它们自己的动力学），通过连接组影响其他神经元。
手写编码（运行前写定）：
  * 弦音器（chordotonal organ）→ 该腿 腿节-胫节（Tibia）角度。按 bodyId 排序，偶数号“高角度调谐” r = r_max·σ((θ − θ_mid)/w)，
    奇数号“低角度调谐” r = r_max·σ((θ_mid − θ)/w)；θ_mid = 该腿预设步态里 Tibia 角的中点，w = 该角范围的 10%。
  * 毛板（hair plate）→ 该腿 胸-基节（drive_legs_manc 选出的 ThC 自由度）角度接近两端：偶数号 r_max·σ((θ − θ_90%)/w)，奇数号 r_max·σ((θ_10% − θ)/w)。
  * 钟形感器（campaniform sensilla）→ 负载：r_max·tanh((|τ_CTr| + |τ_FTi|)/τ0)，τ0 = CPG 步态对照 2 s 内该腿同一量的中位数。
  * r_max = 16 Hz（与标定后前进指令 DNg100 的发放率同量级）；敏感性检查 r_max = 50 Hz。
条件（DNg100 双侧 I = 350，副本参数与第 1 项相同）：
  open        感受器保持 0（开环，定步长积分）
  closed16    编码开启，r_max 16 Hz
  shuffled16  编码开启，但把 6 条腿的感受信号整体错位（前左 ← 中左 ← 后左 ← 前右 ← 中右 ← 后右 ← 前左）
  closed50    编码开启，r_max 50 Hz（只做副本 0）
先做 parity：定步长开环（不接身体）与第 1 项 Dopri5 结果对比，判据：腿部运动神经元总活动的主频相差 ≤ 0.5 Hz 且相关 ≥ 0.8（副本 0–2）。

—— 第二版：相位性编码（run_phasic，运行前写定）——
上一版的持续编码（弦音器平均 8 Hz）把网络推进失控，且正确/错位反馈结果相同。第二版改成“关节动了才放电、静止时为 0”：
  * 弦音器 → 该腿 腿节-胫节（Tibia）角速度 ω：偶数号 r = r_max·tanh(max(0, ω)/ω0)，奇数号 r = r_max·tanh(max(0, −ω)/ω0)（方向选择性）。
  * 毛板 → 该腿 胸-基节（ThC 自由度）角速度，同样按方向分两半。
  * 钟形感器 → 负载增加的速度：r = r_max·tanh(max(0, d(|τ_CTr| + |τ_FTi|)/dt)/τ̇0)。
  * ω0、τ̇0 = CPG 步态对照 2 s 内（去掉前 100 ms）该腿对应量绝对值的中位数；不做额外滤波。
  * r_max = 16 Hz；敏感性 50 Hz（副本 0）。对照：信号错位到别的腿（同上一版）。开环结果与上一版相同（同一积分器、同一身体、无随机性），直接沿用。
判据（运行前写定）：
  A 不破坏节律：活跃腿部运动神经元 < 50，且运动神经元总活动的 2–30 Hz 节律占比 ≥ 0.5；
  B 有改善：节律腿（摆幅 ≥ 0.1 mm 且节律占比 ≥ 0.5）多于开环的 1 条；
  C 反馈信息起作用：同一副本里正确对应与错位对应在 A 或 B 上结论不同，或节律腿数相差 ≥ 2。
另记感受器“活跃时间比例”（发放率 > 1 Hz 的样本比例），检查静止时是否真的不放电。
用法（fba 环境）：python vnc/proprio_loop.py parity | run | run_phasic
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

sys.path.insert(0, str(Path(__file__).resolve().parent))
import drive_legs as base  # noqa: E402
import drive_legs_manc as dlm  # noqa: E402
from flygym.examples.locomotion import PreprogrammedSteps, CPGNetwork  # noqa: E402
import flygym  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MF = dlm.MF                     # 随 MANC_DATASET 切换（manc_full / manc_all）
DTN = 0.0005
PRIMARY = "DNg100_LR_360" if dlm.DATASET == "all" else "DNg100_LR_350"
STIM_I = 360.0 if dlm.DATASET == "all" else 350.0


class Net:
    def __init__(self, rep):
        self.Wt = sp.load_npz(MF / "Wt_csr.npz").tocsr()
        p = np.load(MF / "params_reps0-3.npz")
        self.tau, self.a, self.thr, self.fr = (p[k][rep].astype(np.float64) for k in ("tau", "a", "thr", "frcap"))
        self.wt = pd.read_feather(dlm.WT)
        self.N = len(self.wt)
        self.inputs = np.zeros(self.N); self.inputs[self.wt.index[self.wt.type == "DNg100"]] = STIM_I
        self.R = np.zeros(self.N)
        self.sens_idx = np.zeros(0, int); self.sens_rate = np.zeros(0)

    def f(self, R, t):
        R = R.copy(); R[self.sens_idx] = self.sens_rate
        total = self.inputs * (0.02 <= t <= 1.999) + self.Wt @ R
        d = (np.maximum(self.fr * np.tanh((self.a / self.fr) * (total - self.thr)), 0) - R) / self.tau
        d[self.sens_idx] = 0
        return d

    def step(self, t):
        R, h = self.R, DTN
        k1 = self.f(R, t); k2 = self.f(R + h / 2 * k1, t + h / 2); k3 = self.f(R + h / 2 * k2, t + h / 2); k4 = self.f(R + h * k3, t + h)
        self.R = np.clip(R + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4), 0, 1000)
        self.R[self.sens_idx] = self.sens_rate


def legmn_rows(wt):
    return np.where((wt["class"] == "motor neuron").to_numpy() & wt.somaNeuromere.isin(["T1", "T2", "T3"]).to_numpy())[0]


def dom_freq(x, fs=1000.0):
    x = x - x.mean()
    P = np.abs(np.fft.rfft(x)) ** 2; f = np.fft.rfftfreq(len(x), 1 / fs)
    band = (f >= 2) & (f <= 30)
    return float(f[band][np.argmax(P[band])]) if P[band].sum() > 0 else None, float(P[band].sum() / max(P[1:].sum(), 1e-12))


def cmd_parity():
    ref = np.load(MF / f"{PRIMARY}.npz")
    sel = ref["sel_index"]
    out = []
    for rep in (0, 1, 2):
        net = Net(rep)
        rows = legmn_rows(net.wt)
        pos = {int(i): k for k, i in enumerate(sel)}
        t0 = time.time()
        trace = np.zeros((2001, len(rows)))
        for ms in range(2000):
            for k in range(2):
                net.step(ms * 1e-3 + k * DTN)
            trace[ms + 1] = net.R[rows]
        refR = ref["R_sel"][rep][[pos[int(i)] for i in rows]].astype(np.float64).T
        a_sum, b_sum = trace[230:].sum(axis=1), refR[230:].sum(axis=1)
        fa, _ = dom_freq(a_sum); fb, _ = dom_freq(b_sum)
        c = float(np.corrcoef(a_sum, b_sum)[0, 1]) if a_sum.std() > 0 and b_sum.std() > 0 else None
        ok = fa is not None and fb is not None and abs(fa - fb) <= 0.5 and c is not None and c >= 0.8
        out.append(dict(rep=rep, freq_rk4=fa, freq_dopri5=fb, corr=None if c is None else round(c, 3), max_abs_diff_hz=round(float(np.abs(trace - refR).max()), 2),
                        passed=bool(ok), sim_s=round(time.time() - t0, 1)))
        print(out[-1], flush=True)
    (MF / "proprio_parity.json").write_text(json.dumps(out, indent=1))


def encoders(choice, legs):
    steps = PreprogrammedSteps()
    ph = np.linspace(0, 2 * np.pi, 721)[:-1]
    geo = {}
    for leg in legs:
        ang = np.array([steps.get_joint_angles(leg, p, 1.0) for p in ph])
        tib = ang[:, dlm.JOINTS.index("Tibia")]
        thc = ang[:, dlm.JOINTS.index(choice[(leg, "ThC")][0])]
        geo[leg] = dict(tib_mid=(tib.min() + tib.max()) / 2, tib_w=0.1 * np.ptp(tib),
                        thc_lo=thc.min() + 0.1 * np.ptp(thc), thc_hi=thc.min() + 0.9 * np.ptp(thc), thc_w=0.1 * np.ptp(thc))
    return geo


def cpg_torque_scale(choice):
    fly, sim, obs = base.make_sim()
    dofs = list(fly.actuated_joints)
    steps = PreprogrammedSteps()
    biases = flygym.preprogrammed.get_cpg_biases("tripod")
    cpg = CPGNetwork(timestep=base.DT, intrinsic_freqs=np.ones(6) * 12, intrinsic_amps=np.ones(6), coupling_weights=(biases > 0) * 10,
                     phase_biases=biases, convergence_coefs=np.ones(6) * 20)
    acc = {leg: [] for leg in steps.legs}
    for step in range(int(2.0 / base.DT)):
        cpg.step()
        joints = np.concatenate([steps.get_joint_angles(leg, cpg.curr_phases[i], cpg.curr_magnitudes[i]) for i, leg in enumerate(steps.legs)])
        obs, *_ = sim.step({"joints": joints})
        if step % 10 == 0 and step > 1000:
            for leg in steps.legs:
                tq = np.asarray(obs["joints"][2])
                acc[leg].append(abs(tq[dofs.index(f"joint_{leg}{choice[(leg, 'CTr')][0]}")]) + abs(tq[dofs.index(f"joint_{leg}Tibia")]))
    sim.close()
    return {leg: float(np.median(v)) for leg, v in acc.items()}


def cpg_scales(choice):
    """相位性编码的归一化常数：CPG 步态对照里各腿 |ω_Tibia|、|ω_ThC|、|d负载/dt| 的中位数（每 1 ms 采样，去掉前 100 ms）。"""
    fly, sim, obs = base.make_sim()
    dofs = list(fly.actuated_joints)
    steps = PreprogrammedSteps()
    biases = flygym.preprogrammed.get_cpg_biases("tripod")
    cpg = CPGNetwork(timestep=base.DT, intrinsic_freqs=np.ones(6) * 12, intrinsic_amps=np.ones(6), coupling_weights=(biases > 0) * 10,
                     phase_biases=biases, convergence_coefs=np.ones(6) * 20)
    acc = {leg: dict(w_tib=[], w_thc=[], dtau=[]) for leg in steps.legs}
    prev = {}
    for step in range(int(2.0 / base.DT)):
        cpg.step()
        joints = np.concatenate([steps.get_joint_angles(leg, cpg.curr_phases[i], cpg.curr_magnitudes[i]) for i, leg in enumerate(steps.legs)])
        obs, *_ = sim.step({"joints": joints})
        if step % 10 == 0:
            qd, tq = np.asarray(obs["joints"][1]), np.asarray(obs["joints"][2])
            for leg in steps.legs:
                load = abs(tq[dofs.index(f"joint_{leg}{choice[(leg, 'CTr')][0]}")]) + abs(tq[dofs.index(f"joint_{leg}Tibia")])
                if step > 1000:
                    acc[leg]["w_tib"].append(abs(qd[dofs.index(f"joint_{leg}Tibia")]))
                    acc[leg]["w_thc"].append(abs(qd[dofs.index(f"joint_{leg}{choice[(leg, 'ThC')][0]}")]))
                    acc[leg]["dtau"].append(abs(load - prev[leg]) / 1e-3)
                prev[leg] = load
    sim.close()
    return {leg: {k: float(np.median(v)) for k, v in d.items()} for leg, d in acc.items()}


def sig(x):
    return 1 / (1 + np.exp(-x))


def run_loop(rep, mode, r_max, legs, mean_pose, choice, geo, tau0, sensors, scales=None):
    net = Net(rep)
    wt = net.wt
    rows = legmn_rows(wt)
    e1 = {dlm.LEG_OF[(wt.somaNeuromere[i], wt.somaSide[i])]: int(i) for i in wt.index[wt.type == "IN17A001"]}
    # 模块行
    sub = wt
    mod_rows = {}
    for (seg, side), leg in dlm.LEG_OF.items():
        for g, (_, mods) in dlm.GROUPS.items():
            for m in mods:
                mod_rows[(leg, m)] = np.where((sub["class"].to_numpy() == "motor neuron") & (sub.somaNeuromere.to_numpy() == seg) &
                                              (sub.somaSide.to_numpy() == side) & (sub["motor module"].to_numpy() == m))[0]
    # 感受器（按腿、类型、bodyId 排序）
    shift = {"LF": "LM", "LM": "LH", "LH": "RF", "RF": "RM", "RM": "RH", "RH": "LF"}   # shuffled：该腿的感受器读 shift[腿] 的关节
    enc = []
    for leg, g in sensors.items():
        src = shift[leg] if "shuffled" in mode else leg
        for sub_, ids in g.items():
            ids = sorted(ids, key=lambda i: int(wt.bodyId[i]))
            for k, i in enumerate(ids):
                enc.append((i, sub_, src, k % 2))
    if mode != "open":
        net.sens_idx = np.array([e[0] for e in enc], int); net.sens_rate = np.zeros(len(enc))
    fly, sim, obs = base.make_sim()
    dofs = list(fly.actuated_joints)
    tips = base.tip_indices(sim, fly)
    pose = np.concatenate([mean_pose[leg] for leg in legs])
    tip_log = {leg: [] for leg in base.LEG_CN}
    mn_trace = np.zeros((2001, len(rows)), np.float32); e1_trace = {leg: np.zeros(2001, np.float32) for leg in e1}
    sens_mean = {}
    prev_load = {}
    t0 = time.time()
    for ms in range(2000):
        if mode.startswith("phasic"):
            qd = np.asarray(obs["joints"][1]); tq = np.asarray(obs["joints"][2])
            wt_leg, wh_leg, dl_leg = {}, {}, {}
            for lg in legs:
                wt_leg[lg] = qd[dofs.index(f"joint_{lg}Tibia")]
                wh_leg[lg] = qd[dofs.index(f"joint_{lg}{choice[(lg, 'ThC')][0]}")]
                load = abs(tq[dofs.index(f"joint_{lg}{choice[(lg, 'CTr')][0]}")]) + abs(tq[dofs.index(f"joint_{lg}Tibia")])
                dl_leg[lg] = (load - prev_load.get(lg, load)) / 1e-3
                prev_load[lg] = load
            rates = np.empty(len(enc))
            for n, (i, sub_, src, parity) in enumerate(enc):
                sc = scales[src]
                if sub_ == "chordotonal organ":
                    v = wt_leg[src] if parity == 0 else -wt_leg[src]
                    rates[n] = r_max * np.tanh(max(0.0, v) / max(sc["w_tib"], 1e-9))
                elif sub_ == "hair plate":
                    v = wh_leg[src] if parity == 0 else -wh_leg[src]
                    rates[n] = r_max * np.tanh(max(0.0, v) / max(sc["w_thc"], 1e-9))
                else:
                    rates[n] = r_max * np.tanh(max(0.0, dl_leg[src]) / max(sc["dtau"], 1e-12))
            net.sens_rate = rates
            if ms >= 230:
                for n, (i, sub_, src, parity) in enumerate(enc):
                    sens_mean.setdefault(sub_, []).append(rates[n])
        elif mode != "open":
            q = np.asarray(obs["joints"][0]); tq = np.asarray(obs["joints"][2])
            rates = np.empty(len(enc))
            for n, (i, sub_, src, parity) in enumerate(enc):
                G = geo[src]
                if sub_ == "chordotonal organ":
                    th = q[dofs.index(f"joint_{src}Tibia")]
                    x = (th - G["tib_mid"]) / G["tib_w"]
                    rates[n] = r_max * sig(x if parity == 0 else -x)
                elif sub_ == "hair plate":
                    th = q[dofs.index(f"joint_{src}{choice[(src, 'ThC')][0]}")]
                    rates[n] = r_max * (sig((th - G["thc_hi"]) / G["thc_w"]) if parity == 0 else sig((G["thc_lo"] - th) / G["thc_w"]))
                else:
                    load = abs(tq[dofs.index(f"joint_{src}{choice[(src, 'CTr')][0]}")]) + abs(tq[dofs.index(f"joint_{src}Tibia")])
                    rates[n] = r_max * np.tanh(load / max(tau0[src], 1e-9))
            net.sens_rate = rates
            if ms >= 230:
                for n, (i, sub_, src, parity) in enumerate(enc):
                    sens_mean.setdefault(sub_, []).append(rates[n])
        for k in range(2):
            net.step(ms * 1e-3 + k * DTN)
        mn_trace[ms + 1] = net.R[rows]
        for leg, i in e1.items():
            e1_trace[leg][ms + 1] = net.R[i]
        target = pose.copy()
        for leg in legs:
            for g, (_, (msw, mst)) in dlm.GROUPS.items():
                rs = float(net.R[mod_rows[(leg, msw)]].mean()) if len(mod_rows[(leg, msw)]) else 0.0
                rt = float(net.R[mod_rows[(leg, mst)]].mean()) if len(mod_rows[(leg, mst)]) else 0.0
                u = rs / (rs + rt) if rs + rt >= 0.5 else 0.5
                j, e_sw, e_st = choice[(leg, g)]
                target[dofs.index(f"joint_{leg}{j}")] = e_st + u * (e_sw - e_st)
        for s_ in range(10):
            obs, *_ = sim.step({"joints": target})
            if (ms * 10 + s_) % 50 == 0:
                for leg, bi in tips.items():
                    tip_log[leg].append(np.array(sim.physics.data.xpos[bi]))
    sim.close()
    tips_arr = {leg: np.array(v) for leg, v in tip_log.items()}
    fq, rp = dom_freq(mn_trace[230:].sum(axis=1))
    legact = {}
    for (seg, side), leg in dlm.LEG_OF.items():
        m = (wt["class"].to_numpy()[rows] == "motor neuron") & (wt.somaNeuromere.to_numpy()[rows] == seg) & (wt.somaSide.to_numpy()[rows] == side)
        legact[leg] = int((mn_trace[230:, m].max(axis=0) > 1).sum())
    return tips_arr, dict(wall_s=round(time.time() - t0, 1), legmn_active_total=int((mn_trace[230:].max(axis=0) > 1).sum()), legmn_active=legact,
                          legmn_sum_freq=fq, legmn_sum_rhythm=round(rp, 3),
                          sensor_mean_hz={k: round(float(np.mean(v)), 2) for k, v in sens_mean.items()},
                          sensor_active_frac={k: round(float(np.mean(np.asarray(v) > 1)), 3) for k, v in sens_mean.items()}), e1_trace


def cmd_run():
    legs, mean_pose, choice = dlm.geometry()
    geo = encoders(choice, legs)
    tau0 = cpg_torque_scale(choice)
    sensors = json.loads((MF / "sensors.json").read_text())["groups"]
    runs = [(r, m, x) for r in (0, 1, 2) for m, x in (("open", 0), ("closed16", 16), ("shuffled16", 16))] + [(0, "closed50", 50)]
    summary = dict(tau0=tau0, runs={})
    base.T = 2.0
    for rep, mode, r_max in runs:
        tips, stats, e1 = run_loop(rep, mode, r_max, legs, mean_pose, choice, geo, tau0, sensors)
        d = base.describe(tips, f"{mode}#{rep}")
        key = f"{mode}_rep{rep}"
        summary["runs"][key] = dict(legs=d, phase=dlm.phases(tips, d), **stats)
        print(f"   {key}: {stats}；相位 {summary['runs'][key]['phase']}", flush=True)
        np.savez_compressed(MF / f"proprio_{key}.npz", **tips, **{f"E1_{k}": v for k, v in e1.items()})
        (MF / "proprio_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))


def cmd_run_phasic():
    legs, mean_pose, choice = dlm.geometry()
    geo = encoders(choice, legs)
    scales = cpg_scales(choice)
    print("CPG 归一化常数：", {k: {kk: f"{vv:.3g}" for kk, vv in v.items()} for k, v in scales.items()}, flush=True)
    sensors = json.loads((MF / "sensors.json").read_text())["groups"]
    runs = [(r, m, x) for r in (0, 1, 2) for m, x in (("phasic16", 16), ("phasic_shuffled16", 16))] + [(0, "phasic50", 50)]
    if "--with_open" in sys.argv:          # 新网络没有现成的开环结果：每个副本先跑开环
        runs = [(r, m, x) for r in (0, 1, 2) for m, x in (("open", 0), ("phasic16", 16), ("phasic_shuffled16", 16))] + [(0, "phasic50", 50)]
    summary = dict(scales=scales, open_loop=("本文件内 open_rep0–2" if "--with_open" in sys.argv else "沿用 proprio_summary.json 的 open_rep0–2（同一积分器与身体，无随机性）"), runs={})
    base.T = 2.0
    for rep, mode, r_max in runs:
        tips, stats, e1 = run_loop(rep, mode, r_max, legs, mean_pose, choice, geo, None, sensors, scales=scales)
        d = base.describe(tips, f"{mode}#{rep}")
        key = f"{mode}_rep{rep}"
        summary["runs"][key] = dict(legs=d, phase=dlm.phases(tips, d), **stats)
        print(f"   {key}: {stats}；相位 {summary['runs'][key]['phase']}", flush=True)
        np.savez_compressed(MF / f"proprio_{key}.npz", **tips, **{f"E1_{k}": v for k, v in e1.items()})
        (MF / "proprio_phasic_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    {"parity": cmd_parity, "run": cmd_run, "run_phasic": cmd_run_phasic}[sys.argv[1]]()
