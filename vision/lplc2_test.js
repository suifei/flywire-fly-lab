#!/usr/bin/env node
/**
 * LPLC2 汇集模型的决定性检验：它能不能把**逼近**和远离/平移分开？
 *
 * ── 预先声明（写在跑之前）──────────────────────────────────
 * 刺激：六边形点阵上的暗圆盘，亮背景。dt 5 ms，共 1.2 s。
 *   · 逼近 loom：角半径按 θ(t)=atan(R/(d0−v·t)) 从 0.6 涨到 8 个小眼（加速扩张）
 *   · 远离 rec ：把 loom 的时间倒过来
 *   · 匀速镜像对 loomLin / recLin：半径线性 0.6↔8。**这一对才是干净的 A 判据** ——
 *     真实的远离在物理上就是"开局角速度最大"，而那一刻恰好是运动起始、网络刚脱离静止
 *     适应态，和逼近的最快阶段（连续运动 1.2 s 之后）在适应状态上不对等。匀速镜像
 *     把速度和适应都配平了。
 *   · 近距平移 transN：半径恒为 4 个小眼，圆心横扫 −11 → +11
 *   · 远距平移 transF：半径恒为 1.5 个小眼，同样横扫
 * 读数：**运动段**里 LPLC2 population `mean` 的峰值（逼近检测器应在接触前达到峰）。
 * 每个刺激先把**首帧静态呈现 0.4 s** 让网络稳定，再开始运动，只对运动段计分 ——
 * 第一版没有这个预呈现，结果远离/平移的峰值全部落在计分窗口的第一帧（0.15 s），
 * 那是刺激骤现的瞬态：远离一开局就是半径 8 的大暗盘凭空出现，平移是圆盘从边缘切入，
 * 而逼近开局只有半径 0.6 的小点。比的是"谁出场动静大"，不是"谁在逼近"。
 * 统一规则：运动开始后的前 0.3 s 不计分（所有刺激一视同仁，压住运动起始的瞬态）。
 * 预先判据（三条）：
 *   A) loomLin 峰值 > recLin 峰值   ← 匀速镜像，干净
 *   A') loom 峰值 > rec 峰值         ← 物理真实但适应态不对等，记录不作判据
 *   B) loom 峰值 > 两种平移的峰值
 * §18 里全脑那条离线链路在同一问题上是 A 成立、B 只对远距平移成立
 * （逼近 0.65 Hz vs 近距平移 1.14 Hz），所以 B 是真正的难关。
 *
 * 注意：读数统计量（mean 而不是 max）和感受野半径（20）是由**另一组独立刺激**
 * （全场径向光栅，纯扩张 vs 纯收缩）的诊断定下来的，所以下面这次 A/B 检验
 * **不是完全独立**的。诊断数据见 report §28.18。
 * ────────────────────────────────────────────────────────
 *
 * 用法：node vision/lplc2_test.js
 */
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, "..");
const FlyVis = require(path.join(__dirname, "flyvis.js"));
const LPLC2 = require(path.join(__dirname, "lplc2.js"));

const netDoc = JSON.parse(fs.readFileSync(path.join(ROOT, "results/vision/flyvis_net.json"), "utf8"));
const net = FlyVis.load(netDoc);
const lat = netDoc.lattice, N = lat.length;
const pos = lat.map(([u, v]) => [u + v / 2, v * Math.sqrt(3) / 2]);
const dirTable = JSON.parse(fs.readFileSync(path.join(ROOT, "results/vision/t4t5_directions.json"), "utf8")).定标;

const model = LPLC2.build(lat, dirTable, {});   // 默认 R=20 / stride=3，理由见 lplc2.js
console.log(`LPLC2 模型：用上 ${model.types.length} 个亚型 [${model.types.join(", ")}]，`
          + `${model.centers} 个中心，感受野半径 ${model.R} 个小眼\n`);

const DT = +(process.env.DT || 0.005), T = 1.2, STEPS = Math.round(T / DT);
const PRE = Math.round(0.4 / DT);                  // 首帧静态预呈现的步数
const SKIP = Math.round(0.3 / DT);                 // 运动开始后不计分的步数
const EDGE = 0.8;                                  // 边缘软化宽度（小眼），防点阵混叠

function frame(x, cx, cy, rad) {
  for (let i = 0; i < N; i++) {
    const d = Math.hypot(pos[i][0] - cx, pos[i][1] - cy);
    const t = Math.max(0, Math.min(1, (d - rad) / EDGE + 0.5));   // 圆内 0（暗），圆外 1（亮）
    x[i] = 0.15 + 0.85 * t;
  }
}

