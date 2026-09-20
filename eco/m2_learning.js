#!/usr/bin/env node
// 生态箱 M2：单只果蝇的生存学习。用法：node eco/m2_learning.js  （~2 min，纯 CPU）→ results/eco/m2_learning.json
//
// **事先写定的方案与判据**（写在跑之前；docs/ecobox/PLAN.md 的 M2 验收线）：
//   个体：3 个独立个体（训练种子基数 2000 / 3000 / 4000），默认世界规则，飞行关闭（先天的逃逸起跳保留）。
//   训练：同一个体连续 30 条命，可塑性层跨命保留（同一只果蝇的「第 N 次生命」），每条命观察上限 1,800 s，世界种子各不相同。
//   测试：**冻结学习**（权重不再变，探索噪声照旧），在 30 个训练时没见过的世界种子（5000–5029）上各活一次，上限 1,800 s。
//   四个臂：on = 正常学习；off = 不学习（对照）；shuffle = 奖励时序被打乱（同样的奖励分布，错开 20–60 s）；nobrain = 可塑性层看不到大脑输出（探索性，只报告）。
//   C1  on 臂测试寿命中位数 ≥ 1.5 × off 臂（3 个个体都要满足）
//   C2  shuffle 臂测试寿命中位数 < 1.2 × off 臂（3 个个体都要满足）——学到的东西得来自奖励与行为的对应，不是来自「权重动了」
//   寿命在 1,800 s 处截尾：活到上限记 1,800。
//   【事后加的，探索性】yoked = 轭式对照：把 on 臂同一序号那条命的逐步奖励原样回放给它（奖励分布完全相同，与它自己的行为无关）。
//     加它的原因：第一次跑完 C2 是 2/3——shuffle 只把奖励延后 20–60 s，而喝水这类行为会持续几十秒，延后的奖励与行为仍然相关，对照是漏的。C2 的结论照原判据登记，不改。
// 版本：v1（results/eco/m2_learning_v1.json）左右差特征用 (L−R)/200、策略权重不衰减——C1 3/3、C2 2/3，但换 10 个个体只有 3/10 学成（5 个贴墙、2 个躺平）。
//   v2（现在）：左右差用对比度、加「气味×风侧」特征、运动策略缓慢衰减回先天值（吃喝那一路不衰减）。**方案与判据没有动**；学习器的超参是在另一批种子（20000 起）上定的，不是在下面的测试种子上。
// 另外只报告、不设判据：学到了什么（权重最大的几项）、行为时间分配、死因、发现卡；三种更凶的世界（干旱 / 甲虫多 / 寒夜）里 on 与 off 的寿命。
const fs = require("fs"), path = require("path"), ROOT = path.resolve(__dirname, "..");
const Sim = require("./sim.js"), Surf = require("./brain_surface.js"), Plastic = require("./plastic.js"), Cards = require("./cards.js"), World = require("./world.js");
const SURF = JSON.parse(fs.readFileSync(path.join(ROOT, "results/eco/brain_surface.json"), "utf8")), brain = Surf.create(SURF);
const TRAIN = 30, TEST = 30, CAP = 1800, med = a => { a = a.slice().sort((x, y) => x - y); const n = a.length; return n % 2 ? a[n >> 1] : (a[n / 2 - 1] + a[n / 2]) / 2; };
const MILD = {}, WORLDS = { mild: {}, drought: { water: 1, evaporation: 2.5, rain: 0.3 }, beetles: { predators: 4, predatorSpeed: 9 }, coldnight: { tempNight: 6, tempDay: 24, sunrocks: 5 } };
function life(rules, seed, learn, P, extra) { const sim = Sim.create(rules, Object.assign({ seed, brain, learn, trail: false }, extra || {})), a = sim.spawn(null, P); let n = 0; while (a.alive && n < CAP * 10) { sim.step(); n++; } if (a.alive) a.deathT = null; return { a, sim, L: Cards.lifeSummary(a, sim.world) }; }
const TRACES = {};   // on 臂每条命的逐步奖励，给轭式对照回放
function individual(base, arm, rules, nTrain) { let P = null; const train = [], extra = arm === "nobrain" ? { noBrainFeatures: true } : {}, learn = arm === "nobrain" ? "on" : arm;
  for (let i = 0; i < (nTrain || TRAIN); i++) { const ex = Object.assign({}, extra, arm === "on" && !nTrain ? { recordReward: true } : {}, arm === "yoked" ? { yoke: TRACES[base + ":" + i] } : {}); const r = life(rules, base + i, learn, arm === "off" ? null : P, ex); P = r.a.P; train.push(r.L); if (ex.recordReward && rules === MILD) TRACES[base + ":" + i] = Float32Array.from(r.a.rtrace); }
  const test = [], cards = []; for (let i = 0; i < TEST; i++) { const Pc = arm === "off" ? null : clone(P), r = life(rules, 5000 + i, "off", Pc, extra); test.push(r.L); cards.push(...Cards.detect(r.L, { t: i })); }
  return { train, test, P, cards }; }
