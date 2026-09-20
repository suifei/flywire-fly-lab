#!/usr/bin/env python3
"""生态箱页面构建：把 eco/ 下的模块、响应面、实测汇总内联进模板 → docs/ecobox.html（同时放一份到 results/eco/ecobox.html 供发布）。
与 dodge/build.py 同样的两条防线：模板里出现相邻模板字面量（`a``b`，会被当成标签模板调用）或模板字面量里有 markdown 的 ** 就拒绝构建。"""
import json, os, re, sys
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); E = os.path.join(ROOT, "eco")
MODULES = ["channels.js", "world.js", "physiology.js", "senses.js", "plastic.js", "brain_surface.js", "sim.js", "cards.js", "evolve.js", "save.js"]
tpl = open(os.path.join(E, "ecobox.template.html"), encoding="utf-8").read()
if re.search(r"`\s*`", tpl.replace("``", "` `")) and re.search(r"[^`]`\s*`[^`]", tpl): sys.exit("模板里有相邻的模板字面量（少了一个 +）")
for m in re.finditer(r"`[^`]*`", tpl):
    if "**" in m.group(0): sys.exit("模板字面量里有 markdown 的 **（会原样显示出来）：" + m.group(0)[:80])
js = "\n".join(open(os.path.join(E, m), encoding="utf-8").read() for m in MODULES)
assert "</script" not in js
surf = json.load(open(os.path.join(ROOT, "results/eco/brain_surface.json")))
slim = {k: surf[k] for k in ("inputs", "features", "maxhz", "layers")}; slim["heldout"] = {f: {"usable": v["usable"]} for f, v in surf["heldout"].items()}
summary = json.load(open(os.path.join(ROOT, "results/eco/summary.json")))
dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
html = tpl.replace("/*__ECO_MODULES__*/", js).replace("/*__SURF__*/null", dump(slim)).replace("/*__RESULTS__*/null", dump(summary))
assert "/*__" not in html, "还有没替换的占位符"
for out in ("docs/ecobox.html", "results/eco/ecobox.html"):
    open(os.path.join(ROOT, out), "w", encoding="utf-8").write(html)
print(f"docs/ecobox.html  {len(html.encode()) / 1024:.0f} KB")
