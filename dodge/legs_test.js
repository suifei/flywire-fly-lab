#!/usr/bin/env node
// 六条腿身体的自检：给定「想要的速度 / 转向」，腿推出来的身体运动对不对。判据写在跑之前。
//   T1 直行 18 mm/s：实际速度误差 ≤10%，偏航 ≤2°/s
//   T2 转向 ±60°/s：符号正确，实际角速度误差 ≤25%
//   T3 后退 −12 mm/s：误差 ≤10%
//   T4 完整的六条腿：任何时刻支撑腿 ≥3，重心始终在支撑多边形内
// 只报告、不设判据：截掉一条腿、按住一条腿之后会怎样。
// 输出 results/dodge/legs_test.json
const fs = require("fs"), path = require("path"), ROOT = path.resolve(__dirname, "..");
const Legs = require("./legs.js"), GAIT = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge/gait.json"), "utf8"));
function run(cmd, T, setup) {
  const body = Legs.create(GAIT); if (setup) setup(body); let x = 0, y = 0, h = 0, minSt = 9, unstable = 0, n = 0; const dt = 1 / 600;
  for (let t = 0; t < T; t += dt) { const d = body.step(dt, cmd); x += Math.cos(h) * d.dx - Math.sin(h) * d.dy; y += Math.sin(h) * d.dx + Math.cos(h) * d.dy; h += d.dth; minSt = Math.min(minSt, body.state.nStance); unstable += body.state.stable ? 0 : 1; n++; }
  return { dist: Math.hypot(x, y), x, y, speed: (x * Math.cos(h / 2) + y * Math.sin(h / 2)) / T, path_speed: Math.hypot(x, y) / T, yaw_deg_s: h * 180 / Math.PI / T, min_stance: minSt, unstable_frac: unstable / n };
}
const out = { stride_mm: GAIT.stride_mm, tests: {}, explore: {} }, r = x => Math.round(x * 100) / 100;
const s = run({ v: 18, omega: 0 }, 5); out.tests.T1_straight = { ...s, pass: Math.abs(s.path_speed - 18) <= 1.8 && Math.abs(s.yaw_deg_s) <= 2 };
const om = 60 * Math.PI / 180, tl = run({ v: 18, omega: om }, 3), tr = run({ v: 18, omega: -om }, 3);
out.tests.T2_turn = { left: tl, right: tr, pass: tl.yaw_deg_s > 0 && tr.yaw_deg_s < 0 && Math.abs(tl.yaw_deg_s - 60) <= 15 && Math.abs(tr.yaw_deg_s + 60) <= 15 };
const b = run({ v: -12, omega: 0 }, 5); out.tests.T3_back = { ...b, signed_x: b.x / 5, pass: Math.abs(b.x / 5 + 12) <= 1.2 };
out.tests.T4_support = { min_stance: s.min_stance, unstable_frac: s.unstable_frac, pass: s.min_stance >= 3 && s.unstable_frac === 0 };
for (const L of Legs.NAMES) out.explore["amputate_" + L] = run({ v: 18, omega: 0 }, 5, body => body.amputate(L, true));
out.explore.hold_LM = run({ v: 18, omega: 0 }, 5, body => body.hold("LM", true));
out.all_pass = Object.values(out.tests).every(t => t.pass);
fs.writeFileSync(path.join(ROOT, "results/dodge/legs_test.json"), JSON.stringify(out, null, 1));
for (const [k, t] of Object.entries(out.tests)) console.log((t.pass ? "✓ " : "✗ ") + k, JSON.stringify(t.left ? { left: r(t.left.yaw_deg_s), right: r(t.right.yaw_deg_s) } : { speed: r(t.path_speed || 0), yaw: r(t.yaw_deg_s || 0), min_stance: t.min_stance, unstable: t.unstable_frac }));
for (const [k, t] of Object.entries(out.explore)) console.log("  " + k, "速度", r(t.path_speed), "mm/s 偏航", r(t.yaw_deg_s), "°/s 失稳时间", r(t.unstable_frac * 100) + "%");
process.exit(out.all_pass ? 0 : 1);
