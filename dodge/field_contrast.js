#!/usr/bin/env node
/**
 * 「画出视野」的三个扇区，在球场地板上到底看不看得见 —— 量，不靠眼睛。
 *
 * 起因：右眼扇区原本是金黄 0xe8b339，和地板 #b8763a 同色相；阳光 100% 时
 * 地板是 (255,161,76)，**红通道已经削顶在 255**，暖色叠加抬不动 R，
 * 实测扇区内外只差 Δ=8.4（RGB 欧氏距离），等于没画。换成冷色后 43.3。
 *
 * 做法：果蝇摆到场地中心，相机正上方俯视，按各扇区的角度范围在半径 15 mm 处
 * 采样取平均，和半径 30 mm（扇区之外）的裸地板比 RGB 欧氏距离。
 * 三档阳光都量。把旧配色注回去验证过：7 个（扇区 × 阳光）组合不达标、退出码 1，
 * 也就是说旧配色**三档下都不合格**（左眼 15.7–18.2、右眼 8.4–19.4），
 * 只是 100% 时右眼最差（8.4），所以用户在那里最先看出来。
 *
 * 色块之外还量**边界线**（不透明，沿 R=22 圆弧取最大偏离）：半透明色块叠在
 * 饱和橙地板上出来的只是"更亮/更暗的橙"，色相身份是丢的，真正划出区域的是那道线。
 *
 * 用法：node dodge/field_contrast.js [页面路径或 URL]
 */
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, "..");
const PAGE = process.argv[2] || path.join(ROOT, "docs/game.html");
const MIN = 20;                      // 低于这个值就当作“没画”

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
  await page.goto(/^https?:/.test(PAGE) ? PAGE : "file://" + PAGE, { waitUntil: "load", timeout: 180000 });
  await page.waitForFunction(() => window.__eyeDiag && window.__eyeDiag.head(), { timeout: 180000 });

  const rows = [];
  for (const lv of [0, 50, 100]) {
    rows.push(Object.assign({ lv }, await page.evaluate(lv => {
      const FS = window.__flyScene;
      const sl = document.getElementById("lightSlider");
      sl.value = lv; sl.dispatchEvent(new Event("input"));
      const g = window.__game, S = g.S || g.state;
      S.x = 0; S.y = 0; S.h = 0;
      window.__eyeDiag.forceUpdate();          // 扇区跟着虚拟头部走，得刷一次
      const cam = FS.camera;
      cam.position.set(0, 0, 120); cam.up.set(0, 1, 0); cam.lookAt(0, 0, 0);
      cam.updateProjectionMatrix();
      FS.renderer.render(FS.scene, cam);
      const cv = FS.renderer.domElement;
      const off = document.createElement("canvas");
      off.width = cv.width; off.height = cv.height;
      off.getContext("2d").drawImage(cv, 0, 0);
      const d = off.getContext("2d").getImageData(0, 0, off.width, off.height).data;
      const W = off.width, H = off.height, cx = W / 2, cy = H / 2;
      const mmPx = H / (2 * 120 * Math.tan(21 * Math.PI / 180));   // 视场 42°、相机高 120 mm
      const px = (ang, rmm) => {
        const x = Math.round(cx + Math.cos(ang) * rmm * mmPx);
        const y = Math.round(cy - Math.sin(ang) * rmm * mmPx);
        const i = (y * W + x) * 4; return [d[i], d[i + 1], d[i + 2]];
      };
      const avg = (a0, a1, rmm) => {
        const a = [0, 0, 0]; let n = 0;
        for (let t = a0; t < a1; t += (a1 - a0) / 40) { const c = px(t, rmm); a[0] += c[0]; a[1] += c[1]; a[2] += c[2]; n++; }
        return a.map(v => v / n);
      };
      const half = window.__eyeDiag.HALF_FOV, ax = window.__eyeDiag.EYE_AZ, ov = half - ax;
      const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
      const floor = avg(-(ax + half) + 0.05, -(ax + half) + 0.15, 30);   // 半径 30 > 扇区半径 22
      const L = avg(ov + 0.1, ax + half - 0.1, 15);
      const R = avg(-(ax + half) + 0.1, -ov - 0.1, 15);
      const O = avg(-ov + 0.05, ov - 0.05, 15);
      // 边界线：沿 R=22 的圆弧扫一圈，取**最亮的偏离**（线只有 1 px，平均会被地板稀释）
      let edge = 0;
      for (let t = -(ax + half) + 0.05; t < ax + half; t += 0.01)
        for (const rr of [21.6, 21.8, 22.0, 22.2])
          edge = Math.max(edge, dist(px(t, rr), floor));
      return { floor: floor.map(Math.round), edge: +edge.toFixed(1),
               dO: +dist(O, floor).toFixed(1), dL: +dist(L, floor).toFixed(1), dR: +dist(R, floor).toFixed(1) };
    }, lv)));
  }
  await browser.close();

  console.log("扇区内 vs 裸地板的 RGB 欧氏距离（越大越看得见）");
  console.log("");
  console.log("阳光   裸地板           双眼重叠  左眼单眼  右眼单眼   边界线");
  let bad = 0;
  for (const r of rows) {
    const f = x => String(x).padStart(9);
    console.log((r.lv + "%").padEnd(6) + " " + r.floor.join(",").padEnd(16) + f(r.dO) + f(r.dL) + f(r.dR) + f(r.edge));
    for (const v of [r.dO, r.dL, r.dR]) if (v < MIN) bad++;
    if (r.edge < 60) bad++;          // 边界线是不透明的，本来就该远高于色块
  }
  console.log("");
  fs.writeFileSync(path.join(ROOT, "results/dodge/field_contrast.json"), JSON.stringify({ min: MIN, rows }, null, 1));
  if (bad) { console.log("✗ 有 " + bad + " 个（扇区 × 阳光）组合的对比度 < " + MIN + "，等于没画"); process.exit(1); }
  console.log("✓ 三个扇区在 0/50/100% 阳光下色块对比度都 ≥ " + MIN + "、边界线 ≥ 60");
})().catch(e => { console.error("FAIL", e); process.exit(1); });
