#!/usr/bin/env python
"""
第 2 步分析：LPLC2 对逼近物体的反应是否强于平移（及远离）物体？
读取 results/vision/connectome_responses.csv 与 rates_<stim>_o<k>.npz，
按“8 种格子朝向”分别比较，报告中位数与范围，并画时间曲线。

输出：results/vision/summary.json、results/vision/lplc2_looming_vs_translation.png
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
VIS = ROOT / "results" / "vision"
STIMS = ["loom_L", "translate_near_L", "translate_far_L", "recede_L", "loom_R"]
LABEL = {"loom_L": "左侧逼近", "loom_R": "右侧逼近", "recede_L": "左侧远离", "translate_near_L": "左侧近距平移", "translate_far_L": "左侧远距平移"}
GROUPS = ["LPLC2", "LC4", "DNp01", "DNa01", "DNa02"]


def main():
    df = pd.read_csv(VIS / "connectome_responses.csv")
    n_or = df.orient.nunique()
    out = {"orientations": int(n_or), "stimuli": {}, "ratios": {}}
    print(f"每个刺激 × {n_or} 种格子朝向；数值 = 刺激后 0.5–0.95 s 的平均发放率（Hz），[朝向间最小–最大]\n")
    for s in STIMS:
        g = df[df.stim == s]
        rec = {}
        line = []
        for grp in GROUPS:
            for side in ("left", "right"):
                v = g[f"{grp}_{side}_late_hz"].to_numpy()
                pk = g[f"{grp}_{side}_peak_hz"].to_numpy()
                rec[f"{grp}_{side}"] = dict(late_median=float(np.median(v)), late_min=float(v.min()), late_max=float(v.max()),
                                            peak_median=float(np.median(pk)))
                if grp in ("LPLC2", "LC4", "DNp01"):
                    line.append(f"{grp}{'左' if side == 'left' else '右'} {np.median(v):6.1f} [{v.min():.0f}–{v.max():.0f}]")
        rec["input_hz_mean"] = float(g.input_hz_mean.mean())
        out["stimuli"][s] = rec
        print(f"{LABEL[s]:8s} 输入均值 {rec['input_hz_mean']:5.1f} Hz | " + " | ".join(line))

    # 逐朝向比值：同侧（左）LPLC2 / LC4 / GF 的后段发放率，逼近 ÷ 对照
    print("\n逐朝向比较（左侧刺激，左侧神经元后段发放率）：")
    for grp in ("LPLC2", "LC4", "DNp01"):
        key = f"{grp}_left_late_hz"
        piv = df.pivot(index="orient", columns="stim", values=key)
        for ctrl in ("translate_near_L", "translate_far_L", "recede_L"):
            diff = piv["loom_L"] - piv[ctrl]
            wins = int((diff > 0).sum())
            ratio = (piv["loom_L"] + 1) / (piv[ctrl] + 1)
            out["ratios"][f"{grp}_loom_vs_{ctrl}"] = dict(orient_wins=wins, n=int(len(diff)), ratio_median=float(ratio.median()),
                                                         ratio_min=float(ratio.min()), ratio_max=float(ratio.max()),
                                                         diff_median_hz=float(diff.median()))
            print(f"  {grp:6s} 逼近 vs {LABEL[ctrl]:6s}：{wins}/{len(diff)} 个朝向逼近更强；(逼近+1)/(对照+1) 中位 {ratio.median():.2f} [{ratio.min():.2f}–{ratio.max():.2f}]，差值中位 {diff.median():+.1f} Hz")
    # 侧化：左侧逼近时左/右 LPLC2，右侧逼近时反之
    lat = {}
    for s, same, other in (("loom_L", "left", "right"), ("loom_R", "right", "left")):
        g = df[df.stim == s]
        w = int((g[f"LPLC2_{same}_late_hz"] > g[f"LPLC2_{other}_late_hz"]).sum())
        lat[s] = dict(same_side_wins=w, n=int(len(g)))
        print(f"  侧化 {LABEL[s]}：{w}/{len(g)} 个朝向同侧 LPLC2 > 对侧")
    out["lateralization"] = lat

    # —— 探索性（看过时间曲线之后才加的）指标：不能替代上面事先声明的比较 ——
    print("\n【探索性、事后指标】接近碰撞的最后 150 ms（0.80–0.95 s）峰值，以及刺激前基线期（−0.18–0 s）平均发放率：")
    expl = {}
    for grp in ("LPLC2_left", "LC4_left", "DNp01_left"):
        row = {}
        for s in ("loom_L", "translate_near_L", "translate_far_L", "recede_L"):
            pk, base = [], []
            for k in range(n_or):
                c = np.load(VIS / f"rates_{s}_o{k}.npz"); t = c["t"]
                pk.append(c[grp][(t >= 0.80) & (t < 0.95)].max()); base.append(c[grp][(t >= -0.18) & (t < 0)].mean())
            row[s] = dict(end_peak_median=float(np.median(pk)), end_peak_min=float(np.min(pk)), end_peak_max=float(np.max(pk)),
                          baseline_median=float(np.median(base)))
        wins = {ctrl: int(sum(
            np.load(VIS / f"rates_loom_L_o{k}.npz")[grp][(np.load(VIS / f"rates_loom_L_o{k}.npz")["t"] >= 0.80) & (np.load(VIS / f"rates_loom_L_o{k}.npz")["t"] < 0.95)].max()
            > np.load(VIS / f"rates_{ctrl}_o{k}.npz")[grp][(np.load(VIS / f"rates_{ctrl}_o{k}.npz")["t"] >= 0.80) & (np.load(VIS / f"rates_{ctrl}_o{k}.npz")["t"] < 0.95)].max()
            for k in range(n_or))) for ctrl in ("translate_near_L", "translate_far_L", "recede_L")}
        row["loom_end_peak_wins"] = wins
        expl[grp] = row
        print(f"  {grp:11s} 末段峰值中位：逼近 {row['loom_L']['end_peak_median']:5.1f} / 近距平移 {row['translate_near_L']['end_peak_median']:5.1f} / "
              f"远距平移 {row['translate_far_L']['end_peak_median']:5.1f} / 远离 {row['recede_L']['end_peak_median']:5.1f} Hz；"
              f"逼近更强的朝向数 {wins['translate_near_L']}/{wins['translate_far_L']}/{wins['recede_L']} (/8)；"
              f"基线期中位 {row['loom_L']['baseline_median']:.1f} Hz")
    out["exploratory_end_window"] = expl
    (VIS / "summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))

    # 时间曲线：左侧 LPLC2，各刺激在 8 个朝向上的中位数与范围
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["PingFang SC", "Hiragino Sans GB", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2), sharex=True)
    colors = {"loom_L": "#2a78d6", "translate_near_L": "#eb6834", "translate_far_L": "#e8a13d", "recede_L": "#7c8884"}
    for ax, grp in zip(axes, ("LPLC2_left", "LC4_left", "DNp01_left")):
        for s in ("loom_L", "translate_near_L", "translate_far_L", "recede_L"):
            curves = [np.load(VIS / f"rates_{s}_o{k}.npz") for k in range(n_or)]
            t = curves[0]["t"]; Y = np.stack([c[grp] for c in curves])
            ax.plot(t, np.median(Y, 0), color=colors[s], lw=2, label=LABEL[s])
            ax.fill_between(t, Y.min(0), Y.max(0), color=colors[s], alpha=0.15, lw=0)
        ax.axvline(0, color="k", lw=0.8, ls=":")
        ax.set_title(f"{grp.replace('_left', '（左侧）').replace('DNp01', '巨纤维 DNp01')}")
        ax.set_xlabel("刺激开始后时间 (s)"); ax.set_ylabel("发放率 (Hz)")
    axes[0].legend(fontsize=9)
    fig.suptitle("复眼 → flyvis → FlyWire 全脑 LIF：线为 8 种格子朝向的中位数，阴影为范围")
    fig.tight_layout(); fig.savefig(VIS / "lplc2_looming_vs_translation.png", dpi=130)
    print("\n写入", VIS / "summary.json", "与", VIS / "lplc2_looming_vs_translation.png")


if __name__ == "__main__":
    main()
