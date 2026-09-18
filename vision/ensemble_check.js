#!/usr/bin/env node
/**
 * flyvis 集成检验：我们所有视觉结论都建立在 50 个成员里的**1 个**上。
 *
 * 背景：Lappalainen et al. 2024 的核心主张是关于**集成**的 —— 连接组约束下解不唯一，
 * 他们训练了一组网络并强调成员间的差异。而本项目的 §18、§28.17、§28.18 全部只用了
 * `flow/0000/000` 这一个成员（本机 `flyvis/data/results/flow/0000/` 下有 50 个）。
 * 所以那些结论可能只是成员 000 的性质。
 *
 * ── 跑之前写定的三个问题（不预设答案）──────────────────────
 * Q1 「T4d 和 T5b 没有方向选择性」是成员 000 的性质，还是整个集成的性质？
 * Q2 「偏好方向落在六边形棱方向族 30°+60°k 上」在多少个成员里成立？
 * Q3 LPLC2 的判据 A（匀速扩张 > 匀速收缩）和 B（逼近 > 两种平移）在多少个成员里成立？
 * 另记：导出脚本会**逐成员验证**"权重只依赖 (源型, 靶型, du, dv)"这个卷积前提，
 *      不成立就拒绝导出 —— 有多少成员通过，本身就是一个结果。
 * ────────────────────────────────────────────────────────
 *
 * 用法：node vision/ensemble_check.js        （纯 CPU，约 36 分钟）
 * 输出 results/vision/ensemble_summary.json
 */
const fs = require("fs"), path = require("path"), cp = require("child_process");
const ROOT = path.resolve(__dirname, "..");
const ENS = path.join(ROOT, "results/vision/ensemble");
const TMP = path.join(ENS, ".work");
fs.mkdirSync(TMP, { recursive: true });

const members = [{ id: "000", net: path.join(ROOT, "results/vision/flyvis_net.json") }];
for (const f of fs.readdirSync(ENS).sort()) {
  const m = /^flyvis_net_(\d+)\.json$/.exec(f);
  if (m) members.push({ id: m[1], net: path.join(ENS, f) });
}
console.log(`集成成员 ${members.length} 个（含权威的 000）\n`);

const run = (script, env) => {
  const r = cp.spawnSync("node", [path.join(ROOT, "vision", script)],
    { env: Object.assign({}, process.env, env), encoding: "utf8", maxBuffer: 1 << 26 });
  return { code: r.status, out: (r.stdout || "") + (r.stderr || "") };
};

const SUB = ["T4a", "T4b", "T4c", "T4d", "T5a", "T5b", "T5c", "T5d"];
const rows = [];
for (const m of members) {
  const dirOut = path.join(TMP, `dir_${m.id}.json`);
  const lpOut = path.join(TMP, `lplc2_${m.id}.json`);
  const t0 = Date.now();
  let r = run("t4t5_directions.js", { FLYVIS_NET: m.net, OUT_JSON: dirOut });
  if (r.code !== 0 || !fs.existsSync(dirOut)) {
    console.log(`  成员 ${m.id}：方向测定失败 — ${r.out.trim().split("\n").pop()}`);
    rows.push({ id: m.id, ok: false, why: "方向测定失败" });
    continue;
  }
  const D = JSON.parse(fs.readFileSync(dirOut, "utf8")).定标;
  r = run("lplc2_test.js", { FLYVIS_NET: m.net, DIR_JSON: dirOut, OUT_JSON: lpOut });
  let L = null;
  if (fs.existsSync(lpOut)) L = JSON.parse(fs.readFileSync(lpOut, "utf8"));
  const sel = {}, fam = {};
  for (const t of SUB) {
    const d = D[t] || {};
    const isSel = d.方向选择性 != null && d.方向选择性 >= 0.2 && d.峰值增量 >= 0.05;
    sel[t] = isSel;
    fam[t] = isSel ? { 偏好: d.偏好方向, DSI: d.方向选择性, 族: d.所属族, 偏差: d.偏差, TF: d.最佳TF } : null;
  }
  rows.push({ id: m.id, ok: true, 有方向选择性: sel, 细节: fam,
              判据A: L ? L.判据A : null, "判据A'": L ? L["记录A'"] : null, 判据B: L ? L.判据B : null,
              LPLC2失败: L ? null : (r.out.trim().split("\n").pop() || "").slice(0, 80) });
  const n = SUB.filter(t => sel[t]).length;
  console.log(`  成员 ${m.id}：有方向选择性 ${n}/8`
    + `  A ${L ? (L.判据A ? "✓" : "✗") : "—"}  B ${L ? (L.判据B ? "✓" : "✗") : "—"}`
    + `  (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
}

// ── 汇总 ──────────────────────────────────────────────
const ok = rows.filter(r => r.ok);
console.log(`\n成功测定 ${ok.length}/${rows.length} 个成员\n`);
console.log("亚型   有方向选择性的成员数   偏好方向(中位/范围)   DSI中位   落在棱族(30+60k)");
const perType = {};
for (const t of SUB) {
  const have = ok.filter(r => r.有方向选择性[t]);
  const dirs = have.map(r => r.细节[t].偏好).sort((a, b) => a - b);
  const dsis = have.map(r => r.细节[t].DSI).sort((a, b) => a - b);
  const edge = have.filter(r => (r.细节[t].族 || "").indexOf("30") === 0).length;
  const md = dirs.length ? dirs[dirs.length >> 1] : null;
  perType[t] = { n_selective: have.length, n_total: ok.length,
                 偏好中位: md, 偏好范围: dirs.length ? [dirs[0], dirs[dirs.length - 1]] : null,
                 DSI中位: dsis.length ? +dsis[dsis.length >> 1].toFixed(3) : null,
                 落在棱族: edge };
  console.log(`${t.padEnd(6)} ${String(have.length + "/" + ok.length).padStart(14)}`
    + (md === null ? "            —" : `   ${md.toFixed(0)}° (${dirs[0].toFixed(0)}–${dirs[dirs.length - 1].toFixed(0)})`).padEnd(24)
    + (dsis.length ? dsis[dsis.length >> 1].toFixed(3) : "—").padStart(9)
    + String(edge + "/" + have.length).padStart(18));
}
const cA = ok.filter(r => r.判据A === true).length, cB = ok.filter(r => r.判据B === true).length;
const cA2 = ok.filter(r => r["判据A'"] === true).length;
const nL = ok.filter(r => r.判据A !== null).length;
console.log(`\nLPLC2 判据（在能建起汇集模型的 ${nL} 个成员里）：`);
console.log(`  A 匀速扩张>匀速收缩  ${cA}/${nL}`);
console.log(`  A' 加速逼近>时间倒放 ${cA2}/${nL}`);
console.log(`  B 逼近>两种平移      ${cB}/${nL}`);

fs.writeFileSync(path.join(ROOT, "results/vision/ensemble_summary.json"),
  JSON.stringify({ 说明: "flyvis 50 成员集成：逐成员重测 T4/T5 方向与 LPLC2 判据",
                   预先问题: ["Q1 T4d/T5b 无方向选择性是成员 000 的性质还是集成的性质",
                              "Q2 偏好方向落在棱族的成员比例", "Q3 LPLC2 判据 A/B 的成员比例"],
                   成员数: rows.length, 测定成功: ok.length,
                   按亚型: perType,
                   LPLC2判据: { 可建模成员: nL, A: cA, "A'": cA2, B: cB },
                   逐成员: rows }, null, 1));
console.log("\n→ results/vision/ensemble_summary.json");
