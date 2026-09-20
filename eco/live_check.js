#!/usr/bin/env node
// 生态箱：真脑闭环复核。响应面是真脑的蒸馏（开环留出 R² 见 brain_surface.json）；这里查**闭环**：把 M2 里在响应面上学成的个体（冻结权重）放回真的 15,055 神经元脉冲网络里活。
// 用法：node eco/live_check.js （纯 CPU，~30–40 min，~300 MB）→ results/eco/live_check.json
// **事先写定**：3 个世界种子（6000–6002），观察上限 900 s。三个臂：live = 真脑 + 学成的权重；surface = 响应面 + 同一份权重；naive = 响应面 + 白纸（不学习）。
//   L1  live 臂寿命中位数 ≥ 1.5 × naive 臂（学到的东西换到真脑上还管用）
//   L2  live 臂的喝水时间占比在 surface 臂的 0.5–2 倍之内（行为量级一致）
//   真脑在两次决策之间保留自己的状态（不复位），读出按 ~300 ms 平滑；响应面没有记忆。这是两者原理上的差别，不是 bug。
const fs = require("fs"), path = require("path"), ROOT = path.resolve(__dirname, ".."), Sim = require("./sim.js"), Surf = require("./brain_surface.js"), Live = require("./brain_live.js"), CH = require("./channels.js"), Cards = require("./cards.js"), { ConnectomeBrain } = require("../dodge/brain.js");
const surf = Surf.create(JSON.parse(fs.readFileSync(path.join(ROOT, "results/eco/brain_surface.json"), "utf8"))), SUB = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge/subcircuit_v5.json"), "utf8"));
const champ = JSON.parse(fs.readFileSync(path.join(ROOT, "results/eco/m2_champion.json"), "utf8")), mkP = () => Object.fromEntries(Object.entries(champ.P).map(([k, v]) => [k, Array.isArray(v) ? Float64Array.from(v) : v]));
const CAP = 900, SEEDS = [6000, 6001, 6002], med = a => { a = a.slice().sort((x, y) => x - y); return a[a.length >> 1]; }, out = { protocol: { cap_s: CAP, seeds: SEEDS }, arms: {} };
function life(seed, brain, P) { const sim = Sim.create({}, { seed, brain, learn: "off", trail: false }), a = sim.spawn(null, P); let n = 0; const t0 = Date.now(); while (a.alive && n < CAP * 10) { sim.step(); n++; } if (a.alive) a.deathT = null; const L = Cards.lifeSummary(a, sim.world); L.wall_s = +((Date.now() - t0) / 1000).toFixed(0); return L; }
for (const arm of ["naive", "surface", "live"]) { const Ls = []; for (const seed of SEEDS) { const brain = arm === "live" ? Live.create(SUB, ConnectomeBrain, CH, seed) : surf, L = life(seed, brain, arm === "naive" ? null : mkP()); Ls.push(L); console.log(arm, seed, `${L.life} s`, L.alive ? "活着" : L.cause, `喝 ${L.drink} 吃 ${L.eat} 起跳 ${L.hops}`, `用时 ${L.wall_s} s`); }
  out.arms[arm] = { lives: Ls.map(L => ({ life: L.life, cause: L.alive ? "alive" : L.cause, drink: L.drink, eat: L.eat, hops: L.hops, drinks: L.drinks, waterVisits: L.waterVisits, wall_s: L.wall_s })), median_life: med(Ls.map(L => L.life)), median_drink: med(Ls.map(L => L.drink)), median_eat: med(Ls.map(L => L.eat)) }; }
const A = out.arms, ratio = A.live.median_life / A.naive.median_life, dr = A.surface.median_drink > 0 ? A.live.median_drink / A.surface.median_drink : null;
out.summary = { lives: SEEDS.length, cap_s: CAP, live_median: Math.round(A.live.median_life), surface_median: Math.round(A.surface.median_life), naive_median: Math.round(A.naive.median_life), ratio_live_vs_naive: +ratio.toFixed(2), drink_live: A.live.median_drink, drink_surface: A.surface.median_drink, drink_ratio: dr === null ? null : +dr.toFixed(2), L1: ratio >= 1.5, L2: dr !== null && dr >= 0.5 && dr <= 2 };
fs.writeFileSync(path.join(ROOT, "results/eco/live_check.json"), JSON.stringify(out, null, 1)); console.log(JSON.stringify(out.summary));
