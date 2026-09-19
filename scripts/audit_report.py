#!/usr/bin/env python
"""把报告正文里的数字回查结果文件——这个项目最大的错误源就是手抄数字。

2026-09-16 那次人工倒查在 §14–25 里翻出 16 处缺陷，其中 3 处是结论级的。
今天一口气写了 §37–41 五节，所以把这件事做成脚本：
每条规则 = （报告里的一段正则，结果文件里的一个取值路径，容差）。
对不上就打印出来，退出码 1。

**只能查"我写下来的数字"，查不出"我该写却没写的"**——那一类仍然只能靠人读。

用法：python scripts/audit_report.py（只读）
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = (ROOT / "docs/log/report.md").read_text()


def jget(path, *keys):
    v = json.loads((ROOT / path).read_text())
    for k in keys:
        v = v[int(k)] if isinstance(v, list) else v[k]
    return v


# (说明, 报告里的正则（第 1 组是数字）, 取值函数, 容差)
CHECKS = [
    # ── §37 补充表 10 的十行 ──────────────────────────────────────────
    ("ST4 糖+苦 组合比", r"糖\+苦 \*\*([\d.]+)\*\*（论文 0\.033）",
     lambda: jget("results/screen/taste/notebook/summary.json", "interaction", "Sugar_Bitter", "ours_ratio"), 0.001),
    ("ST4 水+Ir94e 组合比", r"水\+Ir94e \*\*([\d.]+)\*\*（0\.056）",
     lambda: jget("results/screen/taste/notebook/summary.json", "interaction", "Water_Ir94e", "ours_ratio"), 0.001),
    ("Fig3 苦压制比例", r"苦 220 Hz 压到 \*\*16\.3（降 ([\d.]+)%）\*\*",
     lambda: jget("results/screen/taste/grid/summary.json", "drop", "bitter", "drop_frac") * 100, 0.1),
    ("Fig3 Ir94e 压制比例", r"Ir94e 220 Hz 只压到 \*\*67\.3（降 ([\d.]+)%）\*\*",
     lambda: jget("results/screen/taste/grid/summary.json", "drop", "ir94e", "drop_frac") * 100, 0.1),
    ("Fig3 苦压后 MN9", r"苦 220 Hz 压到 \*\*([\d.]+)（降",
     lambda: jget("results/screen/taste/grid/summary.json", "drop", "bitter", "mn9_with_mod"), 0.05),
    ("Fig2A 我们 vs 光遗传", r"\*\*我们 (\d+)/101，论文自己在同一批 101 个上是",
     lambda: jget("results/screen/sufficiency/summary.json", "ours_vs_opto", "correct"), 0),
    ("Fig2A 论文 vs 光遗传", r"论文自己在同一批 101 个上是 (\d+)/101",
     lambda: jget("results/screen/sufficiency/summary.json", "paper_vs_opto", "correct"), 0),
    ("Fig2A 50Hz Pearson", r"\*\*Pearson ([\d.]+)（50 Hz）",
     lambda: jget("results/screen/sufficiency/summary.json", "pearson_50"), 0.0005),
    ("Fig5G aBN1 CE", r"\| aBN1 @ JO-CE 150 Hz \| \*\*([\d.]+) Hz\*\*",
     lambda: jget("results/screen/jon_ce_f/summary.json", "abn1", "ours_ce"), 0.02),
    ("Fig5G aBN1 F", r"\| aBN1 @ JO-F 150 Hz \| \*\*([\d.]+) Hz\*\*",
     lambda: jget("results/screen/jon_ce_f/summary.json", "abn1", "ours_f"), 0.02),
    ("ST1D 全脑 Pearson", r"不打乱时我们与论文的 \*\*Pearson ([\d.]+)\*\*",
     lambda: jget("results/screen/shuffle_full/summary.json", "pearson_intact_vs_paper"), 0.0005),
    # ── §39 扰动下的敲除筛选 ──────────────────────────────────────────
    ("§39 平均绝对差", r"平均绝对差 ([\d.]+)。\*\*",
     lambda: jget("results/screen/robust_knockout/summary.json", "mean_abs_diff"), 0.001),
    # ── §38 触感 / 围栏 ───────────────────────────────────────────────
    ("§38 触感 v3 格子数", r"走过的格子 \*\*9 → ([\d.]+)\*\*",
     lambda: jget("results/dodge/touch.json", "arms", "v3 · 触感→头部刚毛", "mean", "cells"), 0.05),
    ("§38 触感 v3 路程", r"路程 \*\*156 → (\d+) mm\*\*",
     lambda: jget("results/dodge/touch.json", "arms", "v3 · 触感→头部刚毛", "mean", "pathLen"), 1.0),
    ("§38 墙对照 p95", r"与\"背墙走\"（[\d.]+ / ([\d.]+)）\*\*几乎分不开\*\*",
     lambda: jget("results/dodge/wall_vision.json", "control_p95"), 0.1),
    # ── §38.4 / §41 五子棋 ────────────────────────────────────────────
    ("五子棋 v3 真实 top1", r"\| 果蝇脑 · 真实连接组 \| [\d.]+ \| ([\d.]+) \|",
     lambda: jget("results/gomoku/train_v3.json", "arms", "fly_intact", "best", "test", "top1"), 0.0005),
    ("五子棋 v3 打乱 top1", r"\| 果蝇脑 · 打乱接线 \| [\d.]+ \| ([\d.]+) \|",
     lambda: jget("results/gomoku/train_v3.json", "arms", "fly_shuffled", "best", "test", "top1"), 0.0005),
    ("五子棋 v3 打随机（真实）", r"\| 子回路 v3 \| (\d+)/40 \|",
     lambda: jget("results/gomoku/play_v3.json", "vs_random", "fly_intact"), 0),
    ("五子棋 v2 打随机（真实）", r"\| 子回路 v2 \| \*\*(\d+)/40\*\* \|",
     lambda: jget("results/gomoku/play.json", "vs_random", "fly_intact"), 0),
    # ── §43 Fotowat 2009 的角度阈值 ───────────────────────────────────
    ("§43 8mm 变异系数", r"\*\*17\.0° / 17\.2° / 17\.8°，变异系数只有 ([\d.]+)%",
     lambda: jget("results/dodge/looming_threshold.json", "by_radius", 1, "theta_cv") * 100, 0.05),
    ("§43 2.5mm 变异系数", r"\*\*变异系数 ([\d.]+)% → 判据 A 不成立\*\*",
     lambda: jget("results/dodge/looming_threshold.json", "by_radius", 0, "theta_cv") * 100, 0.05),
    ("§43 8mm 阈值均值", r"我们 ([\d.]+)°，论文 54°",
     lambda: jget("results/dodge/looming_threshold.json", "by_radius", 1, "theta_mean"), 0.05),
    # ── §42 气味效价复查 ──────────────────────────────────────────────
    ("§42 实质通过数", r"原始 4/6，扣掉空对照后实质 (\d)/6",
     lambda: jget("results/fba_odor_valence/recheck.json", "effective_passed"), 0),
    ("§42 DM1 读出 Hz", r"\*\*(16\.7) Hz vs 16\.2 Hz\*\*",
     lambda: jget("results/fba_odor_valence/recheck.json", "q1_dm1_vs_dm5", "dm1_readout_hz"), 0.05),
    # ── §42.1 自查打乱对照 ────────────────────────────────────────────
    ("§42.1 五子棋打乱活跃数", r"每个局面 (\d+) 个活跃神经元 vs 完整的",
     lambda: jget("results/shuffle_controls.json", "gomoku", "shuffled", "mean_active_per_position"), 1.0),
    # ── §41 子回路 v3 ─────────────────────────────────────────────────
    ("§41 v3 神经元数", r"\| v3 \| ([\d,]+) \| 432,437",
     lambda: jget("results/dodge/sensor_drive.json", "n"), 0),
    # ── §44 不跳也规划方向（阴性） ────────────────────────────────────
    ("§44 起飞次数", r"共 \*\*(\d+) 次起飞\*\*",
     lambda: jget("results/dodge/takeoff_planning.json", "takeoffs"), 0),
    ("§44 A 背离比例", r"\| A 起飞前 200 ms \| 98\.7% \| \*\*([\d.]+)%\*\*",
     lambda: jget("results/dodge/takeoff_planning.json", "pre_takeoff", "frac_away") * 100, 0.05),
    ("§44 B 背离比例", r"\| B 最终没起飞 \| 98\.8% \| \*\*([\d.]+)%\*\*",
     lambda: jget("results/dodge/takeoff_planning.json", "no_takeoff", "frac_away") * 100, 0.05),
    ("§44 正面 A 分箱", r"\| 0–15°（正面） \| \*\*([\d.]+)%\*\*",
     lambda: jget("results/dodge/takeoff_planning.json", "pre_bins", 0, "frac") * 100, 0.05),
    ("§44 正面 B 分箱", r"\| 0–15°（正面） \| \*\*[\d.]+%\*\* \| \*\*([\d.]+)%\*\*",
     lambda: jget("results/dodge/takeoff_planning.json", "no_bins", 0, "frac") * 100, 0.05),
    # ── §45 巨纤维对逼近的响应（阴性） ────────────────────────────────
    ("§45 looming 最低", r"looming 组 6 个条件里\*\*最低的一次是 (\d+) Hz\*\*",
     lambda: jget("results/dodge/gf_looming_check.json", "looming_min_hz"), 0),
    ("§45 其他最高", r"其他 28 个条件里\*\*最高的一次是 (\d+) Hz\*\*",
     lambda: jget("results/dodge/gf_looming_check.json", "other_max_hz"), 0),
    ("§45 严格为零的条件数", r"28 个里有 (\d+) 个是严格的 0",
     lambda: jget("results/dodge/gf_looming_check.json", "n_other_strictly_zero"), 0),
    ("§45 LOOM_L_100 左", r"\| LOOM_L_100（左侧，100 Hz） \| ([\d.]+) ±",
     lambda: jget("results/dodge/gf_looming_check.json", "looming", "LOOM_L_100", "GF_L", "mean"), 0.05),
    ("§45 只刺激 LC4", r"\| LC4_L_100（只刺激 LC4） \| ([\d.]+) ±",
     lambda: jget("results/dodge/gf_looming_check.json", "looming", "LC4_L_100", "GF_L", "mean"), 0.05),
    ("§44.1 无转向对照 A", r"\| 对照（turnGain = 0） \| \*\*([\d.]+)%\*\*",
     lambda: jget("results/dodge/takeoff_planning_noturn.json", "selection_control", "front_A") * 100, 0.05),
    ("§44.1 无转向对照 B", r"\| 对照（turnGain = 0） \| \*\*[\d.]+%\*\* \| \*\*([\d.]+)%\*\*",
     lambda: jget("results/dodge/takeoff_planning_noturn.json", "selection_control", "front_B") * 100, 0.05),
    ("§44.1 2×2 左上格", r"\| 左 DNa 更强（→ 左转） \| (\d+) \|",
     lambda: jget("results/dodge/takeoff_planning.json", "front_table", "pre", "dnaL_threatL"), 0),
    ("§44.1 P(左DNa|威胁在左)", r"威胁在左时左 DNa 更强的概率 \*\*([\d.]+)%\*\*",
     lambda: jget("results/dodge/takeoff_planning.json", "front_table", "pre", "frac_dnaL_given_threatL") * 100, 0.05),
    ("§44 正面分箱样本数", r"它偏离 50% 太远（n = ([\d,]+)）",
     lambda: jget("results/dodge/takeoff_planning.json", "pre_bins", 0, "n"), 0),
]

bad, ok = [], 0
for name, pat, get, tol in CHECKS:
    m = re.search(pat, REPORT)
    if not m:
        bad.append(f"{name}：报告里找不到这段（正则 {pat[:45]}…）")
        continue
    written = float(m.group(1).replace(",", ""))
    try:
        actual = float(get())
    except Exception as e:
        bad.append(f"{name}：结果文件里取不到（{e}）")
        continue
    if abs(written - actual) > tol:
        bad.append(f"{name}：报告写 {written}，文件里是 {actual}")
    else:
        ok += 1

print(f"回查 {len(CHECKS)} 条：对上 {ok} 条")
for b in bad:
    print("  ✗ " + b)
if bad:
    sys.exit(1)
print("✓ 报告 §37–45 的关键数字与结果文件全部一致")
