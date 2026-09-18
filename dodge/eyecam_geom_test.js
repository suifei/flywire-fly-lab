#!/usr/bin/env node
/**
 * 复眼视窗的**几何校验**：在已知方位角放一个亮标记，核对它出现在视野图的哪个位置。
 *
 * 为什么必须有这个：前面的浏览器测试只验证"画布有内容"，方差够大就算过。
 * 但鱼眼映射、±63.1° 光轴、方向表、全景映射里任何一处符号搞反，
 * 画面照样"有内容"，只是**看到的世界是错的**。这个项目已经吃过一次这种亏
 * （超分辨那次：画面看着变平滑了，指标却在说谎）。
 *
 * 判据：标记的实测方位角与放置方位角之差 < 12°（小眼间角约 4.5°，
 * 加上全景图的像素量化，这个容差是合理的）。
 *
 * 用法：node dodge/eyecam_geom_test.js [页面路径或 URL]
 */
const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "..");
const PAGE = process.argv[2] || path.join(ROOT, "docs/game.html");

function loadPuppeteer() {
  for (const p of ["puppeteer-core", "puppeteer",
                   path.join(ROOT, "studio/capture/node_modules/puppeteer-core"),
                   path.join(ROOT, "studio/capture/node_modules/puppeteer")]) {
    try { return require(p); } catch (e) {}
  }
  return null;
}
function chromePath() {
  return [process.env.CHROME_PATH,
          "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
          "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium-browser"]
    .filter(Boolean).find(p => { try { return fs.existsSync(p); } catch { return false; } });
}

// 放在这些方位角上（相对果蝇头部前方，度）。180° 在盲区，应该看不见。
const CASES = [0, 30, -30, 60, -60, 100, -100, 180];

(async () => {
  const strict = !!process.env.CI;
  const puppeteer = loadPuppeteer(), exe = chromePath();
  if (!puppeteer || !exe) {
    const m = !puppeteer ? "没有 puppeteer-core" : "找不到 Chrome";
    if (strict) { console.error("✗ " + m); process.exit(1); }
    console.log("跳过：" + m); process.exit(0);
  }
  const isUrl = /^https?:\/\//.test(PAGE);
  const browser = await puppeteer.launch({ executablePath: exe, headless: "new",
    args: ["--no-sandbox", "--disable-dev-shm-usage", "--allow-file-access-from-files"] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1200, height: 900 });
  const errs = [];
  page.on("pageerror", e => errs.push(e.message));
  await page.goto(isUrl ? PAGE : "file://" + PAGE, { waitUntil: "load", timeout: 180000 });
  await page.waitForFunction(() => window.__eyeDiag && window.__eyeDiag.head(), { timeout: 180000 });
  // 暂停游戏：否则果蝇一边走一边转，标记的真实方位会在测量过程中漂掉
  await page.evaluate(() => {
    const b = document.getElementById("pause");
    if (b && !/继续/.test(b.textContent)) b.click();
  });
  await new Promise(r => setTimeout(r, 400));

  const out = await page.evaluate(async (CASES) => {
    const T = window.__flyScene.THREE, sc = window.__flyScene.scene;
    const D = window.__eyeDiag;
    // 头部网格本地轴实测：+x 前、+y 上、+z 右（不是 +z 上 —— 这个错误假设
    // 一开始同时污染了实现和这个测试，导致测试"验证"了一个错误的几何）。
    // 每个测例都重新读位姿：即使暂停了，也不假设它一定没动。
    const readHead = () => {
      const h = D.head();
      const hp = new T.Vector3(), hq = new T.Quaternion();
      h.getWorldPosition(hp); h.getWorldQuaternion(hq);
      return { hp, hq };
    };
    let { hp, hq } = readHead();

    // **直接测数据，不测渲染结果**。
    // 之前一直隔着全景画布量，而那张图每帧按全局 lo/hi 归一化 ——
    // 标记一进视野就把范围撑大、整幅变暗，差分指标一直在和归一化搏斗，
    // 连续三次改指标都没绕过去。这里直接拿小眼读数和方向表算，没有渲染伪影。
    const mark = new T.Mesh(new T.SphereGeometry(1.6, 16, 16),
                            new T.MeshBasicMaterial({ color: 0xffffff }));
    sc.add(mark);
    const perm = D.perm(), dirs = D.dirs();
    const res = [];
    for (const deg of CASES) {
      mark.visible = false;
      const base = D.forceUpdate();
      ({ hp, hq } = readHead());
      const a = deg * Math.PI / 180;
      const dir = new T.Vector3(Math.cos(a), 0, -Math.sin(a)).applyQuaternion(hq);
      mark.position.copy(hp).add(dir.multiplyScalar(9));
      mark.visible = true;
      const now = D.forceUpdate();
      // 找增量最大的那个小眼（两只眼一起找），报它的方位角
      let bestAz = NaN, bestEl = NaN, bv = -1e9, eye = -1, n = 0;
      for (let e = 0; e < 2; e++) {
        const { az, el } = dirs[e], b = base[e], w = now[e];
        for (let j = 0; j < w.length; j++) {
          const k = perm[j];
          if (!Number.isFinite(az[k])) continue;
          const dv = w[j] - b[j];
          if (dv > 0.02) n++;
          if (dv > bv) { bv = dv; bestAz = az[k] * 180 / Math.PI; bestEl = el[k] * 180 / Math.PI; eye = e; }
        }
      }
      res.push({ deg, az: +bestAz.toFixed(1), el: +bestEl.toFixed(1),
                 gain: +bv.toFixed(3), n, eye: eye === 0 ? "左" : eye === 1 ? "右" : "-" });
    }
    sc.remove(mark);
    return res;
  }, CASES);

  console.log(`${"放置方位".padStart(8)}${"实测方位".padStart(10)}${"误差".padStart(8)}${"仰角".padStart(8)}${"哪只眼".padStart(8)}${"亮起小眼".padStart(10)}`);
  let bad = 0;
  const seen = [];
  const maxN = Math.max(...out.filter(r => Math.abs(r.deg) <= 141.6).map(r => r.n));
  for (const r of out) {
    const blind = Math.abs(r.deg) > 141.6;          // 157/2 + 63.1 = 141.6°，之外是盲区
    const err = Math.abs(((r.az - r.deg + 540) % 360) - 180);
    // 盲区里那个方位应该**几乎看不见**：亮度增量远小于可见方位
    const ok = blind ? (r.n < 0.2 * maxN) : err < 12;
    if (!blind) seen.push(err);
    if (!ok) bad++;
    console.log(`${String(r.deg).padStart(8)}${String(r.az).padStart(10)}` +
                `${(blind ? "—(盲区)" : err.toFixed(1)).padStart(8)}${String(r.el).padStart(8)}${String(r.eye).padStart(8)}${String(r.n).padStart(10)}  ${ok ? "✓" : "✗"}`);
  }
  await browser.close();
  console.log();
  if (errs.length) { console.log(`✗ 页面报错 ${errs.length} 个：${errs[0]}`); process.exit(1); }
  if (bad) {
    console.log(`✗ ${bad}/${out.length - 1} 个方位对不上 —— 鱼眼映射 / 光轴符号 / 方向表 有一处搞反了`);
    process.exit(1);
  }
  const mean = seen.reduce((a, b) => a + b, 0) / Math.max(seen.length, 1);
  console.log(`✓ 视野几何正确：${seen.length} 个可见方位平均误差 ${mean.toFixed(1)}°（小眼间角约 4.5°）`);
})().catch(e => { console.error("FAIL", e); process.exit(1); });
