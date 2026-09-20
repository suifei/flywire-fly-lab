// 果蝇闪避：与渲染无关的游戏核心（浏览器与 node 共用）
// 连接组部分在 brain.js；这里是手写的部分：视觉前端、运动映射、起跳规则、球与判定。
(function (root) {
  const DEFAULTS = {
    walkSpeed: 18,          // mm/s 基础行走速度
    turnGain: 6,            // °/s per Hz（左 DNa − 右 DNa）
    turnMax: 420,           // °/s
    loomGain: 120,          // Hz per rad/s of dθ/dt
    loomMax: 200,           // Hz
    gfThreshold: 90,        // Hz（平滑后）
    // 起跳：原地垂直腾空、不带水平位移。回路里没有“起跳方向”的姿态控制，
    // 所以不人为指定方向，躲不躲得开只取决于巨纤维放电的时机
    jumpDur: 0.3, jumpDist: 0, jumpHeight: 6, jumpCooldown: 0.9,
    ballR: 2.5, flyR: 1.4,
    // 场地边界：按 1:87.5 缩小的篮球场（真实 28×15 m → 320×172 mm）。
    // 纯场景设定，不参与任何神经计算；只决定果蝇能走到哪。
    courtW: 320, courtH: 172, courtPad: 4,
    chunkSteps: 50,         // 5 ms 一块：块间更新视觉输入与身体
    emaTau: 0.08,
    gfTau: 0.08,            // 巨纤维读出的平滑时间常数（v2 用 0.02）

    // —— 视觉编码 ——
    // "legacy"：LC4 与 LPLC2 都 = loomGain·dθ/dt（第一版，巨纤维放电过早）
    // "ache2019"：Ache et al. 2019 Curr Biol：LC4 编码角速度（线性），LPLC2 编码角尺寸（高斯）；
    //   函数形式来自文献，参数（斜率、高斯中心/宽度、峰值）为手选，原文参数未能获取
    encoding: "legacy",
    lc4Slope: 0.5,          // Hz per °/s
    // 角尺寸高斯：中心/宽度（°）、峰值 Hz。
    // **中心 42° 是 Ache et al. 2019 的论文值**（2026-09-19 查到：该文的 GF 输入模型里
    // 角大小高斯项"peak at 42°"）；此前这里是手选的 45°。实测改动影响在噪声内：
    // hop 起飞模式下 5 种子 × 90 s，闪避率 83.3% → 84.7%（差 1.4 pp，二项标准误约 3.6 pp）。
    // 宽度 15° 与峰值 200 Hz 仍是手选 —— 论文全文取不到（cell.com 403），只拿到峰位。
    lplc2Mu: 42, lplc2Sigma: 15, lplc2Peak: 200,

    // —— 起飞 ——
    // "hop"：原地垂直腾空 0.3 s（第一版）
    // "flyaway"：Card & Dickinson 2008：起飞前姿态调整使果蝇“直接背离逼近的威胁”起跳；
    //   这一姿态控制不在回路里，方向按手写规则取当前最强 looming 刺激的反方向
    takeoff: "hop",
    flyClimb: 0.05, flySpeed: 150, flyDur: 0.5, flyHeight: 10,
    // "clip"：沿真实果蝇逃逸飞行轨迹（Muijres et al. 2014，经 flybody 导出）飞行；
    //   威胁在左 → 选右转轨迹（反之亦然），轨迹旋转到“背离威胁”方向；起飞 20 ms 内升到 clipLift 高度（手写过渡）
    clipLift: 5, clipLiftDur: 0.02, landDur: 0.05,

    // —— v3：进食 / 苦味 / 梳理 / 后退（需要 subcircuit_v2 的输入输出组；v1 子回路下自动不启用）——
    ema2Tau: 0.05,          // MN9 / aDN1 / MDN 读出平滑
    lc16Slope: 0.5,         // Hz per °/s：Sen et al. 2017，LC16 对 looming 反应并经 MDN 引发后退（编码形式手选，同 LC4）
    mdnThreshold: 20, backSpeed: 12,           // MDN 平滑发放率 > 阈值 → 后退（mm/s）
    gustRate: 200,          // 头部碰到颗粒时味觉神经元频率（Hz）
    pelletR: 0.8, headOffset: 1.3,             // 颗粒半径、头部相对胸部前移（mm）
    feedThreshold: 30, eatRate: 0.6,           // MN9 两侧平均 > 阈值 → 停下伸喙进食；每秒吃掉的份量（颗粒 1 份）
    joRate: 200, groomThreshold: 20, groomDur: 0.6,   // 灰尘在触角上 → 该侧 JO；aDN1 > 阈值 → 梳理 groomDur 秒后清掉灰尘
    autoPellets: false, pelletEvery: 4, pelletAhead: 8, pelletTypes: ["sugar", "bitter", "mixed"],

    // —— 物理环境（2026-09-16 加）——
    // 风：连接组依据是「游戏里的 JO 组正是 JO-C/E 亚型」——风觉 / 重力觉神经元（Yorozu et al. 2009），
    //     也正是报告 §13 词表里“风”对应的那群。风强度与方向随机游走；迎风一侧的触角被驱动得更强。
    //     风速 → JO 频率的换算是手选的（没有该模型下的定标数据）。
    wind: false, windSpeed: 0, windDir: 0, windTau: 6, windJO: 120, windPush: 0.25, windFlyPush: 2.5,
    // 光照：0 = 全黑，1 = 正午。直接刺激光感受器在这个 LIF 模型里驱动不了下行神经元（见 AGENTS.md），
    //     所以光照只按手写规则调节视觉前端的增益（暗 → 对比度低 → looming 检测弱），不假装是连接组算出来的。
    light: 1, lightFloor: 0.35,
    // 口渴：论文的水味觉实验用的是脱水处理过（pseudodessicated）的果蝇，渴时才会对水伸喙。
    // 这里用一个手写的口渴度：随时间上升，喝水下降；口渴时喝水的阈值按比例降低（阈值形式是手写的，依据是论文的实验条件）。
    thirstRise: 0.06, thirstDrop: 0.5, waterThreshRatio: 0.12,
    optoHz: 150, optoDur: 0.4,      // 光遗传脉冲：强度与时长（手选；论文的单神经元激活扫频用 25–200 Hz）
    speechEvery: 1.2,        // 每隔多久更新一次“果蝇在说什么”
    speechWind: 25,          // JO 里风的贡献 > 这个频率才算“感觉到风”
    autoDust: false, dustEvery: 5,
    autoDist: 55, autoEvery: [1.4, 2.2], ballLife: 4,

    // —— v4：手写嗅觉导航（非连接组；全脑模型给不出气味侧化，见 docs/log/report.md 11.4）——
    // 颗粒散发高斯气味场；左右触角各采一次浓度，浓度 > odorMin 时按 sign(左 − 右) 以 odorTurn 转向，叠加在 DNa 转向上；
    // 已经尝过（碰过）的颗粒不再吸引。odorNav 为 true 时自动放的颗粒改放在 pelletAround mm 外的随机方位。
    // 围栏视觉（见 visualInput 里的长注释）：wallSpan 是墙在视野里的"有效宽度"（手选），
    // wallSee 是多远之外就不再当成逼近物（手选），wallGain 是相对球的增益（手选）。
    // 这三个都是手写参数，没有文献值——真果蝇对墙的反应没有可用的定标数据。
    // **默认关**：autoplay.js / step1 / step_v3 / backward_v4 已发布的闪避率都是在"看不见墙"
    // 的条件下测的，改默认值会让那些数字全部失效（与 pelletTypes 同样的处理）。页面把它打开。
    wallVision: false, wallSpan: 40, wallSee: 60, wallGain: 1.0,
    // 触感：触角碰到围栏 → 该侧 JO。这是**物理量**，不是判断逻辑——
    // 碰到之后转不转、跳不跳、还是去梳理，完全由连接组决定。
    // 默认关，理由同 wallVision：已发布的对局数字都是在没有它的条件下测的。
    touch: false, touchRate: 200, antennaLen: 1.6,
    // 温度 / 湿度场：G.fields 里每个源 {type:"heat"|"damp", x, y, sigma, strength}
    // 强度 1.0 对应 fieldRate Hz。同样是**物理量**，没有任何"太热就走开"之类的规则。
    fieldRate: 200,
    // ── v4：听觉 / 嗅觉 / 内感受 + 自主生活（2026-09-20）。**全部默认关**，已发布的数字不受影响 ──
    // 原则不变：世界只提供物理量，送到真实的感受器上；转不转、跳不跳、吃不吃由连接组决定。
    // 声源 G.sounds：{x, y, level, t, dur}。到达触角的声强按 level / (1 + (d/soundRef)²) 衰减（手写），换算成 AUDIO 神经元的频率。
    //   左右耳差：声源在哪一侧，哪一侧略强（±earBias，手写）。sensor_drive_v4.json：双侧 100 Hz 就能让巨纤维放电，单侧不行。
    audioRate: 200, soundRef: 60, earBias: 0.25,
    // 气味源 G.odors：{x, y, kind: "vinegar" | "geosmin", sigma, strength}。两根触角各自采样浓度（高斯羽流，手写）→ OLFA / OLFR。
    //   sensor_drive_v4.json：这两路在这个子回路里**没有落到任何运动读出上**——它闻得到，但闻到之后往哪走，模型里没有通路。
    olfRate: 200,
    // —— v5：蘑菇体学习回路（子回路带 mb_tag 时才有）——
    // 气味 = 哪些嗅小球的感受神经元被驱动（SUB.meta.odors：A / B 各 20 个互不重合的小球；vinegar = DM1；geosmin = DA2）。
    // 强化信号：连接组自己叫不起多巴胺神经元（learn/reinforcement_route.py，阴性），所以这根线是**手接的**：
    //   吃到糖 → PAM 整簇 danRate Hz；热到 painThermo 以上、或者吃到苦的 → PPL1 整簇 danRate Hz。
    //   等价于真果蝇实验里用光遗传激活多巴胺神经元代替糖 / 电击。学到什么、改哪几个隔室，仍由连接组和可塑性规则决定（dodge/plasticity.js）。
    learning: true, reinforce: true, danRate: 30, painThermo: 0.5, plastEta: 0.003, plastTauE: 200, plastForget: 0,
    // 记忆 → 行为的桥（**手写，默认关**）：实测这个模型里记忆走不到运动输出（learn/memory_to_motor.py，阴性）。打开后：
    //   价 = 这种气味在奖赏隔室（PAM）被压掉的比例 − 在惩罚隔室（PPL1）被压掉的比例（文献：PAM 隔室的 MBON 促回避、PPL1 隔室的促趋近，压低前者 = 趋近，Aso 2014 eLife；Owald 2015 Neuron），
    //   再乘两根触角浓度差的符号 → 转向。隔室归属来自连接组；「读突触 → 价 → 转向」这条链是我们写的。
    memoryNav: false, memoryTurn: 150, memoryTau: 0.3,
    // 身体状态（能量 / 水分）：属于**身体**，不是大脑。它们只改两样东西，都不是决策：
    //   ① 味觉感受器的灵敏度：饿了糖感受器更敏感、渴了水感受器更敏感（文献：Inagaki et al. 2012 饥饿经多巴胺提高糖 GRN 的敏感度；增益大小手选）
    //   ② 走路速度：能量低了走得慢（手写）
    //   physiology = false 时完全不起作用。与旧的 thirst 手写阈值规则互斥：physiology 打开时关掉那条规则。
    physiology: false, energyDrop: 0.002, energyFly: 0.012, energyEat: 0.35, hydraDrop: 0.003, hydraDrink: 0.5, gainMin: 0.1, gainMax: 1.6,
    //   physiology 打开时「MN9 超过多少 Hz 算开吃」统一用 lifeFeedThreshold（糖、水一视同仁，手选）。原来的 30 Hz 水永远过不了：
    //   水感受器开到 320 Hz，MN9 也只有 22 Hz（实测）；页面球场模式里是靠一条手写的"渴了就降阈值"规则绕过去的，这里不用那条规则。
    lifeFeedThreshold: 10,
    // 内感受神经元 ISN（4 个）：文献（González-Segarra 2023）里饥饿提高、口渴降低它的活动。isnDrive = true 时按这个关系驱动真实的 ISN。
    //   **默认关**：sense_modulation.json 实测，这个模型里驱动 ISN 会把吃糖的 MN9 从 44 Hz 压到 2.5 Hz——与文献方向相反
    //   （ISN 用神经肽 dILP3，LIF 模型只有预测的快递质符号）。打开它会得到一只饿了反而不吃的果蝇；保留开关只为如实展示这一点。
    isnDrive: false, isnRate: 200,
    // 自主生活：世界自己运转（昼夜、糖 / 水 / 苦、气味、声音、热源、水洼、风、灰尘、来袭的球）。节奏参数全部手选。
    arenaR: 0,   // > 0 = 圆形场地（半径 mm），像真实实验用的培养皿；矩形场地的墙角会把只靠触感避墙的果蝇卡死（两根触角同时压墙，左右相等，转向差为 0）
    life: false, dayLength: 180, lifeNearFrac: 0.7, lifeCull: 170, lifeFoodR: 7, lifeFoodAmount: 4, lifeFood: [6, 14], lifeWater: [9, 18], lifeSound: [18, 40], lifeHeat: [40, 80], lifeBall: [20, 45],
    odorNav: false, odorSigma: 15, odorTurn: 120, odorMin: 0.01, antennaAhead: 1.0, antennaSep: 0.6, pelletAround: 25,
  };
  const TG = ["DNa01_left", "DNa01_right", "DNa02_left", "DNa02_right", "DNp01_left", "DNp01_right"];

  function rng32(seed) {
    let s = seed >>> 0;
    return () => { s = (s + 0x6d2b79f5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  }

  // 飞行片段在起飞后 t 秒时的位置（step() 与页面渲染共用；页面用它在两个 5 ms 游戏步之间逐帧显示，
  // 否则 0.4 ms 一帧的拍翅数据每步跳 12–13 帧 ≈ 1.09 个拍翅周期，翅膀看起来几乎不动）
  // 起飞后 clipLiftDur 内抬升到 clipLift（手写过渡）；片段结束后在 landDur 内线性降落（手写过渡）
  function clipPose(c, CFG, origin, jumpDir, t) {
    const fi = Math.min(c.n - 1, Math.floor(t / c.dt));
    const ca = Math.cos(jumpDir), sa = Math.sin(jumpDir);
    const px = c.pos[fi * 3], py = c.pos[fi * 3 + 1], pz = c.pos[fi * 3 + 2];
    const end = c.n * c.dt;
    const P = { frame: fi, x: origin[0] + ca * px - sa * py, y: origin[1] + sa * px + ca * py, landing: t >= end, done: false, z: 0, landU: 0 };
    if (t < end) P.z = CFG.clipLift * Math.min(1, t / CFG.clipLiftDur) + Math.max(0, pz - c.zmin);   // 不低于起飞后的抬升高度
    else {
      const u = Math.min(1, (t - end) / CFG.landDur);
      P.z = (CFG.clipLift + Math.max(0, c.pos[(c.n - 1) * 3 + 2] - c.zmin)) * (1 - u);
      P.done = u >= 1;
      P.landU = u;      // 落地进度（显示用）：页面据此把机体姿态插值回水平，否则片段最后一帧的抬头姿态会让腹部插进地面
    }
    return P;
  }

  function createGame(SUB, BrainClass, opts = {}) {
    const CFG = Object.assign({}, DEFAULTS, opts.cfg || {});
    const rand = rng32(opts.seed ?? 11);
    const brain = new BrainClass(SUB, (opts.seed ?? 11) * 7 + 1);
    const targetOf = new Int8Array(SUB.meta.n).fill(-1);
    TG.forEach((g, k) => SUB.groups[g].forEach(i => { targetOf[i] = k; }));
    const ema = new Float32Array(TG.length), counts = new Float32Array(TG.length);
    const chunkDt = CFG.chunkSteps * brain.dt / 1000;
    // v3 读出组（只在子回路里存在时启用）
    const TG2 = ["MN9_left", "MN9_right", "aDN1_left", "aDN1_right", "MDN_left", "MDN_right"].filter(g => SUB.groups[g] && SUB.groups[g].length);
    const has = g => !!(SUB.groups[g] && SUB.groups[g].length);
    const V3 = TG2.length === 6 && has("SUGAR_left") && has("JO_left") && has("LC16_left");
    // v5：蘑菇体 + 可塑性
    const V5 = !!SUB.mb_tag, PlastAPI = V5 ? (opts.Plasticity || root.FlyPlasticity || (typeof require === "function" ? require("./plasticity.js") : null)) : null;
    const MB = V5 ? (() => {
      const plast = PlastAPI.create(SUB, brain, { eta: CFG.plastEta, tauE: CFG.plastTauE, tauForget: CFG.plastForget }), n = SUB.meta.n, tag = SUB.mb_tag, sides = SUB.sides;
      const orn = []; for (let i = 0; i < n; i++) if (tag[i] === "ORN" && (sides[i] === "left" || sides[i] === "right")) orn.push(i);
      const ornIdx = Int32Array.from(orn), ornHz = new Float32Array(orn.length), slot = new Int32Array(n).fill(-1); orn.forEach((i, k) => { slot[i] = k; });
      const odorSlots = {}; for (const [kind, gl] of Object.entries(SUB.meta.odors)) { const L = [], R = []; for (const g of gl) for (const i of SUB.meta.glomeruli[g] || []) { if (slot[i] < 0) continue; (sides[i] === "left" ? L : R).push(slot[i]); } odorSlots[kind] = { L: Int32Array.from(L), R: Int32Array.from(R) }; }
      const dan = { PAM: [...SUB.groups.PAM_left, ...SUB.groups.PAM_right], PPL1: [...SUB.groups.PPL1_left, ...SUB.groups.PPL1_right] };
      // 隔室权重：每个 MBON 的多巴胺输入（≥3 突触的边）里来自 PAM / PPL1 的比例——只看连接组
      const mLocal = new Int32Array(n).fill(-1); plast.mbonIdx.forEach((i, m) => { mLocal[i] = m; });
      const frac = { PAM: new Float32Array(plast.mbonIdx.length), PPL1: new Float32Array(plast.mbonIdx.length) }, tot = new Float32Array(plast.mbonIdx.length), isIn = { PAM: new Set(dan.PAM), PPL1: new Set(dan.PPL1) };
      for (const d of plast.danIdx) for (let e = brain.indptr[d]; e < brain.indptr[d + 1]; e++) { const m = mLocal[brain.post[e]]; if (m < 0) continue; const c = Math.round(Math.abs(brain.w0[e]) / 0.275); if (c < 3) continue; tot[m] += c; for (const k of ["PAM", "PPL1"]) if (isIn[k].has(d)) frac[k][m] += c; }
      for (let m = 0; m < tot.length; m++) if (tot[m] > 0) { frac.PAM[m] /= tot[m]; frac.PPL1[m] /= tot[m]; }
      const kcLocal = new Int32Array(n).fill(-1); plast.kcIdx.forEach((i, k) => { kcLocal[i] = k; });
      return { plast, ornIdx, ornHz, odorSlots, dan, frac, mLocal, kcLocal, mbonCount: new Float32Array(plast.mbonIdx.length), mbonHz: new Float32Array(plast.mbonIdx.length), kcCount: new Float32Array(plast.kcIdx.length),
               kcProfile: {}, danHz: { PAM: 0, PPL1: 0 }, danCount: { PAM: 0, PPL1: 0 }, drive: { PAM: false, PPL1: false }, puff: { PAM: 0, PPL1: 0 }, conc: {}, valence: 0, kcActive: 0 };
    })() : null;
    const target2Of = new Int8Array(SUB.meta.n).fill(-1);
    TG2.forEach((g, k) => SUB.groups[g].forEach(i => { target2Of[i] = k; }));
    const ema2 = new Float32Array(TG2.length), counts2 = new Float32Array(TG2.length);

    const G = {
      CFG, brain, chunkDt,
      S: { x: 0, y: 0, h: 0, z: 0, phase: 0, jumpT: -1, cooldown: 0, jumpDir: 0, t: 0, hitFlash: 0, omega: 0, thirst: 0,
           state: "walk", groomT: 0, speed: 0, proboscis: 0 },
      score: { dodge: 0, hit: 0, jump: 0, launched: 0, eaten: 0, eaten_sugar: 0, eaten_bitter: 0, eaten_mixed: 0,
               eaten_water: 0, contacts_sugar: 0, contacts_bitter: 0, contacts_mixed: 0, contacts_water: 0,
               groom: 0, dust: 0, back_s: 0, feed_s: 0, groom_s: 0 },
      balls: [], loom: { L: 0, R: 0 },
      pellets: [], dust: [], V3, gust: { sugar: 0, bitter: 0 },
      mode: opts.mode || "auto", ballSpeed: opts.ballSpeed || 60, mapSign: 1,
      lesion: { LC4: false, LPLC2: false, GF: false, DNa: false, LC16: false, SUGAR: false, BITTER: false, JO: false, MN9: false, aDN1: false, MDN: false },
      pelletTimer: 1.0, dustTimer: 2.0, pelletCycle: 0,
      autoTimer: 0.6, nextId: 1,
      onSpike: null, onEvent: null,
      clips: null,
    };

    // 飞行片段：{turn, dt, n, root: [x,y,z,qw,qx,qy,qz]×n}（mm，起点在原点、初始水平速度朝 +x）
    G.setFlightClips = (clips) => {
      G.clips = clips.map(c => {
        const n = c.n_frames, pos = new Float32Array(n * 3), yaw = new Float32Array(n);
        let zmin = Infinity, prev = 0, acc = 0;
        for (let i = 0; i < n; i++) {
          const o = i * 7, [x, y, z, w, qx, qy, qz] = c.root.slice(o, o + 7);
          pos.set([x, y, z], i * 3); zmin = Math.min(zmin, z);
          let a = Math.atan2(2 * (w * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz));
          if (i === 0) prev = a;
          let da = a - prev; da -= 2 * Math.PI * Math.round(da / (2 * Math.PI)); acc += da; prev = a;
          yaw[i] = acc;                                                 // 相对起点的累计偏航
        }
        return { turn: c.turn, dt: c.dt, n, pos, yaw, zmin, name: c.name };
      });
    };

    // —— 用虚拟敲除筛选（报告 §14–24）选出来的真实神经元；只列在这个子回路里存在的 ——
    // full = 全脑筛选（糖 → MN9）的比值；sugar / water / groom = **在这个子回路里实测**的比值。
    // full / fullWater / fullAdn1 = **全脑**（138,639 神经元）的比值，由 `python dodge/measure_neurons_fullbrain.py` 重算；
    // 两侧都用同一口径：把该类型列出的全部 ID 一起切断传出突触、零参照中位数归一化、前 6 个实现。
    // 子回路实测值由 `SUB=subcircuit_v3 node dodge/measure_neurons.js` 生成（口径写在那个脚本里：
    // 颗粒钉在头前持续接触、3 个种子、取后 1.25 s 平均），结果存到 results/dodge/neuron_ratios_v3.json。
    // **2026-09-19 起页面用子回路 v3**（5,563 神经元，多了触感/温度/湿度三路输入）；
    // v2 的那一版留在 results/dodge/neuron_ratios.json 里备查，两版数值很接近
    //（例如 Roundup 糖 0.05 → 0.07、Phantom 水 2.06 → 1.94）。改口径要两边一起改。
    // 子回路只有 4,599 个神经元（全脑的 3%），与全脑不一致是意料之中，页面上必须两个数都显示。
    G.NEURONS = [
      { key: "Roundup", type: "CB0553", ids: ["720575940623211725", "720575940607272649"], game: 0.07, water: 0.09, full: 0.30, fullWater: 0.00,
        note: "糖 → MN9 最强的前运动神经元之一。全脑里两条通路都靠它（糖 0.30、水 0.00），子回路里更极端（0.07 / 0.09）。" },
      { key: "G2N-1", type: "CB0616", ids: ["720575940620874757", "720575940623718380"], game: 0.53, water: 0.89, full: 0.47, fullWater: 0.96,
        note: "论文与我们都判「伸喙必需」，真实光遗传实验也证实。只对糖有效（0.53），对水几乎无关（0.89）。" },
      { key: "Clavicle", type: "AN_GNG_30", ids: ["720575940655014049"], game: 0.93, water: 0.00, full: 0.58, fullWater: 0.02,
        note: "真实实验证实糖、水都必需。糖水反差在全脑（0.58 / 0.02）和子回路（0.93 / 0.00）里都成立，子回路里更极端。" },
      { key: "CB0277", type: "CB0277", ids: ["720575940626835146"], game: 0.72, water: 1.01, full: 0.41, fullWater: 0.98,
        note: "全脑穷举筛选里效应第二强；它同时驱动一个强烈抑制 MN9 的 GABA 神经元。只影响糖（0.72 / 1.01）。" },
      { key: "CB0051", type: "CB0051", ids: ["720575940632365905"], game: 0.87, water: 0.00, full: 0.97, fullWater: 0.49,
        note: "水味觉通路的「枢纽」（报告 §21.1）。全脑里糖 0.97 / 水 0.49，子回路里糖 0.87 / 水 0.00——水那一侧两边都关键。" },
      { key: "Zorro", type: "CB0192", ids: ["720575940629888530", "720575940611015122"], game: 1.04, water: 0.82, full: 0.81, fullWater: 0.47,
        note: "真实实验说必需，单个敲除（论文的和我们的）都判不出来（1.04 / 0.82）。全脑里它和 CB0883 一起敲才塌到 0.43。" },
      { key: "Phantom", type: "CB0062", ids: ["720575940616103218"], game: 0.93, water: 1.94, full: 0.92, fullWater: 3.02,
        note: "抑制性（GABA）。敲掉它水通路的 MN9 翻倍——全脑 3.02 倍、子回路 1.94 倍，方向和量级都对上了；糖通路因为本来就饱和，两边都看不出来（0.92 / 0.93）。" },
      { key: "Rattle", type: "CB0499", ids: ["720575940638103349"], game: 1.11, water: 1.00, full: 0.88, fullWater: 0.64,
        note: "真实实验说糖与水都必需，模型两条通路都判不出（1.11 / 1.00）——论文自己指出的失败点之一。" },
      { key: "CB0883", type: "CB0883", ids: ["720575940625102692"], game: 1.01, water: 1.00, full: 0.76, fullWater: 1.00,
        note: "全脑里是「枢纽」：单独敲 0.76 不算必需，配上 Clavicle / G2N-1 就把 MN9 打到 0.24。在这个子回路里单敲同样看不出来（1.01 / 1.00）——它依赖的旁路大半在裁剪时被切掉了。" },
      { key: "aBN1", type: "SAD093", ids: ["720575940630907434"], game: 1.00, water: 1.00, adn1: 0.00, full: 1.00, fullWater: 1.00, fullAdn1: 0.00,
        note: "触角通路的唯一瓶颈：对进食和喝水都没有影响（全脑与子回路都是 1.00），但敲掉它梳理指令 aDN1 直接归零（子回路基线 53.9 → 0 Hz，全脑 0.00），与 Hampel et al. 2015 的实验一致。" },
    ];
    G.NEURON_PAIRS = [
      { keys: ["Clavicle", "G2N-1"], game: 0.28, expect: 0.49,
        note: "子回路里的协同：各自敲 0.93 / 0.53，一起敲 0.28，明显低于独立相乘的 0.49。" },
      { keys: ["CB0883", "G2N-1"], game: 0.79, expect: 0.53,
        note: "全脑里这一对是强协同（0.25），子回路里反而是「亚可加」（一起敲 0.79 高于独立预期 0.53）——差别来自裁剪。" },
    ];
    {
      const pos = new Map(SUB.fids.map((f, i) => [String(f), i]));
      G.NEURONS.forEach(n => { n.idx = n.ids.map(String).map(i => pos.get(i)).filter(i => i !== undefined); });
      G.NEURONS = G.NEURONS.filter(n => n.idx.length);
      G.neuronLesion = {};
    }
    // 水味觉受体：报告 §19 用的 18 个右侧唇瓣水味觉 GRN 里，有 17 个在这个子回路中
    // （它们的注释 cell_type 也是 LB3，本来就在糖味觉组里；这里把它们单独取出来，水滴只刺激这 17 个）
    G.WATER_IDS = ["720575940612950568", "720575940631898285", "720575940606002609", "720575940612579053", "720575940622902535",
      "720575940616177458", "720575940660292225", "720575940622486922", "720575940613786774", "720575940629852866",
      "720575940625861168", "720575940613996959", "720575940617857694", "720575940644965399", "720575940625203504",
      "720575940630553415", "720575940635172191", "720575940634796536"];
    {
      const pos = new Map(SUB.fids.map((f, i) => [String(f), i]));
      G.waterIdx = G.WATER_IDS.map(f => pos.get(f)).filter(i => i !== undefined);
    }

    // —— 光遗传手指（v7）：点一下，给指定神经元 optoDur 秒的泊松驱动 ——
    // 真实成分：驱动的是这个子回路里**真实的** FlyWire 神经元，用的也是和感觉输入同一套泊松机制
    //（与论文 poi() 相同：被驱动神经元不应期置 0）。手写成分：强度、时长、以及"点哪个"由页面决定。
    G.opto = null;
    G.optoPulse = (idx, hz = CFG.optoHz, dur = CFG.optoDur, label = "") => {
      if (!idx || !idx.length) return null;
      G.opto = { idx: Array.from(idx), hz, t: dur, dur, label };
      brain.setOpto(G.opto.idx, hz);
      G.onEvent && G.onEvent("opto", G.opto);
      return G.opto;
    };
    G.optoStop = () => { if (G.opto) { brain.setOpto([], 0); G.opto = null; } };

    G.setNeuronLesion = (key, on) => {
      const rec = G.NEURONS.find(n => n.key === key);
      if (!rec) return;
      G.neuronLesion[key] = on;
      brain.setSilencedNeurons("N:" + key, rec.idx, on);
    };

    G.setLesion = (name, on) => {
      G.lesion[name] = on;
      if (["LC4", "LPLC2", "LC16", "SUGAR", "BITTER", "JO", "TOUCH", "THERMO", "HYGRO", "AUDIO", "OLFA", "OLFR", "ISN"].includes(name) && has(name + "_left")) {
        brain.setSilenced(name + "_left", on); brain.setSilenced(name + "_right", on);   // 输入：切断传出突触
      }                                                 // GF / DNa / MN9 / aDN1 / MDN：切除运动输出（readout 置 0）
    };

    // —— 果蝇“在说什么”（报告 §13 的游戏简化版）——
    // 词的触发量都是真实的：糖 / 苦 / JO 是当前注入这些神经元的频率（手写前端算出的），
    // 吃 / 梳理 / 后退 / 飞是**连接组读出神经元的平滑发放率**。句子模板是手写的。
    // 与 §13 的差别：那里是 121,706 个神经元 + 岭回归解码器，这里子回路只有 4,599 个神经元、
    // 也没有醋 / 霉味 / 温湿度那些通路，所以只能用游戏里真实存在的这几路输入，且用阈值而非回归。
    G.speech = () => {
      const o = G.readout(), w = [], S = G.S;
      if (G.gust && G.gust.sugar > 0) w.push("甜");
      if (G.gust && G.gust.bitter > 0) w.push("苦");
      if (G.gust && G.gust.water > 0) w.push("水");
      if (G.wind.joL + G.wind.joR > 2 * CFG.speechWind) w.push("风");
      if (G.dust.length) w.push("痒");
      if (Math.max(G.loom.L, G.loom.R) > CFG.loomMax * 0.25) w.push("逼近");
      const act = o.gf > CFG.gfThreshold ? "飞" : V3 && o.mdn > CFG.mdnThreshold ? "后退"
        : V3 && o.mn9 > CFG.feedThreshold ? "吃" : V3 && o.adn1 > CFG.groomThreshold ? "梳理" : null;
      const has = x => w.includes(x);
      let s = "";
      if (has("水")) s = S.thirst > 0.5 ? "是水，正渴着" : "是水";
      else if (S.thirst > 0.75 && !w.length) s = "有点渴";
      else if (has("甜") && has("苦")) s = "又甜又苦";
      else if (has("甜")) s = "尝到甜的";
      else if (has("苦")) s = "好苦";
      if (has("逼近")) s = (s ? s + "，" : "") + "有东西冲过来";
      if (has("风")) s = (s ? s + "，" : "") + "有风吹来";
      if (has("痒")) s = (s ? s + "，" : "") + "触角上有东西";
      const tail = { 飞: "我要飞走！", 吃: "我要吃。", 后退: "我得后退。", 梳理: "我来梳一下。" }[act];
      if (tail) s = (s ? s + "。" : "") + tail;
      else if (s) s += "。";
      return { words: w, action: act, sentence: s, hz: { sugar: G.gust ? G.gust.sugar : 0, bitter: G.gust ? G.gust.bitter : 0,
        joWind: Math.round((G.wind.joL + G.wind.joR) / 2), loom: Math.round(Math.max(G.loom.L, G.loom.R)),
        mn9: Math.round(o.mn9 || 0), adn1: Math.round(o.adn1 || 0), mdn: Math.round(o.mdn || 0), gf: Math.round(o.gf) } };
    };

    // —— v4：它此刻"在想什么" ——
    // 每一个词的触发量都是**实测的**：感觉词 = 此刻送进那一路感受器的频率；身体词 = 能量 / 水分；动作词 = 连接组读出神经元的平滑发放率。
    // 句子模板与阈值是手写的（和 G.speech 一样）。它不是语言模型，也不是果蝇真的会说话——是把正在发生的神经活动翻译成一句人话。
    // —— v5：多巴胺桥 + 可塑性 + 记忆读数 ——
    function mbStep(dt) {
      const S = G.S, eatingSugar = S.state === "feed" && G.onPellet && G.onPellet.type !== "water" && G.onPellet.type !== "bitter", eatingBitter = S.state === "feed" && G.onPellet && G.onPellet.type === "bitter";
      for (const k of ["PAM", "PPL1"]) MB.puff[k] = Math.max(0, MB.puff[k] - dt);
      const want = { PAM: MB.puff.PAM > 0 || (CFG.reinforce && eatingSugar), PPL1: MB.puff.PPL1 > 0 || (CFG.reinforce && (eatingBitter || (G.field && G.field.thermo > CFG.painThermo))) };
      for (const k of ["PAM", "PPL1"]) if (want[k] !== MB.drive[k]) { MB.drive[k] = want[k]; brain.setDrive(k, MB.dan[k], want[k] ? CFG.danRate : 0); G.onEvent && G.onEvent("dopamine", { cluster: k, on: want[k] }); }
      MB.plast.enabled = CFG.learning; MB.plast.step(dt * 1000);
      const a = dt / (0.2 + dt); let act = 0, vp = 0, va = 0;
      for (let m = 0; m < MB.mbonHz.length; m++) { MB.mbonHz[m] += a * (MB.mbonCount[m] / dt - MB.mbonHz[m]); vp += MB.frac.PPL1[m] * MB.mbonHz[m]; va += MB.frac.PAM[m] * MB.mbonHz[m]; }
      MB.mbonCount.fill(0);
      for (const k of ["PAM", "PPL1"]) { MB.danHz[k] += a * (MB.danCount[k] / dt / MB.dan[k].length - MB.danHz[k]); MB.danCount[k] = 0; } MB.danCount.other = 0;
      // 哪种气味此刻最浓 → 把这一段的 KC 活动记到它名下（只用来显示「这种气味的记忆」，不参与任何决定）
      let top = null, tc = 0.3; for (const [kind, c] of Object.entries(MB.conc)) { const m = Math.max(c.L, c.R); if (m > tc) { tc = m; top = kind; } }
      for (let q = 0; q < MB.kcCount.length; q++) if (MB.kcCount[q] > 0) act++;
      if (top) { const prof = MB.kcProfile[top] || (MB.kcProfile[top] = new Float32Array(MB.kcCount.length)); for (let q = 0; q < prof.length; q++) prof[q] += 0.02 * (MB.kcCount[q] / dt - prof[q]); }
      MB.kcCount.fill(0); MB.kcActive += a * (act - MB.kcActive); MB.top = top;
      const v = vp + va > 1 ? (vp - va) / (vp + va) : 0; MB.valence += (dt / (CFG.memoryTau + dt)) * (v - MB.valence); MB.mbonPPL1 = vp; MB.mbonPAM = va;
    }
    G.V5 = V5; G.MB = MB;
    G.puff = (cluster, seconds = 1) => { if (MB) MB.puff[cluster] = seconds; };                       // 手动喷多巴胺（页面按钮）
    // 某种气味的记忆：它的 KC 活动谱（上面在线记的）经过现在的 KC→MBON 权重，给奖赏隔室 / 惩罚隔室的 MBON 的输入还剩原来的多少（1 = 没变）
    G.memoryOf = kind => {
      if (!MB || !MB.kcProfile[kind]) return null; const P = MB.plast, prof = MB.kcProfile[kind], out = { PAM: [0, 0], PPL1: [0, 0] };
      P.forEachEdge((k, m, w0, r) => { const x = prof[k] * w0; if (x <= 0) return; for (const c of ["PAM", "PPL1"]) { out[c][0] += MB.frac[c][m] * x * r; out[c][1] += MB.frac[c][m] * x; } });
      return { PAM: out.PAM[1] > 0 ? out.PAM[0] / out.PAM[1] : 1, PPL1: out.PPL1[1] > 0 ? out.PPL1[0] / out.PPL1[1] : 1 };
    };
    G.forget = () => { if (MB) { MB.plast.reset(); MB.kcProfile = {}; } };
    G.legs = null; G.attachLegs = legs => { G.legs = legs; return legs; };   // 六条腿的身体（可选）
    G.mind = () => {
      const o = G.readout(), S = G.S, Sn = G.senses, B = G.body, felt = [], fThr = CFG.physiology ? CFG.lifeFeedThreshold : CFG.feedThreshold;
      const loom = Math.max(G.loom.L || 0, G.loom.R || 0), aud = Math.max(Sn.audioL, Sn.audioR), vin = Math.max(Sn.olfaL, Sn.olfaR), geo = Math.max(Sn.olfrL, Sn.olfrR);
      if (loom > CFG.loomMax * 0.25) felt.push(["视", "有东西冲过来", loom]);
      if (aud > 20) felt.push(["听", aud > 120 ? "好响的嗡嗡声" : "有嗡嗡声", aud]);
      if (vin > 20) felt.push(["嗅", vin > 120 ? "醋味很浓，附近有烂果子" : "闻到一点醋味", vin]);
      if (geo > 20) felt.push(["嗅", "一股霉味", geo]);
      if (MB) for (const kind of ["A", "B"]) { const c = MB.conc[kind]; if (!c) continue; const hz = Math.max(c.L, c.R) * CFG.olfRate; if (hz <= 20) continue;
        const mem = G.memoryOf(kind), tail = !mem ? "" : mem.PAM < 0.7 && mem.PPL1 < 0.7 ? "——这味道，有过好事也有过坏事" : mem.PAM < 0.7 ? "——这味道，上次有吃的" : mem.PPL1 < 0.7 ? "——这味道，上次很难受" : "";
        felt.push(["嗅", (kind === "A" ? "果香（气味 A）" : "焦味（气味 B）") + tail, hz]); }
      if (MB && MB.drive.PAM) felt.push(["多巴胺", "奖赏多巴胺（PAM）在放电", CFG.danRate]); if (MB && MB.drive.PPL1) felt.push(["多巴胺", "惩罚多巴胺（PPL1）在放电", CFG.danRate]);
      if (G.gust.sugar > 0) felt.push(["味", "甜的", G.gust.sugar]); if (G.gust.bitter > 0) felt.push(["味", "苦的", G.gust.bitter]); if (G.gust.water > 0) felt.push(["味", "是水", G.gust.water]);
      if (G.touch.L + G.touch.R > 0) felt.push(["触", "撞到墙了", Math.max(G.touch.L, G.touch.R)]);
      if (G.dust.length) felt.push(["触", "触角上有灰", CFG.joRate]);
      if (G.wind.joL + G.wind.joR > 2 * CFG.speechWind) felt.push(["触", "有风", (G.wind.joL + G.wind.joR) / 2]);
      if (G.field.thermo > 0.3) felt.push(["温", "这里好热", G.field.thermo * CFG.fieldRate]); if (G.field.hygro > 0.3) felt.push(["湿", "这里潮乎乎的", G.field.hygro * CFG.fieldRate]);
      const body = []; if (CFG.physiology) { if (B.energy < 0.3) body.push("饿了"); if (B.hydration < 0.3) body.push("渴了"); if (B.energy > 0.9 && B.hydration > 0.9) body.push("吃饱喝足"); }
      if (CFG.light < 0.3) body.push("天黑了，看不太清");
      const act = S.z > 0.01 ? "我在飞" : o.gf > CFG.gfThreshold ? "快飞！" : o.mdn > CFG.mdnThreshold ? "往后退" : (G.onPellet && o.mn9 > fThr) ? (G.onPellet.type === "water" ? "喝水" : "吃") : (o.adn1 > CFG.groomThreshold && G.dust.length) ? "梳一梳触角"
        : Math.abs(o.dnaL - o.dnaR) > 8 ? (o.dnaL > o.dnaR ? "往左拐" : "往右拐") : null;
      const parts = felt.map(f => f[1]).concat(body);
      return { felt, body, action: act, sentence: parts.join("，") + (act ? (parts.length ? "——" : "") + act : "") + (parts.length || act ? "。" : ""),
        hz: { loom: Math.round(loom), audio: Math.round(aud), vinegar: Math.round(vin), geosmin: Math.round(geo), sugar: Math.round(G.gust.sugar), bitter: Math.round(G.gust.bitter), water: Math.round(G.gust.water),
              touch: Math.round(Math.max(G.touch.L, G.touch.R)), thermo: Math.round(G.field.thermo * CFG.fieldRate), hygro: Math.round(G.field.hygro * CFG.fieldRate), isn: Math.round(Sn.isn),
              gf: Math.round(o.gf), dnaL: Math.round(o.dnaL), dnaR: Math.round(o.dnaR), mn9: Math.round(o.mn9 || 0), adn1: Math.round(o.adn1 || 0), mdn: Math.round(o.mdn || 0) } };
    };

    G.readout = () => {
      const r = k => (G.lesion.DNa && k < 4) || (G.lesion.GF && k >= 4) ? 0 : ema[k];
      const out = { dnaL: r(0) + r(2), dnaR: r(1) + r(3), gf: (r(4) + r(5)) / 2, raw: Array.from(ema) };
      if (V3) {
        out.mn9 = G.lesion.MN9 ? 0 : (ema2[0] + ema2[1]) / 2;
        out.adn1 = G.lesion.aDN1 ? 0 : Math.max(ema2[2], ema2[3]);
        out.mdnL = G.lesion.MDN ? 0 : ema2[4]; out.mdnR = G.lesion.MDN ? 0 : ema2[5];
        out.mdn = (out.mdnL + out.mdnR) / 2;
      }
      return out;
    };

    // —— 风：随机游走的风场（强度 0–1、方向），每步更新 ——
    G.fields = [];                    // 温度 / 湿度源；G.addField / G.clearFields
    G.sounds = []; G.odors = [];      // v4：声源与气味源
    G.senses = { audioL: 0, audioR: 0, olfaL: 0, olfaR: 0, olfrL: 0, olfrR: 0, isn: 0, gainSugar: 1, gainWater: 1 };
    G.body = { energy: 0.8, hydration: 0.8, age: 0, meals: 0, drinks: 0, startles: 0 };
    G.V4 = !!(SUB.groups && SUB.groups.AUDIO_left);
    G.addSound = (x, y, level = 1, dur = 0.8) => { const o = { x, y, level, t: 0, dur }; G.sounds.push(o); G.onEvent && G.onEvent("sound", o); return o; };
    G.addOdor = (x, y, kind = "vinegar", sigma = 28, strength = 1, life = 60) => { const o = { x, y, kind, sigma, strength, base: strength, life, t: 0 }; G.odors.push(o); G.onEvent && G.onEvent("odor", o); return o; };
    G.wallTheta = {};                 // 四面墙上一帧的张角，用来算 dθ/dt
    G.wind = { speed: CFG.windSpeed, dir: CFG.windDir, joL: 0, joR: 0 };
    function windStep(dt) {
      if (!CFG.wind) { G.wind.speed = 0; G.wind.joL = G.wind.joR = 0; return; }
      const k = dt / (CFG.windTau + dt);
      G.wind.speed += k * ((0.25 + 0.75 * rand()) - G.wind.speed) + (rand() - 0.5) * 0.08;
      G.wind.speed = Math.max(0, Math.min(1, G.wind.speed));
      G.wind.dir += (rand() - 0.5) * 0.9 * dt;
    }

    // 颗粒与灰尘
    G.addPellet = (x, y, type) => { const p = { id: G.nextId++, x, y, type, amount: 1, touched: false }; G.pellets.push(p); G.onEvent && G.onEvent("pellet", p); return p; };
    G.addPelletAhead = (type, ahead = CFG.pelletAhead, lateral = 0) => {
      const S = G.S; return G.addPellet(S.x + Math.cos(S.h) * ahead - Math.sin(S.h) * lateral, S.y + Math.sin(S.h) * ahead + Math.cos(S.h) * lateral, type);
    };
    G.addField = (type, x, y, sigma = 40, strength = 1) => {
      const f = { id: G.nextId++, type, x, y, sigma, strength };
      G.fields.push(f); G.onEvent && G.onEvent("field", f); return f;
    };
    G.clearFields = () => { for (const f of G.fields) G.onEvent && G.onEvent("removeField", f); G.fields.length = 0; };
    G.addDust = (side) => { const d = { id: G.nextId++, side }; G.dust.push(d); G.score.dust++; G.onEvent && G.onEvent("dust", d); return d; };

    // o.strike = true：“扑击”型威胁 —— 瞄准果蝇发射时的当前位置（不带提前量），到达该点后停住 o.hold 秒再消失
    //（v4 后退实验用；默认的滚球行为不变）
    G.launch = (fromX, fromY, o = {}) => {
      const S = G.S;
      const dx = S.x - fromX, dy = S.y - fromY, d = Math.hypot(dx, dy) || 1;
      if (d < 20) { fromX = S.x - dx / d * 20; fromY = S.y - dy / d * 20; }
      // 提前量瞄准：假设果蝇保持当前方向和速度，求 |P + V·t − B| = s·t 的最早正解，
      // 这样“毫无反应”的果蝇必被击中，躲开完全取决于大脑的反应
      const vx = o.strike ? 0 : Math.cos(S.h) * CFG.walkSpeed, vy = o.strike ? 0 : Math.sin(S.h) * CFG.walkSpeed;
      const px = S.x - fromX, py = S.y - fromY, s = G.ballSpeed;
      const qa = vx * vx + vy * vy - s * s, qb = 2 * (px * vx + py * vy), qc = px * px + py * py;
      const disc = qb * qb - 4 * qa * qc;
      let tHit = Math.hypot(px, py) / s;
      if (disc >= 0 && Math.abs(qa) > 1e-9) {                        // 取最早的正解；球比果蝇慢（qa > 0）时也成立
        const pos = [(-qb - Math.sqrt(disc)) / (2 * qa), (-qb + Math.sqrt(disc)) / (2 * qa)].filter(t => t > 0);
        if (pos.length) tHit = Math.min(...pos);
      }
      const ex = px + vx * tHit, ey = py + vy * tHit, e = Math.hypot(ex, ey) || 1;
      const b = { id: G.nextId++, x: fromX, y: fromY, vx: ex / e * s, vy: ey / e * s, tHit, prevTheta: null, minD: Infinity, done: false, age: 0, outcome: null };
      if (o.strike) { b.stopT = tHit; b.removeT = tHit + (o.hold ?? 0.3); }
      G.balls.push(b); G.score.launched++;
      G.onEvent && G.onEvent("launch", b);
      return b;
    };

    // 连接组视觉前端的接管口（报告 §28.19）。置 null 时走下面手写的那套。
    // 传入 {lc4L,lc4R,lplc2L,lplc2R,lc16L,lc16R,bearing}，单位 Hz，bearing 是眼内方位（弧度，+ 为左）。
    G.visionOverride = null;
    G.setVisionOverride = o => { G.visionOverride = o; };

    // 视觉前端（手写）：每个球在左右眼中的张角增长率 → LC4/LPLC2 频率
    function visualInput(dt) {
      const S = G.S;
      const ov = G.visionOverride;
      if (ov) {
        // 连接组前端接管：这些频率来自**真实像素**，不知道球在哪。
        // 不再乘光照增益 —— 光照已经体现在渲染出的像素里了（手写版才需要补这一项）。
        const m2 = CFG.loomMax;
        const c = v => Math.min(m2, Math.max(0, v || 0));
        G.loom = { L: c(Math.max(ov.lc4L, ov.lplc2L)), R: c(Math.max(ov.lc4R, ov.lplc2R)),
                   lc4L: c(ov.lc4L), lc4R: c(ov.lc4R), lplc2L: c(ov.lplc2L), lplc2R: c(ov.lplc2R),
                   lc16L: c(ov.lc16L), lc16R: c(ov.lc16R) };
        G.threatDir = ov.bearing == null ? null : S.h + ov.bearing;   // 眼内方位 → 世界方位
        brain.setRate("LC4_left", G.loom.lc4L); brain.setRate("LPLC2_left", G.loom.lplc2L);
        brain.setRate("LC4_right", G.loom.lc4R); brain.setRate("LPLC2_right", G.loom.lplc2R);
        if (V3) { brain.setRate("LC16_left", G.loom.lc16L); brain.setRate("LC16_right", G.loom.lc16R); }
        for (const b of G.balls) {                 // 仍要维护 prevTheta，切回手写时才不会跳变
          const rx = b.x - S.x, ry = b.y - S.y;
          const d = Math.max(Math.hypot(rx, ry), CFG.ballR + 0.01);
          b.prevTheta = 2 * Math.atan(CFG.ballR / d);
        }
        return;
      }
      let lc4L = 0, lc4R = 0, lpL = 0, lpR = 0, l16L = 0, l16R = 0, threat = null, threatDrive = 0;
      const ch = Math.cos(-S.h), sh = Math.sin(-S.h);
      for (const b of G.balls) {
        const rx = b.x - S.x, ry = b.y - S.y;
        const fx = ch * rx - sh * ry, fy = sh * rx + ch * ry;        // 果蝇坐标：x 前、y 左
        const d = Math.max(Math.hypot(fx, fy), CFG.ballR + 0.01);
        const theta = 2 * Math.atan(CFG.ballR / d);
        const dtheta = b.prevTheta === null ? 0 : (theta - b.prevTheta) / dt;
        b.prevTheta = theta;
        if (dtheta <= 0 || theta < 0.05) continue;                    // 只对“正在变大”的物体反应
        const bearing = Math.atan2(fy, fx) * 180 / Math.PI;          // 0 = 正前，+ = 左
        if (Math.abs(bearing) > 165) continue;                        // 正后方盲区
        let lc4, lp;
        if (CFG.encoding === "ache2019") {
          const thetaDeg = theta * 180 / Math.PI, velDeg = dtheta * 180 / Math.PI;
          lc4 = CFG.lc4Slope * velDeg;
          lp = CFG.lplc2Peak * Math.exp(-((thetaDeg - CFG.lplc2Mu) ** 2) / (2 * CFG.lplc2Sigma ** 2));
        } else {
          lc4 = lp = CFG.loomGain * dtheta;
        }
        const l16 = CFG.lc16Slope * dtheta * 180 / Math.PI;           // LC16：与 LC4 同样的角速度编码（手选）
        if (bearing > -15) { lc4L += lc4; lpL += lp; l16L += l16; }   // 左眼（含前方 ±15° 双眼重叠）
        if (bearing < 15) { lc4R += lc4; lpR += lp; l16R += l16; }
        if (lc4 + lp > threatDrive) { threatDrive = lc4 + lp; threat = Math.atan2(ry, rx); }  // 世界坐标方位
      }
      // 围栏也是一个视觉物体（2026-09-19 加）。
      // 在这之前，墙**根本没有接进任何感觉通路**——视觉前端只读球的世界坐标，
      // 边界只是 step() 末尾的一次几何钳位，于是果蝇会顶着围栏一直走。
      // 这里不给它加"避障规则"，而是把墙按同一套手写前端算成逼近物体：
      // 取最近的那面墙，视线方向上的张角 θ = 2·atan(wallSpan/2 ÷ 距离)，
      // 再走和球完全相同的 LC4/LPLC2 编码，让连接组自己决定转还是跳。
      // 依据：LC4/LPLC2 对**任何**逼近物体反应，不只对球（Ache 2019 / Klapoetke 2017）。
      // 与球的区别只有一点必须说明：墙是**静止**的，"逼近"来自果蝇自己在走——
      // 这正是报告 §28.19 里量过的"自体运动造成的假逼近"，那里是噪声，这里是信号。
      if (CFG.wallVision && CFG.courtW) {
        const hw = CFG.courtW / 2 - CFG.courtPad, hh = CFG.courtH / 2 - CFG.courtPad;
        // 四面墙各取最近点（在墙上、与果蝇最近的那个点）
        for (const [wx, wy] of [[hw, S.y], [-hw, S.y], [S.x, hh], [S.x, -hh]]) {
          const rx = wx - S.x, ry = wy - S.y;
          const d = Math.max(Math.hypot(rx, ry), 0.5);
          if (d > CFG.wallSee) continue;                              // 太远就看不出它在逼近
          const fx = ch * rx - sh * ry, fy = sh * rx + ch * ry;
          const bearing = Math.atan2(fy, fx) * 180 / Math.PI;
          if (Math.abs(bearing) > 100) continue;                      // 背后的墙不算
          const theta = 2 * Math.atan(CFG.wallSpan / 2 / d);
          const key = "w" + (wx === S.x ? (wy > 0 ? "T" : "B") : (wx > 0 ? "R" : "L"));
          const prev = G.wallTheta[key];
          G.wallTheta[key] = theta;
          if (prev === undefined) continue;
          const dtheta = (theta - prev) / dt;
          if (dtheta <= 0) continue;
          let lc4, lp;
          if (CFG.encoding === "ache2019") {
            const thetaDeg = theta * 180 / Math.PI, velDeg = dtheta * 180 / Math.PI;
            lc4 = CFG.lc4Slope * velDeg;
            lp = CFG.lplc2Peak * Math.exp(-((thetaDeg - CFG.lplc2Mu) ** 2) / (2 * CFG.lplc2Sigma ** 2));
          } else { lc4 = lp = CFG.loomGain * dtheta; }
          lc4 *= CFG.wallGain; lp *= CFG.wallGain;
          const l16 = CFG.lc16Slope * dtheta * 180 / Math.PI * CFG.wallGain;
          if (bearing > -15) { lc4L += lc4; lpL += lp; l16L += l16; }
          if (bearing < 15) { lc4R += lc4; lpR += lp; l16R += l16; }
          if (lc4 + lp > threatDrive) { threatDrive = lc4 + lp; threat = Math.atan2(ry, rx); }
        }
      }
      // 光照增益（手写）：暗处对比度低，逼近检测变弱
      const gain = CFG.lightFloor + (1 - CFG.lightFloor) * Math.max(0, Math.min(1, CFG.light));
      lc4L *= gain; lc4R *= gain; lpL *= gain; lpR *= gain; l16L *= gain; l16R *= gain;
      const m = CFG.loomMax;
      G.loom = { L: Math.min(m, Math.max(lc4L, lpL)), R: Math.min(m, Math.max(lc4R, lpR)),
                 lc4L: Math.min(m, lc4L), lc4R: Math.min(m, lc4R), lplc2L: Math.min(m, lpL), lplc2R: Math.min(m, lpR),
                 lc16L: Math.min(m, l16L), lc16R: Math.min(m, l16R) };
      G.threatDir = threat;
      brain.setRate("LC4_left", G.loom.lc4L); brain.setRate("LPLC2_left", G.loom.lplc2L);
      brain.setRate("LC4_right", G.loom.lc4R); brain.setRate("LPLC2_right", G.loom.lplc2R);
      if (V3) { brain.setRate("LC16_left", G.loom.lc16L); brain.setRate("LC16_right", G.loom.lc16R); }
    }

    // 味觉与触角（手写前端）：头部下方的颗粒 → 糖/苦味觉神经元；触角上的灰尘 → 该侧 JO
    function contactInput() {
      const S = G.S;
      let sugar = 0, bitter = 0, water = 0; G.onPellet = null;
      if (S.z <= 0.01) {
        const hx = S.x + Math.cos(S.h) * CFG.headOffset, hy = S.y + Math.sin(S.h) * CFG.headOffset;
        for (const p of G.pellets) {
          if (Math.hypot(p.x - hx, p.y - hy) < (p.r || CFG.pelletR) + 0.3) {
            G.onPellet = p;
            if (!p.touched) { p.touched = true; G.score["contacts_" + p.type] = (G.score["contacts_" + p.type] || 0) + 1; }
            if (p.type === "water") water = CFG.gustRate;
            else {
              if (p.type !== "bitter") sugar = CFG.gustRate;
              if (p.type !== "sugar") bitter = CFG.gustRate;
            }
            break;
          }
        }
      }
      // —— 触感（2026-09-19 加）：世界里的**物理接触**，不是我们写的判断 ——
      // 原则：我们只负责把物理量送到真实的感受器上，转不转、跳不跳由连接组自己决定。
      // 几何：两根触角在体轴 ±35°、前伸 antennaAhead mm；哪根触角越过围栏，哪侧就被压住。
      // **必须说明的近似**：JO（Johnston's organ）是触角的机械感觉器，真果蝇用它感知
      // 气流 / 重力 / 声音；真正的"碰到东西"走的是刚毛与腿部机械感觉，**那些神经元不在这个
      // 4,599 神经元的子回路里**（子回路是按 LC4/LPLC2/LC16/味觉/JO 这几路输入裁的）。
      // 所以这里是拿触角机械感觉近似触碰感觉，不是它的本职。要做对得重裁一版子回路。
      let touchL = 0, touchR = 0;
      if (CFG.touch && CFG.courtW && S.z <= 0.01) {
        const hw = CFG.courtW / 2 - CFG.courtPad, hh = CFG.courtH / 2 - CFG.courtPad;
        for (const [side, a] of [["L", 0.61], ["R", -0.61]]) {
          const ax = S.x + Math.cos(S.h + a) * CFG.antennaLen, ay = S.y + Math.sin(S.h + a) * CFG.antennaLen;
          const over = CFG.arenaR > 0 ? Math.hypot(ax, ay) - (CFG.arenaR - CFG.courtPad)      // 圆形场地：径向越界量
                                      : Math.max(Math.abs(ax) - hw, Math.abs(ay) - hh);   // > 0 = 这根触角压在围栏上
          if (over > 0) {
            const v = Math.min(1, over / CFG.antennaLen) * CFG.touchRate;
            if (side === "L") touchL = v; else touchR = v;
          }
        }
      }
      G.touch = { L: touchL, R: touchR };

      // —— 温度与湿度（2026-09-19 加）：世界里的**物理场**，同样不写任何判断逻辑 ——
      // 场地上可以放热源与水洼；果蝇所在位置的温度 / 湿度按距离衰减，直接换算成
      // THERMO / HYGRO 神经元的泊松频率。**热了要不要走开、湿了要不要靠近，全由连接组决定。**
      // 需要子回路 v3（v2 里没有这两组感受器，给了也没有落点——这一点在 §38.3 里实测过）。
      // 换算（Hz per 单位强度）是手选的：没有该模型下的温度/湿度定标数据。
      let thermo = 0, hygro = 0;
      if (has("THERMO_left") || has("HYGRO_left")) {
        for (const f of G.fields) {
          const d = Math.hypot(f.x - S.x, f.y - S.y);
          const g2 = Math.exp(-(d * d) / (2 * f.sigma * f.sigma));
          if (f.type === "heat") thermo += f.strength * g2;
          else if (f.type === "damp") hygro += f.strength * g2;
        }
      }
      G.field = { thermo, hygro };
      if (has("THERMO_left")) {
        const t = Math.min(CFG.fieldRate, thermo * CFG.fieldRate);
        brain.setRate("THERMO_left", t); brain.setRate("THERMO_right", t);
      }
      if (has("HYGRO_left")) {
        const h2 = Math.min(CFG.fieldRate, hygro * CFG.fieldRate);
        brain.setRate("HYGRO_left", h2); brain.setRate("HYGRO_right", h2);
      }
      // —— v4：听觉、嗅觉、内感受 + 身体状态对味觉感受器灵敏度的调制 ——
      if (G.V4) {
        const ear = a => [S.x + Math.cos(S.h + a) * CFG.antennaLen, S.y + Math.sin(S.h + a) * CFG.antennaLen];
        const [lx, ly] = ear(0.61), [rx, ry] = ear(-0.61);
        let aL = 0, aR = 0;
        for (const o of G.sounds) {
          const env = Math.sin(Math.PI * Math.min(1, o.t / o.dur));                  // 声音的包络：起 → 落
          const at = (x, y) => o.level * env / (1 + ((Math.hypot(o.x - x, o.y - y)) / CFG.soundRef) ** 2);
          const rel = Math.sin(Math.atan2(o.y - S.y, o.x - S.x) - S.h);              // + = 声源在左
          aL += at(lx, ly) * (1 + CFG.earBias * rel); aR += at(rx, ry) * (1 - CFG.earBias * rel);
        }
        let vL = 0, vR = 0, gL = 0, gR = 0;
        for (const o of G.odors) {
          const c = (x, y) => o.strength * Math.exp(-((o.x - x) ** 2 + (o.y - y) ** 2) / (2 * o.sigma * o.sigma));
          if (o.kind === "vinegar") { vL += c(lx, ly); vR += c(rx, ry); } else if (o.kind === "geosmin") { gL += c(lx, ly); gR += c(rx, ry); }
        }
        const cap = (v, m) => Math.min(m, Math.max(0, v) * m), Sn = G.senses;
        Sn.audioL = cap(aL, CFG.audioRate); Sn.audioR = cap(aR, CFG.audioRate);
        Sn.olfaL = cap(vL, CFG.olfRate); Sn.olfaR = cap(vR, CFG.olfRate); Sn.olfrL = cap(gL, CFG.olfRate); Sn.olfrR = cap(gR, CFG.olfRate);
        brain.setRate("AUDIO_left", Sn.audioL); brain.setRate("AUDIO_right", Sn.audioR);
        if (!MB) { brain.setRate("OLFA_left", Sn.olfaL); brain.setRate("OLFA_right", Sn.olfaR); brain.setRate("OLFR_left", Sn.olfrL); brain.setRate("OLFR_right", Sn.olfrR); }
        else {                       // v5：每种气味驱动它自己那组嗅小球；一个 ORN 同时被几种气味驱动时取最大
          MB.ornHz.fill(0); const lesion = G.lesion.OLFA || G.lesion.OLFR; MB.conc = {};
          for (const o of G.odors) {
            const sl = MB.odorSlots[o.kind]; if (!sl) continue;
            const c = (x, y) => o.strength * Math.exp(-((o.x - x) ** 2 + (o.y - y) ** 2) / (2 * o.sigma * o.sigma)), cL = c(lx, ly), cR = c(rx, ry), hL = cap(cL, CFG.olfRate), hR = cap(cR, CFG.olfRate);
            for (const q of sl.L) if (hL > MB.ornHz[q]) MB.ornHz[q] = hL; for (const q of sl.R) if (hR > MB.ornHz[q]) MB.ornHz[q] = hR;
            const k = MB.conc[o.kind] || (MB.conc[o.kind] = { L: 0, R: 0 }); k.L = Math.max(k.L, Math.min(1, cL)); k.R = Math.max(k.R, Math.min(1, cR));
          }
          if (lesion) MB.ornHz.fill(0);
          brain.setRatesArray(MB.ornIdx, MB.ornHz);
        }
        // 身体状态 → 感受器灵敏度（不是决策）：缺什么，对什么更敏感
        if (CFG.physiology) {
          const gain = need => CFG.gainMin + (CFG.gainMax - CFG.gainMin) * need;   // need ∈ [0,1]
          Sn.gainSugar = gain(1 - G.body.energy); Sn.gainWater = gain(1 - G.body.hydration);
          sugar = Math.min(CFG.gustRate * CFG.gainMax, sugar * Sn.gainSugar); water = Math.min(CFG.gustRate * CFG.gainMax, water * Sn.gainWater);
        }
        // 内感受神经元：饥饿 ↑、口渴 ↓（文献的方向）。默认关，原因见 DEFAULTS 里的注释
        Sn.isn = CFG.isnDrive ? CFG.isnRate * Math.max(0, Math.min(1, 0.5 + (1 - G.body.energy) * 0.5 - (1 - G.body.hydration) * 0.5)) : 0;
        brain.setRate("ISN_left", Sn.isn); brain.setRate("ISN_right", Sn.isn);
      }
      G.gust = { sugar, bitter, water };
      brain.setRate("SUGAR_left", sugar); brain.setRate("SUGAR_right", sugar);
      brain.setRate("BITTER_left", bitter); brain.setRate("BITTER_right", bitter);
      if (G.waterIdx.length) brain.setRateNeurons(G.waterIdx, water);   // 水：只刺激那 17 个水味觉受体（糖 = 全部 122 个 LB3）
      const dl = G.dust.some(d => d.side === "left"), dr = G.dust.some(d => d.side === "right");
      // 风吹在触角上：风来自 windDir 方向，两根触角相对体轴 ±35°，取迎风分量（手写几何）
      let wL = 0, wR = 0;
      if (CFG.wind && G.wind.speed > 0) {
        const drive = CFG.windJO * G.wind.speed;
        // 触角对任何方向的气流偏折都有反应（基础分量），迎风更强（方向性分量）——形式手写
        const rel = a => 0.35 + 0.65 * Math.max(0, Math.cos(G.wind.dir + Math.PI - (S.h + a)));
        wL = drive * rel(0.61); wR = drive * rel(-0.61);
      }
      G.wind.joL = wL; G.wind.joR = wR;
      // 触感送到哪里：子回路 v3 有**头部刚毛**（TOUCH，真正的触觉感受器）就送那里；
      // 只有 v2 的话退回触角 JO —— 但 JO 在 v2 里只通到梳理指令，实测对绕开围栏毫无作用
      // （贴墙 85.6% → 85.6%），这正是"没有通路就没有行为"。
      const hasTouch = has("TOUCH_left");
      G.joInput = { L: Math.min(CFG.joRate, (dl ? CFG.joRate : 0) + wL + (hasTouch ? 0 : touchL)),
                    R: Math.min(CFG.joRate, (dr ? CFG.joRate : 0) + wR + (hasTouch ? 0 : touchR)) };
      if (hasTouch) { brain.setRate("TOUCH_left", touchL); brain.setRate("TOUCH_right", touchR); }
      brain.setRate("JO_left", G.joInput.L); brain.setRate("JO_right", G.joInput.R);
    }

    G.step = () => {
      const S = G.S, dt = chunkDt;
      if (G.opto) { G.opto.t -= dt; if (G.opto.t <= 0) G.optoStop(); }     // 光遗传脉冲到时自动关掉
      counts.fill(0);
      counts2.fill(0);
      brain.run(CFG.chunkSteps, (i, s) => {
        const k = targetOf[i]; if (k >= 0) counts[k]++;
        const k2 = target2Of[i]; if (k2 >= 0) counts2[k2]++;
        G.onSpike && G.onSpike(i);
        if (MB) { MB.plast.spike(i); const m = MB.mLocal[i]; if (m >= 0) MB.mbonCount[m]++; else { const q = MB.kcLocal[i]; if (q >= 0) MB.kcCount[q]++; else if (SUB.mb_tag[i] === "DAN") MB.danCount[SUB.types[i].startsWith("PAM") ? "PAM" : SUB.types[i].startsWith("PPL1") ? "PPL1" : "other"]++; } }
      });
      if (MB) mbStep(dt);
      for (let k = 0; k < TG2.length; k++) ema2[k] += (dt / (CFG.ema2Tau + dt)) * (counts2[k] / dt / SUB.groups[TG2[k]].length - ema2[k]);
      for (let k = 0; k < TG.length; k++) {
        const tau = k >= 4 ? CFG.gfTau : CFG.emaTau;
        ema[k] += (dt / (tau + dt)) * (counts[k] / dt / SUB.groups[TG[k]].length - ema[k]);
      }
      const out = G.readout();
      windStep(dt);
      S.thirst = Math.max(0, Math.min(1, S.thirst + CFG.thirstRise * dt
        - (S.state === "feed" && G.onPellet && G.onPellet.type === "water" ? CFG.thirstDrop : 0) * dt));
      S.t += dt;

      // 身体（手写映射）
      let odorTurn = 0;
      if (CFG.odorNav) {
        const lure = G.pellets.filter(p => !p.touched);
        const conc = (ax, ay) => lure.reduce((s, p) => s + Math.exp(-((p.x - ax) ** 2 + (p.y - ay) ** 2) / (2 * CFG.odorSigma ** 2)), 0);
        const fx = S.x + Math.cos(S.h) * CFG.antennaAhead, fy = S.y + Math.sin(S.h) * CFG.antennaAhead;
        const ox = -Math.sin(S.h) * CFG.antennaSep / 2, oy = Math.cos(S.h) * CFG.antennaSep / 2;   // 指向果蝇左侧
        const cL = conc(fx + ox, fy + oy), cR = conc(fx - ox, fy - oy);
        G.odor = { L: cL, R: cR };
        if (Math.max(cL, cR) > CFG.odorMin) odorTurn = Math.sign(cL - cR) * CFG.odorTurn;
      } else G.odor = null;
      if (MB && CFG.memoryNav) {                                   // 手写的桥，默认关
        // 第二版。第一版用 MBON 此刻的发放算「价」：MBON 只在气味很浓的羽流核心才放电，离远了价恒为 0，二选一没有任何效果（results/learn/game_learning_bridge_v1.json）。
        // 现在直接读突触里的记忆：价 = 这种气味在奖赏隔室被压掉的比例 − 在惩罚隔室被压掉的比例（G.memoryOf，每 0.5 s 重算一次），只要闻得到（浓度 > 0.02）就起作用。
        MB.navT = (MB.navT || 0) - dt; if (MB.navT <= 0) { MB.navT = 0.5; MB.navV = {}; for (const kind of Object.keys(MB.conc)) { const m = G.memoryOf(kind); MB.navV[kind] = m ? (1 - m.PAM) - (1 - m.PPL1) : 0; } }
        for (const [kind, c] of Object.entries(MB.conc)) { const v = (MB.navV || {})[kind] || 0; if (v && Math.max(c.L, c.R) > 0.02 && Math.abs(c.L - c.R) > 1e-5) odorTurn += Math.sign(c.L - c.R) * v * CFG.memoryTurn; }
      }
      const omega = Math.max(-CFG.turnMax, Math.min(CFG.turnMax, G.mapSign * CFG.turnGain * (out.dnaL - out.dnaR) + odorTurn)) * Math.PI / 180;
      S.cooldown = Math.max(0, S.cooldown - dt);
      if (S.jumpT < 0 && S.cooldown === 0 && out.gf > CFG.gfThreshold) {
        S.jumpT = 0; G.score.jump++;
        // flyaway / clip：背离当前最强 looming 刺激；没有明确威胁时沿当前朝向
        S.jumpDir = CFG.takeoff !== "hop" && G.threatDir !== null ? G.threatDir + Math.PI : S.h;
        if (CFG.takeoff === "clip" && G.clips) {
          // 威胁相对朝向在左（+）→ 右转轨迹；找不到威胁时随机
          const rel = G.threatDir === null ? (rand() - 0.5) : Math.sin(G.threatDir - S.h);
          const want = rel > 0 ? "right" : "left";
          S.clip = G.clips.find(c => c.turn === want) || G.clips[0];
          S.clipOrigin = [S.x, S.y]; S.clipFrame = 0;
        }
        G.onEvent && G.onEvent("jump");
      }
      if (S.jumpT >= 0 && CFG.takeoff === "clip" && S.clip) {
        S.jumpT += dt;
        const c = S.clip, P = clipPose(c, CFG, S.clipOrigin, S.jumpDir, S.jumpT);
        S.clipFrame = P.frame; S.x = P.x; S.y = P.y; S.z = P.z;
        if (!P.landing) S.flyYaw = S.jumpDir + c.yaw[P.frame];
        else if (P.done) { S.jumpT = -1; S.z = 0; S.h = S.jumpDir + c.yaw[c.n - 1]; S.cooldown = CFG.jumpCooldown; S.clip = null; }
        S.omega = 0;
      } else if (S.jumpT >= 0 && CFG.takeoff === "flyaway") {
        S.jumpT += dt;
        const total = CFG.flyClimb + CFG.flyDur + CFG.flyClimb;
        const t = S.jumpT;
        // 爬升 → 平飞 → 下降落地
        S.z = t < CFG.flyClimb ? CFG.flyHeight * t / CFG.flyClimb
          : t < CFG.flyClimb + CFG.flyDur ? CFG.flyHeight
          : Math.max(0, CFG.flyHeight * (total - t) / CFG.flyClimb);
        S.x += Math.cos(S.jumpDir) * CFG.flySpeed * dt;
        S.y += Math.sin(S.jumpDir) * CFG.flySpeed * dt;
        S.omega = 0;
        if (t >= total) { S.jumpT = -1; S.z = 0; S.h = S.jumpDir; S.cooldown = CFG.jumpCooldown; }
      } else if (S.jumpT >= 0) {
        S.jumpT += dt;
        const u = Math.min(1, S.jumpT / CFG.jumpDur);
        S.x += Math.cos(S.jumpDir) * CFG.jumpDist / CFG.jumpDur * dt;
        S.y += Math.sin(S.jumpDir) * CFG.jumpDist / CFG.jumpDur * dt;
        S.z = 4 * CFG.jumpHeight * u * (1 - u);
        S.omega = 0;
        if (u >= 1) { S.jumpT = -1; S.z = 0; S.cooldown = CFG.jumpCooldown; }
      } else {
        // 地面行为优先级（手写）：后退 > 进食 > 梳理 > 行走
        let state = "walk";
        if (V3) {
          if (out.mdn > CFG.mdnThreshold) state = "back";
          else if (G.onPellet && out.mn9 > (G.onPellet.type === "water" && !CFG.physiology
                   ? CFG.feedThreshold * Math.max(CFG.waterThreshRatio, 1 - S.thirst) : (CFG.physiology ? CFG.lifeFeedThreshold : CFG.feedThreshold))) state = "feed";
          else if (S.groomT > 0 || (out.adn1 > CFG.groomThreshold && G.dust.length)) state = "groom";
        }
        if (state !== S.state) { G.onEvent && G.onEvent("state", { from: S.state, to: state }); if (state === "groom" && S.groomT <= 0) { S.groomT = CFG.groomDur; G.score.groom++; } }
        S.state = state;
        const vigor = CFG.physiology ? 0.45 + 0.55 * G.body.energy : 1;      // 能量低了走得慢（身体，不是决策）
        const speed = state === "walk" ? CFG.walkSpeed * vigor : state === "back" ? -CFG.backSpeed * vigor : 0;
        if (G.legs) {
          // 六条腿的身体（dodge/legs.js，默认不装）：上面算出的 speed / omega 只是**指令**，身体实际怎么动由支撑腿的运动学解出来。
          // 截掉一条腿、按住一条腿之后，同样的指令走出来的路就不一样了。
          const moving = state === "walk" || state === "back", d = G.legs.step(dt, { v: moving ? speed : 0, omega: moving ? omega : 0 });
          const c = Math.cos(S.h), sn = Math.sin(S.h); S.x += c * d.dx - sn * d.dy; S.y += sn * d.dx + c * d.dy; S.h += d.dth;
          S.speed = dt > 0 ? d.dx / dt : 0; S.omega = dt > 0 ? d.dth / dt : 0; S.cmd = { v: moving ? speed : 0, omega: moving ? omega : 0 };
        } else {
        S.speed = speed;
        if (state === "walk" || state === "back") { S.h += omega * dt; S.omega = omega; } else S.omega = 0;
        S.x += Math.cos(S.h) * speed * dt;
        S.y += Math.sin(S.h) * speed * dt;
        }
        S.phase += speed * dt;                                         // 以 mm 计的步态进度（后退时倒放）
        if (state === "back") G.score.back_s += dt;
        if (state === "feed") G.score.feed_s += dt;                    // 伸喙进食的累计秒数（比"吃完几颗"灵敏：水的驱动弱，常常够不到吃完一颗）
        if (state === "groom") G.score.groom_s += dt;
        S.proboscis += ((state === "feed" ? 1 : 0) - S.proboscis) * Math.min(1, dt / 0.06);   // 伸喙动画进度
        if (state === "feed" && G.onPellet) {
          const p = G.onPellet; p.amount -= CFG.eatRate * dt;
          if (p.amount <= 0) {
            G.pellets.splice(G.pellets.indexOf(p), 1); G.score.eaten++; G.score["eaten_" + p.type] = (G.score["eaten_" + p.type] || 0) + 1;
            G.onEvent && G.onEvent("eaten", p); G.onPellet = null;
          }
        }
        if (S.groomT > 0) {
          S.groomT -= dt;
          if (S.groomT <= 0) { S.groomT = 0; const n = G.dust.length; G.dust = []; if (n) G.onEvent && G.onEvent("groomed", n); }
        }
      }
      // 风的推力（手写物理）：地面上受阻力小幅偏移，空中更明显
      if (CFG.wind && G.wind.speed > 0) {
        const push = (S.jumpT >= 0 ? CFG.windFlyPush : CFG.windPush) * G.wind.speed * dt;
        S.x += Math.cos(G.wind.dir) * push; S.y += Math.sin(G.wind.dir) * push;
      }
      // 关在场内：走、飞、被风吹，最后统一夹一次。
      // 撞到边界就停在边上（不反弹）—— 反弹要改朝向，会污染"哪侧 DNa 活跃
      // 就往哪侧转"的对照，那是这个游戏要测的东西。
      if (CFG.courtW) {
        const hw = CFG.courtW / 2 - CFG.courtPad, hh = CFG.courtH / 2 - CFG.courtPad;
        let cx = Math.max(-hw, Math.min(hw, S.x)), cy = Math.max(-hh, Math.min(hh, S.y));
        if (CFG.arenaR > 0) { const rr = Math.hypot(S.x, S.y), lim = CFG.arenaR - CFG.courtPad; if (rr > lim) { cx = S.x * lim / rr; cy = S.y * lim / rr; } else { cx = S.x; cy = S.y; } }
        if (cx !== S.x || cy !== S.y) { S.x = cx; S.y = cy; S.wall = (S.wall || 0) + dt; }
        else S.wall = 0;
      }
      if (S.jumpT >= 0) { S.state = "fly"; S.proboscis = 0; }

      // 球与判定
      for (const b of G.balls) {
        if (b.stopT === undefined || b.age < b.stopT) { b.x += b.vx * dt; b.y += b.vy * dt; }
        b.age += dt;
        if (CFG.courtW && !b.done &&
            (Math.abs(b.x) > CFG.courtW / 2 + 20 || Math.abs(b.y) > CFG.courtH / 2 + 20)) {
          b.done = true; b.outcome = "out";        // 出界作废，不计入躲开/击中
        }
        const d = Math.hypot(b.x - S.x, b.y - S.y);
        if (!b.done && d < CFG.ballR + CFG.flyR && S.z < CFG.ballR * 1.6) {
          b.done = true; b.outcome = "hit"; G.score.hit++; S.hitFlash = 0.5; G.onEvent && G.onEvent("hit", b);
        }
        if (!b.done && d > b.minD + 1 && b.minD < 30) {                // 逼近过又远离且没打中 = 躲开
          b.done = true; b.outcome = "dodge"; G.score.dodge++; G.onEvent && G.onEvent("dodge", b);
        }
        b.minD = Math.min(b.minD, d);
      }
      for (let i = G.balls.length - 1; i >= 0; i--) {
        if (G.balls[i].age > (G.balls[i].removeT ?? CFG.ballLife)) { G.onEvent && G.onEvent("remove", G.balls[i]); G.balls.splice(i, 1); }
      }
      visualInput(dt);
      if (V3) {
        contactInput();
        if (CFG.autoPellets) {
          G.pelletTimer -= dt;
          if (G.pelletTimer <= 0) {
            G.pelletTimer = CFG.pelletEvery;
            const types = CFG.pelletTypes, type = types[G.pelletCycle++ % types.length];
            if (CFG.odorNav) { const a = rand() * 2 * Math.PI; G.addPellet(S.x + Math.cos(a) * CFG.pelletAround, S.y + Math.sin(a) * CFG.pelletAround, type); }
            else G.addPelletAhead(type);
          }
        }
        if (CFG.autoDust) {
          G.dustTimer -= dt;
          if (G.dustTimer <= 0) { G.dustTimer = CFG.dustEvery; G.addDust(rand() < 0.5 ? "left" : "right"); }
        }
        // 走远的颗粒回收
        if (!CFG.life) G.pellets = G.pellets.filter(p => Math.hypot(p.x - S.x, p.y - S.y) < 80 || (G.onEvent && G.onEvent("removePellet", p), false));   // 自主生活时食物散在整个场地上，不回收
        else if (G.pellets.length > 14) { const p = G.pellets.shift(); G.onEvent && G.onEvent("removePellet", p); }
      }

      if (G.mode === "auto") {
        G.autoTimer -= dt;
        if (G.autoTimer <= 0) {
          G.autoTimer = CFG.autoEvery[0] + rand() * (CFG.autoEvery[1] - CFG.autoEvery[0]);
          const a = S.h + (rand() * 2 - 1) * Math.PI * 0.8;           // 大多从前半视野来
          G.launch(S.x + Math.cos(a) * CFG.autoDist, S.y + Math.sin(a) * CFG.autoDist);
        }
      }
      // —— v4：声音 / 气味随时间消散；身体状态；自主生活的世界调度 ——
      for (const o of G.sounds) o.t += dt;
      G.sounds = G.sounds.filter(o => o.t < o.dur || (G.onEvent && G.onEvent("removeSound", o), false));
      for (const o of G.odors) { o.t += dt; if (o.pellet && !G.pellets.includes(o.pellet)) o.t = Math.max(o.t, o.life - 3); o.strength = o.base * Math.min(1, Math.max(0, (o.life - o.t) / 3)); }
      for (const o of G.odors) if (o.field && !G.fields.includes(o.field)) o.t = Math.max(o.t, o.life - 3), o.life = Math.min(o.life, o.t + 3);
      G.odors = G.odors.filter(o => o.t < o.life || (G.onEvent && G.onEvent("removeOdor", o), false));
      if (CFG.physiology) {
        const B = G.body; B.age += dt;
        const eating = S.state === "feed" && G.onPellet;
        B.energy = Math.max(0, Math.min(1, B.energy - (S.z > 0.01 ? CFG.energyFly : CFG.energyDrop) * dt + (eating && G.onPellet.type !== "water" && G.onPellet.type !== "bitter" ? CFG.energyEat * dt : 0)));
        B.hydration = Math.max(0, Math.min(1, B.hydration - CFG.hydraDrop * dt + (eating && G.onPellet.type === "water" ? CFG.hydraDrink * dt : 0)));
      }
      if (CFG.life) lifeStep(dt);
      S.hitFlash = Math.max(0, S.hitFlash - dt);
    };

    // 自主生活：世界自己运转。**这里只造世界，不碰果蝇**——每一样东西都只通过上面的感觉输入进到脑子里。
    const LT = { food: 3, water: 6, sound: 12, heat: 25, ball: 15 };
    function lifeStep(dt) {
      const S = G.S, hw = (CFG.courtW || 200) / 2 - 12, hh = (CFG.courtH || 140) / 2 - 12, OPEN = !CFG.courtW;
      // courtW = 0 → **没有墙的开放世界**：东西出现在它周围，离远了就消失（页面的生活模式用这个）。
      // 为什么不要墙：只靠触感它避不开墙——矩形场地卡死在墙角（两根触角同时压墙，转向差为 0），圆形场地也有 93–97% 的时间贴在墙上（实测）。
      // 这颗脑子里没有腹神经索的腿部反射；那条局限记在报告里，不在这里用一条"卡住就掉头"的规则掩盖。
      if (OPEN) { const far = o => Math.hypot(o.x - S.x, o.y - S.y) > CFG.lifeCull;
        for (const p of G.pellets.filter(far)) { G.pellets.splice(G.pellets.indexOf(p), 1); G.onEvent && G.onEvent("removePellet", p); }
        for (const f of G.fields.filter(far)) { G.fields.splice(G.fields.indexOf(f), 1); G.onEvent && G.onEvent("removeField", f); } }
      const between = ([a, b]) => a + rand() * (b - a);
      const inside = (x, y) => { if (!(CFG.arenaR > 0)) return [x, y]; const rr = Math.hypot(x, y), lim = CFG.arenaR - 12; return rr > lim ? [x * lim / rr, y * lim / rr] : [x, y]; };
      const spot = () => { if (OPEN) { const a = rand() * 2 * Math.PI, d = 35 + rand() * 75; return [S.x + Math.cos(a) * d, S.y + Math.sin(a) * d]; } if (CFG.arenaR > 0) { const a = rand() * 2 * Math.PI, r0 = Math.sqrt(rand()) * (CFG.arenaR - 12); return [Math.cos(a) * r0, Math.sin(a) * r0]; } return [(rand() * 2 - 1) * hw, (rand() * 2 - 1) * hh]; };
      // 吃的喝的七成放在它附近（20–50 mm，偏前方），三成随机。第一版全场均匀撒：嗅觉不通到转向、它又贴着墙走，10 分钟平均只碰到 0.3 次糖，一直在挨饿。
      // 这是**世界**的设计（球场模式里糖粒也是出现在它前方），不是给果蝇写的规则。
      const near = () => { if (rand() > CFG.lifeNearFrac) return spot(); const a = S.h + (rand() * 2 - 1) * 1.2, d = 20 + rand() * 30;
        if (OPEN) return [S.x + Math.cos(a) * d, S.y + Math.sin(a) * d];
        return inside(Math.max(-hw, Math.min(hw, S.x + Math.cos(a) * d)), Math.max(-hh, Math.min(hh, S.y + Math.sin(a) * d))); };
      // 昼夜：光照按正弦变化（0.15–1）。只是视觉前端的光照系数，和页面上的光照滑块同一个量
      G.clock = ((G.clock || 0) + dt) % CFG.dayLength; CFG.light = 0.575 + 0.425 * Math.cos(2 * Math.PI * G.clock / CFG.dayLength);
      if ((LT.food -= dt) <= 0) { LT.food = between(CFG.lifeFood); const [x, y] = near(), bad = rand() < 0.2;
        // 食物是**一块**烂果子（半径 lifeFoodR），不是 2 mm 的糖粒：嗅觉在这个模型里不通到转向，果蝇只能靠撞，2 mm 的目标 10 分钟也撞不到一次
        const p = G.addPellet(x, y, bad ? "bitter" : "sugar"); p.r = CFG.lifeFoodR; p.amount = CFG.lifeFoodAmount;
        const od = G.addOdor(x, y, bad ? "geosmin" : "vinegar", 26, 1, 90); od.pellet = p;      // 烂果子有醋味，发霉的有土臭素味
        if (MB && !bad) G.addOdor(x, y, "A", 26, 1, 90).pellet = p; }                           // v5：好果子另带一种可学的气味 A（醋味只占 1 个嗅小球，凯尼恩细胞几乎不响应，学不了）
      if ((LT.water -= dt) <= 0) { LT.water = between(CFG.lifeWater); const [x, y] = near(); const p = G.addPellet(x, y, "water"); p.r = CFG.lifeFoodR; p.amount = CFG.lifeFoodAmount; if (G.fields.length < 4) G.addField("damp", x, y, 22, 0.8); }
      if ((LT.sound -= dt) <= 0) { LT.sound = between(CFG.lifeSound); const a = rand() * 2 * Math.PI, d = 25 + rand() * 70; G.addSound(S.x + Math.cos(a) * d, S.y + Math.sin(a) * d, 0.6 + rand() * 0.9, 0.6 + rand() * 0.8); }
      if ((LT.heat -= dt) <= 0) { LT.heat = between(CFG.lifeHeat); if (G.fields.filter(f => f.type === "heat").length < 2) { const [x, y] = spot(); const f = G.addField("heat", x, y, 30, 1); if (MB) { const o = G.addOdor(x, y, "B", 30, 1, 1e9); o.field = f; } /* v5：热源带气味 B（"焦味"） */ } else { const f = G.fields.find(f2 => f2.type === "heat"); G.fields.splice(G.fields.indexOf(f), 1); G.onEvent && G.onEvent("removeField", f); } }
      if ((LT.ball -= dt) <= 0) { LT.ball = between(CFG.lifeBall); const a = S.h + (rand() * 2 - 1) * Math.PI * 0.8; G.launch(S.x + Math.cos(a) * CFG.autoDist, S.y + Math.sin(a) * CFG.autoDist); }
    }

    // —— 论文式扰动（Shiu 2024 补充表 1D / 11B–F）的对外接口 ——
    // 页面把它们做成滑块和按钮，玩家能直接看到"接线和参数到底重不重要"。
    // 注意：这些是**定性演示**，不是复现论文的定量结果（论文在全脑上跑，这里是 4,599 个神经元的子回路；
    // 而且打乱方式论文没给，见 brain.js 里 setShuffle 的说明）。
    G.PERTURB = { weightScale: 1, inhibScale: 1, shuffle: false, glutExc: false };
    G.setPerturb = (k, v) => {
      if (!(k in G.PERTURB)) return;
      G.PERTURB[k] = v;
      if (k === "weightScale") brain.setWeightScale(v);
      else if (k === "inhibScale") brain.setInhibScale(v);
      else if (k === "glutExc") brain.setGlutExcitatory(v);
      else if (k === "shuffle") brain.setShuffle(v, (opts.seed ?? 11) * 977 + 3);
    };
    G.resetPerturb = () => {
      G.PERTURB = { weightScale: 1, inhibScale: 1, shuffle: false, glutExc: false };
      brain.setShuffle(false); brain.setGlutExcitatory(false);
      brain.setInhibScale(1); brain.setWeightScale(1);
    };

    G.brain = brain; G.SUB = SUB;   // 供 dodge/audit.js 核对损毁是否真的切断了突触
    return G;
  }

  const api = { createGame, DEFAULTS, TG, clipPose };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.FlyDodgeGame = api;
})(typeof self !== "undefined" ? self : this);
