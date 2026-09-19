#!/usr/bin/env node
/**
 * 让果蝇脑把**每一种**线型都跑一遍，导出下游神经元的发放计数（水库特征）。
 *
 * 输入：线型的 8 个格子 × {我方, 对方, 边界} = 24 个通道，每个通道固定分到约 61 个真实感觉神经元
 *      （分配表由固定种子打乱得到——映射是任意的，我们不假装果蝇"看得懂"棋子）。
 * 输出：**不含输入神经元**的下游发放计数，分 BINS 个时间窗（时间窗让读出层能用上响应的先后）。
 * 脑子里一个突触都不训练；随机流每次重播（reseed），所以"线型 → 特征"是一个确定性函数。
 *
 * 臂：intact 真实连接组 ｜ shuffled 打乱接线（保出度与权重，只重排靶点）
 *
 * 用法：SEED=777 node gomoku/line_features.js intact|shuffled [hz=160] [ms=60] [bins=2] [limit]
 * 输出：results/gomoku/linefeat_<arm>_s<seed>.bin（uint8，行 = 线型，列 = 下游神经元 × 时间窗）+ .json
 */
const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "..");
const L = require("./lines.js");
const LF = require("./line_map.js");
const { ConnectomeBrain } = require(ROOT + "/dodge/brain.js");
const ARM = process.argv[2] || "intact";
const HZ = +(process.argv[3] || 160), MS = +(process.argv[4] || 60), BINS = +(process.argv[5] || 2);
const LIMIT = process.argv[6] ? +process.argv[6] : null;
const SUBNAME = process.env.SUB || "subcircuit_v3";
const VIEW = +(process.env.VIEW || 1);             // 视角 = 「24 个通道 → 输入神经元」的分配表。视角 1 是原来那张；其余换一个洗牌种子
const SEED = +(process.env.SEED || 777);            // 泊松随机流的种子；训练用 777/778，留 779 只做测试
const SUB = JSON.parse(fs.readFileSync(ROOT + "/results/dodge/" + SUBNAME + ".json", "utf8"));

const brain = new ConnectomeBrain(SUB, 11);
if (ARM === "shuffled") brain.setShuffle(true, 20260919);
const map = LF.makeLineMap(SUB, LF.viewSeed(VIEW));
const codes = LIMIT ? L.allCodes().filter((_, i, a) => i % Math.floor(a.length / LIMIT) === 0).slice(0, LIMIT) : L.allCodes();
const cols = map.downstream;
const D = cols.length * BINS;
console.log(`${ARM}：${codes.length} 种线型 × ${cols.length} 个下游神经元 × ${BINS} 个时间窗（每通道 ${map.perChannel} 个输入神经元）`);

const buf = Buffer.alloc(codes.length * D);
let sat = 0;
const t0 = Date.now();
for (let s = 0; s < codes.length; s++) {
  const cnt = LF.lineFeatures(brain, map, codes[s], { hz: HZ, ms: MS, bins: BINS, seed: SEED });
  for (let k = 0; k < D; k++) { let v = cnt[k]; if (v > 255) { v = 255; sat++; } buf[s * D + k] = v; }
  if (s % 500 === 0) process.stdout.write(`\r  ${s}/${codes.length}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
}
const secs = (Date.now() - t0) / 1000;
const vb = (VIEW === 1 && BINS === 1) ? "" : `_v${VIEW}b${BINS}`;          // 视角 1 + 单时间窗保持原文件名
const tag = LIMIT ? `_probe_${MS}ms_s${SEED}` : `${vb}_s${SEED}`;
fs.writeFileSync(ROOT + `/results/gomoku/linefeat_${ARM}${tag}.bin`, buf);
fs.writeFileSync(ROOT + `/results/gomoku/linefeat_${ARM}${tag}.json`, JSON.stringify(
  { arm: ARM, subcircuit: SUBNAME, view: VIEW, seed: SEED, hz: HZ, ms: MS, bins: BINS, rows: codes.length, cols: D, n_downstream: cols.length,
    codes: Array.from(codes), col_idx: cols, per_channel: map.perChannel, saturated_cells: sat,
    seconds: +secs.toFixed(1), ms_per_pattern: +(secs * 1000 / codes.length).toFixed(2) }));
console.log(`\n→ linefeat_${ARM}${tag}.bin  ${(buf.length / 1e6).toFixed(1)} MB，${secs.toFixed(0)} s（每种 ${(secs * 1000 / codes.length).toFixed(1)} ms），饱和格 ${sat}`);
