// 把棋盘送进果蝇脑，取出发放率特征。**页面与训练共用同一份代码**，否则线上与线下会不一致。
//
// 这是"水库计算"（reservoir computing）的用法，必须说清楚：
//   · 棋盘 → 神经元的映射是**任意的**（固定随机种子分配）。我们不假装果蝇在"看"棋盘，
//     也不假装这些感觉神经元天生编码棋子。
//   · 果蝇脑里**没有任何东西被训练**——突触权重全部来自 FlyWire 连接组，一个都没动。
//     唯一被训练的是最后一层**线性读出**。
//   · 因此"它会下棋"这句话必须带一个对照：把连接组打乱之后再训练同样的读出，
//     如果成绩不变，那就说明真实接线没起作用。这个对照是本项目做这件事的**全部意义**。
//
// 编码：棋盘永远从**当前该走的一方**看（通道 0 = 我方子，通道 1 = 对方子），所以不需要再告诉它轮到谁。
(function (root) {
  const G = typeof module !== "undefined" && module.exports ? require("./rules.js") : root.Gomoku;

  // 输入组从 SUB.meta.inputs 里读（v3 比 v2 多了 TOUCH/THERMO/HYGRO）。
  // **必须按实际子回路取**：写死成 v2 那 12 组的话，v3 的三路新输入会被当成"下游神经元"
  // 留在特征里——它们在下棋时恒为 0，虽不致命，但口径就不干净了。
  const FALLBACK_GROUPS = ["LC4", "LPLC2", "LC16", "SUGAR", "BITTER", "JO"];
  const inputGroupsOf = SUB => {
    const names = Object.keys((SUB.meta && SUB.meta.inputs) || {});
    const base = names.length ? names : FALLBACK_GROUPS;
    const out = [];
    for (const b of base) for (const side of ["left", "right"]) if (SUB.groups[b + "_" + side]) out.push(b + "_" + side);
    return out;
  };

  function rng32(seed) {
    let s = seed >>> 0;
    return () => { s = (s + 0x6d2b79f5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  }

  // 「保拓扑」分配表：按输入神经元的**真实胞体位置**在 x–y 平面上排序，
  // 让棋盘上相邻的格子落到空间上相邻的神经元。
  // 为什么要有这一版：随机分配把棋盘的邻接关系全打散了，果蝇没有任何理由能算出「连成五」——
  // 那样得到的阴性结果是我们自己造成的，不能算数。这一版给它一个公平的机会。
  function makeTopoMap(SUB, soma) {
    const inputs = [];
    for (const g of inputGroupsOf(SUB)) for (const i of (SUB.groups[g] || [])) inputs.push(i);
    // 胞体坐标投到 x–y（y 取反 = 背侧向上），按 y 分带、带内按 x 排 —— 得到一个二维扫描序
    const pts = inputs.map(i => ({ i, x: soma.xyz[i][0], y: -soma.xyz[i][1] }));
    const rows = Math.round(Math.sqrt(pts.length * (G.N / G.N)));      // 近似方阵
    pts.sort((a, b) => a.y - b.y);
    const perBand = Math.ceil(pts.length / rows);
    const order = [];
    for (let r = 0; r < rows; r++) {
      const band = pts.slice(r * perBand, (r + 1) * perBand).sort((a, b) => a.x - b.x);
      for (const p of band) order.push(p.i);
    }
    // 把这个扫描序按同样的二维顺序铺到 15×15 的格子上，每格分到 order 里连续的一小段；
    // 我方 / 对方两个通道**共用同一批神经元的两半**，这样"同一个格子"在空间上也是同一块。
    const chan = Array.from({ length: G.SIZE * 2 }, () => []);
    const perCell = Math.floor(order.length / G.SIZE);
    for (let c = 0; c < G.SIZE; c++) {
      const seg = order.slice(c * perCell, (c + 1) * perCell);
      const h = Math.ceil(seg.length / 2);
      chan[c * 2] = seg.slice(0, h);
      chan[c * 2 + 1] = seg.slice(h);
    }
    return { inputs, chan, nCh: G.SIZE * 2, topo: true, perCell };
  }

  // 固定的「格子×通道 → 输入神经元」分配表。种子写死，页面与训练必须一致。
  function makeMap(SUB, seed = 20260919) {
    const inputs = [];
    for (const g of inputGroupsOf(SUB)) for (const i of (SUB.groups[g] || [])) inputs.push(i);
    const rand = rng32(seed);
    const perm = inputs.slice();
    for (let i = perm.length - 1; i > 0; i--) { const j = (rand() * (i + 1)) | 0; [perm[i], perm[j]] = [perm[j], perm[i]]; }
    const nCh = G.SIZE * 2;                       // 225 格 × 2 通道
    const chan = Array.from({ length: nCh }, () => []);
    perm.forEach((n, k) => chan[k % nCh].push(n));
    return { inputs, chan, nCh };
  }

  // 棋盘 → 每个输入神经元的频率（Hz）
  function ratesFor(map, board, me, hz = 160) {
    const r = new Float32Array(map.inputs.length ? Math.max(...map.inputs) + 1 : 0);
    const opp = me === G.BLACK ? G.WHITE : G.BLACK;
    for (let i = 0; i < G.SIZE; i++) {
      const v = board[i];
      if (v === G.EMPTY) continue;
      const ch = v === me ? i * 2 : i * 2 + 1;
      for (const n of map.chan[ch]) r[n] = hz;
    }
    return r;
  }

  // 跑一局位置：复位 → 注入 → 跑 msRun 毫秒 → 返回每个神经元的脉冲计数
  // opt.seed：给定时先重播随机流——同一个棋盘永远给出同一份特征。
  // **这不是作弊**：水库计算要求水库是个确定性函数，否则读出层学到的只是噪声。
  // 不给 seed 就是原来的随机行为（游戏里就该是随机的）。
  function featuresOf(brain, map, board, me, opt = {}) {
    const ms = opt.ms ?? 100, hz = opt.hz ?? 160;
    if (opt.seed !== undefined && brain.reseed) brain.reseed(opt.seed);
    brain.reset();
    const r = ratesFor(map, board, me, hz);
    const idxs = [], vals = [];
    for (const n of map.inputs) { idxs.push(n); vals.push(r[n] || 0); }
    // 按频率分组调用（setOpto 一次只能给一个频率），只需两组：0 与 hz
    const on = idxs.filter((n, k) => vals[k] > 0);
    brain.setOpto(on, hz);
    const steps = Math.round(ms / brain.dt);
    const counts = new Float32Array(brain.n);
    brain.run(steps, i => { counts[i]++; });
    brain.setOpto([], 0);
    return counts;
  }

  const API = { inputGroupsOf, makeMap, makeTopoMap, ratesFor, featuresOf };
  if (typeof module !== "undefined" && module.exports) module.exports = API;
  else root.GomokuFeatures = API;
})(typeof window !== "undefined" ? window : globalThis);
