#!/usr/bin/env python
"""复查 Fly-Brain-AI 气味效价实验的 4/6：两个失败项是什么原因，四个通过项有多硬？

§10.5 记了「6 条判据复现 4 条，DM1 那两条失败」，但没说为什么。
这个脚本只读已有的 checkpoint（results/fba_odor_valence/checkpoints/*.json），
不跑任何新仿真，回答两件事：

  1. **失败的两条是不是因为 DM1 让全脑失控？**（§11.4 测过 35 个 DM1 ORN @10 Hz
     会在 25 ms 内点着约 8,300 个神经元）——比较 DM1 与 DM5 条件下读出层的活动强度。
  2. **通过的四条里，有两条是「真实 vs 打乱」的对照。** 如果打乱臂根本不放电，
     那这种对照是**空的**——任何非零效应都能通过。这一点必须查。

用法：python fba_odor_recheck.py（只读，几秒）→ results/fba_odor_valence/recheck.json
"""
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CK = ROOT / "results/fba_odor_valence/checkpoints"
RES = json.loads((ROOT / "results/fba_odor_valence/valence_results.json").read_text())

rows = defaultdict(list)
for f in sorted(CK.glob("*.json")):
    d = json.loads(f.read_text())
    for e in d["episode_log"]:
        rows[d["label"]].append(e)

def agg(pred, key):
    v = [e[key] for lab, es in rows.items() if pred(lab) for e in es]
    return round(st.median(v), 3) if v else None

out = {"note": "只读 checkpoint，不跑新仿真；readout_* 是解码器读出那 ~350 个神经元的统计，不是全脑",
       "n_conditions": len(rows), "by_condition": {}}
for lab in sorted(rows):
    es = rows[lab]
    out["by_condition"][lab] = dict(
        n=len(es),
        readout_mean_hz=round(st.median(e["readout_mean_hz"] for e in es), 2),
        readout_active=round(st.median(e["readout_active"] for e in es), 1),
        turn_drive=round(st.median(e["turn_drive"] for e in es), 4),
        forward_drive=round(st.median(e["forward_drive"] for e in es), 4))

real = lambda l: "_real_" in l
shuf = lambda l: "_shuffled_" in l
dm1 = lambda l: l.startswith("DM1") and real(l)
dm5 = lambda l: l.startswith("DM5") and real(l)

out["q1_dm1_vs_dm5"] = dict(
    dm1_readout_hz=agg(dm1, "readout_mean_hz"), dm5_readout_hz=agg(dm5, "readout_mean_hz"),
    dm1_readout_active=agg(dm1, "readout_active"), dm5_readout_active=agg(dm5, "readout_active"),
    verdict=None)
q1 = out["q1_dm1_vs_dm5"]
q1["verdict"] = ("DM1 与 DM5 的读出活动几乎一样，**失败不是因为 DM1 把读出打爆了**"
                 if abs(q1["dm1_readout_hz"] - q1["dm5_readout_hz"]) < 3 else
                 "DM1 的读出活动明显更高，与「DM1 引发失控」一致")

out["q2_shuffled_control"] = dict(
    shuffled_readout_hz=agg(shuf, "readout_mean_hz"),
    shuffled_readout_active=agg(shuf, "readout_active"),
    real_readout_hz=agg(real, "readout_mean_hz"),
    shuffled_is_dead=bool((agg(shuf, "readout_active") or 0) < 1),
    verdict=None)
q2 = out["q2_shuffled_control"]
q2["verdict"] = ("**打乱臂的读出完全不放电**，所以「真实 vs 打乱」这类判据是空的——"
                 "任何非零效应都能通过。6 条里有 2 条属于这一类"
                 if q2["shuffled_is_dead"] else "打乱臂仍有读出活动，对照不空")

out["turn_drive_common_bias"] = agg(real, "turn_drive")
out["tests"] = RES["tests"]
out["passed"] = sum(1 for t in RES["tests"] if t["passed"])
out["vacuous_tests"] = [t["name"] for t in RES["tests"] if "specificity" in t["name"]] if q2["shuffled_is_dead"] else []
out["effective_passed"] = out["passed"] - sum(1 for t in RES["tests"] if t["passed"] and t["name"] in out["vacuous_tests"])

print(f"{'条件':26s}{'读出 Hz':>10s}{'活跃':>7s}{'turn_drive':>12s}")
for lab, v in out["by_condition"].items():
    print(f"{lab:26s}{v['readout_mean_hz']:10.1f}{v['readout_active']:7.0f}{v['turn_drive']:12.3f}")
print(f"\n问题 1：DM1 读出 {q1['dm1_readout_hz']} Hz vs DM5 {q1['dm5_readout_hz']} Hz → {q1['verdict']}")
print(f"问题 2：打乱臂读出 {q2['shuffled_readout_hz']} Hz、活跃 {q2['shuffled_readout_active']} 个 → {q2['verdict']}")
print(f"\n原始判据 {out['passed']}/6；扣掉空对照后**实质通过 {out['effective_passed']}/6**"
      f"（空的是 {'、'.join(out['vacuous_tests']) or '无'}）")
print(f"所有真实条件的 turn_drive 中位 {out['turn_drive_common_bias']}——§10.5 说的那个共同偏置")
p = ROOT / "results/fba_odor_valence/recheck.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=1))
print("→", p)
