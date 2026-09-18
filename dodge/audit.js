#!/usr/bin/env node
/**
 * 总审计：把每个功能当一道题，逐条核对**数值**，不看"有没有内容"。
 *
 * 动机：这个项目反复栽在同一个地方 —— 工具通过 ≠ 东西是对的。
 *   · node --check 全过，线上白屏（标签模板）
 *   · 画布有方差就算过，其实视线一直在看天（头部轴假设错了）
 *   · 累积图"看着变平滑了"，指标却在说谎（坐标系开错）
 * 所以这里查的是可证伪的数：角度、计数、边界、范围。
 *
 * 用法：node dodge/audit.js [页面路径或 URL]
 */
const fs = require("fs"), path = require("path");
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
const chromePath = () => [process.env.CHROME_PATH,
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium-browser"]
  .filter(Boolean).find(p => { try { return fs.existsSync(p); } catch { return false; } });

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
  page.on("pageerror", e => errs.push("pageerror: " + e.message));
  page.on("console", m => { if (m.type() === "error") errs.push("console: " + m.text()); });
  await page.goto(isUrl ? PAGE : "file://" + PAGE, { waitUntil: "load", timeout: 180000 });
  await page.waitForFunction(() => window.__eyeDiag && window.__eyeDiag.head(), { timeout: 180000 });

  const R = await page.evaluate(() => {
    const out = [];
    const ok = (name, pass, got, want) => out.push({ name, pass: !!pass, got: String(got), want });
    const D = window.__eyeDiag, FS = window.__flyScene, T = FS.THREE;
    const G = window.FlyDodgeGame;

    // ── 视觉资产 ──────────────────────────────────────────
    const net = JSON.parse(document.getElementById("flyvis-data").textContent);
    const taps = Object.values(net.kernels).reduce((a, k) => a + k.length, 0);
    ok("flyvis 细胞类型数", net.types.length === 65, net.types.length, "65");
    ok("flyvis 卷积抽头数", taps === 2355, taps, "2355");
    const ret = JSON.parse(document.getElementById("retina-data").textContent);
    ok("小眼数", ret.n_ommatidia === 721, ret.n_ommatidia, "721");
    ok("相机画面尺寸（上传图那条链路用）", ret.width === 450 && ret.height === 512,
       `${ret.width}×${ret.height}`, "450×512");
    const pale = ret.pale_type_mask.reduce((a, b) => a + b, 0);
    ok("pale 型小眼（读蓝通道）", pale === 216, pale, "216");
    ok("yellow 型小眼（读绿通道）", 721 - pale === 505, 721 - pale, "505");
    const dec = JSON.parse(document.getElementById("decoders-data").textContent);
    ok("解码器层数", Object.keys(dec.layers).length === 4, Object.keys(dec.layers).length, "4");
    ok("解码器留出整张图测试", dec.n_test_images >= 2, dec.n_test_images + " 张", "≥2");

    // ── 复眼视窗几何 ──────────────────────────────────────
    const half = D.HALF_FOV * 180 / Math.PI, fovy = 2 * half, az = D.EYE_AZ * 180 / Math.PI;
    ok("小眼间角 Δφ", Math.abs(D.DPHI * 180 / Math.PI - 5.7) < 0.01,
       (D.DPHI * 180 / Math.PI).toFixed(1) + "°", "5.7°");
    ok("单眼视野 = 2×15×Δφ", Math.abs(fovy - 171) < 0.2, fovy.toFixed(1) + "°", "171°");
    ok("光轴方位角（MuJoCo 实测）", Math.abs(az - 63.1) < 0.05, az.toFixed(1) + "°", "63.1°");
    const binoc = fovy - 2 * az, total = fovy + 2 * az, blind = 360 - total;
    ok("双眼重叠 = 单眼视野 − 2×光轴", Math.abs(binoc - 44.8) < 0.2, binoc.toFixed(1) + "°", "44.8°");
    ok("总视野 = 单眼视野 + 2×光轴", Math.abs(total - 297.2) < 0.2, total.toFixed(1) + "°", "297.2°");
    ok("背后盲区", Math.abs(blind - 62.8) < 0.2, blind.toFixed(1) + "°", "62.8°");

    // 方向表：两眼应对称，且范围接近 ±fovy/2 绕各自光轴
    const dirs = D.dirs();
    const rng = dirs.map(d => {
      let lo = 1e9, hi = -1e9, n = 0;
      for (const v of d.az) { if (!Number.isFinite(v)) continue; const g = v * 180 / Math.PI;
        if (g < lo) lo = g; if (g > hi) hi = g; n++; }
      return { lo, hi, mid: (lo + hi) / 2, half: (hi - lo) / 2, n };
    });
    ok("左眼方向表中心 ≈ +63.1°", Math.abs(rng[0].mid - 63.1) < 4, rng[0].mid.toFixed(1) + "°", "63.1°±4");
    ok("右眼方向表中心 ≈ −63.1°", Math.abs(rng[1].mid + 63.1) < 4, rng[1].mid.toFixed(1) + "°", "−63.1°±4");
    ok("两眼方向表对称", Math.abs(rng[0].mid + rng[1].mid) < 3,
       (rng[0].mid + rng[1].mid).toFixed(1), "≈0");
    ok("方向表覆盖 = 单眼半视野", Math.abs(rng[0].half - half) < 1,
       rng[0].half.toFixed(1) + "°", half.toFixed(1) + "°");
    // 每个小眼与本眼光轴的球面夹角必须都 ≤ 半视野（方位等距投影的定义）
    let maxSep = 0;
    for (let e = 0; e < 2; e++) {
      const d = dirs[e], A = (e ? -1 : 1) * D.EYE_AZ;
      for (let i = 0; i < d.az.length; i++) {
        const c = Math.cos(d.el[i]) * Math.cos(d.az[i] - A);
        const sep = Math.acos(Math.max(-1, Math.min(1, c))) * 180 / Math.PI;
        if (sep > maxSep) maxSep = sep;
      }
    }
    ok("小眼与光轴最大夹角 = 半视野", Math.abs(maxSep - half) < 0.5,
       maxSep.toFixed(1) + "°", half.toFixed(1) + "°");
    // 紫外通道必须真的有数据，且与彩色通道不同（否则是同一路复制的）
    const rr = D.forceUpdate();
    let du = 0;
    for (let i = 0; i < rr.uv[0].length; i++) du += Math.abs(rr.uv[0][i] - rr.color[0][i]);
    ok("紫外通道与彩色通道不同", du / rr.uv[0].length > 0.02,
       (du / rr.uv[0].length).toFixed(4), ">0.02");
    ok("有效小眼数（扣掉鱼眼奇点外）", rng[0].n > 600 && rng[0].n <= 721, rng[0].n, "600–721");

    // 两只眼必须给出**不同**的读数（否则是同一台相机渲了两次）
    const rd0 = D.forceUpdate(), rd = rd0.color;
    let diff = 0;
    for (let i = 0; i < rd[0].length; i++) diff += Math.abs(rd[0][i] - rd[1][i]);
    ok("左右眼读数不同（不是同一台相机）", diff / rd[0].length > 0.01,
       (diff / rd[0].length).toFixed(4), ">0.01");

    // ── 场地边界 ──────────────────────────────────────────
    const CFG = G.DEFAULTS;
    ok("场地比例 = 篮球场 28:15", Math.abs(CFG.courtW / CFG.courtH - 28 / 15) < 0.02,
       (CFG.courtW / CFG.courtH).toFixed(3), "1.867");
    // 把果蝇扔到场外，跑一步，必须被夹回来
    const g = window.__game;
    let clamped = "没拿到 game 实例";
    const St = g && (g.S || g.state);
    if (g && St) {
      St.x = CFG.courtW; St.y = CFG.courtH;
      if (g.step) g.step(0.02);
      clamped = `(${St.x.toFixed(0)}, ${St.y.toFixed(0)})`;
      ok("果蝇出不了场地", Math.abs(St.x) <= CFG.courtW / 2 && Math.abs(St.y) <= CFG.courtH / 2,
         clamped, `|x|≤${CFG.courtW / 2}, |y|≤${CFG.courtH / 2}`);
    } else {
      ok("果蝇出不了场地", false, clamped, "需要 window.__game");
    }

    // ── 视野投影 ──────────────────────────────────────────
    const fans = [];
    FS.scene.traverse(o => { if (o.geometry && o.geometry.type === "CircleGeometry" &&
                                 o.geometry.parameters.thetaLength < 6.2) fans.push(o.geometry.parameters); });
    const spans = fans.map(p => p.thetaLength * 180 / Math.PI).sort((a, b) => a - b);
    ok("视野投影有 3 个扇区", fans.length === 3, fans.length, "3");
    if (spans.length === 3) {
      ok("重叠扇区 = 双眼重叠角", Math.abs(spans[0] - binoc) < 0.5, spans[0].toFixed(1) + "°", binoc.toFixed(1) + "°");
      ok("两个单眼扇区相等", Math.abs(spans[1] - spans[2]) < 0.5,
         `${spans[1].toFixed(1)}° / ${spans[2].toFixed(1)}°`, "相等");
      ok("三扇区合计 = 总视野", Math.abs(spans[0] + spans[1] + spans[2] - total) < 1,
         (spans[0] + spans[1] + spans[2]).toFixed(1) + "°", total.toFixed(1) + "°");
    }
    return out;
  });

  await browser.close();
  const w = Math.max(...R.map(r => r.name.length)) + 2;
  let bad = 0;
  for (const r of R) {
    if (!r.pass) bad++;
    console.log(`${r.pass ? "✓" : "✗"} ${r.name.padEnd(w)}${String(r.got).padStart(16)}   期望 ${r.want}`);
  }
  console.log();
  if (errs.length) { console.log(`✗ 页面报错 ${errs.length} 个：${errs[0]}`); bad++; }
  if (bad) { console.log(`✗ ${bad} 项不通过`); process.exit(1); }
  console.log(`✓ ${R.length} 项全部通过`);
})().catch(e => { console.error("FAIL", e); process.exit(1); });
