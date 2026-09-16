#!/usr/bin/env python
"""
双敲除筛选：找"单独敲都没事、一起敲就断"的备份通路（糖 → MN9，50 Hz）

单个敲除只能告诉我们"少了它行不行"。真实回路里常有冗余：两条通路各自都能把信号送到 MN9，
敲掉任一条都看不出问题，两条一起敲才断。这种组合实验在真实果蝇上要同时做两条 split-GAL4，
基本没人做得起；在模型里只是多跑几段。

事先写定的设计（运行前写好，结果出来后不改）：
  模型、刺激、读出、沉默方式、段落安排、输入实现都与 screen/sugar_mn9_screen.py 完全相同（同一个 build，50 Hz，6 个实现）。
  参照：单敲除筛选发现"扰动任何神经元都会让 MN9 向条件均值回归"（报告 14.4 节）。所以这里每类扰动各自算零参照：
    单敲除比值 = Σ MN9 / Σ(同实现所有单敲除的 MN9 中位数)  —— 直接取自 summary.json
    双敲除比值 = Σ MN9 / Σ(C 组 30 对"单独都无效"的对照对的 MN9 中位数)
  三组条件：
    A 组（通路冗余）：50 Hz 修正后效应最强的 12 个**非感觉**神经元，两两组合 66 对。
    B 组（输入冗余）：随机去掉 k 个糖 GRN，k ∈ {2,3,5,8,13,21}，每个 k 取 3 个随机子集（k=21 只有 1 个），种子 20260916。
    C 组（双敲除零参照）：单敲除修正后比值落在 0.97–1.03 的神经元里随机取 60 个，配成 30 对。
  判据（相对各自零参照的效应 E = 1 − 比值）：
    独立预期 E_exp = 1 − (1 − E_a)(1 − E_b)（乘性）
    协同（备份通路）：E_ab > E_exp + 0.1；亚可加（共用瓶颈）：E_ab < E_exp − 0.1。
  段数 66×6 + 16×6 + 30×6 = 672 段，约 22 min。

用法（brain-fly-cpu 环境，套 scratch/memguard.sh）：
  python screen/double_knockout.py run
  python screen/double_knockout.py analyze   # → results/screen/double_summary.json
"""
import argparse
import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sugar_mn9_screen as S  # noqa: E402

OUT = S.OUT
DOUBLE = OUT / "double"
SEED2 = 20260916
N_TOP = 12
NULL_LO, NULL_HI, N_NULL_PAIRS = 0.97, 1.03, 30
K_GRN = (2, 3, 5, 8, 13, 21)
N_SUBSETS = 3
SYN_MARGIN = 0.1
FI = 0            # 只在 50 Hz 做


def load_single():
    """单敲除结果：每个神经元 6 个实现的 MN9、修正后比值、零参照中位数。"""
    summ = json.loads((OUT / "summary.json").read_text())
    R = summ["plan"]["R"]
    med = summ["exploratory_null_normalized"]["null_median_mn9"]["50"]
    fids, fid2i = S.load_ids()
    N = len(fids)
    mn9 = fid2i[S.MN9]
    _, bc, _ = S.load_chunk(S.CHUNKS / "baseline.npz", N)
    base = {r: bc[FI * S.R_MAX + r] for r in range(S.R_MAX)}
    res = {}
    for p in sorted(S.CHUNKS.glob("chunk_*.npz")):
        keys, summ_rows = S.chunk_summary(p, {"mn9": mn9})
        res.update({k: v["mn9"] for k, v in zip(keys, summ_rows)})
    single = {}
    for row in json.loads((OUT / "exhaustive_50Hz.json").read_text()):
        n = fid2i[int(row["fid"])]
        m = [res.get((FI, r, (n,)), int(base[r][mn9])) if base[r][n] > 0 else int(base[r][mn9]) for r in range(R)]
        single[n] = dict(fid=int(row["fid"]), mn9=m, ratio=sum(m) / sum(med), rate=row["rate_hz"],
                         super_class=row.get("super_class"), cell_type=row.get("cell_type"), nt=row.get("nt"))
    return R, med, single, base, mn9, fids, fid2i


