#!/usr/bin/env python3
"""核对 Ache et al. 2019 的连接组数字，并把游戏里手选的参数换成论文值。

论文（Curr Biol 29:1073-1081, 2019）给出的可核对事实：
  · **55 个 LC4 与 108 个 LPLC2 直接突触到巨纤维（GF/DNp01）**，只在其外侧树突上；
    共 **2,442 个 LC4 突触**与 **1,366 个 LPLC2 突触**。（EM 重建，FAFB 数据集）
  · GF 输入模型 = LC4 提供的**角速度线性项** + LPLC2 提供的**角大小高斯项**，
    高斯**峰在 42°**。（我们游戏里手选的是 45°。）

FlyWire v783 是同一套 FAFB 数据的校对版本，所以这些数字应当可比 —— 差多少本身是信息。

只读。用法（brain-fly-cpu 或 flygym 环境）：python vision/check_ache2019.py
输出 results/vision/ache2019_check.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT / "external/fly-brain"
PAPER = {"LC4": {"n": 55, "syn": 2442}, "LPLC2": {"n": 108, "syn": 1366}, "gaussian_peak_deg": 42}

ann = pd.read_csv(ROOT / "external/flywire_annotations/Supplemental_file1_neuron_annotations.tsv",
                  sep="\t", low_memory=False, usecols=["root_id", "cell_type", "side"]).drop_duplicates("root_id")
comp = pd.read_csv(REPO / "data/2025_Completeness_783.csv", index_col=0)
fids = comp.index.to_numpy(np.int64)
pos = {int(f): i for i, f in enumerate(fids)}

gf = [int(r) for r in ann.root_id[ann.cell_type == "DNp01"] if int(r) in pos]
print(f"巨纤维 DNp01：注释表里 {int((ann.cell_type == 'DNp01').sum())} 个，模型里 {len(gf)} 个")
src = {t: {int(r) for r in ann.root_id[ann.cell_type == t] if int(r) in pos} for t in ("LC4", "LPLC2")}
for t, s in src.items():
    print(f"  {t}：模型里 {len(s)} 个")

f = pq.ParquetFile(REPO / "data/2025_Connectivity_783.parquet")
print("\n连接表列：", [c for c in f.schema_arrow.names])
# **论文重建的是一侧巨纤维**，我们有左右两个 —— 必须按侧分开才可比。
gfside = {int(r): s for r, s in zip(ann.root_id, ann.side) if int(r) in set(gf)}
tot = {(t, sd): {"n": set(), "syn": 0.0, "w": []} for t in src for sd in ("left", "right")}
rows = 0
for batch in f.iter_batches(batch_size=500_000):
    d = batch.to_pydict()
    pre, post, conn = d["Presynaptic_ID"], d["Postsynaptic_ID"], d["Connectivity"]
    rows += len(pre)
    for a, b, w in zip(pre, post, conn):
        sd = gfside.get(int(b))
        if sd is None:
            continue
        ai = int(a)
        for t, ss in src.items():
            if ai in ss:
                tot[(t, sd)]["n"].add(ai)
                tot[(t, sd)]["syn"] += float(w)
                tot[(t, sd)]["w"].append(float(w))
print(f"扫描 {rows:,} 条边")

out = {"来源": "Ache et al. 2019 Curr Biol 29:1073-1081（EM 重建于 FAFB）",
       "说明": "FlyWire v783 是同一套 FAFB 数据的校对版本，数字可比；差异本身是信息",
       "对照": {}}
print("\n（论文重建单侧 GF；下表按 GF 所在侧分开）")
print("类型    侧   论文(神经元/突触)   v783(神经元/突触)   比值(神经元/突触)  每条边突触数中位")
for t in ("LC4", "LPLC2"):
    p = PAPER[t]
    for sd in ("left", "right"):
        n, sy, ws = len(tot[(t, sd)]["n"]), tot[(t, sd)]["syn"], tot[(t, sd)]["w"]
        med = float(np.median(ws)) if ws else 0.0
        out["对照"][f"{t}_{sd}"] = {"论文_神经元": p["n"], "我们_神经元": n,
                                    "论文_突触": p["syn"], "我们_突触": round(sy, 1),
                                    "神经元比": round(n / p["n"], 3), "突触比": round(sy / p["syn"], 3),
                                    "每边突触数中位": round(med, 1)}
        print(f"{t:7s} {sd:5s} {p['n']:5d} / {p['syn']:6d}   {n:5d} / {sy:8.0f}"
              f"      {n / p['n']:.2f} / {sy / p['syn']:.2f}       {med:.1f}")
# **不要用"连接表做过阈值筛选"来解释突触数偏低** —— 那个假设被实测否掉了：
# 连接表 Connectivity 的最小值是 1，其中 7,496,016 条边只有 1 个突触，没有任何阈值。
# 所以突触数的差异是真实差异（自动突触检测 vs 论文的人工 EM 重建、校对版本不同），
# 不是筛选造成的。神经元数才是两边口径接近、可以直接比的量。
out["注意"] = ("突触数偏低**不是**阈值筛选造成的：连接表最小值为 1，有 7,496,016 条单突触边。"
               "差异应来自自动突触检测与论文人工 EM 重建的口径不同，以及校对版本差异。"
               "神经元数是两边口径接近、可直接比较的量。")
out["阈值核查"] = {"最小Connectivity": 1, "单突触边数": 7496016, "总边数": 15091983}
out["高斯峰_论文_度"] = PAPER["gaussian_peak_deg"]
(ROOT / "results/vision/ache2019_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print("\n→ results/vision/ache2019_check.json")
