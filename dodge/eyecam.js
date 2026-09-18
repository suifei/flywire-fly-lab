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
  // 光轴方位角：在 MuJoCo 里实测 LEye_cam +63.1° / REye_cam −63.1°
  const EYE_AZ = 63.1 * Math.PI / 180;

  // ── 小眼视线方向：直接从六边形点阵算 ──────────────────────
  //
  // 为什么不再用 FlyGym 那套（157° 透视 + 鱼眼校正）：
  // 那是为 MuJoCo 的**直线渲染**做的补偿 —— 透视投影天生到不了 180°，
  // 157° 时边缘已经被拉得极扁，鱼眼公式还有个奇点（半径 0.513 处分母变号）。
  // 换成立方体贴图后不存在这个限制：六个 90° 面覆盖整个球面，
  // 任意方向都能精确采样，于是小眼方向可以直接按点阵定义。
  //
  // 点阵半径 15（721 = 3·15²+3·15+1），小眼间角取 5.7°，
  // 单眼视野 = 2×15×5.7 = **171°**，接近真果蝇（文献 ~160–180°）。
  // 真果蝇的小眼间角从正前 ~4.5° 到侧面 ~8° 渐变，这里取**常数 5.7°**
  // 是简化，属于手写设定。
  const DPHI = 5.7 * Math.PI / 180;
  const HALF_FOV = 15 * DPHI;              // 每眼半视野 85.5° → 单眼 171°

  /**
   * @param {Array<[number,number]>} lattice 721 个柱的轴向六边形坐标
   * @param {number} sign +1 左眼 / −1 右眼
   * @returns {{dir:Float64Array, az:Float64Array, el:Float64Array}}
   *   dir 是 3×n 的方向（**头部本地系**：+x 前、+y 上、+z 右）
   */
  function latticeDirs(lattice, sign) {
    const n = lattice.length;
    const dir = new Float64Array(n * 3), az = new Float64Array(n), el = new Float64Array(n);
    const yaw0 = sign * EYE_AZ;
    // 光轴 F，以及它所在切平面的两个基：R = 方位角增大的方向，U = 上。
    const F = [Math.cos(yaw0), 0, -Math.sin(yaw0)];
    const R = [-Math.sin(yaw0), 0, -Math.cos(yaw0)];
    const U = [0, 1, 0];
    for (let i = 0; i < n; i++) {
      const [u, v] = lattice[i];
      const hx = u + v / 2, hy = v * Math.sqrt(3) / 2;
      // **方位等距投影**：把 (hx,hy) 当成偏离光轴的角度向量，
      // 偏离角 θ = |h|·Δφ，方向 φ = atan2(hy,hx)。
      //
      // 第一版把 hx、hy 分别当成方位角和仰角（等距圆柱投影），
      // 结果仰角接近 ±85° 的小眼全挤向极点、方位角失去意义 ——
      // 几何自检里表现为"右眼报出本该只有左眼看得到的方位"。
      const th = Math.hypot(hx, hy) * DPHI, ph = Math.atan2(hy, hx);
      const ct = Math.cos(th), st = Math.sin(th), cp = Math.cos(ph), sp = Math.sin(ph);
      const x = F[0] * ct + (R[0] * cp + U[0] * sp) * st;
      const y = F[1] * ct + (R[1] * cp + U[1] * sp) * st;
      const z = F[2] * ct + (R[2] * cp + U[2] * sp) * st;
      dir[i * 3] = x; dir[i * 3 + 1] = y; dir[i * 3 + 2] = z;
      az[i] = Math.atan2(-z, x);          // 与 d=(cos az·cos el, sin el, −sin az·cos el) 一致
      el[i] = Math.asin(Math.max(-1, Math.min(1, y)));
    }
    return { dir, az, el };
  }

  /**
   * 世界方向 → 立方体贴图的（面, 像素下标）。
   * 用的是 OpenGL 立方体贴图的标准约定；面序 0:+X 1:−X 2:+Y 3:−Y 4:+Z 5:−Z。
   * readRenderTargetPixels 读回是**自下而上**的，所以行要翻。
   */
  function cubeLookup(x, y, z, size) {
    const ax = Math.abs(x), ay = Math.abs(y), az2 = Math.abs(z);
    let face, sc, tc, ma;
    if (ax >= ay && ax >= az2) { ma = ax; if (x > 0) { face = 0; sc = -z; } else { face = 1; sc = z; } tc = -y; }
    else if (ay >= az2) { ma = ay; if (y > 0) { face = 2; sc = x; tc = z; } else { face = 3; sc = x; tc = -z; } }
    else { ma = az2; if (z > 0) { face = 4; sc = x; } else { face = 5; sc = -x; } tc = -y; }
    let sX = Math.floor(0.5 * (sc / ma + 1) * size);
    let sY = Math.floor(0.5 * (tc / ma + 1) * size);
    sX = Math.min(size - 1, Math.max(0, sX));
    sY = Math.min(size - 1, Math.max(0, sY));
    // **不要翻行**：普通渲染目标 readRenderTargetPixels 是自下而上的，
    // 但立方体贴图的面是自上而下存的 —— 多翻一次会让整幅画面上下颠倒，
    // 表现为"小眼报出的方位和它实际看到的方向成镜像"。
    // 这是实测出来的：在 +X 面上放偏心标记，实测行 133 而翻转后的预测是 47。
    return face * size * size + sY * size + sX;
  }

  // ── 紫外反射率（手写设定，不是测量值）────────────────────
  //
  // 果蝇的 R7 是紫外感受器（pale 型 Rh3 ~345 nm / yellow 型 Rh4 ~375 nm），
  // 而 sRGB 渲染里根本没有紫外。这里给场景里每类物体**指定**一个紫外反射率。
  //
  // 指定的依据是真实的紫外世界结构，不是随手编的：自然界里**天空是压倒性的
  // 紫外源**，绝大多数表面紫外很暗 —— 果蝇正是靠这个对比找开阔空间、
  // 判断上下（背侧边缘区）。所以这里天空给 1.0，地面和器械都很低。
  //
  // **但它终究是手写的**：数值没有任何测量依据，只是结构上说得通。
  // 上传的照片里更是完全没有紫外信息，那一路会显示为"无数据"。
  const UV = {
    sky: 1.0, floor: 0.06, line: 0.30, seat: 0.09,
    rig: 0.16, board: 0.22, rim: 0.18,
    ball: 0.02, pellet: 0.14, fly: 0.05, default: 0.08,
  };
  function uvOf(obj) {
    const n = (obj.name || "") + " " + (obj.parent && obj.parent.name || "");
    if (/ball/i.test(n)) return UV.ball;
    if (/pellet|dust/i.test(n)) return UV.pellet;
    if (/court|floor/i.test(n)) return UV.floor;
    if (/seat|stand/i.test(n)) return UV.seat;
    if (/rim/i.test(n)) return UV.rim;
    if (/board/i.test(n)) return UV.board;
    if (/post|rig/i.test(n)) return UV.rig;
    return UV.default;
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
      this.retina = retina; this.draw = draw; this.lattice = lattice;
      this.size = opts.cube || 192;                        // 每面边长
      this.rt = new THREE.WebGLCubeRenderTarget(this.size, {
        format: THREE.RGBAFormat, type: THREE.UnsignedByteType,
        minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter,
      });
      // 两只眼几乎同位（FlyGym 里相距 0.76 mm，在本场景可忽略），
      // 所以**一张立方体贴图两只眼共用**，各自按自己的方向表采样。
      this.cube = new THREE.CubeCamera(0.05, 900, this.rt);
      this.buf = new Uint8Array(this.size * this.size * 4);
      this.faces = [];                                     // 6 面的 RGB
      for (let f = 0; f < 6; f++) this.faces.push(new Uint8Array(this.size * this.size * 3));
      this.dirs = [1, -1].map(sg => latticeDirs(lattice, sg));
      this.pale = retina.paleByColumn();
      this.permArr = retina.perm;
      this.geom = null;
      this.lastMs = 0;
      this.sky = new THREE.Color(opts.sky || "#9fb4c8");
      // 复制一份：外面可能整体重新赋值 fs.selfMeshes，别名会让这里悄悄指向旧数组。
      // 建好之后还会把"视野扇区"推进来（见 eye.js）——那是给玩家看的标注，
      // 不该出现在果蝇自己的复眼里。
      this.selfMeshes = (opts.selfMeshes || []).slice();
      this.n = lattice.length;
      // 六边形邻居表：去马赛克要用。每个小眼只测一路（pale 测蓝 / yellow 测绿），
      // 另一路靠邻居里另一型的平均估出来 —— 和拜耳滤镜的去马赛克是同一回事。
      // **果蝇本身并没有在每个小眼上同时拿到两路**，这一步是显示用的插值。
      {
        const key = (u, v) => ((u + 32) << 6) | (v + 32);
        const pos = new Map();
        lattice.forEach(([u, v], i) => pos.set(key(u, v), i));
        const NB = [[1, 0], [-1, 0], [0, 1], [0, -1], [1, -1], [-1, 1]];
        this.nbr = lattice.map(([u, v]) => {
          const out = [];
          for (const [du, dv] of NB) {
            const i = pos.get(key(u + du, v + dv));
            if (i !== undefined) out.push(i);
          }
          return out;
        });
      }
      this.demo = [new Float64Array(this.n * 2), new Float64Array(this.n * 2)];  // [G,B] 交错
      this.out = [new Float64Array(this.n), new Float64Array(this.n)];   // 彩色（G 或 B）
      this.uv = [new Float64Array(this.n), new Float64Array(this.n)];    // 紫外（R7）
      this._uvMats = null;
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
    /**
     * @param {object} headObj 果蝇头部（用它的世界位姿：同时跟上机体姿态和头部摆动）
     * @param {HTMLCanvasElement[]} canvases [左眼, 右眼]
     * @returns {{color:Float64Array[], uv:Float64Array[]}}
     */
    update(headObj, canvases) {
      const { THREE, renderer, scene, rt, cube, buf, faces, size, retina } = this;
      if (!this.geom) this.geom = this.draw.hexGeom(this.lattice, canvases[0].width, canvases[0].height);
      const prevTarget = renderer.getRenderTarget();
      const prevClear = renderer.getClearColor(new THREE.Color());
      const prevAlpha = renderer.getClearAlpha();
      renderer.setClearColor(this.sky, 1);

      // 果蝇看不到自己的头（FlyGym 渲眼图时也隐藏头/口器/胸/触角共 14 个部件）
      const self = this.selfMeshes.map(m => [m, m.visible]);
      for (const [m] of self) m.visible = false;

      // 紫外：R 通道空着没用，正好拿来装 R7。渲之前把每个材质的 red
      // 换成它的紫外反射率，渲完还原。这样一次渲染同时得到 紫外/绿/蓝 三路。
      if (!this._uvMats) {
        this._uvMats = [];
        scene.traverse(o => {
          if (!o.material) return;
          for (const m of (Array.isArray(o.material) ? o.material : [o.material]))
            if (m.color) this._uvMats.push([m, uvOf(o)]);
        });
      }
      const savedR = this._uvMats.map(([m]) => m.color.r);
      this._uvMats.forEach(([m, v], i) => { m.color.r = v; });
      // 天空（清屏色）也要带紫外：自然界里天空是压倒性的紫外源
      renderer.setClearColor(new THREE.Color(UV.sky, this.sky.g, this.sky.b), 1);

      const wp = this._wp || (this._wp = new THREE.Vector3());
      const wq = this._wq || (this._wq = new THREE.Quaternion());
      headObj.getWorldPosition(wp); headObj.getWorldQuaternion(wq);
      cube.position.copy(wp);
      cube.update(renderer, scene);

      for (let f = 0; f < 6; f++) {
        renderer.readRenderTargetPixels(rt, 0, 0, size, size, buf, f);
        const dst = faces[f];
        for (let i = 0, j = 0; i < buf.length; i += 4, j += 3) {
          dst[j] = buf[i]; dst[j + 1] = buf[i + 1]; dst[j + 2] = buf[i + 2];
        }
      }
      this._uvMats.forEach(([m], i) => { m.color.r = savedR[i]; });
      for (const [m, v] of self) m.visible = v;

      // 按每个小眼的方向去采样：不需要鱼眼，任意方向都能精确取到
      const q = wq, n = this.n, pale = this.pale;
      const vTmp = this._v || (this._v = new THREE.Vector3());
      for (let e = 0; e < 2; e++) {
        const d = this.dirs[e].dir, col = this.out[e], uvv = this.uv[e];
        for (let j = 0; j < n; j++) {
          // 方向表是按**点阵（柱序）**建的，不涉及 flygym 序 ——
          // 这里曾经多套了一层 retina.perm，把方向全打乱了：
          // 右眼会"看到"本该只有左眼能看到的方位（几何自检里表现为
          // 两眼都看到同一个标记、合成质心落在 0° 附近）。
          // 局部 → 世界：用 three.js 自己的实现，不手写四元数展开。
          // 3 fps 下每帧 1442 次向量运算可以忽略，而手写展开是整条链路里
          // 唯一没被独立验证过的一环（方向表、cubeLookup 都单独验过）。
          vTmp.set(d[j * 3], d[j * 3 + 1], d[j * 3 + 2]).applyQuaternion(q);
          const idx = cubeLookup(vTmp.x, vTmp.y, vTmp.z, size);
          const face = (idx / (size * size)) | 0, off = (idx % (size * size)) * 3;
          const px = faces[face];
          uvv[j] = px[off] / 255;                            // R = 紫外
          col[j] = (pale[j] ? px[off + 2] : px[off + 1]) / 255;   // pale 取蓝、yellow 取绿
        }
        // 去马赛克：把每个小眼缺的那一路用邻居里另一型的平均补上
        const dm = this.demo[e], nbr = this.nbr;
        for (let j = 0; j < n; j++) {
          const isP = pale[j];
          let s2 = 0, c2 = 0;
          for (const i of nbr[j]) if (!!pale[i] !== !!isP) { s2 += col[i]; c2++; }
          const other = c2 ? s2 / c2 : col[j];
          dm[j * 2] = isP ? other : col[j];       // G（yellow 直接测到）
          dm[j * 2 + 1] = isP ? col[j] : other;   // B（pale 直接测到）
        }
        this.draw.drawHex(canvases[e], col, this.geom,
                          this.demosaic ? "fly" : "mosaic", pale, dm);
      }

      renderer.setRenderTarget(prevTarget);
      renderer.setClearColor(prevClear, prevAlpha);
      // 返回**副本**：this.out/this.uv 是复用缓冲区，直接返回引用的话
      // 调用方拿到的"上一帧"会被下一帧覆盖，差分恒为 0（几何自检就是这么挂的）。
      return { color: this.out.map(a => Float64Array.from(a)),
               uv: this.uv.map(a => Float64Array.from(a)),
               gb: this.demo.map(a => Float64Array.from(a)) };
    }

    /**
     * 「大脑成像」：把左右眼的 721 个小眼按**各自真实的视线方向**画到
     * 同一张方位角/仰角图上，就是这只果蝇此刻的完整视野。
     *
     * 它不是"两张图拼在一起"的示意 —— 每个小眼的位置都是从
     * 鱼眼逆映射 + 157° 透视投影 + ±63.1° 光轴 算出来的。
     * 正前方那条重叠带就是**双眼视区**，两侧是单眼区，背后是盲区。
     */
    drawBrain(cv, readouts, mode, gbs) {
      const g = cv.getContext("2d"), W2 = cv.width, H2 = cv.height;
      g.clearRect(0, 0, W2, H2);
      const AZ = 155 * Math.PI / 180, EL = 90 * Math.PI / 180;
      const X = a => W2 * (0.5 + a / (2 * AZ));
      const Y = e => H2 * (0.5 - e / (2 * EL));
      // 双眼重叠：每眼半视野 15×Δφ = 85.5°，光轴 ±63.1° → 重叠 ±22.4°
      const ov = HALF_FOV - EYE_AZ;
      g.fillStyle = "rgba(255,255,255,.055)";
      g.fillRect(X(-ov), 0, X(ov) - X(-ov), H2);
      let lo = Infinity, hi = -Infinity;
      for (const r of readouts) for (const v of r) { if (v < lo) lo = v; if (v > hi) hi = v; }
      const rng = (hi - lo) || 1;
      // 绿/蓝两路有自己的量程，不能和紫外共用 —— 紫外的天空是压倒性的亮，
      // 共用量程会把绿蓝全压成黑。
      let lo2 = Infinity, hi2 = -Infinity;
      if (gbs) for (const a of gbs) for (const v of a) { if (v < lo2) lo2 = v; if (v > hi2) hi2 = v; }
      const rng2 = (hi2 - lo2) || 1;
      const rad = Math.max(1.3, W2 / 170);
      for (let e = 0; e < 2; e++) {
        const { az, el } = this.dirs[e], r = readouts[e];
        for (let j = 0; j < r.length; j++) {
          const t = (r[j] - lo) / rng;
          // 紫外没有对应的可见色，用紫罗兰表示；彩色路按 pale/yellow 分型
          if (mode === "uv") {
            if (gbs) {
              // 三通道合成：果蝇的全部三路一起看。
              // 紫外→紫（R7 每个小眼都有，**本来就不存在马赛克**），
              // 绿/蓝→绿/蓝（这两路才是马赛克的，去马赛克只作用在它们身上）。
              const G = Math.max(0, Math.min(1, (gbs[e][j * 2] - lo2) / rng2));
              const B = Math.max(0, Math.min(1, (gbs[e][j * 2 + 1] - lo2) / rng2));
              g.fillStyle = `rgb(${((t * 0.85 + G * 0.15) * 255) | 0},` +
                            `${((G * 0.75 + t * 0.25) * 255) | 0},` +
                            `${((B * 0.55 + t * 0.45) * 255) | 0})`;
            } else {
              g.fillStyle = `rgb(${(t * 190) | 0},${(t * 90) | 0},${(t * 255) | 0})`;
            }
          } else if (gbs) {
            // 「果蝇色」：去马赛克后的绿/蓝两路，红给 0（果蝇几乎看不见红）
            const G = Math.max(0, Math.min(1, (gbs[e][j * 2] - lo) / rng));
            const B = Math.max(0, Math.min(1, (gbs[e][j * 2 + 1] - lo) / rng));
            g.fillStyle = `rgb(${(40 * Math.min(G, B)) | 0},${(G * 255) | 0},${(B * 255) | 0})`;
          } else {
            g.fillStyle = this.pale[j]
              ? `rgb(${(t * 90) | 0},${(t * 150) | 0},${(t * 255) | 0})`
              : `rgb(${(t * 110) | 0},${(t * 255) | 0},${(t * 120) | 0})`;
          }
          g.beginPath(); g.arc(X(az[j]), Y(el[j]), rad, 0, 7); g.fill();
        }
      }
      // 不在数据画布上画刻度线 —— 恒亮装饰会在归一化后主导差分测量。
    }
  }

  return { Cam, DPHI, HALF_FOV, EYE_AZ, latticeDirs, cubeLookup, UV };
})();
if (typeof module !== "undefined" && module.exports) module.exports = FlyEyeCam;
