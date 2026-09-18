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
  const RW = 450, RH = 512;              // 必须和 ommatidia_id_map 的尺寸一致

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
      this.fov = opts.fov ?? 130;                          // 近似值，真果蝇接近 180°
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
    update(x, y, z, h, canvases) {
      const { THREE, renderer, scene, target, cams, buf, G, B, retina } = this;
      if (!this.geom) this.geom = this.draw.hexGeom(this.lattice, canvases[0].width, canvases[0].height);
      const prevTarget = renderer.getRenderTarget();
      const prevClear = renderer.getClearColor(new THREE.Color());
      const prevAlpha = renderer.getClearAlpha();
      renderer.setClearColor(this.sky, 1);
      // 真果蝇看不到自己的头。摄像机在身体前方 0.9 单位，不藏起来的话
      // 自己的网格会糊满半个视野（实测右眼那条亮竖纹就是自己的身体）。
      const self = (this.selfMeshes || []).map(m => [m, m.visible]);
      for (const [m] of self) m.visible = false;
      const ex = x + Math.cos(h) * this.eyeFwd, ey = y + Math.sin(h) * this.eyeFwd, ez = z + this.eyeUp;

      for (let e = 0; e < 2; e++) {
        // +y 是果蝇的左边（见 CLAUDE.md 的世界坐标约定），所以左眼偏 +yaw
        const a = h + (e === 0 ? this.eyeYaw : -this.eyeYaw);
        const c = cams[e];
        c.position.set(ex, ey, ez);
        c.lookAt(ex + Math.cos(a) * 10, ey + Math.sin(a) * 10, ez);
        c.updateProjectionMatrix();
        renderer.setRenderTarget(target);
        renderer.render(scene, c);
        renderer.readRenderTargetPixels(target, 0, 0, RW, RH, buf);
        // WebGL 读回是**自下而上**的，而采样表是按正常图像（自上而下）建的，
        // 不翻转的话果蝇看到的世界是上下颠倒的。
        for (let row = 0; row < RH; row++) {
          const src = (RH - 1 - row) * RW, dst = row * RW;
          for (let col = 0; col < RW; col++) {
            const i = (src + col) * 4;
            G[dst + col] = buf[i + 1] / 255;
            B[dst + col] = buf[i + 2] / 255;
          }
        }
        const hex = retina.sampleGB(G, B);
        this.draw.drawHex(canvases[e], hex, this.geom, "mosaic", this.pale);
      }
      for (const [m, v] of self) m.visible = v;
      renderer.setRenderTarget(prevTarget);
      renderer.setClearColor(prevClear, prevAlpha);
    }
  }

  return { Cam, RW, RH };
})();
if (typeof module !== "undefined" && module.exports) module.exports = FlyEyeCam;
