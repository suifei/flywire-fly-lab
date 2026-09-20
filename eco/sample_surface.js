#!/usr/bin/env node
// 让真脑（v5，15,055 个神经元）把输入空间采样跑一遍：每个样本 = 一组 26 通道的输入频率 → 100 ms 预热 + 300 ms 计数 → 12 个特征的发放率。
// 采样分布照着世界里会发生的样子：多数时候只有 0–3 类感觉同时在场，可以单侧、双侧相等、双侧不等。用法：node eco/sample_surface.js <分片 k> <共 K 片> <每片样本数>
// 输出 results/eco/surface_samples_<k>.json（4 片 × 900 个 ≈ 每片 5 分钟，可并行）
const fs = require("fs"), path = require("path"), ROOT = path.resolve(__dirname, "..");
const { ConnectomeBrain } = require("../dodge/brain.js"), CH = require("./channels.js");
const SUB = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge/subcircuit_v5.json"), "utf8")), B = CH.bind(SUB);
const k = +(process.argv[2] || 0), K = +(process.argv[3] || 1), N = +(process.argv[4] || 900), REPS = +(process.argv[5] || 1);   /* REPS > 1：同一组输入换种子重复，写 surface_test_<k>.json（量噪声天花板用，不参与训练） */
let s = (k * 7919 + 12345) >>> 0; const rnd = () => { s = (s + 0x6d2b79f5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
const X = [], Y = [], YREP = [], t0 = Date.now(), brain = new ConnectomeBrain(SUB, 1000 + k), cnt = new Float32Array(SUB.meta.n);
for (let i = 0; i < N; i++) {
  const x = Object.fromEntries(CH.INPUTS.map(c => [c, 0])), nf = [0, 1, 1, 1, 2, 2, 2, 3, 3, 4][Math.floor(rnd() * 10)], fams = CH.FAMILIES.slice().sort(() => rnd() - 0.5).slice(0, nf);
  for (const [f, max, two] of fams) { const u = Math.pow(rnd(), 0.7) * max; if (two === 1) { x[f] = u; continue; } const m = rnd(); if (m < 0.4) { x[f + "_L"] = u; x[f + "_R"] = u; } else if (m < 0.55) x[f + "_L"] = u; else if (m < 0.7) x[f + "_R"] = u; else { x[f + "_L"] = u; x[f + "_R"] = u * rnd(); if (rnd() < 0.5) [x[f + "_L"], x[f + "_R"]] = [x[f + "_R"], x[f + "_L"]]; } }
  if (fams.some(f => f[0] === "lc4") && rnd() < 0.7) { x.lplc2_L = x.lc4_L * (0.3 + 0.9 * rnd()); x.lplc2_R = x.lc4_R * (0.3 + 0.9 * rnd()); }          // 逼近时 LC4 与 LPLC2 总是一起来
  const reps = [];
  for (let r = 0; r < REPS; r++) { brain.reset(); brain.reseed(5000 + k * 100000 + i * 16 + r); for (const c of CH.INPUTS) brain.setDrive(c, B.idx[c], x[c]);
    brain.run(1000); cnt.fill(0); brain.run(3000, j => { cnt[j]++; }); const y = B.read(cnt, 0.3); reps.push(CH.FEATURES.map(f => +y[f].toFixed(2))); }
  X.push(CH.INPUTS.map(c => +x[c].toFixed(1))); Y.push(reps[0]); if (REPS > 1) YREP.push(reps);
  if (i % 100 === 99) console.log(`片 ${k}: ${i + 1}/${N}  ${((Date.now() - t0) / 1000).toFixed(0)} s`);
}
fs.writeFileSync(path.join(ROOT, `results/eco/surface_${REPS > 1 ? "test" : "samples"}_${k}.json`), JSON.stringify(Object.assign({ inputs: CH.INPUTS, features: CH.FEATURES, X, Y, settle_ms: 100, read_ms: 300 }, REPS > 1 ? { YREP, reps: REPS } : {})));
