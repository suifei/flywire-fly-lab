#!/usr/bin/env node
/**
 * 「五感 + 自己生活」的实测。子回路 v4，世界自己运转（CFG.life），果蝇身上没有任何新写的决策规则——
 * 世界只把物理量送到真实的感受器上。这里量的是：每一路新感觉**在行为上到底有没有用**。
 *
 * 判据（写在跑之前，2026-09-20）：
 *   H1 听觉有用    声音响起后 1 s 内起飞的比例：完整 ≥ 20%，且 ≥ 2 × 聋了的（AUDIO 断突触）
 *   H2 嗅觉有用    每 10 分钟吃到的糖粒数：完整 ≥ 1.3 × 闻不到的（OLFA+OLFR 断突触）。**预期不成立**——
 *                  sensor_drive_v4.json 已经量过，这两路没有落到任何运动读出上；这里量的是行为层面是不是也如此
 *   H3 身体状态有用 碰到糖粒后伸喙进食的比例：饿着的（能量钉在 0.1）≥ 1.5 × 饱着的（钉在 1.0）
 *   另报告：自主生活 10 分钟的生存情况（能量 / 水分的时间均值、吃喝次数、起飞次数），以及打开 ISN 通路之后的同一组数字。
 *
 * 用法：node dodge/life_test.js [每个条件的秒数=600] [种子数=3]     输出：results/dodge/life_test.json
 */
const fs = require("fs"), path = require("path"), ROOT = path.resolve(__dirname, "..");
const { ConnectomeBrain } = require("./brain.js"), { createGame } = require("./game_core.js");
const SUB = JSON.parse(fs.readFileSync(ROOT + "/results/dodge/subcircuit_v4.json", "utf8"));
const FLIGHT = JSON.parse(fs.readFileSync(ROOT + "/results/flight/flight_clips.json", "utf8")).clips;
const T = +(process.argv[2] || 600), SEEDS = +(process.argv[3] || 3);

function run(seed, setup) {
  const g = createGame(SUB, ConnectomeBrain, { seed, mode: "manual", cfg: { encoding: "ache2019", lplc2Mu: 45, gfTau: 0.02, takeoff: "clip", wallVision: false, touch: false,   // 开放世界，没有墙（原因见 game_core 的 lifeStep）
    autoPellets: false, autoDust: false, courtW: 0, life: true, physiology: true, ...(setup.cfg || {}) } });
  if (g.setFlightClips) g.setFlightClips(FLIGHT);
  for (const l of setup.lesions || []) g.setLesion(l, true);
  const n = Math.round(T / g.chunkDt); let prevJump = false, eSum = 0, hSum = 0, sounds = 0, startled = 0, sugarContacts = 0, sugarFeeds = 0;
  const pendingSounds = []; const seenSound = new Set(), contactSeen = new Set(), fedSeen = new Set();
  for (let i = 0; i < n; i++) {
    if (setup.pin) Object.assign(g.body, setup.pin);
    g.step(); const S = g.S, t = S.t;
    for (const o of g.sounds) if (!seenSound.has(o)) { seenSound.add(o); if (S.z <= 0.01) { sounds++; pendingSounds.push({ t, hit: false }); } }
    const jumping = S.jumpT >= 0;
    if (jumping && !prevJump) for (const p of pendingSounds) if (!p.hit && t - p.t <= 1.0) { p.hit = true; startled++; }
    prevJump = jumping;
    if (g.onPellet && g.onPellet.type === "sugar") { if (!contactSeen.has(g.onPellet.id)) { contactSeen.add(g.onPellet.id); sugarContacts++; } if (S.state === "feed" && !fedSeen.has(g.onPellet.id)) { fedSeen.add(g.onPellet.id); sugarFeeds++; } }
    eSum += g.body.energy; hSum += g.body.hydration;
  }
  const sc = g.score;
  return { sounds, startled, startle_rate: sounds ? startled / sounds : null, sugar_contacts: sugarContacts, sugar_feeds: sugarFeeds, feed_rate: sugarContacts ? sugarFeeds / sugarContacts : null,
    eaten_sugar: sc.eaten_sugar || 0, eaten_water: sc.eaten_water || 0, feed_s: +sc.feed_s.toFixed(1), jumps: sc.jump, dodge: sc.dodge, hit: sc.hit,
    mean_energy: +(eSum / n).toFixed(3), mean_hydration: +(hSum / n).toFixed(3), final_energy: +g.body.energy.toFixed(3), final_hydration: +g.body.hydration.toFixed(3) };
}
const CONDS = { intact: {}, deaf: { lesions: ["AUDIO"] }, anosmic: { lesions: ["OLFA", "OLFR"] }, starved: { pin: { energy: 0.1 } }, sated: { pin: { energy: 1.0 } }, isn_on: { cfg: { isnDrive: true } } };
const agg = rows => { const o = {}; for (const k of Object.keys(rows[0])) { const v = rows.map(r => r[k]).filter(x => x !== null); o[k] = v.length ? +(v.reduce((a, x) => a + x, 0) / v.length).toFixed(3) : null; } return o; };
const out = { subcircuit: "subcircuit_v4", seconds: T, seeds: SEEDS, conds: {} }, t0 = Date.now();
for (const [name, setup] of Object.entries(CONDS)) { const rows = []; for (let s = 1; s <= SEEDS; s++) rows.push(run(s * 101, setup)); out.conds[name] = { mean: agg(rows), runs: rows };
  const m = out.conds[name].mean; console.log(`${name.padEnd(8)} 声音惊飞 ${m.startled}/${m.sounds}（${m.startle_rate === null ? "—" : (m.startle_rate * 100).toFixed(0) + "%"}）  碰到糖 ${m.sugar_contacts} 次、开吃 ${m.sugar_feeds} 次  吃完糖 ${m.eaten_sugar} 水 ${m.eaten_water}  起飞 ${m.jumps}  能量均值 ${m.mean_energy} 水分 ${m.mean_hydration}   ${((Date.now() - t0) / 1000).toFixed(0)} s`); }
const C = out.conds, per10 = v => v * 600 / T;
out.H1 = { intact: C.intact.mean.startle_rate, deaf: C.deaf.mean.startle_rate, passed: C.intact.mean.startle_rate >= 0.2 && C.intact.mean.startle_rate >= 2 * (C.deaf.mean.startle_rate || 0) };
out.H2 = { intact_per10min: +per10(C.intact.mean.eaten_sugar).toFixed(2), anosmic_per10min: +per10(C.anosmic.mean.eaten_sugar).toFixed(2), passed: C.intact.mean.eaten_sugar >= 1.3 * Math.max(C.anosmic.mean.eaten_sugar, 0.34) };
out.H3 = { starved: C.starved.mean.feed_rate, sated: C.sated.mean.feed_rate, passed: (C.starved.mean.feed_rate || 0) >= 1.5 * Math.max(C.sated.mean.feed_rate || 0, 0.05) };
console.log(`H1 听觉有用：${JSON.stringify(out.H1)}\nH2 嗅觉有用：${JSON.stringify(out.H2)}\nH3 身体状态有用：${JSON.stringify(out.H3)}`);
fs.writeFileSync(ROOT + "/results/dodge/life_test.json", JSON.stringify(out, null, 1)); console.log("→ results/dodge/life_test.json");
