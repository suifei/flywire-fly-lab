#!/usr/bin/env python3
"""页面多语言：合并译文 → i18n/en.json，并按页面切出子集供构建脚本内联。

来源（后者覆盖前者）：
  i18n/en_parts/*.json   按 i18n/catalog.json 分块翻译的结果（zh → en）
  i18n/en_extra.json     之后补的：真浏览器英文模式下跑出来、目录里没有的运行时拼接句（i18n/residue.js 收集）
用法：python3 i18n/build_dict.py            → i18n/en.json（全部）、i18n/dict_<page>.json（每个页面自己的子集）、docs/i18n.js（首页用的外链版）
      python3 i18n/build_dict.py --check    校验：占位符一致、没有空译文、每个页面的目录条目都有译文；有问题退出码 1
"""
import json, re, sys
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent; I = ROOT / "i18n"
PH = re.compile(r"\{\d+\}|\{#\}")
merged = {}
for f in sorted((I / "en_parts").glob("*.json")): merged.update(json.loads(f.read_text()))
extra = I / "en_extra.json"
if extra.exists(): merged.update(json.loads(extra.read_text()))
# 页面上 markdown 的 **加粗** / `代码` 会渲染成 <b> / <code>，文字节点从那里断开——把这类条目按标记同步切开，中英逐段对应（段数相同才用），另存为片段
derived = {}; derived_from = {}
for zh, en in list(merged.items()):
    for mark in ("**", "`"):
        if mark not in zh or not isinstance(en, str) or zh.startswith("html:"): continue
        a, b = zh.split(mark), en.split(mark)
        if len(a) != len(b): continue
        for x, y in zip(a, b):
            x, y = x.strip(), y.strip()
            if x and y and re.search(r"[\u4e00-\u9fff]", x) and x not in merged and not re.search(r"[\u4e00-\u9fff]", y): derived.setdefault(x, y); derived_from.setdefault(x, zh)
# 同理按中文标点同步切（运行时会在「，；——」处拆句）：只对 80 字以内的条目，中英两边切出的段数一样才配对
ZS, ES = re.compile(r"，|；|——"), re.compile(r",\s|;\s|\s?—\s?")
for zh, en in list(merged.items()):
    if not isinstance(en, str) or len(zh) > 80 or not ZS.search(zh) or "{" in zh or zh.startswith("html:"): continue
    a, b = [x.strip() for x in ZS.split(zh)], [y.strip() for y in ES.split(en)]
    if len(a) != len(b): continue
    for x, y in zip(a, b):
        if x and y and re.search(r"[\u4e00-\u9fff]", x) and x not in merged and x not in derived and not re.search(r"[\u4e00-\u9fff]", y): derived[x] = y; derived_from.setdefault(x, zh)
for k, v in derived.items(): merged.setdefault(k, v)
print(f"  （从 **加粗** / `代码` 同步切出 {len(derived)} 个片段）")
cat = json.loads((I / "catalog.json").read_text())["items"]
bad = []
for zh, en in merged.items():
    if not isinstance(en, str) or (not en.strip() and zh.strip() not in {"个", "只", "颗", "次", "种", "份", "段", "条"}): bad.append(f"空译文：{zh[:40]}")   # 单独的量词在英文里本来就省掉
    elif sorted(PH.findall(zh)) != sorted(PH.findall(en)): bad.append(f"占位符不一致：{zh[:40]} → {en[:40]}")
    elif zh.startswith("html:") and (not en.startswith("html:") or sorted(re.findall(r"<[^>]+>", zh)) != sorted(re.findall(r"<[^>]+>", en))): bad.append(f"行内段落的标签对不上：{zh[:50]}")
    elif re.search(r"[\u4e00-\u9fff]", re.sub(r"<[^>]*>", "", en)) and not re.fullmatch(r".*(中文|English).*", en): bad.append(f"译文里还有中文：{zh[:30]} → {en[:50]}")   # 属性值里的中文不算（title 由运行时另外翻）
pages = sorted({p for e in cat for p in e["pages"]})
missing = {p: [e["zh"] for e in cat if p in e["pages"] and e["zh"] not in merged] for p in pages}
if "--check" in sys.argv:
    for b in bad[:30]: print("✗", b)
    for p, m in missing.items():
        if m: print(f"✗ {p}：{len(m)} 条没有译文，例如 {m[0][:50]}")
    ok = not bad and not any(missing.values()); print("✓ 词典校验通过：" if ok else "✗ 词典校验不通过：", f"{len(merged)} 条译文；", "，".join(f"{p} 缺 {len(m)}" for p, m in missing.items()))
    sys.exit(0 if ok else 1)
(I / "en.json").write_text(json.dumps(dict(sorted(merged.items())), ensure_ascii=False, indent=0))
# 每个页面的子集：目录里属于这个页面的条目 + en_extra 里标了这个页面的（en_extra 不分页面，所以全带上——它们都是运行时拼出来的短句）
catkeys = {e["zh"] for e in cat}
extra_keys = (set(json.loads(extra.read_text())) if extra.exists() else set()) | {k for k in merged if k not in catkeys and k not in derived}   # 目录里没有的（运行时拼出来、真浏览器里收到的）每个页面都带
for p in pages:
    own = {e["zh"] for e in cat if p in e["pages"]}
    keys = own | extra_keys | {k for k, src in derived_from.items() if src in own}   # 切出来的片段跟着原句归属的页面
    sub = {k: merged[k] for k in sorted(keys) if k in merged}
    (I / f"dict_{p}.json").write_text(json.dumps(sub, ensure_ascii=False, separators=(",", ":")))
    print(f"→ i18n/dict_{p}.json：{len(sub)} 条（缺 {len(missing[p])}）")
# 首页（静态文件）用外链：docs/i18n.js = 运行时 + 首页子集
rt = (I / "i18n.js").read_text(); idx = json.loads((I / "dict_index.json").read_text()) if (I / "dict_index.json").exists() else {}
(ROOT / "docs/i18n.js").write_text(rt.replace("/*__I18N_DICT__*/{}", json.dumps(idx, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")))
print(f"→ i18n/en.json：{len(merged)} 条；docs/i18n.js")
if bad: print(f"（有 {len(bad)} 条问题，python3 i18n/build_dict.py --check 看详情）")
