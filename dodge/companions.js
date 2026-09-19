// 同伴果蝇：场上再放几只，**每一只都有自己独立的一份真实连接组大脑**（同一个 4,599 神经元子回路）。
//
// 诚实说明：同伴只接了「视觉 → 转向 / 起飞」这一路（LC4/LPLC2 → DNa01/02、DNp01），
// 不吃、不梳理、不后退——那些通路在它们身上没有接输入，不是被简化掉了。
// 球与围栏用的是和主角**完全相同**的手写前端（game_core 里那套 dθ/dt）。
// 代价是算力：每多一只就多跑一份 4,599 神经元的网络，页面帧率会掉。
(function (root) {
  const TG = ["DNa01_left", "DNa01_right", "DNa02_left", "DNa02_right", "DNp01_left", "DNp01_right"];

  function rng32(seed) {
    let s = seed >>> 0;
    return () => { s = (s + 0x6d2b79f5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  }

  function create(SUB, BrainClass, game, seed) {
    const CFG = game.CFG;
    const brain = new BrainClass(SUB, seed * 13 + 5);
    const rand = rng32(seed * 77 + 3);
    const targetOf = new Int8Array(SUB.meta.n).fill(-1);
    TG.forEach((g, k) => (SUB.groups[g] || []).forEach(i => { targetOf[i] = k; }));
    const ema = new Float32Array(TG.length), counts = new Float32Array(TG.length);
    const hw = CFG.courtW / 2 - CFG.courtPad, hh = CFG.courtH / 2 - CFG.courtPad;
    const S = { x: (rand() * 2 - 1) * hw * 0.7, y: (rand() * 2 - 1) * hh * 0.7, h: rand() * 6.283,
                z: 0, phase: rand() * 10, jumpT: -1, cooldown: 0, jumpDir: 0, state: "walk",
                speed: 0, omega: 0, wall: 0 };
    const wallTheta = {};
    const ballTheta = new Map();

    function sense(dt) {
      let lc4L = 0, lc4R = 0, lpL = 0, lpR = 0, threat = null, threatDrive = 0;
      const ch = Math.cos(-S.h), sh = Math.sin(-S.h);
      const enc = (theta, dtheta) => {
        if (CFG.encoding === "ache2019") {
          const td = theta * 180 / Math.PI, vd = dtheta * 180 / Math.PI;
          return [CFG.lc4Slope * vd, CFG.lplc2Peak * Math.exp(-((td - CFG.lplc2Mu) ** 2) / (2 * CFG.lplc2Sigma ** 2))];
        }
        const v = CFG.loomGain * dtheta; return [v, v];
      };
      const seen = new Set();
      for (const b of game.balls) {
        seen.add(b.id);
        const rx = b.x - S.x, ry = b.y - S.y;
        const fx = ch * rx - sh * ry, fy = sh * rx + ch * ry;
        const d = Math.max(Math.hypot(fx, fy), CFG.ballR + 0.01);
        const theta = 2 * Math.atan(CFG.ballR / d);
        const prev = ballTheta.get(b.id);
        ballTheta.set(b.id, theta);
        if (prev === undefined) continue;
        const dtheta = (theta - prev) / dt;
        if (dtheta <= 0 || theta < 0.05) continue;
        const bearing = Math.atan2(fy, fx) * 180 / Math.PI;
        if (Math.abs(bearing) > 165) continue;
        const [lc4, lp] = enc(theta, dtheta);
        if (bearing > -15) { lc4L += lc4; lpL += lp; }
        if (bearing < 15) { lc4R += lc4; lpR += lp; }
        if (lc4 + lp > threatDrive) { threatDrive = lc4 + lp; threat = Math.atan2(ry, rx); }
      }
      for (const id of [...ballTheta.keys()]) if (!seen.has(id)) ballTheta.delete(id);
      if (CFG.wallVision) {
        for (const [wx, wy] of [[hw, S.y], [-hw, S.y], [S.x, hh], [S.x, -hh]]) {
          const rx = wx - S.x, ry = wy - S.y, d = Math.max(Math.hypot(rx, ry), 0.5);
          if (d > CFG.wallSee) continue;
          const fx = ch * rx - sh * ry, fy = sh * rx + ch * ry;
          const bearing = Math.atan2(fy, fx) * 180 / Math.PI;
          if (Math.abs(bearing) > 100) continue;
          const theta = 2 * Math.atan(CFG.wallSpan / 2 / d);
          const key = "w" + (wx === S.x ? (wy > 0 ? "T" : "B") : (wx > 0 ? "R" : "L"));
          const prev = wallTheta[key]; wallTheta[key] = theta;
          if (prev === undefined) continue;
          const dtheta = (theta - prev) / dt;
          if (dtheta <= 0) continue;
          let [lc4, lp] = enc(theta, dtheta);
          lc4 *= CFG.wallGain; lp *= CFG.wallGain;
          if (bearing > -15) { lc4L += lc4; lpL += lp; }
          if (bearing < 15) { lc4R += lc4; lpR += lp; }
          if (lc4 + lp > threatDrive) { threatDrive = lc4 + lp; threat = Math.atan2(ry, rx); }
        }
      }
      S.threatDir = threat;
      const gain = CFG.lightFloor + (1 - CFG.lightFloor) * Math.max(0, Math.min(1, CFG.light));
      const m = CFG.loomMax, c = v => Math.min(m, Math.max(0, v * gain));
      brain.setRate("LC4_left", c(lc4L)); brain.setRate("LPLC2_left", c(lpL));
      brain.setRate("LC4_right", c(lc4R)); brain.setRate("LPLC2_right", c(lpR));
    }

    function step() {
      const dt = game.chunkDt;
      sense(dt);
      counts.fill(0);
      brain.run(CFG.chunkSteps, i => { const k = targetOf[i]; if (k >= 0) counts[k]++; });
      const k = dt / (CFG.emaTau + dt), kg = dt / (CFG.gfTau + dt);
      for (let i = 0; i < TG.length; i++) {
        const hz = counts[i] / Math.max(1, (SUB.groups[TG[i]] || []).length) / dt;
        ema[i] += (i >= 4 ? kg : k) * (hz - ema[i]);
      }
      const dnaL = ema[0] + ema[2], dnaR = ema[1] + ema[3], gf = (ema[4] + ema[5]) / 2;
      if (S.cooldown > 0) S.cooldown -= dt;
      if (S.jumpT >= 0) {
        S.jumpT += dt;
        const dur = CFG.flyDur, u = Math.min(1, S.jumpT / dur);
        S.z = CFG.flyHeight * Math.sin(Math.PI * u);
        S.h = S.jumpDir;
        S.x += Math.cos(S.jumpDir) * CFG.flySpeed * dt;
        S.y += Math.sin(S.jumpDir) * CFG.flySpeed * dt;
        if (u >= 1) { S.jumpT = -1; S.z = 0; S.cooldown = CFG.jumpCooldown; }
        S.state = "fly"; S.speed = 0; S.omega = 0;
      } else if (gf > CFG.gfThreshold && S.cooldown <= 0) {
        // 起飞方向：背离最强的逼近刺激（Card & Dickinson 2008；与主角的"真实逃逸飞行"同一条规则，
        // 只是同伴用的是简化的直线飞走，不放飞行片段）。
        // **这一条是必要的，不是装饰**：只做原地垂直跳的话，落回原处仍然对着墙——
        // 实测同伴贴墙时间 15%（ache2019）/ 24.8%（legacy）。
        S.jumpT = 0; S.state = "fly";
        S.jumpDir = S.threatDir == null ? S.h + Math.PI : S.threatDir + Math.PI;
      } else {
        S.state = "walk";
        const omega = Math.max(-CFG.turnMax, Math.min(CFG.turnMax, game.mapSign * CFG.turnGain * (dnaL - dnaR))) * Math.PI / 180;
        S.omega = omega; S.h += omega * dt;
        S.speed = CFG.walkSpeed;
        S.x += Math.cos(S.h) * S.speed * dt; S.y += Math.sin(S.h) * S.speed * dt;
        S.phase += S.speed * dt;
      }
      const cx = Math.max(-hw, Math.min(hw, S.x)), cy = Math.max(-hh, Math.min(hh, S.y));
      if (cx !== S.x || cy !== S.y) { S.x = cx; S.y = cy; S.wall += dt; } else S.wall = 0;
      return S;
    }

    return { S, brain, step, readout: () => ({ dnaL: ema[0] + ema[2], dnaR: ema[1] + ema[3], gf: (ema[4] + ema[5]) / 2 }) };
  }

  const API = { create };
  if (typeof module !== "undefined" && module.exports) module.exports = API;
  else root.FlyCompanions = API;
})(typeof window !== "undefined" ? window : globalThis);
