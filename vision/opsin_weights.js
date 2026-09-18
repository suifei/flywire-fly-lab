#!/usr/bin/env node
/** 生成 results/vision/opsin_weights.json —— 页面和报告里的权重数字都从这里来，不手抄。 */
const fs = require("fs"), path = require("path");
const O = require(path.join(__dirname, "opsins.js"));
const out = {
  来源: "Govardovskii et al. 2000 A1 视色素模板（α 带 + β 带），逐 1 nm 积分 300–700 nm",
  波段: O.BANDS,
  假设: [
    "场景是 sRGB 著作的，没有真实光谱：把渲染出的三个通道当成各自波段内的平均反射率【推测】",
    "光源按等能白（平谱）处理【推测】",
    "红端没有第四个通道（果蝇也无红受体），600–700 nm 并入绿带",
  ],
  增感色素: Object.assign({ 说明: "果蝇 R1–6 的 3-羟基视黄醇增感色素在 ~350 nm 给第二个峰，不在 Govardovskii 模板里；幅度是手选的【推测】" }, O.SENS),
  视蛋白: O.OPSINS,
  权重: { 无增感色素: O.weights(false), 有增感色素: O.weights(true) },
};
const f = path.join(__dirname, "..", "results/vision/opsin_weights.json");
fs.writeFileSync(f, JSON.stringify(out, null, 1));
console.log("写入 " + f);
console.log("视蛋白  细胞    λmax   紫外300-400  蓝400-500  绿500-700");
for (const [k, v] of Object.entries(out.权重.有增感色素))
  console.log(k.padEnd(7) + O.OPSINS[k].cells.padEnd(7) + String(O.OPSINS[k].lmax).padStart(4)
    + v.U.toFixed(3).padStart(12) + v.B.toFixed(3).padStart(11) + v.G.toFixed(3).padStart(11));