def conditions(R, single, fid2i):
    rng = np.random.default_rng(SEED2)
    nonsens = sorted([n for n, v in single.items() if v["super_class"] != "sensory"], key=lambda n: single[n]["ratio"])
    top = nonsens[:N_TOP]
    a_pairs = [tuple(sorted(p)) for p in itertools.combinations(top, 2)]
    grn = [fid2i[f] for f in S.sugar_ids()]
    b_sets = []
    for k in K_GRN:
        for j in range(1 if k >= len(grn) else N_SUBSETS):
            b_sets.append(tuple(sorted(rng.choice(grn, min(k, len(grn)), replace=False).tolist())))
    b_sets = sorted(set(b_sets))
    pool = sorted([n for n, v in single.items() if NULL_LO <= v["ratio"] <= NULL_HI])
    pick = rng.choice(pool, min(2 * N_NULL_PAIRS, len(pool) // 2 * 2), replace=False).tolist()
    c_pairs = [tuple(sorted(pick[2 * i:2 * i + 2])) for i in range(len(pick) // 2)]
    return top, a_pairs, b_sets, c_pairs, pool


def cmd_run():
    DOUBLE.mkdir(parents=True, exist_ok=True)
    R, med, single, base, mn9, fids, fid2i = load_single()
    top, a_pairs, b_sets, c_pairs, pool = conditions(R, single, fid2i)
    print(f"A 组前 {N_TOP} 个非感觉神经元：", [f"{fids[n]}({single[n]['cell_type']},{single[n]['ratio']:.2f})" for n in top], flush=True)
    print(f"A {len(a_pairs)} 对；B {len(b_sets)} 个 GRN 子集；C 零参照池 {len(pool)} 个 → {len(c_pairs)} 对", flush=True)
    segs, groups = [], []
    for grp, conds in (("A", a_pairs), ("B", b_sets), ("C", c_pairs)):
        for sil in conds:
            for r in range(R):
                if any(base[r][n] > 0 for n in sil):
                    segs.append((FI, r, tuple(sil))); groups.append(grp)
    print(f"需要模拟 {len(segs)} 段，估计 {len(segs) * 2.0 / 60:.0f} min", flush=True)
    (OUT / "double_plan.json").write_text(json.dumps(dict(
        R=R, top=[int(fids[n]) for n in top], a_pairs=[[int(fids[x]) for x in p] for p in a_pairs],
        b_sets=[[int(fids[x]) for x in s] for s in b_sets], c_pairs=[[int(fids[x]) for x in p] for p in c_pairs],
        n_segments=len(segs)), indent=1))
    sc = S.Screen()
    n_chunks = math.ceil(len(segs) / S.K)
    import time
    t0 = time.time(); done = 0
    for c in range(n_chunks):
        path = DOUBLE / f"chunk_{c:04d}.npz"
        part = segs[c * S.K:(c + 1) * S.K]
        if path.exists() and S.chunk_keys(path) == [(fi, r, tuple(s)) for fi, r, s in part]:
            continue
        counts, wall = sc.run_chunk(part)
        S.save_chunk(path, [S.key(*s) for s in part], counts, wall)
        done += 1
        el = time.time() - t0
        print(f"块 {c + 1}/{n_chunks}：{wall:.0f} s；已跑 {el / 60:.1f} min，预计还需 {el / done * (n_chunks - c - 1) / 60:.0f} min", flush=True)
    print("全部完成", flush=True)


def cmd_analyze():
    R, med, single, base, mn9, fids, fid2i = load_single()
    top, a_pairs, b_sets, c_pairs, pool = conditions(R, single, fid2i)
    res = {}
    for p in sorted(DOUBLE.glob("chunk_*.npz")):
        keys, rows = S.chunk_summary(p, {"mn9": mn9})
        res.update({k: v["mn9"] for k, v in zip(keys, rows)})

    def counts(sil):
        return [res[(FI, r, tuple(sorted(sil)))] if any(base[r][n] > 0 for n in sil) else int(base[r][mn9]) for r in range(R)]
    # 双敲除零参照：C 组各实现的中位数
    med2 = []
    for r in range(R):
        v = [res[(FI, r, tuple(sorted(p)))] for p in c_pairs if (FI, r, tuple(sorted(p))) in res]
        med2.append(float(np.median(v)) if v else float(med[r]))
    out = dict(design=dict(n_top=N_TOP, k_grn=K_GRN, n_null_pairs=len(c_pairs), synergy_margin=SYN_MARGIN, seed=SEED2, freq_hz=50, R=R),
               null_median_single=med, null_median_double=med2,
               double_null_over_single_null=round(sum(med2) / sum(med), 4), pairs=[], grn_dose=[], top=[])
    for n in top:
        v = single[n]
        out["top"].append(dict(fid=str(v["fid"]), cell_type=v["cell_type"], nt=v["nt"], rate_hz=v["rate"], ratio_single=round(v["ratio"], 4)))
    for a, b in a_pairs:
        m = counts((a, b))
        r_ab = sum(m) / sum(med2)
        e_a, e_b = 1 - single[a]["ratio"], 1 - single[b]["ratio"]
        e_exp = 1 - (1 - e_a) * (1 - e_b)
        e_ab = 1 - r_ab
        out["pairs"].append(dict(a=str(single[a]["fid"]), b=str(single[b]["fid"]), a_type=single[a]["cell_type"], b_type=single[b]["cell_type"],
                                 ratio_a=round(single[a]["ratio"], 4), ratio_b=round(single[b]["ratio"], 4), ratio_ab=round(r_ab, 4),
                                 effect_expected=round(e_exp, 4), effect_observed=round(e_ab, 4), delta=round(e_ab - e_exp, 4),
                                 verdict="协同" if e_ab > e_exp + SYN_MARGIN else ("亚可加" if e_ab < e_exp - SYN_MARGIN else "可加"),
                                 mn9=m))
    for s in b_sets:
        m = counts(s)
        out["grn_dose"].append(dict(k=len(s), ratio=round(sum(m) / sum(med2), 4), mn9=m, ids=[str(fids[x]) for x in s]))
    out["summary"] = dict(n_pairs=len(out["pairs"]),
                          n_synergy=sum(p["verdict"] == "协同" for p in out["pairs"]),
                          n_subadditive=sum(p["verdict"] == "亚可加" for p in out["pairs"]),
                          n_additive=sum(p["verdict"] == "可加" for p in out["pairs"]),
                          strongest_synergy=sorted(out["pairs"], key=lambda p: -p["delta"])[:5],
                          strongest_subadditive=sorted(out["pairs"], key=lambda p: p["delta"])[:5],
                          grn_dose_median={k: round(float(np.median([d["ratio"] for d in out["grn_dose"] if d["k"] == k])), 3) for k in K_GRN})
    (OUT / "double_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps(out["summary"], ensure_ascii=False, indent=1)[:4000])
    print("双敲除零参照 / 单敲除零参照 =", out["double_null_over_single_null"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "analyze"])
    a = ap.parse_args()
    (cmd_run if a.cmd == "run" else cmd_analyze)()
