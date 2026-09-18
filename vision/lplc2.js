/**
 * LPLC2 逼近检测：汇集**背离感受野中心**的 T4/T5 运动（Klapoetke et al. 2017 的模型形式）。
 *
 * 关键：各亚型的偏好方向用 **vision/t4t5_directions.js 实测出来的**，不是文献命名惯例 ——
 * 实测表明 flyvis 里 T4d 和 T5b 根本没有方向选择性，"a/b/c/d = 四个正交方向"不成立。
 *
 * 一个中心在 c 的 LPLC2：E(c) = Σ_j Σ_s a_s[j] · max(0, cos(θ_s − φ_{c→j}))
 *   j 跑遍 c 周围半径 R 内的柱，φ_{c→j} 是 c→j 的方向，θ_s 是亚型 s 的实测偏好方向。
 *   物体逼近时图像整体向外扩张，"背离中心"的运动处处为正，E(c) 在扩张焦点处最大；
 *   远离（收缩）时这些项全被 max(0,·) 切掉；平移时一半为正一半被切掉。
 *
 * 手选参数【推测】：感受野半径 R、中心取样步长、population 读数用 max 还是 mean。
 */
(function (root, factory) {
  if (typeof module !== "undefined" && module.exports) module.exports = factory();
  else root.LPLC2 = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /**
   * @param {Array} lattice 721 个柱的 (u,v)
   * @param {object} dirTable vision/t4t5_directions.json 的「定标」段
   * @param {object} opts { R=5, stride=2, minDSI=0.2, minPeak=0.05 }
   */
  function build(lattice, dirTable, opts) {
    opts = opts || {};
    // 默认值由**独立的诊断实验**定下（全场径向光栅，纯扩张 vs 纯收缩，见 report §28.18）：
    //   · 感受野越大越好：R=8/12/15/20 → 扩张:收缩 = 1.11/1.28/1.47/1.69（点阵半径本就是 15，
    //     R=20 相当于每个中心都看整只眼）
    //   · 六个亚型全用，好过只留方向选择性最强的三个（1.69 vs 1.63）——方向覆盖更全
    //   · **不要用 max 统计量**：R=5 时扩张:收缩 = 0.76，是反的。圆盘收缩时，位于对侧的
    //     中心会看到盘缘正在"远离自己"，被算成向外；取 max 专挑这种假阳性。用 mean。
    const R = opts.R || 20, stride = opts.stride || 3;
    const minDSI = opts.minDSI == null ? 0.2 : opts.minDSI;
    const minPeak = opts.minPeak == null ? 0.05 : opts.minPeak;
    const n = lattice.length;
    const pos = lattice.map(([u, v]) => [u + v / 2, v * Math.sqrt(3) / 2]);

    // 只留**实测确实有方向选择性**的亚型
    const use = [];
    for (const [ty, r] of Object.entries(dirTable)) {
      if (r.方向选择性 == null || r.方向选择性 < minDSI) continue;
      if (r.峰值增量 < minPeak) continue;
      use.push({ type: ty, th: r.偏好方向 * Math.PI / 180, dsi: r.方向选择性, base: r.静止 });
    }
    if (!use.length) throw new Error("方向表里没有一个亚型够格（DSI≥" + minDSI + " 且峰值≥" + minPeak + "）");

    // 预计算：每个中心 c 的 (邻居 j, 每个亚型的权重)
    const centers = [];
    for (let c = 0; c < n; c += stride) {
      const idx = [], w = [];
      for (let j = 0; j < n; j++) {
        if (j === c) continue;
        const dx = pos[j][0] - pos[c][0], dy = pos[j][1] - pos[c][1];
        const d = Math.hypot(dx, dy);
        if (d > R) continue;
        const phi = Math.atan2(dy, dx);
        const ws = new Float64Array(use.length);
        let any = false;
        for (let s = 0; s < use.length; s++) {
          const k = Math.cos(use[s].th - phi);
          if (k > 0) { ws[s] = k; any = true; }
        }
        if (any) { idx.push(j); w.push(ws); }
      }
      if (idx.length) centers.push({ c, idx: Int32Array.from(idx), w });
    }

    return {
      types: use.map(u => u.type), centers: centers.length, R, stride,
      /**
       * @param {object} act flyvis 的 act 字典
       * @returns {{max:number, mean:number, argmax:number}} 该眼的 LPLC2 population 读数
       */
      run(act) {
        let best = 0, bestC = -1, sum = 0;
        const A = use.map(u => act[u.type]), B = use.map(u => u.base);
        for (let k = 0; k < centers.length; k++) {
          const { c, idx, w } = centers[k];
          let e = 0;
          for (let m = 0; m < idx.length; m++) {
            const j = idx[m], ws = w[m];
            for (let s = 0; s < A.length; s++) {
              const a = A[s][j] - B[s];          // 减静息基线：这些细胞本底活动很高
              if (a > 0 && ws[s] > 0) e += a * ws[s];
            }
          }
          e /= idx.length;
          sum += e;
          if (e > best) { best = e; bestC = c; }
        }
        return { max: best, mean: sum / centers.length, argmax: bestC };
      },
      /** LC4：非方向性的总运动能量（Ache et al. 2019 说 LC4 编码角速度） */
      energy(act) {
        let s = 0, n2 = 0;
        for (let i = 0; i < use.length; i++) {
          const a = act[use[i].type], b = use[i].base;
          for (let j = 0; j < a.length; j++) { const v = a[j] - b; if (v > 0) s += v; n2++; }
        }
        return s / n2;
      },
    };
  }

  return { build };
});
