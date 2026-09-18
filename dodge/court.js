/**
 * 把场地做成一个**按 1:50 缩小的篮球场**：地面线条、两个篮架、四周观众席。
 *
 * 尺度怎么定的：先按 1:50 做成 560×300 mm，结果**相机最远只能拉到 160 mm**，
 * 视野里只看得到一段巨大的弧线。缩到 320×172（1:87.5）并把相机上限放到 420 mm，
 * 才能看全场。果蝇体长约 3 mm，相当于球场上一只 26 cm 的生物；横穿全场约 18 秒。
 * 代价是球（直径 5 mm）比真实篮球按比例偏大 —— 这是可玩性换来的，说清楚就好。
 *
 * 线条用 canvas 贴图，不用几何体 —— 几百条线做成网格会拖慢渲染，
 * 贴图一次生成、之后零成本。
 *
 * 这一整块是**手写的场景装饰**，不来自任何实验数据。它只影响果蝇能走到哪
 * （边界），不改变任何神经计算。
 */
const FlyCourt = (() => {
  const W = 320, H = 172;                 // 场地内沿尺寸（mm），28:15（1:87.5）
  const S = W / 28000;                    // 真实毫米 → 场地单位（1:50）

  function texture(THREE, line, floor) {
    // 按 FIBA 真实尺寸画（米），再统一换算到像素。
    // 球场 28×15；中圈 r=1.8；限制区 5.8×4.9；罚球圈 r=1.8（圆心距端线 5.8）；
    // 三分：篮圈中心距端线 1.575，弧半径 6.75，两条直边距边线 0.9。
    const px = 8;                                   // 每场地 mm 8 像素
    const c = document.createElement("canvas");
    c.width = Math.round(W * px); c.height = Math.round(H * px);
    const g = c.getContext("2d");
    g.fillStyle = floor; g.fillRect(0, 0, c.width, c.height);
    g.strokeStyle = line; g.lineCap = "butt"; g.lineJoin = "round";

    const sx = c.width / 28, sy = c.height / 15;     // 米 → 像素
    const X = m => m * sx, Y = m => (7.5 - m) * sy;  // 球场坐标：x 0..28，y −7.5..7.5
    g.lineWidth = Math.max(2, 0.05 * sx);

    g.strokeRect(g.lineWidth / 2, g.lineWidth / 2, c.width - g.lineWidth, c.height - g.lineWidth);
    g.beginPath(); g.moveTo(X(14), Y(7.5)); g.lineTo(X(14), Y(-7.5)); g.stroke();
    g.beginPath(); g.ellipse(X(14), Y(0), 1.8 * sx, 1.8 * sy, 0, 0, 7); g.stroke();

    for (const end of [0, 1]) {
      const base = end ? 28 : 0, dir = end ? -1 : 1;   // dir：从端线指向场内
      const bx = m => X(base + dir * m);
      // 限制区
      g.strokeRect(Math.min(bx(0), bx(5.8)), Y(2.45),
                   Math.abs(bx(5.8) - bx(0)), Math.abs(Y(-2.45) - Y(2.45)));
      // 罚球圈
      g.beginPath(); g.ellipse(bx(5.8), Y(0), 1.8 * sx, 1.8 * sy, 0, 0, 7); g.stroke();
      // 三分线：直边从端线到 y=±6.6 与弧相切处，再接 6.75 m 弧
      const cxm = 1.575;                              // 篮圈中心距端线
      const yEdge = 6.6;                              // 直边距中线的距离
      const dx = Math.sqrt(Math.max(0, 6.75 * 6.75 - yEdge * yEdge));  // 弧在该 y 处的 x 偏移
      g.beginPath();
      g.moveTo(bx(0), Y(yEdge));
      g.lineTo(bx(cxm + dx), Y(yEdge));
      // 用参数方程画弧（x/y 像素比例不同，ellipse 的起止角会被压扁，所以手动采样）
      const a0 = Math.atan2(yEdge, dx), a1 = -a0;
      for (let i = 0; i <= 48; i++) {
        const a = a0 + (a1 - a0) * i / 48;
        g.lineTo(bx(cxm + 6.75 * Math.cos(a)), Y(6.75 * Math.sin(a)));
      }
      g.lineTo(bx(0), Y(-yEdge));
      g.stroke();
    }
    const t = new THREE.CanvasTexture(c);
    t.anisotropy = 4;
    return t;
  }

  /**
   * @returns {{group:THREE.Group, W:number, H:number, dispose:Function}}
   */
  function build(THREE, scene, colors) {
    const grp = new THREE.Group(); scene.add(grp);
    const real = v => v * 1000 * S;                    // 真实米 → 场地 mm

    // 地面
    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(W, H),
      new THREE.MeshBasicMaterial({ map: texture(THREE, colors.line, colors.floor) }));
    floor.position.z = 0.004; grp.add(floor);

    // 两个篮架：底座 + 立柱 + 篮板 + 篮圈（真实尺寸换算）
    for (const s of [-1, 1]) {
      const x = s * (W / 2 + real(1.2));
      const post = new THREE.Mesh(new THREE.CylinderGeometry(real(0.12), real(0.16), real(3.6), 10),
        new THREE.MeshLambertMaterial({ color: colors.rig }));
      post.rotation.x = Math.PI / 2; post.position.set(x, 0, real(1.8)); grp.add(post);
      const board = new THREE.Mesh(new THREE.BoxGeometry(real(0.05), real(1.8), real(1.05)),
        new THREE.MeshLambertMaterial({ color: colors.board, transparent: true, opacity: 0.78 }));
      board.position.set(x - s * real(0.5), 0, real(3.05 + 0.15)); grp.add(board);
      const rim = new THREE.Mesh(new THREE.TorusGeometry(real(0.225), real(0.02), 8, 20),
        new THREE.MeshLambertMaterial({ color: colors.rim }));
      rim.position.set(x - s * real(0.95), 0, real(3.05)); grp.add(rim);
    }

    // 观众席：四周三级看台，越外越高
    const tiers = 3, step = real(1.6), rise = real(0.9);
    for (let i = 0; i < tiers; i++) {
      const pad = real(1.4) + i * step, z = (i + 0.5) * rise;
      const ow = W + 2 * pad + step, oh = H + 2 * pad + step;
      const col = i % 2 ? colors.seatA : colors.seatB;
      const mat = new THREE.MeshLambertMaterial({ color: col });
      for (const [w, h, dx, dy] of [
        [ow, step, 0, (oh - step) / 2], [ow, step, 0, -(oh - step) / 2],
        [step, oh - 2 * step, (ow - step) / 2, 0], [step, oh - 2 * step, -(ow - step) / 2, 0],
      ]) {
        const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, rise), mat);
        m.position.set(dx, dy, z); grp.add(m);
      }
    }
    return { group: grp, W, H, real };
  }

  return { build, W, H, SCALE: S };
})();
if (typeof module !== "undefined" && module.exports) module.exports = FlyCourt;
