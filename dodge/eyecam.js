/**
 * 果蝇第一人称复眼视窗：把 3D 世界从果蝇眼睛的位置渲一遍，
 * 走**真实的复眼采样表**成像，画到舞台右上角。
 *
 * 链路：three.js 场景 → 眼位摄像机 → 450×512 离屏渲染 → FlyGym 的
 * ommatidia_id_map 归并到 721 个小眼 → pale 取蓝通道 / yellow 取绿通道
 * → 彩色马赛克。和「让果蝇看你的图」用的是同一套采样表和同一套分型。
 *
 * 为了速度**跳过 flyvis 和解码器**（那两步是给静态图做深度分析的），
 * 这里只到"视网膜接收到什么"为止，所以能实时跑。
 *
 * 诚实标注：
 *   · 小眼排布、采样表、pale/yellow 分型（216:505）—— 真实的，来自 FlyGym
 *   · 视野角度和镜头畸变 —— **近似**。FlyGym 的鱼眼参数没有照搬，
 *     这里用的是宽视角透视投影。真果蝇单眼视野接近 180°，透视投影到不了。
 *   · 紫外缺失 —— 场景是 sRGB 渲的，没有紫外通道（果蝇最重要的通道之一）。
 */
const FlyEyeCam = (() => {
  // 全部照抄 FlyGym 的 config.yaml["vision"]，不是估的：
  const RW = 450, RH = 512;              // raw_img_width_px / raw_img_height_px
  const FOVY = 157;                      // fovy_per_eye（度，竖直方向）
  const ZOOM = 2.72;                     // fisheye_zoom
  const DIST = 3.8;                      // fisheye_distortion_coefficient
  const EYE_AZ = 63.1 * Math.PI / 180;   // 左右眼光轴相对机体前方的方位角
                                         // （在 MuJoCo 里实测 LEye_cam +63.1° / REye_cam −63.1°）

  /**
   * FlyGym 的鱼眼校正（`Retina._correct_fisheye`，源自 iFish, MIT）。
   * MuJoCo 渲的是**直线透视图**，边缘角度被过度拉伸；这一步把它扭成
   * "等角等像素"，**然后才**用 ommatidia_id_map 采样（见 fly.py:1098）。
   * 之前我整个漏了这一步，所以视野边缘是错的。
   *
   * 这里预先算出「校正后像素 → 原始像素」的查找表，跑的时候只剩一次取址。
   * @returns {Int32Array} 长度 RW*RH，值为原始图的像素下标；-1 表示落在画面外
   */
  function buildFisheye() {
    const map = new Int32Array(RW * RH).fill(-1);
    for (let r = 0; r < RH; r++) {
      const rn = ((2 * r - RH) / RH) / ZOOM;
      for (let c = 0; c < RW; c++) {
        const cn = ((2 * c - RW) / RW) / ZOOM;
        const denom = 1 - DIST * (cn * cn + rn * rn) + 1e-6;
        // 奇点：denom 在半径 r > sqrt(1/3.8) = 0.513 处变负，映射翻转到对侧，
        // 取到的是镜像位置的垃圾内容。最外圈小眼正好落在这附近
        // （画面角上 r ≈ 0.52），几何自检里表现为"物体出现在视野最外缘"。
        // 这一圈标为无效，宁可空着也不要假内容。
        if (denom <= 0.05) continue;
        const sr = Math.trunc(((rn / denom) + 1) * RH / 2);
        const sc = Math.trunc(((cn / denom) + 1) * RW / 2);
        if (sr >= 0 && sr < RH && sc >= 0 && sc < RW) map[r * RW + c] = sr * RW + sc;
      }
    }
    return map;
  }

  /**
   * 每个小眼的视线方向（机体坐标系）。
   *
   * 小眼中心坐标是在**校正后**的图像里量的（id_map 作用于 fish_img），
   * 所以要先经鱼眼逆映射回原始像素，再按 fovy=157° 的透视投影算出射线，
   * 最后绕 z 轴转 ±63.1° 到机体坐标系。
   * @returns {{az:Float64Array, el:Float64Array}} 方位角/仰角，弧度
   */
  function eyeDirections(cx, cy, fish, sign) {
    const n = cx.length;
    const az = new Float64Array(n), el = new Float64Array(n);
    const ty = Math.tan(FOVY * Math.PI / 360);      // tan(fovy/2)
    const tx = ty * (RW / RH);                      // 水平半角（同一焦距）
    const yaw = sign * EYE_AZ;
    for (let k = 0; k < n; k++) {
      const dc = Math.round(cx[k]), dr = Math.round(cy[k]);
      const si = (dr >= 0 && dr < RH && dc >= 0 && dc < RW) ? fish[dr * RW + dc] : -1;
      if (si < 0) { az[k] = NaN; el[k] = NaN; continue; }   // 落在鱼眼奇点外，方向无意义
      const sr = (si / RW) | 0, sc = si % RW;
      // 相机看向 -z，x 向右、y 向上（MuJoCo / three.js 一致）
      const x = (2 * sc / RW - 1) * tx, y = (1 - 2 * sr / RH) * ty, z = -1;
      // 相机 -z → 机体 +x（前方）；相机 +x → 机体 -y（右）；相机 +y → 机体 +z（上）
      const fx = -z, fy = -x, fz = y;
      const cxr = Math.cos(yaw), sxr = Math.sin(yaw);
      const bx = fx * cxr - fy * sxr, by = fx * sxr + fy * cxr, bz = fz;
      const len = Math.hypot(bx, by, bz);
      az[k] = Math.atan2(by / len, bx / len);
      el[k] = Math.asin(bz / len);
    }
    return { az, el };
  }

  class Cam {
    /**
     * @param {object} THREE three.js 命名空间
     * @param {object} renderer 复用游戏的 WebGLRenderer
     * @param {object} scene 游戏场景
     * @param {object} retina Retina 实例
     * @param {Array} lattice 721 个柱的 (u,v)
     * @param {object} draw { hexGeom, drawHex } 来自 FlyEye
     */
    constructor(THREE, renderer, scene, retina, lattice, draw, opts = {}) {
      this.THREE = THREE; this.renderer = renderer; this.scene = scene;
      this.retina = retina; this.draw = draw;
      this.eyeYaw = opts.eyeYaw ?? (50 * Math.PI / 180);   // 两眼各偏离前方的角度
      this.eyeUp = opts.eyeUp ?? 1.4;                      // 眼睛离身体原点的高度
      this.eyeFwd = opts.eyeFwd ?? 0.9;                    // 向前偏移
      this.fov = FOVY;                                     // 照抄 FlyGym 的 fovy_per_eye
      this.target = new THREE.WebGLRenderTarget(RW, RH, {
        minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter,
        format: THREE.RGBAFormat, depthBuffer: true,
      });
      this.cams = [0, 1].map(() => {
        const c = new THREE.PerspectiveCamera(this.fov, RW / RH, 0.05, 800);
        c.up.set(0, 0, 1);
        return c;
      });
      this.buf = new Uint8Array(RW * RH * 4);
      this.G = new Float32Array(RW * RH);
      this.B = new Float32Array(RW * RH);
      this.pale = retina.paleByColumn();
      this.fish = buildFisheye();                          // 校正后像素 → 原始像素
      // 每个小眼的视线方向（机体系）。左眼 +63.1°，右眼 −63.1°。
      const m = retina.meta;
      this.dirs = [1, -1].map(sg => eyeDirections(
        Float64Array.from(m.centers_x), Float64Array.from(m.centers_y), this.fish, sg));
      this.permArr = retina.perm;
      this.geom = null; this.lattice = lattice;
      this.lastMs = 0;
      // 游戏的天空是 CSS 渐变，不在 3D 场景里。离屏渲染时那块是透明的，
      // 果蝇会"看到"一片纯黑。用舞台的天空色当清屏色补上。
      this.sky = new THREE.Color(opts.sky || "#9fb4c8");
      this.selfMeshes = opts.selfMeshes || [];
    }

    /** 每秒最多刷几次（默认 3）——读回 GPU 像素会打断流水线，不能每帧做 */
    shouldUpdate(nowMs, fps = 3) {
      if (nowMs - this.lastMs < 1000 / fps) return false;
      this.lastMs = nowMs; return true;
    }

    /**
     * @param {number} x,y,z 果蝇身体位置（世界坐标）
     * @param {number} h 朝向（弧度，和 fly.rotation.z 一致）
     * @param {HTMLCanvasElement[]} canvases [左眼, 右眼]
     */
    /**
     * @param {object} headObj 果蝇头部网格（three.js Object3D）。用它的世界位姿，
     *   这样视线会**同时跟上机体姿态和头部摆动** —— 之前只用偏航角，
     *   起飞时机体大幅上仰、视线却还在平视，看到的东西是错的。
     *   头部网格的本地 +x 就是前方（实测与机体前方夹角 5.1°，不是假设）。
     * @param {HTMLCanvasElement[]} canvases [左眼, 右眼]
     * @returns {Float64Array[]} 两只眼的 721 个小眼读数，供合成视窗用
     */
    update(headObj, canvases) {
      const { THREE, renderer, scene, target, cams, buf, G, B, retina, fish } = this;
      if (!this.geom) this.geom = this.draw.hexGeom(this.lattice, canvases[0].width, canvases[0].height);
      const prevTarget = renderer.getRenderTarget();
      const prevClear = renderer.getClearColor(new THREE.Color());
      const prevAlpha = renderer.getClearAlpha();
      renderer.setClearColor(this.sky, 1);
      // 真果蝇看不到自己的头。FlyGym 渲眼图时也会把头、口器、胸、触角等
      // 14 个部件隐藏（config.yaml 的 hidden_segments）。
      const self = (this.selfMeshes || []).map(m => [m, m.visible]);
      for (const [m] of self) m.visible = false;

      const wp = this._wp || (this._wp = new THREE.Vector3());
      const wq = this._wq || (this._wq = new THREE.Quaternion());
      headObj.getWorldPosition(wp); headObj.getWorldQuaternion(wq);
      // 头部网格的本地坐标轴**实测**是：+x 前方、+y 上方、+z 右方。
      //   本地 +x → [0.964, 0.164, 0.211]  ≈ 前
      //   本地 +y → [-0.241, 0.192, 0.951] ≈ 世界 +z（上）
      //   本地 +z → [0.116, -0.967, 0.225] ≈ 世界 -y（右）
      // 我一开始验证了前方轴，却想当然地把 +z 当成上，绕"右方"轴转 63.1°，
      // 视线被抬到仰角 70.7° —— 看的全是天空。几何自检把这个揪了出来。
      const fwd = (this._f || (this._f = new THREE.Vector3())).set(1, 0, 0).applyQuaternion(wq);
      const up = (this._u || (this._u = new THREE.Vector3())).set(0, 1, 0).applyQuaternion(wq);
      const tgt = this._t || (this._t = new THREE.Vector3());
      const readouts = [];

      for (let e = 0; e < 2; e++) {
        // 在头部本地系里定方向：+x 前、+z 右 → 向左是 −z。
        // 左眼 +63.1°（偏左），右眼 −63.1°（偏右）。
        const a = (e === 0 ? 1 : -1) * EYE_AZ;
        const c = cams[e];
        c.position.copy(wp);
        c.up.copy(up);
        tgt.set(Math.cos(a), 0, -Math.sin(a)).applyQuaternion(wq).multiplyScalar(10).add(wp);
        c.lookAt(tgt);
        c.updateProjectionMatrix();
        renderer.setRenderTarget(target);
        renderer.render(scene, c);
        renderer.readRenderTargetPixels(target, 0, 0, RW, RH, buf);
        // WebGL 读回自下而上，而采样表按正常图像（自上而下）建 →
        // 不翻转的话果蝇看到的世界是上下颠倒的。
        // 同时在这里做鱼眼校正：fish[dst] 给出该位置该取原始图的哪个像素。
        for (let d = 0; d < RW * RH; d++) {
          const si = fish[d];
          if (si < 0) { G[d] = 0; B[d] = 0; continue; }
          const sr = (si / RW) | 0, sc = si % RW;
          const i = ((RH - 1 - sr) * RW + sc) * 4;
          G[d] = buf[i + 1] / 255; B[d] = buf[i + 2] / 255;
        }
        const hex = Float64Array.from(retina.sampleGB(G, B));
        readouts.push(hex);
        this.draw.drawHex(canvases[e], hex, this.geom, "mosaic", this.pale);
      }
      for (const [m, v] of self) m.visible = v;
      renderer.setRenderTarget(prevTarget);
      renderer.setClearColor(prevClear, prevAlpha);
      return readouts;
    }

    /**
     * 「大脑成像」：把左右眼的 721 个小眼按**各自真实的视线方向**画到
     * 同一张方位角/仰角图上，就是这只果蝇此刻的完整视野。
     *
     * 它不是"两张图拼在一起"的示意 —— 每个小眼的位置都是从
     * 鱼眼逆映射 + 157° 透视投影 + ±63.1° 光轴 算出来的。
     * 正前方那条重叠带就是**双眼视区**，两侧是单眼区，背后是盲区。
     */
    drawBrain(cv, readouts) {
      const g = cv.getContext("2d"), W = cv.width, H = cv.height;
      g.clearRect(0, 0, W, H);
      const AZ = 150 * Math.PI / 180;               // 画 ±150°，够覆盖 283° 的视野
      const EL = 80 * Math.PI / 180;
      const X = a => W * (0.5 + a / (2 * AZ));
      const Y = e => H * (0.5 - e / (2 * EL));
      // 双眼重叠带：两眼视场各 157°、光轴 ±63.1° → 重叠 157−2×63.1 = 30.8°
      const ov = (157 - 2 * (EYE_AZ * 180 / Math.PI)) / 2 * Math.PI / 180;
      g.fillStyle = "rgba(255,255,255,.055)";
      g.fillRect(X(-ov), 0, X(ov) - X(-ov), H);
      let lo = Infinity, hi = -Infinity;
      for (const r of readouts) for (const v of r) { if (v < lo) lo = v; if (v > hi) hi = v; }
      const rng = (hi - lo) || 1;
      const rad = Math.max(1.4, W / 150);
      for (let e = 0; e < 2; e++) {
        const { az, el } = this.dirs[e], r = readouts[e], perm = this.permArr;
        for (let j = 0; j < r.length; j++) {
          const k = perm[j];                        // 柱序 → flygym 序（方向表按 flygym 序）
          if (!Number.isFinite(az[k])) continue;            // 无效小眼不画
          const t = (r[j] - lo) / rng;
          g.fillStyle = this.pale[j]
            ? `rgb(${(t * 90) | 0},${(t * 150) | 0},${(t * 255) | 0})`
            : `rgb(${(t * 110) | 0},${(t * 255) | 0},${(t * 120) | 0})`;
          g.beginPath(); g.arc(X(az[k]), Y(el[k]), rad, 0, 7); g.fill();
        }
      }
      // 不在这张画布上画刻度线 —— 它是**要被测量的数据画布**，
      // 混进恒亮的装饰会在归一化后主导差分（几何自检一开始就被它骗了）。
      // 刻度改用画布外的 HTML 标签。
    }
  }

  return { Cam, RW, RH, FOVY, ZOOM, DIST, EYE_AZ, buildFisheye, eyeDirections };
})();
if (typeof module !== "undefined" && module.exports) module.exports = FlyEyeCam;
