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
    # ── §41 子回路 v3 ─────────────────────────────────────────────────
    ("§41 v3 神经元数", r"\| v3 \| ([\d,]+) \| 432,437",
     lambda: jget("results/dodge/sensor_drive.json", "n"), 0),
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
print("✓ 报告 §37–41 的关键数字与结果文件全部一致")
