#!/usr/bin/env node
// 生态箱：采「闭环工况」——果蝇真的活着的时候，大脑实际收到的是哪些输入。随机输入（sample_surface.js 的默认模式）覆盖得很散，
//   恰恰在决策最要紧的几个工作点（只有水味、糖 + 醋味、逼近 + 声音……）样本太少：第一版响应面在「尝到水」上给 MN9 7–9 Hz，真脑是 13 Hz，闭环里喝水时间差了 4 倍。
// 用法：node eco/collect_manifold.js → results/eco/manifold_inputs.json（输入向量，按「哪几类感觉同时在场」分层抽样）；
//   然后 for k in 20 21 22 23; do node eco/sample_surface.js $k 4 0 1 results/eco/manifold_inputs.json & done   让真脑在这些输入上作答
//   可选第二个来源：results/eco/manifold_nature.json（3D 大自然里记下来的输入，eco/nature_harness.js 写的），存在就一并并入
const fs = require("fs"), path = require("path"), ROOT = path.resolve(__dirname, ".."), Sim = require("./sim.js"), Evolve = require("./evolve.js"), Surf = require("./brain_surface.js"), CH = require("./channels.js"), World = require("./world.js");
const brain = Surf.create(JSON.parse(fs.readFileSync(path.join(ROOT, "results/eco/brain_surface.json"), "utf8"))), PER_SIG = +(process.argv[2] || 60), seen = new Map();
const FAM = CH.FAMILIES.map(f => f[0]), IX = Object.fromEntries(CH.INPUTS.map((c, i) => [c, i]));
function record(x) { let sig = ""; for (const f of FAM) { const on = IX[f] !== undefined ? x[IX[f]] > 1 : (x[IX[f + "_L"]] > 1 || x[IX[f + "_R"]] > 1); if (on) sig += f + "+"; } if (!sig) return; let b = seen.get(sig); if (!b) seen.set(sig, b = { n: 0, keep: [] }); b.n++;
  const v = Array.from(x, q => Math.round(q)); if (b.keep.length < PER_SIG) b.keep.push(v); else { const j = Math.floor(rnd() * b.n); if (j < PER_SIG) b.keep[j] = v; } }     // 蓄水池抽样：每种组合最多留 PER_SIG 个
let s = 987654321; const rnd = () => { s = (s + 0x6d2b79f5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
// 单只：学着活（同一个体连续几条命），几种世界
for (const [name, v] of Object.entries(World.PRESETS)) { let P = null; for (let life = 0; life < 6; life++) { const sim = Sim.create(v[1], { seed: 70000 + life, brain, learn: "on", trail: false }), a = sim.spawn(null, P); P = a.P; let n = 0; while (a.alive && n < 12000) { sim.step(); n++; if (n % 3 === 0) record(a.xin); } } console.log("单只", name, "→ 组合数", seen.size); }
// 种群：32 只、飞行解锁
for (const name of ["beetles", "mild", "sparse"]) { const E = Evolve.create(World.PRESETS[name][1], { seed: 71000, brain }); for (let i = 0; i < 24000; i++) { E.step(); if (i % 5 === 0) for (const a of E.sim.agents) if (a.alive) record(a.xin); } console.log("种群", name, "→ 组合数", seen.size); }
const nat = path.join(ROOT, "results/eco/manifold_nature.json"); let nNat = 0; if (fs.existsSync(nat)) { for (const v of JSON.parse(fs.readFileSync(nat, "utf8")).X) { record(Float32Array.from(v)); nNat++; } console.log("并入大自然里记下的输入", nNat, "→ 组合数", seen.size); }
const X = [], sigs = []; for (const [sig, b] of seen) { for (const v of b.keep) X.push(v); sigs.push([sig.slice(0, -1), b.n, b.keep.length]); } sigs.sort((a, b) => b[1] - a[1]);
fs.writeFileSync(path.join(ROOT, "results/eco/manifold_inputs.json"), JSON.stringify({ inputs: CH.INPUTS, per_signature_cap: PER_SIG, n: X.length, n_signatures: sigs.length, from_nature: nNat, signatures: sigs, X }));
console.log(`写了 ${X.length} 个输入向量，${sigs.length} 种感觉组合；最常见的：`, sigs.slice(0, 6).map(q => q[0] + "×" + q[1]).join("  "));
