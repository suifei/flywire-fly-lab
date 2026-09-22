// 生态箱：感觉。把世界里的**物理量**换算成 27 路感觉神经元的发放率（与 dodge/game_core.js 同一套换算：场强 1.0 = 200 Hz；逼近 = Ache 2019 的形式）。
// 这里不做任何判断——不写「饿了就去找吃的」。食物只是一团醋味 + 碰到时的甜味；水只是湿度 + 碰到时的水味；危险只是一个变大的黑影 + 一种气味。
(function (root) {
  const CH = (typeof module !== "undefined" && module.exports) ? require("./channels.js") : root.EcoChannels, WK = ((typeof module !== "undefined" && module.exports) ? require("./world.js") : root.EcoWorld).K;
  const IX = Object.fromEntries(CH.INPUTS.map((c, i) => [c, i])), RATE = 200, ANT_A = 0.61, ANT_L = 1.6, FLY_R = 1.2, sm = new Float64Array(3), sm2 = new Float64Array(2);
  const loomLP = (thetaDeg) => 200 * Math.exp(-((thetaDeg - 42) ** 2) / (2 * 15 * 15));
  function sense(W, a, agents, x) {
    x.fill(0); const R = W.rules.size, cl = v => v < 0 ? 0 : v > 1 ? 1 : v;
    const snd = W.sound(a, agents, sm2);
    for (let s = 0; s < 2; s++) { const ang = a.h + (s === 0 ? ANT_A : -ANT_A), ax = a.x + Math.cos(ang) * ANT_L, ay = a.y + Math.sin(ang) * ANT_L, sd = s === 0 ? "_L" : "_R";
      W.smell(ax, ay, sm); x[IX["vinegar" + sd]] = RATE * cl(sm[0]); x[IX["geosmin" + sd]] = RATE * cl(sm[1]); x[IX["odorA" + sd]] = RATE * cl(sm[2]);
      x[IX["hygro" + sd]] = RATE * cl(W.humidity(ax, ay)); x[IX["thermo" + sd]] = RATE * cl(W.heat(ax, ay)); x[IX["audio" + sd]] = RATE * cl(snd[s]);
      const over = Math.hypot(ax, ay) - R; if (over > 0) x[IX["touch" + sd]] = RATE * cl(over / ANT_L); }
    // 风：与 game_core 同式——120 Hz × 风速(0–1) × (0.35 + 0.65 × 迎风分量)，两根触角在体轴 ±35°
    { const wf = W.wind.speed / WK.windMax, rel = ang => 0.35 + 0.65 * Math.max(0, Math.cos(W.wind.dir + Math.PI - (a.h + ang))); x[IX.jo_L] = Math.min(RATE, 120 * wf * rel(ANT_A)); x[IX.jo_R] = Math.min(RATE, 120 * wf * rel(-ANT_A)); }
    // 逼近的东西：与 game_core 同式——θ = 2·atan(r/d)，只对正在变大的反应；LC4 = 0.5 × 角速度，LPLC2 = 角大小的高斯(42°, 15°)，LC16 = 0.5 × 角速度；方位 > −15° 记左、< 15° 记右（正前方两侧都记）；多个物体相加；光照增益 0.35 + 0.65 × 光
    const gain = 0.35 + 0.65 * Math.max(0, Math.min(1, W.light())); let k = 0, l4L = 0, l4R = 0, lpL = 0, lpR = 0;
    const loom = (ox, oy, r) => { const dx = ox - a.x, dy = oy - a.y, d = Math.max(r + 0.01, Math.hypot(dx, dy)), theta = 2 * Math.atan(r / d), prev = a.lastD[k]; a.lastD[k] = theta; k++; if (prev === undefined || prev === null) return; const dth = (theta - prev) / a.dt; if (dth <= 0 || theta < 0.05) return;
      let b = Math.atan2(dy, dx) - a.h; b = Math.atan2(Math.sin(b), Math.cos(b)) * 57.2958; const vel = dth * 57.2958, l4 = 0.5 * vel * gain, lp = loomLP(theta * 57.2958) * gain; if (b > -15) { l4L += l4; lpL += lp; } if (b < 15) { l4R += l4; lpR += lp; }
      if (l4 + lp > a.threatLP) { a.threatLP = l4 + lp; a.threatDir = Math.atan2(dy, dx); } };
    a.threatLP = 0; for (const p of W.predators) loom(p.x, p.y, WK.predR); if (agents.length > 1) for (const o of agents) if (o !== a && o.alive && Math.hypot(o.x - a.x, o.y - a.y) < 40) loom(o.x, o.y, FLY_R); else k++;
    x[IX.lc4_L] = Math.min(RATE, l4L); x[IX.lc4_R] = Math.min(RATE, l4R); x[IX.lplc2_L] = Math.min(RATE, lpL); x[IX.lplc2_R] = Math.min(RATE, lpR); x[IX.lc16_L] = Math.min(RATE, l4L); x[IX.lc16_R] = Math.min(RATE, l4R);
    // 被咬 = 一次很重的机械接触：送进刚毛触觉通道（哪一侧由甲虫的方位定）
    if (a.bite) { let b = Math.atan2(a.bite.y - a.y, a.bite.x - a.x) - a.h; const s = Math.sin(b); x[IX.touch_L] = Math.max(x[IX.touch_L], RATE * cl(0.5 + s)); x[IX.touch_R] = Math.max(x[IX.touch_R], RATE * cl(0.5 - s)); }
    // 味觉：腿 / 喙碰到才有
    a.onFood = a.air > 0 ? null : W.foodAt(a.x, a.y); a.onWater = a.air > 0 ? null : W.waterAt(a.x, a.y);
    if (a.onFood) { const rot = W.isRotten(a.onFood) ? 1 : 0; a.rotten = rot; if (rot) x[IX.bitter] = RATE; else x[IX.sugar] = RATE; } else a.rotten = 0;   /* 同 game_core：好的果子只有甜、烂的只有苦 */
    if (a.onWater) x[IX.water] = RATE;
    return x;
  }
  const API = { sense, IX }; if (typeof module !== "undefined" && module.exports) module.exports = API; else root.EcoSenses = API;
})(typeof window !== "undefined" ? window : globalThis);
