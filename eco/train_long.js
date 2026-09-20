#!/usr/bin/env node
// 生态箱：长期训练任务。目标（用户 2026-09-20 定的）：**10 个独立个体 10/10 学成**。用法：node eco/train_long.js [最多轮数=30]   纯 CPU，可后台，可中断续跑
//   → results/eco/train_long.json（汇总）+ results/eco/train_long_state.json（续跑用的完整状态；删掉它 = 从头来）
//
// **事先写定的规则**：
//   个体：10 个，训练世界种子基数 40000 + 1000·k（与 M2 的 2000–4000、定超参用的 20000 起、测试用的 5000 起都不重叠）；默认世界规则；飞行关闭。
//   一轮 = 连续 10 条命（可塑性层跨命保留，每条命观察上限 1,800 s）。每轮结束后**冻结学习**，在 20 个没见过的世界（种子 5000–5019）上测。
//   「学成」= 冻结测试的寿命中位数 ≥ 1.5 × 不学习的果蝇在同样 20 个世界上的中位数。学成的个体毕业、不再训练；没学成的进下一轮，最多 maxRounds 轮。
//   另外记录（不设判据）：毕业时是第几轮、测试时的行为占比、有没有塌进贴墙 / 躺平（发现卡的阈值）、毕业后再测一次换 20 个新世界（种子 5100–5119）看成绩稳不稳。
//   任务成功 = 10/10 学成，**且**换新世界复测仍然 10/10。没达到就照实写几比几、卡在哪种作弊上。
const fs = require("fs"), path = require("path"), ROOT = path.resolve(__dirname, ".."), Sim = require("./sim.js"), Surf = require("./brain_surface.js"), Plastic = require("./plastic.js"), Cards = require("./cards.js"), Phys = require("./physiology.js");
const brain = Surf.create(JSON.parse(fs.readFileSync(path.join(ROOT, "results/eco/brain_surface.json"), "utf8"))), MAXR = +(process.argv[2] || 30), PER = 10, CAP = 1800, NT = 20, N = 10;
const med = a => { a = a.slice().sort((x, y) => x - y); const n = a.length; return n % 2 ? a[n >> 1] : (a[n / 2 - 1] + a[n / 2]) / 2; }, SF = path.join(ROOT, "results/eco/train_long_state.json"), OF = path.join(ROOT, "results/eco/train_long.json");
const pack = P => Object.fromEntries(Object.entries(P).map(([k, v]) => [k, v instanceof Float64Array ? { f64: Array.from(v) } : v])), unpack = o => Object.fromEntries(Object.entries(o).map(([k, v]) => [k, v && v.f64 ? Float64Array.from(v.f64) : v]));
function life(seed, learn, P) { const sim = Sim.create({}, { seed, brain, learn, trail: false }), a = sim.spawn(null, P); let n = 0; while (a.alive && n < CAP * 10) { sim.step(); n++; } if (a.alive) a.deathT = null; return { P: a.P, L: Cards.lifeSummary(a, sim.world) }; }
function test(P, base) { const Ls = []; for (let i = 0; i < NT; i++) Ls.push(life(base + i, "off", P ? unpack(pack(P)) : null).L); return { median: med(Ls.map(L => L.life)), drink: +med(Ls.map(L => L.drink)).toFixed(3), eat: +med(Ls.map(L => L.eat)).toFixed(3), wall: +med(Ls.map(L => L.wall)).toFixed(3), rest: +med(Ls.map(L => L.rest)).toFixed(3),
  alive: Ls.filter(L => L.alive).length, causes: Ls.reduce((o, L) => { const c = L.alive ? "alive" : L.cause; o[c] = (o[c] || 0) + 1; return o; }, {}) }; }
let S = fs.existsSync(SF) ? JSON.parse(fs.readFileSync(SF, "utf8")) : null;
if (!S) { console.log("测不学习的基线 …"); S = { baseline: test(null, 5000), baseline2: test(null, 5100), inds: Array.from({ length: N }, (_, k) => ({ k, base: 40000 + 1000 * k, rounds: 0, P: null, learned: false, history: [] })), started: new Date().toISOString() }; }
const need = 1.5 * S.baseline.median; console.log(`基线（不学习）：${S.baseline.median.toFixed(0)} s → 学成线 ${need.toFixed(0)} s`);
const save = () => { fs.writeFileSync(SF, JSON.stringify(S)); const inds = S.inds.map(d => ({ k: d.k, base: d.base, learned: d.learned, rounds: d.rounds, lives: d.rounds * PER, last: d.history[d.history.length - 1] || null, retest: d.retest || null, history: d.history.map(h => ({ round: h.round, median: h.median, wall: h.wall, rest: h.rest, drink: h.drink })) }));
  const out = { rule: { individuals: N, lives_per_round: PER, max_rounds: MAXR, cap_s: CAP, test_worlds: NT, threshold: "1.5 × 不学习的测试寿命中位数", test_seeds: "5000–5019", retest_seeds: "5100–5119" }, baseline_median: S.baseline.median, baseline_retest_median: S.baseline2.median, need_s: +need.toFixed(1),
    n_learned: inds.filter(d => d.learned).length, n_retest_ok: inds.filter(d => d.retest && d.retest.ok).length, n: N, total_lives: inds.reduce((s, d) => s + d.lives, 0), rounds_to_learn: inds.filter(d => d.learned).map(d => d.rounds), individuals: inds,
    stuck: inds.filter(d => !d.learned).map(d => ({ k: d.k, rounds: d.rounds, wall: d.last && d.last.wall, rest: d.last && d.last.rest, median: d.last && d.last.median })) };
  out.goal_met = out.n_learned === N && out.n_retest_ok === N; fs.writeFileSync(OF, JSON.stringify(out, null, 1)); return out; };
for (let round = 1; round <= MAXR; round++) { const todo = S.inds.filter(d => !d.learned && d.rounds < round); if (!todo.length) continue;
  for (const d of todo) { let P = d.P ? unpack(d.P) : null; for (let i = 0; i < PER; i++) P = life(d.base + d.rounds * PER + i, "on", P).P; d.rounds++; const t = test(P, 5000); d.P = pack(P); d.history.push(Object.assign({ round: d.rounds }, t)); d.learned = t.median >= need;
    if (d.learned) { const r = test(P, 5100); d.retest = Object.assign({ ok: r.median >= 1.5 * S.baseline2.median }, r); }
    console.log(`第 ${d.rounds} 轮 个体 ${d.k}: 测试中位 ${t.median.toFixed(0)} s  喝 ${t.drink} 贴墙 ${t.wall} 歇 ${t.rest}  ${d.learned ? "✓ 学成" + (d.retest.ok ? "（换新世界复测 " + d.retest.median.toFixed(0) + " s ✓）" : "（复测 " + d.retest.median.toFixed(0) + " s ✗）") : "… 继续"}`); save(); }
  const o = save(); console.log(`—— 第 ${round} 轮结束：${o.n_learned}/${N} 学成`); if (o.n_learned === N) break; }
const o = save(); console.log(`\n结果：${o.n_learned}/${N} 学成，复测通过 ${o.n_retest_ok}/${N}，共 ${o.total_lives} 条命；各自用了 ${o.rounds_to_learn.join("、")} 轮。目标${o.goal_met ? "达成" : "**未达成**"}`); process.exit(o.goal_met ? 0 : 2);
