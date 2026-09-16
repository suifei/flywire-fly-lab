#!/usr/bin/env python
"""
什么时候可以不跑模拟？——用连线预测“敲除效应”和“两个神经元是不是互为备份”。

背景：14.7 节已经发现，在糖通路上只看连线预测单敲除效应很差（直接突触 Spearman 0.14，加上活跃度与 1–3 跳通路 0.34）。
现在多了一条水通路（更集中）和两次枢纽全扫描（共 527 个带标签的配对：协同 / 可加 / 亚可加），于是可以问两个问题：
  A. 连线指标在水通路上是不是更管用？（如果通路越集中、结构越能预测功能，这应该成立）
  B. “两个神经元一起敲会不会塌”，能不能用结构预测？直觉是：**互为备份 = 各走各的路**，**共用瓶颈 = 走同一条路**。

事先写定（写在看结果之前）：
  单敲除预测（A）：沿用 14.7 节的三个指标，只把通路换成水——
    G1 = 对 MN9 的带符号直接突触数；G2 = 基线放电率 × G1；
    G3 = 基线放电率 × 只经过本通路活跃神经元、长度 1–3 的带符号通路权重和（每个突触折算 0.275/7）。
    与效应（1 − 修正后比值）求 Spearman，并看模拟前 20 名命中几个。
  配对预测（B）：对每个神经元 c，定义它“到 MN9 的路径画像” v(c)：在活跃子图上，对每个中间神经元 m，
    记 c 经过 m 到达 MN9 的 2–3 跳带符号权重之和，得到一个稀疏向量；两神经元的**路径重叠度** = v(c) 与 v(h) 的余弦相似度。
    检验：重叠度与全扫描的 Δ（实测效应 − 独立预期效应，正 = 协同、负 = 亚可加）求 Spearman；
    并比较“协同”组与“亚可加”组的重叠度中位数。预测方向事先声明为：**重叠度越低，Δ 越大（越像备份）**。
输出 results/screen/structure_vs_function.json
用法（brain-fly-cpu 环境）：python screen/structure_vs_function.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import sugar_mn9_screen as S  # noqa: E402
import segments as SEG  # noqa: E402

SCALE = 0.275 / 7.0
R = 6


def subgraph(active_idx, mn9):
    """活跃子图上的带符号权重矩阵（按突触折算），以及每个神经元到 MN9 的 1/2/3 跳权重。"""
    con = pd.read_parquet(S.PATH_CON, columns=["Presynaptic_Index", "Postsynaptic_Index", "Excitatory x Connectivity"])
    A = np.array(sorted(set(active_idx) | {mn9}))
    pos = -np.ones(int(con[["Presynaptic_Index", "Postsynaptic_Index"]].to_numpy().max()) + 2, np.int64)
    pos[A] = np.arange(len(A))
    pre, post = con.Presynaptic_Index.to_numpy(), con.Postsynaptic_Index.to_numpy()
    m = (pos[pre] >= 0) & (pos[post] >= 0)
    M = sp.csr_matrix((con["Excitatory x Connectivity"].to_numpy(float)[m] * SCALE, (pos[pre[m]], pos[post[m]])), shape=(len(A), len(A)))
    j = pos[mn9]
    col1 = np.asarray(M[:, j].todense()).ravel()          # 1 跳
    col2 = M @ col1                                        # 2 跳
    col3 = M @ col2                                        # 3 跳
    return A, pos, M, j, col1, col2, col3


def path_profile(M, col1, col2, j):
    """v(c)[m] = c → m → MN9（2 跳）+ c → m → · → MN9（3 跳）的带符号权重；行 = 神经元，列 = 中间神经元。"""
    w_mid = col1 + col2                                    # 中间神经元 m 自己到 MN9 的 1–2 跳权重
    V = M.multiply(w_mid[None, :]).tocsr()
    V[:, j] = 0                                            # MN9 自己不算中间节点
    V.eliminate_zeros()
    return V


def cosine(V, a, b):
    va, vb = V.getrow(a).toarray().ravel(), V.getrow(b).toarray().ravel()
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    return float(va @ vb / (na * nb)) if na > 0 and nb > 0 else None


def sugar_ctx():
    import double_extend as E
    E.setup()
    fids, fid2i = S.load_ids()
    mn9 = fid2i[S.MN9]
    _, bc, _ = S.load_chunk(E.EXT / "baseline12.npz", len(fids))
    base = {r: bc[r] for r in range(R)}
    repo = SEG.Repo([S.CHUNKS, S.OUT / "double", E.EXT, S.OUT / "double_hub", S.OUT / "hub_scan"], watch={"mn9": mn9})
    med = json.loads((S.OUT / "double12_summary.json").read_text())["null_median_single"][:R]
    scan = json.loads((S.OUT / "hub_scan_stageA.json").read_text())["rows"]
    hub = fid2i[720575940625102692]
    return fids, fid2i, mn9, base, repo, med, scan, hub, "糖 50 Hz"


def water_ctx():
    import water_screen as W
    W.setup()
    fids, fid2i, N, mn9, base12, _ = W.load_state()
    base = {r: base12[r] for r in range(R)}
    repo = SEG.Repo([W.WDIR / "chunks", W.WDIR / "hub_scan"], watch={"mn9": mn9})
    plan = json.loads((W.WDIR / "plan.json").read_text())
    med = [float(np.median([[repo.get((0, r, (fid2i[f],)), field="mn9", default=None) if base[r][fid2i[f]] > 0 else int(base[r][mn9])
                             for r in range(R)][r] for f in plan["null_single"]])) for r in range(R)]
    scan = json.loads((W.WDIR / "hub_scan_stageA.json").read_text())["rows"]
    hub = fid2i[int(json.loads((W.WDIR / "hub_scan_stageA.json").read_text())["hub"])]
    return fids, fid2i, mn9, base, repo, med, scan, hub, "水 160 Hz"


def analyse(ctx):
    fids, fid2i, mn9, base, repo, med, scan, hub, label = ctx
    active = sorted({int(n) for r in range(R) for n in np.nonzero(base[r])[0]} - {mn9})
    rate = {n: float(np.mean([base[r][n] for r in range(R)])) for n in active}
    ratios = {}
    for n in active:
        m = [repo.get((0, r, (n,)), field="mn9", default=None) if base[r][n] > 0 else int(base[r][mn9]) for r in range(R)]
        if None not in m:
            ratios[n] = sum(m) / sum(med)
    A, pos, M, j, col1, col2, col3 = subgraph(active, mn9)
    to_mn9 = pd.read_parquet(S.PATH_CON, columns=["Presynaptic_Index", "Postsynaptic_Index", "Excitatory x Connectivity"])
    to_mn9 = to_mn9[to_mn9.Postsynaptic_Index == mn9].groupby("Presynaptic_Index")["Excitatory x Connectivity"].sum()
    ids = [n for n in active if n in ratios]
    eff = np.array([1 - ratios[n] for n in ids])
    G = dict(G1=np.array([float(to_mn9.get(n, 0.0)) for n in ids]),
             G2=np.array([rate[n] * float(to_mn9.get(n, 0.0)) for n in ids]),
             G3=np.array([rate[n] * float(col1[pos[n]] + col2[pos[n]] + col3[pos[n]]) for n in ids]))
    top20 = set(np.argsort(-eff)[:20])
    singles = {k: dict(spearman=S.spearman(v, eff), top20_overlap=len(top20 & set(np.argsort(-v)[:20]))) for k, v in G.items()}
    # B：路径重叠度 vs 配对结果
    V = path_profile(M, col1, col2, j)
    rows = []
    for r in scan:
        n = fid2i[r["fid"]]
        if n >= len(pos) or pos[n] < 0:
            continue
        c = cosine(V, pos[n], pos[hub])
        if c is None:
            continue
        rows.append(dict(fid=r["fid"], overlap=round(c, 4), delta=r["delta"],
                         verdict="协同" if r["delta"] >= 0.05 else ("亚可加" if r["delta"] <= -0.05 else "中间")))
    ov = np.array([x["overlap"] for x in rows]); dl = np.array([x["delta"] for x in rows])
    syn = [x["overlap"] for x in rows if x["verdict"] == "协同"]
    sub = [x["overlap"] for x in rows if x["verdict"] == "亚可加"]
    # “不是指标退化”的证据：这些量以前只在终端打印、没有存盘，导致报告里引用了无从核对的数字（2026-09-16 补）
    nz = ov[ov > 0]
    hub_profile_nnz = int((V[pos[hub]] != 0).sum()) if pos[hub] >= 0 else None
    nonzero = dict(n_pairs_with_overlap=int((ov > 0).sum()), frac=round(float((ov > 0).mean()), 4),
                   max_overlap=round(float(ov.max()), 4),
                   spearman_among_nonzero=S.spearman(nz, dl[ov > 0]) if len(nz) > 2 else None,
                   hub_profile_nonzero_nodes=hub_profile_nnz)
    pair = dict(n=len(rows), spearman_overlap_vs_delta=S.spearman(ov, dl),
                median_overlap_synergy=round(float(np.median(syn)), 4) if syn else None,
                median_overlap_subadditive=round(float(np.median(sub)), 4) if sub else None,
                n_synergy=len(syn), n_subadditive=len(sub), degeneracy_check=nonzero)
    return dict(label=label, n_active=len(active), n_scored=len(ids), singles=singles, pairs=pair,
                rows=rows[:50], all_rows=rows)


def main():
    out = {}
    for name, ctx in (("sugar", sugar_ctx()), ("water", water_ctx())):
        out[name] = analyse(ctx)
        r = out[name]
        print(f"\n=== {r['label']}（活跃 {r['n_active']}，有效 {r['n_scored']}）")
        print("  单敲除效应能不能只用连线预测：")
        for k, v in r["singles"].items():
            print(f"    {k}: Spearman {v['spearman']}，模拟前 20 名命中 {v['top20_overlap']}")
        d = r["pairs"]["degeneracy_check"]
        print(f"    退化性核对：{d['n_pairs_with_overlap']}/{r['pairs']['n']} 个配对有非零重叠（{d['frac']:.0%}），"
              f"最大重叠 {d['max_overlap']}，枢纽路径画像非零节点 {d['hub_profile_nonzero_nodes']} 个，"
              f"只看有重叠的那些 Spearman {d['spearman_among_nonzero']}")
        p = r["pairs"]
        print(f"  路径重叠度 vs 配对 Δ：Spearman {p['spearman_overlap_vs_delta']}（n = {p['n']}）")
        print(f"    协同组重叠度中位 {p['median_overlap_synergy']}（n = {p['n_synergy']}）；亚可加组 {p['median_overlap_subadditive']}（n = {p['n_subadditive']}）")
    (S.OUT / "structure_vs_function.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("\n写入", S.OUT / "structure_vs_function.json")


if __name__ == "__main__":
    main()
