#!/usr/bin/env python3
"""复现台账的**唯一事实源**。

设计原则（2026-09-19 按用户要求确立）：
  · 这里只记**最终复现状态**，不记过程。过程日志在 docs/log/report.md。
  · 每条主张都要有 `script` 和 `result_file`，页面与 REPRODUCTION.md 都从这里渲染，
    **任何一处都不许手抄数字**。
  · 每次迭代先读 REPRODUCTION.md（或本文件），需要细节再去翻 docs/log/report.md。

status 取值：
  reproduced  复现了，定量对上
  partial     部分复现 / 有条件成立
  negative    做了，结果是阴性（这也是结果）
  not_done    还没做
  blocked     做不了，并说明卡在哪
"""

PAPERS = [
    dict(key="shiu2024", cite="Shiu et al. 2024, Nature 634:210-219",
         url="https://www.nature.com/articles/s41586-024-07763-9",
         note="本项目的核心对象：FlyWire v783 全脑 LIF 模型。补充材料 CC BY 4.0，存于 external/shiu2024_supp/",
         claims=[
             dict(id="sugar_mn9", what="糖味觉 GRN → MN9 沉默筛选（补充表 1A–C）", status="reproduced",
                  result="与论文判定 κ **0.59**、Pearson 0.83；对论文自己的光遗传实验 **6/10**",
                  caveat="Roundup 与 Zorro 的比值紧贴 0.8 判据，判定随实现数与归一化口径翻转；其余 8 个类型四种口径一致",
                  script="screen/sugar_mn9_screen.py", result_file="results/screen/summary.json", log="§14"),
             dict(id="water_mn9", what="水味觉 GRN → MN9 沉默筛选（补充表 5/6）", status="reproduced",
                  result="κ **0.87**、Pearson 0.96、判定一致率 97%；对实验 **9/10**（与论文同分）",
                  caveat="唯一错项 Usnea 是神经肽通路，模型里只有经典递质",
                  script="screen/water_screen.py", result_file="results/screen/water/summary.json", log="§19"),
             dict(id="jon_adn1", what="触角机械感觉 JON → aDN1 梳理指令（补充表 7A/B/D）", status="reproduced",
                  result="κ **0.907**、Pearson 0.945；基线 aDN1 **24.2 Hz**（论文 23.3）；论文判必需的 6 个我们判出 5 个",
                  caveat="刺激名单是从补充表 7A 反推的 146 个（被刺激神经元发放率精确等于刺激频率）。"
                         "**基线口径**：24.2 Hz 是本分析所用的 6 个实现，与 κ/Pearson 同口径；全部 12 个实现是 23.4 Hz。"
                         "早先文档只写 23.4 而没说实现数，和 R=6 的 κ 混在一句话里",
                  script="screen/jon_paper.py", result_file="results/screen/jon_paper/full_summary.json", log="§24.3",
                  verify=[("paper_comparison.kappa", 0.907, 0.001), ("paper_comparison.pearson", 0.945, 0.001),
                          ("baseline.mean", 24.2, 0.05)]),
             dict(id="jon_adn2", what="同一通路的第二个读出 aDN2（补充表 7C/E）", status="reproduced",
                  result="κ **0.887**、Pearson 0.946；基线 **24.5 Hz**（论文 23.7）；判必需 4 个 vs 论文 5 个",
                  caveat="零新仿真——段落文件本来就存了全部活跃神经元的计数。唯一分歧 JO_EDM_14（0.810 vs 0.737）卡在判据线上",
                  script="screen/jon_adn2.py", result_file="results/screen/jon_paper/adn2_summary.json", log="§29",
                  verify=[("paper_comparison.kappa", 0.887, 0.001), ("paper_comparison.pearson", 0.946, 0.001),
                          ("baseline.mean", 24.5, 0.05)]),
             dict(id="abn1_bottleneck", what="aBN1 是梳理通路的绝对瓶颈", status="reproduced",
                  result="单敲 aBN1 让 **aDN1 与 aDN2 同时归零**（比值 0.000，论文两表也都是 0.000）",
                  caveat="两个梳理指令神经元共用同一个瓶颈——这一条事先声明不预设答案",
                  script="screen/jon_adn2.py", result_file="results/screen/jon_paper/adn2_summary.json", log="§29"),
             dict(id="shuffle", what="打乱接线对照（补充表 1D）", status="partial",
                  result="糖 → MN9 从 **82.9 Hz 掉到 3.5 ± 4.2 Hz**（比值 0.043），与论文同量级（Zorro_l 102.2 → 2.75 ± 7.17）",
                  caveat="只在 4,599 个神经元的**子回路**上做，不是全脑；论文未公开打乱做法，我们用的是「保出度与权重、只重排靶点」。定性方向可比，定量不可比",
                  script="dodge/measure_perturb.js", result_file="results/dodge/perturb.json", log="§30.1",
                  verify=[("baseline_hz.sugar", 82.9, 0.05), ("shuffle.sugar.均值Hz", 3.5, 0.1),
                          ("shuffle.sugar.比值", 0.043, 0.002)]),
             dict(id="robustness", what="参数稳健性（补充表 11B–F）", status="partial",
                  result="按论文判据（判定是否翻转）：突触权重 ±30% → **9/10 与 10/10 不变**；抑制 ±30% → 7/10 与 9/10；谷氨酸改兴奋性 → 7/10",
                  caveat="同上，子回路而非全脑；翻转的全是贴着 0.8 判据的边缘情况",
                  script="dodge/measure_perturb.js", result_file="results/dodge/perturb.json", log="§30.2"),
             dict(id="taste_interaction", what="糖/水/苦/Ir94e 四味及其组合（补充表 4，615 行）", status="not_done",
                  result="—", caveat="需要先把每种刺激标定到 MN9 = 40 Hz（论文口径），工期未估",
                  script=None, result_file=None, log="§附录·空白清单"),
             dict(id="baseline_rates", what="基线发放率：糖 → MN9、LC4 → 巨纤维", status="reproduced",
                  result="糖 100 Hz → MN9 **98/69 Hz**；左侧 54 个 LC4 100 Hz → 巨纤维 **85/40 Hz**",
                  caveat="PyTorch 后端在 DNa02 上与 Brian2 有 20 vs 10 Hz 的差异（各自独立抽泊松输入，在噪声量级）",
                  script="run_experiment.py", result_file="results/", log="§3.2"),
         ]),
    dict(key="lappalainen2024", cite="Lappalainen et al. 2024, Nature 634:1132-1140（flyvis）",
         url="https://github.com/TuragaLab/flyvis", note="连接组约束的视觉网络，MIT 许可",
         claims=[
             dict(id="hexconv", what="网络本质上是六边形卷积（权重只依赖源型/靶型/位移）", status="reproduced",
                  result="**50 个集成成员全部通过**逐成员验证；45,669 个节点只由 604 个核、**2,355 个抽头**决定 → 80 KB JSON",
                  caveat="导出脚本会验证这个前提，不成立就拒绝导出（exit 2）",
                  script="vision/export_flyvis_js.py", result_file="results/vision/flyvis_net.json", log="§28.1"),
             dict(id="t4t5_dir", what="T4/T5 亚型的方向选择性（**50 个集成成员全测**）", status="partial",
                  result="跨成员离散度极大：有方向选择性的成员数 T4a 34/50、T4b 31/50、T4c 42/50、**T4d 37/50**；"
                         "T4a 偏好方向中位 275° 但范围 3–357°",
                  caveat="**成员 000 里 T4d 与 T5b 没有方向选择性，但那只是它自己的性质**——T4d 在 37/50 个成员里有，"
                         "DSI 中位 0.849。所以「文献的 a/b/c/d = 四个正交方向在 flyvis 里不成立」必须限定为「在成员 000 里不成立」。"
                         "「偏好方向落在六边形棱方向族」只有 T4a（28/34）与 T4b（24/31）有集成支持，T4c 仅 13/42",
                  script="vision/ensemble_check.js", result_file="results/vision/ensemble_summary.json", log="§28.17 + §33.2"),
         ]),
    dict(key="ache2019", cite="Ache et al. 2019, Curr Biol 29:1073-1081",
         url="https://www.cell.com/current-biology/fulltext/S0960-9822(19)30138-1",
         note="全文不可得（cell.com 403、Caltech 库 metadata-only），下列内容来自摘要与检索",
         claims=[
             dict(id="gf_model_form", what="巨纤维输入 = LC4 角速度线性项 + LPLC2 角大小高斯项", status="reproduced",
                  result="模型形式被证实，游戏的 `encoding: \"ache2019\"` 用的就是这个形式",
                  caveat=None, script="dodge/game_core.js", result_file=None, log="§32.1"),
             dict(id="gf_gaussian_peak", what="角大小高斯的峰位", status="reproduced",
                  result="论文值 **42°**，已采用（此前手选 45°）。实测影响在噪声内：闪避率 83.3%→84.7%，差 1.4 pp、标准误 3.6 pp",
                  caveat="高斯宽度 15° 与峰值 200 Hz **仍是手选**，论文没给到",
                  script="dodge/game_core.js", result_file=None, log="§32.1"),
             dict(id="gf_connectome", what="直接突触到巨纤维的 LC4 / LPLC2 数量", status="reproduced",
                  result="论文（单侧）LC4 **55** → v783 **54/50**（比 0.98/0.91）；LPLC2 **108** → **94/95**（0.87/0.88）",
                  caveat="突触数低 2–7 倍（论文 2,442/1,366）。**不是阈值筛选造成的**——连接表最小值为 1，有 7,496,016 条单突触边；是自动突触检测与人工 EM 重建的口径差异",
                  script="vision/check_ache2019.py", result_file="results/vision/ache2019_check.json", log="§32.1",
                  verify=[("对照.LC4_left.我们_神经元", 54, 0), ("对照.LPLC2_left.我们_神经元", 94, 0)]),
         ]),
    dict(key="card2008", cite="Card & Dickinson 2008, Curr Biol 18:1300-1307",
         url="https://pubmed.ncbi.nlm.nih.gov/18760606/", note="全文不可得，下列来自摘要",
         claims=[
             dict(id="escape_away", what="逃逸方向背离逼近刺激", status="reproduced",
                  result="游戏按此实现：取背离威胁的一侧并把飞行片段整体旋转过去",
                  caveat="只是按规则实现，没有对照该文的定量分布（拿不到）",
                  script="dodge/game_core.js", result_file=None, log="§32.2"),
             dict(id="planning_200ms", what="起飞前约 200 ms 的姿态准备期", status="not_done",
                  result="我们的巨纤维越阈**即刻**起飞，延迟 **0 ms**；起飞时剩余撞击时间中位 **477 ms**",
                  caveat="时间预算是够的（477 > 200），但准备期、姿态依赖的方向、「不跳也规划」三条都没建模",
                  script="dodge/takeoff_timing.js", result_file="results/dodge/takeoff_timing.json", log="§32.2",
                  verify=[("实测.GF越阈到起飞延迟ms中位", 0, 0), ("实测.剩余撞击时间ms中位", 477, 1)]),
         ]),
    dict(key="klapoetke2017", cite="Klapoetke et al. 2017, Nature 551:237-241",
         url="https://www.nature.com/articles/nature24626", note="LPLC2 汇集「背离感受野中心」的运动",
         claims=[
             dict(id="lplc2_pooling", what="LPLC2 = 汇集背离中心的 T4/T5 运动", status="partial",
                  result="在成员 000 上三条判据全过（匀速扩张 > 收缩 1.24×、逼近 > 两种平移 1.26×/1.69×），"
                         "但**在 50 个集成成员里只有 8/49 三条全过**（A 单独 17/49、B 单独 11/49）",
                  caveat="**成员 000 属于少数派（约 16%）**，所以这不是 flyvis 的普遍性质。此外裕度很小、"
                         "**只在峰值上成立，均值上近距平移反而更高**（与 §18 全脑结论一致）；"
                         "汇集必须用 mean 不能用 max（max 时比值 0.76，是反的）",
                  script="vision/lplc2_test.js", result_file="results/vision/lplc2_test.json", log="§28.18 + §33.3",
                  verify=[("结果.loomLin.峰值", 0.1943, 0.0002), ("结果.recLin.峰值", 0.1569, 0.0002)]),
         ]),
    dict(key="hampel2015", cite="Hampel et al. 2015, eLife 4:e07866",
         url="https://elifesciences.org/articles/07866", note="aBN1/aBN2 驱动触角梳理",
         claims=[
             dict(id="abn1_exp", what="aBN1 是梳理必需（实验验证）", status="reproduced",
                  result="模型里单敲 aBN1 让 aDN1 与 aDN2 都归零，与实验一致",
                  caveat="aBN2 的 v630 ID 在 v783 里没有对应，**从来无法测试**——所以诚实的分数是 1/1 可测，不是 2/2",
                  script="screen/jon_adn2.py", result_file="results/screen/jon_paper/adn2_summary.json", log="§24 更正"),
         ]),
    dict(key="pugliese2025", cite="Pugliese et al. 2025（腹神经索发放率模型）",
         url="https://github.com/smpuglie/Pugliese_cpg_2025", note="**无许可证**：只能本地导入运行，不得复制其代码",
         claims=[
             dict(id="t1_rhythm", what="DNg100 驱动前足网络产生节律", status="partial",
                  result="16/16 复制里出现 **~11 Hz** 节律",
                  caveat="但只有 144 个运动神经元里的 2–4 个参与；摆动/支撑模块同相（+0.73）、左右不相关；驱动的左前腿摆幅 0.19 mm vs CPG 0.83 mm",
                  script="vnc/run_pugliese.py", result_file="results/vnc/pugliese/", log="§11.5"),
             dict(id="edfig8", what="全 MANC 上的 DNg100 刺激（Extended Data Fig 8）", status="blocked",
                  result="—", caveat="**作者仓库里没有那个配置文件**（`DNg100_Stim_fullManc`，128 复制），无法复现",
                  script=None, result_file=None, log="§12"),
         ]),
    dict(key="vaxenburg2025", cite="Vaxenburg et al. 2025, Nature（flybody）",
         url="https://www.nature.com/articles/s41586-025-09029-4", note="Apache-2.0 代码，飞行数据 GPL-3.0+",
         claims=[
             dict(id="flight_policy", what="训练好的飞行控制器能复飞记录轨迹", status="reproduced",
                  result="跟踪误差中位 **0.26 / 0.30 mm**",
                  caveat="左侧片段在最后约 30 ms 发散到约 7 mm / 50°",
                  script="flight/policy_rollout.py", result_file="results/flight/flight_clips.json", log="§9.3"),
         ]),
    dict(key="govardovskii2000", cite="Govardovskii et al. 2000, Vis Neurosci 17:509-528",
         url="https://pubmed.ncbi.nlm.nih.gov/11016572/", note="A1 视色素敏感度模板（解析式）",
         claims=[
             dict(id="opsin_template", what="按 λmax 算视蛋白敏感度曲线", status="reproduced",
                  result="实现了 α 带 + β 带模板，对果蝇五个视蛋白（Rh1 478 / Rh3 345 / Rh4 375 / Rh5 437 / Rh6 508 nm）积分出通道权重",
                  caveat="R1–6 的 3-羟基视黄醇**增感色素不在模板里**，做成显式开关、幅度手选；场景是 sRGB 著作的，没有真实光谱",
                  script="vision/opsin_weights.js", result_file="results/vision/opsin_weights.json", log="§28.16"),
         ]),
    dict(key="flybrainai", cite="neilt93/Fly-Brain-AI（社区项目）",
         url="https://github.com/neilt93/Fly-Brain-AI", note="**无许可证**：只能本地导入运行，不得复制其代码或再分发",
         claims=[
             dict(id="looming_loop", what="Brian2 全脑 ↔ FlyGym 闭环的 looming 实验", status="reproduced",
                  result="复现成功，峰值内存 **4.3 GB**（其 README 说约 8 GB）",
                  caveat=None, script="fba_export_replay.py", result_file="results/fba_replay/replay.json", log="§4.1"),
             dict(id="odor_valence", what="气味效价实验", status="partial",
                  result="6 条里复现 **4 条**", caveat=None,
                  script="external/Fly-Brain-AI/plastic-fly/experiments/odor_valence.py", result_file=None, log="§10.5"),
             dict(id="turn_sign", what="turn_drive 的符号（文档说正值向右，代码却是向左）", status="reproduced",
                  result="**代码对、文档错**：`turn_drive > 0` 让身体转**左**。3 个种子全部一致——"
                         "左注入 +0.352、右注入 −0.533；相对对照的净侧移 +4.82 mm（偏左）vs −1.60 mm（偏右）。"
                         "打乱连接组后左右差从 **+6.42 mm 塌到 −0.02 mm**",
                  caveat="而且左 LPLC2 注入让果蝇转向**被刺激的同侧**，与作者报告的「对侧逃逸」相反。"
                         "三点限制：①绝对侧移读不出方向（不注入的对照也漂 −15.56 mm，是步态偏置）；"
                         "②打乱同时改变了整个运动（打乱后基线漂移只有 −3.47 mm），能干净比较的只有左右差；③n=3 种子",
                  script="fba_turn_sign.py", result_file="results/fba_turn_sign.json", log="§34",
                  verify=[("result.lateral_diff_real_mm", 6.419, 0.01), ("result.lateral_diff_shuffled_mm", -0.018, 0.01)]),
         ]),
]

