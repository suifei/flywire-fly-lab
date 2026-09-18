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
