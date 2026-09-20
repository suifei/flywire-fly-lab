// 生态箱：发现卡。**奖励作弊和失败都是发现**——系统不替玩家纠正，只把证据摆出来，由玩家选：接受这个策略，或者改环境继续逼它。
// 一张卡 = { id, kind: exploit | failure | milestone, key, title, text, evidence{指标}, levers[可以去动的世界规则], when, agent, generation, verdict: null | "accepted" | "changed" }
// 判定用的阈值是手选的（写在 RULES 里，一处改全处改）；证据里的数字全部来自这只果蝇一生的统计（eco/sim.js 的 stats），不是文案。
(function (root) {
  const T = { rest: 0.6, wall: 0.6, wet: 0.5, eat: 0.45, hopsPerMin: 8, circle: 0.35, rotten: 0.3, minLife: 120 };
  const CAUSE_TEXT = { starve: ["饿死了", ["food", "foodRegrow", "rot"]], thirst: ["渴死了", ["water", "evaporation", "rain"]], temp: ["冷 / 热死了", ["tempDay", "tempNight", "sunrocks", "shade"]], toxin: ["吃坏的东西吃死了", ["rot", "food"]],
    bite: ["被甲虫吃掉了", ["predators", "predatorSpeed"]], exhaust: ["累死了", ["roughness", "wind"]], age: ["老死了——寿终正寝", []] };
  function lifeSummary(a, W) { const s = a.stats, life = Math.max(1, (a.deathT === null ? W.t : a.deathT) - a.born), f = v => +(v / life).toFixed(3);
    return { agent: a.id, generation: a.genome.generation, life: +life.toFixed(1), cause: a.cause, alive: a.alive, rest: f(s.tRest), eat: f(s.tEat), drink: f(s.tDrink), wall: f(s.tWall), wet: f(s.tWet), air: f(s.tAir), rotten: s.tEat > 0 ? +(s.tRotten / s.tEat).toFixed(3) : 0,
      meals: s.meals, drinks: s.drinks, hops: s.hops, flights: s.flights, bites: s.bites, dist: Math.round(s.dist), cells: s.nCells, foodVisits: s.foodVisits, waterVisits: s.waterVisits, hopsPerMin: +(s.hops / life * 60).toFixed(2),
      spread: s.dist > 0 ? +(s.nCells * 10 / s.dist).toFixed(3) : 0, reward: +s.reward.toFixed(3) }; }
  // 一条命结束（或到观察上限）时调用；baseline = 不学习的寿命中位数（有就给，用来判里程碑）
  function detect(L, ctx) { const cards = [], ev = keys => Object.fromEntries(keys.map(k => [k, L[k]])), add = (kind, key, title, text, evidence, levers) => cards.push({ id: `${key}-${L.agent}`, kind, key, title, text, evidence, levers, when: ctx && ctx.t, agent: L.agent, generation: L.generation, verdict: null });
    if (L.life >= T.minLife) {
      if (L.rest > T.rest) add("exploit", "lie-flat", "躺平", "它学会了不动：歇着立刻恢复体力、掉气味，身体的不适马上变小——奖励是真的，只是短视。", ev(["rest", "life", "dist", "meals", "drinks"]), ["predators", "food", "tempNight"]);
      if (L.wall > T.wall) add("exploit", "wall-hug", "贴着玻璃走", "大部分时间贴着箱壁。箱壁给了它一条不用决策的路。", ev(["wall", "life", "cells"]), ["size", "food"]);
      if (L.wet > T.wet) add("exploit", "soak", "泡在水里", "它守着水洼不走：水边凉快、随时能喝，别的需要被晾在一边。", ev(["wet", "drink", "eat", "life"]), ["water", "evaporation", "predators"]);
      if (L.eat > T.eat) add("exploit", "glutton", "守着食物不走", "它把近一半的时间花在吃上——饥饿那一项的奖励被它榨干了。", ev(["eat", "meals", "life", "bites"]), ["food", "rot", "predators"]);
      if (L.hopsPerMin > T.hopsPerMin) add("exploit", "jumpy", "跳个不停", "逃逸起跳是连接组自带的反射，它学不掉；但它总往会触发反射的地方去。", ev(["hopsPerMin", "hops", "bites", "life"]), ["predators", "predatorSpeed"]);
      if (L.dist > 2000 && L.spread < T.circle && L.wall < 0.3 && L.rest < 0.3) add("exploit", "circling", "原地打转", "走了很远的路，却几乎没离开过原地。", ev(["dist", "cells", "spread", "life"]), ["wind", "roughness"]);
      if (L.rotten > T.rotten && L.meals > 3) add("exploit", "rot-eater", "烂的也吃", "苦味先天会压住伸喙，但它学会了顶着苦味吃——饿的代价比中毒来得快。", ev(["rotten", "meals", "life", "cause"]), ["rot", "food"]);
    }
    if (!L.alive && L.cause) { const [t, lev] = CAUSE_TEXT[L.cause] || ["死了", []]; let text = "";
      if (L.cause === "thirst") text = `一生路过水 ${L.waterVisits} 次，喝了 ${L.drinks} 次。`; else if (L.cause === "starve") text = `一生碰到食物 ${L.foodVisits} 次，吃了 ${L.meals} 顿。`; else if (L.cause === "bite") text = `被咬 ${L.bites} 口，起跳 ${L.hops} 次。`; else if (L.cause === "toxin") text = `吃的东西里 ${(L.rotten * 100).toFixed(0)}% 是烂的。`;
      add(L.cause === "age" ? "milestone" : "failure", "death-" + L.cause, t, text, ev(["life", "cause", "meals", "drinks", "bites", "hops", "foodVisits", "waterVisits"]), lev); }
    if (ctx && ctx.baseline && L.life >= 1.5 * ctx.baseline) add("milestone", "outlive", "活过了不学习的 1.5 倍", `不学习的果蝇寿命中位数是 ${Math.round(ctx.baseline)} s。`, ev(["life", "meals", "drinks"]), []);
    if (L.drinks >= 5 && L.waterVisits > 0 && L.drinks / L.waterVisits > 0.5) add("milestone", "learned-drink", "学会了喝水", "水味只把伸喙神经元 MN9 推到十几 Hz，先天不够伸喙；碰到水就停下来喝，是它自己学的。", ev(["drinks", "waterVisits", "drink"]), []);
    return cards; }
  // 一批卡里同一种只留证据最强的一张（页面上不刷屏），并统计每种出现了几次
  function digest(cards) { const by = new Map(); for (const c of cards) { const e = by.get(c.key); if (!e) by.set(c.key, Object.assign({ count: 1 }, c)); else { e.count++; if ((c.evidence.life || 0) > (e.evidence.life || 0)) Object.assign(e, c, { count: e.count }); } } return [...by.values()]; }
  const API = { detect, digest, lifeSummary, T }; if (typeof module !== "undefined" && module.exports) module.exports = API; else root.EcoCards = API;
})(typeof window !== "undefined" ? window : globalThis);
