#!/usr/bin/env python
"""
用论文准确的刺激名单重跑 JON 通路：把最后一点差异也闭合掉。

24 / 24.1 节的残留问题：论文 notebook 里 `neu_JON_all` 这个变量没能直接提取，我们先用了注释表里全部 1,091 个 JO- 神经元，
刺激过强；调低频率只补回了一部分差距，推测剩下的来自“刺激集合不同”。现在把名单找回来了，可以直接验证：

  从补充表 7A 反推：被刺激的神经元放电率会精确跟随刺激频率（20 Hz 列 ≈ 20、100 ≈ 100、200 ≈ 200，因为泊松输入直驱且不应期为 0）。
  按此筛出 **146 个**，其中 145 个注释 cell_type 以 JO 开头（另 1 个无注释），145 个在 v783 模型里。
  独立核对：notebook 里 JON_CE(70) + JON_F(60) + JON_D_m(16) 的并集恰好也是这 146 个，两者**完全一致**。
  → 论文的 neu_JON_all = 这三个子集的并集。名单存于 results/screen/jon_all_paper.json。

事先写定（运行前写好）：
  刺激这 146 个（在模型里的 145 个）、160 Hz（论文表 7D 同频率），读出 aDN1，前 6 个实现，判据 ≤ 0.8。
  候选：论文表 7D 效应最强的 30 个（覆盖论文判必需的 6 个）+ 50 个随机活跃神经元作零参照（种子 20260921）。
  **事先声明的预测：刺激集合与论文一致后，aDN1 基线应接近论文的 23.3 Hz，且论文判必需的 6 个我们应当判出大部分。**
输出 results/screen/jon_paper/summary.json
用法（brain-fly-cpu 环境，套 scratch/memguard.sh）：python screen/jon_paper.py baseline|screen|analyze
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import sugar_mn9_screen as S  # noqa: E402
import jon_screen as J  # noqa: E402
import segments as SEG  # noqa: E402

FREQS = (160,)
R_ALL, R_A = 12, 6
N_TOP_PAPER, N_NULL, SEED_NULL = 30, 50, 20260921
CALL = 0.8
WDIR = S.OUT / "jon_paper"
PAPER_SET = json.loads((S.OUT / "jon_all_paper.json").read_text())


def setup():
    fids, fid2i = S.load_ids()
    ids = [f for f in PAPER_SET if f in fid2i]      # 论文的 146 个里在模型中的 145 个
    S.FREQS = FREQS
    S.R_MAX = R_ALL
    S.MN9 = J.ADN1
    S.BUILD = S.OUT / ".brian2_build_jon_paper"
    S.CHUNKS = WDIR / "chunks"
    S.sugar_ids = lambda: list(ids)
    WDIR.mkdir(parents=True, exist_ok=True)
    (WDIR / "chunks").mkdir(exist_ok=True)
    return fids, fid2i, ids


def cmd_baseline():
    fids, fid2i, ids = setup()
    print(f"刺激 {len(ids)} 个 JON，频率 {FREQS}", flush=True)
    sc = S.Screen()
    segs = [(fi, r, ()) for fi in range(len(FREQS)) for r in range(R_ALL)]
    out = {}
    for c in range(0, len(segs), S.K):
        part = segs[c:c + S.K]
        cnts, wall = sc.run_chunk(part)
        S.save_chunk(WDIR / f"baseline_{c // S.K:02d}.npz", [S.key(*s) for s in part], cnts, wall)
    idx = fid2i[J.ADN1]
    for f_i, f in enumerate(FREQS):
        v = []
        for p in sorted(WDIR.glob("baseline_*.npz")):
            keys, rows = S.chunk_summary(p, {"aDN1": idx})
            v += [row["aDN1"] for k, row in zip(keys, rows) if k[0] == f_i]
        out[f] = dict(per_rep=v, mean=round(float(np.mean(v)), 1))
        print(f"  {f} Hz：aDN1 平均 {out[f]['mean']} Hz（论文 {J.PAPER_160['aDN1']}）", flush=True)
    best = min(FREQS, key=lambda f: abs(out[f]["mean"] - J.PAPER_160["aDN1"]))
    print(f"选定 f* = {best} Hz（最接近论文基线）", flush=True)
    (WDIR / "baseline.json").write_text(json.dumps(dict(freqs=list(FREQS), stats={str(k): v for k, v in out.items()},
                                                        chosen=best, paper=J.PAPER_160["aDN1"]), indent=1))


def load_base(fid2i):
    fids, _ = S.load_ids()
    N = len(fids)
    meta = json.loads((WDIR / "baseline.json").read_text())
    fi = FREQS.index(meta["chosen"])
    base = {}
    for p in sorted(WDIR.glob("baseline_*.npz")):
        keys, counts, _ = S.load_chunk(p, N)
        for k, v in zip(keys, counts):
            if k[0] == fi:
                base[k[1]] = v
    return fi, base, meta


def cmd_screen():
    fids, fid2i, ids = setup()
    fi, base, meta = load_base(fid2i)
    rows7d, _ = J.paper_7d()
    top = sorted([r for r in rows7d if r["fid"] in fid2i and r["fid"] != J.ADN1],
                 key=lambda r: r["aDN1_160"])[:N_TOP_PAPER]
    rng = np.random.default_rng(SEED_NULL)
    active = sorted({int(n) for r in range(R_A) for n in np.nonzero(base[r])[0]} - {fid2i[J.ADN1]})
    null = sorted(rng.choice(active, N_NULL, replace=False).tolist())
    print(f"f* = {meta['chosen']} Hz；论文效应最强 {len(top)} 个 + {len(null)} 个零参照；活跃 {len(active)}", flush=True)
    (WDIR / "plan.json").write_text(json.dumps(dict(freq=meta["chosen"], fi=fi, top=[str(r["fid"]) for r in top],
                                                    null=[int(fids[n]) for n in null]), indent=1))
    repo = SEG.Repo([WDIR / "chunks"], watch={"aDN1": fid2i[J.ADN1]})
    conds = [[fid2i[r["fid"]] for r in top][i:i + 1] for i in range(len(top))] + [[n] for n in null]
    keys = SEG.needed_keys(base, R_A, conds, fi=fi)
    repo.fill(keys, lambda: S.Screen(), WDIR / "chunks", "weak")
    print("完成", flush=True)


def cmd_analyze():
    fids, fid2i, ids = setup()
    fi, base, meta = load_base(fid2i)
    plan = json.loads((WDIR / "plan.json").read_text())
    idx = fid2i[J.ADN1]
    repo = SEG.Repo([WDIR / "chunks"], watch={"aDN1": idx})
    rows7d, _ = J.paper_7d()
    p7 = {r["fid"]: r for r in rows7d}

    def cnt(sil):
        return [repo.get((fi, r, tuple(sorted(sil))), field="aDN1", default=None) if any(base[r][n] > 0 for n in sil)
                else int(base[r][idx]) for r in range(R_A)]
    med = [float(np.median([cnt([fid2i[f]])[r] for f in plan["null"]])) for r in range(R_A)]
    ann = pd.read_csv(S.ANNOT, sep="\t", low_memory=False, usecols=["root_id", "cell_type"]).drop_duplicates("root_id").set_index("root_id")
    strong = json.loads((S.OUT / "jon" / "summary.json").read_text())
    items = []
    for f in plan["top"]:
        f = int(f)
        m = cnt([fid2i[f]])
        if None in m:
            continue
        ours = sum(m) / sum(med)
        paper = p7[f]["aDN1_160"] / J.PAPER_160["aDN1"]
        items.append(dict(fid=str(f), name=p7[f]["name"], cell_type=ann.loc[f].cell_type if f in ann.index else None,
                          paper=round(paper, 4), ours_weak=round(ours, 4)))
    # 24 节（160 Hz、强刺激）下同样这些神经元的比值
    strong_items = {x["fid"]: x["ours"] for x in strong.get("required", [])}
    o = np.array([x["ours_weak"] for x in items]); pp = np.array([x["paper"] for x in items])
    paper_req = [x for x in items if x["paper"] <= CALL]
    hit = [x for x in paper_req if x["ours_weak"] <= CALL]
    out = dict(design=dict(freqs=list(FREQS), chosen=meta["chosen"], baseline_stats=meta["stats"], R=R_A, call=CALL,
                           n_top_paper=len(items), n_null=len(plan["null"])),
               null_median=med, items=sorted(items, key=lambda x: x["ours_weak"]),
               comparison=dict(pearson=round(float(np.corrcoef(o, pp)[0, 1]), 3), spearman=S.spearman(o, pp),
                               calls_ours=int((o <= CALL).sum()), calls_paper=len(paper_req),
                               paper_required_we_also_call=len(hit),
                               call_agreement=round(float(((o <= CALL) == (pp <= CALL)).mean()), 3)))
    (WDIR / "summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"f* = {meta['chosen']} Hz，aDN1 基线 {meta['stats'][str(meta['chosen'])]['mean']} Hz（论文 {meta['paper']}）")
    print(f"论文效应最强的 {len(items)} 个里：论文判必需 {len(paper_req)} 个，我们（弱刺激）判必需 {out['comparison']['calls_ours']} 个，"
          f"其中与论文重合 {len(hit)} 个")
    print(f"相关：Pearson {out['comparison']['pearson']}，判定一致率 {out['comparison']['call_agreement']}\n")
    print(f"{'神经元':14s} {'名称':12s} {'论文':>7s} {'我们(弱)':>9s} {'我们(强,160Hz)':>14s}")
    for x in out["items"][:12]:
        st = strong_items.get(x["fid"], "—")
        print(f"{str(x['cell_type']):14s} {x['name']:12s} {x['paper']:7.2f} {x['ours_weak']:9.2f} {str(st):>14s}")


def cmd_full():
    """用论文名单把整条通路重做一遍（P 集合 + 双敲除），口径与糖 / 水 / 24 节完全相同，取代 24 节里用过宽刺激得到的数字。"""
    import itertools
    fids, fid2i, ids = setup()
    fi, base, meta = load_base(fid2i)
    rows7d, _ = J.paper_7d()
    p_idx = [fid2i[r["fid"]] for r in rows7d if r["fid"] in fid2i and r["fid"] != J.ADN1]
    plan = json.loads((WDIR / "plan.json").read_text())
    repo = SEG.Repo([WDIR / "chunks"], watch={"aDN1": fid2i[J.ADN1]})
    active = sorted({int(n) for r in range(R_A) for n in np.nonzero(base[r])[0]} - {fid2i[J.ADN1]})
    print(f"P 集合 {len(p_idx)} 个；活跃 {len(active)} 个（论文名单刺激）", flush=True)
    keys = SEG.needed_keys(base, R_A, [[n] for n in p_idx], fi=fi)
    repo.fill(keys, lambda: S.Screen(), WDIR / "chunks", "full")
    # 双敲除：效应最强的 12 个非感觉神经元
    med = [float(np.median([[repo.get((fi, r, (fid2i[f],)), field="aDN1", default=None) if base[r][fid2i[f]] > 0 else int(base[r][fid2i[J.ADN1]])
                             for r in range(R_A)][r] for f in plan["null"]])) for r in range(R_A)]
    ann = pd.read_csv(S.ANNOT, sep="\t", low_memory=False, usecols=["root_id", "cell_type", "super_class"]).drop_duplicates("root_id").set_index("root_id")
    eff = []
    for n in p_idx:
        m = [repo.get((fi, r, (n,)), field="aDN1", default=None) if base[r][n] > 0 else int(base[r][fid2i[J.ADN1]]) for r in range(R_A)]
        if None in m:
            continue
        f = int(fids[n])
        eff.append((n, sum(m) / sum(med), ann.loc[f].super_class if f in ann.index else None, ann.loc[f].cell_type if f in ann.index else None))
    top = [e[0] for e in sorted([e for e in eff if e[2] != "sensory"], key=lambda e: e[1])[:12]]
    print("双敲除前 12 个：", [f"{e[3]}({e[1]:.2f})" for e in sorted([e for e in eff if e[2] != 'sensory'], key=lambda e: e[1])[:12]], flush=True)
    pairs = [list(pp) for pp in itertools.combinations(sorted(top), 2)]
    (WDIR / "full_plan.json").write_text(json.dumps(dict(top=[str(fids[n]) for n in top],
                                                          pairs=[[str(fids[a]), str(fids[b])] for a, b in pairs]), indent=1))
    repo.fill(SEG.needed_keys(base, R_A, pairs, fi=fi), lambda: S.Screen(), WDIR / "chunks", "fullpairs")
    print("完成", flush=True)


def cmd_full_analyze():
    """分析 full 跑出来的全通路结果，口径与 24 节（jon_screen analyze）逐项对应，用来取代其中过宽刺激得到的数字。

    口径说明（与 24 节的唯一差别就是刺激名单：146 个论文 JON vs 1,091 个全部 JO-）：
      零参照仍用 plan.json 里那 50 个随机活跃神经元（单敲）；双敲的零参照这里没有单独跑，
      因此配对用**单敲零参照**，与糖 / 水通路的 R6 口径一致，并在输出里注明。
    """
    import itertools
    fids, fid2i, ids = setup()
    fi, base, meta = load_base(fid2i)
    idx = fid2i[J.ADN1]
    plan = json.loads((WDIR / "plan.json").read_text())
    fplan = json.loads((WDIR / "full_plan.json").read_text())
    repo = SEG.Repo([WDIR / "chunks"], watch={"aDN1": idx})
    rows7d, _ = J.paper_7d()
    ann = pd.read_csv(S.ANNOT, sep="\t", low_memory=False,
                      usecols=["root_id", "cell_type", "super_class", "top_nt"]).drop_duplicates("root_id").set_index("root_id")

    def cnt(sil):
        return [repo.get((fi, r, tuple(sorted(sil))), field="aDN1", default=None) if any(base[r][n] > 0 for n in sil)
                else int(base[r][idx]) for r in range(R_A)]
    med = [float(np.median([cnt([fid2i[f]])[r] for f in plan["null"]])) for r in range(R_A)]

    def ratio(sil):
        m = cnt(sil)
        return None if None in m else sum(m) / sum(med)
    base_adn1 = [int(base[r][idx]) for r in range(R_A)]
    active = sorted({int(n) for r in range(R_A) for n in np.nonzero(base[r])[0]} - {idx})
    out = dict(design=dict(freq=meta["chosen"], readout="aDN1", R=R_A, call=CALL, n_active=len(active),
                           n_stim=len(ids), note="刺激 = 论文 neu_JON_all 的 146 个里在 v783 模型中的 %d 个；双敲零参照用单敲中位数" % len(ids)),
               baseline=dict(aDN1=base_adn1, mean=round(float(np.mean(base_adn1)), 1), paper=J.PAPER_160["aDN1"]),
               null_median_single=med)
    items, skipped = [], 0
    for r in rows7d:
        if r["fid"] not in fid2i or r["fid"] == J.ADN1:
            continue
        v = ratio([fid2i[r["fid"]]])
        if v is None:
            skipped += 1
            continue
        items.append(dict(fid=str(r["fid"]), name=r["name"], paper=round(r["aDN1_160"] / J.PAPER_160["aDN1"], 4), ours=round(v, 4),
                          cell_type=ann.loc[r["fid"]].cell_type if r["fid"] in ann.index else None))
    o = np.array([x["ours"] for x in items]); pp = np.array([x["paper"] for x in items])
    out["paper_comparison"] = dict(n=len(items), n_skipped_missing_segments=skipped,
                                   spearman=S.spearman(o, pp), pearson=round(float(np.corrcoef(o, pp)[0, 1]), 3),
                                   calls_ours=int((o <= CALL).sum()), calls_paper=int((pp <= CALL).sum()),
                                   call_agreement=round(float(((o <= CALL) == (pp <= CALL)).mean()), 3),
                                   kappa=S.kappa(o <= CALL, pp <= CALL),
                                   median_abs_diff=round(float(np.median(np.abs(o - pp))), 3))
    out["required"] = sorted([x for x in items if x["ours"] <= CALL], key=lambda x: x["ours"])[:25]
    # 集中度（口径与 21 节 concentration.py 相同：效应 = max(0, 1 − 比值)，全部活跃神经元）
    eff, ok = [], 0
    for n in active:
        v = ratio([n])
        if v is None:
            continue
        ok += 1
        eff.append(max(0.0, 1 - v))
    if ok:
        import concentration as C
        e = np.array(eff)
        out["concentration"] = dict(n_scored=ok, n_required=int((e >= 0.2).sum()),
                                    frac_required=round(float((e >= 0.2).mean()), 4),
                                    gini=round(C.gini(e), 4), n80=C.n80(e),
                                    max_effect=round(float(e.max()), 3), median_effect=round(float(np.median(e)), 4),
                                    note="只覆盖 plan/full 已跑的单敲段；未跑到的活跃神经元被跳过")
    # 双敲除
    MARGIN = 0.1
    pairs, syn = [], []
    for a_s, b_s in fplan["pairs"]:
        a, b = fid2i[int(a_s)], fid2i[int(b_s)]
        ra, rb, rab = ratio([a]), ratio([b]), ratio([a, b])
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
    (WDIR / "full_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    old = json.loads((S.OUT / "jon" / "summary.json").read_text())
    print(f"刺激 {len(ids)} 个论文 JON（24 节用的是 1,091 个全部 JO-）")
    print(f"基线 aDN1 {out['baseline']['mean']} Hz（论文 {J.PAPER_160['aDN1']}；24 节 {old['baseline']['mean']}）")
    pc, po = out["paper_comparison"], old["paper_comparison"]
    print(f"\n{'与论文表 7D 比':22s} {'本次（论文名单）':>16s} {'24 节（全部 JO-）':>18s}")
    for k in ("n", "pearson", "spearman", "calls_ours", "calls_paper", "call_agreement", "kappa", "median_abs_diff"):
        print(f"{k:22s} {str(pc[k]):>16s} {str(po.get(k)):>18s}")
    print(f"\n判为必需的 {len(out['required'])} 个：")
    for x in out["required"]:
        print(f"  {str(x['cell_type']):12s} {x['name']:14s} 我们 {x['ours']:.2f} | 论文 {x['paper']:.2f}")
    if "concentration" in out:
        c = out["concentration"]
        print(f"\n集中度：活跃 {len(active)}（评分 {c['n_scored']}），必需 {c['n_required']} 个，"
              f"基尼 {c['gini']}，n80 {c['n80']}，最大效应 {c['max_effect']}")
    print("\n双敲除：", {k: out["double"][k] for k in ("n_pairs", "n_synergy", "n_additive", "n_subadditive")},
          f"（24 节：{old['double']['n_pairs']} 对，协同 {old['double']['n_synergy']}）")
    for p in sorted(pairs, key=lambda p: -p["delta"])[:5]:
        print(f"  {p['a']}+{p['b']}：各自 {p['ratio_a']:.2f}/{p['ratio_b']:.2f} → 一起 {p['ratio_ab']:.2f}，Δ {p['delta']:+.2f}（{p['verdict']}）")
    print("\n写入", WDIR / "full_summary.json")


def cmd_full_conc():
    """把 596 个活跃神经元全部单敲一遍，让 JON 的集中度能和 22.2 节的糖 / 水两列直接比。

    24.3 节的集中度只覆盖 304 个评分神经元（论文表 7D 的 280 个 + 50 个零参照），口径与糖 / 水不同，
    所以当时明确标了“不能放进三通路排序表”。这里补齐缺的那部分段，然后用 concentration.py 完全相同的定义重算。
    口径（与 22.2 节逐字一致）：效应 e = max(0, 1 − 比值)，比值用同实现的零参照中位数修正，前 6 个实现；
    frac_required = 效应 ≥ 0.2 的占比；gini = 效应分布的基尼系数；n80 = 贡献 80% 总效应所需的神经元个数。
    """
    fids, fid2i, ids = setup()
    fi, base, meta = load_base(fid2i)
    idx = fid2i[J.ADN1]
    active = sorted({int(n) for r in range(R_A) for n in np.nonzero(base[r])[0]} - {idx})
    repo = SEG.Repo([WDIR / "chunks"], watch={"aDN1": idx})
    keys = SEG.needed_keys(base, R_A, [[n] for n in active], fi=fi)
    print(f"活跃 {len(active)} 个 → 需要 {len(keys)} 段，缺 {len(repo.need(keys))} 段", flush=True)
    repo.fill(keys, lambda: S.Screen(), WDIR / "chunks", "conc")

    import concentration as C
    plan = json.loads((WDIR / "plan.json").read_text())

    def cnt(sil):
        return [repo.get((fi, r, tuple(sorted(sil))), field="aDN1", default=None) if any(base[r][n] > 0 for n in sil)
                else int(base[r][idx]) for r in range(R_A)]
    med = [float(np.median([cnt([fid2i[f]])[r] for f in plan["null"]])) for r in range(R_A)]
    eff, scored_ids, skipped = [], [], 0
    for n in active:
        m = cnt([n])
        if None in m:
            skipped += 1
            continue
        scored_ids.append(n)
        eff.append(max(0.0, 1 - sum(m) / sum(med)))
    e = np.array(eff)
    # 连线预测力 G3，口径与 22.2 节 concentration.py 的 pathway() 完全一致（活跃度 × 有符号 1–3 跳通路和）
    import structure_vs_function as SF
    rate = {n: float(np.mean([base[r][n] for r in range(R_A)])) for n in active}
    A, pos, M, j, col1, col2, col3 = SF.subgraph(scored_ids, idx)
    g3 = np.array([rate[n] * float(col1[pos[n]] + col2[pos[n]] + col3[pos[n]]) for n in scored_ids])
    out = dict(name="JON 160 Hz（论文名单）", n_active=len(active), n_scored=len(eff), n_skipped=skipped,
               g3_spearman=S.spearman(g3, e),
               frac_required=round(float((e >= 0.2).mean()), 4), n_required=int((e >= 0.2).sum()),
               gini=round(C.gini(e), 4), n80=C.n80(e),
               max_effect=round(float(e.max()), 3), median_effect=round(float(np.median(e)), 4))
    (WDIR / "concentration_full.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    old = json.loads((S.OUT / "concentration.json").read_text())
    print(f"\n{'通路':22s} {'活跃':>6s} {'评分':>6s} {'必需':>5s} {'基尼':>7s} {'n80':>5s} {'最大效应':>8s}")
    for r in old[:2]:
        print(f"{r['name']:22s} {r['n_active']:6d} {r['n_scored']:6d} {r['n_required']:5d} {r['gini']:7.3f} {str(r['n80']):>5s} {r['max_effect']:8.2f}")
    print(f"{'JON 160Hz 旧(304 评分)':22s} {old[2]['n_active']:6d} {old[2]['n_scored']:6d} {old[2]['n_required']:5d} "
          f"{old[2]['gini']:7.3f} {str(old[2]['n80']):>5s} {old[2]['max_effect']:8.2f}")
    print(f"{'JON 160Hz 新(全量)':22s} {out['n_active']:6d} {out['n_scored']:6d} {out['n_required']:5d} "
          f"{out['gini']:7.3f} {str(out['n80']):>5s} {out['max_effect']:8.2f}")
    print("\n写入", WDIR / "concentration_full.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["baseline", "screen", "full", "analyze", "full_analyze", "full_conc"])
    dict(baseline=cmd_baseline, screen=cmd_screen, full=cmd_full, analyze=cmd_analyze, full_analyze=cmd_full_analyze, full_conc=cmd_full_conc)[ap.parse_args().cmd]()
