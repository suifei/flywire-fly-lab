#!/usr/bin/env node
/**
 * 外部考卷：Karesis/Gomoku（HuggingFace，MIT；WinePy = Wine 五子棋引擎的 Python 版自对弈，
 * alpha-beta 4–10 步，875 局 / 26,378 手）。存放：external/gomoku_wine/（只读，不改）。
 *
 * **为什么要它**：我们自己的测试集是「果蝇的着法与我们自己写的老师一不一致」——老师和果蝇共用同一套
 * 线型定义，有自己出题自己判的嫌疑。Wine 是别人写的引擎，标签与我们的老师无关。
 * 这份数据**只用来考，不参与训练**。
 *
 * 口径差异（如实记录）：Wine 是无禁手规则；我们的候选集对黑方排除了禁手点，且只取已有棋子周围 2 格。
 * Wine 的着法落在我们候选集之外的局面会被剔除，剔除数写进元信息。
 *
 * 用法：node gomoku/import_wine.js   → results/gomoku/ds_wine/{dataset2.json, cand_*.u*}
 */
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, ".."), DIR = ROOT + "/results/gomoku/ds_wine";
const G = require("./rules.js"), L = require("./lines.js");
const games = JSON.parse(fs.readFileSync(ROOT + "/external/gomoku_wine/complete_games.json", "utf8"));
fs.mkdirSync(DIR, { recursive: true });
const samples = []; let total = 0, outside = 0, forbid = 0, occupied = 0;
games.forEach((seq, g) => {
  const b = G.newBoard();
  seq.forEach((m, ply) => {
    const i = Math.abs(m), c = m > 0 ? G.BLACK : G.WHITE;      // 正 = 黑，负 = 白；|m| = y*15+x（0 起）
    if (ply === 0 && m === 0) { b[0] = G.BLACK; return; }
    total++;
    if (b[i] !== G.EMPTY) { occupied++; return; }
    if (ply >= 2) {
      const cands = G.candidates(b, 2).filter(k => !(c === G.BLACK && G.forbidden(b, k % G.N, (k / G.N) | 0)));
      if (!cands.includes(i)) { if (c === G.BLACK && G.forbidden(b, i % G.N, (i / G.N) | 0)) forbid++; else outside++; }
      else if (cands.length >= 2) samples.push({ g, ply, me: c, board: Buffer.from(b).toString("base64"), cands, best: { wine: i } });
    }
    b[i] = c;
  });
});
const nC = samples.reduce((a, s) => a + s.cands.length, 0);
const off = new Uint32Array(samples.length + 1), cell = new Uint8Array(nC), codes = new Uint16Array(nC * 4);
let p = 0;
samples.forEach((s, k) => { off[k] = p; const b = new Uint8Array(Buffer.from(s.board, "base64"));
  for (const i of s.cands) { cell[p] = i; codes.set(L.codesFor(b, i, s.me).att, p * 4); p++; } });
off[samples.length] = p;
fs.writeFileSync(DIR + "/cand_off.u32", Buffer.from(off.buffer));
fs.writeFileSync(DIR + "/cand_cell.u8", Buffer.from(cell.buffer));
fs.writeFileSync(DIR + "/cand_codes.u16", Buffer.from(codes.buffer));
const meta = { source: "Karesis/Gomoku (HuggingFace, MIT) — WinePy self-play", n_games: games.length, moves_total: total, n: samples.length,
  dropped: { outside_radius2: outside, black_forbidden_under_renju: forbid, occupied: occupied, first_two_plies: games.length * 2 },
  n_candidates: nC, samples: samples.map(s => ({ g: s.g, ply: s.ply, me: s.me, board: s.board, best: s.best })) };
fs.writeFileSync(DIR + "/dataset2.json", JSON.stringify(meta));
console.log(`Wine：${games.length} 局 ${total} 手 → 可用 ${samples.length} 个局面；剔除：候选集外 ${outside}、黑方禁手 ${forbid}、落在已有子上 ${occupied}`);
