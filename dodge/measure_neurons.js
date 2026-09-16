#!/usr/bin/env node
/**
 * 量出页面“敲神经元”那一排开关上标的比值，使其可复现。
 *
 * 背景：这些神经元来自报告 §14–24 的全脑虚拟敲除筛选，但游戏子回路只有 4,599 个神经元（全脑的 3%），
 * 敲除效果与全脑并不一致。页面上每个开关同时标“子回路实测值”和“全脑筛选值”，这个脚本负责前者。
 *
 * 口径（写死在这里，改了要同时改页面说明）：
 *   - 走游戏真实通路：把颗粒钉在头部正前方 1.3 mm（= CFG.headOffset）持续接触 → contactInput() 注入 200 Hz。
 *     糖粒刺激全部 122 个 LB3；水滴只刺激其中 17 个水味觉 GRN（报告 §19）。
 *   - 梳理用 aDN1：左右触角各落一粒灰 → JO 200 Hz，读出 aDN1。
 *   - 每条件 2.5 s（500 步 × 5 ms），取后 1.25 s 平均，3 个种子（1/2/3）取平均。
 *   - 口渴固定为 1（只为让水滴那一路也能进入 feed 状态；读出的是 MN9 发放率本身，与状态无关）。
 *   - 比值 = 敲除后 ÷ 不敲除，与全脑筛选同一定义（切断传出突触）。
 * 输出 results/dodge/neuron_ratios.json
 * 用法：node dodge/measure_neurons.js
 */
const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "..");
const SUB = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge/subcircuit_v2.json")));
const { ConnectomeBrain } = require(path.join(ROOT, "dodge/brain.js"));
const { createGame } = require(path.join(ROOT, "dodge/game_core.js"));

const SEEDS = [1, 2, 3], STEPS = 500, WARM = 250, DT = 0.005, HEAD = 1.3;

function run(mode, seed, ko) {
  const g = createGame(SUB, ConnectomeBrain, { seed, mode: "click",
    cfg: { autoPellets: false, autoDust: false, takeoff: "clip" } });
  if (ko) g.setNeuronLesion(ko, true);
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
const avg = (mode, ko) => SEEDS.reduce((a, s) => a + run(mode, s, ko), 0) / SEEDS.length;

const MODES = ["sugar", "water", "groom"];
const base = {};
for (const m of MODES) base[m] = avg(m, null);
console.log("基线（Hz）：" + MODES.map(m => `${m} ${base[m].toFixed(1)}`).join("，"));

const probe = createGame(SUB, ConnectomeBrain, { seed: 1, mode: "click" });
const out = { protocol: { seeds: SEEDS, steps: STEPS, warmup: WARM, dt: DT, head_offset_mm: HEAD,
                          rate_hz: 200, note: "颗粒钉在头前持续接触；梳理用双侧落灰；取后 1.25 s 平均" },
              baseline_hz: Object.fromEntries(MODES.map(m => [m, +base[m].toFixed(2)])),
              n_water_grn: probe.waterIdx.length, neurons: [] };
console.log("\n神经元        类型          糖    水    梳理   全脑(糖)");
for (const rec of probe.NEURONS) {
  const r = {};
  for (const m of MODES) r[m] = +(avg(m, rec.key) / base[m]).toFixed(3);
  out.neurons.push({ key: rec.key, cell_type: rec.type, n_in_subcircuit: rec.idx.length,
                     sugar: r.sugar, water: r.water, groom_adn1: r.groom, full_brain_sugar: rec.full });
  console.log(`${rec.key.padEnd(12)} ${String(rec.type).padEnd(12)} ${r.sugar.toFixed(2).padStart(5)} ` +
              `${r.water.toFixed(2).padStart(5)} ${r.groom.toFixed(2).padStart(5)} ${String(rec.full).padStart(8)}`);
}
// 配对：页面上写明的那两对
out.pairs = [];
for (const pr of probe.NEURON_PAIRS) {
  const [a, b] = pr.keys;
  const ra = avg("sugar", a) / base.sugar, rb = avg("sugar", b) / base.sugar;
  const g = createGame(SUB, ConnectomeBrain, { seed: 1, mode: "click" });
  const both = SEEDS.reduce((acc, seed) => {
    const gg = createGame(SUB, ConnectomeBrain, { seed, mode: "click",
      cfg: { autoPellets: false, autoDust: false, takeoff: "clip" } });
    gg.setNeuronLesion(a, true); gg.setNeuronLesion(b, true);
    let s = 0, n = 0;
    for (let i = 0; i < STEPS; i++) {
      if (!gg.pellets.length) gg.addPellet(0, 0, "sugar");
      const p = gg.pellets[0];
      p.x = gg.S.x + Math.cos(gg.S.h) * HEAD; p.y = gg.S.y + Math.sin(gg.S.h) * HEAD; p.amount = 1;
      gg.step(DT);
      if (i >= WARM) { s += gg.readout().mn9; n++; }
    }
    return acc + s / n;
  }, 0) / SEEDS.length / base.sugar;
  out.pairs.push({ a, b, ratio_a: +ra.toFixed(3), ratio_b: +rb.toFixed(3), ratio_ab: +both.toFixed(3),
                   expected: +(ra * rb).toFixed(3), delta: +((1 - both) - (1 - ra * rb)).toFixed(3) });
  console.log(`配对 ${a}+${b}：各自 ${ra.toFixed(2)}/${rb.toFixed(2)} → 一起 ${both.toFixed(2)}（独立预期 ${(ra * rb).toFixed(2)}）`);
}
const dst = path.join(ROOT, "results/dodge/neuron_ratios.json");
fs.writeFileSync(dst, JSON.stringify(out, null, 1));
console.log("\n写入", dst);
