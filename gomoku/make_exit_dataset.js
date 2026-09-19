#!/usr/bin/env node
/**
 * 自我迭代（expert iteration）的数据：**不用手写的老师**。
 *   局面来源：当前价值表 + 引擎想 DEPTH_PLAY 步 的自对弈（EPS 概率从前 4 名里随机挑，保证多样）
 *   标签    ：同一张表 + 引擎想 DEPTH_LABEL 步（先试连续冲四杀棋）给出的最佳着
 * 也就是「让深思熟虑的自己教只凭直觉的自己」。训练沿用 train_lines.py（--ds <目录> --init-from <表> --label 8）。
 *
 * 用法：node gomoku/make_exit_dataset.js <表.json> <输出目录名> <分片> <分片数> [总局数=600]
 *       node gomoku/make_exit_dataset.js merge <输出目录名>
 */
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, ".."), R = ROOT + "/results/gomoku";
const G = require("./rules.js"), L = require("./lines.js"), T2 = require("./teacher2.js"), E = require("./engine.js"), F2 = require("./fly2.js"), { rng32 } = require("./arena.js");
const DEPTH_PLAY = +(process.env.DEPTH_PLAY || 4), DEPTH_LABEL = +(process.env.DEPTH_LABEL || 8), EPS = 0.25;

if (process.argv[2] === "merge") {
  const DIR = `${R}/${process.argv[3]}`, files = fs.readdirSync(DIR).filter(f => /^shard_\d+\.json$/.test(f)).sort();
  let samples = [], nGames = 0, secs = 0, src = null;
  for (const f of files) { const d = JSON.parse(fs.readFileSync(`${DIR}/${f}`, "utf8")); samples = samples.concat(d.samples); nGames = d.n_games; secs += d.seconds; src = d.table; }
  samples.sort((a, b) => a.g - b.g || a.ply - b.ply);
  const testFrom = Math.floor(nGames * 0.8), nC = samples.reduce((a, s) => a + s.cands.length, 0);
  const off = new Uint32Array(samples.length + 1), cell = new Uint8Array(nC), codes = new Uint16Array(nC * 4); let p = 0;
  samples.forEach((s, k) => { off[k] = p; const b = new Uint8Array(Buffer.from(s.board, "base64")); for (const i of s.cands) { cell[p] = i; codes.set(L.codesFor(b, i, s.me).att, p * 4); p++; } }); off[samples.length] = p;
  fs.writeFileSync(`${DIR}/cand_off.u32`, Buffer.from(off.buffer)); fs.writeFileSync(`${DIR}/cand_cell.u8`, Buffer.from(cell.buffer)); fs.writeFileSync(`${DIR}/cand_codes.u16`, Buffer.from(codes.buffer));
  fs.copyFileSync(`${R}/ds2/teacher_cls.json`, `${DIR}/teacher_cls.json`);
  const agree1 = +(samples.filter(s => s.best["1"] === s.best["8"]).length / samples.length).toFixed(4);
  fs.writeFileSync(`${DIR}/dataset2.json`, JSON.stringify({ n: samples.length, n_games: nGames, test_from_game: testFrom, table: src, depth_play: DEPTH_PLAY, depth_label: DEPTH_LABEL,
    n_train: samples.filter(s => s.g < testFrom).length, n_test: samples.filter(s => s.g >= testFrom).length, n_candidates: nC, greedy_agrees_with_label: agree1, cpu_seconds: +secs.toFixed(0),
    samples: samples.map(s => ({ g: s.g, ply: s.ply, me: s.me, board: s.board, best: s.best, s8: [] })) }));
  console.log(`${nGames} 局 → ${samples.length} 个局面；直觉与"想 ${DEPTH_LABEL} 步"一致的比例 ${agree1}；CPU ${secs.toFixed(0)} s`);
  process.exit(0);
}
const [tableFile, outName, SHARD, NSHARD] = [process.argv[2], process.argv[3], +process.argv[4], +process.argv[5]], NGAMES = +(process.argv[6] || 600);
const DIR = `${R}/${outName}`; fs.mkdirSync(DIR, { recursive: true });
const j = JSON.parse(fs.readFileSync(`${R}/${tableFile}`, "utf8")), eng = E.makeEngine(F2.loadTable(j).att, j.lam);
const samples = [], t0 = Date.now();
for (let g = SHARD; g < NGAMES; g += NSHARD) {
  const rand = rng32(90000 + g), b = G.newBoard(); let c = G.BLACK;
  for (let ply = 0; ply < 80; ply++) {
    let mv;
    if (ply < 2) { do { mv = G.idx(5 + ((rand() * 5) | 0), 5 + ((rand() * 5) | 0)); } while (b[mv] !== G.EMPTY); }
    else {
      const cands = G.candidates(b, 2).filter(i => !(c === G.BLACK && G.forbidden(b, i % G.N, (i / G.N) | 0)));
      if (cands.length < 2) break;
      const k = T2.vcf(b.slice(), c, 12), lab = k >= 0 ? k : eng.think(b, c, { depth: DEPTH_LABEL }).move, g1 = eng.greedy(b, c);
      if (lab >= 0 && cands.includes(lab)) samples.push({ g, ply, me: c, board: Buffer.from(b).toString("base64"), cands, best: { 1: g1, 8: lab } });
      mv = eng.think(b, c, { depth: DEPTH_PLAY }).move;
      if (rand() < EPS) { const sc = F2.scoreCells({ att: F2.loadTable(j).att, def: F2.loadTable(j).def }, b, c).sort((p, q) => q[1] - p[1]).slice(0, 4); mv = sc[(rand() * sc.length) | 0][0]; }
    }
    if (mv < 0 || b[mv]) break;
    b[mv] = c; if (G.wins(b, mv % G.N, (mv / G.N) | 0, c)) break; c = c === G.BLACK ? G.WHITE : G.BLACK;
  }
  if (((g - SHARD) / NSHARD) % 10 === 0) console.log(`分片 ${SHARD}：第 ${g} 局，${samples.length} 个局面，${((Date.now() - t0) / 1000).toFixed(0)} s`);
}
fs.writeFileSync(`${DIR}/shard_${SHARD}.json`, JSON.stringify({ shard: SHARD, n_games: NGAMES, table: tableFile, seconds: (Date.now() - t0) / 1000, samples }));
console.log(`分片 ${SHARD} 完成：${samples.length} 个局面`);
