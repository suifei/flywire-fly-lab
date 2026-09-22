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
import sys
# 工作区在 exFAT 外接盘上，时间戳只有 2 秒精度。台账文件改动前后字节数常常相同，
# 于是 __pycache__ 里的 .pyc 会被判定为仍然有效，--check 就会读到**过期的台账**。
# 2026-09-19 实测踩到：改回正确值后仍然报旧值，删掉 __pycache__ 才对。
sys.dont_write_bytecode = True
import json
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
        # expr 支持三种取值：直接取标量；"len:路径" 取长度；"sumlen:路径" 取各元素长度之和
        # （后两种是为了能核对「604 个核」「2,355 个抽头」这类由结构决定、而不是存成字段的数字）
        op, _, path = expr.partition(":")
        if not path:
            op, path = "", expr
        try:
            v = json.loads((ROOT / c["result_file"]).read_text())
            for k in path.split("."):
                v = v[k] if not isinstance(v, list) else v[int(k)]
            if op == "len":
                v = len(v)
            elif op == "sumlen":
                v = sum(len(x) for x in (v.values() if isinstance(v, dict) else v))
            elif op:
                raise ValueError(f"未知取值方式 {op}")
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

# ── 错误账本的总数（这个数自己漂过两次：README 写 40 时 docs/index.html 还停在 28）──
# 前两轮 28 处是历史值（写在 §23 的错误账本里，不逐条编号）；第三轮 §36.1/§36.5 的表格行是编号的，
# 总数 = 28 + 第三轮行数。任何一处手抄的总数与它对不上就拦下。
ROUND12 = 28
_rep = (ROOT / "docs/log/report.md").read_text()
_r3 = set()
for _m in _re.finditer(r"^\|\s*(\d+)\s*\|\s*[^|]+\|[^|]+\|[^|]+\|\s*$", _rep, _re.M):
    _n = int(_m.group(1))
    if 1 <= _n <= 99 and "倒查" in _rep[max(0, _m.start() - 3000):_m.start()]:
        _r3.add(_n)
if _r3 != set(range(1, max(_r3) + 1)) if _r3 else True:
    bad.append(f"错误账本第三轮编号不连续：{sorted(_r3)}")
_total = ROUND12 + len(_r3)
for _f, _pat in [("README.zh-CN.md", r"共查出 \*\*(\d+) 处\*\*问题"), ("README.md", r"found \*\*(\d+)\*\* problems"),
                 ("docs/index.html", r"共查出 (\d+) 处问题")]:
    _t = (ROOT / _f).read_text()
    _m = _re.search(_pat, _t)
    if not _m:
        bad.append(f"{_f}：找不到错误账本总数（正则没匹配上）")
    elif int(_m.group(1)) != _total:
        bad.append(f"{_f}：写着 {_m.group(1)} 处，实际 {ROUND12} + {len(_r3)} = {_total} 处")

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

def plain(t):
    """去掉 what 里自带的 ** 强调。

    渲染 `- **{what}** — …` 时，如果 what 自己含 `**`（例如「参数稳健性（补充表 11A–F，**全脑**）」），
    markdown 的加粗就会嵌套错位，页面上直接显示出星号。2026-09-19 倒查时在 REPRODUCTION.md 里看到。
    """
    return t.replace("**", "")


