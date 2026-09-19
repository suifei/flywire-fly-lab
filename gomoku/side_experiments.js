#!/usr/bin/env node
/**
 * 五子棋 v2 的几个旁证实验。每个子命令写一个 JSON——文档里引用的数字都从这些文件来，不许手抄。
 *
 *   ladder   老师 v2 各搜索深度对深度 3 的胜负（棋力随深度怎么涨）            → teacher_ladder.json
 *   noise    **表的精度值多少棋力**：给老师的对数分值表加高斯噪声到指定 R²，
 *            同一个引擎想 4 步，对老师深度 4                                     → table_noise.json
 *   timing   引擎搜到各深度的节点数与用时（开局 3 子局面；**用时受机器负载影响，节点数不受**） → depth_timing.json
 *   forms    「直接相加」为什么不行：老师的对数分值按两种形式下（只看 1 步），对旧老师        → score_forms.json
 *
 * 用法：node gomoku/side_experiments.js ladder|noise|timing|forms
 */
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, ".."), R = ROOT + "/results/gomoku";
const G = require("./rules.js"), L = require("./lines.js"), T1 = require("./teacher.js"), T2 = require("./teacher2.js"), A = require("./arena.js"), E = require("./engine.js");
const cmd = process.argv[2], slim = r => ({ win: r.win, loss: r.loss, draw: r.draw, games: r.games });
const save = (f, o) => { fs.writeFileSync(`${R}/${f}`, JSON.stringify(o, null, 1)); console.log("→ results/gomoku/" + f); };
const codes = L.allCodes(), logv = c => Math.log(T2.ATT[T2.CLS[c]] + 1);

