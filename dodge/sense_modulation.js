#!/usr/bin/env node
/**
 * 嗅觉与内感受（ISN）单独刺激没有落到任何运动读出上（sensor_drive_v4.json）。但它们可能是**调制**性的：
 * 在吃糖 / 喝水 / 逼近刺激的同时加上它们，读出会不会变？每个条件 5 个种子 × 1 s，报告均值 ± SD。
 * 判「有调制」= 与不加时相比差 > 2 个 SD 且 > 20%（写在跑之前）。
 * 用法：node dodge/sense_modulation.js   → results/dodge/sense_modulation.json
 */
const fs = require("fs"), path = require("path"), ROOT = path.resolve(__dirname, "..");
const { ConnectomeBrain } = require("./brain.js");
const SUB = JSON.parse(fs.readFileSync(ROOT + "/results/dodge/subcircuit_v4.json", "utf8"));
const rate = (groups, seed) => { const b = new ConnectomeBrain(SUB, seed); for (const [g, hz] of groups) for (const s of ["left", "right"]) if (SUB.groups[g + "_" + s]) b.setRate(g + "_" + s, hz);
  const cnt = new Float32Array(b.n); b.run(Math.round(1000 / b.dt), i => { cnt[i]++; });
  const m = g => { const idx = (SUB.groups[g + "_left"] || []).concat(SUB.groups[g + "_right"] || []); return idx.reduce((a, i) => a + cnt[i], 0) / idx.length; };
  return { MN9: m("MN9"), GF: m("DNp01"), DNa: (m("DNa01") + m("DNa02")) / 2, aDN1: m("aDN1"), MDN: m("MDN") }; };
const stat = v => { const mu = v.reduce((a, x) => a + x, 0) / v.length, sd = Math.sqrt(v.reduce((a, x) => a + (x - mu) ** 2, 0) / (v.length - 1)); return { mean: +mu.toFixed(2), sd: +sd.toFixed(2) }; };
const BASES = { "吃糖（SUGAR 60 Hz）": [[["SUGAR", 60]], "MN9"], "逼近（LPLC2 60 Hz）": [[["LPLC2", 60]], "GF"], "碰触（TOUCH 100 Hz）": [[["TOUCH", 100]], "DNa"] };
const MODS = { "＋醋味 OLFA 200": ["OLFA", 200], "＋土臭素 OLFR 200": ["OLFR", 200], "＋饥渴 ISN 200": ["ISN", 200], "＋声音 AUDIO 60": ["AUDIO", 60] };
const out = { note: "5 个种子 × 1 s；判据：差 > 2 SD 且 > 20%", rows: [] };
for (const [bn, [base, key]] of Object.entries(BASES)) {
  const b0 = stat([1, 2, 3, 4, 5].map(s => rate(base, s)[key])); console.log(`${bn}：${key} = ${b0.mean} ± ${b0.sd} Hz`);
  for (const [mn, mod] of Object.entries(MODS)) { const r = stat([1, 2, 3, 4, 5].map(s => rate(base.concat([mod]), s)[key]));
    const diff = r.mean - b0.mean, sig = Math.abs(diff) > 2 * Math.max(b0.sd, r.sd, 0.5) && Math.abs(diff) > 0.2 * Math.max(b0.mean, 1);
    out.rows.push({ base: bn, readout: key, base_hz: b0, mod: mn, hz: r, diff: +diff.toFixed(2), modulates: sig });
    console.log(`   ${mn.padEnd(18)} ${r.mean} ± ${r.sd}   差 ${diff >= 0 ? "+" : ""}${diff.toFixed(1)} Hz  ${sig ? "← 有调制" : ""}`); } }
fs.writeFileSync(ROOT + "/results/dodge/sense_modulation.json", JSON.stringify(out, null, 1)); console.log("→ results/dodge/sense_modulation.json");
