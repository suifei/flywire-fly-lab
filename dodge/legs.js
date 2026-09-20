// 六条腿的身体：腿是**执行器**，身体是被腿推着走的——不再是「身体按速度滑行、腿只放动画」。
//
// 数据：每条腿的足尖轨迹来自 results/dodge/gait.json（FlyGym / NeuroMechFly 物理仿真录下的一个步态周期，Apache-2.0），
//       按腿拆开，每条腿有自己的相位，可以单独停、单独截掉。
// 运动学：支撑相的脚钉在地上。每一步里支撑脚在身体坐标系里往后划了多少，身体就得往前挪多少——
//       对所有支撑脚做一次二维刚体最小二乘（平移 + 转角），得到身体这一步的位移和转角。转向 = 左右腿步幅不等，是算出来的，不是直接改朝向。
// 神经 → 腿：大脑给的仍然是那几个下行神经元的读出（前进 / 后退 / 左右转向），映射成「步频 + 左右步幅」。这层映射是手写的，
//       和 FlyGym 的 HybridTurningController、Eon 的做法同一类。**腹神经索连接组（MANC）给不出三足步态**（report §12），所以腿间协调
//       也是手写的：相邻腿的相位用 Kuramoto 耦合锁回录制时的三足关系。
// 失稳：重心落在支撑多边形之外（比如截掉一条腿之后只剩两条腿撑地）时，身体那一侧着地拖行——当成一只「粘在地上、权重为 drag 的虚拟脚」
//       放进同一个最小二乘里。drag 是手选参数。没有动力学、没有打滑。
(function (root) {
  const NAMES = ["LF", "LM", "LH", "RF", "RM", "RH"];
  // 耦合：同侧相邻 + 同节对侧
  const NEIGHBORS = { LF: ["LM", "RF"], LM: ["LF", "LH", "RM"], LH: ["LM", "RH"], RF: ["RM", "LF"], RM: ["RF", "RH", "LM"], RH: ["RM", "LH"] };

  function prepare(GAIT) {
    const names = GAIT.meshes.map(m => m.name), nF = GAIT.frames.length, legs = {};
    for (const L of NAMES) {
      const tip = names.indexOf(L + "Tarsus5"), coxa = names.indexOf(L + "Coxa");
      const foot = GAIT.frames.map(f => [f[tip * 7], f[tip * 7 + 1], f[tip * 7 + 2]]);
      // 推进相 = 足尖在身体坐标系里往后划（x 递减）的那一段；其余是回摆。录下来的后腿回摆时几乎不抬脚（贴地拖回去），
      // 所以「着地」另算：足尖高度 < 0.12 mm。支撑多边形用着地的脚，推身体只用推进相的脚。
      let swing = foot.map((p, i) => foot[(i + 1) % nF][0] - p[0] > 0);
      swing = swing.map((s, i) => s || (swing[(i + nF - 1) % nF] && swing[(i + 1) % nF]));
      let best = [0, 0];
      for (let i = 0; i < nF; i++) if (swing[i] && !swing[(i + nF - 1) % nF]) { let n = 0; while (n < nF && swing[(i + n) % nF]) n++; if (n > best[1]) best = [i, n]; }
      const sw = new Array(nF).fill(false); for (let k = 0; k < best[1]; k++) sw[(best[0] + k) % nF] = true;
      const ground = foot.map(p => p[2] < 0.12);
      const st = foot.filter((_, i) => !sw[i]);
      legs[L] = { foot, swing: sw, ground, lift: Math.max(...foot.map(p => p[2])), swingStart: best[0], swingLen: best[1], coxa: [GAIT.frames[0][coxa * 7], GAIT.frames[0][coxa * 7 + 1]],
                  center: [st.reduce((s, p) => s + p[0], 0) / st.length, st.reduce((s, p) => s + p[1], 0) / st.length],
                  meshes: names.map((n, i) => n.startsWith(L) && /Coxa|Femur|Tibia|Tarsus/.test(n) ? i : -1).filter(i => i >= 0) };
    }
    return { legs, nF, stride: GAIT.stride_mm };
  }

  function create(GAIT, opts) {
    const o = Object.assign({ coupling: 8, drag: 0.6, ampMin: -1, ampMax: 2, com: [-0.2, 0] }, opts || {}), G = prepare(GAIT), nF = G.nF;
    const halfTrack = NAMES.reduce((s, L) => s + Math.abs(G.legs[L].center[1]), 0) / 6;
    const legs = NAMES.map(L => ({ name: L, side: L[0] === "L" ? 1 : -1, phase: 0, amp: 1, attached: true, hold: false, stance: !G.legs[L].swing[0], data: G.legs[L] }));
    const byName = Object.fromEntries(legs.map(l => [l.name, l]));
    const state = { v: 0, omega: 0, nStance: 0, stable: true, freq: 0 }, cal = { vRef: 18, y0: 0, g: 1, force: null };

    // 身体坐标系里的足尖位置。推进相按**匀速直线**理想化：一个周期身体前进 stride，推进相占周期的 d，所以脚在身体系里往后划 stride·d，
    // 以录制的推进相中点为中心。这样步幅相同时六只脚的速度严格一致，身体只平移；偏航只来自左右步幅差。
    // （直接回放录制的足尖轨迹不行：物理仿真里脚会打滑，各腿同一时刻的速度差到 6 倍，刚体拟合会凭空转出 ±15° 的摆动。）
    // 回摆相：x 线性回到前端，抬脚高度用录制的最大值。渲染仍用录制的网格帧，和这里的足尖有零点几毫米的出入。
    function footAt(l, phase, amp) {
      const D = l.data, f = (((phase % 1) + 1) % 1) * nF, rel = (f - D.swingStart + nF) % nF, c = D.center, L = G.stride * (nF - D.swingLen) / nF * amp;
      if (rel < D.swingLen) { const u = rel / D.swingLen; return [c[0] + L * (u - 0.5), c[1], D.lift * Math.sin(Math.PI * u)]; }
      const u = (rel - D.swingLen) / (nF - D.swingLen); return [c[0] + L * (0.5 - u), c[1], 0];
    }
    const inSwing = (l, phase) => l.data.swing[Math.floor((((phase % 1) + 1) % 1) * nF) % nF];
    const onGround = (l, phase) => l.data.ground[Math.floor((((phase % 1) + 1) % 1) * nF) % nF];

    function insidePolygon(pts, q) {        // 凸包 + 点在内
      if (pts.length < 3) return false;
      const P = pts.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]), cr = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]), H = [];
      for (const p of P) { while (H.length >= 2 && cr(H[H.length - 2], H[H.length - 1], p) <= 0) H.pop(); H.push(p); }
      const t = H.length + 1; for (let i = P.length - 2; i >= 0; i--) { const p = P[i]; while (H.length >= t && cr(H[H.length - 2], H[H.length - 1], p) <= 0) H.pop(); H.push(p); }
      H.pop(); if (H.length < 3) return false;
      for (let i = 0; i < H.length; i++) if (cr(H[i], H[(i + 1) % H.length], q) < 0) return false;
      return true;
    }

    // cmd: { v: 想要的前进速度 mm/s（负 = 后退）, omega: 想要的转向角速度 rad/s（正 = 左转） }
    function step(dt, cmd) {
      const v = cmd.v || 0, om = cmd.omega || 0, freq = Math.abs(v) / G.stride, dir = v < 0 ? -1 : 1;
      // 左转：左腿步幅小、右腿大。「步幅差 k → 偏航」的增益 cal.g 和录制步态自带的偏航 cal.y0 在创建时用同一套运动学数值标定（见 calibrate）
      const k = cal.force !== null ? cal.force : Math.abs(v) > 1e-6 ? (om * dir * cal.vRef / Math.abs(v) - cal.y0) / cal.g : 0;
      const A = [], B = [], W = [];
      for (const l of legs) {
        if (!l.attached) continue;
        const amp = Math.max(o.ampMin, Math.min(o.ampMax, 1 - l.side * k)); l.amp += (amp - l.amp) * Math.min(1, dt / 0.03);
        let dphi = l.hold ? 0 : dir * freq * dt;
        if (!l.hold && freq > 0) for (const nb of NEIGHBORS[l.name]) { const m = byName[nb]; if (m.attached && !m.hold) dphi += o.coupling * Math.sin(2 * Math.PI * (m.phase - l.phase)) / (2 * Math.PI) * dt; }
        const p0 = footAt(l, l.phase, l.amp), was = !inSwing(l, l.phase); l.phase += dphi; const p1 = footAt(l, l.phase, l.amp), now = !inSwing(l, l.phase);
        l.stance = now; l.ground = onGround(l, l.phase); l.foot = p1;
        if (was && now) { A.push(p1); B.push(p0); W.push(1); }
      }
      const support = legs.filter(l => l.attached && l.ground).map(l => [l.foot[0], l.foot[1]]);
      state.nStance = support.length; state.stable = insidePolygon(support, o.com);
      if (!state.stable && A.length) {       // 着地拖行：重心一侧缺了支撑 → 在缺的那一侧加一只粘住的虚拟脚
        const miss = legs.filter(l => !l.attached || !l.ground).map(l => l.data.coxa); const cx = support.reduce((s, p) => s + p[0], 0) / Math.max(1, support.length), cy = support.reduce((s, p) => s + p[1], 0) / Math.max(1, support.length);
        let q = miss[0] || o.com, far = -1; for (const m of miss) { const d = Math.hypot(m[0] - cx, m[1] - cy); if (d > far) { far = d; q = m; } }
        A.push(q); B.push(q); W.push(o.drag * A.length);
      }
      let dx = 0, dy = 0, dth = 0;
      if (A.length) {                        // 求 R, t 使 B ≈ R·A + t（加权）
        const sw = W.reduce((s, w) => s + w, 0); let ax = 0, ay = 0, bx = 0, by = 0;
        A.forEach((p, i) => { ax += W[i] * p[0]; ay += W[i] * p[1]; bx += W[i] * B[i][0]; by += W[i] * B[i][1]; }); ax /= sw; ay /= sw; bx /= sw; by /= sw;
        let sxx = 0, sxy = 0;
        A.forEach((p, i) => { const px = p[0] - ax, py = p[1] - ay, qx = B[i][0] - bx, qy = B[i][1] - by; sxx += W[i] * (px * qx + py * qy); sxy += W[i] * (px * qy - py * qx); });
        dth = A.length >= 2 ? Math.atan2(sxy, sxx) : 0; const c = Math.cos(dth), s = Math.sin(dth);
        dx = bx - (c * ax - s * ay); dy = by - (s * ax + c * ay);
      }
      state.v = dt > 0 ? dx / dt : 0; state.vy = dt > 0 ? dy / dt : 0; state.omega = dt > 0 ? dth / dt : 0; state.freq = freq;
      return { dx, dy, dth };                // 身体坐标系里的位移（x 向前、y 向左）和转角
    }

    function calibrate() {               // 直接给步幅差 k（绕过 cmd.omega），量 2 s 的平均偏航
      const meas = kk => { reset(); let h = 0; const dt = 1 / 600, T = 2; cal.force = kk; for (let t = 0; t < T; t += dt) h += step(dt, { v: cal.vRef, omega: 0 }).dth; cal.force = null; return h / T; };
      const y0 = meas(0), yp = meas(0.3), ym = meas(-0.3); cal.y0 = y0; cal.g = (yp - ym) / 0.6; reset();
    }
    function reset() { for (const l of legs) { l.phase = 0; l.amp = 1; l.hold = false; l.stance = !l.data.swing[0]; } }
    calibrate();
    return { legs, byName, state, step, footAt, halfTrack, stride: G.stride, nF, cal, reset,
             frameOf: l => (((l.phase % 1) + 1) % 1) * nF,
             amputate(name, on) { byName[name].attached = !on; }, hold(name, on) { byName[name].hold = !!on; } };
  }

  const API = { create, prepare, NAMES };
  if (typeof module !== "undefined" && module.exports) module.exports = API;
  else root.FlyLegs = API;
})(typeof window !== "undefined" ? window : globalThis);
