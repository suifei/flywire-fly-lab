#!/usr/bin/env python
"""
第 2 步的稳健性检查：同一条件重复跑几次，第 9.2 节那些“8/8、7/8、0/8”还站得住吗？

背景：`vision/connectome_from_flyvis.py` 没有调用 b2.seed()，所以每次 device.run 的泊松噪声本来就互相独立；
但原来每个刺激 × 朝向只跑了 1 次，没法知道这些计数里有多少是噪声。现在每个条件重复 3 次。

事先写定（写在跑完之前）：
  指标沿用第 9.2 节事先声明的那个：刺激开始后 0.5–0.95 s，左侧 LPLC2 的平均发放率（Hz）。
  三项比较，每项在 8 种格子朝向上各判一次：逼近 > 远离、逼近 > 远距平移、逼近 > 近距平移。
  对每一次重复各算一遍这三个计数（0–8），报告 3 次重复的计数是否一致；再报告每个条件跨重复的均值 ± 标准差，
  以及“重复之间的标准差”与“朝向之间的标准差”哪个大——后者是原分析当作变异来源的东西。
输出 results/vision/repeat_check.json
用法（任意带 pandas 的环境）：python vision/repeat_check.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
VIS = ROOT / "results" / "vision"
METRIC = "LPLC2_left_late_hz"
CMP = [("逼近 > 远离", "loom_L", "recede_L"), ("逼近 > 远距平移", "loom_L", "translate_far_L"),
       ("逼近 > 近距平移", "loom_L", "translate_near_L")]


def main():
    df = pd.read_csv(VIS / "connectome_responses_reps.csv")
    reps = sorted(df.rep.unique())
    ors = sorted(df.orient.unique())
    out = dict(metric=METRIC, n_repeats=len(reps), n_orientations=len(ors), counts={}, per_condition={}, variability={})
    print(f"重复 {len(reps)} 次 × {len(ors)} 种朝向 × {df.stim.nunique()} 个刺激\n")
    for name, a, b in CMP:
        per_rep = []
        for r in reps:
            d = df[df.rep == r].set_index(["stim", "orient"])[METRIC]
            per_rep.append(int(sum(d[(a, k)] > d[(b, k)] for k in ors)))
        out["counts"][name] = dict(per_repeat=per_rep, all_equal=bool(len(set(per_rep)) == 1))
        print(f"{name:14s} 每次重复的计数（满分 {len(ors)}）：{per_rep}" + ("  ← 三次一致" if len(set(per_rep)) == 1 else "  ← 有变化"))
    print()
    for s in sorted(df.stim.unique()):
        g = df[df.stim == s]
        per_or = g.groupby("orient")[METRIC]
        within = float(np.mean([v.std(ddof=1) for _, v in per_or]))          # 同一朝向、跨重复
        across = float(g.groupby("rep")[METRIC].apply(lambda v: v.std(ddof=1)).mean())  # 同一次重复、跨朝向
        m = float(g[METRIC].mean())
        out["per_condition"][s] = dict(mean_hz=round(m, 2), sd_between_repeats=round(within, 2), sd_between_orientations=round(across, 2))
        print(f"{s:18s} 均值 {m:6.2f} Hz | 重复之间 SD {within:5.2f} | 朝向之间 SD {across:5.2f}")
    out["variability"] = dict(
        median_sd_between_repeats=round(float(np.median([v["sd_between_repeats"] for v in out["per_condition"].values()])), 3),
        median_sd_between_orientations=round(float(np.median([v["sd_between_orientations"] for v in out["per_condition"].values()])), 3))
    gf = df[df.stim == "loom_L"]["DNp01_left_late_hz"]
    out["gf_baseline_hz"] = dict(mean=round(float(gf.mean()), 1), sd=round(float(gf.std(ddof=1)), 1))
    (VIS / "repeat_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("\n写入", VIS / "repeat_check.json")


if __name__ == "__main__":
    main()
