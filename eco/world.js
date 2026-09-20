// 生态箱：世界。一个圆形的玻璃箱（半径 rules.size mm），里面有地形、食物（会烂）、水洼（会干）、昼夜冷热、晒热的石头、荫凉、风、雨、捕食者。
// **玩家只能改 RULES 里的这些量**；奖励函数不在这里，也不对玩家开放（见 eco/physiology.js）。
// 全部状态都是普通对象 + 一个 32 位随机数状态，可以原样存成 JSON 再读回来接着跑（M4 的逐位复现靠这个）。
(function (root) {
  const RULES = {            // 玩家可调的世界规则（默认 = 「温和」）。每一项的含义与范围见 META
    size: 140, food: 10, foodRegrow: 45, rot: 1, water: 3, evaporation: 1, rain: 1, dayLength: 240, tempDay: 28, tempNight: 18,
    wind: 0.4, predators: 1, predatorSpeed: 6, roughness: 1, sunrocks: 3, shade: 3 };
  const META = { size: ["箱子半径 mm", 80, 300], food: ["同时存在的食物数", 0, 40], foodRegrow: ["吃完 / 烂掉后多久再长出来 s", 5, 300], rot: ["腐烂速度倍率", 0, 5], water: ["水洼数", 0, 12], evaporation: ["蒸发速度倍率", 0, 5],
    rain: ["下雨频率倍率", 0, 4], dayLength: ["一昼夜 s", 60, 1200], tempDay: ["白天气温 ℃", 10, 42], tempNight: ["夜里气温 ℃", 0, 35], wind: ["风 0–1", 0, 1], predators: ["捕食者数", 0, 8], predatorSpeed: ["捕食者速度 mm/s", 3, 25],
    roughness: ["地形起伏倍率", 0, 3], sunrocks: ["晒热的石头数", 0, 10], shade: ["荫凉数", 0, 10] };
  // 世界的物理常数（手选；不对玩家开放，登记在 docs/ecobox 里）
  const K = { foodSigma: 28, foodReach: 6, rotAge: 260, goneAge: 420, waterSigma: 24, rockSigma: 16, rockHeat: 10, rockTau: 50, shadeSigma: 20, shadeCool: 5, puddleCool: 2, windMax: 30, plumeStretch: 1.6,
    predR: 3.5, biteReach: 3.0, biteDamage: 0.12, biteCooldown: 3.0, predDetect: 22, predScent: 55, predOdorSigma: 18, chaseMax: 8, chaseRest: 12, rainEvery: 300, rainLen: 35 };
  const fade = t => t * t * (3 - 2 * t);
  function hash(ix, iy, k, seed) { let h = (ix * 374761393 + iy * 668265263 + k * 1274126177 + seed * 2246822519) | 0; h = Math.imul(h ^ (h >>> 13), 1274126177); h ^= h >>> 16; return (h >>> 0) / 4294967296; }

  function create(rules, seed) {
    const W = { rules: Object.assign({}, RULES, rules || {}), seed: (seed >>> 0) || 1, rs: ((seed >>> 0) || 1) ^ 0x9e3779b9, t: 0, food: [], water: [], rocks: [], shade: [], predators: [], pendingFood: [],
      wind: { dir: 0, speed: 0 }, rain: 0, rainLeft: 0, nextRain: 0, stats: { eaten: 0, rotted: 0, bites: 0 } };
    attach(W); const r = W.rules, R = r.size;
    W.wind.dir = W.rand() * 6.2832; W.nextRain = r.rain > 0 ? K.rainEvery / r.rain * (0.5 + W.rand()) : 1e18;   /* 不用 Infinity：存档要过 JSON */
    const spot = (margin) => { const a = W.rand() * 6.2832, d = Math.sqrt(W.rand()) * (R - margin); return [Math.cos(a) * d, Math.sin(a) * d]; };
    for (let i = 0; i < r.water; i++) { const [x, y] = spot(25); W.water.push({ x, y, r: 9 + 6 * W.rand(), level: 0.7 + 0.3 * W.rand() }); }
    for (let i = 0; i < r.sunrocks; i++) { const [x, y] = spot(20); W.rocks.push({ x, y, heat: 0 }); }
    for (let i = 0; i < r.shade; i++) { const [x, y] = spot(20); W.shade.push({ x, y }); }
    for (let i = 0; i < r.food; i++) W.food.push(W.newFood(true));
    for (let i = 0; i < r.predators; i++) { const [x, y] = spot(15); W.predators.push({ x, y, h: W.rand() * 6.2832, cool: 0, target: -1, chase: 0, rest: 0 }); }
    return W;
  }

  // 方法单独挂（存档里只有数据；读回来再 attach 一次）
  function attach(W) {
    const r = W.rules, R = r.size, seed = W.seed;
    W.rand = () => { W.rs = (W.rs + 0x6d2b79f5) >>> 0; let t = W.rs; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
    const vnoise = (x, y, k) => { const ix = Math.floor(x), iy = Math.floor(y), fx = fade(x - ix), fy = fade(y - iy), a = hash(ix, iy, k, seed), b = hash(ix + 1, iy, k, seed), c = hash(ix, iy + 1, k, seed), d = hash(ix + 1, iy + 1, k, seed);
      return (a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy) * 2 - 1; };
    W.height = (x, y) => r.roughness * (6 * vnoise(x / 90 + 3.7, y / 90 - 1.3, 1) + 2 * vnoise(x / 32 - 8.1, y / 32 + 4.4, 2));
    W.grad = (x, y) => { const e = 1.5; return [(W.height(x + e, y) - W.height(x - e, y)) / (2 * e), (W.height(x, y + e) - W.height(x, y - e)) / (2 * e)]; };
    W.phase = () => (W.t / r.dayLength) % 1;                                     // 0 = 日出，0.25 = 正午，0.5 = 日落
    W.sun = () => Math.max(0, Math.sin(W.phase() * 6.2832)) * (W.rain > 0 ? 0.35 : 1);
    W.light = () => Math.min(1, 0.12 + 1.6 * W.sun());                        /* 夜里有月光：看得见，但逼近信号只剩一成多 */
    W.ambient = () => (r.tempDay + r.tempNight) / 2 + (r.tempDay - r.tempNight) / 2 * Math.sin((W.phase() - 0.06) * 6.2832) - (W.rain > 0 ? 2 : 0);
    const g2 = (dx, dy, s) => Math.exp(-(dx * dx + dy * dy) / (2 * s * s));
    W.temp = (x, y) => { let T = W.ambient(); const sun = W.sun(); for (const k of W.rocks) T += k.heat * g2(x - k.x, y - k.y, K.rockSigma); if (sun > 0) for (const s of W.shade) T -= K.shadeCool * sun * g2(x - s.x, y - s.y, K.shadeSigma);
      for (const p of W.water) if (p.level > 0.05) T -= K.puddleCool * g2(x - p.x, y - p.y, p.r); return T; };
    // 气味羽流：顺风一侧被拉长、逆风一侧被压短
    const plume = (px, py, sx, sy, sigma) => { const dx = px - sx, dy = py - sy, wf = W.wind.speed / K.windMax, wx = Math.cos(W.wind.dir), wy = Math.sin(W.wind.dir), a = dx * wx + dy * wy, c = -dx * wy + dy * wx,
      sa = a > 0 ? sigma * (1 + K.plumeStretch * wf) : sigma / (1 + 0.6 * wf); return Math.exp(-(a * a) / (2 * sa * sa) - (c * c) / (2 * sigma * sigma)); };
    W.smell = (x, y, out) => { let v = 0, g = 0, b = 0; for (const f of W.food) { const c = plume(x, y, f.x, f.y, K.foodSigma) * Math.min(1, f.amount * 2); const rot = f.age > K.rotAge ? 1 : 0; v += c * (rot ? 0.35 : 1); g += c * rot; }
      for (const p of W.predators) b += plume(x, y, p.x, p.y, K.predOdorSigma); out[0] = v; out[1] = g; out[2] = b; return out; };
    W.humidity = (x, y) => { if (W.rain > 0) return 1; let h = 0; for (const p of W.water) if (p.level > 0.05) h += Math.sqrt(p.level) * g2(x - p.x, y - p.y, p.r + K.waterSigma); return Math.min(1, h); };
    W.foodAt = (x, y) => { let best = null, bd = 1e9; for (const f of W.food) { const d = Math.hypot(f.x - x, f.y - y); if (d < K.foodReach && d < bd && f.amount > 0) { best = f; bd = d; } } return best; };
    W.waterAt = (x, y) => { if (W.rain > 0.5) return RAINWATER; for (const p of W.water) if (p.level > 0.05 && Math.hypot(p.x - x, p.y - y) < p.r * Math.sqrt(p.level)) return p; return null; };
    const RAINWATER = { rainwater: true, level: 1 };
    W.newFood = (initial) => { const a = W.rand() * 6.2832, d = Math.sqrt(W.rand()) * (R - 15); return { x: Math.cos(a) * d, y: Math.sin(a) * d, amount: 0.6 + 0.4 * W.rand(), age: initial ? W.rand() * K.rotAge * 0.6 : 0 }; };
    W.isRotten = f => f.age > K.rotAge;

    W.step = function (dt, agents) {
      W.t += dt;
      // 风：方向慢慢漂，强弱有阵性
      W.wind.dir += (W.rand() - 0.5) * 0.25 * dt; W.wind.speed = r.wind * K.windMax * (0.55 + 0.45 * Math.sin(W.t / 37 + 1.3) * Math.sin(W.t / 11));
      // 雨
      if (W.rainLeft > 0) { W.rainLeft -= dt; W.rain = 1; if (W.rainLeft <= 0) { W.rain = 0; W.nextRain = W.t + K.rainEvery / Math.max(0.05, r.rain) * (0.5 + W.rand()); } } else if (W.t >= W.nextRain && r.rain > 0) { W.rainLeft = K.rainLen * (0.6 + 0.8 * W.rand()); W.rain = 1; }
      // 水洼：蒸发（越热越快）、下雨补满
      const amb = W.ambient(); for (const p of W.water) { p.level += dt * (W.rain > 0 ? 0.02 : -0.00045 * r.evaporation * (1 + Math.max(0, amb - 20) / 8)); p.level = Math.max(0, Math.min(1, p.level)); }
      // 石头：白天晒热，夜里慢慢放热
      const sun = W.sun(); for (const k of W.rocks) k.heat += dt * (K.rockHeat * sun - k.heat) / K.rockTau;
      // 食物：变老、烂掉、消失、过一阵在别处长出来
      for (let i = W.food.length - 1; i >= 0; i--) { const f = W.food[i]; f.age += dt * r.rot; if (f.amount <= 0 || f.age > K.goneAge) { if (f.amount > 0) W.stats.rotted++; W.food.splice(i, 1); W.pendingFood.push(W.t + r.foodRegrow * (0.5 + W.rand())); } }
      for (let i = W.pendingFood.length - 1; i >= 0; i--) if (W.t >= W.pendingFood[i] && W.food.length < r.food) { W.pendingFood.splice(i, 1); W.food.push(W.newFood(false)); }
      while (W.food.length + W.pendingFood.length < r.food) W.pendingFood.push(W.t + r.foodRegrow * W.rand());
      // 捕食者（地面甲虫）：闲逛；闻到 / 看到果蝇就追；够得着就咬。飞在空中的咬不到。越脏（气味越重）越容易被盯上；夜里更活跃
      const night = W.sun() <= 0; const bites = [];
      for (const p of W.predators) { p.cool = Math.max(0, p.cool - dt); p.rest = Math.max(0, p.rest - dt); let tgt = null, td = 1e9;
        if (p.rest === 0) for (const a of agents) { if (!a.alive || a.air > 0) continue; const d = Math.hypot(a.x - p.x, a.y - p.y), reach = K.predDetect + K.predScent * a.phys.scent; if (d < reach && d < td) { tgt = a; td = d; } }
        const sp = r.predatorSpeed * (night ? 1.25 : 1) * (tgt ? 1 : 0.45) * (p.cool > 0.3 ? 0.1 : 1);   /* 咬了一口之后要停下来嚼一会儿（3 s），被咬的有机会跑 */
        if (tgt) { const want = Math.atan2(tgt.y - p.y, tgt.x - p.x); let dh = want - p.h; dh = Math.atan2(Math.sin(dh), Math.cos(dh)); p.h += Math.max(-3 * dt, Math.min(3 * dt, dh)); p.target = tgt.id; p.chase += dt; if (p.chase > K.chaseMax) { p.chase = 0; p.rest = K.chaseRest; }   /* 追不上就歇一阵 */
          if (td < K.biteReach && p.cool === 0) { p.cool = K.biteCooldown; bites.push({ agent: tgt, x: p.x, y: p.y }); W.stats.bites++; } } else { p.h += (W.rand() - 0.5) * 1.6 * dt; p.target = -1; p.chase = Math.max(0, p.chase - dt); }
        p.x += Math.cos(p.h) * sp * dt; p.y += Math.sin(p.h) * sp * dt; const d = Math.hypot(p.x, p.y); if (d > R - 4) { p.x *= (R - 4) / d; p.y *= (R - 4) / d; p.h = Math.atan2(-p.y, -p.x) + (W.rand() - 0.5); } }
      return bites;
    };
    return W;
  }
  // 玩家中途改规则（「改环境继续逼它」）：原地改 W.rules，把水洼 / 石头 / 荫凉 / 甲虫的个数补齐或裁掉，再重新挂一次方法（箱子半径是闭包里的常数）。用 W.rand，所以仍然可复现
  function applyRules(W, patch) { const r = W.rules; for (const k in patch) if (k in META) r[k] = Math.max(META[k][1], Math.min(META[k][2], +patch[k])); for (const k of ["food", "water", "predators", "sunrocks", "shade"]) r[k] = Math.round(r[k]); attach(W);
    const R = r.size, spot = m => { const a = W.rand() * 6.2832, d = Math.sqrt(W.rand()) * Math.max(10, R - m); return [Math.cos(a) * d, Math.sin(a) * d]; }, fit = (arr, n, make) => { while (arr.length > n) arr.pop(); while (arr.length < n) arr.push(make()); };
    fit(W.water, r.water, () => { const [x, y] = spot(25); return { x, y, r: 9 + 6 * W.rand(), level: 0.8 }; }); fit(W.rocks, r.sunrocks, () => { const [x, y] = spot(20); return { x, y, heat: 0 }; }); fit(W.shade, r.shade, () => { const [x, y] = spot(20); return { x, y }; });
    fit(W.predators, r.predators, () => { const [x, y] = spot(15); return { x, y, h: W.rand() * 6.2832, cool: 0, target: -1, chase: 0, rest: 0 }; }); while (W.food.length > r.food) W.food.pop(); W.pendingFood.length = Math.min(W.pendingFood.length, Math.max(0, r.food - W.food.length));
    if (W.nextRain > 1e17 && r.rain > 0) W.nextRain = W.t + K.rainEvery / r.rain * (0.5 + W.rand()); if (r.rain <= 0) W.nextRain = 1e18;
    for (const list of [W.food, W.water, W.rocks, W.shade, W.predators]) for (const o of list) { const d = Math.hypot(o.x, o.y); if (d > R - 6) { o.x *= (R - 6) / d; o.y *= (R - 6) / d; } } return W; }
  const PRESETS = { mild: ["温和", {}], drought: ["干旱", { water: 1, evaporation: 2.5, rain: 0.3 }], beetles: ["甲虫横行", { predators: 8, predatorSpeed: 10, size: 200, food: 30, water: 6 }], coldnight: ["寒夜", { tempNight: 6, tempDay: 24, sunrocks: 5 }],
    sparse: ["地广物稀", { size: 300, food: 14, water: 3, predators: 0 }], feast: ["丰饶", { food: 30, water: 6, predators: 0, rot: 0.5 }] };
  const API = { create, attach, applyRules, RULES, META, K, PRESETS }; if (typeof module !== "undefined" && module.exports) module.exports = API; else root.EcoWorld = API;
})(typeof window !== "undefined" ? window : globalThis);
