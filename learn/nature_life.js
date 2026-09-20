#!/usr/bin/env node
// 它在大自然里过得怎么样：v5 + 六条腿，3 分钟 × 3 个种子，三个世界并排。只报告，不设判据。
//   nature  有地形、石头、浆果丛、水洼、天气、甲虫的开放世界（dodge/nature.js）
//   flat    没有墙的平地开放世界（「生活」标签里的设定：东西凭空出现在它附近）
//   court   篮球场（有边界，触感 + 围栏视觉）
// 量：总路程、平均速度系数（坡度）、被实心物件挡住的时间、触角触碰的时间、起飞 / 躲开 / 被撞、掉下来的浆果数、碰到糖 / 吃了几秒、喝水几秒、
//     淋雨几秒、雨点砸中次数、被晒烫（热 > 0.5）几秒、多巴胺秒数、3 分钟后 A 的奖赏记忆 / B 的惩罚记忆。
// 输出 results/learn/nature_life.json（约 12 分钟）
const fs = require("fs"), path = require("path"), ROOT = path.resolve(__dirname, "..");
const { ConnectomeBrain } = require("../dodge/brain.js"), { createGame } = require("../dodge/game_core.js"), Legs = require("../dodge/legs.js"), Nature = require("../dodge/nature.js");
const SUB = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge/subcircuit_v5.json"), "utf8")), GAIT = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge/gait.json"), "utf8")), CLIPS = JSON.parse(fs.readFileSync(path.join(ROOT, "results/flight/flight_clips.json"), "utf8")).clips;
const T = +(process.argv[2] || 180), WORLDS = { nature: { courtW: 0, touch: true, wallVision: false, nature: true }, flat: { courtW: 0, touch: false, wallVision: false }, court: { touch: true, wallVision: true } }, out = { seconds: T, seeds: 3, worlds: {} };
for (const [name, cfg0] of Object.entries(WORLDS)) { const rows = [], { nature, ...cfg } = cfg0;
  for (const seed of [101, 202, 303]) {
    const g = createGame(SUB, ConnectomeBrain, { seed, mode: "manual", ballSpeed: 60, cfg: { encoding: "ache2019", lplc2Mu: 45, gfTau: 0.02, takeoff: "clip", autoPellets: false, autoDust: true, dustEvery: 40, wind: true, life: true, physiology: true, ...cfg } });
    g.setFlightClips(CLIPS); g.attachLegs(Legs.create(GAIT)); const W = nature ? g.attachWorld(Nature.create(seed)) : null;
    let pathLen = 0, px = g.S.x, py = g.S.y, bump = 0, touch = 0, pam = 0, ppl = 0, rainS = 0, hot = 0, slope = 0, walkN = 0, berries = 0, drink = 0; const n = Math.round(T / g.chunkDt), seen = new Set(); let contacts = 0;
    g.onEvent = (t, b) => { if (t === "launch" && b.kind === "berry") berries++; };
    for (let i = 0; i < n; i++) { g.step(); const S = g.S; pathLen += Math.hypot(S.x - px, S.y - py); px = S.x; py = S.y; if (S.bump) bump += g.chunkDt; if (g.touch.L + g.touch.R > 0) touch += g.chunkDt; if (g.MB.drive.PAM) pam += g.chunkDt; if (g.MB.drive.PPL1) ppl += g.chunkDt;
      if (W && W.weather.rain > 0.3) rainS += g.chunkDt; if (g.field.thermo > 0.5) hot += g.chunkDt; if (W && S.state === "walk") { slope += W.slopeFactor(S.x, S.y, S.h, 1); walkN++; } if (S.state === "feed" && g.onPellet && g.onPellet.type === "water") drink += g.chunkDt;
      if (g.onPellet && g.onPellet.type === "sugar" && !seen.has(g.onPellet.id)) { seen.add(g.onPellet.id); contacts++; } }
    const mA = g.memoryOf("A"), mB = g.memoryOf("B");
    rows.push({ path_mm: Math.round(pathLen), slope_factor: walkN ? +(slope / walkN).toFixed(3) : 1, blocked_s: +bump.toFixed(1), touch_s: +touch.toFixed(1), jumps: g.score.jump, dodge: g.score.dodge, hit: g.score.hit, bonk: g.score.bonk || 0, berries, sugar_contacts: contacts, feed_s: +g.score.feed_s.toFixed(1), drink_s: +drink.toFixed(1),
      rain_s: +rainS.toFixed(1), rain_hits: g.score.rainHits || 0, hot_s: +hot.toFixed(1), pam_s: +pam.toFixed(1), ppl1_s: +ppl.toFixed(1), memA_reward: mA ? +(1 - mA.PAM).toFixed(3) : 0, memB_punish: mB ? +(1 - mB.PPL1).toFixed(3) : 0, energy: +g.body.energy.toFixed(2), hydration: +g.body.hydration.toFixed(2) }); }
  const mean = k => +(rows.reduce((a, r) => a + r[k], 0) / rows.length).toFixed(3);
  out.worlds[name] = { mean: Object.fromEntries(Object.keys(rows[0]).map(k => [k, mean(k)])), runs: rows }; console.log(name.padEnd(7), JSON.stringify(out.worlds[name].mean)); }
fs.writeFileSync(path.join(ROOT, "results/learn/nature_life.json"), JSON.stringify(out, null, 1));
