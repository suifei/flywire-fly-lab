#!/usr/bin/env python
"""
全腹神经索（MANC）结果分析，指标在看结果之前写定：
  1. 条件汇总：作者网络振荡得分（腿部运动神经元，丢弃前 230 ms，≥ 0.5 记为振荡）的副本比例、频率中位、活跃数；
     全网活跃神经元 ≥ 2,000 的副本记为“失控”（与全脑分析同一阈值）。
  2. 每条腿（T1/T2/T3 × 左/右）：活跃运动神经元（> 1 Hz）、该腿运动神经元的作者单神经元得分均值（≥ 0.5 记该腿振荡）、频率中位。
  3. 腿间相位：用每条腿的 E1（IN17A001，作者 Extended Data Fig. 8 用的同一类神经元）。
     只在网络振荡的副本里、两条腿的 E1 都活跃（> 1 Hz）且单神经元得分 ≥ 0.5、各自峰值频率相差 ≤ 1 Hz 时计算；
     相位差 = 两条轨迹在 2–30 Hz 内 |Xi|·|Xj| 峰值频率处互谱的相角；跨副本给出圆均值与一致性 R（0–1）。
     三足步态预期：同一体节左右 180°，同侧相邻（T1–T2、T2–T3）180°，同侧 T1–T3 0°。
  4. 同一条腿“摆动模块和”与“支撑模块和”的零滞后相关（< 0 = 交替）。
输出 results/vnc/manc_full/analysis.json
用法（vnc-sim 环境）：python vnc/analyze_manc_full.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PUG = ROOT / "external" / "Pugliese_cpg_2025"
import os  # noqa: E402
DATASET = os.environ.get("MANC_DATASET", "20251006")
OUT = ROOT / "results" / "vnc" / ("manc_all" if DATASET == "all" else "manc_full")
TABLE = PUG / "data/manc full vnc data" / ("wTable_20260522_allSynapses.feather" if DATASET == "all" else "wTable_20251006.feather")
sys.path.insert(0, str(PUG))
CLIP = 230
LEGS = [(n, s) for n in ("T1", "T2", "T3") for s in ("LHS", "RHS")]
LEG_NAME = {("T1", "LHS"): "LF", ("T1", "RHS"): "RF", ("T2", "LHS"): "LM", ("T2", "RHS"): "RM", ("T3", "LHS"): "LH", ("T3", "RHS"): "RH"}
PAIRS = {"同体节左右": [("LF", "RF"), ("LM", "RM"), ("LH", "RH")],
         "同侧相邻": [("LF", "LM"), ("LM", "LH"), ("RF", "RM"), ("RM", "RH")],
         "同侧前后（T1–T3）": [("LF", "LH"), ("RF", "RH")]}
EXPECT = {"同体节左右": 180, "同侧相邻": 180, "同侧前后（T1–T3）": 0}


def peak_phase(x, y, fs=1000.0):
    x, y = x - x.mean(), y - y.mean()
    X, Y = np.fft.rfft(x), np.fft.rfft(y)
    f = np.fft.rfftfreq(len(x), 1 / fs)
    band = (f >= 2) & (f <= 30)
    k = np.where(band)[0][np.argmax((np.abs(X) * np.abs(Y))[band])]
    fx = f[band][np.argmax(np.abs(X)[band])]; fy = f[band][np.argmax(np.abs(Y)[band])]
    return float(np.degrees(np.angle(X[k] * np.conj(Y[k])))), float(fx), float(fy)


def main():
    import jax
    import jax.numpy as jnp
    from src.utils.sim_utils import neuron_oscillation_score
    score_all = jax.jit(jax.vmap(neuron_oscillation_score, in_axes=(0, None)))
    wt = pd.read_feather(TABLE)
    S = json.loads((OUT / "summary.json").read_text())
    res = {}
    for cond, s in S.items():
        f = OUT / f"{cond}.npz"
        if not f.exists():
            continue
        d = np.load(f)
        R_all, sel = d["R_sel"], d["sel_index"]
        pos = {int(i): k for k, i in enumerate(sel)}
        legmn = {leg: [pos[i] for i in wt.index[(wt["class"] == "motor neuron") & (wt.somaNeuromere == leg[0]) & (wt.somaSide == leg[1])] if i in pos] for leg in LEGS}
        e1 = {LEG_NAME[(wt.somaNeuromere[i], wt.somaSide[i])]: pos[i] for i in wt.index[wt.type == "IN17A001"]}
        step = wt["step contribution"].fillna("")
        leg_rows, phases, swst = {LEG_NAME[l]: [] for l in LEGS}, {}, []
        for rep in range(R_all.shape[0]):
            R = R_all[rep].astype(np.float32)[:, CLIP:]
            osc_net = s["runs"][rep]["oscillating"]
            sc, fr = score_all(jnp.asarray(R), 0.05)
            sc, fr = np.asarray(sc), np.asarray(fr) / 0.001
            for leg in LEGS:
                ix = legmn[leg]
                act = [k for k in ix if R[k].max() > 1]
                ls = float(np.mean(sc[act])) if act else 0.0
                good = [k for k in act if sc[k] >= 0.5]
                leg_rows[LEG_NAME[leg]].append(dict(active=len(act), score=ls, freq=float(np.median(fr[good])) if good else None))
                ids = [int(sel[k]) for k in ix]
                sw = R[[pos[i] for i in ids if step[i] == "swing"]].sum(axis=0) if ids else np.zeros(R.shape[1])
                stc = R[[pos[i] for i in ids if step[i] == "stance"]].sum(axis=0) if ids else np.zeros(R.shape[1])
                if osc_net and sw.std() > 1e-6 and stc.std() > 1e-6:
                    swst.append(float(np.corrcoef(sw, stc)[0, 1]))
            if not osc_net:
                continue
            ok = {leg: (R[k].max() > 1 and sc[k] >= 0.5) for leg, k in e1.items()}
            for group, pairs in PAIRS.items():
                for i, j in pairs:
                    if ok.get(i) and ok.get(j):
                        ph, fi, fj = peak_phase(R[e1[i]], R[e1[j]])
                        if abs(fi - fj) <= 1:
                            phases.setdefault(f"{i}-{j}", []).append(ph)
        legs_sum = {}
        for leg, rows in leg_rows.items():
            fq = [r["freq"] for r in rows if r["freq"]]
            legs_sum[leg] = dict(active_mean=round(float(np.mean([r["active"] for r in rows])), 1),
                                 frac_leg_oscillating=round(float(np.mean([r["score"] >= 0.5 for r in rows])), 2),
                                 freq_median=round(float(np.median(fq)), 2) if fq else None)
        ph_sum = {}
        for group, pairs in PAIRS.items():
            for i, j in pairs:
                v = phases.get(f"{i}-{j}", [])
                if v:
                    z = np.exp(1j * np.radians(v)).mean()
                    ph_sum[f"{i}-{j}"] = dict(group=group, n=len(v), circ_mean_deg=round(float(np.degrees(np.angle(z))), 1), R=round(float(abs(z)), 2), expect_deg=EXPECT[group])
                else:
                    ph_sum[f"{i}-{j}"] = dict(group=group, n=0, circ_mean_deg=None, R=None, expect_deg=EXPECT[group])
        res[cond] = dict(frac_oscillating=s["frac_oscillating"], median_freq_hz=s["median_freq_hz"], reps=s["reps"],
                         active_all_median=int(np.median([r["n_active_all_1hz"] for r in s["runs"]])),
                         n_runaway=int(sum(r["n_active_all_1hz"] >= 2000 for r in s["runs"])),
                         active_legmn_median=int(np.median([r["n_active_legmn_1hz"] for r in s["runs"]])),
                         stim_rate_median=[round(float(np.median([r["stim_rate_hz"][k] for r in s["runs"]])), 1) for k in range(len(s["stim_index"]))],
                         legs=legs_sum, e1_phase=ph_sum,
                         swing_stance_corr_median=round(float(np.median(swst)), 2) if swst else None, n_swing_stance=len(swst))
        o = res[cond]
        print(f"\n{cond}: 振荡 {o['frac_oscillating']}  失控 {o['n_runaway']}/{o['reps']}  频率 {o['median_freq_hz']} Hz  全网活跃中位 {o['active_all_median']}  腿部运动神经元活跃中位 {o['active_legmn_median']}  刺激神经元 {o['stim_rate_median']} Hz  摆动-支撑相关 {o['swing_stance_corr_median']}（{o['n_swing_stance']}）")
        print("  每条腿：" + "  ".join(f"{k} 活跃 {v['active_mean']} 振荡 {v['frac_leg_oscillating']} {v['freq_median']} Hz" for k, v in legs_sum.items()))
        print("  E1 相位：" + "  ".join(f"{k} {v['circ_mean_deg']}°(R {v['R']}, n {v['n']}, 预期 {v['expect_deg']}°)" for k, v in ph_sum.items()))
    (OUT / "analysis.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
