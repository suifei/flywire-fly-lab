#!/usr/bin/env node
/**
 * 汇总线型版五子棋的全部结果 → results/gomoku/lines_summary.json（页面「训练过程」卡片与台账都从这里取数）。
 * 只读。页面上不许手抄数字，所以凡是要显示的都在这里算好。
 *
 *   shape_values  每个臂学到的线型价值，按老师的 9 个棋形类别取均值 —— "果蝇学会了成五 > 活四 > 活三吗"
 *                 （类别只用来**分组展示**，训练时果蝇从没见过这些类别）
 *   order_ok      学到的进攻价值是否满足 成五 > 活四 > max(冲四, 活三) > max(眠三, 活二) > 眠二
 */
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, ".."), R = ROOT + "/results/gomoku";
const L = require("./lines.js"), T2 = require("./teacher2.js"), F2 = require("./fly2.js");
const rd = f => (fs.existsSync(`${R}/${f}`) ? JSON.parse(fs.readFileSync(`${R}/${f}`, "utf8")) : null);
const out = { generated_by: "gomoku/collect_lines.js", class_names: T2.NAMES };
const train = rd("train_lines.json"), play = rd("play_lines.json"), rl = rd("rl.json"), probe = rd("line_class_probe.json"), depth = rd("depth_labels.json");
for (const [k, f] of [["dataset", "dataset_summary.json"], ["table_noise", "table_noise.json"], ["depth_timing", "depth_timing.json"], ["teacher_ladder", "teacher_ladder.json"],
                      ["score_forms", "score_forms.json"], ["depth_models", "depth_models.json"], ["search_width", "search_width.json"], ["vcf_value", "vcf_value.json"], ["seed_averaging", "seed_averaging.json"], ["opto_leak", "opto_leak.json"], ["rl_small", "rl_small.json"]]) { const d = rd(f); if (d) out[k] = k === "rl_small" ? { iters: d.iters, games_per_iter: d.games_per_iter, lr: d.lr, final: d.final, win_rate_vs_supervised: d.win_rate_vs_supervised, criterion_passed: d.criterion_passed } : d; }
// 多视角：稳健精度随视角数的变化、两次换表对决 + 独立确认、单视角时的关键数字（留档对照）
{ const tv = rd("two_views.json"); if (tv) out.views_r2 = tv;
  const c1 = rd("compare_mv_attempt1.json"), c2 = rd("compare_linetable_fly_intact_mv2.json"), c3 = rd("compare_linetable_fly_intact_mv2_confirm.json");
  if (c2) out.view_adoption = { attempt1_fixed_ridge: c1, attempt2: c2, confirm: c3 };
  const t1 = rd("train_lines_1view.json"), p1 = rd("play_lines_1view.json");
  if (t1 && p1) out.one_view = { fly_intact: (({ dim, distill_r2, distill_r2_newseeds, test_top1, test_top1_testseeds, wine_top1, seed_drop }) => ({ dim, distill_r2, distill_r2_newseeds, test_top1, test_top1_testseeds, wine_top1, seed_drop }))(t1.arms.fly_intact),
    fly_shuffled: { dim: t1.arms.fly_shuffled.dim, test_top1: t1.arms.fly_shuffled.test_top1 }, play_fly_intact: p1.engine.fly_intact, head_to_head: p1.head_to_head }; }
if (train) out.train = train;
if (play) out.play = play;
if (probe) out.class_probe = probe;
if (depth) out.depth_labels = depth;
if (rl) out.rl = { ...rl, log: rl.log.map(r => ({ iter: r.iter, win_rate: r.win_rate, baseline: r.baseline, mean_abs_delta: r.mean_abs_delta })),
                   delta_trace: rl.log.flatMap(r => r.deltas).filter((_, i) => i % 4 === 0) };
const codes = L.allCodes(), counts = new Array(9).fill(0);
for (const c of codes) counts[T2.CLS[c]]++;
out.class_counts = counts;
out.shape_values = {};
for (const arm of ["fly_intact", "fly_shuffled", "raw24", "rand_relu", "free_table", "fly_intact_rl"]) {
  const j = rd(`linetable_${arm}.json`); if (!j) continue;
  // 表是线性尺度、跨 7 个数量级，算术平均会被最大的几种线型带走——在**对数尺度**上取均值
  const t = F2.loadTable(j), sum = new Array(9).fill(0), lin = j.form === "lse";
  for (const c of codes) sum[T2.CLS[c]] += lin ? Math.log(Math.max(t.att[c], 1e-12)) : t.att[c];
  const A = sum.map((v, k) => +(v / counts[k]).toFixed(3));
  const o = T2, ok = A[o.FIVE] > A[o.OPEN4] && A[o.OPEN4] > Math.max(A[o.FOUR], A[o.OPEN3]) &&
    Math.min(A[o.FOUR], A[o.OPEN3]) > Math.max(A[o.THREE], A[o.OPEN2]) && Math.min(A[o.THREE], A[o.OPEN2]) > A[o.TWO];
  out.shape_values[arm] = { log_att: A, lam: j.lam, order_ok: ok };
}
out.shape_values.teacher = { log_att: T2.ATT.map(v => +Math.log(v + 1).toFixed(3)), note: "老师的手选分值取 ln(分值+1)；这就是阶段一的拟合目标" };
fs.writeFileSync(`${R}/lines_summary.json`, JSON.stringify(out));
console.log("→ results/gomoku/lines_summary.json", Object.keys(out).join(", "));
for (const [arm, v] of Object.entries(out.shape_values)) if (v.order_ok !== undefined)
  console.log(`  ${arm.padEnd(14)} 对数价值按类别：` + T2.NAMES.map((n, k) => `${n} ${v.log_att[k]}`).join("  ") + `   顺序正确：${v.order_ok}`);
