// 生态箱：大脑的输入通道与读出特征的**唯一定义**（真脑、响应面、采样脚本、仿真都从这里取）。
// 输入 = 26 个通道的泊松频率（Hz）；输出 = 12 个特征群的发放率（Hz）。真脑和响应面是同一个接口的两种实现。
(function (root) {
  const WATER_IDS = ["720575940612950568", "720575940631898285", "720575940606002609", "720575940612579053", "720575940622902535", "720575940616177458", "720575940660292225", "720575940622486922", "720575940613786774",
    "720575940629852866", "720575940625861168", "720575940613996959", "720575940617857694", "720575940644965399", "720575940625203504", "720575940630553415", "720575940635172191", "720575940634796536"];
  // [通道名, 最大频率 Hz, 家族]；带 _L / _R 的是分侧的
  const FAMILIES = [["lc4", 200, 2], ["lplc2", 200, 2], ["lc16", 200, 2], ["jo", 200, 2], ["touch", 200, 2], ["thermo", 200, 2], ["hygro", 200, 2], ["audio", 200, 2], ["odorA", 200, 2], ["odorB", 200, 2], ["vinegar", 200, 2], ["geosmin", 200, 2],
    ["sugar", 320, 1], ["water", 320, 1], ["bitter", 320, 1]];
  const INPUTS = FAMILIES.flatMap(([n, , k]) => k === 2 ? [n + "_L", n + "_R"] : [n]), MAXHZ = Object.fromEntries(FAMILIES.flatMap(([n, m, k]) => k === 2 ? [[n + "_L", m], [n + "_R", m]] : [[n, m]]));
  const FEATURES = ["dnaL", "dnaR", "gf", "mn9", "adn1", "mdn", "odn1", "bdn2", "mbonReward", "mbonPunish", "pam", "ppl1"];

  // 把通道 / 特征映射到某个子回路（v5）的神经元下标
  function bind(SUB) {
    const G = SUB.groups, side = SUB.sides, typ = SUB.types, n = SUB.meta.n, pos = new Map(SUB.fids.map((f, i) => [String(f), i]));
    const glom = (names, sd) => names.flatMap(g => (SUB.meta.glomeruli[g] || []).filter(i => side[i] === sd)), sdn = { L: "left", R: "right" };
    const two = (f, fn) => ({ [f + "_L"]: fn("left"), [f + "_R"]: fn("right") });
    const idx = Object.assign({}, two("lc4", s => G["LC4_" + s]), two("lplc2", s => G["LPLC2_" + s]), two("lc16", s => G["LC16_" + s]), two("jo", s => G["JO_" + s]), two("touch", s => G["TOUCH_" + s]), two("thermo", s => G["THERMO_" + s]),
      two("hygro", s => G["HYGRO_" + s]), two("audio", s => G["AUDIO_" + s]), two("odorA", s => glom(SUB.meta.odors.A, s)), two("odorB", s => glom(SUB.meta.odors.B, s)), two("vinegar", s => glom(["DM1"], s)), two("geosmin", s => glom(["DA2"], s)),
      { sugar: [...G.SUGAR_left, ...G.SUGAR_right], water: WATER_IDS.map(f => pos.get(f)).filter(i => i !== undefined), bitter: [...G.BITTER_left, ...G.BITTER_right] });
    const waterSet = new Set(idx.water); idx.sugar = idx.sugar.filter(i => !waterSet.has(i));          // 水味觉神经元在注释里属于糖那一组；分开驱动
    const byType = t => { const o = []; for (let i = 0; i < n; i++) if (typ[i] === t) o.push(i); return o; };
    // MBON 按隔室：它的多巴胺输入（≥3 突触的边）里来自 PAM / PPL1 的比例（只看连接组，见 §48.3）
    const mbon = [], fr = { PAM: [], PPL1: [] }; { const isDan = new Map(); for (const c of ["PAM", "PPL1"]) for (const s of ["left", "right"]) for (const i of G[c + "_" + s]) isDan.set(i, c);
      const dec = (k, T) => { const bin = Buffer.from(SUB[k], "base64"); return new T(bin.buffer, bin.byteOffset, bin.length / T.BYTES_PER_ELEMENT); }, ip = dec("indptr", Int32Array), po = dec("post", Int32Array), w = dec("w", Float32Array);
      const mi = new Map(); for (let i = 0; i < n; i++) if (SUB.mb_tag[i] === "MBON") { mi.set(i, mbon.length); mbon.push(i); } const tot = new Float64Array(mbon.length), part = { PAM: new Float64Array(mbon.length), PPL1: new Float64Array(mbon.length) };
      for (const [d, c] of isDan) for (let e = ip[d]; e < ip[d + 1]; e++) { const m = mi.get(po[e]); if (m === undefined) continue; const cnt = Math.round(Math.abs(w[e]) / 0.275); if (cnt < 3) continue; tot[m] += cnt; part[c][m] += cnt; }
      for (const c of ["PAM", "PPL1"]) fr[c] = Array.from(part[c], (v, m) => tot[m] > 0 ? v / tot[m] : 0); }
    const feat = { dnaL: [...G.DNa01_left, ...G.DNa02_left], dnaR: [...G.DNa01_right, ...G.DNa02_right], gf: [...G.DNp01_left, ...G.DNp01_right], mn9: [...G.MN9_left, ...G.MN9_right], adn1: [...G.aDN1_left, ...G.aDN1_right], mdn: [...G.MDN_left, ...G.MDN_right],
      odn1: byType("DNg97"), bdn2: byType("DNg100"), pam: [...G.PAM_left, ...G.PAM_right], ppl1: [...G.PPL1_left, ...G.PPL1_right] };
    // 从一段时间的脉冲计数算 12 个特征（Hz）。DNa = 两种细胞合计；巨纤维 / MN9 / MDN / 前进 / 多巴胺 = 群均值；aDN1 = 左右取大；MBON = 按隔室加权的总发放
    function read(cnt, sec) { const mean = ix => ix.length ? ix.reduce((s, i) => s + cnt[i], 0) / ix.length / sec : 0, sum = ix => ix.reduce((s, i) => s + cnt[i], 0) / sec, o = {};
      o.dnaL = sum(feat.dnaL); o.dnaR = sum(feat.dnaR); o.gf = mean(feat.gf); o.mn9 = mean(feat.mn9); o.adn1 = Math.max(...feat.adn1.map(i => cnt[i] / sec), 0); o.mdn = mean(feat.mdn); o.odn1 = mean(feat.odn1); o.bdn2 = mean(feat.bdn2); o.pam = mean(feat.pam); o.ppl1 = mean(feat.ppl1);
      let a = 0, b = 0; mbon.forEach((i, m) => { a += fr.PAM[m] * cnt[i]; b += fr.PPL1[m] * cnt[i]; }); o.mbonReward = a / sec; o.mbonPunish = b / sec; return o; }
    return { idx, feat, mbon, read };
  }
  const API = { INPUTS, MAXHZ, FEATURES, FAMILIES, bind };
  if (typeof module !== "undefined" && module.exports) module.exports = API; else root.EcoChannels = API;
})(typeof window !== "undefined" ? window : globalThis);
