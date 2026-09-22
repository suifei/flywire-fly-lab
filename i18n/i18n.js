// 注意：本文件会被内联进 <script>，构建脚本会把「<」「/」相连的两个字符改写成转义形式——这里的正则与字符串一律避开这两个字符相连。
// 页面多语言（中文 / English）。所有页面共用这一份：游戏页与生态箱页由构建脚本内联，文档首页用 <script src>。
//   语言：?lang=zh|en > 本机记住的选择（localStorage「fly-lang」）> 浏览器语言（zh* → 中文，其余 → English）。
//   页面源码一律写中文；English 模式下，本文件把页面上会显示的文字换成英文：文字节点（含之后动态生成的）、title / placeholder / aria-label / alt、
//   canvas 上画的字、alert / confirm / prompt、document.title。词典（zh → en）由 i18n/build_dict.py 从 i18n/en.json 生成并内联在 DICT 处。
//   找译文的顺序：整句 → 只差数字（数字换成 {#} 再查，查到后按原顺序填回）→ 模板（{0}、{1}…，占位处是中文就递归翻）→ 按中文标点拆成短句逐段翻 → 找不到就保留原文。
//   不翻：<script> / <style> / <textarea> / 可编辑区域 / 带 data-no-i18n 的元素（用户输入与挑战码之类）。
(function (root) {
  "use strict";
  const DICT = /*__I18N_DICT__*/{};
  const CJK = /[\u3400-\u9fff\uf900-\ufaff]/, NUM = /[-+]?\d+(?:[.,:]\d+)*/g, KEY = "fly-lang";
  let lang = "zh";
  try {
    const q = new URLSearchParams(root.location ? root.location.search : "").get("lang"); let st = null; try { st = root.localStorage.getItem(KEY); } catch (e) {}
    const nav = (root.navigator && (root.navigator.languages && root.navigator.languages[0] || root.navigator.language)) || "zh";
    lang = q === "zh" || q === "en" ? q : st === "zh" || st === "en" ? st : (/^zh\b/i.test(nav) ? "zh" : "en");
  } catch (e) { lang = "zh"; }
  const I18N = root.I18N = { lang, t: s => s, set(l) { try { root.localStorage.setItem(KEY, l); } catch (e) {} try { const u = new URL(root.location.href); u.searchParams.delete("lang"); root.location.replace(u.toString()); } catch (e) { root.location.reload(); } }, missing: new Map(), stats: { hit: 0, miss: 0 } };
  try { if (root.document && root.document.documentElement) root.document.documentElement.lang = lang === "zh" ? "zh-CN" : "en"; } catch (e) {}

  // ── 词典索引 ──
  const exact = new Map(), numeric = new Map(), patterns = [];
  const ws = s => s.replace(/\s+/g, " ").trim();
  for (const [zh0, en] of Object.entries(DICT)) { const zh = ws(zh0); if (!zh || typeof en !== "string") continue; exact.set(zh, en);
    if (/\{\d+\}/.test(zh)) { const parts = zh.split(/(\{\d+\})/), idx = []; let re = "^";
      for (const p of parts) { const m = /^\{(\d+)\}$/.exec(p); if (m) { idx.push(+m[1]); re += "([\\s\\S]*?)"; } else re += p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/ /g, "\\s*"); }
      const lits = parts.filter(p => !/^\{\d+\}$/.test(p)); const anchor = lits.filter(p => CJK.test(p)).sort((a, b) => b.length - a.length)[0] || "";
      if (anchor) patterns.push({ re: new RegExp(re + "$"), idx, en, anchor: anchor.trim(), lit: lits.join("").length }); }
    else if (/\d/.test(zh)) { const nz = zh.match(NUM) || [], ne = en.match(NUM) || []; if (nz.length === ne.length) numeric.set(zh.replace(NUM, "{#}"), en.replace(NUM, "{#}")); } }
  patterns.sort((a, b) => b.lit - a.lit);
  // 核心词：键两头的符号（「· 失控」「（失控）」里的 · 与括号）剥掉另存一份，译文两头同样剥；这样「8,848 · 失控」剥掉数字后剩下的「失控」也查得到
  const EDGE0 = /^([^\u3400-\u9fff\uf900-\ufaff]*)([\s\S]*?)([^\u3400-\u9fff\uf900-\ufaff]*)$/;
  for (const [zh, en] of [...exact]) { if (/\{\d+\}/.test(zh)) continue; const m = EDGE0.exec(zh); if (!m || (!m[1] && !m[3]) || !m[2] || exact.has(m[2])) continue;
    const pre = m[1].trim(), suf = m[3].trim(), clean = x => x.replace(/^[（(]/, "").replace(/[）)]$/, "").trim(); let e = en.trim();
    if (pre && !/^[（(]$/.test(pre)) { if (!e.startsWith(pre)) continue; e = e.slice(pre.length); } if (suf && !/^[）)]$/.test(suf)) { if (!e.endsWith(suf)) continue; e = e.slice(0, e.length - suf.length); }
    e = clean(e); if (e) exact.set(m[2].trim(), e); }
  const cache = new Map(), SECT = /(　|\n| \| | · |\s{2,})/, DELIM = /(，|、|；|。|！|？|：|——|—| · |·| \| |\n|　|\s{2,})/, PUNCT = { "，": ", ", "、": ", ", "；": "; ", "。": ". ", "！": "! ", "？": "? ", "：": ": ", "——": " — ", "—": " — ", "　": "  ", "·": "·" };

  // 两头夹着的非中文（数字、单位、#47、DNg100、·0.61 之类）剥下来，只翻中间的中文，再原样拼回
  const EDGE = /^([^\u3400-\u9fff\uf900-\ufaff（(「【]*)([\s\S]*?)([^\u3400-\u9fff\uf900-\ufaff）)」】]*)$/;
  function core(s, depth) {
    const r0 = core1(s, depth); if (r0 != null) return r0;
    const m = EDGE.exec(s); if (m && (m[1] || m[3]) && m[2] && CJK.test(m[2])) { const mid = core1(m[2].trim(), depth); if (mid != null) return (m[1] + mid + m[3]).replace(/\s+/g, " ").trim(); }
    return null;
  }
  function core1(s, depth) {
    if (exact.has(s)) return exact.get(s);
    if (/\d/.test(s)) { const k = s.replace(NUM, "{#}"), hit = numeric.get(k); if (hit !== undefined) { const nums = s.match(NUM) || []; let i = 0; return hit.replace(/\{#\}/g, () => nums[i++] || ""); } }
    for (const p of patterns) { if (!s.includes(p.anchor)) continue; const m = p.re.exec(s); if (!m) continue;
      const vals = []; let ok = true; p.idx.forEach((k, j) => { const v = m[j + 1]; const x = depth < 3 && CJK.test(v) ? tr(v, depth + 1) : v; if (CJK.test(x)) ok = false; vals[k] = x; }); if (!ok) continue;   /* 占位处的中文翻不出来就不算匹配（否则会拼出半中半英） */
      return p.en.replace(/\{(\d+)\}/g, (_, k) => vals[+k] !== undefined ? vals[+k] : ""); }
    return null;
  }
  function tr(s0, depth) {
    depth = depth || 0; if (typeof s0 !== "string" || !CJK.test(s0)) return s0;
    const c = cache.get(s0); if (c !== undefined) return c;
    const lead = /^\s*/.exec(s0)[0], trail = /\s*$/.exec(s0)[0], s = ws(s0); let out = core(s, depth);
    if (out == null && depth < 4) { const secs = s.split(SECT); if (secs.length > 1) { let any = false;
        let all = true; const r = secs.map(p => { if (!p || SECT.test(p) && !CJK.test(p)) return p === "　" ? "  " : p; const q = p.trim(); if (!CJK.test(q)) return p; const x = tr(q, depth + 1); if (CJK.test(x)) all = false; else any = true; return x; }).join("").replace(/ {3,}/g, "  ").trim();
        if (any && all) out = r; } }   /* 每一段都翻出来才采用，不拼半中半英 */
    if (out == null && depth < 3) { const parts = s.split(DELIM); if (parts.length > 1) { let any = false, all = true;
        out = parts.map(p => { if (!p) return ""; if (p in PUNCT) return PUNCT[p]; if (p === " · " || p === " | " || p === "\n" || /^\s+$/.test(p)) return p; const q = p.trim(); if (!CJK.test(q)) return p; const t = core(q, depth + 1); if (t != null && !CJK.test(t)) { any = true; return t; } const r = tr(q, depth + 1); if (!CJK.test(r)) { any = true; return r; } all = false; return q; }).join("").replace(/\s+([,.;:!?])/g, "$1").replace(/ {2,}/g, " ").trim();
        if (!any || !all) out = null; } }   /* 按标点细拆时，每个中文片段都翻出来才采用；否则整句保留中文、记进待补清单 */
    if (out == null) { I18N.stats.miss++; if (I18N.missing.size < 5000) I18N.missing.set(s, (I18N.missing.get(s) || 0) + 1); out = s; } else I18N.stats.hit++;
    const r = out === s ? s0 : lead + out + trail; if (cache.size > 40000) cache.clear(); cache.set(s0, r); return r;
  }
  if (lang !== "en") { I18N.t = s => s; mountToggle(); return; }
  I18N.t = s => tr(s, 0);

  // ── 行内段落：块级元素之间一段连续的「文字 + 行内元素」（<b>、<code>、<a>…）整段翻（词典里带 html: 前缀的条目）──
  //   浏览器里它是好几个文字节点，逐个翻会粘词、乱语序；整段翻之后按标签把**原来的元素**挪到译文里的位置、只换文字——
  //   元素一个都不重建，页面代码手里拿着的元素引用（按 id 缓存的计数器之类）仍然有效。整段查不到才退回逐个文字节点（并在标签两侧补空格）。
  const INLINE = new Set("B STRONG EM I CODE A SPAN SMALL SUP SUB BR KBD U MARK S ABBR Q CITE VAR TIME".split(" ")), VOID = new Set(["BR", "IMG", "INPUT", "HR", "WBR"]);
  const hEx = new Map(), hNum = new Map(), hPat = [], hCache = new Map(); let hReady = false, depthH = 0;
  const escT = x => x.replace(/&/g, "&amp;").replace(/[<]/g, "&lt;").replace(/>/g, "&gt;"), escA = x => x.replace(/&/g, "&amp;").replace(/"/g, "&quot;");
  function hSer(nodes) { let o = ""; for (const n of nodes) { if (n.nodeType === 3) o += escT(n.nodeValue); else if (n.nodeType === 1) { const tg = n.tagName.toLowerCase(); o += "<" + tg; for (const a of n.attributes) o += " " + a.name + '="' + escA(a.value) + '"'; o += ">"; if (!VOID.has(n.tagName)) o += hSer(n.childNodes) + "<" + "/" + tg + ">"; } } return o; }
  const hCanon = h => { const t = root.document.createElement("template"); t.innerHTML = h; return ws(hSer(t.content.childNodes)); };
  function hBuild() { hReady = true; for (const [k, v] of Object.entries(DICT)) { if (!k.startsWith("html:") || typeof v !== "string") continue;
      let zh = hCanon(k.slice(5)), en = hCanon(v.replace(/^html:/, "")); let q = 100;
      // 空的行内元素（运行时由代码填内容，例如一个 id 为 lnN 的空 span）：内容当作占位 {100+k}
      zh = zh.replace(/<(\w+)((?: [^>]*)?)>[<]\/\1>/g, (m, tg, at) => { const ph = "{" + (q++) + "}", open = "<" + tg + at + ">"; en = en.replace(open + "<" + "/" + tg + ">", open + ph + "<" + "/" + tg + ">"); return open + ph + "<" + "/" + tg + ">"; });
      if (/\{\d+\}/.test(zh)) { const parts = zh.split(/(\{\d+\})/), idx = []; let re = "^"; for (const p of parts) { const m = /^\{(\d+)\}$/.exec(p); if (m) { idx.push(+m[1]); re += "([\\s\\S]*?)"; } else re += p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/ /g, "\\s*"); }
        const lit = parts.filter(p => !/^\{\d+\}$/.test(p)).join(""), anc = (lit.match(/[\u3400-\u9fff]+/g) || []).sort((a, b) => b.length - a.length)[0]; if (anc) hPat.push({ re: new RegExp(re + "$"), idx, en, anc, lit: lit.length }); }
      else { hEx.set(zh, en); if (/\d/.test(zh)) { const nz = zh.match(NUM) || [], ne = en.match(NUM) || []; if (nz.length === ne.length) hNum.set(zh.replace(NUM, "{#}"), en.replace(NUM, "{#}")); } } }
    hPat.sort((a, b) => b.lit - a.lit); }
  function hLookup(key) { if (hCache.has(key)) return hCache.get(key); let r = hEx.get(key);
    if (r === undefined && /\d/.test(key)) { const h = hNum.get(key.replace(NUM, "{#}")); if (h !== undefined) { const nums = key.match(NUM) || []; let i = 0; r = h.replace(/\{#\}/g, () => nums[i++] || ""); } }
    if (r === undefined) for (const p of hPat) { if (!key.includes(p.anc)) continue; const m = p.re.exec(key); if (!m) continue; const vals = {}; let ok = true;
      p.idx.forEach((k, j) => { const v = m[j + 1]; let x = v;
        if (CJK.test(v)) { if (/[<>]/.test(v)) { const h = depthH < 3 ? (depthH++, hLookup(ws(v)), depthH--, hCache.get(ws(v))) : null; if (h != null) x = h; }   /* 占位里装的是带标签的中文：按整段再查一次 */
          else if (k < 100) { x = tr(v, 1); if (CJK.test(x)) ok = false; } }
        vals[k] = x; }); if (!ok) continue;
      r = p.en.replace(/\{(\d+)\}/g, (_, k) => vals[+k] !== undefined ? vals[+k] : ""); break; }
    if (r === undefined) r = null; if (hCache.size > 5000) hCache.clear(); hCache.set(key, r); return r; }
  const sig = el => el.tagName + "|" + [...el.attributes].map(a => a.name + "=" + a.value).join("&");
  function hApply(parent, nodes, html) { const t = root.document.createElement("template"); t.innerHTML = html; const pool = nodes.filter(n => n.nodeType === 1), anchor = nodes[nodes.length - 1].nextSibling, frag = root.document.createDocumentFragment();
    const take = tn => { const sg = sig(tn), i = pool.findIndex(o => sig(o) === sg); return i < 0 ? null : pool.splice(i, 1)[0]; };
    for (const tn of [...t.content.childNodes]) { if (tn.nodeType === 3) { const x = root.document.createTextNode(tn.nodeValue); if (!CJK.test(x.nodeValue)) done.set(x, x.nodeValue); frag.appendChild(x); }   /* 还含中文的不标记，留给逐段翻译兜底 */
      else if (tn.nodeType === 1) { const o = take(tn); if (o) { fillEl(o, tn); frag.appendChild(o); } else frag.appendChild(tn); } }
    for (const o of pool) frag.appendChild(o);                      // 译文里没出现的原元素也留着（引用不能丢）
    for (const n of nodes) if (n.nodeType === 3 && n.parentNode === parent) parent.removeChild(n);
    parent.insertBefore(frag, anchor && anchor.parentNode === parent ? anchor : null); }
  function fillEl(o, tn) { const oEl = [...o.childNodes].some(n => n.nodeType === 1), tEl = [...tn.childNodes].some(n => n.nodeType === 1);
    if (!oEl && !tEl) { const txt = tn.textContent; if (o.textContent !== txt) o.textContent = txt; for (const c of o.childNodes) if (c.nodeType === 3 && !CJK.test(c.nodeValue)) done.set(c, c.nodeValue); return; }
    const kids = [...o.childNodes]; if (kids.length) hApply(o, kids, tn.innerHTML); }
  const blockInside = el => { for (const c of el.children) { if (!INLINE.has(c.tagName) || blockInside(c)) return true; } return false; };
  function runs(el) { if (!el || el.nodeType !== 1 || SKIP.has(el.tagName) || skipped(el)) return; if (!hReady) hBuild();
    let cur = []; const flush = () => { if (cur.some(n => n.nodeType === 1) && cur.some(n => CJK.test(n.textContent))) { const key = ws(hSer(cur)); const hit = hLookup(key); if (hit != null) try { hApply(el, cur, hit); } catch (e) {} } cur = []; };
    for (const n of [...el.childNodes]) { if (n.nodeType === 3 || (n.nodeType === 1 && INLINE.has(n.tagName) && !blockInside(n))) cur.push(n); else flush(); } flush(); }

  // ── 页面上的文字 ──
  const SKIP = new Set(["SCRIPT", "STYLE", "TEXTAREA", "NOSCRIPT", "CODE", "PRE"]), ATTRS = ["title", "placeholder", "aria-label", "alt"], done = new WeakMap();
  const skipped = el => { for (let e = el; e && e.nodeType === 1; e = e.parentElement) { if (SKIP.has(e.tagName) || e.isContentEditable || (e.hasAttribute && e.hasAttribute("data-no-i18n"))) return true; } return false; };
  function textNode(n) { const v = n.nodeValue; if (!v || done.get(n) === v || !CJK.test(v)) return; if (skipped(n.parentElement)) { done.set(n, v); return; } let t = tr(v, 0);
    if (t !== v) { const pv = n.previousSibling, nx = n.nextSibling, inl = x => x && x.nodeType === 1 && INLINE.has(x.tagName) && x.tagName !== "BR";   /* 逐段翻时，行内标签两侧补空格，免得英文粘在一起 */
      if (inl(pv) && /^[A-Za-z0-9(“"'‘]/.test(t)) t = " " + t; if (inl(nx) && /[A-Za-z0-9)”"'’,:;.]$/.test(t)) t = t + " "; }
    done.set(n, t); if (t !== v) n.nodeValue = t; }
  function attrs(el) { if (skipped(el)) return; for (const a of ATTRS) { const v = el.getAttribute && el.getAttribute(a); if (v && CJK.test(v)) { const t = tr(v, 0); if (t !== v) el.setAttribute(a, t); } }
    if (el.tagName === "INPUT" && /^(button|submit|reset)$/i.test(el.type) && CJK.test(el.value)) el.value = tr(el.value, 0);
    if (el.tagName === "OPTION" && el.label && CJK.test(el.label)) el.label = tr(el.label, 0); }
  function walk(node) { if (!node) return; if (node.nodeType === 3) { if (node.parentElement) runs(node.parentElement); return textNode(node); } if (node.nodeType !== 1 && node.nodeType !== 9 && node.nodeType !== 11) return; if (node.nodeType === 1) { if (SKIP.has(node.tagName)) return; attrs(node); runs(node); }
    if (node.querySelectorAll) for (const e of node.querySelectorAll("*")) runs(e);
    const it = (node.ownerDocument || node).createTreeWalker(node, 5 /* 元素 | 文字 */); let n; while ((n = it.nextNode())) { if (n.nodeType === 3) textNode(n); else if (SKIP.has(n.tagName)) continue; else attrs(n); } }
  function start() { const d = root.document; walk(d.body); if (d.title && CJK.test(d.title)) d.title = tr(d.title, 0);
    for (const m of d.querySelectorAll('meta[name="description"],meta[property^="og:"],meta[name^="twitter:"]')) { const c = m.getAttribute("content"); if (c && CJK.test(c)) m.setAttribute("content", tr(c, 0)); }
    new MutationObserver(ms => { for (const m of ms) { if (m.type === "characterData") textNode(m.target); else if (m.type === "attributes") attrs(m.target); else { if (m.addedNodes.length) runs(m.target); for (const n of m.addedNodes) walk(n); } } })
      .observe(d.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS });
    const tt = d.querySelector("title"); if (tt) new MutationObserver(() => { if (CJK.test(d.title)) d.title = tr(d.title, 0); }).observe(tt, { childList: true, characterData: true, subtree: true });
    mountToggle(); }
  I18N._debug = { runs, walk, textNode, hLookup, hSer, ws };   // 测试与排错用
  // canvas 上画的字（HUD、脑图标签、步态图、回放说明……）
  try { const P = root.CanvasRenderingContext2D && root.CanvasRenderingContext2D.prototype; if (P) for (const f of ["fillText", "strokeText", "measureText"]) { const o = P[f]; P[f] = function (s, ...a) { return o.call(this, typeof s === "string" && CJK.test(s) ? tr(s, 0) : s, ...a); }; }
    const O = root.OffscreenCanvasRenderingContext2D && root.OffscreenCanvasRenderingContext2D.prototype; if (O) for (const f of ["fillText", "strokeText", "measureText"]) { const o = O[f]; O[f] = function (s, ...a) { return o.call(this, typeof s === "string" && CJK.test(s) ? tr(s, 0) : s, ...a); }; } } catch (e) {}
  for (const f of ["alert", "confirm", "prompt"]) { const o = root[f]; if (typeof o === "function") root[f] = function (s, ...a) { return o.call(root, typeof s === "string" ? tr(s, 0) : s, ...a); }; }
  if (root.document) { if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", start); else start(); }

  // ── 语言切换 ──
  function mountToggle() { const d = root.document; if (!d || !d.body || d.getElementById("i18nToggle")) { if (d && !d.body) d.addEventListener("DOMContentLoaded", mountToggle); return; }
    const b = d.createElement("button"); b.id = "i18nToggle"; b.setAttribute("data-no-i18n", ""); b.type = "button"; b.textContent = lang === "en" ? "中文" : "English"; b.title = lang === "en" ? "切换到中文" : "Switch to English";
    b.style.cssText = "position:fixed;right:10px;bottom:10px;z-index:2147483000;font:600 12px/1 system-ui,sans-serif;padding:7px 11px;border-radius:999px;border:1px solid rgba(128,128,128,.45);background:rgba(20,22,26,.72);color:#fff;cursor:pointer;backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px)";
    b.onclick = () => I18N.set(lang === "en" ? "zh" : "en"); d.body.appendChild(b); }
})(typeof window !== "undefined" ? window : globalThis);
