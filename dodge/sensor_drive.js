#!/usr/bin/env node
/**
 * 子回路里每一路感觉输入，到底能不能驱动运动输出？——「给了物理量」不等于「有落点」。
 *
 * 起因：按「只给物理量、不写判断逻辑」这条原则加了触感、温度、湿度之后，必须先回答
 * 每一路在**这个裁出来的子回路里**能不能真的推动 DNa（转向）/ DNp01（逃逸）/ MDN（后退）/
 * MN9（伸喙）/ aDN1（梳理）。全脑里 2–3 跳可达（dodge/sensor_reach.py）**不等于**
 * 裁剪之后还留着足够的通路。
 *
 * 做法：每一路输入组单独给固定频率跑 1 s，量六个读出组的平均发放率。
 * 单侧与双侧分开测——双侧对称驱动会把左右差抵消掉，**这本身就是结果**。
 *
 * 用法：node dodge/sensor_drive.js [子回路=subcircuit_v3]
 * 输出：results/dodge/sensor_drive.json
 */
const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "..");
const { ConnectomeBrain } = require("./brain.js");
const NAME = process.argv[2] || "subcircuit_v3";
const SUB = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge", NAME + ".json"), "utf8"));
const READ = ["DNa01_left", "DNa01_right", "DNa02_left", "DNa02_right", "DNp01_left", "DNp01_right",
              "MDN_left", "MDN_right", "aDN1_left", "aDN1_right", "MN9_left", "MN9_right"];
const HZ = [100, 200, 400, 600];
const inputs = Object.keys(SUB.meta.inputs || {});

function drive(groups, hz) {
  const b = new ConnectomeBrain(SUB, 7);
  for (const g of groups) if (SUB.groups[g]) b.setRate(g, hz);
  const cnt = new Float32Array(b.n);
  b.run(Math.round(1000 / b.dt), i => { cnt[i]++; });
  const out = {};
  for (const g of READ) {
    const idx = SUB.groups[g] || [];
    out[g] = idx.length ? +(idx.reduce((a, i) => a + cnt[i], 0) / idx.length).toFixed(1) : null;
  }
  out._active = cnt.reduce((a, v) => a + (v > 0 ? 1 : 0), 0);
  return out;
}

const out = { subcircuit: NAME, n: SUB.meta.n, freqs: HZ,
  note: "每一路输入组单独驱动 1 s，量六个读出组的平均 Hz。判「有落点」= 任一读出组 > 5 Hz。",
  inputs: {} };
const SHORT = g => g.replace("_left", "L").replace("_right", "R");
console.log(`${NAME}：${SUB.meta.n} 神经元，输入组 ${inputs.length} 个\n`);
console.log(`${"输入".padEnd(10)}${"侧".padEnd(6)}${"Hz".padStart(5)}${"活跃".padStart(7)}   驱动到的读出组`);
for (const g of inputs) {
  const rec = { n_left: (SUB.groups[g + "_left"] || []).length, n_right: (SUB.groups[g + "_right"] || []).length, runs: [] };
  for (const side of ["left", "both"]) {
    const groups = side === "left" ? [g + "_left"] : [g + "_left", g + "_right"];
    for (const hz of HZ) {
      const r = drive(groups, hz);
      const hits = READ.filter(k => (r[k] || 0) > 5);
      rec.runs.push({ side, hz, active: r._active, rates: r, hits });
      console.log(`${g.padEnd(10)}${(side === "left" ? "单侧" : "双侧").padEnd(6)}${String(hz).padStart(5)}${String(r._active).padStart(7)}   ` +
        (hits.length ? hits.map(k => SHORT(k) + " " + r[k]).join("  ") : "—"));
    }
  }
  rec.lands = rec.runs.some(x => x.hits.length > 0);
  rec.lands_at_200 = rec.runs.some(x => x.hz <= 200 && x.hits.length > 0);
  out.inputs[g] = rec;
}
const ok = Object.entries(out.inputs).filter(([, v]) => v.lands_at_200).map(([k]) => k);
const weak = Object.entries(out.inputs).filter(([, v]) => v.lands && !v.lands_at_200).map(([k]) => k);
const none = Object.entries(out.inputs).filter(([, v]) => !v.lands).map(([k]) => k);
out.summary = { lands_at_200: ok, only_at_high_rate: weak, no_landing: none };
console.log(`\n≤200 Hz 就有落点：${ok.join("、") || "（无）"}`);
console.log(`只有高频才有落点：${weak.join("、") || "（无）"}`);
console.log(`完全没有落点：    ${none.join("、") || "（无）"}`);
fs.writeFileSync(ROOT + "/results/dodge/sensor_drive.json", JSON.stringify(out, null, 1));
console.log("→ results/dodge/sensor_drive.json");
