#!/usr/bin/env python
"""五感补全的前置问题：嗅觉、信息素、听觉、内感受（ISN，感知饥渴）几跳能到我们的六个运动输出？
sensor_reach.py 按 cell_sub_class 分组，嗅觉的子类别是空的，所以没算进去；ISN 是 central 不是 sensory。只读，约 1 分钟。
另外列出：嗅觉 2 跳之内能到哪些**下行神经元**（按到达的突触权重排序）——闻到东西之后，连接组里最先被推动的是哪些行为指令。
输出 results/dodge/sensor_reach_v4.json
"""
import json
from collections import deque
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parent.parent; REPO = ROOT / "external/fly-brain"
ANNOT = ROOT / "external/flywire_annotations/Supplemental_file1_neuron_annotations.tsv"
WMIN, MAXHOP = 3, 4
comp = pd.read_csv(REPO / "data/2025_Completeness_783.csv", index_col=0); fids = comp.index.to_numpy(); fid2i = {int(f): i for i, f in enumerate(fids)}; N = len(fids)
con = pd.read_parquet(REPO / "data/2025_Connectivity_783.parquet")
w = con["Connectivity"].to_numpy(); keep = w >= WMIN
pre = con["Presynaptic_Index"].to_numpy()[keep]; post = con["Postsynaptic_Index"].to_numpy()[keep]; ww = w[keep]
order = np.argsort(pre, kind="stable"); pre_s, post_s, w_s = pre[order], post[order], ww[order]; starts = np.searchsorted(pre_s, np.arange(N + 1))
ann = pd.read_csv(ANNOT, sep="\t", low_memory=False, usecols=["root_id", "super_class", "cell_class", "cell_sub_class", "cell_type", "side"]).drop_duplicates("root_id")
ann = ann[ann.root_id.isin(fid2i)]; ann["i"] = ann.root_id.map(fid2i)
def bfs(src):
    dist = np.full(N, 99, dtype=np.int16); dist[src] = 0; dq = deque(src)
    while dq:
        u = dq.popleft()
        if dist[u] >= MAXHOP: continue
        for v in post_s[starts[u]:starts[u + 1]]:
            if dist[v] == 99: dist[v] = dist[u] + 1; dq.append(v)
    return dist
OUT = {"DNa01": ["DNa01"], "DNa02": ["DNa02"], "DNp01（巨纤维）": ["DNp01"], "MDN（后退）": ["MDN"], "aDN1（梳理）": ["DNg62"], "MN9（伸喙）": ["CB0701"]}
out_idx = {k: ann[ann.cell_type.isin(v)].i.to_numpy() for k, v in OUT.items()}
GROUPS = {
  "嗅觉（全部 ORN）": ann[(ann.super_class == "sensory") & (ann.cell_class == "olfactory") & (ann.cell_sub_class != "pheromone")],
  "嗅觉 · ORN_DM1（醋，吸引）": ann[ann.cell_type == "ORN_DM1"], "嗅觉 · ORN_DA2（土臭素，厌恶）": ann[ann.cell_type == "ORN_DA2"],
  "信息素": ann[ann.cell_sub_class == "pheromone"], "听觉": ann[ann.cell_sub_class == "auditory"],
  "内感受 ISN（饥渴）": ann[ann.cell_type == "ISN"],
}
res = {"wmin": WMIN, "max_hop": MAXHOP, "groups": {}}
dn = ann[ann.super_class == "descending"]
for name, g in GROUPS.items():
    src = g.i.to_numpy(); d = bfs(list(src))
    hops = {k: (int(d[v].min()) if len(v) and d[v].min() < 99 else None) for k, v in out_idx.items()}
    # 2 跳之内到达的下行神经元类型：按"1 跳直接突触数 + 2 跳路径上的最小突触数之和"粗排
    direct = np.zeros(N)
    for u in src: np.add.at(direct, post_s[starts[u]:starts[u + 1]], w_s[starts[u]:starts[u + 1]])
    second = np.zeros(N); mids = np.nonzero(direct > 0)[0]
    for u in mids: np.add.at(second, post_s[starts[u]:starts[u + 1]], np.minimum(w_s[starts[u]:starts[u + 1]], direct[u]))
    score = direct + second; t = dn.assign(score=score[dn.i.to_numpy()], hop=d[dn.i.to_numpy()])
    top = t[t.hop <= 2].groupby("cell_type").agg(score=("score", "sum"), hop=("hop", "min"), n=("i", "size")).sort_values("score", ascending=False).head(10)
    res["groups"][name] = {"n": int(len(src)), "hops": hops, "n_descending_within_2_hops": int((t.hop <= 2).sum()),
                           "top_descending": [dict(cell_type=k, hop=int(r.hop), n=int(r.n), score=float(round(r.score, 1))) for k, r in top.iterrows()]}
    print(f"{name:26} n={len(src):5d}  跳数 {hops}\n{'':28}2 跳内下行神经元 {(t.hop <= 2).sum()} 个；最强的：" + "、".join(f"{k}({int(r.hop)}跳)" for k, r in top.head(6).iterrows()))
json.dump(res, open(ROOT / "results/dodge/sensor_reach_v4.json", "w"), ensure_ascii=False, indent=1)
