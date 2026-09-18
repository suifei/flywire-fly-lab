#!/usr/bin/env node
/**
 * 量出「动脑子」那一排扰动的效果，对应论文 Shiu 2024 补充表 **1D**（打乱接线）与 **11B–F**（参数稳健性）。
 *
 * 口径与 `dodge/measure_neurons.js` **完全相同**（改了要两边一起改）：
 *   颗粒钉在头前 1.3 mm 持续接触 → 200 Hz；糖刺激 122 个 LB3，水只刺激其中 17 个水味觉 GRN；
 *   梳理用双侧落灰 → JO 200 Hz，读出 aDN1；每条件 2.5 s，取后 1.25 s 平均，种子 1/2/3。
 *
 * 扰动档位按论文：权重 ±30%（表 11B/C）、抑制 ±30%（表 11D/E）、谷氨酸改兴奋性（表 11F）、
 * 打乱接线（表 1D，论文跑 100 次，这里 10 次给均值±标准差）。
 *
 * **不声称复现论文的定量结果**：论文在全脑 138,639 个神经元上跑，这里是 4,599 个的子回路；
 * 而且论文没有公开打乱的具体做法（补充表 1D 只给结果），我们用的是"保出度与权重、只随机重排靶点"。
 * 能比的是**定性方向**：真实接线是否重要、参数扰动下结论是否还站得住。
 *
 * 用法：node dodge/measure_perturb.js   → results/dodge/perturb.json
 */
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, "..");
const SUB = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge/subcircuit_v2.json")));
const NT = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge/subcircuit_nt.json"))).nt;
const { ConnectomeBrain } = require(path.join(ROOT, "dodge/brain.js"));
const { createGame } = require(path.join(ROOT, "dodge/game_core.js"));

const SEEDS = [1, 2, 3], STEPS = 500, WARM = 250, DT = 0.005, HEAD = 1.3;
const MODES = ["sugar", "water", "groom"];

function run(mode, seed, apply) {
  const g = createGame(SUB, ConnectomeBrain, { seed, mode: "click",
    cfg: { autoPellets: false, autoDust: false, takeoff: "clip" } });
  g.brain.setNT(NT);
  if (apply) apply(g);
  if (mode === "groom") { g.addDust("left"); g.addDust("right"); }
  let acc = 0, n = 0;
  for (let i = 0; i < STEPS; i++) {
    if (mode !== "groom") {
      if (!g.pellets.length) g.addPellet(0, 0, mode);
      const p = g.pellets[0];
      p.x = g.S.x + Math.cos(g.S.h) * HEAD; p.y = g.S.y + Math.sin(g.S.h) * HEAD; p.amount = 1;
      g.S.thirst = 1;
    } else if (g.dust.length < 2) { g.dust.length = 0; g.addDust("left"); g.addDust("right"); }
    g.step(DT);
    if (i >= WARM) { const o = g.readout(); acc += mode === "groom" ? o.adn1 : o.mn9; n++; }
  }
  return acc / n;
}
const avg = (mode, apply) => SEEDS.reduce((a, s) => a + run(mode, s, apply), 0) / SEEDS.length;

const base = {};
for (const m of MODES) base[m] = avg(m, null);
console.log("基线（Hz）： " + MODES.map(m => `${m} ${base[m].toFixed(1)}`).join("   "));

const COND = [
  ["权重 −30%（表 11B）", g => g.setPerturb("weightScale", 0.7)],
  ["权重 +30%（表 11C）", g => g.setPerturb("weightScale", 1.3)],
  ["抑制 −30%（表 11D）", g => g.setPerturb("inhibScale", 0.7)],
  ["抑制 +30%（表 11E）", g => g.setPerturb("inhibScale", 1.3)],
  ["谷氨酸改兴奋性（表 11F）", g => g.setPerturb("glutExc", true)],
];
const rows = [];
console.log("\n扰动                        糖MN9   比值    水MN9   比值   梳理aDN1  比值");
for (const [name, ap] of COND) {
  const v = {}; for (const m of MODES) v[m] = avg(m, ap);
  rows.push({ 扰动: name, ...Object.fromEntries(MODES.flatMap(m =>
    [[m + "_hz", +v[m].toFixed(2)], [m + "_ratio", +(v[m] / base[m]).toFixed(3)]])) });
  console.log(name.padEnd(26) + MODES.map(m =>
    v[m].toFixed(1).padStart(7) + (v[m] / base[m]).toFixed(2).padStart(7)).join(""));
}

