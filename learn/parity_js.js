#!/usr/bin/env node
// 页面引擎（dodge/brain.js + dodge/plasticity.js）与 Python（learn/lif.py + learn/plasticity.py）在同一份 v5 子回路上跑同一个条件化流程。
// 两边随机数不同，所以比的是统计量。Python 那一半在 learn/parity_py.py；两边都写进 results/learn/parity_{js,py}.json，由 parity_py.py compare 判。
const fs = require("fs"), path = require("path"), ROOT = path.resolve(__dirname, "..");
const { ConnectomeBrain } = require("../dodge/brain.js"), Plast = require("../dodge/plasticity.js");
const SUB = JSON.parse(fs.readFileSync(path.join(ROOT, "results/dodge/subcircuit_v5.json"), "utf8")), proto = JSON.parse(fs.readFileSync(path.join(ROOT, "results/learn/parity_protocol.json"), "utf8"));
const out = { seeds: proto.seeds, runs: [] }, t0 = Date.now();
for (const seed of proto.seeds) for (const cond of ["mock", "paired"]) {
  const brain = new ConnectomeBrain(SUB, seed); brain.sparse = process.env.DENSE !== "1"; const pl = Plast.create(SUB, brain, { eta: proto.eta, tauE: proto.tau_e_ms }), n = SUB.meta.n;
  const idxOf = gl => gl.flatMap(g => SUB.meta.glomeruli[g]), A = idxOf(proto.A), B = idxOf(proto.B), dan = [...SUB.groups[proto.dan + "_left"], ...SUB.groups[proto.dan + "_right"]];
  // 气味直接按神经元下标驱动（走 drive 通道：DM1 / DA2 的 ORN 在 OLFA / OLFR 组里，其余在 ORN 组里，统一用下标最省事）
  const present = (odor, da, ms, learn) => {
    brain.setDrive("odor", odor, odor ? proto.odor_hz : 0); brain.setDrive("dan", da ? dan : null, da ? proto.dan_hz : 0);
    const tot = new Float64Array(n);
    for (let k = 0; k < ms / 10; k++) { brain.run(100, i => { tot[i]++; if (learn) pl.spike(i); }); if (learn) pl.step(10); }
    return tot;
  };
  for (let r = 0; r < proto.reps; r++) { present(A, cond === "paired", 1000, true); present(null, false, 500, true); present(B, false, 1000, true); present(null, false, 500, true); }
  present(null, false, 1000, false); const ta = present(A, false, 1000, false); present(null, false, 1000, false); const tb = present(B, false, 1000, false);
  out.runs.push({ seed, cond, mbon_A: pl.mbonIdx.map(i => ta[i]), mbon_B: pl.mbonIdx.map(i => tb[i]), kc_active_A: pl.kcIdx.filter(i => ta[i] > 0).length, kc_active_B: pl.kcIdx.filter(i => tb[i] > 0).length, strength: pl.strength() });
  console.log(`seed ${seed} ${cond}: MBON A ${ta.reduce((s, x, i) => s + (SUB.mb_tag[i] === "MBON" ? x : 0), 0)} B ${tb.reduce((s, x, i) => s + (SUB.mb_tag[i] === "MBON" ? x : 0), 0)}  (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
}
out.seconds = (Date.now() - t0) / 1000; out.sim_seconds_per_run = proto.reps * 3 + 4;
fs.writeFileSync(path.join(ROOT, "results/learn/parity_js.json"), JSON.stringify(out));
