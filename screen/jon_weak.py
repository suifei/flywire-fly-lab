#!/usr/bin/env python
"""
验证一个推测：JON 通路上“我们只判 1 个必需、论文判 6 个”，是不是因为我们的刺激更强？

24 节的情况：论文 notebook 的 neu_JON_all 列表提取不到，我们改用注释表里全部 1,091 个 JO- 神经元，
结果 aDN1 基线 32.3 Hz、论文 23.3 Hz。5 处判定不一致全部是同方向的边缘情况（论文 0.68–0.74、我们 0.83–0.90），
推测是“读出被推离阈值 → 单个神经元的影响被压缩”。这里直接检验。

事先写定（运行前写好）：
  第一步（只看基线，不看任何敲除结果）：在 80 / 100 / 120 / 140 Hz 四个频率上各跑 12 个实现的基线，
  选 aDN1 平均放电率最接近论文 23.3 Hz 的那个频率，记作 f*。
  第二步：在 f* 下跑两组条件 × 前 6 个实现——
    论文补充表 7D 里归一化值最小的 30 个神经元（一定覆盖论文判为“必需”的那 6 个）；
    50 个随机活跃神经元作零参照（抽样种子 20260920），口径与前三条通路一致。
  判定：比值 ≤ 0.8 记为“必需”。
  **事先声明的预测：在 f* 下，论文判必需的那 6 个里，我们应当判出明显多于 1 个**；
  如果仍然只有 aBN1，则推测不成立，24 节的差异另有原因。
输出 results/screen/jon_weak/summary.json
用法（brain-fly-cpu 环境，套 scratch/memguard.sh）：python screen/jon_weak.py baseline|screen|analyze
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

FREQS = (80, 100, 120, 140)
R_ALL, R_A = 12, 6
N_TOP_PAPER, N_NULL, SEED_NULL = 30, 50, 20260920
CALL = 0.8
WDIR = S.OUT / "jon_weak"


def setup():
    fids, fid2i = S.load_ids()
    ids = J.jon_ids(fid2i)
    S.FREQS = FREQS
    S.R_MAX = R_ALL
    S.MN9 = J.ADN1
    S.BUILD = S.OUT / ".brian2_build_jon_weak"
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


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["baseline", "screen", "analyze"])
    dict(baseline=cmd_baseline, screen=cmd_screen, analyze=cmd_analyze)[ap.parse_args().cmd]()
