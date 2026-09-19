// 线型版果蝇棋手（v2）。页面与 node 共用。
//
// 它怎么选一步棋：
//   每个合法候选点 → 4 个方向各取一条线（两侧各 4 格）→ 查**线型价值表** → 8 个值相加（4 进攻 + 4 防守）→ 取最大。
//   线型价值表 = 这颗果蝇脑对 14,641 种线型逐一跑出来的放电 × 训练出的线性读出。脑子里一个突触都没训练。
//   depth > 1 时把同一张表塞进 alpha-beta：搜索知道规则（成五 = 赢、必须挡五），不知道棋形。
//
// **表是预先跑好的，所以每走一步都现场核对**：被选中那一步的 8 条线当场在真实的果蝇脑里重跑，
//   用读出权重现算价值，和表里的数逐个比对，偏差写进 lastStats.liveCheck。
//   这也是页面上 spike 图、下行神经元、感觉输入三块面板在下棋时的数据来源。
//
// 禁手与合法性仍由规则引擎判，不是果蝇。
(function (root) {
  const node = typeof module !== "undefined" && module.exports;
  const G = node ? require("./rules.js") : root.Gomoku;
  const L = node ? require("./lines.js") : root.GomokuLines;
  const LM = node ? require("./line_map.js") : root.GomokuLineMap;
  const T2 = node ? require("./teacher2.js") : root.GomokuTeacher2;
  const EN = node ? require("./engine.js") : root.GomokuEngine;

  const f32 = s => {
    const bin = typeof Buffer !== "undefined" ? Uint8Array.from(Buffer.from(s, "base64")) : Uint8Array.from(atob(s), c => c.charCodeAt(0));
    return new Float32Array(bin.buffer, bin.byteOffset, bin.byteLength >> 2);
  };
  // 表 JSON → 按线型编码索引的两张 Float32Array。codes 省略时用 allCodes() 的顺序（导出时就是这个顺序）
  function loadTable(j) {
    const codes = j.codes || Array.from(L.allCodes()), a = f32(j.att), d = f32(j.deff);
    const att = new Float32Array(L.NCODE), def = new Float32Array(L.NCODE);
    for (let k = 0; k < codes.length; k++) { att[codes[k]] = a[k]; def[codes[k]] = d[k]; }
    const t = { att, def, combo: false, linear: j.form === "lse" };
    if (j.value) { const v = f32(j.value), g = new Float32Array(L.NCODE); for (let k = 0; k < codes.length; k++) g[codes[k]] = v[k]; t.valueTable = g; t.valueBias = j.value_bias || 0; }
    return t;
  }

  function scoreCells(tab, board, me) {
    const out = [];
    for (const i of G.candidates(board, 2)) {
      if (me === G.BLACK && G.forbidden(board, i % G.N, (i / G.N) | 0)) continue;
      const x = i % G.N, y = (i / G.N) | 0; let s = 0;
      for (let d = 0; d < 4; d++) { const code = L.codeAt(board, x, y, d, me); s += tab.att[code] + tab.def[T2.SWAP[code]]; }
      out.push([i, s]);
    }
    return out;
  }

  function makeLinePlayer(SUB, BrainClass, tableJson, opt = {}) {
    const tab = loadTable(tableJson);
    const live = !!(tableJson.w_a && BrainClass && SUB);
    let brain = null, map = null, views = null, wa, wd, mu, sd, keep;
    if (live) {
      brain = new BrainClass(SUB, opt.seed ?? 11);
      if (opt.shuffle) brain.setShuffle(true, 20260919);
      // 特征可以由几个「视角」拼成：每个视角 = 一张通道→神经元分配表 + 时间分段数（训练脚本写在 tableJson.views 里）
      views = (tableJson.views && tableJson.views.length ? tableJson.views : [{ view: 1, bins: tableJson.bins || 1 }])
        .map(v => ({ bins: v.bins, map: LM.makeLineMap(SUB, LM.viewSeed(v.view)) }));
      map = views[0].map;
      wa = f32(tableJson.w_a); mu = f32(tableJson.mu); sd = f32(tableJson.sd); keep = tableJson.keep;
    }
    const READ = ["DNa01_left", "DNa01_right", "DNa02_left", "DNa02_right", "DNp01_left", "DNp01_right",
                  "MN9_left", "MN9_right", "aDN1_left", "aDN1_right", "MDN_left", "MDN_right"];
    const ING = SUB ? Object.keys((SUB.meta && SUB.meta.inputs) || {}) : [];
    const colOfGroup = {}, liveCache = new Map();
    // 表是 K 个泊松种子的**试次平均**（√计数的平均），现场核对就照样跑 K 遍再平均——否则对不上
    const SEEDS = tableJson.seeds || [tableJson.seed ?? 777];
    let engine = null;
    if (live) for (const g of READ) colOfGroup[g] = (SUB.groups[g] || []).map(i => map.colOf[i]).filter(k => k >= 0);

    // 在真实的脑子里跑一条线型，用读出权重现算它的价值（kind: "att" | "def"）
    // 表是 K 个泊松种子的**试次平均**（√计数的平均），现场核对就照样跑 K 遍再平均——否则对不上
    // 在真实的脑子里跑一条线型，返回读出层给的**对数价值** v（进攻价值 = exp(v)，防守价值 = λ·exp(v)）。
    function liveRaw(code, acc) {
      const nd = map ? map.downstream.length : 0;
      const f = new Float64Array(keep.length);
      let width = 0; for (const vw of views) width += nd * vw.bins;
      const cat = new Float64Array(width);
      for (const seed of SEEDS) {
        let off = 0;
        for (const vw of views) {
          const cnt = LM.lineFeatures(brain, vw.map, code, { hz: tableJson.hz, ms: tableJson.ms, bins: vw.bins, seed, onSpike: opt.onSpike });
          for (let k = 0; k < cnt.length; k++) cat[off + k] = cnt[k];
          off += cnt.length;
          if (acc) { acc.runs++;
            for (const g of READ) for (const c of colOfGroup[g]) { let s2 = 0; for (let b = 0; b < vw.bins; b++) s2 += cnt[b * nd + c]; acc.spk[g] = (acc.spk[g] || 0) + s2; }
            for (const ch of L.channelsOf(code)) for (const nIdx of vw.map.chan[ch]) acc.driven.add(nIdx); }
        }
        for (let k = 0; k < keep.length; k++) f[k] += Math.sqrt(cat[keep[k]]);
      }
      let v = tableJson.bias || 0;
      for (let k = 0; k < keep.length; k++) v += ((f[k] / SEEDS.length - mu[k]) / sd[k]) * wa[k];
      return v;
    }
    const toValue = (v, kind) => (tableJson.form === "lse" ? Math.exp(Math.min(v, 30)) * (kind === "att" ? 1 : tableJson.lam) : (kind === "att" ? v : v * tableJson.lam));

    return {
      tab, live, brain, shuffled: !!opt.shuffle, lastStats: null,
      // 选点：depth ≤ 1 = 直觉（落子分最大）；否则把同一张表交给增量搜索引擎（engine.js）。
      // o.budgetMs 给了就做限时迭代加深；o.vcf 先试连续冲四杀棋（纯规则）。返回 {move, scores, depth, how, nodes, ms}
      choose(board, me, o = {}) {
        const depth = o.depth ?? opt.depth ?? 1, t0 = Date.now();
        const cells = scoreCells(tab, board, me);
        const scores = new Float64Array(G.SIZE).fill(-Infinity);
        for (const [i, s] of cells) scores[i] = s;
        if (!engine) engine = EN.makeEngine(tab.att, tableJson.lam ?? 1);
        if (depth <= 1 && !o.budgetMs) return { move: engine.greedy(board, me), scores, depth: 1, how: "greedy", nodes: 0, ms: Date.now() - t0 };
        if (o.vcf) { const k = T2.vcf(board.slice(), me, o.vcfDepth ?? 12); if (k >= 0) return { move: k, scores, depth: 0, how: "vcf", nodes: 0, ms: Date.now() - t0 }; }
        const r = engine.think(board, me, { depth: o.budgetMs ? undefined : depth, budgetMs: o.budgetMs, K: o.K, K0: o.K0 });
        let move = r.move, avoided = 0;
        if (o.vcf && r.ranked && r.ranked.length > 1 && Math.abs(r.score) < EN.WIN / 2) { const a = T2.avoidVcf(board.slice(), me, r.ranked, o.vcfDepth ?? 12); move = a.move; avoided = a.skipped; }
        return { move, scores, depth: r.depth, how: r.how, nodes: r.nodes, ms: Date.now() - t0, score: r.score, avoided };
      },
      // 现场核对（分步）：把这一步的 8 条线放进真实的果蝇脑里重跑，与表逐个比对。
      // 生成器每跑完一条线型就 yield 一次，页面可以一帧跑一条，不卡界面。同一种线型本局已核对过就直接用缓存。
      *inspectGen(board, me, move) {
        const rates = {}, drive = {}, lines = [];
        const acc = { runs: 0, cached: 0, spk: {}, driven: new Set() };
        let maxDiff = 0;
        if (move >= 0) {
          const x = move % G.N, y = (move / G.N) | 0;
          for (let d = 0; d < 4; d++) {
            const code = L.codeAt(board, x, y, d, me), sw = T2.SWAP[code];
            const row = { dir: d, att_code: code, def_code: sw, att: tab.att[code], def: tab.def[sw], att_show: L.show(code), def_show: L.show(sw) };
            if (live) for (const [kind, c, key] of [["att", code, "att_live"], ["def", sw, "def_live"]]) {
              if (liveCache.has(c)) { row[key] = toValue(liveCache.get(c), kind); acc.cached++; }
              else { const v = liveRaw(c, acc); liveCache.set(c, v); row[key] = toValue(v, kind); yield { done: false, runs: acc.runs, line: row, kind }; }
              const ref = kind === "att" ? row.att : row.def;
              maxDiff = Math.max(maxDiff, Math.abs(row[key] - ref) / Math.max(1e-9, Math.abs(ref)));
            }
            lines.push(row);
          }
        }
        let liveCheck = null;
        if (live && move >= 0) {
          liveCheck = { runs: acc.runs, cached: acc.cached, max_rel_diff: maxDiff };
          const secs = Math.max(acc.runs, 1) * tableJson.ms / 1000;
          for (const g of READ) { const nG = (SUB.groups[g] || []).length; rates[g] = nG && acc.runs ? (acc.spk[g] || 0) / nG / secs : 0; }
          for (const g of ING) for (const side of ["left", "right"]) { const key = g + "_" + side, idx = SUB.groups[key] || [];
            drive[key] = idx.length ? idx.filter(nI => acc.driven.has(nI)).length / idx.length * tableJson.hz : 0; }
        }
        this.lastStats = { rates, drive, ms: tableJson.ms, hz: tableJson.hz, liveCheck, lines };
        return this.lastStats;
      },
      inspect(board, me, move) { const g = this.inspectGen(board, me, move); let r = g.next(); while (!r.done) r = g.next(); return r.value; },
      think(board, me, o = {}) {
        const c = this.choose(board, me, o);
        const st = o.live === false ? { lines: [], liveCheck: null } : this.inspect(board, me, c.move);
        if (this.lastStats) this.lastStats.depth = c.depth;
        return { ...c, lines: st.lines, liveCheck: st.liveCheck };
      },
    };
  }

  const API = { loadTable, scoreCells, makeLinePlayer };
  if (node) module.exports = API; else root.GomokuFly2 = API;
})(typeof window !== "undefined" ? window : globalThis);
