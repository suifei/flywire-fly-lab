/**
 * 「果蝇画你的图」—— 上传一张图，让果蝇用它真实的视觉系统看，再画出来。
 *
 * 链路（每一步都是真的，没有示意图）：
 *   你的图 → 450×512 相机画面
 *          → FlyGym 真实复眼采样表（ommatidia_id_map，含鱼眼畸变）→ 721 个小眼
 *          → flyvis 预训练连接组视觉网络（65 类 × 721 柱，2355 个卷积抽头）
 *          → 六边形卷积解码器 → 重建
 *
 * 为什么要让果蝇「扫视」：T4/T5 是运动检测器，**盯着不动的图几乎不响应**。
 * 真果蝇也靠扫视和飞行中的视网膜滑动来看世界。所以动起来不是为了好看，
 * 是让视觉系统真正工作起来的必要条件。
 *
 * 界面同时给出两种画法，这是有意的：
 *   · 神经活动直显 —— 神经元里确实有的东西
 *   · 解码重建     —— 好看得多，但解码器会补出活动里没有的细节
 * 差距本身就是要展示的内容（见 report.md §15 解码器压力测试）。
 */
const FlyEye = (() => {
  const S = { net: null, retina: null, dec: null, lat: null, running: false, raf: 0 };
  const W = 450, H = 512;                    // FlyGym 相机画面尺寸
  const STEPS = 72, DT = 1 / 100, AMP = 16;  // 扫视步数 / 积分步长 / 幅度（像素）

  // 扫视轨迹：快转 + 停顿，不是匀速平移。停顿时 T4/T5 会衰减，这是真的。
  const KEYS = [[0,0,0],[.18,1,.45],[.30,1,.45],[.52,-1,-.5],[.64,-1,-.5],[.86,.9,-.55],[1,.9,-.55]];
  function gaze(k) {
    const t = k / (STEPS - 1);
    for (let i = 1; i < KEYS.length; i++) {
      if (t <= KEYS[i][0]) {
        const [t0, x0, y0] = KEYS[i - 1], [t1, x1, y1] = KEYS[i];
        const f = (t - t0) / Math.max(t1 - t0, 1e-9);
        return [(x0 + (x1 - x0) * f) * AMP, (y0 + (y1 - y0) * f) * AMP];
      }
    }
    return [KEYS[KEYS.length - 1][1] * AMP, KEYS[KEYS.length - 1][2] * AMP];
  }

  // ── 六边形绘制 ─────────────────────────────────────────────
  // 朝向：实测 相机x ↔ 六边形y、相机y ↔ 六边形x（相关 1.000，精确转置）。
  // 所以画的时候要交换两轴，否则用户会看到自己的图被转了 90°。
  function hexGeom(lat, w, h) {
    const P = lat.map(([u, v]) => [v * Math.sqrt(3) / 2, u + v / 2]);   // 交换后的 (x,y)
    const xs = P.map(p => p[0]), ys = P.map(p => p[1]);
    const x0 = Math.min(...xs), x1 = Math.max(...xs);
    const y0 = Math.min(...ys), y1 = Math.max(...ys);
    const s = Math.min(w / (x1 - x0 + 2), h / (y1 - y0 + 2));
    return { P, x0, y0, x1, y1, s, ox: (w - (x1 - x0) * s) / 2, oy: (h - (y1 - y0) * s) / 2 };
  }
  function drawHex(cv, vals, geom, mode) {
    const g = cv.getContext("2d"), { P, x0, y0, s, ox, oy } = geom;
    g.clearRect(0, 0, cv.width, cv.height);
    let lo = Infinity, hi = -Infinity;
    for (const v of vals) { if (v < lo) lo = v; if (v > hi) hi = v; }
    if (mode === "signed") {
      // 神经活动有很大的直流分量（Mi1 之类整片都是正的），直接按 ±max 上色
      // 会糊成一片。扣掉中位数再上色，显示的是"相对静息的偏离"，结构才看得见。
      const srt = Float64Array.from(vals).sort();
      const med = srt[srt.length >> 1];
      let m = 0;
      for (const v of vals) { const d = Math.abs(v - med); if (d > m) m = d; }
      m = m || 1;
      vals = Float64Array.from(vals, v => v - med);
      lo = -m; hi = m;
    }
    const rng = hi - lo || 1, r = s * 0.62;
    for (let i = 0; i < P.length; i++) {
      const t = (vals[i] - lo) / rng;
      g.fillStyle = mode === "signed"
        ? (t > .5 ? `rgb(${200 + 55 * (t - .5) * 2 | 0},${120 - 110 * (t - .5) * 2 | 0},${90 - 80 * (t - .5) * 2 | 0})`
                  : `rgb(${90 - 60 * (.5 - t) * 2 | 0},${130 + 40 * (.5 - t) * 2 | 0},${200 + 55 * (.5 - t) * 2 | 0})`)
        : `rgb(${(t * 255) | 0},${(t * 255) | 0},${(t * 255) | 0})`;
      const cx = ox + (P[i][0] - x0) * s, cy = oy + (P[i][1] - y0) * s;
      g.beginPath();
      for (let k = 0; k < 6; k++) {
        const a = Math.PI / 6 + k * Math.PI / 3;
        const x = cx + r * Math.cos(a), y = cy + r * Math.sin(a);
        k ? g.lineTo(x, y) : g.moveTo(x, y);
      }
      g.closePath(); g.fill();
    }
  }

  // ── 相机画面：把上传的图铺满果蝇视野，留一点扫视余量 ────────
  function frameFor(img) {
    const pad = 1.14, cw = Math.round(W * pad), ch = Math.round(H * pad);
    const c = document.createElement("canvas"); c.width = cw; c.height = ch;
    const g = c.getContext("2d");
    g.fillStyle = "#000"; g.fillRect(0, 0, cw, ch);
    const sc = Math.min(cw / img.width, ch / img.height);      // 整图放进去，不裁切
    const dw = img.width * sc, dh = img.height * sc;
    g.drawImage(img, (cw - dw) / 2, (ch - dh) / 2, dw, dh);
    const d = g.getImageData(0, 0, cw, ch).data;
    const gray = new Float32Array(cw * ch);
    for (let i = 0; i < gray.length; i++)
      gray[i] = (0.299 * d[i * 4] + 0.587 * d[i * 4 + 1] + 0.114 * d[i * 4 + 2]) / 255;
    return { gray, cw, ch };
  }
  function crop(src, dx, dy) {
    const { gray, cw, ch } = src;
    const x0 = Math.max(0, Math.min(cw - W, Math.round((cw - W) / 2 + dx)));
    const y0 = Math.max(0, Math.min(ch - H, Math.round((ch - H) / 2 + dy)));
    const out = new Float32Array(W * H);
    for (let y = 0; y < H; y++) out.set(gray.subarray((y0 + y) * cw + x0, (y0 + y) * cw + x0 + W), y * W);
    return out;
  }

  // ── 预设图：不上传也能玩 ────────────────────────────────
  function preset(kind, size = 420) {
    const c = document.createElement("canvas"); c.width = c.height = size;
    const g = c.getContext("2d");
    g.fillStyle = "#111"; g.fillRect(0, 0, size, size);
    const s = size / 420;
    if (kind === "shapes") {
      g.fillStyle = "#eee"; g.beginPath(); g.arc(120 * s, 120 * s, 70 * s, 0, 7); g.fill();
      g.fillStyle = "#999"; g.fillRect(250 * s, 60 * s, 110 * s, 110 * s);
      g.fillStyle = "#fff";
      for (let i = 0; i < 9; i++) g.fillRect((60 + i * 16) * s, 250 * s, 7 * s, 110 * s);
      g.fillStyle = "#bbb"; g.beginPath();
      g.moveTo(250 * s, 360 * s); g.lineTo(360 * s, 360 * s); g.lineTo(305 * s, 240 * s); g.fill();
    } else if (kind === "face") {
      g.fillStyle = "#ddd"; g.beginPath(); g.ellipse(210 * s, 210 * s, 130 * s, 160 * s, 0, 0, 7); g.fill();
      g.fillStyle = "#222";
      g.beginPath(); g.ellipse(165 * s, 175 * s, 22 * s, 26 * s, 0, 0, 7); g.fill();
      g.beginPath(); g.ellipse(255 * s, 175 * s, 22 * s, 26 * s, 0, 0, 7); g.fill();
      g.strokeStyle = "#222"; g.lineWidth = 10 * s; g.beginPath();
      g.arc(210 * s, 240 * s, 60 * s, 0.35, Math.PI - 0.35); g.stroke();
    } else {                                            // 文字：考验分辨率
      g.fillStyle = "#fff"; g.textAlign = "center"; g.textBaseline = "middle";
      g.font = `bold ${150 * s}px system-ui,sans-serif`;
      g.fillText("果蝇", size / 2, size / 2);
    }
    return c;
  }

  return { S, W, H, STEPS, DT, gaze, hexGeom, drawHex, frameFor, crop, preset };
})();
if (typeof module !== "undefined" && module.exports) module.exports = FlyEye;

