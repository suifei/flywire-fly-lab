#!/usr/bin/env node
/**
 * 像素路径看得见墙吗？——回答一个架构质疑（2026-09-19 用户提）
 *
 * 质疑是对的：手写视觉前端是**按物体**算的（只读球的世界坐标），所以往场里加任何东西
 * 它都看不见；而真正正确的做法是用果蝇头上那台摄像机渲染出来的画面。
 * 那条路径**本来就有**（eyecam 的 CubeCamera 渲染整个 3D 场景 → 721 小眼 → flyvis → LPLC2），
 * 只是默认关着。关的理由写在报告 §28.19：对 **2.5 mm 的球** 它在 45 mm 外读数恒为 0。
 *
 * **但那个理由对墙不一定成立**——球在 60 mm 外不到一个小眼，而墙是一整面。
 * 这个脚本就量这一件事：把果蝇钉在离墙不同距离上朝墙走，看像素路径的 LPLC2 读数。
 *
 * 三个条件：
 *   朝墙走   果蝇正对最近的墙，以行走速度靠近（墙从 120 mm 逼近到 5 mm）
 *   朝场心走 同样速度但背对墙（对照：同样的自体运动，没有逼近的墙）
 *   静止     完全不动（对照：读数应该趋近 0）
 * 判据事先写死：朝墙走时的 LPLC2 峰值 > 朝场心走的 p95，且在 ≥45 mm 处就已经高于它
 *（45 mm 是球那条结论的失明距离）。
 *
 * 用法：node dodge/wall_vision_test.js [页面路径]
 * 输出：results/dodge/wall_vision.json
 */
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, "..");
const PAGE = process.argv[2] || path.join(ROOT, "docs/game.html");
const loadPup = () => { for (const p of ["puppeteer-core", "puppeteer",
    path.join(ROOT, "studio/capture/node_modules/puppeteer-core")]) { try { return require(p); } catch (e) {} } return null; };
