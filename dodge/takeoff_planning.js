#!/usr/bin/env node
/**
 * Card & Dickinson 2008 那条「起飞前约 200 ms 的姿态准备期」——全文拿不到，
 * 但它最有意思的一条主张是**可以在我们的模型里测的**：
 *
 *   「flies plan a takeoff direction even in instances when they choose not to jump」
 *   （果蝇**即使最终没跳**，也已经规划好了起飞方向）
 *
 * 我们没有姿态、没有腿部准备动作，所以「准备期」本身测不了。但**方向规划信号**有对应物：
 * DNa01/02 的左右差就是回路自己算出来的转向命令。于是问：
 *
 *   A. 巨纤维越阈前的 200 ms 里，DNa 左右差是不是指向**背离威胁**的一侧？
 *   B. **最终没有起飞**的那些威胁，同一个窗口里是不是也有同样的方向信号？
 *
 * 判据事先写死：两个比例都要**显著高于 50%**（随机猜是 50%），取 > 60% 算成立。
 *
 * **第一版的 B 组是错的，记在这里**：当时还额外要求 |DNa 左右差| > 0.5 Hz 才算一个样本，
 * 于是 n 从 37,730 掉到 68，比例被抬到 76.5%。那是**按被测量的信号本身筛样本**——
 * 先挑出有信号的帧，再问「有没有信号」，必然虚高。去掉这个筛选后 B 组回到 52.3%。
 * 注意 A 里用的是 DNa（连接组自己的输出），**不是** game_core 里那条手写的
 * 「起飞方向取背离威胁」规则——那条是我们写的，拿来当证据就是循环论证。
 *
 * **对照（2026-09-19 加，预测写在跑之前）**：分箱里正面（|方位| < 15°）背离比例只有 35%，远离 50%。
 * 候选解释是**选择效应**：方位是被转向本身改变的——朝威胁转，方位才会缩进正面这一档；
 * 背离威胁转，方位只会变大、离开这一档。于是正面一档里装的多半是「正在朝威胁转」的时刻，
 * 再加上 DNa 读出带 EMA 滞后，那一刻的信号自然还指着威胁。
 * 干预：TURN_GAIN=0 让 DNa 不再影响朝向（果蝇只直走），选择效应随之消失。
 * **预测**：TURN_GAIN=0 时正面一档 A、B 两组都回到 [43%, 57%]；
 * 只要有一组仍 < 43%，这个解释就被否掉，35% 继续记为未解释。
 *
 * 用法：node dodge/takeoff_planning.js [每局秒数=120] [种子数=5]
 *       TURN_GAIN=0 node dodge/takeoff_planning.js 150 6     ← 对照，写到 takeoff_planning_noturn.json
 * 输出：results/dodge/takeoff_planning.json
 */
const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "..");
const { ConnectomeBrain } = require("./brain.js");
const { createGame } = require("./game_core.js");
const SUBNAME = process.env.SUB || "subcircuit_v3";
const SUB = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge", SUBNAME + ".json"), "utf8"));
const T = +(process.argv[2] || 120), SEEDS = +(process.argv[3] || 5);
const WIN = 0.2;                     // 论文里的准备期长度：200 ms
const TURN_GAIN = process.env.TURN_GAIN === undefined ? null : +process.env.TURN_GAIN;
const OUTNAME = TURN_GAIN === null ? "takeoff_planning.json" : "takeoff_planning_noturn.json";

function wrap(a) { return Math.atan2(Math.sin(a), Math.cos(a)); }

