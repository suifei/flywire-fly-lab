/**
 * 连接组视觉前端：真实像素 → flyvis → LPLC2/LC4 频率。
 *
 * 这是游戏里**手写 dθ/dt 前端**的替代品。区别在于它不知道球在哪：
 *   手写版直接拿球的世界坐标算张角增长率；这一版只看复眼的 721 个 R1–6 读数。
 *
 * 链路：eyecam 的 r16（Rh1 = R1–R6，§28.16）→ flyvis（每只眼一套）
 *      → LPLC2 汇集（背离中心的 T4/T5，方向用 §28.17 实测值）→ 频率。
 *
 * 手写部分（都标出来）：
 *   · **自适应基线**：这些细胞静息活动很高（§28.17），用指数滑动平均当基线，
 *     信号 = max(0, 当前 − 基线)。相当于一个高通，和真实的运动适应同方向但不是它。
 *   · **增益**：从信号到 Hz 的换算。默认值由 dodge/front_end_calib.js 标定。
 *   · LC4 用非方向性的总运动能量（Ache et al. 2019 说 LC4 编码角速度）。
 *   · LC16 沿用 LC4 的编码乘一个系数，和手写版一致。
 */
(function (root, factory) {
  if (typeof module !== "undefined" && module.exports) module.exports = factory();
  else root.ConnectomeFrontEnd = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function create(FlyVis, LPLC2, netDoc, dirTable, opts) {
    opts = opts || {};
    const tauBase = opts.tauBase || 1.5;         // 基线时间常数（s）
    const gainLP = opts.gainLP == null ? 2600 : opts.gainLP;   // LPLC2 信号 → Hz
    const gainLC4 = opts.gainLC4 == null ? 5200 : opts.gainLC4;
    const lc16Scale = opts.lc16Scale == null ? 0.6 : opts.lc16Scale;
    const maxHz = opts.maxHz || 200;

    // 预热：flyvis 刚 reset 时活动是暂态的（实测 0.366，稳定后只有 0.13）。
    // 第一版直接用第一帧当基线，基线被瞬态毒化后要几秒才衰减下来，
    // 这期间 max(0, 当前 − 基线) 恒为 0 —— 前端整段"瞎着"。
    const warmup = opts.warmup == null ? 30 : opts.warmup;
    let warm = 0;
    const nets = [FlyVis.load(netDoc), FlyVis.load(netDoc)];     // 左眼、右眼各一套
    const pool = LPLC2.build(netDoc.lattice, dirTable, opts.pool || { stride: 8 });
    const base = [{ lp: null, e: null }, { lp: null, e: null }];
    const lat = netDoc.lattice;

    // 每根柱在点阵平面上的方位角（用于把 LPLC2 的扩张焦点转成方位）
    const colAz = lat.map(([u, v]) => Math.atan2(v * Math.sqrt(3) / 2, u + v / 2));

    return {
      types: pool.types, centers: pool.centers,
      reset() { nets.forEach(n => n.reset()); base.forEach(b => { b.lp = null; b.e = null; }); warm = 0; },
      get warmedUp() { return warm >= warmup; },
      /**
       * @param {Float64Array[]} r16 两只眼的 721 个 R1–6 读数
       * @param {number} dt 距上次调用的秒数
       * @returns {{lc4L,lc4R,lplc2L,lplc2R,lc16L,lc16R,threatCol,raw}}
       */
      step(r16, dt) {
        const o = { raw: [] };
        const k = 1 - Math.exp(-dt / tauBase);
        if (warm < warmup) warm++;                 // 预热期只推进网络，不建基线、不输出
        for (let e = 0; e < 2; e++) {
          nets[e].step(r16[e], dt);
          const r = pool.run(nets[e].act), en = pool.energy(nets[e].act);
          const b = base[e];
          if (warm < warmup) {                     // 预热：不采基线、输出 0
            o.raw.push({ lp: r.mean, base: null, energy: en, argmax: -1 });
            if (e === 0) { o.lplc2L = 0; o.lc4L = 0; o.lc16L = 0; }
            else { o.lplc2R = 0; o.lc4R = 0; o.lc16R = 0; }
            continue;
          }
          if (b.lp === null) { b.lp = r.mean; b.e = en; }
          const sLP = Math.max(0, r.mean - b.lp), sE = Math.max(0, en - b.e);
          b.lp += k * (r.mean - b.lp); b.e += k * (en - b.e);
          o.raw.push({ lp: r.mean, base: b.lp, energy: en, argmax: r.argmax });
          const hzLP = Math.min(maxHz, gainLP * sLP), hzE = Math.min(maxHz, gainLC4 * sE);
          if (e === 0) { o.lplc2L = hzLP; o.lc4L = hzE; o.lc16L = Math.min(maxHz, hzE * lc16Scale); }
          else { o.lplc2R = hzLP; o.lc4R = hzE; o.lc16R = Math.min(maxHz, hzE * lc16Scale); }
        }
        // 威胁方位：取两眼中 LPLC2 更强的那只，用它的扩张焦点所在柱的方位角
        o.warm = warm >= warmup;
        const stronger = o.lplc2L >= o.lplc2R ? 0 : 1;
        const col = o.raw[stronger].argmax;
        o.threatCol = col;
        o.threatOffset = col >= 0 ? colAz[col] : null;      // 相对该眼光轴的方位（弧度）
        o.eye = stronger;
        return o;
      },
    };
  }

  return { create };
});
