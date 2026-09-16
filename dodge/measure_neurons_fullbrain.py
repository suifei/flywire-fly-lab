#!/usr/bin/env python
"""页面上那 10 个神经元的**全脑**敲除比值，用单一口径从段数据重算。

为什么要有这个脚本（2026-09-16）：
  页面 `G.NEURONS` 里的 `full` 一列原本是从报告各节里手抄的，核对后发现**混了至少三种口径**——
  Roundup 0.74 是未做零参照归一化的值（同口径应为 0.83）；Phantom 1.08 在任何一份结果文件里都找不到来源；
  CB0883 0.75 来自 12 实现的双敲除表，和其余几个的 6 实现单敲不同。
  这类"数字来源不明"正是本轮连续栽跟头的原因，所以改成一次算全、口径写死在这里。

口径（与 22.2 节 concentration.py、19 节 water_screen.py 完全一致）：
  - 糖通路：50 Hz，`results/screen/` 的段；水通路：160 Hz，`results/screen/water/` 的段。
  - 比值 = 敲除后读出脉冲数之和 ÷ 零参照中位数之和，**前 6 个实现**。
    零参照 = 同实现下所有单敲除的中位数（板内中位数归一化，14.4 节的混沌偏差修正）。
  - 该神经元在某实现里不放电时，敲它等于什么都没做，直接用基线（已逐位验证，V2）。
  - **与页面开关口径一致**：页面的开关会把该类型列出的全部 ID 一起切断传出突触，所以这里也**一起敲**
    （Roundup / G2N-1 / Zorro 各 2 个，其余各 1 个；三个联合段都已在盘上）。同时保留逐个神经元的值供查。
输出 results/dodge/neuron_ratios_fullbrain.json
用法（brain-fly-cpu 环境）：python dodge/measure_neurons_fullbrain.py
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "screen")); sys.path.insert(0, str(ROOT))
import sugar_mn9_screen as S  # noqa: E402
import segments as SEG  # noqa: E402

R = 6


def game_neurons():
    """从 game_core.js 里读出页面实际用的那 10 个神经元及其 ID（保持单一事实来源）。"""
    src = (ROOT / "dodge" / "game_core.js").read_text()
    out = []
    for m in re.finditer(r'\{ key: "([^"]+)", type: "([^"]+)", ids: \[([^\]]+)\]', src):
        ids = [int(x.strip().strip('"')) for x in m.group(3).split(",")]
        out.append(dict(key=m.group(1), cell_type=m.group(2), ids=ids))
    return out


def joint_ratios(neurons, base, repo, readout_idx, fid2i, med, field, fi=0):
    """把该类型列出的全部 ID **一起**敲掉，口径与页面开关一致；同时记录逐个神经元的值。"""
    res = {}
    for rec in neurons:
        detail, idxs = [], []
        for f in rec["ids"]:
            n = fid2i.get(f)
            if n is None:
                detail.append(dict(fid=str(f), status="不在 v783 模型里")); continue
            rate = float(np.mean([base[r][n] for r in range(R)]))
            m = [repo.get((fi, r, (n,)), field=field, default=None) if base[r][n] > 0 else int(base[r][readout_idx])
                 for r in range(R)]
            detail.append(dict(fid=str(f), status="ok" if None not in m else "缺段", rate_hz=round(rate, 2),
                               ratio=None if None in m else round(sum(m) / sum(med), 4)))
            idxs.append(n)
        joint = None
        if idxs:
            key = tuple(sorted(idxs))
            fires = any(base[r][n] > 0 for r in range(R) for n in idxs)
            if not fires:
                joint = 1.0                      # 全都不放电 → 敲了等于没敲（V2 已逐位验证）
            else:
                m = [repo.get((fi, r, key), field=field, default=None) if any(base[r][n] > 0 for n in idxs)
                     else int(base[r][readout_idx]) for r in range(R)]
                joint = None if None in m else sum(m) / sum(med)
        res[rec["key"]] = dict(ratio=None if joint is None else round(joint, 3),
                               n_ids_in_model=len(idxs), per_neuron=detail)
    return res


def main():
    neurons = game_neurons()
    print(f"页面神经元 {len(neurons)} 个：{', '.join(n['key'] for n in neurons)}\n")
    fids, fid2i = S.load_ids()
    N = len(fids)

    # —— 糖 50 Hz ——
    import double_extend as E
    E.setup()
    mn9 = fid2i[S.MN9]
    _, bc, _ = S.load_chunk(E.EXT / "baseline12.npz", N)
    base = {r: bc[r] for r in range(R)}
    repo = SEG.Repo([S.CHUNKS, S.OUT / "double", E.EXT, S.OUT / "double_hub", S.OUT / "hub_scan"], watch={"mn9": mn9})
    plan = json.loads((S.OUT / "plan.json").read_text()) if (S.OUT / "plan.json").exists() else None
    # 零参照：与 concentration.py 一致，用 double12_summary 里存好的那一组
    med_sugar = json.loads((S.OUT / "double12_summary.json").read_text())["null_median_single"][:R]
    sugar = joint_ratios(neurons, base, repo, mn9, fid2i, med_sugar, "mn9")

    # —— 水 160 Hz ——
    import water_screen as W
    W.setup()
    fidsw, fid2iw, Nw, mn9w, basew12, _ = W.load_state()
    basew = {r: basew12[r] for r in range(R)}
    repow = SEG.Repo([W.WDIR / "chunks", W.WDIR / "hub_scan"], watch={"mn9": mn9w})
    planw = json.loads((W.WDIR / "plan.json").read_text())
    med_water = [float(np.median([
        (repow.get((0, r, (fid2iw[f],)), field="mn9", default=None) if basew[r][fid2iw[f]] > 0 else int(basew[r][mn9w]))
        for f in planw["null_single"] if f in fid2iw])) for r in range(R)]
    water = joint_ratios(neurons, basew, repow, mn9w, fid2iw, med_water, "mn9")

    gm = {n["key"]: n for n in json.loads((ROOT / "results/dodge/neuron_ratios.json").read_text())["neurons"]}
    rows = []
    print(f"{'神经元':10s} {'类型':12s} {'全脑糖':>7s} {'全脑水':>7s} {'游戏糖':>7s} {'游戏水':>7s}")
    for rec in neurons:
        k = rec["key"]
        row = dict(key=k, cell_type=rec["cell_type"],
                   full_sugar=sugar[k]["ratio"], full_water=water[k]["ratio"],
                   game_sugar=gm.get(k, {}).get("sugar"), game_water=gm.get(k, {}).get("water"),
                   sugar_detail=sugar[k]["per_neuron"], water_detail=water[k]["per_neuron"])
        rows.append(row)
        f = lambda v: "  —  " if v is None else f"{v:5.2f}"
        print(f"{k:10s} {rec['cell_type']:12s} {f(row['full_sugar']):>7s} {f(row['full_water']):>7s} "
              f"{f(row['game_sugar']):>7s} {f(row['game_water']):>7s}")
    out = dict(protocol=dict(R=R, sugar_freq_hz=50, water_freq_hz=160,
                             note="比值 = 敲除后读出 ÷ 同实现全部单敲除的中位数（板内中位数归一化，见报告 14.4 节）；"
                                  "一个类型有多个神经元时**一起敲**（与页面开关一致）；全员都不放电时记 1.0"),
               null_median=dict(sugar=med_sugar, water=med_water), neurons=rows)
    dst = ROOT / "results/dodge/neuron_ratios_fullbrain.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("\n写入", dst)


if __name__ == "__main__":
    main()
