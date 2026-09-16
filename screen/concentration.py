#!/usr/bin/env python
"""
“通路集中度”——把一句印象变成可计算的量，再看它能不能解释模型准不准。

前面反复出现这句话：糖通路“分散、冗余多”，水通路“集中”，JON 通路“几乎只有一个瓶颈”。
这是印象。这里把它定义清楚，并检验它是不是真的和两件事相关：
  (1) 只看连线能不能预测敲除效应（22 节的 G3）；
  (2) 模型对真实沉默实验的准确率（糖 6/10、水 9/10、JON 1/1 可测——aBN2 在 v783 无对应 ID，见下方 EXPERIMENT 处的说明）。

事先写定（写在算之前）：
  效应 e(c) = max(0, 1 − 比值)，比值用各通路自己的零参照（同实现所有单敲除的中位数）修正，前 6 个实现。
  三个集中度指标：
    frac_required  = 效应 ≥ 0.2（即比值 ≤ 0.8）的神经元数 ÷ 活跃神经元数；
    gini           = 效应分布的基尼系数（0 = 人人一样，1 = 全集中在一个神经元）；
    n80            = 从大到小累加，贡献 80% 总效应所需的神经元个数（越小越集中）。
  预先声明的方向：**越集中（gini 越大、n80 越小）→ 连线预测力越高、对实验越准。**
  样本只有三条通路，所以只看方向是否一致，不做统计检验。
输出 results/screen/concentration.json
用法（brain-fly-cpu 环境）：python screen/concentration.py
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import sugar_mn9_screen as S  # noqa: E402
import segments as SEG  # noqa: E402
import structure_vs_function as SF  # noqa: E402

R = 6
# 真实沉默实验对照。JON 那条**曾经手写成 "2/2（aBN1、aBN2）"，是错的**：
# Hampel et al. 2015 验证的是 aBN1 + aBN2，但 aBN2 的 v630 ID 720575940611163610 在 v783 模型里不存在，我们测不了；
# 而且论文自己表 7D 里同一个 ID（那里叫 "Descending BN2_3"）160 Hz 比值是 0.844，按 0.8 门槛也判不出必需。
# 所以我们能测的只有 aBN1 一个，且判对了。
EXPERIMENT = {"糖 50 Hz": "6/10", "水 160 Hz": "9/10", "JON 160 Hz": "1/1 可测（aBN1 判对；aBN2 在 v783 无对应 ID）"}


def gini(x):
    x = np.sort(np.asarray(x, float))
    if x.sum() <= 0:
        return 0.0
    n = len(x)
    return float((2 * np.arange(1, n + 1) - n - 1) @ x / (n * x.sum()))


def n80(x):
    x = np.sort(np.asarray(x, float))[::-1]
    if x.sum() <= 0:
        return None
    c = np.cumsum(x) / x.sum()
    return int(np.searchsorted(c, 0.8) + 1)


def pathway(name, repo, base, readout_idx, med, fid2i, fids):
    active = sorted({int(n) for r in range(R) for n in np.nonzero(base[r])[0]} - {readout_idx})
    rate = {n: float(np.mean([base[r][n] for r in range(R)])) for n in active}
    key = {"糖 50 Hz": "mn9", "水 160 Hz": "mn9", "JON 160 Hz": "aDN1"}[name]
    eff, ids = [], []
    for n in active:
        m = [repo.get((0, r, (n,)), field=key, default=None) if base[r][n] > 0 else int(base[r][readout_idx]) for r in range(R)]
        if None in m:
            continue
        ids.append(n); eff.append(max(0.0, 1 - sum(m) / sum(med)))
    eff = np.array(eff)
    A, pos, M, j, col1, col2, col3 = SF.subgraph(ids, readout_idx)
    g3 = np.array([rate[n] * float(col1[pos[n]] + col2[pos[n]] + col3[pos[n]]) for n in ids])
    return dict(name=name, n_active=len(active), n_scored=len(ids),
                frac_required=round(float((eff >= 0.2).mean()), 4), n_required=int((eff >= 0.2).sum()),
                gini=round(gini(eff), 4), n80=n80(eff),
                max_effect=round(float(eff.max()), 3), median_effect=round(float(np.median(eff)), 4),
                g3_spearman=S.spearman(g3, eff), experiment=EXPERIMENT[name])


def main():
    rows = []
    # 糖
    import double_extend as E
    E.setup()
    fids, fid2i = S.load_ids()
    mn9 = fid2i[S.MN9]
    _, bc, _ = S.load_chunk(E.EXT / "baseline12.npz", len(fids))
    base = {r: bc[r] for r in range(R)}
    repo = SEG.Repo([S.CHUNKS, S.OUT / "double", E.EXT, S.OUT / "double_hub", S.OUT / "hub_scan"], watch={"mn9": mn9})
    med = json.loads((S.OUT / "double12_summary.json").read_text())["null_median_single"][:R]
    rows.append(pathway("糖 50 Hz", repo, base, mn9, med, fid2i, fids))
    # 水
    import water_screen as W
    W.setup()
    fids, fid2i, N, mn9w, basew, _ = W.load_state()
    basew = {r: basew[r] for r in range(R)}
    repow = SEG.Repo([W.WDIR / "chunks", W.WDIR / "hub_scan"], watch={"mn9": mn9w})
    planw = json.loads((W.WDIR / "plan.json").read_text())
    medw = [float(np.median([[repow.get((0, r, (fid2i[f],)), field="mn9", default=None) if basew[r][fid2i[f]] > 0 else int(basew[r][mn9w])
                              for r in range(R)][r] for f in planw["null_single"]])) for r in range(R)]
    rows.append(pathway("水 160 Hz", repow, basew, mn9w, medw, fid2i, fids))
    # JON
    import jon_screen as J
    fidsj, fid2ij, Nj, watch, basej, repoj = J.state()
    basej = {r: basej[r] for r in range(R)}
    planj = json.loads((J.JDIR / "plan.json").read_text())
    adn1 = fid2ij[J.ADN1]
    medj = [float(np.median([[repoj.get((0, r, (fid2ij[f],)), field="aDN1", default=None) if basej[r][fid2ij[f]] > 0 else int(basej[r][adn1])
                              for r in range(R)][r] for f in planj["null_single"]])) for r in range(R)]
    rows.append(pathway("JON 160 Hz", repoj, basej, adn1, medj, fid2ij, fidsj))
    (S.OUT / "concentration.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    hdr = f"{'通路':12s} {'活跃':>6s} {'必需数':>6s} {'必需占比':>8s} {'基尼':>6s} {'n80':>5s} {'最大效应':>8s} {'连线 G3':>8s}  对实验"
    print(hdr); print("-" * len(hdr))
    for r in rows:
        print(f"{r['name']:12s} {r['n_active']:6d} {r['n_required']:6d} {r['frac_required']:8.3f} {r['gini']:6.3f} "
              f"{str(r['n80']):>5s} {r['max_effect']:8.2f} {r['g3_spearman']:8.3f}  {r['experiment']}")
    print("\n写入", S.OUT / "concentration.json")


if __name__ == "__main__":
    main()
