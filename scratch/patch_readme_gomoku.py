#!/usr/bin/env python3
"""一次性：README 补上五子棋 v2（数字从结果 JSON 读，不经过人手）。"""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; R = ROOT / "results/gomoku"
S = json.loads((R / "lines_summary.json").read_text()); A = S["train"]["arms"]; P = S["play"]; RL = S["rl"]; OL = S["opto_leak"]
pct = lambda v: f"{v * 100:.1f}%"; wl = lambda r: f"{r['win']}–{r['loss']}" + (f"–{r['draw']}" if r.get("draw") else "")
E = P["engine"]["fly_intact"]; HH = P["head_to_head"]
p = ROOT / "README.md"; s = p.read_text()
item5 = f'''**5. 训练它下五子棋：能学会，但功劳要分清。**
果蝇脑（一个突触都不训练）+ 一层线性读出，学会了给五子棋的每条线估价——14,641 种线型每一种都在脑子里跑过一遍，
它自己排出的顺序（成五 > 活四 > 冲四、活三 > …）全部正确，第一选择与深度 8 搜索一致的比例 **{pct(A['fly_intact']['test_top1'])}**（随机 {pct(S['train']['random_top1'])}、不经过脑子 {pct(A['raw24']['test_top1'])}）。
把这张表交给只懂规则的搜索，想 6 步对搜 4 步的手写老师 **{wl(E['d6']['teacher2_d4'])}**、想 10 步对搜 8 步的老师 **{wl(E['d10']['teacher2_d8'])}**。
**但**：打乱接线（{pct(A['fly_shuffled']['test_top1'])}）和同维度的随机网络（{pct(A['rand_relu']['test_top1'])}）都不输它，正面交锋 {wl(HH['d4'])}——
**真实连接组对下棋没有特殊贡献**；向前推演是搜索做的，不是果蝇。详见 [docs/log/report.md §46](docs/log/report.md)。

'''
import re
if "**5. 训练它下五子棋" in s: s = re.sub(r"\*\*5\. 训练它下五子棋.*?(?=## 它做不到什么)", lambda m: item5, s, flags=re.S)
else: s = s.replace("## 它做不到什么（同样重要）", item5 + "## 它做不到什么（同样重要）", 1)
row = f"| 自对弈强化（「多巴胺」式三因子规则）让它越下越强 | **阴性**：强化后的表对强化前 {wl(RL['final']['d4_vs_supervised_d4'])}（{pct(RL['win_rate_vs_supervised'])}，事先定的线是 55%）。而且奖励预测误差是在连接组**外面**算的——这个模型自己的多巴胺神经元不放电（[§46.7](docs/log/report.md)） |\n"
if "自对弈强化（「多巴胺」" in s: s = re.sub(r"\| 自对弈强化（「多巴胺」[^\n]*\n", lambda m: row, s)
else: s = s.replace("| 学习 / 记忆 / 可塑性 |", row + "| 学习 / 记忆 / 可塑性 |", 1)
bullet = f'''- 五子棋第一版的结论「果蝇脑几乎等于随机、连接组没有贡献」**整个作废**：给大脑换输入时上一批刺激没清掉，输入一个接一个叠上去
  （线型 A 单独是 {OL['fixed']['A_first']} 个脉冲，先喂过 B 再喂 A 是 {OL['old_behaviour']['A_after_B']:,} 个）。一个「几乎等于随机」的阴性结果，第一反应应该是查输入有没有真的送进去；
'''
if "五子棋第一版的结论" not in s: s = s.replace("- 仿真软件把随机种子编译进程序", bullet + "- 仿真软件把随机种子编译进程序", 1)
drow = "| `gomoku/` | 五子棋：线型 → 果蝇脑 → 线性读出；增量搜索引擎；老师、数据、训练、对弈与回归测试 |\n"
if "| `gomoku/` |" not in s: s = s.replace("| `language/` |", drow + "| `language/` |", 1)
# ── 五子棋专门一节（<!-- gomoku:begin/end --> 之间整段由本脚本渲染）──────────────
DM = S.get("depth_models"); NV = len(S["train"].get("feat_sets", [""]))
fi = A["fly_intact"]
dm_rows = ""
if DM:
    dm_rows = "\n| 推理步数（用哪个读出层） | 与深度 8 搜索的最佳着一致 | 对随机 | 对旧老师 | 对老师搜 1 步 | 对老师搜 2 步 |\n|---|---|---|---|---|---|\n" + "\n".join(
        f"| {d} 步 | {pct(DM['train'][d]['agree_depth8'])} | {wl(v['random'])} | {wl(v['old_teacher'])} | {wl(v['teacher2_d1'])} | {wl(v['teacher2_d2'])} |" for d, v in DM["vs"].items()) + \
        f"\n\n事先写好的判据「{DM['criterion']['text']}」→ **{'成立' if DM['criterion']['passed'] else '不成立'}**（{pct(DM['criterion']['win_rate'])}）。\n"