function run(seed) {
  const g = createGame(SUB, ConnectomeBrain, { seed, ballSpeed: 60,
    cfg: { encoding: "ache2019", gfTau: 0.02, takeoff: "hop",   // hop：起飞不带方向，免得手写飞行规则混进来
           autoPellets: false, autoDust: false, wallVision: false, touch: false,
           ...(TURN_GAIN === null ? {} : { turnGain: TURN_GAIN }) } });
  const n = Math.round(T / g.chunkDt), dt = g.chunkDt;
  const hist = [];                   // 每步：[t, omega, threatBearing(体坐标), gf]
  const events = [];                 // 每次起飞的时刻
  let prevJump = false;
  for (let i = 0; i < n; i++) {
    g.step();
    const S = g.S, o = g.readout();
    let bearing = null;
    if (g.threatDir != null) bearing = wrap(g.threatDir - S.h);     // + = 威胁在左
    hist.push([S.t, o.dnaL - o.dnaR, bearing, o.gf]);
    const jumping = S.jumpT >= 0;
    if (jumping && !prevJump) events.push(S.t);
    prevJump = jumping;
  }
  // A：每次起飞前 WIN 秒的窗口
  // dna === 0 时方向是**未定义**，不是"方向错"。第一版把它算进分母，
  // 而 |DNa 左右差| 的中位数恰好就是 0（大部分时刻根本没有转向信号），
  // 于是比例被一堆"零"钉在 50% 附近。现在零帧返回 null 排除掉，并单独报告它占多少。
  const away = (dna, bearing) => (bearing == null || dna === 0 ? null : (Math.sign(dna) === -Math.sign(bearing)));
  const frac = rows => {
    const v = rows.map(r => away(r[1], r[2])).filter(x => x !== null);
    return v.length ? { n: v.length, of: rows.length, defined: +(v.length / Math.max(rows.length, 1)).toFixed(3),
                        frac: v.filter(Boolean).length / v.length }
                    : { n: 0, of: rows.length, defined: 0, frac: null };
  };
  // 按威胁方位角分箱：正面的威胁本来就没有"左右"可言，这一项用来解释 A 的结果
  const bins = [[0, 15], [15, 40], [40, 80], [80, 180]];
  const byBearing = rows => bins.map(([lo, hi]) => {
    const v = rows.filter(r => r[2] != null && Math.abs(r[2]) * 180 / Math.PI >= lo && Math.abs(r[2]) * 180 / Math.PI < hi)
      .map(r => away(r[1], r[2])).filter(x => x !== null);
    return { from: lo, to: hi, n: v.length, frac: v.length ? v.filter(Boolean).length / v.length : null };
  });
  const preTakeoff = [];
  for (const t0 of events) for (const r of hist) if (r[0] >= t0 - WIN && r[0] < t0) preTakeoff.push(r);
  // B：**没有**起飞的窗口——有威胁在视野里、巨纤维始终没越阈的那些步
  const jumpMask = new Set();
  for (const t0 of events) for (const r of hist) if (r[0] >= t0 - WIN && r[0] <= t0 + 0.6) jumpMask.add(r[0]);
  // B 组原来还要求 |DNa 左右差| > 0.5 Hz，样本一下掉到几十个。
  // 现在只要求「视野里有威胁、且不在起飞窗口内」；转向信号弱不弱另外单独报告，
  // 不要用它来筛样本——那等于先挑了有信号的再问有没有信号。
  const noTakeoff = hist.filter(r => r[2] != null && !jumpMask.has(r[0]));
  const absMed = rows => { const v = rows.map(r => Math.abs(r[1])).sort((x, y) => x - y);
    return v.length ? +v[Math.floor(v.length / 2)].toFixed(2) : null; };
  // 正面一档的 2×2 表：DNa 左右差的符号 × 威胁方位的符号。
  // 用来分辨「DNa 自带固定的左右偏置」（某一行恒大，与方位无关）
  // 和「DNa 真的随方位变、但方向反了」（对角线上的两格大）。
  const table = rows => {
    const t = { dnaL_threatL: 0, dnaL_threatR: 0, dnaR_threatL: 0, dnaR_threatR: 0 };
    for (const r of rows) {
      if (r[2] == null || r[1] === 0 || r[2] === 0 || Math.abs(r[2]) * 180 / Math.PI >= 15) continue;
      t[(r[1] > 0 ? "dnaL" : "dnaR") + "_" + (r[2] > 0 ? "threatL" : "threatR")]++;
    }
    return t;
  };
  return { takeoffs: events.length, pre: frac(preTakeoff), no: frac(noTakeoff),
           front_table_pre: table(preTakeoff), front_table_no: table(noTakeoff),
           pre_dna_abs_median: absMed(preTakeoff), no_dna_abs_median: absMed(noTakeoff),
           pre_bins: byBearing(preTakeoff), no_bins: byBearing(noTakeoff),
           dodge: g.score.dodge, hit: g.score.hit };
}

