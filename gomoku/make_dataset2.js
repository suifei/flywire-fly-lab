#!/usr/bin/env node
/**
 * 训练数据 v2：混合水平的自对弈产生局面，再用老师 v2 在**多个搜索深度**上给每个局面打标签。
 *
 *   · 局面来源：每局双方各自随机取深度 ∈ {1,2,3,4}，并以 EPS 概率从前 5 名里随机挑一步——
 *     这样既有高手局面也有臭棋局面，果蝇以后自己下出来的烂局面也在分布里。
 *   · 标签：深度 1,2,3,4,5,6,8 的最佳着（深度 = 向前看的总步数），外加深度 8 的根候选分数。
 *   · **按整局切分**训练/测试（同一局的相邻局面高度相关）。
 *
 * 用法：node gomoku/make_dataset2.js <分片号> <分片数> [总局数=800]
 * 输出：results/gomoku/ds2/shard_<k>.json ；合并：node gomoku/make_dataset2.js merge
 */
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, "..");
const G = require("./rules.js"), T = require("./teacher2.js"), L = require("./lines.js");
const { rng32 } = require("./arena.js");
const DIR = ROOT + "/results/gomoku/" + (process.env.DS_DIR || "ds2");      // DS_DIR=ds2_tiny 用来调试流水线
const DEPTHS = [1, 2, 3, 4, 5, 6, 8], EPS = 0.2;
fs.mkdirSync(DIR, { recursive: true });

if (process.argv[2] === "merge") {
  const files = fs.readdirSync(DIR).filter(f => /^shard_\d+\.json$/.test(f)).sort();
  let samples = [], nGames = 0, secs = 0;
  for (const f of files) { const d = JSON.parse(fs.readFileSync(DIR + "/" + f, "utf8")); samples = samples.concat(d.samples); nGames = d.n_games; secs += d.seconds; }
  samples.sort((a, b) => a.g - b.g || a.ply - b.ply);
  const testFrom = Math.floor(nGames * 0.8);
  // 训练用的紧凑二进制：每个候选点 = 格子下标(u8) + 4 个进攻线型编码(u16)
  const nC = samples.reduce((a, s) => a + s.cands.length, 0);
  const off = new Uint32Array(samples.length + 1), cell = new Uint8Array(nC), codes = new Uint16Array(nC * 4);
  let p = 0;
  samples.forEach((s, k) => {
    off[k] = p;
    const b = new Uint8Array(Buffer.from(s.board, "base64"));
    for (const i of s.cands) { cell[p] = i; const c = L.codesFor(b, i, s.me).att; codes.set(c, p * 4); p++; }
  });
  off[samples.length] = p;
  fs.writeFileSync(DIR + "/cand_off.u32", Buffer.from(off.buffer));
  fs.writeFileSync(DIR + "/cand_cell.u8", Buffer.from(cell.buffer));
  fs.writeFileSync(DIR + "/cand_codes.u16", Buffer.from(codes.buffer));
  const agree = {}; for (const d of DEPTHS) agree[d] = +(samples.filter(s => s.best[d] === s.best[8]).length / samples.length).toFixed(4);
  const meta = { n: samples.length, n_games: nGames, test_from_game: testFrom, depths: DEPTHS, eps: EPS, n_candidates: nC,
    n_train: samples.filter(s => s.g < testFrom).length, n_test: samples.filter(s => s.g >= testFrom).length,
    agree_with_depth8: agree, cpu_seconds: +secs.toFixed(0),
    note: "按整局切分；深度 = 向前看的总步数；cand_* 三个二进制文件与 samples 同序",
    samples: samples.map(s => ({ g: s.g, ply: s.ply, me: s.me, board: s.board, best: s.best, s8: s.s8 })) };
  fs.writeFileSync(DIR + "/dataset2.json", JSON.stringify(meta));
  console.log(`${nGames} 局 → ${samples.length} 个局面（训练 ${meta.n_train} / 测试 ${meta.n_test}），候选点 ${nC} 个，CPU ${secs.toFixed(0)} s`);
  console.log("各深度的最佳着与深度 8 相同的比例：", JSON.stringify(agree));
  process.exit(0);
}

const SHARD = +process.argv[2], NSHARD = +process.argv[3], NGAMES = +(process.argv[4] || 800);
const samples = [], t0 = Date.now();
for (let g = SHARD; g < NGAMES; g += NSHARD) {
  const rand = rng32(50000 + g), b = G.newBoard();
  const dep = { [G.BLACK]: 1 + ((rand() * 4) | 0), [G.WHITE]: 1 + ((rand() * 4) | 0) };
  let c = G.BLACK;
  for (let ply = 0; ply < 90; ply++) {
    let mv;
    if (ply < 2) { do { mv = G.idx(5 + ((rand() * 5) | 0), 5 + ((rand() * 5) | 0)); } while (b[mv] !== G.EMPTY); }
    else {
      const cands = G.candidates(b, 2).filter(i => !(c === G.BLACK && G.forbidden(b, i % G.N, (i / G.N) | 0)));
      if (!cands.length) break;
      const best = {}; let s8 = null;
      for (const d of DEPTHS) { const r = T.search(b, c, d); best[d] = r.move; if (d === 8) s8 = r.scores.map(([i, v]) => [i, Math.round(Math.max(-2e9, Math.min(2e9, v)))]); }
      samples.push({ g, ply, me: c, board: Buffer.from(b).toString("base64"), cands, best, s8 });
      const r = T.search(b, c, dep[c]);
      mv = r.move;
      if (rand() < EPS) { const top = r.scores.slice().sort((p, q) => q[1] - p[1]).slice(0, 5); mv = top[(rand() * top.length) | 0][0]; }
    }
    if (mv < 0) break;
    b[mv] = c;
    if (G.wins(b, mv % G.N, (mv / G.N) | 0, c)) break;
    c = c === G.BLACK ? G.WHITE : G.BLACK;
  }
  if ((g - SHARD) / NSHARD % 10 === 0) console.log(`分片 ${SHARD}：第 ${g} 局，${samples.length} 个局面，${((Date.now() - t0) / 1000).toFixed(0)} s`);
}
fs.writeFileSync(`${DIR}/shard_${SHARD}.json`, JSON.stringify({ shard: SHARD, n_games: NGAMES, seconds: (Date.now() - t0) / 1000, samples }));
console.log(`分片 ${SHARD} 完成：${samples.length} 个局面，${((Date.now() - t0) / 1000).toFixed(0)} s`);
