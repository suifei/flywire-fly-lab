#!/usr/bin/env node
/**
 * 任务模式自检：每一关都实测两种情况——**不干预** 与 **参考解**——各跑若干种子；
 * 标了 `singles` 的关卡还会把参考解里的每个开关**单独**跑一遍（用来展示协同）。
 *
 * 为什么必须这么测：一关如果不干预也能过，它就没在考任何东西；参考解如果过不了，
 * 那这关就是不可能完成的。两头都要有数。missions.js 里的通过线就是照这份实测定的。
 *
 * 用法：node dodge/mission_test.js [每局秒数=60] [种子数=3]
 * 输出：results/dodge/missions.json（页面从这里读，不手抄数字）；SUB=subcircuit_v3 时写 missions_v3.json
 */
const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "..");
// 子回路用 SUB 环境变量切换（默认 v2）；输出文件名跟着走，免得覆盖已发布的 v2 数字
const SUF = (process.env.SUB && process.env.SUB !== "subcircuit_v2") ? "_" + process.env.SUB.replace("subcircuit_", "") : "";
const { ConnectomeBrain } = require("./brain.js");
const { createGame } = require("./game_core.js");
const { MISSIONS, applyKeys } = require("./missions.js");
const SUB = JSON.parse(fs.readFileSync(ROOT + "/results/dodge/" + (process.env.SUB || "subcircuit_v2") + ".json", "utf8"));
const CLIPS = JSON.parse(fs.readFileSync(ROOT + "/results/flight/flight_clips.json", "utf8")).clips;
const T = +(process.argv[2] || 60), SEEDS = +(process.argv[3] || 3);
// 页面默认档位：Ache 2019 编码 + 真实逃逸飞行片段；关卡可以用 cfg 覆盖
const BASE = { encoding: "ache2019", gfTau: 0.02, takeoff: "clip" };

function play(m, keys, seed) {
  const g = createGame(SUB, ConnectomeBrain, { seed, ballSpeed: 60, cfg: Object.assign({}, BASE, m.cfg || {}) });
  g.setFlightClips(CLIPS);
  // 光遗传关卡要用的目标集合（页面上就是那几个可点的按钮）
  g.optoTargets = { LC4_LPLC2_left: (SUB.groups.LC4_left || []).concat(SUB.groups.LPLC2_left || []),
                    LC4_LPLC2_right: (SUB.groups.LC4_right || []).concat(SUB.groups.LPLC2_right || []),
                    SUGAR: (SUB.groups.SUGAR_left || []).concat(SUB.groups.SUGAR_right || []),
                    JO_left: SUB.groups.JO_left || [],
                    LC16: (SUB.groups.LC16_left || []).concat(SUB.groups.LC16_right || []) };
  if (m.init) m.init(g);
  applyKeys(g, keys);
  const noServe = m.cfg && m.cfg.autoServe === false;
  if (noServe) g.mode = "click";                      // 不自动发球
  const n = Math.round(T / g.chunkDt), acc = {};
  for (let i = 0; i < n; i++) {
    g.step();
    if (m.tick) m.tick(g, acc);
    if (keys === "REF" && m.refAct) m.refAct(g, g.S.t);
  }
  return m.metrics(g, acc);
}

const mean = (rs, k) => {
  const v = rs.map(r => r[k]).filter(x => typeof x === "number");
  return v.length ? +(v.reduce((a, b) => a + b, 0) / v.length).toFixed(3) : null;
};

const t0 = Date.now();
const out = { seconds_per_seed: T, seeds: SEEDS, ball_speed: 60, base_cfg: BASE,
  note: "每关两种情况各跑 " + SEEDS + " 个种子；通过线写在 missions.js 里，是照这份实测定的",
  missions: [] };
for (const m of MISSIONS) {
  const arms = { none: [], ref: [] };
  for (let seed = 1; seed <= SEEDS; seed++) {
    arms.none.push(play(m, [], seed));
    // refAct 关卡靠脚本化动作而不是开关，用 "REF" 这个标记告诉 play 去执行它
    arms.ref.push(play(m, m.refKeys.length ? m.refKeys : "REF", seed));
  }
  if (m.singles) for (const k of m.refKeys) {
    arms["single_" + k.split(":")[1]] = Array.from({ length: SEEDS }, (_, i) => play(m, [k], i + 1));
  }
  const keys = Object.keys(arms.ref[0]);
  const summ = rs => ({ pass: rs.filter(r => m.pass(r)).length, of: SEEDS,
                        mean: Object.fromEntries(keys.map(k => [k, mean(rs, k)])), runs: rs });
  const rec = { id: m.id, title: m.title, basis: m.basis, goal: m.goal, line: m.line, why: m.why,
                brief: m.brief, hint: m.hint, refKeys: m.refKeys, calibrated: !!m.calibrated, arms: {} };
  for (const [name, rs] of Object.entries(arms)) rec.arms[name] = summ(rs);
  rec.discriminating = rec.arms.ref.pass === SEEDS && rec.arms.none.pass === 0;
  if (m.singles) rec.singles_pass = Object.entries(rec.arms).filter(([k]) => k.startsWith("single_"))
    .map(([k, v]) => `${k.slice(7)} ${v.pass}/${SEEDS}`).join("，");
  out.missions.push(rec);
  const fmt = o => keys.map(k => `${k} ${o.mean[k]}`).join("  ");
  console.log(`${m.title.padEnd(10, "　")} 参考解 ${rec.arms.ref.pass}/${SEEDS}  不干预 ${rec.arms.none.pass}/${SEEDS}` +
    (rec.singles_pass ? `  单敲 ${rec.singles_pass}` : "") + `  ${rec.discriminating ? "✓ 有区分度" : "← 需要调整"}`);
  console.log(`    参考解：${fmt(rec.arms.ref)}`);
  console.log(`    不干预：${fmt(rec.arms.none)}`);
  for (const [k, v] of Object.entries(rec.arms)) if (k.startsWith("single_")) console.log(`    单敲 ${k.slice(7)}：${fmt(v)}`);
}
const bad = out.missions.filter(m => !m.discriminating);
out.all_discriminating = bad.length === 0;
fs.writeFileSync(ROOT + "/results/dodge/missions" + SUF + ".json", JSON.stringify(out, null, 1));
console.log(`\n用时 ${((Date.now() - t0) / 1000).toFixed(0)} s，写入 results/dodge/missions${SUF}.json`);
if (bad.length) { console.log("没有区分度的关卡：" + bad.map(m => m.title).join("、")); process.exit(1); }