const chromePath = () => [process.env.CHROME_PATH,
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
  .filter(Boolean).find(p => { try { return fs.existsSync(p); } catch { return false; } });

(async () => {
  const puppeteer = loadPup(), exe = chromePath();
  if (!puppeteer || !exe) { console.log("跳过：没有 puppeteer 或 Chrome"); process.exit(process.env.CI ? 1 : 0); }
  const browser = await puppeteer.launch({ executablePath: exe, headless: "new",
    args: ["--no-sandbox", "--allow-file-access-from-files", "--use-gl=angle"] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1200, height: 900 });
  const errs = [];
  page.on("pageerror", e => errs.push(e.message));
  await page.goto("file://" + PAGE + "?scene=court", { waitUntil: "load", timeout: 180000 });
  await page.waitForFunction(() => window.__eyeDiag && window.__game, { timeout: 120000 });
  await new Promise(r => setTimeout(r, 3000));

  const out = { conditions: {} };
  for (const cond of ["朝墙走", "朝场心走", "静止"]) {
    const rows = await page.evaluate(async COND => {
      const D = window.__eyeDiag, cam = D.instance(), G = window.__game, S = G.S;
      const netDoc = JSON.parse(document.getElementById("flyvis-data").textContent);
      const dirT = JSON.parse(document.getElementById("t4t5-data").textContent).定标;
      const fe = ConnectomeFrontEnd.create(FlyVis, LPLC2, netDoc, dirT, { stride: 8 });
      const CVS = [document.getElementById("ecL"), document.getElementById("ecR")];
      const pageTick = window.__eyeTick;
      const hw = G.CFG.courtW / 2 - G.CFG.courtPad;
      const rows = [];
      let last = performance.now(), t0 = null, dist = 120;
      const speed = G.CFG.walkSpeed;                        // 18 mm/s，和真的走一样
      G.balls.length = 0; G.pellets.length = 0; G.dust.length = 0;
      G.CFG.autoPellets = false; G.CFG.autoDust = false; G.mode = "click";
      // 每一物理步都钉住，而不是只在 30 fps 的眼动帧里钉——否则两帧之间它照样走。
      const realStep = G.step;
      G.step = () => { realStep(); if (COND === "静止") { S.phase = 0; S.speed = 0; } S.x = hw - dist; S.y = 0;
                       S.h = COND === "朝场心走" ? Math.PI : 0; S.jumpT = -1; S.z = 0; };
      window.__eyeTick = () => {
        const head = D.head(); if (!head) return;
        const now = performance.now(), dt = Math.min(0.2, (now - last) / 1000); last = now;
        // 把果蝇**钉在**指定位姿上：朝墙 / 背墙 / 不动
        if (COND !== "静止" && t0 !== null) dist = Math.max(5, dist - speed * dt);
        S.jumpT = -1; S.clip = null; S.z = 0;
        S.x = hw - dist; S.y = 0;
        S.h = COND === "朝场心走" ? Math.PI : 0;             // 0 = 朝 +x（墙在那边）
        // **步态相位也要钉住**：第一版只钉了位置，腿还在动、头还在晃，
        // 于是"静止"对照的 LPLC2 p95 高到 159 Hz，对照就没意义了。
        // 报告 §28.19 量到的"自体运动造成的假逼近"正是这一项。
        if (COND === "静止") S.phase = 0;
        S.speed = COND === "静止" ? 0 : S.speed;
        const r = cam.updateAsync(head, CVS, 30); if (!r) return;
        const o = fe.step(r.r16, dt);
        if (t0 === null) return;
        rows.push({ d: +dist.toFixed(1), lplc2: +Math.max(o.lplc2L, o.lplc2R).toFixed(1),
                    lc4: +Math.max(o.lc4L, o.lc4R).toFixed(1) });
      };
      await new Promise(r => setTimeout(r, 2500));          // 前端预热
      t0 = performance.now();
      await new Promise(r => setTimeout(r, 8000));
      window.__eyeTick = pageTick;
      G.step = realStep;
      return rows;
    }, cond);
    out.conditions[cond] = rows;
    const v = rows.map(r => r.lplc2);
    const p = q => { const s = [...v].sort((a, b) => a - b); return s.length ? s[Math.floor(q * (s.length - 1))] : NaN; };
    console.log(`${cond.padEnd(8, "　")} ${rows.length} 帧  LPLC2 中位 ${p(0.5).toFixed(1)}  p95 ${p(0.95).toFixed(1)}  峰值 ${Math.max(...v, 0).toFixed(1)} Hz`);
  }
  await browser.close();

  const wall = out.conditions["朝墙走"], ctrl = out.conditions["朝场心走"];
  const pct = (a, q) => { const s = [...a].sort((x, y) => x - y); return s.length ? s[Math.floor(q * (s.length - 1))] : NaN; };
  const ctrlP95 = pct(ctrl.map(r => r.lplc2), 0.95);
  const far = wall.filter(r => r.d >= 45).map(r => r.lplc2);
  const near = wall.filter(r => r.d < 45).map(r => r.lplc2);
  out.control_p95 = +ctrlP95.toFixed(1);
  out.wall_far_median = far.length ? +pct(far, 0.5).toFixed(1) : null;
  out.wall_far_max = far.length ? +Math.max(...far).toFixed(1) : null;
  out.wall_near_median = near.length ? +pct(near, 0.5).toFixed(1) : null;
  out.wall_peak = +Math.max(...wall.map(r => r.lplc2), 0).toFixed(1);
  out.criterion_peak_above_control = out.wall_peak > ctrlP95;
  out.criterion_visible_at_45mm = out.wall_far_max !== null && out.wall_far_max > ctrlP95;
  // 按距离分箱，看从多远开始看得见
  const bins = [[100, 120], [80, 100], [60, 80], [45, 60], [30, 45], [15, 30], [5, 15]];
  out.by_distance = bins.map(([a, b]) => {
    const v = wall.filter(r => r.d >= a && r.d < b).map(r => r.lplc2);
    return { from: a, to: b, n: v.length, median: v.length ? +pct(v, 0.5).toFixed(1) : null,
             max: v.length ? +Math.max(...v).toFixed(1) : null };
  });
  console.log(`\n对照（朝场心走）p95 = ${out.control_p95} Hz —— 这是自体运动造成的噪声底`);
  console.log(`${"距离墙 (mm)".padEnd(14)}${"中位".padStart(8)}${"峰值".padStart(8)}`);
  for (const b of out.by_distance) console.log(`${(b.from + "–" + b.to).padEnd(14)}${String(b.median ?? "—").padStart(8)}${String(b.max ?? "—").padStart(8)}`);
  console.log(`\n判据 1（峰值高过噪声底）${out.criterion_peak_above_control ? "成立" : "不成立"}`);
  console.log(`判据 2（45 mm 外就看得见，球在这个距离已经全瞎）${out.criterion_visible_at_45mm ? "成立" : "不成立"}`);
  if (errs.length) console.log("页面报错：" + errs.slice(0, 3).join("；"));
  fs.writeFileSync(ROOT + "/results/dodge/wall_vision.json", JSON.stringify(out, null, 1));
  console.log("→ results/dodge/wall_vision.json");
})().catch(e => { console.error("FAIL", e.message); process.exit(1); });
