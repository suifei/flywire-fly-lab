#!/usr/bin/env node
// 大自然的物理自检。判据写在跑之前（都是能手算的量）：
//   N1 自由落体：从 30 mm 高处落下，首次触地时间与 √(2h/g) 相差 ≤ 1 个物理步（5 ms）
//   N2 反弹不生能量：每次弹起的最高点单调下降，第一次反弹高度 ≤ e² × 初始高度 × 1.15
//   N3 会停：平地上 3 秒之内停稳；停稳后位置不再变
//   N4 陡坡上往下滚：在坡度 > 0.25 的地方放一颗球，1 秒后高度更低；坡度 < 0.1 的地方静止放下不滚（滚动阻力兜得住）
//   N5 地形确定性 + 连续：同一种子同一点高度逐位相同；相邻 0.1 mm 的高度差 < 0.2 mm
//   N6 上坡慢下坡快：同一处正对上坡的速度系数 < 1 < 正对下坡的
//   N7 实心物件不可穿透：把果蝇放在一块石头正中，collide 之后圆心在石头之外
//   N8 风把气味吹向下风：下风 1.5σ 处的浓度 > 上风 1.5σ 处的；无风时两者相等
//   N9 闭环里走 60 秒（v5 + 六条腿 + 大自然）：脚下高度始终等于地形高度；从不穿进实心物件；总路程 > 300 mm
// 输出 results/dodge/nature_test.json
const fs = require("fs"), path = require("path"), ROOT = path.resolve(__dirname, "..");
const Nature = require("./nature.js"); const W = Nature.create(7), g = Nature.G_MM, out = { tests: {} }, T = (k, pass, info) => { out.tests[k] = { pass: !!pass, ...info }; console.log((pass ? "✓ " : "✗ ") + k, JSON.stringify(info)); };
const dt = 0.005;
// 找地方：平地 / 陡坡
let flat = null, steep = null; for (let x = -1500; x < 1500 && !(flat && steep); x += 2.5) for (let y = -1500; y < 1500 && !(flat && steep); y += 2.5) { const s = Math.hypot(...W.grad(x, y)); let clear = true; W.near(x, y, 18, it => { if (it.solid || it.kind === "hollow") clear = false; }); if (!clear) continue; if (!flat && s < 0.03) flat = [x, y]; if (!steep && s > 0.255) steep = [x, y]; }
{ const b = { x: flat[0], y: flat[1], r: 2.5, vx: 0, vy: 0, vz: 0 }; b.z = W.h(b.x, b.y) + b.r + 30; let t = 0, tHit = null, peaks = [], prevVz = 0, zmax = -1e9; const g0 = () => W.h(b.x, b.y) + b.r; let restT = null;
  for (let i = 0; i < 800; i++) { const before = b.bounces || 0; W.integrate(b, dt); t += dt; if (tHit === null && (b.bounces || 0) > before) tHit = t; if (prevVz > 0 && b.vz <= 0 && !b.rolling) peaks.push(b.z - g0()); prevVz = b.vz; if (b.rest && restT === null) restT = t; }
  const tAna = Math.sqrt(2 * 30 / g), e = W.o.restitution; T("N1_free_fall", Math.abs(tHit - tAna) <= dt + 1e-9, { t_sim: +tHit.toFixed(4), t_analytic: +tAna.toFixed(4) });
  T("N2_no_energy_gain", peaks.length > 0 && peaks.every((p, i) => i === 0 || p <= peaks[i - 1] + 1e-6) && peaks[0] <= e * e * 30 * 1.15, { peaks_mm: peaks.map(p => +p.toFixed(2)), bound_mm: +(e * e * 30 * 1.15).toFixed(2) });
  const p0 = [b.x, b.y]; for (let i = 0; i < 100; i++) W.integrate(b, dt); T("N3_comes_to_rest", restT !== null && restT <= 3 && b.x === p0[0] && b.y === p0[1], { rest_s: restT }); }
{ const b = { x: steep[0], y: steep[1], r: 2.5, vx: 0, vy: 0, vz: 0, rolling: true }; b.z = W.h(b.x, b.y) + b.r; const z0 = b.z; for (let i = 0; i < 200; i++) W.integrate(b, dt);
  const c = { x: flat[0], y: flat[1], r: 2.5, vx: 0, vy: 0, vz: 0, rolling: true }; c.z = W.h(c.x, c.y) + c.r; for (let i = 0; i < 200; i++) W.integrate(c, dt);
  T("N4_rolls_downhill_only_when_steep", b.z < z0 - 0.5 && c.rest === true && Math.hypot(c.x - flat[0], c.y - flat[1]) < 1e-9, { steep_slope: +Math.hypot(...W.grad(steep[0], steep[1])).toFixed(2), dropped_mm: +(z0 - b.z).toFixed(2), flat_moved_mm: +Math.hypot(c.x - flat[0], c.y - flat[1]).toFixed(3) }); }
{ const W2 = Nature.create(7); let same = true, maxStep = 0; for (let k = 0; k < 400; k++) { const x = (k * 37.7) % 500 - 250, y = (k * 91.3) % 500 - 250; if (W.h(x, y) !== W2.h(x, y)) same = false; maxStep = Math.max(maxStep, Math.abs(W.h(x + 0.1, y) - W.h(x, y))); }
  T("N5_deterministic_continuous", same && maxStep < 0.2, { max_step_mm: +maxStep.toFixed(4) }); }
{ const [gx, gy] = W.grad(steep[0], steep[1]), up = Math.atan2(gy, gx), fu = W.slopeFactor(steep[0], steep[1], up, 1), fd = W.slopeFactor(steep[0], steep[1], up + Math.PI, 1); T("N6_slope_speed", fu < 1 && fd > 1, { uphill: +fu.toFixed(2), downhill: +fd.toFixed(2) }); }
{ let rock = null; for (let ix = -5; ix <= 5 && !rock; ix++) for (let iy = -5; iy <= 5 && !rock; iy++) rock = W.cell(ix, iy).items.find(i => i.kind === "rock") || null; const q = { x: rock.x + 0.01, y: rock.y }; W.collide(q, 1); T("N7_solid", Math.hypot(q.x - rock.x, q.y - rock.y) >= rock.r + 1 - 1e-9, { rock_r: +rock.r.toFixed(2), pushed_to: +Math.hypot(q.x - rock.x, q.y - rock.y).toFixed(2) }); }
{ const o = { x: 0, y: 0, sigma: 20, strength: 1 }, wind = { speed: 0.6, dir: 0 }; const down = W.plume(o, wind, 30, 0), up = W.plume(o, wind, -30, 0), d0 = W.plume(o, { speed: 0, dir: 0 }, 30, 0), u0 = W.plume(o, { speed: 0, dir: 0 }, -30, 0);
  T("N8_wind_plume", down > up * 1.5 && Math.abs(d0 - u0) < 1e-12, { downwind: +down.toFixed(3), upwind: +up.toFixed(3), calm: +d0.toFixed(3) }); }
{ const { ConnectomeBrain } = require("./brain.js"), { createGame } = require("./game_core.js"), Legs = require("./legs.js");
  const SUB = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge/subcircuit_v5.json"), "utf8")), GAIT = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge/gait.json"), "utf8")), CLIPS = JSON.parse(fs.readFileSync(path.join(ROOT, "results/flight/flight_clips.json"), "utf8")).clips;
  const G = createGame(SUB, ConnectomeBrain, { seed: 3, mode: "manual", cfg: { encoding: "ache2019", lplc2Mu: 45, gfTau: 0.02, takeoff: "clip", autoPellets: false, autoDust: true, dustEvery: 40, wind: true, courtW: 0, touch: true, wallVision: false, life: true, physiology: true } });
  G.setFlightClips(CLIPS); G.attachLegs(Legs.create(GAIT)); const WW = G.attachWorld(Nature.create(11)); let path_mm = 0, px = 0, py = 0, maxGroundErr = 0, maxPen = 0, n = Math.round(60 / G.chunkDt), berries = 0, rainS = 0;
  G.onEvent = (t, b) => { if (t === "launch" && b.kind === "berry") berries++; };
  for (let i = 0; i < n; i++) { G.step(); const S = G.S; path_mm += Math.hypot(S.x - px, S.y - py); px = S.x; py = S.y; maxGroundErr = Math.max(maxGroundErr, Math.abs(S.ground - WW.h(S.x, S.y))); if (S.z <= 0.01) WW.near(S.x, S.y, 8, it => { if (it.solid) maxPen = Math.max(maxPen, it.r + G.CFG.flyR * 0.75 - Math.hypot(S.x - it.x, S.y - it.y)); }); if (WW.weather.rain > 0.3) rainS += G.chunkDt; }
  T("N9_closed_loop_walk", maxGroundErr < 1e-9 && maxPen < 1e-6 && path_mm > 300, { path_mm: Math.round(path_mm), max_penetration_mm: +maxPen.toFixed(6), berries_dropped: berries, rain_s: +rainS.toFixed(1), jumps: G.score.jump, fields: G.fields.length, pellets: G.pellets.length }); }
out.all_pass = Object.values(out.tests).every(t => t.pass); fs.writeFileSync(path.join(ROOT, "results/dodge/nature_test.json"), JSON.stringify(out, null, 1)); process.exit(out.all_pass ? 0 : 1);
