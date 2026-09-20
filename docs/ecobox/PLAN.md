# 无人值守数字果蝇生态箱 · 计划

> 玩家是造物者：只设计世界规则、观察、微调环境。**不给任务，不改奖励函数。**
> 果蝇在生存压力下自己学；它可能学会飞，也可能始终不飞——由环境和长期的生存结果决定。
> 它是一只会成长、会跑偏、会被玩家「骗着走」的数字生物，不是一个演示模型。

## 一条主线：连接组是固定的身体，可塑性层是后天的学习

| 层 | 是什么 | 会不会变 | 谁能改 |
|---|---|---|---|
| **连接组**（FlyWire v783 子回路 v5，15,055 个神经元） | 先天的身体：感受器 → 中间神经元 → 下行 / 运动神经元。逼近就起飞、尝到糖就伸喙、触角被压就转向，都是它自带的 | **不变**（突触权重一个不动） | 谁也不能 |
| **蘑菇体突触**（KC→MBON，多巴胺门控） | 连接组里文献确认的可塑位点：气味记忆 | 一生之内变 | 只有它自己的经历 |
| **可塑性层**（本项目加的一小层，约几百个权重） | 读大脑的放电 + 身体内感受，调节「转多少、走不走、肯不肯吃喝、（解锁后）起不起飞」 | 一生之内变，**不遗传** | 只有它自己的经历 |
| **基因**（第二阶段，≤ 10 个数） | 学得多快、多爱探索、飞行倾向、偏好的体温…… | 一生之内不变，**代际之间带变异地遗传** | 只有淘汰 |
| **世界规则** | 食物 / 水 / 天敌的多少、昼夜、冷热、风雨、地形 | 玩家随时改 | **玩家** |

奖励不是玩家给的：六种内部状态偏离各自的舒适点有多远 = 「驱力」；驱力下降就是好事、上升就是坏事（稳态强化学习，Keramati & Gutkin 2014）。
这条公式写死在生理模块里，界面上没有任何入口能改它。玩家想让它学别的，只能改世界。

## 四个里程碑

| | 内容 | 产出 | 事先写死的验收 |
|---|---|---|---|
| **M1 技术审计** | 感知 / 动作 / 飞行 / 学习四条链路逐项实测，固定成清单 | `eco/audit.js` → `results/eco/audit.json` → `docs/ecobox/AUDIT.md` | 每一项都有实测数字和「接上了 / 半接上 / 没接上」的判定；后面的玩法只许建立在「接上了」的项上 |
| **M2 单只生存学习** | 六种内部状态、内生奖励、可塑性层、爬行世界；飞行作为**可学技能**先锁着（先天的逃逸起跳保留——那是连接组自带的反射） | `eco/` 核心 + 无头实验 + 页面 | 学过的个体寿命中位数 ≥ 1.5 × 不学习的对照；打乱奖励时序的对照不提升 |
| **M3 跨代进化** | 32 只同时跑；活得好就繁殖；≤ 10 个可遗传参数带变异；「飞行倾向」是其中之一；世代时间线 + 关键事件回放 | 进化实验 + 页面时间线 | 不同世界规则下，飞行倾向的演化方向不同（至少两种世界，方向相反或一升一平） |
| **M4 存档分享** | 实验存档 = 世界种子 + 环境参数 + 世代记录 + 关键检查点 + 代表个体；本地存档 + 导出 / 导入；别人能续跑、能复现 | 存档格式 + 导入导出 + 挑战码 | 导出 → 清空 → 导入之后，同一种子续跑的前 N 步逐位相同 |

贯穿全程的玩法规则：**奖励作弊和失败都要生成「发现卡」**。玩家可以「接受这个策略」（归档成一个故事），也可以「改环境，继续逼它进化」。

## 为什么需要「响应面」（M1 的实测结论决定的）

15,055 个神经元的放电大脑在这台机器上约 1.5 × 实时，一只都开不了时间加速，更别说 32 只。做法沿用五子棋那一套：
**让真脑把输入空间采样跑一遍 → 拟合成一张响应面（输入频率 → 各读出 / 特征群的发放率）→ 快进和群体用响应面，镜头里那一只随时可以切回真脑并排核对。**
页面上必须写明哪一只在跑真脑、哪些在跑响应面，以及响应面对真脑的拟合优度。

## 数据结构

```text
Genome        { id, parent, generation, genes: { learnRate, explore, flightBias, tempPref, metabolism, caution, innateTurn[4] } }
Physiology    { hunger, thirst, stamina, health, scent, bodyTemp }        # 0–1（bodyTemp 为 ℃）；舒适点与耗损速率是常数，不对玩家开放
Senses        { food:{L,R}, water:{L,R}, slope:{pitch,roll}, wind:{L,R}, temp, danger:{L,R}, others:{L,R}, taste:{sugar,bitter,water}, touch:{L,R} }
BrainOut      { dnaL, dnaR, gf, mn9, adn1, mdn, mbonReward, mbonPunish, pam, ppl1, pop[k]:{L,R} }   # 来自真脑或响应面，同一接口
Plastic       { W[actions × features], V[features], elig, baseline }      # 可塑性层：演员 - 评论家，三因子规则
Action        { turn, speed, feedWill, takeoff }                           # 转向偏置、走 / 停、肯不肯吃喝、（解锁后）起飞
Agent         { genome, phys, plastic, memory(odor→隔室), pose, age, alive, log }
WorldRules    { seed, food, water, predators, dayLength, tempDay, tempNight, rain, wind, roughness, sunrocks, rot }   # 玩家只能改这些
Event         { t, agent, kind: birth|death|eat|drink|hit|takeoff|exploit|..., data }
DiscoveryCard { id, kind: exploit|failure|milestone, title, evidence{指标}, when, verdict: null|accepted|rejected }
Experiment    { version, rules, generationLog[], checkpoints[], cards[], champion }   # 可发布的训练成果
```

## 接口

```text
eco/physiology.js   create(genes) → { state, step(dt, ctx) → drive, reward }         ctx = 吃 / 喝 / 受伤 / 环境温度 / 用力程度
eco/senses.js       sense(world, agent, others) → Senses ; encode(Senses) → 输入频率向量（与 game_core 同一套换算）
eco/brain_live.js   真脑：step(rates, dt) → BrainOut        eco/brain_surface.js  响应面：同接口
eco/plastic.js      create(nFeat, genes) → { act(features) → Action, learn(reward, dt) }
eco/sim.js          create(rules, opts) → { agents, step(dt), spawn(genome), on(event) }   多只、无渲染、可快进
eco/evolve.js       繁殖 / 变异 / 淘汰 / 世代记录
eco/cards.js        从行为统计里找奖励作弊与失败 → DiscoveryCard
eco/save.js         Experiment ⇄ JSON ⇄ 挑战码
```

## 参考数据集（暂不接，留作后续）

真实步行数据（Dryad / Zenodo）可用来校步速与转向分布；FlyMABe2022 与 InsectSound 适合第二阶段之后的「其他果蝇」通道。本阶段不引入，避免玩法建立在还没核实的数据上。
