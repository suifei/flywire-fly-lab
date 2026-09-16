"""探查 looming→下行神经元 子回路在不同阈值/跳数下的规模（只做图计算，不仿真）。"""
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp


def bfs_hops(A, sources, limit=5):
    """多源 BFS：A 为 (pre, post) 邻接矩阵，返回每个节点离最近源的跳数（不可达 = inf）。"""
    dist = np.full(A.shape[0], np.inf)
    frontier = np.zeros(A.shape[0], bool); frontier[sources] = True
    dist[frontier] = 0
    for h in range(1, limit + 1):
        nxt = (A.T @ frontier.astype(np.float32)) > 0  # frontier 的突触后邻居
        nxt &= np.isinf(dist)
        if not nxt.any():
            break
        dist[nxt] = h
        frontier = nxt
    return dist

ROOT = Path(__file__).resolve().parent.parent
ann = pd.read_csv(ROOT / "external/flywire_annotations/Supplemental_file1_neuron_annotations.tsv", sep="\t",
                  low_memory=False, usecols=["root_id", "cell_type", "side"])
comp = pd.read_csv(ROOT / "external/fly-brain/data/2025_Completeness_783.csv", index_col=0)
fid2i = {int(f): i for i, f in enumerate(comp.index)}
n = len(comp)
con = pd.read_parquet(ROOT / "external/fly-brain/data/2025_Connectivity_783.parquet",
                      columns=["Presynaptic_Index", "Postsynaptic_Index", "Connectivity"])


def ids(t, s=None):
    m = ann.cell_type == t
    if s:
        m &= ann.side == s
    return [fid2i[int(r)] for r in ann.root_id[m] if int(r) in fid2i]


S = ids("LC4") + ids("LPLC2")
T = ids("DNa01") + ids("DNa02") + ids("DNp01")
print("sources", len(S), "targets", len(T),
      [(t, s, len(ids(t, s))) for t in ["DNa01", "DNa02", "DNp01"] for s in ["left", "right"]], flush=True)
pre, post = con.Presynaptic_Index.to_numpy(), con.Postsynaptic_Index.to_numpy()
for wmin in [3, 5, 10]:
    m = con.Connectivity.to_numpy() >= wmin
    A = sp.csr_matrix((np.ones(m.sum()), (pre[m], post[m])), shape=(n, n))
    dS = bfs_hops(A, S)                 # 从 looming 神经元出发的正向跳数
    dT = bfs_hops(A.T.tocsr(), T)       # 到下行神经元的反向跳数
    for K in [2, 3, 4]:
        sel = np.union1d(np.where(dS + dT <= K)[0], np.array(S + T))
        mask = np.zeros(n, bool); mask[sel] = True
        e = mask[pre] & mask[post]
        print(f"syn>={wmin} K={K}: neurons {len(sel)}, induced edges {int(e.sum())}, "
              f"shortest S->T {dS[T].min():.0f} hops", flush=True)
