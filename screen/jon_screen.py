#!/usr/bin/env python
"""
第三条通路：触角听觉 / 机械感觉（JON → aDN1 梳理指令），读出不再是 MN9。

为什么做：前面 22 节的方法学结论（混沌带来的配对偏差、枢纽、结构预测不了冗余）全部来自味觉 → MN9。
换一条**不同模态、不同读出**的通路，才能知道那些结论是通路特定的还是这个模型的普遍性质。
论文补充表 7D 给了同一条通路上 299 个神经元的沉默筛选（读出 aDN1），可以直接对照。

事先写定（运行前写好）：
  刺激：注释表里 cell_type 以 "JO-" 开头、且在模型中的全部 1,091 个 Johnston 器神经元（两侧），160 Hz
        （论文补充表 7D 覆盖 140–180 Hz，取中间值；与水通路用同一频率便于横向比较）。
  读出：aDN1 = 720575940616185531（论文 notebook 的 id_DN1_1，注释 DNg62 右）；
        另记 aDN2 = 720575940629806974、aBN1 = 720575940630907434 作为次要读出（论文表 7A 在 160 Hz 分别是 23.3 / 23.7 / 54.5 Hz）。
  输入实现 r = 0…11（种子 20260914 + r），段落安排与糖 / 水完全相同。
  零参照与前两条通路同口径：单敲除 = 每实现 50 个随机活跃神经元单敲后 aDN1 的中位数（抽样种子 20260919）；
  双敲除 = 20 对“单独都无效”的对照对的中位数。
  两阶段：阶段 A 前 6 个实现；阶段 B 把 |1 − 比值| ≥ 0.1 的补到 12 个实现，并做效应最强 12 个非感觉神经元的 66 对双敲除。
  候选：P = 论文补充表 7D 的 299 个里 v783 中 ID 未变的 281 个（去掉读出 aDN1 自己）。
  判定：比值 ≤ 0.8 记为“该通路必需”；协同 / 亚可加判据与前两条一致（±0.1 缓冲）。
输出 results/screen/jon/
用法（brain-fly-cpu 环境，套 scratch/memguard.sh）：python screen/jon_screen.py baseline|screen|double|analyze
"""
import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import sugar_mn9_screen as S  # noqa: E402
import segments as SEG  # noqa: E402
from xlsx_lite import read_xlsx  # noqa: E402

FREQ, R_ALL, R_A = 160, 12, 6
ADN1, ADN2, ABN1 = 720575940616185531, 720575940629806974, 720575940630907434
PAPER_160 = dict(aDN1=23.3, aDN2=23.7, aBN1=54.5)
SEED_NULL, N_NULL_SINGLE, N_NULL_PAIRS = 20260919, 50, 20
N_TOP, MARGIN, CALL = 12, 0.1, 0.8
JDIR = S.OUT / "jon"
FI = 0


def jon_ids(fid2i):
    ann = pd.read_csv(S.ANNOT, sep="\t", low_memory=False, usecols=["root_id", "cell_type"]).drop_duplicates("root_id")
    return sorted(int(f) for f in ann.root_id[ann.cell_type.fillna("").str.startswith("JO-")] if int(f) in fid2i)


def setup():
    fids, fid2i = S.load_ids()
    ids = jon_ids(fid2i)
    S.FREQS = (FREQ,)
    S.R_MAX = R_ALL
    S.MN9 = ADN1                      # 读出换成 aDN1（Screen 只用它做 rfc / 索引，不影响其他）
    S.BUILD = S.OUT / ".brian2_build_jon"
    S.CHUNKS = JDIR / "chunks"
    S.sugar_ids = lambda: list(ids)
    JDIR.mkdir(parents=True, exist_ok=True)
    (JDIR / "chunks").mkdir(exist_ok=True)
    return fids, fid2i, ids


