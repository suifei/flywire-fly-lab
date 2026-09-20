// 场边的 3D 五子棋盘：15×15 的棋盘悬在球场一侧，果蝇飞过去插旗当棋子。
// 只管画，不管规则（规则在 rules.js，落子决策在 fly.js）。
(function (root) {
  const G = typeof module !== "undefined" && module.exports ? require("./rules.js") : root.Gomoku;

  // 棋盘放在球场右侧外面，立起来（法线沿 +y），这样从默认机位能看清
  const CFG = { cell: 11, x0: 210, y0: 0, z0: 8, flagH: 7 };

  function build(THREE, scene, colors) {
    const grp = new THREE.Group();
    const S = CFG.cell, span = S * (G.N - 1);
    grp.position.set(CFG.x0, CFG.y0, CFG.z0);
    scene.add(grp);

    // 盘面
    const pad = S * 0.8;
    const mat = new THREE.MeshLambertMaterial({ color: colors.boardWood });
    const slab = new THREE.Mesh(new THREE.BoxGeometry(span + 2 * pad, span + 2 * pad, 1.6), mat);
    slab.position.set(0, 0, -0.8);
    slab.receiveShadow = true; grp.add(slab);

    // 线
    const lineMat = new THREE.LineBasicMaterial({ color: colors.boardLine });
    for (let k = 0; k < G.N; k++) {
      const t = -span / 2 + k * S;
      for (const [a, b] of [[[-span / 2, t, 0.05], [span / 2, t, 0.05]], [[t, -span / 2, 0.05], [t, span / 2, 0.05]]]) {
        const g = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(...a), new THREE.Vector3(...b)]);
        grp.add(new THREE.Line(g, lineMat));
      }
    }
    // 五个星位
    for (const [cx, cy] of [[3, 3], [11, 3], [3, 11], [11, 11], [7, 7]]) {
      const d = new THREE.Mesh(new THREE.CircleGeometry(S * 0.12, 10),
        new THREE.MeshBasicMaterial({ color: colors.boardLine }));
      d.position.set(-span / 2 + cx * S, -span / 2 + cy * S, 0.08); grp.add(d);
    }

    const cellPos = i => {
      const x = i % G.N, y = (i / G.N) | 0;
      return new THREE.Vector3(-span / 2 + x * S, span / 2 - y * S, 0);       // y 向下数行
    };
    const worldOf = i => grp.localToWorld(cellPos(i).clone());

    // 旗子：细杆 + 三角旗（黑白两色）
    const stones = new Map();
    function flag(color) {
      const g = new THREE.Group();
      const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.22, CFG.flagH, 6),
        new THREE.MeshLambertMaterial({ color: colors.pole }));
      pole.rotation.x = Math.PI / 2; pole.position.z = CFG.flagH / 2; g.add(pole);
      const sh = new THREE.Shape();
      sh.moveTo(0, 0); sh.lineTo(S * 0.62, S * 0.2); sh.lineTo(0, S * 0.4); sh.lineTo(0, 0);
      const cloth = new THREE.Mesh(new THREE.ShapeGeometry(sh),
        new THREE.MeshLambertMaterial({ color, side: THREE.DoubleSide }));
      cloth.rotation.x = Math.PI / 2; cloth.position.set(0.2, 0, CFG.flagH - S * 0.42);
      g.add(cloth);
      // 旗杆底下垫一颗扁棋子：只有细杆和小旗的话，从上往下看几乎看不出落在哪个交叉点上
      const stone = new THREE.Mesh(new THREE.SphereGeometry(S * 0.4, 18, 10), new THREE.MeshLambertMaterial({ color }));
      stone.scale.set(1, 1, 0.32); stone.position.z = S * 0.12; g.add(stone);
      g.castShadow = true;
      return g;
    }
    function place(i, c) {
      if (stones.has(i)) return stones.get(i);
      const f = flag(c === G.BLACK ? colors.stoneBlack : colors.stoneWhite);
      f.position.copy(cellPos(i));
      grp.add(f); stones.set(i, f);
      return f;
    }
    function clear() { for (const [, f] of stones) grp.remove(f); stones.clear(); }

    // 高亮：最后一手 + 悬停
    const ring = new THREE.Mesh(new THREE.RingGeometry(S * 0.3, S * 0.42, 18),
      new THREE.MeshBasicMaterial({ color: colors.mark, side: THREE.DoubleSide }));
    ring.position.z = 0.12; ring.visible = false; grp.add(ring);
    const markAt = i => { if (i == null) { ring.visible = false; return; } ring.position.copy(cellPos(i)); ring.position.z = 0.12; ring.visible = true; };

    return { group: grp, cell: S, span, cellPos, worldOf, place, clear, markAt, stones, CFG };
  }

  const API = { build, CFG };
  if (typeof module !== "undefined" && module.exports) module.exports = API;
  else root.GomokuBoard3D = API;
})(typeof window !== "undefined" ? window : globalThis);
