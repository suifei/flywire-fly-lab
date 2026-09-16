// v4 后退实验（设计在运行前写定，所有组合都报告）
// 问题：连接组里 LC16 → MDN 的后退通路，在什么条件下能减少“正前方威胁”的击中？后退与转向各贡献多少？
//
// 设计：
//   * 每次只有一个威胁：从果蝇正前方 40 mm、方位 ±10°（均匀随机）发出；结束后等 1.5 s，且果蝇在地面，才发下一个。
//   * 威胁类型：
//       roll   = 原游戏滚球（按“果蝇继续前进”的提前量瞄准，穿过后继续滚，4 s 后消失；击中/躲开按游戏原判定）
//       strike = “扑击”：瞄准发射时果蝇所在位置，到点停住 0.3 s 后消失；存续期间任何时刻接触即击中，否则躲开
//   * 速度：15 / 30 / 60 mm/s
//   * 切除：intact；GF（切除巨纤维输出，只剩地面反应）；GF_MDN（只剩转向）；GF_DNa（只剩后退）；GF_LC16（LC16 断突触）
//   * LC16 编码斜率（Hz per °/s）：0.5（v3 事先声明值）、2、5
//   * 每格 3 个种子 × 8 个威胁 = 24 个。指标：击中率；威胁存续期间出现后退的比例；接触/结束前的后退距离
// 事先写下的物理预期：后退速度 12 mm/s；roll 型球速都 ≥ 15 mm/s 且继续滚动，正面来球后退只能推迟被击中；
//   strike 型到点即停，结束前需退出 ≥ 3.9 mm（球半径 2.5 + 果蝇半径 1.4）。
// 全脑参考（results/v2_ref）：双侧 LC16 25/50/100/150 Hz → MDN 0/0/15/31 Hz；单侧 100 Hz → MDN ≤ 5 Hz，
//   所以不加“MDN 左右差 → 转向”的映射（转向仍走 DNa01/DNa02）。
// 注：运行前修正了 game_core.js 的提前量瞄准——球速低于行走速度（18 mm/s）时原公式会把球瞄到果蝇身后，现取最早的正解；
//   页面的球速 35/60/95 mm/s 不受影响。
// 用法：node dodge/backward_v4.js [每种子威胁数=8] [种子数=3]
const fs = require("fs");
const { ConnectomeBrain } = require("./brain.js");
const { createGame } = require("./game_core.js");
const SUB = JSON.parse(fs.readFileSync(__dirname + "/../results/dodge/subcircuit_v2.json", "utf8"));
const PER_SEED = +(process.argv[2] || 8), SEEDS = +(process.argv[3] || 3);
const BASE = { gfTau: 0.02, encoding: "ache2019", lplc2Mu: 45, takeoff: "hop" };
const LESIONS = { intact: [], GF: ["GF"], GF_MDN: ["GF", "MDN"], GF_DNa: ["GF", "DNa"], GF_LC16: ["GF", "LC16"] };
const TYPES = ["roll", "strike"], SPEEDS = [15, 30, 60], SLOPES = [0.5, 2, 5];

function mulberry(seed) {
  let s = seed >>> 0;
  return () => { s = (s + 0x6d2b79f5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

function cell(type, speed, slope, lesion) {
  const agg = { n: 0, hit: 0, backed: 0, back_mm: 0, sim_s: 0 };
  for (let seed = 1; seed <= SEEDS; seed++) {
    const g = createGame(SUB, ConnectomeBrain, { seed: seed * 101 + speed, ballSpeed: speed, mode: "click", cfg: { ...BASE, lc16Slope: slope } });
    for (const l of LESIONS[lesion]) g.setLesion(l, true);
    const rand = mulberry(seed * 7919 + speed);
    const R = g.CFG.ballR + g.CFG.flyR;
    let trial = null, wait = 0.5, done = 0, steps = 0;
    g.onEvent = (ev, b) => {
      if (!trial || !b || b.id !== trial.id) return;
      if ((ev === "hit" || ev === "dodge") && !trial.gameOutcome) trial.gameOutcome = ev;
      if (ev === "remove") trial.removed = true;
    };
    while (done < PER_SEED && steps * g.chunkDt < 400) {
      if (!trial) {
        wait -= g.chunkDt;
        if (wait <= 0 && g.S.jumpT < 0 && g.S.z === 0) {
          const a = g.S.h + (rand() * 2 - 1) * 10 * Math.PI / 180;
          const b = g.launch(g.S.x + Math.cos(a) * 40, g.S.y + Math.sin(a) * 40, { strike: type === "strike" });
          trial = { id: b.id, b, gameOutcome: null, removed: false, contact: false, backed: false, back_mm: 0 };
        }
      }
      g.step(); steps++;
      if (!trial) continue;
      const S = g.S, b = trial.b;
      const settled = type === "roll" ? !!trial.gameOutcome : trial.contact;
      if (S.state === "back" && S.jumpT < 0) { trial.backed = true; if (!settled) trial.back_mm += g.CFG.backSpeed * g.chunkDt; }
      if (type === "strike" && !trial.removed && Math.hypot(b.x - S.x, b.y - S.y) < R && S.z < g.CFG.ballR * 1.6) trial.contact = true;
      const end = type === "roll" ? (trial.gameOutcome || trial.removed) : trial.removed;
      if (end) {
        const hit = type === "roll" ? trial.gameOutcome === "hit" : trial.contact;
        agg.n++; agg.hit += hit ? 1 : 0; agg.backed += trial.backed ? 1 : 0; agg.back_mm += trial.back_mm;
        trial = null; wait = 1.5; done++;
      }
    }
    agg.sim_s += steps * g.chunkDt;
  }
  return { type, speed, slope, lesion, n: agg.n, hit_rate: agg.n ? agg.hit / agg.n : null, backed_frac: agg.n ? agg.backed / agg.n : null,
           back_mm_mean: agg.n ? agg.back_mm / agg.n : null, sim_s: agg.sim_s };
}

const rows = [];
const t0 = Date.now();
let simTotal = 0;
for (const type of TYPES) for (const speed of SPEEDS) for (const slope of SLOPES) {
  const line = [];
  for (const lesion of Object.keys(LESIONS)) {
    const r = cell(type, speed, slope, lesion);
    rows.push(r); simTotal += r.sim_s;
    line.push(`${lesion} 击中 ${(r.hit_rate * 100).toFixed(0)}% 后退 ${(r.backed_frac * 100).toFixed(0)}%/${r.back_mm_mean.toFixed(1)}mm`);
  }
  console.log(`${type.padEnd(6)} ${String(speed).padStart(2)} mm/s 斜率 ${slope}：${line.join(" | ")}`);
  fs.writeFileSync(__dirname + "/../results/dodge/backward_v4.json", JSON.stringify({ per_seed: PER_SEED, seeds: SEEDS, rows }, null, 1));
}
console.log(`仿真 ${simTotal.toFixed(0)} s，用时 ${((Date.now() - t0) / 1000).toFixed(0)} s（${(simTotal / ((Date.now() - t0) / 1000)).toFixed(2)}× 实时）`);
