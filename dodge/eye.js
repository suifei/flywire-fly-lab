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
  const STEPS = 96, DT = 1 / 100, AMP = 22;  // 扫视步数 / 积分步长 / 大扫视幅度（像素）
  let SPACING = 16.4;                        // 相邻小眼间距，由 retina.json 覆盖

  // 扫视轨迹：大扫视 + 细漂移。
  // 大扫视让 T4/T5 工作（它们是运动检测器，盯着不动几乎不响应）；
  // 细漂移是**分辨率的关键**：相邻小眼间距 16.4 像素，如果每次都落在同一个
  // 相位上，采到的永远是同一批点，结果就是 721 块马赛克。漂移用两个非公度
  // 频率，让落点铺满一个小眼的内部，多帧合起来才能超过静态采样极限。
  // （真果蝇也这么干——微扫视超敏锐度，见 report.md §28.6。轨迹本身是手写的。）
  const KEYS = [[0,0,0],[.18,1,.45],[.30,1,.45],[.52,-1,-.5],[.64,-1,-.5],[.86,.9,-.55],[1,.9,-.55]];
  function gaze(k) {
    const t = k / (STEPS - 1);
    let bx = KEYS[KEYS.length - 1][1], by = KEYS[KEYS.length - 1][2];
    for (let i = 1; i < KEYS.length; i++) {
      if (t <= KEYS[i][0]) {
        const [t0, x0, y0] = KEYS[i - 1], [t1, x1, y1] = KEYS[i];
        const f = (t - t0) / Math.max(t1 - t0, 1e-9);
        bx = x0 + (x1 - x0) * f; by = y0 + (y1 - y0) * f;
        break;
      }
    }
    // 细漂移：幅度约一个小眼间距，频率不成简单比例 → 相位不重复
    const d = SPACING * 0.62;
    return [bx * AMP + d * Math.sin(k * 0.9137), by * AMP + d * Math.cos(k * 0.5413)];
  }

  // ── 超分辨累积 ─────────────────────────────────────────────
  // 每个小眼在相机里有固定的中心；果蝇一动，同一个小眼就落到世界的不同位置。
  // 把每步的采样值按"它当时看的是世界哪一点"投回一张高分辨率画布，
  // 多帧合起来的信息量**真的**高于任何单帧 —— 这不是补细节，是真的多采了。
  //
  // 上限不是采样点数，而是小眼的**接受角**（每个小眼本身就是个模糊的探头）。
  // 所以累积能去掉马赛克、逼近真实轮廓，但不会变成一张照片。
  class Accum {
    constructor(cx, cy, spacing, w, h) {
      this.cx = cx; this.cy = cy; this.w = w; this.h = h;
      this.sig = spacing * 0.5;                 // 落点核 ≈ 接受角
      this.rad = Math.ceil(this.sig * 2.2);
      this.num = new Float64Array(w * h);
      this.den = new Float64Array(w * h);
      const R = this.rad, K = new Float64Array((2 * R + 1) * (2 * R + 1));
      for (let dy = -R; dy <= R; dy++) for (let dx = -R; dx <= R; dx++)
        K[(dy + R) * (2 * R + 1) + (dx + R)] = Math.exp(-(dx * dx + dy * dy) / (2 * this.sig * this.sig));
      this.K = K;
      this.samples = [];        // 反投影迭代要用原始测量值 + 落点
    }
    clear() { this.num.fill(0); this.den.fill(0); this.samples = []; }
    /** vals 按 flyvis 柱序；perm 把它换回 flygym 序好对上中心坐标 */
    add(vals, perm, ox, oy) {
      const { cx, cy, w, h, rad: R, K, num, den } = this;
      const S = 2 * R + 1;
      const sx = new Float32Array(vals.length), sy = new Float32Array(vals.length);
      const sv = Float64Array.from(vals);
      for (let j = 0; j < vals.length; j++) {
        const v = vals[j], g = perm[j];
        const px = cx[g] + ox, py = cy[g] + oy;
        sx[j] = px; sy[j] = py;
        const ix = Math.round(px), iy = Math.round(py);
        for (let dy = -R; dy <= R; dy++) {
          const y = iy + dy; if (y < 0 || y >= h) continue;
          for (let dx = -R; dx <= R; dx++) {
            const x = ix + dx; if (x < 0 || x >= w) continue;
            const kk = K[(dy + R) * S + (dx + R)];
            num[y * w + x] += kk * v; den[y * w + x] += kk;
          }
        }
      }
      this.samples.push({ x: sx, y: sy, v: sv });
    }

    /**
     * 反投影迭代（Landweber）：真正的超分辨。
     *
     * 简单平均**不会**提高分辨率 —— 每次测量本来就是小眼 footprint 的平均，
     * 再用一个宽核摊开、多帧叠加，只是把更多张模糊图平均起来（实测提升 -0.2%）。
     * 要提分辨率必须解反问题：找一张高分辨图 X，使得"用小眼去测 X"能复现全部测量值。
     *
     *   预测 = footprint 平均(X)   →   残差 = 实测 − 预测   →   把残差投回去
     *
     * 用的全是实测值和已知几何，不引入训练数据的统计 —— 和解码器不同，
     * 这里不会"补"出没测到的东西，只会把已经测到的信息解开。
     */
    refineInit() {
      const { w, h, num, den } = this;
      const X = new Float64Array(w * h);
      for (let i = 0; i < X.length; i++) X[i] = den[i] > 1e-6 ? num[i] / den[i] : 0;
      this.refined = X;
      return this;
    }
    refine(iters = 8, lam = 0.8) {
      if (!this.refined) this.refineInit();
      const { w, h } = this;
      const X = this.refined;
      // 精修用较窄的核，跑得动；太宽会把残差又抹开
      const sig = this.sig * 0.75, R = Math.ceil(sig * 2.0), S = 2 * R + 1;
      const K = new Float64Array(S * S);
      let ksum = 0;
      for (let dy = -R; dy <= R; dy++) for (let dx = -R; dx <= R; dx++) {
        const v = Math.exp(-(dx * dx + dy * dy) / (2 * sig * sig));
        K[(dy + R) * S + (dx + R)] = v; ksum += v;
      }
      const gn = new Float64Array(w * h), gd = new Float64Array(w * h);
      for (let it = 0; it < iters; it++) {
        gn.fill(0); gd.fill(0);
        for (const s of this.samples) {
          for (let j = 0; j < s.v.length; j++) {
            const ix = Math.round(s.x[j]), iy = Math.round(s.y[j]);
            let pred = 0, wsum = 0;
            for (let dy = -R; dy <= R; dy++) {
              const y = iy + dy; if (y < 0 || y >= h) continue;
              const row = (dy + R) * S;
              for (let dx = -R; dx <= R; dx++) {
                const x = ix + dx; if (x < 0 || x >= w) continue;
                const kk = K[row + dx + R];
                pred += kk * X[y * w + x]; wsum += kk;
              }
            }
            if (wsum < 1e-9) continue;
            const res = s.v[j] - pred / wsum;
            for (let dy = -R; dy <= R; dy++) {
              const y = iy + dy; if (y < 0 || y >= h) continue;
              const row = (dy + R) * S;
              for (let dx = -R; dx <= R; dx++) {
                const x = ix + dx; if (x < 0 || x >= w) continue;
                const kk = K[row + dx + R];
                gn[y * w + x] += kk * res; gd[y * w + x] += kk;
              }
            }
          }
        }
        for (let i = 0; i < X.length; i++) if (gd[i] > 1e-9) X[i] += lam * gn[i] / gd[i];
      }
      return X;
    }
    toCanvas(cv, useRefined) {
      const { num, den, w, h } = this;
      const Xr = useRefined ? this.refined : null;
      const g = cv.getContext("2d");
      const im = g.createImageData(w, h);
      const val = i => (Xr ? Xr[i] : num[i] / den[i]);
      let lo = Infinity, hi = -Infinity;
      for (let i = 0; i < num.length; i++) if (den[i] > 1e-6) {
        const v = val(i); if (v < lo) lo = v; if (v > hi) hi = v;
      }
      const rng = hi - lo || 1;
      for (let i = 0; i < num.length; i++) {
        const has = den[i] > 1e-6;
        const t = has ? (val(i) - lo) / rng : 0;
        const c = (t * 255) | 0;
        im.data[i * 4] = c; im.data[i * 4 + 1] = c; im.data[i * 4 + 2] = c;
        im.data[i * 4 + 3] = has ? 255 : 255;     // 没采到的地方留黑，不是留空
      }
      const tmp = document.createElement("canvas");
      tmp.width = w; tmp.height = h;
      tmp.getContext("2d").putImageData(im, 0, 0);
      g.clearRect(0, 0, cv.width, cv.height);
      g.imageSmoothingEnabled = true;
      const sc = Math.min(cv.width / w, cv.height / h);
      g.drawImage(tmp, (cv.width - w * sc) / 2, (cv.height - h * sc) / 2, w * sc, h * sc);
    }
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
  function drawHex(cv, vals, geom, mode, pale) {
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
      if (mode === "mosaic") {
        // 彩色马赛克：pale 小眼（读蓝通道）画蓝，yellow（读绿）画绿。
        // 这是 FlyGym 真实的 pale/yellow 分型，比例 30/70，和真果蝇一致。
        const t2 = (vals[i] - lo) / rng;
        g.fillStyle = pale && pale[i]
          ? `rgb(${(t2 * 90) | 0},${(t2 * 150) | 0},${(t2 * 255) | 0})`
          : `rgb(${(t2 * 110) | 0},${(t2 * 255) | 0},${(t2 * 120) | 0})`;
      } else
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
    // 保留绿/蓝两路：pale 小眼读蓝、yellow 读绿（FlyGym 原样）。
    // 先转灰度会把 pale/yellow 的区别丢掉 —— 那是之前的实现缺陷。
    const G = new Float32Array(cw * ch), B = new Float32Array(cw * ch);
    for (let i = 0; i < G.length; i++) { G[i] = d[i * 4 + 1] / 255; B[i] = d[i * 4 + 2] / 255; }
    return { G, B, cw, ch };
  }
  function cropAt(src, dx, dy) {
    const { G, B, cw, ch } = src;
    const x0 = Math.max(0, Math.min(cw - W, Math.round((cw - W) / 2 + dx)));
    const y0 = Math.max(0, Math.min(ch - H, Math.round((ch - H) / 2 + dy)));
    const outG = new Float32Array(W * H), outB = new Float32Array(W * H);
    for (let y = 0; y < H; y++) {
      const a = (y0 + y) * cw + x0;
      outG.set(G.subarray(a, a + W), y * W);
      outB.set(B.subarray(a, a + W), y * W);
    }
    const out = outG;
    // ox,oy = 这一帧相机画面在"世界"里的原点。累积时把小眼中心加上它，
    // 才知道这个小眼当时看的是世界哪一点。
    return { frame: out, G: outG, B: outB, ox: x0, oy: y0 };
  }
  const crop = (src, dx, dy) => cropAt(src, dx, dy).frame;

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
    } else if (kind === "color") {                      // 色块：演示果蝇的光谱
      const cols = [["#ff2020", "红"], ["#20ff40", "绿"], ["#2050ff", "蓝"], ["#ffffff", "白"]];
      g.font = `bold ${26 * s}px system-ui,sans-serif`;
      g.textAlign = "center"; g.textBaseline = "middle";
      for (let i = 0; i < 4; i++) {
        const x = 30 + (i % 2) * 190, y = 30 + ((i / 2) | 0) * 190;
        g.fillStyle = cols[i][0];
        g.fillRect(x * s, y * s, 170 * s, 170 * s);
        g.fillStyle = "#000";
        g.fillText(cols[i][1], (x + 85) * s, (y + 85) * s);
      }
    } else {                                            // 文字：考验分辨率
      g.fillStyle = "#fff"; g.textAlign = "center"; g.textBaseline = "middle";
      g.font = `bold ${150 * s}px system-ui,sans-serif`;
      g.fillText("果蝇", size / 2, size / 2);
    }
    return c;
  }

  return { S, W, H, STEPS, DT, gaze, hexGeom, drawHex, frameFor, crop, cropAt, preset, Accum,
           setSpacing: v => { SPACING = v; }, spacing: () => SPACING };
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
    src: $("eSrc"), omm: $("eOmm"), acc: $("eAcc"), act: $("eAct"),
    retina: $("eRetina"), lamina: $("eLamina"), medulla: $("eMedulla"), motion: $("eMotion"),
  };
  const geom = E.hexGeom(S.lat, cvs.omm.width, cvs.omm.height);
  const meta = S.retina.meta;
  E.setSpacing(meta.spacing_px || 16.4);
  const CX = Float64Array.from(meta.centers_x), CY = Float64Array.from(meta.centers_y);
  const perm = S.retina.perm;
  const PALE = S.retina.paleByColumn();     // 每柱是不是 pale 型（读蓝通道）
  const ACC = {};                       // 超分辨累积：小眼原始 + 四个解码层
  for (const k of ["acc", "retina", "lamina", "medulla", "motion"])
    ACC[k] = new E.Accum(CX, CY, 16.4, E.W, E.H);   // 选图时按实际尺寸重建
  // 画布用**大图**尺寸：投点坐标是 ox+cx，会超出相机画面范围。
  // 按相机尺寸开会把越界的点全丢掉（这个 bug 让相关从 0.85 掉到 0.40）。
  let ACCW = E.W, ACCH = E.H;
  let src = null, img = null;

  function showSource(canvasOrImg) {
    img = canvasOrImg;
    const g = cvs.src.getContext("2d");
    g.fillStyle = "#0d1117"; g.fillRect(0, 0, cvs.src.width, cvs.src.height);
    const sc = Math.min(cvs.src.width / img.width, cvs.src.height / img.height);
    const w = img.width * sc, h = img.height * sc;
    g.drawImage(img, (cvs.src.width - w) / 2, (cvs.src.height - h) / 2, w, h);
    src = E.frameFor(img);
    if (src.cw !== ACCW || src.ch !== ACCH) {
      ACCW = src.cw; ACCH = src.ch;
      for (const k of ["acc", "retina", "lamina", "medulla", "motion"])
        ACC[k] = new E.Accum(CX, CY, E.spacing(), ACCW, ACCH);
    }
    $("eStatus").textContent = "按「让果蝇看」开始";
  }

  function run() {
    if (!src || S.running) return;
    S.running = true;
    S.net.reset();
    const actType = $("eType").value;
    for (const a of Object.values(ACC)) a.clear();
    let k = 0;
    const tick = () => {
      if (!S.running) return;
      const [dx, dy] = E.gaze(k);
      // 累积要用**同一个**裁切原点，否则投回世界坐标会错位
      const { ox, oy, G, B } = E.cropAt(src, dx, dy);
      const hex = S.retina.sampleGB(G, B);
      S.net.step(hex, E.DT);
      E.drawHex(cvs.omm, hex, geom, "mosaic", PALE);
      E.drawHex(cvs.act, S.net.get(actType), geom, "signed");
      ACC.acc.add(hex, perm, ox, oy);
      for (const key of ["retina", "lamina", "medulla", "motion"])
        ACC[key].add(S.dec[key].decode(t => S.net.get(t)), perm, ox, oy);
      // 高分辨画布重绘较贵，隔几步画一次；最后一步一定画
      if (k % 8 === 7 || k === E.STEPS - 1)
        for (const key of ["acc", "retina", "lamina", "medulla", "motion"]) ACC[key].toCanvas(cvs[key]);
      $("eStatus").textContent = `扫视中 ${k + 1}/${E.STEPS} 步（${((k + 1) * E.DT * 1000).toFixed(0)} ms 脑内时间）`;
      if (++k < E.STEPS) { S.raf = requestAnimationFrame(tick); }
      else {
        // 扫完再精修：朴素平均**不提分辨率**（实测 -0.2%），
        // 靠反投影解反问题才行（0.851 → 0.920，超过单次接受角天花板 0.883）
        const keys = ["acc", "retina", "lamina", "medulla", "motion"];
        for (const key of keys) ACC[key].refineInit();
        let it = 0;
        const ITERS = 8;
        const step = () => {
          if (!S.running) return;
          for (const key of keys) { ACC[key].refine(1); ACC[key].toCanvas(cvs[key], true); }
          $("eStatus").textContent = `反投影精修 ${++it}/${ITERS} 轮`;
          if (it < ITERS) S.raf = requestAnimationFrame(step);
          else { S.running = false; $("eStatus").textContent =
            `完成：${E.STEPS} 步扫视（${(E.STEPS * E.DT * 1000).toFixed(0)} ms 脑内时间）· ${E.STEPS * 721} 次小眼采样 · 精修 ${ITERS} 轮`; }
        };
        S.raf = requestAnimationFrame(step);
      }
    };
    tick();
  }

  $("eFile").addEventListener("change", ev => {
    const f = ev.target.files[0]; if (!f) return;
    const im = new Image();
    im.onload = () => showSource(im);
    im.src = URL.createObjectURL(f);
  });
  for (const k of ["shapes", "face", "text", "color"])
    $("ePre_" + k).addEventListener("click", () => showSource(E.preset(k)));
  $("eRun").addEventListener("click", run);
  $("eType").addEventListener("change", () => {
    if (!S.running && S.net) E.drawHex(cvs.act, S.net.get($("eType").value), geom, "signed");
  });

  // ── 舞台右上角的第一人称复眼视窗 ────────────────────────
  // 和上面那块用同一套采样表、同一套 pale/yellow 分型，
  // 但为了实时**跳过 flyvis 和解码器**，只到"视网膜接收到什么"为止。
  (() => {
    const fs = window.__flyScene;
    const box = $("eyecam");
    if (!fs || !box || typeof FlyEyeCam === "undefined") { if (box) box.hidden = true; return; }
    const cvL = $("ecL"), cvR = $("ecR");
    let cam;
    try {
      const sky = getComputedStyle(document.documentElement)
        .getPropertyValue("--stage-top").trim() || "#9fb4c8";
      cam = new FlyEyeCam.Cam(fs.THREE, fs.renderer, fs.scene, S.retina, S.lat,
                              { hexGeom: E.hexGeom, drawHex: E.drawHex },
                              { sky, selfMeshes: fs.selfMeshes });
    } catch (err) { box.hidden = true; return; }
    const note = $("ecNote");
    window.__eyeTick = (x, y, z, h) => {
      if (!cam.shouldUpdate(performance.now(), 3)) return;
      try { cam.update(x, y, z, h, [cvL, cvR]); }
      catch (err) { window.__eyeTick = null; box.hidden = true; }
    };
    if (note) note.textContent = "果蝇视角 · 721 小眼/眼 · 3 fps";
  })();

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