# ── 渲染 Markdown（中文 REPRODUCTION.md；英文 REPRODUCTION.en.md 用同一个函数，数据文字经 i18n/en.json 翻译）────
LABEL_EN = {"reproduced": "reproduced", "partial": "partial", "negative": "negative result", "not_done": "not done", "blocked": "blocked"}
def render(en=False):
    if en:
        sys.path.insert(0, str(ROOT / "i18n")); import tr as _tr; T = _tr.t
    else:
        T = lambda x: x
    H = (lambda zh, e: e) if en else (lambda zh, e: zh)
    lab = lambda k: (LABEL[k][0], LABEL_EN[k] if en else LABEL[k][1])
    L = [H("# 复现台账", "# Reproduction ledger"), "",
         H("**这是本项目的「复现了什么」的唯一事实源。** 每次迭代先读这里；要看怎么一步步做的、中途错在哪、改过几版，去 [`docs/log/report.md`](docs/log/report.md)（过程日志，约 6.5 万字）。",
           "**This is the single source of truth for what this project reproduced.** For how it was done step by step — including the mistakes and revisions — see the lab notebook [`docs/log/report.md`](docs/log/report.md) (Chinese). [中文版](REPRODUCTION.md)"), "",
         H("本文件由 `python3 scripts/reproduction.py` 从 `scripts/reproduction_data.py` 渲染，**不要手改**。", "Rendered by `python3 scripts/reproduction.py` from `scripts/reproduction_data.py` — **do not edit by hand**. The English text is translated through `i18n/en.json`; the numbers are the same as in the Chinese ledger."),
         H("渲染时会校验每条主张引用的脚本与结果文件是否存在。", "Rendering checks that every script and result file a claim cites exists."), "",
         H("| 状态 | 条数 |", "| Status | Count |"), "|---|---|"]
    for k in LABEL:
        if n[k]: ic, nm = lab(k); L.append(f"| {ic} {nm} | {n[k]} |")
    L += ["", "---", ""]
    for p in PAPERS:
        L.append(f"## {T(p['cite'])}"); L.append("")
        if p.get("url"): L += [f"<{p['url']}>", ""]
        if p.get("note"): L += [f"> {T(p['note'])}", ""]
        L += [H("| 状态 | 主张 | 我们的结果 | 脚本 |", "| Status | Claim | Our result | Script |"), "|---|---|---|---|"]
        for c in p["claims"]:
            sc = f"`{c['script']}`" if c.get("script") else "—"
            L.append(f"| {LABEL[c['status']][0]} | {T(c['what'])} | {T(c['result'])} | {sc} |")
        L.append("")
        for c in p["claims"]:
            if c.get("caveat"): L.append(f"- **{plain(T(c['what']))}** — {T(c['caveat'])}" + ((f"（日志 {c['log']}）" if not en else f" (notebook {c['log']})") if c.get("log") else ""))
        L.append("")
    L += ["---", "", H("## 关键参数", "## Key parameters"), "",
          H("凡是**我们自己标定**或**手选**的参数都标出来了——不标就等于冒充论文值。", "Every parameter we **calibrated ourselves** or **picked by hand** is listed — leaving one out would pass it off as a published value."), "",
          H("| 参数 | 取值 | 来源 | 说明 |", "| Parameter | Value | Source | Note |"), "|---|---|---|---|"]
    for q in PARAMETERS: L.append(f"| `{T(q['name'])}` | **{T(q['value'])}** | {T(q['source'])} | {T(q['note'])} |")
    L += ["", "---", "", H("## 本项目自己的结果", "## This project's own results"), "",
          H("下面这些不是对某篇论文的复现，是这个项目自己做出来的结论——**阴性的也在里面**。", "These are not reproductions of a paper but conclusions this project reached itself — **negative results included**."), "",
          H("| 问题 | 结果 | 脚本 |", "| Question | Result | Script |"), "|---|---|---|"]
    for f_ in FINDINGS: L.append(f"| {T(f_['what'])} | {T(f_['result'])} | `{f_['script']}` |")
    L.append("")
    for f_ in FINDINGS:
        if f_.get("caveat"): L.append(f"- **{plain(T(f_['what']))}** — {T(f_['caveat'])}" + ((f"（日志 {f_['log']}）" if not en else f" (notebook {f_['log']})") if f_.get("log") else ""))
    L += ["", "---", "", H("## 还没做的（按可行性排序）", "## Not done yet (most feasible first)"), ""]
    for p, c in [(p, c) for p in PAPERS for c in p["claims"] if c["status"] in ("not_done", "blocked")]:
        L.append(f"- {LABEL[c['status']][0]} **{plain(T(c['what']))}**" + (f"（{p['cite'].split(',')[0]}）：" if not en else f" ({p['cite'].split(',')[0]}): ") + (T(c.get('caveat')) or '—'))
    L.append("")
    return L, (_tr.MISSING if en else {})

L, _ = render(False)
(ROOT / "REPRODUCTION.md").write_text("\n".join(L))
doc = dict(说明="复现台账，由 scripts/reproduction.py 渲染；页面与 REPRODUCTION.md 都从这里取数，不许手抄",
           counts=n, total_claims=tot, papers=PAPERS, parameters=PARAMETERS, findings=FINDINGS)
(ROOT / "results/reproduction.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))
print(f"\n→ REPRODUCTION.md（{len('\n'.join(L))/1024:.1f} KB）")
print("→ results/reproduction.json")
L_en, miss = render(True)
(ROOT / "REPRODUCTION.en.md").write_text("\n".join(L_en))
print(f"→ REPRODUCTION.en.md（{len(chr(10).join(L_en))/1024:.1f} KB；" + (f"{len(miss)} 段没有译文，保留了中文：先跑 node i18n/extract.js 与翻译，再 python3 i18n/build_dict.py" if miss else "每一段都有译文") + "）")
