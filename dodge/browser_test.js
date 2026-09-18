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

  await page.click("#ePre_shapes");
  await page.click("#eRun");
  await page.waitForFunction(
    () => (document.getElementById("eStatus") || {}).textContent?.startsWith("完成："),
    { timeout: 120000 });
  console.log("  " + await page.$eval("#eStatus", e => e.textContent.trim()));

  // 每个画布都必须画出东西：全黑/全白（方差≈0）算失败
  const stats = await page.evaluate(() => {
    const ids = ["eSrc", "eOmm", "eAcc", "eAct", "eRetina", "eLamina", "eMedulla", "eMotion"];
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
  await browser.close();

  console.log();
  if (errs.length) { console.log(`✗ 页面报了 ${errs.length} 个错：`); errs.slice(0, 6).forEach(e => console.log("   " + e)); }
  if (bad) console.log(`✗ ${bad} 个画布没画出东西`);
  if (errs.length || bad) process.exit(1);
  console.log("✓ 浏览器里跑通：无报错，8 个画布都画出了内容");
})().catch(e => { console.error("FAIL", e); process.exit(1); });
