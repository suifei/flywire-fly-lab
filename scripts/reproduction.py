#!/usr/bin/env python3
"""从 scripts/reproduction_data.py 渲染复现台账。

产出：
  REPRODUCTION.md            人读的台账（仓库根目录，**每次迭代先读这个**）
  results/reproduction.json  机器读的（游戏页从它渲染，不许手抄）

同时**校验**：每条主张引用的 script 与 result_file 必须真的存在，
否则退出码 1。台账里的死链接就是台账开始腐烂的信号。

用法：python3 scripts/reproduction.py [--check]
  --check 只校验不写文件（CI 用）
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from reproduction_data import PAPERS, PARAMETERS, FINDINGS  # noqa: E402

LABEL = {"reproduced": ("✅", "已复现"), "partial": ("🟡", "部分复现"),
         "negative": ("⬛", "阴性结果"), "not_done": ("⬜", "未做"), "blocked": ("🚫", "做不了")}

ap = argparse.ArgumentParser()
ap.add_argument("--check", action="store_true")
a = ap.parse_args()

# ── 校验 ──────────────────────────────────────────────
# 台账条目允许出现的字段。写错字段名不能被静默吞掉——2026-09-19 就发生过：
# 给 FINDINGS 条目加了 verify，而当时只有 PAPERS 走 verify，--check 照样印「通过」。
OK_KEYS_CLAIM = {"id", "what", "status", "result", "caveat", "script", "result_file", "log", "verify"}
OK_KEYS_FIND = {"id", "what", "status", "result", "caveat", "script", "result_file", "log", "verify"}


def check_verify(c, who, bad):
    """台账里的关键数字必须与结果文件对得上（台账本身也是手打的，同样会脱节）。"""
    for expr, want, tol in c.get("verify", []):
        if not c.get("result_file"):
            bad.append(f"{who}：写了 verify 却没有 result_file")
            continue
        try:
            v = json.loads((ROOT / c["result_file"]).read_text())
            for k in expr.split("."):
                v = v[k] if not isinstance(v, list) else v[int(k)]
        except Exception as e:
            bad.append(f"{who}：verify 取不到 {expr}（{e}）")
            continue
        if abs(float(v) - float(want)) > tol:
            bad.append(f"{who}：台账写 {expr}={want}，文件里是 {v}")


bad = []
for p in PAPERS:
    for c in p["claims"]:
        if c["status"] not in LABEL:
            bad.append(f"{p['key']}/{c['id']}：status 非法 {c['status']}")
        for f in ("script", "result_file"):
            v = c.get(f)
            if v and not (ROOT / v).exists():
                bad.append(f"{p['key']}/{c['id']}：{f} 不存在 → {v}")
        if c["status"] in ("reproduced", "partial", "negative") and not c.get("script"):
            bad.append(f"{p['key']}/{c['id']}：声称做过却没有 script")
        check_verify(c, f"{p['key']}/{c['id']}", bad)
import re as _re
for q in PARAMETERS:
    if q.get("script") and not (ROOT / q["script"]).exists():
        bad.append(f"参数 {q['name']}：script 不存在 → {q['script']}")
    # code_check：台账写的参数值必须和代码里真实的值一致（参数漂移是另一类静默错误）
    cc = q.get("code_check")
    if cc:
        f_, pat, want = cc
        if not (ROOT / f_).exists():
            bad.append(f"参数 {q['name']}：code_check 的文件不存在 → {f_}")
            continue
        m = _re.search(pat, (ROOT / f_).read_text(), _re.S)
        if not m:
            bad.append(f"参数 {q['name']}：code_check 正则在 {f_} 里没匹配到")
        elif "/".join(m.groups()) != want:
            bad.append(f"参数 {q['name']}：台账写 {want}，{f_} 里是 {'/'.join(m.groups())}")
for f_ in FINDINGS:
    for k in ("script", "result_file"):
        v = f_.get(k)
        if v and not (ROOT / v).exists():
            bad.append(f"本项目结果 {f_['id']}：{k} 不存在 → {v}")
    for k in set(f_) - OK_KEYS_FIND:
        bad.append(f"本项目结果 {f_['id']}：无法识别的字段 {k}（写错字段名会被静默忽略）")
    check_verify(f_, f"本项目结果 {f_['id']}", bad)
for p in PAPERS:
    for c in p["claims"]:
        for k in set(c) - OK_KEYS_CLAIM:
            bad.append(f"{p['key']}/{c['id']}：无法识别的字段 {k}（写错字段名会被静默忽略）")
if bad:
    print("✗ 台账校验不通过：")
    for b in bad:
        print("   " + b)
    sys.exit(1)

n = {k: 0 for k in LABEL}
for p in PAPERS:
    for c in p["claims"]:
        n[c["status"]] += 1
tot = sum(n.values())
nv = (sum(len(c.get("verify", [])) for p_ in PAPERS for c in p_["claims"])
      + sum(len(f_.get("verify", [])) for f_ in FINDINGS))
print(f"✓ 台账校验通过：{len(PAPERS)} 篇来源、{tot} 条主张、{len(PARAMETERS)} 个关键参数、{nv} 个数字与结果文件逐一核对")
print("  " + "　".join(f"{LABEL[k][1]} {v}" for k, v in n.items() if v))
if a.check:
    sys.exit(0)

# ── 渲染 Markdown ────────────────────────────────────
L = ["# 复现台账",
     "",
     "**这是本项目的「复现了什么」的唯一事实源。** 每次迭代先读这里；要看怎么一步步做的、"
     "中途错在哪、改过几版，去 [`docs/log/report.md`](docs/log/report.md)（过程日志，约 6.5 万字）。",
     "",
     "本文件由 `python3 scripts/reproduction.py` 从 `scripts/reproduction_data.py` 渲染，**不要手改**。",
     "渲染时会校验每条主张引用的脚本与结果文件是否存在。",
     "",
     "| 状态 | 条数 |", "|---|---|"]
for k, (icon, name) in LABEL.items():
    if n[k]:
        L.append(f"| {icon} {name} | {n[k]} |")
L += ["", "---", ""]

for p in PAPERS:
    L.append(f"## {p['cite']}")
    L.append("")
    if p.get("url"):
        L.append(f"<{p['url']}>")
        L.append("")
    if p.get("note"):
        L.append(f"> {p['note']}")
        L.append("")
    L.append("| 状态 | 主张 | 我们的结果 | 脚本 |")
    L.append("|---|---|---|---|")
    for c in p["claims"]:
        icon = LABEL[c["status"]][0]
        sc = f"`{c['script']}`" if c.get("script") else "—"
        L.append(f"| {icon} | {c['what']} | {c['result']} | {sc} |")
    L.append("")
    for c in p["claims"]:
        if c.get("caveat"):
            L.append(f"- **{c['what']}** — {c['caveat']}" + (f"（日志 {c['log']}）" if c.get("log") else ""))
    L.append("")

L += ["---", "", "## 关键参数", "",
      "凡是**我们自己标定**或**手选**的参数都标出来了——不标就等于冒充论文值。", "",
      "| 参数 | 取值 | 来源 | 说明 |", "|---|---|---|---|"]
for q in PARAMETERS:
    L.append(f"| `{q['name']}` | **{q['value']}** | {q['source']} | {q['note']} |")
L += ["", "---", "", "## 本项目自己的结果", "",
      "下面这些不是对某篇论文的复现，是这个项目自己做出来的结论——**阴性的也在里面**。", "",
      "| 问题 | 结果 | 脚本 |", "|---|---|---|"]
for f_ in FINDINGS:
    L.append(f"| {f_['what']} | {f_['result']} | `{f_['script']}` |")
L.append("")
for f_ in FINDINGS:
    if f_.get("caveat"):
        L.append(f"- **{f_['what']}** — {f_['caveat']}" + (f"（日志 {f_['log']}）" if f_.get("log") else ""))

L += ["", "---", "",
      "## 还没做的（按可行性排序）", ""]
todo = [(p, c) for p in PAPERS for c in p["claims"] if c["status"] in ("not_done", "blocked")]
for p, c in todo:
    icon = LABEL[c["status"]][0]
    L.append(f"- {icon} **{c['what']}**（{p['cite'].split(',')[0]}）：{c.get('caveat') or '—'}")
L.append("")

(ROOT / "REPRODUCTION.md").write_text("\n".join(L))
doc = dict(说明="复现台账，由 scripts/reproduction.py 渲染；页面与 REPRODUCTION.md 都从这里取数，不许手抄",
           counts=n, total_claims=tot, papers=PAPERS, parameters=PARAMETERS, findings=FINDINGS)
(ROOT / "results/reproduction.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))
print(f"\n→ REPRODUCTION.md（{len('\n'.join(L))/1024:.1f} KB）")
print("→ results/reproduction.json")
