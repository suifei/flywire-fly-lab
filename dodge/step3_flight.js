// 第 3 步对局：起飞方式对比（原地起跳 / 直线飞离 / 真实逃逸飞行轨迹），同一批球。
// 用法：node dodge/step3_flight.js [每局秒数=120] [种子数=5]
const fs = require("fs");
const { ConnectomeBrain } = require("./brain.js");
const { createGame } = require("./game_core.js");
const SUB = JSON.parse(fs.readFileSync(__dirname + "/../results/dodge/subcircuit.json", "utf8"));
const CLIPS = JSON.parse(fs.readFileSync(__dirname + "/../results/flight/flight_clips.json", "utf8")).clips;
const T = +(process.argv[2] || 120), SEEDS = +(process.argv[3] || 5);

function play(cfg, setup = () => {}) {
  const agg = { dodge: 0, hit: 0, jump: 0, launched: 0, airborne_s: 0, clipUse: { left: 0, right: 0 } };
  for (let seed = 1; seed <= SEEDS; seed++) {
    const g = createGame(SUB, ConnectomeBrain, { seed, ballSpeed: 60, cfg });
    g.setFlightClips(CLIPS);
    setup(g);
    g.onEvent = (type) => { if (type === "jump" && g.S.clip) agg.clipUse[g.S.clip.turn]++; };
    const n = Math.round(T / g.chunkDt);
    for (let i = 0; i < n; i++) { g.step(); if (g.S.z > 0) agg.airborne_s += g.chunkDt; }
    for (const k of ["dodge", "hit", "jump", "launched"]) agg[k] += g.score[k];
  }
  const decided = agg.dodge + agg.hit;
  return { launched: agg.launched, dodge: agg.dodge, hit: agg.hit, dodge_rate: decided ? agg.dodge / decided : 0,
    jumps_per_min: agg.jump / (T * SEEDS / 60), airborne_frac: agg.airborne_s / (T * SEEDS), clip_left: agg.clipUse.left, clip_right: agg.clipUse.right };
}
const fmt = r => `躲开率 ${(r.dodge_rate * 100).toFixed(1).padStart(5)}%  起跳 ${r.jumps_per_min.toFixed(1).padStart(4)}/分  空中时间 ${(r.airborne_frac * 100).toFixed(0).padStart(2)}%` +
  (r.clip_left + r.clip_right ? `  轨迹使用 左转 ${r.clip_left} / 右转 ${r.clip_right}` : "");

const ACHE = { gfTau: 0.02, encoding: "ache2019", lplc2Mu: 45 };
const PROFILES = [
  ["legacy_hop", "旧编码 + 原地起跳", { takeoff: "hop" }],
  ["legacy_flyaway", "旧编码 + 直线飞离", { takeoff: "flyaway" }],
  ["legacy_clip", "旧编码 + 真实逃逸轨迹", { takeoff: "clip" }],
  ["ache45_hop", "新编码 μ45° + 原地起跳", { ...ACHE, takeoff: "hop" }],
  ["ache45_flyaway", "新编码 μ45° + 直线飞离", { ...ACHE, takeoff: "flyaway" }],
  ["ache45_clip", "新编码 μ45° + 真实逃逸轨迹", { ...ACHE, takeoff: "clip" }],
];
const out = { seconds_per_seed: T, seeds: SEEDS, ball_speed: 60, clips: CLIPS.map(c => ({ name: c.name, turn: c.turn, yaw_change_deg: c.yaw_change_deg, dur_ms: Math.round(c.n_frames * c.dt * 1000) })), profiles: [], lesions: [] };
const t0 = Date.now();
console.log(`== 起飞方式（每组 ${SEEDS} 局 × ${T} s）`);
for (const [key, label, cfg] of PROFILES) { const r = play(cfg); out.profiles.push({ key, label, cfg, ...r }); console.log(`${label.padEnd(16, "　")} ${fmt(r)}`); }
const MAIN = { ...ACHE, takeoff: "clip" };
const LESIONS = [
  ["intact", "完整大脑", g => {}],
  ["no_gf", "切除巨纤维输出", g => g.setLesion("GF", true)],
  ["no_lplc2", "LPLC2 断突触", g => g.setLesion("LPLC2", true)],
  ["no_lc4", "LC4 断突触", g => g.setLesion("LC4", true)],
  ["no_looming", "LC4 + LPLC2 断突触", g => { g.setLesion("LC4", true); g.setLesion("LPLC2", true); }],
];
console.log(`\n== 真实逃逸轨迹（新编码 μ45°）的损毁对照`);
for (const [key, label, setup] of LESIONS) { const r = play(MAIN, setup); out.lesions.push({ key, label, ...r }); console.log(`${label.padEnd(12, "　")} ${fmt(r)}`); }
fs.writeFileSync(__dirname + "/../results/dodge/step3_flight.json", JSON.stringify(out, null, 1));
console.log(`\n用时 ${((Date.now() - t0) / 1000).toFixed(0)} s，写入 results/dodge/step3_flight.json`);