/** 界面装配。由页面在资产就绪后调用一次。 */
function initFlyEye(assets) {
  const E = FlyEye, S = E.S;
  S.net = FlyVis.load(assets.net);
  S.lat = assets.net.lattice;
  S.dec = HexDecoder.load(assets.decoders, S.lat);
  S.retina = assets.retina;                    // 已构造好的 Retina 实例
  const $ = id => document.getElementById(id);

  const cvs = {
    src: $("eSrc"), omm: $("eOmm"), act: $("eAct"),
    retina: $("eRetina"), lamina: $("eLamina"), medulla: $("eMedulla"), motion: $("eMotion"),
  };
  const geom = E.hexGeom(S.lat, cvs.omm.width, cvs.omm.height);
  let src = null, img = null;

  function showSource(canvasOrImg) {
    img = canvasOrImg;
    const g = cvs.src.getContext("2d");
    g.fillStyle = "#0d1117"; g.fillRect(0, 0, cvs.src.width, cvs.src.height);
    const sc = Math.min(cvs.src.width / img.width, cvs.src.height / img.height);
    const w = img.width * sc, h = img.height * sc;
    g.drawImage(img, (cvs.src.width - w) / 2, (cvs.src.height - h) / 2, w, h);
    src = E.frameFor(img);
    $("eStatus").textContent = "按「让果蝇看」开始";
  }

  function run() {
    if (!src || S.running) return;
    S.running = true;
    S.net.reset();
    const actType = $("eType").value;
    let k = 0;
    const tick = () => {
      if (!S.running) return;
      const [dx, dy] = E.gaze(k);
      const hex = S.retina.sample(E.crop(src, dx, dy));
      S.net.step(hex, E.DT);
      E.drawHex(cvs.omm, hex, geom, "gray");
      E.drawHex(cvs.act, S.net.get(actType), geom, "signed");
      for (const key of ["retina", "lamina", "medulla", "motion"])
        E.drawHex(cvs[key], S.dec[key].decode(t => S.net.get(t)), geom, "gray");
      $("eStatus").textContent = `扫视中 ${k + 1}/${E.STEPS} 步（${((k + 1) * E.DT * 1000).toFixed(0)} ms 脑内时间）`;
      if (++k < E.STEPS) { S.raf = requestAnimationFrame(tick); }
      else { S.running = false; $("eStatus").textContent = `看完了：${E.STEPS} 步 / ${(E.STEPS * E.DT * 1000).toFixed(0)} ms 脑内时间`; }
    };
    tick();
  }

  $("eFile").addEventListener("change", ev => {
    const f = ev.target.files[0]; if (!f) return;
    const im = new Image();
    im.onload = () => showSource(im);
    im.src = URL.createObjectURL(f);
  });
  for (const k of ["shapes", "face", "text"])
    $("ePre_" + k).addEventListener("click", () => showSource(E.preset(k)));
  $("eRun").addEventListener("click", run);
  $("eType").addEventListener("change", () => {
    if (!S.running && S.net) E.drawHex(cvs.act, S.net.get($("eType").value), geom, "signed");
  });

  showSource(E.preset("shapes"));
  $("eNote").textContent =
    `flyvis ${S.net.types.length} 类细胞 / ${S.net.nTaps} 个卷积抽头 · ` +
    `解码器在 ${S.dec._meta.n_images} 张图上训练、留出整张图测试`;
}

/** 启动：先把视网膜采样表从内联 PNG 解出来，再装配界面。 */
function bootFlyEye(netJson, retinaMeta, retinaPngDataUri, decodersJson) {
  const im = new Image();
  im.onload = () => {
    const c = document.createElement("canvas");
    c.width = im.width; c.height = im.height;
    const g = c.getContext("2d", { willReadFrequently: true });
    g.drawImage(im, 0, 0);
    const data = g.getImageData(0, 0, im.width, im.height).data;
    initFlyEye({
      net: netJson,
      decoders: decodersJson,
      retina: Retina.fromImageData(data, retinaMeta),
    });
  };
  im.onerror = () => { const s = document.getElementById("eStatus"); if (s) s.textContent = "视网膜采样表加载失败"; };
  im.src = retinaPngDataUri;
}
