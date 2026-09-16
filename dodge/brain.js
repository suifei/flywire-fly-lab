// 连接组子回路 LIF 引擎（浏览器 / node 通用）
// 数值方案与 dodge/subcircuit.py 的参考实现、以及 Shiu et al. 的 Brian2 模型逐项对齐：
//   不应期外：v ← v0 + (v − v0)·a + g·c，g ← g·b（线性 ODE 精确解，dt = 0.1 ms）
//   阈值 v > −45 mV → 放电；本步到达的延迟突触输入 g += w；Poisson 事件 v += 68.75 mV；
//   放电神经元重置 v = −52 mV、g = 0，不应期 2.2 ms（被刺激神经元为 0）
(function (root) {
  function decodeB64(b64, Ctor) {
    const bin = typeof atob === "function" ? atob(b64) : Buffer.from(b64, "base64").toString("binary");
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new Ctor(bytes.buffer);
  }

  // 可复现的快速随机数（mulberry32）
  function rng32(seed) {
    let s = seed >>> 0;
    return () => {
      s = (s + 0x6d2b79f5) >>> 0;
      let t = s;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  class ConnectomeBrain {
    constructor(data, seed = 1) {
      const P = data.meta.params;
      this.P = P;
      this._meta = data.meta;
      this.n = data.meta.n;
      this.groups = data.groups;
      this.indptr = decodeB64(data.indptr, Int32Array);
      this.post = decodeB64(data.post, Int32Array);
      this.w0 = decodeB64(data.w, Float32Array);
      this.w = new Float32Array(this.w0);
      this.dt = P.dt;
      this.D = Math.round(P.t_dly / P.dt);
      this.a = Math.exp(-P.dt / P.t_mbr);
      this.b = Math.exp(-P.dt / P.tau);
      this.c = (P.tau / (P.tau - P.t_mbr)) * (this.b - this.a);
      this.kick = P.w_syn * P.f_poi;
      this.rfcSteps = Math.round(P.t_rfc / P.dt);
      this.v = new Float32Array(this.n);
      this.g = new Float32Array(this.n);
      this.last = new Int32Array(this.n);
      this.rfc = new Int32Array(this.n);
      this.ring = Array.from({ length: this.D }, () => new Float32Array(this.n));
      this.stimProb = new Float32Array(this.n); // 每步 Poisson 事件概率
      this.stimList = new Int32Array(0);
      this.fired = new Int32Array(this.n);
      this.nFired = 0;
      this.random = rng32(seed);
      this.silenced = new Set();
      this.reset();
    }

    reset() {
      this.v.fill(this.P.v0); this.g.fill(0); this.last.fill(-1e9); this.step = 0;
      for (const r of this.ring) r.fill(0);
      this.counts = new Float32Array(this.n);
      this._updateStim();
    }

    // 设置某组输入神经元的 Poisson 频率（Hz）
    setRate(group, hz) {
      const p = (Math.max(0, hz) * this.dt) / 1000;
      for (const i of this.groups[group]) this.stimProb[i] = p;
      this._updateStim();
    }

    // 按神经元下标设定输入频率（水味觉受体是糖味觉组 LB3 里的一个子集，没有单独的组名）
    setRateNeurons(idx, hz) {
      const p = (Math.max(0, hz) * this.dt) / 1000;
      for (const i of idx) this.stimProb[i] = p;
      this._updateStim();
    }

    _updateStim() {
      const list = [];
      for (let i = 0; i < this.n; i++) {
        this.rfc[i] = this.rfcSteps;
      }
      // 输入组：v2 子回路在 meta.inputs 里列出；v1 只有 LC4/LPLC2
      const inputPrefixes = this.inputPrefixes || (this.inputPrefixes = Object.keys((this.P && this._meta && this._meta.inputs) || {}).length
        ? Object.keys(this._meta.inputs) : ["LC4", "LPLC2"]);
      for (const g of Object.keys(this.groups)) {
        if (!inputPrefixes.some(p => g.startsWith(p + "_"))) continue;
        for (const i of this.groups[g]) { this.rfc[i] = 0; if (this.stimProb[i] > 0) list.push(i); }
      }
      this.stimList = Int32Array.from(list);
    }

    // 沉默 = 该组神经元的传出突触权重置 0（与官方 silence() 一致）
    setSilenced(group, on) {
      if (on) this.silenced.add(group); else this.silenced.delete(group);
      this.rebuildWeights();
    }

    // 按单个神经元沉默（游戏里的“真实神经元损毁”：用虚拟敲除筛选选出来的那些）
    setSilencedNeurons(name, idx, on) {
      this.adhoc = this.adhoc || new Map();
      if (on) this.adhoc.set(name, Int32Array.from(idx)); else this.adhoc.delete(name);
      this.rebuildWeights();
    }

    rebuildWeights() {
      this.w.set(this.w0);
      for (const gname of this.silenced) {
        for (const i of this.groups[gname]) this.w.fill(0, this.indptr[i], this.indptr[i + 1]);
      }
      if (this.adhoc) for (const arr of this.adhoc.values()) {
        for (const i of arr) this.w.fill(0, this.indptr[i], this.indptr[i + 1]);
      }
    }

    // 推进 nSteps 步；onSpike(i, step) 可选，用于实时 raster
    run(nSteps, onSpike) {
      const { n, v, g, last, rfc, a, b, c, D, indptr, post, w, counts } = this;
      const v0 = this.P.v0, vth = this.P.vth, vrst = this.P.vrst, kick = this.kick;
      const fired = this.fired;
      for (let k = 0; k < nSteps; k++) {
        const s = this.step;
        let nf = 0;
        for (let i = 0; i < n; i++) {
          if (s - last[i] >= rfc[i]) {
            const gi = g[i];
            v[i] = v0 + (v[i] - v0) * a + gi * c;
            g[i] = gi * b;
            if (v[i] > vth) fired[nf++] = i;
          }
        }
        const slot = this.ring[s % D];
        for (let i = 0; i < n; i++) { if (slot[i] !== 0) { g[i] += slot[i]; slot[i] = 0; } }
        const sl = this.stimList, sp = this.stimProb;
        for (let j = 0; j < sl.length; j++) { const i = sl[j]; if (this.random() < sp[i]) v[i] += kick; }
        for (let f = 0; f < nf; f++) {
          const i = fired[f];
          for (let e = indptr[i]; e < indptr[i + 1]; e++) slot[post[e]] += w[e];
          v[i] = vrst; g[i] = 0; last[i] = s; counts[i]++;
          if (onSpike) onSpike(i, s);
        }
        this.nFired = nf;
        this.step++;
      }
    }

    // 读出并清零计数：返回各组平均发放率（Hz）
    readRates(groupNames, windowSteps) {
      const out = {}, sec = (windowSteps * this.dt) / 1000;
      for (const gname of groupNames) {
        const idx = this.groups[gname]; let s = 0;
        for (const i of idx) s += this.counts[i];
        out[gname] = idx.length ? s / idx.length / sec : 0;
      }
      this.counts.fill(0);
      return out;
    }
  }

  const api = { ConnectomeBrain, decodeB64 };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.FlyDodgeBrain = api;
})(typeof self !== "undefined" ? self : this);
