#!/usr/bin/env python
"""脑连接组里那些我们没用上的感觉通道，能不能到达运动输出？

起因（2026-09-19 用户提的原则）：「果蝇看到的任何物体都该由它大脑自行决策，
我们绝不写死判断逻辑，只负责提供必需的物理量（触感、冷热……）」。
按这条原则给了「触角碰到围栏 → JO」之后，果蝇**完全没反应**（贴墙率 85.6% → 85.6%）——
因为 JO 在这个子回路里只通到梳理指令 aDN1，不通到转向（DNa）或逃逸（DNp01）。

所以先回答一个前置问题：**脑连接组里还有哪些感觉通道，它们几跳能到运动输出？**
能到的才值得重裁子回路；到不了的，给了物理量也不会有行为。

只读，约 2 分钟。输出 results/dodge/sensor_reach.json
"""
import json
from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT / "external" / "fly-brain"
ANNOT = ROOT / "external" / "flywire_annotations" / "Supplemental_file1_neuron_annotations.tsv"
WMIN = 3                      # 与子回路同一口径：只走 ≥3 个突触的边
MAXHOP = 4

comp = pd.read_csv(REPO / "data" / "2025_Completeness_783.csv", index_col=0)
fids = comp.index.to_numpy()
fid2i = {int(f): i for i, f in enumerate(fids)}
N = len(fids)
con = pd.read_parquet(REPO / "data" / "2025_Connectivity_783.parquet")
w = con["Connectivity"].to_numpy() if "Connectivity" in con else np.abs(con["Excitatory x Connectivity"].to_numpy())
keep = w >= WMIN
pre = con["Presynaptic_Index"].to_numpy()[keep]
post = con["Postsynaptic_Index"].to_numpy()[keep]
print(f"{N:,} 个神经元，≥{WMIN} 突触的边 {keep.sum():,} 条")

order = np.argsort(pre, kind="stable")
pre_s, post_s = pre[order], post[order]
starts = np.searchsorted(pre_s, np.arange(N + 1))

ann = pd.read_csv(ANNOT, sep="\t", low_memory=False,
                  usecols=["root_id", "super_class", "cell_class", "cell_sub_class", "cell_type", "side"]).drop_duplicates("root_id")
ann = ann[ann.root_id.isin(fid2i)]

TARGETS = {"DNa01": ["DNa01"], "DNa02": ["DNa02"], "DNp01（巨纤维）": ["DNp01"],
           "MDN（后退）": ["MDN"], "aDN1（梳理）": ["DNg62"], "MN9（伸喙）": ["CB0701"]}
tgt_idx = {k: [fid2i[int(r)] for r, t in zip(ann.root_id, ann.cell_type) if t in v] for k, v in TARGETS.items()}

def bfs(src):
    """从一组源出发的最短跳数（沿突触方向）。"""
    d = np.full(N, -1, np.int8)
    q = deque()
    for s in src:
        d[s] = 0; q.append(s)
    while q:
        u = q.popleft()
        if d[u] >= MAXHOP:
            continue
        for k in range(starts[u], starts[u + 1]):
            v = post_s[k]
            if d[v] < 0:
                d[v] = d[u] + 1; q.append(v)
    return d

SENSORS = {}
sens = ann[ann.super_class == "sensory"]
for sc, g in sens.groupby("cell_sub_class"):
    ids = [fid2i[int(r)] for r in g.root_id]
    if len(ids) >= 10:
        SENSORS[str(sc)] = ids
for cc in ("thermosensory", "hygrosensory"):
    ids = [fid2i[int(r)] for r in sens.root_id[sens.cell_class == cc]]
    if ids:
        SENSORS[cc] = ids

out = {"wmin": WMIN, "max_hop": MAXHOP, "n_neurons": int(N), "sensors": {}}
print(f"\n{'感觉通道':26s}{'数量':>6s}" + "".join(f"{k:>16s}" for k in TARGETS))
for name, ids in sorted(SENSORS.items(), key=lambda x: -len(x[1])):
    d = bfs(ids)
    row = {}
    for t, idxs in tgt_idx.items():
        hops = [int(d[i]) for i in idxs if d[i] >= 0]
        row[t] = min(hops) if hops else None
    out["sensors"][name] = {"n": len(ids), "hops": row}
    print(f"{name:26s}{len(ids):6d}" + "".join(f"{(row[k] if row[k] is not None else '—'):>16}" for k in TARGETS))

(ROOT / "results/dodge/sensor_reach.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print("\n→ results/dodge/sensor_reach.json")
