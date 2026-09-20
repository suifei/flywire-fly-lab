// 生态箱：真脑（v5，15,055 个脉冲神经元，dodge/brain.js）。接口与 eco/brain_surface.js 相同；一只果蝇约 1.2 倍实时，只给「被盯着看的那一只」和复核实验用。
(function (root) {
  function create(SUB, ConnectomeBrain, CH, seed, opts) {
    const o = Object.assign({ window: 0.1, smooth: 0.3 }, opts || {}), ema = new Float32Array(CH.FEATURES.length), al = Math.min(1, 0.1 / ((opts && opts.smooth) || 0.3)), brain = new ConnectomeBrain(SUB, seed || 1), B = CH.bind(SUB), cnt = new Float32Array(SUB.meta.n), steps = Math.round(o.window * 10000), onSpike = j => { cnt[j]++; };
    function evalInto(x, out) { CH.INPUTS.forEach((c, i) => brain.setDrive(c, B.idx[c], x[i])); cnt.fill(0); brain.run(steps, onSpike); const y = B.read(cnt, o.window); CH.FEATURES.forEach((f, j) => { ema[j] += al * (y[f] - ema[j]); out[j] = ema[j] < 0.3 ? 0 : ema[j]; }); return out; }   /* 读出按 ~300 ms 平滑，与响应面的噪声窗口一致 */
    return { eval: evalInto, features: CH.FEATURES, inputs: CH.INPUTS, kind: "live", brain, counts: cnt };
  }
  const API = { create }; if (typeof module !== "undefined" && module.exports) module.exports = API; else root.EcoBrainLive = API;
})(typeof window !== "undefined" ? window : globalThis);
