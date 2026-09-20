#!/usr/bin/env node
/**
 * 两套视觉前端并排对比：手写 dθ/dt  vs  真实像素 → flyvis → LPLC2。
 *
 * 差别在于**信息来源**：
 *   · 手写版直接读球的世界坐标算张角增长率，且只看球、无视场景里其它一切；
 *   · 连接组版只看复眼的 721 个 R1–6 读数，不知道球在哪，也分不清什么是球。
 *
 * 两个条件**分离噪声与信号**（第一版把两者混在一次里测，被慢动作毁了：
 * 果蝇一起飞页面就 ×0.04 慢放，球停在 55 mm，样本不可比）：
 *   A「只有自体运动」：场上无球，果蝇自由行走 → 连接组前端读到的全是噪声底
 *   B「只有球」：每帧把果蝇位姿钉回原点（既不走也飞不起来），球从 120 mm 逼近 → 信号
 * 预期（跑之前写下）：如果噪声主要来自自体运动，A 的读数会显著高于 0，
 * 而 B 只在球足够近（几个小眼大）时才起来。判据：B 在近距的信号要高过 A 的 p95。
 *
 * 球半径 2.5 mm、小眼间角 5.7°：球在 60 mm 外不到一个小眼，25 mm 时约 2 个，10 mm 时约 5 个。
 *
 *
 * 用法：node dodge/front_end_compare.js [页面路径或 URL]
 */
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, "..");
const PAGE = process.argv[2] || path.join(ROOT, "docs/game.html");

