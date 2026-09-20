#!/usr/bin/env node
/**
 * 为什么生活模式是**没有墙的开放世界**：只靠触感，这颗脑子避不开墙。三个场地各跑 3 分钟 × 3 个种子（子回路 v4，世界自己运转）：
 *   rect_touch   矩形场地 + 触感：会卡死在墙角（两根触角同时压墙，左右相等，转向差为 0）
 *   round_touch  圆形场地 + 触感：没有墙角，仍然绝大部分时间贴在墙上
 *   rect_vision  矩形场地 + 围栏视觉：不贴墙了，但它自己走向围栏就会被当成逼近，白白起飞
 *   open         没有墙
 * 量：总路程（18 mm/s 走满 3 分钟是 3,240 mm）、贴墙时间占比、起飞次数、碰到食物的次数。只报告，不设判据。
 * 用法：node dodge/wall_limits.js   → results/dodge/wall_limits.json（约 8 分钟）
 */
const fs = require("fs"), path = require("path"), ROOT = path.resolve(__dirname, "..");
const { ConnectomeBrain } = require("./brain.js"), { createGame } = require("./game_core.js");
const SUB = JSON.parse(fs.readFileSync(ROOT + "/results/dodge/subcircuit_v4.json", "utf8")), CLIPS = JSON.parse(fs.readFileSync(ROOT + "/results/flight/flight_clips.json", "utf8")).clips;
const T = 180, ARENAS = { rect_touch: { courtW: 200, courtH: 140, courtPad: 4, touch: true, wallVision: false }, round_touch: { courtW: 220, courtH: 220, courtPad: 4, arenaR: 100, touch: true, wallVision: false },
  rect_vision: { courtW: 200, courtH: 140, courtPad: 4, touch: true, wallVision: true }, open: { courtW: 0, touch: false, wallVision: false } };
const out = { seconds: T, seeds: 3, walk_speed_mm_s: 18, arenas: {} };
for (const [name, cfg] of Object.entries(ARENAS)) { const rows = [];
  for (const seed of [101, 202, 303]) { const g = createGame(SUB, ConnectomeBrain, { seed, mode: "manual", cfg: { encoding: "ache2019", lplc2Mu: 45, gfTau: 0.02, takeoff: "clip", autoPellets: false, autoDust: false, life: true, physiology: true, lifeBall: [1e9, 1e9], ...cfg } });
    g.setFlightClips(CLIPS); let pathLen = 0, px = 0, py = 0, wall = 0; const n = Math.round(T / g.chunkDt);
    for (let i = 0; i < n; i++) { g.step(); const S = g.S; pathLen += Math.hypot(S.x - px, S.y - py); px = S.x; py = S.y; if ((S.wall || 0) > 0) wall++; }
    rows.push({ path_mm: Math.round(pathLen), wall_frac: +(wall / n).toFixed(3), jumps: g.score.jump, food_contacts: (g.score.contacts_sugar || 0) + (g.score.contacts_water || 0) + (g.score.contacts_bitter || 0) }); }
  const mean = k => +(rows.reduce((a, r) => a + r[k], 0) / rows.length).toFixed(3);
  out.arenas[name] = { mean: { path_mm: mean("path_mm"), wall_frac: mean("wall_frac"), jumps: mean("jumps"), food_contacts: mean("food_contacts") }, runs: rows };
  console.log(`${name.padEnd(12)} 路程 ${mean("path_mm")} mm  贴墙 ${(mean("wall_frac") * 100).toFixed(0)}%  起飞 ${mean("jumps")}（没有来球）  碰到食物 ${mean("food_contacts")}`); }
fs.writeFileSync(ROOT + "/results/dodge/wall_limits.json", JSON.stringify(out, null, 1)); console.log("→ results/dodge/wall_limits.json");
