/**
 * 果蝇视蛋白光谱 → 渲染通道权重。
 *
 * 为什么需要它：flyvis 的输入是 R1–R8，其中 **R1–R6 用 Rh1（宽带）**，是运动/亮度主通道。
 * 而 eyecam 至今只产出 R8 那一路（pale 取蓝、yellow 取绿）和 R7 紫外，**Rh1 完全没建模**。
 * 八个感光细胞里的六个缺席，下一步要把像素接进 flyvis 就没有正确的输入。
 *
 * 做法（每一步都写明是数据还是假设）：
 *   · 视蛋白敏感度曲线用 **Govardovskii et al. 2000 的 A1 视色素模板**（已发表解析式，
 *     α 带 + β 带），只需要各自的 λmax。【官方】
 *   · λmax 用果蝇已发表值：Rh1 478（R1–6）、Rh3 345（R7p）、Rh4 375（R7y）、
 *     Rh5 437（R8p）、Rh6 508（R8y）。【官方】
 *   · 场景是 sRGB 著作的，没有真实光谱。把渲染出的三个通道当成三个代表波长处的
 *     反射率采样（紫外 365、蓝 465、绿 550），用分段线性（帽函数）插出反射谱。【推测】
 *   · 光源当作等能白（平谱）。【推测】
 *   · 权重 = ∫ S(λ)·帽函数(λ) dλ ÷ ∫ S(λ) dλ，所以**理想白面（三通道都是 1）响应为 1**。
 *
 * 已知缺口：果蝇 R1–6 还带一个 3-羟基视黄醇「增感色素」，在 ~350 nm 给出第二个大峰，
 * 这个**不在** Govardovskii 模板里。这里把它做成显式可开关的附加项 `sensitizer`，
 * 幅度是手选的【推测】；关掉时 Rh1 的紫外敏感度会被**低估**，两套权重都写进了
 * results/vision/opsin_weights.json，可以直接看差别。
 */
(function (root, factory) {
  if (typeof module !== "undefined" && module.exports) module.exports = factory();
  else root.Opsins = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // Govardovskii et al. 2000, A1 模板
  function templateA1(lam, lmax) {
    const x = lmax / lam;
    const A = 69.7, a = 0.8795 + 0.0459 * Math.exp(-((lmax - 300) * (lmax - 300)) / 11940);
    const B = 28, b = 0.922, C = -14.9, c = 1.104, D = 0.674;
    const alpha = 1 / (Math.exp(A * (a - x)) + Math.exp(B * (b - x)) + Math.exp(C * (c - x)) + D);
    const lmb = 189 + 0.315 * lmax;            // β 带中心
    const bb = -40.5 + 0.195 * lmax;           // β 带宽度
    const beta = 0.26 * Math.exp(-Math.pow((lam - lmb) / bb, 2));
    return alpha + beta;
  }

  // 渲染通道 → 波段。**箱型**，不是帽函数：每个通道的语义就是"这一段里的平均反射率"。
  // 第一版用帽函数（峰值 365/465/550 线性过渡），结果 Rh5（λmax 437，蓝）拿到 46% 的
  // 紫外权重 —— 因为紫外帽一路延伸到 465，把 400–465 的紫蓝光算成了紫外。那是基函数的错，
  // 不是光谱的事实。红端没有第四个通道（果蝇也没有红受体），600–700 并入绿带。
  const BANDS = [{ key: "U", lo: 300, hi: 400 },
                 { key: "B", lo: 400, hi: 500 },
                 { key: "G", lo: 500, hi: 700 }];
  function box(i, lam) { const b = BANDS[i]; return lam >= b.lo && lam < b.hi ? 1 : 0; }

  const OPSINS = {
    Rh1: { lmax: 478, cells: "R1–R6", note: "宽带，运动/亮度主通道" },
    Rh3: { lmax: 345, cells: "R7p", note: "紫外" },
    Rh4: { lmax: 375, cells: "R7y", note: "紫外" },
    Rh5: { lmax: 437, cells: "R8p", note: "蓝" },
    Rh6: { lmax: 508, cells: "R8y", note: "绿" },
  };

  /** 手选的增感色素项【推测】：~350 nm 的第二个峰，仅 Rh1（R1–6）有 */
  const SENS = { lam: 350, width: 45, amp: 0.55 };

  /**
   * 算出每个视蛋白对三个渲染通道的权重。
   * @param {boolean} sensitizer Rh1 是否带增感色素附加峰
   * @returns {{[opsin:string]: {U:number,B:number,G:number}}}
   */
  function weights(sensitizer) {
    const LO = 300, HI = 700, STEP = 1;
    const out = {};
    for (const [name, o] of Object.entries(OPSINS)) {
      const w = [0, 0, 0]; let tot = 0;
      // 注意 lam < HI 不是 <=：波段是左闭右开 [500,700)，写成 <= 的话 700 nm 这一个
      // 采样点会进总量却不进任何波段，归一化差 1.5e-7（审计的 1e-9 容差抓到过）。
      for (let lam = LO; lam < HI; lam += STEP) {
        let S = templateA1(lam, o.lmax);
        if (sensitizer && name === "Rh1")
          S += SENS.amp * Math.exp(-Math.pow((lam - SENS.lam) / SENS.width, 2));
        tot += S * STEP;
        for (let i = 0; i < 3; i++) w[i] += S * box(i, lam) * STEP;
      }
      out[name] = { U: w[0] / tot, B: w[1] / tot, G: w[2] / tot };
    }
    return out;
  }

  return { templateA1, weights, OPSINS, BANDS, SENS };
});
