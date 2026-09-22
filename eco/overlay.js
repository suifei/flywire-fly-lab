// 生态箱 → 3D 大自然：把生态箱的可塑性层 + 六种内部状态挂到 dodge/game_core.js 的那只果蝇上（G.attachEco，**默认不装**）。
//   与生态箱共用同一份代码：27 路输入的定义（channels.js）、特征（sim.js 的 buildFeatures）、可塑性层（plastic.js）、身体与内生奖励（physiology.js）。
//   大脑是 game_core 自己那个真的脉冲网络（v5）；这里只读它：感觉神经元此刻被驱动的频率、12 个读出特征最近 ~300 ms 的发放率。
//   对行为的影响只有三处，全是「先天反射 + 学到的偏置」：转向加一个偏置、走路速度乘一个系数（太低 = 歇着）、碰到东西肯不肯吃喝（MN9 必须先动）。
(function (root) {
  const N = typeof module !== "undefined" && module.exports, CH = N ? require("./channels.js") : root.EcoChannels, Plastic = N ? require("./plastic.js") : root.EcoPlastic, Phys = N ? require("./physiology.js") : root.EcoPhysiology, Sim = N ? require("./sim.js") : root.EcoSim, WK = (N ? require("./world.js") : root.EcoWorld).K;
  const IX = Object.fromEntries(CH.INPUTS.map((c, i) => [c, i])), TICK = 0.1, SMOOTH = 0.3;
  // opts: { SUB, genes, P（学成的权重；不给 = 白纸）, learn: "on" | "off", seed, tempDay, tempNight, record（记下每次决策时的 27 路输入，给 collect_manifold 用） }
  function create(opts) { const o = Object.assign({ learn: "off", seed: 1, tempDay: 28, tempNight: 18 }, opts || {}), genes = Object.assign({}, Sim.GENES, o.genes || {}, { innateTurn: ((o.genes && o.genes.innateTurn) || Sim.GENES.innateTurn).slice() }), B = CH.bind(o.SUB);
    let rs = (o.seed >>> 0) || 1; const rand = () => { rs = (rs + 0x6d2b79f5) >>> 0; let t = rs; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
    const cnt = new Float32Array(o.SUB.meta.n), ema = new Float32Array(CH.FEATURES.length);
    const a = { xin: new Float32Array(CH.INPUTS.length), out: new Float32Array(CH.FEATURES.length), phi: new Float64Array(Plastic.NF), lp: { vinegar: 0, hygro: 0, thermo: 0, odorA: 0 }, dt: TICK, rand, genome: { genes }, phys: Phys.create(genes), P: o.P || Plastic.create(genes) };
    Plastic.clearTraces(a.P);
    const E = { agent: a, genes, act: { turn: 0, speed: 1, ingest: 0, takeoff: 0, pIngest: 0 }, speedFactor: 1, rest: false, vigor: 1, alive: true, cause: null, t: 0, acc: 0, r: 0, lastHits: 0, effortAcc: 0, effortN: 0, record: o.record ? [] : null,
      stats: { tEat: 0, tDrink: 0, tRest: 0, meals: 0, drinks: 0, waterVisits: 0, foodVisits: 0, bites: 0, reward: 0, thirstSum: 0, n: 0 }, wasOn: 0, wasState: "" };
    E.spike = i => { cnt[i]++; };
    // 每个游戏步（5 ms）调一次；每 0.1 s 做一次决策
    E.tick = function (G, out, dt) { if (!E.alive) return; const S = G.S, st = E.stats; E.t += dt; E.acc += dt; E.effortAcc += Math.abs(S.speed || 0) / G.CFG.walkSpeed; E.effortN++;
      const p = G.onPellet, eatingNow = S.state === "feed" && p && p.type !== "water", drinkingNow = S.state === "feed" && p && p.type === "water"; if (eatingNow) st.tEat += dt; if (drinkingNow) st.tDrink += dt; if (E.rest && S.state === "walk") st.tRest += dt;
      if (E.acc < TICK - 1e-9) return; const T = E.acc; E.acc = 0;
      // 12 个读出特征：这 0.1 s 的脉冲计数 → ~300 ms 平滑（与 eco/brain_live.js 一致）
      const y = B.read(cnt, T), al = Math.min(1, T / SMOOTH); CH.FEATURES.forEach((f, j) => { ema[j] += al * (y[f] - ema[j]); a.out[j] = ema[j] < 0.3 ? 0 : ema[j]; }); cnt.fill(0);
      // 27 路输入：直接读 game_core 此刻送进感觉神经元的频率
      const x = a.xin, L = G.loom || {}, Sn = G.senses || {}, F = G.fieldLR, olf = G.CFG.olfRate, conc = (G.MB && G.MB.conc) || {}, c1 = k => conc[k] || { L: 0, R: 0 }; x.fill(0);
      x[IX.lc4_L] = L.lc4L || 0; x[IX.lc4_R] = L.lc4R || 0; x[IX.lplc2_L] = L.lplc2L || 0; x[IX.lplc2_R] = L.lplc2R || 0; x[IX.lc16_L] = L.lc16L || 0; x[IX.lc16_R] = L.lc16R || 0;
      x[IX.jo_L] = (G.joInput && G.joInput.L) || 0; x[IX.jo_R] = (G.joInput && G.joInput.R) || 0; x[IX.touch_L] = (G.touch && G.touch.L) || 0; x[IX.touch_R] = (G.touch && G.touch.R) || 0;
      if (F) { x[IX.thermo_L] = F.tL; x[IX.thermo_R] = F.tR; x[IX.hygro_L] = F.hL; x[IX.hygro_R] = F.hR; } else if (G.field) { const t = Math.min(200, G.field.thermo * 200), h = Math.min(200, G.field.hygro * 200); x[IX.thermo_L] = x[IX.thermo_R] = t; x[IX.hygro_L] = x[IX.hygro_R] = h; }
      x[IX.audio_L] = Sn.audioL || 0; x[IX.audio_R] = Sn.audioR || 0;
      for (const [kind, ch] of [["vinegar", "vinegar"], ["geosmin", "geosmin"], ["A", "odorA"], ["B", "odorB"]]) { const c = c1(kind); x[IX[ch + "_L"]] = Math.min(olf, c.L * olf); x[IX[ch + "_R"]] = Math.min(olf, c.R * olf); }
      if (G.gust) { x[IX.sugar] = G.gust.sugar; x[IX.bitter] = G.gust.bitter; x[IX.water] = G.gust.water; }
      if (E.record && E.record.length < 20000) E.record.push(Array.from(x, q => Math.round(q)));
      // 身体：吃 / 喝 / 被撞 / 冷热 / 用力
      const hits = G.score.hit - E.lastHits; E.lastHits = G.score.hit; if (hits > 0) st.bites += hits; const light = Math.max(0, Math.min(1, G.CFG.light)), rain = G.world && G.world.weather ? G.world.weather.rain : 0, thermo = G.field ? G.field.thermo : 0;
      const ambient = o.tempNight + (o.tempDay - o.tempNight) * light + WK.rockHeatC * thermo / WK.rockGain - (rain > 0.3 ? 2 : 0), effort = E.effortN ? E.effortAcc / E.effortN : 0; E.effortAcc = 0; E.effortN = 0;
      let along = 0, across = 0; if (G.world && G.world.grad) { const gr = G.world.grad(S.x, S.y), c = Math.cos(S.h), sn = Math.sin(S.h); along = gr[0] * c + gr[1] * sn; across = -gr[0] * sn + gr[1] * c; }
      const on = (p ? (p.type === "water" ? 2 : 1) : 0); if ((on & 1) && !(E.wasOn & 1)) st.foodVisits++; if ((on & 2) && !(E.wasOn & 2)) st.waterVisits++; E.wasOn = on;
      if (eatingNow && E.wasState !== "eat") st.meals++; if (drinkingNow && E.wasState !== "drink") st.drinks++; E.wasState = eatingNow ? "eat" : drinkingNow ? "drink" : "";
      E.r = Phys.step(a.phys, genes, T, { eating: eatingNow, rotten: p && p.type === "bitter" ? 1 : p && p.type === "mixed" ? 0.5 : 0, drinking: drinkingNow, bites: hits * WK.biteDamage, ambient, effort, flying: S.z > 0.01, raining: rain > 0.3, resting: E.rest && S.state === "walk", wet: !!(p && p.type === "water") && S.z <= 0.01, wind: (G.wind && G.wind.speed) || 0, uphill: Math.max(0, along) * 3 });
      st.reward += E.r; st.thirstSum += a.phys.thirst; st.n++;
      if (a.phys.health <= 0) { E.alive = false; E.cause = Phys.causeOfDeath(a.phys); Plastic.learn(a.P, E.r, null, genes, o.learn === "on" ? "on" : "off"); E.speedFactor = 0; E.act.ingest = 0; return; }
      // 先学（上一次决策之后的奖励、此刻的状态），再决策
      const phi = Sim.buildFeatures(a, along, across, light); Plastic.learn(a.P, E.r, phi, genes, o.learn === "on" ? "on" : "off");
      const mn9 = out.mn9 || 0, can = !!p && S.z <= 0.01 && mn9 > Sim.BODY.mn9Min; Plastic.act(a.P, phi, genes, T, rand, { canIngest: can, ingestLogit: (mn9 - Sim.BODY.feedThreshold) / Sim.BODY.feedSlope, flight: false }, E.act);
      E.rest = E.act.speed < Sim.BODY.restSpeed; E.speedFactor = E.rest ? 0 : E.act.speed; E.vigor = 0.35 + 0.65 * Math.min(1, a.phys.stamina / 0.3); };
    // 死了以后同一只重生（单只模式的语义）：身体复位，学到的权重留着
    E.reborn = () => { a.phys = Phys.create(genes); Plastic.clearTraces(a.P); ema.fill(0); cnt.fill(0); E.alive = true; E.cause = null; E.speedFactor = 1; E.rest = false; for (const k in E.stats) E.stats[k] = 0; E.t = 0; };
    return E; }
  const API = { create }; if (N) module.exports = API; else root.EcoOverlay = API;
})(typeof window !== "undefined" ? window : globalThis);
