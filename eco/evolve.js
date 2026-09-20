// 生态箱 M3：跨代进化。32 只同时活在一个箱子里；活得好（吃饱、喝足、健康）的攒够了就产卵；后代带着**少量可遗传参数**的变异出生。
//   能遗传的只有 10 个数：学习率、探索幅度、飞行倾向、偏好体温、代谢快慢、警觉度（逃逸起跳的阈值倍率）、四个先天偏置（饿时朝醋味转、渴时朝湿处转、尝到水就喝、朝 / 背着捕食者气味转）。
//   **可塑性层不遗传**——每只果蝇出生时是一张白纸，一生里学到的东西随它一起死掉。连接组更不变：所有个体、所有世代共用同一个大脑。
//   没有适应度函数：没人给「活得久」打分。能不能留下后代只取决于身体状态够不够产卵——选择压力全部来自世界规则。
(function (root) {
  const N = typeof module !== "undefined" && module.exports, Sim = N ? require("./sim.js") : root.EcoSim, Cards = N ? require("./cards.js") : root.EcoCards;
  const CFG = { n: 32, reproTime: 100, reproHunger: 0.5, reproThirst: 0.5, reproHealth: 0.6, eggCost: 0.15, minAge: 60, immigrateBelow: 6, bin: 60, maxReplays: 40, hall: 12 };
  const MUT = { p: 0.5, learnRate: ["log", 0.25, 0.001, 0.1], explore: ["log", 0.2, 0.05, 1.2], flightBias: ["add", 0.6, -8, 2], tempPref: ["add", 1.0, 12, 36], metabolism: ["log", 0.08, 0.6, 1.6], caution: ["log", 0.15, 0.4, 2.5], innateTurn: ["add", 0.5, -6, 6] };
  const GENE_KEYS = ["learnRate", "explore", "flightBias", "tempPref", "metabolism", "caution", "innateTurn0", "innateTurn1", "innateTurn2", "innateTurn3"];
  const GENE_NAMES = { learnRate: "学习率", explore: "探索幅度", flightBias: "飞行倾向", tempPref: "偏好体温 ℃", metabolism: "代谢快慢", caution: "警觉度", innateTurn0: "先天：饿时朝醋味转", innateTurn1: "先天：渴时朝湿处转", innateTurn2: "先天：尝到水就喝", innateTurn3: "先天：朝捕食者气味转" };
  const flat = g => ({ learnRate: g.learnRate, explore: g.explore, flightBias: g.flightBias, tempPref: g.tempPref, metabolism: g.metabolism, caution: g.caution, innateTurn0: g.innateTurn[0], innateTurn1: g.innateTurn[1], innateTurn2: g.innateTurn[2], innateTurn3: g.innateTurn[3] });
  function mutate(genes, rand) { const gauss = () => Math.sqrt(-2 * Math.log(1 - rand())) * Math.cos(6.283185307 * rand()), g = Object.assign({}, genes, { innateTurn: genes.innateTurn.slice() });
    const one = (v, [mode, sd, lo, hi]) => { if (rand() > MUT.p) return v; v = mode === "log" ? v * Math.exp(sd * gauss()) : v + sd * gauss(); return Math.max(lo, Math.min(hi, v)); };
    for (const k of ["learnRate", "explore", "flightBias", "tempPref", "metabolism", "caution"]) g[k] = one(g[k], MUT[k]); for (let i = 0; i < 4; i++) g.innateTurn[i] = one(g.innateTurn[i], MUT.innateTurn); return g; }

  function create(rules, opts) {
    const o = Object.assign({ seed: 1, flight: !(opts && opts.solo), learn: "on", genes: null, solo: false }, opts || {}), sim = Sim.create(rules, { seed: o.seed, brain: o.brain, learn: o.learn, flight: o.flight, trail: true });
    const E = { sim, cfg: CFG, timeline: [], replays: [], cards: [], hall: [], lives: 0, births: 0, immigrants: 0, nextGenome: 1, bin: null, flight: o.flight, solo: !!o.solo, lifeLog: [] };   // solo = 单只模式（M2）：死了以后同一只带着它的可塑性层重生，不繁殖、不变异
    const founder = Object.assign({}, Sim.GENES, o.genes || {}, { innateTurn: ((o.genes && o.genes.innateTurn) || Sim.GENES.innateTurn).slice() });
    E.founder = founder; for (let i = 0; i < (E.solo ? 1 : CFG.n); i++) { const a = sim.spawn({ id: E.nextGenome++, parent: null, generation: 0, genes: founder }); a.repro = sim.world.rand() * 0.5; a.kids = 0; }
    attach(E); return E;
  }
  function attach(E) { const sim = E.sim, W = sim.world;
    const newBin = () => ({ t0: W.t, births: 0, deaths: {}, immigrants: 0, flights: 0, hops: 0, lifeSum: 0, lifeN: 0 });
    if (!E.bin) E.bin = newBin();
    E.step = function () { sim.step(); const dt = sim.dt, alive = []; let nAlive = 0; for (const a of sim.agents) if (a.alive) nAlive++;
      for (const a of sim.agents) { if (a.alive) { alive.push(a); const p = a.phys; if (a.air <= 0 && p.age > CFG.minAge && p.hunger < CFG.reproHunger && p.thirst < CFG.reproThirst && p.health > CFG.reproHealth) a.repro += dt * a.genome.genes.metabolism / CFG.reproTime;
            if (!E.solo && a.repro >= 1 && nAlive < CFG.n) { a.repro = 0; a.kids++; p.hunger = Math.min(1, p.hunger + CFG.eggCost); const kid = sim.spawn({ id: E.nextGenome++, parent: a.genome.id, generation: a.genome.generation + 1, genes: mutate(a.genome.genes, W.rand) });
              const ang = W.rand() * 6.2832, d = 6 + 10 * W.rand(), R = W.rules.size - 2; kid.x = a.x + Math.cos(ang) * d; kid.y = a.y + Math.sin(ang) * d; const dd = Math.hypot(kid.x, kid.y); if (dd > R) { kid.x *= R / dd; kid.y *= R / dd; } kid.repro = 0; kid.kids = 0; nAlive++; E.births++; E.bin.births++; } }   /* spawn 已把它接在 sim.agents 末尾，本轮循环稍后会走到它；这里再 push 一次就重复了（第一版种群出现过 34 只） */
        else { // 刚死：记一生、出卡、留回放
          const L = Cards.lifeSummary(a, W); L.genes = flat(a.genome.genes); if (E.solo) { L.n = E.lifeLog.length + 1; L.t = Math.round(W.t); E.lifeLog.push(L); if (E.lifeLog.length > 400) E.lifeLog.shift(); E.reborn = a; } L.kids = a.kids || 0; E.lives++; E.bin.deaths[a.cause] = (E.bin.deaths[a.cause] || 0) + 1; E.bin.lifeSum += L.life; E.bin.lifeN++; E.bin.flights += a.stats.flights; E.bin.hops += a.stats.hops;
          const cs = Cards.detect(L, { t: W.t }); for (const c of cs) { const seen = E.cards.find(x => x.key === c.key); if (seen) { seen.count++; if (L.life > (seen.evidence.life || 0) && seen.verdict === null) Object.assign(seen, c, { count: seen.count, id: seen.id }); } else { E.cards.push(Object.assign({ count: 1 }, c)); keepReplay(E, a, L, c.title, c.kind); } }
          E.hall.push({ life: L.life, kids: L.kids, generation: L.generation, genes: a.genome.genes }); E.hall.sort((x, y) => (y.kids - x.kids) || (y.life - x.life)); if (E.hall.length > CFG.hall) E.hall.length = CFG.hall;
          if (!E.oldest || L.life > E.oldest.life) { const big = !E.oldest || (E.lives >= 10 && L.life > 1.25 * (E.oldestShown || 0)); E.oldest = L; if (big) { E.oldestShown = L.life; keepReplay(E, a, L, "目前最长寿的一只", "milestone"); } }   /* 开头每死一只都是「新纪录」，不值得都留回放 */ } }
      sim.agents = alive;
      if (E.solo && E.reborn) { const old = E.reborn; E.reborn = null; (N ? require("./plastic.js") : root.EcoPlastic).clearTraces(old.P); const b = sim.spawn({ id: old.genome.id, parent: null, generation: old.genome.generation + 1, genes: old.genome.genes }, old.P); b.repro = 0; b.kids = 0; }
      // 快灭绝了：从「名人堂」（留下后代最多的那些）里取基因再变异一次放进来，算迁入，单独计数
      if (!E.solo && nAlive < CFG.immigrateBelow) { const src = E.hall.length ? E.hall[Math.floor(W.rand() * Math.min(4, E.hall.length))] : { genes: E.founder, generation: 0 }; const kid = sim.spawn({ id: E.nextGenome++, parent: null, generation: src.generation + 1, genes: mutate(src.genes, W.rand) }); kid.repro = 0; kid.kids = 0; E.immigrants++; E.bin.immigrants++; }
      if (W.t - E.bin.t0 >= CFG.bin) { const b = E.bin, g = {}, sd = {}; const F = sim.agents.map(a => flat(a.genome.genes)); for (const k of GENE_KEYS) { const v = F.map(f => f[k]), m = v.reduce((s, x) => s + x, 0) / Math.max(1, v.length); g[k] = +m.toFixed(4); sd[k] = +Math.sqrt(v.reduce((s, x) => s + (x - m) * (x - m), 0) / Math.max(1, v.length)).toFixed(4); }
        const gens = sim.agents.map(a => a.genome.generation); E.timeline.push({ t: Math.round(W.t), pop: sim.agents.length, births: b.births, deaths: b.deaths, immigrants: b.immigrants, meanLife: b.lifeN ? +(b.lifeSum / b.lifeN).toFixed(1) : null, flights: b.flights, hops: b.hops,
          gen: gens.length ? +(gens.reduce((s, x) => s + x, 0) / gens.length).toFixed(2) : 0, genMax: gens.length ? Math.max(...gens) : 0, genes: g, sd }); E.bin = newBin(); } };
    E.run = seconds => { const n = Math.round(seconds / sim.dt); for (let i = 0; i < n; i++) E.step(); return E; };
    return E; }
  function keepReplay(E, a, L, title, kind) { if (E.replays.length >= CFG.maxReplays) { const i = E.replays.findIndex(r => r.kind === "failure"); E.replays.splice(i >= 0 ? i : 0, 1); } const W = E.sim.world;
    E.replays.push({ t: +W.t.toFixed(1), title, kind, agent: a.id, generation: L.generation, cause: L.cause, life: L.life, trail: a.trail.slice(), scene: { size: W.rules.size, food: W.food.map(f => [+f.x.toFixed(1), +f.y.toFixed(1), W.isRotten(f) ? 1 : 0]), water: W.water.map(p => [+p.x.toFixed(1), +p.y.toFixed(1), +(p.r * Math.sqrt(p.level)).toFixed(1)]), predators: W.predators.map(p => [+p.x.toFixed(1), +p.y.toFixed(1)]) } }); }
  const API = { create, attach, mutate, flat, CFG, MUT, GENE_KEYS, GENE_NAMES }; if (typeof module !== "undefined" && module.exports) module.exports = API; else root.EcoEvolve = API;
})(typeof window !== "undefined" ? window : globalThis);
