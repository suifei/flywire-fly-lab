// v3 对局：进食 / 苦味 / 梳理 / 后退（子回路 v2，wmin=3 K=3，按事先规则选定）
// 用法：node dodge/step_v3.js [每局秒数=120] [种子数=3]
const fs = require("fs");
const { ConnectomeBrain } = require("./brain.js");
const { createGame } = require("./game_core.js");
const SUB = JSON.parse(fs.readFileSync(__dirname + "/../results/dodge/subcircuit_v2.json", "utf8"));
const CLIPS = JSON.parse(fs.readFileSync(__dirname + "/../results/flight/flight_clips.json", "utf8")).clips;
const T = +(process.argv[2] || 120), SEEDS = +(process.argv[3] || 3);
const ACHE = { gfTau: 0.02, encoding: "ache2019", lplc2Mu: 45 };

function play(opts, setup, collect) {
  const agg = {};
  for (let seed = 1; seed <= SEEDS; seed++) {
    const g = createGame(SUB, ConnectomeBrain, { seed, ballSpeed: 60, ...opts });
    if (!g.V3) throw new Error("子回路缺少 v3 输入输出组");
    g.setFlightClips(CLIPS);
    setup(g);
    const extra = { frontN: 0, frontHit: 0, groomLatency: [], dustT: new Map() };
    const info = new Map();
    g.onEvent = (type, b) => {
      const S = g.S;
      if (type === "launch") {
        const rx = b.x - S.x, ry = b.y - S.y;
        const bearing = Math.atan2(Math.sin(-S.h) * rx + Math.cos(-S.h) * ry, Math.cos(-S.h) * rx - Math.sin(-S.h) * ry) * 180 / Math.PI;
        info.set(b.id, bearing);
      } else if ((type === "hit" || type === "dodge") && Math.abs(info.get(b.id)) < 15) {
        extra.frontN++; if (type === "hit") extra.frontHit++;
      } else if (type === "dust") extra.dustT.set(b.id, S.t);
      else if (type === "state" && b.to === "groom" && extra.dustT.size) {
        extra.groomLatency.push(S.t - Math.min(...extra.dustT.values())); extra.dustT.clear();
      } else if (type === "groomed") extra.dustT.clear();
    };
    const n = Math.round(T / g.chunkDt);
    for (let i = 0; i < n; i++) g.step();
    for (const [k, v] of Object.entries(g.score)) agg[k] = (agg[k] || 0) + v;
    agg.frontN = (agg.frontN || 0) + extra.frontN; agg.frontHit = (agg.frontHit || 0) + extra.frontHit;
    agg.groomLatency = (agg.groomLatency || []).concat(extra.groomLatency);
  }
  const lat = agg.groomLatency.sort((a, b) => a - b);
  return { ...agg, groomLatency: undefined, groom_latency_median_s: lat.length ? lat[Math.floor(lat.length / 2)] : null,
    dodge_rate: (agg.dodge + agg.hit) ? agg.dodge / (agg.dodge + agg.hit) : null,
    front_hit_rate: agg.frontN ? agg.frontHit / agg.frontN : null };
}
const pct = (a, b) => (b ? (100 * a / b).toFixed(0) + "%" : "—");
const out = { seconds_per_seed: T, seeds: SEEDS, subcircuit: SUB.meta, feeding: [], grooming: [], backward: [] };
const t0 = Date.now();

console.log(`== 进食（无球；每 ${4} s 在前方 8 mm 放颗粒：糖 → 苦 → 混合 轮换；${SEEDS} 局 × ${T} s）`);
for (const [key, label, setup] of [
  ["intact", "完整", g => {}], ["no_sugar", "糖味神经元断突触", g => g.setLesion("SUGAR", true)],
  ["no_bitter", "苦味神经元断突触", g => g.setLesion("BITTER", true)], ["no_mn9", "切除 MN9 输出", g => g.setLesion("MN9", true)]]) {
  const r = play({ mode: "click", cfg: { ...ACHE, takeoff: "clip", autoPellets: true } }, setup);
  out.feeding.push({ key, label, ...r });
  console.log(`  ${label.padEnd(10, "　")} 吃掉/接触  糖 ${r.eaten_sugar}/${r.contacts_sugar} (${pct(r.eaten_sugar, r.contacts_sugar)})  苦 ${r.eaten_bitter}/${r.contacts_bitter} (${pct(r.eaten_bitter, r.contacts_bitter)})  混合 ${r.eaten_mixed}/${r.contacts_mixed} (${pct(r.eaten_mixed, r.contacts_mixed)})`);
}

console.log(`\n== 梳理（无球；每 5 s 随机一侧触角落灰）`);
for (const [key, label, setup] of [
  ["intact", "完整", g => {}], ["no_jo", "JO 断突触", g => g.setLesion("JO", true)], ["no_adn1", "切除 aDN1 输出", g => g.setLesion("aDN1", true)]]) {
  const r = play({ mode: "click", cfg: { ...ACHE, takeoff: "clip", autoDust: true } }, setup);
  out.grooming.push({ key, label, ...r });
  console.log(`  ${label.padEnd(10, "　")} 落灰 ${r.dust} 次 → 梳理 ${r.groom} 次 (${pct(r.groom, r.dust)})，落灰到开始梳理中位 ${r.groom_latency_median_s === null ? "—" : r.groom_latency_median_s.toFixed(2) + " s"}`);
}

console.log(`\n== 后退（自动发球 60 mm/s）`);
for (const [key, label, opts, setup] of [
  ["hop_intact", "原地起跳 · 完整", { takeoff: "hop" }, g => {}],
  ["hop_no_lc16", "原地起跳 · LC16 断突触", { takeoff: "hop" }, g => g.setLesion("LC16", true)],
  ["hop_no_mdn", "原地起跳 · 切除 MDN 输出", { takeoff: "hop" }, g => g.setLesion("MDN", true)],
  ["hop_no_gf", "原地起跳 · 切除巨纤维（只剩转向+后退）", { takeoff: "hop" }, g => g.setLesion("GF", true)],
  ["hop_no_gf_mdn", "原地起跳 · 切除巨纤维 + MDN", { takeoff: "hop" }, g => { g.setLesion("GF", true); g.setLesion("MDN", true); }],
  ["clip_intact", "真实逃逸飞行 · 完整", { takeoff: "clip" }, g => {}],
  ["clip_no_gf", "真实逃逸飞行 · 切除巨纤维", { takeoff: "clip" }, g => g.setLesion("GF", true)]]) {
  const r = play({ mode: "auto", cfg: { ...ACHE, ...opts } }, setup);
  out.backward.push({ key, label, ...r });
  console.log(`  ${label.padEnd(22, "　")} 躲开率 ${pct(r.dodge, r.dodge + r.hit)}  正前方被击中 ${pct(r.frontHit, r.frontN)}（${r.frontN} 球）  起跳 ${r.jump}  后退累计 ${r.back_s.toFixed(1)} s`);
}
fs.writeFileSync(__dirname + "/../results/dodge/step_v3.json", JSON.stringify(out, null, 1));
console.log(`\n用时 ${((Date.now() - t0) / 1000).toFixed(0)} s，写入 results/dodge/step_v3.json`);
