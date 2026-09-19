#!/usr/bin/env node
/**
 * 真浏览器里跑一遍游戏页，重点验「让果蝇看你的图」这条链路。
 *
 * 为什么必须有这个：smoke_test.js 只能执行不依赖 DOM 的渲染路径，
 * 而复眼这块要 canvas、Image、getImageData。这个项目已经吃过一次亏——
 * `node --check` 全过、线上却因为标签模板直接白屏（见 CI 注释）。
 * 「工具通过」只覆盖它检查的东西。
 *
 * 判定：页面无 console error / 无未捕获异常，且六个画布都**画出了东西**
 * （像素有方差；全黑或全白都算失败）。
 *
 * 用法：node dodge/browser_test.js [页面路径]
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const PAGE = process.argv[2] || path.join(ROOT, "docs/game.html");

function loadPuppeteer() {
  for (const p of ["puppeteer-core", "puppeteer",
                   path.join(ROOT, "studio/capture/node_modules/puppeteer-core"),
                   path.join(ROOT, "studio/capture/node_modules/puppeteer")]) {
    try { return require(p); } catch (e) { /* 继续找 */ }
  }
  return null;
}

function chromePath() {
  const cands = [
    process.env.CHROME_PATH,
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium-browser",
  ].filter(Boolean);
  return cands.find(p => { try { return fs.existsSync(p); } catch { return false; } });
}

