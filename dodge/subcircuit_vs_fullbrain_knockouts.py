#!/usr/bin/env python
"""游戏子回路 vs 全脑：同一批神经元，在糖通路和水通路上分别有多像？

【探索性 · 事后分析】：是先看到 Phantom 在两边都让 MN9 翻倍，才想到算这个的。

口径（两侧、两条通路**完全一致**，这一点是第二版才做到的）：
  - 全脑：`dodge/measure_neurons_fullbrain.py`（138,639 神经元，糖 50 Hz / 水 160 Hz，
    把该类型列出的全部 ID 一起切断传出突触，零参照中位数归一化，前 6 个实现）。
  - 子回路：`dodge/measure_neurons.js`（4,599 神经元，颗粒钉在头前持续接触，3 个种子，取后 1.25 s 平均）。
  第一版曾经把糖的未归一化值和水的归一化值放在一起比，属于口径混用，已更正；
  第一版还只覆盖 6 个在论文里有命名的类型，现在 10 个全覆盖。
输出 results/dodge/subcircuit_vs_fullbrain_knockouts.json
用法：python dodge/subcircuit_vs_fullbrain_knockouts.py
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "results/"


def spearman(a, b):
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    return round(float(np.corrcoef(ra, rb)[0, 1]), 3)


def main():
    fb = json.loads((R / "dodge/neuron_ratios_fullbrain.json").read_text())["neurons"]
    rows = [r for r in fb if None not in (r["full_sugar"], r["full_water"], r["game_sugar"], r["game_water"])]
    fs = np.array([r["full_sugar"] for r in rows]); gs = np.array([r["game_sugar"] for r in rows])
    fw = np.array([r["full_water"] for r in rows]); gw = np.array([r["game_water"] for r in rows])
    print(f"{'神经元':10s} {'全脑糖':>7s} {'游戏糖':>7s} {'全脑水':>7s} {'游戏水':>7s}")
    for r in rows:
        print(f"{r['key']:10s} {r['full_sugar']:7.2f} {r['game_sugar']:7.2f} {r['full_water']:7.2f} {r['game_water']:7.2f}")
    out = dict(note="探索性事后分析；全脑与子回路两侧口径一致（见脚本头部）", n=len(rows),
               rows=[{k: r[k] for k in ("key", "cell_type", "full_sugar", "game_sugar", "full_water", "game_water")} for r in rows],
               sugar=dict(pearson=round(float(np.corrcoef(fs, gs)[0, 1]), 3), spearman=spearman(fs, gs),
                          median_abs_diff=round(float(np.median(np.abs(fs - gs))), 3)),
               water=dict(pearson=round(float(np.corrcoef(fw, gw)[0, 1]), 3), spearman=spearman(fw, gw),
                          median_abs_diff=round(float(np.median(np.abs(fw - gw))), 3)))
    # 水这一列有 Phantom 一个 3.02 的极端值，单独报一份剔除它的，避免结论被一个点撑起来
    keep = [i for i, r in enumerate(rows) if r["key"] != "Phantom"]
    out["water_without_phantom"] = dict(
        n=len(keep), pearson=round(float(np.corrcoef(fw[keep], gw[keep])[0, 1]), 3),
        spearman=spearman(fw[keep], gw[keep]))
    out["sugar_without_phantom"] = dict(
        n=len(keep), pearson=round(float(np.corrcoef(fs[keep], gs[keep])[0, 1]), 3),
        spearman=spearman(fs[keep], gs[keep]))
    print(f"\nn = {len(rows)}")
    for k in ("sugar", "water"):
        v = out[k]
        print(f"{'糖' if k == 'sugar' else '水'}：Pearson {v['pearson']:+.3f}，Spearman {v['spearman']:+.3f}，中位绝对差 {v['median_abs_diff']:.2f}")
    print(f"剔除 Phantom（水那列唯一的极端值 3.02）后：糖 Pearson {out['sugar_without_phantom']['pearson']:+.3f}"
          f"（Spearman {out['sugar_without_phantom']['spearman']:+.3f}），"
          f"水 Pearson {out['water_without_phantom']['pearson']:+.3f}（Spearman {out['water_without_phantom']['spearman']:+.3f}）")
    dst = R / "dodge/subcircuit_vs_fullbrain_knockouts.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("\n写入", dst)


if __name__ == "__main__":
    main()
