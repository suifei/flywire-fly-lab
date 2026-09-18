// 手写嗅觉导航（非连接组）接进游戏后的检验（设计在运行前写定，全部报告）
// 背景：全脑 LIF 模型里单侧气味刺激没有下行侧化，且 10 Hz 就引发全脑失控（docs/log/report.md 11.4），连接组给不出转向信号。
// 所以这里的“闻着找”完全是手写的：颗粒散发高斯气味场（σ = 15 mm），左右触角（胸部前方 1.0 mm、左右相距 0.6 mm）
// 各采一次浓度，浓度 > 0.01 时按 sign(左 − 右) 以 120°/s 转向（叠加在 DNa 转向上）；已经尝过的颗粒不再吸引。
// 连接组负责的部分不变：头碰到颗粒 → 糖/苦味觉神经元 → MN9 决定吃不吃。
// 设计：每局依次放 6 颗（糖 → 苦 → 混合 ×2），在距果蝇 25 mm、相对朝向 −180°～180° 均匀随机的位置；
//   每颗最多等 20 s，碰到后再等 3 s（或吃完）进入下一颗。3 个种子，嗅觉 开 / 关 两个条件。
// 指标：20 s 内碰到颗粒的比例、碰到所需时间中位、碰到后按类型吃掉的比例。
// 用法：node dodge/odor_v4.js
const fs = require("fs");
const { ConnectomeBrain } = require("./brain.js");
const { createGame } = require("./game_core.js");
const SUB = JSON.parse(fs.readFileSync(__dirname + "/../results/dodge/subcircuit_v2.json", "utf8"));
const CLIPS = JSON.parse(fs.readFileSync(__dirname + "/../results/flight/flight_clips.json", "utf8")).clips;
const ACHE = { gfTau: 0.02, encoding: "ache2019", lplc2Mu: 45, takeoff: "clip" };
const SEEDS = 3, PER = 6, TYPES = ["sugar", "bitter", "mixed"];

function mulberry(seed) {
  let s = seed >>> 0;
  return () => { s = (s + 0x6d2b79f5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

const out = { design: { sigma_mm: 15, turn_deg_s: 120, dist_mm: 25, timeout_s: 20, seeds: SEEDS, per_seed: PER }, conditions: [] };
const t0 = Date.now();
let simS = 0;
for (const odorNav of [false, true]) {
  const trials = [];
  for (let seed = 1; seed <= SEEDS; seed++) {
    const g = createGame(SUB, ConnectomeBrain, { seed: seed * 53, mode: "click", cfg: { ...ACHE, odorNav } });
    g.setFlightClips(CLIPS);
    const rand = mulberry(seed * 977);
    for (let k = 0; k < PER; k++) {
      const type = TYPES[k % 3], S = g.S;
      const a = S.h + (rand() * 2 - 1) * Math.PI;
      const p = g.addPellet(S.x + Math.cos(a) * 25, S.y + Math.sin(a) * 25, type);
      let eaten = false, t = 0, contactT = null;
      g.onEvent = (ev, x) => { if (ev === "eaten" && x.id === p.id) eaten = true; };
      while (t < 20) {
        g.step(); t += g.chunkDt;
        if (p.touched && contactT === null) contactT = t;
        if (eaten || (contactT !== null && t - contactT > 3)) break;
      }
      simS += t;
      g.pellets = g.pellets.filter(q => q.id !== p.id);
      trials.push({ seed, type, contact: contactT !== null, contact_s: contactT, eaten });
    }
  }
  const hit = trials.filter(r => r.contact), ts = hit.map(r => r.contact_s).sort((x, y) => x - y);
  const byType = Object.fromEntries(TYPES.map(ty => { const c = hit.filter(r => r.type === ty); return [ty, { contacts: c.length, eaten: c.filter(r => r.eaten).length }]; }));
  const row = { odorNav, n: trials.length, contact_rate: hit.length / trials.length, contact_s_median: ts.length ? ts[Math.floor(ts.length / 2)] : null, by_type: byType, trials };
  out.conditions.push(row);
  console.log(`嗅觉${odorNav ? "开" : "关"}：20 s 内碰到 ${hit.length}/${trials.length}，用时中位 ${row.contact_s_median === null ? "—" : row.contact_s_median.toFixed(1) + " s"}；` +
    TYPES.map(ty => `${ty} 吃掉 ${byType[ty].eaten}/${byType[ty].contacts}`).join("，"));
}
fs.writeFileSync(__dirname + "/../results/dodge/odor_v4.json", JSON.stringify(out, null, 1));
console.log(`仿真 ${simS.toFixed(0)} s，用时 ${((Date.now() - t0) / 1000).toFixed(0)} s`);