function loadPuppeteer() {
  for (const p of ["puppeteer-core", "puppeteer",
                   path.join(ROOT, "studio/capture/node_modules/puppeteer-core")]) {
    try { return require(p); } catch (e) {}
  }
  return null;
}
const chromePath = () => [process.env.CHROME_PATH,
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/usr/bin/google-chrome", "/usr/bin/chromium-browser"]
  .filter(Boolean).find(p => { try { return fs.existsSync(p); } catch { return false; } });

(async () => {
  const puppeteer = loadPuppeteer(), exe = chromePath();
  if (!puppeteer || !exe) {
    const m = !puppeteer ? "没有 puppeteer-core" : "找不到 Chrome";
    if (process.env.CI) { console.error("✗ " + m); process.exit(1); }
    console.log("跳过：" + m); process.exit(0);
  }
  const browser = await puppeteer.launch({ executablePath: exe, headless: "new",
    args: ["--no-sandbox", "--allow-file-access-from-files"] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1200, height: 900 });
  const errs = [];
  page.on("pageerror", e => errs.push(e.message));
  await page.goto((/^https?:/.test(PAGE) ? PAGE : "file://" + PAGE) + "?scene=court", { waitUntil: "load", timeout: 180000 });
  await page.waitForFunction(() => window.__eyeDiag && window.__eyeDiag.head(), { timeout: 180000 });

  const REPS = +(process.env.REPS || 3);      // 噪声底本身在波动（单次 p95 在 39–74 Hz 之间跳），必须重复
  const out = { 自体运动: [], 球逼近: [] };
  for (let rep = 0; rep < REPS; rep++)
  for (const mode of ["自体运动", "球逼近"]) {
    const rows = await page.evaluate(async MODE => {
      const FREEZE = MODE === "球逼近";
      const D = window.__eyeDiag, cam = D.instance(), G = window.__game, S = G.S || G.state;
      const netDoc = JSON.parse(document.getElementById("flyvis-data").textContent);
      const dirT = JSON.parse(document.getElementById("t4t5-data").textContent).定标;
      const fe = ConnectomeFrontEnd.create(FlyVis, LPLC2, netDoc, dirT, { stride: 8 });
      const CVS = [document.getElementById("ecL"), document.getElementById("ecR")];
      const pageTick = window.__eyeTick;
      const rows = [];
      let t0 = null, myBall = null, last = performance.now();
      const ground = () => { S.x = 0; S.y = 0; S.h = 0; S.clip = null; S.jumpT = -1; };
      window.__eyeTick = () => {
        const head = D.head(); if (!head) return;
        if (FREEZE) ground();
        const r = cam.updateAsync(head, CVS, 30); if (!r) return;
        const now = performance.now(), dt = Math.min(0.2, (now - last) / 1000); last = now;
        const o = fe.step(r.r16, dt);
        if (t0 === null) return;
        if (FREEZE && (!myBall || G.balls.indexOf(myBall) < 0)) return;
        rows.push({ t: +((now - t0) / 1000).toFixed(3), gt: +S.t.toFixed(2),
          d: myBall ? +Math.hypot(myBall.x - S.x, myBall.y - S.y).toFixed(1) : null,
          hand: +Math.max(G.loom.lplc2L, G.loom.lplc2R).toFixed(1),
          conn: +Math.max(o.lplc2L, o.lplc2R).toFixed(1) });
      };
      await new Promise(r => setTimeout(r, 2500));        // 前端预热 + 基线收敛
      if (FREEZE) {
        ground(); G.balls.length = 0;
        await new Promise(r => setTimeout(r, 400));
        ground(); G.balls.length = 0;
        G.launch(120, 0, {});
        myBall = G.balls[G.balls.length - 1];
        t0 = performance.now();
        await new Promise(r => setTimeout(r, 3500));
      } else {
        // 自体运动条件：全程清空球，果蝇照常走
        t0 = performance.now();
        const iv = setInterval(() => { G.balls.length = 0; }, 50);
        await new Promise(r => setTimeout(r, 3500));
        clearInterval(iv);
      }
      window.__eyeTick = pageTick;
      return rows;
    }, mode);
    out[mode].push(...rows);
  }
  await browser.close();

  const pct = (a, q) => { if (!a.length) return NaN; const s2 = [...a].sort((x, y) => x - y);
                          return s2[Math.min(s2.length - 1, Math.floor(q * s2.length))]; };
  const noise = out["自体运动"].map(r => r.conn);
  const noiseH = out["自体运动"].map(r => r.hand);
  const p95 = pct(noise, 0.95), p50 = pct(noise, 0.5);
  console.log("球半径 2.5 mm、小眼间角 5.7°：球在 60 mm 外不到一个小眼\n");
  console.log(`A 只有自体运动（无球，果蝇自由行走，${REPS} 次重复共 ${noise.length} 帧）`);
  console.log(`   连接组前端  中位 ${p50.toFixed(1)} Hz   p95 ${p95.toFixed(1)} Hz   峰值 ${Math.max(...noise).toFixed(1)} Hz`);
  console.log(`   手写前端    中位 ${pct(noiseH,0.5).toFixed(1)} Hz   p95 ${pct(noiseH,0.95).toFixed(1)} Hz   峰值 ${Math.max(...noiseH).toFixed(1)} Hz  ← 无球时本应恒为 0`);
  // **只取逼近段**：球过了最近点就开始远离，而手写前端对远离不响应（dtheta<=0），
  // 近距箱里那些 0 其实是"球已经飞过去了"，混进来会把两边都读错。
  const approach = [];
  let minSoFar = Infinity, prevT = -1;
  for (const r of out["球逼近"]) {
    if (r.d === null) continue;
    if (r.t < prevT) { minSoFar = Infinity; }            // 新的一次重复，重置
    prevT = r.t;
    if (r.d <= minSoFar + 0.5) { minSoFar = Math.min(minSoFar, r.d); approach.push(r); }
  }
  const closest = approach.reduce((m, r) => Math.min(m, r.d), 1e9);
  console.log(`\nB 只有球（果蝇钉死），只取逼近段（${approach.length}/${out["球逼近"].length} 帧，最近 ${closest.toFixed(1)} mm），按距离分箱：`);
  console.log("  距离(mm)   帧数   手写Hz中位   连接组Hz中位   连接组>A的p95?");
  const bins = [[110, 90], [90, 70], [70, 55], [55, 45], [45, 35], [35, 25], [25, 0]];
  const binOut = [];
  for (const [hi, lo] of bins) {
    const r = approach.filter(x => x.d <= hi && x.d > lo);
    if (!r.length) continue;
    const mh = pct(r.map(x => x.hand), 0.5), mc = pct(r.map(x => x.conn), 0.5);
    const over = mc > p95;
    binOut.push({ 距离: `${lo}–${hi}`, 帧数: r.length, 手写中位: +mh.toFixed(1), 连接组中位: +mc.toFixed(1), 超过噪声p95: over });
    console.log(`  ${(lo + "–" + hi).padStart(8)}${String(r.length).padStart(7)}${mh.toFixed(1).padStart(13)}${mc.toFixed(1).padStart(15)}${(over ? "  ✓" : "  ✗").padStart(16)}`);
  }
  const first = binOut.slice().reverse().find(b => b.超过噪声p95);
  console.log(`\n连接组前端最远能在 ${first ? first.距离.split("–")[1] + " mm" : "——"} 处把球从自体运动噪声里分出来（判据：距离箱中位 > A 的 p95 = ${p95.toFixed(1)} Hz）`);
  const summary = { 自体运动噪声: { 中位: +p50.toFixed(1), p95: +p95.toFixed(1), 峰值: +Math.max(...noise).toFixed(1), 帧数: noise.length },
                    手写在无球时: { 中位: +pct(noiseH,0.5).toFixed(1), 峰值: +Math.max(...noiseH).toFixed(1) },
                    球逼近分箱: binOut, 逼近段帧数: approach.length, 最近距离mm: +closest.toFixed(1), 重复次数: REPS,
                    连接组可分辨的最远距离mm: first ? +first.距离.split("–")[1] : null };
  fs.writeFileSync(path.join(ROOT, "results/vision/front_end_compare.json"),
    JSON.stringify({ 说明: "A 只有自体运动（噪声底） vs B 只有球（信号）；两者分开测，避免起飞慢放污染",
                     摘要: summary, 曲线: out }, null, 1));
  console.log("\n→ results/vision/front_end_compare.json");
  if (errs.length) { console.log("✗ 页面报错：" + errs[0]); process.exit(1); }
})().catch(e => { console.error("FAIL", e); process.exit(1); });
