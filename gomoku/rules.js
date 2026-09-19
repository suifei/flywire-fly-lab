// 五子棋规则引擎（15×15，含黑方禁手），与渲染无关，页面与 node 共用。
//
// 禁手按连珠（Renju）规则，只对**黑方**生效：
//   长连  六子及以上连成一线
//   四四  一手同时形成两个及以上「四」
//   三三  一手同时形成两个及以上「活三」
// 说明（诚实起见写在这里）：完整连珠规则里禁手点的判定是**递归**的
// （形成三时要看那个三能不能真的成四，而成四的点本身可能又是禁手）。
// 这里只做**一层**判定，不递归。对本项目的用途（生成训练数据、人机对弈）足够，
// 但和专业连珠裁判会有极少数分歧。
(function (root) {
  const N = 15, SIZE = N * N;
  const DIRS = [[1, 0], [0, 1], [1, 1], [1, -1]];
  const EMPTY = 0, BLACK = 1, WHITE = 2;

  const idx = (x, y) => y * N + x;
  const inside = (x, y) => x >= 0 && x < N && y >= 0 && y < N;

  function newBoard() { return new Uint8Array(SIZE); }

  // 沿一个方向数同色连子（不含落子点本身），返回 [连子数, 端点是否为空]
  function ray(b, x, y, dx, dy, c) {
    let n = 0, cx = x + dx, cy = y + dy;
    while (inside(cx, cy) && b[idx(cx, cy)] === c) { n++; cx += dx; cy += dy; }
    const open = inside(cx, cy) && b[idx(cx, cy)] === EMPTY;
    return [n, open, cx, cy];
  }

  // 落子后是否成五（黑方恰好 5；白方 ≥5 都算赢）
  function wins(b, x, y, c) {
    for (const [dx, dy] of DIRS) {
      const [a] = ray(b, x, y, dx, dy, c), [d] = ray(b, x, y, -dx, -dy, c);
      const len = a + d + 1;
      if (c === BLACK ? len === 5 : len >= 5) return true;
    }
    return false;
  }

  function overline(b, x, y) {
    for (const [dx, dy] of DIRS) {
      const [a] = ray(b, x, y, dx, dy, BLACK), [d] = ray(b, x, y, -dx, -dy, BLACK);
      if (a + d + 1 >= 6) return true;
    }
    return false;
  }

  // 取一条线上以 (x,y) 为中心、半径 5 的模式串（'x' 界外，'0' 空，'1' 己方，'2' 对方）
  function line(b, x, y, dx, dy, me) {
    let s = "";
    for (let k = -5; k <= 5; k++) {
      const cx = x + dx * k, cy = y + dy * k;
      if (!inside(cx, cy)) { s += "x"; continue; }
      const v = b[idx(cx, cy)];
      s += v === EMPTY ? "0" : v === me ? "1" : "2";
    }
    return s;
  }

  // 在一条线的模式串里数「活三」与「四」（中心第 5 位已经是落子后的己方子）
  const FOUR = ["11110", "01111", "11011", "10111", "11101"];
  const OPEN3 = ["011100", "010110", "011010"];
  function countLine(s) {
    let four = 0, open3 = 0;
    // 「四」：任一处再落一子即成五
    for (let i = 0; i + 5 <= s.length; i++) {
      const w = s.slice(i, i + 5);
      if (i <= 5 && i + 5 > 5 && FOUR.includes(w)) four++;
    }
    for (let i = 0; i + 6 <= s.length; i++) {
      const w = s.slice(i, i + 6);
      if (i <= 5 && i + 6 > 5 && OPEN3.includes(w)) open3++;
    }
    return { four: four > 0 ? 1 : 0, open3: open3 > 0 ? 1 : 0 };
  }

  // 黑方禁手判定：先在副本上落子，再看长连 / 四四 / 三三
  function forbidden(b, x, y) {
    if (b[idx(x, y)] !== EMPTY) return null;
    b[idx(x, y)] = BLACK;
    let bad = null;
    try {
      if (wins(b, x, y, BLACK)) return null;             // 成五优先于一切禁手
      if (overline(b, x, y)) return "长连";
      let f = 0, t = 0;
      for (const [dx, dy] of DIRS) {
        const c = countLine(line(b, x, y, dx, dy, BLACK));
        f += c.four; t += c.open3;
      }
      if (f >= 2) bad = "四四";
      else if (t >= 2) bad = "三三";
    } finally { b[idx(x, y)] = EMPTY; }
    return bad;
  }

  function legalMoves(b, c) {
    const out = [];
    for (let i = 0; i < SIZE; i++) {
      if (b[i] !== EMPTY) continue;
      if (c === BLACK && forbidden(b, i % N, (i / N) | 0)) continue;
      out.push(i);
    }
    return out;
  }

  // 只考虑已有棋子附近 r 格的空点（开局给中心）——搜索与训练都用这个候选集
  function candidates(b, r = 2) {
    const out = [];
    let any = false;
    for (let i = 0; i < SIZE; i++) if (b[i] !== EMPTY) { any = true; break; }
    if (!any) return [idx(7, 7)];
    for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
      if (b[idx(x, y)] !== EMPTY) continue;
      let near = false;
      for (let dy = -r; dy <= r && !near; dy++) for (let dx = -r; dx <= r; dx++) {
        const cx = x + dx, cy = y + dy;
        if (inside(cx, cy) && b[idx(cx, cy)] !== EMPTY) { near = true; break; }
      }
      if (near) out.push(idx(x, y));
    }
    return out;
  }

  const API = { N, SIZE, EMPTY, BLACK, WHITE, DIRS, idx, inside, newBoard, wins, forbidden, legalMoves,
                candidates, line, countLine, ray };
  if (typeof module !== "undefined" && module.exports) module.exports = API;
  else root.Gomoku = API;
})(typeof window !== "undefined" ? window : globalThis);
