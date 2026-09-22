# 数据许可与使用限制 / Data licence and restrictions

> **⚠️ 这个仓库不是单一许可证的仓库。**
> **代码**（`*.py`、`*.js`、`*.sh`、模板 HTML）按 **GPL-3.0-or-later** 发布，见 [`LICENSE`](LICENSE)。
> **`results/` 下的数据**与**构建出来的页面**不适用 GPL——它们派生自第三方数据集，条款见下表。
> **其中含 FlyWire 连接组的派生数据，按 CC BY-NC 4.0 处理：可以自由研究、教学、改编，但不得用于商业目的。**

> **⚠️ This repository is not under a single licence.**
> **Code** (`*.py`, `*.js`, `*.sh`, template HTML) is **GPL-3.0-or-later**; see [`LICENSE`](LICENSE).
> **Data under `results/`** and the **built pages** are **not** GPL — they are derived from third-party datasets, terms below.
> **Data derived from the FlyWire connectome is treated as CC BY-NC 4.0: free to study, teach and adapt, but not for commercial use.**

---

## 1. 仓库里的数据分别来自哪里 / Where the data comes from

| 文件 / Files | 派生自 / Derived from | 条款 / Terms | 商用 / Commercial use |
|---|---|---|---|
| `results/dodge/subcircuit*.json`、`results/dodge/soma.json` | **FlyWire v783 连接组**（从全脑裁剪出的子回路、胞体坐标）+ flyconnectome 注释表<br>**FlyWire v783 connectome** (sub-circuits cut from the whole brain, soma positions) + flyconnectome annotations | 按 **CC BY-NC 4.0** 处理（见第 2 节）<br>treated as **CC BY-NC 4.0** (see §2) | ❌ 禁止 / not allowed |
| `results/dodge/fly_dodge.html`、`docs/game.html`、`docs/ecobox.html` | 同上：页面里内联了连接组子回路，或由它拟合出的响应面<br>Same: the pages inline connectome sub-circuits, or a response surface fitted to them | 同上 / same | ❌ 禁止 / not allowed |
| `results/screen/`、`results/language/`、`results/learn/`、`results/gomoku/`、`results/eco/`、`results/dodge/` 下的其余 `*.json` | 在 FlyWire 连接组上做仿真得到的**测量结果**（发放率、比值、统计量、拟合的模型），多数含 FlyWire root ID<br>**Measurements** from simulations on the FlyWire connectome (firing rates, ratios, statistics, fitted models), mostly containing FlyWire root IDs | 同上 / same | ❌ 禁止 / not allowed |
| `results/vnc/` | **MANC / BANC** 腹神经索连接组上的仿真结果；按同样最严格的口径处理<br>Simulations on the **MANC / BANC** ventral-nerve-cord connectomes; treated just as strictly | 按 **CC BY-NC 4.0** 处理<br>treated as **CC BY-NC 4.0** | ❌ 禁止 / not allowed |
| `results/vision/*.json` | **flyvis** 预训练视觉网络（Lappalainen et al. 2024）的输出 + FlyWire 仿真<br>Outputs of the pretrained **flyvis** network + FlyWire simulations | flyvis 为 MIT；合并结果含 FlyWire 派生数据 → 按 CC BY-NC 处理<br>flyvis is MIT; combined results include FlyWire-derived data → CC BY-NC | ❌ 禁止 / not allowed |
| `results/flight/flight_clips.json` | **flybody** 的 figshare 数据集（Vaxenburg et al. 2025）：真实果蝇逃逸飞行轨迹 + 训练好的飞行控制器输出<br>The **flybody** figshare dataset: real escape-flight trajectories + trained flight-controller outputs | **GPL-3.0-or-later** | ✅ 需同样开源 / copyleft |
| `results/dodge/gait.json`、`results/dodge/poses.json` | **NeuroMechFly / FlyGym** 物理仿真录制<br>Recorded **NeuroMechFly / FlyGym** physics simulations | **Apache-2.0** | ✅ 需署名 / attribution |

## 2. 关于 FlyWire 许可证的一个诚实说明 / An honest note on the FlyWire licence

