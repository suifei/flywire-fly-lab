#!/usr/bin/env python3
"""
Fotowat et al. 2009 的一条主张：巨纤维（DNp01）**不**响应逼近刺激。
这条在台账里原先记为「做不了」（模型没有长/短两种逃逸模式）。
但「在这个连接组模型里，逼近通路会不会驱动巨纤维」本身是可以直接量的，
而且**现成的全脑参考跑次里就有答案**，零新仿真。

数据：results/v2_ref/rerun_diff.csv —— 种子 bug 修复后重跑的 34 个全脑参考条件，
每个条件 2–4 个**独立**试次（run_experiment.py，Brian2 全脑，0.5 s），
里面有 GF_L / GF_R 的均值、SD、最小、最大。

分组（按刺激的是哪条通路，不看结果）：
  looming  = 刺激 LC4 和/或 LPLC2（dodge_ref/* 与 v2_ref/FRONT_LOOM）
  其他     = 糖、苦、JO（机械感觉）、LC16（另一类视觉投射神经元）、气味（DA2/DM1）

判据（**是看过参考表之后写的，如实说明**；但差距是 0 对 ~90–170 Hz，判据怎么定结论都一样）：
  论文主张在本模型里成立 ⇔ looming 组的巨纤维发放与「其他」组无法区分。
  这里取：looming 组每个条件的 min（4 个试次里最低的那次）都 > 其他组所有条件的 max ⇒ 主张不成立。

注意这测的**不是**论文的原话。论文是在体记录、真实视觉刺激；
我们是直接给 LC4/LPLC2 注入泊松放电，跳过了视网膜到小叶的全部视觉处理。
所以结论只能说到：「在这张接线图 + LIF 参数下，LC4/LPLC2 群体放电会强力驱动巨纤维」，
这与 Ache et al. 2019 一致、与 Fotowat 2009 的在体结果相反。

用法：python3 dodge/gf_looming_check.py      （只读，瞬时）
输出：results/dodge/gf_looming_check.json
"""
import csv, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "results/v2_ref/rerun_diff.csv")
OUT = os.path.join(ROOT, "results/dodge/gf_looming_check.json")


def pathway(cond):
    name = cond.split("/")[1]
    if name.startswith(("LOOM", "LC4_", "LPLC2_", "FRONT_LOOM")):
        return "looming"
    if name.startswith("LC16"):
        return "LC16"
    if name.startswith(("DA2", "DM1")):
        return "气味"
    if name.startswith("JO"):
        return "JO"
    if name.startswith(("SUGAR", "BITTER")):
        return "味觉"
    raise SystemExit(f"没见过的条件名：{cond}（补进 pathway() 再跑，别让它默默归到某一组）")


conds = {}
for r in csv.DictReader(open(SRC)):
    if r["readout"] not in ("GF_L", "GF_R"):
        continue
    c = conds.setdefault(r["cond"], {"pathway": pathway(r["cond"])})
    c[r["readout"]] = dict(n=int(r["n_trials"]), mean=float(r["new_mean"]), sd=float(r["new_sd"]),
                           min=float(r["new_min"]), max=float(r["new_max"]))

missing = [k for k, v in conds.items() if "GF_L" not in v or "GF_R" not in v]
if missing:
    raise SystemExit(f"这些条件缺 GF_L 或 GF_R：{missing}")

loom = {k: v for k, v in conds.items() if v["pathway"] == "looming"}
other = {k: v for k, v in conds.items() if v["pathway"] != "looming"}

loom_min = min(min(v["GF_L"]["min"], v["GF_R"]["min"]) for v in loom.values())
other_max = max(max(v["GF_L"]["max"], v["GF_R"]["max"]) for v in other.values())
other_nonzero = {k: {s: v[s] for s in ("GF_L", "GF_R") if v[s]["max"] > 0}
                 for k, v in other.items() if max(v["GF_L"]["max"], v["GF_R"]["max"]) > 0}

by_path = {}
for v in other.values():
    p = by_path.setdefault(v["pathway"], {"n_conditions": 0, "max_hz": 0.0})
    p["n_conditions"] += 1
    p["max_hz"] = max(p["max_hz"], v["GF_L"]["max"], v["GF_R"]["max"])

holds = not (loom_min > other_max)
res = {
    "source": "results/v2_ref/rerun_diff.csv",
    "note": "只读重算，零新仿真。GF_L/GF_R 用注释表 side；每个条件 2–4 个独立试次",
    "criterion": "looming 组每个条件、每一侧、每个试次的巨纤维发放都 > 其他组的最大值 ⇒ 论文主张在本模型里不成立",
    "criterion_written_after_seeing_data": True,
    "looming": {k.split("/")[1]: {"GF_L": v["GF_L"], "GF_R": v["GF_R"]} for k, v in sorted(loom.items())},
    "n_looming_conditions": len(loom),
    "n_other_conditions": len(other),
    "n_other_strictly_zero": len(other) - len(other_nonzero),
    "other_by_pathway": by_path,
    "other_nonzero": {k.split("/")[1]: v for k, v in other_nonzero.items()},
    "looming_min_hz": loom_min,
    "other_max_hz": other_max,
    "dose": {"LOOM_L_40_GF_L": loom["dodge_ref/LOOM_L_40"]["GF_L"]["mean"],
             "LOOM_L_100_GF_L": loom["dodge_ref/LOOM_L_100"]["GF_L"]["mean"]},
    "single_type": {"LC4_L_100_GF_L": loom["dodge_ref/LC4_L_100"]["GF_L"]["mean"],
                    "LPLC2_L_100_GF_L": loom["dodge_ref/LPLC2_L_100"]["GF_L"]["mean"]},
    "paper_claim_holds_in_model": holds,
}
json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1)

print(f"looming 条件 {len(loom)} 个，其他通路条件 {len(other)} 个")
for k, v in sorted(loom.items()):
    print(f"  {k.split('/')[1]:14} GF 左 {v['GF_L']['mean']:6.1f} ± {v['GF_L']['sd']:.1f}   右 {v['GF_R']['mean']:6.1f} ± {v['GF_R']['sd']:.1f} Hz")
for p, s in by_path.items():
    print(f"  {p:6} {s['n_conditions']:2d} 个条件，巨纤维最大 {s['max_hz']:.1f} Hz")
if other_nonzero:
    print(f"  其他组里非零的：{json.dumps(res['other_nonzero'], ensure_ascii=False)}")
print(f"looming 组最低的一次 {loom_min:.1f} Hz  vs  其他组最高的一次 {other_max:.1f} Hz")
print("→ 论文主张「巨纤维不响应逼近」在本模型里" + ("成立" if holds else "**不成立**"))
print("→", os.path.relpath(OUT, ROOT))
