#!/usr/bin/env python3
"""日志 §49（大自然：有物理的 3D 开放世界）从 results/dodge/nature_test.json 与 results/learn/nature_life.json 渲染进 docs/log/report.md 的 <!-- §49:begin/end --> 之间。叙述手写，数字取自 JSON。"""
import json, re, sys
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
T = json.loads((ROOT / "results/dodge/nature_test.json").read_text())["tests"]; NL = json.loads((ROOT / "results/learn/nature_life.json").read_text()); W = {k: v["mean"] for k, v in NL["worlds"].items()}
V1 = json.loads((ROOT / "results/learn/nature_life_v1.json").read_text())["worlds"]["nature"]
v1note = f"**世界改过一次**：第一版里食物只有从浆果丛现掉下来的浆果。它一直往前走、闻到了也不会拐过去（嗅觉不通到转向，§47），浆果都落在身后——3 分钟掉了 {V1['berries']:.0f} 颗，只碰到 {V1['sugar_contacts']:.1f} 次糖，结束时能量 {V1['energy']:.2f}（`nature_life_v1.json`）。于是在世界里加了「早先掉在地上、已经在发酵的果子」（每格约 55% 的概率有一颗）。这是**世界的设计**，和平地世界把食物放在它前方是同一类做法，不是给果蝇写的规则。\n\n"
yn = lambda b: "成立" if b else "**不成立**"; n, f, c = W["nature"], W["flat"], W["court"]
row = lambda lab, k, fmt="{:.1f}", unit="": f"| {lab} | {fmt.format(n[k])}{unit} | {fmt.format(f[k])}{unit} | {fmt.format(c[k])}{unit} |"
text = f"""<!-- §49:begin （本节由 scripts/render_report49.py 渲染；不要手改数字）-->
## 49. 把篮球场换成大自然：一个有重力、有天气、没有边界的 3D 世界（2026-09-20）【工程 + 实测】（`dodge/nature.js`、`dodge/nature3d.js`、`dodge/nature_test.js`、`learn/nature_life.js`）

用户的目标原话：「将篮球场改成一个 3D 立体的大自然……做成开放世界，有物理，有大自然要素，有重力，有物理特性的虚拟元宇宙世界」。

### 49.1 做了什么

- **世界**（`dodge/nature.js`，按种子确定性生成、没有边界，单位 mm / s）：三层值噪声叠出来的起伏地形（约 ±10 mm），每 40 mm 一格里确定性地放石头、深色石板、蘑菇、花、落叶、草丛、浆果丛、洼地。
  游戏核心和 3D 渲染（`dodge/nature3d.js`）用的是**同一个世界对象**——画出来的石头就是它撞上的石头。渲染端是一张跟着果蝇走的地形网格 + 实例化的植被（约 7,500 片草叶，随风摆）+ 天空、太阳、星星、雾、雨。
- **物理**（真实单位）：重力 9,810 mm/s²；浆果熟了从枝头掉下来，落地按地形法线反弹（恢复系数 0.35），之后按实心球纯滚动（a = 5/7 · g · sinθ），滚动阻力 0.15 g，停稳后变成一块会发酵的果肉；
  实心物件（石头、蘑菇柄、灌木茎）不可穿透；上坡走得慢、下坡快（身体做功）；深色石板的温度以 20 s 的时间常数跟着日照走；洼地下雨蓄水、晴天蒸发；风把气味羽流吹向下风并拉长。
- **果蝇只通过已有的感觉通道知道这一切**：坡度 → 步速；实心物件 → 挡路 + 触角被压（TOUCH）；晒烫的石板 → 温度感受器；水洼 / 雨 → 湿度感受器 + 水味觉；雨声 / 甲虫振翅 → 听觉神经元；
  落地发酵的浆果 → 醋味 + 气味 A（坏的发霉）；爬过来的甲虫、头顶掉下来的浆果 → 同一套逼近视觉前端。吃到糖 → PAM、被烫 → PPL1 的那根手接的线不变。**没有新增任何一条行为规则。**
- **为什么威胁是甲虫而不是飞来的球**：在这个尺度上，60 mm/s 水平速度的抛体 0.1 秒内就落地、滚几毫米就停——「慢慢滚过来的球」不物理。自己会爬的东西才可能以这个速度贴着地面靠近；视觉前端对它和对球完全一样。
- **页面**：第一个标签改成「大自然 / 篮球场」，下面的「世界」开关三选一——**大自然 · 开放世界 · 五感全开**（第一次来的访客默认进这里）/ 篮球场 · 五感全开 / 篮球场 · 球场版 5,563（任务、突变体、光遗传仍属于它，用到时自动切过去）。
  选择记在本机，世界的种子也记在本机（每个人有自己的一片地）。自动化测试带 `?scene=court`，因为那些检查针对的是球场版。

### 49.2 物理自检（`dodge/nature_test.js`；判据写在跑之前，都是能手算的量）

| 判据 | 实测 | |
|---|---|---|
| N1 自由落体：30 mm 落地时间与 √(2h/g) 相差 ≤ 1 个物理步（5 ms） | {T['N1_free_fall']['t_sim']} s 对 {T['N1_free_fall']['t_analytic']} s | {yn(T['N1_free_fall']['pass'])} |
| N2 反弹不生能量：弹起高度单调下降，首次 ≤ e² × 初始高度 × 1.15 | {' → '.join(str(p) for p in T['N2_no_energy_gain']['peaks_mm'])} mm（上限 {T['N2_no_energy_gain']['bound_mm']}） | {yn(T['N2_no_energy_gain']['pass'])} |
| N3 平地上 3 秒内停稳，之后不再动 | {T['N3_comes_to_rest']['rest_s']:.2f} s | {yn(T['N3_comes_to_rest']['pass'])} |
| N4 陡坡上往下滚，缓坡上滚动阻力兜得住 | 坡度 {T['N4_rolls_downhill_only_when_steep']['steep_slope']}：1 秒降了 {T['N4_rolls_downhill_only_when_steep']['dropped_mm']} mm；平地移动 {T['N4_rolls_downhill_only_when_steep']['flat_moved_mm']} mm | {yn(T['N4_rolls_downhill_only_when_steep']['pass'])} |
| N5 地形确定且连续（相邻 0.1 mm 高差 < 0.2 mm） | 最大 {T['N5_deterministic_continuous']['max_step_mm']} mm | {yn(T['N5_deterministic_continuous']['pass'])} |
| N6 上坡慢、下坡快 | 速度系数 {T['N6_slope_speed']['uphill']} / {T['N6_slope_speed']['downhill']} | {yn(T['N6_slope_speed']['pass'])} |
| N7 实心物件不可穿透 | 半径 {T['N7_solid']['rock_r']} mm 的石头，圆心被推到 {T['N7_solid']['pushed_to']} mm 外 | {yn(T['N7_solid']['pass'])} |
| N8 风把气味吹向下风（无风时两侧相等） | 下风 {T['N8_wind_plume']['downwind']}、上风 {T['N8_wind_plume']['upwind']}、无风 {T['N8_wind_plume']['calm']} | {yn(T['N8_wind_plume']['pass'])} |
| N9 闭环里走 60 秒：脚下高度恒等于地形高度、从不穿进实心物件、总路程 > 300 mm | 走了 {T['N9_closed_loop_walk']['path_mm']} mm，最大穿入 {T['N9_closed_loop_walk']['max_penetration_mm']} mm，掉了 {T['N9_closed_loop_walk']['berries_dropped']} 颗浆果 | {yn(T['N9_closed_loop_walk']['pass'])} |

### 49.3 它在大自然里过得怎么样（`learn/nature_life.js`；v5 + 六条腿，{NL['seconds']} s × {NL['seeds']} 个种子的均值；只报告，不设判据）

| | 大自然 | 平地开放世界（「生活」标签） | 篮球场 |
|---|---|---|---|
{row('总路程', 'path_mm', '{:.0f}', ' mm')}
{row('平均步速系数（坡度）', 'slope_factor', '{:.2f}')}
{row('被实心物件挡住的时间', 'blocked_s', '{:.1f}', ' s')}
{row('触角有触碰的时间', 'touch_s', '{:.1f}', ' s')}
{row('起飞', 'jumps')}
{row('躲开 / 被撞（甲虫或球）', 'dodge')}
{row('被撞', 'hit')}
{row('掉下来的浆果', 'berries')}
{row('被浆果砸到', 'bonk')}
{row('碰到糖', 'sugar_contacts')}
{row('吃了几秒', 'feed_s', '{:.1f}', ' s')}
{row('喝水几秒', 'drink_s', '{:.1f}', ' s')}
{row('淋雨', 'rain_s', '{:.1f}', ' s')}
{row('被晒烫 / 烤热（热 > 0.5）', 'hot_s', '{:.1f}', ' s')}
{row('多巴胺 PAM', 'pam_s', '{:.1f}', ' s')}
{row('多巴胺 PPL1', 'ppl1_s', '{:.1f}', ' s')}
{row('3 分钟后：A 的奖赏记忆', 'memA_reward', '{:.0%}')}
{row('3 分钟后：B 的惩罚记忆', 'memB_punish', '{:.0%}')}
{row('结束时的能量', 'energy', '{:.2f}')}

{v1note}大自然里没有气味 B 的来源（B 是球场 / 平地世界里热源带的「焦味」；晒烫的石板不带气味），所以 B 的惩罚记忆那一格本来就该是空的。

### 49.4 像「我的世界」那样玩：沙盒、生物群系、铺满窗口（用户的下一条要求；画面不学它的方块，尽量拟态）

- **沙盒**：场景底部一条工具栏（数字键 1–0 选，点地面使用）：放发酵的果子 / 发霉的果子、挖蓄水的小洼、放石头、种蘑菇 / 浆果丛 / 花、放深色石板、放甲虫；`=` / `-` 抬高 / 挖低地形（每次 1.5 mm 的高斯土丘，可反复点）；`X` 拆掉点到的东西。
  这些改的是**同一个世界对象**（`W.place / removeNear / dig`）：放下的石头真的挡路、真的压到触角，种的浆果丛真的会按重力掉果子，抬高的地形真的让它走得慢。改动按世界种子存在本机（`fly-nature-edits-<种子>`），重新打开还在；「新世界」换一个种子。
- **生物群系**：一张很低频的噪声把世界分成草甸 / 林下 / 砾石滩 / 湿地四种地方（出生点附近固定是草甸），各自的石头、石板、蘑菇、浆果丛、洼地、落果、花、落叶、草的多少不同，地面色调也不同。比例全部手选。
- **视角**：`C` 在 轨道 / 跟在身后 / 第一人称 之间切。**键盘遥控的不是身体，是神经元**：按住 `A` / `D` / `S` / 空格 = 直接驱动真实的 DNa 左 / DNa 右 / MDN / 巨纤维（和「神经元遥控」那排按钮是同一个东西），身体怎么动仍由读出 → 六条腿决定。
- **铺满窗口**（`F` 键；不是浏览器全屏）：场景盖满整个可视区，其余内容盖住。右侧栏的面板在铺满时**整个停画**；大脑和实时 spike 改成**同一个 WebGL 画面里的第二趟渲染**——大脑 = 一个 `THREE.Points`（原来是每帧在 2D 画布上逐个画 5,563 个圆），spike 图 = 一张环形写入的数据纹理。
  顺带两处提速：铺在地形上的气味 / 热的光晕不再每帧重铺（位置没变就 0.4 s 一次、错开）；五感全开时复眼视窗降到 10 fps。实测（无头 Chrome，M1 Pro）铺满 1500×900 时仍约 1.0 × 实时；时间的大头是 15,055 个神经元的大脑本身（每 5 ms 物理步约 3.2 ms）。
- 每次打开页面默认进「大自然 · 开放世界 · 五感全开」（`?scene=court|five` 可指定别的）。

### 49.5 哪些是手写的、哪些不能说

- **手写 / 手选**：地形的幅度与波长、物件的种类与密度、恢复系数 0.35、滚动阻力 0.15、坡度对步速的系数 1.2、石板升温的时间常数、天气的节奏（约每 3–6 分钟一场雨）、雨点砸中它的频率、甲虫出现的节奏、
  风对羽流形状的影响系数。这些登记在台账 PARAMETERS。重力、自由落体、纯滚动的 5/7 是物理，不是参数。
- **不能说**：「它认得石头 / 认得甲虫」——默认的视觉前端仍然是手写的逼近检测，只知道甲虫和下落的浆果这两类会动的东西；石头、草、地形起伏**没有**进到它的视觉里，它绕开石头靠的是被挡住之后贴着滑过去加上触角触碰。
  复眼视窗里那个「只靠眼睛躲」的开关（真实像素 → flyvis → LPLC2，§28）现在也接到了大自然里这一只上：打开后它确实是从像素里看世界，但那条通路有 §28.19 量过的老问题——它自己一走动，满地的草就成了「假逼近」，所以默认关。
  「没有动力学」：果蝇自己的身体仍是运动学（六条腿的支撑脚解出位移），不会摔倒、不会被风吹翻；受重力支配的是浆果和它起飞后的轨迹（真实果蝇的逃逸飞行录像）。水洼是水位，不是流体。
<!-- §49:end -->"""
p = ROOT / "docs/log/report.md"; s = p.read_text()
if "<!-- §49:begin" in s: s = re.sub(r"<!-- §49:begin.*?<!-- §49:end -->", lambda m: text, s, flags=re.S)
else: s = s.rstrip("\n") + "\n\n" + text + "\n"
p.write_text(s); print("§49 已渲染", len(text), "字")
