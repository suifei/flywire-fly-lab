// 生态箱 M4：存档。保存的对象是一份**可发布的训练成果**（Experiment）：世界规则 + 世代记录 + 代表个体 + 发现卡 + 能接着跑的完整状态。
//   snapshot(E) → 纯 JSON（Float64Array 等带标记保存；函数不存，读回来再挂）；restore(json, brain) → 接着跑，**逐位相同**（eco/m4_save_test.js 验证）。
//   challenge(E) → 一段短的挑战码（只有世界规则 + 种子 + 可选的冠军基因），别人贴进来就能在同一个世界里开局。
(function (root) {
  const N = typeof module !== "undefined" && module.exports, World = N ? require("./world.js") : root.EcoWorld, Evolve = N ? require("./evolve.js") : root.EcoEvolve, Sim = N ? require("./sim.js") : root.EcoSim;
  const VERSION = 1, SKIP = new Set(["_v", "reborn", "rand", "brain", "onFood", "onWater", "bite", "listeners", "events", "step", "run", "emit", "on", "spawn", "opts", "cfg", "sim"]);
  function enc(v) { if (v === null || v === undefined) return null; if (v instanceof Float64Array) return { __f64: Array.from(v) }; if (v instanceof Float32Array) return { __f32: Array.from(v) }; if (Array.isArray(v)) return v.map(enc); if (typeof v === "function") return undefined;
    if (typeof v === "object") { const o = {}; for (const k in v) { if (SKIP.has(k)) continue; const e = enc(v[k]); if (e !== undefined) o[k] = e; } return o; } return v; }
  function dec(v) { if (v === null || typeof v !== "object") return v; if (v.__f64) return Float64Array.from(v.__f64); if (v.__f32) return Float32Array.from(v.__f32); if (Array.isArray(v)) return v.map(dec); const o = {}; for (const k in v) o[k] = dec(v[k]); return o; }
  function encWorld(W) { const o = {}; for (const k in W) if (typeof W[k] !== "function") o[k] = enc(W[k]); return o; }
  function snapshot(E, meta) { const sim = E.sim, W = sim.world; return { format: "fly-ecobox", version: VERSION, meta: Object.assign({ savedAt: null, title: "" }, meta || {}), rules: W.rules, seed: W.seed, simOpts: { dt: sim.dt, learn: sim.opts.learn, flight: sim.opts.flight, seed: sim.opts.seed },
      world: encWorld(W), agents: sim.agents.map(enc), nextId: sim.nextId, evolve: enc({ timeline: E.timeline, replays: E.replays, cards: E.cards, hall: E.hall, lives: E.lives, births: E.births, immigrants: E.immigrants, nextGenome: E.nextGenome, bin: E.bin, founder: E.founder, oldest: E.oldest || null, oldestShown: E.oldestShown || 0, flight: E.flight, solo: !!E.solo, lifeLog: E.lifeLog || [] }) }; }
  function restore(S, brain) { if (!S || S.format !== "fly-ecobox") throw new Error("不是生态箱存档"); if (S.version > VERSION) throw new Error("存档版本比页面新");
    const sim = Sim.create(S.rules, Object.assign({}, S.simOpts, { brain })), W = sim.world; const data = dec(S.world); for (const k in data) W[k] = data[k]; World.attach(W);
    sim.agents = S.agents.map(a => { const o = dec(a); o.onFood = null; o.onWater = null; o.bite = null; o.rand = () => { o.rs = (o.rs + 0x6d2b79f5) >>> 0; let t = o.rs; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; return o; }); sim.nextId = S.nextId;
    const E = Object.assign({ sim, cfg: Evolve.CFG }, dec(S.evolve)); if (!E.oldest) delete E.oldest; Evolve.attach(E); return E; }
  // 状态指纹：比较两份运行是否逐位相同（FNV-1a over JSON）
  function fingerprint(E) { const s = JSON.stringify(snapshot(E, { savedAt: null })); let h = 0x811c9dc5; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193); } return (h >>> 0).toString(16).padStart(8, "0") + ":" + s.length; }
  const b64 = { enc: s => (typeof Buffer !== "undefined" ? Buffer.from(s, "utf8").toString("base64") : btoa(unescape(encodeURIComponent(s)))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, ""),
    dec: s => { s = s.replace(/-/g, "+").replace(/_/g, "/"); return typeof Buffer !== "undefined" ? Buffer.from(s, "base64").toString("utf8") : decodeURIComponent(escape(atob(s))); } };
  function challenge(E, note) { const W = E.sim.world, diff = {}; for (const k in W.rules) if (W.rules[k] !== World.RULES[k]) diff[k] = W.rules[k]; const champ = E.hall && E.hall[0] ? Evolve.flat(E.hall[0].genes) : null;
    return "FLYECO1." + b64.enc(JSON.stringify({ r: diff, s: W.seed, f: E.flight ? 1 : 0, c: champ ? Object.values(champ).map(v => +v.toFixed(3)) : null, n: (note || "").slice(0, 80) })); }
  function parseChallenge(code) { const m = /^FLYECO1\.([A-Za-z0-9_-]+)$/.exec((code || "").trim()); if (!m) throw new Error("不是挑战码"); const o = JSON.parse(b64.dec(m[1])), rules = Object.assign({}, World.RULES);
    for (const k in o.r) if (k in World.META) rules[k] = Math.max(World.META[k][1], Math.min(World.META[k][2], +o.r[k])); let genes = null; if (o.c && o.c.length === 10) genes = { learnRate: o.c[0], explore: o.c[1], flightBias: o.c[2], tempPref: o.c[3], metabolism: o.c[4], caution: o.c[5], innateTurn: o.c.slice(6, 10) };
    return { rules, seed: (o.s >>> 0) || 1, flight: !!o.f, genes, note: String(o.n || "") }; }
  const API = { snapshot, restore, fingerprint, challenge, parseChallenge, VERSION }; if (typeof module !== "undefined" && module.exports) module.exports = API; else root.EcoSave = API;
})(typeof window !== "undefined" ? window : globalThis);
