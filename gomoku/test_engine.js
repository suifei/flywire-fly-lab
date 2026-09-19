#!/usr/bin/env node
/**
 * 五子棋引擎与棋手的回归测试（每一项都对应一个真出过的 bug）。失败退出码 1。CI 里跑。
 *   1 线型枚举        合法线型恰好 14,641 种，对 互换视角 / 镜像 封闭
 *   2 刺激不残留      brain.setOpto 换一批输入后上一批必须清零（v1 五子棋的全部特征就是被这个污染的）
 *   3 增量估值        落子 / 悔棋 200 步，增量维护的估值与从头重算逐步一致
 *   4 着法合法        随机局面里搜索与直觉都不走已占点、不走黑方禁手点（含必败局面、含窗口外的长连）
 *   5 杀棋搜索        双四局面能找到杀着；对手已有成五点时必须先挡
 *   6 真脑核对        被选中那一步的线型放进真实果蝇脑里重跑，与价值表一致（有表才测）
 */
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, ".."), R = ROOT + "/results/gomoku";
const G = require("./rules.js"), L = require("./lines.js"), T2 = require("./teacher2.js"), E = require("./engine.js"), A = require("./arena.js"), F2 = require("./fly2.js");
let fail = 0; const ok = (name, cond, detail) => { console.log(`${cond ? "✓" : "✗"} ${name}  ${detail || ""}`); if (!cond) fail++; };

{ const all = L.allCodes(), set = new Set(all); let closed = 0; for (const c of all) if (set.has(L.swap(c)) && set.has(L.mirror(c))) closed++;
  ok("线型枚举", all.length === 14641 && closed === 14641, `${all.length} 种，封闭 ${closed}`); }

const subF = ROOT + "/results/dodge/subcircuit_v3.json", tabF = R + "/linetable_fly_intact.json";
const haveSub = fs.existsSync(subF), haveTab = fs.existsSync(tabF);
let SUB = null, ConnectomeBrain = null;
if (haveSub) { SUB = JSON.parse(fs.readFileSync(subF, "utf8")); ({ ConnectomeBrain } = require(ROOT + "/dodge/brain.js"));
  const LM = require("./line_map.js"), brain = new ConnectomeBrain(SUB, 11), map = LM.makeLineMap(SUB);
  const f = c => LM.lineFeatures(brain, map, c, { seed: 777, ms: 40 }), sum = a => a.reduce((x, y) => x + y, 0);
  const Acode = L.encode([0, 0, 0, 1, 1, 0, 0, 0]), Bcode = L.encode([2, 2, 2, 2, 2, 2, 2, 2]);
  const a1 = f(Acode), bb = f(Bcode), a2 = f(Acode); let d = 0; for (let i = 0; i < a1.length; i++) d += Math.abs(a1[i] - a2[i]);
  ok("刺激不残留", d === 0 && sum(bb) !== sum(a1), `A ${sum(a1)} → B ${sum(bb)} → A ${sum(a2)}，|A1−A2| = ${d}`);
  // 把旧行为**重演**一遍留作证据：setOpto 之后手动把上一批的 stimProb 写回去（= 修复前不清零的效果）
  const chanOf = c => { const o = []; for (const ch of L.channelsOf(c)) for (const n of map.chan[ch]) o.push(n); return o; };
  const oldStyle = (code, stale) => { brain.reseed(777); brain.reset(); brain.setOpto(chanOf(code), 160); for (const n of stale) brain.stimProb[n] = brain.optoProb; brain._updateStim();
    const out = new Uint16Array(map.downstream.length); brain.run(Math.round(40 / brain.dt), i => { const k = map.colOf[i]; if (k >= 0) out[k]++; }); brain.setOpto([], 0); for (const n of stale) brain.stimProb[n] = 0; return out; };
  const nd = map.downstream.length, fold = v => { const o = new Float64Array(nd); for (let i = 0; i < v.length; i++) o[i % nd] += v[i]; return o; };   // lineFeatures 默认分 2 个时间窗，折回每个神经元一个数
  const oA2 = oldStyle(Acode, chanOf(Bcode)), fa = fold(a1), fb = fold(bb); let dOld = 0, dB = 0; for (let i = 0; i < nd; i++) { dOld += Math.abs(oA2[i] - fa[i]); dB += Math.abs(oA2[i] - fb[i]); }
  fs.writeFileSync(R + "/opto_leak.json", JSON.stringify({ note: "A、B 是两种线型；40 ms、种子 777、160 Hz。old_behaviour = 重演修复前的行为（先喂过 B 再喂 A，B 的刺激没清掉）",
    fixed: { A_first: sum(a1), B: sum(bb), A_again: sum(a2), abs_diff_A_first_vs_again: d },
    old_behaviour: { A_after_B: sum(oA2), abs_diff_vs_true_A: dOld, abs_diff_vs_B: dB, identical_to_B: dB === 0 } }, null, 1));
  console.log(`  （重演旧行为：先 B 后 A 得到总脉冲 ${sum(oA2)}，与真正的 A 相差 ${dOld}，与 B 相差 ${dB}）`);
} else console.log("– 刺激不残留：没有子回路文件，跳过");

