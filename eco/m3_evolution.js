#!/usr/bin/env node
// 生态箱 M3：跨代进化。用法：node eco/m3_evolution.js [世界名]（不给 = 全部；每个世界 5 个种子 × 3 小时箱内时间，~10 min）→ results/eco/m3_evolution.json
//
// **事先写定的方案与判据**（docs/ecobox/PLAN.md 的 M3 验收线：「不同世界规则下，飞行倾向的演化方向不同——至少两种世界，方向相反或一升一平」）：
//   32 只同时跑，飞行作为**可决策的技能**解锁（起不起飞是决策；怎么飞是固定的 1.2 s / 72 mm 弹道——飞行控制没接进连接组，见 AUDIT.md）。
//   奠基者基因全部取默认值（飞行倾向 −4，四个先天偏置 0）。三个世界，各 5 个种子（11–15），各跑 10,800 s：
//     beetles  甲虫横行：8 只甲虫、速度 10 mm/s            calm  风平浪静：没有甲虫            sparse  地广物稀：箱子半径 300、食物 14、水 3、没有甲虫
//     其余相同：半径 200、食物 30、水 6。
//   每次运行的 Δ = 最后 20% 时间里种群平均飞行倾向 − 奠基值（−4）。一个世界的标签：≥4/5 个种子 Δ > +0.5 →「升」；≥4/5 个种子 Δ < −0.5 →「降」；否则「平」。
//   M3 判据：三个世界里至少有两个标签不同。
//   只报告、不设判据：其余 9 个基因的走向、每代寿命、死因构成、迁入数（种群快灭绝时从名人堂补进来的，单独计数）、发现卡。
const fs = require("fs"), path = require("path"), ROOT = path.resolve(__dirname, "..");
const Evolve = require("./evolve.js"), Surf = require("./brain_surface.js"), Sim = require("./sim.js");
const brain = Surf.create(JSON.parse(fs.readFileSync(path.join(ROOT, "results/eco/brain_surface.json"), "utf8")));
const BASE = { size: 200, food: 30, water: 6 }, WORLDS = { beetles: Object.assign({}, BASE, { predators: 8, predatorSpeed: 10 }), calm: Object.assign({}, BASE, { predators: 0 }), sparse: { size: 300, food: 14, water: 3, predators: 0 } };
const NAMES = { beetles: "甲虫横行", calm: "风平浪静", sparse: "地广物稀" }, SEEDS = [11, 12, 13, 14, 15], T = 10800, F0 = Sim.GENES.flightBias, mean = a => a.reduce((s, x) => s + x, 0) / Math.max(1, a.length);
const file = path.join(ROOT, "results/eco/m3_evolution.json"), out = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf8")) : { protocol: { n: 32, seconds: T, seeds: SEEDS, founder_flightBias: F0, up: "+0.5", down: "-0.5", need: "4/5" }, worlds: {} };
for (const w of (process.argv[2] ? [process.argv[2]] : Object.keys(WORLDS))) { const runs = [], t0 = Date.now();
  for (const seed of SEEDS) { const E = Evolve.create(WORLDS[w], { seed, brain }); E.run(T); const tl = E.timeline, tail = tl.slice(Math.floor(tl.length * 0.8)), g = {}; for (const k of Evolve.GENE_KEYS) g[k] = +mean(tail.map(b => b.genes[k])).toFixed(4);
    const deaths = {}; tl.forEach(b => { for (const c in b.deaths) deaths[c] = (deaths[c] || 0) + b.deaths[c]; }); const lifeTail = tail.filter(b => b.meanLife !== null).map(b => b.meanLife), lifeHead = tl.slice(0, Math.ceil(tl.length * 0.2)).filter(b => b.meanLife !== null).map(b => b.meanLife);
    runs.push({ seed, delta_flight: +(g.flightBias - F0).toFixed(4), genes_tail: g, lives: E.lives, births: E.births, immigrants: E.immigrants, gen_max: tl[tl.length - 1].genMax, pop_tail: +mean(tail.map(b => b.pop)).toFixed(1), mean_life_head: +mean(lifeHead).toFixed(1), mean_life_tail: +mean(lifeTail).toFixed(1),
      flights_per_fly_min_tail: +(mean(tail.map(b => b.flights / Math.max(1, b.pop))) ).toFixed(3), deaths, cards: E.cards.map(c => ({ key: c.key, title: c.title, kind: c.kind, count: c.count })), timeline: tl.filter((b, i) => i % 5 === 4).map(b => ({ t: b.t, pop: b.pop, gen: b.gen, flightBias: b.genes.flightBias, drink: b.genes.innateTurn2, learnRate: b.genes.learnRate, meanLife: b.meanLife })) });
    console.log(`${NAMES[w]} 种子 ${seed}: Δ飞行倾向 ${runs[runs.length - 1].delta_flight}  代数 ${runs[runs.length - 1].gen_max}  寿命 ${runs[runs.length - 1].mean_life_head} → ${runs[runs.length - 1].mean_life_tail} s  迁入 ${E.immigrants}  先天喝水 ${g.innateTurn2}  学习率 ${g.learnRate}`); }
  const up = runs.filter(r => r.delta_flight > 0.5).length, down = runs.filter(r => r.delta_flight < -0.5).length;
  out.worlds[w] = { name: NAMES[w], rules: WORLDS[w], runs, n_up: up, n_down: down, label: up >= 4 ? "升" : down >= 4 ? "降" : "平", delta_mean: +mean(runs.map(r => r.delta_flight)).toFixed(3), seconds: +((Date.now() - t0) / 1000).toFixed(0) };
  console.log(`→ ${NAMES[w]}：${out.worlds[w].label}（升 ${up}/5，降 ${down}/5，Δ 均值 ${out.worlds[w].delta_mean}）`); fs.writeFileSync(file, JSON.stringify(out)); }
if (Object.keys(out.worlds).length === 3) { const labels = Object.values(out.worlds).map(w => w.label); out.criterion = { labels: Object.fromEntries(Object.entries(out.worlds).map(([k, w]) => [k, w.label])), pass: new Set(labels).size >= 2 }; fs.writeFileSync(file, JSON.stringify(out)); console.log("M3 判据：", out.criterion.pass ? "通过" : "未通过", JSON.stringify(out.criterion.labels)); }