def paper_7d():
    X = read_xlsx(str(S.SUPP))
    t = [v for k, v in X.items() if k.startswith("Supp Table 7D")][0]
    c160 = t[0].index(160)
    return [dict(fid=int(r[0]), name=str(r[1]), aDN1_160=float(r[c160])) for r in t[1:] if str(r[0]).isdigit()], X


def state():
    fids, fid2i, ids = setup()
    N = len(fids)
    watch = dict(aDN1=fid2i[ADN1], aDN2=fid2i[ADN2], aBN1=fid2i[ABN1])
    _, bc, _ = S.load_chunk(JDIR / "baseline.npz", N)
    base = {r: bc[r] for r in range(R_ALL)}
    repo = SEG.Repo([JDIR / "chunks"], watch=watch)
    return fids, fid2i, N, watch, base, repo


def counts(repo, base, sil, R, key="aDN1", idx=None):
    out = []
    for r in range(R):
        if any(base[r][n] > 0 for n in sil):
            out.append(repo.get((FI, r, tuple(sorted(sil))), field=key, default=None))
        else:
            out.append(int(base[r][idx]))
    return out


def cmd_baseline():
    fids, fid2i, ids = setup()
    print(f"刺激 {len(ids)} 个 JON（注释 cell_type 以 JO- 开头），{FREQ} Hz", flush=True)
    sc = S.Screen()
    segs = [(FI, r, ()) for r in range(R_ALL)]
    cnts, wall = sc.run_chunk(segs)
    S.save_chunk(JDIR / "baseline.npz", [S.key(*s) for s in segs], cnts, wall)
    for nm, f in (("aDN1", ADN1), ("aDN2", ADN2), ("aBN1", ABN1)):
        v = [int(cnts[r][fid2i[f]]) for r in range(R_ALL)]
        print(f"  {nm}：各实现 {v}，平均 {np.mean(v):.1f} Hz（论文 {PAPER_160[nm]} Hz）", flush=True)
    print("  活跃神经元：", [int((cnts[r] > 0).sum()) for r in range(R_ALL)], flush=True)


def cmd_screen():
    fids, fid2i, N, watch, base, repo = state()
    rows7d, _ = paper_7d()
    p_idx = [fid2i[r["fid"]] for r in rows7d if r["fid"] in fid2i and r["fid"] != ADN1]
    rng = np.random.default_rng(SEED_NULL)
    active = sorted({int(n) for r in range(R_A) for n in np.nonzero(base[r])[0]} - {fid2i[ADN1]})
    null_single = sorted(rng.choice(active, N_NULL_SINGLE, replace=False).tolist())
    pool = [n for n in active if n not in null_single]
    pick = rng.choice(pool, 2 * N_NULL_PAIRS, replace=False).tolist()
    null_pairs = [tuple(sorted(pick[2 * i:2 * i + 2])) for i in range(N_NULL_PAIRS)]
    print(f"P 集合 {len(p_idx)} 个；活跃 {len(active)} 个", flush=True)
    (JDIR / "plan.json").write_text(json.dumps(dict(freq=FREQ, n_P=len(p_idx), n_active=len(active),
                                                    null_single=[int(fids[n]) for n in null_single],
                                                    null_pairs=[[int(fids[a]), int(fids[b])] for a, b in null_pairs]), indent=1))
    keys = SEG.needed_keys(base, R_A, [[n] for n in null_single + p_idx] + [list(p) for p in null_pairs], fi=FI)
    repo.fill(keys, lambda: S.Screen(), JDIR / "chunks", "stageA")
    print("阶段 A 完成", flush=True)