const runs = Array.from({ length: SEEDS }, (_, i) => run(i + 1));
const sum = (k, f) => runs.reduce((a, r) => a + r[k][f], 0);
const preN = sum("pre", "n"), preOK = runs.reduce((a, r) => a + (r.pre.frac || 0) * r.pre.n, 0);
const noN = sum("no", "n"), noOK = runs.reduce((a, r) => a + (r.no.frac || 0) * r.no.n, 0);
const A = preN ? preOK / preN : null, B = noN ? noOK / noN : null;
const out = { subcircuit: SUBNAME, seconds_per_seed: T, seeds: SEEDS, window_s: WIN,
  note: "「背离威胁」= DNa 左右差的符号与威胁方位相反。用的是连接组自己的 DNa 输出，" +
        "不是 game_core 里那条手写的「起飞方向取背离威胁」规则。",
  criterion: "A（起飞前 200 ms）与 B（最终没起飞的窗口）的比例都要 > 60%；" +
             "分箱是**事后加的探索性分析**，用来解释 A 为什么不成立",
  takeoffs: runs.reduce((a, r) => a + r.takeoffs, 0),
  pre_takeoff: { n: preN, frac_away: A === null ? null : +A.toFixed(4),
                 frac_frames_with_signal: +(runs.reduce((a, r) => a + r.pre.defined, 0) / SEEDS).toFixed(3),
                 dna_abs_median: +(runs.reduce((a, r) => a + (r.pre_dna_abs_median || 0), 0) / SEEDS).toFixed(2) },
  no_takeoff: { n: noN, frac_away: B === null ? null : +B.toFixed(4),
                frac_frames_with_signal: +(runs.reduce((a, r) => a + r.no.defined, 0) / SEEDS).toFixed(3),
                dna_abs_median: +(runs.reduce((a, r) => a + (r.no_dna_abs_median || 0), 0) / SEEDS).toFixed(2) },
  criterion_A: A !== null && A > 0.6, criterion_B: B !== null && B > 0.6, runs };
console.log(`子回路 ${SUBNAME}，${SEEDS} 个种子 × ${T} s，共 ${out.takeoffs} 次起飞`);
console.log(`A 起飞前 ${WIN * 1000} ms：${preN} 个有方向的采样（占 ${(out.pre_takeoff.frac_frames_with_signal * 100).toFixed(0)}%），` +
  `背离威胁的比例 ${(A * 100).toFixed(1)}% → ${out.criterion_A ? "成立" : "不成立"}`);
console.log(`B 最终没起飞：     ${noN} 个有方向的采样（占 ${(out.no_takeoff.frac_frames_with_signal * 100).toFixed(0)}%），` +
  `背离威胁的比例 ${(B * 100).toFixed(1)}% → ${out.criterion_B ? "成立" : "不成立"}`);
