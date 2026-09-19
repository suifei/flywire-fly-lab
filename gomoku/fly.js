// 果蝇怎么选一步棋：棋盘 → 真实神经元的泊松驱动 → 4,599 个神经元跑 100 ms →
// 下游发放计数 → **一层线性读出** → 225 个格子的分数 → 在合法点里取最大。
//
// 必须说清楚的三件事（页面上也照写）：
//   1. 果蝇脑里**一个突触都没有被训练**，全部来自 FlyWire 连接组。
//   2. 唯一被训练的是最后那层线性读出（岭回归，results/gomoku/train.json 里有全部对照）。
//   3. 禁手与合法性判断是**规则引擎**做的，不是果蝇——它只给分数。
(function (root) {
  const G = typeof module !== "undefined" && module.exports ? require("./rules.js") : root.Gomoku;
  const F = typeof module !== "undefined" && module.exports ? require("./features.js") : root.GomokuFeatures;

  function makePlayer(SUB, BrainClass, readout, opt = {}) {
    const brain = new BrainClass(SUB, opt.seed ?? 11);
    if (opt.shuffle) brain.setShuffle(true, 20260919);
    const map = F.makeMap(SUB);
    const cols = readout.col_idx, W = readout.W, mu = readout.mu, sd = readout.sd;
    const D = cols.length;
    return {
      brain, map, shuffled: !!opt.shuffle,
      // 返回 {move, scores}，scores 是 225 维（非法点为 -Infinity）
      think(board, me) {
        const cnt = F.featuresOf(brain, map, board, me, { hz: readout.hz, ms: readout.ms, seed: opt.featSeed ?? 777 });
        const x = new Float64Array(D + 1);
        for (let k = 0; k < D; k++) x[k] = (Math.sqrt(cnt[cols[k]]) - mu[k]) / sd[k];
        x[D] = 1;
        const s = new Float64Array(G.SIZE);
        for (let k = 0; k <= D; k++) {
          const v = x[k]; if (v === 0) continue;
          const row = W[k];
          for (let m = 0; m < G.SIZE; m++) s[m] += v * row[m];
        }
        const scores = new Float64Array(G.SIZE).fill(-Infinity);
        let bi = -1, bs = -Infinity;
        for (let i = 0; i < G.SIZE; i++) {
          if (board[i] !== G.EMPTY) continue;
          if (me === G.BLACK && G.forbidden(board, i % G.N, (i / G.N) | 0)) continue;
          scores[i] = s[i];
          if (s[i] > bs) { bs = s[i]; bi = i; }
        }
        return { move: bi, scores, raw: s };
      },
    };
  }

  const API = { makePlayer };
  if (typeof module !== "undefined" && module.exports) module.exports = API;
  else root.GomokuFly = API;
})(typeof window !== "undefined" ? window : globalThis);
