#!/usr/bin/env node
/**
 * 游戏页的冒烟测试：**真的把代码跑一遍**，而不是只做语法检查。
 *
 * 为什么需要它：2026-09-16 线上崩过一次——三处 `a``b` 之间漏写 `+`，
 * JS 把前一个模板字符串当成了标签函数去调用，报 "… is not a function"。
 * `node --check` 全程通过，因为那种写法**语法完全合法**。
 * 教训：模板改完必须用真实数据执行一遍渲染路径。
 *
 * 这个测试不需要浏览器：用最小的 DOM 桩把页面里纯计算 / 纯字符串的部分跑出来。
 * 用法：node dodge/smoke_test.js        （退出码非 0 表示失败）
 */
const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "..");

let failed = 0;
const ok = (name, cond, detail = "") => {
  console.log((cond ? "  ✓ " : "  ✗ ") + name + (detail ? "  " + detail : ""));
  if (!cond) failed++;
};
const section = t => console.log("\n" + t);

// ── 1. 模板里那两类「语法合法、行为错误」的写法 ─────────────────
section("模板静态检查");
const tpl = fs.readFileSync(path.join(ROOT, "dodge/fly_dodge.template.html"), "utf8");
const adj = tpl.split("\n").map((l, i) => [i + 1, l]).filter(([, l]) => l.includes("``"));
ok("无相邻模板字符串（缺 + 会被当成标签模板调用）", adj.length === 0,
   adj.length ? `第 ${adj.map(([i]) => i).join("、")} 行` : "");
const md = tpl.split("\n").map((l, i) => [i + 1, l])
  .filter(([, l]) => l.includes("`") && l.includes("**") && !l.includes("<b>"));
ok("模板字符串里无 markdown ** **（textContent 会显示星号）", md.length === 0,
   md.length ? `第 ${md.map(([i]) => i).join("、")} 行` : "");

// 页面内联脚本本身必须能通过语法检查。
// 为什么单列一条：2026-09-19 新加的一段里少写了一个右括号，模板的两条静态检查
// 全过、smoke 也全过，直到三分钟的真浏览器测试才报 "missing ) after argument list"。
// 语法错误应该在一秒内暴露，不该等到浏览器。
{
  const blocks = [...tpl.matchAll(/<script(?![^>]*\bsrc=)(?![^>]*type="application\/json")[^>]*>([\s\S]*?)<\/script>/g)]
    .map(m => m[1]).filter(b => b.trim() && !b.includes("/*__"));
  const vm = require("vm");
  let bad = [];
  blocks.forEach((b, i) => { try { new vm.Script(b); } catch (e) { bad.push(`第 ${i + 1} 块：${e.message}`); } });
  ok("页面内联脚本语法正确", bad.length === 0, bad.join("；"));
}

// ── 2. 大脑引擎与游戏逻辑真的能跑 ──────────────────────────────
section("引擎运行");
// 跟着 build.py 走：页面用哪一版子回路，冒烟测试就测哪一版（2026-09-19 起是 v3）
const SUBNAME = (fs.readFileSync(path.join(ROOT, "dodge/build.py"), "utf8")
  .match(/__SUBCIRCUIT__\*\/", \(ROOT \/ "results\/dodge\/(subcircuit_v\d)\.json"/) || [, "subcircuit_v2"])[1];
const SUB = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge", SUBNAME + ".json"), "utf8"));
const { ConnectomeBrain } = require(path.join(ROOT, "dodge/brain.js"));
const { createGame } = require(path.join(ROOT, "dodge/game_core.js"));
const g = createGame(SUB, ConnectomeBrain, { seed: 7, mode: "click",
  cfg: { autoPellets: false, autoDust: false, takeoff: "clip" } });
let spikes = 0;
g.addPellet(g.S.x + Math.cos(g.S.h) * 1.3, g.S.y + Math.sin(g.S.h) * 1.3, "sugar");
for (let i = 0; i < 300; i++) {
  const p = g.pellets[0];
  if (p) { p.x = g.S.x + Math.cos(g.S.h) * 1.3; p.y = g.S.y + Math.sin(g.S.h) * 1.3; p.amount = 1; }
  g.step(0.005);
  if (i > 150) spikes += g.readout().mn9;
}
ok("子回路加载（" + SUBNAME + "）", SUB.meta.n > 0, `${SUB.meta.n} 个神经元、${SUB.meta.n_edges} 条连接`);
ok("糖刺激能驱动 MN9", spikes / 149 > 20, `MN9 ${(spikes / 149).toFixed(1)} Hz`);
ok("神经元开关可用", g.NEURONS.length > 0 && typeof g.setNeuronLesion === "function",
   `${g.NEURONS.length} 个真实神经元`);
ok("说话功能可用", typeof g.speech === "function" && !!g.speech().sentence !== undefined);
const water = g.waterIdx || [];
ok("水味觉受体已定位", water.length > 0, `${water.length} 个`);

// ── 3. 页面里那些纯字符串 / 纯计算的渲染分支 ────────────────────
section("页面渲染分支（用真实数据执行）");
const V6R = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge/v6_results.json"), "utf8"));
const grab = (from, to) => {
  const i = tpl.indexOf(from), j = tpl.indexOf(to);
  if (i < 0 || j < 0 || j <= i) throw new Error(`定位失败：${from}`);
  return tpl.slice(i, j);
};
const out = {};
const stub = `
  const $ = () => ({ set textContent(v){ __out.txt = v; }, get textContent(){ return __out.txt; } });
  const tableHTML = (id, head, rows) => { __out.head = head; __out.rows = rows; };
`;
const run = (src, label) => {
  const fn = new Function("V6R", "__out", stub + src + "\nreturn __out;");
  return fn(V6R, {});
};
try {
  const r = run(grab("const T3 = V6R.three_pathways;", "const SF = V6R.structure;"), "三通路");
  ok("三通路表能渲染", (r.rows || []).length >= 6, `${(r.rows || []).length} 行`);
  ok("三通路说明文字非空", (r.txt || "").length > 200, `${(r.txt || "").length} 字`);
  ok("说明里无未替换的模板占位", !/\$\{/.test(r.txt || ""));
  ok("说明里无残留 markdown 星号", !(r.txt || "").includes("**"));
} catch (e) {
  ok("三通路表能渲染", false, e.message);
}

// ── 4. 构建产物 ───────────────────────────────────────────────
section("构建产物");
for (const f of ["results/dodge/fly_dodge.html", "docs/game.html", "docs/index.html", "docs/article.html"]) {
  const p = path.join(ROOT, f);
  const e = fs.existsSync(p);
  ok(f, e && fs.statSync(p).size > 1000, e ? `${(fs.statSync(p).size / 1048576).toFixed(2)} MB` : "缺失");
}
if (fs.existsSync(path.join(ROOT, "results/dodge/fly_dodge.html")) && fs.existsSync(path.join(ROOT, "docs/game.html"))) {
  const a = fs.statSync(path.join(ROOT, "results/dodge/fly_dodge.html")).size;
  const b = fs.statSync(path.join(ROOT, "docs/game.html")).size;
  ok("docs/game.html 与构建产物同步", a === b, a === b ? "" : `${a} vs ${b} bytes —— 需要重新复制`);
}

console.log(failed ? `\n失败 ${failed} 项` : "\n全部通过");
process.exit(failed ? 1 : 0);
