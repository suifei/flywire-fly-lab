#!/usr/bin/env python
"""
CB0883 全扫描：50 Hz 下全部 313 个活跃神经元，每个都和 CB0883 一起敲，看谁和它冗余。

由来：第 16 节里 7 对留一稳定的协同有 5 对含 CB0883；16.1 节又在排名 13–24 里找到 3 个。
现在把范围扩到**全部**在 50 Hz 基线里放过电的神经元，做一张完整的“谁和 CB0883 互为备份”的图。

事先写定（运行前写好）：
  模型、刺激（50 Hz 糖）、沉默方式、段落安排与 screen/sugar_mn9_screen.py 相同；输入实现 r = 0…11（种子 20260914 + r）。
  为了省时间用两阶段，两阶段的判据都在跑之前定好：
    阶段 A：全部 313 个候选（去掉 CB0883 自己和 MN9）× 前 6 个实现；
    阶段 B：阶段 A 里 Δ = 实测效应 − 独立预期效应 ≥ 0.05 的候选，补跑第 7–12 个实现，用 12 个实现重算。
    （0.05 这个门槛比判定用的 0.1 松一档，目的是不漏掉边缘的；阶段 A 只用来筛，不用来下结论。）
  零参照：单敲除用 double_extend 里 50 个随机单敲除的每实现中位数，双敲除用 C 组 20 对的每实现中位数（前 6 个实现已有，
  阶段 B 用 12 个实现的版本）。判据：E = 1 − 比值；独立预期 E_exp = 1 − (1 − E_a)(1 − E_b)；
  协同 = E_ab > E_exp + 0.1；留一 = 去掉任一实现判定不变。
输出 results/screen/hub_scan_summary.json
用法（brain-fly-cpu 环境，套 scratch/memguard.sh）：python screen/hub_scan.py run|analyze
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

HUB = 720575940625102692          # CB0883
STAGE_A_R, STAGE_B_R = 6, 12
PICK_DELTA = 0.05
MARGIN = 0.1
DIR = S.OUT / "hub_scan"
FI = 0


def context():
    E.setup()
    fids, fid2i = S.load_ids()
    N = len(fids)
    mn9 = fid2i[S.MN9]
    _, bc, _ = S.load_chunk(E.EXT / "baseline12.npz", N)
    base = {r: bc[r] for r in range(E.R_NEW)}
    res = {}
    for p in (sorted(S.CHUNKS.glob("chunk_*.npz")) + sorted((S.OUT / "double").glob("chunk_*.npz"))
              + sorted(E.EXT.glob("chunk_*.npz")) + sorted((S.OUT / "double_hub").glob("chunk_*.npz")) + sorted(DIR.glob("*.npz"))):   # 保存名是 stageA_/stageB_，不是 chunk_
        keys, rows = S.chunk_summary(p, {"mn9": mn9})
        res.update({k: v["mn9"] for k, v in zip(keys, rows)})
    d12 = json.loads((S.OUT / "double12_summary.json").read_text())
    return fids, fid2i, mn9, base, res, d12


def counts(res, base, mn9, sil, R):
    out = []
    for r in range(R):
        k = (FI, r, tuple(sorted(sil)))
        out.append(res.get(k) if any(base[r][n] > 0 for n in sil) else int(base[r][mn9]))
    return out


def verdict(e_ab, e_exp):
    return "协同" if e_ab > e_exp + MARGIN else ("亚可加" if e_ab < e_exp - MARGIN else "可加")


def cmd_run():
    DIR.mkdir(parents=True, exist_ok=True)
    fids, fid2i, mn9, base, res, d12 = context()
    hub = fid2i[HUB]
    cand = [fid2i[int(x["fid"])] for x in json.loads((S.OUT / "exhaustive_50Hz.json").read_text()) if int(x["fid"]) in fid2i]
    cand = [n for n in cand if n not in (hub, mn9)]
    print(f"候选 {len(cand)} 个（全部 50 Hz 活跃神经元，去掉 CB0883 与 MN9）", flush=True)
    have = set(res)
    sc = None

    def run_segs(segs, tag):
        nonlocal sc
        segs = [s for s in segs if s not in have]
        if not segs:
            print(f"{tag}：没有需要补跑的段", flush=True)
            return
        print(f"{tag}：{len(segs)} 段，估计 {len(segs) * 2.0 / 60:.0f} min", flush=True)
        if sc is None:
            sc = S.Screen()
        n_chunks = math.ceil(len(segs) / S.K)
        t0 = time.time(); done = 0
        for c in range(n_chunks):
            path = DIR / f"{tag}_{c:04d}.npz"
            part = segs[c * S.K:(c + 1) * S.K]
            if path.exists() and S.chunk_keys(path) == part:
                continue
            cnts, wall = sc.run_chunk(part)
            S.save_chunk(path, [S.key(*s) for s in part], cnts, wall)
            done += 1
            el = time.time() - t0
            print(f"  {tag} 块 {c + 1}/{n_chunks}：{wall:.0f} s；已跑 {el / 60:.1f} min，预计还需 {el / done * (n_chunks - c - 1) / 60:.0f} min", flush=True)

    segs_a = []
    for n in cand:
        for r in range(STAGE_A_R):
            for sil in ([n], [n, hub]):
                if any(base[r][x] > 0 for x in sil):
                    segs_a.append((FI, r, tuple(sorted(sil))))
    run_segs(list(dict.fromkeys(segs_a)), "stageA")

    # 阶段 A 结果 → 挑候选
    fids, fid2i, mn9, base, res, d12 = context()
    med_s6, med_d6 = d12["null_median_single"][:STAGE_A_R], d12["null_median_double"][:STAGE_A_R]
    mh = counts(res, base, mn9, [hub], STAGE_A_R)
    rh = sum(mh) / sum(med_s6)
    picks, rowsA = [], []
    for n in cand:
        mc = counts(res, base, mn9, [n], STAGE_A_R)
        mab = counts(res, base, mn9, [n, hub], STAGE_A_R)
        if None in mc or None in mab:
            continue
        rc, rab = sum(mc) / sum(med_s6), sum(mab) / sum(med_d6)
        d = (1 - rab) - (1 - rc * rh)
        rowsA.append(dict(idx=n, fid=int(fids[n]), ratio_c=round(rc, 4), ratio_pair=round(rab, 4), delta=round(d, 4)))
        if d >= PICK_DELTA:
            picks.append(n)
    print(f"阶段 A 完成：{len(rowsA)} 个候选算出结果，其中 Δ ≥ {PICK_DELTA} 的 {len(picks)} 个进入阶段 B", flush=True)
    (S.OUT / "hub_scan_stageA.json").write_text(json.dumps(dict(hub=str(HUB), n_candidates=len(rowsA), picks=[int(fids[n]) for n in picks],
                                                                rows=sorted(rowsA, key=lambda x: -x["delta"])), ensure_ascii=False, indent=1))
    segs_b = []
    for n in picks + [hub]:
        for r in range(STAGE_A_R, STAGE_B_R):
            for sil in ([n], [n, hub]):
                if n == hub and len(sil) > 1:
                    continue
                if any(base[r][x] > 0 for x in sil):
                    segs_b.append((FI, r, tuple(sorted(sil))))
    run_segs(list(dict.fromkeys(segs_b)), "stageB")
    print("全部完成", flush=True)


def cmd_analyze():
    fids, fid2i, mn9, base, res, d12 = context()
    hub = fid2i[HUB]
    picks = [fid2i[f] for f in json.loads((S.OUT / "hub_scan_stageA.json").read_text())["picks"]]
    med_s, med_d = d12["null_median_single"], d12["null_median_double"]
    ct = {int(x["fid"]): (x.get("cell_type"), x.get("nt"), x.get("super_class"), x["rate_hz"]) for x in json.loads((S.OUT / "exhaustive_50Hz.json").read_text())}
    mh = counts(res, base, mn9, [hub], E.R_NEW)
    rh = sum(mh) / sum(med_s)
    rows, skipped = [], []
    for n in picks:
        mc, mab = counts(res, base, mn9, [n], E.R_NEW), counts(res, base, mn9, [n, hub], E.R_NEW)
        if None in mc or None in mab:          # 不再静默跳过：记下来，最后报出去（见 screen/segments.py 的说明）
            skipped.append(int(fids[n]))
            continue
        rc, rab = sum(mc) / sum(med_s), sum(mab) / sum(med_d)
        e_exp, e_ab = 1 - rc * rh, 1 - rab
        v = verdict(e_ab, e_exp)
        loo = []
        for j in range(E.R_NEW):
            rc_j = (sum(mc) - mc[j]) / (sum(med_s) - med_s[j])
            rh_j = (sum(mh) - mh[j]) / (sum(med_s) - med_s[j])
            rab_j = (sum(mab) - mab[j]) / (sum(med_d) - med_d[j])
            loo.append(verdict(1 - rab_j, 1 - rc_j * rh_j))
        c = ct.get(int(fids[n]), (None, None, None, None))
        rows.append(dict(fid=str(fids[n]), cell_type=c[0], nt=c[1], super_class=c[2], rate_hz=c[3],
                         ratio_single=round(rc, 4), ratio_with_hub=round(rab, 4), effect_expected=round(e_exp, 4),
                         effect_observed=round(e_ab, 4), delta=round(e_ab - e_exp, 4), verdict=v,
                         loo_stable=bool(all(x == v for x in loo))))
    rows.sort(key=lambda x: -x["delta"])
    syn = [r for r in rows if r["verdict"] == "协同"]
    if skipped:
        print(f"⚠️ {len(skipped)} 个候选缺少段，未计入：{skipped[:10]}（用 python screen/audit.py --fill 补跑）", flush=True)
    out = dict(design=dict(hub="CB0883", hub_fid=str(HUB), R=E.R_NEW, stage_a_R=STAGE_A_R, pick_delta=PICK_DELTA, margin=MARGIN),
               hub_ratio_single=round(rh, 4), n_stage_b=len(rows), n_skipped_missing_segments=len(skipped),
               summary=dict(n_synergy=len(syn), n_synergy_stable=sum(r["loo_stable"] for r in syn),
                            n_hidden=sum(r["loo_stable"] and r["ratio_single"] > 0.8 for r in syn)),
               rows=rows)
    (S.OUT / "hub_scan_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"CB0883 单独敲 {rh:.2f}；进入阶段 B 的 {len(rows)} 个里协同 {len(syn)} 个（留一稳定 {out['summary']['n_synergy_stable']} 个，"
          f"其中单独敲 > 0.8“看不出来”的 {out['summary']['n_hidden']} 个）\n")
    for r in syn:
        print(f"  {str(r['cell_type']):10s} {str(r['nt'])[:4]:5s} 放电 {r['rate_hz']:5.1f} Hz | 单独 {r['ratio_single']:.2f} → 加 CB0883 {r['ratio_with_hub']:.2f}"
              f" | Δ {r['delta']:+.2f} {'留一稳' if r['loo_stable'] else ''}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "analyze"])
    (cmd_run if ap.parse_args().cmd == "run" else cmd_analyze)()
