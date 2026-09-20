#!/usr/bin/env node
// 它走到「B 味的热源」前会自己掉头——是热让它掉头，还是气味 B？页面引擎里分开测：正前方 60 mm 处只放热 / 只放 B / 只放 A / 热 + B，各 5 个种子，走 12 s。
// 只报告：最大转向读出（左 / 右 DNa，Hz）、朝向总变化、离源头最近到多少。输出 results/learn/uturn_cause.json
const fs = require("fs"), path = require("path"), ROOT = path.resolve(__dirname, "..");
const { ConnectomeBrain } = require("../dodge/brain.js"), { createGame } = require("../dodge/game_core.js"), Legs = require("../dodge/legs.js");
const SUB = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge/subcircuit_v5.json"), "utf8")), GAIT = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge/gait.json"), "utf8"));
const CONDS = { heat_only: g => g.addField("heat", 60, 0, 10, 1.5), odorB_only: g => g.addOdor(60, 0, "B", 12, 1, 1e9), odorA_only: g => g.addOdor(60, 0, "A", 12, 1, 1e9), heat_and_B: g => { g.addField("heat", 60, 0, 10, 1.5); g.addOdor(60, 0, "B", 12, 1, 1e9); }, nothing: g => {} };
const out = { seeds: 5, seconds: 12, conds: {} };
for (const [name, setup] of Object.entries(CONDS)) { const rows = [];
  for (let seed = 1; seed <= 5; seed++) {
    const g = createGame(SUB, ConnectomeBrain, { seed, mode: "manual", cfg: { encoding: "ache2019", lplc2Mu: 45, gfTau: 0.02, takeoff: "hop", wallVision: false, touch: false, autoPellets: false, autoDust: false, courtW: 0, life: false, physiology: true, wind: false, reinforce: false, learning: false } });
    g.attachLegs(Legs.create(GAIT)); g.S.x = 0; g.S.y = 0; g.S.h = 0; setup(g); let maxL = 0, maxR = 0, minD = 1e9, turned = 0, h0 = 0; const n = Math.round(12 / g.chunkDt);
    for (let i = 0; i < n; i++) { g.step(); const o = g.readout(); maxL = Math.max(maxL, o.dnaL); maxR = Math.max(maxR, o.dnaR); minD = Math.min(minD, Math.hypot(g.S.x - 60, g.S.y)); turned += Math.abs(g.S.h - h0); h0 = g.S.h; }
    rows.push({ seed, max_dna_left: +maxL.toFixed(1), max_dna_right: +maxR.toFixed(1), min_dist_mm: +minD.toFixed(1), total_turn_deg: +(turned * 180 / Math.PI).toFixed(0), end_x: +g.S.x.toFixed(1), passed_through: g.S.x > 75 }); }
  const mean = k => +(rows.reduce((s, r) => s + r[k], 0) / rows.length).toFixed(1);
  out.conds[name] = { rows, mean_max_dna_left: mean("max_dna_left"), mean_max_dna_right: mean("max_dna_right"), mean_min_dist_mm: mean("min_dist_mm"), mean_total_turn_deg: mean("total_turn_deg"), n_passed_through: rows.filter(r => r.passed_through).length };
  console.log(name.padEnd(12), JSON.stringify({ ...out.conds[name], rows: undefined })); }
fs.writeFileSync(path.join(ROOT, "results/learn/uturn_cause.json"), JSON.stringify(out, null, 1));
