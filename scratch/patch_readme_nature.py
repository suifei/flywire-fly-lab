#!/usr/bin/env python3
"""README 的「大自然」一节（<!-- nature:begin/end -->），数字取自结果 JSON。可重复执行。"""
import json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
t = json.loads((ROOT / "results/dodge/nature_test.json").read_text())["tests"]; NL = json.loads((ROOT / "results/learn/nature_life.json").read_text()); n = NL["worlds"]["nature"]["mean"]
sec = f"""<!-- nature:begin （本节由 scratch/patch_readme_nature.py 渲染）-->
## 大自然：一个有重力、有天气、没有边界的 3D 世界

游戏页第一个标签现在默认进的是**大自然**（「世界」开关还可以切回篮球场）：按种子生成、没有边界的起伏地形，石头、深色石板、蘑菇、花、草、浆果丛、水洼，昼夜、风和雨。
物理用真实单位：重力 9,810 mm/s²——浆果熟了从枝头掉下来（30 mm 落地 {t['N1_free_fall']['t_sim']} s，解析值 {t['N1_free_fall']['t_analytic']} s）、按地形法线反弹、顺坡滚、停稳后发酵；石头不可穿透；上坡走得慢；太阳把石板晒烫；洼地下雨蓄水、晴天蒸发；风把气味吹向下风。
住在里面的是「五感全开」那只（15,055 个神经元，带蘑菇体和六条腿）。**它只通过真实的感受器知道这个世界**：坡度 → 步速，实心物件 → 挡路 + 触角被压，石板 → 温度感受器，雨 → 湿度感受器和听觉神经元，
发酵的浆果 → 嗅觉感受神经元，爬过来的甲虫 → 逼近视觉。没有新增任何一条行为规则。九条事先写好的物理判据全过（`node dodge/nature_test.js`）；在里面过 3 分钟：走 {n['path_mm']:.0f} mm、被挡住 {n['blocked_s']:.1f} s、掉下来 {n['berries']:.1f} 颗浆果、碰到糖 {n['sugar_contacts']:.1f} 次。

**玩法像「我的世界」**（画面不学它的方块，尽量拟态）：场景底部一条工具栏，数字键选、点地面用——放果子、挖水洼、放石头、种蘑菇 / 浆果丛 / 花、放甲虫、抬高 / 挖低地形、拆除；改的是同一个世界对象，所以放下的石头真的挡路、种的浆果丛真的掉果子；改动按种子存在本机。世界分草甸 / 林下 / 砾石滩 / 湿地四种生物群系。`C` 切视角（轨道 / 跟在身后 / 第一人称），按住 `A` `D` `S` 空格 = 直接驱动真实的转向 / 后退 / 巨纤维神经元。`F` 把场景铺满窗口：大脑和实时 spike 改在同一个 3D 画面里渲染，别的面板停画。

如实说明：默认的视觉前端仍是手写的逼近检测，石头和草不在它的视觉里（真实像素那条通路可选、默认关）；果蝇自己的身体是运动学，不会摔倒；威胁从「飞来的球」换成了「爬过来的甲虫」，因为毫米尺度上慢慢滚过来的球不物理。细节：[docs/log/report.md §49](docs/log/report.md)。
<!-- nature:end -->
"""
p = ROOT / "README.zh-CN.md"; s = p.read_text()
if "<!-- nature:begin" in s: s = re.sub(r"<!-- nature:begin.*?<!-- nature:end -->\n", lambda m: sec, s, flags=re.S)
else: s = s.replace("<!-- learn:begin", sec + "\n<!-- learn:begin", 1)
p.write_text(s); print("README 已更新（大自然一节）")
