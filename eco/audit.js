#!/usr/bin/env node
/**
 * 生态箱 M1 · 技术审计：感知 / 动作 / 飞行 / 学习四条链路，逐项实测，固定成清单。后面的玩法只许建立在「接上了」的项上。
 *
 * 感知：每一路感受器单独驱动（左 / 右 / 双侧，150 Hz，600 ms 取后 500 ms，3 个种子），量它到不到得了运动读出。
 *   判定（写在跑之前）：
 *     「能定向」= 左刺激与右刺激的转向指数 LI =（DNa 左 − DNa 右）÷ 和 符号相反，且 |LI| 都 ≥ 0.2，且 DNa 合计 ≥ 2 Hz
 *     「能触发」= 双侧驱动时 巨纤维 ≥ 90 Hz（起飞）/ MN9 ≥ 10 Hz（伸喙）/ aDN1 ≥ 20 Hz（梳理）/ MDN ≥ 20 Hz（后退）—— 与页面用的阈值相同
 *     「只到脑内」= 上面都不满足，但除被驱动者之外活跃的神经元 ≥ 50
 * 速度：v5 真脑每 5 ms 物理步要多少毫秒 → 一只能不能加速、32 只能不能同时跑。
 * 飞行与学习：读已有的结果文件（flight_clips.json、learn_summary.json），不重跑。
 * 输出 results/eco/audit.json（约 3 分钟）；docs/ecobox/AUDIT.md 由 eco/render_audit.py 渲染。
 */
const fs = require("fs"), path = require("path"), ROOT = path.resolve(__dirname, "..");
const { ConnectomeBrain } = require("../dodge/brain.js");
const SUB = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge/subcircuit_v5.json"), "utf8"));
const HZ = 150, SEEDS = [11, 22, 33], G = SUB.groups, side = SUB.sides, typ = SUB.types, n = SUB.meta.n;
const glom = (names, sd) => names.flatMap(g => (SUB.meta.glomeruli[g] || []).filter(i => !sd || side[i] === sd));
const grp = (names, sd) => names.flatMap(g => G[g + "_" + sd] || []);
const byType = t => { const o = { left: [], right: [] }; for (let i = 0; i < n; i++) if (typ[i] === t && o[side[i]]) o[side[i]].push(i); return o; };
const oDN1 = byType("DNg97"), BDN2 = byType("DNg100");
const CH = {   // 名字：[说明, (侧) => 神经元下标]
  looming: ["逼近的物体（LC4 + LPLC2）", sd => grp(["LC4", "LPLC2"], sd)], lc16: ["正面逼近（LC16）", sd => grp(["LC16"], sd)],
  sugar: ["甜（糖味觉 LB3）", sd => grp(["SUGAR"], sd)], bitter: ["苦（LB1）", sd => grp(["BITTER"], sd)],
  wind: ["风 / 触角偏转（JO）", sd => grp(["JO"], sd)], touch: ["触碰（头部刚毛）", sd => grp(["TOUCH"], sd)],
  heat: ["热（温度感受器）", sd => grp(["THERMO"], sd)], humid: ["湿（湿度感受器）", sd => grp(["HYGRO"], sd)], sound: ["声音（JO 听觉亚群）", sd => grp(["AUDIO"], sd)],
  odorA: ["气味 A（20 个嗅小球）", sd => glom(SUB.meta.odors.A, sd)], odorB: ["气味 B（20 个嗅小球）", sd => glom(SUB.meta.odors.B, sd)],
  vinegar: ["醋味（DM1）", sd => glom(["DM1"], sd)], geosmin: ["霉味（DA2）", sd => glom(["DA2"], sd)], cva: ["同类的信息素 cVA（DA1）", sd => glom(["DA1"], sd)],
  isn: ["内感受 ISN", sd => grp(["ISN"], sd)] };
const RO = { dnaL: [...G.DNa01_left, ...G.DNa02_left], dnaR: [...G.DNa01_right, ...G.DNa02_right], gf: [...G.DNp01_left, ...G.DNp01_right], mn9: [...G.MN9_left, ...G.MN9_right], adn1: [...G.aDN1_left, ...G.aDN1_right], mdn: [...G.MDN_left, ...G.MDN_right],
  odn1: [...oDN1.left, ...oDN1.right], bdn2: [...BDN2.left, ...BDN2.right], mbon: [], pam: [...G.PAM_left, ...G.PAM_right], ppl1: [...G.PPL1_left, ...G.PPL1_right] };
for (let i = 0; i < n; i++) if (SUB.mb_tag[i] === "MBON") RO.mbon.push(i);
function probe(idx, seed) { const b = new ConnectomeBrain(SUB, seed); b.setDrive("probe", idx, HZ); b.run(1000); const cnt = new Float32Array(n); b.run(5000, i => { cnt[i]++; }); const driven = new Set(idx), out = {};
  for (const [k, ix] of Object.entries(RO)) out[k] = ix.length ? ix.reduce((s, i) => s + cnt[i], 0) / ix.length / 0.5 * (k === "dnaL" || k === "dnaR" ? ix.length / 1 : 1) : 0;      // DNa：两种细胞合计（与页面读出一致）
  let act = 0; for (let i = 0; i < n; i++) if (cnt[i] > 0 && !driven.has(i)) act++; out.active = act; return out; }
