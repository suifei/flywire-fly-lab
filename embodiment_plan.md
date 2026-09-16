# 具身化路线：让 FlyWire 数字大脑“看见、思考、行走”

> 基于 2026-09-13 的核实与本机实测（M1 Pro 16 GB）。**【实测】** 本机跑过；**【官方】** Eon 公开的内容；**【社区】** 第三方项目；**【推测】** 未验证的判断

## 1. 现状一句话

Eon **没有公开**大脑→身体的接口代码。可用的积木有三块：
- **【官方】** 大脑：eonsystemspbc/fly-brain，GPL-2.0-or-later。
- **【社区】** 身体、3D 世界、复眼：FlyGym 2.1，Apache-2.0。
- **【推测】** 接口：参照 Eon 官网描述（下行神经元当“控制把手”，每 15 ms 同步一次）自己写。

## 2. 实测得到的几个硬约束（决定了路线怎么走）

| 约束 | 证据 |
|---|---|
| 视觉不能从光感受器注入 | 激活 4,044 个 R1-6 或 1,330 个 R7/R8 → 0.2 s 内所有 DN/MN 都是 0 Hz；激活 54 个左 LC4 → 巨纤维 85/40 Hz、DNa01 30 Hz（`results/vis_*`） |
| CPU 上 Brian2 最快，但不能边跑边改输入 | Brian2 standalone：1 s 大脑时间约 2.5 s；PyTorch CPU：0.1 s 要 45 s；PyTorch MPS：1 s 约 130 s（每 0.1 ms 步约 13 ms）。闭环需要逐窗改刺激频率，只能用 PyTorch |
| FlyGym 2.1 API 与网上 1.x 教程不兼容 | 没有 `SingleFlySimulation`、`Fly(enable_vision=True)`；实际要用 `make_locomotion_fly` + `fly.add_vision()` + `Simulation` + `HybridTurningController.step([L, R], obs)` |
| 转向驱动的方向 | `[1.2, 0.4]`（左强右弱）→ **向右转** |
| 左右侧命名有冲突 | 官方 notebook 的 left/right 与 FlyWire 注释表 `side` 相反（P9、DNa01、DNa02、MN9） |
| 身体侧预编程了步态 | FlyGym 的 HybridTurningController = CPG + 预录步态 + 规则反射。大脑只决定左右“幅度”，与 Eon 做法一致，也是 Carboncopies 批评的点 |
| 内存 | 大脑 + 身体同进程峰值约 2.5–4 GB；不要一次激活成千上万个神经元再用官方 `poi()`（已踩坑死机，见 report.md 2.3 报错 4） |

## 3. 三条路线（按难度从低到高）

### 路线 C：开环刺激，先把“大脑侧”搞明白 ★ 难度低，**现在就能做**【实测可行】

**做什么**
- 用 `run_experiment.py` 做激活/沉默实验，建立“输入神经元 → 下行神经元发放率”的查找表。例如：
  - 糖 → MN9
  - P9 → oDN1/DNa02
  - LC4 左/右 → GF、DNa01/02
  - 触角 JO → aDN1
- 把查找表回放到 FlyGym：DN 频率 → `[L, R]` 驱动 → 录一段行走视频。**大脑和身体不同时运行。**

**产出**
- 每种“刺激 → 行为”一张图加一段视频。
- 能验证映射方向，例如 LC4 左 → 往右逃。

**优点**
- 用 Brian2 CPU，速度快。
- 大脑和身体分开跑，没有 GPL/Apache 组合问题。
- 内存占用小。

**缺点**
- 没有反馈：身体动了，视觉输入不会跟着变。

**命令**
```bash
conda activate brain-fly-cpu
python run_experiment.py --exc_type LC4:left  --rate 100 --t_run 0.5 --out results/lc4_L
python run_experiment.py --exc_type LC4:right --rate 100 --t_run 0.5 --out results/lc4_R
# 读 results/lc4_*/readout.csv → 手写映射 → 用 flygym_vision_demo.py 里的 HybridTurningController 回放
```

