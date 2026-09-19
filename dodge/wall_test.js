#!/usr/bin/env node
/**
 * 围栏接进视觉通路之后，果蝇还会不会顶着墙一直走？
 *
 * 起因（2026-09-19 用户反馈）：果蝇走到场地边缘会一直顶着围栏往前走。
 * 查下来不是"认不出墙"，而是**墙从来没有接进任何感觉通路**——
 * 视觉前端只读球的世界坐标，边界只是 step() 末尾的一次几何钳位。
 *
 * 改法不是加避障规则，而是把墙按同一套手写前端算成逼近物体，走 LC4/LPLC2 → 连接组。
 * 这个脚本量的是改动有没有用，指标事先定死：
 *   贴墙时间占比  = S.wall > 0 的步数 ÷ 总步数
 *   最长一次贴墙  = 连续贴墙的最长秒数
 *   离墙均距      = 到最近墙的平均距离（mm）
 * 对照：wallVision 关 / 开；另外报告起跳次数（怕它靠"一直起飞"来解决问题）。
 *
 * 用法：node dodge/wall_test.js [每局秒数=120] [种子数=3]
 * 输出：results/dodge/wall.json
 */
const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "..");
const { ConnectomeBrain } = require("./brain.js");
const { createGame } = require("./game_core.js");
const SUB = JSON.parse(fs.readFileSync(ROOT + "/results/dodge/subcircuit_v2.json", "utf8"));
const CLIPS = JSON.parse(fs.readFileSync(ROOT + "/results/flight/flight_clips.json", "utf8")).clips;
const T = +(process.argv[2] || 120), SEEDS = +(process.argv[3] || 3);

function run(wallVision, seed, noBalls) {
  const g = createGame(SUB, ConnectomeBrain, { seed, ballSpeed: 60,
    cfg: { encoding: "ache2019", gfTau: 0.02, takeoff: "clip", wallVision,
           autoPellets: false, autoDust: false } });
  g.setFlightClips(CLIPS);
  if (noBalls) g.mode = "click";
  const n = Math.round(T / g.chunkDt);
  const hw = g.CFG.courtW / 2 - g.CFG.courtPad, hh = g.CFG.courtH / 2 - g.CFG.courtPad;
  let stuck = 0, run0 = 0, maxRun = 0, dsum = 0;
  for (let i = 0; i < n; i++) {
    g.step();
    const S = g.S;
    const d = Math.min(hw - Math.abs(S.x), hh - Math.abs(S.y));
    dsum += d;
    if (S.wall > 0) { stuck++; run0 += g.chunkDt; maxRun = Math.max(maxRun, run0); } else run0 = 0;
  }
  return { stuckFrac: +(stuck / n).toFixed(4), maxStuckS: +maxRun.toFixed(2),
           meanWallDist: +(dsum / n).toFixed(2), jump: g.score.jump,
           dodge: g.score.dodge, hit: g.score.hit };
}

const out = { seconds_per_seed: T, seeds: SEEDS,
  note: "贴墙 = game_core 里 S.wall > 0（那一步被边界钳位过）。两种场景各测：有球（默认自动发球）与无球。",
  arms: {} };
for (const noBalls of [false, true]) {
  for (const wv of [false, true]) {
    const key = (noBalls ? "无球_" : "有球_") + (wv ? "看得见墙" : "看不见墙");
    const rs = Array.from({ length: SEEDS }, (_, i) => run(wv, i + 1, noBalls));
    const m = k => +(rs.reduce((a, r) => a + r[k], 0) / SEEDS).toFixed(4);
    out.arms[key] = { runs: rs, mean: { stuckFrac: m("stuckFrac"), maxStuckS: m("maxStuckS"),
                                        meanWallDist: m("meanWallDist"), jump: m("jump") } };
    const v = out.arms[key].mean;
    console.log(`${key.padEnd(18, "　")} 贴墙时间 ${(v.stuckFrac * 100).toFixed(1)}%　最长一次 ${v.maxStuckS}s　` +
                `离墙均距 ${v.meanWallDist}mm　起跳 ${v.jump}`);
  }
}
const a = out.arms["无球_看不见墙"].mean, b = out.arms["无球_看得见墙"].mean;
out.improvement_no_balls = { stuckFrac: +(a.stuckFrac - b.stuckFrac).toFixed(4),
                             maxStuckS: +(a.maxStuckS - b.maxStuckS).toFixed(2) };
out.works = b.stuckFrac < a.stuckFrac * 0.5;
fs.writeFileSync(ROOT + "/results/dodge/wall.json", JSON.stringify(out, null, 1));
console.log(`\n无球时贴墙时间 ${(a.stuckFrac * 100).toFixed(1)}% → ${(b.stuckFrac * 100).toFixed(1)}%，` +
            `判据（降到一半以下）${out.works ? "成立" : "不成立"}\n→ results/dodge/wall.json`);
