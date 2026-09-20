/**
 * 大自然的 3D 样子（three.js）。**纯场景**：这里画的每一块石头、每一丛浆果、每一片水洼，位置和大小都直接来自 dodge/nature.js 的世界对象——
 * 果蝇撞上的、闻到的、被晒到的，就是你看到的这些。这里不做任何物理，也不参与任何神经计算。
 * 地形是一张跟着果蝇走的网格（顶点固定在世界坐标的格点上，所以不会「游动」），远处用雾收掉；物件用实例化网格，整格整格地重建。
 */
const FlyNature3D = (() => {
  function build(THREE, scene, W, css) {
    const grp = new THREE.Group(); grp.visible = false; scene.add(grp);
    const N = 100, STEP = 3.4, SIZE = N * STEP, R_ITEMS = 165;
    // —— 地形 ——
    const tg = new THREE.PlaneGeometry(SIZE, SIZE, N, N); tg.setAttribute("color", new THREE.BufferAttribute(new Float32Array((N + 1) * (N + 1) * 3), 3));
    const terrain = new THREE.Mesh(tg, new THREE.MeshLambertMaterial({ vertexColors: true })); terrain.receiveShadow = true; grp.add(terrain);
    const hash2 = (x, y) => { const s = Math.sin(x * 12.9898 + y * 78.233) * 43758.5453; return s - Math.floor(s); };
    const soft = (x, y, L) => { const X = x / L, Y = y / L, ix = Math.floor(X), iy = Math.floor(Y), fx = X - ix, fy = Y - iy, sx = fx * fx * (3 - 2 * fx), sy = fy * fy * (3 - 2 * fy);
      const a = hash2(ix, iy), b = hash2(ix + 1, iy), c = hash2(ix, iy + 1), d = hash2(ix + 1, iy + 1); return a + (b - a) * sx + (c - a) * sy + (a - b - c + d) * sx * sy; };
    // —— 实例化物件 ——
    const zUp = g => { g.rotateX(Math.PI / 2); return g; };
    const inst = (geo, mat, cap, shadow) => { const m = new THREE.InstancedMesh(geo, mat, cap); m.count = 0; m.castShadow = !!shadow; m.receiveShadow = true; m.frustumCulled = false; grp.add(m); return m; };
    const lam = (o) => new THREE.MeshLambertMaterial(Object.assign({ color: 0xffffff }, o || {}));
    const blade = new THREE.BufferGeometry(); { const w = 0.5, v = [-w, 0, 0, w, 0, 0, -0.7 * w, 0.12, 0.4, 0.7 * w, 0.12, 0.4, -0.4 * w, 0.3, 0.75, 0.4 * w, 0.3, 0.75, 0, 0.55, 1];
      blade.setAttribute("position", new THREE.Float32BufferAttribute(v, 3)); blade.setIndex([0, 1, 2, 1, 3, 2, 2, 3, 4, 3, 5, 4, 4, 5, 6]); blade.computeVertexNormals(); }
    const grassMat = lam({ side: THREE.DoubleSide }), uni = { uT: { value: 0 }, uW: { value: 0.2 } };
    grassMat.onBeforeCompile = sh => { sh.uniforms.uT = uni.uT; sh.uniforms.uW = uni.uW;
      sh.vertexShader = "uniform float uT;\nuniform float uW;\n" + sh.vertexShader.replace("#include <begin_vertex>", "#include <begin_vertex>\n#ifdef USE_INSTANCING\n float ph = instanceMatrix[3].x * 0.31 + instanceMatrix[3].y * 0.17;\n float k = position.z * position.z;\n transformed.x += k * (0.10 + 0.55 * uW) * sin(uT * (1.6 + uW * 2.5) + ph);\n transformed.y += k * (0.06 + 0.35 * uW) * cos(uT * 1.3 + ph * 1.7);\n#endif"); };
    const M = { grass: inst(blade, grassMat, 9000), rock: inst(new THREE.IcosahedronGeometry(1, 1), new THREE.MeshLambertMaterial({ flatShading: true }), 500, true), sunrock: inst(new THREE.IcosahedronGeometry(1, 1), new THREE.MeshLambertMaterial({ flatShading: true }), 120),
      stem: inst(zUp(new THREE.CylinderGeometry(1, 1, 1, 8).translate(0, 0.5, 0)), lam(), 700, true), cap: inst(new THREE.SphereGeometry(1, 16, 8, 0, 6.2832, 0, Math.PI / 2).rotateX(Math.PI / 2), lam(), 120, true),
      blob: inst(new THREE.IcosahedronGeometry(1, 1), new THREE.MeshLambertMaterial({ flatShading: true }), 900, true), fruit: inst(new THREE.SphereGeometry(1, 10, 8), lam(), 900),
      petal: inst(new THREE.CircleGeometry(1, 7), lam({ side: THREE.DoubleSide }), 400), leaf: inst(new THREE.CircleGeometry(1, 10), lam({ side: THREE.DoubleSide }), 500) };
    const mat4 = new THREE.Matrix4(), pos = new THREE.Vector3(), quat = new THREE.Quaternion(), scl = new THREE.Vector3(), eul = new THREE.Euler(), col = new THREE.Color(), up = new THREE.Vector3(0, 0, 1), nrm = new THREE.Vector3();
    function put(m, x, y, z, rx, ry, rz, sx, sy, sz, r, g, b) { if (m.count >= m.instanceMatrix.count) return; pos.set(x, y, z); quat.setFromEuler(eul.set(rx, ry, rz, "ZYX")); scl.set(sx, sy, sz); mat4.compose(pos, quat, scl); m.setMatrixAt(m.count, mat4); m.setColorAt(m.count, col.setRGB(r, g, b)); m.count++; }
    function putOnGround(m, x, y, lift, rz, sx, sy, sz, r, g, b) { if (m.count >= m.instanceMatrix.count) return; const n = W.normal(x, y); nrm.set(n[0], n[1], n[2]); quat.setFromUnitVectors(up, nrm); quat.multiply(new THREE.Quaternion().setFromAxisAngle(up, rz));
      pos.set(x, y, W.h(x, y) + lift); scl.set(sx, sy, sz); mat4.compose(pos, quat, scl); m.setMatrixAt(m.count, mat4); m.setColorAt(m.count, col.setRGB(r, g, b)); m.count++; }
    let center = [1e9, 1e9]; const bushes = [];
    function rebuild(cx, cy) {
      cx = Math.round(cx / STEP) * STEP; cy = Math.round(cy / STEP) * STEP; center = [cx, cy]; terrain.position.set(cx, cy, 0);
      const P = tg.attributes.position, C = tg.attributes.color;
      for (let i = 0; i < P.count; i++) { const x = cx + P.getX(i), y = cy + P.getY(i), z = W.h(x, y); P.setZ(i, z);
        const moss = Math.min(1, Math.max(0, soft(x, y, 46) * 1.5 - 0.25 + z * 0.03)), grit = 0.85 + 0.3 * hash2(Math.round(x / STEP), Math.round(y / STEP)), low = Math.max(0, Math.min(1, (-z - 4) / 5));
        C.setXYZ(i, (0.43 + (0.27 - 0.43) * moss) * grit * (1 - 0.35 * low), (0.34 + (0.43 - 0.34) * moss) * grit * (1 - 0.25 * low), (0.21 + (0.16 - 0.21) * moss) * grit * (1 - 0.1 * low)); }
      P.needsUpdate = true; C.needsUpdate = true; tg.computeVertexNormals(); tg.computeBoundingSphere();
      for (const m of Object.values(M)) m.count = 0; bushes.length = 0;
      W.near(cx, cy, R_ITEMS, it => { const t = it.tint, z = W.h(it.x, it.y);
        if (it.kind === "grass") { for (let k = 0; k < it.n * 2; k++) { const a = it.rot + k * 2.399, d = 0.5 + 0.55 * k * 0.6, x = it.x + Math.cos(a) * d, y = it.y + Math.sin(a) * d, hh = it.hgt * (0.55 + 0.45 * hash2(x, y)), g = 0.42 + 0.3 * hash2(y, x);
            put(M.grass, x, y, W.h(x, y) - 0.1, (hash2(x, k) - 0.5) * 0.5, (hash2(k, y) - 0.5) * 0.5, a * 3.1, 0.9 + 0.5 * t, 1, hh, 0.22 + 0.18 * t, g, 0.13); } }
        else if (it.kind === "rock") put(M.rock, it.x, it.y, z + it.hgt * 0.25, 0.3 * t, 0.4 * (1 - t), it.rot, it.r * 1.08, it.r * (0.85 + 0.3 * t), it.hgt, 0.46 + 0.12 * t, 0.45 + 0.1 * t, 0.43 + 0.08 * t);
        else if (it.kind === "sunrock") putOnGround(M.sunrock, it.x, it.y, 0.15, it.rot, it.r, it.r * (0.75 + 0.2 * t), 0.5, 0.2 + 0.05 * t, 0.2 + 0.04 * t, 0.22);
        else if (it.kind === "mushroom") { put(M.stem, it.x, it.y, z - 0.3, 0, 0, 0, it.r - 0.25, it.r - 0.25, it.hgt, 0.9, 0.87, 0.78); put(M.cap, it.x, it.y, z + it.hgt - 0.4, 0, 0, it.tint * 6, it.cap, it.cap, it.cap * 0.62, 0.72 + 0.2 * t, 0.22 + 0.25 * (1 - t), 0.14); }
        else if (it.kind === "flower") { const lean = (t - 0.5) * 0.3; put(M.stem, it.x, it.y, z - 0.2, lean, lean * 0.6, 0, 0.18, 0.18, it.hgt, 0.3, 0.5, 0.18); const hx = it.x + Math.sin(lean * 0.6) * it.hgt, hy = it.y - Math.sin(lean) * it.hgt, hz = z + it.hgt;
          const pc = t < 0.33 ? [0.95, 0.9, 0.35] : t < 0.66 ? [0.93, 0.93, 0.96] : [0.72, 0.45, 0.85]; for (let k = 0; k < 6; k++) { const a = it.rot + k * 1.047; put(M.petal, hx + Math.cos(a) * 1.5, hy + Math.sin(a) * 1.5, hz, 0.25, 0, a, 1.5, 0.75, 1, pc[0], pc[1], pc[2]); }
          put(M.fruit, hx, hy, hz + 0.1, 0, 0, 0, 0.8, 0.8, 0.5, 0.85, 0.6, 0.1); }
        else if (it.kind === "leaf") putOnGround(M.leaf, it.x, it.y, 0.12, it.rot, it.r, it.r * 0.5, 1, 0.55 + 0.3 * t, 0.36 + 0.2 * (1 - t), 0.12);
        else if (it.kind === "bush") { bushes.push(it); put(M.stem, it.x, it.y, z - 0.3, 0.06, -0.05, 0, 1.1, 1.1, it.hgt * 0.8, 0.36, 0.26, 0.16);
          for (let k = 0; k < 7; k++) { const a = it.rot || k * 0.9, aa = a + k * 0.898, d = it.spread * (k ? 0.55 : 0), bx = it.x + Math.cos(aa) * d, by = it.y + Math.sin(aa) * d, bz = z + it.hgt * (0.78 + 0.12 * hash2(bx, by)), rr = it.spread * (0.42 + 0.2 * hash2(by, bx));
            put(M.blob, bx, by, bz, 0, 0, aa, rr, rr, rr * 0.55, 0.16 + 0.1 * t, 0.36 + 0.12 * hash2(bx, k), 0.12);
            for (let q = 0; q < 3; q++) { const fa = aa + q * 2.1, fx = bx + Math.cos(fa) * rr * 0.7, fy = by + Math.sin(fa) * rr * 0.7; put(M.fruit, fx, fy, bz - rr * 0.45, 0, 0, 0, 1.3, 1.3, 1.3, 0.75, 0.1, 0.22); } } }
      });
      for (const m of Object.values(M)) { m.instanceMatrix.needsUpdate = true; if (m.instanceColor) m.instanceColor.needsUpdate = true; }
    }
    // —— 水洼（水位会变）、会动的东西（甲虫、下落的浆果、落地的果肉）——
    const waterMat = new THREE.MeshStandardMaterial({ color: 0x4f86b8, roughness: 0.08, metalness: 0.35, transparent: true, opacity: 0.72, depthWrite: false }), waterGeo = new THREE.CircleGeometry(1, 40), puddles = new Map();
    const dyn = new Map(), berryGeo = new THREE.SphereGeometry(1, 16, 12), legGeo = zUp(new THREE.CylinderGeometry(0.05, 0.03, 1, 5).translate(0, 0.5, 0));
    function beetle(r) { const g3 = new THREE.Group(), shell = new THREE.MeshStandardMaterial({ color: 0x1d2a1f, roughness: 0.25, metalness: 0.55 }), dark = new THREE.MeshStandardMaterial({ color: 0x0e0e10, roughness: 0.6 });
      const body = new THREE.Mesh(berryGeo, shell); body.scale.set(r * 1.25, r * 0.9, r * 0.7); body.position.z = r * 0.75; body.castShadow = true; const head = new THREE.Mesh(berryGeo, dark); head.scale.setScalar(r * 0.42); head.position.set(r * 1.3, 0, r * 0.6); g3.add(body, head); g3.userData.legs = [];
      for (let k = 0; k < 6; k++) { const L = new THREE.Mesh(legGeo, dark), sd = k < 3 ? 1 : -1, ax = (k % 3 - 1) * r * 0.7; L.position.set(ax, sd * r * 0.6, r * 0.55); L.scale.set(r * 1.4, r * 1.4, r * 1.25); L.rotation.set(sd * 2.3, 0, 0); g3.add(L); g3.userData.legs.push({ L, sd, k }); } return g3; }
    // —— 天空、太阳、雨 ——
    const sunL = new THREE.DirectionalLight(0xfff2dc, 1.0); sunL.castShadow = true; sunL.shadow.mapSize.set(2048, 2048); { const c = sunL.shadow.camera; c.left = -70; c.right = 70; c.top = 70; c.bottom = -70; c.near = 10; c.far = 600; } sunL.shadow.bias = -0.0006; grp.add(sunL, sunL.target);
    const skyL = new THREE.HemisphereLight(0xbfd9ff, 0x5a4a30, 0.75); grp.add(skyL);
    const sunDisc = new THREE.Mesh(new THREE.CircleGeometry(26, 32), new THREE.MeshBasicMaterial({ color: 0xfff1c0, fog: false, depthWrite: false })); grp.add(sunDisc);
    const stars = new THREE.Points(new THREE.BufferGeometry(), new THREE.PointsMaterial({ color: 0xffffff, size: 1.6, sizeAttenuation: false, transparent: true, opacity: 0, fog: false, depthWrite: false })); { const v = []; for (let k = 0; k < 500; k++) { const a = hash2(k, 1) * 6.2832, e = Math.asin(0.08 + 0.92 * hash2(1, k)); v.push(Math.cos(a) * Math.cos(e) * 780, Math.sin(a) * Math.cos(e) * 780, Math.sin(e) * 780); } stars.geometry.setAttribute("position", new THREE.Float32BufferAttribute(v, 3)); stars.frustumCulled = false; } grp.add(stars);
    const NR = 700, rainGeo = new THREE.BufferGeometry(), rainPos = new Float32Array(NR * 6), rainSeed = new Float32Array(NR * 3); for (let k = 0; k < NR; k++) { rainSeed[k * 3] = (hash2(k, 3) - 0.5) * 220; rainSeed[k * 3 + 1] = (hash2(3, k) - 0.5) * 220; rainSeed[k * 3 + 2] = hash2(k, k) * 90; }
    rainGeo.setAttribute("position", new THREE.BufferAttribute(rainPos, 3)); const rain = new THREE.LineSegments(rainGeo, new THREE.LineBasicMaterial({ color: 0xcfe2f5, transparent: true, opacity: 0, depthWrite: false })); rain.frustumCulled = false; grp.add(rain);
    const DAY = new THREE.Color(0x9fc8ee), DUSK = new THREE.Color(0xe9a36b), NIGHT = new THREE.Color(0x0b1226), RAINY = new THREE.Color(0x7f8a93), bg = new THREE.Color(), saved = { bg: scene.background, fog: scene.fog };
    let tAcc = 0;
    function update(dt, g, camera) {
      const S = g.S, wx = W.weather; tAcc += dt; uni.uT.value = tAcc; uni.uW.value = g.CFG.wind && g.wind ? g.wind.speed : 0.1;
      if (Math.hypot(S.x - center[0], S.y - center[1]) > 28) rebuild(S.x, S.y);
      // 昼夜：太阳按 game_core 的时钟走一圈（light = 0.575 + 0.425·cos），雨天压暗、发灰
      const ph = 2 * Math.PI * (g.clock || 0) / g.CFG.dayLength, elev = Math.cos(ph), L = Math.max(0, Math.min(1, (elev + 0.25) / 1.25));
      const dir = new THREE.Vector3(Math.sin(ph) * 0.8, -0.45, Math.max(0.12, elev * 0.9 + 0.15)).normalize(), gz = S.ground || 0;
      sunL.position.set(S.x + dir.x * 300, S.y + dir.y * 300, gz + dir.z * 300); sunL.target.position.set(S.x, S.y, gz); sunL.intensity = (0.15 + 1.05 * L) * (1 - 0.6 * wx.rain); sunL.color.setHSL(0.09 + 0.04 * L, 0.55 - 0.3 * L, 0.72 + 0.2 * L);
      skyL.intensity = (0.22 + 0.6 * L) * (1 - 0.3 * wx.rain);
      bg.copy(NIGHT).lerp(DUSK, Math.min(1, L * 2.2)).lerp(DAY, Math.max(0, Math.min(1, (L - 0.35) / 0.5))).lerp(RAINY, 0.75 * wx.rain * L + 0.2 * wx.rain); scene.background = bg; if (!scene.fog || !scene.fog.isFog) scene.fog = new THREE.Fog(0xffffff, 120, 190); scene.fog.color.copy(bg); scene.fog.near = 110 - 50 * wx.rain; scene.fog.far = 185 - 45 * wx.rain;
      sunDisc.position.set(camera.position.x + dir.x * 700, camera.position.y + dir.y * 700, camera.position.z + dir.z * 700); sunDisc.lookAt(camera.position); sunDisc.visible = elev > -0.2 && wx.rain < 0.6; sunDisc.material.color.setHSL(0.11, 0.9, 0.62 + 0.3 * L);
      stars.position.copy(camera.position); stars.material.opacity = Math.max(0, 0.9 - L * 2.4) * (1 - wx.rain);
      terrain.material.color.setScalar(1 - 0.28 * wx.wet);                                           // 淋湿的地面颜色发深
      // 雨
      rain.material.opacity = 0.55 * wx.rain; rain.visible = wx.rain > 0.02;
      if (rain.visible) { const wxv = g.wind ? Math.cos(g.wind.dir) * g.wind.speed * 12 : 0, wyv = g.wind ? Math.sin(g.wind.dir) * g.wind.speed * 12 : 0;
        for (let k = 0; k < NR; k++) { const z = 90 - ((rainSeed[k * 3 + 2] + tAcc * 900) % 90), x = S.x + rainSeed[k * 3] + wxv * (90 - z) / 90, y = S.y + rainSeed[k * 3 + 1] + wyv * (90 - z) / 90, o = k * 6; rainPos[o] = x; rainPos[o + 1] = y; rainPos[o + 2] = gz + z; rainPos[o + 3] = x + wxv * 0.05; rainPos[o + 4] = y + wyv * 0.05; rainPos[o + 5] = gz + z + 4; }
        rainGeo.attributes.position.needsUpdate = true; }
      // 水洼
      const live = new Set(); W.near(S.x, S.y, 150, it => { if (it.kind !== "hollow" || it.level <= 0.15) return; live.add(it); let m = puddles.get(it); if (!m) { m = new THREE.Mesh(waterGeo, waterMat); grp.add(m); puddles.set(it, m); }
        const rw = it.s * (0.35 + 0.75 * it.level); m.scale.setScalar(rw); m.position.set(it.x, it.y, W.h(it.x, it.y) + it.depth * (1 - Math.exp(-(rw * rw) / (2 * it.s * it.s))) + 0.03); });
      for (const [it, m] of puddles) if (!live.has(it)) { grp.remove(m); puddles.delete(it); }
      // 甲虫、浆果、落地的果肉
      const alive = new Set();
      for (const b of g.balls) { alive.add(b); let m = dyn.get(b); const r = b.r || g.CFG.ballR;
        if (!m) { if (b.kind === "berry") { m = new THREE.Mesh(berryGeo, new THREE.MeshStandardMaterial({ color: b.bad ? 0x5a4a3a : 0xb81d3a, roughness: 0.35 })); m.castShadow = true; m.scale.setScalar(r); } else m = beetle(r); grp.add(m); dyn.set(b, m); }
        if (b.kind === "berry") { m.position.set(b.x, b.y, b.z); m.rotation.y = b.spin || 0; }
        else { const z = W.h(b.x, b.y), n = W.normal(b.x, b.y); m.position.set(b.x, b.y, z); const hd = Math.atan2(b.vy, b.vx); m.rotation.set(Math.atan(-(-n[0] * Math.sin(hd) + n[1] * Math.cos(hd))) * -1, -Math.atan(-(n[0] * Math.cos(hd) + n[1] * Math.sin(hd))), hd, "ZYX");
          for (const q of m.userData.legs) q.L.rotation.z = 0.5 * Math.sin(tAcc * 38 + q.k * 2.1) * (b.done && b.outcome === "hit" ? 0 : 1); } }
      for (const p of g.pellets) { if (p.hollow) continue; alive.add(p); let m = dyn.get(p); if (!m) { m = new THREE.Mesh(berryGeo, new THREE.MeshStandardMaterial({ color: p.type === "bitter" ? 0x4a4034 : p.type === "water" ? 0x4f86b8 : 0xa8233f, roughness: 0.6, transparent: p.type === "water", opacity: p.type === "water" ? 0.75 : 1 })); m.castShadow = true; grp.add(m); dyn.set(p, m); }
        const r = (p.r || g.CFG.pelletR) * (p.berry ? 0.5 : 1) * Math.sqrt(Math.max(0.2, Math.min(1, p.amount / g.CFG.lifeFoodAmount))); m.scale.set(r * 1.25, r * 1.25, r * 0.55); m.position.set(p.x, p.y, W.h(p.x, p.y) + r * 0.3); }
      for (const [o, m] of dyn) if (!alive.has(o)) { grp.remove(m); dyn.delete(o); }
    }
    function show(v) { if (v === grp.visible) return; grp.visible = v; if (v) { saved.bg = scene.background; saved.fog = scene.fog; center = [1e9, 1e9]; } else { scene.background = saved.bg; scene.fog = saved.fog; } }
    return { group: grp, update, show, rebuild, counts: () => ({ grass: M.grass.count, rocks: M.rock.count, bushes: bushes.length, puddles: puddles.size, dynamic: dyn.size }) };
  }
  return { build };
})();
if (typeof module !== "undefined" && module.exports) module.exports = FlyNature3D;
