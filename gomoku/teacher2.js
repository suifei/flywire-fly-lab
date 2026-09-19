// 五子棋老师 v2：**线型价值表 + alpha-beta 搜索**。用来生成训练数据、当对手、当棋力标尺。
// 它不是果蝇的一部分。和果蝇共用的只有 lines.js 的线型编码——这样老师的价值表与果蝇学到的
// 价值表定义在同一组 14,641 个线型上，可以逐格对比。
//
// 线型分类用的是递归定义（不是手抄的模式串表）：
//   成五  落子后已有 ≥5 连
//   活四  落子后有 ≥2 个点能成五        冲四  恰好 1 个点能成五
//   活三  再下一子能变活四              眠三  再下一子只能变冲四
//   活二  再下一子能变活三              眠二  再下一子只能变眠三
// **分值是手选的**（下面 ATT / DEF / 组合加分），不是任何论文或引擎的值；它的棋力主要来自搜索深度。
(function (root) {
  const node = typeof module !== "undefined" && module.exports;
  const G = node ? require("./rules.js") : root.Gomoku;
  const L = node ? require("./lines.js") : root.GomokuLines;
  const { N, SIZE, EMPTY, BLACK, WHITE } = G;
  const NONE = 0, ONE = 1, TWO = 2, OPEN2 = 3, THREE = 4, OPEN3 = 5, FOUR = 6, OPEN4 = 7, FIVE = 8;
  const NAMES = ["无", "单子", "眠二", "活二", "眠三", "活三", "冲四", "活四", "成五"];
  const ATT = [0, 1, 10, 100, 120, 1500, 2000, 1e5, 1e7];
  const DEF = [0, 1, 8, 80, 90, 1200, 300, 2e4, 1e6];
  const WIN = 1e9;

  // ── 线型分类表 ───────────────────────────────────────────────────────────
  const hasFive = a => { let r = 0; for (let k = 0; k < 9; k++) { r = a[k] === 1 ? r + 1 : 0; if (r >= 5) return true; } return false; };
  const fiveCompletions = a => { let c = 0; for (let j = 0; j < 9; j++) if (a[j] === 0) { a[j] = 1; if (hasFive(a)) c++; a[j] = 0; } return c; };
  function level3(a) {                     // 已知不是五/四：看再下一子能到哪一级
    let best = 0;
    for (let j = 0; j < 9; j++) if (a[j] === 0) { a[j] = 1; const c = fiveCompletions(a); a[j] = 0; if (c >= 2) return OPEN3; if (c === 1) best = THREE; }
    return best;
  }
  function classify(a) {
    if (hasFive(a)) return FIVE;
    const c = fiveCompletions(a);
    if (c >= 2) return OPEN4;
    if (c === 1) return FOUR;
    const t = level3(a);
    if (t) return t;
    let best = 0;
    for (let j = 0; j < 9; j++) if (a[j] === 0) { a[j] = 1; const s = level3(a); a[j] = 0; if (s === OPEN3) { best = OPEN2; break; } if (s === THREE) best = TWO; }
    if (best) return best;
    // 这条线上还有没有可能成五（9 格窗口里存在一段 5 连的空间）
    for (let s = 0; s <= 4; s++) { let ok = true; for (let k = s; k < s + 5; k++) if (a[k] === 2) { ok = false; break; } if (ok) return ONE; }
    return NONE;
  }
  const CLS = new Uint8Array(L.NCODE), SWAP = new Uint16Array(L.NCODE);
  for (const code of L.allCodes()) {
    const c = L.decode(code), a = new Uint8Array(9);
    for (let k = 0; k < 8; k++) a[k < 4 ? k : k + 1] = c[k] === L.ME ? 1 : c[k] === L.E ? 0 : 2;
    a[4] = 1;
    CLS[code] = classify(a);
    SWAP[code] = L.swap(code);
  }
  // 老师的线型价值表（与果蝇学到的表同定义域，可逐格对比）
  const attTable = () => { const t = new Float32Array(L.NCODE); for (const c of L.allCodes()) t[c] = ATT[CLS[c]]; return t; };
  const defTable = () => { const t = new Float32Array(L.NCODE); for (const c of L.allCodes()) t[c] = DEF[CLS[c]]; return t; };

  // ── 一个候选点的分数 ─────────────────────────────────────────────────────
  // tables：{att, def}（Float32Array，按线型编码索引）。传果蝇学到的表进来，搜索就变成"果蝇在想"。
  // 组合加分（双四 / 四三 / 双三）只在用老师自己的表时才加——果蝇的表里没有"类别"这个概念。
  function cellScore(b, i, me, tables) {
    const x = i % N, y = (i / N) | 0;
    let s = 0, f = 0, t = 0, of = 0, ot = 0, mx = 0, omx = 0;
    for (let d = 0; d < 4; d++) {
      const code = L.codeAt(b, x, y, d, me), sw = SWAP[code];
      s += tables.att[code] + tables.def[sw];
      const c = CLS[code], oc = CLS[sw];
      if (c > mx) mx = c; if (oc > omx) omx = oc;
      if (c >= FOUR) f++; else if (c === OPEN3) t++;
      if (oc >= FOUR) of++; else if (oc === OPEN3) ot++;
    }
    if (tables.combo) {
      if (f >= 2 || (f >= 1 && t >= 1)) s += 8e4; else if (t >= 2) s += 2e4;
      if (of >= 2 || (of >= 1 && ot >= 1)) s += 4e4; else if (ot >= 2) s += 1e4;
    }
    return { s, mx, omx, f, t };
  }
  const TEACHER = { att: attTable(), def: defTable(), combo: true };

  // 只懂规则的走法生成：**不查棋形类别表**，只问规则引擎三件事——
  //   这一手我能不能直接赢？对手下在这里会不会直接赢（那我必须挡）？黑方这一手是不是禁手？
  // 果蝇的价值表只用来排序和估值。这样"果蝇 + 搜索"里没有任何一点老师的棋形知识。
  function genMovesRules(b, me, tables, K) {
    const opp = me === BLACK ? WHITE : BLACK, cands = G.candidates(b, 2), out = [], oppFive = [];
    for (const i of cands) {
      const x = i % N, y = (i / N) | 0;
      if (me === BLACK && G.forbidden(b, x, y)) continue;
      b[i] = me; const w = G.wins(b, x, y, me); b[i] = EMPTY;
      if (w) return { win: i, moves: [[i, WIN, FIVE]] };
      b[i] = opp; const ow = G.wins(b, x, y, opp); b[i] = EMPTY;
      if (ow) oppFive.push(i);
      let s = 0;
      for (let d = 0; d < 4; d++) { const code = L.codeAt(b, x, y, d, me); s += tables.att[code] + tables.def[SWAP[code]]; }
      out.push([i, s, 0]);
    }
    if (oppFive.length) return { forced: oppFive.length, moves: out.filter(m => oppFive.includes(m[0])) };
    out.sort((p, q) => q[1] - p[1]);
    return { moves: K ? out.slice(0, K) : out };
  }

  // 学出来的表（果蝇等）也走这条快路径。这里用到线型类别的地方**只有规则事实**：
  //   「这一手成不成五」「对手下这里成不成五」（= 胜负规则），以及「要不要去问规则引擎是不是禁手」的预筛。
  //   排序与估值全部来自传进来的表；组合加分只在 tables.combo（老师自己）时才加。
  // tables.rulesOnly = true 时改走 genMovesRules（完全不查类别表，慢 5 倍，结果应当一致——用来核对这句话）。
  function genMoves(b, me, tables, K) {
    if (tables.rulesOnly) return genMovesRules(b, me, tables, K);
    const cands = G.candidates(b, 2), out = [];
    let myFive = -1; const oppFive = [];
    for (const i of cands) {
      const r = cellScore(b, i, me, tables);
      if (me === BLACK && (r.mx === FIVE || r.f >= 2 || r.t >= 2) && G.forbidden(b, i % N, (i / N) | 0)) continue;
      if (r.mx === FIVE) { b[i] = me; const w = G.wins(b, i % N, (i / N) | 0, me); b[i] = EMPTY; if (w) { myFive = i; break; } }
      if (r.omx === FIVE) oppFive.push(i);
      out.push([i, r.s, r.mx]);
    }
    if (myFive >= 0) return { win: myFive, moves: [[myFive, WIN, FIVE]] };
    if (oppFive.length) return { forced: oppFive.length, moves: out.filter(m => oppFive.includes(m[0])) };
    out.sort((p, q) => q[1] - p[1]);
    return { moves: K ? out.slice(0, K) : out };
  }

  // 学出来的表（果蝇 / 对照臂）的叶子估值。表里存的是"这一步有多值得下"的相对偏好（softmax 的 logit），
  // 带任意常数偏移，**不能**像老师的分值那样对所有候选点求和（第一版这么做，想 3 步反而 0:20 全败）。
  // 这里只比双方**最强的两个进攻点**：先减掉空线型的基线（消掉偏移），再取 我方(最强 + ½次强) − 对方(同)。
  // tables.value 存在时改用训练出来的局面价值表（见 train_value.py）。
  function evaluateLearned(b, me, tables) {
    const cands = G.candidates(b, 2);
    if (tables.value) {
      let v = 0; const u = tables.value;
      for (const i of cands) { const x = i % N, y = (i / N) | 0; for (let d = 0; d < 4; d++) { const code = L.codeAt(b, x, y, d, me); v += u.me[code] - u.opp[SWAP[code]]; } }
      return v * (tables.valueScale || 1);
    }
    // 表是对数尺度（softmax 的 logit：成五 ≈ 4.7、活三 ≈ 1.5）。两个教训（都实测过，都是 0:16 全败）：
    //   ① 直接相减：「对手有活三」只值 3 个单位，被我方多一个活二抵掉；
    //   ② 先把一个点的 4 条线相加再取指数：一条活四线（5.5）+ 三条空线（各 −2.4）反而不如四条活二线。
    // 所以**每条线先各自取指数**还原成"几率"尺度，再在点内相加——一条活四线就该压过一切。
    // β 是搜索这一侧的手选参数（不属于果蝇），登记在台账 PARAMETERS 里。
    if (tables.linear) {                                       // form = "lse" 的表已经是线性尺度，直接按老师的形式求和
      // 两条**规则事实**（往前多看一步就能确定，不是棋形策略）：轮到我走且我有成五点 → 必胜；对手有 ≥2 个成五点 → 必败。
      let sm = 0, so = 0, myFive = false, oppFive = 0;
      for (const i of cands) {
        const x = i % N, y = (i / N) | 0; let of = false;
        for (let d = 0; d < 4; d++) { const code = L.codeAt(b, x, y, d, me), sw = SWAP[code]; sm += tables.att[code]; so += tables.att[sw];
          if (CLS[code] === FIVE) myFive = true; if (CLS[sw] === FIVE) of = true; }
        if (of) oppFive++;
      }
      if (myFive) return WIN - 1;
      if (oppFive >= 2) return -WIN + 2;
      return (tables.tempo ?? 1.2) * sm - so;
    }
    const be = tables.beta ?? 2, EX = tables._ex || (tables._ex = (() => { const t = new Float32Array(L.NCODE); for (let c = 0; c < L.NCODE; c++) t[c] = Math.exp(be * Math.min(tables.att[c], 12)); return t; })());
    let m1 = 0, m2 = 0, o1 = 0, o2 = 0, sm = 0, so = 0;
    for (const i of cands) {
      const x = i % N, y = (i / N) | 0; let a = 0, o = 0;
      for (let d = 0; d < 4; d++) { const code = L.codeAt(b, x, y, d, me); a += EX[code]; o += EX[SWAP[code]]; }
      sm += a; so += o;
      if (a > m1) { m2 = m1; m1 = a; } else if (a > m2) m2 = a;
      if (o > o1) { o2 = o1; o1 = o; } else if (o > o2) o2 = o;
    }
    if (tables.leaf === "top2") return (m1 + 0.5 * m2) * (tables.tempo ?? 1.3) - (o1 + 0.5 * o2);
    return (tables.tempo ?? 1.2) * sm - so;                  // 默认：与老师的叶子估值同一形式（双方全部候选点的进攻价值之和）
  }

  // 静态估值（轮到 me 走）：战术先行，其余按双方候选点分数之和
  function evaluate(b, me, tables) {
    if (!tables.combo) return evaluateLearned(b, me, tables);
    const opp = me === BLACK ? WHITE : BLACK, cands = G.candidates(b, 2);
    let sm = 0, so = 0, myMax = 0, oppFive = 0, myCombo = false;
    for (const i of cands) {
      const x = i % N, y = (i / N) | 0;
      let a = 0, o = 0, mx = 0, omx = 0, f = 0, t = 0;
      for (let d = 0; d < 4; d++) {
        const code = L.codeAt(b, x, y, d, me), sw = SWAP[code];
        a += tables.att[code]; o += tables.att[sw];
        const c = CLS[code], oc = CLS[sw];
        if (c > mx) mx = c; if (oc > omx) omx = oc;
        if (c >= FOUR) f++; else if (c === OPEN3) t++;
      }
      sm += a; so += o; if (mx > myMax) myMax = mx; if (omx === FIVE) oppFive++;
      if (f >= 2 || (f >= 1 && t >= 1)) myCombo = true;
    }
    if (tables.combo) {                       // 只有老师用类别做战术判断；果蝇的表只走求和那一支
      if (myMax === FIVE) return WIN - 1;
      if (oppFive >= 2) return -WIN + 2;
      if (!oppFive && myMax === OPEN4) return WIN - 3;
      if (!oppFive && myCombo) return 5e5 + sm - so;
    }
    return 1.2 * sm - so;
  }

  let nodes = 0;
  function negamax(b, me, depth, alpha, beta, tables, K, ply) {
    nodes++;
    const opp = me === BLACK ? WHITE : BLACK;
    const g = genMoves(b, me, tables, K);
    if (g.win !== undefined) return WIN - ply;
    if (!g.moves.length) return g.forced ? -WIN + ply : 0;
    if (depth <= 0) return evaluate(b, me, tables);
    let best = -Infinity;
    for (const [i] of g.moves) {
      b[i] = me;
      const v = -negamax(b, opp, depth - 1, -beta, -alpha, tables, K, ply + 1);
      b[i] = EMPTY;
      if (v > best) best = v;
      if (v > alpha) alpha = v;
      if (alpha >= beta) break;
    }
    return best;
  }

  // 根节点：返回最佳着与每个根候选的搜索值。depth = 向前看的总步数（1 = 只看自己这一步）
  function search(b, me, depth, opt = {}) {
    const tables = opt.tables || TEACHER, K = opt.K ?? 10, K0 = opt.K0 ?? 14;
    const opp = me === BLACK ? WHITE : BLACK;
    nodes = 0;
    const g = genMoves(b, me, tables, K0);
    if (!g.moves.length) return { move: -1, scores: [], nodes };
    if (g.win !== undefined) return { move: g.win, scores: [[g.win, WIN]], nodes, forced: "win" };
    const scores = [];
    let alpha = -Infinity, bi = g.moves[0][0];
    for (const [i, s0] of g.moves) {
      let v;
      if (depth <= 1) v = s0;                                   // 1 步 = 直接用候选点分数（与果蝇的贪心口径一致）
      else { b[i] = me; v = -negamax(b, opp, depth - 2, -Infinity, -alpha, tables, K, 1); b[i] = EMPTY; }
      scores.push([i, v]);
      if (v > alpha) { alpha = v; bi = i; }
    }
    return { move: bi, scores, nodes, forced: g.forced ? "block" : undefined };
  }

  // ── 连续冲四杀棋（VCF）：纯规则 ────────────────────────────────────────────
  // 进攻方每一手都必须造出"下一手就能成五"的点（= 四）；防守方只能去挡。造出两个成五点，或者
  // 防守方唯一的挡点是黑方禁手点 ⇒ 杀棋成立。只用 G.wins / G.forbidden，不查任何棋形表。
  function winCellsNear(b, i, c) {                            // 落子 i 之后，c 在 i 所在四条线上的成五点
    const x = i % N, y = (i / N) | 0, out = [];
    for (const [dx, dy] of G.DIRS) for (let s = -4; s <= 4; s++) {
      if (!s) continue; const cx = x + dx * s, cy = y + dy * s;
      if (!G.inside(cx, cy)) continue; const j = cy * N + cx;
      if (b[j] !== EMPTY || out.includes(j)) continue;
      b[j] = c; const w = G.wins(b, cx, cy, c); b[j] = EMPTY;
      if (w && !(c === BLACK && G.forbidden(b, cx, cy))) out.push(j);
    }
    return out;
  }
  let vcfNodes = 0;
  function vcfRec(b, me, depth, only) {
    if (depth <= 0 || ++vcfNodes > 20000) return -1;
    const opp = me === BLACK ? WHITE : BLACK;
    for (const i of (only || G.candidates(b, 1))) {
      const x = i % N, y = (i / N) | 0;
      if (me === BLACK && G.forbidden(b, x, y)) continue;
      b[i] = me;
      if (G.wins(b, x, y, me)) { b[i] = EMPTY; return i; }
      const wc = winCellsNear(b, i, me);
      let ok = false;
      if (wc.length >= 2) ok = true;
      else if (wc.length === 1) {
        const j = wc[0], jx = j % N, jy = (j / N) | 0;
        if (opp === BLACK && G.forbidden(b, jx, jy)) ok = true;           // 黑方挡不了（禁手点）
        else {
          b[j] = opp;
          const oppWins = G.wins(b, jx, jy, opp);                          // 对手这一挡顺便成五了
          const oppFour = !oppWins && winCellsNear(b, j, opp).length > 0;  // 对手这一挡顺便反冲四：杀棋链断了，保守起见不算
          if (!oppWins && !oppFour && vcfRec(b, me, depth - 1) >= 0) ok = true;
          b[j] = EMPTY;
        }
      }
      b[i] = EMPTY;
      if (ok) return i;
    }
    return -1;
  }
  // 根节点的前提：**对手此刻若已有成五点，我这一手必须先挡住它**（第一版漏了这条，带杀棋搜索的一方
  // 会顾着自己冲四而不挡对手的四，实测 1 胜 19 负）。递归内部不用再查——防守方的挡子一旦顺便成四，那条分支已被放弃。
  function vcf(b, me, depth = 8) {
    vcfNodes = 0;
    const opp = me === BLACK ? WHITE : BLACK, threats = [];
    for (const j of G.candidates(b, 1)) { const x = j % N, y = (j / N) | 0; b[j] = opp; const w = G.wins(b, x, y, opp); b[j] = EMPTY; if (w) threats.push(j); }
    if (threats.length >= 2) return -1;
    return vcfRec(b, me, depth, threats.length ? threats : null);
  }

  // 防杀：引擎选的这一步走下去之后，如果对手有连续冲四的杀棋，就按搜索排名换下一个；都躲不掉就还走原来那步。纯规则。
  function avoidVcf(b, me, ranked, depth = 12) {
    const opp = me === BLACK ? WHITE : BLACK;
    for (let k = 0; k < ranked.length; k++) { const i = ranked[k]; b[i] = me; const bad = vcf(b, opp, depth) >= 0; b[i] = EMPTY; if (!bad) return { move: i, skipped: k }; }
    return { move: ranked[0], skipped: 0, unavoidable: true };
  }

  // 完整棋手：先看自己有没有连续冲四的杀棋 → 再做限时迭代加深搜索；根节点上剔除"走了之后对手有杀棋"的着法
  function bestMove(b, me, opt = {}) {
    const budget = opt.budgetMs ?? 1000, opp = me === BLACK ? WHITE : BLACK, t0 = Date.now();
    if (opt.vcf !== false) { const k = vcf(b, me, opt.vcfDepth ?? 8); if (k >= 0) return { move: k, how: "vcf", ms: Date.now() - t0 }; }
    const r = opt.depth ? search(b, me, opt.depth, opt) : searchTimed(b, me, budget, opt);
    if (opt.vcf !== false && r.scores.length > 1 && !r.forced) {
      const order = r.scores.slice().sort((p, q) => q[1] - p[1]);
      for (const [i] of order.slice(0, 6)) {
        b[i] = me; const bad = vcf(b, opp, opt.vcfDepth ?? 8) >= 0; b[i] = EMPTY;
        if (!bad) { r.move = i; break; }
        r.avoided = (r.avoided || 0) + 1;
      }
    }
    r.how = "search"; r.ms = Date.now() - t0;
    return r;
  }

  // 迭代加深：在时间预算内能搜多深搜多深（页面上"果蝇想多久"用这个）。每一层都是完整搜索，超时就用上一层的结果。
  function searchTimed(b, me, budgetMs, opt = {}) {
    const t0 = Date.now(), maxDepth = opt.maxDepth ?? 12;
    let best = search(b, me, 1, opt); best.depth = 1;
    for (let d = 2; d <= maxDepth; d++) {
      if (best.forced === "win" || Math.abs(best.scores.find(s => s[0] === best.move)?.[1] ?? 0) > WIN / 2) break;   // 已经算出必胜/必败
      const spent = Date.now() - t0;
      if (spent * 4 > budgetMs) break;                        // 下一层大约要 4 倍时间，来不及就不开
      const r = search(b, me, d, opt); r.depth = d; best = r;
    }
    best.ms = Date.now() - t0;
    return best;
  }

  const API = { NAMES, ATT, DEF, CLS, SWAP, WIN, TEACHER, searchTimed, genMovesRules, vcf, avoidVcf, bestMove, classify, cellScore, genMoves, evaluate, search,
                attTable, defTable, NONE, ONE, TWO, OPEN2, THREE, OPEN3, FOUR, OPEN4, FIVE };
  if (node) module.exports = API; else root.GomokuTeacher2 = API;
})(typeof window !== "undefined" ? window : globalThis);
