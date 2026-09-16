# flywire-fly-lab

**把果蝇全脑连接组跑在一台 16 GB 笔记本上，接上身体，做成游戏，再对它做 17,628 次虚拟手术。**
完整记录能做到什么、**做不到什么**，以及作者自查出的每一处错误。

> A complete, reproducible attempt to run the *Drosophila* whole-brain connectome on a laptop:
> wire it to a physics body, ship it as a browser game, and run a 17,628-segment virtual knockout
> screen across three sensory pathways. Every negative result and every self-caught mistake is
> documented. Docs are in Chinese; code comments are in Chinese; issues in English are welcome.

[**▶ 在线试玩（浏览器里 4,599 个真实神经元实时放电）**](https://suifei.github.io/flywire-fly-lab/game.html) · [**完整报告 report.md**](report.md) · [**数据许可 ⚠**](DATA_LICENSE.md)

---

## 这是什么

2024 年，FlyWire 公布了果蝇成虫大脑的完整连接组；Shiu、Sterne 等人在其上建立了一个全脑漏积分发放（LIF）模型；Eon Systems 把它开源。

本仓库是**一次完整的复现 + 延伸**，全部在一台 16 GB M1 Pro MacBook 上完成：

| | |
|---|---|
| 模型规模 | 138,639 个神经元、15,091,983 条带权连接，dt = 0.1 ms |
| 跑一秒大脑 | 约 2.5 秒，峰值内存 3–4 GB |
| 虚拟敲除筛选 | **17,628 段**全脑仿真，9.88 小时机时，3 条感觉通路 |
| 浏览器里的子回路 | 4,599 个神经元、338,837 条连接（全脑的 3%），比实时快 13 倍 |

## 主要结论

**1. "这个模型准不准"这个问法是错的——它的可信度是局部的。**
同一套参数、同一个判定门槛，在三条通路上与论文的一致性（Cohen κ，已去掉蒙对成分）差别很大：

| 通路 | κ | 对真实光遗传实验 |
|---|---|---|
| 糖味觉 → 伸喙 | 0.59 | 6 / 10 |
| 水味觉 → 伸喙 | **0.87** | **9 / 10** |
| 触角机械感觉 → 梳理 | **0.91** | 1 / 1（可测） |

**2. 冗余结构光看连线图预测不出来。**
事先声明的假设是"互为备份 = 到输出的图上路径各走各的"。实测相关系数 **−0.008（糖）/ +0.013（水）**——不是弱相关，是零，且已排除指标退化。**要知道两个神经元是不是互为备份，只能真的一起敲掉跑一遍。**

**3. 同一个动作，背后是两套线路。**
糖和水都通过同一个运动神经元 MN9 引发伸喙，但活跃神经元只重叠三分之一，枢纽各自私有：`CB0883` 在水通路里根本不放电，`CB0051` 在糖通路里敲了毫无影响。抑制性神经元 `Phantom` 敲掉后水通路输出**翻 3 倍**。

**4. 事先声明的"集中度 → 可预测性"假设，被自己的数据推翻。**
JON 通路最集中（基尼 0.922），却是只看连线**最预测不了**的（G3 0.288 < 糖的 0.316）。详见 [report.md §22.2](report.md)。

## 它做不到什么（同样重要）

| 想做的事 | 实际结果 |
|---|---|
| 从感光细胞（R1-6/R7/R8）驱动行为 | 下行神经元**全部 0 Hz**，信号传不过去；必须从 LC4 这类视觉投射神经元注入 |
| 吃到糖产生奖赏信号 | 307 个 PAM 多巴胺神经元**一个都不放电**。这个模型里没有奖赏，也谈不上学习 |
| 腹神经索产生走路节律 | 有节律，但凑不出三角步态；六条腿里实际只有一条在动 |
| 闻到气味往哪边转 | 单侧刺激给不出左右差异；刺激稍强，约 8,300 个神经元一起失控放电 |
| 学习 / 记忆 / 可塑性 | 模型里根本没有，突触权重固定 |
| 闭环行为（大脑 + 身体） | **仍未验证**。视觉前端已单独验证（[§26](report.md)），但加载大脑后的行为没有结论 |

## 作者自查出的错误

[report.md §23](report.md) 里有一份**错误账本**，记录所有自己发现、又自己改掉的错误，不删。两轮逐数字核对（对照结果文件）共查出 **28 处**问题，其中：

- 仿真软件把随机种子编译进程序，导致"跑了 4 次"其实是同一次的 4 份拷贝 → 34 个实验重跑；
- 一张表里的 "2/2 准确率" 是**手写的字符串**，其中一个神经元**从来没有被测过** → 改为 "1/1 可测"；
- 刚写完"一致率是骗人的、要看 κ"，自己引用的 κ 就连填错两次（口径混用）。

约 300 个由脚本自动产出的数字全部无误——**错误几乎全部集中在手写的汇总与跨章节引用上**。所以现在网页上的表格一律从结果文件读取，不写死。

## 快速开始

```bash
# 1. 环境（三个 conda 环境不能合并，见 CLAUDE.md）
bash setup.sh cpu        # brain-fly-cpu：Brian2 + numpy 1.26
bash setup.sh flygym     # flygym：FlyGym 2.1 + torch

# 2. 获取上游项目（本仓库不再分发它们，见 DATA_LICENSE.md 第 4 节）
git clone https://github.com/eonsystemspbc/fly-brain external/fly-brain
# FlyWire 注释表、Shiu 补充材料等的获取方式见 CLAUDE.md

# 3. 最小实验：刺激糖味觉神经元，看伸喙运动神经元 MN9
conda activate brain-fly-cpu
python run_experiment.py --preset sugar --t_run 1
#   → 398 个活跃神经元；MN9 左 98 Hz / 右 69 Hz；其余下行神经元全 0

# 4. 本地打开游戏
python3 dodge/build.py && open results/dodge/fly_dodge.html
```

完整命令清单（虚拟敲除筛选、腹神经索、视觉管线、"果蝇说中文"等）见 [`CLAUDE.md`](CLAUDE.md)。

## 目录

| 路径 | 内容 |
|---|---|
| `run_experiment.py` | 最小实验：激活 / 沉默 / 记录，Brian2 与 PyTorch 两个后端 |
| `dodge/` | 子回路裁剪、JS 实时大脑引擎、游戏逻辑与页面 |
| `screen/` | 虚拟敲除筛选（三条通路、双敲除、枢纽全扫描、集中度分析） |
| `vnc/` | 腹神经索：BANC LIF、Pugliese 发放率模型、完整 MANC、本体感觉闭环 |
| `vision/` | 复眼 → flyvis → 全脑连接组的离线视觉管线 |
| `language/` | "果蝇说中文"：12 个词的解码器 + 脑机接口压力测试 |
| `flight/` | flybody 飞行控制器回放，导出真实逃逸飞行轨迹 |
| `report.md` | **完整报告**，约 6.5 万字，含全部结果、阴性结果与错误账本 |
| `CLAUDE.md` | 工程笔记：环境、命令、内存安全规则、领域陷阱 |

## 许可

- **代码**：[GPL-3.0-or-later](LICENSE)（因为 import 了 Eon 的 GPL-2.0-or-later 代码）
- **`results/` 下的数据**：**不适用 GPL**。其中含 FlyWire 连接组派生数据，**按 CC BY-NC 4.0 处理——不得商用**。详见 [**DATA_LICENSE.md**](DATA_LICENSE.md)，用之前请务必读一遍。
- 引用请引原始论文，不要只引本仓库；文献列表在 [DATA_LICENSE.md §3](DATA_LICENSE.md)。

## 一句话说明

> 拿到一个大脑的全部接线图，和知道怎么在这张图上开车，是两件事。
> 这个仓库记录的是我开着它撞了多少次墙。
