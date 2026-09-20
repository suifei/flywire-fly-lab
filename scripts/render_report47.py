#!/usr/bin/env python3
"""日志 §47（五感 + 自己生活）从 results/dodge/life_summary.json 渲染进 docs/log/report.md 的 <!-- §47:begin/end --> 之间。叙述手写，数字全部取自 JSON。"""
import json, re, sys
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
S = json.loads((ROOT / "results/dodge/life_summary.json").read_text())
sub, reach, mod, sp, lt = S["subcircuit"], S["reach"], S["modulation"], S["sound_priming"], S.get("life_test")
pct = lambda v: "—" if v is None else f"{v * 100:.0f}%"
hop = lambda g: "、".join(f"{k.split('（')[0]} {v}" for k, v in reach[g]["hops"].items())
modrow = "\n".join(f"| {r['base']} | {r['readout']} | {r['base_hz']['mean']} ± {r['base_hz']['sd']} | {r['mod']} | {r['hz']['mean']} ± {r['hz']['sd']} | {'**有**' if r['modulates'] else '—'} |" for r in mod["rows"])
G = sp["groups"]; sprow = "\n".join(f"| {k} | {v['jumped']}/{sp['n']} | {v['dodged']}/{sp['n']} | {v['lead_ms_median']} | {v['gf_max_mean']} |" for k, v in G.items())
life = ""
if lt:
    C = lt["conds"]; NM = dict(intact="完整", deaf="失聪（AUDIO 断突触）", anosmic="失嗅（OLFA+OLFR 断突触）", starved="能量钉在 0.1", sated="能量钉在 1.0", isn_on="打开 ISN 通路")
    rows = "\n".join(f"| {NM[k]} | {v['startled']}/{v['sounds']} | {v['sugar_contacts']} | {v['sugar_feeds']} | {v['eaten_sugar']} | {v['eaten_water']} | {v['jumps']} | {v['mean_energy']} | {v['mean_hydration']} |" for k, v in C.items())
    life = f"""
### 47.5 让它自己过 {lt['seconds'] // 60} 分钟（`dodge/life_test.js`，每个条件 {lt['seeds']} 个种子的均值）

| 条件 | 声音响起 1 s 内起飞 | 碰到糖 | 开吃 | 吃完的糖 | 喝完的水 | 起飞 | 能量均值 | 水分均值 |
|---|---|---|---|---|---|---|---|---|
{rows}

判据都写在跑之前：

- **H1 听觉有用**（声音后 1 s 内起飞 ≥ 20% 且 ≥ 2 × 失聪）→ **{'成立' if lt['H1']['passed'] else '不成立'}**：完整 {pct(lt['H1']['intact'])}、失聪 {pct(lt['H1']['deaf'])}。声音单独驱动不了起飞（见 47.3），它的作用是让逼近反应提前。
- **H2 嗅觉有用**（每 10 分钟吃到的糖 ≥ 1.3 × 失嗅）→ **{'成立' if lt['H2']['passed'] else '不成立'}**：完整 {lt['H2']['intact_per10min']}、失嗅 {lt['H2']['anosmic_per10min']}。与 47.2 一致：这两个嗅小球在这个子回路里没有通到转向。
- **H3 身体状态有用**（碰到糖后开吃的比例：饿 ≥ 1.5 × 饱）→ **{'成立' if lt['H3']['passed'] else '不成立'}**：饿 {pct(lt['H3']['starved'])}、饱 {pct(lt['H3']['sated'])}。
"""
text = f"""<!-- §47:begin （本节由 scripts/render_report47.py 从 results/dodge/life_summary.json 渲染；不要手改数字）-->
## 47. 五感补全 + 让它自己生活（2026-09-20）【实测】（子回路 v4、`dodge/life_test.js`、`dodge/sound_priming.js`、`dodge/sense_modulation.js`）

用户的目标：「激活果蝇的五感，让它自己思考，生活在我们提供的世界里」。原则沿用 §38：**世界只提供物理量，送到真实的感受器上；转不转、飞不飞、吃不吃由连接组决定，不写任何判断逻辑。**

### 47.1 先查通路，再裁子回路

视、味、触（加温度、湿度）在 v3 里已经接好。缺的是听、嗅，以及「身体内部的感觉」。`dodge/sensor_reach_v4.py` 在全脑上查（≥3 个突触的边）：

| 感觉 | 神经元数 | 到各运动输出的最少跳数 |
|---|---|---|
""" + "\n".join(f"| {g} | {reach[g]['n']} | {hop(g)} |" for g in reach) + f"""

听觉 1 跳到巨纤维——文献里江氏器的听觉神经元确实直接接在巨纤维的树突上。于是裁了**子回路 v4**：{sub['n']:,} 个神经元、{sub['n_edges']:,} 条边，
比 v3 多四路输入：AUDIO（听觉，左 {sub['inputs']['AUDIO'][0]} / 右 {sub['inputs']['AUDIO'][1]}）、OLFA（醋，ORN_DM1）、OLFR（土臭素，ORN_DA2）、ISN（4 个内感受神经元）。
嗅觉只取两个嗅小球：全取 1,850 个 ORN 会把整个触角叶和蘑菇体卷进来，页面跑不动。**球场（v3）与五子棋（v3）不动**，生活模式单独用 v4，已发布的数字不受影响。

### 47.2 每一路有没有落点（`sensor_drive_v4.json`，每路单独驱动 1 s）

≤200 Hz 就有落点：{'、'.join(S['drive_summary']['lands_at_200'])}；只有高频才有：{'、'.join(S['drive_summary']['only_at_high_rate'])}；完全没有落点：{'、'.join(S['drive_summary']['no_landing'])}（BITTER 本来就是抑制性的）。
**听觉有落点**（双侧 100 Hz 就能让巨纤维放电，单侧不行）；**嗅觉与 ISN 单独驱动没有落到六个运动读出的任何一个上**——它们各自能激活上百个神经元，但闻到之后往哪走，这个模型里没有通路（与 §10 全脑上「嗅觉没有左右偏侧化」一致）。

### 47.3 调制：单独没落点的，叠在别的感觉上有没有用（`sense_modulation.json`，5 个种子，判据「差 > 2 SD 且 > 20%」写在跑之前）

| 基础刺激 | 读出 | 基础（Hz） | 叠加 | 叠加后（Hz） | 调制 |
|---|---|---|---|---|---|
{modrow}

**ISN 是一个很强的门控——但方向与文献相反。** González-Segarra et al. 2023（eLife 12:e88143）：ISN 活动增强 → 吃糖增多、喝水减少；饥饿提高、口渴降低 ISN 活动。
模型里驱动 ISN 把吃糖的伸喙几乎关掉。喝水那一侧的方向与文献一致（另测：水 GRN 160 Hz 时 MN9 5.1 → 2.6 Hz），所以模型里的 ISN 是一个对伸喙的**通用抑制**。
原因和 §14 的 Usnea 同类：ISN 用的是神经肽 dILP3，LIF 模型只有预测的快递质符号。**所以没有用 ISN 去做"饿了想吃"**——那样得翻转它的符号，等于为了想要的行为去改模型。
页面上留了一个默认关闭的「ISN 通路」开关，打开就能看到一只饿了反而不吃的果蝇。

### 47.4 声音单独不让它起飞，但让它对逼近更敏感（`sound_priming.json`，探索性）

听觉神经元开到 200 Hz，巨纤维读出最高约 80 Hz，起飞阈值是 90 Hz（按视觉逼近标定的）。**没有为了让它被吓飞去调阈值或声音强度。**对照实验：同一颗慢球（{sp['ball_speed']} mm/s），发球的同时在来球方向放不放声源：

| 组 | 起飞 | 躲开 | 起飞提前量中位（ms） | 巨纤维峰值均值（Hz） |
|---|---|---|---|---|
{sprow}

有声时起飞明显提前、躲开的更多；**切断听觉神经元的传出突触之后两个数字都回到无声的水平**——效应确实是经由听觉神经元、在连接组里汇到巨纤维上的。这是多模态整合，没有一行新写的判断逻辑。
判据是看过 life_test 的初跑之后才想到的，所以标探索性。
{life}
### 47.6 「身体」与「它在想什么」——哪些是手写的

- **身体状态**（能量、水分）属于身体，不是大脑。它只改两样东西：味觉感受器的灵敏度（缺什么对什么更敏感；文献依据 Inagaki et al. 2012，增益范围手选）和走路速度。**不直接决定任何行为。**
  打开它的时候，球场模式里那条手写的「渴了就降低喝水阈值」规则不再使用；「MN9 超过多少算开吃」统一为 10 Hz（手选）——原来的 30 Hz 水永远过不了：水感受器开到 320 Hz，MN9 也只有 22 Hz。
- **世界**（昼夜、果子、水洼、气味、声音、热源、风、灰尘、来球）的节奏与强度全部手选。食物是半径 7 mm 的一块烂果子而不是 2 mm 的糖粒——嗅觉不通到转向，果蝇只能靠撞。
- **「它在想什么」**：每个词的触发量都是实测的（感觉词 = 此刻送进那一路感受器的频率；动作词 = 读出神经元的发放率），句子模板与阈值手写。它不是语言模型，也不是果蝇会说话。
- 围栏视觉在生活模式里关掉了：果蝇自己走向围栏会被当成逼近，实测每分钟白白起飞 21 次；避墙交给触感。
<!-- §47:end -->"""
rep = ROOT / "docs/log/report.md"; s = rep.read_text()
if "<!-- §47:begin" in s: s = re.sub(r"<!-- §47:begin.*?<!-- §47:end -->", lambda m: text, s, flags=re.S)
else: s = s.rstrip() + "\n\n" + text + "\n"
rep.write_text(s); print(f"§47 已渲染（{len(text):,} 字符）")
