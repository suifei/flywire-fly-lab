// JS 引擎 vs Python 参考实现：同样刺激、4 个 trial × 0.5 s，比较目标下行神经元平均发放率
const fs = require("fs");
const { ConnectomeBrain } = require("./brain.js");
const data = JSON.parse(fs.readFileSync(__dirname + "/../results/dodge/subcircuit.json", "utf8"));
const TG = ["DNa01_left", "DNa01_right", "DNa02_left", "DNa02_right", "DNp01_left", "DNp01_right"];
const CONDS = { LC4_L_100: { LC4_left: 100 }, LPLC2_L_100: { LPLC2_left: 100 }, LOOM_L_100: { LC4_left: 100, LPLC2_left: 100 },
  LOOM_R_100: { LC4_right: 100, LPLC2_right: 100 }, LOOM_L_40: { LC4_left: 40, LPLC2_left: 40 } };
const val = Object.fromEntries(data.validation.map(r => [r.cond, r]));
const steps = 5000, trials = 4;
let t0 = Date.now(), totalSteps = 0;
for (const [name, rates] of Object.entries(CONDS)) {
  const acc = Object.fromEntries(TG.map(k => [k, 0]));
  for (let tr = 0; tr < trials; tr++) {
    const b = new ConnectomeBrain(data, 1000 + tr);
    for (const [g, hz] of Object.entries(rates)) b.setRate(g, hz);
    b.run(steps); totalSteps += steps;
    const r = b.readRates(TG, steps);
    TG.forEach(k => acc[k] += r[k] / trials);
  }
  const s = k => k.replace("_left", "L").replace("_right", "R");
  console.log(`${name.padEnd(12)} JS  ` + TG.map(k => `${s(k)}=${acc[k].toFixed(1).padStart(6)}`).join(" "));
  console.log(`${"".padEnd(12)} PY  ` + TG.map(k => `${s(k)}=${val[name]["sub_" + k].toFixed(1).padStart(6)}`).join(" "));
  console.log(`${"".padEnd(12)} 全脑 ` + TG.map(k => `${s(k)}=${val[name]["ref_" + k].toFixed(1).padStart(6)}`).join(" "));
}
const sec = (Date.now() - t0) / 1000;
console.log(`\nJS 速度：${totalSteps} 步 / ${sec.toFixed(1)} s = ${(totalSteps / sec).toFixed(0)} 步/秒（实时需要 10000 步/秒，单线程 node）`);
