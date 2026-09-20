#!/usr/bin/env node
// 在**游戏里**学：页面的引擎（game_core + brain.js + plasticity.js + legs.js，子回路 v5），六条腿的身体，直线走过两个地方——
//   A 味的烂果子（吃到糖 → PAM）和 B 味的热源（烫 → PPL1）。之后量它对 A、B 的记忆，再做二选一。约 6 分钟。
// 判据（跑之前写死）：
//   G1 吃过 A 味的果子之后：A 的奖赏隔室（PAM）输入 ≤ 0.7，A 的惩罚隔室（PPL1）输入 ≥ 0.85
//   G2 烫过之后：            B 的惩罚隔室输入 ≤ 0.7，B 的奖赏隔室输入 ≥ 0.85
//   G3 对照（reinforce = false，别的都一样）：四个数都 ≥ 0.85
//   二选一用**互换设计**（果蝇学习实验的标准做法）：一组「A 配奖赏、B 配惩罚」，另一组「B 配奖赏、A 配惩罚」，比较两组走向 A 的比例——这样气味本身的偏好（没训练过的就有九成走向 A）被抵消。
//   这两组用**经典条件化**训练（实验者控制气味和多巴胺：气味源跟着果蝇走 5 秒，同时喷 PAM 或 PPL1；和 T 型迷宫训练一样，不依赖它自己走到哪）。
//   原因：自由行走的互换训练做不成——B 味的果子它根本走不到（B 会把它转走，一口没吃上，见 game_learning_choice_v2_failed.json）。
//   A、B 分在左前 / 右前，左右对调各一半；每组 N 只（默认 40；12 只时标准误 ±13 个百分点，分不清 25 个百分点的差）。
//   G4 **不开**手写的桥：两组走向 A 的比例相差 < 20 个百分点（预期：记忆走不到运动输出）
//   G5 **打开**手写的桥（memoryNav，第二版）：「A 配糖」组走向 A 的比例比「B 配糖」组高 ≥ 40 个百分点
//   （第一轮的设计——训练过 vs 没训练过、每组 12 只——留在 game_learning_choice_v1.json：没训练过的 92% 已经走向 A，判据没法成立；桥第一版的结果在 game_learning_bridge_v1.json。）
// 输出 results/learn/game_learning.json
const fs = require("fs"), path = require("path"), ROOT = path.resolve(__dirname, "..");
const { ConnectomeBrain } = require("../dodge/brain.js"), { createGame } = require("../dodge/game_core.js"), Legs = require("../dodge/legs.js");
const SUB = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge/subcircuit_v5.json"), "utf8")), GAIT = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge/gait.json"), "utf8"));
const N_CHOICE = +(process.argv[2] || 40);
function make(seed, cfg) {
  const g = createGame(SUB, ConnectomeBrain, { seed, mode: "manual", cfg: { encoding: "ache2019", lplc2Mu: 45, gfTau: 0.02, takeoff: "hop", wallVision: false, touch: false, autoPellets: false, autoDust: false, courtW: 0, life: false, physiology: true, wind: false, ...cfg } });
  g.brain.sparse = true; g.attachLegs(Legs.create(GAIT)); g.S.x = 0; g.S.y = 0; g.S.h = 0; g.body.energy = 0.3; return g;
}
function train(seed, reinforce, swap) {
  const g = make(seed, { reinforce }), t0 = Date.now(), FOOD = swap ? "B" : "A", HOT = swap ? "A" : "B"; let pamS = 0, pplS = 0, fedS = 0;
  // 正前方 25 mm：A 味的烂果子；再往前 70 mm：B 味的热源
  const food = g.addPellet(25, 0, "sugar"); food.r = 7; food.amount = 3; const oa = g.addOdor(25, 0, FOOD, 12, 1, 1e9); oa.pellet = food;
  g.addField("heat", 95, 0, 10, 1.5); g.addOdor(95, 0, HOT, 12, 1, 1e9);
  const T = 40, n = Math.round(T / g.chunkDt);
  for (let i = 0; i < n; i++) { g.step(); if (g.MB.drive.PAM) pamS += g.chunkDt; if (g.MB.drive.PPL1) pplS += g.chunkDt; if (g.S.state === "feed") fedS += g.chunkDt; if (g.S.x > 140) break; }
  return { g, pam_s: +pamS.toFixed(2), ppl1_s: +pplS.toFixed(2), fed_s: +fedS.toFixed(2), end_x: +g.S.x.toFixed(1), end_y: +g.S.y.toFixed(1), sim_s: +g.S.t.toFixed(1), wall_s: (Date.now() - t0) / 1000, memA: g.memoryOf("A"), memB: g.memoryOf("B"), saved: g.MB.plast.save() };
}
function classical(seed, rewarded, punished) {            // 经典条件化：气味源跟着它走，同时喷多巴胺
  const g = make(seed, { reinforce: false }), S = g.S, sniff = (kind, cluster) => { const o = g.addOdor(S.x, S.y, kind, 40, 1, 1e9); const n = Math.round(5 / g.chunkDt);
    for (let i = 0; i < n; i++) { o.x = S.x; o.y = S.y; if (i % 40 === 0) g.puff(cluster, 1); g.step(); } g.odors.length = 0; for (let i = 0; i < Math.round(2 / g.chunkDt); i++) g.step(); };
  sniff(rewarded, "PAM"); sniff(punished, "PPL1"); return { saved: g.MB.plast.save(), memA: g.memoryOf("A"), memB: g.memoryOf("B") };
}
function choice(seed, saved, nav) {
  const g = make(seed, { reinforce: false, learning: false, memoryNav: nav }); if (saved) g.MB.plast.load(saved);
  const a = 35 * Math.PI / 180, R = 45, sg = seed % 2 ? 1 : -1, ax = R * Math.cos(a), ay = sg * R * Math.sin(a);     // 奇数种子 A 在左，偶数种子 A 在右
  g.addOdor(ax, ay, "A", 22, 1, 1e9); g.addOdor(ax, -ay, "B", 22, 1, 1e9);
  let minA = 1e9, minB = 1e9; const n = Math.round(8 / g.chunkDt);
  for (let i = 0; i < n; i++) { g.step(); minA = Math.min(minA, Math.hypot(g.S.x - ax, g.S.y - ay)); minB = Math.min(minB, Math.hypot(g.S.x - ax, g.S.y + ay)); }
  return { minA, minB, toA: minA < minB, y: g.S.y * sg };
}
const out = { n_choice: N_CHOICE }, r2 = x => x == null ? null : +x.toFixed(3);
const tr = train(1, true, false), ct = train(1, false, false), cA = classical(2, "A", "B"), cB = classical(2, "B", "A");
out.trained = { ...tr, g: undefined, saved: undefined }; out.control = { ...ct, g: undefined, saved: undefined }; out.classical = { A_rewarded: { memA: cA.memA, memB: cA.memB }, B_rewarded: { memA: cB.memA, memB: cB.memB } };
console.log("训练（A 配糖、B 配烫）：", JSON.stringify(out.trained)); console.log("对照（不给多巴胺）：", JSON.stringify(out.control)); console.log("经典条件化：", JSON.stringify(out.classical));
out.realtime_factor = +(tr.sim_s / tr.wall_s).toFixed(2);
const frac = (saved, nav) => { let k = 0; const ys = []; for (let s = 0; s < N_CHOICE; s++) { const c = choice(100 + s, saved, nav); k += c.toA ? 1 : 0; ys.push(+c.y.toFixed(1)); } return { to_A: k / N_CHOICE, n: N_CHOICE, final_y: ys }; };
out.choice = { bridge_off: { naive: frac(null, false), A_rewarded: frac(cA.saved, false), B_rewarded: frac(cB.saved, false) }, bridge_on: { A_rewarded: frac(cA.saved, true), B_rewarded: frac(cB.saved, true) } };
const m = out.trained, c = out.control, ch = out.choice;
out.criteria = { G1_reward_memory: m.memA && m.memA.PAM <= 0.7 && m.memA.PPL1 >= 0.85, G2_punish_memory: m.memB && m.memB.PPL1 <= 0.7 && m.memB.PAM >= 0.85,
  G3_control_flat: !!(c.memA && c.memB) && [c.memA.PAM, c.memA.PPL1, c.memB.PAM, c.memB.PPL1].every(x => x >= 0.85),
  G4_no_behavior_without_bridge: Math.abs(ch.bridge_off.A_rewarded.to_A - ch.bridge_off.B_rewarded.to_A) < 0.20, G5_bridge_works: ch.bridge_on.A_rewarded.to_A - ch.bridge_on.B_rewarded.to_A >= 0.40 };
for (const k of Object.keys(out.criteria)) out.criteria[k] = !!out.criteria[k];
fs.writeFileSync(path.join(ROOT, "results/learn/game_learning.json"), JSON.stringify(out, null, 1));
console.log("二选一（走向 A 的比例）：", JSON.stringify({ naive: ch.bridge_off.naive.to_A, off: [ch.bridge_off.A_rewarded.to_A, ch.bridge_off.B_rewarded.to_A], on: [ch.bridge_on.A_rewarded.to_A, ch.bridge_on.B_rewarded.to_A] }), "\n判据：", JSON.stringify(out.criteria), "\n速度：", out.realtime_factor, "× 实时");