const att = haveTab ? F2.loadTable(JSON.parse(fs.readFileSync(tabF, "utf8"))).att : T2.attTable();
const lam = haveTab ? JSON.parse(fs.readFileSync(tabF, "utf8")).lam : 0.4, eng = E.makeEngine(att, lam);
{ const rand = A.rng32(3), b = G.newBoard(), hist = []; eng.setBoard(b); let bad = 0;
  for (let k = 0; k < 200; k++) {
    if (hist.length && rand() < 0.35) { const p = hist.pop(); eng.undo(p); b[p] = 0; } else { let p; do { p = (rand() * 225) | 0; } while (b[p]); const c = 1 + (hist.length & 1); eng.place(p, c); b[p] = c; hist.push(p); }
    if (!hist.length) continue; const st = eng.state(); let sb = 0, sw = 0;
    for (const q of G.candidates(b, 2)) for (let d = 0; d < 4; d++) { const c = L.codeAt(b, q % 15, (q / 15) | 0, d, 1); sb += att[c]; sw += att[L.swap(c)]; }
    if (Math.abs(sb - st.SB) > 1e-6 * Math.max(1, Math.abs(sb)) || Math.abs(sw - st.SW) > 1e-6 * Math.max(1, Math.abs(sw))) bad++; }
  ok("增量估值", bad === 0, `不一致 ${bad} / 200 步`); }

{ const rand = A.rng32(9); let bad = 0, none = 0, n = 0;
  for (let g = 0; g < 600; g++) { const b = G.newBoard(), m = 10 + ((rand() * 40) | 0);
    for (let k = 0; k < m; k++) { let p; do { p = G.idx(3 + ((rand() * 9) | 0), 3 + ((rand() * 9) | 0)); } while (b[p]); b[p] = 1 + (k & 1); }
    for (const me of [1, 2]) for (const mv of [eng.think(b, me, { depth: 2 }).move, eng.greedy(b, me)]) { n++; if (mv < 0) none++; else if (b[mv] || (me === 1 && G.forbidden(b, mv % 15, (mv / 15) | 0))) bad++; } }
  ok("着法合法", bad === 0 && none === 0, `${n} 次选点：非法 ${bad}，无着 ${none}`); }

{ const b = G.newBoard(), put = (x, y, c) => { b[G.idx(x, y)] = c; };
  put(3, 7, 1); put(4, 7, 2); put(5, 7, 2); put(6, 7, 2); put(7, 3, 1); put(7, 4, 2); put(7, 5, 2); put(7, 6, 2); put(0, 0, 1); put(1, 0, 1); put(0, 2, 1);
  const k = T2.vcf(b.slice(), 2, 6);
  const b2 = b.slice(); b2[G.idx(10, 10)] = 1; b2[G.idx(11, 10)] = 1; b2[G.idx(12, 10)] = 1; b2[G.idx(13, 10)] = 1;      // 黑有四：白必须先挡
  const k2 = T2.vcf(b2.slice(), 2, 6);
  ok("杀棋搜索", k === G.idx(7, 7) && k2 !== G.idx(7, 7), `双四杀着 ${k}（应 ${G.idx(7, 7)}）；对手有四时不再乱冲（返回 ${k2}）`); }

if (haveSub && haveTab) { const j = JSON.parse(fs.readFileSync(tabF, "utf8"));
  if (j.w_a) { const p = F2.makeLinePlayer(SUB, ConnectomeBrain, j, { seed: 11 }), b = G.newBoard();
    [[7, 7, 1], [8, 7, 2], [7, 8, 1], [8, 8, 2], [7, 6, 1]].forEach(([x, y, c]) => { b[G.idx(x, y)] = c; });
    const c = p.choose(b, 2, { depth: 4, vcf: true }), st = p.inspect(b, 2, c.move);
    ok("真脑核对", st.liveCheck.max_rel_diff < 1e-3 && (c.move === G.idx(7, 5) || c.move === G.idx(7, 9)), `重跑 ${st.liveCheck.runs} 次，最大相对偏差 ${st.liveCheck.max_rel_diff.toExponential(1)}；白蝇走 ${c.move}（应挡 ${G.idx(7, 5)} 或 ${G.idx(7, 9)}）`); }
} else console.log("– 真脑核对：没有子回路或价值表，跳过");
console.log(fail ? `\n✗ ${fail} 项失败` : "\n✓ 全部通过"); process.exit(fail ? 1 : 0);
