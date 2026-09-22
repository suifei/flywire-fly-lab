// 生态箱：大脑响应面（真脑 v5 的蒸馏，eco/fit_surface.py 拟合）。与 eco/brain_live.js 同一个接口：
//   brain.eval(x: Float32Array(27 路输入 Hz), out: Float32Array(12 个特征 Hz), rand?)
// 响应面给的是**平均**发放率；传 rand 就按 window 秒的泊松计数把单次试验的噪声加回去（真脑本来就有这份噪声）。
// **噪声的时间结构要和真脑的读出一样**（2026-09-22，l2_diagnosis.js）：真脑那边是 0.1 s 计数再按 τ = 0.3 s 平滑，相邻两步相关、逐步标准差小；
//   第一版这里每步独立抽一个 0.3 s 窗的泊松样本，方差对了但没有时间相关，逐步标准差是真脑的 2.5 倍，MN9 每 10 步就跌破一次 5 Hz 的进食门槛，果蝇在水洼上待不住——真脑闭环里喝水时间因此是响应面的 4 倍。
//   现在默认 window = 0.1 s、噪声按真脑量的等效单元数与 Fano 因子（brain_surface.json 的 noise，eco/measure_fano.js），平滑由调用方按个体做（eco/sim.js 里每只果蝇一份 EMA；smooth 选项给单个体用）。
(function (root) {
  function create(SURF, opts) {
    const o = Object.assign({ window: 0.1, smooth: 0 }, opts || {}), ema = new Float32Array(SURF.features.length), al = o.smooth > 0 ? Math.min(1, o.window / o.smooth) : 1, L = SURF.layers.map(l => ({ W: Float32Array.from(l.W.flat()), b: Float32Array.from(l.b), nin: l.W[0].length, nout: l.W.length }));
    const NZ = SURF.noise || null, nUnit = SURF.features.map(f => NZ ? (NZ.units[f] || 1) : 1), fano = SURF.features.map(f => NZ ? (NZ.fano[f] || 0.5) : 1), maxhz = Float32Array.from(SURF.maxhz), bufs = L.map(l => new Float32Array(l.nout)), xin = new Float32Array(L[0].nin), usable = SURF.features.map(f => SURF.heldout[f].usable ? 1 : 0);
    const poisson = (lam, rand) => { if (lam <= 0) return 0; if (lam > 30) { const u = Math.sqrt(-2 * Math.log(1 - rand())) * Math.cos(6.283185307 * rand()); return Math.max(0, Math.round(lam + Math.sqrt(lam) * u)); } let k = 0, p = Math.exp(-lam), s = p; const u = rand(); while (u > s && k < 200) { k++; p *= lam / k; s += p; } return k; };
    function evalInto(x, out, rand) {
      let quiet = true; for (let i = 0; i < xin.length; i++) { xin[i] = x[i] / maxhz[i]; if (x[i] > 0) quiet = false; }
      if (quiet) { if (o.smooth > 0) { for (let j = 0; j < out.length; j++) { ema[j] *= 1 - al; out[j] = ema[j] < 0.3 ? 0 : ema[j]; } } else out.fill(0); return out; }                                 // 没有输入 = 没有输出（真脑没有自发放电；audit.json 里安静时的读出全是 0）
      let a = xin; for (let k = 0; k < L.length; k++) { const l = L[k], b = bufs[k]; for (let j = 0; j < l.nout; j++) { let s = l.b[j]; const off = j * l.nin; for (let i = 0; i < l.nin; i++) s += l.W[off + i] * a[i]; b[j] = k < L.length - 1 ? s / (1 + Math.exp(-s)) : s; } a = b; }
      for (let j = 0; j < out.length; j++) { let hz = usable[j] && a[j] > 0 ? a[j] * a[j] : 0; if (hz < 0.3) hz = 0; if (rand && hz > 0) { const k = o.window * nUnit[j] / fano[j]; hz = poisson(hz * k, rand) / k; }   /* 噪声按真脑量的等效单元数与 Fano 因子：var = hz·fano/(window·n) */ if (o.smooth > 0) { ema[j] += al * (hz - ema[j]); hz = ema[j] < 0.3 ? 0 : ema[j]; } out[j] = hz; }
      return out;
    }
    return { eval: evalInto, features: SURF.features, inputs: SURF.inputs, kind: "surface", window: o.window, smoothed: o.smooth > 0 };
  }
  const API = { create }; if (typeof module !== "undefined" && module.exports) module.exports = API; else root.EcoBrainSurface = API;
})(typeof window !== "undefined" ? window : globalThis);
