#!/usr/bin/env node
// 生态箱 → 3D 大自然的无头运行（真脑 v5 + dodge/nature.js 的世界 + eco/overlay.js）。纯 CPU，约 1 倍实时，~300 MB / 进程，可以几个并行。
//   node eco/nature_harness.js collect <种子> <秒>          记下大自然里大脑实际收到的输入（白纸、边活边学）→ results/eco/manifold_nature_<种子>.json
//   node eco/nature_harness.js collect-merge                 → results/eco/manifold_nature.json（collect_manifold.js 会并入）
//   node eco/nature_harness.js run <arm> <种子> <秒>         arm = naive（白纸、不学）| trained（生态箱学成的权重，冻结）→ results/eco/nature_run_<arm>_<种子>.json
//   node eco/nature_harness.js probe <秒>                    接线自检：打印每秒的状态
const fs = require("fs"), path = require("path"), ROOT = path.resolve(__dirname, "..");
const { ConnectomeBrain } = require("../dodge/brain.js"), { createGame } = require("../dodge/game_core.js"), Legs = require("../dodge/legs.js"), Nature = require("../dodge/nature.js"), Overlay = require("./overlay.js"), Phys = require("./physiology.js");
const SUB = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge/subcircuit_v5.json"), "utf8")), GAIT = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge/gait.json"), "utf8")), CLIPS = JSON.parse(fs.readFileSync(path.join(ROOT, "results/flight/flight_clips.json"), "utf8")).clips;
const champion = () => { const c = JSON.parse(fs.readFileSync(path.join(ROOT, "results/eco/m2_champion.json"), "utf8")); return Object.fromEntries(Object.entries(c.P).map(([k, v]) => [k, Array.isArray(v) ? Float64Array.from(v) : v])); };
// 与页面里「大自然 · 五感全开」同一套配置；生态箱挂上之后用它自己的身体，所以 game_core 自带的 physiology（味觉增益那条手写调制）关掉；温 / 湿感受器分左右（fieldLR）
function make(seed, eco) { const g = createGame(SUB, ConnectomeBrain, { seed, mode: "manual", ballSpeed: 60, cfg: { encoding: "ache2019", lplc2Mu: 45, gfTau: 0.02, takeoff: "clip", autoPellets: false, autoDust: true, dustEvery: 40, wind: true, life: true, physiology: false, fieldLR: true, courtW: 0, touch: true, wallVision: false } });
  g.setFlightClips(CLIPS); g.attachLegs(Legs.create(GAIT)); g.attachWorld(Nature.create(seed)); g.attachEco(eco); return g; }
function live(seed, arm, seconds, record) { const eco = Overlay.create({ SUB, seed, learn: arm === "learn" ? "on" : "off", P: arm === "trained" ? champion() : null, record }), g = make(seed, eco), n = Math.round(seconds / g.chunkDt), t0 = Date.now(); let i = 0, px = g.S.x, py = g.S.y, dist = 0;
  for (; i < n && eco.alive; i++) { g.step(); dist += Math.hypot(g.S.x - px, g.S.y - py); px = g.S.x; py = g.S.y; }
  const p = eco.agent.phys, st = eco.stats, T = i * g.chunkDt; return { eco, g, row: { arm, seed, life_s: +T.toFixed(1), alive: eco.alive, cause: eco.cause, drink_s: +st.tDrink.toFixed(2), eat_s: +st.tEat.toFixed(2), rest_s: +st.tRest.toFixed(2), drinks: st.drinks, meals: st.meals, waterVisits: st.waterVisits, foodVisits: st.foodVisits, hits: st.bites,
    thirst_mean: +(st.thirstSum / Math.max(1, st.n)).toFixed(3), thirst_end: +p.thirst.toFixed(3), hunger_end: +p.hunger.toFixed(3), health_end: +p.health.toFixed(3), dist_mm: Math.round(dist), jumps: g.score.jump, wall_s: +((Date.now() - t0) / 1000).toFixed(0) } }; }
const mode = process.argv[2];
if (mode === "probe") { const eco = Overlay.create({ SUB, seed: 5, learn: "on" }), g = make(5, eco), T = +(process.argv[3] || 30), t0 = Date.now(); for (let i = 0; i < T / g.chunkDt; i++) { g.step(); if (i % Math.round(5 / g.chunkDt) === 0) { const p = eco.agent.phys, x = eco.agent.xin; console.log(`${(i * g.chunkDt).toFixed(0)} s  ${g.S.state}  饿 ${p.hunger.toFixed(2)} 渴 ${p.thirst.toFixed(2)} 体温 ${p.bodyTemp.toFixed(1)}  速度系数 ${eco.speedFactor.toFixed(2)}  输入非零 ${Array.from(x).filter(v => v > 0).length} 路  MN9 ${g.readout().mn9.toFixed(0)}  on ${g.onPellet ? g.onPellet.type : "-"}`); } }
  console.log(`${T} s 用时 ${((Date.now() - t0) / 1000).toFixed(1)} s`); }
else if (mode === "collect") { const seed = +process.argv[3], r = live(seed, "learn", +(process.argv[4] || 300), true); fs.writeFileSync(path.join(ROOT, `results/eco/manifold_nature_${seed}.json`), JSON.stringify({ seed, row: r.row, X: r.eco.record })); console.log(JSON.stringify(r.row), "记下", r.eco.record.length, "个输入"); }
else if (mode === "collect-merge") { const X = []; for (const f of fs.readdirSync(path.join(ROOT, "results/eco")).filter(f => /^manifold_nature_\d+\.json$/.test(f))) X.push(...JSON.parse(fs.readFileSync(path.join(ROOT, "results/eco", f), "utf8")).X); fs.writeFileSync(path.join(ROOT, "results/eco/manifold_nature.json"), JSON.stringify({ n: X.length, X })); console.log("合并", X.length, "个输入"); }
else if (mode === "run") { const arm = process.argv[3], seed = +process.argv[4], r = live(seed, arm, +(process.argv[5] || 900), false); fs.writeFileSync(path.join(ROOT, `results/eco/nature_run_${arm}_${seed}.json`), JSON.stringify(r.row)); console.log(JSON.stringify(r.row)); }
else console.log("用法见文件头");