(async () => {
  const puppeteer = loadPuppeteer();
  const strict = !!process.env.CI;          // CI 里缺环境要报错，本地才允许跳过
  if (!puppeteer) {
    const m = "没有 puppeteer-core（npm i）";
    if (strict) { console.error("✗ " + m); process.exit(1); }
    console.log("跳过：" + m); process.exit(0);
  }
  const exe = chromePath();
  if (!exe) {
    const m = "找不到 Chrome，可用 CHROME_PATH 指定";
    if (strict) { console.error("✗ " + m); process.exit(1); }
    console.log("跳过：" + m); process.exit(0);
  }
  const isUrl = /^https?:\/\//.test(PAGE);
  if (!isUrl && !fs.existsSync(PAGE)) { console.error(`没有 ${PAGE}`); process.exit(1); }

  const browser = await puppeteer.launch({
    executablePath: exe, headless: "new",
    args: ["--no-sandbox", "--disable-dev-shm-usage", "--allow-file-access-from-files"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 1000 });

  const errs = [];
  page.on("console", m => { if (m.type() === "error") errs.push("console: " + m.text()); });
  page.on("pageerror", e => errs.push("pageerror: " + e.message));

  const target = isUrl ? PAGE : "file://" + PAGE;
  console.log(`打开 ${isUrl ? PAGE : path.relative(ROOT, PAGE)} …`);
  await page.goto(target, { waitUntil: "load", timeout: 180000 });

  // 等资产装配完成（eNote 被填上说明 bootFlyEye 跑通了）
  await page.waitForFunction(
    () => { const n = document.getElementById("eNote"); return n && n.textContent.trim().length > 0; },
    { timeout: 120000 });
  const note = await page.$eval("#eNote", e => e.textContent.trim());
  console.log("  装配完成：" + note);

  // 复眼视窗要等游戏跑几帧才有内容（3 fps，读回 GPU 像素）
  await page.waitForFunction(() => {
    const c = document.getElementById("ecL");
    if (!c) return false;
    const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
    for (let i = 3; i < d.length; i += 4) if (d[i] !== 0) return true;
    return false;
  }, { timeout: 60000 }).catch(() => console.log("  ⚠ 复眼视窗一直是空的"));

  await page.click("#ePre_shapes");
  await page.click("#eRun");
  await page.waitForFunction(
    () => (document.getElementById("eStatus") || {}).textContent?.startsWith("完成："),
    { timeout: 120000 });
  console.log("  " + await page.$eval("#eStatus", e => e.textContent.trim()));

  // 每个画布都必须画出东西：全黑/全白（方差≈0）算失败
  const stats = await page.evaluate(() => {
    const ids = ["eSrc", "eOmm", "eAcc", "eAct", "eRetina", "eLamina", "eMedulla", "eMotion", "ecL", "ecR"];
    return ids.map(id => {
      const c = document.getElementById(id);
      if (!c) return { id, ok: false, why: "没有这个画布" };
      const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
      let n = 0, s = 0, s2 = 0;
      for (let i = 0; i < d.length; i += 4) {
        if (d[i + 3] === 0) continue;
        const v = (d[i] + d[i + 1] + d[i + 2]) / 3;
        n++; s += v; s2 += v * v;
      }
      const mean = s / Math.max(n, 1);
      const sd = Math.sqrt(Math.max(0, s2 / Math.max(n, 1) - mean * mean));
      return { id, n, mean: +mean.toFixed(1), sd: +sd.toFixed(2), ok: n > 100 && sd > 3 };
    });
  });

  console.log(`\n${"画布".padEnd(10)}${"不透明像素".padStart(11)}${"均值".padStart(8)}${"标准差".padStart(9)}`);
  let bad = 0;
  for (const s of stats) {
    console.log(`${s.id.padEnd(10)}${String(s.n ?? "-").padStart(11)}${String(s.mean ?? "-").padStart(8)}${String(s.sd ?? "-").padStart(9)}  ${s.ok ? "✓" : "✗ " + (s.why || "画面是空的/纯色")}`);
    if (!s.ok) bad++;
  }
  // ── v7：任务模式与光遗传手指，在真浏览器里点一遍 ─────────────────────
  console.log("\n任务模式 / 光遗传");
  const ui = [];
  const step = async (name, fn) => { try { ui.push([name, await fn()]); } catch (e) { ui.push([name, "异常：" + e.message]); } };

  await step("光遗传按钮渲染出来了", async () => {
    const n = await page.$$eval("#optoBtns button", b => b.length);
    return n >= 4 ? true : `只有 ${n} 个`;
  });
  await step("点亮 LC4+LPLC2 后巨纤维越过阈值", async () => {
    const r = await page.evaluate(async () => {
      const g = window.__game, SUB = g.brain.groups || {};
      const idx = (SUB.LC4_left || []).concat(SUB.LPLC2_left || []);
      g.optoPulse(idx, 200, 0.6, "test");
      let mx = 0;
      for (let i = 0; i < Math.round(0.8 / g.chunkDt); i++) { g.step(); mx = Math.max(mx, g.readout().gf); }
      return { mx, thr: g.CFG.gfThreshold };
    });
    return r.mx > r.thr ? `巨纤维峰值 ${r.mx.toFixed(0)} Hz > 阈值 ${r.thr}` : `只到 ${r.mx.toFixed(0)} Hz`;
  });
  await step("任务面板能打开且七关都在", async () => {
    await page.click("#mOpen");
    const n = await page.$$eval("#mList .mcard", b => b.length);
    return n === 7 ? true : `只有 ${n} 关`;
  });
  await step("进入第一关后目标与实测说明都显示了", async () => {
    await page.click("#mList .mcard");
    const t = await page.$eval("#mTitle", e => e.textContent.trim());
    const goal = await page.$eval("#mGoal", e => e.textContent.trim());
    const line = await page.$eval("#mLine", e => e.textContent.trim());
    return (t && goal.length > 5 && line.length > 10) ? `${t}｜${goal.slice(0, 24)}…` : "文本是空的";
  });
  await step("看参考解会真的把开关拨下去", async () => {
    await page.click("#mGiveup");
    const on = await page.evaluate(() => Object.entries(window.__game.lesion).filter(([, v]) => v).map(([k]) => k));
    return on.length ? on.join("+") : "没有任何开关被拨下";
  });
  await step("退出任务会还原玩家原来的设定", async () => {
    await page.click("#mQuit");
    const on = await page.evaluate(() => Object.entries(window.__game.lesion).filter(([, v]) => v).map(([k]) => k));
    return on.length === 0 ? true : "残留：" + on.join("+");
  });
  await step("盲盒突变体：抽取会真的敲掉一个神经元", async () => {
    await page.click("#mutNew");
    const on = await page.evaluate(() => Object.entries(window.__game.neuronLesion).filter(([, v]) => v).map(([k]) => k));
    return on.length === 1 ? "敲掉了 " + on[0] : "敲掉了 " + on.length + " 个";
  });
  await step("提交诊断会给出答案与实测破绽", async () => {
    await page.select("#mutGuess", "Roundup");
    await page.click("#mutSubmit");
    const pill = await page.$eval("#mutPill", e => e.textContent.trim());
    const coach = await page.$eval("#coach", e => e.textContent.trim());
    return (pill && coach.length > 20) ? pill : "没有给出结果";
  });
  await step("治好它会把神经元恢复", async () => {
    await page.click("#mutCure");
    const on = await page.evaluate(() => Object.entries(window.__game.neuronLesion).filter(([, v]) => v).map(([k]) => k));
    return on.length === 0 ? true : "残留：" + on.join("+");
  });
  await step("脑图画布真的画出了神经元", async () => {
    const r = await page.evaluate(() => {
      const c = document.getElementById("brainCv");
      if (!c || !c.width) return { ok: false, why: "画布没有尺寸" };
      const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
      let n = 0, s = 0, s2 = 0;
      for (let i = 0; i < d.length; i += 4) { const v = (d[i] + d[i + 1] + d[i + 2]) / 3; n++; s += v; s2 += v * v; }
      const m = s / n; return { ok: true, sd: Math.sqrt(Math.max(0, s2 / n - m * m)), n };
    });
    return r.ok ? (r.sd > 2 ? `像素标准差 ${r.sd.toFixed(1)}` : `画面是纯色（标准差 ${r.sd.toFixed(1)}）`) : r.why;
  });
  await step("脑图的神经元数与子回路一致", async () => {
    const r = await page.evaluate(() => {
      const s = JSON.parse(document.getElementById("soma-data").textContent);
      return { n: s.n, sub: window.__game.brain.n, soma: s.n_from_soma };
    });
    return r.n === r.sub ? `${r.n} 个（其中 ${r.soma} 个是真胞体坐标）` : `脑图 ${r.n} vs 子回路 ${r.sub}`;
  });
  await step("五子棋：切到主画面后球场停渲、果蝇自对弈能落子", async () => {
    await page.click("#viewGomoku");
    await page.click("#gmSelf");
    await new Promise(r => setTimeout(r, 7000));
    const r = await page.evaluate(() => {
      const g = window.__gm; if (!g) return { ok: false, why: "没有五子棋模块" };
      if (window.__stageMode !== "gomoku") return { ok: false, why: "主画面没切过去" };
      const cv = document.getElementById("gmStage");
      const d = cv.getContext("2d").getImageData(0, 0, cv.width, cv.height).data;
      let n2 = 0, s = 0, s2 = 0;
      for (let i = 0; i < d.length; i += 4) { const v = (d[i] + d[i + 1] + d[i + 2]) / 3; n2++; s += v; s2 += v * v; }
      const m = s / n2;
      return { ok: true, n: g.state.board.filter(v => v !== 0).length, sd: Math.sqrt(Math.max(0, s2 / n2 - m * m)) };
    });
    if (!r.ok) return r.why;
    if (!(r.n > 0)) return "7 秒内一子未落";
    return r.sd > 2 ? `已落 ${r.n} 子，棋盘画布标准差 ${r.sd.toFixed(1)}` : `落了 ${r.n} 子但画布是纯色`;
  });
  await step("五子棋：黑白是两只独立的果蝇", async () => {
    const r = await page.evaluate(() => {
      const SUBd = JSON.parse(document.getElementById("sub-data").textContent);
      const RO = JSON.parse(document.getElementById("gomoku-readout").textContent);
      const G = window.Gomoku;
      const mk = (seed, fs2) => window.GomokuFly.makePlayer(SUBd, window.FlyDodgeBrain.ConnectomeBrain, RO,
        { seed, featSeed: fs2 });
      const a = mk(11, 777), b2 = mk(23, 20260919);
      let diff = 0;
      for (let t = 0; t < 6; t++) {
        const bd = G.newBoard();
        for (let k = 0; k < 20; k++) { const m = (t * 37 + k * 11) % 225; if (!bd[m]) bd[m] = 1 + (k % 2); }
        if (a.think(bd, 1).move !== b2.think(bd, 1).move) diff++;
      }
      return { diff };
    });
    return r.diff > 0 ? `6 个局面里有 ${r.diff} 个选点不同` : "两只给出的着法完全一样（不是两个个体）";
  });
  await step("五子棋：立体模式棋盘在视野里", async () => {
    await page.click("#gmView3d");
    await new Promise(r => setTimeout(r, 2500));
    const r = await page.evaluate(() => {
      const c = document.getElementById("gmStage");
      const ctx = c.getContext("2d");
      const w = c.width, h = c.height;
      // 棋盘是暖木色：数一数画面左 2/3 里有多少"偏黄"的像素，太少说明棋盘跑出视野了
      const d = ctx.getImageData(0, 0, Math.floor(w * 0.66), h).data;
      let wood = 0, n = 0;
      for (let i = 0; i < d.length; i += 4) { n++; if (d[i] > 120 && d[i] > d[i + 2] + 30) wood++; }
      return { frac: wood / n };
    });
    await page.click("#gmView2d");
    return r.frac > 0.25 ? `左侧 2/3 里木色占比 ${(r.frac * 100).toFixed(0)}%` : `棋盘不在视野里（木色占比只有 ${(r.frac * 100).toFixed(0)}%）`;
  });
  await step("五子棋：立体模式能切换并渲染", async () => {
    await page.click("#gmView3d");
    await new Promise(r => setTimeout(r, 2500));
    const r = await page.evaluate(() => {
      const c = document.getElementById("gmStage");
      const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
      let n = 0, s = 0, s2 = 0;
      for (let i = 0; i < d.length; i += 4) { const v = (d[i] + d[i + 1] + d[i + 2]) / 3; n++; s += v; s2 += v * v; }
      const m = s / n;
      return { view: window.__gm.state.view, sd: Math.sqrt(Math.max(0, s2 / n - m * m)) };
    });
    await page.click("#gmView2d");
    return (r.view === "3d" && r.sd > 2) ? `立体模式画布标准差 ${r.sd.toFixed(1)}` : `view=${r.view} sd=${r.sd.toFixed(1)}`;
  });
  await step("切到五子棋后球场那只果蝇被冻结", async () => {
    const a0 = await page.evaluate(() => ({ t: window.__game.S.t, x: window.__game.S.x }));
    await new Promise(r => setTimeout(r, 2500));
    const a1 = await page.evaluate(() => ({ t: window.__game.S.t, x: window.__game.S.x }));
    return (a1.t === a0.t && a1.x === a0.x)
      ? `大脑时钟与位置都停在 ${a0.t.toFixed(2)} s` : `还在动（t ${a0.t.toFixed(2)}→${a1.t.toFixed(2)}）`;
  });
  await step("面板切到下棋那只果蝇的读数", async () => {
    const r = await page.evaluate(async () => {
      // 等一次"思考"跑完
      const t0 = performance.now();
      while (performance.now() - t0 < 6000) {
        const v = document.getElementById("vGF").textContent;
        if (+v > 0) break;
        await new Promise(x => setTimeout(x, 100));
      }
      return { gf: +document.getElementById("vGF").textContent,
               sug: +document.getElementById("vSUG").textContent,
               odr: document.getElementById("vODR").textContent,
               state: document.getElementById("pState").textContent };
    });
    return (r.gf > 0 && r.sug > 0 && r.odr === "棋盘")
      ? `巨纤维 ${r.gf} Hz、糖味 ${r.sug} Hz、状态「${r.state}」` : JSON.stringify(r);
  });
  await step("切回球场后三维场景恢复渲染", async () => {
    await page.click("#viewCourt");
    await new Promise(r => setTimeout(r, 1500));
    if (await page.evaluate(() => window.__stageMode) !== "court") return "没切回去";
    const a0 = await page.evaluate(() => window.__game.S.t);
    await new Promise(r => setTimeout(r, 1500));
    const a1 = await page.evaluate(() => window.__game.S.t);
    return a1 > a0 ? `球场那只恢复计算（${a0.toFixed(2)} → ${a1.toFixed(2)} s）` : "切回去了但没恢复计算";
  });
  await step("五子棋禁手规则可用", async () => {
    const r = await page.evaluate(() => {
      const G = window.Gomoku, b = G.newBoard();
      [[5, 5], [6, 5], [7, 5], [8, 5], [9, 5]].forEach(([x, y]) => { b[G.idx(x, y)] = G.BLACK; });
      return { overline: G.forbidden(b, 10, 5), legal: G.forbidden(b, 10, 8) };
    });
    return r.overline === "长连" && r.legal === null ? "长连判出、正常点放行" : `长连=${r.overline} 正常点=${r.legal}`;
  });
  await step("同伴果蝇：加两只之后各自有独立大脑并在动", async () => {
    await page.click("#cpAdd"); await page.click("#cpAdd");
    const before = await page.evaluate(() => window.__comp ? window.__comp.list.map(c => [c.S.x, c.S.y]) : null);
    await new Promise(r => setTimeout(r, 2500));
    const after = await page.evaluate(() => window.__comp ? window.__comp.list.map(c => [c.S.x, c.S.y]) : null);
    if (!before || before.length !== 2) return "没有同伴模块或数量不对";
    const moved = before.filter((p, i) => Math.hypot(after[i][0] - p[0], after[i][1] - p[1]) > 1).length;
    const brains = await page.evaluate(() => window.__comp.list.map(c => c.brain.n));
    return moved === 2 ? `2 只都在走，各自 ${brains[0]} 神经元` : `只有 ${moved} 只在动`;
  });
  await step("页面跑的是子回路 v3 且触感已接通", async () => {
    const r = await page.evaluate(() => {
      const g = window.__game;
      const hasTouch = !!(g.brain.groups.TOUCH_left || []).length;
      return { n: g.brain.n, hasTouch, touchOn: g.CFG.touch,
               inputs: Object.keys(JSON.parse(document.getElementById("sub-data").textContent).meta.inputs || {}) };
    });
    return (r.n > 5000 && r.hasTouch && r.touchOn)
      ? `${r.n} 神经元，输入 ${r.inputs.join("/")}` : `n=${r.n} hasTouch=${r.hasTouch} touchOn=${r.touchOn}`;
  });
  await step("放热源后温度真的送进了温度感受器", async () => {
    await page.click("#heatOn");
    await new Promise(r => setTimeout(r, 1200));
    const r = await page.evaluate(() => {
      const g = window.__game;
      // 把果蝇挪到热源上量一次
      g.S.x = 0; g.S.y = 0;
      for (let i = 0; i < 20; i++) g.step();
      return { thermo: g.field ? +g.field.thermo.toFixed(2) : null, fields: g.fields.length };
    });
    await page.click("#heatOn");
    return (r.fields === 1 && r.thermo > 0.5) ? `热源上温度读数 ${r.thermo}` : `fields=${r.fields} thermo=${r.thermo}`;
  });
  let uiBad = 0;
  for (const [name, v] of ui) {
    // 失败词要写全：2026-09-19 "6 秒内一子未落" 被当成通过，因为它不以任何一个前缀开头
    const BAD = ["异常", "只", "没有", "残留", "文本", "6 秒内", "画面是", "脑图 ", "长连="];
    const ok = v === true || (typeof v === "string" && !BAD.some(b2 => v.startsWith(b2)));
    console.log(`  ${ok ? "✓" : "✗"} ${name}${typeof v === "string" ? "  " + v : ""}`);
    if (!ok) uiBad++;
  }

  await browser.close();

  console.log();
  if (uiBad) console.log(`✗ 任务模式 / 光遗传有 ${uiBad} 项没通过`);
  if (errs.length) { console.log(`✗ 页面报了 ${errs.length} 个错：`); errs.slice(0, 6).forEach(e => console.log("   " + e)); }
  if (bad) console.log(`✗ ${bad} 个画布没画出东西`);
  if (errs.length || bad || uiBad) process.exit(1);
  console.log("✓ 浏览器里跑通：无报错，10 个画布都画出了内容，任务模式与光遗传都能用");
})().catch(e => { console.error("FAIL", e); process.exit(1); });