// 逼近的角半径序列：θ(t) = atan(R/(d0 − v t))，归一化到 0.6 → 8 个小眼
function loomRadii() {
  const R0 = 1, d0 = 30, v = 22;                   // 手选，只为造出加速扩张的形状
  const raw = [];
  for (let s = 0; s < STEPS; s++) raw.push(Math.atan(R0 / (d0 - v * (s * DT))));
  const lo = raw[0], hi = raw[raw.length - 1];
  return raw.map(r => 0.6 + (r - lo) / (hi - lo) * (8 - 0.6));
}
const LOOM = loomRadii();

const STIM = {
  loom:   s => [0, 0, LOOM[s]],
  rec:    s => [0, 0, LOOM[STEPS - 1 - s]],
  transN: s => [-11 + 22 * s / (STEPS - 1), 0, 4],
  transF: s => [-11 + 22 * s / (STEPS - 1), 0, 1.5],
  loomLin: s => [0, 0, 0.6 + 7.4 * s / (STEPS - 1)],
  recLin:  s => [0, 0, 8 - 7.4 * s / (STEPS - 1)],
};

const res = {};
for (const [name, f] of Object.entries(STIM)) {
  net.reset();
  const x = new Float64Array(N);
  let peak = 0, peakT = 0, sum = 0, peakE = 0;
  const trace = [];
  { const [cx0, cy0, r0] = f(0); frame(x, cx0, cy0, r0);
    for (let s = 0; s < PRE; s++) net.step(x, DT); }    // 首帧静态预呈现，不计分
  for (let s = 0; s < STEPS; s++) {
    const [cx, cy, rad] = f(s);
    frame(x, cx, cy, rad);
    net.step(x, DT);
    if (s < SKIP) continue;                        // 运动起始瞬态，不计分
    const r = model.run(net.act);
    const e = model.energy(net.act);
    if (r.mean > peak) { peak = r.mean; peakT = s * DT; }
    if (e > peakE) peakE = e;
    sum += r.mean;
    if (s % 8 === 0) trace.push(+r.mean.toFixed(4));
  }
  res[name] = { 峰值: +peak.toFixed(4), 峰值时刻: +peakT.toFixed(3),
                均值: +(sum / (STEPS - SKIP)).toFixed(4), LC4能量峰: +peakE.toFixed(4), 曲线: trace };
}

console.log("刺激        LPLC2峰值  峰值时刻   LPLC2均值   LC4能量峰");
for (const [k, v] of Object.entries(res))
  console.log(k.padEnd(10) + v.峰值.toFixed(4).padStart(10) + (v.峰值时刻 + "s").padStart(10)
            + v.均值.toFixed(4).padStart(12) + v.LC4能量峰.toFixed(4).padStart(12));

const A = res.loomLin.峰值 > res.recLin.峰值;
const A2 = res.loom.峰值 > res.rec.峰值;
const B = res.loom.峰值 > res.transN.峰值 && res.loom.峰值 > res.transF.峰值;
console.log(`\n判据 A   匀速扩张 > 匀速收缩   ${A ? "✓" : "✗"}  (${res.loomLin.峰值} vs ${res.recLin.峰值})`);
console.log(`记录 A'  加速逼近 > 时间倒放   ${A2 ? "✓" : "✗"}  (${res.loom.峰值} vs ${res.rec.峰值})  不作判据`);
console.log(`判据 B   逼近 > 两种平移       ${B ? "✓" : "✗"}  (${res.loom.峰值} vs 近 ${res.transN.峰值} / 远 ${res.transF.峰值})`);
// 同上：非默认 dt 只写带后缀的文件，绝不覆盖权威结果
const OUT = path.join(ROOT, DT === 0.005 ? "results/vision/lplc2_test.json"
                                         : `results/vision/lplc2_test_dt${Math.round(DT * 1000)}ms.json`);
fs.writeFileSync(OUT,
  JSON.stringify({ 模型: { 亚型: model.types, 中心数: model.centers, 感受野半径: model.R },
                   预先判据: { A: "匀速扩张峰值 > 匀速收缩峰值", "A'": "加速逼近 > 时间倒放（记录，不作判据）",
                              B: "逼近峰值 > 两种平移峰值" },
                   结果: res, 判据A: A, "记录A'": A2, 判据B: B }, null, 1));
console.log("→ " + path.relative(ROOT, OUT) + (DT === 0.005 ? "（权威）" : "（参数变体）"));
process.exit(A && B ? 0 : 1);
