#!/usr/bin/env node
// 真脑各读出特征在 0.1 s 计数上的 Fano 因子（方差 / 均值）与等效单元数——响应面加噪声要按它来，不能一律按泊松（l2_diagnosis：按泊松高估噪声一倍，果蝇在水洼上待不住）。
// 用法：node eco/measure_fano.js → results/eco/readout_noise.json（110 个闭环工况输入 × 4 s，取会放电的特征）
const fs = require("fs"), path = require("path"), ROOT = path.resolve(__dirname, ".."), CH = require("./channels.js"), { ConnectomeBrain } = require("../dodge/brain.js");
const SUB = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge/subcircuit_v5.json"), "utf8")), B = CH.bind(SUB), M = JSON.parse(fs.readFileSync(path.join(ROOT, "results/eco/manifold_inputs.json"), "utf8"));
let s = 4242; const rnd = () => { s = (s * 1103515245 + 12345) >>> 0; return s / 4294967296; }; const IXm = Object.fromEntries(M.inputs.map((c, i) => [c, i])), shuf = a => a.slice().sort(() => rnd() - 0.5), X = [...shuf(M.X).slice(0, 60), ...shuf(M.X.filter(v => v[IXm.water] > 0)).slice(0, 25), ...shuf(M.X.filter(v => Math.max(v[IXm.lplc2_L], v[IXm.lplc2_R]) > 50)).slice(0, 15), ...shuf(M.X.filter(v => v[IXm.sugar] > 0)).slice(0, 10)],   /* 随机 60 + 有水 25 + 有逼近 15 + 有糖 10：让 MN9 / 巨纤维也有足够的样本 */ brain = new ConnectomeBrain(SUB, 17), cnt = new Float32Array(SUB.meta.n), F = CH.FEATURES;
const NUNIT = { dnaL: 1, dnaR: 1, mbonReward: 1, mbonPunish: 1 }; for (const f of F) if (!(f in NUNIT)) NUNIT[f] = B.feat[f] ? B.feat[f].length : 1;   // 求和型特征 = 1 个泊松单元；均值型 = 组里的神经元数
const acc = Object.fromEntries(F.map(f => [f, { sumF: 0, n: 0 }]));
for (const x of X) { brain.reset(); CH.INPUTS.forEach((c, j) => brain.setDrive(c, B.idx[c], x[j])); brain.run(1000); const ys = []; for (let t = 0; t < 40; t++) { cnt.fill(0); brain.run(1000, q => { cnt[q]++; }); ys.push(B.read(cnt, 0.1)); }
  for (const f of F) { const v = ys.map(y => y[f] * 0.1 * NUNIT[f]), m = v.reduce((a, b) => a + b, 0) / v.length; if (m < 0.3) continue; const va = v.reduce((a, b) => a + (b - m) * (b - m), 0) / (v.length - 1); acc[f].sumF += va / m; acc[f].n++; } }
const out = { window_s: 0.1, n_inputs: X.length, units: NUNIT, fano: Object.fromEntries(F.map(f => [f, acc[f].n ? +(acc[f].sumF / acc[f].n).toFixed(3) : null])), n_used: Object.fromEntries(F.map(f => [f, acc[f].n])) };
fs.writeFileSync(path.join(ROOT, "results/eco/readout_noise.json"), JSON.stringify(out, null, 1)); for (const f of F) console.log(f.padEnd(11), "单元", String(NUNIT[f]).padStart(3), "Fano", out.fano[f], `(n=${acc[f].n})`);
