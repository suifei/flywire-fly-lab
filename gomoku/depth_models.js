#!/usr/bin/env node
/**
 * 「推理 N 步」模型的实战评测。每个模型 = 果蝇脑特征 × 用「深度 N 搜索的最佳着」训练出来的读出层；
 * **下棋时不做任何搜索**，只取模型落子分最大的点。
 *
 * 判据（写在训练之前，2026-09-20）：「标签越深，训练出的直觉越强」——
 *   用 8 步标签训练的模型 对 用 1 步标签训练的模型，200 局胜率 ≥ 55% 才算成立。
 *
 * 用法：node gomoku/depth_models.js      输出：results/gomoku/depth_models.json
 */
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, ".."), R = ROOT + "/results/gomoku";
const A = require("./arena.js"), F2 = require("./fly2.js"), E = require("./engine.js"), T1 = require("./teacher.js"), T2 = require("./teacher2.js");
const tr = JSON.parse(fs.readFileSync(`${R}/depth_models_train.json`, "utf8")), depths = tr.labels;
const eng = {}; for (const d of depths) { const j = JSON.parse(fs.readFileSync(`${R}/linetable_fly_intact_d${d}.json`, "utf8")); eng[d] = E.makeEngine(F2.loadTable(j).att, j.lam); }
const pl = d => (b, c) => eng[d].greedy(b, c), slim = r => ({ win: r.win, loss: r.loss, draw: r.draw, games: r.games });
const OPP = { random: [A.randomPlayer, 20], old_teacher: [(b, c) => T1.best(b, c).move, 100], teacher2_d1: [(b, c) => T2.search(b, c, 1).move, 100], teacher2_d2: [(b, c) => T2.search(b, c, 2).move, 50], teacher2_d4: [(b, c) => T2.search(b, c, 4).move, 50] };
const out = { note: "下棋时不搜索：每一步 = 模型落子分最大的点。每格 = 胜–负–和", train: tr.models, vs: {}, vs_d1_model: {} };
for (const d of depths) {
  out.vs[d] = {}; for (const [n, [o, pairs]] of Object.entries(OPP)) out.vs[d][n] = slim(A.match(pl(d), o, pairs, 15000));
  if (d !== depths[0]) out.vs_d1_model[d] = slim(A.match(pl(d), pl(depths[0]), 100, 16000));
  console.log(`推理 ${d} 步的模型：` + Object.entries(out.vs[d]).map(([k, r]) => `${k} ${r.win}-${r.loss}-${r.draw}`).join("  ") + (out.vs_d1_model[d] ? `  ｜对 1 步模型 ${out.vs_d1_model[d].win}-${out.vs_d1_model[d].loss}-${out.vs_d1_model[d].draw}` : ""));
}
const last = depths[depths.length - 1], h = out.vs_d1_model[last], wr = h.win / h.games;
out.criterion = { text: `用 ${last} 步标签训练的模型 对 用 ${depths[0]} 步标签训练的模型，200 局胜率 ≥ 55%`, win_rate: +wr.toFixed(3), passed: wr >= 0.55 };
console.log(`判据：${out.criterion.text} → ${(wr * 100).toFixed(1)}% → ${out.criterion.passed ? "成立" : "不成立"}`);
fs.writeFileSync(`${R}/depth_models.json`, JSON.stringify(out, null, 1)); console.log("→ results/gomoku/depth_models.json");
