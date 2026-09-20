// 生态箱：**可塑性层**——后天学习发生的地方。它**不是连接组**：连接组（15,055 个神经元）是固定的身体，一生不变、也不遗传变异；
//   这一层是接在旁边的一组可变权重（演员 - 评论家），读三样东西：① 感觉神经元群的发放率，② 大脑的输出（下行神经元、蘑菇体输出、多巴胺），③ 身体内部状态；
//   输出的是对先天反射的**偏置**：转向偏置、走多快、碰到东西肯不肯吃喝、（解锁之后）要不要起飞。先天反射（巨纤维起跳、MN9 伸喙、DNa 转向、MDN 后退）一直在，学不掉。
// 学习规则是三因子的：Δw = 学习率 × δ × 资格迹，δ = 奖励 + γ·V(之后) − V(之前)；转向 / 速度的资格迹 = 探索噪声 × 输入（node perturbation）。
//   奖励只来自 eco/physiology.js 的 drive 下降。可塑性层**不遗传**；能遗传的只有学习率、探索幅度和四个先天偏置（genes）。
(function (root) {
  const NAMES = (() => { const n = ["dnaL", "dnaR", "gf", "mn9", "adn1", "mdn", "odn1", "bdn2", "mbonReward", "mbonPunish", "pam", "ppl1"].map(s => "脑:" + s);
    for (const s of ["vinegar", "geosmin", "hygro", "thermo", "jo", "odorA", "audio", "lc4", "touch"]) n.push("感:" + s + "Σ", "感:" + s + "Δ"); for (const s of ["vinegar", "hygro", "thermo", "odorA"]) n.push("感:" + s + "′");
    n.push("味:sugar", "味:water", "味:bitter", "内:hunger", "内:thirst", "内:tired", "内:hurt", "内:scent", "内:hot", "内:cold");
    for (const [g, s] of [["hunger", "vinegar"], ["thirst", "hygro"], ["hot", "thermo"], ["cold", "thermo"]]) n.push(g + "×" + s + "Σ", g + "×" + s + "Δ", g + "×" + s + "′");
    for (const s of ["vinegar", "hygro", "odorA"]) n.push(s + "Σ×joΔ");                       // 闻到气味时风从哪边来（迎风找源头要用；真实果蝇主要靠这个）
    n.push("坡:pitch", "坡:roll", "光", "1"); return n; })();
  // 身体左右对称：**往哪边转**只能由分左右的信号（名字以 Δ 结尾的、以及侧倾）决定；不分侧的信号只能决定**转得多不多**（趋激性 kinesis：探索噪声的幅度）
  const LATERAL = NAMES.map(s => (s.endsWith("Δ") || s === "坡:roll") ? 1 : 0);
  const NF = NAMES.length, IDX = Object.fromEntries(NAMES.map((s, i) => [s, i])), INNATE = [["Wt", "hunger×vinegarΔ"], ["Wt", "thirst×hygroΔ"], ["Wi", "味:water"], ["Wt", "感:odorAΔ"]];   // 四个可遗传的先天偏置：饿时朝醋味转、渴时朝湿处转、尝到水就喝、朝（或背着）捕食者气味转
  const HP = { gamma: 0.995, lambda: 0.9, alphaV: 0.03, ingestGain: 6, moveGain: 1, decay: 1e-4, rScale: 20, ouTau: 0.8, speedBias: 2.2, speedSigma: 0.5, wMax: 6, turnMax: 200 };
  function innate(genes) { const w = new Float64Array(NF); INNATE.forEach(([m, f], i) => { if (m === "Wt") w[IDX[f]] = genes.innateTurn[i]; }); return w; }
  function create(genes) { const z = () => new Float64Array(NF), P = { Wt: z(), Wk: z(), Ws: z(), Wi: z(), Wf: z(), V: z(), eT: z(), eK: z(), eS: z(), eI: z(), eF: z(), eV: z(), phi: z(), v: 0, nT: 0, nS: 0, has: false, steps: 0, dSum: 0 };
    INNATE.forEach(([m, f], i) => { P[m][IDX[f]] = genes.innateTurn[i]; }); return P; }
  const dot = (w, p) => { let s = 0; for (let i = 0; i < NF; i++) s += w[i] * p[i]; return s; }, sig = u => 1 / (1 + Math.exp(-u));
  function gauss(rand) { return Math.sqrt(-2 * Math.log(1 - rand())) * Math.cos(6.283185307 * rand()); }
  // act：phi = 此刻的特征；innate = { ingestLogit（MN9 给的先天伸喙倾向）, canIngest, flight（是否解锁） }
  function act(P, phi, genes, dt, rand, innate, out) {
    const k = Math.exp(-dt / HP.ouTau), kin = Math.exp(Math.max(-1.5, Math.min(1.5, dot(P.Wk, phi)))), sT = genes.explore * kin; P.zT = k * (P.zT || 0) + Math.sqrt(1 - k * k) * gauss(rand); P.nT = sT * P.zT; P.nS = k * P.nS + Math.sqrt(1 - k * k) * HP.speedSigma * gauss(rand);
    let mu = 0; for (let i = 0; i < NF; i++) if (LATERAL[i]) mu += P.Wt[i] * phi[i]; mu = Math.max(-1, Math.min(1, mu)); out.turn = (mu + P.nT) * HP.turnMax; out.speed = sig(dot(P.Ws, phi) + HP.speedBias + P.nS);
    const pI = innate.canIngest ? sig(dot(P.Wi, phi) + innate.ingestLogit) : 0; out.ingest = rand() < pI ? 1 : 0; out.pIngest = pI;
    const pF = innate.flight ? sig(dot(P.Wf, phi) + genes.flightBias) * dt : 0; out.takeoff = rand() < pF ? 1 : 0;
    // 资格迹：这一步「往哪边试了一下」× 当时的输入
    const gl = HP.gamma * HP.lambda, nt = P.zT, nk = P.zT * P.zT - 1, ns = P.nS / HP.speedSigma, gi = innate.canIngest ? out.ingest - pI : 0, gf = innate.flight ? out.takeoff - pF : 0;
    for (let i = 0; i < NF; i++) { const f = phi[i]; P.eT[i] = gl * P.eT[i] + (LATERAL[i] ? nt * f : 0); P.eK[i] = gl * P.eK[i] + (LATERAL[i] ? 0 : nk * f); P.eS[i] = gl * P.eS[i] + ns * f; P.eI[i] = gl * P.eI[i] + gi * f; P.eF[i] = gl * P.eF[i] + gf * f; P.eV[i] = gl * P.eV[i] + f; }
    P.v = dot(P.V, phi); P.has = true; return out;
  }
  // learn：r = 这一步的 drive 下降；phiNext = 之后的特征（死了就传 null）
  function learn(P, r, phiNext, genes, mode) {
    if (!P.has) return 0; const vN = phiNext ? dot(P.V, phiNext) : 0, delta = HP.rScale * r + HP.gamma * vN - P.v; P.steps++; P.dSum += Math.abs(delta);
    if (mode === "off") return delta; let n2 = 1; if (phiNext) for (let i = 0; i < NF; i++) n2 += phiNext[i] * phiNext[i];
    const aV = HP.alphaV / n2 * delta, aA = genes.learnRate / n2 * delta, M = HP.wMax, c = v => v > M ? M : v < -M ? -M : v;
    const aM = aA * HP.moveGain, kd = 1 - HP.decay, w0 = P.w0 || (P.w0 = innate(genes));   /* 不用就忘：策略权重慢慢衰减回先天值（τ ≈ 1,000 s）；没有奖励进来时，评论家的噪声不至于把策略带着漂走 */
    for (let i = 0; i < NF; i++) { P.V[i] = c(P.V[i] + aV * P.eV[i]); P.Wt[i] = c(w0[i] + (P.Wt[i] - w0[i]) * kd + aM * P.eT[i]); P.Wk[i] = c(P.Wk[i] * kd + 0.3 * aM * P.eK[i]); P.Ws[i] = c(P.Ws[i] * kd + aM * P.eS[i]); P.Wi[i] = c(P.Wi[i] + aA * HP.ingestGain * P.eI[i]);   /* 吃喝这一路不衰减：它的奖励是即时的，漂不走；衰减只会让它在两次喝水之间把刚学的忘掉（实测 1/10） */ P.Wf[i] = c(P.Wf[i] * kd + aA * P.eF[i]); }
    return delta;
  }
  function clearTraces(P) { for (const k of ["eT", "eK", "eS", "eI", "eF", "eV"]) P[k].fill(0); P.has = false; P.nT = 0; P.zT = 0; P.nS = 0; }
  const API = { create, act, learn, clearTraces, NAMES, NF, IDX, INNATE, LATERAL, HP }; if (typeof module !== "undefined" && module.exports) module.exports = API; else root.EcoPlastic = API;
})(typeof window !== "undefined" ? window : globalThis);
