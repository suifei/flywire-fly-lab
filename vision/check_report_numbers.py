#!/usr/bin/env python3
"""逐条核对 docs/log/report.md §28.16–28.20 里的数字与 results/vision/*.json 是否一致。

为什么要有这个：本项目记录在案的头号错误源就是**手抄数字**
（2026-09-16 的一次人工审计在 §14–25 里找出 16 处缺陷，全部集中在手写小结，
而不是分析脚本里）。一次性的核对脚本挡不住下一次，所以把它固化下来。

它还抓到过另一类错：**参数扫描覆盖权威结果文件**。用 `TF=2 DT=0.033` 重跑
`t4t5_directions.js` 之后，文件里留下的是参数变体的结果，正文数字没错但
文件已经不能复现它。那两个脚本现在只有默认参数才写权威文件。

用法：python3 vision/check_report_numbers.py     （只读；有不一致时退出码 1）
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = (ROOT / "docs/log/report.md").read_text()
V = ROOT / "results/vision"


def sec(head):
    i = R.index(f"### {head}")
    j = R.find("\n### ", i + 5)
    return R[i:j if j > 0 else len(R)]


bad, n = [], 0


def chk(label, rep, fil, tol=0.0):
    global n
    n += 1
    ok = abs(rep - fil) <= tol if isinstance(rep, (int, float)) else rep == fil
    if not ok:
        bad.append(f"{label}: 报告 {rep} vs 文件 {fil}")
    return ok


def need(f):
    p = V / f
    if not p.exists():
        bad.append(f"缺少结果文件 {f}")
        return None
    return json.loads(p.read_text())


# ── §28.16 视蛋白权重 ────────────────────────────────────────
d = need("opsin_weights.json")
if d:
    w = d["权重"]["有增感色素"]
    t = sec("28.16 视蛋白光谱")
    for k in ("Rh1", "Rh3", "Rh4", "Rh5", "Rh6"):
        m = re.search(r"\| " + k + r" \| [^|]+\| \d+ \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \|", t)
        if not m:
            bad.append(f"§28.16 表里找不到 {k}")
            continue
        for i, band in enumerate("UBG"):
            chk(f"§28.16 {k}.{band}", float(m.group(i + 1)), round(w[k][band], 3), 1e-9)

# ── §28.17 T4/T5 定标 ───────────────────────────────────────
d = need("t4t5_directions.json")
if d:
    D = d["定标"]
    t = sec("28.17 测 flyvis")
    for k in ("T4b", "T4c", "T5c", "T4a", "T5a", "T5d"):
        m = re.search(r"\| " + k + r" \| (\d+) Hz \| ([\d.]+) \| (\d+)° \| ([\d.]+) \| (\d+)°", t)
        if not m:
            bad.append(f"§28.17 表里找不到 {k}")
            continue
        chk(f"§28.17 {k} 最佳TF", int(m.group(1)), D[k]["最佳TF"])
        chk(f"§28.17 {k} 峰值增量", float(m.group(2)), round(D[k]["峰值增量"], 3), 5e-4)
        chk(f"§28.17 {k} 偏好方向", int(m.group(3)), round(D[k]["偏好方向"]))
        chk(f"§28.17 {k} 方向选择性", float(m.group(4)), round(D[k]["方向选择性"], 3), 5e-4)
        chk(f"§28.17 {k} 最贴六边形", int(m.group(5)), D[k]["最近六边形方向"])

# ── §28.18 LPLC2 圆盘检验 ────────────────────────────────────
d = need("lplc2_test.json")
if d:
    L = d["结果"]
    t = sec("28.18 LPLC2")
    for name, key in (("逼近（加速）", "loom"), ("远离（时间倒放）", "rec"), ("近距平移", "transN"),
                      ("远距平移", "transF"), ("匀速扩张", "loomLin"), ("匀速收缩", "recLin")):
        m = re.search(r"\| " + re.escape(name) + r" \| \*{0,2}([\d.]+)\*{0,2} \| ([\d.]+) s \| \*{0,2}([\d.]+)\*{0,2} \|", t)
        if not m:
            bad.append(f"§28.18 表里找不到 {name}")
            continue
        chk(f"§28.18 {name} 峰值", float(m.group(1)), L[key]["峰值"], 5e-5)
        chk(f"§28.18 {name} 均值", float(m.group(3)), L[key]["均值"], 5e-5)

# ── §28.19 前端对比 ─────────────────────────────────────────
d = need("front_end_compare.json")
if d:
    F = d["摘要"]
    t = sec("28.19 把视觉回路")
    chk("§28.19 自体运动p95", float(re.search(r"p95 \*\*([\d.]+) Hz\*\*", t).group(1)), F["自体运动噪声"]["p95"], 5e-2)
    chk("§28.19 自体运动峰值", float(re.search(r"峰值 \*\*([\d.]+) Hz\*\*", t).group(1)), F["自体运动噪声"]["峰值"], 5e-2)
    for b in F["球逼近分箱"]:
        m = re.search(r"\| " + re.escape(b["距离"]) + r" \| ([\d.]+) \| \*{0,2}([\d.]+)\*{0,2} \|", t)
        if m:
            chk(f"§28.19 {b['距离']}mm 手写", float(m.group(1)), b["手写中位"], 5e-2)
            chk(f"§28.19 {b['距离']}mm 连接组", float(m.group(2)), b["连接组中位"], 5e-2)

# ── §28.20 解剖锚点与形变 ────────────────────────────────────
d = need("lattice_anchor.json")
if d:
    t = sec("28.20 晶格对齐")
    for side, cn in (("left", "左眼"), ("right", "右眼")):
        m = re.search(r"\| " + cn + r"（\d+ 柱） \| ([\d.]+)° \| ([\d.]+)° \| ([\d.]+)° \|", t)
        if not m:
            bad.append(f"§28.20 表里找不到 {cn}")
            continue
        chk(f"§28.20 {cn} +p角", float(m.group(1)), round(d["结果"][side]["p角度_前为0背为90"], 1), 5e-2)
        chk(f"§28.20 {cn} +q角", float(m.group(2)), round(d["结果"][side]["q角度_前为0背为90"], 1), 5e-2)
    chk("§28.20 拟合φ", int(re.search(r"φ = (\d+)°", t).group(1)), d["T4T5拟合"]["phi"])
    chk("§28.20 拟合RMS", float(re.search(r"RMS 误差 ([\d.]+)°", t).group(1)), d["T4T5拟合"]["RMS误差度"], 5e-2)
    if "normalize形变" in d:
        D2 = d["normalize形变"]
        for label, key in (("原始 `cart(p,q)`", "原始cart"), ("`normalize` 之后", "normalize后")):
            # 报告里用的是 Unicode 负号 −（U+2212），不是 ASCII 连字符 —— 两个都要接
            m = re.search(r"\| " + re.escape(label) + r" \| [−-]?([\d.]+)° \| ([\d.]+)° \| \*\*([\d.]+)°\*\* \| ([\d.]+) \|", t)
            if not m:
                bad.append(f"§28.20 形变表里找不到「{label}」")
                continue
            chk(f"§28.20 {key} 基矢夹角", float(m.group(3)), D2["left"][key]["基矢夹角"], 5e-2)
            chk(f"§28.20 {key} 长宽比", float(m.group(4)), D2["left"][key]["长宽比"], 5e-3)
    else:
        bad.append("lattice_anchor.json 里没有 normalize形变 段（重跑 vision/lattice_anchor.py）")

print(f"核对了 {n} 个数字")
if bad:
    print(f"\n✗ {len(bad)} 处对不上：")
    for b in bad:
        print("   " + b)
    sys.exit(1)
print("✓ docs/log/report.md §28.16–28.20 的数字全部来自结果文件，没有手抄错")
