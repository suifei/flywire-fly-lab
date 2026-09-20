// 生态箱：生理。六种内部状态 + 内生奖励。
//   饥饿 hunger、口渴 thirst（0 = 满足，1 = 极限）；体力 stamina、健康 health（1 = 满）；气味 scent（0 = 干净，1 = 很重，容易被捕食者盯上）；体温 bodyTemp（℃）。
// **奖励不是玩家给的目标**：它只是「身体离舒适点有多远」这个量的减少（drive reduction，Keramati & Gutkin 2014 的稳态强化学习）。
//   drive D = Σ wᵢ·(偏离ᵢ)²，reward = D(之前) − D(之后)。吃到东西 → 饥饿下降 → D 下降 → 正奖励；被咬 → 健康下降 → 负奖励。没有任何一项写着「去找食物」。
// 这些常数是**身体**，不是世界规则：玩家改不了（手选值，登记在 docs/ecobox/PLAN.md）。只有 metabolism / tempPref 两项可以遗传。
(function (root) {
  const C = { hungerTime: 600, thirstTime: 480, eatRate: 0.10, eatAmount: 0.035, drinkRate: 0.22, drinkAmount: 0.004, tempTau: 12, tempTol: 7, tempSpan: 5, starveDamage: 0.006, thirstDamage: 0.007, tempDamage: 0.006, toxinDamage: 0.035,
    exhaustDamage: 0.004, regen: 0.0035, walkCost: 0.0025, restGain: 0.045, flyCost: 0.10, scentRate: 0.0015, scentEat: 0.015, scentFade: 0.004, groom: 0.05, rainWash: 0.08, wadeWash: 0.06, senescence: 3600, senesceDamage: 0.004,
    w: { hunger: 1, thirst: 1, stamina: 0.25, health: 3, scent: 0.12, temp: 0.6 } };
  function create(genes) { return { hunger: 0.25, thirst: 0.25, stamina: 1, health: 1, scent: 0.1, bodyTemp: (genes && genes.tempPref) || 25, age: 0, dmg: { starve: 0, thirst: 0, temp: 0, toxin: 0, bite: 0, exhaust: 0, age: 0 } }; }
  function drive(p, genes) { const w = C.w, dT = (p.bodyTemp - genes.tempPref) / 10; return w.hunger * p.hunger * p.hunger + w.thirst * p.thirst * p.thirst + w.stamina * (1 - p.stamina) * (1 - p.stamina) + w.health * (1 - p.health) * (1 - p.health) + w.scent * p.scent * p.scent + w.temp * dT * dT; }
  // ctx: { eating, rotten(0–1), drinking, bites, ambient, effort(0–1), flying, raining, resting, wet, wind(0–1), uphill } → 返回奖励
  function step(p, genes, dt, ctx) {
    const D0 = drive(p, genes), m = genes.metabolism, cl = v => Math.max(0, Math.min(1, v)), d = p.dmg;
    p.age += dt; p.bodyTemp += dt * (ctx.ambient - p.bodyTemp) / C.tempTau;
    const cold = Math.max(0, genes.tempPref - p.bodyTemp), hot = Math.max(0, p.bodyTemp - genes.tempPref);
    p.hunger = cl(p.hunger + dt * m / C.hungerTime * (1 + 0.15 * ctx.effort + (ctx.flying ? 3 : 0))   /* 走路的代谢只比静息高一两成（昆虫步行很省），飞行才贵 */ * (1 + 0.03 * cold) - (ctx.eating ? C.eatRate * dt : 0));
    p.thirst = cl(p.thirst + dt * m / C.thirstTime * (1 + 0.1 * ctx.effort + (ctx.flying ? 1.5 : 0)) * (1 + 0.07 * hot) * (1 + 0.3 * ctx.wind) - (ctx.drinking ? C.drinkRate * dt : 0));
    p.stamina = cl(p.stamina + dt * (ctx.flying ? -C.flyCost : ctx.effort > 0.05 ? -C.walkCost * ctx.effort * ctx.effort * (1 + ctx.uphill) : C.restGain * (1 - 0.6 * Math.max(p.hunger, p.thirst))));
    p.scent = cl(p.scent + dt * (C.scentRate + (ctx.eating ? C.scentEat : 0) - C.scentFade * p.scent - (ctx.resting ? C.groom : 0) - (ctx.raining ? C.rainWash : ctx.wet ? C.wadeWash : 0)));   /* 第一版气味涨得太快、只有歇着和下雨能降 → 恒为 1，六种状态里有一种成了常数。现在：累积减半多、随时间自己消散（−scentFade × 气味，不吃东西时平衡在 ~0.37）、蹚水也能洗掉 */
    let loss = 0, x;
    x = C.starveDamage * Math.max(0, p.hunger - 0.85) / 0.15 * dt; d.starve += x; loss += x;
    x = C.thirstDamage * Math.max(0, p.thirst - 0.85) / 0.15 * dt; d.thirst += x; loss += x;
    x = C.tempDamage * Math.min(3, Math.max(0, Math.abs(p.bodyTemp - genes.tempPref) - C.tempTol) / C.tempSpan) * dt; d.temp += x; loss += x;
    x = (ctx.eating ? C.toxinDamage * ctx.rotten * dt : 0); d.toxin += x; loss += x;
    x = ctx.bites; d.bite += x; loss += x;
    x = p.stamina < 0.05 ? C.exhaustDamage * dt : 0; d.exhaust += x; loss += x;
    x = p.age > C.senescence ? C.senesceDamage * dt : 0; d.age += x; loss += x;
    const regen = (p.hunger < 0.5 && p.thirst < 0.5 && loss === 0) ? C.regen * dt : 0;
    p.health = cl(p.health - loss + regen);
    return D0 - drive(p, genes);
  }
  function causeOfDeath(p) { let best = "age", bv = -1; for (const k in p.dmg) if (p.dmg[k] > bv) { bv = p.dmg[k]; best = k; } return best; }
  const CAUSE = { starve: "饿死", thirst: "渴死", temp: "冷 / 热死", toxin: "吃坏了", bite: "被吃掉", exhaust: "累死", age: "老死" };
  const API = { create, step, drive, causeOfDeath, C, CAUSE }; if (typeof module !== "undefined" && module.exports) module.exports = API; else root.EcoPhysiology = API;
})(typeof window !== "undefined" ? window : globalThis);
