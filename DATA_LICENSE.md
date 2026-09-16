# 数据许可与使用限制 / Data licence and restrictions

> **⚠️ 这个仓库不是单一许可证的仓库。**
> **代码**（`*.py`、`*.js`、`*.sh`、模板 HTML）按 **GPL-3.0-or-later** 发布，见 [`LICENSE`](LICENSE)。
> **`results/` 下的数据**不适用 GPL——它们派生自第三方数据集，条款见下表。
> **其中含 FlyWire 连接组的派生数据，按 CC BY-NC 4.0 处理：可以自由研究、教学、改编，但不得用于商业目的。**

> **⚠️ This repository is not under a single licence.**
> Code is **GPL-3.0-or-later**. Data under `results/` is **not** — it is derived from third-party
> datasets, most importantly the FlyWire connectome, and is redistributed here **for
> non-commercial use only (CC BY-NC 4.0)**. See the table below.

---

## 1. 仓库里的数据分别来自哪里

| 文件 | 派生自 | 条款 | 商用 |
|---|---|---|---|
| `results/dodge/subcircuit_v2.json`<br>`results/dodge/subcircuit.json` | **FlyWire v783 连接组**（4,599 个神经元、338,837 条连接，从全脑裁剪而来）+ flyconnectome 注释表 | 按 **CC BY-NC 4.0** 处理（见第 2 节说明） | ❌ 禁止 |
| `results/dodge/fly_dodge.html` | 同上（连接组数据内联在页面里） | 同上 | ❌ 禁止 |
| `results/screen/**/*.json`<br>`results/vnc/**/*.json`<br>`results/language/*.json` | 在 FlyWire 连接组上做仿真得到的**测量结果**（发放率、比值、统计量），含 FlyWire root ID | 同上 | ❌ 禁止 |
| `results/flight/flight_clips.json` | **flybody** 的 figshare 数据集（Vaxenburg et al. 2025）：真实果蝇逃逸飞行轨迹 + 训练好的飞行控制器输出 | **GPL-3.0-or-later** | ✅ 需同样开源 |
| `results/dodge/gait.json`<br>`results/dodge/poses.json` | **NeuroMechFly / FlyGym** 物理仿真录制 | **Apache-2.0** | ✅ 需署名 |
| `results/vision/*.json` | **flyvis** 预训练视觉网络（Lappalainen et al. 2024）的输出 + FlyWire 仿真 | flyvis 为 MIT；合并结果含 FlyWire 派生数据 → 按 CC BY-NC 处理 | ❌ 禁止 |

## 2. 关于 FlyWire 许可证的一个诚实说明

FlyWire 的服务条款写明**用户提交的编辑与注释以 CC BY-NC 4.0 发布**。但 **v783 数据发布包本身的许可证，我没能确认**——Codex 的 FAQ 没有写明，Zenodo 页面访问超时。

因此本仓库**按最严格的一种解释处理**：把全部 FlyWire 派生数据视为 **CC BY-NC 4.0**（署名、非商用）。

**如果你要商用，请先写信给 `flywire@princeton.edu` 确认**，不要依赖本仓库的判断。
如果 FlyWire 方面认为本仓库的再分发方式不妥，请开 issue 或直接联系，我会立即移除相关文件。

## 3. 必须的引用

用到本仓库的数据或结论时，请引用**原始工作**，而不只是本仓库：

```
Dorkenwald, S. et al. (2024). Neuronal wiring diagram of an adult brain. Nature 634, 124–138.
Schlegel, P. et al. (2024). Whole-brain annotation and multi-connectome cell typing of Drosophila. Nature 634, 139–152.
Shiu, P. K., Sterne, G. R. et al. (2024). A leaky integrate-and-fire computational model based on
    the connectome of the entire adult Drosophila brain reveals insights into sensorimotor processing. Nature 634, 210–219.
Vaxenburg, R. et al. (2025). Whole-body physics simulation of fruit fly locomotion. Nature.
Lappalainen, J. K. et al. (2024). Connectome-constrained networks predict neural activity across the fly visual system. Nature 634, 1132–1140.
Wang-Chen, S. et al. (2024). NeuroMechFly v2: simulating embodied sensorimotor control in adult Drosophila. Nature Methods.
```

## 4. 本仓库**没有**包含、也不会包含的东西

`.gitignore` 里 `external/` 被整个排除。那里面是以下项目的完整克隆，本仓库**只在本地 import 它们，绝不复制或再分发其代码**：

| 项目 | 许可证 | 为什么不发 |
|---|---|---|
| `eonsystemspbc/fly-brain` | GPL-2.0-or-later | 请从上游获取；本仓库只 import |
| `neilt93/Fly-Brain-AI` | **无许可证** | 无许可证 = 保留全部权利，**不得再分发** |
| `smpuglie/Pugliese_cpg_2025` | **无许可证** | 同上 |
| FlyWire 全脑连接组原始包 | 见第 2 节 | 体积 1.5 GB，且应从官方渠道获取 |
| flyconnectome 注释表 | 未声明 SPDX | 请从上游获取 |

跑完整流程需要自己按 [`README.md`](README.md) 的说明获取这些上游项目。

## 5. 免责

本文件是作者对各上游条款的**善意理解**，**不构成法律意见**。任何商业用途请自行核实并咨询律师。
