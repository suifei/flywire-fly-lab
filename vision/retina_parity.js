#!/usr/bin/env node
/** 视网膜采样：JS 必须和 Python 逐值对上。 */
const fs = require("fs"), path = require("path");
const Retina = require("./retina.js");
const ROOT = path.resolve(__dirname, "..");
const P = f => path.join(ROOT, "results/vision", f);

for (const f of ["retina.json", "retina_map.bin", "retina_parity.json"]) {
  if (!fs.existsSync(P(f))) {
    console.error(`缺少 ${P(f)}\n先跑：conda activate fba && python vision/export_retina_js.py && python vision/retina_parity.py`);
    process.exit(1);
  }
}
const meta = JSON.parse(fs.readFileSync(P("retina.json"), "utf8"));
const ref = JSON.parse(fs.readFileSync(P("retina_parity.json"), "utf8"));
const r = Retina.fromBuffer(fs.readFileSync(P("retina_map.bin")), meta);

const n = r.w * r.h;
const frame = new Float64Array(n);
for (let i = 0; i < n; i++) frame[i] = ((i * 2654435761) % 65536) / 65536;
const got = r.sample(frame);

let mx = 0, at = -1;
for (let j = 0; j < got.length; j++) {
  const d = Math.abs(got[j] - ref.hex[j]);
  if (d > mx) { mx = d; at = j; }
}
console.log(`画面 ${r.w}×${r.h} → ${got.length} 个小眼`);
console.log(`最大绝对差 ${mx.toExponential(2)}（第 ${at} 柱）`);
if (mx < 1e-12) {
  console.log("✓ 视网膜采样与 Python 完全一致");
} else {
  console.log("✗ 对不上 —— 检查 idmap 解析、每小眼像素数、flygym→flyvis 排列");
  process.exit(1);
}
