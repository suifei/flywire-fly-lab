#!/usr/bin/env node
// 生态箱 → 3D 大自然：迁移实测。用法：
//   for s in 901 902 903 904 905; do for a in naive trained; do node eco/nature_harness.js run $a $s 900 & done; done; wait     （真脑，每条 ~15 min，10 条可并行）
//   node eco/nature_transfer.js                                                                                              → results/eco/nature_transfer.json；判据没过退出码 2
//
// **事先写定**（写在跑之前）：5 个大自然世界种子（901–905，与采工况用的 811–813 不重叠），每条命上限 900 s，真脑（15,055 个脉冲神经元）+ dodge/nature.js 的世界。
//   两个臂用同一个世界种子：naive = 白纸、不学；trained = 生态箱 M2 学成的那个个体的权重（results/eco/m2_champion.json），**冻结**，不在大自然里再学。
//   「有信息的种子」= 至少一个臂碰到过水（两个臂都没碰到水的种子什么也说明不了，单列、不计入分母）；有信息的种子少于 3 个 = 没有结论。
//   X1  在有信息的种子里，trained 喝水的总时间多于 naive 的占 ≥ 80%，且 trained「每次碰到水喝几次」的中位数 ≥ 3 × naive（naive 为 0 时 trained > 0 即可）
//   X2  在有信息的种子里，trained 的平均口渴低于 naive 的占 ≥ 80%
//   只报告：寿命（900 s 截尾）、死因、吃的时间、被撞次数、走的路程
const fs = require("fs"), path = require("path"), ROOT = path.resolve(__dirname, ".."), D = path.join(ROOT, "results/eco"), SEEDS = [901, 902, 903, 904, 905], med = a => { a = a.slice().sort((x, y) => x - y); const n = a.length; return n ? (n % 2 ? a[n >> 1] : (a[n / 2 - 1] + a[n / 2]) / 2) : null; };
const rows = []; for (const seed of SEEDS) { const r = {}; for (const arm of ["naive", "trained"]) { const f = path.join(D, `nature_run_${arm}_${seed}.json`); if (!fs.existsSync(f)) { console.error("缺", f); process.exit(1); } r[arm] = JSON.parse(fs.readFileSync(f, "utf8")); } rows.push({ seed, naive: r.naive, trained: r.trained, informative: r.naive.waterVisits + r.trained.waterVisits > 0 }); }
const inf = rows.filter(r => r.informative), per = a => a.waterVisits ? a.drinks / a.waterVisits : 0, nMore = inf.filter(r => r.trained.drink_s > r.naive.drink_s).length, nThirst = inf.filter(r => r.trained.thirst_mean < r.naive.thirst_mean).length;
const pvT = med(inf.map(r => per(r.trained))), pvN = med(inf.map(r => per(r.naive))), enough = inf.length >= 3;
const out = { protocol: { seeds: SEEDS, cap_s: 900, brain: "live v5", champion: "results/eco/m2_champion.json（冻结）" }, runs: rows, n_informative: inf.length, conclusive: enough,
  X1: { more_drink_time: `${nMore}/${inf.length}`, drinks_per_visit_trained: pvT, drinks_per_visit_naive: pvN, pass: enough && nMore >= 0.8 * inf.length && (pvN > 0 ? pvT >= 3 * pvN : pvT > 0) },
  X2: { lower_mean_thirst: `${nThirst}/${inf.length}`, pass: enough && nThirst >= 0.8 * inf.length },
  report: { life_naive: med(rows.map(r => r.naive.life_s)), life_trained: med(rows.map(r => r.trained.life_s)), drink_s_naive: med(rows.map(r => r.naive.drink_s)), drink_s_trained: med(rows.map(r => r.trained.drink_s)), thirst_naive: med(rows.map(r => r.naive.thirst_mean)), thirst_trained: med(rows.map(r => r.trained.thirst_mean)),
    eat_s_naive: med(rows.map(r => r.naive.eat_s)), eat_s_trained: med(rows.map(r => r.trained.eat_s)), alive_naive: rows.filter(r => r.naive.alive).length, alive_trained: rows.filter(r => r.trained.alive).length } };
out.pass = out.X1.pass && out.X2.pass; fs.writeFileSync(path.join(D, "nature_transfer.json"), JSON.stringify(out, null, 1));
for (const r of rows) console.log(`种子 ${r.seed}${r.informative ? "" : "（没碰到水，不计）"}: 白纸 喝 ${r.naive.drink_s} s / 碰水 ${r.naive.waterVisits} 次 / 平均口渴 ${r.naive.thirst_mean} / 活 ${r.naive.life_s} s   学成 喝 ${r.trained.drink_s} s / 碰水 ${r.trained.waterVisits} 次 / 平均口渴 ${r.trained.thirst_mean} / 活 ${r.trained.life_s} s`);
console.log(`X1 ${out.X1.pass ? "通过" : "未通过"}（喝得更久 ${out.X1.more_drink_time}；每次碰到水喝 ${pvT} 对 ${pvN} 次）  X2 ${out.X2.pass ? "通过" : "未通过"}（更不渴 ${out.X2.lower_mean_thirst}）  ${enough ? "" : "有信息的种子不足 3 个：没有结论"}`); process.exit(out.pass ? 0 : 2);