FlyWire 的服务条款写明**用户提交的编辑与注释以 CC BY-NC 4.0 发布**。但 **v783 数据发布包本身的许可证，我没能确认**——Codex 的 FAQ 没有写明，Zenodo 页面访问超时。
因此本仓库**按最严格的一种解释处理**：把全部 FlyWire 派生数据视为 **CC BY-NC 4.0**（署名、非商用）。

FlyWire's terms of service state that **user-submitted edits and annotations are released under CC BY-NC 4.0**. I could **not confirm the licence of the v783 data release itself** — the Codex FAQ does not say, and the Zenodo page timed out.
This repository therefore **takes the strictest reading** and treats all FlyWire-derived data as **CC BY-NC 4.0** (attribution, non-commercial).

**如果你要商用，请先写信给 `flywire@princeton.edu` 确认**，不要依赖本仓库的判断。如果 FlyWire 方面认为本仓库的再分发方式不妥，请开 issue 或直接联系，我会立即移除相关文件。
**For commercial use, write to `flywire@princeton.edu` first** rather than relying on this repository's reading. If FlyWire considers this redistribution inappropriate, please open an issue or get in touch and the files will be removed immediately.

## 3. 必须的引用 / Required citations

用到本仓库的数据或结论时，请引用**原始工作**，而不只是本仓库：
If you use data or conclusions from this repository, please cite the **original work**, not only this repository:

```
Dorkenwald, S. et al. (2024). Neuronal wiring diagram of an adult brain. Nature 634, 124–138.
Schlegel, P. et al. (2024). Whole-brain annotation and multi-connectome cell typing of Drosophila. Nature 634, 139–152.
Shiu, P. K., Sterne, G. R. et al. (2024). A leaky integrate-and-fire computational model based on
    the connectome of the entire adult Drosophila brain reveals insights into sensorimotor processing. Nature 634, 210–219.
Vaxenburg, R. et al. (2025). Whole-body physics simulation of fruit fly locomotion. Nature.
Lappalainen, J. K. et al. (2024). Connectome-constrained networks predict neural activity across the fly visual system. Nature 634, 1132–1140.
Wang-Chen, S. et al. (2024). NeuroMechFly v2: simulating embodied sensorimotor control in adult Drosophila. Nature Methods.
```

## 4. 本仓库**没有**包含、也不会包含的东西 / What this repository does **not** contain

`.gitignore` 里 `external/` 被整个排除。那里面是以下项目的完整克隆，本仓库**只在本地 import 它们，绝不复制或再分发其代码**：
`external/` is excluded entirely by `.gitignore`. It holds full clones of the projects below; this repository **only imports them locally and never copies or redistributes their code**:

| 项目 / Project | 许可证 / Licence | 为什么不发 / Why it is not shipped |
|---|---|---|
| `eonsystemspbc/fly-brain` | GPL-2.0-or-later | 请从上游获取；本仓库只 import / get it upstream; imported only |
| `neilt93/Fly-Brain-AI` | **无许可证 / none** | 无许可证 = 保留全部权利，**不得再分发** / no licence = all rights reserved, **must not be redistributed** |
| `smpuglie/Pugliese_cpg_2025` | **无许可证 / none** | 同上 / same |
| FlyWire 全脑连接组原始包 / FlyWire whole-brain release | 见第 2 节 / see §2 | 体积 1.5 GB，且应从官方渠道获取 / 1.5 GB, and should come from the official source |
| flyconnectome 注释表 / flyconnectome annotations | 未声明 SPDX / no SPDX identifier | 请从上游获取 / get it upstream |

跑完整流程需要自己按 [`README.md`](README.md)（[English](README.en.md)）的说明获取这些上游项目。
To run the full pipeline, fetch these upstream projects as described in [`README.en.md`](README.en.md).

## 5. 免责 / Disclaimer

本文件是作者对各上游条款的**善意理解**，**不构成法律意见**。任何商业用途请自行核实并咨询律师。
This file is the author's **good-faith reading** of the upstream terms and **is not legal advice**. Verify independently and consult a lawyer before any commercial use.
