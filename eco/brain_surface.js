// 生态箱：大脑响应面（真脑 v5 的蒸馏，eco/fit_surface.py 拟合）。与 eco/brain_live.js 同一个接口：
//   brain.eval(x: Float32Array(27 路输入 Hz), out: Float32Array(12 个特征 Hz), rand?)
// 响应面给的是**平均**发放率；传 rand 就按 window 秒的泊松计数把单次试验的噪声加回去（真脑本来就有这份噪声）。
(function (root) {
  function create(SURF, opts) {
    const o = Object.assign({ window: 0.3 }, opts || {}), L = SURF.layers.map(l => ({ W: Float32Array.from(l.W.flat()), b: Float32Array.from(l.b), nin: l.W[0].length, nout: l.W.length }));
    const maxhz = Float32Array.from(SURF.maxhz), bufs = L.map(l => new Float32Array(l.nout)), xin = new Float32Array(L[0].nin), usable = SURF.features.map(f => SURF.heldout[f].usable ? 1 : 0);
    const poisson = (lam, rand) => { if (lam <= 0) return 0; if (lam > 30) { const u = Math.sqrt(-2 * Math.log(1 - rand())) * Math.cos(6.283185307 * rand()); return Math.max(0, Math.round(lam + Math.sqrt(lam) * u)); } let k = 0, p = Math.exp(-lam), s = p; const u = rand(); while (u > s && k < 200) { k++; p *= lam / k; s += p; } return k; };
    function evalInto(x, out, rand) {
      let quiet = true; for (let i = 0; i < xin.length; i++) { xin[i] = x[i] / maxhz[i]; if (x[i] > 0) quiet = false; }
      if (quiet) { out.fill(0); return out; }                                 // 没有输入 = 没有输出（真脑没有自发放电；audit.json 里安静时的读出全是 0）
      let a = xin; for (let k = 0; k < L.length; k++) { const l = L[k], b = bufs[k]; for (let j = 0; j < l.nout; j++) { let s = l.b[j]; const off = j * l.nin; for (let i = 0; i < l.nin; i++) s += l.W[off + i] * a[i]; b[j] = k < L.length - 1 ? s / (1 + Math.exp(-s)) : s; } a = b; }
      for (let j = 0; j < out.length; j++) { let hz = usable[j] && a[j] > 0 ? a[j] * a[j] : 0; if (hz < 0.3) hz = 0; if (rand && hz > 0) hz = poisson(hz * o.window, rand) / o.window; out[j] = hz; }
      return out;
    }
    return { eval: evalInto, features: SURF.features, inputs: SURF.inputs, kind: "surface" };
  }
  const API = { create }; if (typeof module !== "undefined" && module.exports) module.exports = API; else root.EcoBrainSurface = API;
})(typeof window !== "undefined" ? window : globalThis);
