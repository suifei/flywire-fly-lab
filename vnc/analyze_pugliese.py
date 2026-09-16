#!/usr/bin/env python
"""
汇总 vnc/run_pugliese.py 的结果（指标运行前写定）：
  * 每个条件：振荡副本比例、网络振荡得分中位、频率中位；活跃运动神经元（最大发放率 > 1 Hz，丢弃前 230 ms）按 侧别 × 模块 计数（16 个副本合计）。
  * 节律结构（只看振荡副本）：同一条腿 swing 模块总和 与 stance 模块总和 的零滞后相关（< 0 表示摆动/支撑交替）；
    左腿与右腿同一迈步相（swing 或 stance）的相关（< 0 表示左右交替，三足步态里左右前腿应交替）。
    某一侧/模块整段为 0 时记为 None。
输出 results/vnc/pugliese/analysis.json
用法（vnc-sim 或 flygym 环境）：python vnc/analyze_pugliese.py
"""
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PR = ROOT / "results" / "vnc" / "pugliese"
CLIP = 230


def corr(a, b):
    if a.std() < 1e-6 or b.std() < 1e-6:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def main():
    S = json.loads((PR / "summary.json").read_text())
    tab = pd.read_csv(PR / "mn_table.csv", index_col=0)
    side, mod, step = tab.somaSide.to_numpy(), tab["motor module"].fillna("NA").to_numpy(), tab["step contribution"].fillna("NA").to_numpy()
    out = {}
    for cond, s in S.items():
        if not (PR / f"{cond}.npz").exists():
            continue
        R = np.load(PR / f"{cond}.npz")["R_mn"].astype(np.float32)[:, :, CLIP:]
        cnt = Counter()
        sw_st, lr = [], []
        for rep in range(R.shape[0]):
            act = R[rep].max(axis=1) > 1
            cnt.update(f"{side[i]} {mod[i]}" for i in np.where(act)[0])
            if not s["runs"][rep]["oscillating"]:
                continue
            ph = {(sd, p): R[rep][(side == sd) & (step == p)].sum(axis=0) for sd in ("LHS", "RHS") for p in ("swing", "stance")}
            for sd in ("LHS", "RHS"):
                c = corr(ph[(sd, "swing")], ph[(sd, "stance")])
                if c is not None:
                    sw_st.append(c)
            for p in ("swing", "stance"):
                c = corr(ph[("LHS", p)], ph[("RHS", p)])
                if c is not None:
                    lr.append(c)
        out[cond] = dict(frac_oscillating=s["frac_oscillating"], median_score=s["median_net_score"], median_freq_hz=s["median_freq_hz"],
                         active_mn_counts=dict(cnt.most_common()),
                         swing_vs_stance_corr_median=round(float(np.median(sw_st)), 2) if sw_st else None, n_swing_stance=len(sw_st),
                         left_vs_right_corr_median=round(float(np.median(lr)), 2) if lr else None, n_left_right=len(lr))
        o = out[cond]
        print(f"{cond:10s} 振荡 {o['frac_oscillating']:.2f}  得分 {o['median_score']}  频率 {o['median_freq_hz']} Hz  "
              f"摆动-支撑相关 {o['swing_vs_stance_corr_median']}（{o['n_swing_stance']}）  左-右相关 {o['left_vs_right_corr_median']}（{o['n_left_right']}）")
        print("           活跃运动神经元（16 副本合计）：", o["active_mn_counts"])
    (PR / "analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
