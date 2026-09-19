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
      this._seed0 = seed >>> 0;
      this.silenced = new Set();
      this.reset();
    }

    // 把泊松输入的随机流重新播种：同一个输入在同一个种子下给出**逐位相同**的结果。
    // 五子棋那套"水库"用得到——否则同一个棋盘每次跑出来的特征都不一样，读出层只能去拟合噪声。
    reseed(seed) { this.random = rng32((seed >>> 0) || this._seed0); }

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

    // 直接驱动**任意**神经元（"光遗传手指"）。必须单独有个接口，是因为 _updateStim 只会把
    // **输入组**里的神经元放进 stimList —— 2026-09-19 实测：对中间神经元调 setRateNeurons
    // 只会写 stimProb，永远不会真的放电。传 hz = 0 关掉。
    // 与官方 poi() 一致：被驱动的神经元不应期置 0。
    setOpto(idx, hz) {
      this.optoIdx = Int32Array.from(idx || []);
      this.optoProb = (Math.max(0, hz) * this.dt) / 1000;
      for (const i of this.optoIdx) this.stimProb[i] = this.optoProb;
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
      if (this.optoIdx && this.optoProb > 0) {          // 光遗传驱动的神经元不一定在输入组里
        const seen = new Set(list);
        for (const i of this.optoIdx) {
          // 光遗传优先：游戏每一步都会用 setRate 重写输入组的 stimProb（没球时写 0），
          // 不在这里盖回去的话，点在 LC4/LPLC2 上的脉冲会被立刻抹掉。
          this.stimProb[i] = Math.max(this.stimProb[i], this.optoProb);
          this.rfc[i] = 0;
          if (!seen.has(i)) { seen.add(i); list.push(i); }
        }
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

    // ── 论文式扰动（对应 Shiu 2024 补充表 1D 与 11B–F）────────────────────
    // 11B/C  突触权重整体缩放       → setWeightScale
    // 11D/E  抑制强度缩放（只动负权）→ setInhibScale
    // 11F    谷氨酸改成兴奋性        → setGlutExcitatory（需要递质标签）
    // 1D     打乱接线                → setShuffle
    // 这些都在 rebuildWeights 里按固定顺序施加，顺序本身会影响结果，所以写死在这里。
    setWeightScale(s) { this.wScale = s; this.rebuildWeights(); }
    setInhibScale(s) { this.inhScale = s; this.rebuildWeights(); }
    setGlutExcitatory(on) { this.glutExc = !!on; this.rebuildWeights(); }
    /** 递质编码数组（与神经元同序）：0=ACh 1=Glut 2=GABA 3=DA 4=5HT 5=OA 6=未知 */
    setNT(nt) { this.nt = nt; }
    /**
     * 打乱接线：保持每个神经元的**出度**和它那串权重不变，只把突触后靶点随机重排。
     * **论文的打乱方式我们不知道**（补充表 1D 只给了结果，没给方法），所以这是我们
     * 自己定义的一种打乱，用来演示"真实接线是否重要"这个定性问题，不声称与论文同法。
     */
    setShuffle(on, seed = 12345) {
      if (!on) { this.postShuf = null; this.rebuildWeights(); return; }
      const rnd = rng32(seed >>> 0);
      const p = Int32Array.from(this.post);
      for (let i = p.length - 1; i > 0; i--) {          // Fisher–Yates
        const j = (rnd() * (i + 1)) | 0;
        const t = p[i]; p[i] = p[j]; p[j] = t;
      }
      this.postShuf = p;
      this.rebuildWeights();
    }
    /** 当前实际生效的突触后靶点数组 */
    get postArr() { return this.postShuf || this.post; }

    rebuildWeights() {
      this.w.set(this.w0);
      const ws = this.wScale, is = this.inhScale;
      if (this.glutExc && this.nt) {                     // 谷氨酸能神经元的传出突触改为兴奋性
        for (let i = 0; i < this.n; i++) {
          if (this.nt[i] !== 1) continue;
          for (let k = this.indptr[i]; k < this.indptr[i + 1]; k++) this.w[k] = Math.abs(this.w[k]);
        }
      }
      if (is != null && is !== 1) {                      // 只缩放抑制（负权）
        for (let k = 0; k < this.w.length; k++) if (this.w[k] < 0) this.w[k] *= is;
      }
      if (ws != null && ws !== 1) {                      // 整体缩放
        for (let k = 0; k < this.w.length; k++) this.w[k] *= ws;
      }
      for (const gname of this.silenced) {
        for (const i of this.groups[gname]) this.w.fill(0, this.indptr[i], this.indptr[i + 1]);
      }
      if (this.adhoc) for (const arr of this.adhoc.values()) {
        for (const i of arr) this.w.fill(0, this.indptr[i], this.indptr[i + 1]);
      }
    }

    // 推进 nSteps 步；onSpike(i, step) 可选，用于实时 raster
    run(nSteps, onSpike) {
      const { n, v, g, last, rfc, a, b, c, D, indptr, w, counts } = this;
      const post = this.postArr;   // 打乱接线时换成重排过的靶点数组
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
