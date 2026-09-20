#!/usr/bin/env python
"""学习回路的前置问题（只读，约 1 分钟）：
  ① 强化信号：糖 / 苦 / 热 / 湿 / 触 这些感觉神经元，几跳能到多巴胺神经元（PAM = 文献里的奖赏，PPL1 = 惩罚）？各自到得了多少个？
  ② 记忆的出口：蘑菇体输出神经元（MBON）几跳能到我们的运动输出（转向 DNa01/02、巨纤维、后退 MDN、梳理 aDN1、伸喙 MN9、前进 oDN1）？
  ③ MBON 2 跳之内最强地接到哪些下行神经元？
边只算 ≥3 个突触的（与子回路同一口径）。"奖赏 / 惩罚"是文献给 PAM / PPL1 的标签，不是我们写进模型的规则。
输出 results/learn/mb_reach.json
"""
import json
from collections import deque
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parent.parent; REPO = ROOT / "external/fly-brain"
ANNOT = ROOT / "external/flywire_annotations/Supplemental_file1_neuron_annotations.tsv"
WMIN, MAXHOP = 3, 5
comp = pd.read_csv(REPO / "data/2025_Completeness_783.csv", index_col=0); fids = comp.index.to_numpy(); fid2i = {int(f): i for i, f in enumerate(fids)}; N = len(fids)
con = pd.read_parquet(REPO / "data/2025_Connectivity_783.parquet")
w = con["Connectivity"].to_numpy(); keep = w >= WMIN
pre = con["Presynaptic_Index"].to_numpy()[keep]; post = con["Postsynaptic_Index"].to_numpy()[keep]; ww = w[keep]; sg = con["Excitatory x Connectivity"].to_numpy()[keep]
order = np.argsort(pre, kind="stable"); pre_s, post_s, w_s, sg_s = pre[order], post[order], ww[order], sg[order]; starts = np.searchsorted(pre_s, np.arange(N + 1))
ann = pd.read_csv(ANNOT, sep="\t", low_memory=False, usecols=["root_id", "super_class", "cell_class", "cell_sub_class", "cell_type", "side"]).drop_duplicates("root_id")
ann = ann[ann.root_id.isin(fid2i)].copy(); ann["i"] = ann.root_id.map(fid2i)
def bfs(src):
    dist = np.full(N, 99, dtype=np.int16); dist[src] = 0; dq = deque(src)
    while dq:
        u = dq.popleft()
        if dist[u] >= MAXHOP: continue
        for v in post_s[starts[u]:starts[u + 1]]:
            if dist[v] == 99: dist[v] = dist[u] + 1; dq.append(v)
    return dist
SENS = {"糖 SUGAR（LB3）": ann[ann.cell_type == "LB3"], "苦 BITTER（LB1）": ann[ann.cell_type.isin(["LB1a,LB1d", "LB1b", "LB1c"])],
        "热 THERMO": ann[ann.cell_class == "thermosensory"], "湿 HYGRO": ann[ann.cell_class == "hygrosensory"],
        "触 TOUCH（头部刚毛）": ann[ann.cell_sub_class == "head bristle"], "内感受 ISN": ann[ann.cell_type == "ISN"],
        "嗅 ORN（全部）": ann[(ann.cell_class == "olfactory")]}
dan = ann[ann.cell_class == "DAN"].copy(); dan["cluster"] = dan.cell_type.str.extract(r"^(PAM|PPL1|PPL2)")[0]
res = {"wmin": WMIN, "max_hop": MAXHOP, "n_dan": {k: int(v) for k, v in dan.cluster.value_counts().items()}, "sensory_to_dan": {}, "mbon_to_motor": {}}
print("① 感觉 → 多巴胺神经元（≥3 突触的边）")
for name, g in SENS.items():
    d = bfs(list(g.i.to_numpy())); row = {"n": int(len(g))}
    for cl in ("PAM", "PPL1", "PPL2"):
        dd = d[dan[dan.cluster == cl].i.to_numpy()]
        row[cl] = {"min_hop": int(dd.min()) if dd.min() < 99 else None, "within2": int((dd <= 2).sum()), "within3": int((dd <= 3).sum()), "n": int(len(dd))}
    res["sensory_to_dan"][name] = row
    print(f"  {name:20} n={len(g):5d}  " + "  ".join(f"{cl}: 最少 {row[cl]['min_hop']} 跳，2 跳内 {row[cl]['within2']}/{row[cl]['n']}，3 跳内 {row[cl]['within3']}" for cl in ("PAM", "PPL1")))
OUT = {"DNa01": ["DNa01"], "DNa02": ["DNa02"], "DNp01（巨纤维）": ["DNp01"], "MDN（后退）": ["MDN"], "aDN1（梳理）": ["DNg62"], "MN9（伸喙）": ["CB0701"], "oDN1（前进）": ["DNg97"], "BDN2（前进）": ["DNg100"]}
out_idx = {k: ann[ann.cell_type.isin(v)].i.to_numpy() for k, v in OUT.items()}
mbon = ann[ann.cell_class == "MBON"]; dn = ann[ann.super_class == "descending"]
print("\n② MBON → 运动输出")
d = bfs(list(mbon.i.to_numpy())); hops = {k: (int(d[v].min()) if len(v) and d[v].min() < 99 else None) for k, v in out_idx.items()}
res["mbon_to_motor"]["all"] = {"n": int(len(mbon)), "hops": hops, "n_descending_within_2_hops": int((d[dn.i.to_numpy()] <= 2).sum()), "n_descending_within_1_hop": int((d[dn.i.to_numpy()] <= 1).sum())}
print("  全部 96 个 MBON：", hops, f"；1 跳内下行神经元 {(d[dn.i.to_numpy()] <= 1).sum()} 个，2 跳内 {(d[dn.i.to_numpy()] <= 2).sum()} 个")
per = {}
for t, g in mbon.groupby("cell_type"):
    dd = bfs(list(g.i.to_numpy())); per[t] = {k: (int(dd[v].min()) if dd[v].min() < 99 else None) for k, v in out_idx.items()}
res["mbon_to_motor"]["per_type"] = per
best = sorted(per.items(), key=lambda kv: sum(x if x is not None else 9 for x in kv[1].values()))[:8]
for t, h in best: print(f"    {t:16}", h)
# ③ MBON 直接（1 跳）接到的下行神经元，按带符号突触数
direct = np.zeros(N); signed = np.zeros(N)
for u in mbon.i.to_numpy(): np.add.at(direct, post_s[starts[u]:starts[u + 1]], w_s[starts[u]:starts[u + 1]]); np.add.at(signed, post_s[starts[u]:starts[u + 1]], sg_s[starts[u]:starts[u + 1]])
t = dn.assign(syn=direct[dn.i.to_numpy()], signed=signed[dn.i.to_numpy()]); t = t[t.syn > 0].groupby("cell_type").agg(syn=("syn", "sum"), signed=("signed", "sum"), n=("i", "size")).sort_values("syn", ascending=False)
res["mbon_direct_descending"] = [dict(cell_type=k, n=int(r.n), syn=int(r.syn), signed=int(r.signed)) for k, r in t.head(15).iterrows()]
print("\n③ MBON 直接接到的下行神经元：" + "、".join(f"{k}({int(r.syn)} 突触, 带符号 {int(r.signed)})" for k, r in t.head(10).iterrows()))
json.dump(res, open(ROOT / "results/learn/mb_reach.json", "w"), ensure_ascii=False, indent=1)
