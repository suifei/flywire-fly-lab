#!/usr/bin/env node
/**
 * 两张线型价值表正面交锋（同一个引擎、同一个深度）。用来决定要不要换表。
 * 判据（2026-09-20 写在多视角的表训练出来之前）：新表对旧表，都想 6 步，200 局，**胜率 ≥ 55% 才换用**。
 * 用法：node gomoku/compare_tables.js <新表.json> <旧表.json> [深度=6] [对数=100] → results/gomoku/compare_<新表名>.json
 */
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, ".."), R = ROOT + "/results/gomoku";
const A = require("./arena.js"), F2 = require("./fly2.js"), E = require("./engine.js"), T2 = require("./teacher2.js");
const [fa, fb] = [process.argv[2], process.argv[3]], depth = +(process.argv[4] || 6), pairs = +(process.argv[5] || 100);
const SEED0 = +(process.argv[6] || 12000), OUTTAG = process.argv[7] || "";      // 换一批开局做独立确认：node … 6 100 22000 _confirm
const mk = f => { const j = JSON.parse(fs.readFileSync(`${R}/${f}`, "utf8")), e = E.makeEngine(F2.loadTable(j).att, j.lam); return d => (b, c) => (d <= 1 ? e.greedy(b, c) : e.think(b, c, { depth: d }).move); };
const a = mk(fa), b = mk(fb), slim = r => ({ win: r.win, loss: r.loss, draw: r.draw, games: r.games });
const main = A.match(a(depth), b(depth), pairs, SEED0), greedy = A.match(a(1), b(1), pairs, SEED0 + 1000);
const tD6 = (bd, c) => T2.search(bd, c, 6).move, vsA = A.match(a(depth), tD6, 30, SEED0 + 2000), vsB = A.match(b(depth), tD6, 30, SEED0 + 2000);
const wr = main.win / main.games;
const out = { new_table: fa, old_table: fb, depth, opening_seed: SEED0, criterion: `新表对旧表，都想 ${depth} 步，${2 * pairs} 局，胜率 ≥ 55% 才换用`, head_to_head: slim(main), win_rate: +wr.toFixed(3), adopt: wr >= 0.55,
  greedy_head_to_head: slim(greedy), vs_teacher_d6: { new: slim(vsA), old: slim(vsB) } };
fs.writeFileSync(`${R}/compare_${path.basename(fa, ".json")}${OUTTAG}.json`, JSON.stringify(out, null, 1));
console.log(`${fa} 对 ${fb}（都想 ${depth} 步）：${main.win}-${main.loss}-${main.draw}（${(wr * 100).toFixed(1)}%）→ ${out.adopt ? "换用新表" : "不换"}；直觉 ${greedy.win}-${greedy.loss}-${greedy.draw}；对老师搜 6 步：新 ${vsA.win}-${vsA.loss}，旧 ${vsB.win}-${vsB.loss}`);