sec = f"""<!-- gomoku:begin （本节由 scratch/patch_readme_gomoku.py 从结果文件渲染）-->
## 五子棋：和一颗果蝇脑下棋

游戏页（[数字果蝇实验室](https://suifei.github.io/flywire-fly-lab/game.html)）顶部有两个模式标签：**篮球场**和**五子棋**。切到五子棋，球场那只果蝇连同它的世界一起冻结，
主画面换成 15×15 的棋盘，左边的三块面板（实时 spike、下行神经元、感觉输入）改为显示**正在下棋的那只果蝇**。

**怎么玩**

- 三种对局：**我 vs 果蝇**（你执黑，含连珠禁手：长连、四四、三三，禁手点会打红叉）、**果蝇自对弈**（黑白各一只，各自一份 5,563 神经元的大脑）、**果蝇 vs 老师**。
- **推理步数**（1–6、8）随时可切，立即生效——正在想的那一步也会按新设定重想。每个步数对应一个**训练出来的读出层**：
  训练时拿「向前搜 N 步得到的最佳着」当标签；**下棋时不做任何搜索**，只做模型推理。
- **思考过程画在棋盘上**：橙色圆圈 = 模型给各候选点的概率（越大越实 = 把握越大，标着百分比）；编号的虚子 = 它预想的后续（同一个模型替双方轮流往下走 N 步，一颗一颗出现）。
- **平面 / 立体**两种棋盘；立体棋盘拖动转视角、点一下落子，每一手有一只小果蝇飞过去插旗。
- **真脑核对**：每走一步，把这一步的线型放进真实的果蝇脑里现场重跑，与训练好的价值表比对（相对偏差 10⁻⁶ 量级）——这时面板上的放电就是下棋这只果蝇的。
- **外挂搜索**（默认关）：把果蝇的价值表交给 alpha-beta 搜索算法往前搜 4–14 步。**这是算法，不是果蝇**，但棋力强得多，页面上明确标着。

**它是怎么下的**

对一个候选点，沿 4 个方向各取一条线（两侧各 4 格，每格 = 空 / 我方 / 对方 / 边界）。这样的线型一共只有 14,641 种，少到可以让果蝇脑**把每一种都跑一遍**：
8 个格子 × 3 种状态 = 24 个通道，各接约 61 个真实感觉神经元，泊松驱动 300 ms，数下游神经元的脉冲（{NV} 套输入分配 × 3 个随机种子取平均）。
**脑子里一个突触都不训练**，训练的只有一层线性读出，它把放电换成这条线的对数价值；落子分 = 4 条进攻线 + λ × 4 条防守线的价值之和（每条线先取指数）。
训练分两个阶段：先把「落子评分算法」当训练数据，让读出层拟合全部线型的分值；再用 800 局、21,015 个局面上的搜索最佳着做微调。

**结果（判据都写在跑之前）**

| | |
|---|---|
| 第一选择与深度 8 搜索一致 | **{pct(fi['test_top1'])}**（随机 {pct(S['train']['random_top1'])}、不经过脑子 {pct(A['raw24']['test_top1'])}） |
| 外部考卷（Wine 引擎的 25,146 个局面，只考不训） | {pct(fi['wine_top1'])} |
| 换一组从未见过的泊松种子 | 只掉 {fi['seed_drop'] * 100:.1f} 个百分点 |
| 它自己排出的价值顺序 | 成五 > 活四 > 冲四、活三 > 眠三、活二 > 眠二，全部正确（它从没见过这些类别） |
| 外挂搜索：想 6 步 对 老师搜 4 / 6 / 8 步 | {wl(E['d6']['teacher2_d4'])} / {wl(E['d6']['teacher2_d6'])} / {wl(E['d6']['teacher2_d8'])} |
| 外挂搜索：想 10 步 对 老师搜 8 步 | {wl(E['d10']['teacher2_d8'])} |
{dm_rows}
**同样重要的三句话**

1. **真实连接组对下棋没有特殊贡献**：打乱接线（{pct(A['fly_shuffled']['test_top1'])}）与同维度的随机网络（{pct(A['rand_relu']['test_top1'])}）都不输它；能说的只是「这颗脑子是一个够用的非线性展开」。
2. **自对弈强化（「多巴胺」式三因子规则）是阴性结果**：强化后的表对强化前 {wl(RL['final']['d4_vs_supervised_d4'])}；而且奖励预测误差是在连接组外面算的——这个模型自己的多巴胺神经元不放电。
3. **五子棋第一版的全部数字已作废**：当时给大脑换输入不清上一批刺激，每个棋盘喂进去几乎是同一个输入。

复现：`AGENTS.md` 里「五子棋 v2」一段是完整命令；细节与踩过的坑见 [docs/log/report.md §46](docs/log/report.md)；改了 `gomoku/` 或 `dodge/brain.js` 之后跑 `node gomoku/test_engine.js`。
<!-- gomoku:end -->
"""
if "<!-- gomoku:begin" in s: s = re.sub(r"<!-- gomoku:begin.*?<!-- gomoku:end -->\n", lambda m: sec, s, flags=re.S)
else: s = s.replace("## 它做不到什么（同样重要）", sec + "\n## 它做不到什么（同样重要）", 1)
p.write_text(s); print("README 已更新")
