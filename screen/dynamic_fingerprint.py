#!/usr/bin/env python
"""
静态连线预测不了冗余（22 节），那“动力学指纹”行不行？

22 节事先声明的结构假设被证伪：两个神经元到 MN9 的**图上路径**重不重叠，和它们一起敲会不会塌毫无关系
（Spearman −0.008 / 0.013）。这里换一个同样能事先算、但用到动力学的量：
  敲掉神经元 c 之后，**全脑哪些神经元的放电变了**——这张“指纹” Δ(c) 已经存在段文件里（每段存的是全部神经元的脉冲数，不只是读出）。
  如果 c 和枢纽 h 影响的是同一批下游神经元（指纹相似），它们大概率共用瓶颈；影响不同的神经元，则更可能是并行的两条路。

事先写定（写在看结果之前）：
  Δ(c) = 6 个实现上“敲除 c 的全脑脉冲数 − 基线全脑脉冲数”的平均，只保留基线活跃的神经元，并去掉 c 自己与读出本身。
  动力学重叠 = cos(Δ(c), Δ(h))。
  检验：与枢纽全扫描的 Δ（实测效应 − 独立预期效应；正 = 协同，负 = 亚可加）求 Spearman，
  并比较协同组与亚可加组的中位数。**事先声明的方向：动力学重叠越高 → Δ 越负（越像共用瓶颈）。**
  对照：同时报告“指纹的大小” |Δ(c)|（敲掉它在全脑造成多大扰动）与配对 Δ 的关系，用来判断相似度是不是只是幅度的替身。
输出 results/screen/dynamic_fingerprint.json
用法（brain-fly-cpu 环境）：python screen/dynamic_fingerprint.py
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import sugar_mn9_screen as S  # noqa: E402

R = 6


def load_full_counts(dirs, wanted_keys, N):
    """从段文件里读全部神经元的脉冲数（稀疏存储 → 只取需要的段）。"""
    out = {}
    want = set(wanted_keys)
    for d in dirs:
        for p in sorted(Path(d).glob("*.npz")):
            keys = S.chunk_keys(p)
            if not want.intersection(keys):
                continue
            z = np.load(p)
            for s, k in enumerate(keys):
                if k in want and k not in out:
                    a, b = z["ptr"][s], z["ptr"][s + 1]
                    v = np.zeros(N, np.int32)
                    v[z["idx"][a:b]] = z["cnt"][a:b]
                    out[k] = v
    return out


def analyse(name, ctx):
    fids, fid2i, readout_idx, base, dirs, scan, hub, N = ctx
    active = sorted({int(n) for r in range(R) for n in np.nonzero(base[r])[0]} - {readout_idx})
    cand = [fid2i[r["fid"]] for r in scan if r["fid"] in fid2i]
    need = [(0, r, (n,)) for n in cand + [hub] for r in range(R) if base[r][n] > 0]
    full = load_full_counts(dirs, need, N)
    act = np.array(active)

    def fingerprint(n):
        d = np.zeros(len(act), float)
        ok = 0
        for r in range(R):
            v = full.get((0, r, (n,)))
            if v is None:
                if base[r][n] > 0:
                    return None
                v = base[r]                      # 该实现里它不放电 → 与基线逐位相同
            d += v[act].astype(float) - base[r][act].astype(float)
            ok += 1
        d /= max(ok, 1)
        keep = (act != n) & (act != readout_idx)
        return d * keep
    fh = fingerprint(hub)
    rows = []
    for r in scan:
        n = fid2i.get(r["fid"])
        if n is None or n == hub:
            continue
        f = fingerprint(n)
        if f is None:
            continue
        na, nb = np.linalg.norm(f), np.linalg.norm(fh)
        cos = float(f @ fh / (na * nb)) if na > 0 and nb > 0 else None
        rows.append(dict(fid=r["fid"], overlap=None if cos is None else round(cos, 4),
                         magnitude=round(float(na), 3), delta=r["delta"],
                         verdict="协同" if r["delta"] >= 0.05 else ("亚可加" if r["delta"] <= -0.05 else "中间")))
    ok = [x for x in rows if x["overlap"] is not None]
    ov = np.array([x["overlap"] for x in ok]); dl = np.array([x["delta"] for x in ok]); mg = np.array([x["magnitude"] for x in ok])
    syn = [x["overlap"] for x in ok if x["verdict"] == "协同"]
    sub = [x["overlap"] for x in ok if x["verdict"] == "亚可加"]
    # 事后加的诊断：重叠度是不是只是“扰动幅度”的替身？控制幅度后的偏相关（对秩做线性回归取残差）
    def rank(v):
        o = np.argsort(np.argsort(v)).astype(float)
        return (o - o.mean()) / (o.std() or 1)
    ro, rd, rm = rank(ov), rank(dl), rank(mg)
    res_o, res_d = ro - (ro @ rm / (rm @ rm)) * rm, rd - (rd @ rm / (rm @ rm)) * rm
    partial = round(float(np.corrcoef(res_o, res_d)[0, 1]), 3)
    res = dict(label=name, n=len(ok), n_active=len(active),
               spearman_overlap_vs_delta=S.spearman(ov, dl),
               spearman_magnitude_vs_delta=S.spearman(mg, dl),
               partial_overlap_vs_delta_controlling_magnitude=partial,
               median_overlap_synergy=round(float(np.median(syn)), 4) if syn else None,
               median_overlap_subadditive=round(float(np.median(sub)), 4) if sub else None,
               n_synergy=len(syn), n_subadditive=len(sub),
               rows=sorted(ok, key=lambda x: -x["delta"]))
    print(f"\n=== {name}（{len(ok)} 个候选，活跃 {len(active)}）")
    print(f"  动力学重叠 vs 配对 Δ：Spearman {res['spearman_overlap_vs_delta']}")
    print(f"    协同组中位 {res['median_overlap_synergy']}（n = {len(syn)}）；亚可加组中位 {res['median_overlap_subadditive']}（n = {len(sub)}）")
    print(f"  对照——指纹大小 vs 配对 Δ：Spearman {res['spearman_magnitude_vs_delta']}")
    print(f"  控制幅度后的偏相关（重叠度 vs Δ）：{partial}")
    return res


def sugar_ctx():
    import double_extend as E
    E.setup()
    fids, fid2i = S.load_ids()
    N = len(fids)
    mn9 = fid2i[S.MN9]
    _, bc, _ = S.load_chunk(E.EXT / "baseline12.npz", N)
    base = {r: bc[r] for r in range(R)}
    scan = json.loads((S.OUT / "hub_scan_stageA.json").read_text())["rows"]
    dirs = [S.CHUNKS, S.OUT / "double", E.EXT, S.OUT / "double_hub", S.OUT / "hub_scan"]
    return fids, fid2i, mn9, base, dirs, scan, fid2i[720575940625102692], N


def water_ctx():
    import water_screen as W
    W.setup()
    fids, fid2i, N, mn9, base12, _ = W.load_state()
    base = {r: base12[r] for r in range(R)}
    st = json.loads((W.WDIR / "hub_scan_stageA.json").read_text())
    return fids, fid2i, mn9, base, [W.WDIR / "chunks", W.WDIR / "hub_scan"], st["rows"], fid2i[int(st["hub"])], N


def main():
    out = {}
    for name, f in (("糖 50 Hz × CB0883", sugar_ctx), ("水 160 Hz × CB0051", water_ctx)):
        out[name] = analyse(name, f())
    (S.OUT / "dynamic_fingerprint.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("\n写入", S.OUT / "dynamic_fingerprint.json")


if __name__ == "__main__":
    main()
