#!/usr/bin/env python
"""
把双敲除的输入实现从 6 个加到 12 个，重算判定。

起因：第 16 节的协同 / 亚可加判定里，去掉任一个输入实现后只有 4/7 和 13/20 保持不变——判定还不够稳。
在扩大神经元范围之前，先把现有 66 对的判定稳住。

事先写定（运行前写好）：
  模型、刺激、沉默方式、段落安排与 screen/sugar_mn9_screen.py 完全相同，50 Hz。输入实现 r = 0…11，
  第 r 个的随机数种子仍是 20260914 + r，所以 r = 0…5 与之前逐位相同（跑一遍基线核对）。
  新实现 r = 6…11 需要补跑：
    1. 基线 12 段（r = 0…11，其中前 6 段用于核对逐位一致）；
    2. 零参照：与主筛选同口径——在新实现下随机抽 50 个“50 Hz 基线里放过电”的神经元做单敲除（种子 20260917），
       取每个实现的 MN9 中位数作为“单敲除零参照”；C 组 20 对照对作为“双敲除零参照”；
    3. A 组 12 个神经元的单敲除，以及 66 对的双敲除。
  判据不变：效应 E = 1 − 比值（各自对应零参照）；独立预期 E_exp = 1 − (1 − E_a)(1 − E_b)；
  协同 = E_ab > E_exp + 0.1，亚可加 = E_ab < E_exp − 0.1。留一检验改为“去掉任一个实现（12 选 11）判定是否不变”。
输出 results/screen/double12_summary.json
用法（brain-fly-cpu 环境，套 scratch/memguard.sh）：
  python screen/double_extend.py run
  python screen/double_extend.py analyze
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sugar_mn9_screen as S  # noqa: E402
import double_knockout as D  # noqa: E402

R_OLD, R_NEW = 6, 12
N_NULL_SINGLE, SEED_NULL = 50, 20260917
EXT = S.OUT / "double12"
FI = 0


def setup():
    """把输入源数量扩到 12 个实现（模式由种子决定，前 6 个不变）。"""
    S.R_MAX = R_NEW
    EXT.mkdir(parents=True, exist_ok=True)


def old_baseline():
    fids, fid2i = S.load_ids()
    _, bc, _ = S.load_chunk(S.CHUNKS / "baseline.npz", len(fids))
    return {r: bc[0 * 8 + r] for r in range(8)}          # 旧 baseline 按 R_MAX = 8 的布局存储


def cmd_run():
    setup()
    fids, fid2i = S.load_ids()
    N = len(fids)
    mn9 = fid2i[S.MN9]
    plan = json.loads((S.OUT / "double_plan.json").read_text())
    top = [fid2i[f] for f in plan["top"]]
    a_pairs = [tuple(sorted(fid2i[x] for x in p)) for p in plan["a_pairs"]]
    c_pairs = [tuple(sorted(fid2i[x] for x in p)) for p in plan["c_pairs"]]
    rng = np.random.default_rng(SEED_NULL)
    exhaustive = [int(x["fid"]) for x in json.loads((S.OUT / "exhaustive_50Hz.json").read_text())]
    null_single = sorted(fid2i[f] for f in rng.choice(exhaustive, N_NULL_SINGLE, replace=False))
    print(f"A 组 {len(top)} 个神经元、{len(a_pairs)} 对；C 组 {len(c_pairs)} 对；零参照单敲除 {len(null_single)} 个", flush=True)

    sc = S.Screen()
    # 1) 基线 12 段（前 6 段与旧结果逐位核对）
    bpath = EXT / "baseline12.npz"
    if not bpath.exists():
        segs = [(FI, r, ()) for r in range(R_NEW)]
        counts, wall = sc.run_chunk(segs)
        S.save_chunk(bpath, [S.key(*s) for s in segs], counts, wall)
    _, bc, _ = S.load_chunk(bpath, N)
    base = {r: bc[r] for r in range(R_NEW)}
    ob = old_baseline()
    same = [bool(np.array_equal(base[r], ob[r])) for r in range(R_OLD)]
    print(f"与旧实现逐位一致（r = 0…5）：{same}；各实现 MN9 {[int(base[r][mn9]) for r in range(R_NEW)]}", flush=True)
    if not all(same):
        raise SystemExit("扩展后前 6 个实现不再一致，停止")

    # 2) 需要补跑的段：只跑新实现 r = 6…11
    segs = []
    def add(r, sil):
        if any(base[r][n] > 0 for n in sil):
            segs.append((FI, r, tuple(sorted(sil))))
    for r in range(R_OLD, R_NEW):
        for n in null_single:
            add(r, [n])
        for n in top:
            add(r, [n])
        for p in c_pairs:
            add(r, p)
        for p in a_pairs:
            add(r, p)
    segs = list(dict.fromkeys(segs))
    print(f"补跑 {len(segs)} 段，估计 {len(segs) * 2.0 / 60:.0f} min", flush=True)
    (S.OUT / "double12_plan.json").write_text(json.dumps(dict(
        R=R_NEW, n_segments=len(segs), null_single=[int(fids[n]) for n in null_single],
        top=[int(fids[n]) for n in top]), indent=1))
    n_chunks = math.ceil(len(segs) / S.K)
    t0 = time.time(); done = 0
    for c in range(n_chunks):
        path = EXT / f"chunk_{c:04d}.npz"
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
    setup()
    fids, fid2i = S.load_ids()
    N = len(fids)
    mn9 = fid2i[S.MN9]
    plan = json.loads((S.OUT / "double_plan.json").read_text())
    p12 = json.loads((S.OUT / "double12_plan.json").read_text())
    top = [fid2i[f] for f in plan["top"]]
    a_pairs = [tuple(sorted(fid2i[x] for x in p)) for p in plan["a_pairs"]]
    c_pairs = [tuple(sorted(fid2i[x] for x in p)) for p in plan["c_pairs"]]
    null_single = [fid2i[f] for f in p12["null_single"]]
    _, bc, _ = S.load_chunk(EXT / "baseline12.npz", N)
    base = {r: bc[r] for r in range(R_NEW)}
    res = {}
    for p in sorted(S.CHUNKS.glob("chunk_*.npz")) + sorted((S.OUT / "double").glob("chunk_*.npz")) + sorted(EXT.glob("chunk_*.npz")):
        keys, rows = S.chunk_summary(p, {"mn9": mn9})
        res.update({k: v["mn9"] for k, v in zip(keys, rows)})

    def counts(sil):
        out = []
        for r in range(R_NEW):
            k = (FI, r, tuple(sorted(sil)))
            out.append(res[k] if any(base[r][n] > 0 for n in sil) else int(base[r][mn9]))
        return out
    med_single = [float(np.median([counts([n])[r] for n in null_single])) for r in range(R_NEW)]
    med_double = [float(np.median([counts(p)[r] for p in c_pairs])) for r in range(R_NEW)]
    print("单敲除零参照", med_single, "\n双敲除零参照", med_double, flush=True)

    def verdict(e_ab, e_exp):
        return "协同" if e_ab > e_exp + D.SYN_MARGIN else ("亚可加" if e_ab < e_exp - D.SYN_MARGIN else "可加")

    single = {n: counts([n]) for n in top}
    out = dict(design=dict(R=R_NEW, n_null_single=len(null_single), n_null_pairs=len(c_pairs), margin=D.SYN_MARGIN, freq_hz=50),
               null_median_single=med_single, null_median_double=med_double,
               double_null_over_single_null=round(sum(med_double) / sum(med_single), 4), pairs=[])
    stable = {"协同": [0, 0], "可加": [0, 0], "亚可加": [0, 0]}
    for a, b in a_pairs:
        ma, mb, mab = single[a], single[b], counts((a, b))
        ra, rb = sum(ma) / sum(med_single), sum(mb) / sum(med_single)
        rab = sum(mab) / sum(med_double)
        e_exp, e_ab = 1 - ra * rb, 1 - rab
        v = verdict(e_ab, e_exp)
        loo = []
        for j in range(R_NEW):
            ra_j = (sum(ma) - ma[j]) / (sum(med_single) - med_single[j])
            rb_j = (sum(mb) - mb[j]) / (sum(med_single) - med_single[j])
            rab_j = (sum(mab) - mab[j]) / (sum(med_double) - med_double[j])
            loo.append(verdict(1 - rab_j, 1 - ra_j * rb_j))
        ok = all(x == v for x in loo)
        stable[v][0] += ok; stable[v][1] += 1
        out["pairs"].append(dict(a=str(fids[a]), b=str(fids[b]), ratio_a=round(ra, 4), ratio_b=round(rb, 4), ratio_ab=round(rab, 4),
                                 effect_expected=round(e_exp, 4), effect_observed=round(e_ab, 4), delta=round(e_ab - e_exp, 4),
                                 verdict=v, loo_stable=ok, mn9=mab))
    out["summary"] = dict(counts={k: v[1] for k, v in stable.items()}, loo_stable={k: v[0] for k, v in stable.items()},
                          synergy=sorted([p for p in out["pairs"] if p["verdict"] == "协同"], key=lambda p: -p["delta"]),
                          reversal=sorted([p for p in out["pairs"] if p["verdict"] == "亚可加" and p["ratio_ab"] > min(p["ratio_a"], p["ratio_b"]) + 0.05],
                                          key=lambda p: p["delta"]))
    (S.OUT / "double12_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("\n判定（12 个实现）：", out["summary"]["counts"], "；留一稳定：", out["summary"]["loo_stable"], flush=True)
    ann_name = {int(x["fid"]): x["cell_type"] for x in json.loads((S.OUT / "exhaustive_50Hz.json").read_text())}
    for p in out["summary"]["synergy"]:
        print(f"  协同 {ann_name.get(int(p['a']))}+{ann_name.get(int(p['b']))}: 各自 {p['ratio_a']:.2f}/{p['ratio_b']:.2f} → 一起 {p['ratio_ab']:.2f}，Δ {p['delta']:+.2f}，留一{'稳' if p['loo_stable'] else '不稳'}")
    for p in out["summary"]["reversal"][:5]:
        print(f"  回升 {ann_name.get(int(p['a']))}+{ann_name.get(int(p['b']))}: 各自 {p['ratio_a']:.2f}/{p['ratio_b']:.2f} → 一起 {p['ratio_ab']:.2f}，Δ {p['delta']:+.2f}，留一{'稳' if p['loo_stable'] else '不稳'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "analyze"])
    (cmd_run if ap.parse_args().cmd == "run" else cmd_analyze)()
