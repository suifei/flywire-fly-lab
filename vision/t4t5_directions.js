#!/usr/bin/env node
/**
 * 测 flyvis 里 T4/T5 四个亚型各自偏好哪个运动方向 —— **不靠命名惯例**。
 *
 * 为什么必须测：文献里 T4a/T5a 叫"前→后"、b"后→前"、c"上"、d"下"，
 * 但 flyvis 是用光流任务训练出来的，它学到的解是否和这套命名在**同一套点阵坐标里**
 * 对齐，是个经验问题。下一步要按 Klapoetke et al. 2017 的 LPLC2 模型汇集
 * "背离感受野中心"的 T4/T5，方向搞反整个逼近检测就是反的。
 *
 * 做法：在六边形点阵上放一张**漂移正弦光栅**，8 个方向各跑一遍，
 * 记录每个亚型在后半段的平均活动。另外跑一次**静止光栅**做对照 ——
 * 顺便检验"T4/T5 对静止图几乎不响应"这个说法。
 *
 * 点阵坐标：轴向 (u,v) → 平面 (hx,hy) = (u + v/2, v·√3/2)，与 eyecam 的 latticeDirs 一致。
 *
 * 用法：node vision/t4t5_directions.js
 */
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, "..");
const FlyVis = require(path.join(__dirname, "flyvis.js"));

// 网络文件可由 FLYVIS_NET 指定（集成扫描用）。默认是权威的成员 000。
const NETFILE = process.env.FLYVIS_NET
  ? path.resolve(process.env.FLYVIS_NET)
  : path.join(ROOT, "results/vision/flyvis_net.json");
const netDocRaw = fs.readFileSync(NETFILE, "utf8");
const net = FlyVis.load(netDocRaw);
const lat = JSON.parse(netDocRaw).lattice;
const N = lat.length;
const pos = lat.map(([u, v]) => [u + v / 2, v * Math.sqrt(3) / 2]);

const DT = +(process.env.DT || 0.005);       // 积分步长 s（默认 5 ms，远小于 T4/T5 的 τ≈19.8 ms）
const T_TOTAL = 1.2, T_SCORE = 0.6;          // 后 0.6 s 计分
const PERIOD_COL = 4;        // 空间周期 ≈ 4 个小眼 ≈ 22.8°
const TFS = (process.env.TF || "2,5,10,20").split(",").map(Number);  // 时间频率扫描 Hz
let TF = TFS[0];
const K = 2 * Math.PI / PERIOD_COL;

const SUB = net.types.filter(t => /^T[45][abcd]$/.test(t));

function run(angleDeg, drift) {
  const th = angleDeg * Math.PI / 180, kx = Math.cos(th) * K, ky = Math.sin(th) * K;
  net.reset();
  const x = new Float64Array(N);
  const acc = {}; for (const t of SUB) acc[t] = 0;
  let nAcc = 0;
  const steps = Math.round(T_TOTAL / DT);
  for (let s = 0; s < steps; s++) {
    const t = s * DT;
    const ph = drift ? 2 * Math.PI * TF * t : 0;
    for (let i = 0; i < N; i++) x[i] = 0.5 + 0.5 * Math.sin(kx * pos[i][0] + ky * pos[i][1] - ph);
    net.step(x, DT);
    if (t >= T_TOTAL - T_SCORE) {
      nAcc++;
      for (const ty of SUB) {
        const a = net.act[ty]; let s2 = 0;
        for (let j = 0; j < a.length; j++) s2 += Math.max(0, a[j]);   // ReLU 后的活动
        acc[ty] += s2 / a.length;
      }
    }
  }
  for (const ty of SUB) acc[ty] /= nAcc;
  return acc;
}

