#!/usr/bin/env python
"""
还有没有别的 CB0883？——拿两个“枢纽”去配排名 13–24 的神经元。

由来（明确是探索性的、上一轮结果提出来的假设）：12 个输入实现下，7 对留一稳定的协同里有 5 对含 CB0883、3 对含 CB0616。
CB0883 单独敲只到 0.75（算不上“必需”），配对却能把 MN9 压到 0.17–0.36。问题是：这种“单独看不出来、配对才显形”的神经元
是不是还有？这里不再做全部两两组合（代价太大），而是拿 CB0883 与 CB0616 当固定伙伴，去配效应排名 13–24 的 12 个非感觉神经元。

事先写定（运行前写好）：
  模型、刺激、沉默方式、段落安排与 screen/sugar_mn9_screen.py 相同，50 Hz，12 个输入实现（r = 0…11）。
  候选：results/screen/summary.json 里修正后比值排名第 13–24 的非感觉神经元（A 组那 12 个之后的 12 个）。
  伙伴：CB0883（720575940625102692）与 CB0616（720575940620874757）。
  零参照沿用 double_extend 的两条（单敲除 50 个的中位数、C 组 20 对的中位数）。
  判据不变：E = 1 − 比值；独立预期 E_exp = 1 − (1 − E_a)(1 − E_b)；协同 = E_ab > E_exp + 0.1；留一 = 12 选 11 判定不变。
  预计段数 ≈ 12 候选 × 2 伙伴 × 12 实现 + 候选单敲除补跑 ≈ 360 段（约 12 min）。
输出 results/screen/double_hub_summary.json
用法（brain-fly-cpu 环境，套 scratch/memguard.sh）：python screen/double_hub.py run|analyze
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
import double_extend as E  # noqa: E402

HUBS = [720575940625102692, 720575940620874757]      # CB0883, CB0616
N_CAND, RANK_FROM = 12, 12                            # 排名 13–24（0 基下标 12–23）
OUT_DIR = S.OUT / "double_hub"
FI = 0


def candidates(fid2i):
    rows = json.loads((S.OUT / "exhaustive_50Hz.json").read_text())
    summ = json.loads((S.OUT / "summary.json").read_text())
    corr = 1.0 / summ["exploratory_null_normalized"]["null_over_baseline"]["50"]
    nonsens = [r for r in rows if r.get("super_class") != "sensory" and int(r["fid"]) in fid2i]
    nonsens.sort(key=lambda r: r["ratio"])
    return [(int(r["fid"]), r["cell_type"], round(r["ratio"] * corr, 3)) for r in nonsens[RANK_FROM:RANK_FROM + N_CAND]]


def cmd_run():
    E.setup()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fids, fid2i = S.load_ids()
    N = len(fids)
    cands = candidates(fid2i)
    print("候选（排名 13–24）：", [f"{c[1]}({c[2]})" for c in cands], flush=True)
    _, bc, _ = S.load_chunk(E.EXT / "baseline12.npz", N)
    base = {r: bc[r] for r in range(E.R_NEW)}
    have = set()
    for p in list(S.CHUNKS.glob("chunk_*.npz")) + list((S.OUT / "double").glob("chunk_*.npz")) + list(E.EXT.glob("chunk_*.npz")):
        have.update(S.chunk_keys(p))
    segs = []
    def add(r, sil):
        k = (FI, r, tuple(sorted(sil)))
        if any(base[r][n] > 0 for n in sil) and k not in have and k not in segs:
            segs.append(k)
    for fid, _ct, _ratio in cands:
        n = fid2i[fid]
        for r in range(E.R_NEW):
            add(r, [n])
            for h in HUBS:
                add(r, [n, fid2i[h]])
    print(f"需要模拟 {len(segs)} 段，估计 {len(segs) * 2.0 / 60:.0f} min", flush=True)
    (S.OUT / "double_hub_plan.json").write_text(json.dumps(dict(hubs=[str(h) for h in HUBS],
        candidates=[dict(fid=str(c[0]), cell_type=c[1], ratio_single_6reps=c[2]) for c in cands], n_segments=len(segs)), ensure_ascii=False, indent=1))
    sc = S.Screen()
    n_chunks = math.ceil(len(segs) / S.K)
    t0 = time.time(); done = 0
    for c in range(n_chunks):
        path = OUT_DIR / f"chunk_{c:04d}.npz"
        part = segs[c * S.K:(c + 1) * S.K]
        if path.exists() and S.chunk_keys(path) == part:
            continue
        counts, wall = sc.run_chunk(part)
        S.save_chunk(path, [S.key(*s) for s in part], counts, wall)
        done += 1
        el = time.time() - t0
        print(f"块 {c + 1}/{n_chunks}：{wall:.0f} s；已跑 {el / 60:.1f} min，预计还需 {el / done * (n_chunks - c - 1) / 60:.0f} min", flush=True)
    print("全部完成", flush=True)


def cmd_analyze():
    E.setup()
    fids, fid2i = S.load_ids()
    N = len(fids)
    mn9 = fid2i[S.MN9]
    d12 = json.loads((S.OUT / "double12_summary.json").read_text())
    med_s, med_d = d12["null_median_single"], d12["null_median_double"]
    cands = candidates(fid2i)
    _, bc, _ = S.load_chunk(E.EXT / "baseline12.npz", N)
    base = {r: bc[r] for r in range(E.R_NEW)}
    res = {}
    for p in (sorted(S.CHUNKS.glob("chunk_*.npz")) + sorted((S.OUT / "double").glob("chunk_*.npz"))
              + sorted(E.EXT.glob("chunk_*.npz")) + sorted(OUT_DIR.glob("chunk_*.npz"))):
        keys, rows = S.chunk_summary(p, {"mn9": mn9})
        res.update({k: v["mn9"] for k, v in zip(keys, rows)})

    def counts(sil):
        return [res[(FI, r, tuple(sorted(sil)))] if any(base[r][n] > 0 for n in sil) else int(base[r][mn9]) for r in range(E.R_NEW)]

    def verdict(e_ab, e_exp):
        return "协同" if e_ab > e_exp + 0.1 else ("亚可加" if e_ab < e_exp - 0.1 else "可加")
    hub_single = {h: counts([fid2i[h]]) for h in HUBS}
    ct = {int(x["fid"]): x["cell_type"] for x in json.loads((S.OUT / "exhaustive_50Hz.json").read_text())}
    out = dict(design=dict(R=E.R_NEW, hubs=[str(h) for h in HUBS], rank_range=[RANK_FROM + 1, RANK_FROM + N_CAND], margin=0.1), pairs=[])
    for fid, cell, _r6 in cands:
        n = fid2i[fid]
        mc = counts([n])
        rc = sum(mc) / sum(med_s)
        for h in HUBS:
            mh, mab = hub_single[h], counts([n, fid2i[h]])
            rh = sum(mh) / sum(med_s)
            rab = sum(mab) / sum(med_d)
            e_exp, e_ab = 1 - rc * rh, 1 - rab
            v = verdict(e_ab, e_exp)
            loo = [verdict(1 - (sum(mab) - mab[j]) / (sum(med_d) - med_d[j]),
                           1 - ((sum(mc) - mc[j]) / (sum(med_s) - med_s[j])) * ((sum(mh) - mh[j]) / (sum(med_s) - med_s[j]))) for j in range(E.R_NEW)]
            out["pairs"].append(dict(candidate=str(fid), candidate_type=cell, hub=ct.get(h, str(h)), ratio_candidate=round(rc, 4),
                                     ratio_hub=round(rh, 4), ratio_pair=round(rab, 4), effect_expected=round(e_exp, 4),
                                     effect_observed=round(e_ab, 4), delta=round(e_ab - e_exp, 4), verdict=v,
                                     loo_stable=bool(all(x == v for x in loo))))
    syn = [p for p in out["pairs"] if p["verdict"] == "协同"]
    out["summary"] = dict(n_pairs=len(out["pairs"]), n_synergy=len(syn), n_synergy_stable=sum(p["loo_stable"] for p in syn),
                          n_subadditive=sum(p["verdict"] == "亚可加" for p in out["pairs"]),
                          hub_like=sorted([p for p in syn if p["ratio_candidate"] > 0.8], key=lambda p: -p["delta"]))
    (S.OUT / "double_hub_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps(out["summary"], ensure_ascii=False, indent=1)[:2500])
    print("\n全部组合：")
    for p in sorted(out["pairs"], key=lambda p: -p["delta"]):
        print(f"  {p['candidate_type']:10s}（单独 {p['ratio_candidate']:.2f}）+ {p['hub']:8s}（单独 {p['ratio_hub']:.2f}）→ 一起 {p['ratio_pair']:.2f}"
              f"  预期效应 {p['effect_expected']:.2f} 实测 {p['effect_observed']:.2f}  {p['verdict']}{'（留一稳）' if p['loo_stable'] else ''}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "analyze"])
    (cmd_run if ap.parse_args().cmd == "run" else cmd_analyze)()
