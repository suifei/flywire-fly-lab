// 对弈场：两个"棋手函数"下若干局，轮流执黑。棋手 = (board, me, rand) → 落子下标。
const G = require("./rules.js");
function rng32(seed) { let s = seed >>> 0; return () => { s = (s + 0x6d2b79f5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
// 开局随机化：前 nOpen 手在中心 5×5 内随机落（两边共用同一个开局各执一次黑，公平）
function playGame(black, white, seed, nOpen = 2, maxPly = 160) {
  const rand = rng32(seed), b = G.newBoard(); let c = G.BLACK;
  for (let ply = 0; ply < maxPly; ply++) {
    let mv;
    if (ply < nOpen) { do { mv = G.idx(5 + ((rand() * 5) | 0), 5 + ((rand() * 5) | 0)); } while (b[mv] !== G.EMPTY || (c === G.BLACK && G.forbidden(b, mv % G.N, (mv / G.N) | 0))); }
    else mv = (c === G.BLACK ? black : white)(b, c, rand);
    if (mv < 0 || b[mv] !== G.EMPTY) return { winner: 0, ply, illegal: c };
    if (c === G.BLACK && G.forbidden(b, mv % G.N, (mv / G.N) | 0)) return { winner: G.WHITE, ply, forbidden: true };
    b[mv] = c;
    if (G.wins(b, mv % G.N, (mv / G.N) | 0, c)) return { winner: c, ply: ply + 1 };
    c = c === G.BLACK ? G.WHITE : G.BLACK;
  }
  return { winner: 0, ply: maxPly };
}
// A 对 B 下 nPairs 对（每个开局双方各执一次黑）。返回 A 的胜/负/和。
function match(A, B, nPairs, seed0 = 1) {
  let w = 0, l = 0, d = 0, ply = 0;
  for (let k = 0; k < nPairs; k++) {
    const r1 = playGame(A, B, seed0 + k), r2 = playGame(B, A, seed0 + k);
    for (const [r, aIs] of [[r1, G.BLACK], [r2, G.WHITE]]) { ply += r.ply; if (r.winner === 0) d++; else if (r.winner === aIs) w++; else l++; }
  }
  return { win: w, loss: l, draw: d, games: 2 * nPairs, mean_ply: +(ply / (2 * nPairs)).toFixed(1) };
}
const randomPlayer = (b, c, rand) => { const m = G.candidates(b, 2).filter(i => !(c === G.BLACK && G.forbidden(b, i % G.N, (i / G.N) | 0))); return m.length ? m[(rand() * m.length) | 0] : -1; };
module.exports = { playGame, match, randomPlayer, rng32 };
