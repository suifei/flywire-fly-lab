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
if "**5. 训练它下五子棋" not in s: s = s.replace("## 它做不到什么（同样重要）", item5 + "## 它做不到什么（同样重要）", 1)
row = f"| 自对弈强化（「多巴胺」式三因子规则）让它越下越强 | **阴性**：强化后的表对强化前 {wl(RL['final']['d4_vs_supervised_d4'])}（{pct(RL['win_rate_vs_supervised'])}，事先定的线是 55%）。而且奖励预测误差是在连接组**外面**算的——这个模型自己的多巴胺神经元不放电（[§46.7](docs/log/report.md)） |\n"
if "自对弈强化（「多巴胺」" not in s: s = s.replace("| 学习 / 记忆 / 可塑性 |", row + "| 学习 / 记忆 / 可塑性 |", 1)
bullet = f'''- 五子棋第一版的结论「果蝇脑几乎等于随机、连接组没有贡献」**整个作废**：给大脑换输入时上一批刺激没清掉，输入一个接一个叠上去
  （线型 A 单独是 {OL['fixed']['A_first']} 个脉冲，先喂过 B 再喂 A 是 {OL['old_behaviour']['A_after_B']:,} 个）。一个「几乎等于随机」的阴性结果，第一反应应该是查输入有没有真的送进去；
'''
if "五子棋第一版的结论" not in s: s = s.replace("- 仿真软件把随机种子编译进程序", bullet + "- 仿真软件把随机种子编译进程序", 1)
drow = "| `gomoku/` | 五子棋：线型 → 果蝇脑 → 线性读出；增量搜索引擎；老师、数据、训练、对弈与回归测试 |\n"
if "| `gomoku/` |" not in s: s = s.replace("| `language/` |", drow + "| `language/` |", 1)
p.write_text(s); print("README 已更新")
