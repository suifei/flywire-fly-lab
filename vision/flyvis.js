/**
 * 果蝇视觉系统前向计算（flyvis）—— 浏览器 / Node 通用。
 *
 * 为什么能在浏览器里跑整个视觉系统：flyvis 是**六边形卷积网络**。
 * 45,669 个节点 = 65 种细胞类型 × 每类若干柱，1,513,231 条边只有 604 种
 * (源类型→目标类型) 组合，每种共享一个卷积核（共 2,355 个抽头）。
 * 参数导出后约 80 KB（gzip ~25 KB），见 vision/export_flyvis_js.py。
 *
 * 动力学（flyvis PPNeuronIGRSynapses，欧拉积分）：
 *     v ← v + dt/max(τ,dt) · ( −v + bias + Σ w·ReLU(v_源) + x )
 *     w = sign × syn_count × syn_strength（导出时已算好）
 *
 * 两个必须照搬的约定（都是查出来的，不是猜的）：
 *   · du,dv = 目标 − 源  → 源柱 = (u_目标 − du, v_目标 − dv)，151 万条边全验证过
 *   · 输入：721 个小眼亮度**同时**送进 R1–R8 八种感受器，柱顺序按 (u,v) lexsort
 *
 * 用法：
 *   const net = await FlyVis.load(fetch/readFile 得到的 JSON);
 *   net.reset();                       // 初态 = bias（和 Python 的 write_initial_state 一致）
 *   net.step(brightness721, dt);       // 走一帧
 *   net.get("L1");                     // → Float64Array(721)，该类型每柱的活动
 */
const FlyVis = (() => {
  const key = (u, v) => ((u + 32) << 6) | (v + 32);   // u,v ∈ [-15,15]，塞进一个整数

  class Net {
    constructor(doc) {
      this.doc = doc;
      this.types = doc.types;
      this.bias = doc.bias;
      this.tau = doc.tau;

      // 每个类型的柱坐标：绝大多数共用主格子，只有少数例外
      this.cols = {};
      for (const t of this.types) this.cols[t] = doc.columns_exc[t] || doc.lattice;

      // (u,v) -> 该类型内的柱下标
      this.idx = {};
      for (const t of this.types) {
        const m = new Map();
        this.cols[t].forEach(([u, v], i) => m.set(key(u, v), i));
        this.idx[t] = m;
      }

      // 预解析卷积核：每个抽头预先算出"每个目标柱对应哪个源柱"，
      // 跑的时候就只剩乘加，不用再查表。
      this.kern = [];
      for (const [name, taps] of Object.entries(doc.kernels)) {
        const [s, t] = name.split(">");
        const nDst = this.cols[t].length;
        for (const [du, dv, w] of taps) {
          const map = new Int32Array(nDst);
          for (let j = 0; j < nDst; j++) {
            const [u, v] = this.cols[t][j];
            const i = this.idx[s].get(key(u - du, v - dv));
            map[j] = i === undefined ? -1 : i;      // 格子边缘：该边不存在
          }
          this.kern.push({ s, t, w, map });
        }
      }

      this.act = {};
      this.cur = {};
      for (const t of this.types) {
        this.act[t] = new Float64Array(this.cols[t].length);
        this.cur[t] = new Float64Array(this.cols[t].length);
      }
      this.inputTypes = doc.input_types;
      this.nTaps = this.kern.length;
    }

    /** 初态 = bias，和 flyvis 的 write_initial_state 一致 */
    reset() {
      for (const t of this.types) this.act[t].fill(this.bias[t]);
      return this;
    }

    /**
     * 走一帧。
     * @param {ArrayLike<number>} x 721 个小眼的亮度（顺序 = doc.lattice）
     * @param {number} dt 积分步长，秒
     */
    step(x, dt) {
      const { act, cur } = this;
      for (const t of this.types) cur[t].fill(0);

      // 突触电流：Σ w·ReLU(v_源)
      for (let k = 0; k < this.kern.length; k++) {
        const { s, t, w, map } = this.kern[k];
        const a = act[s], c = cur[t];
        for (let j = 0; j < map.length; j++) {
          const i = map[j];
          if (i < 0) continue;
          const v = a[i];
          if (v > 0) c[j] += w * v;              // ReLU 内联
        }
      }

      // 外部输入只进感受器
      const inp = new Set(this.inputTypes);

      for (const t of this.types) {
        const a = act[t], c = cur[t], b = this.bias[t];
        const r = dt / Math.max(this.tau[t], dt);
        const isIn = inp.has(t);
        for (let j = 0; j < a.length; j++) {
          a[j] += r * (-a[j] + b + c[j] + (isIn ? x[j] : 0));
        }
      }
      return this;
    }

    get(type) { return this.act[type]; }
    columns(type) { return this.cols[type]; }
  }

  return {
    Net,
    load(doc) { return new Net(typeof doc === "string" ? JSON.parse(doc) : doc); },
  };
})();

if (typeof module !== "undefined" && module.exports) module.exports = FlyVis;
