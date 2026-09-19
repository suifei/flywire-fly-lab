#!/usr/bin/env node
/**
 * 阶段三：**自对弈强化**（用户提的「链接多巴胺自主训练」）。
 *
 * 三因子学习规则，只作用在**读出层**（果蝇脑里仍然一个突触都不动）：
 *     Δw = 学习率 × δ × 资格迹
 *     资格迹 = Σ_步 ∇_w log π(选中的那一步)        π = softmax(log 落子分 / 温度)，落子分 = Σ e^{a[进攻线]} + λ Σ e^{a[防守线]}，a = Φ̄·w
 *     δ      = 这一局的结果 R（赢 +1 / 输 −1 / 和 0）− 基线 b（近期结果的滑动平均）   ← 奖励预测误差
 * δ 在强化学习里对应多巴胺信号。**必须说清楚**：这个 LIF 模型自己的多巴胺神经元在非失控条件下根本不放电
 *（report §11：PAM 0/307），所以 δ 是在连接组**外面**算的，不是果蝇脑自己给的。
 *
 * 训练对局：果蝇按 π 采样落子（只看一步），对手轮换 = 老师 v2 深度 2 / 深度 4 / 自己的冻结副本。从阶段二的权重出发。
 *
 * 判据（**写在跑之前**）：强化后的表 vs 阶段二的表，都交给同一个引擎想 4 步，正面交锋 200 局，
 *   强化版胜率 ≥ 55% 才算"强化有用"，页面才换用强化版；否则如实记阴性，页面继续用阶段二的表。
 *   另报告只凭直觉的正面交锋，以及两者对老师深度 4 的成绩。
 *
 * 用法：node gomoku/selfplay_rl.js [轮数=80] [每轮局数=48] [学习率=0.05] [温度=0.5]
 * 输出：results/gomoku/rl.json、linetable_fly_intact_rl.json
 */
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, ".."), R = ROOT + "/results/gomoku";
const G = require("./rules.js"), L = require("./lines.js"), T2 = require("./teacher2.js"), A = require("./arena.js"), E = require("./engine.js");
const ITERS = +(process.argv[2] || 80), GAMES = +(process.argv[3] || 48), LR = +(process.argv[4] || 0.05), TEMP = +(process.argv[5] || 0.5);
if (ITERS < 1) { console.error("轮数必须 ≥ 1（0 轮会把一张没训练过的表写到正式文件名上——2026-09-20 自检时干过一次）"); process.exit(1); }
const ARM = process.env.ARM || "fly_intact", RL_TAG = process.env.RL_TAG || "";   // RL_TAG 非空 = 探索性的另一组超参，不覆盖主结果

const tab = JSON.parse(fs.readFileSync(`${R}/linetable_${ARM}.json`, "utf8"));
if (tab.form !== "lse" || !tab.tied) throw new Error("需要 lse + tied 的表");
const f32 = s => { const b = Uint8Array.from(Buffer.from(s, "base64")); return new Float32Array(b.buffer, 0, b.byteLength >> 2); };
const mu = f32(tab.mu), sd = f32(tab.sd), keep = tab.keep, D = keep.length, codes = tab.codes, NP = codes.length, lam = tab.lam;
const w = new Float64Array(D + 1); f32(tab.w_a).forEach((v, k) => { w[k] = v; }); w[D] = tab.bias;
const rowOf = new Int32Array(L.NCODE).fill(-1); codes.forEach((c, k) => { rowOf[c] = k; });
// Φ̄：训练种子的试次平均（√计数），标准化
const arm = ARM.split("_")[1], PHI = new Float32Array(NP * D);
// 特征可以由几个视角横向拼成（tab.views）；keep 是拼接后的列号
const views = (tab.views && tab.views.length) ? tab.views : [{ view: 1, bins: tab.bins || 1 }];
const tagOf = v => ((v.view === 1 && v.bins === 1) ? "" : `_v${v.view}b${v.bins}`);
for (const seed of tab.seeds) {
  const parts = views.map(v => { const m = JSON.parse(fs.readFileSync(`${R}/linefeat_${arm}${tagOf(v)}_s${seed}.json`, "utf8")); return { cols: m.cols, raw: fs.readFileSync(`${R}/linefeat_${arm}${tagOf(v)}_s${seed}.bin`) }; });
  const start = []; let acc0 = 0; for (const p of parts) { start.push(acc0); acc0 += p.cols; }
  const where = keep.map(c => { let i = parts.length - 1; while (c < start[i]) i--; return [i, c - start[i]]; });
  for (let r = 0; r < NP; r++) for (let k = 0; k < D; k++) { const [i, c] = where[k]; PHI[r * D + k] += Math.sqrt(parts[i].raw[r * parts[i].cols + c]) / tab.seeds.length; }
}
for (let r = 0; r < NP; r++) for (let k = 0; k < D; k++) PHI[r * D + k] = (PHI[r * D + k] - mu[k]) / sd[k];
function attFrom(w) { const att = new Float32Array(L.NCODE); for (let r = 0; r < NP; r++) { let a = w[D]; const o = r * D; for (let k = 0; k < D; k++) a += PHI[o + k] * w[k]; att[codes[r]] = Math.exp(Math.min(a, 30)); } return att; }
{ const a0 = attFrom(w), ref = f32(tab.att); let md = 0; for (let r = 0; r < NP; r++) md = Math.max(md, Math.abs(a0[codes[r]] - ref[r]) / Math.max(1e-9, ref[r])); console.log(`由权重重建的表与导出的表最大相对偏差 ${md.toExponential(1)}`); if (md > 1e-3) throw new Error("重建的表对不上"); }

