// 五子棋"老师"：一个纯启发式的评分引擎，用来**生成训练数据**和当对手。
// 它不是果蝇的一部分——果蝇只学它给出的落子偏好。
//
// 评分方式（标准做法）：对每个候选点，算「我下这里」的进攻分 + 「对手下这里」的防守分。
// 每个方向上把 9 格窗口里的己方连子形态映射成分值：成五 > 活四 > 冲四 ≈ 活三 > 眠三 > 活二。
(function (root) {
  const G = typeof module !== "undefined" && module.exports ? require("./rules.js") : root.Gomoku;
  const { N, EMPTY, BLACK, WHITE, DIRS, idx, inside } = G;

  const VAL = { five: 1e7, open4: 1e6, four: 1e4, open3: 8e3, three: 5e2, open2: 2e2, two: 20 };

  // 沿一个方向，统计落子后己方的连子长度与两端开放情况
  function shape(b, x, y, dx, dy, c) {
    let n = 1, open = 0, gap = 0;
    for (const s of [1, -1]) {
      let cx = x + dx * s, cy = y + dy * s, run = 0;
      while (inside(cx, cy) && b[idx(cx, cy)] === c) { run++; cx += dx * s; cy += dy * s; }
      n += run;
      if (inside(cx, cy) && b[idx(cx, cy)] === EMPTY) {
        open++;
        // 跳一格看看还有没有己方子（"跳四""跳三"）
        const gx = cx + dx * s, gy = cy + dy * s;
        if (inside(gx, gy) && b[idx(gx, gy)] === c) gap++;
      }
    }
    return { n, open, gap };
  }

  function dirScore(b, x, y, dx, dy, c) {
    const { n, open, gap } = shape(b, x, y, dx, dy, c);
    if (n >= 5) return VAL.five;
    if (n === 4) return open === 2 ? VAL.open4 : open === 1 ? VAL.four : 0;
    if (n === 3) return open === 2 ? (gap ? VAL.open4 * 0.4 : VAL.open3) : open === 1 ? VAL.three : 0;
    if (n === 2) return open === 2 ? (gap ? VAL.open3 * 0.3 : VAL.open2) : open === 1 ? VAL.two : 0;
    return open === 2 ? 4 : 1;
  }

  function moveScore(b, i, c) {
    const x = i % N, y = (i / N) | 0;
    b[i] = c;
    let s = 0;
    for (const [dx, dy] of DIRS) s += dirScore(b, x, y, dx, dy, c);
    b[i] = EMPTY;
    return s;
  }

  // 每个候选点的总分：进攻 + 0.9 × 防守（对手下在这里的价值）
  function scoreAll(b, c, cands) {
    const o = c === BLACK ? WHITE : BLACK;
    const out = new Map();
    for (const i of cands) {
      if (c === BLACK && G.forbidden(b, i % N, (i / N) | 0)) continue;   // 禁手点直接排除
      out.set(i, moveScore(b, i, c) + 0.9 * moveScore(b, i, o));
    }
    return out;
  }

  function best(b, c, r = 2) {
    const cands = G.candidates(b, r);
    const sc = scoreAll(b, c, cands);
    let bi = -1, bs = -Infinity;
    for (const [i, s] of sc) if (s > bs) { bs = s; bi = i; }
    return { move: bi, score: bs, scores: sc };
  }

  const API = { VAL, moveScore, scoreAll, best };
  if (typeof module !== "undefined" && module.exports) module.exports = API;
  else root.GomokuTeacher = API;
})(typeof window !== "undefined" ? window : globalThis);