const ANGLES = [0, 45, 90, 135, 180, 225, 270, 315];
const all = {};
for (const tf of TFS) {
  TF = tf;
  // **必须减静止基线**：T4c/T4d/T5c/T5d 的静止活动本来就有 0.15–0.36，
  // 直接拿平均活动算方向选择性，等于把基线当成"对所有方向都响应"，DSI 被系统性压低。
  // 第一版就是这么算的，把 T4c 的 DSI 从 0.85 压成了 0.41，结论差点反了。
  const stat = run(0, false);
  const res = {}, raw = {};
  for (const a of ANGLES) {
    raw[a] = run(a, true);
    res[a] = {}; for (const t of SUB) res[a][t] = Math.max(0, raw[a][t] - stat[t]);
  }
  const per = {};
  for (const ty of SUB) {
    let cx = 0, cy = 0, tot = 0;
    for (const a of ANGLES) { const r = res[a][ty], th = a * Math.PI / 180;
      cx += r * Math.cos(th); cy += r * Math.sin(th); tot += r; }
    per[ty] = { 增量: ANGLES.map(a => +res[a][ty].toFixed(4)),
                原始: ANGLES.map(a => +raw[a][ty].toFixed(4)), 静止: +stat[ty].toFixed(4),
                峰值增量: +Math.max(...ANGLES.map(a => res[a][ty])).toFixed(4),
                偏好方向: tot > 1e-6 ? +(((Math.atan2(cy, cx) * 180 / Math.PI) + 360) % 360).toFixed(1) : null,
                方向选择性: tot > 1e-6 ? +(Math.hypot(cx, cy) / tot).toFixed(3) : null };
  }
  const movMean = SUB.reduce((s2, t) => s2 + ANGLES.reduce((u, a) => u + raw[a][t], 0) / ANGLES.length, 0) / SUB.length;
  const statMean = SUB.reduce((s2, t) => s2 + stat[t], 0) / SUB.length;
  all[tf] = { 亚型: per, 运动对静止: { 运动: +movMean.toFixed(4), 静止: +statMean.toFixed(4), 比值: +(movMean / statMean).toFixed(2) } };
}

// 每个亚型取**峰值增量最大的那个时间频率**作为它的定标结果
console.log("亚型   最佳TF  峰值增量  偏好方向  方向选择性        最贴的六边形方向");
const best = {};
for (const ty of SUB) {
  let bt = null;
  for (const tf of TFS) if (!bt || all[tf].亚型[ty].峰值增量 > all[bt].亚型[ty].峰值增量) bt = tf;
  const r = all[bt].亚型[ty];
  // 六边形点阵有两族特征方向：顶点方向 60°k，和棱方向 30°+60°k。
  // 哪一族才对是**测**出来的，不是挑的 —— 两族都算，报更贴的那个。
  let hex = null, off = null, fam = null;
  if (r.偏好方向 !== null) {
    const fit = k0 => { const h = (Math.round((r.偏好方向 - k0) / 60) * 60 + k0 + 360) % 360;
                        return [h, Math.abs(((r.偏好方向 - h + 540) % 360) - 180)]; };
    const [h0, d0] = fit(0), [h30, d30] = fit(30);
    if (d30 <= d0) { hex = h30; off = +d30.toFixed(1); fam = "30°+60°k（棱）"; }
    else { hex = h0; off = +d0.toFixed(1); fam = "60°k（顶点）"; }
  }
  best[ty] = Object.assign({ 最佳TF: bt, 最近六边形方向: hex, 偏差: off, 所属族: fam }, r);
  console.log(ty.padEnd(6) + String(bt + " Hz").padStart(7) + r.峰值增量.toFixed(4).padStart(10)
    + (r.偏好方向 === null ? "   —" : (r.偏好方向.toFixed(0) + "°").padStart(10))
    + (r.方向选择性 === null ? "        —" : r.方向选择性.toFixed(3).padStart(12))
    + (hex === null ? "          —" : (hex + "° 差" + off + "° " + fam).padStart(24)));
}
const out = { 说明: "漂移正弦光栅，空间周期 4 小眼、dt 5 ms、后 0.6 s 平均，响应**减去静止光栅基线**；角度 = 点阵平面 atan2(hy,hx)",
              方向: ANGLES, 时间频率扫描: TFS, 定标: best, 全部: all };
// **非默认参数不许覆盖权威文件**：这一步踩过 —— 后来用 TF=2 / DT=0.033 跑参数扫描，
// 把默认参数那次的结果覆盖了，报告里的数字和文件对不上（自查才发现）。
// 权威文件只由默认参数产生，变体自动加后缀。
const DEFAULT = (DT === 0.005) && (process.env.TF === undefined) && !process.env.FLYVIS_NET && !process.env.OUT_JSON;
const suffix = DEFAULT ? "" : `_dt${Math.round(DT * 1000)}ms_tf${TFS.join("-")}`;
const outFile = process.env.OUT_JSON ? path.resolve(process.env.OUT_JSON)
                                     : path.join(ROOT, `results/vision/t4t5_directions${suffix}.json`);
fs.writeFileSync(outFile, JSON.stringify(out, null, 1));
console.log(`\n→ ${path.relative(ROOT, outFile)}${DEFAULT ? "（权威）" : "（参数变体，不覆盖权威文件）"}`);