function clone(P) { const Q = {}; for (const k in P) Q[k] = P[k] instanceof Float64Array ? Float64Array.from(P[k]) : P[k]; return Q; }
const top = (w, k) => Array.from(w).map((v, i) => [Plastic.NAMES[i], +v.toFixed(3)]).filter(e => e[1] !== 0).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1])).slice(0, k);
const frac = (Ls, k) => +med(Ls.map(L => L[k])).toFixed(3), causes = Ls => Ls.reduce((o, L) => { const c = L.alive ? "alive" : L.cause; o[c] = (o[c] || 0) + 1; return o; }, {});

const t0 = Date.now(), out = { protocol: { train_lives: TRAIN, test_lives: TEST, cap_s: CAP, bases: [2000, 3000, 4000], test_seeds: "5000–5029", frozen_at_test: true }, rules: World.RULES, genes: Sim.GENES, plastic_hp: Plastic.HP, n_features: Plastic.NF, individuals: [], worlds: {} };
for (const base of [2000, 3000, 4000]) { const ind = { base, arms: {} };
  for (const arm of ["off", "on", "shuffle", "nobrain", "yoked"]) { const r = individual(base, arm, MILD); const lt = r.test.map(L => L.life);
    ind.arms[arm] = { test_median_life: med(lt), test_lives: lt.map(v => Math.round(v)), train_lives: r.train.map(L => Math.round(L.life)), causes: causes(r.test), eat: frac(r.test, "eat"), drink: frac(r.test, "drink"), rest: frac(r.test, "rest"), wall: frac(r.test, "wall"),
      drinks_per_water_visit: +med(r.test.map(L => L.waterVisits ? L.drinks / L.waterVisits : 0)).toFixed(3), cards: Cards.digest(r.cards).map(c => ({ key: c.key, kind: c.kind, title: c.title, count: c.count, evidence: c.evidence })) };
    if (arm === "on") { ind.learned = { turn: top(r.P.Wt, 6), kinesis: top(r.P.Wk, 6), speed: top(r.P.Ws, 6), ingest: top(r.P.Wi, 6), value: top(r.P.V, 8) }; if (base === 2000) fs.writeFileSync(path.join(ROOT, "results/eco/m2_champion.json"), JSON.stringify({ base, P: Object.fromEntries(Object.entries(r.P).map(([k, v]) => [k, v instanceof Float64Array ? Array.from(v) : v])) })); } }
  const A = ind.arms; ind.ratio_on = +(A.on.test_median_life / A.off.test_median_life).toFixed(3); ind.ratio_shuffle = +(A.shuffle.test_median_life / A.off.test_median_life).toFixed(3); ind.ratio_nobrain = +(A.nobrain.test_median_life / A.off.test_median_life).toFixed(3); ind.ratio_yoked_posthoc = +(A.yoked.test_median_life / A.off.test_median_life).toFixed(3);
  ind.C1 = ind.ratio_on >= 1.5; ind.C2 = ind.ratio_shuffle < 1.2; out.individuals.push(ind);
  console.log(`个体 ${base}: off ${A.off.test_median_life.toFixed(0)} s | on ${A.on.test_median_life.toFixed(0)} s (×${ind.ratio_on}) | shuffle ${A.shuffle.test_median_life.toFixed(0)} s (×${ind.ratio_shuffle}) | nobrain ${A.nobrain.test_median_life.toFixed(0)} s (×${ind.ratio_nobrain}) | 轭式（事后加）${A.yoked.test_median_life.toFixed(0)} s (×${ind.ratio_yoked_posthoc})   C1 ${ind.C1 ? "过" : "不过"}  C2 ${ind.C2 ? "过" : "不过"}`); }
