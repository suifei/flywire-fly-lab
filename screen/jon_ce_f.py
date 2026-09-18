#!/usr/bin/env python
"""复现论文 Fig 5G / 补充表 8：aBN1 只对 JO-CE 响应，对 JO-F 几乎不响应（表 10 第 10 行，论文自报 2/2）。

刺激名单是官方的：figures.ipynb Figure 5b 里的 neu_JON_CE(70) / neu_JON_F(60)
（已抄到 results/screen/jon_ce_f_lists.json；三者并集与 §24.3 反推出的 146 个完全相同）。
频率 150 Hz，和表 8 的列名一致。

**判据事先写死**（照论文表 8 里 aBN1 那一行：CE 50.77 Hz、F 1.23 Hz）：
  A. aBN1 在 JO-CE 下 > 10 Hz；
  B. aBN1 在 JO-F  下 < 5 Hz。
另外对表 8 的 465 行做整向量比较（两列各一个 Pearson），并**剔除被刺激的 JON 本身**再算一次——
被刺激神经元两边都精确等于刺激频率，留着会把相关撑高。

用法（brain-fly-cpu，套 memguard）：python screen/jon_ce_f.py run|analyze（一次编译，2 条件 × 3 实现）
输出 results/screen/jon_ce_f/
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import sugar_mn9_screen as S  # noqa: E402
import jon_screen as J  # noqa: E402
from xlsx_lite import read_xlsx  # noqa: E402

FREQS = (150,)
R = 3
WDIR = S.OUT / "jon_ce_f"
LISTS = S.OUT / "jon_ce_f_lists.json"
TRIAL_S = S.TRIAL_STEPS * S.DT_MS * 1e-3
CE_MIN, F_MAX = 10.0, 5.0


def setup():
    fids, fid2i = S.load_ids()
    raw = json.loads(LISTS.read_text())
    g, order, span = {}, [], {}
    for k, nk in (("CE", "neu_JON_CE"), ("F", "neu_JON_F")):
        ids = [int(x) for x in raw[nk] if int(x) in fid2i]
        span[k] = list(range(len(order), len(order) + len(ids)))
        g[k] = ids
        order += ids
    S.FREQS = FREQS
    S.R_MAX = R
    S.MN9 = J.ABN1                                  # 读出换成 aBN1
    S.BUILD = S.OUT / ".brian2_build_jon_ce_f"
    S.CHUNKS = WDIR / "chunks"
    S.sugar_ids = lambda: list(order)
    WDIR.mkdir(parents=True, exist_ok=True)
    (WDIR / "chunks").mkdir(exist_ok=True)
    return g, order, span


def cmd_run():
    g, order, span = setup()
    print(f"JO-CE {len(g['CE'])} 个、JO-F {len(g['F'])} 个（模型内），{FREQS[0]} Hz × {R} 个实现", flush=True)
    f = WDIR / "chunks" / "ce_f.npz"
    if f.exists():
        print("已有，跳过"); return
    sc = S.Screen()
    jobs = [(k, r) for k in ("CE", "F") for r in range(R)]
    segs = [(0, r, ()) for _, r in jobs]
    G = len(sc.sugar)
    pad = S.K - len(segs)
    ing = np.zeros((S.K, sc.n_src))
    for i, (k, r) in enumerate(jobs):
        ing[i, r * G + np.array(span[k])] = 1.0
    t0 = time.time()
    cnt, _ = sc.run_chunk(segs + [(0, 0, ())] * pad, extra_args={sc.ingate: ing})
    S.save_chunk(f, [[0, r, [("CE", "F").index(k)]] for k, r in jobs], cnt, time.time() - t0)
    print(f"  {len(jobs)} 段，{time.time() - t0:.0f}s → {f}")


def paper_t8():
    t = read_xlsx(str(S.SUPP))["Supp Table 8 JO-CE and JO-F fir"]
    out = {}
    for r in t[1:]:
        sid = str(r[1]).strip()
        if sid.isdigit() and isinstance(r[2], (int, float)) and isinstance(r[3], (int, float)):
            out[int(sid)] = (float(r[2]), float(r[3]))
    return out


def cmd_analyze():
    g, order, span = setup()
    fids, fid2i = S.load_ids()
    keys, cnt, _ = S.load_chunk(WDIR / "chunks" / "ce_f.npz", len(fids))
    rows = {"CE": [], "F": []}
    for (_, r, code), row in zip(keys, cnt):
        rows[("CE", "F")[code[0]]].append(row)
    ours = {k: np.mean(np.array(v), 0) / TRIAL_S for k, v in rows.items()}
    ab = fid2i[J.ABN1]
    ce, fr = float(ours["CE"][ab]), float(ours["F"][ab])
    p8 = paper_t8()
    p_ab = p8.get(J.ABN1)
    stim = set(order)
    both = [f for f in p8 if f in fid2i]
    nons = [f for f in both if f not in stim]
    def corr(ids, col, key):
        a = np.array([p8[f][col] for f in ids]); b = np.array([ours[key][fid2i[f]] for f in ids])
        rk = lambda x: np.argsort(np.argsort(x)).astype(float)
        return (round(float(np.corrcoef(a, b)[0, 1]), 3), round(float(np.corrcoef(rk(a), rk(b))[0, 1]), 3),
                round(float(((a > 0) & (b > 0)).sum() / max(((a > 0) | (b > 0)).sum(), 1)), 3))
    A, B = ce > CE_MIN, fr < F_MAX
    out = dict(design=dict(freq_hz=FREQS[0], R=R, n_ce=len(g["CE"]), n_f=len(g["F"]),
                           criterion=f"aBN1：JO-CE > {CE_MIN} Hz 且 JO-F < {F_MAX} Hz（论文表 8：50.77 / 1.23）",
                           stim_list="官方 notebook Figure 5b"),
               abn1=dict(ours_ce=round(ce, 2), ours_f=round(fr, 2),
                         paper_ce=None if not p_ab else round(p_ab[0], 2),
                         paper_f=None if not p_ab else round(p_ab[1], 2)),
               criterion_A_ce_responds=bool(A), criterion_B_f_does_not=bool(B), both_pass=bool(A and B),
               vector=dict(n_all=len(both), n_nonstim=len(nons)))
    for col, key in ((0, "CE"), (1, "F")):
        pe, sp, ja = corr(both, col, key)
        pe2, sp2, ja2 = corr(nons, col, key)
        out["vector"][key] = dict(pearson=pe, spearman=sp, respond_jaccard=ja,
                                  pearson_nonstim=pe2, spearman_nonstim=sp2, respond_jaccard_nonstim=ja2)
    print(f"aBN1：我们 JO-CE {ce:.2f} Hz / JO-F {fr:.2f} Hz；论文 {p_ab[0]:.2f} / {p_ab[1]:.2f}")
    print(f"  A（CE > {CE_MIN}）{'成立' if A else '不成立'}；B（F < {F_MAX}）{'成立' if B else '不成立'}")
    for key in ("CE", "F"):
        v = out["vector"][key]
        print(f"  表 8 全向量 JO-{key}：{len(both)} 个 Pearson {v['pearson']}；"
              f"剔除被刺激的 {len(nons)} 个 Pearson {v['pearson_nonstim']}、Spearman {v['spearman_nonstim']}、"
              f"响应集 Jaccard {v['respond_jaccard_nonstim']}")
    (WDIR / "summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("→", WDIR / "summary.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["run", "analyze"])
    {"run": cmd_run, "analyze": cmd_analyze}[ap.parse_args().cmd]()
