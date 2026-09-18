#!/usr/bin/env node
/**
 * 端到端：相机画面 → 视网膜 → flyvis → 解码重建，全在 JS 里跑一遍。
 *
 * 前两个 parity 只证明了单个模块与 Python 一致；这个测的是**接起来对不对**，
 * 并把结果与 Python 端同一条链路（vision/eye_e2e.py）对照。
 *
 * 用法：node vision/eye_e2e.js
 */
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, "..");
const P = f => path.join(ROOT, "results/vision", f);
const FlyVis = require("./flyvis.js");
const Retina = require("./retina.js");
const HexDecoder = require("./decoder.js");
const Eye = require("../dodge/eye.js");

for (const f of ["flyvis_net.json", "retina.json", "retina_map.bin", "decoders.json"]) {
  if (!fs.existsSync(P(f))) { console.error(`缺少 ${P(f)}`); process.exit(1); }
}
const netDoc = JSON.parse(fs.readFileSync(P("flyvis_net.json"), "utf8"));
const net = FlyVis.load(netDoc);
const meta = JSON.parse(fs.readFileSync(P("retina.json"), "utf8"));
const ret = Retina.fromBuffer(fs.readFileSync(P("retina_map.bin")), meta);
const decs = HexDecoder.load(fs.readFileSync(P("decoders.json"), "utf8"), netDoc.lattice);

// 程序化生成的"图"：圆 + 方块 + 条纹 + 斜边，和 Python 端一模一样的公式
const { W, H, STEPS, DT } = Eye;
const CW = Math.round(W * 1.14), CH = Math.round(H * 1.14);
const gray = new Float32Array(CW * CH);
for (let y = 0; y < CH; y++) for (let x = 0; x < CW; x++) {
  const u = x / CW, v = y / CH;
  let g = 0.12;
  if ((u - .28) ** 2 + (v - .28) ** 2 < .026) g = .92;                  // 圆
  else if (u > .56 && u < .84 && v > .13 && v < .41) g = .58;           // 方块
  else if (v > .60 && v < .88 && u > .12 && u < .46)                    // 条纹
    g = (Math.floor(u * 40) % 2) ? .97 : .12;
  else if (u > .58 && v > .58 && (u - .58) + (v - .58) < .34 && v > .62) g = .78;  // 斜边
  gray[y * CW + x] = g;
}
const src = { gray, cw: CW, ch: CH };

const corr = (a, b) => {
  const n = a.length; let ma = 0, mb = 0;
  for (let i = 0; i < n; i++) { ma += a[i]; mb += b[i]; }
  ma /= n; mb /= n;
  let sa = 0, sb = 0, sab = 0;
  for (let i = 0; i < n; i++) { const x = a[i] - ma, y = b[i] - mb; sa += x * x; sb += y * y; sab += x * y; }
  return sab / Math.sqrt(sa * sb || 1e-12);
};

net.reset();
const getAct = t => net.get(t);
let truth = null, last = {};
// 超分辨累积：同一个小眼在不同时刻落到世界不同位置，多帧合起来信息量更高
const CX = Float64Array.from(meta.centers_x), CY = Float64Array.from(meta.centers_y);
// 画布必须是**大图**尺寸：投点坐标是 ox+cx，范围到 CW×CH。
// 之前按相机尺寸 W×H 开，越界的点全被丢掉，而且和对照图整体错位。
const accAll = new Eye.Accum(CX, CY, meta.spacing_px, CW, CH);
const accOne = new Eye.Accum(CX, CY, meta.spacing_px, CW, CH);
const t0 = Date.now();
for (let k = 0; k < STEPS; k++) {
  const [dx, dy] = Eye.gaze(k);
  const { frame, ox, oy } = Eye.cropAt(src, dx, dy);
  truth = Float64Array.from(ret.sample(frame));
  net.step(truth, DT);
  accAll.add(truth, ret.perm, ox, oy);
  if (k === STEPS - 1) {
    accOne.clear(); accOne.add(truth, ret.perm, ox, oy);
    for (const key of Object.keys(decs)) {
      if (key[0] !== "_") last[key] = Float64Array.from(decs[key].decode(getAct));
    }
  }
}
const ms = Date.now() - t0;

console.log(`端到端：${STEPS} 步扫视，${(ms / STEPS).toFixed(1)} ms/步，共 ${ms} ms`);
console.log(`网络 ${net.types.length} 类型 / ${net.nTaps} 抽头；视网膜 ${ret.w}×${ret.h} → ${ret.n} 小眼\n`);
console.log(`${"层".padEnd(16)}${"末帧 r".padStart(9)}${"训练时 r".padStart(11)}`);
let bad = 0;
for (const key of Object.keys(decs)) {
  if (key[0] === "_") continue;
  const r = corr(last[key], truth);
  const ref = decs[key].testR;
  console.log(`${decs[key].label.padEnd(16)}${r.toFixed(3).padStart(9)}${String(ref).padStart(11)}`);
  if (!(r > 0.3)) bad++;
}
// 超分辨到底有没有用：拿累积图和原图（同一坐标系）逐像素比
const world = gray;                       // 对照就是大图本身，同一坐标系
const pick = (acc) => {
  const v = [], t = [];
  for (let i = 0; i < CW * CH; i++) if (acc.den[i] > 1e-6) { v.push(acc.num[i] / acc.den[i]); t.push(world[i]); }
  return [v, t];
};
const [va, ta] = pick(accAll), [vo, to] = pick(accOne);
const rAll = corr(va, ta), rOne = corr(vo, to);
const tRef = Date.now();
accAll.refine(8);
const msRef = Date.now() - tRef;
const [vr, tr] = (() => {
  const v = [], t = [];
  for (let i = 0; i < CW * CH; i++) if (accAll.den[i] > 1e-6) { v.push(accAll.refined[i]); t.push(world[i]); }
  return [v, t];
})();
const rRef = corr(vr, tr);
console.log(`\n超分辨累积（与原图逐像素比，${CW}×${CH} 全分辨率）`);
console.log(`  单帧 721 个小眼        r = ${rOne.toFixed(3)}   覆盖 ${(vo.length / (CW * CH) * 100).toFixed(0)}%`);
console.log(`  ${STEPS} 帧扫视累积        r = ${rAll.toFixed(3)}   覆盖 ${(va.length / (CW * CH) * 100).toFixed(0)}%`);
console.log(`  反投影精修 8 轮      r = ${rRef.toFixed(3)}   用时 ${msRef} ms`);
console.log(`  单帧 → 精修          ${((rRef - rOne) / Math.abs(rOne) * 100).toFixed(1)}%`);
console.log(`  参考：把原图用 σ=8.2px 高斯模糊后与原图的相关 = 0.883（小眼接受角决定的天花板）`);

console.log();
if (rRef <= rOne + 0.005) {
  console.log("✗ 反投影精修没有实质提升 —— 不要在页面上声称超分辨");
  process.exit(1);
}
if (bad) { console.log(`✗ ${bad} 层重建相关低于 0.3 —— 链路接错了`); process.exit(1); }
console.log("✓ 整条链路在 JS 里跑通，各层重建都有实质相关");
console.log("  注：末帧 r 是单张图单帧，和训练时的跨图平均值不可直接比大小");