### 路线 B：FlyGym 身体 + FlyWire 大脑，闭环，视觉只走 LC 通路 ★★ 难度中，**推荐**【原型已写，未验证】

**做什么**：就是 `connectome_vision_loop.py`。

```
FlyGym 复眼 (2×721) → [视觉前端] 每侧 looming/物体位置特征 → LC4 / LC10a / LPLC2 的 Poisson 频率
    → 全脑 LIF（官方 TorchModel，每 15 ms 推进 150 步）
    → 读出 DNa01/DNa02(左右) · DNg97=oDN1 · DNp01=GF · MDN
    → 映射：前进 = f(oDN1)，转向 = g(DNa 右 − DNa 左)，GF > 阈值 → 逃逸（FlyGym 行走模型不能起飞，先用冻结/后退占位）
    → HybridTurningController.step([L, R]) → MuJoCo
```

**实施步骤**

1. **修视觉前端（冒烟测试暴露的问题）**：
   - 现在用“整只眼暗面积增长率”，会被自己的腿干扰，远处的球还没来 LC4 就被打满到 200 Hz。
   - 改法：只取上半视野的小眼，按 `retina.ommatidia_id_map` 的行坐标筛选；排除自身肢体；增长率加阈值和低通滤波。
   - 再进一步：按 LC4 的视网膜位置（注释表的空间坐标 / flyvis 的柱位置）分块，给不同 LC4 不同频率，而不是整侧同一个频率。
2. **统一左右侧**：
   - 以注释表 `side` 为准。
   - 先用路线 C 的开环数据确认 “LC4 左 → 哪侧 DNa” 以及方向是否合理。
3. **跑正式对比（每个 1 s，MPS 上约 2–3 分钟，峰值约 3–4 GB）**：
   - `--no-looming` 对照
   - 左侧逼近
   - 右侧逼近
   - 沉默 GF / LC4 的“损毁”对照：给脚本加 `--silence`，复用 `run_experiment.py` 按 parquet 置零权重的逻辑
4. **加更多通路**（都已在官方 notebook 里有 ID，可直接复用）：
   - 触角 JO → aDN1 → 梳理（FlyGym 需要自写前腿梳理动作）
   - 糖 GRN → MN9 → 伸喙（需要带喙关节的身体模型）

**优点**
- 真·连接组在环。
- 所有组件都开源，而且本机已装好。

**缺点**
- 慢（MPS 上约 0.007× 实时；有 NVIDIA GPU 会快很多，未测）。
- 视觉前端和 DN→腿的映射是手写的。
- 同进程里组合了 GPL 与 Apache 代码：自己用没问题，分发时整体按 GPLv3。**【推测，非法律意见】**

**提速选项（按投入从小到大）**
- 只在窗口末尾同步 GPU（原型已这样做）。
- 把大脑放在另一台 NVIDIA 机器上，通过 ZeroMQ 与身体进程通信，顺带解决许可证组合问题。
- 用 GeNN/Brian2CUDA 的逐步推进接口。**【未验证是否支持在线改输入】**

### 路线 A：复刻 Eon 完整做法（flyvis 视觉 + LIF 大脑 + NeuroMechFly 多行为） ★★★ 难度高

**做什么**
- 用 **flyvis**（TuragaLab，MIT；Lappalainen et al. 2024，64 种视觉细胞类型）把 FlyGym 复眼图像转成 T4/T5/LC 等细胞的活动，替换路线 B 的手写视觉前端。Eon 官网说明他们就是这么做的。
- flyvis 用的六边形柱坐标与 FlyGym 的 721 小眼要做一次空间对齐。flyvis 自带六边形刺激渲染工具，FlyGym 也提供 `hex_pxls_to_human_readable`。
- flyvis 输出的是连续活动。要转成 FlyWire 里对应 root ID 的 Poisson 频率，需要做 flyvis 细胞类型 → FlyWire cell_type/root ID 的匹配（注释表的 `cell_type`）。
- 多行为：行走 + 转向 + 梳理 + 进食 + 逃逸，要在 FlyGym 里补梳理/伸喙动作，还要一个行为选择状态机（Eon 也是这样做的）。

