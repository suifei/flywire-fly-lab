#!/usr/bin/env node
/**
 * 造五子棋训练数据：老师自对弈（带随机扰动保证局面多样），每一步记下
 * 「当前局面 + 老师给每个候选点的分数 + 老师的最佳着」。
 *
 * **按整局切分训练/测试**——同一局里相邻局面高度相关，按局面随机切会泄漏。
 *
 * 用法：node gomoku/make_dataset.js [局数=400] [随机率=0.25]
 * 输出：results/gomoku/dataset.json
 */
const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "..");
const G = require("./rules.js");
const T = require("./teacher.js");
const NGAMES = +(process.argv[2] || 400), EPS = +(process.argv[3] || 0.25);

function rng32(seed) {
  let s = seed >>> 0;
  return () => { s = (s + 0x6d2b79f5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

const b64 = u8 => Buffer.from(u8).toString("base64");
const samples = [];
let wins = { 1: 0, 2: 0, draw: 0 }, forb = 0;
const t0 = Date.now();

for (let g = 0; g < NGAMES; g++) {
  const rand = rng32(1000 + g);
  const b = G.newBoard();
  let c = G.BLACK, over = false;
  for (let ply = 0; ply < 120 && !over; ply++) {
    const { move, scores } = T.best(b, c);
    if (move < 0) { wins.draw++; break; }
    // 记录样本：老师的分数向量（只记候选点）
    const cand = [...scores.entries()];
    if (cand.length >= 4 && ply >= 2) {
      samples.push({ g, ply, board: b64(b), me: c, best: move,
                     cand: cand.map(([i, s]) => [i, +s.toFixed(1)]) });
    }
    // 走子：以 EPS 的概率从前 5 名里随机挑一个（制造多样性，但不走明显的坏棋）
    let mv = move;
    if (rand() < EPS) {
      const top = cand.sort((a, d) => d[1] - a[1]).slice(0, 5);
      mv = top[(rand() * top.length) | 0][0];
    }
    if (c === G.BLACK && G.forbidden(b, mv % G.N, (mv / G.N) | 0)) { forb++; continue; }
    b[mv] = c;
    if (G.wins(b, mv % G.N, (mv / G.N) | 0, c)) { wins[c]++; over = true; break; }
    c = c === G.BLACK ? G.WHITE : G.BLACK;
  }
  if (!over && g % 50 === 0) process.stdout.write(`\r  ${g}/${NGAMES} 局，${samples.length} 个局面`);
}
const testFrom = Math.floor(NGAMES * 0.8);
const out = { n_games: NGAMES, eps: EPS, test_from_game: testFrom,
  note: "按整局切分：前 80% 的局用于训练，后 20% 用于测试（同一局的相邻局面相关，按局面切会泄漏）",
  wins, forbidden_skipped: forb, n: samples.length, samples };
fs.mkdirSync(ROOT + "/results/gomoku", { recursive: true });
fs.writeFileSync(ROOT + "/results/gomoku/dataset.json", JSON.stringify(out));
console.log(`\n${NGAMES} 局 → ${samples.length} 个局面（训练 ${samples.filter(s => s.g < testFrom).length} / 测试 ${samples.filter(s => s.g >= testFrom).length}）`);
console.log(`黑胜 ${wins[1]}、白胜 ${wins[2]}、和/未终局 ${wins.draw}；禁手跳过 ${forb} 次；用时 ${((Date.now() - t0) / 1000).toFixed(0)} s`);