// ── 论文自己的判据：扰动之后**定性预测**是否不变 ────────────────────
// 表 11B–F 每行都有一列 "Same prediction as baseline?"。发放率变了多少不是论文的判据，
// 所以这里按论文口径再测一遍：10 个真实神经元的敲除判定（比值 ≤ 0.8 记为"必需"）在扰动前后是否一致。
const probe = createGame(SUB, ConnectomeBrain, { seed: 1, mode: "click" });
const KEYS = probe.NEURONS.map(r => r.key);
const CALL = 0.8;
function calls(apply) {
  const b = avg("sugar", apply);
  const o = {};
  for (const k of KEYS) {
    const v = avg("sugar", g => { if (apply) apply(g); g.setNeuronLesion(k, true); });
    o[k] = { ratio: +(v / b).toFixed(3), required: v / b <= CALL };
  }
  return o;
}
console.log("\n论文口径：扰动后敲除判定是否不变（比值 ≤ 0.8 = 必需）");
const baseCalls = calls(null);
console.log("  基线判必需： " + KEYS.filter(k => baseCalls[k].required).join(", "));
const robust = [];
for (const [name, ap] of COND) {
  const c = calls(ap);
  const same = KEYS.filter(k => c[k].required === baseCalls[k].required).length;
  const flipped = KEYS.filter(k => c[k].required !== baseCalls[k].required);
  robust.push({ 扰动: name, 判定不变: same, 总数: KEYS.length,
                翻转的: flipped.map(k => ({ key: k, 基线: baseCalls[k].ratio, 扰动后: c[k].ratio })) });
  console.log(`  ${name.padEnd(26)} ${same}/${KEYS.length} 不变`
    + (flipped.length ? `   翻转：${flipped.map(k => `${k}(${baseCalls[k].ratio}→${c[k].ratio})`).join(" ")}` : ""));
}

// 打乱接线：10 个种子，给均值 ± 标准差（论文表 1D 是 100 次）
const NSHUF = 10;
const shuf = Object.fromEntries(MODES.map(m => [m, []]));
for (let k = 0; k < NSHUF; k++)
  for (const m of MODES) shuf[m].push(run(m, 1, g => g.setPerturb("shuffle", true) || g.brain.setShuffle(true, 8000 + k)));
const mean = a => a.reduce((x, y) => x + y, 0) / a.length;
const sd = a => Math.sqrt(a.reduce((s, x) => s + (x - mean(a)) ** 2, 0) / Math.max(1, a.length - 1));
console.log(`\n打乱接线（${NSHUF} 次，论文表 1D 是 100 次）`);
const shufOut = {};
for (const m of MODES) {
  const mu = mean(shuf[m]), s = sd(shuf[m]);
  shufOut[m] = { 均值Hz: +mu.toFixed(2), 标准差: +s.toFixed(2), 比值: +(mu / base[m]).toFixed(3), 逐次: shuf[m].map(x => +x.toFixed(2)) };
  console.log(`  ${m.padEnd(7)} 正确接线 ${base[m].toFixed(1)} Hz  →  打乱后 ${mu.toFixed(1)} ± ${s.toFixed(1)} Hz   比值 ${(mu / base[m]).toFixed(3)}`);
}

fs.writeFileSync(path.join(ROOT, "results/dodge/perturb.json"), JSON.stringify({
  protocol: { seeds: SEEDS, steps: STEPS, warmup: WARM, dt: DT, head_offset_mm: HEAD, rate_hz: 200,
              note: "口径与 dodge/measure_neurons.js 相同；子回路 4,599 神经元，非全脑" },
  caveat: "论文在全脑上跑，且未公开打乱做法；这里只比定性方向，不声称复现定量结果",
  baseline_hz: Object.fromEntries(MODES.map(m => [m, +base[m].toFixed(2)])),
  perturbations: rows, shuffle: { n: NSHUF, paper_n: 100, ...shufOut },
  call_robustness: { call_threshold: CALL, baseline: baseCalls, per_perturbation: robust,
                     note: "论文表 11B–F 的判据是 Same prediction as baseline，即定性判定是否不变，不是发放率变化量" },
}, null, 1));
console.log("\n→ results/dodge/perturb.json");
