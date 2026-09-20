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
                         "方向该是对的。**追查过一次、预测被否**：假设是选择效应（朝威胁转才会进入正面一档），"
                         "事先写明「转向增益设 0 后应回到 43–57%」，实测仍是 **40.7% / 37.7%**，不成立。"
                         "2×2 表显示它也不是固定的左右偏置——威胁在左时左 DNa 更强的概率 66.9%、在右时 37.6%。机制未定，见日志 §44.1。"
                         "**第一版的 B 组是错的**：当时额外要求 |DNa 左右差| > 0.5 Hz 才算样本，"
                         "n 从 37,730 掉到 68、比例被抬到 76.5%——那是按被测量的信号本身筛样本，必然虚高。"
                         "另外这只是一个弱类比：模型里没有姿态、没有腿部准备动作，"
                         "而论文那条讲的是质心与腿的预备摆位",
                  script="dodge/takeoff_planning.js", result_file="results/dodge/takeoff_planning.json",
                  log="§32.2 + §44",
                  verify=[("pre_takeoff.frac_away", 0.5069, 0.002), ("no_takeoff.frac_away", 0.5231, 0.002),
                          ("criterion_A", False, 0), ("criterion_B", False, 0),
                          ("pre_bins.0.frac", 0.3502, 0.002), ("takeoffs", 496, 0),
                          ("front_table.pre.frac_dnaL_given_threatL", 0.6687, 0.0005),
                          ("front_table.pre.frac_dnaL_given_threatR", 0.3765, 0.0005)]),
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
             dict(id="gf_not_looming", what="巨纤维**不**响应逼近刺激（逃逸另有一条下行通路）", status="negative",
                  result="**在这个连接组模型里不成立，而且差距悬殊**。全脑里刺激 LC4/LPLC2 的 6 个条件，"
                         "巨纤维发放 **44–180 Hz**（每个条件 4 个独立试次里最低的一次也有 44 Hz）；"
                         "刺激其他通路的 28 个条件（糖、苦、JO、LC16、气味）巨纤维最高 **4 Hz**，其中 27 个是严格的 0。"
                         "有剂量关系（同侧巨纤维：40 Hz 刺激 → 92.5 Hz，100 Hz → 145.5 Hz），"
                         "LC4 单独（86.0）与 LPLC2 单独（112.5）都能驱动",
                  caveat="**量的不是论文原话**：论文是在体记录 + 真实视觉刺激，我们是直接给 LC4/LPLC2 注入泊松放电，"
                         "跳过了视网膜到小叶的全部视觉处理。所以结论只到「这张接线图 + LIF 参数下，"
                         "LC4/LPLC2 群体放电会强力、专一地驱动巨纤维」——站在 Ache 2019 一边、与 Fotowat 2009 的在体结果相反。"
                         "判据是看过参考表之后才写的（如实标注），但 44 对 4 Hz 的差距下判据怎么定结论都一样。"
                         "只读重算、零新仿真。"
                         "**这条与我们游戏的设计直接冲突**：游戏就是用巨纤维（DNp01）越阈来触发起飞的。"
                         "但这不是简单的对错——文献本身有张力：Fotowat 2009 测到巨纤维对 looming 不放电"
                         "（白眼果蝇 7 只全部如此，Dα7 突变体仍以 81–89% 概率逃逸）；"
                         "而 Ache et al. 2019（我们编码所依据的那篇）恰恰是在讲 LC4/LPLC2 怎么把 looming 编码进巨纤维。"
                         "von Reyn et al. 2014 的解释是**两种逃逸模式**：巨纤维负责「短模式」（牺牲稳定性换速度），"
                         "而 Fotowat 用的慢逼近（l/|v| 10–80 ms）引发的是先抬翅的「长模式」，那条不需要巨纤维。"
                         "**我们的模型里没有这两种模式之分**，也没有抬翅，所以「长模式不需要巨纤维」这一半仍然测不了——"
                         "要测它得先把长/短模式和抬翅建进去",
                  script="dodge/gf_looming_check.py", result_file="results/dodge/gf_looming_check.json", log="§43 + §45",
                  verify=[("looming_min_hz", 44.0, 0), ("other_max_hz", 4.0, 0),
                          ("n_looming_conditions", 6, 0), ("n_other_conditions", 28, 0),
                          ("n_other_strictly_zero", 27, 0),
                          ("dose.LOOM_L_40_GF_L", 92.5, 0.05), ("dose.LOOM_L_100_GF_L", 145.5, 0.05),
                          ("single_type.LC4_L_100_GF_L", 86.0, 0.05), ("single_type.LPLC2_L_100_GF_L", 112.5, 0.05),
                          ("paper_claim_holds_in_model", False, 0)]),
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
                  caveat=None, script="fba_export_replay.py", result_file="results/fba_replay/replay_summary.json", log="§4.1"),
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
    dict(name="五子棋老师的线型分值", value="成五 1e7 / 活四 1e5 / 冲四 2000 / 活三 1500 / 眠三 120 / 活二 100 / 眠二 10 / 单子 1", source="**手选**",
         code_check=("gomoku/teacher2.js", r"const ATT = \[0, 1, 10, 100, 120, (1500), 2000, 1e5, 1e7\]", "1500"),
         note="不是任何论文或引擎的值；老师的棋力主要来自搜索深度。它也是果蝇读出层阶段一的拟合目标（取 ln(分值+1)），所以果蝇学到的价值顺序是老师给的，不是它自己发现的",
         script="gomoku/teacher2.js", log="§46.3"),
    dict(name="五子棋线型的驱动", value="160 Hz × 300 ms，每通道约 61 个输入神经元，3 个泊松种子取平均", source="本项目按实测选定",
         code_check=("gomoku/line_map.js", r"const ms = opt\.ms \?\? (\d+), hz = opt\.hz \?\? (\d+)", "60/160"),
         note="窗口长度按「特征跨种子的相关」选：60 ms 中位 0.44、150 ms 0.77、300 ms 0.87（代码里的缺省 60 ms 只是缺省，流水线显式传 300）。通道→神经元的分配是固定种子的随机洗牌，是任意的",
         script="gomoku/line_features.js", log="§46.4"),
    dict(name="五子棋搜索引擎", value="每层宽度 K = 6（根 16）、先手系数 1.2", source="K 实测选定；先手系数**手选**",
         code_check=("gomoku/engine.js", r"const K = o\.K \?\? (\d+), K0", "6"),
         note="同等节点预算下 K=6 对 K=10 是 65–35（100 局，search_width.json）；先手系数换成 1.0 / 1.5 / 2.0 临时量过，都在 100 局的噪声里（没有存档，所以不写数字）。这两个属于搜索，不属于果蝇",
         script="gomoku/engine.js", log="§46.6"),
    dict(name="生活模式：声音与气味的物理换算", value="听觉神经元上限 200 Hz、声强半衰距离 60 mm、左右耳差 ±25%；嗅觉上限 200 Hz、气味羽流为高斯", source="**手选**",
         code_check=("dodge/game_core.js", r"audioRate: (\d+), soundRef: (\d+), earBias: ([\d.]+)", "200/60/0.25"),
         note="没有该模型下的声强 / 气味浓度定标数据。上限 200 Hz 与味觉、温湿度那几路取同一个值。没有为了让它被声音吓飞去调这些数或起飞阈值",
         script="dodge/game_core.js", log="§47.4"),
    dict(name="生活模式：身体状态", value="味觉感受器灵敏度增益 0.1–1.6（缺什么对什么更敏感）；MN9 > 10 Hz 算开吃；能量 / 水分的消耗与补充速率", source="方向有文献依据（Inagaki 2012），**幅度与速率手选**",
         code_check=("dodge/game_core.js", r"gainMin: ([\d.]+), gainMax: ([\d.]+)", "0.1/1.6"),
         note="身体状态不直接决定任何行为，只改感受器灵敏度与走路速度。开吃阈值从球场模式的 30 Hz 降到 10 Hz：水感受器开到 320 Hz，MN9 也只有 22 Hz（实测），30 Hz 水永远过不了",
         script="dodge/game_core.js", log="§47.6"),
    dict(name="蘑菇体回路：两处建模决定", value="触角叶局部神经元（ALLN，429 个）发出的突触一律取抑制性；页面用的 v5 里碰到蘑菇体的边只留 ≥2 个突触的", source="①有文献依据（Wilson & Laurent 2005；Olsen & Wilson 2008；Liu & Wilson 2013），**但属于手选的建模决定**；②工程取舍",
         code_check=("dodge/subcircuit_v5.py", r"MB_WMIN = (\d+)", "2"),
         note="①不改的话一闻到气味整个回路就失控；三个臂（原样 / 改抑制性 / 去掉）都跑了，按事先规则取改动最小且判据全过的。②全留是 129 万条边，页面装不下；裁完之后的回路与 Python 做过一致性检验（learning_engine_parity）",
         script="learn/mb_odor_coding.py", log="§48.1 + §48.5"),
    dict(name="可塑性规则与强化信号", value="学习率 0.003、KC 资格迹 200 ms、不遗忘；强化 = PAM 或 PPL1 整簇 30 Hz；气味 = 20 个嗅小球的 ORN 200 Hz；热到 0.5 以上算烫", source="规则形式来自文献（Hige 2015；Cohn 2015；Handler 2019），**数值手选**",
         code_check=("dodge/game_core.js", r"danRate: (\d+), painThermo: ([\d.]+), plastEta: ([\d.]+), plastTauE: (\d+)", "30/0.5/0.003/200"),
         note="学习率、气味宽度、频率只在另外的种子（5、6、999）上校准过，判据用的 6 对气味没有看过。第一次尝试的学习率 0.02 太大（1 秒配对压到 7%）。「糖 / 烫 → 多巴胺」这根线是手接的，因为连接组自己叫不起多巴胺神经元",
         script="learn/plasticity.py", log="§48.3"),
    dict(name="六条腿的身体", value="腿间相位耦合 8、失稳拖行的虚拟脚权重 0.6、着地判据足尖高 < 0.12 mm、重心在胸部原点后 0.2 mm", source="**手选**",
         code_check=("dodge/legs.js", r"coupling: (\d+), drag: ([\d.]+)", "8/0.6"),
         note="足尖轨迹与步幅来自 NeuroMechFly 录制的步态周期；「步幅差 → 偏航」的增益在创建时用同一套运动学数值标定，不是手调的",
         script="dodge/legs.js", log="§48.6"),
    dict(name="记忆 → 转向的桥（默认关）", value="价 = 奖赏隔室被压掉的比例 − 惩罚隔室被压掉的比例；转向 = 价 × 150 °/s × 两根触角浓度差的符号", source="**整个是手写的**",
         code_check=("dodge/game_core.js", r"memoryNav: (false), memoryTurn: (\d+)", "false/150"),
         note="实测记忆走不到运动输出（memory_to_motor，阴性），这座桥只是让页面上能看到「学了之后会怎样」，默认关、单独标着。第一版用 MBON 的瞬时发放，不起作用",
         script="dodge/game_core.js", log="§48.7"),
    dict(name="大自然：物理常数与世界的手选量", value="恢复系数 0.35、滚动阻力 0.15 g、低于 4 mm/s 且静摩擦兜得住就停、坡度对步速的系数 1.2（夹在 0.45–1.25）；地形三层值噪声（幅度 7 / 2.2 / 0.5 mm，波长 160 / 55 / 18 mm）；石板升温时间常数 20 s；约每 3–6 分钟一场雨", source="重力 9,810 mm/s²、自由落体、纯滚动的 5/7 是物理；**其余手选**",
         code_check=("dodge/nature.js", r"restitution: ([\d.]+), crr: ([\d.]+), restSpeed: (\d+), slopeK: ([\d.]+)", "0.35/0.15/4/1.2"),
         note="没有果蝇尺度下浆果在土面上的恢复系数 / 滚动阻力数据，取的是「软而粗糙的地面」的量级。物件种类与密度、天气节奏、雨点砸中的频率、甲虫出现的节奏都是为了让世界有东西可感受，不来自任何测量",
         script="dodge/nature.js", log="§49.4"),
    dict(name="生态箱：身体常数（奖励的来源）", value="不吃不喝时饥饿 600 s、口渴 480 s 到极限；drive 权重 饥 1 / 渴 1 / 体力 0.25 / 健康 3 / 气味 0.12 / 体温 0.6；被咬一口 −0.12 健康", source="**全部手选**；形式（drive reduction）取自 Keramati & Gutkin 2014",
         code_check=("eco/physiology.js", r"hungerTime: (\d+), thirstTime: (\d+)", "600/480"),
         note="这些常数就是奖励函数。它们写死在身体里，不对玩家开放；玩家能改的只有 eco/world.js 的 RULES。走路的代谢代价第一版设成静息的 1.5 倍，导致躺平成了理性选择，已按「昆虫步行只比静息高一两成」改正",
         script="eco/physiology.js", log="§50.1"),
    dict(name="生态箱：可塑性层的结构与超参", value="演员 - 评论家、线性、63 个特征；γ 0.995、λ 0.9、评论家学习率 0.03、演员 0.012（可遗传）、吃喝那一路 ×6、运动策略每步衰减 1e-4、权重上限 6", source="**全部手选**；超参在另一批种子（20000 起）上定，不在测试种子上",
         code_check=("eco/plastic.js", r"gamma: ([\d.]+), lambda: ([\d.]+), alphaV: ([\d.]+), ingestGain: (\d+)", "0.995/0.9/0.03/6"),
         note="特征里有三类：感觉神经元群的发放率（带群体泊松噪声）、大脑输出、身体内部状态。左右对称性是结构先验：往哪边转只读分侧信号。基因的变异幅度（eco/evolve.js 的 MUT）同样手选",
         script="eco/plastic.js", log="§50.4"),
]

