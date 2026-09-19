#!/usr/bin/env python3
"""把「解剖锚定的映射」和原来 8 种朝向放在一起比（离线，只读）。

判据照抄 §18，写在 results/vision/lattice_prediction.md 里（跑之前写的）：
  C1 逼近 > 远离        C2 逼近 > 远距平移        C3 逼近 < 近距平移
指标 = LPLC2 在 0.5–0.95 s 的平均发放率（两侧取和）。

**不预先声明锚定会更好** —— 要报告的是它落在原来 8 个朝向分布里的什么位置。

用法：python3 vision/lattice_compare.py
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
csv = ROOT / "results/vision/connectome_responses_reps.csv"
df = pd.read_csv(csv)
df["lplc2"] = df["LPLC2_left_late_hz"] + df["LPLC2_right_late_hz"]

def label(r):
    if str(r.swap) == "anchor":
        return f"解剖锚定 ×{r.sx:g}"
    return f"k={int(r.orient)} swap={r.swap} sx={int(r.sx):+d} sy={int(r.sy):+d}"

df["映射"] = df.apply(label, axis=1)
STIM = {"loom_L": "逼近", "loom_R": "逼近(右)", "recede_L": "远离",
        "translate_near_L": "近距平移", "translate_far_L": "远距平移"}
# 刺激名写错会让 C2/C3 静默变成 NaN/False（这个坑刚踩过：trans_near_L vs translate_near_L）。
# AGENTS.md 记过这类失败：分析不能在数据缺失时悄悄降级。
seen = set(df.stim)
missing = [s for s in STIM if s not in seen]
extra = [s for s in seen if s not in STIM]
assert not missing, f"CSV 里缺这些刺激：{missing}（有的是 {sorted(seen)}）"
assert not extra, f"CSV 里有本脚本不认识的刺激：{extra}"
have = list(STIM)
print("刺激集合：", ", ".join(f"{s}({STIM[s]})" for s in have))
print(f"重复次数：{df.rep.nunique()}；映射数：{df.orient.nunique()}\n")

rows = []
for k, g in df.groupby("orient"):
    m = {s: g[g.stim == s].lplc2.mean() for s in have}
    sd = {s: g[g.stim == s].lplc2.std() for s in have}
    if not all(s in m for s in ("loom_L", "recede_L")):
        continue
    c1 = m["loom_L"] > m["recede_L"]
    c2 = m.get("translate_far_L") is not None and m["loom_L"] > m["translate_far_L"]
    c3 = m.get("translate_near_L") is not None and m["loom_L"] < m["translate_near_L"]
    rows.append(dict(orient=int(k), 映射=g.映射.iloc[0], 锚定=str(g.swap.iloc[0]) == "anchor",
                     逼近=m["loom_L"], 逼近sd=sd["loom_L"], 远离=m["recede_L"],
                     近距平移=m.get("translate_near_L", np.nan), 远距平移=m.get("translate_far_L", np.nan),
                     C1=bool(c1), C2=bool(c2), C3=bool(c3)))
R = pd.DataFrame(rows).sort_values("orient")
print("映射                      逼近    远离  近距平移 远距平移   C1  C2  C3")
for _, r in R.iterrows():
    print(f"{r.映射:24s} {r.逼近:6.2f}±{r.逼近sd:.2f} {r.远离:6.2f} {r.近距平移:8.2f} {r.远距平移:8.2f}"
          f"   {'✓' if r.C1 else '✗'}   {'✓' if r.C2 else '✗'}   {'✓' if r.C3 else '✗'}")

old = R[~R.锚定]
new = R[R.锚定]
print(f"\n原来 8 种朝向：C1 {old.C1.sum()}/8   C2 {old.C2.sum()}/8   C3 {old.C3.sum()}/8")
print(f"  逼近响应的朝向间标准差 {old.逼近.std():.3f} Hz，重复间标准差中位 {old.逼近sd.median():.3f} Hz"
      f"（比值 {old.逼近.std() / max(old.逼近sd.median(), 1e-9):.1f}×）")
for _, r in new.iterrows():
    pctl = (old.逼近 < r.逼近).mean() * 100
    print(f"\n{r.映射}：逼近 {r.逼近:.3f} Hz —— 落在原来 8 个朝向的第 {pctl:.0f} 百分位"
          f"（范围 {old.逼近.min():.3f}–{old.逼近.max():.3f}）")
    print(f"  C1 {'✓' if r.C1 else '✗'}  C2 {'✓' if r.C2 else '✗'}  C3 {'✓' if r.C3 else '✗'}")

out = {"判据": {"C1": "逼近 > 远离", "C2": "逼近 > 远距平移", "C3": "逼近 < 近距平移"},
       "指标": "LPLC2 左+右 在 0.5–0.95 s 的平均发放率（Hz）",
       "各映射": R.to_dict("records"),
       "原8朝向": {"C1": int(old.C1.sum()), "C2": int(old.C2.sum()), "C3": int(old.C3.sum()),
                   "朝向间SD": float(old.逼近.std()), "重复间SD中位": float(old.逼近sd.median())}}
(ROOT / "results/vision/lattice_compare.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float))
print("\n→ results/vision/lattice_compare.json")
