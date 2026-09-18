#!/usr/bin/env python
"""复现论文 Fig 3B–C：苦能压住强糖，Ir94e 压不住（补充表 10 第 5 行，论文自报 4/4）。

论文 notebook（figures.ipynb Figure 3）跑的是 11×11 的频率网格（0–200 Hz，步长 20），
两张图：糖 × 苦、糖 × Ir94e，读出 MN9 左。我们用同一个 Brian2 编译（与 taste_interaction.py
共用 81 个 GRN 源、8 个频率档），跑一个 5×6 的子网格——档位受编译时的 FREQS 限制。

**判据事先写死**（照抄论文表 10 第 5 行那句话的两半）：
  A. 最强糖（220 Hz）下，苦 220 Hz 让 MN9 相对无苦对照下降 ≥ 50% → 「苦能压住强糖」成立。
  B. 同条件下 Ir94e 220 Hz 的下降 < 50% → 「Ir94e 压不住」成立。
另外报告每个糖档下两种抑制剂的完整剂量曲线，用于和 Fig 3 的形状比。

刺激名单用官方 notebook 的（TASTE_LIST=notebook 那套：苦 20、Ir94e 18），糖 21 个。

用法（brain-fly-cpu，套 memguard）：python screen/taste_grid.py run|analyze
输出 results/screen/taste/grid/
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

os.environ.setdefault("TASTE_LIST", "notebook")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import sugar_mn9_screen as S  # noqa: E402
import taste_interaction as T  # noqa: E402

SUGAR_HZ = (40, 80, 120, 160, 220)
MOD_HZ = (None, 20, 40, 80, 160, 220)
R = 3
GDIR = S.OUT / "taste" / "grid"
TRIAL_S = S.TRIAL_STEPS * S.DT_MS * 1e-3


def conds():
    """(糖 Hz, 抑制剂模态, 抑制剂 Hz)；抑制剂为空的那 5 条两张图共用，只跑一次。"""
    out = [(s, None, None) for s in SUGAR_HZ]
    for m in ("bitter", "ir94e"):
        out += [(s, m, h) for s in SUGAR_HZ for h in MOD_HZ if h is not None]
    return out


def cmd_run():
    g, order, span = T.setup()
    fi_of = {f: i for i, f in enumerate(T.FREQS)}
    GDIR.mkdir(parents=True, exist_ok=True)
    (GDIR / "chunks").mkdir(exist_ok=True)
    cs = conds()
    jobs = [(c, r) for c in cs for r in range(R)]
    print(f"{len(cs)} 个条件 × {R} 个实现 = {len(jobs)} 段", flush=True)
    sc = None
    for c0 in range(0, len(jobs), S.K):
        blk = jobs[c0:c0 + S.K]
        f = GDIR / "chunks" / f"g{c0:05d}.npz"
        if f.exists():
            continue
        if sc is None:
            sc = S.Screen()
        segs, plan = [], []
        for (sh, m, mh), r in blk:
            segs.append((fi_of[sh], r, ()))
            p = [("sugar", fi_of[sh])]
            if m:
                p.append((m, fi_of[mh]))
            plan.append(p)
        pad = S.K - len(segs)
        t0 = time.time()
        cnt, _ = sc.run_chunk(segs, extra_args={sc.ingate: T.ingate_for(sc, segs + [(0, 0, ())] * pad, span, plan + [[]] * pad)})
        keys = [[sh, r, [MOD_HZ.index(mh) if m else 0, ("", "bitter", "ir94e").index(m or "")]] for (sh, m, mh), r in blk]
        S.save_chunk(f, keys, cnt, time.time() - t0)
        print(f"  {c0:4d}/{len(jobs)}  {time.time() - t0:.0f}s", flush=True)
    print("→", GDIR / "chunks")


def cmd_analyze():
    g, order, span = T.setup()
    fids, fid2i = S.load_ids()
    N = len(fids)
    mn9i = fid2i[S.MN9]
    got = {}
    for f in sorted((GDIR / "chunks").glob("g*.npz")):
        keys, cnt, _ = S.load_chunk(f, N)
        for (sh, r, code), row in zip(keys, cnt):
            mi, mm = code
            m = ("", "bitter", "ir94e")[mm]
            got.setdefault((sh, m or None, MOD_HZ[mi] if m else None), []).append(int(row[mn9i]) / TRIAL_S)
    rate = {k: float(np.mean(v)) for k, v in got.items()}
    miss = [c for c in conds() if len(got.get(c, [])) < R]
    print(f"条件 {len(rate)} 个；缺口 {len(miss)}" + (f" 例：{miss[:3]}" if miss else ""))

    out = dict(design=dict(sugar_hz=list(SUGAR_HZ), mod_hz=[h for h in MOD_HZ if h], R=R,
                           stim_list="notebook", grn_counts={k: len(v) for k, v in g.items()},
                           criterion="最强糖 220 Hz 下：苦 220 Hz 使 MN9 下降 ≥50%（成立）、Ir94e 220 Hz 下降 <50%（成立）"),
               grid={}, drop={})
    print(f"\n{'糖 Hz':>6s}{'无抑制':>8s}" + "".join(f"{'苦'+str(h):>9s}" for h in MOD_HZ if h)
          + "".join(f"{'Ir'+str(h):>9s}" for h in MOD_HZ if h))
    for s in SUGAR_HZ:
        b0 = rate.get((s, None, None), 0.0)
        row = dict(none=round(b0, 2),
                   bitter={str(h): round(rate.get((s, "bitter", h), 0.0), 2) for h in MOD_HZ if h},
                   ir94e={str(h): round(rate.get((s, "ir94e", h), 0.0), 2) for h in MOD_HZ if h})
        out["grid"][str(s)] = row
        print(f"{s:6d}{b0:8.1f}" + "".join(f"{row['bitter'][str(h)]:9.1f}" for h in MOD_HZ if h)
              + "".join(f"{row['ir94e'][str(h)]:9.1f}" for h in MOD_HZ if h))
    smax = SUGAR_HZ[-1]
    base = rate.get((smax, None, None), 0.0)
    res = {}
    for m in ("bitter", "ir94e"):
        v = rate.get((smax, m, 220), 0.0)
        d = 1.0 - (v / base if base > 0 else 0.0)
        res[m] = dict(sugar_hz=smax, mod_hz=220, mn9_no_mod=round(base, 2), mn9_with_mod=round(v, 2),
                      drop_frac=round(d, 3))
    out["drop"] = res
    A = res["bitter"]["drop_frac"] >= 0.5
    B = res["ir94e"]["drop_frac"] < 0.5
    out["criterion_A_bitter_suppresses"] = bool(A)
    out["criterion_B_ir94e_does_not"] = bool(B)
    out["both_pass"] = bool(A and B)
    print(f"\n判据（糖 {smax} Hz，抑制剂 220 Hz，无抑制时 MN9 {base:.1f} Hz）")
    print(f"  A 苦下降 {res['bitter']['drop_frac']:.1%} → {'成立' if A else '不成立'}（要求 ≥50%）")
    print(f"  B Ir94e 下降 {res['ir94e']['drop_frac']:.1%} → {'成立' if B else '不成立'}（要求 <50%）")
    GDIR.mkdir(parents=True, exist_ok=True)
    (GDIR / "summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("\n→", GDIR / "summary.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["run", "analyze"])
    {"run": cmd_run, "analyze": cmd_analyze}[ap.parse_args().cmd]()
