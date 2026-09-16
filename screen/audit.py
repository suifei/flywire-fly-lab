#!/usr/bin/env python
"""
数据体检：报告第 14、16、19 节里每个结论所依赖的段，是不是都真的在盘上。

背景见 screen/segments.py 的说明——这一轮出过三次“分析要用的段没跑到”的问题，而且都是静默降级，不会自己暴露。
这里把每个实验“分析需要哪些段”重新枚举一遍，与仓库对照，缺什么就列出来（`--fill` 则直接补跑）。
不改动任何已有结果，只做核对。

覆盖：
  sugar_P / sugar_E / sugar_T   第 14 节：论文 183 个、穷举 313 个、10 个类型（单个 + 两侧），50 与 100 Hz
  double6 / double12            第 16 节：66 对 + GRN 剂量 + 对照对（6 个实现）、补到 12 个实现的部分
  double_hub                    16.1 节：排名 13–24 × 两个枢纽
  hub_scan                      16.2 节：312 个候选 × CB0883（阶段 A 6 个实现；阶段 B 50 个 × 12 个实现）
  water                         第 19 节：论文 186 个、10 个类型、零参照、双敲除 66 对
用法（brain-fly-cpu 环境）：python screen/audit.py [--fill]
"""
import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import sugar_mn9_screen as S  # noqa: E402
import segments as SEG  # noqa: E402


def sugar_audit(repo_dirs):
    """第 14 节 + 16 节 + 16.1 + 16.2：糖通路（50 / 100 Hz）。"""
    import double_extend as E
    fids, fid2i = S.load_ids()
    N = len(fids)
    mn9 = fid2i[S.MN9]
    plan = json.loads((S.OUT / "plan.json").read_text())
    R6 = plan["R"]
    _, bc8, _ = S.load_chunk(S.CHUNKS / "baseline.npz", N)          # 主筛选：R_MAX = 8 布局
    base8 = {(fi, r): bc8[fi * 8 + r] for fi in range(2) for r in range(8)}
    _, bc12, _ = S.load_chunk(E.EXT / "baseline12.npz", N)          # 扩展：50 Hz、12 个实现
    base12 = {r: bc12[r] for r in range(12)}
    repo = SEG.Repo(repo_dirs, watch={"mn9": mn9})
    audits = []

    rows_1c, _ = S.paper_table_1c()
    p_idx = [fid2i[r["fid"]] for r in rows_1c if r["fid"] in fid2i and r["fid"] != S.MN9]
    e_idx = [fid2i[int(x["fid"])] for x in json.loads((S.OUT / "exhaustive_50Hz.json").read_text()) if int(x["fid"]) in fid2i]
    members = plan["type_members"]
    for name, fi, conds in [
            ("sugar_P_50Hz", 0, [[n] for n in p_idx]),
            ("sugar_P_100Hz", 1, [[n] for n in p_idx]),
            ("sugar_E_50Hz", 0, [[n] for n in e_idx if n != mn9]),
            ("sugar_T_50Hz", 0, [[fid2i[S.PAPER_SINGLE[t]]] for t in S.TYPES] + [[fid2i[x] for x in members[t]] for t in S.TYPES]),
            ("sugar_T_100Hz", 1, [[fid2i[S.PAPER_SINGLE[t]]] for t in S.TYPES] + [[fid2i[x] for x in members[t]] for t in S.TYPES])]:
        b = {r: base8[(fi, r)] for r in range(R6)}
        keys = SEG.needed_keys(b, R6, conds, fi=fi)
        audits.append(dict(name=name, n_required=len(keys), n_missing=len(repo.need(keys)), missing=[list(k) for k in repo.need(keys)[:10]]))

    dplan = json.loads((S.OUT / "double_plan.json").read_text())
    pairs = [[fid2i[x] for x in p] for p in dplan["a_pairs"]]
    cpairs = [[fid2i[x] for x in p] for p in dplan["c_pairs"]]
    bsets = [[fid2i[x] for x in s] for s in dplan["b_sets"]]
    tops = [fid2i[f] for f in dplan["top"]]
    b6 = {r: base12[r] for r in range(6)}
    audits.append(dict(name="double6_A+B+C", **_chk(repo, SEG.needed_keys(b6, 6, pairs + cpairs + bsets + [[t] for t in tops]))))
    p12 = json.loads((S.OUT / "double12_plan.json").read_text())
    null_single = [[fid2i[f]] for f in p12["null_single"]]
    audits.append(dict(name="double12_all", **_chk(repo, SEG.needed_keys(base12, 12, pairs + cpairs + [[t] for t in tops] + null_single))))

    hplan = json.loads((S.OUT / "double_hub_plan.json").read_text())
    hubs = [fid2i[int(h)] for h in hplan["hubs"]]
    hc = [fid2i[int(c["fid"])] for c in hplan["candidates"]]
    audits.append(dict(name="double_hub", **_chk(repo, SEG.needed_keys(base12, 12, [[c] for c in hc] + [[c, h] for c in hc for h in hubs]))))

    hub = fid2i[720575940625102692]
    scanA = [[n] for n in e_idx if n not in (hub, mn9)] + [[n, hub] for n in e_idx if n not in (hub, mn9)]
    audits.append(dict(name="hub_scan_stageA(6)", **_chk(repo, SEG.needed_keys(b6, 6, scanA))))
    picks = [fid2i[f] for f in json.loads((S.OUT / "hub_scan_stageA.json").read_text())["picks"]]
    scanB = [[n] for n in picks + [hub]] + [[n, hub] for n in picks]
    audits.append(dict(name="hub_scan_stageB(12)", **_chk(repo, SEG.needed_keys(base12, 12, scanB))))
    return repo, audits, dict(base8=base8, base12=base12, fid2i=fid2i, mn9=mn9)


