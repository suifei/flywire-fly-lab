#!/usr/bin/env python
"""导出子回路 4,599 个神经元的**真实胞体坐标**，供页面画脑图。

坐标来自公开注释表的 soma_x/y/z（缺失时退回 pos_x/y/z——那是该神经元的一个代表点，
不是胞体，导出时逐个标记出来）。**单位是体素，4×4×40 nm**，这里换算成微米。

坐标系（FlyWire/FAFB）：x 向右、y 向腹（越大越靠下）、z 是前后切片方向。
页面渲染时把 y 取反当作"上"，并按脑的包围盒居中。

用法（任一有 pandas 的环境）：python dodge/export_soma.py → results/dodge/soma.json
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ANNOT = ROOT / "external" / "flywire_annotations" / "Supplemental_file1_neuron_annotations.tsv"
SUBNAME = os.environ.get("SUB", "subcircuit_v2")          # 子回路用 SUB 环境变量切换
SUF = "" if SUBNAME == "subcircuit_v2" else "_" + SUBNAME.replace("subcircuit_", "")
SUB = json.loads((ROOT / f"results/dodge/{SUBNAME}.json").read_text())
VOX = np.array([4e-3, 4e-3, 40e-3])            # 体素 → 微米

ann = pd.read_csv(ANNOT, sep="\t", low_memory=False,
                  usecols=["root_id", "soma_x", "soma_y", "soma_z", "pos_x", "pos_y", "pos_z",
                           "cell_type", "super_class", "side", "top_nt"]).drop_duplicates("root_id").set_index("root_id")

fids = [int(f) for f in SUB["fids"]]
sub = ann.reindex(fids)
soma = sub[["soma_x", "soma_y", "soma_z"]].to_numpy(dtype=float)
pos = sub[["pos_x", "pos_y", "pos_z"]].to_numpy(dtype=float)
from_soma = ~np.isnan(soma).any(1)
xyz = np.where(from_soma[:, None], soma, pos) * VOX
ok = ~np.isnan(xyz).any(1)
xyz[~ok] = np.nanmedian(xyz[ok], 0)            # 两个都缺的放到脑中心，并在 flag 里标出来

group_of = {}
for g, idxs in SUB["groups"].items():
    for i in idxs:
        group_of[i] = g

nt_code = {"acetylcholine": 0, "glutamate": 1, "gaba": 2, "dopamine": 3, "serotonin": 4, "octopamine": 5}
out = dict(
    n=len(fids), unit="µm", source="flywire_annotations soma_x/y/z（缺失时用 pos_*），体素 4×4×40 nm 换算",
    axes="x 向右、y 向腹、z 前后（FAFB 原始方向，页面渲染时把 y 取反当上）",
    n_from_soma=int(from_soma.sum()), n_from_pos=int((~from_soma & ok).sum()), n_missing=int((~ok).sum()),
    bbox=[[round(float(v), 1) for v in xyz[ok].min(0)], [round(float(v), 1) for v in xyz[ok].max(0)]],
    xyz=[[round(float(v), 1) for v in p] for p in xyz],
    group=[group_of.get(i, "") for i in range(len(fids))],
    nt=[int(nt_code.get(str(v).lower(), 6)) for v in sub["top_nt"].to_numpy()],
    side=[("L" if s == "left" else "R" if s == "right" else "?") for s in sub["side"].astype(str)],
    cell_type=[("" if pd.isna(v) else str(v)) for v in sub["cell_type"].to_numpy()],
)
p = ROOT / f"results/dodge/soma{SUF}.json"
p.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
print(f"{out['n']} 个神经元：{out['n_from_soma']} 个有胞体坐标、{out['n_from_pos']} 个退回代表点、{out['n_missing']} 个缺失")
print(f"包围盒（µm）{out['bbox']}")
print("→", p, f"{p.stat().st_size / 1e6:.2f} MB")
