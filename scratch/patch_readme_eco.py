#!/usr/bin/env python3
"""README 的「生态箱」一节（<!-- eco:begin/end -->），数字取自 results/eco/summary.json。可重复执行。"""
import json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
S = json.loads((ROOT / "results/eco/summary.json").read_text()); m2, m3, m4, lv, sf, au = (S[k] for k in ("m2", "m3", "m4", "live", "surface", "audit")); i0 = m2["individuals"][0]; lg = S["long"]; tr = S["transfer"]; mf = sf["manifold"]
sec = f"""<!-- eco:begin （本节由 scratch/patch_readme_eco.py 渲染）-->
## 生态箱：你只设计世界，它自己学、自己进化

**[打开生态箱 →](https://suifei.github.io/flywire-fly-lab/ecobox.html)**（[docs/ecobox.html](docs/ecobox.html)，单文件，离线可用）

一个无人值守的圆形玻璃箱：会烂的食物、会干的水洼、昼夜冷热、风、雨、甲虫。你**不给果蝇下任务**，也**改不了奖励**——奖励只是它身体六种内部状态（饥饿、口渴、体力、健康、气味、体温）离舒适点的距离变小了。你能改的只有世界规则。

| 层 | 是什么 | 谁能改 |
|---|---|---|
| 世界规则 | 食物、水、冷热、风雨、甲虫、地形 | 你 |
| 基因（10 个数） | 学习率、探索、飞行倾向、偏好体温、代谢、警觉度、四个先天偏置 | 进化 |
| 可塑性层 | 接在大脑旁边的可变权重，给先天反射加偏置 | 这只果蝇的一生，**不遗传** |
| 连接组 | {au['n_neurons']:,} 个神经元，逃逸、伸喙、转向、后退这些反射是它自带的 | **没有人** |

- **单只学习**：同一只连续 {m2['train_lives']} 条命后冻结学习，在没见过的世界里测——不学习 {i0['off']} s，学过的 ≥ {i0['on']} s（× {i0['ratio_on']}，截尾）；打乱奖励时序的对照不提升；换 10 个个体 {m2['robust_learned']}/{m2['robust_n']} 学成；**长期训练任务再换 10 个新个体：{lg['n_learned']}/{lg['n']} 学成，换新世界复测 {lg['n_retest_ok']}/{lg['n']}**（`node eco/train_long.js`，共 {lg['total_lives']} 条命）。
  它学到的是「碰到水就停下来喝」（连接组里水味只把伸喙神经元推到十几 Hz，先天不够）和「湿度上升时少拐弯」。**没学会**远距离找水：干旱世界里 {m2['drought_on']} s 对 {m2['drought_off']} s。
- **32 只进化**：没有适应度函数，吃饱喝足的才攒得出卵。{'；'.join(f"{w['name']}：寿命 {w['life_head']} → {w['life_tail']} s，飞行倾向{w['label']}" for w in m3['worlds'])}。事先写定的判据（不同世界把飞行倾向推向不同方向）{'通过' if m3['pass'] else '**未通过**'}。
  飞行是**可决策**的技能：起不起飞它说了算，怎么飞是固定弹道——飞行控制没接进连接组，不假装它能学会飞。
- **发现卡**：躺平、贴着玻璃走、原地打转、守着食物不走……奖励作弊和失败都会被抓出来、配上证据。你来选：接受它现在的活法，或者改世界，逼它换一种。
- **存档就是一份训练成果**：世界规则 + 世代时间线 + 每只果蝇的权重 + 发现卡 + 回放。读回来接着跑与不中断逐位相同；挑战码（{m4['code_chars']} 个字符）发给别人就能在同一个世界里开局。
- 页面里跑的是真脑的**响应面**（真脑一只才 {au['realtime_one']} 倍实时）：{sf['n_samples']:,} 组真脑采样拟合，留出 R² 转向 {sf['features'][0]['r2']:.2f} / {sf['features'][1]['r2']:.2f}、巨纤维 {sf['features'][2]['r2']:.2f}。学成的个体放回真脑复核：{lv['live_median']} s 对白纸 {lv['naive_median']} s（管用）；真脑里喝水的时间占比是响应面的 {lv['drink_ratio']} 倍，事先定的「行为量级一致」（0.5–2 倍）{'通过' if lv['L2'] else '**没过**——响应面是蒸馏，不是真脑'}。

- **搬进 3D 大自然**：训练条件先对齐到大自然（同一套感觉编码；响应面加上闭环工况，只尝到水的 MN9 误差从约 40% 降到 {100 * mf['points'][0]['rel_err']:.1f}%），学成的个体冻结权重放进实验室页的大自然（真脑）：{tr['n_informative']} 个有信息的种子里喝得更久 {tr['X1']['more_drink_time']}、更不渴 {tr['X2']['lower_mean_thirst']}，事先写定的判据{'通过' if tr['pass'] else '**未通过**'}。实验室页「生活」的大自然里可以「载入生态箱存档」。

如实说明：连接组一个突触都没变，学习发生在手写的可塑性层里；「看不到大脑输出」的对照学得一样好——在这个任务里连接组给的是身体和反射，不是学习信号。计划、审计、全部实测：[docs/ecobox/](docs/ecobox/)，日志 [§50](docs/log/report.md)。
<!-- eco:end -->
"""
p = ROOT / "README.md"; s = p.read_text()
if "<!-- eco:begin" in s: s = re.sub(r"<!-- eco:begin.*?<!-- eco:end -->\n", lambda m: sec, s, flags=re.S)
else: s = s.replace("<!-- nature:begin", sec + "\n<!-- nature:begin", 1)
p.write_text(s); print("README 已更新（生态箱一节）")