**难点**
- 视觉模型与连接组的时间尺度、坐标系对齐。
- 算力：flyvis + 13.9 万神经元 LIF + MuJoCo，基本需要 NVIDIA GPU。
- 行为控制器的手工部分很多。

**社区参考**：erojasoficial-byte/fly-brain 做了类似的多模式状态机，但基于 FlyGym 1.x，许可证存疑；只建议**读思路，不要直接复制代码**。

## 4. 推荐

1. **本周**：做路线 C。已经可以做，而且能先把“左右约定 + DN→转向方向”这两个最容易出错的问题验证清楚。
2. **接下来**：做路线 B，第一步修视觉前端，然后跑 4 组 1 s 对比（每组约 2–3 分钟，不要并行跑，16 GB 内存一次跑一个）。
3. **有 NVIDIA GPU 再考虑**路线 A；或者先只把 flyvis 接到路线 B 的视觉前端。

## 5. 你之前那份方案的更正

| 原说法 | 实测 / 核实结果 |
|---|---|
| “Eon 大脑的视觉输入对应 R1–R6 和 R8 光感受器” | FlyWire v783 确实包含 R1-6（模型中 7,932 个）、**R7**（1,336 个）、R8（1,314 个）。但在这个 LIF 模型里激活它们**驱动不了任何下行神经元**；Eon 官网写的是用 Lappalainen 视觉模型的预测接入 LIF |
| “FlyGym 提供复眼视觉，每步作为 observation 返回” | FlyGym 2.1 需要显式调用 `sim.get_ommatidia_readouts(fly_name)`；它不再是 Gymnasium 环境，没有 `obs` 字典 |
| “FlyGym 的视觉来自 Lappalainen 模型” | 不对。FlyGym 的 `Retina` 只做图像到小眼的采样和鱼眼校正，**不含**神经网络模型；Lappalainen 模型是独立的 flyvis 项目 |
| “先装 FlyGym 跑通视觉 demo” | 已完成：`flygym_vision_demo.py`，趋向 / 回避 / 盲走三组对比 |
| “FlyWire 视网膜神经元坐标数据公开” | 注释表里有每个神经元的 `pos_x/y/z` 与 `soma_x/y/z`（已下载）；是否有专门的眼平面投影坐标，未核实 |

## 6. 后续补充（2026-09-14，详见 report.md 第 10–11 节）

- **腿**：大脑 → 腿这一段，BANC 腹神经索配全脑同款 LIF 参数时没有迈步节律。换成 Pugliese et al. 2025 的腹神经索发放率模型（社区代码，无许可证，只本机调用）后，前进指令 DNg100 能产生约 11 Hz 的运动神经元节律，左前腿会跟着节律摆动。但只有 2–4 个运动神经元参与，幅度约为 CPG 的 1/4，左右不交替，**还不能替代 CPG**。路线 B 的行走暂时仍用 FlyGym 的 CPG 控制器。
- **嗅觉**：LIF 全脑里嗅觉输入是全或无的失控，给不出左右转向信号。路线 B 若要做气味导航，只能手写。
- **学习**：模型没有可塑性，吃糖也激活不了奖赏多巴胺神经元。如果要“会学习的果蝇”，最贴近生物的做法是在蘑菇体子回路上加多巴胺门控可塑性（Kenyon 细胞 → MBON）。这需要额外手写学习规则和奖赏注入。
- **强化学习训练身体**：flybody 论文训练需要 10⁸–10⁹ 仿真步，用的是多 CPU + GPU 并行。按本机实测步进速度线性估算，从零训练要几天到几周。实际做法应是下载论文公开的训练好的控制器。
