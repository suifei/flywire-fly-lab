#!/usr/bin/env python
"""复现论文 Fig 2A / 补充表 3：哪些 SEZ 细胞类型**足以**引发伸喙。

这是补充表 10 里最大的一块预测（101/106），也是我们一直没做的一块。

论文口径（补充表 10 第 4 行 + 表 3）：
  「以 50 Hz 激活某类型 → 预测 MN9 发放 > 0 Hz」vs「光遗传激活该类型能否引发 MN9 活动」。
  判据的精确口径是用表 3 自己反查出来的：只看 **50 Hz MN9_Left** 一列、阈值 > 0，
  在论文自己的数字上恰好给出 101/106；换成左右取大是 99、换成 200 Hz 是 96/92。
  所以**判据 = 50 Hz、MN9_Left、> 0 Hz**，事先定死，不在事后挑。

刺激名单是官方的：`external/fly-brain/data/sez_neurons.pickle`（notebook Figure 2 用的就是它），
106 个类型、372 个 ID，其中 308 个在 v783 模型里。

做法：一次编译（2 个频率 × 3 个实现 × 308 个 SEZ 神经元的泊松源），每段只开一个类型的源。
**不应期逐段门控**（RFC_GATE=True）：官方 poi() 只把本次真正被刺激的神经元 rfc 置 0，
而这些 SEZ 神经元是中间神经元，本段没被刺激时必须保持 2.2 ms 不应期，否则全脑动力学被污染。
这一点有自带的校验：论文表 3 给了每个类型的模型发放率，对得上就说明整条管线没走样。

用法（brain-fly-cpu，套 memguard）：python screen/sufficiency.py run|analyze
输出 results/screen/sufficiency/
"""
import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import sugar_mn9_screen as S  # noqa: E402
from xlsx_lite import read_xlsx  # noqa: E402

FREQS = (50, 200)
R = 3
CRIT_FI = 0                      # 判据频率 = 50 Hz
WDIR = S.OUT / "sufficiency"
SEZ_PICKLE = S.REPO / "data" / "sez_neurons.pickle"


def sez_types():
    """官方 pickle：类型名 → ID 列表；只保留模型里有的 ID，按类型名排序固定顺序。"""
    fids, fid2i = S.load_ids()
    raw = pickle.load(open(SEZ_PICKLE, "rb"))
    g, order, span = {}, [], {}
    for name in sorted(raw):
        keep = [int(x) for x in raw[name] if int(x) in fid2i]
        g[name] = keep
        span[name] = list(range(len(order), len(order) + len(keep)))
        order += keep
    return g, order, span


def setup():
    g, order, span = sez_types()
    S.FREQS = FREQS
    S.R_MAX = R
    S.RFC_GATE = True
    S.BUILD = S.OUT / ".brian2_build_suff"
    S.CHUNKS = WDIR / "chunks"
    S.sugar_ids = lambda: list(order)
    WDIR.mkdir(parents=True, exist_ok=True)
    (WDIR / "chunks").mkdir(exist_ok=True)
    return g, order, span


def args_for(sc, segs, span, plan):
    """plan: 每段刺激哪个类型（None = 空段）。逐源门控 + 逐神经元不应期门控。"""
    G = len(sc.sugar)
    ing = np.zeros((S.K, sc.n_src))
    rfc = np.zeros((S.K, G + 1))
    for k, ((fi, r, _), name) in enumerate(zip(segs, plan)):
        if name is None:
            continue
        j = np.array(span[name], dtype=int)
        if len(j) == 0:
            continue
        ing[k, (fi * R + r) * G + j] = 1.0
        rfc[k, 1 + j] = 1.0                        # 只有本段真的被刺激的神经元 rfc = 0
    return {sc.ingate: ing, sc.rfcon: rfc}


def cmd_run():
    g, order, span = setup()
    names = [n for n in g if g[n]]
    print(f"SEZ 类型 {len(g)} 个（模型里有神经元的 {len(names)} 个），刺激神经元 {len(order)} 个", flush=True)
    jobs = [(fi, r, n) for fi in range(len(FREQS)) for n in names for r in range(R)]
    sc = None
    for c0 in range(0, len(jobs), S.K):
        blk = jobs[c0:c0 + S.K]
        f = WDIR / "chunks" / f"c{c0:05d}.npz"
        if f.exists():
            continue
        if sc is None:
            sc = S.Screen()
        segs = [(fi, r, ()) for fi, r, _ in blk]
        plan = [n for _, _, n in blk]
        pad = S.K - len(segs)
        t0 = time.time()
        cnt, _ = sc.run_chunk(segs, extra_args=args_for(sc, segs + [(0, 0, ())] * pad, span, plan + [None] * pad))
        keys = [[fi, r, [names.index(n)]] for fi, r, n in blk]      # 用 sil 位记录"刺激了哪个类型"
        S.save_chunk(f, keys, cnt, time.time() - t0)
        print(f"  {c0:5d}/{len(jobs)}  {time.time() - t0:.0f}s", flush=True)
    print("→", WDIR / "chunks")


def paper_t3():
    t = read_xlsx(str(S.SUPP))["Sup Table 3 Predicted MN9 vs. o"]
    rows = []
    for r in t[1:]:
        if not str(r[0]).strip():
            continue
        num = lambda v: float(v) if isinstance(v, (int, float)) else None
        rows.append(dict(name=str(r[0]), opto=num(r[1]), path=num(r[3]),
                         m50L=num(r[12]), m50R=num(r[13]), m200L=num(r[18]), m200R=num(r[19])))
    return rows


