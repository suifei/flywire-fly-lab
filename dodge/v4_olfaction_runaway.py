"""
嗅觉“全脑失控”诊断（探索性，事后分析；只读已有全脑结果 results/v2_ref/*，不跑仿真）。

问题：为什么 35 个 DM1 嗅觉受体神经元只给 10 Hz，全脑也会在 25 ms 内扩散到 ~8,300 个神经元？
做法（跑之前写定）：
  1. 每个失控条件、每个试次：5 ms 分箱，“有脉冲的不同神经元数”首次 ≥ 500 的时刻 = 失控起点。
  2. 点火集合：起点前 15 ms 内放电、且不是被刺激神经元的神经元，按脉冲数排序取前 50。
  3. 核心 = 至少在 4 个失控条件（DM1_L_10、DM1_R_20、DA2_L_100、SUGAR_LR_100、SUGAR_R）的点火集合里出现的神经元。
  4. 结构对照：DM1 受体神经元（左/右）→ DM1 投射神经元（左/右）的突触数，检查 side 标签的含义。
输出 results/v2_ref/olfaction_runaway.json
用法（flygym 环境）：python dodge/v4_olfaction_runaway.py
"""
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "results" / "v2_ref"
ann = pd.read_csv(ROOT / "external/flywire_annotations/Supplemental_file1_neuron_annotations.tsv", sep="\t", low_memory=False,
                  usecols=["root_id", "cell_type", "side", "super_class", "cell_class", "top_nt"]).drop_duplicates("root_id").set_index("root_id")
CONDS = ["DM1_L_10", "DM1_R_20", "DA2_L_100", "SUGAR_LR_100", "SUGAR_R"]


def ignition(cond, bin_ms=5, pre_ms=15, top=50):
    s = json.load(open(REF / cond / "summary.json"))
    stim = set(map(int, s["exc_ids"]))
    sp = pd.read_parquet(REF / cond / "spikes_baseline.parquet")
    counts, onsets = Counter(), []
    for tr, g in sp.groupby("trial"):
        per = g.groupby(g.time_ms // bin_ms).flywire_id.nunique()
        hit = per.index[per.to_numpy() >= 500]
        if not len(hit):
            continue
        on = float(hit[0] * bin_ms); onsets.append(on)
        w = g[(g.time_ms >= on - pre_ms) & (g.time_ms < on) & ~g.flywire_id.isin(stim)]
        counts.update(w.flywire_id.tolist())
    ids = [i for i, _ in counts.most_common(top)]
    return dict(onsets_ms=onsets, ids=ids, counts={int(i): int(counts[i]) for i in ids})


def describe(ids):
    sub = ann.reindex(ids)
    return [f"{sub.cell_type.get(i)}|{sub.cell_class.get(i)}|{str(sub.side.get(i))[:1]}|{sub.top_nt.get(i)}" for i in ids]


def main():
    res = {c: ignition(c) for c in CONDS}
    for c, r in res.items():
        print(f"\n{c}: 失控起点（每试次）{r['onsets_ms']} ms；点火前 15 ms 放电最多的 12 个：")
        for i, d in zip(r["ids"][:12], describe(r["ids"][:12])):
            print(f"   {i}  {d}  脉冲 {r['counts'][int(i)]}")
    occ = Counter(i for r in res.values() for i in set(r["ids"]))
    core = sorted([i for i, k in occ.items() if k >= 4], key=lambda i: -occ[i])
    print(f"\n核心（≥4 个条件的点火集合都出现）：{len(core)} 个")
    for i, d in zip(core, describe(core)):
        print(f"   {i}  {d}  出现 {occ[i]} 次")
    tc = ann.reindex(core).cell_type.value_counts()
    print("核心细胞类型计数：", tc.to_dict())

    con = pd.read_parquet(ROOT / "external/fly-brain/data/2025_Connectivity_783.parquet",
                          columns=["Presynaptic_ID", "Postsynaptic_ID", "Connectivity", "Excitatory"])
    orn = {s: set(ann.index[(ann.cell_type == "ORN_DM1") & (ann.side == s)]) for s in ("left", "right")}
    pn = {s: set(ann.index[ann.cell_type.fillna("").str.startswith("DM1_") & (ann.cell_class == "ALPN") & (ann.side == s)]) for s in ("left", "right")}
    syn = {}
    for a in ("left", "right"):
        for b in ("left", "right"):
            m = con.Presynaptic_ID.isin(orn[a]) & con.Postsynaptic_ID.isin(pn[b])
            syn[f"ORN_DM1_{a}->DM1_PN_{b}"] = int(con.Connectivity[m].sum())
    print("\n结构：DM1 受体 → DM1 投射神经元突触数：", syn, "；投射神经元数", {s: len(v) for s, v in pn.items()})
    core_set = set(core)
    m = con.Presynaptic_ID.isin(core_set) & con.Postsynaptic_ID.isin(core_set)
    rec = dict(edges=int(m.sum()), synapses=int(con.Connectivity[m].sum()),
               exc_synapses=int(con.Connectivity[m & (con.Excitatory > 0)].sum()))
    print("核心内部互连：", rec)
    out = dict(conditions=res, core=[int(i) for i in core], core_desc=describe(core), core_types=tc.to_dict(),
               orn_pn_synapses=syn, core_internal=rec)
    (REF / "olfaction_runaway.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