def water_audit():
    """第 19 节：水通路（160 Hz）。"""
    import water_screen as W
    W.setup()
    fids, fid2i = S.load_ids()
    N = len(fids)
    mn9 = fid2i[S.MN9]
    _, bc, _ = S.load_chunk(W.WDIR / "baseline.npz", N)
    base = {r: bc[r] for r in range(W.R_ALL)}
    repo = SEG.Repo([W.WDIR / "chunks"], watch={"mn9": mn9})
    plan = json.loads((W.WDIR / "plan.json").read_text())
    dplan = json.loads((W.WDIR / "double_plan.json").read_text())
    rows6c, _ = W.paper_6c()
    p_idx = [fid2i[r["fid"]] for r in rows6c if r["fid"] in fid2i and r["fid"] != S.MN9]
    types = [[fid2i[W.PAPER_SINGLE[t]]] for t in W.TYPES] + [[fid2i[int(x)] for x in plan["members"][t]] for t in W.TYPES]
    nulls = [[fid2i[f]] for f in plan["null_single"]] + [[fid2i[a], fid2i[b]] for a, b in plan["null_pairs"]]
    pairs = [[fid2i[int(a)], fid2i[int(b)]] for a, b in dplan["pairs"]]
    tops = [[fid2i[int(f)]] for f in dplan["top"]]
    audits = [dict(name="water_P(6)", **_chk(repo, SEG.needed_keys({r: base[r] for r in range(6)}, 6, [[n] for n in p_idx]))),
              dict(name="water_T+null(12)", **_chk(repo, SEG.needed_keys(base, 12, types + nulls))),
              dict(name="water_double(12)", **_chk(repo, SEG.needed_keys(base, 12, pairs + tops)))]
    return repo, audits, base


def _chk(repo, keys):
    miss = repo.need(keys)
    return dict(n_required=len(keys), n_missing=len(miss), missing=[list(k) for k in miss[:10]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fill", action="store_true", help="发现缺口就补跑（一次只跑一个仿真）")
    a = ap.parse_args()
    import double_extend as E
    sugar_dirs = [S.CHUNKS, S.OUT / "double", E.EXT, S.OUT / "double_hub", S.OUT / "hub_scan"]
    repo_s, aud_s, ctx = sugar_audit(sugar_dirs)
    print("—— 糖通路 ——")
    for x in aud_s:
        print(f"  {'✅' if x['n_missing'] == 0 else '❌'} {x['name']:22s} 需要 {x['n_required']:5d}，缺 {x['n_missing']}")
    repo_w, aud_w, wbase = water_audit()
    print("—— 水通路 ——")
    for x in aud_w:
        print(f"  {'✅' if x['n_missing'] == 0 else '❌'} {x['name']:22s} 需要 {x['n_required']:5d}，缺 {x['n_missing']}")
    total = SEG.report(aud_s + aud_w, S.OUT / "audit.json")
    if total and a.fill:
        print("\n开始补跑糖通路缺口……", flush=True)
        import double_extend as E2
        E2.setup()
        miss_s = [tuple(k) for x in aud_s for k in x["missing"]]
        if miss_s:
            repo_s.fill(miss_s, lambda: S.Screen(), S.OUT / "audit_fill", "sugar")
        miss_w = [tuple(k) for x in aud_w for k in x["missing"]]
        if miss_w:
            import water_screen as W
            W.setup()
            repo_w.fill(miss_w, lambda: S.Screen(), W.WDIR / "chunks", "audit")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
