#!/usr/bin/env python
"""复核 10 个实验类型的判定：它随**实现数 R** 和**归一化口径**翻转吗？

起因（用户 2026-09-19 指出页面数字对不上）。追下去发现同一个类型有**三个并存的数字**，
各自都没标口径，而且文档自相矛盾：
  · docs/log/report.md §14.5 的表：Zorro 我们 0.76「必需 ✅」
  · docs/log/report.md §16.1 正文：「我们（和论文）的单个敲除都判它不必需」
  · AGENTS.md 第 332 行说判必需、第 333 行说判不必需
  · 游戏页面显示 0.85（零参照归一化），而 docs/log/report.md 的表是未归一化的 0.76

这个脚本**只从权威结果文件取数**（不重新实现归一化），把四个口径并排列出来，
并指出哪些类型的判定是"口径依赖"的 —— 对这些类型，任何"我们判它必需/不必需"的说法
都必须同时说明口径。

数据来源：
  论文值、我们 R=6 未归一化、我们 R=6 零参照归一化  ← results/screen/summary.json
  我们 R=12 未归一化                              ← results/screen/hub_scan_summary.json
                                                   （stage B 只把 |1−比值| ≥ 0.05 的补到 R=12，
                                                    所以只有一部分类型有这个数，缺的如实标 —）
用法：python3 screen/recheck_calls.py   （只读，秒级）
输出 results/screen/recheck_calls.json
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
S = json.loads((ROOT / "results/screen/summary.json").read_text())
H = json.loads((ROOT / "results/screen/hub_scan_summary.json").read_text())
CALL = S["design"]["call_threshold"]
R12 = {r["cell_type"]: r["ratio_single"] for r in H["rows"]}
NORM = S["exploratory_null_normalized"]["types"]
CT = {"Bract": ["DNge173", "DNge174"], "Clavicle": ["AN_GNG_30"], "Fdg": ["CB0038"], "FMIn": ["CB0366"],
      "G2N-1": ["CB0616"], "Phantom": ["CB0062"], "Rattle": ["CB0499"], "Roundup": ["CB0553"],
      "Usnea": ["CB0008"], "Zorro": ["CB0192"]}

rows, flips = {}, []
hdr = ("论文", "R=6 未归一", "R=6 归一化", f"R=12 未归一(n={len(R12)})")
print(f"判据 ≤ {CALL}；50 Hz 糖 → MN9\n")
print(f"{'类型':10s}{'实验':7s}" + "".join(f"{h:>16s}" for h in hdr) + "   判定是否口径依赖")
for t, v in S["types"].items():
    req = v["experiment_required"]
    r12 = next((R12[c] for c in CT.get(t, []) if c in R12), None)
    vals = {"paper": v["paper_single_ratio_50Hz"],
            "R6_raw": v["50Hz"]["single"]["ratio"],
            "R6_norm": NORM[t]["50Hz"]["single"],
            "R12_raw": r12}
    ours = [vals[k] for k in ("R6_raw", "R6_norm", "R12_raw") if vals[k] is not None]
    dep = len({x <= CALL for x in ours}) > 1
    if dep:
        flips.append(t)
    rows[t] = dict(experiment_required=req, **vals,
                   calls={k: (None if x is None else bool(x <= CALL)) for k, x in vals.items()},
                   estimator_dependent=dep)
    f = lambda x: "      —" if x is None else f"{x:.3f}{'必需' if x <= CALL else '不必需'}"
    print(f"{t:10s}{'必需' if req else '不必需':7s}"
          + "".join(f"{f(vals[k]):>16s}" for k in ("paper", "R6_raw", "R6_norm", "R12_raw"))
          + ("   ← 是" if dep else ""))

print(f"\n判定随口径翻转的类型：{flips or '无'}")
for t in flips:
    r = rows[t]
    print(f"  {t}：实验判{'必需' if r['experiment_required'] else '不必需'}；"
          f"R=6 未归一 {r['R6_raw']:.3f} / R=6 归一化 {r['R6_norm']:.3f}"
          + (f" / R=12 未归一 {r['R12_raw']:.3f}" if r["R12_raw"] is not None else ""))

# 各口径下答对几项
score = {}
for k in ("paper", "R6_raw", "R6_norm", "R12_raw"):
    ok = [t for t, r in rows.items() if r[k] is not None and (r[k] <= CALL) == r["experiment_required"]]
    n = sum(1 for r in rows.values() if r[k] is not None)
    score[k] = {"correct": len(ok), "of": n, "correct_types": sorted(ok)}
    print(f"\n{k:9s} 对 {len(ok)}/{n}：{'、'.join(sorted(ok))}")

out = {"说明": "同一批仿真、同一个判据，四种口径并排；判定口径依赖的类型不能单说'我们判它必需/不必需'",
       "判据": CALL, "数据来源": {"论文与R=6": "results/screen/summary.json",
                                  "R=12未归一": "results/screen/hub_scan_summary.json（stage B 只覆盖 |1−比值|≥0.05 的）"},
       "types": rows, "estimator_dependent": flips, "score_by_protocol": score}
(ROOT / "results/screen/recheck_calls.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print("\n→ results/screen/recheck_calls.json")
