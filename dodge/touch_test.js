#!/usr/bin/env node
/**
 * 「只给物理量，不写判断逻辑」这条原则，在带触感的子回路 v3 上成立吗？
 *
 * 链条：触角/头部碰到围栏（纯几何）→ 头部刚毛机械感觉神经元（TOUCH，305 个真实神经元）
 *      → 连接组 → DNa01/02（转向）或 DNp01（逃逸）。**中间没有任何我们写的判断。**
 *
 * 对照（事先定死）：
 *   v2 + 无            没有触感通路，也不给围栏视觉 —— 预期一直贴墙
 *   v2 + 触感→JO       v2 里唯一的机械感觉是触角 JO（实测无效，因为 JO 只通到梳理）
 *   v3 + 触感→TOUCH    头部刚毛，全脑里到转向/逃逸只要 2 跳
 *   v2 + 围栏视觉      我们手写的物体式近似（把墙算成逼近物体喂 LC4/LPLC2）——参照上限
 * 判据：v3+触感的贴墙时间要显著低于「无」，才算「给物理量就够了」。
 *
 * 用法：node dodge/touch_test.js [每局秒数=120] [种子数=3]
 * 输出：results/dodge/touch.json
 */
const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "..");
const { ConnectomeBrain } = require("./brain.js");
const { createGame } = require("./game_core.js");
const SUB2 = JSON.parse(fs.readFileSync(ROOT + "/results/dodge/subcircuit_v2.json", "utf8"));
const SUB3 = JSON.parse(fs.readFileSync(ROOT + "/results/dodge/subcircuit_v3.json", "utf8"));
const CLIPS = JSON.parse(fs.readFileSync(ROOT + "/results/flight/flight_clips.json", "utf8")).clips;
const T = +(process.argv[2] || 120), SEEDS = +(process.argv[3] || 3);

function run(SUB, cfg, seed) {
  const g = createGame(SUB, ConnectomeBrain, { seed, ballSpeed: 60,
    cfg: { encoding: "ache2019", gfTau: 0.02, takeoff: "clip", autoPellets: false, autoDust: false, ...cfg } });
  g.setFlightClips(CLIPS);
  g.mode = "click";                                  // 无球：只看它和墙的关系
  const hw = g.CFG.courtW / 2 - g.CFG.courtPad, hh = g.CFG.courtH / 2 - g.CFG.courtPad;
  const n = Math.round(T / g.chunkDt);
  let stuck = 0, run0 = 0, maxRun = 0, dsum = 0, touchSteps = 0, pathLen = 0;
  let px = g.S.x, py = g.S.y;
  const cells = new Set();                          // 20 mm 的格子，用来量"还在不在探索"
  for (let i = 0; i < n; i++) {
    g.step();
    const S = g.S;
    dsum += Math.min(hw - Math.abs(S.x), hh - Math.abs(S.y));
    pathLen += Math.hypot(S.x - px, S.y - py); px = S.x; py = S.y;
    cells.add(Math.round(S.x / 20) + "," + Math.round(S.y / 20));
    if (g.touch && (g.touch.L > 0 || g.touch.R > 0)) touchSteps++;
    if (S.wall > 0) { stuck++; run0 += g.chunkDt; maxRun = Math.max(maxRun, run0); } else run0 = 0;
  }
  // **stuckFrac 分不出"钉死在一点"和"贴着墙滑行"**——两者 S.wall 都 > 0。
  // 第一版只有它，结论就成了"触感没用"，其实果蝇在沿墙走。所以主指标换成覆盖格子数与路程。
  return { cells: cells.size, pathLen: +pathLen.toFixed(0),
           stuckFrac: +(stuck / n).toFixed(4), maxStuckS: +maxRun.toFixed(2),
           meanWallDist: +(dsum / n).toFixed(2), touchFrac: +(touchSteps / n).toFixed(4),
           jump: g.score.jump, groom: g.score.groom };
}

const ARMS = [
  ["v2 · 什么都不给", SUB2, {}],
  ["v2 · 触感→JO", SUB2, { touch: true }],
  ["v3 · 触感→头部刚毛", SUB3, { touch: true }],
  ["v3 · 什么都不给", SUB3, {}],
  ["v2 · 围栏视觉（手写）", SUB2, { wallVision: true }],
];
const out = { seconds_per_seed: T, seeds: SEEDS,
  note: "无球条件。触感 = 触角越过围栏时驱动该侧机械感觉神经元；v2 只有 JO，v3 有头部刚毛（TOUCH）。",
  arms: {} };
console.log(`${"条件".padEnd(22, "　")}${"走过格子".padStart(9)}${"路程mm".padStart(9)}${"贴墙".padStart(8)}${"触到".padStart(8)}${"起跳".padStart(7)}`);
for (const [name, SUB, cfg] of ARMS) {
  const rs = Array.from({ length: SEEDS }, (_, i) => run(SUB, cfg, i + 1));
  const m = k => +(rs.reduce((a, r) => a + r[k], 0) / SEEDS).toFixed(4);
  const rec = { runs: rs, mean: Object.fromEntries(Object.keys(rs[0]).map(k => [k, m(k)])) };
  out.arms[name] = rec;
  const v = rec.mean;
  console.log(`${name.padEnd(22, "　")}${String(v.cells).padStart(9)}${String(v.pathLen).padStart(9)}` +
    `${((v.stuckFrac * 100).toFixed(1) + "%").padStart(8)}${((v.touchFrac * 100).toFixed(1) + "%").padStart(8)}${String(v.jump).padStart(7)}`);
}
const base = out.arms["v3 · 什么都不给"].mean, touch = out.arms["v3 · 触感→头部刚毛"].mean;
out.v3_touch_helps = touch.cells > base.cells * 1.5;         // 判据换成"走过的格子数至少多一半"
out.v3_base = base; out.v3_touch = touch;
fs.writeFileSync(ROOT + "/results/dodge/touch.json", JSON.stringify(out, null, 1));
console.log(`\nv3 里：不给触感走过 ${base.cells} 个格子 / ${base.pathLen} mm → 给触感 ${touch.cells} 个 / ${touch.pathLen} mm，` +
            `判据（格子数多一半以上）${out.v3_touch_helps ? "成立" : "不成立"}`);
console.log("→ results/dodge/touch.json");
