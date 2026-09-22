// 生态箱：仿真循环。无渲染、可快进、多只。一步 = 0.1 s：感觉 → 大脑（真脑或响应面）→ 可塑性层 → 先天反射 + 学到的偏置 → 身体 → 生理 → 奖励 → 学习。
// 先天的部分与 dodge/game_core.js 同一套常数：转向 = 6 °/s × (左 DNa − 右 DNa)；巨纤维 > 90 Hz 起跳；MDN > 20 Hz 后退；MN9 30 Hz 左右伸喙。
(function (root) {
  const N = typeof module !== "undefined" && module.exports, World = N ? require("./world.js") : root.EcoWorld, Phys = N ? require("./physiology.js") : root.EcoPhysiology, Senses = N ? require("./senses.js") : root.EcoSenses,
    Plastic = N ? require("./plastic.js") : root.EcoPlastic, CH = N ? require("./channels.js") : root.EcoChannels;
  const GENES = { learnRate: 0.012, explore: 0.35, flightBias: -4, tempPref: 25, metabolism: 1, caution: 1, innateTurn: [0, 0, 0, 0] };
  const BODY = { walkSpeed: 18, backSpeed: 12, turnGain: 6, turnMax: 420, gfThreshold: 90, mdnThreshold: 20, feedThreshold: 30, feedSlope: 6, mn9Min: 5, hopDist: 22, hopTime: 0.35, hopCost: 0.035, hopCooldown: 1.2,
    flightSpeed: 60, flightTime: 1.2, flightMinStamina: 0.3, slopeK: 1.2, restSpeed: 0.15 };
  const SMOOTH = 0.3, FSCALE = [40, 40, 250, 100, 30, 30, 30, 80, 100, 200, 10, 10], IX = Senses.IX, PI = Plastic.IDX, NF = Plastic.NF;
  const PAIRS = ["vinegar", "geosmin", "hygro", "thermo", "jo", "odorA", "audio", "lc4", "touch"], DERIV = ["vinegar", "hygro", "thermo", "odorA"], GATED = [["hunger", "vinegar"], ["thirst", "hygro"], ["hot", "thermo"], ["cold", "thermo"]];

  function newAgent(sim, genome, plastic) { const W = sim.world, a0 = W.rand() * 6.2832, d = Math.sqrt(W.rand()) * W.rules.size * 0.5, genes = Object.assign({}, GENES, genome && genome.genes, { innateTurn: ((genome && genome.genes && genome.genes.innateTurn) || GENES.innateTurn).slice() });
    const a = { id: sim.nextId++, genome: { id: (genome && genome.id) || sim.nextId, parent: genome ? genome.parent : null, generation: genome ? genome.generation || 0 : 0, genes }, phys: Phys.create(genes), P: plastic || Plastic.create(genes),
      x: Math.cos(a0) * d, y: Math.sin(a0) * d, h: W.rand() * 6.2832, air: 0, avx: 0, avy: 0, flying: false, cool: 0, lastD: [], dt: sim.dt, state: "walk", alive: true, born: W.t, deathT: null, cause: null, r: 0, rs: (W.rand() * 4294967296) >>> 0,
      xin: new Float32Array(CH.INPUTS.length), out: new Float32Array(CH.FEATURES.length), ema: new Float32Array(CH.FEATURES.length), phi: new Float64Array(NF), lp: { vinegar: 0, hygro: 0, thermo: 0, odorA: 0 }, act: { turn: 0, speed: 1, ingest: 0, takeoff: 0, pIngest: 0 }, threatLP: 0, threatDir: 0, onFood: null, onWater: null, rotten: 0,
      stats: { tEat: 0, tDrink: 0, tRest: 0, tWall: 0, tWet: 0, tAir: 0, tRotten: 0, meals: 0, drinks: 0, hops: 0, flights: 0, bites: 0, dist: 0, reward: 0, rPos: 0, foodVisits: 0, waterVisits: 0, nCells: 0, cells: {}, tNight: 0, tHot: 0, tCold: 0 }, wasOn: 0, trail: [], trailT: 0, rbuf: [], lag: 300 };
    Plastic.clearTraces(a.P); a.rand = () => { a.rs = (a.rs + 0x6d2b79f5) >>> 0; let t = a.rs; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
    sim.agents.push(a); sim.emit({ t: W.t, agent: a.id, kind: "birth", data: { generation: a.genome.generation } }); return a; }

  // 可塑性层的特征。生态箱（这里）和 3D 大自然（eco/overlay.js）用的是**同一个函数**：a = { xin(27 路输入 Hz), out(12 个大脑输出 Hz), phys, genome.genes, phi, lp, dt, rand }，
  //   along / across = 脚下的坡度在体轴方向 / 侧向的分量，light = 光照 0–1
  function buildFeatures(a, along, across, light) { const x = a.xin, o = a.out, p = a.phys, g = a.genome.genes, phi = a.phi, dt = a.dt; let i = 0; for (let j = 0; j < 12; j++) phi[i++] = Math.min(2, o[j] / FSCALE[j]);
    /* 可塑性层读的是感觉神经元群的发放，不是干净的物理量：每侧按 30 个神经元、0.1 s 的泊松计数加噪声 */
    const nz = r => { if (r <= 0) return 0; const lam = r * 3; const u = Math.sqrt(-2 * Math.log(1 - a.rand())) * Math.cos(6.283185307 * a.rand()); return Math.max(0, lam + Math.sqrt(lam) * u) / 3; };
    const S = {}, D = {}; for (const s of PAIRS) { const L = nz(x[IX[s + "_L"]]), R = nz(x[IX[s + "_R"]]); S[s] = (L + R) / 400; D[s] = (L - R) / (L + R + 20); phi[i++] = S[s]; phi[i++] = D[s]; }
    const dv = {}; for (const s of DERIV) { a.lp[s] += (S[s] - a.lp[s]) * Math.min(1, dt / 1.0); dv[s] = Math.max(-1, Math.min(1, (S[s] - a.lp[s]) * 6)); phi[i++] = dv[s]; }
    phi[i++] = x[IX.sugar] / 200; phi[i++] = x[IX.water] / 200; phi[i++] = x[IX.bitter] / 200;
    const I = { hunger: p.hunger, thirst: p.thirst, hot: Math.max(0, Math.min(1, (p.bodyTemp - g.tempPref) / 10)), cold: Math.max(0, Math.min(1, (g.tempPref - p.bodyTemp) / 10)) };
    phi[i++] = p.hunger; phi[i++] = p.thirst; phi[i++] = 1 - p.stamina; phi[i++] = 1 - p.health; phi[i++] = p.scent; phi[i++] = I.hot; phi[i++] = I.cold;
    for (const [gt, s] of GATED) { phi[i++] = I[gt] * S[s]; phi[i++] = I[gt] * D[s]; phi[i++] = I[gt] * dv[s]; }
    for (const s of ["vinegar", "hygro", "odorA"]) phi[i++] = Math.min(1, S[s] * 2) * D.jo;
    phi[i++] = Math.max(-1, Math.min(1, along * 2)); phi[i++] = Math.max(-1, Math.min(1, across * 2)); phi[i++] = light; phi[i++] = 1; return phi; }
  function features(a, W) { const gr = W.grad(a.x, a.y), c = Math.cos(a.h), sn = Math.sin(a.h); a.along = gr[0] * c + gr[1] * sn; return buildFeatures(a, a.along, -gr[0] * sn + gr[1] * c, W.light()); }

  // 读档迁移：存档格式随版本演进，旧存档里的果蝇缺后来加的字段。接着跑之前补齐；可塑性层的维度对不上（特征数改过）就重置这只果蝇学到的权重——
  //   宁可忘掉，也不让页面在 sim.step 里崩掉（2026-09-23：旧存档没有 ema，页面报 Cannot read properties of undefined (reading '0')）
  const P_KEYS = ["Wt", "Wk", "Ws", "Wi", "Wf", "V", "eT", "eK", "eS", "eI", "eF", "eV", "phi"];
  function migrate(a) { const nOut = CH.FEATURES.length, nIn = CH.INPUTS.length;
    if (!(a.ema instanceof Float32Array) || a.ema.length !== nOut) a.ema = new Float32Array(nOut);
    if (!(a.out instanceof Float32Array) || a.out.length !== nOut) a.out = new Float32Array(nOut);
    if (!(a.xin instanceof Float32Array) || a.xin.length !== nIn) a.xin = new Float32Array(nIn);
    if (!(a.phi instanceof Float64Array) || a.phi.length !== NF) a.phi = new Float64Array(NF);
    a.lp = Object.assign({ vinegar: 0, hygro: 0, thermo: 0, odorA: 0 }, a.lp || {}); for (const k in a.lp) if (!Number.isFinite(a.lp[k])) a.lp[k] = 0;
    if (!a.lastD) a.lastD = []; if (!a.act) a.act = { turn: 0, speed: 1, ingest: 0, takeoff: 0, pIngest: 0 };
    const P = a.P, okP = P && P_KEYS.every(k => P[k] instanceof Float64Array && P[k].length === NF);
    if (!okP) { a.P = Plastic.create(a.genome.genes); Plastic.clearTraces(a.P); a.migrated = "plastic-reset"; }   /* 只有真的重置了才清资格迹：正常读档必须与不中断逐位相同 */
    a._v = 1; }

  function create(rules, opts) {
    const o = Object.assign({ seed: 1, dt: 0.1, brain: null, learn: "on", flight: false, noBrainFeatures: false, trail: true }, opts || {});
    const sim = { world: World.create(rules, o.seed), agents: [], dt: o.dt, nextId: 1, events: [], listeners: [], opts: o, brain: o.brain };
    sim.emit = ev => { sim.events.push(ev); if (sim.events.length > 4000) sim.events.splice(0, 1000); for (const f of sim.listeners) f(ev); }; sim.on = f => sim.listeners.push(f);
    sim.spawn = (genome, plastic) => newAgent(sim, genome, plastic);
    sim.step = function () { const W = sim.world, dt = sim.dt, bites = W.step(dt, sim.agents);
      for (const a of sim.agents) { if (!a.alive) continue; if (!a._v) migrate(a); const p = a.phys, g = a.genome.genes, st = a.stats; let bite = 0; a.bite = null; for (const b of bites) if (b.agent === a) { bite += World.K.biteDamage; a.bite = b; } if (bite > 0) { st.bites++; sim.emit({ t: W.t, agent: a.id, kind: "hit", data: { health: +p.health.toFixed(2) } }); }
        Senses.sense(W, a, sim.agents, a.xin); { const br = a.brain || sim.brain; br.eval(a.xin, a.out, a.rand); if (br.kind === "surface" && !br.smoothed) { const al = Math.min(1, dt / SMOOTH); for (let j = 0; j < a.out.length; j++) { a.ema[j] += al * (a.out[j] - a.ema[j]); a.out[j] = a.ema[j] < 0.3 ? 0 : a.ema[j]; } } }   /* 响应面共用一个对象，读出的 τ = 0.3 s 平滑按个体做（与 eco/brain_live.js 一致） */ if (o.noBrainFeatures) { /* 探索性对照：可塑性层看不到大脑输出（先天反射照旧） */ }
        const phi = features(a, W); if (o.noBrainFeatures) for (let j = 0; j < 12; j++) phi[j] = 0;
        // 先学（上一步的奖励、这一步的状态），再做
        let r = a.r; if (o.learn === "shuffle") { a.rbuf.push(r); if (a.rbuf.length > 700) a.rbuf.shift(); if (a.rand() < dt / 30) a.lag = 200 + Math.floor(a.rand() * 400); r = a.rbuf.length > a.lag ? a.rbuf[a.rbuf.length - 1 - a.lag] : 0; }
        else if (o.learn === "yoked") { a.stepN = (a.stepN || 0) + 1; r = o.yoke && o.yoke.length ? o.yoke[a.stepN % o.yoke.length] : 0; }   /* 轭式对照：别的命的奖励序列原样回放，与自己的行为无关 */
        if (o.recordReward) (a.rtrace || (a.rtrace = [])).push(a.r);
        Plastic.learn(a.P, r, phi, g, o.learn === "off" ? "off" : "on");
        const out = a.out, mn9 = out[3], canIngest = a.air <= 0 && (a.onFood || a.onWater) && mn9 > BODY.mn9Min;
        Plastic.act(a.P, phi, g, dt, a.rand, { canIngest, ingestLogit: (mn9 - BODY.feedThreshold) / BODY.feedSlope, flight: o.flight && a.air <= 0 }, a.act);
        if (o.trace) o.trace(a, { onWater: !!a.onWater, onFood: !!a.onFood, mn9, canIngest, pIngest: a.act.pIngest, ingest: a.act.ingest, dnaL: out[0], dnaR: out[1], speed: a.act.speed, turn: a.act.turn });   /* 诊断用：每次决策回调（L2 那 4 倍就是靠它拆开的） */
        let eating = false, drinking = false, effort = 0, resting = false, uphill = 0; a.cool = Math.max(0, a.cool - dt);
        if (a.air > 0) { a.x += a.avx * dt; a.y += a.avy * dt; if (a.flying) { a.x += Math.cos(W.wind.dir) * W.wind.speed * 0.6 * dt; a.y += Math.sin(W.wind.dir) * W.wind.speed * 0.6 * dt; } a.air -= dt; st.tAir += dt; a.state = a.flying ? "fly" : "hop"; if (a.air <= 0) { a.air = 0; a.flying = false; a.lastD.length = 0; } }
        else if (out[2] > BODY.gfThreshold * g.caution && a.cool <= 0) { const dir = a.threatLP > 0 ? a.threatDir + Math.PI + (a.rand() - 0.5) * 0.8 : a.h; a.air = BODY.hopTime; a.avx = Math.cos(dir) * BODY.hopDist / BODY.hopTime; a.avy = Math.sin(dir) * BODY.hopDist / BODY.hopTime; a.h = dir; a.cool = BODY.hopCooldown;
          p.stamina = Math.max(0, p.stamina - BODY.hopCost); st.hops++; a.state = "hop"; sim.emit({ t: W.t, agent: a.id, kind: "hop", data: {} }); }
        else if (a.act.takeoff && p.stamina > BODY.flightMinStamina) { a.air = BODY.flightTime; a.flying = true; a.avx = Math.cos(a.h) * BODY.flightSpeed; a.avy = Math.sin(a.h) * BODY.flightSpeed; st.flights++; a.state = "fly"; sim.emit({ t: W.t, agent: a.id, kind: "takeoff", data: {} }); }
        else { const omega = Math.max(-BODY.turnMax, Math.min(BODY.turnMax, BODY.turnGain * (out[0] - out[1]) + a.act.turn)) * Math.PI / 180; a.h += omega * dt; if (a.h > 6.2832) a.h -= 6.2832; else if (a.h < 0) a.h += 6.2832;
          const vigor = 0.35 + 0.65 * Math.min(1, p.stamina / 0.3), sf = Math.max(0.45, Math.min(1.25, 1 - BODY.slopeK * a.along)); let v = 0;
          if (out[5] > BODY.mdnThreshold) { v = -BODY.backSpeed * vigor; a.state = "back"; }
          else if (canIngest && a.act.ingest) { if (a.onFood) { eating = true; a.onFood.amount -= Phys.C.eatAmount * dt; if (a.state !== "eat") { st.meals++; if (W.t - (a.evT || -99) > 8) { a.evT = W.t; sim.emit({ t: W.t, agent: a.id, kind: "eat", data: { rotten: +a.rotten.toFixed(2), hunger: +p.hunger.toFixed(2) } }); } } a.state = "eat"; st.tEat += dt; if (a.rotten > 0) st.tRotten += dt; }
            else { drinking = true; a.onWater.level = Math.max(0, a.onWater.level - Phys.C.drinkAmount * dt); if (a.state !== "drink") { st.drinks++; if (W.t - (a.evT || -99) > 8) { a.evT = W.t; sim.emit({ t: W.t, agent: a.id, kind: "drink", data: { thirst: +p.thirst.toFixed(2) } }); } } a.state = "drink"; st.tDrink += dt; } }
          else { const cmd = a.act.speed < BODY.restSpeed ? 0 : a.act.speed; v = BODY.walkSpeed * g.metabolism * cmd * vigor * sf * (W.rain > 0 ? 0.75 : 1);   /* 代谢快 = 走得快、饿得快、产卵快 */ a.state = cmd === 0 ? "rest" : "walk"; if (cmd === 0) { resting = true; st.tRest += dt; } }
          a.x += Math.cos(a.h) * v * dt; a.y += Math.sin(a.h) * v * dt; effort = Math.abs(v) / (BODY.walkSpeed * g.metabolism); uphill = Math.max(0, a.along * Math.sign(v)) * 3; st.dist += Math.abs(v) * dt; }
        { const on = (a.onFood ? 1 : 0) | (a.onWater ? 2 : 0); if ((on & 1) && !(a.wasOn & 1)) st.foodVisits++; if ((on & 2) && !(a.wasOn & 2)) st.waterVisits++; a.wasOn = on; const ck = Math.floor(a.x / 10) + "," + Math.floor(a.y / 10); if (!st.cells[ck]) { st.cells[ck] = 1; st.nCells++; }
          if (W.sun() <= 0) st.tNight += dt; if (p.bodyTemp > g.tempPref + 5) st.tHot += dt; else if (p.bodyTemp < g.tempPref - 5) st.tCold += dt; }
        const R = W.rules.size - 0.5, d = Math.hypot(a.x, a.y); if (d > R) { a.x *= R / d; a.y *= R / d; } if (d > R - 4) st.tWall += dt; if (a.onWater) st.tWet += dt;
        a.r = Phys.step(p, g, dt, { eating, rotten: a.rotten, drinking, bites: bite, ambient: W.temp(a.x, a.y), effort, flying: a.flying, raining: W.rain > 0, resting, wet: !!a.onWater && a.air <= 0, wet: !!a.onWater && a.air <= 0, wind: W.wind.speed / World.K.windMax, uphill }); st.reward += a.r; if (a.r > 0) st.rPos += a.r;
        if (o.trail) { a.trailT += dt; if (a.trailT >= 0.5) { a.trailT = 0; a.trail.push([+W.t.toFixed(1), +a.x.toFixed(1), +a.y.toFixed(1), +a.h.toFixed(2), a.state, +p.health.toFixed(2)]); if (a.trail.length > 240) a.trail.shift(); } }
        if (p.health <= 0) { a.alive = false; a.deathT = W.t; a.cause = Phys.causeOfDeath(p); Plastic.learn(a.P, a.r, null, g, o.learn === "off" ? "off" : "on"); sim.emit({ t: W.t, agent: a.id, kind: "death", data: { cause: a.cause, age: +(W.t - a.born).toFixed(1) } }); } }
    };
    return sim;
  }
  const API = { create, buildFeatures, GENES, BODY, FSCALE }; if (typeof module !== "undefined" && module.exports) module.exports = API; else root.EcoSim = API;
})(typeof window !== "undefined" ? window : globalThis);
