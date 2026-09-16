// 被击中的原因诊断：记录每个球的来球方向、巨纤维起跳时机与结果（完整大脑，不改游戏规则）
// 用法：node dodge/diagnose.js [每局秒数=120] [种子数=5]
const fs = require("fs");
const { ConnectomeBrain } = require("./brain.js");
const { createGame } = require("./game_core.js");
const SUB = JSON.parse(fs.readFileSync(__dirname + "/../results/dodge/subcircuit.json", "utf8"));
const T = +(process.argv[2] || 120), SEEDS = +(process.argv[3] || 5);

const recs = [];
for (let seed = 1; seed <= SEEDS; seed++) {
  const g = createGame(SUB, ConnectomeBrain, { seed, ballSpeed: 60 });
  const info = new Map();
  let jumpStarts = [];
  g.onEvent = (type, b) => {
    const S = g.S;
    if (type === "launch") {
      const rx = b.x - S.x, ry = b.y - S.y;
      const bearing = Math.atan2(Math.sin(-S.h) * rx + Math.cos(-S.h) * ry, Math.cos(-S.h) * rx - Math.sin(-S.h) * ry) * 180 / Math.PI;
      info.set(b.id, { bearing, t0: S.t, tHit: b.tHit, others: g.balls.length - 1 });
    }
    if (type === "jump") jumpStarts.push(S.t);
    if (type === "hit" || type === "dodge") {
      const r = info.get(b.id);
      const tImpact = r.t0 + r.tHit;
      // 离预计撞击时刻最近的一次起跳（撞击前 0.6 s 内）
      const js = jumpStarts.filter(t => t > tImpact - 0.6 && t < tImpact + 0.1);
      const lead = js.length ? tImpact - js[js.length - 1] : null;   // 起跳比预计撞击早多少秒
      recs.push({ outcome: type, bearing: r.bearing, lead, airborneAtHit: type === "hit" ? g.S.jumpT >= 0 : null, others: r.others });
    }
  };
  const n = Math.round(T / g.chunkDt);
  for (let i = 0; i < n; i++) g.step();
}

const pct = (a, b) => (b ? (100 * a / b).toFixed(0) + "%" : "—");
console.log(`共 ${recs.length} 个已结算的球（完整大脑，球速 60 mm/s）\n`);
console.log("按来球方向（相对果蝇朝向，+ = 左）：");
for (const [lo, hi, name] of [[-15, 15, "正前方 ±15°（双眼重叠）"], [15, 90, "左前"], [-90, -15, "右前"], [90, 165, "左后"], [-165, -90, "右后"], [165, 181, "正后方盲区"]]) {
  const sel = recs.filter(r => name.includes("盲区") ? Math.abs(r.bearing) >= 165 : r.bearing >= lo && r.bearing < hi);
  const hit = sel.filter(r => r.outcome === "hit").length;
  console.log(`  ${name.padEnd(14, "　")} ${String(sel.length).padStart(3)} 个  被击中 ${pct(hit, sel.length)}`);
}
console.log("\n按起跳时机（起跳时刻距预计撞击）：");
const bins = [[null, null, "没有起跳"], [0.45, 0.7, "提前 >0.45 s"], [0.3, 0.45, "提前 0.30–0.45 s"], [0.15, 0.3, "提前 0.15–0.30 s"], [-0.2, 0.15, "提前 <0.15 s / 太晚"]];
for (const [lo, hi, name] of bins) {
  const sel = recs.filter(r => lo === null ? r.lead === null : r.lead !== null && r.lead >= lo && r.lead < hi);
  const hit = sel.filter(r => r.outcome === "hit").length;
  console.log(`  ${name.padEnd(12, "　")} ${String(sel.length).padStart(3)} 个  被击中 ${pct(hit, sel.length)}`);
}
const hits = recs.filter(r => r.outcome === "hit");
console.log(`\n被击中时仍在空中（落地前被追上 / 起跳过早）：${pct(hits.filter(r => r.airborneAtHit).length, hits.length)}`);
console.log(`被击中时场上还有其他球（多球干扰）：${pct(hits.filter(r => r.others > 0).length, hits.length)}，全部球中 ${pct(recs.filter(r => r.others > 0).length, recs.length)}`);
fs.writeFileSync(__dirname + "/../results/dodge/diagnose.json", JSON.stringify(recs));