def cmd_double():
    fids, fid2i, N, watch, base, repo = state()
    rows7d, _ = paper_7d()
    plan = json.loads((JDIR / "plan.json").read_text())
    idx = fid2i[ADN1]
    med6 = [float(np.median([counts(repo, base, [fid2i[f]], R_A, idx=idx)[r] for f in plan["null_single"]])) for r in range(R_A)]
    p_idx = [fid2i[r["fid"]] for r in rows7d if r["fid"] in fid2i and r["fid"] != ADN1]
    ann = pd.read_csv(S.ANNOT, sep="\t", low_memory=False, usecols=["root_id", "cell_type", "super_class"]).drop_duplicates("root_id").set_index("root_id")
    eff = []
    for n in p_idx:
        m = counts(repo, base, [n], R_A, idx=idx)
        if None in m:
            continue
        f = int(fids[n])
        eff.append((n, sum(m) / sum(med6), ann.loc[f].super_class if f in ann.index else None,
                    ann.loc[f].cell_type if f in ann.index else None))
    strong = [e[0] for e in eff if abs(1 - e[1]) >= 0.1]
    top = [e[0] for e in sorted([e for e in eff if e[2] != "sensory"], key=lambda e: e[1])[:N_TOP]]
    print(f"阶段 B：效应 ≥ 10% 的 {len(strong)} 个补到 12 个实现；双敲除前 {len(top)} 个：",
          [f"{e[3]}({e[1]:.2f})" for e in sorted([e for e in eff if e[2] != 'sensory'], key=lambda e: e[1])[:N_TOP]], flush=True)
    pairs = [list(p) for p in itertools.combinations(sorted(top), 2)]
    (JDIR / "double_plan.json").write_text(json.dumps(dict(top=[str(fids[n]) for n in top],
                                                           pairs=[[str(fids[a]), str(fids[b])] for a, b in pairs]), indent=1))
    conds = ([[n] for n in strong + top] + [[fid2i[f]] for f in plan["null_single"]]
             + [[fid2i[a], fid2i[b]] for a, b in plan["null_pairs"]])
    keys = SEG.needed_keys(base, R_ALL, conds, fi=FI) + SEG.needed_keys(base, R_ALL, pairs, fi=FI)
    repo.fill(list(dict.fromkeys(keys)), lambda: S.Screen(), JDIR / "chunks", "stageB")
    print("阶段 B 完成", flush=True)


