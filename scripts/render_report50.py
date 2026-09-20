#!/usr/bin/env python3
"""日志 §50（无人值守数字果蝇生态箱）与 docs/ecobox/RESULTS.md：从 results/eco/summary.json（eco/collect_results.py 汇总）渲染。叙述手写，数字取自 JSON。不要手改渲染出来的那一节。"""
import json, re, sys
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
S = json.loads((ROOT / "results/eco/summary.json").read_text())
need = [k for k in ("audit", "surface", "m2", "m3", "m4", "live", "long") if k not in S]
if need: sys.exit("summary.json 里还缺：" + "、".join(need) + "（先把对应实验跑完，再 python3 eco/collect_results.py）")
au, sf, m2, m3, m4, lv = (S[k] for k in ("audit", "surface", "m2", "m3", "m4", "live")); lg = S["long"]
yn = lambda b: "通过" if b else "**未通过**"
FN = {"dnaL": "左转 DNa", "dnaR": "右转 DNa", "gf": "巨纤维", "mn9": "MN9 伸喙", "adn1": "aDN1 梳理", "mdn": "MDN 后退", "odn1": "oDN1", "bdn2": "BDN2", "mbonReward": "MBON 奖赏侧", "mbonPunish": "MBON 惩罚侧", "pam": "PAM", "ppl1": "PPL1"}
surf_rows = "\n".join(f"| {FN[f['name']]} | {'从不放电' if f['silent'] else format(f['r2'], '.3f')} | {sf['vs_mean'].get(f['name'], float('nan')):.3f} | {sf['ceiling'].get(f['name'], float('nan')):.3f} |" for f in sf["features"] if not f["silent"])
m2_rows = "\n".join(f"| {i['base']} | {i['off']} | ≥ {i['on']}（× {i['ratio_on']}） | × {i['ratio_shuffle']} | × {i['ratio_yoked']} | × {i['ratio_nobrain']} | {i['drinks_per_visit_off']} → {i['drinks_per_visit_on']} |" for i in m2["individuals"])
top = lambda k: "、".join(f"{n} {v:+.2f}" for n, v in m2["learned"][k][:4])
WN = {"drought": "干旱", "beetles": "甲虫多", "coldnight": "寒夜"}
world_rows = "\n".join(f"| {WN[k]} | {w['off']} | {w['on']} | {'、'.join(f'{c} {n}' for c, n in w['causes'].items())} | {'、'.join(c['title'] + '×' + str(c['count']) for c in w['cards'][:4])} |" for k, w in m2["worlds"].items())
m3_rows = "\n".join(f"| {w['name']} | {'，'.join(f'{d:+.2f}' for d in w['deltas'])} | {w['delta_mean']:+.3f} | 升 {w['n_up']} / 降 {w['n_down']} | **{w['label']}** | {w['life_head']} → {w['life_tail']} | {w['drink']:+.2f} | {w['odorTurn']:+.2f} | {w['learnRate']} | {'，'.join(map(str, w['gen_max']))} | {'，'.join(map(str, w['immigrants']))} |" for w in m3["worlds"])
nd = m2.get("no_decay")
body = f"""
用户的目标原话（节选）：「核心目标不是让玩家给果蝇下任务，而是让系统在生存压力下自己学出策略，玩家只设计规则、观察和微调环境……玩家只能调环境参数，不能直接改奖励函数……
如果飞行控制还没接好，先别假装它能学会飞……把『连接组是固定身体、可塑性层是后天学习』这条线讲清楚……最重要的玩法规则是奖励作弊和失败都要生成发现卡。」
计划与接口在 `docs/ecobox/PLAN.md`，M1 审计在 `docs/ecobox/AUDIT.md`，页面是 `docs/ecobox.html`（`python3 eco/build.py`）。

### {{N}}.1 四层，各管各的

| 层 | 是什么 | 谁能改它 |
|---|---|---|
| 世界规则 | 食物、水、冷热、风雨、甲虫、地形，共 16 个量（`eco/world.js` 的 RULES） | **玩家**，而且只有玩家 |
| 基因 | 10 个数：学习率、探索幅度、飞行倾向、偏好体温、代谢、警觉度、四个先天偏置（`eco/evolve.js`） | 进化（产卵时带变异） |
| 可塑性层 | {m2['n_features']} 个特征上的演员 - 评论家，三因子规则；给先天反射加偏置（`eco/plastic.js`） | 这只果蝇的一生；**不遗传** |
| 连接组 | 子回路 v5 的 {au['n_neurons']:,} 个神经元；页面里用的是它的响应面 | **没有人**——所有个体、所有世代共用同一个 |

奖励只有一个来源：六种内部状态（饥饿、口渴、体力、健康、气味、体温）离舒适点的加权平方和 D，reward = D 的减少（drive reduction，Keramati & Gutkin 2014）。常数写死在 `eco/physiology.js`，不对玩家开放。
感觉只给物理量（`eco/senses.js`）：食物 = 一团被风拉长的醋味 + 碰到时的甜味；水 = 湿度 + 水味；捕食者 = 一个变大的黑影 + 一种**先天上没有意义**的气味（气味 A）；被咬 = 一次很重的机械接触。
先天反射与 `dodge/game_core.js` 同一套常数（转向 6 °/s·Hz、巨纤维 > 90 Hz 起跳、MDN > 20 Hz 后退、MN9 ≈ 30 Hz 伸喙）。

### {{N}}.2 M1 审计（`eco/audit.js` → `docs/ecobox/AUDIT.md`）

每路感受器以 {au['hz']} Hz 喂进真脑（{au['seeds']} 个种子）看运动输出：{'；'.join(c['name'] + ' ' + c['verdict'] for c in au['channels'])}。
飞行：{au['flight']}。速度：真脑一只 {au['realtime_one']} 倍实时，32 只 {au['realtime_32']} 倍——所以进化必须用蒸馏。

### {{N}}.3 响应面：真脑的蒸馏（`eco/sample_surface.js`、`eco/fit_surface.py`）

27 路输入频率 → 12 个读出特征。真脑每个样本跑 100 ms 预热 + 300 ms 计数。**判据事先写定**：留出集（单次试验、原始 Hz）上转向 / 巨纤维 / MN9 的 R² ≥ {sf['r2_min']}。

- **第一版没过**（{sf['v1_samples']:,} 个样本、log1p 目标）：转向 R² 只有 {sf['v1_dna']}（`surface_fit_v1.json`）。
- 我先猜是目标本身的泊松噪声，**量了之后发现猜错了**：同一组输入换 4 个种子，转向这两路「单次对其余均值」的 R² 是 {sf['ceiling']['dnaL']:.2f} / {sf['ceiling']['dnaR']:.2f}——噪声天花板远高于模型。真正的原因是 log1p 反变换放大误差，加上样本不够（探索性诊断：换 sqrt 目标、加样本后验证 R² 明显上升；诊断脚本没入库，所以这里不写数字）。
- 第二版：sqrt 目标（泊松计数的方差稳定变换）、隐层 128、{sf['n_samples']:,} 个样本。判据 {yn(sf['pass'])}，**判据本身没动**。

| 特征 | 留出 R²（单次，Hz） | 对 4 次均值的 R² | 噪声天花板 |
|---|---|---|---|
{surf_rows}

PAM 在全部 {sf['n_samples']:,} 个样本里一次都没放电（§48 的阴性结果在这里又出现一次），响应面里恒为 0。

### {{N}}.4 M2 单只生存学习（`eco/m2_learning.js`）

**方案与判据写在脚本头**：3 个独立个体，各连续 {m2['train_lives']} 条命（可塑性层跨命保留），然后**冻结学习**，在 {m2['test_lives']} 个没见过的世界种子上测，上限 {m2['cap_s']:,} s。飞行关闭（先天的逃逸起跳保留）。
C1：学习臂测试寿命中位数 ≥ 1.5 × 不学习；C2：打乱奖励时序的对照 < 1.2 × 不学习。都要 3/3。

| 个体 | 不学习 s | 学习 s | 打乱奖励 | 轭式（事后加） | 看不到大脑输出 | 每次碰到水喝几次（不学 → 学） |
|---|---|---|---|---|---|---|
{m2_rows}

C1 {yn(m2['C1'])}，C2 {yn(m2['C2'])}；另换 10 个个体，{m2['robust_learned']}/{m2['robust_n']} 学成。寿命在 {m2['cap_s']:,} s 截尾，所以倍数是下限。

- **学到的是什么**：吃喝那一路 {top('ingest')}；「转得多不多」那一路 {top('kinesis')}。翻译过来：**碰到水就停下来喝**（连接组里水味只把 MN9 推到十几 Hz，先天不够伸喙——游戏页里那条「口渴阈值」是手写的，这里它是从内生奖励里学出来的），以及**湿度在上升时少拐弯**（经典的趋激性，没人教）。
- **没学会的**：远距离找水 / 找食物。干旱世界（1 个水洼）里不学习 {m2['drought_off']} s、学习 {m2['drought_on']} s；训练 30 条命 {m2['long_lives30']} s、120 条命 {m2['long_lives120']} s，没有差别。
- **连接组在这里的角色**：「看不到大脑输出」那一臂学得一样好。这个任务里，连接组给的是固定的身体和反射（不经过 MN9 就吃不了东西、不经过巨纤维就跳不起来），**不是学习信号**。
- **第一版（`m2_learning_v1.json`）C2 只过了 {m2['v1_C2']}**（打乱臂的倍数 {'、'.join(map(str, m2['v1_shuffle_ratios']))}）。原因是对照本身漏了：只把奖励延后 20–60 s，而喝水会持续几十秒，延后的奖励与行为仍然相关。事后加的轭式对照（回放另一条命的奖励序列）在两版里都不提升。
- **稳健性是后来才查的**：{f"把「不用就忘」（运动策略缓慢衰减回先天值）关掉，10 个个体只有 {nd['learned']} 学成，{nd['wall']} 个塌进贴墙、{nd['rest']} 个塌进躺平（`m2_no_decay.json`）" if nd else ""}——没有奖励进来时，评论家的噪声会把策略带着漂走。最初的 3/3 有运气成分。

**长期训练任务（`eco/train_long.js`，用户定的目标：10 个独立个体 10/10 学成）**。规则事先写定：每轮 {lg['lives_per_round']} 条命，轮末冻结学习在 {lg['test_worlds']} 个没见过的世界上测，寿命中位数 ≥ 1.5 × 不学习（{lg['baseline']} s → 线 {lg['need']} s）算学成并毕业，没学成的进下一轮（最多 {lg['max_rounds']} 轮）；毕业后再换 {lg['test_worlds']} 个新世界复测。
结果：**{lg['n_learned']}/{lg['n']} 学成，复测通过 {lg['n_retest_ok']}/{lg['n']}**，共 {lg['total_lives']} 条命，各自用了 {'、'.join(map(str, lg['rounds_to_learn']))} 轮；毕业时的测试寿命中位数 {'、'.join(str(d['median']) for d in lg['individuals'])} s，贴墙占比最高 {max(d['wall'] for d in lg['individuals'])}、歇着占比最高 {max(d['rest'] for d in lg['individuals'])}（没有一只塌进作弊）。任务可中断续跑（`train_long_state.json`）。

更凶的世界（探索性，在那个世界里训练和测试）：

| 世界 | 不学习 s | 学习 s | 学习臂死因 | 发现卡 |
|---|---|---|---|---|
{world_rows}

### {{N}}.5 M3 跨代进化（`eco/evolve.js`、`eco/m3_evolution.js`）

32 只同时活；吃饱喝足健康的才攒得出卵（没有适应度函数）；后代带 10 个基因的变异出生，**可塑性层是白纸**。飞行作为可决策的技能解锁：起不起飞是决策，怎么飞是固定的 1.2 s / 72 mm 弹道。
**判据事先写定**：三个世界各 {m3['n_seeds']} 个种子、{m3['seconds']:,} s；Δ = 最后 20% 时间的种群平均飞行倾向 − 奠基值；≥ 4/5 个种子 Δ > +0.5 为「升」，< −0.5 为「降」，否则「平」；至少两个世界标签不同算通过。

| 世界 | Δ 飞行倾向（各种子） | 均值 | 计数 | 标签 | 寿命 s 前 20% → 后 20% | 先天：尝到水就喝 | 先天：朝捕食者气味转 | 学习率 | 最高代数 | 迁入 |
|---|---|---|---|---|---|---|---|---|---|---|
{m3_rows}

M3 判据 {yn(m3['pass'])}（标签：{'、'.join(f"{next(w['name'] for w in m3['worlds'] if w['key'] == k)} {v}" for k, v in m3['labels'].items())}）。

### {{N}}.6 M4 存档与分享（`eco/save.js`、`eco/m4_save_test.js`）

存档对象是一份训练成果：世界规则、世代时间线、每只果蝇的身体与权重、发现卡、回放、随机数状态。{'、'.join(c['name'] + (' ✓' if c['pass'] else ' ✗') for c in m4['checks'])}。
中断 → JSON → 读回 → 接着跑，状态指纹与不中断的那一份相同（{m4['fingerprint']}，存档约 {m4['save_bytes'] / 1e6:.1f} MB）。挑战码 {m4['code_chars']} 个字符，只含规则、种子和冠军基因。

### {{N}}.7 真脑闭环复核（`eco/live_check.js`）

把 M2 里在响应面上学成的个体冻结权重，放回真的 {au['n_neurons']:,} 神经元脉冲网络（{lv['lives']} 个世界种子，上限 {lv['cap_s']} s）：真脑 {lv['live_median']} s，响应面 {lv['surface_median']} s，白纸 {lv['naive_median']} s。
L1（真脑 ≥ 1.5 × 白纸）{yn(lv['L1'])}（× {lv['ratio_live_vs_naive']}）；L2（喝水时间占比在响应面的 0.5–2 倍内）{yn(lv['L2'])}（{lv['drink_live']} 对 {lv['drink_surface']}）。

### {{N}}.8 这一轮自己查出来的错

1. **猜原因之前先量**：响应面第一版没过，我猜是噪声，量出来天花板 {sf['ceiling']['dnaL']:.2f}——猜错了。
2. **捕食者气味一开始用了「气味 B」**，而连接组对 B 有先天的左转（§48）：果蝇一闻到甲虫就原地打转。换成先天上无意义的气味 A。
3. **走路的代谢代价设成了静息的 1.5 倍**，躺平因此成了理性选择（寿命真的更长）。昆虫步行只比静息高一两成；改正后躺平仍会出现，但不再是默认世界的最优解。
4. **转向策略里混进了不分左右的特征**，学出恒定的单向偏置 = 原地转圈。按身体的左右对称性拆成两路：往哪边转只看分侧信号，转得多不多看不分侧的信号。
5. **打乱奖励的对照是漏的**（见 {{N}}.4）。
6. **3/3 成功有运气成分**，换 10 个个体才看出来。
7. **「气味」这个内部状态第一版几分钟后就恒为 1.00**（涨得太快，只有歇着和下雨能降）——六种状态里有一种成了常数，是看页面截图才发现的。改成：累积减半多、随时间自己消散、蹚水能洗掉。身体变了，所以 M2 / M3 / 真脑复核 / 长期训练全部用最终代码重跑；旧身体的结果留在 `results/eco/old_body/`（本机，不入库）。
8. 进化模块里新生儿在同一步被数了两次（种群一度超过上限）；页面测试里手机宽度那项拿 `innerWidth` 比，内容把布局撑宽时两个数一起变大，假通过了。

### {{N}}.9 能说什么、不能说什么

- **能说**：在一个只给物理量、只有内生奖励的箱子里，接在固定连接组旁边的可塑性层学会了喝水和趋湿；不给任何适应度函数，种群自己演化出了「尝到水就喝」的本能，寿命成倍变长；奖励作弊（躺平、贴墙、原地打转）会自发出现并被系统抓出来。
- **不能说**：「果蝇的大脑学会了生存」——连接组一个突触都没变，学习发生在手写的可塑性层里；「它学会了找食物」——没有，远距离导航没学会；「它学会了飞」——飞行是固定弹道，能学 / 能进化的只有起不起飞。
  响应面是蒸馏，不是真脑；世界、身体常数、可塑性层的结构与超参、基因的变异幅度全部手选（登记在台账 PARAMETERS）。
"""
title = "无人值守数字果蝇生态箱：只改世界，不改奖励（2026-09-20）【工程 + 实测】（`eco/`）"
block = "<!-- §50:begin （本节由 scripts/render_report50.py 渲染；不要手改数字）-->\n## 50. " + title + "\n" + body.replace("{N}", "50") + "<!-- §50:end -->\n"
p = ROOT / "docs/log/report.md"; s = p.read_text()
s = re.sub(r"<!-- §50:begin.*?<!-- §50:end -->\n", lambda m: block, s, flags=re.S) if "<!-- §50:begin" in s else s.rstrip("\n") + "\n\n" + block
p.write_text(s)
(ROOT / "docs/ecobox/RESULTS.md").write_text("# 生态箱：实测结果\n\n> 本文件由 `scripts/render_report50.py` 从 `results/eco/summary.json` 渲染，不要手改。计划见 [PLAN.md](PLAN.md)，M1 审计见 [AUDIT.md](AUDIT.md)。\n" + re.sub(r"### \{N\}\.(\d+)", r"## \1.", body).replace("{N}.", "第 ").replace("{N}", ""))
print("日志 §50 与 docs/ecobox/RESULTS.md 已渲染")
