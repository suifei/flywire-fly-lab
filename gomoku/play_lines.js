#!/usr/bin/env node
/**
 * 线型版果蝇的对弈测试。所有臂用**同一个搜索引擎**（engine.js），唯一的差别是塞进去的那张线型价值表：
 *   fly_intact 真实连接组 ｜ fly_shuffled 打乱接线 ｜ raw24 不经过脑子 ｜ rand_relu 随机网络 ｜ free_table 自由参数 ｜ teacher_table 老师的分值
 * 引擎只懂规则（成五 = 赢、必须挡五、禁手），不含任何棋形分值。
 *
 * 判据（写在跑之前）：
 *   A  棋力达标      fly_intact 只凭直觉（想 1 步）对旧老师胜率 ≥ 50%、对随机 ≥ 95%   （v1：0/40、26/40）
 *   A2 搜索有用      fly_intact 想 6 步 对 老师 v2 深度 4 胜率 ≥ 50%
 *   （深度 10 是 2026-09-20 引擎把宽度收窄到 6 之后加的，只报告、不设判据）
 *   C2 接线有用(对弈) fly_intact 对 fly_shuffled 正面交锋（同为想 4 步）胜率 ≥ 60%
 *
 * 用法：node gomoku/play_lines.js [每组对数=20]      输出：results/gomoku/play_lines.json
 */
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, ".."), R = ROOT + "/results/gomoku";
const G = require("./rules.js"), L = require("./lines.js"), T1 = require("./teacher.js"), T2 = require("./teacher2.js"), A = require("./arena.js"), F2 = require("./fly2.js"), E = require("./engine.js");
if (process.argv[2] === "--dump-cls") { fs.mkdirSync(R + "/ds2", { recursive: true }); fs.writeFileSync(R + "/ds2/teacher_cls.json", JSON.stringify(Array.from(T2.CLS))); console.log("→ ds2/teacher_cls.json"); process.exit(0); }
const PAIRS = +(process.argv[2] || 20), TAG = process.env.TAG || "";
const ARMS = (process.env.ARMS || "fly_intact,fly_shuffled,raw24,rand_relu,free_table,teacher_table").split(",");

const engines = {};
for (const arm of ARMS) {
  if (arm === "teacher_table") { engines[arm] = E.makeEngine(T2.attTable(), 0.4); continue; }   // λ 取与果蝇学到的相近的值，只作参照
  const f = `${R}/linetable_${arm}${TAG}.json`; if (!fs.existsSync(f)) continue;
  const j = JSON.parse(fs.readFileSync(f, "utf8")); engines[arm] = E.makeEngine(F2.loadTable(j).att, j.lam);
}
const pl = (arm, d) => (b, c) => (d <= 1 ? engines[arm].greedy(b, c) : engines[arm].think(b, c, { depth: d }).move);
const OPP = { random: A.randomPlayer, old_teacher: (b, c) => T1.best(b, c).move,
  teacher2_d4: (b, c) => T2.search(b, c, 4).move, teacher2_d6: (b, c) => T2.search(b, c, 6).move, teacher2_d8: (b, c) => T2.search(b, c, 8).move };
const out = { pairs: PAIRS, games_per_match: 2 * PAIRS, engine: {}, head_to_head: {}, note: "所有臂共用 engine.js；深度 = 向前搜的步数，1 = 直觉" };
const t0 = Date.now(), slim = r => ({ win: r.win, loss: r.loss, draw: r.draw, games: r.games, mean_ply: r.mean_ply });
for (const arm of Object.keys(engines)) {
  out.engine[arm] = {};
  const depths = arm === "fly_intact" ? [1, 4, 6, 8, 10] : arm.startsWith("fly") ? [1, 4, 6, 8] : [1, 6];
  for (const d of depths) {
    out.engine[arm]["d" + d] = {};
    for (const [on, opp] of Object.entries(OPP)) {
      if (on === "teacher2_d8" && !(arm === "fly_intact" && d >= 6)) continue;        // 深度 8 的老师很慢，只给主角
      if (d >= 8 && (on === "random" || on === "old_teacher")) continue;               // 想 6 步已经全胜的对手不再重复
      if ((on === "random" || on === "old_teacher") && d > 1 && !arm.startsWith("fly")) continue;
      out.engine[arm]["d" + d][on] = slim(A.match(pl(arm, d), opp, on === "teacher2_d8" ? Math.min(PAIRS, 10) : PAIRS, 7000));
    }
    console.log(`${arm.padEnd(14)} 想${d}步  ` + Object.entries(out.engine[arm]["d" + d]).map(([k, r]) => `${k} ${r.win}-${r.loss}${r.draw ? "-" + r.draw : ""}`).join("  ") + `   ${((Date.now() - t0) / 1000).toFixed(0)} s`);
  }
}
if (engines.fly_intact && engines.fly_shuffled) for (const d of [1, 4, 6]) {
  out.head_to_head["d" + d] = slim(A.match(pl("fly_intact", d), pl("fly_shuffled", d), PAIRS, 9000));
  console.log(`真实接线 对 打乱接线（都想 ${d} 步）：`, JSON.stringify(out.head_to_head["d" + d]));
}
const rate = r => +(r.win / r.games).toFixed(3), fi = out.engine.fly_intact;
if (fi) {
  out.criterion_A = { vs_old_teacher: rate(fi.d1.old_teacher), vs_random: rate(fi.d1.random), passed: rate(fi.d1.old_teacher) >= 0.5 && rate(fi.d1.random) >= 0.95, v1: { vs_teacher: "0/40", vs_random: "26/40" } };
  out.criterion_A2 = { d6_vs_teacher2_d4: rate(fi.d6.teacher2_d4), passed: rate(fi.d6.teacher2_d4) >= 0.5 };
  if (out.head_to_head.d4) out.criterion_C2 = { intact_vs_shuffled_d4: rate(out.head_to_head.d4), passed: rate(out.head_to_head.d4) >= 0.6 };
  console.log("判据 A:", JSON.stringify(out.criterion_A), " A2:", JSON.stringify(out.criterion_A2), " C2:", JSON.stringify(out.criterion_C2));
}
out.seconds = +((Date.now() - t0) / 1000).toFixed(0);
fs.writeFileSync(`${R}/play_lines${TAG}.json`, JSON.stringify(out, null, 1));
console.log(`→ results/gomoku/play_lines${TAG}.json（${out.seconds} s）`);
