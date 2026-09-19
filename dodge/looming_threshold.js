#!/usr/bin/env node
/**
 * 复现 Fotowat, Fayyazuddin, Bellen & Gabbiani 2009（J Neurophysiol 102:875–885）的核心定量结论：
 * **果蝇对逼近刺激的起飞，发生在视角张到一个固定阈值之后的固定延迟**，与逼近快慢无关。
 *
 * 论文的数字（全文由用户提供）：
 *   · 抬翅（WR）平均发生在张角 **49°（SD 4°）**；
 *   · 起飞（TO）发生在张角达到 **54°（SD 5°）之后 6 ms（SD 11 ms）**；
 *   · WR 与 TO 的时刻都与 l/|v| **线性相关**（斜率 2.2 / 2.0，SD 0.2），所以两条线近乎平行；
 *   · 白眼果蝇里阈值 **47°（SD 7.5°）**、TO 在其后 22 ms；
 *   · 逼近越快（l/|v| 越小），起飞越靠近预计碰撞时刻。
 *
 * 我们的球半径 2.5 mm，页面三档球速 35 / 60 / 95 mm/s 对应 l/|v| = **71 / 42 / 26 ms**，
 * 正落在论文测的 5–80 ms 区间里，所以可以直接比。
 *
 * **判据事先写死**：
 *   A. 起飞时的张角在三档球速间基本不变（变异系数 < 20%，且无单调趋势）；
 *   B. 起飞时刻与 l/|v| 正相关（逼近越慢，越早于碰撞时刻起飞），Pearson > 0.5。
 *
 * **必须先说明一个自带的偏置**：我们用的 Ache 2019 编码里，LPLC2 = 角尺寸的高斯（峰在 42°），
 * 所以「在某个固定张角附近起飞」这件事**有一部分是编码本身带来的**，不是纯粹的连接组结果。
 * 真正非平凡的是**阈值落在哪个角度**、以及**它与逼近速度无关到什么程度**。
 *
 * 用法：node dodge/looming_threshold.js [每档秒数=150] [种子数=5]
 * 输出：results/dodge/looming_threshold.json
 */
const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "..");
const { ConnectomeBrain } = require("./brain.js");
const { createGame } = require("./game_core.js");
const SUBNAME = process.env.SUB || "subcircuit_v3";
const SUB = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge", SUBNAME + ".json"), "utf8"));
const CLIPS = JSON.parse(fs.readFileSync(ROOT + "/results/flight/flight_clips.json", "utf8")).clips;
const T = +(process.argv[2] || 150), SEEDS = +(process.argv[3] || 5);
const SPEEDS = [35, 60, 95];                      // 页面三档；l/|v| = 半径/速度
// 刺激大小：默认球半径 2.5 mm 时，**张角 54° 对应距离只有 4.9 mm**——那时球几乎已经贴到脸上
//（接触距离 = 球半径 + 体半径 = 3.9 mm）。也就是说在这个场景里论文的阈值根本来不及逃。
// 所以同时测更大的刺激：半径 8 mm 时 54° 对应 15.7 mm，是逃得掉的距离。
const RADII = (process.env.RADII || "2.5,8").split(",").map(Number);

function run(speed, seed, ballR) {
  const g = createGame(SUB, ConnectomeBrain, { seed, ballSpeed: speed,
    cfg: { encoding: "ache2019", gfTau: 0.02, takeoff: "clip", ballR,
           autoPellets: false, autoDust: false, wallVision: false, touch: false } });
  g.setFlightClips(CLIPS);
  const n = Math.round(T / g.chunkDt);
  const events = [];
  let wasFlying = false;
  for (let i = 0; i < n; i++) {
    g.step();
    const S = g.S, flying = S.jumpT >= 0;
    if (flying && !wasFlying) {
      // 起飞瞬间：找最近的那个球，算它此刻的张角与剩余撞击时间
      let best = null;
      for (const b of g.balls) {
        if (b.done) continue;
        const d = Math.hypot(b.x - S.x, b.y - S.y);
        if (!best || d < best.d) best = { d, b };
      }
      if (best) {
        const theta = 2 * Math.atan(g.CFG.ballR / Math.max(best.d, g.CFG.ballR + 0.01)) * 180 / Math.PI;
        // 剩余撞击时间：球沿自身速度方向逼近，取径向接近速率
        const rx = S.x - best.b.x, ry = S.y - best.b.y, r = Math.hypot(rx, ry) || 1;
        const vr = (best.b.vx * rx + best.b.vy * ry) / r;        // 朝果蝇的径向速度
        const ttc = vr > 1 ? (best.d - g.CFG.ballR - g.CFG.flyR) / vr : null;
        events.push({ theta: +theta.toFixed(2), dist: +best.d.toFixed(2),
                      ttc_ms: ttc === null ? null : +(ttc * 1000).toFixed(1) });
      }
    }
    wasFlying = flying;
  }
  return events;
}

const med = a => { const s = [...a].sort((x, y) => x - y); return s.length ? s[Math.floor(s.length / 2)] : null; };
const sd = a => { if (a.length < 2) return null; const m = a.reduce((x, y) => x + y, 0) / a.length;
  return Math.sqrt(a.reduce((x, y) => x + (y - m) ** 2, 0) / (a.length - 1)); };

