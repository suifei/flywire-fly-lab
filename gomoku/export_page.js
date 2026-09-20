#!/usr/bin/env node
/**
 * 页面要用的五子棋数据 → results/gomoku/page_tables.json。只读、只搬运，不算任何新数字。
 *   black  黑蝇：完整的表 + 读出权重（页面现场在真脑里重跑核对用）
 *   white  白蝇：**同一套读出权重**，但表来自另一组泊松种子的试次平均——
 *          同一份接线、同一个读出层，只是"另一只个体"的放电。所以两只偶尔会选不同的点。
 * 页面不带 codes 数组（90 KB）：顺序就是 lines.js 的 allCodes()，这里断言一致。
 */
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, ".."), R = ROOT + "/results/gomoku";
const L = require("./lines.js");
const j = JSON.parse(fs.readFileSync(`${R}/linetable_fly_intact.json`, "utf8"));
const codes = Array.from(L.allCodes());
if (JSON.stringify(codes) !== JSON.stringify(j.codes)) throw new Error("表的线型顺序与 allCodes() 不一致");
const pick = (o, ks) => Object.fromEntries(ks.filter(k => o[k] !== undefined).map(k => [k, o[k]]));
const black = pick(j, ["arm", "form", "lam", "bias", "att", "deff", "w_a", "mu", "sd", "keep", "hz", "ms", "bins", "views", "seeds", "label_depth", "test_top1"]);
const out = { black };
const wf = `${R}/linetable_fly_intact_white.json`;
if (fs.existsSync(wf)) { const w = JSON.parse(fs.readFileSync(wf, "utf8")); out.white = pick(w, ["att", "deff", "seeds"]); }
// 强化版的表只有在它**通过了事先写好的判据**时才进页面（rl.json 的 criterion_passed）
const rl = `${R}/linetable_fly_intact_rl.json`, rlRes = fs.existsSync(`${R}/rl.json`) ? JSON.parse(fs.readFileSync(`${R}/rl.json`, "utf8")) : null;
if (fs.existsSync(rl) && rlRes && rlRes.criterion_passed) { const w = JSON.parse(fs.readFileSync(rl, "utf8")); out.rl = pick(w, ["att", "deff", "lam", "w_a", "bias"]); }
// 「推理 N 步」的模型：每个 N 一个读出层（同一颗脑子、同一套特征）。页面的「推理步数」选的就是用哪一个。
// 白蝇用同一个读出层、另一组泊松种子的表（att_white）。mu / sd / keep / views 各模型共用，放在 black 里。
const dm = fs.existsSync(`${R}/depth_models_train.json`) ? JSON.parse(fs.readFileSync(`${R}/depth_models_train.json`, "utf8")) : null;
if (dm) { out.depths = {};
  for (const d of dm.labels) { const j2 = JSON.parse(fs.readFileSync(`${R}/linetable_fly_intact_d${d}.json`, "utf8"));
    if (JSON.stringify(j2.keep) !== JSON.stringify(j.keep)) throw new Error(`推理 ${d} 步的模型与主表的特征列不一致`);
    out.depths[d] = { label_depth: d, lam: j2.lam, bias: j2.bias, att: j2.att, w_a: j2.w_a, att_white: j2.att_white, seeds: j2.seeds, seeds_white: j2.seeds_white,
                      agree_depth8: dm.models[d].agree_depth8, agree_own_label: dm.models[d].agree_own_label }; } }
fs.writeFileSync(`${R}/page_tables.json`, JSON.stringify(out));
console.log(`→ page_tables.json  ${(fs.statSync(`${R}/page_tables.json`).size / 1024).toFixed(0)} KB  （黑蝇种子 ${black.seeds}；白蝇 ${out.white ? out.white.seeds : "无 → 与黑蝇同表"}）`);
