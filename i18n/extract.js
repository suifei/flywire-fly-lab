#!/usr/bin/env node
// 页面多语言：从**构建产物**里抽出所有会显示给人看的中文片段 → i18n/catalog.json（每条：中文原文、出现在哪个页面、上下文）。
//   为什么从构建产物抽：页面是源码 + 几十份结果 JSON 内联出来的，只看源码会漏掉数据里的中文（台账、标签、卡片）。
//   JS 用 acorn 真正解析（正则会被 URL 里的 // 之类坑）：字符串字面量原样收；模板字面量把 ${…} 换成 {0}、{1}… 收成「模式」；
//   含 HTML 标签的字符串按标签切开（浏览器里它们落在不同的文字节点上），并收里面 title / placeholder / aria-label / alt 属性的值。
//   HTML 部分收标签之间的文字和同样几个属性。对象的键（数据字段名）不收。
// 用法：node i18n/extract.js → i18n/catalog.json；node i18n/extract.js --missing → 列出 i18n/en.json 里还没有译文的条目（退出码 1 = 有缺）
const fs = require("fs"), path = require("path"), acorn = require("acorn"), ROOT = path.resolve(__dirname, "..");
const PAGES = { game: "results/dodge/fly_dodge.html", eco: "docs/ecobox.html", index: "docs/index.html" };
const CJK = /[㐀-鿿豈-﫿]/, ATTR = /\b(title|placeholder|aria-label|alt|content|data-tip)\s*=\s*"([^"]*)"/g;
const ENT = { "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'", "&nbsp;": " ", "&middot;": "·", "&times;": "×", "&rarr;": "→", "&larr;": "←" };
const unent = s => s.replace(/&[a-z]+;|&#\d+;/g, m => ENT[m] || (m.startsWith("&#") ? String.fromCharCode(+m.slice(2, -1)) : m));
const cat = new Map();   // zh → { pages:Set, ctx }
const TAG = /<\/?[a-zA-Z][^<>]*>/;   // 只认真正的标签：「|方位| < 15°」里的小于号不是（第一版把它当标签切碎了一段台账）
function add(zh, page, ctx) { zh = unent(zh).replace(/\s+/g, " ").trim(); if (!zh || !CJK.test(zh)) return; if (/^[{}0-9\s·,.:;%()/+\-–—×→←<>=]*$/.test(zh.replace(/[㐀-鿿]/g, ""))) { /* 纯中文或中文夹符号，照收 */ }
  let e = cat.get(zh); if (!e) cat.set(zh, e = { pages: new Set(), ctx }); e.pages.add(page); }
// 行内段落：块级标签之间一段连续的「文字 + 行内标签」。它在浏览器里是好几个文字节点，逐个翻会粘词、乱语序，
//   所以连同标签整段收一份（html: 前缀），运行时 i18n.js 先整段查它，查不到才退回逐个文字节点。
const INLINE = "b|strong|em|i|code|a|span|small|sup|sub|br|kbd|u|mark|s|abbr|q|cite|var|time", BLOCK = /<\/?(?:p|div|li|ul|ol|table|thead|tbody|tr|td|th|h[1-6]|section|article|header|footer|nav|details|summary|dl|dt|dd|figure|figcaption|blockquote|pre|form|label|button|select|option|canvas|svg|img|input|textarea|hr|main|aside)\b[^>]*>/i;
function addRuns(s, page, ctx) { if (!CJK.test(s) || !new RegExp("<(" + INLINE + ")\\b", "i").test(s)) return;
  for (const seg of s.split(new RegExp(BLOCK.source, "gi"))) { const t = seg.replace(/\s+/g, " ").trim(); if (!t || !CJK.test(t)) continue;
    if (!new RegExp("<(" + INLINE + ")\\b[^>]*>", "i").test(t)) continue; if (/<script|<style/i.test(t)) continue;
    const text = t.replace(/<[^>]*>/g, ""); if (!CJK.test(text)) continue; add("html:" + t, page, ctx + " (行内段落)"); } }
// 一段「可能含 HTML」的文字 → 按标签切开，逐段收；属性单独收
function addMarkup(s, page, ctx) { addRuns(s, page, ctx); if (!CJK.test(s)) return; for (const m of s.matchAll(ATTR)) add(m[2], page, ctx + " @" + m[1]); const parts = s.split(TAG); for (const p of parts) add(p, page, ctx); }
function walkJS(src, page, where) {
  let ast; try { ast = acorn.parse(src, { ecmaVersion: "latest", sourceType: "script", allowReturnOutsideFunction: true, allowHashBang: true }); } catch (e) { console.error(`  ${page}/${where}: 解析失败 ${e.message}`); return; }
  (function visit(node, parent, key) {
    if (!node || typeof node.type !== "string") return;
    if (node.type === "Literal" && typeof node.value === "string") { if (!(parent && parent.type === "Property" && key === "key")) addMarkup(node.value, page, where); }
    else if (node.type === "BinaryExpression" && node.operator === "+" && !(parent && parent.type === "BinaryExpression" && parent.operator === "+")) {
      // 字符串拼接链 "a" + x + "b" + `c${y}` + …：整条收成一个模式（非字面量的部分变成 {k}），因为浏览器里显示的是拼好的整句
      const ops = []; (function flat(n) { if (n.type === "BinaryExpression" && n.operator === "+") { flat(n.left); flat(n.right); } else ops.push(n); })(node);
      if (ops.some(o => (o.type === "Literal" && typeof o.value === "string" && CJK.test(o.value)) || (o.type === "TemplateLiteral" && o.quasis.some(q => CJK.test(q.value.cooked || ""))))) {
        let s = "", k = 0; for (const o of ops) { if (o.type === "Literal" && (typeof o.value === "string" || typeof o.value === "number")) s += String(o.value);
          else if (o.type === "TemplateLiteral") o.quasis.forEach((q, i) => { s += q.value.cooked == null ? q.value.raw : q.value.cooked; if (i < o.expressions.length) s += "{" + (k++) + "}"; });
          else s += "{" + (k++) + "}"; }
        if (/\{\d+\}/.test(s)) addMarkup(s, page, where + " (拼接)"); } }
    else if (node.type === "TemplateLiteral") { let s = ""; node.quasis.forEach((q, i) => { s += q.value.cooked == null ? q.value.raw : q.value.cooked; if (i < node.expressions.length) s += "{" + i + "}"; }); addMarkup(s, page, where + " (模板)"); }
    for (const k of Object.keys(node)) { if (k === "type" || k === "start" || k === "end") continue; const v = node[k]; if (Array.isArray(v)) v.forEach(c => visit(c, node, k)); else if (v && typeof v === "object" && typeof v.type === "string") visit(v, node, k); }
  })(ast, null, null);
}
function extractPage(page, file) {
  const html = fs.readFileSync(path.join(ROOT, file), "utf8"); let n = 0;
  // <script> 块逐个解析；JSON 型的（type="application/json"）按 JSON 取字符串值
  const outside = html.replace(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi, (m, attrs, body) => { n++; if (/application\/json|text\/plain/.test(attrs)) { try { (function vj(v) { if (typeof v === "string") addMarkup(v, page, "json#" + n); else if (Array.isArray(v)) v.forEach(vj); else if (v && typeof v === "object") Object.values(v).forEach(vj); })(JSON.parse(body)); } catch (e) {} } else if (body.trim()) walkJS(body, page, "script#" + n); return " "; })
    .replace(/<style\b[\s\S]*?<\/style>/gi, " ").replace(/<!--[\s\S]*?-->/g, " ");
  for (const m of outside.matchAll(ATTR)) add(m[2], page, "html @" + m[1]);
  const title = /<title>([^<]*)<\/title>/i.exec(html); if (title) add(title[1], page, "title");
  for (const p of outside.split(TAG)) add(p, page, "html");
  addRuns(outside, page, "html");
}
for (const [p, f] of Object.entries(PAGES)) { if (fs.existsSync(path.join(ROOT, f))) extractPage(p, f); else console.error("缺", f); }
const list = [...cat.entries()].map(([zh, e]) => ({ zh, pages: [...e.pages].sort(), ctx: e.ctx })).sort((a, b) => a.zh.localeCompare(b.zh, "zh"));
const outFile = path.join(ROOT, "i18n/catalog.json");
if (process.argv.includes("--missing")) {
  const en = fs.existsSync(path.join(ROOT, "i18n/en.json")) ? JSON.parse(fs.readFileSync(path.join(ROOT, "i18n/en.json"), "utf8")) : {};
  const miss = list.filter(e => !(e.zh in en)); console.log(`目录 ${list.length} 条，已译 ${list.length - miss.length}，缺 ${miss.length}`); for (const e of miss.slice(0, 40)) console.log("  ·", e.zh.slice(0, 80), " [" + e.pages.join(",") + "]");
  process.exit(miss.length ? 1 : 0);
}
fs.writeFileSync(outFile, JSON.stringify({ n: list.length, chars: list.reduce((s, e) => s + e.zh.length, 0), by_page: Object.fromEntries(Object.keys(PAGES).map(p => [p, list.filter(e => e.pages.includes(p)).length])), items: list }, null, 1));
console.log(`→ i18n/catalog.json：${list.length} 条，${list.reduce((s, e) => s + e.zh.length, 0).toLocaleString()} 字符；`, Object.keys(PAGES).map(p => p + " " + list.filter(e => e.pages.includes(p)).length).join("，"));
