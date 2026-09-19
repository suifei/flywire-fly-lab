#!/usr/bin/env python
"""重数磁盘上的全脑仿真段，写出机时账本。

为什么要有这个脚本：报告 §23 的账本原来是用**报告正文里的一段临时 shell 循环**生成的，
于是它随时会过期而没人发现。2026-09-19 重数发现它**漏记 1,307 段**——
那是 §24.3 之后补跑的 JON 集中度段（`conc_*.npz`），账本写完之后才产生。
CLAUDE.md 里记着"给任何统计加一个自洽列"，这里的自洽列是 **秒/段**：
如果段数或墙钟错了，这一列就会偏离 ~2 s/段。

口径：
  · 段数按 `keys` 数组的行数统计，并**去重**（同一 key 被重跑过会出现在多个 chunk 文件里）；
  · 墙钟取每个 npz 里的 `wall` 字段之和（那是该 chunk 的实际耗时）；
  · 只统计 `results/screen/` 下的全脑 Brian2 段，不含 vision / vnc / language 的运行。

用法：python screen/compute_ledger.py   （只读，约 1 分钟）
输出 results/screen/compute_ledger.json
"""
import glob
import json
import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SRC = [
    ("糖主筛选（14 节）", ["results/screen/chunks"]),
    ("双敲除（16 节，6/12 实现 + 枢纽配对）", ["results/screen/double", "results/screen/double12", "results/screen/double_hub"]),
    ("枢纽全扫描（16.2 + 21.1 节，CB0883 与 CB0051）", ["results/screen/hub_scan", "results/screen/water/hub_scan"]),
    ("水通路（19 节）", ["results/screen/water/chunks"]),
    ("JON 全部 JO-（24 节，已作废）", ["results/screen/jon/chunks"]),
    ("JON 弱刺激（24.1 节）", ["results/screen/jon_weak/chunks"]),
    ("JON 论文名单（24.2 + 24.3 节，含集中度段）", ["results/screen/jon_paper/chunks"]),
    ("参数稳健性 · 前两条预测（35 + 38.1 节）", ["results/screen/robustness/chunks"]),
    ("参数稳健性 · 第三条预测：每种扰动重做整轮敲除（39 节）", ["results/screen/robust_knockout/chunks"]),
    ("四味交互 ST4 + Fig 3 剂量网格（37.1 + 37.2 节）",
     ["results/screen/taste/chunks", "results/screen/taste/notebook/chunks", "results/screen/taste/grid/chunks"]),
    ("Fig 2A 伸喙充分性（37.4 节）", ["results/screen/sufficiency/chunks"]),
    ("Fig 5G JO-CE / JO-F（37.5 节）", ["results/screen/jon_ce_f/chunks"]),
]


def tally(pats):
    uniq, rows, wall, files = set(), 0, 0.0, 0
    for pat in pats:
        d = ROOT / pat
        if not d.exists():
            continue
        for f in sorted(glob.glob(str(d / "**" / "*.npz"), recursive=True)):
            try:
                z = np.load(f)
            except Exception:
                continue
            if "keys" not in z.files:
                continue
            files += 1
            ks = json.loads(str(z["keys"]))
            rows += len(ks)
            for k in ks:
                uniq.add(json.dumps(k, sort_keys=True))
            if "wall" in z.files:
                try:
                    wall += float(z["wall"])
                except Exception:
                    pass
    return dict(files=files, rows=rows, segments=len(uniq), wall_h=round(wall / 3600, 3))


out, T = [], dict(files=0, rows=0, segments=0, wall_h=0.0)
print(f"{'来源':44s}{'文件':>6s}{'行数':>9s}{'去重段':>9s}{'墙钟h':>8s}{'秒/段':>8s}")
for name, pats in SRC:
    r = tally(pats)
    r["name"] = name
    r["sec_per_segment"] = round(r["wall_h"] * 3600 / max(r["segments"], 1), 2)
    out.append(r)
    for k in ("files", "rows", "segments"):
        T[k] += r[k]
    T["wall_h"] += r["wall_h"]
    print(f"{name:44s}{r['files']:6d}{r['rows']:9,d}{r['segments']:9,d}{r['wall_h']:8.2f}{r['sec_per_segment']:8.2f}")
T["wall_h"] = round(T["wall_h"], 2)
T["sec_per_segment"] = round(T["wall_h"] * 3600 / T["segments"], 2)
print(f"{'合计':44s}{T['files']:6d}{T['rows']:9,d}{T['segments']:9,d}{T['wall_h']:8.2f}{T['sec_per_segment']:8.2f}")
dup = T["rows"] - T["segments"]
print(f"\n重跑造成的重复行 {dup} 行（同一段被重算过，只计一次）")
print(f"果蝇脑内时间 = 段数 × 1 s 试次 = {T['segments'] / 3600:.2f} h")

old = None
f = ROOT / "results/screen/compute_ledger.json"
if f.exists():
    try:
        old = json.loads(f.read_text()).get("total_segments")
    except Exception:
        pass
doc = dict(说明="只统计 results/screen 下的全脑 Brian2 段；段数按 keys 行数去重；墙钟取 npz 的 wall 字段之和",
           自洽列="秒/段应当在 2 s 上下；偏离说明段数或墙钟记错了",
           rows=out, total_files=T["files"], total_rows=T["rows"], total_segments=T["segments"],
           total_wall_h=T["wall_h"], sec_per_segment=T["sec_per_segment"],
           duplicate_rows=dup, fly_brain_time_h=round(T["segments"] / 3600, 2))
if old is not None and old != T["segments"]:
    doc["上一版账本"] = dict(total_segments=old, 差=T["segments"] - old,
                             说明="上一版是报告正文里的临时 shell 循环生成的，会随时过期")
    print(f"\n⚠ 上一版账本记 {old:,} 段，本次重数 {T['segments']:,} 段，差 {T['segments'] - old:+,d}")
f.write_text(json.dumps(doc, ensure_ascii=False, indent=1))
print(f"\n→ results/screen/compute_ledger.json")
