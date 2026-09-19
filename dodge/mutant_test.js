#!/usr/bin/env node
/**
 * 突变体诊断模式的底稿：**十个真实神经元，各自敲掉之后行为上看得出来吗？**
 *
 * 这不是为了做玩法才测的——它本身就是本项目反复强调的那条结论的行为版：
 * **单敲除常常什么也看不出来**（全脑筛选里 312 个活跃神经元只有 12 个能算备份通路）。
 * 所以「盲盒突变体」这个玩法必须先知道哪些盲盒是可解的，哪些无解。
 *
 * 协议（一次跑完三条通路）：60 s × 3 种子，自动发球 + 每 3 s 轮换糖/水颗粒 + 每 3 s 落灰。
 * 指标：吃糖时长、喝水时长、喝水时 MN9 峰值、梳理次数、起跳次数、闪避率。
 * 判「可诊断」：某个指标与「不敲」的三次区间**完全不重叠**（保守，不做统计检验，n=3）。
 *
 * 用法：node dodge/mutant_test.js [每局秒数=60] [种子数=3]
 * 输出：results/dodge/mutants.json；SUB=subcircuit_v3 时写 mutants_v3.json
 */
const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "..");
// 子回路用 SUB 环境变量切换（默认 v2）；输出文件名跟着走，免得覆盖已发布的 v2 数字
const SUF = (process.env.SUB && process.env.SUB !== "subcircuit_v2") ? "_" + process.env.SUB.replace("subcircuit_", "") : "";
const { ConnectomeBrain } = require("./brain.js");
const { createGame } = require("./game_core.js");
const SUB = JSON.parse(fs.readFileSync(ROOT + "/results/dodge/" + (process.env.SUB || "subcircuit_v2") + ".json", "utf8"));
const CLIPS = JSON.parse(fs.readFileSync(ROOT + "/results/flight/flight_clips.json", "utf8")).clips;
const T = +(process.argv[2] || 60), SEEDS = +(process.argv[3] || 3);
const KEYS = ["Roundup", "G2N-1", "Clavicle", "CB0277", "CB0051", "Zorro", "Phantom", "Rattle", "CB0883", "aBN1"];

function play(key, seed) {
  const g = createGame(SUB, ConnectomeBrain, { seed, ballSpeed: 60,
    cfg: { encoding: "ache2019", gfTau: 0.02, takeoff: "clip",
           autoPellets: true, pelletEvery: 3, pelletTypes: ["sugar", "water"], autoDust: true, dustEvery: 3 } });
  g.setFlightClips(CLIPS);
  g.S.thirst = 0.8;
  if (key) g.setNeuronLesion(key, true);
  let waterPeak = 0, sugarFeed = 0, waterFeed = 0, prevFeed = 0;
  const n = Math.round(T / g.chunkDt);
  for (let i = 0; i < n; i++) {
    g.step();
    const dF = g.score.feed_s - prevFeed; prevFeed = g.score.feed_s;
    if (dF > 0 && g.onPellet) {
      if (g.onPellet.type === "water") { waterFeed += dF; waterPeak = Math.max(waterPeak, g.readout().mn9 || 0); }
      else sugarFeed += dF;
    }
  }
  const s = g.score, dec = s.dodge + s.hit;
  return { sugarFeedS: +sugarFeed.toFixed(2), waterFeedS: +waterFeed.toFixed(2), waterMn9Peak: +waterPeak.toFixed(1),
           groom: s.groom, jump: s.jump, dodgeRate: dec ? +(s.dodge / dec).toFixed(3) : null };
}

const METRICS = ["sugarFeedS", "waterFeedS", "waterMn9Peak", "groom", "jump", "dodgeRate"];
const runs = {};
const t0 = Date.now();
for (const key of [null, ...KEYS]) {
  runs[key || "intact"] = Array.from({ length: SEEDS }, (_, i) => play(key, i + 1));
  const r = runs[key || "intact"];
  const mean = m => { const v = r.map(x => x[m]).filter(x => typeof x === "number");
    return v.length ? +(v.reduce((a, b) => a + b, 0) / v.length).toFixed(2) : null; };
  console.log((key || "不敲").padEnd(12) + METRICS.map(m => m + " " + mean(m)).join("  "));
}
const range = (rs, m) => { const v = rs.map(x => x[m]).filter(x => typeof x === "number");
  return v.length ? [Math.min(...v), Math.max(...v)] : null; };
const base = Object.fromEntries(METRICS.map(m => [m, range(runs.intact, m)]));
const out = { seconds_per_seed: T, seeds: SEEDS, metrics: METRICS,
  note: "判「可诊断」= 该指标三次的区间与不敲的三次区间完全不重叠（保守，n=3，不做统计检验）",
  intact: { runs: runs.intact, range: base }, mutants: [] };
for (const key of KEYS) {
  const rs = runs[key], tells = [];
  for (const m of METRICS) {
    const a = range(rs, m), b = base[m];
    if (!a || !b) continue;
    if (a[1] < b[0]) tells.push({ metric: m, dir: "低", ours: a, intact: b });
    else if (a[0] > b[1]) tells.push({ metric: m, dir: "高", ours: a, intact: b });
  }
  out.mutants.push({ key, runs: rs, tells, diagnosable: tells.length > 0 });
  console.log(`${key.padEnd(12)}${tells.length ? "可诊断：" + tells.map(t => t.metric + " 偏" + t.dir).join("、") : "行为上看不出来"}`);
}
out.n_diagnosable = out.mutants.filter(m => m.diagnosable).length;
fs.writeFileSync(ROOT + "/results/dodge/mutants" + SUF + ".json", JSON.stringify(out, null, 1));
console.log(`\n${out.n_diagnosable}/${KEYS.length} 个能从行为看出来。用时 ${((Date.now() - t0) / 1000).toFixed(0)} s → results/dodge/mutants${SUF}.json`);
