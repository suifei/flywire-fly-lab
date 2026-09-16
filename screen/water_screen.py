#!/usr/bin/env python
"""
水味觉通路：单敲除筛选 + 双敲除，对照论文补充表 6C（模型）与表 5（**论文自己做的**光遗传沉默实验）。

为什么值得做：糖那条通路上，模型对真实实验只对 6/10；水这条通路论文自己报的是 10/11（补充表 10），
而且表 5 的实验结论全部来自这篇论文自己的实验，不是引用旧文献。同一套方法换一条通路，能看出
“模型和实验对得上多少”是通路特定的，还是碰巧。

事先写定（运行前写好）：
  刺激：论文 notebook 里右侧 18 个唇瓣水味觉受体神经元，160 Hz（论文表 5 判定“必需”用的频率）。
  读出：MN9 720575940660219265，每段 1.000 s 试次，与糖的筛选完全相同的段落安排。
  输入实现：r = 0…11，种子 20260914 + r（与糖共用同一套种子，但水的 GRN 不同，所以是不同的脉冲序列）。
  零参照（与糖同口径，处理“任何扰动都让轨迹回归条件均值”的偏差）：
    单敲除 = 每个实现里 50 个随机活跃神经元单敲后 MN9 的中位数（抽样种子 20260918）；
    双敲除 = 每个实现里 20 对“单独都无效”的对照对的中位数。
  两阶段：阶段 A 用前 6 个实现，阶段 B 把 |1 − 比值| ≥ 0.1 的条件补到 12 个实现。
  候选：
    P = 论文补充表 6C 的 200 个里 v783 中 ID 未变的 187 个（去掉读出 MN9 自己）；
    T = 论文表 5 的 11 个类型，单个（论文用的那个）与两侧一起沉默；
    D = 阶段 B 里效应最强的 12 个非感觉神经元两两组合（66 对），以及 20 对零参照对。
  判定：比值 ≤ 0.8 记为“伸喙必需”；双敲除的协同 / 亚可加判据与糖一致（±0.1 缓冲）。
输出 results/screen/water/{summary.json, ...}
用法（brain-fly-cpu 环境，套 scratch/memguard.sh）：python screen/water_screen.py baseline|screen|double|analyze
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sugar_mn9_screen as S  # noqa: E402
from xlsx_lite import read_xlsx  # noqa: E402

WATER = [720575940612950568, 720575940631898285, 720575940606002609, 720575940612579053, 720575940622902535,
         720575940616177458, 720575940660292225, 720575940622486922, 720575940613786774, 720575940629852866,
         720575940625861168, 720575940613996959, 720575940617857694, 720575940644965399, 720575940625203504,
         720575940630553415, 720575940635172191, 720575940634796536]
FREQ, R_ALL, R_A = 160, 12, 6
SEED_NULL, N_NULL_SINGLE, N_NULL_PAIRS = 20260918, 50, 20
N_TOP, MARGIN, CALL = 12, 0.1, 0.8
WDIR = S.OUT / "water"
FI = 0
# 论文表 5 的 11 个类型 → v783 注释 cell_type（Tophat / Tulip 由补充表里的 tophat_a_r / tulip_r 查出）
TYPES = {"Bract": ["DNge173", "DNge174"], "Clavicle": ["AN_GNG_30"], "G2N-1": ["CB0616"], "Phantom": ["CB0062"],
         "Rattle": ["CB0499"], "Roundup": ["CB0553"], "Tophat": ["Z_vPNml1"], "Tulip": ["CB0579"],
         "Usnea": ["CB0008"], "Zorro": ["CB0192"]}
PAPER_SINGLE = {"Bract": 720575940610001220, "Clavicle": 720575940655014049, "G2N-1": 720575940620874757,
                "Phantom": 720575940616103218, "Rattle": 720575940638103349, "Roundup": 720575940623211725,
                "Tophat": 720575940620441024, "Tulip": 720575940617755220, "Usnea": 720575940632648612,
                "Zorro": 720575940629888530}


def setup():
    S.FREQS = (FREQ,)
    S.R_MAX = R_ALL
    S.BUILD = S.OUT / ".brian2_build_water"
    S.CHUNKS = WDIR / "chunks"
    S.sugar_ids = lambda: list(WATER)
    WDIR.mkdir(parents=True, exist_ok=True)
    (WDIR / "chunks").mkdir(exist_ok=True)


def paper_6c():
    X = read_xlsx(str(S.SUPP))
    t = [v for k, v in X.items() if k.startswith("ST 6C")][0]
    hdr = t[0]
    c160 = hdr.index("Normalized:") + 1
    assert hdr[c160] == 160
    return [dict(fid=int(r[0]), name=str(r[1]), norm=float(r[c160])) for r in t[1:]], X


def paper_table5(X):
    t = [v for k, v in X.items() if k.startswith("Supplemental Table 5")][0]
    out = {}
    for r in t[1:]:
        if r[0] in TYPES:
            out[r[0]] = dict(required=str(r[5]).startswith("Yes"), paper_ratio=float(r[6]) if len(r) > 6 and r[6] != "" else None)
    return out


def load_state():
    fids, fid2i = S.load_ids()
    N = len(fids)
    mn9 = fid2i[S.MN9]
    _, bc, _ = S.load_chunk(WDIR / "baseline.npz", N)
    base = {r: bc[r] for r in range(R_ALL)}
    res = {}
    for p in sorted((WDIR / "chunks").glob("*.npz")):
        keys, rows = S.chunk_summary(p, {"mn9": mn9})
        res.update({k: v["mn9"] for k, v in zip(keys, rows)})
    return fids, fid2i, N, mn9, base, res


def counts(res, base, mn9, sil, R):
    return [res.get((FI, r, tuple(sorted(sil)))) if any(base[r][n] > 0 for n in sil) else int(base[r][mn9]) for r in range(R)]


def run_segments(sc, segs, tag, have):
    segs = [s for s in dict.fromkeys(segs) if s not in have]
    if not segs:
        print(f"{tag}：无需补跑", flush=True)
        return sc
    print(f"{tag}：{len(segs)} 段，估计 {len(segs) * 2.0 / 60:.0f} min", flush=True)
    if sc is None:
        sc = S.Screen()
    n_chunks = math.ceil(len(segs) / S.K)
    t0 = time.time(); done = 0
    for c in range(n_chunks):
        path = WDIR / "chunks" / f"{tag}_{c:04d}.npz"
        part = segs[c * S.K:(c + 1) * S.K]
        if path.exists() and S.chunk_keys(path) == part:
            continue
        cnts, wall = sc.run_chunk(part)
        S.save_chunk(path, [S.key(*s) for s in part], cnts, wall)
        done += 1
        el = time.time() - t0
        print(f"  {tag} 块 {c + 1}/{n_chunks}：{wall:.0f} s；已跑 {el / 60:.1f} min，预计还需 {el / done * (n_chunks - c - 1) / 60:.0f} min", flush=True)
    return sc


def cmd_baseline():
    setup()
    fids, fid2i = S.load_ids()
    sc = S.Screen()
    segs = [(FI, r, ()) for r in range(R_ALL)]
    cnts, wall = sc.run_chunk(segs)
    S.save_chunk(WDIR / "baseline.npz", [S.key(*s) for s in segs], cnts, wall)
    mn9 = fid2i[S.MN9]
    per = [int(cnts[r][mn9]) for r in range(R_ALL)]
    act = [int((cnts[r] > 0).sum()) for r in range(R_ALL)]
    print(f"水 {FREQ} Hz 基线：MN9 各实现 {per}（论文表 6A 同频率 10.0 Hz）；活跃神经元 {act}", flush=True)


def cmd_screen():
    setup()
    rows6c, X = paper_6c()
    fids, fid2i, N, mn9, base, res = load_state()
    have = set(res)
    p_ids = [fid2i[r["fid"]] for r in rows6c if r["fid"] in fid2i and r["fid"] != S.MN9]
    ann = pd.read_csv(S.ANNOT, sep="\t", low_memory=False, usecols=["root_id", "cell_type", "side"]).drop_duplicates("root_id")
    members = {t: sorted(int(x) for x in ann.root_id[ann.cell_type.isin(cts)] if int(x) in fid2i) for t, cts in TYPES.items()}
    rng = np.random.default_rng(SEED_NULL)
    active = sorted({int(n) for r in range(R_A) for n in np.nonzero(base[r])[0]} - {mn9})
    null_single = sorted(rng.choice(active, min(N_NULL_SINGLE, len(active)), replace=False).tolist())
    pool = [n for n in active if n not in null_single]
    pick = rng.choice(pool, 2 * N_NULL_PAIRS, replace=False).tolist()
    null_pairs = [tuple(sorted(pick[2 * i:2 * i + 2])) for i in range(N_NULL_PAIRS)]
    print(f"P 集合 {len(p_ids)} 个；类型 {len(members)} 个（成员数 { {t: len(m) for t, m in members.items()} }）；活跃 {len(active)} 个", flush=True)
    (WDIR / "plan.json").write_text(json.dumps(dict(freq=FREQ, R_A=R_A, R_ALL=R_ALL, n_P=len(p_ids), n_active=len(active),
                                                    null_single=[int(fids[n]) for n in null_single],
                                                    null_pairs=[[int(fids[a]), int(fids[b])] for a, b in null_pairs],
                                                    members={t: [str(x) for x in m] for t, m in members.items()}), ensure_ascii=False, indent=1))
    segs = []
    for r in range(R_A):
        for n in null_single + p_ids:
            if base[r][n] > 0:
                segs.append((FI, r, (n,)))
        for t, mem in members.items():
            for sil in ([fid2i[PAPER_SINGLE[t]]], sorted(fid2i[x] for x in mem)):
                if any(base[r][n] > 0 for n in sil):
                    segs.append((FI, r, tuple(sil)))
        for p in null_pairs:
            if any(base[r][n] > 0 for n in p):
                segs.append((FI, r, p))
    run_segments(None, segs, "stageA", have)
    print("阶段 A 完成", flush=True)


def cmd_double():
    """阶段 B：把强效应条件补到 12 个实现，并做 66 对双敲除（前 6 个实现）。"""
    setup()
    rows6c, X = paper_6c()
    fids, fid2i, N, mn9, base, res = load_state()
    have = set(res)
    plan = json.loads((WDIR / "plan.json").read_text())
    med_s6 = [float(np.median([counts(res, base, mn9, [fid2i[f]], R_A)[r] for f in plan["null_single"]])) for r in range(R_A)]
    p_ids = [fid2i[r["fid"]] for r in rows6c if r["fid"] in fid2i and r["fid"] != S.MN9]
    ann = pd.read_csv(S.ANNOT, sep="\t", low_memory=False, usecols=["root_id", "cell_type", "side", "super_class"]).drop_duplicates("root_id").set_index("root_id")
    eff = []
    for n in p_ids:
        m = counts(res, base, mn9, [n], R_A)
        if None in m:
            continue
        ratio = sum(m) / sum(med_s6)
        f = int(fids[n])
        sc_ = ann.loc[f].super_class if f in ann.index else None
        eff.append((n, ratio, sc_, ann.loc[f].cell_type if f in ann.index else None))
    strong = [e for e in eff if abs(1 - e[1]) >= 0.1]
    top = [e[0] for e in sorted([e for e in eff if e[2] != "sensory"], key=lambda e: e[1])[:N_TOP]]
    print(f"阶段 B：效应 ≥ 10% 的 {len(strong)} 个补到 12 个实现；双敲除取前 {len(top)} 个非感觉神经元",
          [f"{e[3]}({e[1]:.2f})" for e in sorted([e for e in eff if e[2] != 'sensory'], key=lambda e: e[1])[:N_TOP]], flush=True)
    segs = []
    for r in range(R_A, R_ALL):
        for f in plan["null_single"]:
            if base[r][fid2i[f]] > 0:
                segs.append((FI, r, (fid2i[f],)))
        for n, _ratio, _sc, _ct in strong:
            if base[r][n] > 0:
                segs.append((FI, r, (n,)))
        for t in TYPES:
            for sil in ([fid2i[PAPER_SINGLE[t]]], sorted(fid2i[int(x)] for x in plan["members"][t])):
                if any(base[r][n] > 0 for n in sil):
                    segs.append((FI, r, tuple(sil)))
        for a, b in plan["null_pairs"]:
            p = tuple(sorted((fid2i[a], fid2i[b])))
            if any(base[r][n] > 0 for n in p):
                segs.append((FI, r, p))
    pairs = [tuple(sorted(p)) for p in __import__("itertools").combinations(top, 2)]
    for r in range(R_ALL):
        for p in pairs:
            if any(base[r][n] > 0 for n in p):
                segs.append((FI, r, p))
    (WDIR / "double_plan.json").write_text(json.dumps(dict(top=[str(fids[n]) for n in top],
                                                           pairs=[[str(fids[a]), str(fids[b])] for a, b in pairs]), indent=1))
    run_segments(None, segs, "stageB", have)
    print("阶段 B 完成", flush=True)


def cmd_analyze():
    setup()
    rows6c, X = paper_6c()
    t5 = paper_table5(X)
    fids, fid2i, N, mn9, base, res = load_state()
    plan = json.loads((WDIR / "plan.json").read_text())
    dplan = json.loads((WDIR / "double_plan.json").read_text()) if (WDIR / "double_plan.json").exists() else None
    ann = pd.read_csv(S.ANNOT, sep="\t", low_memory=False, usecols=["root_id", "cell_type", "side", "top_nt", "super_class"]).drop_duplicates("root_id").set_index("root_id")

    def med(sils, R):
        return [float(np.median([counts(res, base, mn9, s, R)[r] for s in sils])) for r in range(R)]
    ns = [[fid2i[f]] for f in plan["null_single"]]
    npairs = [tuple(sorted((fid2i[a], fid2i[b]))) for a, b in plan["null_pairs"]]
    med_s6, med_s12 = med(ns, R_A), med(ns, R_ALL)
    med_d6, med_d12 = med(npairs, R_A), med(npairs, R_ALL)

    def ratio(sil, R, double=False):
        m = counts(res, base, mn9, sil, R)
        if None in m:
            return None
        ref = (med_d12 if double else med_s12) if R == R_ALL else (med_d6 if double else med_s6)
        return sum(m) / sum(ref)
    out = dict(design=dict(freq=FREQ, R_A=R_A, R_ALL=R_ALL, call=CALL, margin=MARGIN, n_active=plan["n_active"]),
               baseline_mn9=[int(base[r][mn9]) for r in range(R_ALL)],
               null_median_single=dict(R6=med_s6, R12=med_s12), null_median_double=dict(R6=med_d6, R12=med_d12))
    # (a) 与论文补充表 6C 比
    items = []
    for row in rows6c:
        if row["fid"] not in fid2i or row["fid"] == S.MN9:
            continue
        n = fid2i[row["fid"]]
        r6 = ratio([n], R_A)
        r12 = ratio([n], R_ALL)
        if r6 is None:
            continue
        items.append(dict(fid=str(row["fid"]), name=row["name"], paper=round(row["norm"], 4), ours=round(r12 if r12 is not None else r6, 4),
                          R=R_ALL if r12 is not None else R_A,
                          cell_type=ann.loc[row["fid"]].cell_type if row["fid"] in ann.index else None))
    o = np.array([x["ours"] for x in items]); pp = np.array([x["paper"] for x in items])
    out["paper_comparison"] = dict(n=len(items), spearman=S.spearman(o, pp), pearson=round(float(np.corrcoef(o, pp)[0, 1]), 3),
                                   calls_ours=int((o <= CALL).sum()), calls_paper=int((pp <= CALL).sum()),
                                   call_agreement=round(float(((o <= CALL) == (pp <= CALL)).mean()), 3),
                                   kappa=S.kappa(o <= CALL, pp <= CALL), median_abs_diff=round(float(np.median(np.abs(o - pp))), 3))
    # (b) 11 个类型对论文自己的实验
    types = {}
    for t, cts in TYPES.items():
        single = ratio([fid2i[PAPER_SINGLE[t]]], R_ALL) or ratio([fid2i[PAPER_SINGLE[t]]], R_A)
        mem = sorted(fid2i[int(x)] for x in plan["members"][t])
        bil = ratio(mem, R_ALL) or ratio(mem, R_A)
        types[t] = dict(members=[str(fids[n]) for n in mem], experiment_required=t5[t]["required"], paper_ratio=t5[t]["paper_ratio"],
                        ours_single=round(single, 4) if single else None, ours_bilateral=round(bil, 4) if bil else None)
    score = {}
    for name, get in (("paper", lambda t: types[t]["paper_ratio"]), ("ours_single", lambda t: types[t]["ours_single"]),
                      ("ours_bilateral", lambda t: types[t]["ours_bilateral"])):
        ok = [t for t in types if get(t) is not None and (get(t) <= CALL) == types[t]["experiment_required"]]
        score[name] = dict(correct=len(ok), of=len(types), correct_types=ok,
                           predicted_required=[t for t in types if get(t) is not None and get(t) <= CALL])
    out["types"], out["experiment_score"] = types, score
    # (c) 双敲除
    if dplan:
        pairs, skipped_pairs = [], []
        for a_s, b_s in dplan["pairs"]:
            a, b = fid2i[int(a_s)], fid2i[int(b_s)]
            ra, rb, rab = ratio([a], R_ALL), ratio([b], R_ALL), ratio([a, b], R_ALL, double=True)
            if None in (ra, rb, rab):          # 不再静默跳过：记下来，最后报出去
                skipped_pairs.append([a_s, b_s])
                continue
            e_exp, e_ab = 1 - ra * rb, 1 - rab
            v = "协同" if e_ab > e_exp + MARGIN else ("亚可加" if e_ab < e_exp - MARGIN else "可加")
            ct = lambda n: ann.loc[int(fids[n])].cell_type if int(fids[n]) in ann.index else str(fids[n])
            pairs.append(dict(a=ct(a), b=ct(b), ratio_a=round(ra, 4), ratio_b=round(rb, 4), ratio_ab=round(rab, 4),
                              effect_expected=round(e_exp, 4), effect_observed=round(e_ab, 4), delta=round(e_ab - e_exp, 4), verdict=v))
        if skipped_pairs:
            print(f"⚠️ {len(skipped_pairs)} 对缺少段，未计入（用 python screen/audit.py --fill 补跑）", flush=True)
        out["double"] = dict(n_pairs=len(pairs), n_skipped_missing_segments=len(skipped_pairs), n_synergy=sum(p["verdict"] == "协同" for p in pairs),
                             n_additive=sum(p["verdict"] == "可加" for p in pairs),
                             n_subadditive=sum(p["verdict"] == "亚可加" for p in pairs),
                             synergy=sorted([p for p in pairs if p["verdict"] == "协同"], key=lambda p: -p["delta"]), pairs=pairs)
    (WDIR / "summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("基线 MN9：", out["baseline_mn9"], "（论文 160 Hz 水：10.0 Hz）")
    print("与论文表 6C 比：", out["paper_comparison"])
    print("\n11 个类型（实验来自论文自己）：")
    for t, v in types.items():
        mark = lambda x: "—" if x is None else f"{x:.2f}" + ("✅" if (x <= CALL) == v["experiment_required"] else "❌")
        print(f"  {t:9s} 实验{'必需' if v['experiment_required'] else '不必需'} | 论文模型 {mark(v['paper_ratio'])} | 我们单个 {mark(v['ours_single'])} | 两侧 {mark(v['ours_bilateral'])}")
    print("对上的个数：", {k: f"{v['correct']}/{v['of']}" for k, v in score.items()})
    if dplan and "double" in out:
        print("\n双敲除：", {k: out["double"][k] for k in ("n_pairs", "n_synergy", "n_additive", "n_subadditive")})
        for p in out["double"]["synergy"][:6]:
            print(f"  协同 {p['a']}+{p['b']}：各自 {p['ratio_a']:.2f}/{p['ratio_b']:.2f} → 一起 {p['ratio_ab']:.2f}，Δ {p['delta']:+.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["baseline", "screen", "double", "analyze"])
    dict(baseline=cmd_baseline, screen=cmd_screen, double=cmd_double, analyze=cmd_analyze)[ap.parse_args().cmd]()
