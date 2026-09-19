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
    // 读出组与输入组：页面的「下行神经元」「感觉输入」两块面板在下棋时要显示**这一只**果蝇
    const READ = ["DNa01_left", "DNa01_right", "DNa02_left", "DNa02_right", "DNp01_left", "DNp01_right",
                  "MN9_left", "MN9_right", "aDN1_left", "aDN1_right", "MDN_left", "MDN_right"];
    const ING = Object.keys((SUB.meta && SUB.meta.inputs) || {});
    const cols = readout.col_idx, W = readout.W, mu = readout.mu, sd = readout.sd;
    const D = cols.length;
    return {
      brain, map, shuffled: !!opt.shuffle,
      // 返回 {move, scores}，scores 是 225 维（非法点为 -Infinity）
      lastStats: null,
      think(board, me) {
        const cnt = F.featuresOf(brain, map, board, me,
          { hz: readout.hz, ms: readout.ms, seed: opt.featSeed ?? 777, onSpike: opt.onSpike });
        // 这一次"思考"里每个读出组的平均发放率（Hz）与每个输入组被注入的比例
        const secs = readout.ms / 1000;
        const rates = {};
        for (const g of READ) {
          const idx = SUB.groups[g] || [];
          rates[g] = idx.length ? idx.reduce((a, i) => a + cnt[i], 0) / idx.length / secs : 0;
        }
        // 每个输入组**实际被棋盘点亮**的平均频率：棋盘格子随机铺在这些感觉神经元上，
        // 所以「感觉输入」那块面板在下棋时显示的是"这一组里有多少神经元被棋子点着"
        const r = F.ratesFor(map, board, me, readout.hz);
        const drive = {};
        for (const g of ING) for (const side of ["left", "right"]) {
          const key = g + "_" + side, idx = SUB.groups[key] || [];
          drive[key] = idx.length ? idx.reduce((a, i) => a + (r[i] || 0), 0) / idx.length : 0;
        }
        this.lastStats = { rates, drive, ms: readout.ms, hz: readout.hz };
        const x = new Float64Array(D + 1);
        // sd 可能是 0：那些神经元在训练集里从来不放电，导出时又被四舍五入成 0。
        // 不兜住的话这里会除出 Infinity → 整个分数向量变 NaN → 一个合法着都选不出来
        //（2026-09-19 实测：move 恒为 −1，棋盘上一子未落）。
        for (let k = 0; k < D; k++) { const d = sd[k] || 1e-6; x[k] = (Math.sqrt(cnt[cols[k]]) - mu[k]) / d; }
        x[D] = 1;
        const s = new Float64Array(G.SIZE);
        for (let k = 0; k <= D; k++) {
          const v = x[k]; if (v === 0) continue;
          const row = W[k];
          for (let m = 0; m < G.SIZE; m++) s[m] += v * row[m];
        }
        const scores = new Float64Array(G.SIZE).fill(-Infinity);
        let bi = -1, bs = -Infinity, nan = 0;
        for (let i = 0; i < G.SIZE; i++) {
          if (board[i] !== G.EMPTY) continue;
          if (me === G.BLACK && G.forbidden(board, i % G.N, (i / G.N) | 0)) continue;
          if (!Number.isFinite(s[i])) { nan++; continue; }
          scores[i] = s[i];
          if (s[i] > bs) { bs = s[i]; bi = i; }
        }
        if (bi < 0) {                                    // 兜底：读出层给不出有限分数时随便挑个合法点，但要说出来
          for (let i = 0; i < G.SIZE; i++) {
            if (board[i] !== G.EMPTY) continue;
            if (me === G.BLACK && G.forbidden(board, i % G.N, (i / G.N) | 0)) continue;
            bi = i; break;
          }
        }
        return { move: bi, scores, raw: s, nan };
      },
    };
  }

  const API = { makePlayer };
  if (typeof module !== "undefined" && module.exports) module.exports = API;
  else root.GomokuFly = API;
})(typeof window !== "undefined" ? window : globalThis);