# ── 本项目自己的结果（不是对某篇论文的复现，但同样是"我们知道什么"）──────────
FINDINGS = [
    dict(id="shuffle_controls", what="我们自己用过的每一处「打乱连接组」对照，打乱之后网络还活着吗",
         status="reproduced",
         result="**三处都不是空对照**。全脑 346 → **61** 个活跃神经元（18%）；"
                "游戏子回路 60 s 起跳 32.7 → **2.0** 次；"
                "五子棋水库**反而更活跃**——每种线型活跃神经元 717 → **1602**（线型版特征；v1 的 1795 / 3055 随 v1 一起作废）",
         caveat="起因是 §42：别人那条实验的打乱臂读出完全不放电，判据因此是空的。"
                "这条教训回头套自己身上才不是双标。"
                "五子棋那一行也解释了 §46 里打乱接线为什么不输：**它给读出层的特征更丰富**"
                "（打乱破坏抑制的特异性 → 整体更易兴奋，读出维度多一倍），而不是它更懂棋",
         script="scripts/check_shuffle_controls.py", result_file="results/shuffle_controls.json", log="§42.1",
         verify=[("full_brain.shuffled_active_median", 61, 0), ("all_alive", True, 0),
                 ("gomoku.shuffled.mean_active_per_position", 1602.0, 0.1),
                 ("gomoku.intact.mean_active_per_position", 717.3, 0.1),
                 ("game_subcircuit.shuffled_jump", 2.0, 0.05)]),
    dict(id="gomoku_v1_retracted", what="五子棋 v1（把整盘棋铺进果蝇脑）的结论还算数吗",
         status="negative",
         result="**不算数，全部作废**。`brain.setOpto` 换一批神经元时不清上一批的刺激，输入一个接一个叠上去："
                "线型 A 单独喂是 **252** 个脉冲，先喂过 B 再喂 A 得到 **1901** 个，"
                "逐神经元与真正的 A 相差 1665。v1 的每个棋盘喂进去几乎是同一个输入，读出层学的是噪声",
         caveat="作废的数字：一致率 0.021 / 打乱 0.019 / 直接看棋盘 0.175、对随机 26/40、正面交锋 0:40、"
                "以及「连接组对下棋没有贡献」这句话——那个实验本身是坏的，它既不支持也不否定任何说法。"
                "**游戏不受影响**：`game_core` 每步用 `setRate` 整组重写输入；修复前后 7 个任务 + 10 个突变体的结果逐项相同。"
                "教训：一个「几乎等于随机」的阴性结果，第一反应应该是查输入有没有真的送进去",
         script="gomoku/test_engine.js", result_file="results/gomoku/opto_leak.json", log="§46.1",
         verify=[("fixed.A_first", 252, 0), ("old_behaviour.A_after_B", 1901, 0),
                 ("old_behaviour.abs_diff_vs_true_A", 1665, 0), ("fixed.abs_diff_A_first_vs_again", 0, 0)]),
    dict(id="gomoku_lines", what="线型版：果蝇脑 + 一层线性读出，能学会给五子棋的每条线估价吗",
         status="reproduced",
         result="**能**。14,641 种线型每一种都在果蝇脑里跑一遍（4 套输入分配 × 3 个泊松种子；脑里一个突触都不训练），线性读出给出每条线的对数价值。"
                "测试一致率 **49.5%**（随机 1.5%、不经过脑子 34.8%）；"
                "外部考卷 Wine（别人的引擎，只考不训）**47.0%**；换一组从未见过的泊松种子只掉 3.5 个百分点。"
                "它从没见过棋形类别，自己排出的价值顺序（成五 > 活四 > 冲四、活三 > …）全部正确",
         caveat="事先写好的判据 B（比不经过脑子高 ≥ 5 个点）与 D（换种子掉 ≤ 5 个点）成立。"
                "D 是改了三次训练才过的：单种子 60 ms 窗掉 32 个点、300 ms 掉 17、3 种子平均掉 5.3，加噪声增广才到 3.5，代价是一致率少约 3 个点。"
                "这条路能成靠的是线型可以**全部枚举**——泛化到没见过的线型很差（留出 20% 线型认棋形只有 0.72，活四召回 0.02）。"
                "架构上限（每种线型一个自由参数）也只有 50.6%，老师自己的手写分值 56.2%",
         script="gomoku/train_lines.py", result_file="results/gomoku/train_lines.json", log="§46.2–46.5",
         verify=[("arms.fly_intact.test_top1", 0.4947, 0.0005), ("arms.fly_intact.wine_top1", 0.4704, 0.0005),
                 ("arms.fly_intact.seed_drop", 0.0348, 0.0005), ("arms.raw24.test_top1", 0.3485, 0.0005),
                 ("arms.fly_intact.distill_r2", 0.933, 0.0005),
                 ("criterion_B_brain_helps", True, 0), ("criterion_D_not_noise_hash", True, 0)]),
    dict(id="gomoku_wiring", what="真实接线比打乱接线、比随便一个随机网络更会下棋吗",
         status="negative",
         result="**不**。测试一致率：真实接线 49.5%、打乱接线 **48.8%**、同维度随机 ReLU 网络 **51.1%**；"
                "正面交锋（同一个引擎）直觉 14–20–6、想 4 步 23–16–1、想 6 步 25–15",
         caveat="事先写好的判据 C（一致率高 ≥ 5 个点）与 C2（想 4 步正面交锋 ≥ 60%）都不成立。"
                "这一版两个臂的读出维度相同：打乱接线活跃的特征列有 14,069 个，随机取了与真实接线一样多的 7,493 个——维度相同仍然不输，"
                "所以能说的是「这颗脑子是一个够用的非线性展开」，不能说「真实接线对下棋有特殊贡献」",
         script="gomoku/play_lines.js", result_file="results/gomoku/play_lines.json", log="§46.5–46.6",
         verify=[("head_to_head.d4.win", 23, 0), ("head_to_head.d4.loss", 16, 0), ("criterion_C2.passed", False, 0)]),
    dict(id="gomoku_strength", what="放进搜索之后，它下得怎么样（用户的目标：棋力）",
         status="partial",
         result="想 6 步：对旧老师（v1 的对手，v1 是 0:40）**40–0**，对老师搜 4 步 **31–9**，对搜 6 步 19–21，对搜 8 步 6–14；"
                "想 10 步：对搜 6 步 34–6、对搜 8 步 **13–7**。只凭直觉：对随机 40–0、对旧老师 18–18–4",
         caveat="判据 A（直觉对旧老师 ≥ 50%）**不成立**（45.0%）；A2（想 6 步对老师搜 4 步 ≥ 50%）成立（77.5%）。"
                "**棋力主要来自搜索深度，不是来自果蝇**：向前推演是 alpha-beta 做的，搜索只懂规则（成五、必须挡五、禁手）、不含棋形分值；"
                "每多搜一步节点数约 ×2.26（`depth_timing.json`：深度 14 要 10.13 秒）。每组 40 局（深度 8 的老师 20 局），标准差约 8 个百分点。"
                "表的精度也值棋力（给老师的表加噪声到 R² 0.85，同深度胜率从 45.0% 掉到 20.0%），但这颗脑子可靠的精度上限在 R² ≈ 0.85–0.88",
         script="gomoku/play_lines.js", result_file="results/gomoku/play_lines.json", log="§46.6",
         verify=[("engine.fly_intact.d6.old_teacher.win", 40, 0), ("engine.fly_intact.d6.teacher2_d4.win", 31, 0),
                 ("engine.fly_intact.d10.teacher2_d8.win", 13, 0), ("engine.fly_intact.d1.old_teacher.win", 18, 0),
                 ("criterion_A.passed", False, 0), ("criterion_A2.passed", True, 0)]),
    dict(id="gomoku_multiview", what="多给果蝇脑几套输入分配（视角），读出层能更准、棋下得更好吗",
         status="reproduced",
         result="**能，但很快饱和**。换一组种子后对评分表的拟合 R²：1 个视角 0.834、2 个 0.8785、3 个 0.8973、4 个 **0.9006**。"
                "4 个视角的表对单视角的表（同一个引擎都想 6 步）**113–87（56.5%）**，换一批开局再下 200 局 113–87；"
                "一致率 45.1% → **49.5%**，外部考卷 Wine 41.3% → **47.0%**",
         caveat="事先写死的换用判据是「新表对旧表 200 局胜率 ≥ 55%」。**第一次没过**（93–107，46.5%）："
                "当时阶段一的岭系数固定为 10，维度一多就去拟合噪声。改成每个臂用另一半训练种子自己选岭系数之后重训，才是上面的结果——所以这是**第二次尝试**，两次都在这里。"
                "视角 = 把 24 个通道分给另一批输入神经元的另一张随机分配表；靠分时间段加维度是死路（样本内 R² 0.976、换种子 0.386）。"
                "对老师搜 6 步新旧两张表没有差别（32–28 对 34–26），提升是小幅的",
         script="gomoku/compare_tables.js", result_file="results/gomoku/compare_linetable_fly_intact_mv2.json", log="§46.8",
         verify=[("head_to_head.win", 113, 0), ("head_to_head.loss", 87, 0), ("adopt", True, 0)]),
    dict(id="gomoku_depth_models", what="多步推理能训练进读出层吗（用户的要求：推理必须来自训练好的模型，不能是下棋时现跑的搜索）",
         status="negative",
         result="**基本训练不进去**。对 N = 1–6、8 各训练一个读出层（标签 = 向前搜 N 步的最佳着），下棋时只做模型推理、不搜索。"
                "7 个模型棋力几乎一样：对旧老师 65–70–65（1 步）到 72–88–40（8 步），对老师搜 2 步 33–67、搜 4 步 26–74；"
                "8 步模型对 1 步模型 **72–86–42**",
         caveat="事先写好的判据「用 8 步标签训练的模型 对 用 1 步标签训练的模型，200 局胜率 ≥ 55%」**不成立**（36.0%，和棋算未胜）。"
                "原因是架构上限：读出层只能给每条线一个价值再相加，「向前看」需要的组合推理它表达不了。"
                "页面按用户的要求默认用纯模型推理（推理步数 = 换读出层），alpha-beta 只作为默认关闭、标明「算法，不是果蝇」的外挂保留；"
                "同一张表交给搜索想 6 步，对老师搜 4 步是 31–9——差距全部来自搜索",
         script="gomoku/depth_models.js", result_file="results/gomoku/depth_models.json", log="§46.9",
         verify=[("criterion.passed", False, 0), ("vs_d1_model.8.win", 72, 0), ("vs_d1_model.8.loss", 86, 0),
                 ("vs.8.teacher2_d4.win", 26, 0)]),
    dict(id="gomoku_rl", what="自对弈强化（「多巴胺」式三因子规则）能让它更强吗",
         status="negative",
         result="**不能**。Δw = 学习率 × δ × 资格迹，δ = 这一局的结果 − 近期平均。强化后的表对监督版（同一个引擎都想 4 步，200 局）"
                "**6–194（3.0%）**，事先定的线是 55%；换更小的步长、更多的局数再跑一次是 99–101（49.5%）",
         caveat="**δ 是在连接组外面算的**：这个模型自己的多巴胺神经元在非失控条件下不放电（§11，PAM 0/307），不存在「果蝇自己的奖励信号」。"
                "每轮几十局的胜负太吵，推不动一个 7494 维的读出层。页面上的果蝇用的是监督训练的表",
         script="gomoku/selfplay_rl.js", result_file="results/gomoku/rl.json", log="§46.7",
         verify=[("final.d4_vs_supervised_d4.win", 6, 0), ("criterion_passed", False, 0),
                 ("win_rate_vs_supervised", 0.03, 0.0005)]),
    dict(id="eco_surface", what="生态箱：把 15,055 个神经元的真脑蒸馏成响应面（27 路输入 → 12 个读出），好让 32 只果蝇的进化跑得动",
         status="reproduced",
         result="真脑一只 1.18 倍实时、32 只 0.037 倍。用真脑跑 7,200 组输入拟合；留出集（单次试验、原始 Hz）R²：左转 0.927、右转 0.907、巨纤维 0.993、MN9 0.951（事先定的线 ≥ 0.85）。"
                "第一版（3,600 个样本、log1p 目标）转向只有 0.67 / 0.79，没过线，留档在 surface_fit_v1.json",
         caveat="响应面没有记忆（真脑在两次决策之间保留状态），给的是 300 ms 窗的平均发放率，单次试验的噪声按泊松加回去。PAM 在全部样本里从不放电，响应面里恒为 0。判据没动，动的是目标变换（log1p → sqrt）和样本量",
         script="eco/fit_surface.py", result_file="results/eco/summary.json", log="§50.3",
         verify=[("surface.pass", 1, 0), ("surface.n_samples", 7200, 0), ("surface.features.0.r2", 0.9266, 0.0001), ("surface.features.2.r2", 0.9926, 0.0001)]),
    dict(id="eco_m2_learning", what="生态箱 M2：只给物理量和内生奖励（身体不适的减少），接在固定连接组旁边的可塑性层能不能自己学会活得更久",
         status="partial",
         result="3 个个体各连续 30 条命后冻结学习，在 30 个没见过的世界上测：不学习 460 s，学习 ≥ 1800 s（截尾，× 3.913）；C1（≥ 1.5 ×）3/3 通过，C2（打乱奖励不提升）3/3 通过；另换 10 个个体 10/10 学成；长期训练任务（eco/train_long.js，又 10 个新个体，学成即毕业）10/10 学成、换新世界复测 10/10，共 100 条命。"
                "学到的是「碰到水就停下来喝」（连接组里水味先天不够伸喙）和「湿度上升时少拐弯」",
         caveat="标 partial 的原因：**远距离找水 / 找食物没学会**（干旱世界不学习 383 s、学习 386 s，训练 120 条命 387 s）；可塑性层看不到大脑输出时学得一样好（× 3.913）——连接组在这里给的是身体和反射，不是学习信号。"
                "第一版 C2 只过了 2/3（打乱对照是漏的：奖励只延后 20–60 s，与持续几十秒的喝水仍相关；事后加的轭式对照不提升）。关掉「不用就忘」10 个个体只有 4/10 学成（3 个贴墙、3 个躺平）。寿命在 1,800 s 截尾，倍数是下限",
         script="eco/m2_learning.js", result_file="results/eco/summary.json", log="§50.4",
         verify=[("m2.C1", 1, 0), ("m2.C2", 1, 0), ("m2.individuals.0.ratio_on", 3.913, 0.001), ("m2.robust_learned", 10, 0), ("long.n_learned", 10, 0), ("long.n_retest_ok", 10, 0), ("m2.drought_on", 386, 0)]),
    dict(id="eco_m3_evolution", what="生态箱 M3：32 只果蝇、10 个可遗传参数、没有适应度函数——不同的世界规则会不会把「飞行倾向」推向不同方向",
         status="reproduced",
         result="三个世界各 5 个种子 × 10,800 s：甲虫横行 平（Δ 均值 -0.51，寿命 445 → 1841 s，先天喝水 +1.65）；风平浪静 平（Δ 均值 -0.04，寿命 604 → 2779 s，先天喝水 +1.02）；地广物稀 降（Δ 均值 -1.39，寿命 617 → 1339 s，先天喝水 +1.23）。事先写定的判据（至少两个世界标签不同）通过",
         caveat="飞行是固定的 1.2 s / 72 mm 弹道，能进化 / 能学的只有「起不起飞」（飞行控制没接进连接组，见 docs/ecobox/AUDIT.md）。3 小时箱内时间只有几到十几代，种群 32 只，漂变不小。可塑性层不遗传；种群快灭绝时从名人堂补进来的个体单独计数（迁入）。变异幅度手选",
         script="eco/m3_evolution.js", result_file="results/eco/summary.json", log="§50.5",
         verify=[("m3.pass", 1, 0), ("m3.worlds.0.delta_mean", -0.509, 0.001), ("m3.worlds.1.delta_mean", -0.037, 0.001), ("m3.worlds.2.delta_mean", -1.394, 0.001)]),
    dict(id="eco_live_check", what="生态箱：在响应面上学成的个体，放回真的 15,055 神经元脉冲网络里还管不管用",
         status="partial",
         result="3 个世界种子、上限 900 s：真脑 900 s，响应面 825 s，白纸 469 s。L1（真脑 ≥ 1.5 × 白纸）通过（× 1.92）；L2（喝水时间占比在响应面的 0.5–2 倍内）未通过（0.167 对 0.041）",
         caveat="只有 3 条命、上限 900 s（真脑约 1.2 倍实时）。真脑的读出按约 300 ms 平滑以对齐响应面的噪声窗口",
         script="eco/live_check.js", result_file="results/eco/summary.json", log="§50.7",
         verify=[("live.live_median", 900, 0), ("live.naive_median", 469, 0)]),
    dict(id="eco_m4_save", what="生态箱 M4：存档 → 清空 → 读回 → 接着跑，是否与不中断逐位相同",
         status="reproduced",
         result="四项全过：续跑状态指纹相同（ae890128:764327）、存档格式稳定、挑战码（167 个字符）来回无损、坏输入被拒绝。页面里再验一次（eco/page_test.js）",
         caveat="「逐位相同」指同一份页面代码、同一个 JS 引擎；存档约 0.9 MB，超出本机存储配额时要用导出文件。云端保存没做",
         script="eco/m4_save_test.js", result_file="results/eco/summary.json", log="§50.6",
         verify=[("m4.pass", 1, 0)]),
    dict(id="nature_world", what="把篮球场换成一个有重力、有天气、没有边界的 3D 大自然，物理对不对、果蝇在里面过得怎么样",
         status="reproduced",
         result="九条事先写好的物理判据全过：30 mm 自由落体 0.08 s（解析值 0.0782 s）；弹起高度 3.09 → 0.19 mm，不生能量；"
                "坡度 0.26 的陡坡上 1 秒滚落 3.04 mm、缓坡上停得住；石头不可穿透；风把气味吹向下风（下风 0.811 对上风 0.064）；闭环里走 60 秒从不穿进实心物件。"
                "在里面过 3 分钟（3 个种子均值）：走 2676 mm、被石头之类挡住 26.0 s、起飞 5.7 次、掉下来 17.3 颗浆果、碰到糖 1.0 次（平地开放世界 2.3 次）",
         caveat="世界只通过已有的感觉通道进到脑子里，没有新增行为规则；**默认的视觉前端仍是手写的逼近检测，石头、草、地形不在它的视觉里**（真实像素那条通路可选，默认关）。"
                "果蝇自己的身体仍是运动学，不会摔倒；受重力支配的是浆果。水洼是水位不是流体。地形、物件密度、恢复系数、滚动阻力、坡度系数、天气节奏全部手选（PARAMETERS）。"
                "威胁从飞来的球换成了爬过来的甲虫：毫米尺度上 60 mm/s 的抛体 0.1 秒就落地，「慢慢滚过来的球」不物理",
         script="dodge/nature_test.js", result_file="results/dodge/nature_test.json", log="§49",
         verify=[("all_pass", True, 0), ("tests.N1_free_fall.t_sim", 0.08, 0.0001), ("tests.N4_rolls_downhill_only_when_steep.dropped_mm", 3.04, 0.01), ("tests.N9_closed_loop_walk.max_penetration_mm", 0, 1e-6)]),
    dict(id="olfactory_runaway_source", what="嗅觉输入在这个模型里为什么一给就全脑失控（§11.4 挂了六天的问题）",
         status="reproduced",
         result="**源头是触角叶局部神经元（ALLN）的递质符号**。把它们发出的突触改成抑制性（文献里它们绝大多数是 GABA / 谷氨酸能）："
                "蘑菇体回路里活跃的凯尼恩细胞从 **76.5% 降到 3.5%**（真果蝇约 5–10%），不同气味的 KC 集合几乎不重合（Jaccard 0.005）；"
                "**回到全脑复核**：原样 6 / 6 次失控（其他活跃神经元中位 10212），改后 **0 / 6**（中位 1008）。事先写下的预测成立",
         caveat="这是对递质符号的纠正（手选的建模决定，登记在 PARAMETERS），不是行为规则。全脑复核用的是自写的 numba LIF（方程、参数、每步顺序与 Brian2 版相同），不是 Brian2 本身。"
                "不失控之后单侧气味仍然**没有左右偏侧**（LI -0.01 / -0.06，判据 |LI| ≥ 0.2 且符号相反）",
         script="learn/fullbrain_alln.py", result_file="results/learn/fullbrain_alln.json", log="§48.1",
         verify=[("arms.raw.n_runaway", 6, 0), ("arms.alln_inh.n_runaway", 0, 0), ("arms.alln_inh.median_active", 1007.5, 0.5), ("prediction_holds", True, 0), ("lateralization.lateralized", False, 0)]),
    dict(id="dopamine_not_recruited", what="糖 / 苦 / 热 / 湿这些感觉，能不能靠真实接线把多巴胺神经元（PAM / PPL1）叫起来",
         status="negative",
         result="**不能**。专门为这个问题裁的回路（16,435 个神经元：蘑菇体 ∪ v4 ∪ 所有「感觉 → DAN」≤3 跳路径）里，四种感觉各三档强度共 12 个条件，没有一个失控，"
                "而发放 ≥5 Hz 的多巴胺神经元**最多 0 个**。与 §11.1 的全脑结果一致，并补上了热和湿",
         caveat="结构上是通的（最少 2–3 跳）。推测原因同 §11.1：真实的奖赏通路走章鱼胺 / 神经肽等慢调质，模型只有快递质符号。"
                "所以学习实验和页面里的强化信号是**手接的一根线**（吃到糖 → PAM、烫 / 苦 → PPL1），等价于实验里用光遗传激活多巴胺神经元",
         script="learn/reinforcement_route.py", result_file="results/learn/reinforcement_route.json", log="§48.2",
         verify=[("any_route", False, 0), ("max_dan_ge5hz_without_runaway", 0, 0)]),
    dict(id="mushroom_body_learning", what="给连接组的蘑菇体加一条文献里的突触规则（多巴胺门控的 KC→MBON 压低），它学得会吗",
         status="partial",
         result="**学得会，特异性差一点**。训练后被强化隔室的 MBON 对配对气味的响应降到对照的 **0.00**（L1 ≤ 0.7 成立）；多巴胺与气味错开给则不变（0.99，L3 成立）；"
                "PAM 与 PPL1 各压低 17 / 13 个 MBON、重合 0.00（L4 成立，MBON11 落在 PPL1 一侧，与解剖一致）；"
                "**没配对的气味也掉到 0.82（L2 ≥ 0.85 不成立）**",
         caveat="这是第二次尝试：第一次（mb_conditioning_v1.json）三条判据不过，原因是设计（多巴胺全局归一、学习率过大、气味对本身相似、指标被无关隔室稀释），在看新结果之前改掉、阈值不变。"
                "打乱 ALPN→KC 接线后照样学得会（0.00，事先写下的预期），特异性更差（0.66）：连接组的贡献在隔室，不在这一层的具体接线。"
                "强化信号手接；学习率 / 资格迹时间常数手选，只在另外的种子上校准过；气味是合成的（各 20 个嗅小球）",
         script="learn/mb_conditioning.py", result_file="results/learn/mb_conditioning.json", log="§48.3",
         verify=[("arms.connectome.median_ratio_paired_csp", 0.00024837521215382706, 0.001), ("arms.connectome.median_ratio_paired_csm", 0.8166666666666667, 0.001), ("arms.connectome.median_ratio_unpaired_csp", 0.9890710382513661, 0.001),
                 ("arms.connectome.criteria.L2_specific", False, 0), ("arms.connectome.compartment_jaccard", 0.0, 0.001), ("arms.shuffle_pn_kc.criteria.L1_learned", True, 0)]),
    dict(id="memory_to_motor", what="蘑菇体里形成的记忆，走不走得到运动输出（前进 oDN1 / BDN2、转向 DNa01 / 02、后退 MDN）",
         status="negative",
         result="**走不到**。训练后各测 12 次，6 组（气味对 × PAM / PPL1）里，五个读出满足「Welch |t| ≥ 3 且差 ≥ 20%」的组数最多 **0**。"
                "原因：有运动落点的四类 MBON（12 / 26 / 27 / 35）对气味一个脉冲都没有，被 APL 压死——APL 在真果蝇里不放电，LIF 把它当放电神经元、顶着不应期上限放电",
         caveat="事先声明只试一次的一刀（切掉 APL→MBON）：有响应的 MBON 类型增到 16 / 35，记忆传到了一些别的下行神经元（探索性），但五个读出仍是 0 组，判据不成立；**这一刀没有采用**。"
                "所以页面上的「记忆 → 转向的桥」是手写的、默认关",
         script="learn/memory_to_motor.py", result_file="results/learn/memory_to_motor.json", log="§48.4",
         verify=[("M2_any_stable", False, 0), ("max_hits", 0, 0), ("n_rows", 6, 0)]),
    dict(id="learning_engine_parity", what="页面引擎（brain.js 稀疏推进 + plasticity.js）与 Python 在同一份 v5 回路上学到的一样吗",
         status="reproduced",
         result="**一样**。同一个条件化流程、4 个种子：未配对气味的 MBON 总发放 719.8 对 720.8 Hz；各 MBON 的突触剩余强度相关 r = 0.9999；四条事先写好的判据全过",
         caveat="页面引擎那一半是 learn/parity_js.js。两边随机数不同，比的是统计量。稀疏推进不逐位等于稠密推进（回静息用了阈值、同一步内求和顺序不同），所以球场 / 五子棋（v3）不开它",
         script="learn/parity_py.py", result_file="results/learn/parity.json", log="§48.5",
         verify=[("all_pass", True, 0), ("strength_pearson", 0.9998756216361215, 0.0001)]),
    dict(id="six_leg_body", what="让身体由六条腿推着走（支撑脚的运动学解出身体位移），而不是按速度滑行",
         status="reproduced",
         result="四条事先写好的判据全过：直行 18.29 mm/s（指令 18）、转向 +60.7 / -60.6 °/s（指令 ±60）、后退 -12.19 mm/s（指令 −12）、任何时刻着地 ≥ 4 条腿。"
                "截掉左前腿：速度 15.7 mm/s、偏航 +10 °/s",
         caveat="运动学，没有动力学和打滑；推进相按匀速直线理想化（直接回放录制的足尖轨迹会凭空转出 ±15° 的摆动）。**腿的节律与腿间协调是手写的**——腹神经索连接组给不出三足步态（§12）；大脑给的只是几个下行神经元的发放。截肢后没有适应",
         script="dodge/legs_test.js", result_file="results/dodge/legs_test.json", log="§48.6",
         verify=[("all_pass", True, 0), ("tests.T1_straight.path_speed", 18.29049908248401, 0.01), ("tests.T4_support.min_stance", 4, 0)]),
    dict(id="embodied_learning", what="大脑 + 身体闭环之后，它在身体里学得会吗（页面引擎的六条腿身体；物理仿真的 NeuroMechFly）",
         status="partial",
         result="**奖赏记忆两个身体里都成立**：页面引擎里 A 在奖赏隔室的输入剩 25%（对照 99%）；物理身体里 MBON 响应 0 对 70 Hz。"
                "**惩罚记忆在物理身体里不成立**（只到对照的 89%，判据 ≤ 70%）：它走到 B 味的热源跟前就自己掉头走了，PPL1 只放了 0.5 s。"
                "二选一（互换设计，每组 40 只，走向 A 的比例，「A 配糖」组 vs「B 配糖」组）：桥关着 78% vs 62%；打开手写的桥 85% vs 50%",
         caveat="那个掉头没有人写，两个身体里都出现；分开测（learn/uturn_cause.js）主要是**气味 B** 引起的（只放 B：左侧 DNa 66 Hz、0/5 走穿；只放热 3/5 走穿；只放 A 毫无反应）——两种合成气味在连接组里天生不一样。把转向指令置 0 它就一路走穿、被烫 1.3 s、惩罚记忆很强——身体的行为决定了它学到什么。"
                "物理闭环（learn/embodied_loop.py）只跑了 1 个种子、30 s。桥是手写的（第一版不起作用，见 game_learning_bridge_v1.json），默认关。二选一的第一轮设计（训练过 vs 没训练过、每组 12 只）因天花板效应和样本太小作废，留在 game_learning_choice_v1.json",
         script="learn/game_learning.js", result_file="results/learn/game_learning.json", log="§48.7",
         verify=[("criteria.G1_reward_memory", True, 0), ("criteria.G2_punish_memory", True, 0), ("criteria.G3_control_flat", True, 0), ("criteria.G4_no_behavior_without_bridge", True, 0), ("criteria.G5_bridge_works", False, 0),
                 ("trained.memA.PAM", 0.247556337850842, 0.001)]),
    dict(id="hearing_priming", what="给它听觉之后，声音在行为上有没有用（听觉神经元 1 跳到巨纤维）",
         status="reproduced",
         result="**有，但不是「听到就跑」**。声音单独驱动不了起飞（听觉神经元 200 Hz 时巨纤维读出约 80 Hz，起飞阈值 90）；"
                "它让**逼近反应提前**：同一颗慢球，起飞提前量中位 **435 → 825 ms**，躲开 **24 → 38 / 100**；"
                "切断听觉神经元的传出突触之后回到 425 ms、25 / 100",
         caveat="探索性：这个对照是看过生活模式的初跑（声音一次也没把它惊飞）之后才想到的。事先写好的判据 H1「声音后 1 s 内起飞 ≥ 20%」**不成立**（5%，失聪 2%）。"
                "没有为了让它被吓飞去调起飞阈值或声音强度。声强随距离的衰减与左右耳差是手写的；效应本身（声音 + 逼近在巨纤维上相加）来自连接组",
         script="dodge/sound_priming.js", result_file="results/dodge/sound_priming.json", log="§47.4",
         verify=[("groups.无声.lead_ms_median", 435, 0), ("groups.有声.lead_ms_median", 825, 0), ("groups.有声.dodged", 38, 0), ("groups.无声.dodged", 24, 0)]),
    dict(id="olfaction_no_pathway", what="给它嗅觉之后（醋 DM1、土臭素 DA2 两个嗅小球），闻得到的东西会让它走过去或躲开吗",
         status="negative",
         result="**不会**。两路单独驱动各能激活上百个神经元，但没有落到六个运动读出的任何一个上；自己过日子的 10 分钟里，碰到糖的次数完整 7.667、失嗅 8.667，没有差别",
         caveat="事先写好的判据 H2 不成立。与 §10 全脑上「嗅觉没有左右偏侧化」一致。只取了两个嗅小球（全取 1,850 个 ORN 会把触角叶和蘑菇体都卷进子回路）。"
                "唯一测到的作用是调制：醋味会压低碰触引起的转向（DNa 6.0 → 0.7 Hz）。「吸引 / 厌恶」是文献给这两个小球的标签，不是写进模型的规则",
         script="dodge/life_test.js", result_file="results/dodge/life_test.json", log="§47.2 + §47.5",
         verify=[("H2.passed", False, 0), ("conds.intact.mean.sugar_contacts", 7.667, 0.001), ("conds.anosmic.mean.sugar_contacts", 8.667, 0.001)]),
    dict(id="isn_sign", what="用真实的内感受神经元 ISN（感知饥渴）代替手写的口渴规则，行不行",
         status="negative",
         result="**不行：模型里 ISN 的作用方向与文献相反**。文献（González-Segarra 2023）：ISN 活动增强 → 吃糖增多、喝水减少。"
                "模型里驱动 ISN（200 Hz）把吃糖的 MN9 从 **44.1 Hz 压到 2.5 Hz**；它是一个对伸喙的通用抑制",
         caveat="ISN 用的是神经肽 dILP3，LIF 模型只有预测的快递质符号（与 Usnea 那条同类）。**没有为了得到「饿了想吃」去翻转它的符号。**"
                "页面上留了一个默认关闭的「ISN 通路」开关。身体状态改由感受器灵敏度体现（见下一条）",
         script="dodge/sense_modulation.js", result_file="results/dodge/sense_modulation.json", log="§47.3",
         verify=[("rows.2.base_hz.mean", 44.1, 0.01), ("rows.2.hz.mean", 2.5, 0.01), ("rows.2.modulates", True, 0)]),
    dict(id="body_state", what="身体状态（能量 / 水分）只调味觉感受器的灵敏度、不写任何「饿了就吃」的规则，够不够",
         status="reproduced",
         result="**够**。碰到糖后开吃的比例：饿着 **100%**、饱着 **32%**（判据 H3：≥ 1.5 倍，成立）。"
                "还出现了没人写过的饱腹感：完整条件下几乎每次碰到糖都开吃（7.667 / 7.667），却一块也没吃完——吃一两秒能量上来，糖感受器变钝，MN9 掉到阈值以下，它就走开了",
         caveat="「缺什么对什么更敏感」有文献依据（Inagaki et al. 2012：饥饿经多巴胺提高糖感受器的敏感度），但增益范围（0.1–1.6）与能量 / 水分的消耗速率全部手选。"
                "「MN9 超过多少算开吃」在生活模式里统一为 10 Hz（手选）：原来的 30 Hz 水永远过不了，水感受器开到 320 Hz，MN9 也只有 22 Hz",
         script="dodge/life_test.js", result_file="results/dodge/life_test.json", log="§47.5–47.6",
         verify=[("H3.passed", True, 0), ("H3.starved", 1, 0.001), ("H3.sated", 0.315, 0.001)]),
    dict(id="touch_cannot_avoid_walls", what="只靠触感（加不加围栏视觉），这颗脑子避得开墙吗",
         status="negative",
         result="**避不开**。3 分钟（走满是 3,240 mm）：矩形场地 + 触感只走了 270 mm、97% 的时间贴墙（卡死在墙角：两根触角同时压墙，转向差为 0）；"
                "圆形场地 410 mm、贴墙 93%；打开围栏视觉不贴墙了，但没有任何来球也起飞 21 次",
         caveat="脑子里没有腹神经索的腿部反射。**没有用「卡住就掉头」的规则去掩盖**：生活模式改成没有墙的开放世界（同样 3 分钟走 3093 mm）。§38 里「触感让它沿墙走」的结论不变，这里量的是它走不走得开",
         script="dodge/wall_limits.js", result_file="results/dodge/wall_limits.json", log="§47.6",
         verify=[("arenas.rect_touch.mean.path_mm", 270, 0.5), ("arenas.round_touch.mean.wall_frac", 0.932, 0.001), ("arenas.open.mean.path_mm", 3092.667, 0.5)]),
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
         script="language/fly_words.py", result_file="results/language/first_sentence.json", log="§13"),
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
