// 果蝇闪避 · 任务模式（v7）：把"虚拟敲除筛选"变成可玩的关卡。
// 与渲染无关，页面和 node 自检共用——和 game_core.js 一样的约定。
//
// 每一关给一个**手术目标**，玩家只能动开关（通路断突触 / 真实神经元敲除 / 打乱接线 / 光遗传脉冲），
// 不能改规则。通过与否由游戏自己测出来的行为指标判定。
//
// 三条规矩，写死在数据里、页面照着显示：
//   1. `basis` 说明这一关靠的是**连接组**还是**手写规则**；
//   2. `refKeys` 是参考解。`node dodge/mission_test.js` 实测「不干预」与「参考解」两种情况，
//      **通过线是照那份实测分布定的**——先测再定线，不是先编故事。每条线旁边都写着实测值。
//   3. 不许为了让某一关好看去改 game_core 里的规则（这条在 CLAUDE.md 里已经写了一年）。
(function (root) {
  const rate = s => (s.dodge + s.hit) ? s.dodge / (s.dodge + s.hit) : null;

  const MISSIONS = [
    {
      id: "silence_alarm",
      title: "关掉警报",
      brief: "球照扔，但要让它一次都不起飞——同时还得照常吃到糖。",
      why: "逃逸与进食是两条分开的通路：LC4/LPLC2 → 巨纤维管起飞，糖味 GRN → MN9 管伸喙。" +
           "切断视觉那条，进食毫发无损——这与全脑筛选里「糖与水的活跃神经元集合只重叠三分之一、" +
           "共用的那部分都在靠近输出的地方」是同一件事。",
      basis: "连接组",
      hint: "从「感觉输入」那一侧下手，别动运动输出——切运动输出会把吃也一起切掉。",
      refKeys: ["les:LC4", "les:LPLC2"],
      cfg: { autoPellets: true, pelletEvery: 3, pelletTypes: ["sugar"], autoDust: false },
      metrics: g => ({ jump: g.score.jump, feedS: +g.score.feed_s.toFixed(2), contacts: g.score.contacts_sugar }),
      goal: "起跳 = 0，且伸喙进食累计 ≥ 3 s",
      line: "实测（60 s × 3 种子）：不干预起跳 32 次、进食 8.7 s；切掉两条视觉通路后起跳 0 次、进食 10.6 s——" +
            "**进食反而更长**，因为不再被起飞打断",
      pass: m => m.jump === 0 && m.feedS >= 3,
    },
    {
      id: "stop_itch",
      title: "一刀止痒",
      brief: "灰尘不停落在触角上，让它**再也不梳理**——躲球的本事不许丢。只准动一个真实神经元。",
      why: "aBN1（SAD093）是梳理通路的绝对瓶颈：全脑筛选里单敲它让 aDN1 与 aDN2 同时归零，" +
           "Hampel et al. 2015 的实验也证实。子回路里同样是 59.8 → 0 Hz。" +
           "整条通路 596 个活跃神经元，只有这一个是不可替代的。",
      basis: "连接组",
      hint: "触角机械感觉通路上只有一个神经元是绝对瓶颈——在真实神经元开关里找它。",
      refKeys: ["neu:aBN1"],
      cfg: { autoDust: true, dustEvery: 3, autoPellets: false },
      metrics: g => ({ groom: g.score.groom, groomS: +g.score.groom_s.toFixed(2), dust: g.score.dust, dodgeRate: rate(g.score) }),
      goal: "梳理次数 = 0（且确实落过 ≥ 3 次灰）",
      line: "实测（60 s × 3 种子）：不干预梳理 8.3 次、累计 5.0 s；敲 aBN1 后 0 次、0 s",
      pass: m => m.groom === 0 && m.dust >= 3,
    },
    {
      id: "starve",
      title: "饿死它",
      brief: "糖粒管够，但要让它伸不出喙——躲球的本事不许丢。",
      why: "Roundup（CB0553）是糖 → MN9 通路上效应最强的前运动神经元之一：全脑敲除后比值 0.30，" +
           "子回路里 0.05。它不在逃逸通路上，所以躲球不受影响。",
      basis: "连接组",
      hint: "别切糖味受体（那不算手术）。去找进食通路上效应最强的那个中间神经元。",
      refKeys: ["neu:Roundup"],
      cfg: { autoPellets: true, pelletEvery: 3, pelletTypes: ["sugar"], autoDust: false },
      metrics: g => ({ feedS: +g.score.feed_s.toFixed(2), contacts: g.score.contacts_sugar, dodgeRate: rate(g.score) }),
      goal: "伸喙进食累计 < 1 s（且确实碰到过 ≥ 5 次糖粒）",
      line: "实测（60 s × 3 种子）：不干预进食 8.7 s，敲 Roundup 后 0.0 s（三次全是 0）",
      pass: m => m.feedS < 1 && m.contacts >= 5,
    },
    {
      id: "synergy",
      title: "一个不够，两个才行",
      brief: "还是让它吃不成，但这次 Roundup 不给你用。试试看：单独敲哪个都不太行。",
      why: "这是本项目最反直觉的一条结果：**单独敲除看不到的东西，必须把两个一起敲才会出现**。" +
           "Clavicle 与 G2N-1 单独敲都还剩九成进食，一起敲就塌一半——低于「各自独立」应有的乘积。" +
           "全脑筛选里这类协同有 10 对（留一稳定 7 对），而光看连线预测不出来（路径重叠与配对效应的 Spearman ≈ 0）。",
      basis: "连接组",
      hint: "两个都是论文里「伸喙必需」的类型。一个一个试没用，得同时敲。",
      refKeys: ["neu:Clavicle", "neu:G2N-1"],
      cfg: { autoPellets: true, pelletEvery: 3, pelletTypes: ["sugar"], autoDust: false },
      metrics: g => ({ feedS: +g.score.feed_s.toFixed(2), contacts: g.score.contacts_sugar }),
      goal: "伸喙进食累计 < 4 s（且碰到过 ≥ 5 次糖粒）",
      line: "实测（60 s × 3 种子，逐次）：不干预 6.1 / 8.6 / 11.2 s；单敲 Clavicle 5.4 / 8.1 / 5.1，" +
            "单敲 G2N-1 4.8 / 6.8 / 7.9；两个一起 2.8 / 2.9 / 2.0。" +
            "通过线 4 s 落在「单敲最低的 4.8」与「双敲最高的 2.9」之间——6 次单敲全过不了，3 次双敲全过。" +
            "独立相乘的预期是 4.6 s，实测 2.6 s，所以确实是协同而不只是叠加",
      singles: true,
      pass: m => m.feedS < 4 && m.contacts >= 5,
    },
    {
      id: "thirsty_boost",
      title: "拆掉刹车",
      brief: "场上只有水滴，而且它已经很渴了。想办法让喝水的驱动更强。",
      why: "Phantom（CB0062）是抑制性（GABA）的：敲掉它，**水**通路的 MN9 翻倍——全脑 3.02 倍、子回路 2.06 倍。" +
           "而同一个敲除在**糖**通路上几乎没有效果（0.92 / 0.97）。所以引用这个数字必须说明是哪条通路。",
      basis: "连接组",
      hint: "找一个抑制性神经元：切掉刹车，油门就显得更大。",
      refKeys: ["neu:Phantom"],
      cfg: { autoPellets: true, pelletEvery: 3, pelletTypes: ["water"], autoDust: false },
      init: g => { g.S.thirst = 0.8; },
      tick: (g, a) => { if (g.onPellet && g.onPellet.type === "water") { const v = g.readout().mn9 || 0; a.n = (a.n || 0) + 1; a.sum = (a.sum || 0) + v; a.peak = Math.max(a.peak || 0, v); } },
      metrics: (g, a) => ({ mn9Peak: +(a.peak || 0).toFixed(1), mn9Mean: +((a.sum || 0) / Math.max(a.n || 1, 1)).toFixed(1),
                            feedS: +g.score.feed_s.toFixed(2), contacts: g.score.contacts_water || 0 }),
      goal: "嘴下有水滴时的 MN9 峰值 ≥ 50 Hz",
      line: "实测（60 s × 3 种子）：不干预峰值 35.3 Hz、均值 11.3；敲掉 Phantom 后峰值 71.4、均值 20.2——" +
            "约 2.0 倍，与子回路实测的 2.06 倍、全脑的 3.02 倍同向。通过线 50 Hz 落在两者之间",
      calibrated: true,
      pass: m => m.mn9Peak >= 50,
    },
    {
      id: "shuffle_control",
      title: "证明连接组真的在起作用",
      brief: "打开「打乱接线」——保留每个神经元的出度与权重，只把靶点随机重排，看闪避率会怎样。",
      why: "这是论文补充表 1D 的对照，也是对「这些数字果蝇其实是随机网络在乱按键」这一质疑的正面回答：" +
           "如果打乱之后表现照旧，那连接组就没在起作用。我们实测：糖 → MN9 从 82.9 Hz 掉到 3.5 ± 4.2 Hz。" +
           "这一关用**原地起跳**模式，因为真实飞行轨迹的闪避率接近 100%，测不出差别。",
      basis: "连接组",
      hint: "开关在「动脑子」那一行。",
      refKeys: ["pert:shuffle"],
      cfg: { takeoff: "hop", autoPellets: false, autoDust: false },
      metrics: g => ({ dodgeRate: rate(g.score) === null ? null : +rate(g.score).toFixed(3), jump: g.score.jump, launched: g.score.launched }),
      goal: "起跳次数 < 20（同时看闪避率）",
      line: "实测（60 s × 3 种子，逐次）：不干预起跳 33 / 32 / 33 次、闪避率 0.85 / 0.84 / 0.95；" +
            "打乱后起跳 18 / 5 / 0 次、闪避率 0.07 / 0.79 / 0.43。" +
            "**判据用起跳次数而不是闪避率**——闪避率逐次波动太大（打乱后仍有一次 0.79），" +
            "而起跳次数三次都掉到 20 以下、三次不干预都在 32 以上，没有重叠。" +
            "这也更贴近机制：打乱先打断的是 looming → 巨纤维那一路",
      calibrated: true,
      pass: m => m.jump < 20,
    },
    {
      id: "opto_takeoff",
      title: "不用球，让它自己飞",
      brief: "场上一个球也没有。用「光遗传手指」直接点亮神经元，把它逼起飞。",
      why: "点下去的是这个子回路里**真实的** FlyWire 神经元，用的是和感觉输入同一套泊松驱动" +
           "（与论文 poi() 一致：被驱动的神经元不应期置 0）。实测：左侧 LC4+LPLC2 给 200 Hz、0.6 s，" +
           "巨纤维峰值 206.7 Hz，越过 90 Hz 阈值并触发起飞。强度与时长是手选的。",
      basis: "连接组（驱动真实神经元）+ 手写（强度、时长）",
      hint: "光标点在视觉投射神经元上——直接点巨纤维是作弊（它是输出端）。",
      refKeys: [],
      refAct: (g, t) => { if (t > 0.5 && !g.opto && g.score.jump === 0) g.optoPulse(g.optoTargets.LC4_LPLC2_left, 200, 0.6, "LC4+LPLC2 左"); },
      cfg: { autoPellets: false, autoDust: false, autoServe: false },
      metrics: g => ({ jump: g.score.jump, launched: g.score.launched }),
      goal: "在没有任何球的情况下起飞 ≥ 1 次",
      line: "实测（60 s × 3 种子）：不点任何神经元时起飞 0 次；给左侧 LC4+LPLC2 200 Hz、0.6 s 一次就起飞（巨纤维峰值 206.7 Hz，阈值 90）",
      pass: m => m.jump >= 1 && m.launched === 0,
    },
  ];

  // 把 refKeys 应用到一局游戏上：les:X 通路断突触 / neu:X 真实神经元敲除 / pert:X 论文式扰动
  function applyKeys(g, keys) {
    for (const k of keys || []) {
      const [kind, name] = k.split(":");
      if (kind === "les") g.setLesion(name, true);
      else if (kind === "neu") g.setNeuronLesion(name, true);
      else if (kind === "pert") g.setPerturb(name, true);
    }
  }

  const API = { MISSIONS, applyKeys };
  if (typeof module !== "undefined" && module.exports) module.exports = API;
  else root.FlyDodgeMissions = API;
})(typeof window !== "undefined" ? window : globalThis);
