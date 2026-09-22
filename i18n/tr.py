"""zh → en，Python 版。查找规则与 i18n/i18n.js 完全一样（整句 → 只差数字 → 模板 → 两头的非中文剥掉 → 按中文标点拆开逐段），
给 REPRODUCTION.en.md 之类的离线渲染用。找不到的原样返回，并记进 MISSING。"""
import json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
CJK = re.compile(r"[㐀-鿿豈-﫿]"); NUM = re.compile(r"[-+]?\d+(?:[.,:]\d+)*")
DELIM = re.compile(r"(，|、|；|。|！|？|：|——|—| · |·| \| |\n|　|\s{2,})")
PUNCT = {"，": ", ", "、": ", ", "；": "; ", "。": ". ", "！": "! ", "？": "? ", "：": ": ", "——": " — ", "—": " — ", "　": "  ", "·": "·"}
EDGE = re.compile(r"^([^㐀-鿿豈-﫿（(「【]*)([\s\S]*?)([^㐀-鿿豈-﫿）)」】]*)$")
ws = lambda s: re.sub(r"\s+", " ", s).strip()
MISSING = {}
_d = json.loads((ROOT / "i18n/en.json").read_text()) if (ROOT / "i18n/en.json").exists() else {}
exact, numeric, patterns = {}, {}, []
for zh0, en in _d.items():
    zh = ws(zh0)
    if not zh or not isinstance(en, str): continue
    exact[zh] = en
    if re.search(r"\{\d+\}", zh):
        parts = re.split(r"(\{\d+\})", zh); idx = []; rx = "^"
        for p in parts:
            m = re.fullmatch(r"\{(\d+)\}", p)
            if m: idx.append(int(m.group(1))); rx += r"([\s\S]*?)"
            else: rx += re.escape(p).replace(r"\ ", r"\s*").replace(" ", r"\s*")
        lits = [p for p in parts if not re.fullmatch(r"\{\d+\}", p)]; cj = sorted([p for p in lits if CJK.search(p)], key=len, reverse=True)
        if cj: patterns.append((re.compile(rx + "$"), idx, en, cj[0].strip(), len("".join(lits))))
    elif re.search(r"\d", zh):
        if len(NUM.findall(zh)) == len(NUM.findall(en)): numeric[NUM.sub("{#}", zh)] = NUM.sub("{#}", en)
patterns.sort(key=lambda p: -p[4])
# 核心词（与 i18n.js 同一规则）
_EDGE0 = re.compile(r"^([^\u3400-\u9fff\uf900-\ufaff]*)([\s\S]*?)([^\u3400-\u9fff\uf900-\ufaff]*)$")
for zh, en in list(exact.items()):
    if re.search(r"\{\d+\}", zh): continue
    m = _EDGE0.match(zh)
    if not m or (not m.group(1) and not m.group(3)) or not m.group(2) or m.group(2) in exact: continue
    pre, suf, e = m.group(1).strip(), m.group(3).strip(), en.strip()
    if pre and pre not in ("（", "("):
        if not e.startswith(pre): continue
        e = e[len(pre):]
    if suf and suf not in ("）", ")"):
        if not e.endswith(suf): continue
        e = e[: len(e) - len(suf)]
    e = re.sub(r"^[（(]", "", e); e = re.sub(r"[）)]$", "", e).strip()
    if e: exact[m.group(2).strip()] = e
SECT = re.compile(r"(　|\n| \| | · |\s{2,})")

def _core1(s, depth):
    if s in exact: return exact[s]
    if re.search(r"\d", s):
        hit = numeric.get(NUM.sub("{#}", s))
        if hit is not None: nums = iter(NUM.findall(s)); return re.sub(r"\{#\}", lambda m: next(nums, ""), hit)
    for rx, idx, en, anchor, _ in patterns:
        if anchor not in s: continue
        m = rx.match(s)
        if not m: continue
        vals = {}; ok = True
        for j, k in enumerate(idx):
            v = m.group(j + 1); x = t(v, depth + 1) if depth < 3 and CJK.search(v) else v
            if CJK.search(x): ok = False
            vals[k] = x
        if not ok: continue
        return re.sub(r"\{(\d+)\}", lambda q: vals.get(int(q.group(1)), ""), en)
    return None

def _core(s, depth):
    r = _core1(s, depth)
    if r is not None: return r
    m = EDGE.match(s)
    if m and (m.group(1) or m.group(3)) and m.group(2) and CJK.search(m.group(2)):
        mid = _core1(m.group(2).strip(), depth)
        if mid is not None: return ws(m.group(1) + mid + m.group(3))
    return None

def t(s0, depth=0):
    if not isinstance(s0, str) or not CJK.search(s0): return s0
    s = ws(s0); out = _core(s, depth)
    if out is None and depth < 4:
        secs = SECT.split(s)
        if len(secs) > 1:
            anyhit = False; allsec = True; res = []
            for p in secs:
                if not p: continue
                if SECT.fullmatch(p) and not CJK.search(p): res.append("  " if p == "　" else p); continue
                q = p.strip()
                if not CJK.search(q): res.append(p); continue
                x = t(q, depth + 1); res.append(x)
                if CJK.search(x): allsec = False
                else: anyhit = True
            if anyhit and allsec: out = re.sub(r" {3,}", "  ", "".join(res)).strip()
    if out is None and depth < 3:
        parts = DELIM.split(s)
        if len(parts) > 1:
            anyhit = False; allhit = True; res = []
            for p in parts:
                if not p: continue
                if p in PUNCT: res.append(PUNCT[p]); continue
                if p.strip() == "" or p in (" · ", " | ", "\n"): res.append(p); continue
                q = p.strip()
                if not CJK.search(q): res.append(p); continue
                r = _core(q, depth + 1)
                if r is None or CJK.search(r):
                    r2 = t(q, depth + 1); r = r2 if not CJK.search(r2) else None
                if r is None: allhit = False; res.append(q)
                else: anyhit = True; res.append(r)
            if anyhit and allhit: out = re.sub(r" {2,}", " ", re.sub(r"\s+([,.;:!?])", r"\1", "".join(res))).strip()
    if out is None:
        MISSING[s] = MISSING.get(s, 0) + 1; return s0
    return out
