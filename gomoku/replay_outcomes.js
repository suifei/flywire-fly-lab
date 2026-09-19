#!/usr/bin/env node
/**
 * 给 ds2 的每一局补上**终局胜负**（估值头的训练标签）。
 * make_dataset2.js 当时没存胜负。这里按完全相同的随机流把 800 局重放一遍（走子只用深度 1–4，很快；
 * 打标签的深度 8 搜索不消耗随机数，所以不用重做）。**逐局核对**重放出的局面与存档的局面一致，不一致就报错退出。
 *
 * 用法：node gomoku/replay_outcomes.js <分片> <分片数> ｜ node gomoku/replay_outcomes.js merge
 * 输出：results/gomoku/ds2/outcomes.json  { winner: [每局 0/1/2], plies: [...] }
 */
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, ".."), DIR = ROOT + "/results/gomoku/ds2";
const G = require("./rules.js"), T = require("./teacher2.js"), { rng32 } = require("./arena.js");
const EPS = 0.2;
if (process.argv[2] === "merge") {
  const files = fs.readdirSync(DIR).filter(f => /^outcome_\d+\.json$/.test(f));
  const meta = JSON.parse(fs.readFileSync(DIR + "/dataset2.json", "utf8")), winner = new Array(meta.n_games).fill(-1), plies = new Array(meta.n_games).fill(0);
  let checked = 0;
  for (const f of files) { const d = JSON.parse(fs.readFileSync(DIR + "/" + f, "utf8")); for (const [g, w, p, c] of d.rows) { winner[g] = w; plies[g] = p; checked += c; } }
  if (winner.includes(-1)) throw new Error("有的局没有重放到");
  const cnt = [0, 0, 0]; winner.forEach(w => cnt[w]++);
  fs.writeFileSync(DIR + "/outcomes.json", JSON.stringify({ winner, plies, positions_verified: checked, counts: { unfinished: cnt[0], black: cnt[1], white: cnt[2] } }));
  console.log(`${meta.n_games} 局：黑胜 ${cnt[1]}、白胜 ${cnt[2]}、未分胜负 ${cnt[0]}；逐个核对过的局面 ${checked} / ${meta.n}`);
  process.exit(0);
}
const SHARD = +process.argv[2], NSHARD = +process.argv[3];
const meta = JSON.parse(fs.readFileSync(DIR + "/dataset2.json", "utf8"));
const stored = new Map(); for (const s of meta.samples) stored.set(s.g + ":" + s.ply, s.board);
const rows = [];
for (let g = SHARD; g < meta.n_games; g += NSHARD) {
  const rand = rng32(50000 + g), b = G.newBoard();
  const dep = { [G.BLACK]: 1 + ((rand() * 4) | 0), [G.WHITE]: 1 + ((rand() * 4) | 0) };
  let c = G.BLACK, winner = 0, ply = 0, checked = 0;
  for (; ply < 90; ply++) {
    let mv;
    if (ply < 2) { do { mv = G.idx(5 + ((rand() * 5) | 0), 5 + ((rand() * 5) | 0)); } while (b[mv] !== G.EMPTY); }
    else {
      const cands = G.candidates(b, 2).filter(i => !(c === G.BLACK && G.forbidden(b, i % G.N, (i / G.N) | 0)));
      if (!cands.length) break;
      const key = g + ":" + ply;
      if (stored.has(key)) { if (stored.get(key) !== Buffer.from(b).toString("base64")) throw new Error(`第 ${g} 局第 ${ply} 手：重放的局面与存档不一致`); checked++; }
      const r = T.search(b, c, dep[c]);
      mv = r.move;
      if (rand() < EPS) { const top = r.scores.slice().sort((p, q) => q[1] - p[1]).slice(0, 5); mv = top[(rand() * top.length) | 0][0]; }
    }
    if (mv < 0) break;
    b[mv] = c;
    if (G.wins(b, mv % G.N, (mv / G.N) | 0, c)) { winner = c; ply++; break; }
    c = c === G.BLACK ? G.WHITE : G.BLACK;
  }
  rows.push([g, winner, ply, checked]);
}
fs.writeFileSync(`${DIR}/outcome_${SHARD}.json`, JSON.stringify({ rows }));
console.log(`分片 ${SHARD}：${rows.length} 局`);
