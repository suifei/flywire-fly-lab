#!/usr/bin/env node
/**
 * 探索性（判据是看过 life_test 的初跑之后才想到的，如实标注）：声音单独驱动不了起飞
 *（听觉神经元 200 Hz → 巨纤维读出最高约 80 Hz，起飞阈值 90 Hz），但它会不会让果蝇**对逼近更敏感**？
 * 对照：同一个种子、同一颗来球，A 组不带声音，B 组在发球的同时在来球方向放一个声源。
 * 量：起飞时刻距撞击还剩多少毫秒（越大 = 起飞越早）、躲开率。来球用慢速（35 mm/s）——快球本来就早早过阈值，看不出差别。
 * 用法：node dodge/sound_priming.js [每组球数=60]   → results/dodge/sound_priming.json
 */
const fs = require("fs"), path = require("path"), ROOT = path.resolve(__dirname, "..");
const { ConnectomeBrain } = require("./brain.js"), { createGame } = require("./game_core.js");
const SUB = JSON.parse(fs.readFileSync(ROOT + "/results/dodge/subcircuit_v4.json", "utf8"));
const CLIPS = JSON.parse(fs.readFileSync(ROOT + "/results/flight/flight_clips.json", "utf8")).clips;
const N = +(process.argv[2] || 60);
function trial(seed, withSound, deaf) {
  const g = createGame(SUB, ConnectomeBrain, { seed, mode: "manual", ballSpeed: 35, cfg: { encoding: "ache2019", lplc2Mu: 45, gfTau: 0.02, takeoff: "hop", autoPellets: false, autoDust: false, touch: false, wallVision: false } });
  g.setFlightClips(CLIPS); if (deaf) g.setLesion("AUDIO", true);
  for (let i = 0; i < Math.round(0.5 / g.chunkDt); i++) g.step();
  const a = g.S.h + ((seed * 0.6180339) % 1 - 0.5) * 2.4, d = 70, bx = g.S.x + Math.cos(a) * d, by = g.S.y + Math.sin(a) * d;
  g.launch(bx, by); if (withSound) g.addSound(bx, by, 1.5, 2.2);
  const j0 = g.score.jump, d0 = g.score.dodge, h0 = g.score.hit; let tJump = null, gfMax = 0;
  for (let i = 0; i < Math.round(3 / g.chunkDt); i++) { g.step(); gfMax = Math.max(gfMax, g.readout().gf); if (tJump === null && g.score.jump > j0) tJump = g.S.t; if (g.score.dodge > d0 || g.score.hit > h0) break; }
  return { jumped: tJump !== null, tJump, tEnd: g.S.t, dodged: g.score.dodge > d0, gfMax };
}
const out = { n: N, ball_speed: 35, note: "探索性；lead = 起飞时刻到这颗球结束（躲开或击中）的毫秒数", groups: {} };
for (const [name, ws, deaf] of [["无声", false, false], ["有声", true, false], ["有声但聋（AUDIO 断突触）", true, true]]) {
  const rows = []; for (let s = 1; s <= N; s++) rows.push(trial(s * 37, ws, deaf));
  const jumped = rows.filter(r => r.jumped), lead = jumped.map(r => (r.tEnd - r.tJump) * 1000).sort((x, y) => x - y);
  out.groups[name] = { jumped: jumped.length, dodged: rows.filter(r => r.dodged).length, lead_ms_median: lead.length ? +lead[lead.length >> 1].toFixed(0) : null, gf_max_mean: +(rows.reduce((a, r) => a + r.gfMax, 0) / N).toFixed(1) };
  console.log(`${name}：起飞 ${jumped.length}/${N}，躲开 ${out.groups[name].dodged}/${N}，起飞提前量中位 ${out.groups[name].lead_ms_median} ms，巨纤维峰值均值 ${out.groups[name].gf_max_mean} Hz`);
}
fs.writeFileSync(ROOT + "/results/dodge/sound_priming.json", JSON.stringify(out, null, 1)); console.log("→ results/dodge/sound_priming.json");
