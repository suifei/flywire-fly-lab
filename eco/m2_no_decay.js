#!/usr/bin/env node
// 生态箱 M2 的一个对照（探索性）：把「不用就忘」（运动策略缓慢衰减回先天值）关掉，同样 10 个个体 × 30 条命，看有多少塌进贴墙 / 躺平。
// 用法：node eco/m2_no_decay.js （~5 min）→ results/eco/m2_no_decay.json。与 m2_learning.js 的稳健性块同一批种子（20000 起），唯一差别是 HP.decay = 0。
const fs = require("fs"), path = require("path"), ROOT = path.resolve(__dirname, ".."), Sim = require("./sim.js"), Surf = require("./brain_surface.js"), Plastic = require("./plastic.js"), Cards = require("./cards.js");
const brain = Surf.create(JSON.parse(fs.readFileSync(path.join(ROOT, "results/eco/brain_surface.json"), "utf8"))), med = a => { a = a.slice().sort((x, y) => x - y); return a[a.length >> 1]; };
const ref = JSON.parse(fs.readFileSync(path.join(ROOT, "results/eco/m2_learning.json"), "utf8")), off = ref.individuals[0].arms.off.test_median_life; Plastic.HP.decay = 0; const rows = [];
for (let k = 0; k < 10; k++) { let P = null; const last = []; for (let i = 0; i < 30; i++) { const sim = Sim.create({}, { seed: 20000 + 100 * k + i, brain, learn: "on", trail: false }), a = sim.spawn(null, P); P = a.P; let n = 0; while (a.alive && n < 18000) { sim.step(); n++; } if (a.alive) a.deathT = null; if (i >= 20) last.push(Cards.lifeSummary(a, sim.world)); }
  rows.push({ base: 20000 + 100 * k, last10_median: med(last.map(L => L.life)), wall: med(last.map(L => L.wall)), rest: med(last.map(L => L.rest)) }); console.log(rows[rows.length - 1]); }
const out = { decay: 0, off_median: off, individuals: rows, n: rows.length, n_learned: rows.filter(r => r.last10_median >= 1.5 * off).length, n_wall: rows.filter(r => r.wall > Cards.T.wall).length, n_rest: rows.filter(r => r.rest > Cards.T.rest).length, note: "按训练后 10 条命的寿命中位数判（不另做冻结测试）" };
fs.writeFileSync(path.join(ROOT, "results/eco/m2_no_decay.json"), JSON.stringify(out, null, 1)); console.log(`不衰减：${out.n_learned}/${out.n} 学成，贴墙 ${out.n_wall}，躺平 ${out.n_rest}`);
