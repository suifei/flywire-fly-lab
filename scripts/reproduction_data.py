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
                  script="screen/sugar_mn9_screen.py", result_file="results/screen/summary.json", log="§14",
         verify=[("exploratory_null_normalized.by_freq.50Hz.kappa", 0.59, 0.005),
                          ("exploratory_null_normalized.by_freq.50Hz.pearson", 0.831, 0.005)]),
             dict(id="water_mn9", what="水味觉 GRN → MN9 沉默筛选（补充表 5/6）", status="reproduced",
                  result="κ **0.87**、Pearson 0.96、判定一致率 97%；对实验 **9/10**（与论文同分）",
                  caveat="唯一错项 Usnea 是神经肽通路，模型里只有经典递质",
                  script="screen/water_screen.py", result_file="results/screen/water/summary.json", log="§19",
         verify=[("paper_comparison.kappa", 0.869, 0.002), ("paper_comparison.pearson", 0.958, 0.002),
                          ("paper_comparison.call_agreement", 0.973, 0.002),
                          ("experiment_score.ours_single.correct", 9, 0)]),
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
                  script="screen/jon_adn2.py", result_file="results/screen/jon_paper/adn2_summary.json", log="§29",
         verify=[("aBN1.ratio_aDN1", 0.0, 1e-9), ("aBN1.ratio_aDN2", 0.0, 1e-9),
                          ("aBN1.paper_7e", 0.0, 1e-9)]),
             dict(id="shuffle", what="打乱接线对照（补充表 1D）", status="reproduced",
                  result="**全脑**做的：不打乱时表 1D 那 13 个神经元与论文的 **Pearson 0.992**"
                         "（MN9_r 我们 62.7 Hz、论文 68.0）；10 个打乱版本下**这 13 个全部归零**，"
                         "活跃神经元从 348 掉到 60–95。两条事先判据都成立"
                         "（A：MN9_r 打乱后 < 不打乱的 10%；B：≥12/13 下降）",
                  caveat="论文**没有公开打乱的具体做法**，我们用的是「保每个神经元的出度与权重、只把靶点列整体重排」。"
                         "论文跑 100 次、我们跑 10 次，而且论文的打乱均值不是 0 而是 2.7–5.4 Hz（SD 7–11），"
                         "也就是说**少数打乱版本会出现强响应**——10 次抽不到这种罕见事件很正常，"
                         "所以「我们恒为 0」比论文更干净，不能当成复现得更好。"
                         "表 1D 的 15 个 ID 里只有 13 个在 v783 模型中，判据 B 的分母按论文 14/15 的比例折算成 12/13。"
                         "子回路版（4,599 神经元）另见 `dodge/measure_perturb.js`：糖 → MN9 从 82.9 掉到 3.5 Hz",
                  script="screen/shuffle_full.py", result_file="results/screen/shuffle_full/summary.json", log="§30.1 + §37.7",
                  verify=[("pearson_intact_vs_paper", 0.992, 0.0005), ("n_down", 12, 0), ("n_total", 13, 0),
                          ("mn9_r.ours_intact", 62.667, 0.02), ("mn9_r.ours_shuf_mean", 0.0, 0.001),
                          ("design.n_shuffles", 10, 0)]),
             dict(id="robustness", what="参数稳健性（补充表 11A–F，**全脑**，三条预测全做）", status="reproduced",
                  result="**第三条预测也做了**（每种扰动下重做整轮敲除筛选，6,494 段 / 3 h）："
                         "与默认判定一致的个数 **[8, 6, 8, 8, 7]**，论文是 **[8, 7, 8, 7, 7]**——"
                         "**5 个里 3 个完全吻合，其余差 1，平均绝对差 0.4**。"
                         "前两条：w_syn −30% 下 MN9_r **34.5 Hz**（论文 33.47）、+30% **96.7**（96.13）、"
                         "抑制 −50% **154.7**（143.93）、+50% **36.2**（19.07）；「同侧 MN9 比对侧弱」**6/6 成立**",
                  caveat="**论文对每种扰动重新标定了刺激频率**（表 11A 的 Experiment 一列：115 / 30 / 30 / 100 / 45 Hz），"
                         "不是在同一强度下比较——突触弱了就把输入调高。漏掉这一点会全盘对不上。"
                         "**抑制的幅度是 ±50% 不是 ±30%**（分节标题里写着，11D/11E 表头不带幅度；第一版想当然了）。"
                         "翻转最多的是 **Zorro（5 个扰动里翻了 4 次）与 Rattle（3 次）**——"
                         "与 §16 「只有 Zorro 和 Roundup 的判定随口径翻转」一致。"
                         "**逐个神经元的发放率相关只有 r = 0.26–0.47**；谷氨酸改兴奋性让全脑失控（活跃 421 → 30,475）",
                  script="screen/robust_knockout.py", result_file="results/screen/robust_knockout/summary.json",
                  log="§35 + §38.1 + §39",
                  verify=[("ours_consistent.0", 8, 0), ("ours_consistent.1", 6, 0), ("ours_consistent.2", 8, 0),
                          ("ours_consistent.3", 8, 0), ("ours_consistent.4", 7, 0),
                          ("mean_abs_diff", 0.4, 0.001),
                          ("conditions.baseline.n_scored", 183, 0)]),
             dict(id="taste_interaction", what="糖/水/苦/Ir94e 四味及其组合（补充表 4，615 行）", status="reproduced",
                  result="8 个条件全跑（全脑，各 6 个实现），刺激名单用**官方 notebook 的**。"
                         "剔除全部被刺激 GRN 后的 466 个神经元上，与论文发放率的 Pearson **0.963–0.999**；"
                         "四个组合的抑制方向全部一致：糖+苦 MN9 **0.2 Hz**（论文 1.3）、糖+Ir94e **0.8**（1.1）、"
                         "水+苦 **18.8**（10.1）、水+Ir94e **10.7**（2.3）",
                  caveat="表头有**两套标定规则**：糖/水是驱动型（单独标到 MN9≈40 Hz：糖 60 Hz→35.7、水 220 Hz→38.3），"
                         "苦/Ir94e 是抑制型（垫在糖上把 MN9 压到 1 Hz：苦 80 Hz、Ir94e 60 Hz）——只读前半句会让苦「无法标定」。"
                         "频率网格只有 8 档，标定值是最近档而非精确 40/1 Hz。**对水的抑制比论文弱**："
                         "组合÷单独 水+苦 0.49（论文 0.25）、水+Ir94e **0.28（论文 0.06）**；"
                         "Ir94e 单独的响应集与论文重叠最差（Jaccard 0.22，其余条件 0.68–0.93）。"
                         "**一开始以为论文没公开刺激名单，按表 4 的高发放类型反推了一版**（苦 21 / Ir94e 21）；"
                         "后来发现 figures.ipynb 的 Figure 3 单元格里就有原始名单（苦 21 / Ir94e 18）。"
                         "两版都留着（反推版在 results/screen/taste/），官方名单版在糖的两个组合上更接近论文（0.005/0.023 vs 0.000/0.042）",
                  script="screen/taste_interaction.py", result_file="results/screen/taste/notebook/summary.json", log="§37",
                  verify=[("conditions.Sugar_Bitter.ours_mn9", 0.17, 0.02), ("conditions.Sugar_Ir94e.ours_mn9", 0.83, 0.02),
                          ("conditions.Water_Bitter.ours_mn9", 18.83, 0.02), ("conditions.Water_Ir94e.ours_mn9", 10.67, 0.02),
                          ("conditions.Sugar_Ir94e.pearson_nonstim", 0.963, 0.0005),
                          ("conditions.Water_only.pearson_nonstim", 0.999, 0.0005),
                          ("conditions.Ir94e_only.respond_jaccard_nonstim", 0.217, 0.001),
                          ("interaction.Water_Ir94e.ours_ratio", 0.278, 0.001),
                          ("interaction.Water_Ir94e.paper_ratio", 0.056, 0.001),
                          ("calibration.sugar.chosen_mn9", 35.67, 0.01), ("calibration.water.chosen_mn9", 38.33, 0.01)]),
             dict(id="taste_grid", what="苦能压住强糖、Ir94e 压不住（Fig 3B–C，表 10 第 5 行）", status="reproduced",
                  result="**两条事先写死的判据全部成立**。最强糖（220 Hz）下 MN9 = 93.0 Hz："
                         "苦 220 Hz 把它压到 **16.3 Hz（降 82.4%）**，Ir94e 220 Hz 只压到 **67.3 Hz（降 27.6%）**。"
                         "5×6 的剂量网格上两者差距随糖强度单调拉开：糖 120 Hz 时苦 160 Hz 已压到 1.7 Hz，"
                         "而 Ir94e 160 Hz 还有 18.0 Hz",
                  caveat="判据是先写下来再跑的（苦降 ≥50% 成立、Ir94e 降 <50% 成立），但**两个 50% 的阈值是我们定的**，"
                         "论文只说了「苦能、Ir94e 不能」。频率档位受编译限制，只取了论文 11×11 网格的一个 5×6 子集；"
                         "刺激名单用官方 notebook 的",
                  script="screen/taste_grid.py", result_file="results/screen/taste/grid/summary.json", log="§37",
                  verify=[("drop.bitter.drop_frac", 0.824, 0.002), ("drop.ir94e.drop_frac", 0.276, 0.002),
                          ("drop.bitter.mn9_with_mod", 16.33, 0.02), ("drop.ir94e.mn9_with_mod", 67.33, 0.02),
                          ("grid.220.none", 93.0, 0.02)]),
             dict(id="jon_ce_f", what="aBN1 只对 JO-CE 响应、对 JO-F 几乎不响应（Fig 5G / 补充表 8）", status="reproduced",
                  result="**两条事先写死的判据都成立**：aBN1 在 JO-CE 150 Hz 下 **52.00 Hz**（论文 50.77）、"
                         "JO-F 150 Hz 下 **1.67 Hz**（论文 1.23）。表 8 全向量（剔除被刺激的 JON 后 277 个神经元）"
                         "两列 Pearson 都是 **0.999**，Spearman 0.98 / 0.99",
                  caveat="刺激名单用官方 notebook Figure 5b 的 neu_JON_CE(70) / neu_JON_F(60)——"
                         "三者并集与 §24.3 反推的 146 个**完全相同**，是一次独立印证。"
                         "判据阈值（CE > 10 Hz、F < 5 Hz）是照论文表 8 里 aBN1 那一行的数量级定的，跑之前写死",
                  script="screen/jon_ce_f.py", result_file="results/screen/jon_ce_f/summary.json", log="§37",
                  verify=[("abn1.ours_ce", 52.0, 0.02), ("abn1.ours_f", 1.67, 0.02),
                          ("abn1.paper_ce", 50.77, 0.02), ("abn1.paper_f", 1.23, 0.02),
                          ("vector.CE.pearson_nonstim", 0.999, 0.0005), ("vector.F.pearson_nonstim", 0.999, 0.0005)]),
             dict(id="sufficiency", what="106 个 SEZ 类型「足以引发伸喙」（Fig 2A / 补充表 3，论文自报 101/106）", status="reproduced",
                  result="模型里有神经元的 **101** 个类型全跑（50 与 200 Hz 各 3 个实现）。与论文 MN9 发放率的 "
                         "**Pearson 0.993（50 Hz）/ 0.998（200 Hz）**，Spearman 0.99 / 1.00；"
                         "判定与论文**逐条一致 100/101**；对光遗传实验 **95/101**，"
                         "而论文自己在同一批 101 个上是 **96/101**",
                  caveat="**判据口径是从论文表 3 自身反查出来的**：只看 50 Hz、MN9_Left、>0 Hz，在论文自己的数字上恰好给出它所报的 "
                         "101/106；换成左右取大是 99、换成 200 Hz 是 96 / 92——所以这个口径是唯一能对上的那个，"
                         "反查完才跑的我们这一版。106 个类型里有 5 个（TH_VUM、Salivary_MN13、bamboo、gallinule、meteor）"
                         "在 v783 模型里没有神经元，所以分母是 101 而不是 106。"
                         "唯一比论文多错的是 **FMIn**（我们 0.00，论文 0.37，判据线就在 0）——它的效应本来就贴着线。"
                         "这一轮**必须**把不应期逐段门控（RFC_GATE）：这些 SEZ 神经元是中间神经元，"
                         "本段没被刺激时若照旧把 rfc 置 0，全脑动力学会被污染",
                  script="screen/sufficiency.py", result_file="results/screen/sufficiency/summary.json", log="§37",
                  verify=[("ours_vs_opto.correct", 95, 0), ("paper_vs_opto.correct", 96, 0),
                          ("ours_vs_paper_calls.same", 100, 0), ("n_compared", 101, 0),
                          ("pearson_50", 0.993, 0.0005), ("pearson_200", 0.998, 0.0005),
                          ("spearman_200", 1.0, 0.0005)]),
             dict(id="responsive", what="哪些神经元响应糖 / 响应水（Fig 1D、4A，表 10 第 2、6 行）", status="reproduced",
                  result="**零新仿真**（基线段落里本来就存了全部神经元的计数）。糖：与实验一致 **10/11**，"
                         "唯一错项 Usnea——**与论文点名的错项完全相同**；水：一致 **4/6**，两个错项 G2N-1 与 Roundup "
                         "也**正是论文自己列的那两个**。与论文自己的预测列逐条一致（糖 11/11、水 6/6）",
                  caveat="论文数的是 14 项（糖）和 10 项（水），比我们多的 MN6 / Fudog / TH-VUM 等没有把名字对到 v783 的 cell_type，"
                         "所以我们只对表 2 / 表 5 里列出的类型计分。模型对这些类型**全部预测「响应」**，"
                         "所以分数完全由实验侧有几个「不响应」决定——这一点论文也一样",
                  script="screen/responsive.py", result_file="results/screen/responsive.json", log="§37",
                  verify=[("sugar.correct", 10, 0), ("sugar.total", 11, 0), ("water.correct", 4, 0),
                          ("water.total", 6, 0), ("sugar.same_as_paper", 11, 0), ("water.same_as_paper", 11, 0),
                          ("sugar.n_paper_pred", 11, 0), ("water.n_paper_pred", 11, 0)]),
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
                  script="vision/export_flyvis_js.py", result_file="results/vision/flyvis_net.json", log="§28.1",
         verify=[("len:kernels", 604, 0), ("sumlen:kernels", 2355, 0)]),
             dict(id="t4t5_dir", what="T4/T5 亚型的方向选择性（**50 个集成成员全测**）", status="partial",
                  result="跨成员离散度极大：有方向选择性的成员数 T4a 34/50、T4b 31/50、T4c 42/50、**T4d 37/50**；"
                         "T4a 偏好方向中位 275° 但范围 3–357°",
                  caveat="**成员 000 里 T4d 与 T5b 没有方向选择性，但那只是它自己的性质**——T4d 在 37/50 个成员里有，"
                         "DSI 中位 0.849。所以「文献的 a/b/c/d = 四个正交方向在 flyvis 里不成立」必须限定为「在成员 000 里不成立」。"
                         "「偏好方向落在六边形棱方向族」只有 T4a（28/34）与 T4b（24/31）有集成支持，T4c 仅 13/42",
                  script="vision/ensemble_check.js", result_file="results/vision/ensemble_summary.json", log="§28.17 + §33.2",
         verify=[("按亚型.T4d.n_selective", 37, 0), ("按亚型.T4a.n_selective", 34, 0),
                          ("按亚型.T4c.n_selective", 42, 0), ("成员数", 50, 0), ("测定成功", 50, 0)]),
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
                  caveat="时间预算是够的（477 > 200），但准备期与姿态依赖的方向都没建模。"
                         "第三条「不跳也规划方向」现在单独测了，见下一条",
                  script="dodge/takeoff_timing.js", result_file="results/dodge/takeoff_timing.json", log="§32.2",
                  verify=[("实测.GF越阈到起飞延迟ms中位", 0, 0), ("实测.剩余撞击时间ms中位", 477, 1)]),
             dict(id="planning_direction", what="「果蝇即使不跳也会先规划好起飞方向」", status="negative",
                  result="**在这个模型里不成立**。用 DNa01/02 的左右差当「方向规划信号」"
                         "（这是连接组自己的输出，不是游戏里那条手写的「起飞方向取背离威胁」规则）："
                         "起飞前 200 ms 内背离威胁的比例 **50.7%**，最终没起飞的窗口 **52.3%**，"
                         "两个都在随机水平（判据要求 > 60%）。6 种子 × 150 s、496 次起飞、5.7 万个采样",
                  caveat="**按方位角分箱后还查出一个系统性的反向**：正面威胁（|方位| < 15°）时"
                         "背离比例只有 **35%**，也就是六成五的时候转向**指向**威胁；侧向威胁才回到随机水平附近。"
                         "**这不是接线接反了**：全脑参考里单侧 LC4+LPLC2 只驱动**对侧** DNa"
                         "（左侧刺激 → DNa01 右 38.5 Hz / 左 0.0，右侧刺激反过来；侧别已换算成注释表口径），"
                         "方向该是对的。正面这一档还没有解释，见日志 §44。"
                         "**第一版的 B 组是错的**：当时额外要求 |DNa 左右差| > 0.5 Hz 才算样本，"
                         "n 从 37,730 掉到 68、比例被抬到 76.5%——那是按被测量的信号本身筛样本，必然虚高。"
                         "另外这只是一个弱类比：模型里没有姿态、没有腿部准备动作，"
                         "而论文那条讲的是质心与腿的预备摆位",
                  script="dodge/takeoff_planning.js", result_file="results/dodge/takeoff_planning.json",
                  log="§32.2 + §44",
                  verify=[("pre_takeoff.frac_away", 0.5069, 0.002), ("no_takeoff.frac_away", 0.5231, 0.002),
                          ("criterion_A", False, 0), ("criterion_B", False, 0),
                          ("pre_bins.0.frac", 0.3502, 0.002), ("takeoffs", 496, 0)]),
         ]),
    dict(key="fotowat2009", cite="Fotowat, Fayyazuddin, Bellen & Gabbiani 2009, J Neurophysiol 102:875-885",
         url="https://pmc.ncbi.nlm.nih.gov/articles/PMC3817277/",
         note="逼近刺激引发的逃逸：固定角度阈值 + 一条非巨纤维的下行通路（全文可得，用户提供）",
         claims=[
             dict(id="angular_threshold", what="起飞发生在张角达到固定阈值之后（与逼近快慢无关）", status="partial",
                  result="**定性成立、定量差 3 倍**。用 8 mm 的刺激时三档球速（l/|v| = 229/133/84 ms）的起飞张角是 "
                         "**17.0° / 17.2° / 17.8°**，变异系数只有 **2.3%**——确实是固定角度阈值；"
                         "「逼近越慢越早起飞」的相关 **0.999**。但阈值本身是 **17.3°**，论文是 **54°（SD 5°）**",
                  caveat="**默认的 2.5 mm 球测不出这条规律**（变异系数 38.5%）——因为那时 54° 对应距离只有 **4.9 mm**，"
                         "而接触距离就是 3.9 mm，论文的阈值在那个场景里等于「已经贴到脸上」。"
                         "换 8 mm 刺激（54° 对应 15.7 mm）规律才显出来。"
                         "还有一个自带偏置要说明：Ache 2019 编码里 LPLC2 是角尺寸的高斯（峰 42°），"
                         "所以「在固定张角起飞」有一部分是编码带来的；非平凡的是**阈值与速度无关到 2.3%** 这个程度。"
                         "扫过 lc4Slope（0→0.5）完全不影响阈值，说明不是角速度项的问题；"
                         "抬高巨纤维阈值到 220 Hz 能把张角推到 22°，但起飞次数从 62 掉到 4，再高就完全不起飞了",
                  script="dodge/looming_threshold.js", result_file="results/dodge/looming_threshold.json", log="§43",
                  verify=[("by_radius.1.theta_cv", 0.0231, 0.002), ("by_radius.1.theta_mean", 17.33, 0.05),
                          ("by_radius.0.theta_cv", 0.3854, 0.002),
                          ("by_radius.1.criterion_A", True, 0), ("by_radius.1.criterion_B", True, 0)]),
             dict(id="gf_not_looming", what="巨纤维**不**响应逼近刺激（逃逸另有一条下行通路）", status="blocked",
                  result="—",
                  caveat="**这条与我们游戏的设计直接冲突**：游戏就是用巨纤维（DNp01）越阈来触发起飞的。"
                         "但这不是简单的对错——文献本身有张力：Fotowat 2009 测到巨纤维对 looming 不放电"
                         "（白眼果蝇 7 只全部如此，Dα7 突变体仍以 81–89% 概率逃逸）；"
                         "而 Ache et al. 2019（我们编码所依据的那篇）恰恰是在讲 LC4/LPLC2 怎么把 looming 编码进巨纤维。"
                         "von Reyn et al. 2014 的解释是**两种逃逸模式**：巨纤维负责「短模式」（牺牲稳定性换速度），"
                         "而 Fotowat 用的慢逼近（l/|v| 10–80 ms）引发的是先抬翅的「长模式」，那条不需要巨纤维。"
                         "**我们的模型里没有这两种模式之分**，也没有抬翅，所以这条无法在现有模型上判对错——"
                         "要复现它得先把长/短模式和抬翅建进去",
                  script=None, result_file=None, log="§43"),
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
             dict(id="odor_valence", what="气味效价实验（作者 README 自报 6/6）", status="partial",
                  result="6 条判据里通过 **4 条**，但**扣掉空对照后实质只有 2 条**。"
                         "失败的两条都在 DM1（吸引）：转向对比 +0.0010（要求 < 0）、"
                         "以及它自己的打乱对照（真实 0.0010 vs 打乱 0.0011）",
                  caveat="**3 条判据是「真实 vs 打乱连接组」，而打乱臂的读出完全不放电**"
                         "（读出均值 0.0 Hz、活跃 0 个，24 个 checkpoint 全部如此）——"
                         "对照组直接死掉，任何非零效应都能通过，这种判据是空的。"
                         "另外查了一个我们自己的猜测并**否掉**：失败不是因为 DM1 引发全脑失控——"
                         "DM1 与 DM5 的读出活动几乎一样（16.7 vs 16.2 Hz）。"
                         "（只看得到解码器读出那约 350 个神经元，不能据此排除全脑层面的失控。）"
                         "所有真实条件的 turn_drive 中位都是 **−0.10**，被一个共同偏置主导",
                  script="fba_odor_recheck.py", result_file="results/fba_odor_valence/recheck.json",
                  log="§10.5 + §42",
                  verify=[("passed", 4, 0), ("effective_passed", 2, 0),
                          ("q2_shuffled_control.shuffled_readout_active", 0.0, 0.01),
                          ("q1_dm1_vs_dm5.dm1_readout_hz", 16.667, 0.01),
                          ("q1_dm1_vs_dm5.dm5_readout_hz", 16.176, 0.01)]),
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
         code_check=("connectome_vision_loop.py", r'--lc4_gain".*?default=([\d.]+)', "19.8"),
         note="手选的旧值 4000 是它的 **202 倍**；标定后 LC4 从 0/200 两个值变成 15 个分级取值",
         script="connectome_vision_loop.py", log="§27"),
    dict(name="lplc2Mu（角大小高斯峰）", value="42°", source="Ache et al. 2019",
         code_check=("dodge/game_core.js", r"lplc2Mu:\s*(\d+)", "42"),
         note="此前手选 45°；改动影响在噪声内", script="dodge/game_core.js", log="§32.1"),
    dict(name="lplc2Sigma / lplc2Peak", value="15° / 200 Hz", source="**手选**",
         code_check=("dodge/game_core.js", r"lplc2Sigma:\s*(\d+),\s*lplc2Peak:\s*(\d+)", "15/200"),
         note="论文全文拿不到，这两个没有依据", script="dodge/game_core.js", log="§32.1"),
    dict(name="小眼间角 Δφ", value="5.7°", source="FlyGym 规范 + 实测",
         code_check=("dodge/eyecam.js", r"DPHI\s*=\s*([\d.]+)\s*\*\s*Math\.PI", "5.7"),
         note="单眼视野 = 2×15×Δφ = 171°", script="dodge/eyecam.js", log="§28.11"),
    dict(name="复眼光轴方位", value="±63.1°", source="MuJoCo 实测（此前假设 ±50°）",
         code_check=("dodge/eyecam.js", r"EYE_AZ\s*=\s*([\d.]+)\s*\*\s*Math\.PI", "63.1"),
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
    dict(id="shuffle_controls", what="我们自己用过的每一处「打乱连接组」对照，打乱之后网络还活着吗",
         status="reproduced",
         result="**三处都不是空对照**。全脑 346 → **61** 个活跃神经元（18%）；"
                "游戏子回路 60 s 起跳 32.7 → **2.0** 次；"
                "五子棋水库**反而更活跃**——每个局面活跃神经元 1795 → **3055**",
         caveat="起因是 §42：别人那条实验的打乱臂读出完全不放电，判据因此是空的。"
                "这条教训回头套自己身上才不是双标。"
                "五子棋那一行还顺带解释了 §41.6 的翻盘：打乱脑下棋「更强」很可能只是因为"
                "**它给读出层的特征更丰富**（打乱破坏抑制的特异性 → 整体更易兴奋），而不是它更懂棋",
         script="scripts/check_shuffle_controls.py", result_file="results/shuffle_controls.json", log="§42.1",
         verify=[("full_brain.shuffled_active_median", 61, 0), ("all_alive", True, 0),
                 ("gomoku.shuffled.mean_active_per_position", 3055.2, 0.1),
                 ("gomoku.intact.mean_active_per_position", 1795.3, 0.1),
                 ("game_subcircuit.shuffled_jump", 2.0, 0.05)]),
    dict(id="gomoku_reservoir", what="把果蝇脑当「水库」训练它下五子棋，连接组有贡献吗",
         status="negative",
         result="**没有，而且两版子回路上都一样**。脑里一个突触都不训练、只训练一层线性读出："
                "子回路 v3 上真实连接组测试 top1 **0.0213**、**打乱接线 0.0190**（差 0.0023），"
                "而直接看棋盘 **0.1745**（8 倍）；拼接反而更差（0.0786）。"
                "v2 上是 0.0244 / 0.0178 / 0.1745——**同一个结论重复了一次**。"
                "连「保拓扑编码」（按真实胞体位置铺棋盘）也救不回来（v2 上 0.0248）",
         caveat="12,270 个局面、500 局自对弈、按整局切分。只用了线性读出——更强的读出可能挖出更多，"
                "但那正是 Mineault 批评的「读出层足够灵活就能学会任何东西」。"
                "棋盘→神经元的映射是任意的；禁手由规则引擎判定，不是果蝇。"
                "**这条阴性结果的意义**：「把连接组接进游戏 + 训练读出层」本身不能证明连接组在起作用，必须跑打乱对照",
         script="gomoku/train_readout.py", result_file="results/gomoku/train_v3.json", log="§38.4 + §41",
         verify=[("arms.fly_intact.best.test.top1", 0.0213, 0.0005),
                 ("arms.fly_shuffled.best.test.top1", 0.019, 0.0005),
                 ("arms.board_raw.best.test.top1", 0.1745, 0.0005),
                 ("random_baseline_top1", 0.0171, 0.0005)]),
    dict(id="gomoku_play", what="让真实脑与打乱脑真下 40 局，棋力上分得开吗",
         status="negative",
         result="**分不开，而且第一版的结论被自己推翻了**。子回路 v2 上：打随机真实 33/40、打乱 24/40"
                "（差 22.5 pp，越过事先定的 15 pp 线，当时判「有贡献」成立）；"
                "换到子回路 v3 重跑，**完全反过来**——真实 **26/40**、打乱 **40/40**，"
                "正面交锋真实脑 **0/40** 被打乱脑完胜。换一版子回路就翻盘，说明那个差别不可重复。"
                "两版里两者都被启发式老师 **0:40** 完胜",
         caveat="这条的价值在于**它推翻了我们自己先前的判定**：单看 v2 会得出「连接组对棋力有贡献」，"
                "重复一次就没了。与读出层的准确率一致（真实 0.021 vs 打乱 0.019，两版都看不出差别）。"
                "每组 20 局，n 很小；v2 那 40 局里执白的赢了 38 局，先后手效应本来就远大于两个脑的差别",
         script="gomoku/play_test.js", result_file="results/gomoku/play_v3.json", log="§38.4 + §41",
         verify=[("vs_random.fly_intact", 26, 0), ("vs_random.fly_shuffled", 40, 0),
                 ("head_to_head.fly_intact", 0, 0), ("vs_teacher.fly_intact", 0, 0),
                 ("criterion_connectome_helps_play", False, 0)]),
    dict(id="touch_pathway", what="「只给物理量、不写判断逻辑」能让果蝇自己绕开围栏吗",
         status="reproduced",
         result="**能，但前提是子回路里真有那条通路**。触感送到触角 JO（v2 唯一的机械感觉）**完全无效**"
                "——JO 只通到梳理指令；重裁含**头部刚毛**的子回路 v3 后，同样的触感让走过的格子从 "
                "**9 涨到 31.5**、路程 **156 → 603 mm**，中间没有任何我们写的判断逻辑。"
                "全脑查证：头部刚毛（305 个）到转向/逃逸只要 **2 跳**",
         caveat="指标换过一次：第一版用「贴墙时间占比」，它**分不出「钉死在一点」和「贴着墙滑行」**，"
                "按那个指标触感「没用」（85.6% → 85.6%）。指标选错，阴性结果就是假的。"
                "另外 FlyWire 是**脑**的连接组，腿部与刚毛的机械感觉大部分在腹神经索里，不在这份数据中",
         script="dodge/touch_test.js", result_file="results/dodge/touch.json", log="§38.3",
         verify=[("arms.v3 · 触感→头部刚毛.mean.cells", 31.5, 0.6),
                 ("arms.v3 · 什么都不给.mean.cells", 9, 0.6),
                 ("arms.v2 · 触感→JO.mean.cells", 9, 0.6)]),
    dict(id="wall_vision", what="像素路径看得见围栏吗（架构质疑：手写前端只看球）",
         status="partial",
         result="**看得见，但分不出来**。静止时读数恒为 0；朝墙走 LPLC2 中位 **34.2**、p95 140.6，"
                "而**背墙走**是 23.5 / 111.4——两者几乎重叠。所以缺陷不是「墙没接进去」，"
                "而是这套 LPLC2 汇集**不对自体运动做补偿**，走路本身就制造假逼近",
         caveat="§28.19 的「45 mm 外全瞎」是对 **2.5 mm 的球**说的，对墙不成立（墙是整面）。"
                "真果蝇有平衡棒与传出拷贝来抵消自体运动，我们的模型里没有",
         script="dodge/wall_vision_test.js", result_file="results/dodge/wall_vision.json", log="§38.2",
         verify=[("criterion_peak_above_control", True, 0), ("control_p95", 111.4, 0.2)]),
    dict(id="subcircuit_vs_full", what="4,599 个神经元的子回路能多大程度代表全脑",
         result="敲除模式整体重现：糖 Pearson **+0.75**、水 **+0.89**（n=10，同一口径两边各测一次）",
         caveat="单个神经元会失真。最典型是 CB0883：全脑里是枢纽（单敲 0.76、配对 0.24），子回路里**完全无作用**（1.07）——"
                "它依赖的旁路正是 wmin≥3 / K≤3 裁掉的。早先写的「+0.21 糖 / +0.92 水」是错的，来自混用归一化口径",
         script="dodge/subcircuit_vs_fullbrain_knockouts.py",
         result_file="results/dodge/subcircuit_vs_fullbrain_knockouts.json", log="§25.2",
         verify=[("sugar.pearson", 0.745, 0.002), ("water.pearson", 0.891, 0.002),
                 ("sugar.spearman", 0.576, 0.002), ("water.spearman", 0.842, 0.002), ("n", 10, 0)]),
    dict(id="redundancy_needs_sim", what="能不能只看连线就预测「一起敲会不会塌」",
         result="**不能**。路径重叠与配对 Δ 的 Spearman 是 **−0.008（糖）/ 0.013（水）**，且已排除指标退化",
         caveat="换成动力学指纹方向对但很弱（−0.21 / −0.14），而指纹本身就是单敲全脑仿真——省的是筛选，不是配对那一跑",
         script="screen/structure_vs_function.py", result_file="results/screen/structure_vs_function.json", log="§22",
         verify=[("sugar.pairs.spearman_overlap_vs_delta", -0.008, 0.002),
                 ("water.pairs.spearman_overlap_vs_delta", 0.013, 0.002)]),
    dict(id="two_pathways", what="糖和水是不是同一批神经元",
         result="**不是**。活跃集只重叠约三分之一（Jaccard 0.36），共同活跃的 128 个上效应也几乎不相关（Spearman 0.18、κ 0.15）",
         caveat="枢纽各自私有：CB0883 在水通路里根本不放电；CB0051 在糖通路里敲了没影响（0.97 vs 水的 0.49）",
         script="screen/pathway_compare.py", result_file="results/screen/pathway_compare.json", log="§21",
         verify=[("jaccard", 0.356, 0.002)]),
    dict(id="concentration", what="通路集中度能不能解释「模型在哪条通路上预测得准」", status="negative",
         result="**不能**。事先声明的方向是「越集中 → 连线越能预测」。实际 Gini 排 JON **0.922** ≈ 水 0.921 ≫ 糖 0.783，"
                "而连线预测器 G3 排 水 0.485 > 糖 0.316 > **JON 0.288** —— 最集中的通路反而最预测不了；换成 n80 也救不回来",
         caveat="**JON 一行必须取 `results/screen/jon_paper/concentration_full.json`**（论文刺激名单、596 个活跃神经元全打分）。"
                "`concentration.json` 里那一行（0.858 / n80 45 / G3 0.434、只给 326 个打分）是 §24.3 宣布作废的宽刺激运行，不得引用。"
                "两种「集中」本来就不同：水是几个神经元各担一部分（大量协同，n80=15），JON 是一个绝对瓶颈 aBN1 加一条长平尾（必需仅 5 个，n80 仍要 44）。"
                "n = 3 条通路，本来也撑不起任何排序结论",
         script="screen/concentration.py", result_file="results/screen/jon_paper/concentration_full.json", log="§22.2",
         verify=[("gini", 0.9224, 0.001), ("g3_spearman", 0.288, 0.001), ("n80", 44, 0)]),
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
         script="dodge/front_end_compare.js", result_file="results/vision/front_end_compare.json", log="§28.19",
         verify=[("摘要.自体运动噪声.峰值", 125.8, 0.1),
                 ("摘要.连接组可分辨的最远距离mm", 25, 0)]),
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
         script="screen/hub_scan.py", result_file="results/screen/hub_scan_summary.json", log="§16.2",
         verify=[("summary.n_synergy", 32, 0)]),
    dict(id="olfaction", what="全脑模型能不能给出嗅觉转向信号", status="negative",
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
         script="vision/ensemble_check.js", result_file="results/vision/ensemble_summary.json", log="§33",
         verify=[("LPLC2判据.A", 17, 0), ("LPLC2判据.可建模成员", 49, 0), ("测定成功", 50, 0)]),
    dict(id="lattice_distortion", what="flyvis 与 FlyWire 的柱坐标怎么对齐",
         result="用解剖（两视叶质心定左右、全脑质心→GNG 定腹侧、叉积定前后）加实测 T4/T5 方向，"
                "把 8 种朝向**钉到唯一一种**（旋转 φ=277°，即 u=−p, v=−q）",
         caveat="同时查出原流程有形变：`normalize()` 把 Codex 六边形基矢夹角**从 60.0° 拉成 122.6°**。"
                "换成保几何映射后「逼近 > 近距平移」翻转成立（3/3 重复），但只有一种映射给出该结果，属**有条件的修正**",
         script="vision/lattice_anchor.py", result_file="results/vision/lattice_anchor.json", log="§28.20",
         verify=[("T4T5拟合.phi", 277, 0)]),
]