// 按威胁方位角合并各种子
const mergeBins = key => runs[0][key].map((b0, i) => {
  const n = runs.reduce((a, r) => a + r[key][i].n, 0);
  const ok = runs.reduce((a, r) => a + (r[key][i].frac || 0) * r[key][i].n, 0);
  return { from: b0.from, to: b0.to, n, frac: n ? +(ok / n).toFixed(4) : null };
});
out.pre_bins = mergeBins("pre_bins");
out.no_bins = mergeBins("no_bins");
console.log(`\n按威胁方位角分箱（|方位| 度）：`);
console.log(`${"".padEnd(12)}${"起飞前 n".padStart(10)}${"背离比例".padStart(10)}${"没起飞 n".padStart(10)}${"背离比例".padStart(10)}`);
for (let i = 0; i < out.pre_bins.length; i++) {
  const a2 = out.pre_bins[i], b2 = out.no_bins[i];
  console.log(`${(a2.from + "–" + a2.to + "°").padEnd(12)}${String(a2.n).padStart(10)}` +
    `${(a2.frac === null ? "—" : (a2.frac * 100).toFixed(1) + "%").padStart(10)}${String(b2.n).padStart(10)}` +
    `${(b2.frac === null ? "—" : (b2.frac * 100).toFixed(1) + "%").padStart(10)}`);
}
const front = out.pre_bins[0], side = out.pre_bins.slice(2).reduce((a, b2) => ({ n: a.n + b2.n, ok: a.ok + (b2.frac || 0) * b2.n }), { n: 0, ok: 0 });
out.explanation = {
  front_bin: front, side_frac: side.n ? +(side.ok / side.n).toFixed(4) : null,
  verdict: (front.frac !== null && front.frac < 0.42)
    ? ("正面威胁（|方位| < 15°）时转向信号系统性地**指向**威胁——背离比例只有 " +
       (front.frac * 100).toFixed(0) + "%；侧向威胁则在随机水平附近。" +
       "所以不是「正面没有左右可分」，而是方向本身就不对。整体上这个模型没有「背离威胁的方向规划信号」。")
    : "分箱没有显示出方位相关的方向偏好"
};
console.log("\n" + out.explanation.verdict);
const sumTable = key => runs.reduce((a, r) => { for (const k in r[key]) a[k] = (a[k] || 0) + r[key][k]; return a; }, {});
out.front_table = { pre: sumTable("front_table_pre"), no: sumTable("front_table_no"),
  note: "正面一档（|方位| < 15°）。dnaL = 左 DNa 更强（→ 左转）；threatL = 威胁在左。背离 = dnaR_threatL + dnaL_threatR" };
for (const k of ["pre", "no"]) {
  const t = out.front_table[k], n = t.dnaL_threatL + t.dnaL_threatR + t.dnaR_threatL + t.dnaR_threatR;
  t.frac_dnaL = +((t.dnaL_threatL + t.dnaL_threatR) / n).toFixed(4);          // DNa 自身的左右偏置
  t.frac_threatL = +((t.dnaL_threatL + t.dnaR_threatL) / n).toFixed(4);       // 威胁方位的左右偏置
  t.frac_dnaL_given_threatL = +(t.dnaL_threatL / (t.dnaL_threatL + t.dnaR_threatL)).toFixed(4);
  t.frac_dnaL_given_threatR = +(t.dnaL_threatR / (t.dnaL_threatR + t.dnaR_threatR)).toFixed(4);
  console.log(`正面 2×2（${k === "pre" ? "起飞前" : "没起飞"}）：左DNa强 ${(t.frac_dnaL * 100).toFixed(1)}%｜威胁在左 ${(t.frac_threatL * 100).toFixed(1)}%｜` +
    `P(左DNa强 | 威胁在左) ${(t.frac_dnaL_given_threatL * 100).toFixed(1)}%  P(左DNa强 | 威胁在右) ${(t.frac_dnaL_given_threatR * 100).toFixed(1)}%`);
}
if (TURN_GAIN !== null) {
  out.turn_gain = TURN_GAIN;
  const fa = out.pre_bins[0].frac, fb = out.no_bins[0].frac;
  const inBand = x => x !== null && x >= 0.43 && x <= 0.57;
  out.selection_control = {
    prediction: "TURN_GAIN=0 时正面一档 A、B 两组的背离比例都回到 [0.43, 0.57]",
    front_A: fa, front_B: fb, n_A: out.pre_bins[0].n, n_B: out.no_bins[0].n,
    confirmed: inBand(fa) && inBand(fb) };
  console.log(`\n选择效应对照（turnGain = ${TURN_GAIN}）：正面一档 A ${(fa * 100).toFixed(1)}%（n=${out.pre_bins[0].n}）、` +
    `B ${(fb * 100).toFixed(1)}%（n=${out.no_bins[0].n}） → 预测${out.selection_control.confirmed ? "成立" : "**不成立**"}`);
}
fs.writeFileSync(ROOT + "/results/dodge/" + OUTNAME, JSON.stringify(out, null, 1));
console.log("→ results/dodge/" + OUTNAME);
