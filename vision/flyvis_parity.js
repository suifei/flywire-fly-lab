#!/usr/bin/env node
/**
 * JS 的 flyvis 前向必须和 Python 逐值对上 —— 和 dodge/parity_test.js 同一条规矩。
 *
 * 不做这个验证，后面"果蝇画出来的图"只是个看起来像那么回事的近似，
 * 而且错了也不会有任何报错。
 *
 * 用法：
 *   conda activate fba && python vision/flyvis_parity.py   # 先生成参考
 *   node vision/flyvis_parity.js
 */
const fs = require("fs");
const path = require("path");
const FlyVis = require("./flyvis.js");

const ROOT = path.resolve(__dirname, "..");
const NET = path.join(ROOT, "results/vision/flyvis_net.json");
const REF = path.join(ROOT, "results/vision/flyvis_parity.json");

for (const f of [NET, REF]) {
  if (!fs.existsSync(f)) {
    console.error(`缺少 ${f}\n先跑：conda activate fba && python vision/export_flyvis_js.py && python vision/flyvis_parity.py`);
    process.exit(1);
  }
}

const ref = JSON.parse(fs.readFileSync(REF, "utf8"));
const net = FlyVis.load(fs.readFileSync(NET, "utf8"));

console.log(`网络：${net.types.length} 类型，${net.nTaps} 个卷积抽头`);
console.log(`参考：${ref.n_frames} 帧，dt=${ref.dt}，初态=${ref.initial_state}，探针 ${ref.probe.join(" ")}`);

net.reset();
const got = {};
for (const t of ref.probe) got[t] = [];
for (let f = 0; f < ref.n_frames; f++) {
  net.step(ref.movie[f], ref.dt);
  for (const t of ref.probe) got[t].push(Array.from(net.get(t)));
}

let worst = 0, worstAt = "";
let fail = 0;
console.log(`\n${"类型".padEnd(7)}${"最大绝对差".padStart(12)}${"相对".padStart(10)}   末帧 JS / Python`);
for (const t of ref.probe) {
  const exp = ref.activity[t];
  let mx = 0, scale = 0, at = "";
  for (let f = 0; f < ref.n_frames; f++) {
    for (let j = 0; j < exp[f].length; j++) {
      const d = Math.abs(got[t][f][j] - exp[f][j]);
      scale = Math.max(scale, Math.abs(exp[f][j]));
      if (d > mx) { mx = d; at = `帧${f} 柱${j}`; }
    }
  }
  const rel = mx / Math.max(scale, 1e-12);
  if (rel > worst) { worst = rel; worstAt = `${t} ${at}`; }
  const ok = rel < 1e-5;
  if (!ok) fail++;
  const lastJs = got[t][ref.n_frames - 1][0], lastPy = exp[ref.n_frames - 1][0];
  console.log(`${t.padEnd(7)}${mx.toExponential(2).padStart(12)}${rel.toExponential(2).padStart(10)}` +
              `   ${lastJs.toFixed(6)} / ${lastPy.toFixed(6)}  ${ok ? "✓" : "✗"}`);
}

console.log();
if (fail === 0) {
  console.log(`✓ 全部对上（最大相对差 ${worst.toExponential(2)}，出现在 ${worstAt}）`);
  console.log("  JS 跑的就是 Python 那套权重和方程，不是近似。");
} else {
  console.log(`✗ ${fail}/${ref.probe.length} 个类型对不上（最大相对差 ${worst.toExponential(2)} @ ${worstAt}）`);
  console.log("  常见原因：欧拉步的写法、du/dv 方向、输入进哪些感受器、柱排序");
  process.exit(1);
}
