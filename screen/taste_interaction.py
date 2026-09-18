#!/usr/bin/env python
"""复现论文补充表 4：糖 / 水 / 苦 / Ir94e 四味及其两两组合（全脑）。

论文口径（表 4 抬头）：「各味觉受体神经元的发放率**选成让 MN9 达到 40 Hz**」，
然后给出 613 个神经元在 8 个条件下的平均发放率：
  Sugar_only / Water_only / Bitter_only / Ir94e_only /
  Sugar_Bitter / Sugar_Ir94e / Water_Bitter / Water_Ir94e

**刺激名单是反推的**（论文 notebook 没公开）。用 §24.2 对 JON 用过的同一招：
看表 4 里发放 > 60 Hz 的神经元是哪些类型——
  苦 → LB1c / LB1a,LB1d / LB1b；Ir94e → LB1e / LB2a-b / LB2c / LB2d。
糖用论文 Fig 1 的 21 个，水用 §19 的 18 个，两者在 v783 里**完全不重叠**。
四组都取**左侧**（糖与水本来就全在左侧）：糖 21 + 水 18 + 苦 21 + Ir94e 21 = 81 个。
**这是推断出来的名单，不是论文的原始名单**，所以定量差异有一部分可能来自名单不同。

做法：一次编译（8 个频率 × 6 个实现 × 81 个 GRN 的泊松源）。
  阶段 1 标定：每个模态单独在 8 个频率上跑，取 MN9 最接近 40 Hz 的那个频率。
  阶段 2 条件：8 个条件各 6 个实现。组合条件靠**覆盖 ingate** 实现——
    ingate 是逐源的门控，所以糖和苦可以各用自己标定的频率、在同一段里同时激活。

用法（brain-fly-cpu，套 memguard）：python screen/taste_interaction.py calib|run|analyze
输出 results/screen/taste/
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import sugar_mn9_screen as S  # noqa: E402
import water_screen as W  # noqa: E402
from xlsx_lite import read_xlsx  # noqa: E402

FREQS = (10, 20, 40, 60, 80, 120, 160, 220)
R_CAL, R_RUN, R_MAX = 3, 6, 6
TARGET_MN9 = 40.0
WDIR = S.OUT / "taste"
BITTER_T = ["LB1a,LB1d", "LB1b", "LB1c"]
IR94E_T = ["LB1e", "LB2a-b", "LB2c", "LB2d"]
CONDS = [("Sugar_only", ["sugar"]), ("Water_only", ["water"]), ("Bitter_only", ["bitter"]),
         ("Ir94e_only", ["ir94e"]), ("Sugar_Bitter", ["sugar", "bitter"]), ("Sugar_Ir94e", ["sugar", "ir94e"]),
         ("Water_Bitter", ["water", "bitter"]), ("Water_Ir94e", ["water", "ir94e"])]


def grn_sets():
    fids, fid2i = S.load_ids()
    ann = pd.read_csv(S.ANNOT, sep="\t", low_memory=False,
                      usecols=["root_id", "cell_type", "side"]).drop_duplicates("root_id")
    ann = ann[ann.root_id.isin(fid2i)]
    left = lambda ts: [int(r) for r, t, sd in zip(ann.root_id, ann.cell_type, ann.side)
                       if t in ts and sd == "left"]
    g = dict(sugar=list(S.sugar_ids()), water=list(W.WATER), bitter=left(BITTER_T), ir94e=left(IR94E_T))
    g = {k: [f for f in v if f in fid2i] for k, v in g.items()}
    order, span = [], {}
    for k in ("sugar", "water", "bitter", "ir94e"):
        span[k] = (len(order), len(order) + len(g[k]))
        order += g[k]
    return g, order, span


def setup():
    g, order, span = grn_sets()
    S.FREQS = FREQS
    S.R_MAX = R_MAX
    S.BUILD = S.OUT / ".brian2_build_taste"
    S.CHUNKS = WDIR / "chunks"
    S.sugar_ids = lambda: list(order)
    WDIR.mkdir(parents=True, exist_ok=True)
    (WDIR / "chunks").mkdir(exist_ok=True)
    return g, order, span


def ingate_for(sc, segs, span, plan):
    """plan: 每段的 [(模态, 频率下标)]。逐源门控，所以一段里可以混多个模态与频率。"""
    G = len(sc.sugar)
    ing = np.zeros((S.K, sc.n_src))
    for k, ((_, r, _), mods) in enumerate(zip(segs, plan)):
        for mod, fi in mods:
            a, b = span[mod]
            base = (fi * R_MAX + r) * G
            ing[k, base + a:base + b] = 1.0
    return ing


def mn9_of(counts, mn9i, n):
    return [int(row[mn9i]) for row in counts[:n]]


def cmd_calib():
    g, order, span = setup()
    fids, fid2i = S.load_ids()
    mn9i = fid2i[S.MN9]
    sc = S.Screen()
    print(f"GRN：" + "，".join(f"{k} {len(v)}" for k, v in g.items()) + f"（合计 {len(order)}）", flush=True)
    out = {}
    for mod in ("sugar", "water", "bitter", "ir94e"):
        rates = []
        for fi, f in enumerate(FREQS):
            segs = [(fi, r, ()) for r in range(R_CAL)]
            plan = [[(mod, fi)] for _ in segs]
            cnt, wall = sc.run_chunk(segs, extra_args={sc.ingate: ingate_for(sc, segs + [(0, 0, ())] * (S.K - len(segs)), span, plan + [[]] * (S.K - len(plan)))})
            m = float(np.mean(mn9_of(cnt, mn9i, R_CAL)))
            rates.append(m)
            print(f"  {mod:7s} {f:4d} Hz → MN9 {m:6.1f} Hz", flush=True)
        best = int(np.argmin([abs(x - TARGET_MN9) for x in rates]))
        out[mod] = dict(freqs=list(FREQS), mn9=[round(x, 2) for x in rates],
                        chosen_fi=best, chosen_hz=FREQS[best], chosen_mn9=round(rates[best], 2))
        print(f"  → {mod}：选 {FREQS[best]} Hz（MN9 {rates[best]:.1f}，目标 {TARGET_MN9}）\n", flush=True)
    (WDIR / "calibration.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("→", WDIR / "calibration.json")


def cmd_run():
    g, order, span = setup()
    fids, fid2i = S.load_ids()
    cal = json.loads((WDIR / "calibration.json").read_text())
    sc = S.Screen()
    for name, mods in CONDS:
        f = WDIR / "chunks" / f"{name}.npz"
        if f.exists():
            print(f"  {name}：已有，跳过", flush=True)
            continue
        segs = [(0, r, ()) for r in range(R_RUN)]
        plan = [[(m, cal[m]["chosen_fi"]) for m in mods] for _ in segs]
        pad = S.K - len(segs)
        t0 = time.time()
        cnt, wall = sc.run_chunk(segs, extra_args={sc.ingate: ingate_for(sc, segs + [(0, 0, ())] * pad, span, plan + [[]] * pad)})
        S.save_chunk(f, [S.key(*s) for s in segs], cnt, wall)
        print(f"  {name}：{R_RUN} 个实现，{time.time() - t0:.0f}s", flush=True)
    print("→", WDIR / "chunks")


def paper_t4():
    t = read_xlsx(str(S.SUPP))["ST 4 Interaction betw Sugar, Wa"]
    hdr = t[1]
    col = {str(c): i for i, c in enumerate(hdr[:10])}
    rows = []
    for r in t[2:]:
        if not str(r[0]).isdigit():
            continue
        d = dict(fid=int(r[0]), name=str(r[1]))
        ok = True
        for name, _ in CONDS:
            try:
                d[name] = float(r[col[name]])
            except Exception:
                ok = False
        if ok:
            rows.append(d)
    return rows


def cmd_analyze():
    g, order, span = setup()
    fids, fid2i = S.load_ids()
    N = len(fids)
    mn9i = fid2i[S.MN9]
    cal = json.loads((WDIR / "calibration.json").read_text())
    cnt = {}
    for name, _ in CONDS:
        f = WDIR / "chunks" / f"{name}.npz"
        if not f.exists():
            print(f"缺 {name}，先跑 run"); return
        _, c, _ = S.load_chunk(f, N)
        cnt[name] = np.array(c[:R_RUN])
    rows = paper_t4()
    print(f"论文表 4：{len(rows)} 行带 ID；模型里 {sum(1 for r in rows if r['fid'] in fid2i)} 个\n")
    print(f"{'条件':14s}{'我们 MN9':>10s}{'论文 MN9':>10s}{'活跃数':>8s}{'与论文 Pearson':>15s}{'都响应':>10s}")
    pm = {r["fid"]: r for r in rows}
    mn9_paper = pm.get(S.MN9)
    out = dict(design=dict(target_mn9=TARGET_MN9, freqs=list(FREQS), R=R_RUN,
                           grn_counts={k: len(v) for k, v in g.items()},
                           note="刺激名单是从表 4 反推的类型（苦 LB1a/b/c、Ir94e LB1e+LB2），不是论文原始名单"),
               calibration=cal, conditions={})
    for name, mods in CONDS:
        c = cnt[name]
        ours_mn9 = float(c[:, mn9i].mean())
        act = int((c.mean(0) > 0).sum())
        pair = [(pm[f][name], float(c[:, fid2i[f]].mean())) for f in pm if f in fid2i]
        p_, o_ = np.array([a for a, _ in pair]), np.array([b for _, b in pair])
        both = int(((p_ > 0) & (o_ > 0)).sum())
        r_ = round(float(np.corrcoef(p_, o_)[0, 1]), 3) if len(pair) > 2 else None
        out["conditions"][name] = dict(ours_mn9=round(ours_mn9, 2),
                                       paper_mn9=round(mn9_paper[name], 2) if mn9_paper else None,
                                       n_active=act, n_compared=len(pair), both_respond=both, pearson=r_)
        print(f"{name:14s}{ours_mn9:10.1f}"
              f"{(mn9_paper[name] if mn9_paper else float('nan')):10.1f}{act:8,d}{r_ if r_ is not None else 0:15.3f}"
              f"{both:6d}/{len(pair)}")
    # 论文的核心问题：组合 ≈ 更强的那个单独？还是有抑制？
    print("\n组合 vs 单独（论文表 4 的核心问题：苦 / Ir94e 会不会压住糖 / 水）")
    print(f"{'组合':14s}{'我们：组合/较强单独':>22s}{'论文：组合/较强单独':>22s}")
    inter = {}
    for comb, a, b in [("Sugar_Bitter", "Sugar_only", "Bitter_only"), ("Sugar_Ir94e", "Sugar_only", "Ir94e_only"),
                       ("Water_Bitter", "Water_only", "Bitter_only"), ("Water_Ir94e", "Water_only", "Ir94e_only")]:
        om = out["conditions"]
        ours = om[comb]["ours_mn9"] / max(om[a]["ours_mn9"], om[b]["ours_mn9"], 1e-9)
        pp = (mn9_paper[comb] / max(mn9_paper[a], mn9_paper[b], 1e-9)) if mn9_paper else None
        inter[comb] = dict(ours_ratio=round(ours, 3), paper_ratio=round(pp, 3) if pp else None)
        print(f"{comb:14s}{ours:22.3f}{(pp if pp else float('nan')):22.3f}")
    out["interaction"] = inter
    (WDIR / "summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("\n→", WDIR / "summary.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["calib", "run", "analyze"])
    {"calib": cmd_calib, "run": cmd_run, "analyze": cmd_analyze}[ap.parse_args().cmd]()