def cmd_analyze():
    fids, fid2i, N, watch, base, repo = state()
    rows7d, X = paper_7d()
    plan = json.loads((JDIR / "plan.json").read_text())
    dplan = json.loads((JDIR / "double_plan.json").read_text()) if (JDIR / "double_plan.json").exists() else None
    idx = fid2i[ADN1]
    ann = pd.read_csv(S.ANNOT, sep="\t", low_memory=False, usecols=["root_id", "cell_type", "super_class", "top_nt"]).drop_duplicates("root_id").set_index("root_id")

    def med(sils, R):
        return [float(np.median([counts(repo, base, s, R, idx=idx)[r] for s in sils])) for r in range(R)]
    ns = [[fid2i[f]] for f in plan["null_single"]]
    npr = [tuple(sorted((fid2i[a], fid2i[b]))) for a, b in plan["null_pairs"]]
    med_s6, med_s12, med_d12 = med(ns, R_A), med(ns, R_ALL), med(npr, R_ALL)

    def ratio(sil, R, double=False):
        m = counts(repo, base, sil, R, idx=idx)
        if None in m:
            return None
        ref = (med_d12 if double else med_s12) if R == R_ALL else med_s6
        return sum(m) / sum(ref)
    base_adn1 = [int(base[r][idx]) for r in range(R_ALL)]
    out = dict(design=dict(freq=FREQ, readout="aDN1", R_A=R_A, R_ALL=R_ALL, call=CALL, n_active=plan["n_active"]),
               baseline=dict(aDN1=base_adn1, mean=round(float(np.mean(base_adn1)), 1), paper=PAPER_160["aDN1"]),
               null_median_single=dict(R6=med_s6, R12=med_s12), null_median_double_R12=med_d12)
    # 与论文表 7D 比：论文给的是绝对 aDN1 放电率，按论文同频率基线（23.3 Hz）归一化
    items, skipped = [], 0
    for r in rows7d:
        if r["fid"] not in fid2i or r["fid"] == ADN1:
            continue
        n = fid2i[r["fid"]]
        v = ratio([n], R_ALL) or ratio([n], R_A)
        if v is None:
            skipped += 1
            continue
        items.append(dict(fid=str(r["fid"]), name=r["name"], paper=round(r["aDN1_160"] / PAPER_160["aDN1"], 4), ours=round(v, 4),
                          cell_type=ann.loc[r["fid"]].cell_type if r["fid"] in ann.index else None))
    o = np.array([x["ours"] for x in items]); pp = np.array([x["paper"] for x in items])
    out["paper_comparison"] = dict(n=len(items), n_skipped_missing_segments=skipped,
                                   spearman=S.spearman(o, pp), pearson=round(float(np.corrcoef(o, pp)[0, 1]), 3),
                                   calls_ours=int((o <= CALL).sum()), calls_paper=int((pp <= CALL).sum()),
                                   call_agreement=round(float(((o <= CALL) == (pp <= CALL)).mean()), 3),
                                   kappa=S.kappa(o <= CALL, pp <= CALL), median_abs_diff=round(float(np.median(np.abs(o - pp))), 3))
    out["required"] = sorted([x for x in items if x["ours"] <= CALL], key=lambda x: x["ours"])[:25]
    if dplan:
        pairs, syn = [], []
        for a_s, b_s in dplan["pairs"]:
            a, b = fid2i[int(a_s)], fid2i[int(b_s)]
            ra, rb, rab = ratio([a], R_ALL), ratio([b], R_ALL), ratio([a, b], R_ALL, double=True)
            if None in (ra, rb, rab):
                continue
            e_exp, e_ab = 1 - ra * rb, 1 - rab
            v = "协同" if e_ab > e_exp + MARGIN else ("亚可加" if e_ab < e_exp - MARGIN else "可加")
            ct = lambda n: (ann.loc[int(fids[n])].cell_type if int(fids[n]) in ann.index else str(fids[n]))
            d = dict(a=ct(a), b=ct(b), ratio_a=round(ra, 4), ratio_b=round(rb, 4), ratio_ab=round(rab, 4),
                     effect_expected=round(e_exp, 4), effect_observed=round(e_ab, 4), delta=round(e_ab - e_exp, 4), verdict=v)
            pairs.append(d)
            if v == "协同":
                syn.append(d)
        out["double"] = dict(n_pairs=len(pairs), n_synergy=len(syn), n_additive=sum(p["verdict"] == "可加" for p in pairs),
                             n_subadditive=sum(p["verdict"] == "亚可加" for p in pairs),
                             synergy=sorted(syn, key=lambda p: -p["delta"])[:10], pairs=pairs)
    (JDIR / "summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("基线 aDN1：", base_adn1, f"平均 {out['baseline']['mean']} Hz（论文 {PAPER_160['aDN1']} Hz）")
    print("与论文表 7D 比：", out["paper_comparison"])
    print("\n效应最强的 10 个：")
    for x in out["required"][:10]:
        print(f"  {str(x['cell_type']):12s} {x['name']:12s} 我们 {x['ours']:.2f} | 论文 {x['paper']:.2f}")
    if dplan and "double" in out:
        print("\n双敲除：", {k: out["double"][k] for k in ("n_pairs", "n_synergy", "n_additive", "n_subadditive")})
        for p in out["double"]["synergy"][:6]:
            print(f"  协同 {p['a']}+{p['b']}：各自 {p['ratio_a']:.2f}/{p['ratio_b']:.2f} → 一起 {p['ratio_ab']:.2f}，Δ {p['delta']:+.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["baseline", "screen", "double", "analyze"])
    dict(baseline=cmd_baseline, screen=cmd_screen, double=cmd_double, analyze=cmd_analyze)[ap.parse_args().cmd]()
