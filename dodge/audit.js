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
  await page.evaluateOnNewDocument(l => { try { localStorage.setItem("fly-lang", l); } catch (e) {} }, process.env.LANG_UI || "zh");   // 这些检查针对中文界面；英文模式由 i18n/residue.js 单独测
  await page.setViewport({ width: 1200, height: 900 });
  const errs = [];
  page.on("pageerror", e => errs.push("pageerror: " + e.message));
  page.on("console", m => { if (m.type() === "error") errs.push("console: " + m.text()); });
  await page.goto((isUrl ? PAGE : "file://" + PAGE) + "?scene=court", { waitUntil: "load", timeout: 180000 });   // 这些检查针对球场版（v3）；页面默认进的是大自然
  await page.waitForFunction(() => window.__eyeDiag && window.__eyeDiag.head(), { timeout: 180000 });

  const R = await page.evaluate(async IN_CI => {
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
    // ── 固定光源与阴影 ────────────────────────────────────
    const lights = [];
    FS.scene.traverse(o => { if (o.isDirectionalLight && o.castShadow) lights.push(o); });
    ok("阴影总开关", FS.renderer.shadowMap.enabled === true, FS.renderer.shadowMap.enabled, "true");
    ok("投射阴影的固定光源数", lights.length >= 4, lights.length, "≥4");
    // 阴影贴图只有真的渲染过才会被分配；只配 castShadow 不渲染的话它是 null
    ok("阴影贴图已实际渲染", lights.length > 0 && lights.every(l => l.shadow.map),
       lights.filter(l => l.shadow.map).length + "/" + lights.length, "全部");
    // 计数：谁投、谁收
    let casters = 0, receivers = 0;
    FS.scene.traverse(o => { if (o.isMesh) { if (o.castShadow) casters++; if (o.receiveShadow) receivers++; } });
    ok("阴影投射体", casters > 0, casters, ">0");
    ok("阴影接收面", receivers > 0, receivers, ">0");
    // 关键一题：每盏灯的阴影相机要装得下**整个场景**。
    // （远裁面短了一截就是之前那个 bug —— 远处物体直接没影子。）
    const box = new T.Box3();
    FS.scene.traverse(o => { if (o.isMesh && (o.castShadow || o.receiveShadow)) box.expandByObject(o); });
    const corners = [];
    for (const x of [box.min.x, box.max.x]) for (const y of [box.min.y, box.max.y])
      for (const z of [box.min.z, box.max.z]) corners.push(new T.Vector3(x, y, z));
    let worst = -1, worstName = "";
    for (const L of lights) {
      L.shadow.updateMatrices(L);
      const c = L.shadow.camera;
      const fr = new T.Frustum().setFromProjectionMatrix(
        new T.Matrix4().multiplyMatrices(c.projectionMatrix, c.matrixWorldInverse));
      const miss = corners.filter(v => !fr.containsPoint(v)).length;
      if (miss > worst) { worst = miss; worstName = `${miss}/8 角落在外`; }
    }
    ok("每盏灯的阴影相机装得下整个场景", worst === 0, worstName || "无光源", "0/8 在外");
    const sz = lights.length ? lights[0].shadow.mapSize.x : 0;
    ok("阴影贴图分辨率", sz >= 2048, sz, "≥2048");

    // ── 深度精度（z-fighting 防线）────────────────────────
    // 两层地面曾经只差 0.034 mm，远处深度分不开 → 放射状条纹。
    const planes = [];
    FS.scene.traverse(o => {
      if (!o.isMesh || !o.geometry) return;
      const t = o.geometry.type;
      if (t !== "PlaneGeometry" && t !== "CircleGeometry") return;
      const p = o.geometry.parameters;
      const big = t === "PlaneGeometry" ? Math.min(p.width, p.height) : p.radius * 2;
      if (big < 100 || (p.thetaLength && p.thetaLength < 6.2)) return;
      o.updateWorldMatrix(true, false);
      planes.push({ name: o.name || t, z: new T.Vector3().setFromMatrixPosition(o.matrixWorld).z });
    });
    planes.sort((a, b) => a.z - b.z);
    let minGap = Infinity;
    for (let i = 1; i < planes.length; i++) minGap = Math.min(minGap, planes[i].z - planes[i - 1].z);
    ok("大平面层间距（够远处深度分辨）", planes.length < 2 || minGap >= 1,
       planes.length < 2 ? "只有 " + planes.length + " 层" : minGap.toFixed(3) + " mm", "≥1 mm");
    const ratio = FS.camera.far / FS.camera.near;
    ok("相机远近裁面比值", ratio <= 1000, Math.round(ratio) + ":1", "≤1000:1");

    // ── 三通道合成 / 去马赛克 ─────────────────────────────
    const cam = D.instance(), cvB = document.getElementById("ecB"), cvUV = document.getElementById("ecUV");
    ok("去马赛克输出 = 每小眼两路（G,B 交错）",
       rr.gb && rr.gb[0].length === rr.color[0].length * 2,
       rr.gb ? rr.gb[0].length : "无", rr.color[0].length * 2);
    // G 和 B 必须真的不同，否则去马赛克只是把同一路复制了一遍
    let dgb = 0;
    for (let i = 0; i < rr.gb[0].length; i += 2) dgb += Math.abs(rr.gb[0][i] - rr.gb[0][i + 1]);
    ok("去马赛克的绿/蓝两路不同", dgb / (rr.gb[0].length / 2) > 0.005,
       (dgb / (rr.gb[0].length / 2)).toFixed(4), ">0.005");
    const px = cv => { const c = cv.getContext("2d").getImageData(0, 0, cv.width, cv.height).data;
                       let col = 0, lit = 0;
                       for (let i = 0; i < c.length; i += 4) {
                         if (c[i] + c[i + 1] + c[i + 2] < 24) continue; lit++;
                         if (Math.abs(c[i] - c[i + 1]) > 8 || Math.abs(c[i + 1] - c[i + 2]) > 8) col++; }
                       return { col, lit, frac: lit ? col / lit : 0 }; };
    const save = cam.demosaic;
    cam.demosaic = true; D.forceUpdate();
    const bOn = px(cvB), uOn = px(cvUV);
    ok("合成视野面板是彩色的", bOn.frac > 0.1, (bOn.frac * 100).toFixed(0) + "% 彩色像素", ">10%");
    ok("紫外面板是三通道合成", uOn.frac > 0.1, (uOn.frac * 100).toFixed(0) + "% 彩色像素", ">10%");
    const snap = cv => cv.getContext("2d").getImageData(0, 0, cv.width, cv.height).data.join(",");
    const onB = snap(cvB), onU = snap(cvUV);
    cam.demosaic = false; D.forceUpdate();
    ok("去马赛克开关真的改变合成视野", snap(cvB) !== onB, snap(cvB) !== onB ? "变了" : "没变", "变了");
    ok("去马赛克开关真的改变紫外面板", snap(cvUV) !== onU, snap(cvUV) !== onU ? "变了" : "没变", "变了");
    cam.demosaic = save; D.forceUpdate();
    // 场景不过曝：果蝇眼里不能一片死白（加了 4 盏灯之后真的糊过一次）
    let sat = 0, tot = 0;
    for (const a of rr.color) for (const v of a) { tot++; if (v >= 0.99) sat++; }
    ok("果蝇眼里没过曝", sat / tot < 0.5, (sat / tot * 100).toFixed(1) + "% 饱和", "<50%");

    // ── 游戏本体：神经元、损毁、说话、飞行片段 ──────────────
    const g2 = window.__game;
    ok("真实神经元开关数", g2.NEURONS.length === 10, g2.NEURONS.length, "10");
    // JS 数字精度：FlyWire root ID ≈ 7.2e17 > 2^53。写成数字字面量会**静默掉精度**，
    // 查表全落空 —— 这个坑踩过一次（曾误判水味觉 GRN 不在子回路里）。
    const allIds = g2.NEURONS.flatMap(n => n.ids).concat(g2.WATER_IDS);
    ok("神经元 ID 全是字符串（超 2^53）",
       allIds.every(i => typeof i === "string" && /^\d{18}$/.test(i)),
       allIds.length + " 个", "全字符串 18 位");
    ok("每个开关都能在子回路里定位", g2.NEURONS.every(n => n.idx.length > 0),
       g2.NEURONS.filter(n => n.idx.length).length + "/" + g2.NEURONS.length, "全部");
    // 子回路与全脑的比值必须**各自独立测**，不是互相抄的
    const same = g2.NEURONS.filter(n => Math.abs(n.game - n.full) < 0.005).length;
    ok("子回路比值 ≠ 全脑比值（不是抄的）", same <= 2, same + "/10 完全相同", "≤2");
    ok("水味觉 GRN：18 个里 17 个在子回路（§19 实测）",
       g2.WATER_IDS.length === 18 && g2.waterIdx.length === 17,
       `${g2.WATER_IDS.length} → ${g2.waterIdx.length}`, "18 → 17");
    // 损毁必须**真的**把突触清零，不是只改个标志位
    const nnz = () => { let c = 0; const w = g2.brain.w; for (let i = 0; i < w.length; i++) if (w[i] !== 0) c++; return c; };
    const base = nnz();
    g2.setNeuronLesion("Roundup", true); const cut = nnz(); g2.setNeuronLesion("Roundup", false);
    ok("神经元损毁真的切断突触", cut < base, `${base} → ${cut}`, "变少");
    ok("取消损毁后突触复原", nnz() === base, nnz() === base ? "复原" : "没复原", "复原");
    g2.setLesion("LC4", true); const cutL = nnz(); g2.setLesion("LC4", false);
    ok("输入组损毁（LC4）真的切断突触", cutL < base, `${base} → ${cutL}`, "变少");
    // 输入组必须来自子回路元数据，不是硬编码 LC4/LPLC2（v1 的 bug：新输入静默失效）
    const ins = Object.keys((g2.SUB.meta && g2.SUB.meta.inputs) || {});
    const needIn = ["LC4", "LPLC2", "LC16", "SUGAR", "BITTER", "JO"];
    ok("输入组都在子回路元数据里（不是硬编码）",
       needIn.every(k => ins.includes(k)), ins.join("/") || "无", needIn.join("/"));
    // 说话：静止时本来就该没话说，所以给一个真实刺激再看句子
    const say0 = g2.speech();
    ok("说话接口带真实发放率", say0 && say0.hz && typeof say0.hz.mn9 === "number",
       say0 && say0.hz ? "mn9=" + say0.hz.mn9 + "Hz" : "无", "有 hz");
    const gustSave = g2.gust;
    g2.gust = { sugar: 100, bitter: 0, water: 0 };
    const say1 = g2.speech();
    g2.gust = gustSave;
    ok("给糖它会说「甜」", say1.words.includes("甜") && say1.sentence.indexOf("甜") >= 0,
       JSON.stringify(say1.sentence), "含「甜」");
    const clips = g2.clips || [];
    ok("飞行片段已装载（真实物理轨迹）",
       clips.length >= 2 && clips.every(c => c.n > 10 && c.pos.length === c.n * 3),
       clips.length + " 段 / " + clips.map(c => c.n).join(",") + " 帧", "≥2 段，每段 >10 帧");

    // ── 复眼异步读回（PBO）──────────────────────────────────────
    // 这条优化省掉的是一次固定的 GPU 往返同步（~4–5 ms）。它静默退化的方式有两种：
    // (a) 退回同步读回 —— 速率掉回 3 fps；(b) 取到的是**上一帧或空**的像素 —— 画面看着正常，
    // 内容却是错的。两种都只能靠量。
    const cam2 = D.instance();
    ok("复眼走 WebGL2 异步读回", !!cam2._pbo(), cam2._pbo() ? "是" : "退回同步", "是");
    if (cam2._pbo()) {
      // 页面自己的循环每帧也在 collect，会把 fence 先消费掉 —— 测之前先停掉它，
      // 否则这里永远等不到自己的那一笔（第一版就是这样，tries 跑满 60）。
      const savedTick = window.__eyeTick; window.__eyeTick = null;
      await new Promise(r => requestAnimationFrame(r));
      cam2._pbo().sync = null; cam2._pendQ = null;        // 丢掉页面留下的半笔
      cam2._renderCube(D.head());
      cam2._submitAsync();
      let tries = 0;
      while (!cam2._tryCollect() && tries < 60) { await new Promise(r => requestAnimationFrame(r)); tries++; }
      const asyncPx = Uint8Array.from(cam2.px);
      cam2._readSync();                                    // 同一张贴图，改用同步读
      let nd = 0, md = 0;
      for (let i = 0; i < asyncPx.length; i++) {
        const d = Math.abs(asyncPx[i] - cam2.px[i]); if (d) { nd++; if (d > md) md = d; }
      }
      ok("异步读回与同步逐字节相同", nd === 0,
         nd === 0 ? asyncPx.length.toLocaleString() + " 字节全等" : nd + " 字节不同(max " + md + ")", "0 字节不同");
      ok("异步读回等待帧数", tries <= 3, tries + " 帧", "≤3");
      window.__eyeTick = savedTick;
    }
    // 实际成像速率（页面自己的循环）
    {
      let n = 0; const orig = cam2._resample.bind(cam2);
      cam2._resample = c => { n++; return orig(c); };
      const t0 = performance.now();
      await new Promise(r => setTimeout(r, 1500));
      const fps = n / ((performance.now() - t0) / 1000);
      cam2._resample = orig;
      // CI 的机器没有 GPU（SwiftShader 软件渲染），实测只有约 2 fps——那量的是硬件，不是代码。
      // 这一项防的回归是「异步读回退化成同步读回」，上面的逐字节比对与 fence 检查在 CI 里照样在查；帧率门槛只在有 GPU 的本机上判。
      if (IN_CI) out.push({ name: "复眼视窗成像速率（CI 无 GPU，只报告不判；本机门槛 ≥10）", pass: true, got: fps.toFixed(1) + " fps", want: "—" });
      else ok("复眼视窗成像速率", fps >= 10, fps.toFixed(1) + " fps", "≥10（原同步版 3）");
    }

    // ── 视蛋白光谱（R1–6 / R7 / R8）────────────────────────────
    const W = cam2.W;
    ok("加载了视蛋白光谱表", !!W && !!W.Rh1, W ? Object.keys(W).join("/") : "无", "Rh1/Rh3/Rh4/Rh5/Rh6");
    if (W) {
      // 归一化：理想白面（三通道都是 1）每一类响应都应该正好是 1
      let worstSum = 0, worstName = "";
      for (const [k, v] of Object.entries(W)) {
        const d = Math.abs(v.U + v.B + v.G - 1);
        if (d > worstSum) { worstSum = d; worstName = k; }
      }
      ok("每类权重归一化（白面响应=1）", worstSum < 1e-9,
         worstName + " 偏差 " + worstSum.toExponential(1), "<1e-9");
      // 光谱顺序：紫外型必须以紫外为主，绿型的绿权重必须最大
      ok("Rh3(345nm) 以紫外为主", W.Rh3.U > 0.95, W.Rh3.U.toFixed(3), ">0.95");
      ok("Rh4(375nm) 以紫外为主", W.Rh4.U > 0.80, W.Rh4.U.toFixed(3), ">0.80");
      ok("Rh5(437nm) 蓝权重最大", W.Rh5.B > W.Rh5.U && W.Rh5.B > W.Rh5.G,
         `U${W.Rh5.U.toFixed(2)}/B${W.Rh5.B.toFixed(2)}/G${W.Rh5.G.toFixed(2)}`, "B 最大");
      ok("Rh6(508nm) 绿权重全场最大", Object.values(W).every(v => v.G <= W.Rh6.G + 1e-12),
         W.Rh6.G.toFixed(3), "所有类里最大");
      // λmax 越长，绿权重越高（单调性）——光谱表算错了这条最先塌
      const order = ["Rh3", "Rh4", "Rh5", "Rh1", "Rh6"];        // λmax 345/375/437/478/508
      let mono = true;
      for (let i = 1; i < order.length; i++) if (W[order[i]].G < W[order[i - 1]].G) mono = false;
      ok("λmax 越长绿权重越高", mono, order.map(k => W[k].G.toFixed(2)).join("<"), "单调递增");
    }
    // R1–R6：八个感光细胞里的六个，以前完全没建模
    ok("有 R1–R6（Rh1）输出", !!rr.r16 && rr.r16[0].length === rr.color[0].length,
       rr.r16 ? rr.r16[0].length : "无", rr.color[0].length);
    if (rr.r16) {
      let dc = 0, du2 = 0;
      for (let i = 0; i < rr.r16[0].length; i++) {
        dc += Math.abs(rr.r16[0][i] - rr.color[0][i]);
        du2 += Math.abs(rr.r16[0][i] - rr.uv[0][i]);
      }
      const n0 = rr.r16[0].length;
      ok("R1–6 与 R8 不同（不是复制）", dc / n0 > 0.01, (dc / n0).toFixed(4), ">0.01");
      ok("R1–6 与 R7 不同（不是复制）", du2 / n0 > 0.01, (du2 / n0).toFixed(4), ">0.01");
    }
    // pale / yellow 现在在紫外上也不同了（Rh3 vs Rh4）——改光谱之前两者完全一样
    {
      const pal = cam2.pale, uvA = rr.uv[0];
      let sp = 0, np = 0, sy = 0, ny = 0;
      for (let i = 0; i < uvA.length; i++) { if (pal[i]) { sp += uvA[i]; np++; } else { sy += uvA[i]; ny++; } }
      const dp = Math.abs(sp / np - sy / ny);
      ok("pale/yellow 的紫外响应不同(Rh3≠Rh4)", dp > 1e-4,
         dp.toFixed(5), ">1e-4（改光谱前恒为 0）");
    }

    // ── 仓库入口 ────────────────────────────────────────────
    {
      const REPO = "https://github.com/suifei/flywire-fly-lab";
      const links = Array.from(document.querySelectorAll(".repo-btn"));
      ok("仓库入口按钮数", links.length === 2, links.length, "2（源码 + Star）");
      ok("都指向本仓库", links.length > 0 && links.every(a => a.href.indexOf(REPO) === 0),
         links.map(a => a.getAttribute("href")).join(" | ").slice(0, 46), REPO);
      ok("外链带 rel=noopener", links.every(a => (a.rel || "").indexOf("noopener") >= 0),
         links.map(a => a.rel || "无").join("/"), "都带");
      ok("每个按钮都有图标", links.every(a => a.querySelector("svg path")),
         links.filter(a => a.querySelector("svg path")).length + "/" + links.length, "全部");
      // star 数取不到时必须保持隐藏 —— 页面不能因为一个外部请求失败而出现空壳
      const sn = document.getElementById("starN");
      ok("star 数缺省时隐藏", !!sn && (sn.hidden || (sn.textContent || "").trim().length > 0),
         sn ? (sn.hidden ? "隐藏" : JSON.stringify(sn.textContent)) : "无此元素", "隐藏或有内容");
      // 可聚焦（键盘可达）
      ok("按钮可键盘聚焦", links.every(a => a.tabIndex >= 0),
         links.map(a => a.tabIndex).join("/"), "≥0");
    }

    // ── 论文式扰动（表 1D / 11B–F）──────────────────────────
    // 这些开关最容易"看着生效实际没生效"：设了标志位但权重没动、或打乱了 post
    // 却没被 run() 用上（run 原来解构的是 this.post，不是 postArr）。所以逐条查实际数组。
    {
      const b = g2.brain;
      const w0 = Float32Array.from(b.w);
      const sumAbs = a => { let s2 = 0; for (let i = 0; i < a.length; i++) s2 += Math.abs(a[i]); return s2; };
      const neg = a => { let s2 = 0; for (let i = 0; i < a.length; i++) if (a[i] < 0) s2 += a[i]; return s2; };
      const pos = a => { let s2 = 0; for (let i = 0; i < a.length; i++) if (a[i] > 0) s2 += a[i]; return s2; };
      const b0 = { abs: sumAbs(w0), neg: neg(w0), pos: pos(w0) };

      g2.setPerturb("weightScale", 0.5);
      ok("权重滑块真的缩放了权重", Math.abs(sumAbs(b.w) / b0.abs - 0.5) < 1e-3,
         (sumAbs(b.w) / b0.abs).toFixed(4), "0.5");
      g2.setPerturb("weightScale", 1);

      g2.setPerturb("inhibScale", 0.5);
      ok("抑制滑块只动负权重", Math.abs(neg(b.w) / b0.neg - 0.5) < 1e-3 && Math.abs(pos(b.w) / b0.pos - 1) < 1e-3,
         `负 ${(neg(b.w) / b0.neg).toFixed(3)} / 正 ${(pos(b.w) / b0.pos).toFixed(3)}`, "负 0.5 / 正 1.0");
      g2.setPerturb("inhibScale", 1);

      // 谷氨酸改兴奋性：这些神经元的传出突触应当全部变成非负，且负权总量下降
      const nt = b.nt;
      ok("加载了递质标签", !!nt && nt.length === b.n, nt ? nt.length : "无", b.n);
      if (nt) {
        const nGlut = nt.filter(x => x === 1).length;
        g2.setPerturb("glutExc", true);
        let bad = 0;
        for (let i = 0; i < b.n; i++) if (nt[i] === 1)
          for (let k = b.indptr[i]; k < b.indptr[i + 1]; k++) if (b.w[k] < 0) bad++;
        ok("谷氨酸改兴奋性后无负权", bad === 0, bad + " 条仍为负", "0");
        ok("负权总量确实下降", neg(b.w) > b0.neg, `${neg(b.w).toFixed(1)} vs 原 ${b0.neg.toFixed(1)}`, "变小（绝对值）");
        ok("子回路里的谷氨酸能神经元数", nGlut > 0, nGlut, ">0");
        g2.setPerturb("glutExc", false);
      }

      // 打乱接线：postArr 必须真的变，而且 run() 用的就是它
      const p0 = Array.from(b.postArr);
      g2.setPerturb("shuffle", true);
      const p1 = Array.from(b.postArr);
      let diff = 0;
      for (let i = 0; i < p0.length; i++) if (p0[i] !== p1[i]) diff++;
      ok("打乱接线真的改了靶点", diff > p0.length * 0.5,
         `${diff}/${p0.length} 条变了`, ">50%");
      const same = p0.slice().sort((a, c) => a - c).join(",") === p1.slice().sort((a, c) => a - c).join(",");
      ok("打乱保持靶点多重集不变", same, same ? "一致" : "不一致", "一致（只重排，不增删）");
      g2.setPerturb("shuffle", false);
      ok("取消打乱后复原", Array.from(b.postArr).join(",") === p0.join(","), "复原", "复原");

      g2.resetPerturb();
      ok("复原按钮把权重还原", Math.abs(sumAbs(b.w) - b0.abs) < 1e-2,
         sumAbs(b.w).toFixed(1), b0.abs.toFixed(1));
      // 页面表格真的渲染了
      const rs = document.querySelectorAll("#tShuf tr").length, rp = document.querySelectorAll("#tPert tr").length;
      ok("打乱接线表格已渲染", rs >= 4, rs + " 行", "≥4（表头+3 通路）");
      ok("扰动稳健性表格已渲染", rp >= 6, rp + " 行", "≥6（表头+5 种扰动）");
    }

    return out;
  }, !!process.env.CI);

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