if (cmd === "ladder") {
  const t = d => (b, c) => T2.search(b, c, d).move, out = { reference: "老师 v2 深度 3", pairs: 15, rows: [] };
  for (const d of [1, 2, 4, 5, 6, 7, 8]) { const t0 = Date.now(), r = A.match(t(d), t(3), 15, 100); out.rows.push({ depth: d, ...slim(r), seconds: +((Date.now() - t0) / 1000).toFixed(1) }); console.log(`深度 ${d} 对 深度 3：${r.win}-${r.loss}-${r.draw}`); }
  save("teacher_ladder.json", out);
} else if (cmd === "noise") {
  let mean = 0; for (const c of codes) mean += logv(c); mean /= codes.length; let v = 0; for (const c of codes) v += (logv(c) - mean) ** 2; v /= codes.length;
  const noisy = (r2, seed) => { const rand = A.rng32(seed), sd = r2 >= 1 ? 0 : Math.sqrt(v * (1 - r2) / r2), att = new Float32Array(L.NCODE);
    for (const c of codes) { const u = Math.max(rand(), 1e-12), w = rand(); att[c] = Math.exp(logv(c) + sd * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * w)); } return att; };
  const ref = (b, c) => T2.search(b, c, 4).move, out = { note: "老师的 ln(分值+1) 表 + 独立高斯噪声；R² 指加噪后的表对原表的决定系数；每个 R² 两份噪声各 20 局", depth: 4, opponent: "老师 v2 深度 4", lam: 0.4, rows: [] };
  for (const r2 of [1, 0.97, 0.95, 0.92, 0.85, 0.75]) { let w = 0, l = 0, d = 0;
    for (const seed of [1, 2]) { const e = E.makeEngine(noisy(r2, seed), 0.4), r = A.match((b, c) => e.think(b, c, { depth: 4 }).move, ref, 10, 5200 + seed * 100); w += r.win; l += r.loss; d += r.draw; }
    out.rows.push({ r2, win: w, loss: l, draw: d, games: w + l + d, win_rate: +(w / (w + l + d)).toFixed(3) }); console.log(`R² = ${r2}：${w}-${l}-${d}`); }
  save("table_noise.json", out);
} else if (cmd === "timing") {
  const F2 = require("./fly2.js"), j = JSON.parse(fs.readFileSync(`${R}/linetable_fly_intact.json`, "utf8")), e = E.makeEngine(F2.loadTable(j).att, j.lam);
  const b = G.newBoard(); [[7, 7, 1], [8, 8, 2], [7, 8, 1]].forEach(([x, y, c]) => { b[G.idx(x, y)] = c; });
  const out = { position: "开局 3 子，白先", table: "fly_intact", note: "用时受机器负载影响；节点数是确定的", rows: [] };
  for (const d of [2, 4, 6, 8, 10, 12, 14]) { const r = e.think(b, 2, { depth: d, budgetMs: 600000 }); if (r.depth < d) { out.rows.push({ depth: d, finished: false }); break; }
    out.rows.push({ depth: d, nodes: r.nodes, seconds: +(r.ms / 1000).toFixed(2) }); console.log(`深度 ${d}：${r.nodes} 节点，${(r.ms / 1000).toFixed(2)} s`); }
  for (let k = 1; k < out.rows.length; k++) if (out.rows[k].nodes) out.rows[k].nodes_ratio_per_ply = +Math.sqrt(out.rows[k].nodes / out.rows[k - 1].nodes).toFixed(2);
  const done = out.rows.filter(r => r.nodes); out.nodes_growth_per_ply = +Math.pow(done[done.length - 1].nodes / done[0].nodes, 1 / (done[done.length - 1].depth - done[0].depth)).toFixed(2);   // 几何平均
  save("depth_timing.json", out);
} else if (cmd === "forms") {
  const att = new Float32Array(L.NCODE); for (const c of codes) att[c] = logv(c);
  const lam = 0.76, old = (b, c) => T1.best(b, c).move;
  const player = lin => (b, c) => { let bi = -1, bs = -Infinity; for (const i of G.candidates(b, 2)) { if (c === G.BLACK && G.forbidden(b, i % G.N, (i / G.N) | 0)) continue; let s = 0;
    for (let d = 0; d < 4; d++) { const code = L.codeAt(b, i % G.N, (i / G.N) | 0, d, c), sw = T2.SWAP[code]; s += lin ? Math.exp(att[code]) + lam * Math.exp(att[sw]) : att[code] + lam * att[sw]; } if (s > bs) { bs = s; bi = i; } } return bi; };
  const out = { note: "同一张表（老师的 ln(分值+1)），只看 1 步，对旧老师；差别只在一个点的 8 条线怎么合成", lam, sum_of_logs: slim(A.match(player(false), old, 20, 7000)), sum_of_exps: slim(A.match(player(true), old, 20, 7000)) };
  console.log("对数直接相加：", JSON.stringify(out.sum_of_logs), " 取指数再相加：", JSON.stringify(out.sum_of_exps)); save("score_forms.json", out);
} else if (cmd === "width") {
  const F2 = require("./fly2.js"), j = JSON.parse(fs.readFileSync(`${R}/linetable_fly_intact.json`, "utf8")), att = F2.loadTable(j).att;
  const mk = K => { const e = E.makeEngine(att, j.lam); let sd = 0, n = 0; const f = (b, c) => { const r = e.think(b, c, { maxNodes: 20000, K }); sd += r.depth; n++; return r.move; }; f.avg = () => +(sd / n).toFixed(2); return f; };
  const out = { note: "同一张表、同一个引擎，每步 2 万节点的预算（确定性，不受机器负载影响）；每组 100 局", rows: [] };
  for (const [a, b, seed] of [[6, 10, 100], [4, 6, 700], [5, 6, 900]]) { const pa = mk(a), pb = mk(b), r = A.match(pa, pb, 50, seed);
    out.rows.push({ K_a: a, K_b: b, ...slim(r), mean_depth_a: pa.avg(), mean_depth_b: pb.avg() }); console.log(`宽度 ${a} 对 ${b}：${r.win}-${r.loss}-${r.draw}（平均深度 ${pa.avg()} 对 ${pb.avg()}）`); }
  save("search_width.json", out);
} else if (cmd === "vcf") {
  const F2 = require("./fly2.js"), j = JSON.parse(fs.readFileSync(`${R}/linetable_fly_intact.json`, "utf8"));
  const out = { note: "同一张表、同一个深度；A 开杀棋（进攻：先找连续冲四；防守：走之前检查对手有没有杀棋），B 不开；每组 100 局", rows: [] };
  for (const [d, seed] of [[4, 2100], [6, 2300]]) { const pa = F2.makeLinePlayer(null, null, j), pb = F2.makeLinePlayer(null, null, j);
    const r = A.match((b, c) => pa.choose(b, c, { depth: d, vcf: true }).move, (b, c) => pb.choose(b, c, { depth: d, vcf: false }).move, 50, seed);
    out.rows.push({ depth: d, ...slim(r) }); console.log(`想 ${d} 步：带杀棋 对 不带  ${r.win}-${r.loss}-${r.draw}`); }
  save("vcf_value.json", out);
} else { console.log("用法：node gomoku/side_experiments.js ladder|noise|timing|forms|width"); process.exit(1); }