def cmd_analyze():
    g, order, span = setup()
    fids, fid2i = S.load_ids()
    N = len(fids)
    mn9i = fid2i[S.MN9]                                   # notebook 的 "MN9 left"
    names = [n for n in g if g[n]]
    got = {}
    for f in sorted((WDIR / "chunks").glob("c*.npz")):
        keys, cnt, _ = S.load_chunk(f, N)
        for (fi, r, sil), row in zip(keys, cnt):
            got.setdefault((fi, names[sil[0]]), []).append(int(row[mn9i]))
    miss = [(fi, n) for fi in range(len(FREQS)) for n in names if len(got.get((fi, n), [])) < R]
    print(f"段：{sum(len(v) for v in got.values())} 个；缺口 {len(miss)} 个" + (f" 例：{miss[:3]}" if miss else ""))
    ours = {(fi, n): float(np.mean(v)) for (fi, n), v in got.items()}

    rows = paper_t3()
    pn = {r["name"].lower(): r for r in rows}
    pn.setdefault("asteroid", pn.get("asteroid"))
    cmp_rows, n_match, n_cmp = [], 0, 0
    for n in names:
        p = pn.get(n.lower())
        o50, o200 = ours.get((0, n)), ours.get((1, n))
        if p is None or o50 is None:
            continue
        # 事先定死的判据：50 Hz、MN9 左、> 0 Hz
        ours_call, opto_call = o50 > 0, (p["opto"] or 0) > 0
        paper_call = (p["m50L"] or 0) > 0
        n_cmp += 1
        n_match += int(ours_call == opto_call)
        cmp_rows.append(dict(name=n, n_ids=len(g[n]), ours_50=round(o50, 2), paper_50=p["m50L"],
                             ours_200=None if o200 is None else round(o200, 2), paper_200=p["m200L"],
                             opto=p["opto"], ours_call=ours_call, paper_call=paper_call, opto_call=opto_call))
    a50 = np.array([r["ours_50"] for r in cmp_rows]); b50 = np.array([r["paper_50"] or 0.0 for r in cmp_rows])
    a200 = np.array([r["ours_200"] for r in cmp_rows if r["ours_200"] is not None])
    b200 = np.array([r["paper_200"] or 0.0 for r in cmp_rows if r["ours_200"] is not None])
    rk = lambda x: np.argsort(np.argsort(x)).astype(float)
    paper_vs_opto = sum(1 for r in cmp_rows if r["paper_call"] == r["opto_call"])
    ours_vs_paper = sum(1 for r in cmp_rows if r["ours_call"] == r["paper_call"])
    out = dict(design=dict(freqs=list(FREQS), R=R, criterion="50 Hz 激活 → MN9(left) > 0 Hz",
                           n_types=len(names), n_stim_neurons=len(order), rfc_gated=True,
                           note="判据口径从论文表 3 自身反查确定：50 Hz、MN9_Left、>0 恰好给出论文所报的 101/106"),
               n_compared=n_cmp,
               ours_vs_opto=dict(correct=n_match, total=n_cmp, frac=round(n_match / max(n_cmp, 1), 4)),
               paper_vs_opto=dict(correct=paper_vs_opto, total=n_cmp, frac=round(paper_vs_opto / max(n_cmp, 1), 4)),
               ours_vs_paper_calls=dict(same=ours_vs_paper, total=n_cmp, frac=round(ours_vs_paper / max(n_cmp, 1), 4)),
               pearson_50=round(float(np.corrcoef(a50, b50)[0, 1]), 3),
               spearman_50=round(float(np.corrcoef(rk(a50), rk(b50))[0, 1]), 3),
               pearson_200=round(float(np.corrcoef(a200, b200)[0, 1]), 3) if len(a200) > 2 else None,
               spearman_200=round(float(np.corrcoef(rk(a200), rk(b200))[0, 1]), 3) if len(a200) > 2 else None,
               missing_segments=len(miss), types=sorted(cmp_rows, key=lambda r: -r["ours_50"]))
    print(f"\n比较 {n_cmp} 个类型")
    print(f"  我们 vs 光遗传实验：{n_match}/{n_cmp}    论文 vs 光遗传：{paper_vs_opto}/{n_cmp}（论文自报 101/106）")
    print(f"  我们 vs 论文的判定：{ours_vs_paper}/{n_cmp} 一致")
    print(f"  发放率相关：50 Hz Pearson {out['pearson_50']} / Spearman {out['spearman_50']}；"
          f"200 Hz Pearson {out['pearson_200']} / Spearman {out['spearman_200']}")
    print(f"\n{'类型':16s}{'我们50':>9s}{'论文50':>9s}{'我们200':>9s}{'论文200':>9s}{'光遗传':>8s}")
    for r in out["types"][:12]:
        print(f"{r['name']:16s}{r['ours_50']:9.1f}{(r['paper_50'] or 0):9.1f}"
              f"{(r['ours_200'] or 0):9.1f}{(r['paper_200'] or 0):9.1f}{(r['opto'] if r['opto'] is not None else -1):8.2f}")
    dis = [r for r in cmp_rows if r["ours_call"] != r["opto_call"]]
    print(f"\n与实验不一致的 {len(dis)} 个：" + "，".join(
        f"{r['name']}（我们 {r['ours_50']:.2f}，光遗传 {r['opto']}）" for r in dis))
    (WDIR / "summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("\n→", WDIR / "summary.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["run", "analyze"])
    {"run": cmd_run, "analyze": cmd_analyze}[ap.parse_args().cmd]()