const out = { subcircuit: SUBNAME, seconds_per_speed: T, seeds: SEEDS, ball_radius_mm: 2.5,
  paper: { source: "Fotowat, Fayyazuddin, Bellen & Gabbiani 2009, J Neurophysiol 102:875–885",
           wr_angle_deg: 49, wr_sd: 4, to_angle_deg: 54, to_sd: 5, to_delay_ms: 6,
           white_eyed_angle_deg: 47, white_eyed_sd: 7.5 },
  criterion: "A：三档球速间起飞张角的变异系数 < 20% 且无单调趋势；B：起飞时刻与 l/|v| 正相关（Pearson > 0.5）",
  caveat: "Ache 2019 编码里 LPLC2 是角尺寸的高斯（峰 42°），所以「在固定张角起飞」有一部分是编码自带的偏置；" +
          "非平凡的是阈值落在哪个角度、以及它与速度无关到什么程度。",
  by_speed: [] };

out.by_radius = [];
for (const ballR of RADII) {
console.log(`\n刺激半径 ${ballR} mm（张角 54° 对应距离 ${(ballR / Math.tan(27 * Math.PI / 180)).toFixed(1)} mm）`);
console.log(`${"球速".padEnd(8)}${"l/|v| ms".padStart(10)}${"起飞次数".padStart(9)}${"张角中位".padStart(10)}${"SD".padStart(8)}${"剩余撞击 ms".padStart(13)}`);
out.by_speed = [];
for (const sp of SPEEDS) {
  const ev = [];
  for (let s = 1; s <= SEEDS; s++) ev.push(...run(sp, s, ballR));
  const th = ev.map(e => e.theta), ttc = ev.map(e => e.ttc_ms).filter(x => x !== null);
  const rec = { speed_mm_s: sp, l_over_v_ms: +(ballR / sp * 1000).toFixed(1), n: ev.length,
                theta_median: med(th), theta_sd: sd(th) === null ? null : +sd(th).toFixed(2),
                ttc_median_ms: med(ttc), dist_median: med(ev.map(e => e.dist)) };
  out.by_speed.push(rec);
  console.log(`${String(sp).padEnd(8)}${String(rec.l_over_v_ms).padStart(10)}${String(rec.n).padStart(9)}` +
    `${(rec.theta_median === null ? "—" : rec.theta_median.toFixed(1) + "°").padStart(10)}` +
    `${(rec.theta_sd === null ? "—" : rec.theta_sd.toFixed(1)).padStart(8)}${String(rec.ttc_median_ms ?? "—").padStart(13)}`);
}
const ths = out.by_speed.map(r => r.theta_median).filter(x => x !== null);
const mean = ths.reduce((a, b) => a + b, 0) / ths.length;
const cv = sd(ths) / mean;
out.theta_mean_across_speeds = +mean.toFixed(2);
out.theta_cv = +cv.toFixed(4);
out.criterion_A_fixed_threshold = cv < 0.2;
// B：l/|v| 与「起飞时剩余撞击时间」的相关
const x = out.by_speed.map(r => r.l_over_v_ms), y = out.by_speed.map(r => r.ttc_median_ms ?? 0);
const mx = x.reduce((a, b) => a + b, 0) / x.length, my = y.reduce((a, b) => a + b, 0) / y.length;
const r = x.reduce((a, _, i) => a + (x[i] - mx) * (y[i] - my), 0) /
  Math.sqrt(x.reduce((a, v) => a + (v - mx) ** 2, 0) * y.reduce((a, v) => a + (v - my) ** 2, 0) || 1);
out.pearson_lv_vs_ttc = +r.toFixed(3);
out.criterion_B_earlier_for_slow = r > 0.5;
console.log(`三档球速的起飞张角：${ths.map(t => t.toFixed(1) + "°").join(" / ")}，` +
  `均值 ${mean.toFixed(1)}°，变异系数 ${(cv * 100).toFixed(1)}% → 判据 A ${out.criterion_A_fixed_threshold ? "成立" : "不成立"}`);
console.log(`论文：起飞阈值 54°（SD 5°）、白眼果蝇 47°（SD 7.5°）——我们 ${mean.toFixed(1)}°`);
console.log(`l/|v| 与剩余撞击时间的相关 ${r.toFixed(3)} → 判据 B ${out.criterion_B_earlier_for_slow ? "成立" : "不成立"}`);
out.by_radius.push({ ball_radius_mm: ballR, by_speed: out.by_speed,
                    theta_mean: out.theta_mean_across_speeds, theta_cv: out.theta_cv,
                    criterion_A: out.criterion_A_fixed_threshold, pearson_lv_vs_ttc: out.pearson_lv_vs_ttc,
                    criterion_B: out.criterion_B_earlier_for_slow,
                    dist_at_54deg_mm: +(ballR / Math.tan(27 * Math.PI / 180)).toFixed(1) });
}
delete out.by_speed;
out.default_radius_note = "默认球半径 2.5 mm 时 54° 对应距离 4.9 mm，而接触距离就是 3.9 mm——" +
  "论文那个阈值在这个场景里等于「已经贴到脸上」，来不及逃。所以同时测了 8 mm 的刺激。";
fs.writeFileSync(ROOT + "/results/dodge/looming_threshold.json", JSON.stringify(out, null, 1));
console.log("→ results/dodge/looming_threshold.json");
