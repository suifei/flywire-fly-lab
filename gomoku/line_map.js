// 线型 → 果蝇脑 → 特征。页面与 node 共用，保证线上线下逐位一致。
(function (root) {
  const node = typeof module !== "undefined" && module.exports;
  const L = node ? require("./lines.js") : root.GomokuLines;
  const F = node ? require("./features.js") : root.GomokuFeatures;

  function rng32(seed) {
    let s = seed >>> 0;
    return () => { s = (s + 0x6d2b79f5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  }

  // 24 个通道 → 输入神经元。固定种子打乱后轮流发牌。
  function makeLineMap(SUB, seed = 20260920) {
    const inputs = [];
    for (const g of F.inputGroupsOf(SUB)) for (const i of (SUB.groups[g] || [])) inputs.push(i);
    const rand = rng32(seed), perm = inputs.slice();
    for (let i = perm.length - 1; i > 0; i--) { const j = (rand() * (i + 1)) | 0; [perm[i], perm[j]] = [perm[j], perm[i]]; }
    const chan = Array.from({ length: L.NCH }, () => []);
    perm.forEach((n, k) => chan[k % L.NCH].push(n));
    const n = SUB.meta.n, isIn = new Uint8Array(n); inputs.forEach(i => { isIn[i] = 1; });
    const downstream = []; for (let i = 0; i < n; i++) if (!isIn[i]) downstream.push(i);
    const colOf = new Int32Array(n).fill(-1); downstream.forEach((i, k) => { colOf[i] = k; });
    return { inputs, chan, downstream, colOf, perChannel: Math.floor(perm.length / L.NCH) };
  }

  // 跑一条线型：复位 → 点亮通道 → 跑 ms 毫秒 → 下游神经元 × 时间窗 的脉冲计数
  function lineFeatures(brain, map, code, opt = {}) {
    const ms = opt.ms ?? 60, hz = opt.hz ?? 160, bins = opt.bins ?? 2;
    if (opt.seed !== undefined) brain.reseed(opt.seed);
    brain.reset();
    const on = [];
    for (const ch of L.channelsOf(code)) for (const n of map.chan[ch]) on.push(n);
    brain.setOpto(on, hz);
    const nd = map.downstream.length, out = new Uint16Array(nd * bins);
    const steps = Math.round(ms / brain.dt), per = Math.ceil(steps / bins), cb = opt.onSpike;
    for (let b = 0; b < bins; b++) {
      const off = b * nd, n = Math.min(per, steps - b * per);
      brain.run(n, i => { const k = map.colOf[i]; if (k >= 0) out[off + k]++; if (cb) cb(i); });
    }
    brain.setOpto([], 0);
    return out;
  }

  // 视角 → 分配表的洗牌种子。视角 1 必须是 20260920（已发布的特征都是它）
  const viewSeed = v => 20260920 + (v - 1) * 7919;
  const API = { makeLineMap, lineFeatures, viewSeed };
  if (node) module.exports = API; else root.GomokuLineMap = API;
})(typeof window !== "undefined" ? window : globalThis);
