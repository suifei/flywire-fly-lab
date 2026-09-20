// 多巴胺门控的突触可塑性（浏览器 / node 版）。规则与 learn/plasticity.py 逐条相同，两边的一致性由 learn/parity_js.js 验。
//
//   只作用在 KC → MBON 突触上（文献里果蝇嗅觉记忆的位置：Hige 2015 Neuron；Cohn 2015 Cell；Handler 2019 Cell）。
//   KC 最近放过电（资格迹 e，时间常数 tauE）＋ 同一隔室里有多巴胺 D → 这条突触被压低：ratio *= exp(−eta · e · D)
//   D_j = 接到 MBON j 上的那些多巴胺神经元的脉冲数，按连接组里 DAN→MBON 的突触数加权平均（只算 ≥3 个突触的边）。
//   「哪个多巴胺神经元管哪个隔室」完全由连接组决定；规则对 PAM / PPL1 一视同仁。
//   遗忘：ratio 以时间常数 tauForget 回到 1（0 = 不遗忘）。
// eta / tauE / tauForget 是手选参数（台账 PARAMETERS）。
(function (root) {
  function create(SUB, brain, opts) {
    const o = Object.assign({ eta: 0.003, tauE: 200, tauForget: 0, wSyn: 0.275 }, opts || {}), n = SUB.meta.n, tag = SUB.mb_tag;
    if (!tag) throw new Error("这个子回路没有蘑菇体（需要 v5）");
    const indptr = brain.indptr, post = brain.post, w0 = brain.w0;
    const kcIdx = [], mbonIdx = [], danIdx = [], local = new Int32Array(n).fill(-1);
    for (let i = 0; i < n; i++) { if (tag[i] === "KC") { local[i] = kcIdx.length; kcIdx.push(i); } else if (tag[i] === "MBON") { local[i] = mbonIdx.length; mbonIdx.push(i); } else if (tag[i] === "DAN") { local[i] = danIdx.length; danIdx.push(i); } }
    // 可塑的边，按 KC 分组（CSR）
    const ePtr = new Int32Array(kcIdx.length + 1), eList = [], eMbon = [];
    kcIdx.forEach((i, k) => { for (let e = indptr[i]; e < indptr[i + 1]; e++) if (tag[post[e]] === "MBON") { eList.push(e); eMbon.push(local[post[e]]); } ePtr[k + 1] = eList.length; });
    const eIdx = Int32Array.from(eList), eM = Int32Array.from(eMbon), ratio = new Float32Array(eIdx.length).fill(1);
    // DAN → MBON 的突触数
    const dPre = [], dPost = [], dN = [], tot = new Float64Array(mbonIdx.length);
    danIdx.forEach((i, d) => { for (let e = indptr[i]; e < indptr[i + 1]; e++) if (tag[post[e]] === "MBON") { const c = Math.round(Math.abs(w0[e]) / o.wSyn); if (c >= 3) { dPre.push(d); dPost.push(local[post[e]]); dN.push(c); tot[local[post[e]]] += c; } } });
    const kcCount = new Float32Array(kcIdx.length), danCount = new Float32Array(danIdx.length), trace = new Float32Array(kcIdx.length), D = new Float32Array(mbonIdx.length);
    const P = { o, kcIdx, mbonIdx, danIdx, ratio, D, trace, enabled: true, nPlastic: eIdx.length,
      spike(i) { const k = local[i]; if (k < 0) return; const t = tag[i]; if (t === "KC") kcCount[k]++; else if (t === "DAN") danCount[k]++; },
      step(ms) {
        const decay = Math.exp(-ms / o.tauE); let anyD = false; D.fill(0);
        for (let k = 0; k < trace.length; k++) { trace[k] = trace[k] * decay + kcCount[k]; kcCount[k] = 0; }
        for (let j = 0; j < dPre.length; j++) { const c = danCount[dPre[j]]; if (c > 0) { D[dPost[j]] += dN[j] * c; anyD = true; } }
        danCount.fill(0);
        if (anyD) for (let m = 0; m < D.length; m++) D[m] = tot[m] > 0 ? D[m] / tot[m] : 0;
        const forget = o.tauForget > 0 ? 1 - Math.exp(-ms / 1000 / o.tauForget) : 0;
        if (!P.enabled || (!anyD && !forget)) return;
        for (let k = 0; k < trace.length; k++) {
          const tr = trace[k]; if (tr < 1e-3 && !forget) continue;
          for (let q = ePtr[k]; q < ePtr[k + 1]; q++) {
            let r = ratio[q]; const dep = o.eta * tr * D[eM[q]];
            if (dep > 0) r *= Math.exp(-dep);
            if (forget) r += (1 - r) * forget;
            if (r !== ratio[q]) { ratio[q] = r; brain.w[eIdx[q]] = w0[eIdx[q]] * r; }
          }
        }
      },
      // 每个 MBON 的 KC 输入还剩原来的多少（1 = 没学过）
      strength() { const cur = new Float64Array(mbonIdx.length), ori = new Float64Array(mbonIdx.length); for (let q = 0; q < eIdx.length; q++) { const x = Math.abs(w0[eIdx[q]]); ori[eM[q]] += x; cur[eM[q]] += x * ratio[q]; } return Array.from(cur, (c, m) => ori[m] > 0 ? c / ori[m] : 1); },
      forEachEdge(fn) { for (let k = 0; k < kcIdx.length; k++) for (let q = ePtr[k]; q < ePtr[k + 1]; q++) fn(k, eM[q], Math.abs(w0[eIdx[q]]), ratio[q]); },
      apply() { for (let q = 0; q < eIdx.length; q++) brain.w[eIdx[q]] = w0[eIdx[q]] * ratio[q]; },   // brain.rebuildWeights() 之后调用
      reset() { ratio.fill(1); trace.fill(0); kcCount.fill(0); danCount.fill(0); P.apply(); },
      save() { return Array.from(ratio, r => Math.round(r * 1000) / 1000); }, load(a) { if (a && a.length === ratio.length) { ratio.set(a); P.apply(); } },
      // 只存变过的突触：[下标, 千分比, 下标, 千分比, …]
      saveSparse() { const out = []; for (let q = 0; q < ratio.length; q++) if (ratio[q] < 0.999) out.push(q, Math.round(ratio[q] * 1000)); return out; },
      loadSparse(a) { ratio.fill(1); for (let k = 0; a && k + 1 < a.length; k += 2) if (a[k] < ratio.length) ratio[a[k]] = a[k + 1] / 1000; P.apply(); },
    };
    return P;
  }
  const API = { create };
  if (typeof module !== "undefined" && module.exports) module.exports = API; else root.FlyPlasticity = API;
})(typeof window !== "undefined" ? window : globalThis);