# 我们自己标定 / 测定、并在别处引用的关键参数（不是论文给的就标出来）
PARAMETERS = [
    dict(name="lc4_gain", value="19.8", source="本项目标定（规则 A：200 Hz ÷ p95(expansion)）",
         note="手选的旧值 4000 是它的 **202 倍**；标定后 LC4 从 0/200 两个值变成 15 个分级取值",
         script="connectome_vision_loop.py", log="§27"),
    dict(name="lplc2Mu（角大小高斯峰）", value="42°", source="Ache et al. 2019",
         note="此前手选 45°；改动影响在噪声内", script="dodge/game_core.js", log="§32.1"),
    dict(name="lplc2Sigma / lplc2Peak", value="15° / 200 Hz", source="**手选**",
         note="论文全文拿不到，这两个没有依据", script="dodge/game_core.js", log="§32.1"),
    dict(name="小眼间角 Δφ", value="5.7°", source="FlyGym 规范 + 实测",
         note="单眼视野 = 2×15×Δφ = 171°", script="dodge/eyecam.js", log="§28.11"),
    dict(name="复眼光轴方位", value="±63.1°", source="MuJoCo 实测（此前假设 ±50°）",
         note="双眼重叠 44.8°、总视野 297.2°、背后盲区 62.8°", script="dodge/eyecam_geom_test.js", log="§28.9"),
    dict(name="子回路裁剪", value="wmin=3, K=3 → 4,599 神经元", source="本项目选定",
         note="子回路整体重现全脑敲除模式（糖 Pearson +0.75、水 +0.89），但 CB0883 的枢纽效应在裁剪后完全消失",
         script="dodge/subcircuit_v2.py", log="§25.2"),
    dict(name="DNg100 刺激电流", value="I = 350（全 MANC）/ 360（全突触版）", source="本项目标定",
         note="作者的 set_sizes 按**网络**中位体型归一，所以同一电流在全 VNC 里更弱（前足网络默认 250）",
         script="vnc/manc_full.py", log="§12.1"),
]

