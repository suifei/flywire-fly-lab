#!/usr/bin/env node
/**
 * 把每个棋局位置送进果蝇脑，导出下游神经元的发放计数矩阵。
 *
 * **特征里不包含输入神经元本身**——它们的发放率就是棋盘的直接拷贝，
 * 留着的话读出层等于没经过脑子，对照就失去意义了。
 *
 * 两个臂：
 *   intact    真实 FlyWire 连接组
 *   shuffled  打乱接线（保每个神经元的出度与权重，只重排靶点；与论文补充表 1D 的对照同一套做法）
 *
 * 用法：node gomoku/extract_features.js intact|shuffled [hz=400] [ms=100]
 * 输出：results/gomoku/feat_<arm>.bin（float32，行 = 局面，列 = 下游神经元）+ feat_<arm>.json（元信息）
 */
const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "..");
const SUF = (process.env.SUB && process.env.SUB !== "subcircuit_v2") ? "_" + process.env.SUB.replace("subcircuit_", "") : "";
const G = require("./rules.js");
const F = require("./features.js");
const { ConnectomeBrain } = require(ROOT + "/dodge/brain.js");
const ARM = process.argv[2] || "intact";          // intact | shuffled | topo（真实接线 + 保拓扑编码）
const HZ = +(process.argv[3] || 400), MS = +(process.argv[4] || 100);
const SUB = JSON.parse(fs.readFileSync(ROOT + "/results/dodge/" + (process.env.SUB || "subcircuit_v2") + ".json", "utf8"));
const DS = JSON.parse(fs.readFileSync(ROOT + "/results/gomoku/dataset.json", "utf8"));

const brain = new ConnectomeBrain(SUB, 11);
if (ARM === "shuffled") brain.setShuffle(true, 20260919);
const map = ARM === "topo"
  ? F.makeTopoMap(SUB, JSON.parse(fs.readFileSync(ROOT + "/results/dodge/soma.json", "utf8")))
  : F.makeMap(SUB);
if (map.topo) console.log(`保拓扑编码：每格 ${map.perCell} 个神经元（按真实胞体位置的二维扫描序分配）`);
const isIn = new Uint8Array(SUB.meta.n); map.inputs.forEach(i => { isIn[i] = 1; });
const cols = []; for (let i = 0; i < SUB.meta.n; i++) if (!isIn[i]) cols.push(i);
console.log(`${ARM}：${DS.n} 个局面 × ${cols.length} 个下游神经元（总 ${SUB.meta.n}，剔除 ${map.inputs.length} 个输入）`);

const buf = Buffer.alloc(DS.n * cols.length * 4);
const t0 = Date.now();
for (let s = 0; s < DS.n; s++) {
  const smp = DS.samples[s];
  const bd = new Uint8Array(Buffer.from(smp.board, "base64"));
  // 固定种子：同一个局面永远给出同一份特征（水库必须是确定性函数，否则读出层在拟合噪声）
  const cnt = F.featuresOf(brain, map, bd, smp.me, { hz: HZ, ms: MS, seed: 777 });
  for (let k = 0; k < cols.length; k++) buf.writeFloatLE(cnt[cols[k]], (s * cols.length + k) * 4);
  if (s % 500 === 0) process.stdout.write(`\r  ${s}/${DS.n}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
}
fs.writeFileSync(ROOT + `/results/gomoku/feat_${ARM}${SUF}.bin`, buf);
fs.writeFileSync(ROOT + `/results/gomoku/feat_${ARM}${SUF}.json`, JSON.stringify(
  { arm: ARM, hz: HZ, ms: MS, rows: DS.n, cols: cols.length, col_idx: cols,
    n_inputs_excluded: map.inputs.length, seconds: +((Date.now() - t0) / 1000).toFixed(1) }, null, 1));
console.log(`\n→ results/gomoku/feat_${ARM}${SUF}.bin （${(buf.length / 1e6).toFixed(1)} MB，${((Date.now() - t0) / 1000).toFixed(0)} s）`);
