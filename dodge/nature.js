// 大自然：一个按种子确定性生成、没有边界的开放世界（果蝇尺度，单位 mm / s），外加重力与几样物理过程。
// 游戏核心（感觉输入、碰撞、物理）与页面的 3D 渲染共用这一个模块——画出来的石头就是它撞上的石头。
//
// 原则不变：这里只造**世界**。每一样东西都只通过已有的感觉通道进到脑子里：
//   坡度 → 走得慢（身体做功，不是决策）；石头 / 蘑菇柄 / 灌木茎 → 挡路 + 触角被压（TOUCH）；晒烫的石板 → 温度感受器；
//   水洼 / 下雨 → 湿度感受器 + 水味觉；雨声 / 甲虫的嗡嗡声 → 听觉神经元；浆果落地发酵 → 气味（醋 + A / 霉）→ 嗅觉感受神经元，
//   风把气味羽流吹向下风；爬过来的甲虫、头顶掉下来的浆果 → 同一套逼近视觉前端（LC4 / LPLC2）。
// 没有一条「看见甲虫就跑」「闻到果子就过去」的规则。
//
// 物理（全部是真实单位）：重力 9,810 mm/s²；球体落地按地形法线反弹（恢复系数 e）；之后按实心球纯滚动 a = 5/7 · g · sinθ，
//   滚动阻力 Crr · g（松软地面）；低于阈值速度且坡度不够陡就停下。水洼：下雨蓄水、晴天蒸发。石板温度跟着日照走（一阶滞后）。
// **为什么威胁是甲虫而不是飞来的球**：在这个尺度上，60 mm/s 水平速度的抛体 0.1 秒内就落地、滚几毫米就停——「慢慢滚过来的球」不物理。
//   自己会爬的东西才可能以这个速度贴着地面靠近，所以换成沿地形爬行的甲虫；视觉前端对它和对球完全一样（一个逼近的、半径 ballR 的物体）。
// 手选的量（登记在台账 PARAMETERS）：地形起伏的幅度与波长、物件密度、e = 0.35、Crr = 0.15、坡度对步行速度的系数、天气的节奏。
(function (root) {
  const G_MM = 9810, CELL = 40;
  const hash = (ix, iy, k, seed) => { let h = (Math.imul(ix, 374761393) + Math.imul(iy, 668265263) + Math.imul(k, 2246822519) + Math.imul(seed, 3266489917)) | 0; h = Math.imul(h ^ (h >>> 13), 1274126177); return ((h ^ (h >>> 16)) >>> 0) / 4294967296; };
  const fade = t => t * t * t * (t * (t * 6 - 15) + 10);

  function create(seed, opts) {
    seed = (seed | 0) || 1; const o = Object.assign({ amp: [7, 2.2, 0.5], wave: [160, 55, 18], restitution: 0.35, crr: 0.15, restSpeed: 4, slopeK: 1.2 }, opts || {});
    const vnoise = (x, y, k) => { const ix = Math.floor(x), iy = Math.floor(y), fx = fade(x - ix), fy = fade(y - iy);
      const a = hash(ix, iy, k, seed), b = hash(ix + 1, iy, k, seed), c = hash(ix, iy + 1, k, seed), d = hash(ix + 1, iy + 1, k, seed); return (a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy) * 2 - 1; };
    const base = (x, y) => { let h = 0; for (let k = 0; k < o.amp.length; k++) h += o.amp[k] * vnoise(x / o.wave[k] + 17.3 * k, y / o.wave[k] - 9.1 * k, k); return h; };

    // —— 每个 40 mm 的格子里有什么（确定性；缓存）——
    const cache = new Map();
    function cell(ix, iy) {
      const key = ix + "," + iy; let c = cache.get(key); if (c) return c;
      let n = 0; const r = () => hash(ix, iy, 100 + n++, seed), at = () => [(ix + 0.08 + 0.84 * r()) * CELL, (iy + 0.08 + 0.84 * r()) * CELL], items = [];
      const home = Math.abs(ix) <= 0 && Math.abs(iy) <= 0;                 // 出生的那一格不放挡路的东西
      const nRock = home ? 0 : Math.floor(r() * 2.6); for (let k = 0; k < nRock; k++) { const [x, y] = at(), rad = 1.4 + 4.2 * r() * r(); items.push({ kind: "rock", x, y, r: rad, hgt: rad * (0.6 + 0.5 * r()), rot: r() * 6.283, tint: r(), solid: true }); }
      if (r() < 0.22 && !home) { const [x, y] = at(); items.push({ kind: "sunrock", x, y, r: 6 + 5 * r(), rot: r() * 6.283, tint: r(), solid: false, temp: 0 }); }       // 平的深色石板：能走上去，太阳一晒就烫
      if (r() < 0.3 && !home) { const [x, y] = at(), cap = 2 + 2.6 * r(); items.push({ kind: "mushroom", x, y, r: 0.5 + 0.22 * cap, cap, hgt: 5 + 6 * r(), tint: r(), solid: true }); }
      if (r() < 0.3 && !home) { const [x, y] = at(); items.push({ kind: "bush", x, y, r: 1.3, hgt: 15 + 8 * r(), spread: 6 + 3.5 * r(), tint: r(), solid: true, next: 4 + 30 * r() }); }   // 浆果丛：果子熟了会掉
      if (r() < 0.28) { const [x, y] = at(); items.push({ kind: "hollow", x, y, s: 8 + 6 * r(), depth: 1.6 + 1.6 * r(), level: r() < 0.4 ? 0.5 + 0.4 * r() : 0, solid: false }); }     // 洼地：下雨蓄水
      if (r() < 0.55) { const [x, y] = at(); items.push({ kind: "windfall", x, y, r: 4.5 + 2.5 * r(), bad: r() < 0.15, tint: r(), solid: false, eaten: false }); }   // 早先掉在地上、已经在发酵的果子
      const nFl = Math.floor(r() * 3); for (let k = 0; k < nFl; k++) { const [x, y] = at(); items.push({ kind: "flower", x, y, hgt: 7 + 9 * r(), tint: r(), rot: r() * 6.283, solid: false }); }
      const nLf = Math.floor(r() * 3.2); for (let k = 0; k < nLf; k++) { const [x, y] = at(); items.push({ kind: "leaf", x, y, r: 5 + 7 * r(), rot: r() * 6.283, tint: r(), solid: false }); }
      const nGr = 7 + Math.floor(r() * 9); for (let k = 0; k < nGr; k++) { const [x, y] = at(); items.push({ kind: "grass", x, y, n: 4 + Math.floor(r() * 6), hgt: 4.5 + 8 * r(), rot: r() * 6.283, tint: r(), solid: false }); }
      c = { ix, iy, items, hollows: items.filter(i => i.kind === "hollow") }; cache.set(key, c);
      if (cache.size > 900) { const cx = W.focus[0] / CELL, cy = W.focus[1] / CELL; for (const [k2, v] of cache) if (Math.abs(v.ix - cx) > 10 || Math.abs(v.iy - cy) > 10) cache.delete(k2); }
      return c;
    }
    function h(x, y) {
      let z = base(x, y); const ix = Math.floor(x / CELL), iy = Math.floor(y / CELL);
      for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) for (const q of cell(ix + dx, iy + dy).hollows) { const d2 = (x - q.x) ** 2 + (y - q.y) ** 2; if (d2 < 9 * q.s * q.s) z -= q.depth * Math.exp(-d2 / (2 * q.s * q.s)); }
      return z;
    }
    const grad = (x, y) => { const e = 0.4; return [(h(x + e, y) - h(x - e, y)) / (2 * e), (h(x, y + e) - h(x, y - e)) / (2 * e)]; };
    const normal = (x, y) => { const [gx, gy] = grad(x, y), m = Math.hypot(gx, gy, 1); return [-gx / m, -gy / m, 1 / m]; };
    function near(x, y, R, fn) { const x0 = Math.floor((x - R) / CELL), x1 = Math.floor((x + R) / CELL), y0 = Math.floor((y - R) / CELL), y1 = Math.floor((y + R) / CELL);
      for (let ix = x0; ix <= x1; ix++) for (let iy = y0; iy <= y1; iy++) for (const it of cell(ix, iy).items) if (Math.hypot(it.x - x, it.y - y) <= R + (it.r || 0)) fn(it); }

    // —— 物理：一个半径 r 的球体（浆果）。返回 true = 停稳了 ——
    function integrate(b, dt) {
      const gnd = (x, y) => h(x, y) + b.r;
      if (b.z === undefined) { b.z = gnd(b.x, b.y); b.vz = 0; }
      if (b.rolling) {
        const [gx, gy] = grad(b.x, b.y), s2 = 1 + gx * gx + gy * gy, k = (5 / 7) * G_MM / s2; let ax = -k * gx, ay = -k * gy;
        const sp = Math.hypot(b.vx, b.vy), fr = o.crr * G_MM / Math.sqrt(s2);
        if (sp < o.restSpeed && Math.hypot(ax, ay) <= fr) { b.vx = b.vy = 0; b.rest = true; b.z = gnd(b.x, b.y); return true; }     // 静摩擦兜得住：停
        if (sp > 1e-6) { const dv = Math.min(sp, fr * dt); ax -= b.vx / sp * dv / dt; ay -= b.vy / sp * dv / dt; }
        b.vx += ax * dt; b.vy += ay * dt; b.x += b.vx * dt; b.y += b.vy * dt; b.z = gnd(b.x, b.y); b.vz = 0; b.spin = (b.spin || 0) + Math.hypot(b.vx, b.vy) * dt / b.r; return false;
      }
      b.vz -= G_MM * dt; b.x += b.vx * dt; b.y += b.vy * dt; b.z += b.vz * dt;
      const g0 = gnd(b.x, b.y);
      if (b.z <= g0) { b.z = g0; const n = normal(b.x, b.y), vn = b.vx * n[0] + b.vy * n[1] + b.vz * n[2];
        if (vn < 0) { const j = (1 + o.restitution) * vn; b.vx -= j * n[0]; b.vy -= j * n[1]; b.vz -= j * n[2]; b.vx *= 0.8; b.vy *= 0.8; b.bounces = (b.bounces || 0) + 1; }
        if (Math.abs(vn) * o.restitution < 40) { b.rolling = true; b.vz = 0; } }
      return false;
    }

    const W = { seed, CELL, G_MM, o, h, grad, normal, cell, near, integrate, focus: [0, 0],
      weather: { rain: 0, rainT: 0, nextRain: 90 + 120 * hash(1, 2, 3, seed), wet: 0 }, heatFields: new Map(), waterOf: new Map(), fallenOf: new Map(), beetleT: 20, clock: 0,
      // 步行：沿行进方向的坡度让它慢下来 / 快起来（身体做功）
      slopeFactor(x, y, heading, dir) { const [gx, gy] = grad(x, y), along = (gx * Math.cos(heading) + gy * Math.sin(heading)) * (dir < 0 ? -1 : 1); return Math.max(0.45, Math.min(1.25, 1 - o.slopeK * along)); },
      // 挡路：把圆心推到所有实心物件之外；返回是否碰到
      collide(p, rad) { let hit = false; near(p.x, p.y, rad + 8, it => { if (!it.solid) return; const dx = p.x - it.x, dy = p.y - it.y, d = Math.hypot(dx, dy) || 1e-6, need = it.r + rad; if (d < need) { p.x = it.x + dx / d * need; p.y = it.y + dy / d * need; hit = true; } }); return hit; },
      // 触角尖压进实心物件多深（mm）
      press(ax, ay) { let m = 0; near(ax, ay, 8, it => { if (it.solid) m = Math.max(m, it.r - Math.hypot(ax - it.x, ay - it.y)); }); return Math.max(0, m); },
      // 气味羽流被风吹歪：下风方向拉长、上风方向压短，中心略向下风漂
      plume(odor, wind, x, y) { const sp = wind ? wind.speed : 0, c = Math.cos(wind ? wind.dir : 0), s = Math.sin(wind ? wind.dir : 0), dx = x - odor.x, dy = y - odor.y, par = dx * c + dy * s, perp = -dx * s + dy * c;
        const sPar = odor.sigma * (par > 0 ? 1 + 2.2 * sp : Math.max(0.35, 1 - 0.6 * sp)), sPerp = odor.sigma * (1 - 0.25 * sp); return odor.strength * Math.exp(-(par * par) / (2 * sPar * sPar) - (perp * perp) / (2 * sPerp * sPerp)); },
    };

    // —— 世界自己运转（每个物理步调用一次）。G = game_core 的游戏对象，rand = 它的随机数 ——
    W.step = function (dt, G, rand) {
      const S = G.S, CFG = G.CFG, wx = W.weather; W.focus = [S.x, S.y]; W.clock += dt;
      // 天气：隔一阵下一场雨
      wx.nextRain -= dt; if (wx.nextRain <= 0 && wx.rainT <= 0) { wx.rainT = 25 + 30 * rand(); wx.nextRain = 150 + 200 * rand(); G.onEvent && G.onEvent("rain", { on: true }); }
      if (wx.rainT > 0) { wx.rainT -= dt; wx.rain += (1 - wx.rain) * Math.min(1, dt / 3); if (wx.rainT <= 0) G.onEvent && G.onEvent("rain", { on: false }); } else wx.rain += (0 - wx.rain) * Math.min(1, dt / 6);
      wx.wet += ((wx.rain > 0.3 ? 1 : 0) - wx.wet) * Math.min(1, dt / (wx.rain > 0.3 ? 8 : 60 / (0.3 + CFG.light)));    // 地面湿度：雨里很快湿透，晴天慢慢干
      G.ambient = { sound: 0.55 * wx.rain, hygro: 0.7 * wx.wet, lightMul: 1 - 0.45 * wx.rain };
      if (wx.rain > 0.5 && G.wind) G.wind.speed = Math.min(1, G.wind.speed + 0.2 * dt);
      // 雨点砸到它：频率 = 雨强 × 它的截面（手选 0.12 次 / 秒 @ 满雨强）；一滴水有它体重的几十倍，砸中就是一次踉跄
      if (wx.rain > 0.2 && S.z <= 0.01 && rand() < 0.12 * wx.rain * dt) { const a = rand() * 6.283; S.x += Math.cos(a) * 0.8; S.y += Math.sin(a) * 0.8; S.hitFlash = 0.3; G.score.rainHits = (G.score.rainHits || 0) + 1; G.onEvent && G.onEvent("raindrop", {}); }
      // 附近的东西：石板的温度、洼地的水、浆果丛
      const seenHeat = new Set(), seenWater = new Set();
      near(S.x, S.y, 120, it => {
        if (it.kind === "sunrock") { const target = Math.max(0, (CFG.light - 0.45) / 0.55) * (1 - 0.8 * wx.rain); it.temp += (target - it.temp) * Math.min(1, dt / 20);      // 石板升温 / 降温的时间常数 20 s
          if (it.temp > 0.08) { seenHeat.add(it); let f = W.heatFields.get(it); if (!f) { f = G.addField("heat", it.x, it.y, it.r * 1.1, 0); W.heatFields.set(it, f); } f.strength = 1.4 * it.temp; } }
        else if (it.kind === "hollow") { it.level = Math.max(0, Math.min(1, it.level + (0.05 * wx.rain - 0.0025 * CFG.light * (1 - wx.rain)) * dt));
          if (it.level > 0.15) { seenWater.add(it); let w = W.waterOf.get(it); if (!w || !G.pellets.includes(w.p)) { const p = G.addPellet(it.x, it.y, "water"); p.amount = 1e6; p.hollow = it; const f = G.addField("damp", it.x, it.y, it.s * 1.6, 0.8); w = { p, f }; W.waterOf.set(it, w); } w.p.r = it.s * (0.35 + 0.75 * it.level); w.f.strength = 0.4 + 0.5 * it.level; } }
        else if (it.kind === "windfall" && !it.eaten) { let p = W.fallenOf.get(it);
          if (!p) { p = G.addPellet(it.x, it.y, it.bad ? "bitter" : "sugar"); p.r = it.r; p.amount = CFG.lifeFoodAmount; p.berry = true; p.windfall = it; W.fallenOf.set(it, p);
            G.addOdor(it.x, it.y, it.bad ? "geosmin" : "vinegar", 24, 1, 1e9).pellet = p; if (G.MB && !it.bad) G.addOdor(it.x, it.y, "A", 24, 1, 1e9).pellet = p; }
          else if (!G.pellets.includes(p)) { it.eaten = true; W.fallenOf.delete(it); } }                       // 吃完了就没了（这一格不会再长出来）
        else if (it.kind === "bush" && Math.hypot(it.x - S.x, it.y - S.y) < 95) { it.next -= dt * (0.4 + 0.8 * CFG.light);
          if (it.next <= 0) { it.next = 18 + 40 * rand(); const a = rand() * 6.283, d = it.spread * (0.3 + 0.7 * rand()), bad = rand() < 0.2;          // 一颗浆果熟了，从枝头掉下来
            const b = { id: G.nextId++, kind: "berry", bad, r: 2.2 + 0.8 * rand(), x: it.x + Math.cos(a) * d, y: it.y + Math.sin(a) * d, vx: (rand() - 0.5) * 30, vy: (rand() - 0.5) * 30, vz: 0, prevTheta: null, minD: Infinity, done: false, age: 0, outcome: null, physical: true };
            b.z = h(b.x, b.y) + it.hgt * (0.55 + 0.4 * rand()); G.balls.push(b); G.onEvent && G.onEvent("launch", b); } }
      });
      for (const [it, f] of W.heatFields) if (!seenHeat.has(it)) { const k = G.fields.indexOf(f); if (k >= 0) { G.fields.splice(k, 1); G.onEvent && G.onEvent("removeField", f); } W.heatFields.delete(it); }
      for (const [it, w] of W.waterOf) if (!seenWater.has(it)) { let k = G.pellets.indexOf(w.p); if (k >= 0) { G.pellets.splice(k, 1); G.onEvent && G.onEvent("removePellet", w.p); } k = G.fields.indexOf(w.f); if (k >= 0) { G.fields.splice(k, 1); G.onEvent && G.onEvent("removeField", w.f); } W.waterOf.delete(it); }
      // 浆果落地停稳 → 变成一块会发酵的果肉（食物 + 气味）；坏的发霉
      for (let i = G.balls.length - 1; i >= 0; i--) { const b = G.balls[i]; if (b.kind !== "berry" || !b.rest) continue;
        const p = G.addPellet(b.x, b.y, b.bad ? "bitter" : "sugar"); p.r = b.r * 2.2; p.amount = CFG.lifeFoodAmount; p.berry = true;
        G.addOdor(b.x, b.y, b.bad ? "geosmin" : "vinegar", 24, 1, 120).pellet = p; if (G.MB && !b.bad) G.addOdor(b.x, b.y, "A", 24, 1, 120).pellet = p;
        G.onEvent && G.onEvent("remove", b); G.balls.splice(i, 1); }
      if (G.pellets.length > 40) { const k = G.pellets.findIndex(p => !p.hollow && !p.windfall); if (k >= 0) { const p = G.pellets.splice(k, 1)[0]; G.onEvent && G.onEvent("removePellet", p); } }
      // 走远了的东西回收
      const far = q => Math.hypot(q.x - S.x, q.y - S.y) > CFG.lifeCull;
      for (const p of G.pellets.filter(q => !q.hollow && far(q))) { G.pellets.splice(G.pellets.indexOf(p), 1); if (p.windfall) W.fallenOf.delete(p.windfall); G.onEvent && G.onEvent("removePellet", p); }   // 走远了先收起来；地上那颗还在，走回来会再出现
      // 甲虫：隔一阵有一只从远处朝它爬过来（沿地形，自己会动，所以能以 ballSpeed 贴地靠近）；嗡嗡的振翅声先到
      W.beetleT -= dt; if (W.beetleT <= 0) { W.beetleT = CFG.lifeBall[0] + rand() * (CFG.lifeBall[1] - CFG.lifeBall[0]); const a = S.h + (rand() * 2 - 1) * Math.PI * 0.8, fx = S.x + Math.cos(a) * CFG.autoDist, fy = S.y + Math.sin(a) * CFG.autoDist;
        const b = G.launch(fx, fy); b.kind = "beetle"; G.addSound(fx, fy, 1.2, 0.5); }
      // 偶尔远处有别的虫子飞过（只有声音）
      if (rand() < dt / 35) { const a = rand() * 6.283, d = 30 + rand() * 60; G.addSound(S.x + Math.cos(a) * d, S.y + Math.sin(a) * d, 0.5 + rand() * 0.8, 0.5 + rand() * 0.7); }
    };
    return W;
  }
  const API = { create, G_MM, CELL };
  if (typeof module !== "undefined" && module.exports) module.exports = API; else root.FlyNature = API;
})(typeof window !== "undefined" ? window : globalThis);
