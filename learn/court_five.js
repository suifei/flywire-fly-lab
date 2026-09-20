#!/usr/bin/env node
// 「五感全开」搬进篮球场之后过得怎么样：v5 大脑 + 六条腿，世界自己运转（果子带气味 A、热源带气味 B、声音、来球），3 分钟 × 3 个种子。
//   court  篮球场（320 × 172 mm，有边界，触感 + 围栏视觉都开着——和球场版那只同一套设定）
//   open   没有墙的开放世界（「生活」标签里的设定）
// 只报告，不设判据：总路程、贴墙时间、起飞、躲开 / 被砸、碰到糖、吃了几秒、多巴胺放了几秒、3 分钟后 A / B 的记忆。
// 已知的局限（§47.6）：只靠触感避不开墙；开了围栏视觉就会朝着围栏白白起飞。球场版那只本来就是这样，这里量一下有多严重。
// 输出 results/learn/court_five.json（约 8 分钟）
const fs = require("fs"), path = require("path"), ROOT = path.resolve(__dirname, "..");
const { ConnectomeBrain } = require("../dodge/brain.js"), { createGame } = require("../dodge/game_core.js"), Legs = require("../dodge/legs.js");
const SUB = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge/subcircuit_v5.json"), "utf8")), GAIT = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge/gait.json"), "utf8")), CLIPS = JSON.parse(fs.readFileSync(path.join(ROOT, "results/flight/flight_clips.json"), "utf8")).clips;
const T = +(process.argv[2] || 180), WORLDS = { court: { touch: true, wallVision: true }, open: { courtW: 0, touch: false, wallVision: false } }, out = { seconds: T, seeds: 3, worlds: {} };
for (const [name, cfg] of Object.entries(WORLDS)) { const rows = [];
  for (const seed of [101, 202, 303]) {
    const g = createGame(SUB, ConnectomeBrain, { seed, mode: "manual", ballSpeed: 60, cfg: { encoding: "ache2019", lplc2Mu: 45, gfTau: 0.02, takeoff: "clip", autoPellets: false, autoDust: true, dustEvery: 40, wind: true, life: true, physiology: true, ...cfg } });
    g.setFlightClips(CLIPS); g.attachLegs(Legs.create(GAIT)); let pathLen = 0, px = g.S.x, py = g.S.y, wall = 0, pam = 0, ppl = 0; const n = Math.round(T / g.chunkDt), seen = new Set(); let contacts = 0;
    for (let i = 0; i < n; i++) { g.step(); const S = g.S; pathLen += Math.hypot(S.x - px, S.y - py); px = S.x; py = S.y; if ((S.wall || 0) > 0) wall++; if (g.MB.drive.PAM) pam += g.chunkDt; if (g.MB.drive.PPL1) ppl += g.chunkDt;
      if (g.onPellet && g.onPellet.type === "sugar" && !seen.has(g.onPellet.id)) { seen.add(g.onPellet.id); contacts++; } }
    const mA = g.memoryOf("A"), mB = g.memoryOf("B");
    rows.push({ path_mm: Math.round(pathLen), wall_frac: +(wall / n).toFixed(3), jumps: g.score.jump, dodge: g.score.dodge, hit: g.score.hit, sugar_contacts: contacts, feed_s: +g.score.feed_s.toFixed(1), pam_s: +pam.toFixed(1), ppl1_s: +ppl.toFixed(1),
      memA_reward: mA ? +(1 - mA.PAM).toFixed(3) : 0, memB_punish: mB ? +(1 - mB.PPL1).toFixed(3) : 0, energy: +g.body.energy.toFixed(2) }); }
  const mean = k => +(rows.reduce((a, r) => a + r[k], 0) / rows.length).toFixed(3);
  out.worlds[name] = { mean: Object.fromEntries(Object.keys(rows[0]).map(k => [k, mean(k)])), runs: rows }; console.log(name.padEnd(6), JSON.stringify(out.worlds[name].mean)); }
fs.writeFileSync(path.join(ROOT, "results/learn/court_five.json"), JSON.stringify(out, null, 1));
