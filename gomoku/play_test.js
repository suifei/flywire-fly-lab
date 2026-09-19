#!/usr/bin/env node
/**
 * 果蝇真的下几盘：不只看"和老师的最佳着一致率"，直接让它对局。
 *
 * 四个对手，全部对照：
 *   fly_intact    真实连接组 + 训练好的线性读出
 *   fly_shuffled  **打乱接线** + 在打乱特征上单独训练的读出（如果有）
 *   random        在合法点里瞎走
 *   teacher       生成训练数据的那个启发式引擎（果蝇的老师，相当于上限）
 *
 * 用法：node gomoku/play_test.js [每组局数=30]
 * 输出：results/gomoku/play.json
 */
const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "..");
const G = require("./rules.js");
const T = require("./teacher.js");
const FLY = require("./fly.js");
const { ConnectomeBrain } = require(ROOT + "/dodge/brain.js");
const NG = +(process.argv[2] || 30);
const SUB = JSON.parse(fs.readFileSync(ROOT + "/results/dodge/subcircuit_v2.json", "utf8"));
const RO = JSON.parse(fs.readFileSync(ROOT + "/results/gomoku/readout.json", "utf8"));

function rng32(seed) { let s = seed >>> 0;
  return () => { s = (s + 0x6d2b79f5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

const ROS = fs.existsSync(ROOT + "/results/gomoku/readout_shuffled.json")
  ? JSON.parse(fs.readFileSync(ROOT + "/results/gomoku/readout_shuffled.json", "utf8")) : null;
const flyI = FLY.makePlayer(SUB, ConnectomeBrain, RO);
// 打乱脑：**连接组打乱 + 在打乱特征上单独训练的读出**。两边都换掉才是干净的对照。
const flyS = ROS ? FLY.makePlayer(SUB, ConnectomeBrain, ROS, { shuffle: true }) : null;
const AGENTS = {
  fly_intact: (b, c) => flyI.think(b, c).move,
  fly_shuffled: (b, c) => (flyS ? flyS.think(b, c).move : -1),
  teacher: (b, c) => T.best(b, c).move,
  random: (() => { const r = rng32(4242);
    return (b, c) => { const m = G.legalMoves(b, c); return m.length ? m[(r() * m.length) | 0] : -1; }; })(),
};

function game(a, b, seed) {
  const board = G.newBoard();
  let c = G.BLACK;
  for (let ply = 0; ply < 225; ply++) {
    const f = c === G.BLACK ? a : b;
    let mv = AGENTS[f](board, c);
    if (mv < 0 || board[mv] !== G.EMPTY) return { win: 0, ply, why: "无子可走" };
    // 开局前两手加一点随机，避免每局完全相同
    if (ply < 2) { const cands = G.candidates(board, 2); mv = cands[(rng32(seed * 31 + ply)() * cands.length) | 0]; }
    board[mv] = c;
    if (G.wins(board, mv % G.N, (mv / G.N) | 0, c)) return { win: c, ply };
    c = c === G.BLACK ? G.WHITE : G.BLACK;
  }
  return { win: 0, ply: 225, why: "和棋" };
}

const pairs = [["fly_intact", "random"], ["random", "fly_intact"],
               ["fly_intact", "teacher"], ["teacher", "fly_intact"]];
if (flyS) pairs.push(["fly_shuffled", "random"], ["random", "fly_shuffled"],
                     ["fly_intact", "fly_shuffled"], ["fly_shuffled", "fly_intact"]);
const out = { n_games_per_pair: NG, readout_test_top1: RO.test.top1, results: [] };
const t0 = Date.now();
for (const [A, B] of pairs) {
  let wa = 0, wb = 0, dr = 0, plies = 0;
  for (let g = 0; g < NG; g++) {
    const r = game(A, B, g + 1);
    plies += r.ply;
    if (r.win === G.BLACK) wa++; else if (r.win === G.WHITE) wb++; else dr++;
  }
  const rec = { black: A, white: B, black_win: wa, white_win: wb, draw: dr, mean_ply: +(plies / NG).toFixed(1) };
  out.results.push(rec);
  console.log(`黑 ${A.padEnd(12)} vs 白 ${B.padEnd(12)}  ${wa}:${wb}（和 ${dr}），平均 ${rec.mean_ply} 手`);
}
const winsOf = (who, vs) => out.results.filter(r => (r.black === who && r.white === vs) || (r.white === who && r.black === vs))
  .reduce((a, r) => a + (r.black === who ? r.black_win : r.white_win), 0);
out.vs_random = { fly_intact: winsOf("fly_intact", "random"), fly_shuffled: flyS ? winsOf("fly_shuffled", "random") : null, of: NG * 2 };
out.vs_teacher = { fly_intact: winsOf("fly_intact", "teacher"), of: NG * 2 };
if (flyS) out.head_to_head = { fly_intact: winsOf("fly_intact", "fly_shuffled"), of: NG * 2 };
out.fly_total_wins = out.vs_random.fly_intact + out.vs_teacher.fly_intact;
out.fly_total_games = NG * 4;
// 事先写死的判据：如果打乱脑打随机也赢得差不多，那连接组对棋力没有贡献
out.criterion_connectome_helps_play = flyS
  ? (out.vs_random.fly_intact - out.vs_random.fly_shuffled) > NG * 2 * 0.15 : null;
fs.writeFileSync(ROOT + "/results/gomoku/play.json", JSON.stringify(out, null, 1));
console.log(`\n打随机：真实接线 ${out.vs_random.fly_intact}/${out.vs_random.of}` +
  (flyS ? `，打乱接线 ${out.vs_random.fly_shuffled}/${out.vs_random.of}` : "") +
  `　打老师：${out.vs_teacher.fly_intact}/${out.vs_teacher.of}`);
if (flyS) console.log(`真实 vs 打乱 正面交锋：${out.head_to_head.fly_intact}/${out.head_to_head.of}　` +
  `判据（连接组对棋力有贡献）${out.criterion_connectome_helps_play ? "成立" : "不成立"}`);
console.log(`用时 ${((Date.now() - t0) / 1000).toFixed(0)} s → results/gomoku/play.json`);
