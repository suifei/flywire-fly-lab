// 生态箱：感觉。把世界里的**物理量**换算成 27 路感觉神经元的发放率（与 dodge/game_core.js 同一套换算：场强 1.0 = 200 Hz；逼近 = Ache 2019 的形式）。
// 这里不做任何判断——不写「饿了就去找吃的」。食物只是一团醋味 + 碰到时的甜味；水只是湿度 + 碰到时的水味；危险只是一个变大的黑影 + 一种气味。
(function (root) {
  const CH = (typeof module !== "undefined" && module.exports) ? require("./channels.js") : root.EcoChannels, WK = ((typeof module !== "undefined" && module.exports) ? require("./world.js") : root.EcoWorld).K;
  const IX = Object.fromEntries(CH.INPUTS.map((c, i) => [c, i])), RATE = 200, ANT_A = 0.61, ANT_L = 1.6, FLY_R = 1.2, sm = new Float64Array(3);
  const loomLP = (thetaDeg) => 200 * Math.exp(-((thetaDeg - 42) ** 2) / (2 * 15 * 15));
  function sense(W, a, agents, x) {
    x.fill(0); const R = W.rules.size, cl = v => v < 0 ? 0 : v > 1 ? 1 : v;
    for (let s = 0; s < 2; s++) { const ang = a.h + (s === 0 ? ANT_A : -ANT_A), ax = a.x + Math.cos(ang) * ANT_L, ay = a.y + Math.sin(ang) * ANT_L, sd = s === 0 ? "_L" : "_R";
      W.smell(ax, ay, sm); x[IX["vinegar" + sd]] = RATE * cl(sm[0]); x[IX["geosmin" + sd]] = RATE * cl(sm[1]); x[IX["odorA" + sd]] = RATE * cl(sm[2]);   /* 捕食者的气味用先天上没有意义的「气味 A」（§48：A 不驱动任何运动输出；B 会先天左转）——它是一条得靠学的线索 */
      x[IX["hygro" + sd]] = RATE * W.humidity(ax, ay); x[IX["thermo" + sd]] = RATE * cl((W.temp(ax, ay) - 22) / 16);
      const over = Math.hypot(ax, ay) - R; if (over > 0) x[IX["touch" + sd]] = RATE * cl(over / ANT_L); }
    // 风：吹在哪一侧的触角上（约翰斯顿器）。rel = 风的来向相对体轴的角度，左为正
    { const wf = W.wind.speed / WK.windMax, rel = W.wind.dir + Math.PI - a.h, s = Math.sin(rel); x[IX.jo_L] = RATE * wf * cl(0.35 + 0.65 * s); x[IX.jo_R] = RATE * wf * cl(0.35 - 0.65 * s); }
    // 逼近的东西：捕食者（以及别的果蝇）。角大小 θ、角速度 dθ/dt 由真实距离变化算；暗处看不见
    const light = W.light(); let k = 0;
    const loom = (ox, oy, r) => { const dx = ox - a.x, dy = oy - a.y, d = Math.max(0.5, Math.hypot(dx, dy)), prev = a.lastD[k]; a.lastD[k] = d; k++; if (d > 90 || prev === undefined || prev <= 0) return;
      let b = Math.atan2(dy, dx) - a.h; b = Math.atan2(Math.sin(b), Math.cos(b)); if (Math.abs(b) > 2.8) return; const closing = (prev - d) / a.dt; if (closing <= 0) return;
      const theta = 2 * Math.atan(r / d) * 57.2958, vel = 2 * r * closing / (d * d + r * r) * 57.2958, l4 = Math.min(200, 0.5 * vel) * light, lp = loomLP(theta) * light, wl = b > 0.26 ? 1 : b < -0.26 ? 0 : 0.5, wr = 1 - wl;
      x[IX.lc4_L] = Math.max(x[IX.lc4_L], l4 * (wl > 0 ? 1 : 0)); x[IX.lc4_R] = Math.max(x[IX.lc4_R], l4 * (wr > 0 ? 1 : 0)); x[IX.lplc2_L] = Math.max(x[IX.lplc2_L], lp * (wl > 0 ? 1 : 0)); x[IX.lplc2_R] = Math.max(x[IX.lplc2_R], lp * (wr > 0 ? 1 : 0));
      if (Math.abs(b) < 0.8) { x[IX.lc16_L] = Math.max(x[IX.lc16_L], l4); x[IX.lc16_R] = Math.max(x[IX.lc16_R], l4); }
      if (lp > a.threatLP) { a.threatLP = lp; a.threatDir = Math.atan2(dy, dx); } };
    a.threatLP = 0; for (const p of W.predators) loom(p.x, p.y, WK.predR);
    // 别的果蝇：翅膀的声音（近了才听得见），也是一个会变大的小黑影
    if (agents.length > 1) for (const o of agents) { if (o === a || !o.alive) continue; const dx = o.x - a.x, dy = o.y - a.y, d = Math.hypot(dx, dy); if (d > 40) continue; let b = Math.atan2(dy, dx) - a.h; const s = Math.sin(b), v = RATE * Math.exp(-d / 10);
      x[IX.audio_L] = Math.max(x[IX.audio_L], v * cl(0.5 + 0.5 * s)); x[IX.audio_R] = Math.max(x[IX.audio_R], v * cl(0.5 - 0.5 * s)); }
    // 被咬 = 一次很重的机械接触：送进刚毛触觉通道（哪一侧由甲虫的方位定）
    if (a.bite) { let b = Math.atan2(a.bite.y - a.y, a.bite.x - a.x) - a.h; const s = Math.sin(b); x[IX.touch_L] = Math.max(x[IX.touch_L], RATE * cl(0.5 + s)); x[IX.touch_R] = Math.max(x[IX.touch_R], RATE * cl(0.5 - s)); }
    // 味觉：腿 / 喙碰到才有
    a.onFood = a.air > 0 ? null : W.foodAt(a.x, a.y); a.onWater = a.air > 0 ? null : W.waterAt(a.x, a.y);
    if (a.onFood) { const f = a.onFood, rot = W.isRotten(f) ? cl(0.4 + (f.age - WK.rotAge) / (WK.goneAge - WK.rotAge)) : 0; a.rotten = rot; x[IX.sugar] = RATE * (1 - 0.5 * rot); x[IX.bitter] = RATE * rot; } else a.rotten = 0;
    if (a.onWater) x[IX.water] = RATE;
    return x;
  }
  const API = { sense, IX }; if (typeof module !== "undefined" && module.exports) module.exports = API; else root.EcoSenses = API;
})(typeof window !== "undefined" ? window : globalThis);
