// 无画面自动对局：同一套球（相同随机种子），比较完整大脑与各种损毁/反转映射下的躲球表现。
// 用法：node dodge/autoplay.js [每局模拟秒数=120] [种子数=3]
const fs = require("fs");
const { ConnectomeBrain } = require("./brain.js");
const { createGame } = require("./game_core.js");
const SUB = JSON.parse(fs.readFileSync(__dirname + "/../results/dodge/subcircuit.json", "utf8"));
const T = +(process.argv[2] || 120), SEEDS = +(process.argv[3] || 3);

const CONDS = [
  ["intact", "完整大脑（文献映射）", g => {}],
  ["reversed", "反转转向映射", g => { g.mapSign = -1; }],
  ["no_gf", "切除巨纤维输出", g => g.setLesion("GF", true)],
  ["reversed_no_gf", "反转映射 + 切除巨纤维", g => { g.mapSign = -1; g.setLesion("GF", true); }],
  ["no_dna", "切除 DNa01/02 输出", g => g.setLesion("DNa", true)],
  ["no_gf_dna", "巨纤维 + DNa 都切除", g => { g.setLesion("GF", true); g.setLesion("DNa", true); }],
  ["no_looming", "LC4 + LPLC2 断突触", g => { g.setLesion("LC4", true); g.setLesion("LPLC2", true); }],
];

const results = [];
const t0 = Date.now();
for (const [key, label, setup] of CONDS) {
  const agg = { dodge: 0, hit: 0, jump: 0, launched: 0, turnDeg: 0 };
  for (let seed = 1; seed <= SEEDS; seed++) {
    const g = createGame(SUB, ConnectomeBrain, { seed, ballSpeed: 60 });
    setup(g);
    const n = Math.round(T / g.chunkDt);
    let turn = 0;
    for (let i = 0; i < n; i++) { g.step(); turn += Math.abs(g.S.omega) * g.chunkDt; }
    for (const k of ["dodge", "hit", "jump", "launched"]) agg[k] += g.score[k];
    agg.turnDeg += turn * 180 / Math.PI;
  }
  const decided = agg.dodge + agg.hit;
  const row = { key, label, seconds: T * SEEDS, launched: agg.launched, dodge: agg.dodge, hit: agg.hit, jump: agg.jump,
    dodge_rate: decided ? agg.dodge / decided : 0, jumps_per_min: agg.jump / (T * SEEDS / 60), turn_deg_per_s: agg.turnDeg / (T * SEEDS) };
  results.push(row);
  console.log(`${label.padEnd(16, "　")} 发球 ${String(row.launched).padStart(3)}  躲开 ${String(row.dodge).padStart(3)}  被击中 ${String(row.hit).padStart(3)}  ` +
    `躲开率 ${(row.dodge_rate * 100).toFixed(1).padStart(5)}%  起跳 ${row.jumps_per_min.toFixed(1)}/分  平均转向 ${row.turn_deg_per_s.toFixed(0)}°/s`);
}
const out = __dirname + "/../results/dodge/autoplay.json";
fs.writeFileSync(out, JSON.stringify({ seconds_per_seed: T, seeds: SEEDS, ball_speed: 60, results }, null, 1));
console.log(`\n用时 ${((Date.now() - t0) / 1000).toFixed(0)} s，写入 ${out}`);
