// 第 1 步实验：LC4/LPLC2 编码拆分（Ache et al. 2019）+ 背离威胁起飞（Card & Dickinson 2008）
// 所有参数组合全部报告；主设定事先声明为 ache2019 μ=45° + flyaway。
// 用法：node dodge/step1_encoding.js [每局秒数=120] [种子数=5]
const fs = require("fs");
const { ConnectomeBrain } = require("./brain.js");
const { createGame } = require("./game_core.js");
const SUB = JSON.parse(fs.readFileSync(__dirname + "/../results/dodge/subcircuit.json", "utf8"));
const T = +(process.argv[2] || 120), SEEDS = +(process.argv[3] || 5);

function play(cfg, setup = () => {}) {
  const agg = { dodge: 0, hit: 0, jump: 0, launched: 0, frontN: 0, frontHit: 0, leads: [] };
  for (let seed = 1; seed <= SEEDS; seed++) {
    const g = createGame(SUB, ConnectomeBrain, { seed, ballSpeed: 60, cfg });
    setup(g);
    const info = new Map(); const jumps = [];
    g.onEvent = (type, b) => {
      const S = g.S;
      if (type === "launch") {
        const rx = b.x - S.x, ry = b.y - S.y;
        const bearing = Math.atan2(Math.sin(-S.h) * rx + Math.cos(-S.h) * ry, Math.cos(-S.h) * rx - Math.sin(-S.h) * ry) * 180 / Math.PI;
        info.set(b.id, { bearing, tImpact: S.t + b.tHit });
      } else if (type === "jump") jumps.push(S.t);
      else if (type === "hit" || type === "dodge") {
        const r = info.get(b.id);
        if (Math.abs(r.bearing) < 15) { agg.frontN++; if (type === "hit") agg.frontHit++; }
        const js = jumps.filter(t => t > r.tImpact - 1.0 && t < r.tImpact + 0.05);
        if (js.length) agg.leads.push(r.tImpact - js[js.length - 1]);
      }
    };
    const n = Math.round(T / g.chunkDt);
    for (let i = 0; i < n; i++) g.step();
    for (const k of ["dodge", "hit", "jump", "launched"]) agg[k] += g.score[k];
  }
  const decided = agg.dodge + agg.hit;
  const L = agg.leads.sort((a, b) => a - b);
  const q = p => (L.length ? L[Math.min(L.length - 1, Math.floor(p * L.length))] : null);
  return { launched: agg.launched, dodge: agg.dodge, hit: agg.hit, dodge_rate: decided ? agg.dodge / decided : 0,
    jumps_per_min: agg.jump / (T * SEEDS / 60), front_n: agg.frontN, front_hit_rate: agg.frontN ? agg.frontHit / agg.frontN : null,
    lead_median_s: q(0.5), lead_p10_s: q(0.1), lead_p90_s: q(0.9) };
}

const fmt = r => `躲开率 ${(r.dodge_rate * 100).toFixed(1).padStart(5)}%  正前方被击中 ${r.front_hit_rate === null ? " —" : (r.front_hit_rate * 100).toFixed(0).padStart(3) + "%"}` +
  `  起跳 ${r.jumps_per_min.toFixed(1).padStart(4)}/分  起跳距撞击 中位 ${r.lead_median_s === null ? "—" : r.lead_median_s.toFixed(2)} s` +
  ` [${r.lead_p10_s === null ? "—" : r.lead_p10_s.toFixed(2)}–${r.lead_p90_s === null ? "—" : r.lead_p90_s.toFixed(2)}]`;

const V2 = { gfTau: 0.02 };
const PROFILES = [
  ["v1", "第一版：旧编码 + 原地起跳", {}],
  ["v1_flyaway", "旧编码 + 背离飞离", { takeoff: "flyaway" }],
  ["ache30_hop", "新编码 μ30° + 原地起跳", { ...V2, encoding: "ache2019", lplc2Mu: 30 }],
  ["ache45_hop", "新编码 μ45° + 原地起跳", { ...V2, encoding: "ache2019", lplc2Mu: 45 }],
  ["ache60_hop", "新编码 μ60° + 原地起跳", { ...V2, encoding: "ache2019", lplc2Mu: 60 }],
  ["ache30_fly", "新编码 μ30° + 背离飞离", { ...V2, encoding: "ache2019", lplc2Mu: 30, takeoff: "flyaway" }],
  ["ache45_fly", "新编码 μ45° + 背离飞离（主设定）", { ...V2, encoding: "ache2019", lplc2Mu: 45, takeoff: "flyaway" }],
  ["ache60_fly", "新编码 μ60° + 背离飞离", { ...V2, encoding: "ache2019", lplc2Mu: 60, takeoff: "flyaway" }],
];
const out = { seconds_per_seed: T, seeds: SEEDS, ball_speed: 60, profiles: [], lesions: [] };
const t0 = Date.now();
console.log(`== 参数组合（完整大脑，每组 ${SEEDS} 局 × ${T} s）`);
for (const [key, label, cfg] of PROFILES) {
  const r = play(cfg); out.profiles.push({ key, label, cfg, ...r });
  console.log(`${label.padEnd(20, "　")} ${fmt(r)}`);
}
const MAIN = PROFILES.find(p => p[0] === "ache45_fly")[2];
const LESIONS = [
  ["intact", "完整大脑", g => {}],
  ["no_gf", "切除巨纤维输出", g => g.setLesion("GF", true)],
  ["no_dna", "切除 DNa01/02 输出", g => g.setLesion("DNa", true)],
  ["reversed_no_gf", "反转映射 + 切除巨纤维", g => { g.mapSign = -1; g.setLesion("GF", true); }],
  ["no_lplc2", "LPLC2 断突触", g => g.setLesion("LPLC2", true)],
  ["no_lc4", "LC4 断突触", g => g.setLesion("LC4", true)],
  ["no_gf_dna", "巨纤维 + DNa 都切除", g => { g.setLesion("GF", true); g.setLesion("DNa", true); }],
];
console.log(`\n== 主设定（新编码 μ45° + 背离飞离）的损毁对照`);
for (const [key, label, setup] of LESIONS) {
  const r = play(MAIN, setup); out.lesions.push({ key, label, ...r });
  console.log(`${label.padEnd(14, "　")} ${fmt(r)}`);
}
fs.writeFileSync(__dirname + "/../results/dodge/step1_encoding.json", JSON.stringify(out, null, 1));
console.log(`\n用时 ${((Date.now() - t0) / 1000).toFixed(0)} s，写入 results/dodge/step1_encoding.json`);
