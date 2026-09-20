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
  // THROTTLE=6 node dodge/browser_test.js：把浏览器 CPU 限到 1/6，在本机模拟没有 GPU 的 CI 机器，专门用来抓"按墙上时间等"的脆弱测试
  if (process.env.THROTTLE) await page.emulateCPUThrottling(+process.env.THROTTLE);

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
  await step("五子棋：真脑现场重跑与价值表一致", async () => {
    const r = await page.evaluate(() => {
      const SUBd = JSON.parse(document.getElementById("sub-data").textContent);
      const PT = JSON.parse(document.getElementById("gomoku-readout").textContent);
      const G = window.Gomoku, p = window.GomokuFly2.makeLinePlayer(SUBd, window.FlyDodgeBrain.ConnectomeBrain, PT.black, { seed: 11 });
      const b = G.newBoard(); [[7, 7, 1], [8, 7, 2], [7, 8, 1], [8, 8, 2], [7, 6, 1]].forEach(([x, y, c]) => { b[G.idx(x, y)] = c; });
      const c = p.choose(b, 2, { depth: 4, vcf: true }), st = p.inspect(b, 2, c.move);
      return { move: c.move, block: G.idx(7, 5), block2: G.idx(7, 9), runs: st.liveCheck.runs, diff: st.liveCheck.max_rel_diff, depth: c.depth, how: c.how };
    });
    if (!(r.diff < 1e-3)) return `真脑现场重算与表对不上：最大相对偏差 ${r.diff}`;
    if (r.move !== r.block && r.move !== r.block2) return `黑方竖着活三，白蝇没去挡（走了 ${r.move}）`;
    return `白蝇挡住了黑的活三；真脑重跑 ${r.runs} 次，与表的最大相对偏差 ${r.diff.toExponential(1)}`;
  });
  await step("五子棋：推理步数随时可切、立即生效", async () => {
    const r = await page.evaluate(async () => {
      const g = window.__gm, btns = [...document.querySelectorAll("#gmDepthSeg button")];
      if (!btns.length) return { err: "没有推理步数按钮" };
      document.getElementById("gmSelf").click(); await new Promise(x => setTimeout(x, 600));       // 让它开始想
      const before = g.state.thought ? g.state.thought.t : -1;
      const target = btns.find(b => b.getAttribute("aria-pressed") !== "true") || btns[0]; target.click();
      const afterBusy = g.state.busy, d = g.state.depth;
      await new Promise(x => setTimeout(x, 400));
      return { n: btns.length, d, want: +target.dataset.d, restarted: afterBusy === false || (g.state.thought && g.state.thought.t < 0.45), before, list: g.depths };
    });
    if (r.err) return r.err;
    return (r.d === r.want && r.restarted) ? `共 ${r.n} 档（${r.list.join("/") || "只有主表"}）；想到一半切到 ${r.d} 步，这一步立刻按新模型重想` : JSON.stringify(r);
  });
  await step("五子棋：思考过程画在棋盘上（候选点概率 + 预想的后续）", async () => {
    const r = await page.evaluate(async () => {
      const g = window.__gm; let seen = null;
      for (let k = 0; k < 60 && !seen; k++) { const T = g.state.thought; if (T && T.pol.length && T.seq.length) seen = { pol: T.pol.length, seq: T.seq.length, p0: T.pol[0].p, first: T.seq[0].cell, top: T.pol[0].cell, search: T.searching }; await new Promise(x => setTimeout(x, 100)); }
      return seen;
    });
    if (!r) return "✗ 6 秒内没看到思考过程";
    return (r.first === r.top && !r.search) ? `候选点 ${r.pol} 个（首选把握 ${(r.p0 * 100).toFixed(0)}%），预想后续 ${r.seq} 步；没有搜索` : JSON.stringify(r);
  });
  await step("五子棋：立体棋盘上点一下就能落子", async () => {
    await page.click("#gmHuman"); await page.click("#gmView3d");
    await page.evaluate(() => document.getElementById("gmStage").scrollIntoView({ block: "center" }));
    await new Promise(r => setTimeout(r, 1500));
    const pt = await page.evaluate(() => { const g = window.__gm, cv = document.getElementById("gmStage"), rect = cv.getBoundingClientRect();
      // 在画布上扫一遍，找到能拾取到天元 (7,7) 的屏幕点
      for (let y = 20; y < rect.height; y += 6) for (let x = 20; x < rect.width; x += 6) {
        const X = rect.left + x, Y = rect.top + y;
        if (Y < 0 || Y > innerHeight || document.elementFromPoint(X, Y) !== cv) continue;          // 必须真的点得到画布（没被别的元素盖住、在视口内）
        if (g.pick3d(X, Y) === 7 * 15 + 7) return { x: X, y: Y };
      }
      return null; });
    if (!pt) return "✗ 立体模式下拾取不到天元";
    await page.mouse.click(pt.x, pt.y);
    await new Promise(r => setTimeout(r, 1200));
    const r = await page.evaluate(() => ({ center: window.__gm.state.board[7 * 15 + 7], n: window.__gm.state.board.filter(v => v).length }));
    await page.click("#gmView2d"); await page.click("#gmSelf");        // 后面几项要看果蝇自己在想、在放电
    return r.center === 1 ? `点天元 → 黑子落在天元（盘上 ${r.n} 子）` : `✗ 点了天元但没落子（${JSON.stringify(r)}，点击位置 ${JSON.stringify(pt)}）`;
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
  await step("生活模式：五感全开，世界自己运转，球场冻结", async () => {
    const t0 = await page.evaluate(() => window.__game.S.t);
    await page.click("#viewLife");
    for (let k = 0; k < 80; k++) { await new Promise(r => setTimeout(r, 500)); if (await page.evaluate(() => window.__life && window.__life.body.age > 2.2)) break; }   // 不按墙上时间等（慢机器上 6 s 只走 1.3 s 模拟时间）
    const r = await page.evaluate(() => { const g = window.__life, cv = document.getElementById("lifeStage"); if (!g) return null;
      const d = cv.getContext("2d").getImageData(0, 0, cv.width, cv.height).data; let n = 0, s1 = 0, s2 = 0; for (let i = 0; i < d.length; i += 16) { const v = (d[i] + d[i + 1] + d[i + 2]) / 3; n++; s1 += v; s2 += v * v; }
      g.addSound(g.S.x + 10, g.S.y, 1.5, 1.0); for (let k = 0; k < 40; k++) g.step(); const heard = Math.max(g.senses.audioL, g.senses.audioR);
      return { age: g.body.age, n: g.brain.n, v4: g.V4, mode: window.__stageMode, sd: Math.sqrt(Math.max(0, s2 / n - (s1 / n) ** 2)), heard, things: g.pellets.length + g.odors.length + g.fields.length, diary: window.__lifeApi.diary.length, court: window.__game.S.t }; });
    if (!r) return "✗ 生活模式没有启动";
    if (!(r.v4 && r.age > 2 && r.sd > 5 && r.heard > 50 && r.mode === "life")) return "✗ " + JSON.stringify(r);
    if (Math.abs(r.court - t0) > 1e-9) return `✗ 球场那只没有冻结（${t0} → ${r.court}）`;
    return `${r.n} 个神经元的大脑已经活了 ${r.age.toFixed(0)} s；放一声响，听觉神经元到 ${r.heard.toFixed(0)} Hz；世界里有 ${r.things} 样东西，意识流 ${r.diary} 条；球场冻结`;
  });
  await step("生活模式：蘑菇体会学（气味 + 多巴胺 → 突触被压低），六条腿推着身体走，神经元遥控有效", async () => {
    const r = await page.evaluate(() => { const g = window.__life; if (!g || !g.MB || !g.legs) return null;
      // ① 学习：把它钉在气味 A 的中心，喷 PAM 多巴胺；对照：气味 B 不喷
      g.CFG.life = false; g.pellets.length = 0; g.odors.length = 0; g.fields.length = 0; g.forget(); const S = g.S;
      const sniff = (kind, puff) => { g.odors.length = 0; g.addOdor(S.x + 1, S.y, kind, 40, 1, 1e9); for (let k = 0; k < 400; k++) { if (puff && k % 50 === 0) g.puff(puff, 1); g.step(); } g.odors.length = 0; for (let k = 0; k < 100; k++) g.step(); };
      sniff("A", "PAM"); sniff("B", null); const mA = g.memoryOf("A"), mB = g.memoryOf("B");
      // ② 腿：直行时身体的位移来自腿；截掉左前腿之后会偏航
      const walk = () => { const x0 = S.x, y0 = S.y, h0 = S.h; for (let k = 0; k < 300; k++) g.step(); return { d: Math.hypot(S.x - x0, S.y - y0), dh: (S.h - h0) * 180 / Math.PI }; };
      const w0 = walk(); g.legs.amputate("LF", true); const w1 = walk(); g.legs.amputate("LF", false);
      // ③ 遥控：按住「DNa 左」→ 读出的左侧 DNa 明显升高
      const before = g.readout().dnaL; document.querySelector('#lifeRemote [data-remote="dnaL"]').dispatchEvent(new PointerEvent("pointerdown", { bubbles: true })); for (let k = 0; k < 60; k++) g.step(); const during = g.readout().dnaL;
      document.querySelector('#lifeRemote [data-remote="dnaL"]').dispatchEvent(new PointerEvent("pointerup", { bubbles: true })); g.CFG.life = true;
      return { n: g.brain.n, mA, mB, w0, w1, before, during, stance: g.legs.state.nStance }; });
    if (!r) return "✗ 生活模式里没有蘑菇体或六条腿";
    if (!(r.mA && r.mA.PAM < 0.7)) return "✗ 配对过的气味 A 没被记住：" + JSON.stringify(r.mA);
    if (!(r.mB && r.mB.PAM > 0.85)) return "✗ 没配对的气味 B 也被压低了：" + JSON.stringify(r.mB);
    if (!(r.w0.d > 3)) return "✗ 六条腿没把身体推动：" + JSON.stringify(r.w0);
    if (!(r.during > r.before + 30)) return `✗ 遥控无效（DNa 左 ${r.before.toFixed(0)} → ${r.during.toFixed(0)} Hz）`;
    return `${r.n} 个神经元；气味 A 配奖赏多巴胺后，奖赏隔室的输入剩 ${(r.mA.PAM * 100).toFixed(0)}%（没配对的 B 剩 ${(r.mB.PAM * 100).toFixed(0)}%）；六条腿 1.5 s 走了 ${r.w0.d.toFixed(1)} mm，截掉左前腿后走 ${r.w1.d.toFixed(1)} mm、偏航 ${r.w1.dh.toFixed(0)}°；遥控 DNa 左 ${r.before.toFixed(0)} → ${r.during.toFixed(0)} Hz`;
  });
  await step("生活模式：15,055 个神经元在浏览器里跑得动（只报告速度）", async () => {
    const a = await page.evaluate(() => ({ t: window.__life.body.age, w: performance.now() })); await new Promise(r => setTimeout(r, 4000));
    const b = await page.evaluate(() => ({ t: window.__life.body.age, w: performance.now(), n: window.__life.brain.n }));
    const rt = (b.t - a.t) / ((b.w - a.w) / 1000); if (!(rt > 0.05)) return `✗ 几乎不动：${rt.toFixed(3)} × 实时`;
    return `${rt.toFixed(2)} × 实时（无头浏览器${process.env.CI ? "，CI 软件渲染" : ""}，${b.n} 个神经元，稠密推进）`;
  });
  await step("学习卡片：五张表都从 learn_summary.json 渲染出来了", async () => {
    const r = await page.evaluate(() => ({ err: window.__learnCardError || null, rows: ["tLearnRunaway", "tLearnCond", "tLearnMotor", "tLearnBody", "tLearnLegs"].map(id => document.getElementById(id) ? document.getElementById(id).rows.length : 0), note: (document.getElementById("lnNote2") || {}).textContent || "" }));
    if (r.err) return "✗ " + r.err; if (r.rows.some(n => n < 3)) return "✗ 有表是空的：" + JSON.stringify(r.rows); if (/undefined|NaN/.test(r.note)) return "✗ 说明文字里有 undefined / NaN";
    return "各表行数 " + r.rows.join(" / ");
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
    if (!before || before.length !== 2) return "没有同伴模块或数量不对";
    // 不按墙上时间等：CI 没有 GPU，页面每秒只有一两帧，2.5 s 里模拟时间走不了多少。最多等 25 s，两只都走出 1 mm 就立刻通过。
    let after = before, moved = 0;
    for (let k = 0; k < 50 && moved < 2; k++) {
      await new Promise(r => setTimeout(r, 500));
      after = await page.evaluate(() => window.__comp.list.map(c => [c.S.x, c.S.y]));
      moved = before.filter((p, i) => Math.hypot(after[i][0] - p[0], after[i][1] - p[1]) > 1).length;
    }
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
    // 前缀表很脆（靠它漏判过两次）。新写的测试一律用「✗ 」开头表示失败；失败分支里直接转储的 JSON 也算失败。
    const ok = v === true || (typeof v === "string" && !v.startsWith("✗") && !v.startsWith("{") && !BAD.some(b2 => v.startsWith(b2)));
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