const mean = rows => { const o = {}; for (const k of Object.keys(rows[0])) o[k] = +(rows.reduce((s, r) => s + r[k], 0) / rows.length).toFixed(1); return o; };
const out = { hz: HZ, seeds: SEEDS.length, n_neurons: n, senses: {} }, t0 = Date.now();
for (const [key, [label, pick]] of Object.entries(CH)) { const L = pick("left"), R = pick("right"), res = { label, n_left: L.length, n_right: R.length };
  res.left = mean(SEEDS.map(s => probe(L, s))); res.right = mean(SEEDS.map(s => probe(R, s))); res.both = mean(SEEDS.map(s => probe([...L, ...R], s)));
  const li = r => (r.dnaL + r.dnaR) >= 2 ? (r.dnaL - r.dnaR) / (r.dnaL + r.dnaR) : 0; res.LI_left = +li(res.left).toFixed(2); res.LI_right = +li(res.right).toFixed(2);
  res.can_steer = Math.sign(res.LI_left) === -Math.sign(res.LI_right) && Math.min(Math.abs(res.LI_left), Math.abs(res.LI_right)) >= 0.2;
  res.triggers = [["起飞", res.both.gf >= 90], ["伸喙", res.both.mn9 >= 10], ["梳理", res.both.adn1 >= 20], ["后退", res.both.mdn >= 20]].filter(x => x[1]).map(x => x[0]);
  res.fixed_turn = !res.can_steer && (res.both.dnaL + res.both.dnaR) >= 5 ? (res.both.dnaL > res.both.dnaR ? "总是偏左" : "总是偏右") : null;
  res.verdict = res.can_steer || res.triggers.length ? "接上了" : res.fixed_turn ? "半接上" : res.both.active >= 50 ? "只到脑内" : "没接上";
  out.senses[key] = res; console.log(`${label.padEnd(18)} ${res.verdict}  定向 ${res.can_steer ? "能" : "不能"}（LI ${res.LI_left} / ${res.LI_right}） 触发 [${res.triggers.join("、")}]${res.fixed_turn ? " · " + res.fixed_turn : ""}  DNa ${res.both.dnaL}/${res.both.dnaR} GF ${res.both.gf} MN9 ${res.both.mn9} oDN1 ${res.both.odn1} BDN2 ${res.both.bdn2} MBON ${res.both.mbon} 活跃 ${res.both.active}`); }
// 速度
{ const b = new ConnectomeBrain(SUB, 1), jo = grp(["JO"], "left").concat(grp(["JO"], "right")); b.setDrive("w", jo, 30); b.run(2000); let t = Date.now(); b.run(20000); const quiet = (Date.now() - t) / 400;
  b.setDrive("o", glom(SUB.meta.odors.A), 150); b.run(2000); t = Date.now(); b.run(20000); const smell = (Date.now() - t) / 400;
  out.speed = { ms_per_5ms_step_quiet: +quiet.toFixed(2), ms_per_5ms_step_smelling: +smell.toFixed(2), realtime_factor_one_fly: +(5 / smell).toFixed(2), realtime_factor_32_flies: +(5 / smell / 32).toFixed(3) }; console.log("速度：", JSON.stringify(out.speed)); }
// 飞行链路（读文件）
{ const F = JSON.parse(fs.readFileSync(path.join(ROOT, "results/flight/flight_clips.json"), "utf8")); out.flight = { n_clips: F.clips.length, clips: F.clips.map(c => ({ name: c.name, turn: c.turn, frames: c.n, seconds: +(c.n * (c.dt || F.dt || 0.0004)).toFixed(3) })),
    takeoff: "连接组：巨纤维平滑发放 ≥ 90 Hz → 起飞（反射，已实测）", in_flight: "没有接：起飞后播放一段录好的真实逃逸轨迹（flybody 控制器在物理里复飞），大脑不参与，不能转向、不能选落点", landing: "手写：片段末尾插值回行走姿态", verdict: "「起不起飞」可以是一个决策量；「怎么飞」现在学不了" }; }
// 学习链路（读文件）
{ const L = JSON.parse(fs.readFileSync(path.join(ROOT, "results/learn/learn_summary.json"), "utf8")); out.learning = { mb_memory_forms: L.conditioning.connectome.criteria.L1_learned, mb_specific: L.conditioning.connectome.criteria.L2_specific, memory_reaches_motor: L.memory_to_motor.v5.M2,
    dopamine_recruited_by_senses: L.reinforcement.any_route, engine_parity: L.parity.all_pass }; }
out.seconds = +((Date.now() - t0) / 1000).toFixed(0); fs.writeFileSync(path.join(ROOT, "results/eco/audit.json"), JSON.stringify(out, null, 1)); console.log("→ results/eco/audit.json", out.seconds + " s");
