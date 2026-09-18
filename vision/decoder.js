/**
 * 从神经活动重建视网膜图像 —— 六边形卷积解码器。
 *
 *     R̂(u,v) = b + Σ_类型 Σ_偏移 w[类型,du,dv] · act_类型(u+du, v+dv)
 *
 * 为什么是卷积不是全连接：前向本身就是卷积（604 个核），逆向也该平移不变；
 * 而且全连接要 721×721×层数 个参数（每层 2 MB），卷积只要几百个。
 *
 * **诚实性警告**：解码器会"补"出活动里其实没有的细节 —— 它学的是训练图像的
 * 统计规律。所以界面上必须同时显示未解码的神经活动，让人看到差距。
 * （这正是 docs/log/report.md §15 解码器压力测试在警告的事。）
 */
const HexDecoder = (() => {
  const key = (u, v) => ((u + 32) << 6) | (v + 32);

  class Dec {
    /**
     * @param {object} spec decoders.json 里某一层的对象
     * @param {Array<[number,number]>} lattice 721 个柱的 (u,v)，顺序同 flyvis
     */
    constructor(spec, lattice) {
      this.label = spec.label;
      this.types = spec.types;
      this.taps = spec.taps;
      this.w = Float64Array.from(spec.w);
      this.mu = Float64Array.from(spec.mu);
      this.sd = Float64Array.from(spec.sd);
      this.b = spec.b;
      this.testR = spec.test_r;
      this.n = lattice.length;

      const pos = new Map();
      lattice.forEach(([u, v], i) => pos.set(key(u, v), i));
      // 预先算好每个抽头的"源柱"索引，跑的时候只剩乘加
      this.src = this.taps.map(([du, dv]) => {
        const m = new Int32Array(this.n);
        for (let j = 0; j < this.n; j++) {
          const [u, v] = lattice[j];
          const i = pos.get(key(u + du, v + dv));
          m[j] = i === undefined ? -1 : i;
        }
        return m;
      });
      this.out = new Float64Array(this.n);
    }

    /**
     * @param {(t:string)=>ArrayLike<number>} getAct 取某类型当前活动
     * @returns {Float64Array} 长度 721 的重建亮度
     */
    decode(getAct) {
      const { out, n, taps, src, w, mu, sd, b } = this;
      out.fill(b);
      const nT = taps.length;
      for (let a = 0; a < this.types.length; a++) {
        const act = getAct(this.types[a]);
        if (!act) continue;
        for (let t = 0; t < nT; t++) {
          const f = a * nT + t;
          const wf = w[f] / sd[f], off = -mu[f] * w[f] / sd[f];
          const m = src[t];
          for (let j = 0; j < n; j++) {
            const i = m[j];
            out[j] += i < 0 ? off : wf * act[i] + off;
          }
        }
      }
      return out;
    }
  }

  return {
    load(doc, lattice) {
      doc = typeof doc === "string" ? JSON.parse(doc) : doc;
      const out = {};
      for (const [k, spec] of Object.entries(doc.layers)) out[k] = new Dec(spec, lattice);
      out._meta = { radius: doc.radius, n_images: doc.n_images, note: doc.note };
      return out;
    },
  };
})();

if (typeof module !== "undefined" && module.exports) module.exports = HexDecoder;
