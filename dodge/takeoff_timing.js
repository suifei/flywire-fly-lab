#!/usr/bin/env node
/**
 * 对照 Card & Dickinson 2008：我们的起飞和真果蝇差在哪？
 *
 * 该文（Curr Biol 18:1300-1307）的可核对主张（摘要，全文取不到——Caltech 库 metadata-only、
 * cell.com 403）：
 *   1. 真果蝇在**起飞前约 200 ms** 就开始一连串姿态调整，把质心摆到"腿一蹬就推离刺激"的位置；
 *   2. 这套动作**不是前馈固定程序** —— 幅度和方向取决于果蝇当时的初始姿态；
 *   3. 果蝇**即使最终不跳，也会先规划好起飞方向**。
 *
 * 我们的游戏：巨纤维超过阈值 → **立即**起飞，没有姿态准备期。这个脚本把差距量出来。
 * 测量：GF 首次越过阈值到实际起飞之间的延迟，以及起飞时刻球还有多远 / 还有多久撞上。
 *
 * 用法：node dodge/takeoff_timing.js   → results/dodge/takeoff_timing.json
 */
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, "..");
const SUB = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge/subcircuit_v2.json")));
const { ConnectomeBrain } = require(path.join(ROOT, "dodge/brain.js"));
const { createGame } = require(path.join(ROOT, "dodge/game_core.js"));

const SEEDS = [1, 2, 3, 4, 5], T = 90, DT = 0.005;
const ev = [];
for (const seed of SEEDS) {
  const g = createGame(SUB, ConnectomeBrain, { seed, ballSpeed: 60, cfg: { takeoff: "clip" } });
  let gfCross = null, wasFlying = false;
  for (let i = 0; i < T / DT; i++) {
    g.step(DT);
    const t = i * DT;
    const o = g.readout();
    const flying = !!(g.S.clip && g.S.jumpT >= 0);
    if (gfCross === null && o.gf > g.CFG.gfThreshold) gfCross = t;
    if (o.gf <= g.CFG.gfThreshold && !flying) gfCross = null;
    if (flying && !wasFlying) {
      // 起飞瞬间：最近的球有多远、按当前径向速度还有多久撞上
      let best = null;
      for (const b of g.balls) {
        if (b.outcome) continue;
        const dx = b.x - g.S.x, dy = b.y - g.S.y, d = Math.hypot(dx, dy);
        const vr = -((dx * (b.vx || 0) + dy * (b.vy || 0)) / Math.max(d, 1e-6));   // 接近速率
        if (!best || d < best.d) best = { d, vr };
      }
      ev.push({ seed, t: +t.toFixed(3),
                lat_ms: gfCross === null ? null : +((t - gfCross) * 1000).toFixed(1),
                dist_mm: best ? +best.d.toFixed(2) : null,
                ttc_ms: best && best.vr > 0 ? +((best.d / best.vr) * 1000).toFixed(0) : null });
    }
    wasFlying = flying;
  }
}
const num = a => a.filter(x => x !== null && Number.isFinite(x));
const med = a => { const s = num(a).sort((x, y) => x - y); return s.length ? s[s.length >> 1] : null; };
const lat = ev.map(e => e.lat_ms), dis = ev.map(e => e.dist_mm), ttc = ev.map(e => e.ttc_ms);
console.log(`${SEEDS.length} 个种子 × ${T} s，共 ${ev.length} 次起飞\n`);
console.log(`GF 越阈 → 起飞的延迟   中位 ${med(lat)} ms      （真果蝇的姿态准备期约 200 ms）`);
console.log(`起飞时最近的球距离     中位 ${med(dis)} mm`);
console.log(`起飞时的剩余撞击时间   中位 ${med(ttc)} ms`);
const out = {
  来源: "Card & Dickinson 2008 Curr Biol 18:1300-1307（仅摘要可得；cell.com 403、Caltech 库 metadata-only）",
  论文主张: ["起飞前约 200 ms 开始姿态调整，把质心摆到腿一蹬就推离刺激的位置",
             "不是前馈固定程序：幅度与方向取决于初始姿态",
             "即使最终不跳，也会先规划好起飞方向"],
  我们的实现: "巨纤维越阈即起飞，逃逸方向取背离威胁的那一侧并把飞行片段整体旋转过去；没有姿态准备期",
  实测: { 种子: SEEDS, 每局秒数: T, 起飞次数: ev.length,
          GF越阈到起飞延迟ms中位: med(lat), 起飞时球距mm中位: med(dis), 剩余撞击时间ms中位: med(ttc) },
  差距: ["姿态准备期 200 ms：完全没有建模（我们是 %s ms）".replace("%s", String(med(lat))),
         "方向依赖初始姿态：没有建模，我们只用威胁方位",
         "不跳也规划：没有建模"],
  事件: ev,
};
fs.writeFileSync(path.join(ROOT, "results/dodge/takeoff_timing.json"), JSON.stringify(out, null, 1));
console.log("\n→ results/dodge/takeoff_timing.json");