# ── 本项目自己的结果（不是对某篇论文的复现，但同样是"我们知道什么"）──────────
FINDINGS = [
    dict(id="subcircuit_vs_full", what="4,599 个神经元的子回路能多大程度代表全脑",
         result="敲除模式整体重现：糖 Pearson **+0.75**、水 **+0.89**（n=10，同一口径两边各测一次）",
         caveat="单个神经元会失真。最典型是 CB0883：全脑里是枢纽（单敲 0.76、配对 0.24），子回路里**完全无作用**（1.07）——"
                "它依赖的旁路正是 wmin≥3 / K≤3 裁掉的。早先写的「+0.21 糖 / +0.92 水」是错的，来自混用归一化口径",
         script="dodge/subcircuit_vs_fullbrain_knockouts.py",
         result_file="results/dodge/subcircuit_vs_fullbrain_knockouts.json", log="§25.2"),
    dict(id="redundancy_needs_sim", what="能不能只看连线就预测「一起敲会不会塌」",
         result="**不能**。路径重叠与配对 Δ 的 Spearman 是 **−0.008（糖）/ 0.013（水）**，且已排除指标退化",
         caveat="换成动力学指纹方向对但很弱（−0.21 / −0.14），而指纹本身就是单敲全脑仿真——省的是筛选，不是配对那一跑",
         script="screen/structure_vs_function.py", result_file="results/screen/structure_vs_function.json", log="§22"),
    dict(id="two_pathways", what="糖和水是不是同一批神经元",
         result="**不是**。活跃集只重叠约三分之一（Jaccard 0.36），共同活跃的 128 个上效应也几乎不相关（Spearman 0.18、κ 0.15）",
         caveat="枢纽各自私有：CB0883 在水通路里根本不放电；CB0051 在糖通路里敲了没影响（0.97 vs 水的 0.49）",
         script="screen/pathway_compare.py", result_file="results/screen/pathway_compare.json", log="§21"),
    dict(id="concentration", what="为什么有的通路模型预测得准、有的不准",
         result="**通路集中度**能排序：Gini 水 0.92（n80=15）> JON 0.86（45）> 糖 0.78（62），连线预测器 G3 也是同序（0.49 > 0.43 > 0.32）",
         caveat="两种「集中」不同：水是几个神经元各担一部分（大量协同），JON 是一个绝对瓶颈加约 2,000 个无关神经元",
         script="screen/concentration.py", result_file="results/screen/concentration.json", log="§22.2"),
    dict(id="fly_speaks", what="能不能从全脑发放率解码出「果蝇在感知什么」",
         result="12 个词、301 试次一次跑完（429 s、3.3 GB），岭回归解码器给出第一句中文",
         caveat="词的触发是手写的感觉populations，句子模板也是手写的；这是**解码**不是语言",
         script="language/fly_words.py", result_file="results/language/dataset.npz", log="§13"),
    dict(id="decoder_stress", what="像脑机接口那样只看到一部分神经元，还读得出吗",
         result="**覆盖率胜过通道数**：1,000 个随机神经元 0.82，1,000 个**真的会放电的** 0.95，而 3,000 个空间相邻的只有 0.55",
         caveat="90% 的非感觉神经元从不放电；给它们全加 1 Hz 假脉冲会把准确率打到 0.65，而 1,000 通道解码器仍有 0.91。"
                "掉 10% 通道不重标定：0.94 → 0.62",
         script="language/decoder_stress.py", result_file="results/language/stress.json", log="§15"),
    dict(id="manc_vnc", what="全腹神经索（MANC 23,532 神经元）能不能走出步态",
         result="DNg100 在 12/16 复制里出现 **8–11.5 Hz** 节律，且传到六条腿的运动神经元",
         caveat="**但不是三足步态**：E1 相位不对、摆动/支撑同相；只有右后腿真的摆（0.6–0.7 mm）。"
                "GF→TTMn 的电突触在连接组里**根本不存在**，只有化学突触给约 20 ms 瞬变",
         script="vnc/manc_full.py", result_file="results/vnc/manc_full/summary.json", log="§12"),
    dict(id="pixel_loop", what="把游戏的视觉前端换成真像素会怎样",
         result="**负结果，可量化**：45 mm 外读数恒为 0（完全瞎），25 mm 以内才高过噪声；"
                "而果蝇**光是走路**，自体运动的全场光流就造出峰值 **126 Hz** 的假逼近",
         caveat="球半径 2.5 mm、小眼间角 5.7° → 60 mm 外不到一个小眼。败因是分辨率与未补偿的自体运动，不是 LPLC2 模型。"
                "所以做成可切换对照，不做默认前端",
         script="dodge/front_end_compare.js", result_file="results/vision/front_end_compare.json", log="§28.19"),
    dict(id="dopamine", what="模型里有没有奖赏信号（吃到糖会不会分泌多巴胺）",
         result="**没有**。不失控的糖刺激下 PAM 神经元放电 **0/307**；DAN 只在失控里放电，"
                "而且 PPL1 > PAM，气味失控与糖失控完全一样",
         caveat="所以这个 LIF 模型**不具备强化学习所需的奖赏信号**——不是「没测出来」，是结构上就没有",
         script="dodge/v4_refs_analysis.py", result_file="results/v2_ref/v4_analysis.json", log="§11.1"),
    dict(id="hub_cb0883", what="有没有「单独敲都没事、一起敲就断」的备份通路",
         result="有，但是例外。把 312 个活跃神经元逐一与枢纽 CB0883 配对：**32 个协同（19 个留一稳定）**，"
                "其中只有 **12 个**单敲比值 < 1、可解释为备份；**108 个是亚可加**（共用瓶颈）",
         caveat="12 个备份里有 5 个就是糖味觉受体本身。CB0883 单独敲 0.76（算不上必需），"
                "配上 Clavicle / G2N-1 就把 MN9 打到 0.24 —— **单个敲除筛选系统性看不见这一类**",
         script="screen/hub_scan.py", result_file="results/screen/hub_scan_summary.json", log="§16.2"),
    dict(id="olfaction", what="全脑模型能不能给出嗅觉转向信号", status_note="阴性",
         result="**不能**。单侧气味刺激的下行神经元侧化指数 |LI| ≤ 0.05",
         caveat="而且嗅觉刺激是**全或无的失控**：35 个 DM1 嗅觉受体神经元 10 Hz → 25 ms 内约 8,300 个神经元活跃。"
                "右侧 ORN_DM1 对**左侧** DM1 投射神经元的突触反而更多（1,664 vs 1,288），侧向读出本身就被混淆。"
                "游戏里的「闻着找」是**手写**的高斯气味场，不是连接组",
         script="dodge/v4_olfaction_runaway.py", result_file="results/v2_ref/olfaction_runaway.json", log="§10.5 + §11.4"),
    dict(id="banc_vnc", what="BANC 腹神经索能不能走出节律",
         result="**不能**。节律功率约等于噪声；巨纤维驱动 **0 个**腿部运动神经元",
         caveat="原因是 GF→TTMn 的**电突触在连接组里根本不存在**（只有化学突触）。"
                "这条后来在全 MANC 上复核过（§12.3）：化学突触只给约 20 ms 瞬变，"
                "要维持 TTMn 需手加约 1,500 个突触当量的耦合",
         script="vnc/run_vnc.py", result_file="results/vnc/", log="§10.6 + §12.3"),
    dict(id="call_protocol", what="敲除判定对口径有多敏感",
         result="10 个实验类型里**恰好 2 个**（Roundup 与 Zorro）的判定随实现数与归一化口径翻转，其余 8 个四种口径一致",
         caveat="这两个的比值全落在 **0.74–0.85**，紧贴 0.8 判据 —— 不是算错，是本来就在线上。"
                "四种口径都得 6/10，但**答对的是哪 6 个**恰好互换一个。"
                "引用这两个的比值必须同时说明实现数与归一化方式",
         script="screen/recheck_calls.py", result_file="results/screen/recheck_calls.json", log="§31"),
    dict(id="ensemble", what="我们的视觉结论有多少是「那一个模型」的性质",
         result="50 个成员全跑：卷积前提 **50/50** 成立（唯一在集成层面稳的）；"
                "而 LPLC2 三条判据全过只有 **8/49**，我们一直用的成员 000 正是其中之一",
         caveat="T4d 在 **37/50** 个成员里**有**方向选择性（DSI 中位 0.849），"
                "所以 §28.17 那句「T4d/T5b 无方向选择性」只是成员 000 的性质。"
                "教训：`vision/export_flyvis_js.py` 里硬编码着 `flow/0000/000`，一路沿用了十几节——"
                "**凡是「某个预训练模型给出 X」的结论，都要问一句：这个模型是从几个里挑的**",
         script="vision/ensemble_check.js", result_file="results/vision/ensemble_summary.json", log="§33"),
    dict(id="lattice_distortion", what="flyvis 与 FlyWire 的柱坐标怎么对齐",
         result="用解剖（两视叶质心定左右、全脑质心→GNG 定腹侧、叉积定前后）加实测 T4/T5 方向，"
                "把 8 种朝向**钉到唯一一种**（旋转 φ=277°，即 u=−p, v=−q）",
         caveat="同时查出原流程有形变：`normalize()` 把 Codex 六边形基矢夹角**从 60.0° 拉成 122.6°**。"
                "换成保几何映射后「逼近 > 近距平移」翻转成立（3/3 重复），但只有一种映射给出该结果，属**有条件的修正**",
         script="vision/lattice_anchor.py", result_file="results/vision/lattice_anchor.json", log="§28.20"),
]
