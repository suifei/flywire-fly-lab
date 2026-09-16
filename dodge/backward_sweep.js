// 探索性敏感性扫描（事后加的，不替代事先声明的结果）：LC16 编码斜率 × MDN 阈值 对“正面来球”的影响
// 原地起跳模式（时机敏感）；分完整 / 切除巨纤维（只剩后退与转向）；最宽松设定下加 LC16 断突触对照。全部组合都报告。
// 用法：node dodge/backward_sweep.js [每局秒数=90] [种子数=2]
const fs = require("fs");
const { ConnectomeBrain } = require("./brain.js");
const { createGame } = require("./game_core.js");
const SUB = JSON.parse(fs.readFileSync(__dirname + "/../results/dodge/subcircuit_v2.json", "utf8"));
const T = +(process.argv[2] || 90), SEEDS = +(process.argv[3] || 2);
const BASE = { gfTau: 0.02, encoding: "ache2019", lplc2Mu: 45, takeoff: "hop" };

function play(cfg, setup) {
  const agg = { dodge: 0, hit: 0, frontN: 0, frontHit: 0, back_s: 0 };
  for (let seed = 1; seed <= SEEDS; seed++) {
    const g = createGame(SUB, ConnectomeBrain, { seed, ballSpeed: 60, mode: "auto", cfg: { ...BASE, ...cfg } });
    setup(g);
    const bearing = new Map();
    g.onEvent = (type, b) => {
      const S = g.S;
      if (type === "launch") {
        const rx = b.x - S.x, ry = b.y - S.y;
        bearing.set(b.id, Math.atan2(Math.sin(-S.h) * rx + Math.cos(-S.h) * ry, Math.cos(-S.h) * rx - Math.sin(-S.h) * ry) * 180 / Math.PI);
      } else if ((type === "hit" || type === "dodge") && Math.abs(bearing.get(b.id)) < 15) { agg.frontN++; if (type === "hit") agg.frontHit++; }
    };
    const n = Math.round(T / g.chunkDt);
    for (let i = 0; i < n; i++) g.step();
    agg.dodge += g.score.dodge; agg.hit += g.score.hit; agg.back_s += g.score.back_s;
  }
  return { ...agg, dodge_rate: agg.dodge / Math.max(1, agg.dodge + agg.hit), front_hit_rate: agg.frontN ? agg.frontHit / agg.frontN : null };
}
const rows = [];
const t0 = Date.now();
for (const gf of [false, true]) {
  for (const [slope, thr] of [[0.5, 20], [2, 20], [5, 20], [5, 10]]) {
    const r = play({ lc16Slope: slope, mdnThreshold: thr }, g => { if (gf) g.setLesion("GF", true); });
    rows.push({ gf_lesion: gf, lc16Slope: slope, mdnThreshold: thr, lc16_silenced: false, ...r });
    console.log(`${gf ? "切除巨纤维" : "完整　　　"} LC16 斜率 ${slope} · MDN 阈值 ${thr} Hz：躲开率 ${(r.dodge_rate * 100).toFixed(0)}%  正前方被击中 ${r.front_hit_rate === null ? "—" : (r.front_hit_rate * 100).toFixed(0) + "%"}（${r.frontN} 球）  后退累计 ${r.back_s.toFixed(1)} s`);
  }
  const r = play({ lc16Slope: 5, mdnThreshold: 10 }, g => { g.setLesion("LC16", true); if (gf) g.setLesion("GF", true); });
  rows.push({ gf_lesion: gf, lc16Slope: 5, mdnThreshold: 10, lc16_silenced: true, ...r });
  console.log(`${gf ? "切除巨纤维" : "完整　　　"} LC16 断突触对照（斜率 5 · 阈值 10）：躲开率 ${(r.dodge_rate * 100).toFixed(0)}%  正前方被击中 ${r.front_hit_rate === null ? "—" : (r.front_hit_rate * 100).toFixed(0) + "%"}  后退累计 ${r.back_s.toFixed(1)} s`);
}
fs.writeFileSync(__dirname + "/../results/dodge/backward_sweep.json", JSON.stringify({ seconds_per_seed: T, seeds: SEEDS, exploratory: true, rows }, null, 1));
console.log(`用时 ${((Date.now() - t0) / 1000).toFixed(0)} s`);