// 采样式棋手：π ∝ 落子分^(1/温度)；把 ∇ log π 按线型行号累进 trace.g
function samplingPlayer(att, trace, rand) {
  return (b, c) => {
    const cand = [], sc = [], rows = [], wts = [];
    for (const i of G.candidates(b, 2)) {
      if (c === G.BLACK && G.forbidden(b, i % G.N, (i / G.N) | 0)) continue;
      const x = i % G.N, y = (i / G.N) | 0; let s = 0; const r8 = [], w8 = [];
      for (let d = 0; d < 4; d++) { const code = L.codeAt(b, x, y, d, c), sw = T2.SWAP[code]; const va = att[code], vd = lam * att[sw]; s += va + vd; r8.push(rowOf[code], rowOf[sw]); w8.push(va, vd); }
      cand.push(i); sc.push(Math.log(s) / TEMP); rows.push(r8); wts.push(w8.map(v => v / s));
    }
    if (!cand.length) return -1;
    const m = Math.max(...sc); let Z = 0; const p = sc.map(v => { const e = Math.exp(v - m); Z += e; return e; });
    let u = rand() * Z, pick = 0; for (; pick < p.length - 1; pick++) { u -= p[pick]; if (u <= 0) break; }
    if (trace) for (let j = 0; j < cand.length; j++) { const gj = ((j === pick ? 1 : 0) - p[j] / Z) / TEMP; if (Math.abs(gj) < 1e-6) continue; for (let k = 0; k < 8; k++) trace.g[rows[j][k]] += gj * wts[j][k]; }
    return cand[pick];
  };
}
const att0 = attFrom(w), engSup = E.makeEngine(att0, lam);
const tD4 = (b, c) => T2.search(b, c, 4).move, tD2 = (b, c) => T2.search(b, c, 2).move;
function evalNow(att, pairs) {
  const eng = E.makeEngine(att, lam), g = e => (b, c) => e.greedy(b, c), d4 = e => (b, c) => e.think(b, c, { depth: 4 }).move;
  return { d4_vs_supervised_d4: A.match(d4(eng), d4(engSup), pairs, 31000), greedy_vs_supervised: A.match(g(eng), g(engSup), pairs, 32000),
           d4_vs_teacher_d4: A.match(d4(eng), tD4, Math.min(pairs, 20), 33000), greedy_vs_teacher_d2: A.match(g(eng), tD2, Math.min(pairs, 20), 34000) };
}
const slim = ev => Object.fromEntries(Object.entries(ev).map(([k, r]) => [k, { win: r.win, loss: r.loss, draw: r.draw, games: r.games }]));
const rand = A.rng32(424242), log = [], checkpoints = [];
let base = 0, att = att0, frozen = att0;
console.log(`${ARM}：${ITERS} 轮 × ${GAMES} 局，学习率 ${LR}，温度 ${TEMP}，读出维度 ${D}`);
const t0 = Date.now();
for (let it = 0; it <= ITERS; it++) {
  if (it % 20 === 0) { const ev = evalNow(att, 15); checkpoints.push({ iter: it, ...slim(ev) }); frozen = att;
    console.log(`  第 ${it} 轮检查：想4步对监督版 ${ev.d4_vs_supervised_d4.win}-${ev.d4_vs_supervised_d4.loss}  直觉对监督版 ${ev.greedy_vs_supervised.win}-${ev.greedy_vs_supervised.loss}  想4步对老师d4 ${ev.d4_vs_teacher_d4.win}-${ev.d4_vs_teacher_d4.loss}   ${((Date.now() - t0) / 1000).toFixed(0)} s`); }
  if (it === ITERS) break;
  const gw = new Float64Array(D + 1); let wins = 0, sumAbs = 0; const deltas = [];
  for (let g = 0; g < GAMES; g++) {
    const trace = { g: new Float64Array(NP) }, kind = g % 3;
    const opp = kind === 0 ? tD2 : kind === 1 ? tD4 : samplingPlayer(frozen, null, rand), me = samplingPlayer(att, trace, rand), flyBlack = g % 2 === 0;
    const r = A.playGame(flyBlack ? me : opp, flyBlack ? opp : me, 60000 + it * 1000 + g);
    const Rw = r.winner === 0 ? 0 : (r.winner === (flyBlack ? G.BLACK : G.WHITE) ? 1 : -1);
    const delta = Rw - base; base += 0.02 * (Rw - base); deltas.push(+delta.toFixed(3)); sumAbs += Math.abs(delta); if (Rw > 0) wins++;
    for (let row = 0; row < NP; row++) { const gr = trace.g[row]; if (gr === 0) continue; const o = row * D, c = delta * gr; for (let k = 0; k < D; k++) gw[k] += c * PHI[o + k]; gw[D] += c; }
  }
  let nrm = 0; for (let k = 0; k <= D; k++) nrm += gw[k] * gw[k]; nrm = Math.sqrt(nrm) || 1;
  for (let k = 0; k <= D; k++) w[k] += (LR / nrm) * gw[k];                     // 归一化步长：每轮权重移动的长度 = 学习率
  att = attFrom(w);
  log.push({ iter: it, win_rate: +(wins / GAMES).toFixed(3), baseline: +base.toFixed(3), mean_abs_delta: +(sumAbs / GAMES).toFixed(3), deltas });
  if (it % 10 === 0) console.log(`  轮 ${it}：训练对局胜率 ${(wins / GAMES * 100).toFixed(0)}%  基线 ${base.toFixed(2)}  |δ| ${(sumAbs / GAMES).toFixed(2)}`);
}
const final = evalNow(att, 100), wr = final.d4_vs_supervised_d4.win / final.d4_vs_supervised_d4.games;
const out = { arm: ARM, iters: ITERS, games_per_iter: GAMES, lr: LR, temp: TEMP, log, checkpoints, final: slim(final),
  criterion: "强化后的表 对 阶段二的表，同一个引擎都想 4 步，200 局胜率 ≥ 55%", win_rate_vs_supervised: +wr.toFixed(3), criterion_passed: wr >= 0.55,
  note: "δ（奖励预测误差）在连接组外面计算；模型自己的多巴胺神经元不放电（report §11）", seconds: +((Date.now() - t0) / 1000).toFixed(0) };
out.final.vs_supervised = out.final.d4_vs_supervised_d4;
fs.writeFileSync(`${R}/rl${RL_TAG}.json`, JSON.stringify(out));
const a32 = new Float32Array(NP), d32 = new Float32Array(NP); codes.forEach((c, k) => { a32[k] = att[c]; d32[k] = lam * att[c]; });
fs.writeFileSync(`${R}/linetable_${ARM}_rl${RL_TAG}.json`, JSON.stringify({ ...tab, arm: ARM + "_rl", att: Buffer.from(a32.buffer).toString("base64"), deff: Buffer.from(d32.buffer).toString("base64"),
  w_a: Buffer.from(Float32Array.from(w.slice(0, D)).buffer).toString("base64"), bias: w[D] }));
console.log(`最终（各 200 局）：想 4 步对监督版 ${final.d4_vs_supervised_d4.win}-${final.d4_vs_supervised_d4.loss}（${(wr * 100).toFixed(1)}%）→ 判据${out.criterion_passed ? "通过" : "**不通过**"}；直觉对监督版 ${final.greedy_vs_supervised.win}-${final.greedy_vs_supervised.loss}`);
