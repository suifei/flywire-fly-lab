// 快速搜索引擎：**增量维护**每个空点的线型价值。页面与 node 共用。
//
// 它只需要一张「线型 → 进攻价值」的表 att[]（线性尺度）和一个标量 λ：
//     落子分(点) = Σ_4方向 att[我方视角线型] + λ · Σ_4方向 att[对方视角线型]      ← 走法排序 / 直觉下法（与训练的模型同一个式子）
//     局面估值   = tempo · Σ_候选点 我方进攻价值 − Σ_候选点 对方进攻价值            ← 与老师的叶子估值同一形式
// 表可以是果蝇学到的，也可以是老师的——引擎不关心来源。引擎自己**不含任何棋形分值**。
// 它知道的只有规则事实：成五 = 赢（黑方须恰好五）、对手有成五点就必须挡、黑方禁手（问规则引擎）。
//
// 增量：落一子只会改变它所在 4 条线上、距离 ≤4 的空点的线型（≤32 个点），
//       所以 make/unmake 是 O(32)，局面估值是 O(1)，走法生成不用再扫全盘。
(function (root) {
  const node = typeof module !== "undefined" && module.exports;
  const G = node ? require("./rules.js") : root.Gomoku;
  const L = node ? require("./lines.js") : root.GomokuLines;
  const { N, SIZE, EMPTY, BLACK, WHITE, DIRS } = G;
  const WIN = 1e9;

  // 规则事实表：在这条线的中心落我方子之后，穿过中心的连子长度（只看这条线）
  const RUN = new Uint8Array(L.NCODE), SWAP = new Uint16Array(L.NCODE);
  for (let c = 0; c < L.NCODE; c++) {
    let n = 1; for (let k = 3; k >= 0 && ((c >> (2 * k)) & 3) === L.ME; k--) n++; for (let k = 4; k < 8 && ((c >> (2 * k)) & 3) === L.ME; k++) n++;
    RUN[c] = n; SWAP[c] = L.swap(c);
  }
  // Zobrist
  const ZOB = [new Uint32Array(SIZE), new Uint32Array(SIZE), new Uint32Array(SIZE)];
  { let s = 0x9e3779b9; const r = () => { s ^= s << 13; s >>>= 0; s ^= s >>> 17; s ^= s << 5; s >>>= 0; return s; }; for (let c = 1; c <= 2; c++) for (let i = 0; i < SIZE; i++) ZOB[c][i] = r(); }

  // 禁手规则里的「三」「四」：落子后这条线上再下一子能成五 = 四；再下一子能成活四 = 活三。按定义递归算，不用任何分值。
  let _shape = null;
  function defaultShape() {
    if (_shape) return _shape;
    const five = a => { let r = 0; for (let k = 0; k < 9; k++) { r = a[k] === 1 ? r + 1 : 0; if (r >= 5) return true; } return false; };
    const nFive = a => { let c = 0; for (let j = 0; j < 9; j++) if (a[j] === 0) { a[j] = 1; if (five(a)) c++; a[j] = 0; } return c; };
    _shape = new Uint8Array(L.NCODE);
    for (const code of L.allCodes()) {
      const a = new Uint8Array(9); for (let k = 0; k < 8; k++) { const v = (code >> (2 * k)) & 3; a[k < 4 ? k : k + 1] = v === L.ME ? 1 : v === L.E ? 0 : 2; } a[4] = 1;
      if (five(a)) continue;
      let sh = nFive(a) >= 1 ? 1 : 0;
      if (!sh) for (let j = 0; j < 9 && !sh; j++) if (a[j] === 0) { a[j] = 1; if (nFive(a) >= 2) sh = 1; a[j] = 0; }
      _shape[code] = sh;
    }
    return _shape;
  }

  function makeEngine(att, lam, opt = {}) {
    const tempo = opt.tempo ?? 1.2, PVS = opt.pvs !== false;
    const b = new Uint8Array(SIZE), near = new Uint8Array(SIZE);
    const codeB = new Uint16Array(SIZE * 4);                   // 每个点、每个方向：黑方视角的线型编码
    const aB = new Float64Array(SIZE), aW = new Float64Array(SIZE), fB = new Uint8Array(SIZE), fW = new Uint8Array(SIZE);
    let SB = 0, SW = 0, hash = 0, stones = 0, nodes = 0, deadline = Infinity, maxNodes = Infinity, aborted = false, Kdeep = null, KdeepFrom = 99;
    const TT = new Map(), history = new Float64Array(SIZE * 3), scoreBuf = new Float64Array(SIZE);
    const SHAPE = opt.shape || defaultShape();                  // 线型 → 落子后这条线是否成「活三 / 四」（规则事实，用于禁手预筛）

    function recompute(q) {                                     // 由 4 个编码重算 q 点的双方价值与成五标记
      let vb = 0, vw = 0, five_b = 0, five_w = 0;
      for (let d = 0; d < 4; d++) { const c = codeB[q * 4 + d], w = SWAP[c]; vb += att[c]; vw += att[w]; if (RUN[c] === 5) five_b = 1; if (RUN[w] >= 5) five_w = 1; }
      aB[q] = vb; aW[q] = vw; fB[q] = five_b; fW[q] = five_w;
    }
    const isCand = q => b[q] === EMPTY && near[q] > 0;
    function touchLines(p) {                                    // p 点变化后，刷新 4 条线上 ≤32 个空点
      const x = p % N, y = (p / N) | 0;
      for (let d = 0; d < 4; d++) { const dx = DIRS[d][0], dy = DIRS[d][1];
        for (let s = -4; s <= 4; s++) { if (!s) continue; const cx = x + dx * s, cy = y + dy * s; if (cx < 0 || cy < 0 || cx >= N || cy >= N) continue;
          const q = cy * N + cx; if (b[q] !== EMPTY) continue;
          const cand = near[q] > 0; if (cand) { SB -= aB[q]; SW -= aW[q]; }
          codeB[q * 4 + d] = L.codeAt(b, cx, cy, d, BLACK); recompute(q);
          if (cand) { SB += aB[q]; SW += aW[q]; } } }
    }
    function bumpNear(p, delta) {
      const x = p % N, y = (p / N) | 0;
      for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) { const cx = x + dx, cy = y + dy; if (cx < 0 || cy < 0 || cx >= N || cy >= N) continue;
        const q = cy * N + cx, was = near[q] > 0; near[q] += delta; const now = near[q] > 0;
        if (was !== now && b[q] === EMPTY && q !== p) { if (now) { SB += aB[q]; SW += aW[q]; } else { SB -= aB[q]; SW -= aW[q]; } } }
    }
    function place(p, c) {
      if (near[p] > 0) { SB -= aB[p]; SW -= aW[p]; }
      b[p] = c; hash ^= ZOB[c][p]; stones++;
      bumpNear(p, 1); touchLines(p);
    }
    function undo(p) {
      const c = b[p]; b[p] = EMPTY; hash ^= ZOB[c][p]; stones--;
      bumpNear(p, -1);
      const x = p % N, y = (p / N) | 0; for (let d = 0; d < 4; d++) codeB[p * 4 + d] = L.codeAt(b, x, y, d, BLACK); recompute(p);
      touchLines(p);
      if (near[p] > 0) { SB += aB[p]; SW += aW[p]; }
    }
    function setBoard(board) {
      b.fill(0); near.fill(0); SB = SW = 0; hash = 0; stones = 0; TT.clear(); history.fill(0);
      for (let q = 0; q < SIZE; q++) { const x = q % N, y = (q / N) | 0; for (let d = 0; d < 4; d++) codeB[q * 4 + d] = L.codeAt(b, x, y, d, BLACK); recompute(q); }
      for (let q = 0; q < SIZE; q++) if (board[q]) place(q, board[q]);
    }

    const realFive = q => { b[q] = BLACK; const w = G.wins(b, q % N, (q / N) | 0, BLACK); b[q] = EMPTY; return w; };
    // 走法生成：返回 {win} | {lost} | {moves:[点...]}（已按 落子分 + 历史启发 排序并截到 K）
    const buf = [];
    function gen(me, K, ttMove) {
      const mine = me === BLACK ? aB : aW, theirs = me === BLACK ? aW : aB, myF = me === BLACK ? fB : fW, opF = me === BLACK ? fW : fB;
      let block = -1, nBlock = 0; buf.length = 0; const blocks = [];
      for (let q = 0; q < SIZE; q++) {
        if (b[q] !== EMPTY || near[q] === 0) continue;
        // 线型窗口只看两侧各 4 格：「中心 + 一侧 4 子」在窗口里是五连，但第 5 格外若还有黑子，实际是六连（长连禁手）。
        // 所以**黑方**的五连要再问一次规则引擎（白方 ≥5 都算赢，不用问）。2026-09-20 由随机局面测试抓到。
        if (myF[q]) { if (me !== BLACK || realFive(q)) return { win: q }; continue; }      // 黑方假五 = 长连 = 禁手点，直接跳过
        if (opF[q] && (me === BLACK || realFive(q))) { nBlock++; block = q; blocks.push(q); }
        buf.push(q);
      }
      if (stones === 0) return { moves: [G.idx(7, 7)] };
      if (nBlock >= 1) {                                       // 必须挡；挡不住（≥2 个成五点，或黑方的挡点是禁手）就输
        // 必败也得走出一步**合法**的棋（页面不能卡在禁手上）：优先挡其中一个，黑方要避开禁手点
        const legal = q => !(me === BLACK && G.forbidden(b, q % N, (q / N) | 0));
        const okBlocks = blocks.filter(legal);
        if (nBlock >= 2 || !okBlocks.length) { const any = okBlocks.length ? okBlocks : buf.filter(legal).slice(0, 1); return { lost: true, moves: any }; }
        return { moves: [okBlocks[0]], forced: true };
      }
      // 分数只算一次，存进 scoreBuf 再排序（原来在比较函数里反复重算，是走法生成里最贵的一项）
      const hb = me * SIZE;
      for (const q of buf) scoreBuf[q] = mine[q] + lam * theirs[q] + history[hb + q] + (q === ttMove ? 1e30 : 0);
      buf.sort((p, q) => scoreBuf[q] - scoreBuf[p]);
      const out = [];
      for (const q of buf) {
        // 黑方禁手：只有**可能**构成双三 / 双四 / 长连的点才去问规则引擎（预筛只用"这条线落子后是不是三或四"这一规则事实）
        if (me === BLACK && mayForbid(q) && G.forbidden(b, q % N, (q / N) | 0)) continue;
        out.push(q); if (out.length >= K) break;
      }
      return { moves: out };
    }
    // 预筛：黑方在 q 落子后，≥2 条线成「三或四」，或某条线连到 6 以上 ⇒ 才有可能是禁手
    function mayForbid(q) {
      if (!SHAPE) return true;
      let n = 0;
      for (let d = 0; d < 4; d++) { const c = codeB[q * 4 + d]; if (RUN[c] >= 6) return true; if (SHAPE[c]) n++; }
      return n >= 2;
    }
    const evalFor = me => (me === BLACK ? tempo * SB - SW : tempo * SW - SB);

    function negamax(me, depth, alpha, beta, ply, K) {
      if (++nodes > maxNodes || ((nodes & 1023) === 0 && Date.now() > deadline)) { aborted = true; return 0; }
      const key = hash * 4 + me, tt = TT.get(key), a0 = alpha;
      let ttMove = -1;
      if (tt) { ttMove = tt.m; if (tt.d >= depth) { if (tt.f === 0) return tt.v; if (tt.f === 1 && tt.v >= beta) return tt.v; if (tt.f === 2 && tt.v <= alpha) return tt.v; } }
      const g = gen(me, (Kdeep && ply >= KdeepFrom) ? Kdeep : K, ttMove);
      if (g.win !== undefined) return WIN - ply;
      if (g.lost) return -WIN + ply + 1;
      if (!g.moves.length) return 0;
      if (depth <= 0) return evalFor(me);
      const opp = me === BLACK ? WHITE : BLACK;
      let best = -Infinity, bm = g.moves[0];
      let first = true;
      for (const q of g.moves) {
        place(q, me);
        const nd = depth - (g.forced ? 0 : 1);                  // 被迫的挡子不消耗深度（单一应手延伸）
        let v;
        if (first || !PVS) v = -negamax(opp, nd, -beta, -alpha, ply + 1, K);
        else {                                                   // PVS：其余着法先用零宽窗口试探，试出来更好才用完整窗口重搜
          v = -negamax(opp, nd, -alpha - 1e-9 - Math.abs(alpha) * 1e-12, -alpha, ply + 1, K);
          if (v > alpha && v < beta && !aborted) v = -negamax(opp, nd, -beta, -alpha, ply + 1, K);
        }
        first = false;
        undo(q);
        if (aborted) return 0;
        if (v > best) { best = v; bm = q; }
        if (v > alpha) alpha = v;
        if (alpha >= beta) { history[me * SIZE + q] += depth * depth * 1e-3; break; }
      }
      TT.set(key, { d: depth, v: best, m: bm, f: best <= a0 ? 2 : best >= beta ? 1 : 0 });
      return best;
    }

    // 根：迭代加深。opt: {depth} 固定深度 ｜ {budgetMs} 限时。返回 {move, depth, score, nodes, ms, pv_scores}
    function think(board, me, o = {}) {
      const t0 = Date.now(); setBoard(board); nodes = 0; aborted = false;
      // 宽度 K = 每层只展开落子分最高的 K 个点。同等节点预算（2 万）下 K=6 对 K=10 是 62–38（100 局，见 side_experiments.js width）：
      // 收窄之后搜得更深。4–6 之间在 100 局的噪声里分不出高下，取 6。根节点保持 16，免得一开始就漏掉好点。
      const K = o.K ?? 6, K0 = o.K0 ?? 16, maxDepth = o.depth ?? 30;
      deadline = o.budgetMs ? t0 + o.budgetMs : Infinity;
      maxNodes = o.maxNodes ?? Infinity;                        // 按节点数计的预算：确定性的，不受机器负载影响（对比实验用）
      Kdeep = o.Kdeep ?? null; KdeepFrom = o.KdeepFrom ?? 3;    // 离根 ≥ KdeepFrom 步之后把宽度收窄到 Kdeep
      const g = gen(me, K0, -1);
      if (g.win !== undefined) return { move: g.win, depth: 0, score: WIN, nodes, ms: Date.now() - t0, how: "win" };
      if (!g.moves.length) return { move: -1, depth: 0, score: 0, nodes, ms: 0 };
      if (g.lost) return { move: g.moves[0], depth: 0, score: -WIN, nodes, ms: Date.now() - t0, how: "lost" };
      let order = g.moves.slice(), best = { move: order[0], depth: 0, score: 0 };
      if (order.length === 1) return { move: order[0], depth: 0, score: 0, nodes, ms: Date.now() - t0, how: g.forced ? "block" : "only" };
      const opp = me === BLACK ? WHITE : BLACK;
      for (let d = 1; d <= maxDepth; d++) {
        let alpha = -Infinity, bm = order[0]; const sc = new Map();
        let firstRoot = true;
        for (const q of order) {
          place(q, me);
          let v;
          if (firstRoot || !PVS || alpha === -Infinity) v = -negamax(opp, d - 1, -Infinity, -alpha, 1, K);
          else { v = -negamax(opp, d - 1, -alpha - 1e-9 - Math.abs(alpha) * 1e-12, -alpha, 1, K); if (v > alpha && !aborted) v = -negamax(opp, d - 1, -Infinity, -alpha, 1, K); }
          firstRoot = false; undo(q);
          if (aborted) break;
          sc.set(q, v); if (v > alpha) { alpha = v; bm = q; }
        }
        if (aborted) break;
        order.sort((p, q) => (sc.get(q) ?? -Infinity) - (sc.get(p) ?? -Infinity));
        best = { move: bm, depth: d, score: alpha, ranked: order.slice(0, 6) };      // ranked：按这一层的搜索值排好的根着法（防杀棋时换着用）
        if (Math.abs(alpha) > WIN / 2) break;                    // 已算出必胜/必败
        if (o.budgetMs && (Date.now() - t0) * 3 > o.budgetMs) break;
        if (o.maxNodes && nodes * 3 > o.maxNodes) break;
      }
      return { ...best, nodes, ms: Date.now() - t0, how: "search" };
    }
    // 直觉（只看一步）：落子分最大的合法点
    function greedy(board, me) { setBoard(board); const g = gen(me, 1, -1); return g.win !== undefined ? g.win : (g.moves.length ? g.moves[0] : -1); }
    // 供核对增量维护是否正确：与从头重算对比
    function selfCheck(board) {
      setBoard(board); const s1 = [SB, SW];
      let sb = 0, sw = 0; for (let q = 0; q < SIZE; q++) { if (board[q] || near[q] === 0) continue; const x = q % N, y = (q / N) | 0; for (let d = 0; d < 4; d++) { const c = L.codeAt(board, x, y, d, BLACK); sb += att[c]; sw += att[SWAP[c]]; } }
      return { inc: s1, full: [sb, sw] };
    }
    return { think, greedy, selfCheck, place, undo, setBoard, evalFor, state: () => ({ SB, SW, hash, stones }) };
  }

  const API = { makeEngine, RUN, WIN };
  if (node) module.exports = API; else root.GomokuEngine = API;
})(typeof window !== "undefined" ? window : globalThis);
