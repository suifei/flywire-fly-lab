// 线型（line pattern）：五子棋真正的"视觉单元"。页面与 node 共用。
//
// 对一个候选空点，沿 4 个方向各取它两侧 4 格，共 8 格；每格 ∈ {空, 我方, 对方, 边界}。
// 永远从**要落子的一方**看（我方 = 1）。防守价值 = 把同一条线的我方/对方互换后再看。
//
// 为什么换成线型（2026-09-19，见 report §46）：上一版把**整盘棋**随机铺到感觉神经元上，
// 丢掉了五子棋最要紧的两条性质——局部性与平移不变性。同一个"活三"出现在棋盘不同位置，
// 对那一版来说是两个毫不相干的输入，1 万个局面根本不够学。线型版里它们是同一个输入。
//
// 合法线型总数：边界只能从外侧连续地进来，每侧 0–4 格 ⇒ (81+27+9+3+1)² = 14,641 种。
// 这个数小到可以让果蝇脑把**每一种都跑一遍**。
(function (root) {
  const G = typeof module !== "undefined" && module.exports ? require("./rules.js") : root.Gomoku;
  const { N, EMPTY, DIRS, inside, idx } = G;
  const E = 0, ME = 1, OPP = 2, WALL = 3, HALF = 4, LEN = 8, NCODE = 1 << (2 * LEN);   // 4^8 = 65,536

  // 8 格 → 一个 16 位编码。格子顺序：[-4,-3,-2,-1,+1,+2,+3,+4]
  const encode = cells => { let c = 0; for (let k = 0; k < LEN; k++) c |= cells[k] << (2 * k); return c; };
  const decode = code => { const o = new Uint8Array(LEN); for (let k = 0; k < LEN; k++) o[k] = (code >> (2 * k)) & 3; return o; };
  const swap = code => { let o = 0; for (let k = 0; k < LEN; k++) { const v = (code >> (2 * k)) & 3; o |= (v === ME ? OPP : v === OPP ? ME : v) << (2 * k); } return o; };
  const mirror = code => { let o = 0; for (let k = 0; k < LEN; k++) o |= ((code >> (2 * k)) & 3) << (2 * (LEN - 1 - k)); return o; };

  // 候选点 (x,y) 沿方向 d 的线型编码，从颜色 me 的视角
  function codeAt(b, x, y, d, me) {
    const [dx, dy] = DIRS[d];
    let c = 0;
    for (let k = 0; k < LEN; k++) {
      const s = k < HALF ? k - HALF : k - HALF + 1;          // -4..-1, +1..+4
      const cx = x + dx * s, cy = y + dy * s;
      let v;
      if (!inside(cx, cy)) v = WALL;
      else { const q = b[idx(cx, cy)]; v = q === EMPTY ? E : q === me ? ME : OPP; }
      c |= v << (2 * k);
    }
    return c;
  }
  // 一个候选点的 8 个编码：4 条进攻线 + 4 条防守线（= 互换视角）
  function codesFor(b, i, me) {
    const x = i % N, y = (i / N) | 0, att = new Uint16Array(4), def = new Uint16Array(4);
    for (let d = 0; d < 4; d++) { att[d] = codeAt(b, x, y, d, me); def[d] = swap(att[d]); }
    return { att, def };
  }

  // 全部合法线型（边界从外侧连续进来）
  function allCodes() {
    const out = [];
    const side = [];                                          // 一侧 4 格（由外到内）的全部合法取值
    for (let w = 0; w <= HALF; w++) {
      const free = HALF - w, n = 3 ** free;
      for (let t = 0; t < n; t++) {
        const cells = new Array(HALF).fill(WALL); let r = t;
        for (let k = 0; k < free; k++) { cells[w + k] = r % 3; r = (r / 3) | 0; }
        side.push(cells);                                     // cells[0] 最外侧
      }
    }
    for (const L of side) for (const R of side) {
      const cells = [L[0], L[1], L[2], L[3], R[3], R[2], R[1], R[0]];
      out.push(encode(cells));
    }
    return Uint16Array.from(out).sort();
  }

  // 线型 → 24 个通道里哪些点亮：格子 k × {我方, 对方, 边界}
  const NCH = LEN * 3;
  function channelsOf(code) {
    const on = [];
    for (let k = 0; k < LEN; k++) { const v = (code >> (2 * k)) & 3; if (v !== E) on.push(k * 3 + (v - 1)); }
    return on;
  }

  // 给人看的名字（只用于可视化与报告，不参与任何计算）
  const show = code => Array.from(decode(code)).map(v => "·XO#"[v]).join("").replace(/^(.{4})/, "$1[_]");

  const API = { E, ME, OPP, WALL, LEN, HALF, NCODE, NCH, encode, decode, swap, mirror, codeAt, codesFor, allCodes, channelsOf, show };
  if (typeof module !== "undefined" && module.exports) module.exports = API;
  else root.GomokuLines = API;
})(typeof window !== "undefined" ? window : globalThis);