out.criteria = { C1_all: out.individuals.every(i => i.C1), C2_all: out.individuals.every(i => i.C2), censored_note: "寿命在 1,800 s 截尾；on 臂的比值是下限" };
// 稳健性（探索性）：10 个独立个体，各训练 30 条命，看后 10 条命的寿命中位数与有没有塌进某种作弊
{ const rows = []; for (let k = 0; k < 10; k++) { const r = individual(20000 + 100 * k, "on", MILD, 30), last = r.train.slice(20); rows.push({ base: 20000 + 100 * k, last10_median: med(last.map(L => L.life)), wall: +med(last.map(L => L.wall)).toFixed(3), rest: +med(last.map(L => L.rest)).toFixed(3), test_median: med(r.test.map(L => L.life)) }); }
  out.robustness = { individuals: rows, n_learned: rows.filter(r => r.test_median >= 1.5 * out.individuals[0].arms.off.test_median_life).length, n: rows.length }; console.log(`稳健性：${out.robustness.n_learned}/${out.robustness.n} 个个体的测试寿命 ≥ 1.5 × 不学习`); }
// 训练更久有没有用（探索性）：干旱世界里训练 30 / 120 条命
{ const r30 = individual(2000, "on", WORLDS.drought, 30), r120 = individual(2000, "on", WORLDS.drought, 120); out.longer_training_drought = { lives30_median: med(r30.test.map(L => L.life)), lives120_median: med(r120.test.map(L => L.life)), lives120_causes: causes(r120.test), lives120_turn: top(r120.P.Wt, 5), lives120_kinesis: top(r120.P.Wk, 5) };
  console.log(`干旱世界训练 30 条命 → ${out.longer_training_drought.lives30_median.toFixed(0)} s；120 条命 → ${out.longer_training_drought.lives120_median.toFixed(0)} s`); }
// 更凶的世界（探索性）：在那个世界里训练、在那个世界里测
for (const [name, rules] of Object.entries(WORLDS)) { if (name === "mild") continue; const off = individual(2000, "off", rules), on = individual(2000, "on", rules);
  out.worlds[name] = { rules, off_median: med(off.test.map(L => L.life)), on_median: med(on.test.map(L => L.life)), off_causes: causes(off.test), on_causes: causes(on.test), on_cards: Cards.digest(on.cards).map(c => ({ key: c.key, title: c.title, count: c.count })) };
  console.log(`世界「${name}」: off ${out.worlds[name].off_median.toFixed(0)} s → on ${out.worlds[name].on_median.toFixed(0)} s   死因 ${JSON.stringify(out.worlds[name].on_causes)}   卡 ${out.worlds[name].on_cards.map(c => c.title + "×" + c.count).join("、")}`); }
out.seconds = +((Date.now() - t0) / 1000).toFixed(1); out.sim_seconds_per_wall_second = null;
fs.writeFileSync(path.join(ROOT, "results/eco/m2_learning.json"), JSON.stringify(out, null, 1));
console.log(`判据 C1（≥1.5×，3/3）: ${out.criteria.C1_all ? "通过" : "未通过"}   C2（打乱不提升，3/3）: ${out.criteria.C2_all ? "通过" : "未通过"}   用时 ${out.seconds} s`);
