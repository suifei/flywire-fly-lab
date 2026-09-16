#!/usr/bin/env python
"""
糖 vs 水：同一个读出（MN9）、两条输入通路，网络用的是同一批神经元吗？

第 14 节（糖 50 Hz）和第 19 节（水 160 Hz）各自做过穷举 / 大范围的单敲除筛选，两边的活跃集合与敲除效应都在盘上。
这里只做分析、不跑仿真，回答三个问题：
  1. 两条通路的活跃神经元重叠多少？各自私有的是哪些类别？
  2. 在共同活跃的神经元上，“敲掉它对 MN9 的影响”两边一致吗（Spearman / 判定一致率）？
  3. 两条通路各自的“枢纽”（糖 CB0883、水 CB0051）在对方通路里是什么表现？

口径：两边都用各自的零参照（同实现所有单敲除的中位数）修正后的比值，前 6 个实现（两边都有），
判定门槛同为 ≤ 0.8；共同活跃 = 两边的基线里都放过电。
输出 results/screen/pathway_compare.json
用法（brain-fly-cpu 环境）：python screen/pathway_compare.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import sugar_mn9_screen as S  # noqa: E402
import segments as SEG  # noqa: E402

R = 6
CALL = 0.8
HUB_SUGAR, HUB_WATER = "CB0883", "CB0051"


def sugar_side():
    import double_extend as E
    E.setup()
    fids, fid2i = S.load_ids()
    mn9 = fid2i[S.MN9]
    _, bc, _ = S.load_chunk(E.EXT / "baseline12.npz", len(fids))
    base = {r: bc[r] for r in range(R)}
    repo = SEG.Repo([S.CHUNKS, S.OUT / "double", E.EXT, S.OUT / "double_hub", S.OUT / "hub_scan"], watch={"mn9": mn9})
    d12 = json.loads((S.OUT / "double12_summary.json").read_text())
    med = d12["null_median_single"][:R]
    active = sorted({int(n) for r in range(R) for n in np.nonzero(base[r])[0]} - {mn9})
    ratios = {}
    for n in active:
        m = [repo.get((0, r, (n,)), field="mn9", default=None) if base[r][n] > 0 else int(base[r][mn9]) for r in range(R)]
        if None not in m:
            ratios[int(fids[n])] = sum(m) / sum(med)
    return set(int(fids[n]) for n in active), ratios


def water_side():
    import water_screen as W
    W.setup()
    fids, fid2i, N, mn9, base, _ = W.load_state()
    repo = SEG.Repo([W.WDIR / "chunks", W.WDIR / "hub_scan"], watch={"mn9": mn9})
    plan = json.loads((W.WDIR / "plan.json").read_text())
    med = [float(np.median([[repo.get((0, r, (fid2i[f],)), field="mn9", default=None) if base[r][fid2i[f]] > 0 else int(base[r][mn9])
                             for r in range(R)][r] for f in plan["null_single"]])) for r in range(R)]
    active = sorted({int(n) for r in range(R) for n in np.nonzero(base[r])[0]} - {mn9})
    ratios = {}
    for n in active:
        m = [repo.get((0, r, (n,)), field="mn9", default=None) if base[r][n] > 0 else int(base[r][mn9]) for r in range(R)]
        if None not in m:
            ratios[int(fids[n])] = sum(m) / sum(med)
    return set(int(fids[n]) for n in active), ratios


def main():
    sa, sr = sugar_side()
    wa, wr = water_side()
    ann = pd.read_csv(S.ANNOT, sep="\t", low_memory=False, usecols=["root_id", "cell_type", "super_class", "cell_class", "top_nt"]).drop_duplicates("root_id").set_index("root_id")
    cls = lambda f: (ann.loc[f].super_class if f in ann.index else "?")
    ct = lambda f: (ann.loc[f].cell_type if f in ann.index and isinstance(ann.loc[f].cell_type, str) else str(f))
    both, only_s, only_w = sa & wa, sa - wa, wa - sa
    def dist(ids):
        d = {}
        for f in ids:
            d[cls(f)] = d.get(cls(f), 0) + 1
        return dict(sorted(d.items(), key=lambda kv: -kv[1]))
    out = dict(n_active=dict(sugar=len(sa), water=len(wa), both=len(both), only_sugar=len(only_s), only_water=len(only_w)),
               jaccard=round(len(both) / len(sa | wa), 3),
               super_class=dict(both=dist(both), only_sugar=dist(only_s), only_water=dist(only_w)))
    common = sorted(f for f in both if f in sr and f in wr)
    x = np.array([1 - sr[f] for f in common]); y = np.array([1 - wr[f] for f in common])
    calls_s, calls_w = np.array([sr[f] <= CALL for f in common]), np.array([wr[f] <= CALL for f in common])
    out["effects_on_common"] = dict(n=len(common), spearman=S.spearman(x, y), pearson=round(float(np.corrcoef(x, y)[0, 1]), 3),
                                    call_agreement=round(float((calls_s == calls_w).mean()), 3), kappa=S.kappa(calls_s, calls_w),
                                    required_sugar_only=[ct(f) for f in common if sr[f] <= CALL < wr[f]][:20],
                                    required_water_only=[ct(f) for f in common if wr[f] <= CALL < sr[f]][:20],
                                    required_both=[ct(f) for f in common if sr[f] <= CALL and wr[f] <= CALL])
    hubs = {}
    for name, hub_type in (("sugar_hub", HUB_SUGAR), ("water_hub", HUB_WATER)):
        cand = [int(f) for f in ann.index[ann.cell_type == hub_type]]
        hubs[hub_type] = dict(
            in_sugar_active=[ct(f) for f in cand if f in sa], in_water_active=[ct(f) for f in cand if f in wa],
            ratio_sugar=[round(sr[f], 3) for f in cand if f in sr], ratio_water=[round(wr[f], 3) for f in cand if f in wr])
    out["hubs"] = hubs
    (S.OUT / "pathway_compare.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps(out, ensure_ascii=False, indent=1)[:3000])


if __name__ == "__main__":
    main()
