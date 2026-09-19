# Eon Systems “赛博果蝇”复现报告

> 核实与实验日期：2026-09-13；机器：MacBook Pro M1 Pro（8 核 CPU，16 GB 内存，无 NVIDIA GPU），macOS 26.6.2
> 标注约定：**【官方】** Eon 公开的内容；**【社区】** 第三方项目；**【实测】** 本机真实运行得到；**【推测】** 我的判断，未验证

## 目录

> 报告按时间顺序累积，越往后越新。**第 0 节是全篇摘要**；第 1–8 节是最初的复现与可行性核实，第 9–13 节是游戏与各条外围管线，第 14–26 节是虚拟敲除筛选、把结果搬回游戏、以及视觉前端的验证。第 23 节有**错误账本**，记录所有自查出来的错。

- [0. 结论摘要](#0-结论摘要)
- [1. 信息核实](#1-信息核实)
  - [1.1 你给的线索，逐条核对](#11-你给的线索逐条核对)
  - [1.2 开源范围](#12-开源范围)
- [2. 环境配置](#2-环境配置)
  - [2.1 本机实际使用（CPU / macOS arm64）【实测】](#21-本机实际使用cpu--macos-arm64实测)
  - [2.2 Linux + NVIDIA GPU（官方路线）【未实测，按官方 README 整理】](#22-linux--nvidia-gpu官方路线未实测按官方-readme-整理)
  - [2.3 遇到的报错与解决【实测，日志在 `logs/`】](#23-遇到的报错与解决实测日志在-logs)
- [3. 运行结果【全部实测】](#3-运行结果全部实测)
  - [3.1 官方 `main.py`（0.1 s，1 个 trial，sugar 实验）](#31-官方-mainpy01-s1-个-trialsugar-实验)
  - [3.2 自写最小实验 `run_experiment.py`（默认 Brian2 standalone，1 s 模拟）](#32-自写最小实验-run_experimentpy默认-brian2-standalone1-s-模拟)
  - [3.3 核对时发现的问题](#33-核对时发现的问题)
- [4. 具身化可行性](#4-具身化可行性)
  - [4.1 社区的大脑↔身体项目（2026-09-13 在 GitHub 和网页上补查；Eon 官方闭环代码仍然没有公开）](#41-社区的大脑身体项目2026-09-13-在-github-和网页上补查eon-官方闭环代码仍然没有公开)
- [5. 许可证与使用限制](#5-许可证与使用限制)
- [6. 风险与待确认问题](#6-风险与待确认问题)
- [7. 最短使用路径](#7-最短使用路径)
- [8. 交付物清单](#8-交付物清单)
- [参考来源](#参考来源)
- [9. 果蝇闪避游戏：视觉编码、真视觉与飞行（2026-09-14 追加）](#9-果蝇闪避游戏视觉编码真视觉与飞行2026-09-14-追加)
  - [9.1 第 1 步：LC4/LPLC2 编码拆分 + 起飞离开（`dodge/step1_encoding.js` → `results/dodge/step1_encoding.json`）](#91-第-1-步lc4lplc2-编码拆分--起飞离开dodgestep1_encodingjs--resultsdodgestep1_encodingjson)
  - [9.2 第 2 步：复眼 → flyvis → FlyWire 全脑（`vision/*.py` → `results/vision/`）](#92-第-2-步复眼--flyvis--flywire-全脑visionpy--resultsvision)
  - [9.3 第 3 步：flybody 起飞动画（`flight/export_flight.py`、`dodge/step3_flight.js`）](#93-第-3-步flybody-起飞动画flightexport_flightpydodgestep3_flightjs)
- [10. 补齐五项能力（2026-09-14 追加）](#10-补齐五项能力2026-09-14-追加)
  - [10.0 先用全脑确认每条通路存在【实测】（`results/v2_ref/`，0.5 s × 4 次**独立**试次；表中数字已按第 17 节的重跑更新，旧版“× 4 次”实为同一次模拟的 4 份拷贝，见 14.0 节）](#100-先用全脑确认每条通路存在实测resultsv2_ref05-s--4-次独立试次表中数字已按第-17-节的重跑更新旧版-4-次实为同一次模拟的-4-份拷贝见-140-节)
  - [10.1 子回路 v2（`dodge/subcircuit_v2.py`）](#101-子回路-v2dodgesubcircuit_v2py)
  - [10.2 第 1 项：进食 + 苦味【实测】（`dodge/step_v3.js`，3 局 × 120 s，每种颗粒接触 30 次）](#102-第-1-项进食--苦味实测dodgestep_v3js3-局--120-s每种颗粒接触-30-次)
  - [10.3 第 2 项：梳理【实测】](#103-第-2-项梳理实测)
  - [10.4 第 3 项：正面威胁时后退【实测 + 探索性】](#104-第-3-项正面威胁时后退实测--探索性)
  - [10.5 第 4 项：嗅觉导航【实测，阴性】](#105-第-4-项嗅觉导航实测阴性)
  - [10.6 第 5 项：接腹神经索、让运动神经元驱动腿【实测，阴性】（`vnc/`）](#106-第-5-项接腹神经索让运动神经元驱动腿实测阴性vnc)
  - [10.7 汇总](#107-汇总)
- [11. 第 4 轮：多巴胺、后退重做、嗅觉诊断、腹神经索换模型（2026-09-14 追加）](#11-第-4-轮多巴胺后退重做嗅觉诊断腹神经索换模型2026-09-14-追加)
  - [11.1 吃到糖，会分泌多巴胺吗？【实测，阴性】](#111-吃到糖会分泌多巴胺吗实测阴性)
  - [11.2 LC16 剂量 → MDN【实测】](#112-lc16-剂量--mdn实测)
  - [11.3 后退实验重做【实测，设计事先写定】（`dodge/backward_v4.js` → `results/dodge/backward_v4.json`）](#113-后退实验重做实测设计事先写定dodgebackward_v4js--resultsdodgebackward_v4json)
  - [11.4 嗅觉：降低强度、换读出窗口、找失控源头【实测 + 探索性，阴性】](#114-嗅觉降低强度换读出窗口找失控源头实测--探索性阴性)
  - [11.5 腹神经索：换成 Pugliese 2025 发放率模型【社区代码 · 实测】（`vnc/run_pugliese.py`、`vnc/analyze_pugliese.py`、`vnc/drive_legs_pugliese.py`）](#115-腹神经索换成-pugliese-2025-发放率模型社区代码--实测vncrun_pugliesepyvncanalyze_pugliesepyvncdrive_legs_pugliesepy)
  - [11.6 游戏里的“闻着找”（手写，非连接组）【实测】（`dodge/odor_v4.js` → `results/dodge/odor_v4.json`）](#116-游戏里的闻着找手写非连接组实测dodgeodor_v4js--resultsdodgeodor_v4json)
  - [11.7 加上强化训练会怎样？这台电脑能不能跑？【文献 + 实测速度 + 推测】](#117-加上强化训练会怎样这台电脑能不能跑文献--实测速度--推测)
  - [11.8 汇总](#118-汇总)
- [12. 腹神经索三项：全腹神经索 6 条腿、巨纤维电突触、本体感觉闭环（2026-09-14 追加）](#12-腹神经索三项全腹神经索-6-条腿巨纤维电突触本体感觉闭环2026-09-14-追加)
  - [12.0 更正](#120-更正)
  - [12.1 全腹神经索（MANC，23,532 个神经元）【社区模型 · 实测】（`vnc/manc_full.py`、`vnc/analyze_manc_full.py`）](#121-全腹神经索manc23532-个神经元社区模型--实测vncmanc_fullpyvncanalyze_manc_fullpy)
  - [12.2 驱动 NeuroMechFly 的 6 条腿【实测】（`vnc/drive_legs_manc.py`）](#122-驱动-neuromechfly-的-6-条腿实测vncdrive_legs_mancpy)
  - [12.3 巨纤维 → TTMn 电突触【实测 + 手写耦合】（`vnc/manc_full.py gap` → `results/vnc/manc_full/gap_summary.json`）](#123-巨纤维--ttmn-电突触实测--手写耦合vncmanc_fullpy-gap--resultsvncmanc_fullgap_summaryjson)
  - [12.4 本体感觉闭环【实测 · 探索性，感受器编码为手写】（`vnc/export_manc_params.py`、`vnc/proprio_loop.py`）](#124-本体感觉闭环实测--探索性感受器编码为手写vncexport_manc_paramspyvncproprio_looppy)
  - [12.4b 本体感觉闭环第二版：相位性编码【实测 · 探索性】（`vnc/proprio_loop.py run_phasic` → `results/vnc/manc_full/proprio_phasic_summary.json`）](#124b-本体感觉闭环第二版相位性编码实测--探索性vncproprio_looppy-run_phasic--resultsvncmanc_fullproprio_phasic_summaryjson)
  - [12.5 汇总](#125-汇总)
  - [12.6 用作者的全突触数据重跑【实测】（`MANC_DATASET=all`，`scratch/queue_manc_all.sh` → `results/vnc/manc_all/`）](#126-用作者的全突触数据重跑实测manc_datasetallscratchqueue_manc_allsh--resultsvncmanc_all)
- [13. 让果蝇“说中文”，发给 Claude Opus 5（2026-09-14 追加）【实测】（`language/fly_words.py`、`language/ask_claude.py` → `results/language/`）](#13-让果蝇说中文发给-claude-opus-52026-09-14-追加实测languagefly_wordspylanguageask_claudepy--resultslanguage)
- [14. 虚拟敲除筛选：糖 → MN9，哪些神经元不可缺？（2026-09-14 追加）【实测】（`screen/sugar_mn9_screen.py` → `results/screen/`）](#14-虚拟敲除筛选糖--mn9哪些神经元不可缺2026-09-14-追加实测screensugar_mn9_screenpy--resultsscreen)
  - [14.0 更正：以前写的“× 4 次试验”其实是同一次模拟的 4 份拷贝](#140-更正以前写的-4-次试验其实是同一次模拟的-4-份拷贝)
  - [14.1 做法（运行前写定）](#141-做法运行前写定)
  - [14.2 验证（`results/screen/validation.json`）](#142-验证resultsscreenvalidationjson)
  - [14.3 复现论文自己的筛选（183 个神经元）](#143-复现论文自己的筛选183-个神经元)
  - [14.4 我们方法自带的一个偏差：网络混沌 + 单条基线轨迹【探索性，事后发现】](#144-我们方法自带的一个偏差网络混沌--单条基线轨迹探索性事后发现)
  - [14.5 和真实实验比：10 个做过光遗传沉默的类型](#145-和真实实验比10-个做过光遗传沉默的类型)
  - [14.6 穷举 50 Hz 下全部 313 个活跃神经元：论文漏掉了什么吗？](#146-穷举-50-hz-下全部-313-个活跃神经元论文漏掉了什么吗)
  - [14.7 不跑模拟，光看连线能不能预测？（事先写定的对照）](#147-不跑模拟光看连线能不能预测事先写定的对照)
  - [14.8 这件事有什么用、以及别当真的部分](#148-这件事有什么用以及别当真的部分)
- [15. 解码器压力测试：像脑机接口那样只看到一部分神经元，还读得出吗？（2026-09-14 追加）【实测 · 离线分析】（`language/decoder_stress.py` → `results/language/stress.json`）](#15-解码器压力测试像脑机接口那样只看到一部分神经元还读得出吗2026-09-14-追加实测--离线分析languagedecoder_stresspy--resultslanguagestressjson)
- [16. 双敲除：有没有“单独敲都没事、一起敲就断”的备份通路（2026-09-14 追加）【实测 · 探索性】（`screen/double_knockout.py` → `results/screen/double_summary.json`）](#16-双敲除有没有单独敲都没事一起敲就断的备份通路2026-09-14-追加实测--探索性screendouble_knockoutpy--resultsscreendouble_summaryjson)
  - [16.1 还有没有别的 CB0883？（`screen/double_hub.py` → `results/screen/double_hub_summary.json`）](#161-还有没有别的-cb0883screendouble_hubpy--resultsscreendouble_hub_summaryjson)
  - [16.2 CB0883 全扫描：把 312 个活跃神经元都和它一起敲一遍（`screen/hub_scan.py` → `results/screen/hub_scan_summary.json`）](#162-cb0883-全扫描把-312-个活跃神经元都和它一起敲一遍screenhub_scanpy--resultsscreenhub_scan_summaryjson)
- [17. 把受种子 bug 影响的参考实验重跑一遍（2026-09-14 追加）【实测】（`scratch/rerun_refs.py` → `results/v2_ref/rerun_diff.csv`）](#17-把受种子-bug-影响的参考实验重跑一遍2026-09-14-追加实测scratchrerun_refspy--resultsv2_refrerun_diffcsv)
- [18. 视觉管线：补上“每个条件只跑一次”的重复（2026-09-14 追加）【实测】（`vision/connectome_from_flyvis.py --repeats 3`、`vision/repeat_check.py` → `results/vision/repeat_check.json`）](#18-视觉管线补上每个条件只跑一次的重复2026-09-14-追加实测visionconnectome_from_flyvispy---repeats-3visionrepeat_checkpy--resultsvisionrepeat_checkjson)
- [19. 同一套方法换一条通路：水味觉（2026-09-15 追加）【实测】（`screen/water_screen.py` → `results/screen/water/`）](#19-同一套方法换一条通路水味觉2026-09-15-追加实测screenwater_screenpy--resultsscreenwater)
- [20. 一次数据体检，以及把“静默降级”改掉（2026-09-15 追加）【工程】（`screen/segments.py`、`screen/audit.py` → `results/screen/audit.json`）](#20-一次数据体检以及把静默降级改掉2026-09-15-追加工程screensegmentspyscreenauditpy--resultsscreenauditjson)
- [21. 糖和水用的是同一批神经元吗？（2026-09-15 追加）【实测 · 只做分析，不跑新仿真】（`screen/pathway_compare.py` → `results/screen/pathway_compare.json`）](#21-糖和水用的是同一批神经元吗2026-09-15-追加实测--只做分析不跑新仿真screenpathway_comparepy--resultsscreenpathway_comparejson)
  - [21.1 水通路也做一次全扫描：CB0051 × 全部活跃神经元（`screen/water_hub_scan.py` → `results/screen/water/hub_scan_summary.json`）](#211-水通路也做一次全扫描cb0051--全部活跃神经元screenwater_hub_scanpy--resultsscreenwaterhub_scan_summaryjson)
- [22. 什么时候可以不跑模拟？（2026-09-15 追加）【实测 · 只做分析】（`screen/structure_vs_function.py` → `results/screen/structure_vs_function.json`）](#22-什么时候可以不跑模拟2026-09-15-追加实测--只做分析screenstructure_vs_functionpy--resultsscreenstructure_vs_functionjson)
  - [22.1 换成“动力学指纹”：弱但方向对（`screen/dynamic_fingerprint.py` → `results/screen/dynamic_fingerprint.json`）](#221-换成动力学指纹弱但方向对screendynamic_fingerprintpy--resultsscreendynamic_fingerprintjson)
  - [22.2 把“通路集中度”算出来（`screen/concentration.py` → `results/screen/concentration.json`）](#222-把通路集中度算出来screenconcentrationpy--resultsscreenconcentrationjson)
- [23. 这一轮的方法学账本（2026-09-15 追加）](#23-这一轮的方法学账本2026-09-15-追加)
- [24. 第三条通路：触角机械感觉 → 梳理指令 aDN1（2026-09-15 追加）【实测】（`screen/jon_screen.py` → `results/screen/jon/`）](#24-第三条通路触角机械感觉--梳理指令-adn12026-09-15-追加实测screenjon_screenpy--resultsscreenjon)
  - [24.1 验证“差异来自刺激强度”：把刺激调弱再跑一遍（`screen/jon_weak.py` → `results/screen/jon_weak/`）](#241-验证差异来自刺激强度把刺激调弱再跑一遍screenjon_weakpy--resultsscreenjon_weak)
  - [24.2 把论文的刺激名单反推出来，差异基本闭合（`screen/jon_paper.py` → `results/screen/jon_paper/`）](#242-把论文的刺激名单反推出来差异基本闭合screenjon_paperpy--resultsscreenjon_paper)
  - [24.3 用论文名单把整条通路重做一遍，取代 24 节的数字（`screen/jon_paper.py full` / `full_analyze` → `results/screen/jon_paper/full_summary.json`）](#243-用论文名单把整条通路重做一遍取代-24-节的数字screenjon_paperpy-full--full_analyze--resultsscreenjon_paperfull_summaryjson)
- [25. 把研究结果搬回游戏里：真实神经元开关、物理世界、水与口渴（2026-09-16 追加）【实测 + 工程】（`dodge/game_core.js`、`dodge/brain.js`、`dodge/fly_dodge.template.html`）](#25-把研究结果搬回游戏里真实神经元开关物理世界水与口渴2026-09-16-追加实测--工程dodgegame_corejsdodgebrainjsdodgefly_dodgetemplatehtml)
  - [25.1 落地姿态修好了（用户报的 bug）](#251-落地姿态修好了用户报的-bug)
  - [25.2 敲真实神经元的开关：搬进去才发现模型对不上](#252-敲真实神经元的开关搬进去才发现模型对不上)
  - [25.3 物理世界：阳光、风、重力](#253-物理世界阳光风重力)
  - [25.4 水滴与口渴：同一个动作，背后两套线路](#254-水滴与口渴同一个动作背后两套线路)
  - [25.5 “果蝇在想什么”气泡](#255-果蝇在想什么气泡)
  - [25.6 还有哪些研究结果没进游戏](#256-还有哪些研究结果没进游戏)
- [26. 补上一个长期空白：视觉前端修复的验证（2026-09-16）【实测 · 事先写定判据】（`connectome_vision_loop.py --frontend-only`）](#26-补上一个长期空白视觉前端修复的验证2026-09-16实测--事先写定判据connectome_vision_looppy---frontend-only)

---

## 0. 结论摘要

1. 官方仓库是 **`github.com/eonsystemspbc/fly-brain`**（不是 `eonsystems/fly-brain`），许可证 **GPL-2.0-or-later**。开源的只有“数字大脑”：FlyWire v783 LIF 模型 + 6 个后端的基准代码。**“大脑→MuJoCo 身体”的闭环代码没有公开**。
2. **【实测】** 大脑在 16 GB Mac 上用纯 CPU 就能跑：1 s 大脑时间约 2.5 s 算完，峰值内存 3–4 GB。激活糖味神经元 → MN9（进食）98/69 Hz；沉默 6 个中间神经元 → MN9 降到 1 Hz；激活 LC4 → 巨纤维（逃逸）85/40 Hz。
3. **【实测】** 身体方面，FlyGym 2.1（EPFL NeuroMechFly v2，Apache-2.0）的复眼视觉和行走在本机可用；“视觉→控制→行走”的玩具闭环能区分趋向、回避、盲走三种行为。
4. **【实测】** 把复眼信号直接灌进光感受器（R1-6/R7/R8）**到不了任何下行神经元**；要从 LC4 这类视觉投射神经元注入才有效。真·连接组闭环原型只通过了 0.15 s 冒烟测试；其视觉前端的修复已于 2026-09-16 验证（第 26 节：假阳性消除），**增益也已于 2026-09-16 标定**（第 27 节：`lc4_gain` 从手选的 4000 改为标定出的 **19.8**——原值是标定值的 202 倍；LC4 从只有 0/200 两个取值变成 15 个分级取值，饱和率 23%→2%）。**加载大脑之后的行为仍未验证。**
5. 风险：GPL-2.0 与 Apache-2.0 的组合问题；FlyWire 数据可能仅限非商用；脑→腿的映射本质上是手工设计（Eon 自己也承认）。

**后续工作摘要**（第 9–25 节，2026-09-14 起追加；数字均已于 2026-09-16 对照结果文件核对）：

6. **【实测】虚拟敲除筛选**（14、19、24.3 节，合计 **18,799 段**全脑仿真、**10.56 h** 机时）：在三条通路上复现 Shiu et al. 2024 的沉默筛选。
   与论文的判定一致性（Cohen κ，三条都用零参照归一化口径）：**糖 0.59、水 0.87、触角机械感觉 0.91**。
   对论文自己做的光遗传实验：糖 6/10、水 9/10、JON 1/1 可测。**模型准不准是「按通路而定」的，不是一个总体结论。**
   （**口径提醒**，第 31 节：糖那 6/10 里，*答对的是哪 6 个*随口径变化——Roundup 与 Zorro 的比值都紧贴 0.8 判据，未归一化答对 Zorro、零参照归一化答对 Roundup，恰好互换一个；其余 8 个类型在四种口径下判定完全一致。总分不变，但引用这两个时必须说明口径。）
7. **【实测】冗余结构只能靠模拟**（22 节，事先声明的假设）：两个神经元「到读出的图上路径重不重叠」与「一起敲会不会塌」**毫无关系**
   （Spearman −0.008 / 0.013，且已排除指标退化）。换成动力学指纹方向对但很弱。**配对效应必须真跑，看连线看不出来。**
8. **【实测】同一个动作，两套线路**（21 节）：糖和水都读出 MN9、都引发伸喙，但活跃神经元只重叠约三分之一，
   枢纽各自私有（CB0883 在水通路里根本不放电；CB0051 在糖通路里敲了没影响）。
9. **【实测】能做成能玩的东西**：4,599 个神经元的子回路在浏览器里实时决定躲球、起飞、进食、梳理、后退、喝水
   （游戏页 `results/dodge/fly_dodge.html`）。子回路整体重现了全脑的敲除模式（糖 Pearson +0.75、水 +0.89），
   但单个神经元会失真——最典型的是 CB0883 的枢纽效应在裁剪后**完全消失**。
10. **方法学教训**（23 节错误账本，全部自查并如实登记）：Brian2 standalone 把随机种子编译进程序，导致早期「4 次试次」其实是同一次的 4 份拷贝；
    混沌网络让配对设计产生系统性偏差；**极度不平衡的判定问题上「一致率」是骗人的，必须看 κ，而且 κ 在正例太少时同样不可靠**；
    手写汇总数字是本项目最大的错误来源（一次核对查出 16 处，而约 300 个由脚本产出的数字无误）；
    **同一个量在不同口径下被并排展示而不标注，会让文档自相矛盾**（第 31 节：页面用归一化值、报告用未归一化值，两处都没标，导致 report.md 自己前后打架）——**判据附近的值最容易因口径翻转，那里的标注不能省**。

11. **【实测】整套果蝇视觉系统搬进了浏览器**（28 节）：关键发现是 flyvis 本质上是**六边形卷积网络**——
    45,669 个节点只由 **604 个核、2,355 个抽头**决定，所以整个视觉系统是 **80 KB JSON**、在 JS 里 3.4 ms/步。
    导出脚本会**逐成员验证**这个前提（权重只依赖源型/靶型/位移），不成立就拒绝导出；**50 个集成成员全部通过**。
12. **【实测】把视觉回路真的从像素闭上了，结果是负的而且可以量**（28.19 节）：
    游戏里驱动行为的视觉前端**从来不看像素**（直接读球坐标算 dθ/dt）。换成真链路
    （复眼像素 → Rh1 → flyvis → LPLC2 汇集）之后：**45 mm 外读数恒为 0（完全瞎）**，
    25 mm 以内才把球从噪声里分出来；而**果蝇光是走路，自体运动的全场光流就能给自己造出峰值 126 Hz 的假「逼近」**。
    球半径 2.5 mm、小眼间角 5.7°，**60 mm 外球还不到一个小眼**——败因是分辨率与未补偿的自体运动，不是 LPLC2 模型。
13. **【实测】补上了八个感光细胞里缺的六个**（28.16 节）：此前只建模了 R8（pale 取蓝 / yellow 取绿）与 R7 紫外，
    **R1–R6（Rh1）——运动与亮度主通道、也是 flyvis 的主输入——完全没有建模**。现在每类按 Govardovskii 2000 模板
    积分自己的光谱。
14. **【实测】论文自己的两个对照做成了滑块**（30 节）：**打乱接线**后糖 → MN9 从 82.9 Hz 掉到 **3.5 ± 4.2 Hz**
    （比值 0.043，与论文表 1D 同量级）；按论文自己的判据（"判定是否翻转"，不是发放率变化量），
    突触权重 ±30% 下 10 个神经元的敲除判定 **9/10 与 10/10 不变**，但抑制 ±30% 与谷氨酸改兴奋性只有 **7/10**。
15. **【实测】aDN2——官方论文梳理通路的另一半，零新仿真补上了**（29 节）：段落文件存的是全部活跃神经元的稀疏计数，
    所以直接重读存档即可。与论文表 7E 对照：Pearson **0.946**、κ **0.887**。
    事先声明不预设的那条有了答案：**aBN1 单敲让 aDN2 也归零**，两个梳理指令神经元**共用同一个绝对瓶颈**。

---

## 1. 信息核实

### 1.1 你给的线索，逐条核对

| 线索 | 核实结果 |
|---|---|
| 仓库 `eonsystems/fly-brain` | ❌ 不存在（`gh repo view` 报 “Could not resolve”）。实际是 **`eonsystemspbc/fly-brain`**：2026-03-05 创建，最后推送 2026-08-29，625★ |
| 入口 `main.py` | ✅ 存在，但它是**基准测试 CLI**，不是交互式实验入口。只有 `sugar` 和 `p9` 两个实验，`--t_run` 只接受 0.1/1/10/100/1000 |
| 后端 Brian2 / Brian2CUDA / PyTorch / NEST GPU / GeNN | ✅ 另有 Brian2GeNN，共 6 个 |
| 约 12.5–13.9 万神经元、约 1500 万突触连接 | ✅ **【实测】** 数据文件为 138,639 个神经元、15,091,983 条连接（带权边），权重绝对值之和 54,492,922（≈ 突触数，与官网“约 5000 万突触”一致）。README 写的 “~5M synapses” 与数据对不上 |
| LIF 模型 | ✅ 用的是 Shiu et al. 2024 *Nature* 的参数：v_rest −52 mV，阈值 −45 mV，τ_m 20 ms，τ_syn 5 ms，不应期 2.2 ms，延迟 1.8 ms，每突触 0.275 mV，dt 0.1 ms |
| 具身化使用 MuJoCo | ✅ 官网称身体为 **NeuroMechFly v2（MuJoCo）**，每 15 ms 同步一次脑与身体 |
| 官网两篇说明 | ✅ 均存在（2026-03-07/03-10），另有 `weve-uploaded-a-fruit-fly`（03-08）和 `more-flies-are-getting-uploaded`（09-11）。**都没有代码链接或预印本** |
| 替代项目 NeuroMechFly / flybody | ✅ 见第 4 节。注意 FlyGym 已升到 **2.1.0**，API 与网上大部分 1.x 教程不兼容 |

### 1.2 开源范围

| 内容 | 状态 | 地址 / 许可证 |
|---|---|---|
| 全脑 LIF 模型 + 6 后端基准 | **【官方】开源** | eonsystemspbc/fly-brain，GPL-2.0-or-later（LICENSE 与 README 第 418 行明确写 “or any later version”） |
| Shiu et al. 原始 Brian2 代码（仓库内 `code/paper-phil-drosophila/`） | 开源 | **MIT**（Philip Shiu & Nico Spiller） |
| 连接组数据（仓库自带 v783 parquet/csv） | 随仓库分发 | 来自 FlyWire，许可证见第 5 节 |
| Nature 基准完整 spike 数据（600 个 parquet） | 公开 | Google Drive（README 中给出链接） |
| `eonsystemspbc/flybody` | 公开，但只是 TuragaLab/flybody 的**未修改 fork**（领先 0 个提交、落后 1 个） | Apache-2.0 |
| `eonsystemspbc/drosophila_brain_model_lif` | philshiu/Drosophila_brain_model 的 fork，只多了一个 demo notebook | MIT |
| `eonsystemspbc/pathintegrationBPU` | 连接组初始化的 RNN 训练，**与 MuJoCo 身体无关** | 未声明许可证（默认保留所有权利） |
| **具身化闭环（大脑→NeuroMechFly/MuJoCo）** | **❌ 未公开**。官网只描述了做法，提供联系邮箱 | — |
| 视觉通路（官网说用了 Lappalainen et al. 模型） | 未公开 Eon 的接入代码；flyvis 本身开源 | TuragaLab/flyvis，MIT |
| 论文 / 预印本 | 未找到 Eon 2026 年的论文。README 里的 `nature_2026_07` 只是基准测试的 run-label | — |

**【官方】** 官网描述的具身化做法：
- 下行神经元当作“控制把手”：DNa01/DNa02 管转向，oDN1 管前进，触角 DN 管梳理，MN9 管进食。
- 下层控制器把这些信号转成关节动作；映射系数是 “somewhat arbitrarily chosen by hand”。
- 巨纤维（逃逸）和后退行走 “not shown in our demo”。

**【社区】** 第三方的批评（Carboncopies Foundation，“No, a Fruit Fly has not been uploaded”）：步态是身体模型里预编程的，连接组只起“开关”作用。结合官网描述，**【推测】** 这个批评基本成立。

---

## 2. 环境配置

完整脚本见 [`setup.sh`](setup.sh)。下面是要点。

### 2.1 本机实际使用（CPU / macOS arm64）【实测】

```bash
conda create -y -n brain-fly-cpu -c conda-forge python=3.10 numpy=1.26.4 pandas pyarrow scipy matplotlib joblib tqdm brian2 pip cxx-compiler
conda install -y -n brain-fly-cpu -c conda-forge pytorch      # 不要用 pip 装 torch，见 2.3 报错 1
conda create -y -n flygym python=3.12
conda run -n flygym pip install "flygym==2.1.0" torch pandas pyarrow
```

实测版本：brian2 2.9.0、torch 2.13.0（conda-forge）/ 2.14.0（flygym 环境里用 pip 装）、numpy 1.26.4 / 2.5.3、flygym 2.1.0、mujoco 3.9.0。

### 2.2 Linux + NVIDIA GPU（官方路线）【未实测，按官方 README 整理】

```bash
sudo apt-get install -y pkg-config libffi-dev build-essential
export CUDA_PATH=/usr/local/cuda-12.5 CUDA_HOME=/usr/local/cuda-12.5 PATH=/usr/local/cuda-12.5/bin:$PATH
conda env create -f external/fly-brain/environment.yml && conda activate brain-fly
python main.py --pytorch --genn --t_run 1 --n_run 1 --no_log_file
```

- 官方测试平台：Ubuntu 22.04 / WSL2 + RTX 4070 + CUDA 12.x。
- NEST GPU 需要从源码编译，并拷入 `scripts/nestgpu_source_files` 里的 `user_m1` 模型。
- Brian2GeNN 要单独用 `environment-brian2genn.yml` 建环境（它锁定 Brian2<2.6，与 Brian2CUDA 冲突）。

### 2.3 遇到的报错与解决【实测，日志在 `logs/`】

| # | 报错 | 原因 | 解决 |
|---|---|---|---|
| 1 | `OMP: Error #15: Initializing libomp.dylib, but found libomp.dylib already initialized.`（exit 134） | conda-forge 的 llvm-openmp 与 pip torch 自带的 libomp 冲突 | 卸掉 pip 装的 torch，改用 `conda install -c conda-forge pytorch`（`logs/pip_torch_OMP_conflict.txt`） |
| 2 | `ImportError: Unable to find a usable engine; tried using: 'pyarrow'` | 系统 Python 没装 pyarrow | 在环境里运行 |
| 3 | `NotImplementedError: Could not run 'new_compressed_tensor' from the 'mps:0' device` | MPS 不支持 CSR 稀疏张量 | MPS 上改用 COO + `torch.sparse.mm`，只替换官方 forward 里那一次稀疏乘法 |
| 4 | **系统内存耗尽、死机**（激活 4,423 个 R1-6 时） | 官方 `poi()` 为每个被激活神经元建一个 `PoissonInput`，Brian2 standalone 于是生成了 **8,248 个 C++ 代码对象**，又默认用不限并行的 `make -j` 同时起几千个 clang | 超过 50 个被激活神经元时改用 1 个 `PoissonGroup` + 一对一突触（统计等价）；`extra_make_args_unix=["-j4"]`。修复后同一实验峰值 4.1 GB |
| 5 | `ValueError: The truth value of an array ... is ambiguous`（`neu.rfc[idx] = 0*ms`） | Brian2 standalone 不支持按索引数组赋值 | 改为整体赋值 `neu.rfc = array*ms` |
| 6 | 视觉 demo 里果蝇原地不动 | 默认地面棋盘格（0.3/0.4 灰）经复眼后亮度 <0.2，被当成暗物体，触发了“撞上就停” | 把地面纹理改亮（0.85/0.95） |
| 7 | `flygym.__version__` 报 AttributeError | flygym 2.1 没有这个属性 | 不影响使用，改用 `pip show flygym` 查版本 |

小注意：运行官方 `main.py` 会改写仓库里的 `data/benchmark-results.csv`（git 显示为 modified），可以用 `git checkout data/benchmark-results.csv` 还原。

---

## 3. 运行结果【全部实测】

### 3.1 官方 `main.py`（0.1 s，1 个 trial，sugar 实验）

| 后端 | 命令 | 建模/编译 | 仿真 | 活跃神经元 | spike 数 |
|---|---|---|---|---|---|
| Brian2 C++ standalone（CPU） | `python main.py --brian2-cpu --t_run 0.1 --n_run 1 --no_log_file` | 0.7 s + 编译 9.2 s | **1.41 s** | 324 | 1,566 |
| PyTorch（CPU） | `python main.py --pytorch --t_run 0.1 --n_run 1 --no_log_file` | 7.2 s | 45.6 s | 326 | 1,403 |

- 两个后端的活跃神经元数和 spike 数都很接近（Poisson 输入本身是随机的）。
- 在 CPU 上 **Brian2 standalone 比 PyTorch 快约 30 倍**，所以 CPU 用户首选 Brian2。
- 日志：`logs/official_*.log`。

### 3.2 自写最小实验 `run_experiment.py`（默认 Brian2 standalone，1 s 模拟）

| 实验 | 命令 | 结果 |
|---|---|---|
| 激活 21 个糖味 GRN @ 200 Hz | `python run_experiment.py --preset sugar --t_run 1` | 398 个活跃神经元、17,080 个 spike。18 个读出神经元中**只有 MN9 放电：左 98 Hz、右 69 Hz**，所有行走/逃逸 DN 都是 0。与 Shiu et al. 的“糖 → 伸喙”定性一致 |
| 糖 + **沉默** 6 个 MN9 上游兴奋性神经元（CB0553×2、CB0493×2、DNge062×2，按到 MN9 的突触数和 sugar 条件下的活跃度挑选） | `python run_experiment.py --preset sugar --t_run 1 --compare --silence 720575940623211725 720575940607272649 720575940632252743 720575940621261296 720575940627099338 720575940615023535` | **MN9：98→1 Hz、69→1 Hz**；活跃神经元 398→347；spike 17,080→13,878 |
| 激活左右 P9 @ 100 Hz | `python run_experiment.py --preset p9 --t_run 1` | P9_oDN1 16/12 Hz，DNa02 7/19 Hz，其余为 0；83 个活跃神经元 |
| 激活左侧 54 个 LC4（looming 检测）@ 100 Hz，0.2 s | `python run_experiment.py --exc_type LC4:left --rate 100 --t_run 0.2` | **巨纤维 85/40 Hz**，DNa01 30 Hz，DNa02 10 Hz |
| 同上，PyTorch on MPS（Apple GPU） | `... --backend torch --device mps` | 巨纤维 85/40 Hz、DNa01 30 Hz 与 Brian2 完全一致；**DNa02 不一致（20 Hz vs Brian2 的 10 Hz）**；活跃 254 vs 258 个、2,237 vs 2,297 个 spike；每 0.1 ms 步约 13 ms。两个后端的 Poisson 输入是各自独立抽的，小读出上的差别在噪声量级（2026-09-16 核对时补记：原文只写「与 Brian2 一致」，漏了 DNa02 这一项差异） |
| 激活左眼 **R7+R8**（1,330 个）@ 100 Hz，0.2 s | `--exc_type R7:left R8:left` | 1,340 个活跃神经元（几乎只有被刺激的那些），**所有 DN/MN 都是 0 Hz** |
| 激活左眼 **R1-6**（4,044 个）@ 100 Hz，0.2 s | `--exc_type R1-6:left` | 5,174 个活跃神经元，**所有 DN/MN 都是 0 Hz** |

每个实验的输出目录（`results/<实验名>/`）包含：
- `figure.png`：raster + 群体活动 + 读出神经元柱状图
- `voltage.png`：膜电位轨迹
- `rates.csv`：带 FlyWire cell_type 注释
- `readout.csv`
- `spikes_*.parquet`
- `summary.json`

**内存【实测】**：单次实验进程树峰值 **2.5–4.1 GB**（`memguard.sh` 记录）。8 GB 内存可以跑，16 GB 比较宽裕。只有 0.2–1 s 的短实验测过峰值；更长的模拟（例如官方的 100 s / 1000 s）会累积更多 spike 记录，内存会更高，未测。

### 3.3 核对时发现的问题
- 官方 notebook 里 P9、DNa01、DNa02、MN9 的 “left/right” 命名，**与 FlyWire 注释表的 `side`（胞体侧）正好相反**。可能是镜像/视角约定不同，未确认。做左右转向映射前必须先统一。我的闭环脚本统一使用注释表的 `side`。
- 官方 `silence()` 只把该神经元的**传出**突触置 0，README 却写 “to and from”。代码与文档不一致，脚本按代码行为实现。
- README 目录结构写的是 `code/paper-brian2/`，实际目录叫 `code/paper-phil-drosophila/`。

---

## 4. 具身化可行性

详细路线见 [`embodiment_plan.md`](embodiment_plan.md)。现状：

| 组件 | 状态 |
|---|---|
| 身体 + 3D 世界 + 复眼：FlyGym 2.1.0 | **【实测】可用**：`fly.add_vision()` → `sim.get_ommatidia_readouts()` 返回 (2 眼, 721 小眼, 2 通道)；第 2 次起每帧渲染约 19 ms；物理约 0.13–0.2× 实时 |
| 玩具视觉闭环 `flygym_vision_demo.py`（手写规则，无连接组） | **【实测】** 2 s 内离黑柱（半径 1.2 mm）的最近距离：趋向 **0.29 mm**、盲走对照 **3.51 mm**、回避 **7.35 mm** |
| 连接组闭环原型 `connectome_vision_loop.py` | **【实测】只通过 0.15 s 冒烟测试**（能跑、峰值 2.5 GB、0.15 s 用时 12 s）。冒烟测试暴露的问题：果蝇自己的腿出现在下半视野，步态抖动导致“暗面积增长率”误报，远处的球还没逼近 LC4 就被打满到 200 Hz。**修复已于 2026-09-16 验证（第 26 节）**：新增 `LoomingFrontEnd`，先把球藏起来校准，只用“天空 + 离地平线 40 px 以上”的小眼，并加低通滤波和死区；新增 `--frontend-only` 选项（不加载大脑，用来低成本检验前端）。按事先写定的 4 条判据跑 1.0 s：**腿造成的假阳性彻底消失**（前 0.3 s LC4 恒为 0 Hz，旧版是 200 Hz），**真 looming 信号保留**；但揪出一个新缺陷——`lc4_gain` 从未标定，LC4 只有 0 或 200 两个值。**该缺陷已于同日修复（第 27 节）**：按事先写定的规则标定出 `gain = 19.8`（手选的 4000 是它的 202 倍），LC4 变成 15 个分级取值、饱和率 23%→2%，四条判据全过。**加载大脑之后的行为仍未验证** |
| 社区现成的桥接 | 见 4.1。**全部【社区，未实测】** |

### 4.1 社区的大脑↔身体项目（2026-09-13 在 GitHub 和网页上补查；Eon 官方闭环代码仍然没有公开）

| 项目 | 大脑 / 身体 | 许可证 | 状态与要点 |
|---|---|---|---|
| [neilt93/Fly-Brain-AI](https://github.com/neilt93/Fly-Brain-AI) | FlyWire 13.9 万神经元 Brian2 LIF → **FlyGym v1.2.1**；另有 MANC/BANC VNC 发放率模型 | **未声明**（默认保留所有权利，只能读不能复用） | README 自报：因果损毁 10/10、气味效价 6/6、looming 逃逸 5/5，且都有 shuffled 连接组对照。最完整的“连接组在环 + 对照实验”实现，**最值得读** |
| [nishkarsh1215/flywire-neuromechfly](https://github.com/nishkarsh1215/flywire-neuromechfly) | FlyWire LIF（GPU）→ 自建身体 / NeuroMechFly 适配器 | **未声明** | 自报 4 个行为中 2 个通过、2 个失败，逐项标注 REAL / ENGINEERED / FAILED。例如：视动转向和糖→伸喙级联是连接组驱动的；气味导航是手写的；连接组导航失败 |
| [erojasoficial-byte/fly-brain](https://github.com/erojasoficial-byte/fly-brain)（53★；另有 fork Ma-Dan/fly-brain） | FlyWire v783 → FlyGym **1.x** | 标注 MIT，但 `run_pytorch.py` 与 Eon 的 GPL 文件高度相似，**许可证存疑** | 多模式状态机（走 / 逃 / 梳 / 吃 / 飞）；装 FlyGym 2.x 会跑不通 |
| [JayceeB1/flybox](https://github.com/JayceeB1/flybox) | MaleCNS（雄性全 CNS）→ **FlyGym 2.x** | Apache-2.0 | 2026-09-12 新建，**只有规范和基础代码**，README 明说 “No behavioral claim has been made yet”。溯源分级（MEASURED / INFERRED / MODELED / ENGINEERED）的做法值得借鉴 |
| [ZeroXClem/closed-loop-fly](https://github.com/ZeroXClem/closed-loop-fly) | MaleCNS LIF（WebGPU）+ NeuroMechFly 身体，浏览器内运行 | MIT | JS 实现，不是 Python/MuJoCo 路线 |
| [abgnydn/webgpu-fly](https://github.com/abgnydn/webgpu-fly) | FlyWire + MANC + flybody，WebGPU/WASM | MIT | 浏览器实时 |
| [mhdsilva/flywire-arduino](https://github.com/mhdsilva/flywire-arduino) | FlyWire 中裁出 583 个神经元的 looming→逃逸子回路，CPU LIF → Arduino 实物 | 未明确（NOASSERTION） | 带损毁 / 零模型对照实验 |
| [seven-monarchs/NeuroFly](https://github.com/seven-monarchs/NeuroFly) | Brian2 + NeuroMechFly | 未声明 | 个人实验，自报每步约 34 s |

**【推测】** 对你最有用的是 Fly-Brain-AI 和 flywire-neuromechfly：它们在接口设计、对照实验和失败记录上都走在前面。但两者都没有许可证，只能参考思路，不能直接拷代码。

---

## 5. 许可证与使用限制

| 对象 | 许可证 | 对你的影响 |
|---|---|---|
| eonsystemspbc/fly-brain | GPL-2.0-or-later | 自己用、研究、修改都不受限。**对外分发**（包括分发修改版或把它链接进的程序）必须以 GPL 开源全部相关源码。 |
| code/paper-phil-drosophila（Shiu 原始模型） | MIT | 最宽松。想做闭源/商用产品，**从这份 MIT 代码重写 LIF**，比基于 Eon 的 GPL 代码安全 |
| FlyGym / flybody | Apache-2.0 | Apache-2.0 与 GPLv2 不兼容，但与 GPLv3 兼容。Eon 代码是 “or later”，所以组合后的程序可以按 **GPLv3** 整体分发。**【推测，非法律意见】** |
| flyvis | MIT | 可自由组合 |
| FlyWire 数据（v783 连接组 / 注释） | FlyWire 服务条款写明用户编辑与注释以 **CC-BY-NC 4.0** 发布；**v783 数据发布包本身的许可证未能确认**（Codex FAQ 未写，Zenodo 超时） | **按“仅限非商用、需署名引用”处理**，商用前请写信给 flywire@princeton.edu 确认 |
| flyconnectome/flywire_annotations | GitHub 上未声明 SPDX 许可证 | 学术使用须引用 Schlegel et al. 2024 |
| Codex（codex.flywire.ai） | 需 Google 登录并同意服务条款 | 我无法替你登录下载，所以改用 GitHub 上的公开注释表 |

---

## 6. 风险与待确认问题

1. **“上传”的科学含义有限**：连接组只决定哪些 DN 被激活，步态、转向、梳理动作都来自身体侧的预编程控制器，映射系数是手调的。
2. **LIF 模型没有学习、没有神经调质、没有分级电位**。光感受器输入无法驱动行为（3.2 已实测），视觉只能从 LC/LPLC 这类投射神经元注入，或像 Eon 那样接 flyvis。
3. **左右侧约定**：notebook 的命名与注释表 `side` 相反，未确认谁对。直接影响转向方向。
4. **算力**：CPU 上 Brian2 standalone 快，但不能逐窗交互推进，所以闭环只能用 PyTorch。MPS 上 1 s 大脑时间约 2 分钟；NVIDIA GPU 上官方基准可达实时量级（见 `data/benchmark-results.csv`，未在本机验证）。
5. **待确认**：
   - FlyWire v783 数据发布包的正式许可证
   - Eon 用的是 FlyGym 1.x 还是 2.x
   - Eon 视觉接入 flyvis 的具体方式
   - GPU 路线（Brian2CUDA/GeNN/NEST GPU）在 Linux 上的实际表现

---

## 7. 最短使用路径

```bash
bash setup.sh cpu                                   # 或按 2.1 节手动装
conda activate brain-fly-cpu

# 激活一个/一组神经元，看效果（约 15 s，峰值约 3 GB）
python run_experiment.py --preset sugar --t_run 1
open results/sugar_brian2/figure.png

# 激活任意一个 FlyWire 神经元（例：右侧 P9 = 720575940635872101），记录巨纤维膜电位
python run_experiment.py --exc 720575940635872101 --rate 150 --record 720575940622838154

# 按细胞类型激活（查询自 external/flywire_annotations 注释表）
python run_experiment.py --exc_type LC4:left --rate 100 --t_run 0.2

# 沉默并对比
python run_experiment.py --preset sugar --compare --silence 720575940623211725 720575940607272649

# 3D 世界 + 复眼 + 行走
conda activate flygym
python flygym_vision_demo.py --duration 2 --behavior attract
```

在 [FlyWire Codex](https://codex.flywire.ai/?dataset=fafb) 里查到任意神经元的 root ID（v783）后，直接填进 `--exc` 或 `--silence` 即可。

## 8. 交付物清单

| 文件 | 说明 |
|---|---|
| `report.md` | 本报告 |
| `embodiment_plan.md` | 具身化路线与推荐 |
| `setup.sh` | 环境配置（cpu / gpu / flygym） |
| `run_experiment.py` | 最小实验：激活/沉默/记录/作图，支持 Brian2 与 PyTorch（CPU/CUDA/MPS） |
| `flygym_vision_demo.py` | FlyGym 复眼 + 玩具视觉闭环 |
| `connectome_vision_loop.py` | 连接组在环原型（**未验证**，见第 4 节已知问题） |
| `scratch/memguard.sh` | 带内存上限的运行包装（超限自动杀进程） |
| `logs/` | 所有实际运行日志与报错 |
| `results/` | 所有实验输出 |
| `external/fly-brain` | 官方仓库 @ a3db62f |
| `external/flywire_annotations` | 公开注释表 |
## 参考来源
- 官方仓库 https://github.com/eonsystemspbc/fly-brain
- Eon 官网更新：https://eon.systems/updates/embodied-brain-emulation 、https://eon.systems/updates/first-multi-behavior-brain-upload 、https://eon.systems/updates/weve-uploaded-a-fruit-fly
- 批评文章 https://carboncopies.org/Blog/Posts/FruitFlyNotUploaded/Post/
- Shiu et al. 2024 *Nature* https://www.nature.com/articles/s41586-024-07763-9
- FlyGym https://github.com/NeLy-EPFL/flygym （PyPI flygym 2.1.0）；flygym-gymnasium https://github.com/NeLy-EPFL/flygym-gymnasium
- flybody https://github.com/TuragaLab/flybody ；flyvis https://github.com/TuragaLab/flyvis
- 社区桥接 https://github.com/erojasoficial-byte/fly-brain ；清单 https://github.com/cobanov/awesome-fly
- FlyWire 注释 https://github.com/flyconnectome/flywire_annotations ；服务条款 https://flywire.ai/tos ；Codex https://codex.flywire.ai
- 腹神经索发放率模型（Pugliese et al. 2025）代码与数据 https://github.com/smpuglie/Pugliese_cpg_2025 （无许可证）
- flybody 论文 Vaxenburg et al. 2025 *Nature* https://www.nature.com/articles/s41586-025-09029-4 ；全文 https://pmc.ncbi.nlm.nih.gov/articles/PMC12310536/ ；数据与训练好的控制网络 https://doi.org/10.25378/janelia.25309105

---

## 9. 果蝇闪避游戏：视觉编码、真视觉与飞行（2026-09-14 追加）

在线页面：[果蝇闪避](https://claude.ai/code/artifact/31fb7608-dd2f-4c63-8cf1-8fc2a955e6c2)（Version 2）。所有数值均为【实测】，来自下列脚本的输出文件。

### 9.1 第 1 步：LC4/LPLC2 编码拆分 + 起飞离开（`dodge/step1_encoding.js` → `results/dodge/step1_encoding.json`）
- **依据**：
  - Ache et al. 2019 Curr Biol（PubMed 摘要）：巨纤维反应 = LC4 角速度线性项 + LPLC2 角尺寸高斯项。
  - Card & Dickinson 2008 Curr Biol：起飞前约 200 ms 调整姿态，**直接背离逼近的威胁**起跳。
  - 函数形式来自文献；**参数为手选**：LC4 0.5 Hz·(°/s)⁻¹，LPLC2 高斯中心 μ、宽 15°、峰值 200 Hz。原文全文未获取，所以对 μ 做了扫描。
- **结果**（完整大脑，5 局 × 120 s，球速 60 mm/s）：

| 编码 | 起跳方式 | 躲开率 | 起跳距撞击中位 |
|---|---|---|---|
| 第一版（dθ/dt） | 原地 | 64.4% | 0.53 s |
| 新编码 μ30° | 原地 | 75.5% | 0.74 s |
| 新编码 μ45°（事先声明的主设定） | 原地 | 60.7% | 0.32 s |
| 新编码 μ60° | 原地 | 93.9% | 0.14 s |
| 第一版 / 新编码 μ45° | 直线背离飞离 | 99.4% / 99.0% | — |

- **解读**：
  - 飞离类的高躲开率主要来自起飞规则本身。
  - 编码影响的是**起跳时机**（μ 越大越接近碰撞），只有“原地起跳”这种时机敏感的规则能体现出来。
  - μ 是手选参数，所有取值都已列出，不能据此宣称某个 μ 是“真实”的。
- **损毁（新编码 μ45° + 飞离）**：

| 条件 | 躲开率 | 说明 |
|---|---|---|
| 切除巨纤维 | 0% | |
| LPLC2 断突触 | 90.2% | 起跳推迟到距撞击 0.11 s |
| LC4 断突触 | 98.3% | |
| 巨纤维 + DNa 都切除 | 0% | |

### 9.2 第 2 步：复眼 → flyvis → FlyWire 全脑（`vision/*.py` → `results/vision/`）
- **管线**：
  1. 固定的 NeuroMechFly 看半径 2.5 mm 的黑球，FlyGym 1.2.1 复眼 200 Hz 渲染。
  2. flyvis 1.2.0 预训练模型 flow/0000/000 逐帧计算。
  3. 30 种柱状细胞的活动按 Codex `column_assignment`（Matsliah et al. 2024，无需登录的公开下载地址）映射到 FlyWire v783 的 44,252 个神经元，再注入 Brian2 全脑模型。
- **检查**：flyvis 层左右侧化正确（左侧逼近时左眼 T4a 明显高于右眼）。**更正（2026-09-16）**：原文写的「10.9 / 1.8」和「约 2 倍」两组数字在任何结果文件或日志里都查不到；按管线自身的换算从 `flyvis_loom_L.npz` 复算，后段左/右是 **5.3 / 0.9 Hz**、平移/逼近能量比是 **1.69–1.75 倍**。方向性结论成立，但原来那两组具体数值无出处，已删。
- **格子朝向未知**：8 种朝向全部运行。
- **事先声明的指标**（刺激后 0.5–0.95 s，左侧神经元平均发放率，8 个朝向中位数）：

| 刺激 | LPLC2 左 | LC4 左 |
|---|---|---|
| 逼近 | 0.6 Hz | 5.5 Hz |
| 近距平移 | **1.2 Hz** | **9.4 Hz** |
| 远距平移 | 0.3 Hz | 2.7 Hz |
| 远离 | 0.0 Hz | 1.1 Hz |

  LPLC2 逐朝向比较：逼近强于远离 8/8、强于远距平移 7/8，**但弱于近距平移 0/8**；侧化 8/8。（第 18 节重复 3 次后：8/8、7–8/8、0–1/8，结论不变。）
- **结论**：按事先声明的指标，“LPLC2 对逼近的反应强于平移”**只部分成立**：能区分逼近与远离、远距平移，但不能区分逼近与近距平移。
  > **后续修订（2026-09-19，见 28.20 / 28.20.1）**：这个“只部分成立”是在**8 种都已经把点阵角度拉变形的映射**上得到的。
  > `normalize()` 的 PCA + 各轴除以标准差把 Codex 六边形基矢夹角从 60.0° 变成 122.6°（左右眼都是），
  > 映射到的已经不是同一种点阵。换成用解剖锚定的、保持点阵几何的映射重跑全脑之后，
  > **“逼近 > 近距平移”成立了**（解剖锚定 ×0.6，三次重复全过，是十种映射里唯一的）。
  > 这是**有条件的修正**而非推翻：只有一种映射给出该结果、n=3、比值标准差 0.24、输入强度也更高，
  > 机制属事后归因。两种说法都保留，详见 28.20.1。
- **探索性（看过曲线后才加）**：碰撞前最后 150 ms 的峰值。LC4 逼近 27.8 Hz、近距平移 12.5 Hz（8/8）；LPLC2 逼近 2.5、近距平移 1.9 Hz（7/8）。这个窗口是事后选的，不能替代上面的结论。
- **不可解读项**：巨纤维在刺激前基线期已有约 30 Hz，来自 4.4 万个注入输入的整流噪声汇聚。
- **未验证 / 局限**：
  - flyvis 与 FlyWire 两套格子的真实朝向对应；
  - 活动值到发放率的换算（手选）；
  - TmY3 等没有柱坐标的类型未注入（TmY3 占 LC4 输入的 15%）；
  - 只有 1 个 flyvis 模型；每个条件原来只跑 1 次（第 18 节补了 3 次重复）。
- **性能踩坑**：
  - flygym 自带的 `RealisticVisionFly` 每帧重建 `LayerActivity`，经 datamate 反复读 h5 并 `sleep(0.1)` 重试，占约 60% 耗时。替换后单个刺激约 90 s，数值经过核对完全一致。
  - 作为后台任务运行时，OpenGL 渲染被 macOS 节流到约 10% CPU，必须在前台运行。

### 9.3 第 3 步：flybody 起飞动画（`flight/export_flight.py`、`dodge/step3_flight.js`）
- **数据**：flybody figshare `datasets_flight-imitation`（**GPL-3.0+**）里的 184 条逃逸飞行轨迹（含镜像），来自 Muijres et al. 2014 Science 的真实果蝇躲避逼近目标记录；翅膀用 218 Hz 拍翅模式（实测主频 218–219 Hz、幅度 158°）。
- **轨迹选择规则（事先定好）**：左转、右转两组各取净偏航角最接近该组中位数的一条：#67（+62°，150 mm/s）和 #44（−64°，194 mm/s）。
- **分工**：
  - 游戏里起飞**时机**由连接组决定；
  - **飞行动作**是真实录像数据的运动学回放；
  - 选哪条轨迹、起飞 20 ms 抬升到 5 mm 是手写规则；
  - 飞行本身不是连接组或强化学习控制的。
- **结果**：

| 条件 | 躲开率 |
|---|---|
| 真实逃逸轨迹（新编码 μ45°） | 100% |
| 同上，旧编码 | 100% |
| 切除巨纤维 | 0% |
| LPLC2 断突触 | 94.5% |
| LC4 断突触 | 100% |
| LC4 + LPLC2 都断 | 0% |

  新旧编码在这个模式下逐球结果相同：每个球都触发了起飞，飞离足够快，时机差异不再起作用。

---


**飞行动画的真实性与显示修复（2026-09-14 补充）**【实测核对】：
- **真实的部分**：身体的位置和姿态（含俯仰、滚转）来自 flybody 数据集里 Muijres et al. 2014 的原始逃逸轨迹。数据集同时收了镜像增广的轨迹，这里用的是原始那一半。
  - 导出的速度与原始数据一致：左转 150 mm/s（数据集 151）、右转 **194 mm/s**（数据集 196；原文写 195，与本节前面自己写的 194 矛盾，已按 `logs/flight_export.log` 与轨迹复算更正）。速度在 51–597 mm/s 之间变化，100 Hz 以上的功率占比 ≤ 3%，是平滑的真实机动，不是换算噪声。
  - 机头始终抬起约 45–60°（中位 49–50°）。每条轨迹有一次 32–38 ms 的大角度侧倾（最大 126° / 102°），帧间转角 ≤ 3.5°，是连续动作，不是数值翻转。
  - 右转那条路程约 47 mm、净位移约 11 mm，同样来自原始数据：这只果蝇爬升了约 10 mm 并折返。
- **不真实的部分**：
  - 翅膀：数据集只有身体轨迹，翅膀用 flybody 通用拍翅模式（218 Hz），左右扇动角相关 1.000，没有真实转弯时左右翅的差别。
  - 起飞和降落：被记录的果蝇在机动前就在飞，没有起跳；页面里的 20 ms 抬升 5 mm、50 ms 线性降落都是手写过渡。
  - 起飞瞬间机身朝向与飞行方向相差约 50°：轨迹按“初始水平速度背离威胁”对齐，原始数据开头就有这么大的侧滑。
- **显示 bug（已修）**：游戏每 5 ms 更新一次，飞行数据每 0.4 ms 一帧，一个拍翅周期 4.6 ms。
  - 修复前每步跳 12–13 帧，约 1.09 个周期，看上去只前进 0.09 个周期。按原来 ×0.08 慢放，屏幕上翅膀约 1.4 Hz 慢慢摆；模拟 60 fps 刷新，119 个画面帧里只有 31 帧有变化，身体也一顿一顿的。
  - 修复后，页面在两个游戏步之间按渲染时间逐帧取姿态：`game_core.js` 新增 `clipPose`，游戏步与页面共用。逐步核对 40 s 对局、23 次起飞、1,543 个飞行步，状态与修复前完全相同，游戏结果不变。
  - 慢放改为 ×0.04：屏幕上约 8.7 Hz，每帧前进约 0.17 个周期。不慢放时 60 fps 采不到 218 Hz，改为叠加 3 组半透明翅膀显示扇动残影。

**换成 flybody 训练好的飞行控制器（2026-09-14）**【官方模型与数据 · 本机实测】（`flight/policy_rollout.py`、`flight/tfp_compat.py` → `results/flight/flight_clips_policy.json`，现为 `flight_clips.json`；旧的运动学回放保留为 `flight_clips_kinematic.json`）：

- **来源**：flybody 论文在 figshare（10.25378/janelia.25309105，数据许可 GPL-3.0+）公开的 `trained-fly-policies.zip`（6.5 MB），内含 flight、vision-bumps、vision-trench、walking 四个 TensorFlow SavedModel，这里用 flight。
- **加载**：flybody 的 `[tf]` 依赖钉死 TensorFlow 2.8 和 dm-reverb，没有 macOS arm64 版本。所以复制出 `flybody-tf` 环境，装 TensorFlow 2.16.2 和 TFP 0.24。策略输出是 TFP 分布，新旧 TFP 的 TypeSpec 注册名不同（完整模块路径 → `tfp.distributions.…` 短名），加一条名字映射即可加载。输入 9 项观测与飞行任务完全一致，输出 12 维动作（头 3、翅膀 6、腹部 2、拍翅频率 1）。
- **飞法**：同样两条原始逃逸轨迹（左转 067、右转 044），飞行任务用默认参数，只关掉随机起点，取策略均值；全程物理仿真。
- **翅膀**：控制器设定拍翅频率，模式发生器按该频率给出目标角，控制器再给左右 6 个翅膀关节各加一份力修正，翅膀角度由物理引擎算出。

| 指标 | 左转 067 | 右转 044 |
|---|---|---|
| 完成步数 / 参考步数 | 1,690 / 1,690 | 1,202 / 1,202 |
| 身体位置跟踪误差 中位 / 最大 | 0.26 / 7.4 mm | 0.30 / 2.6 mm |
| 机体姿态误差 中位 / 最大 | 5.5° / 51° | 7.0° / 32° |
| 拍翅频率 | 218.9 Hz | 220.5 Hz |
| 左右翅关节角相关（摆动 / 翻滚 / 俯仰） | 0.98 / **0.52** / 0.99 | 0.97 / **0.59** / 0.99 |
| 翻滚角幅度 左 / 右 | 96° / 80° | 74° / 61° |

- **跟踪过程**：大部分时间与记录相差不到 1 mm、机体朝向差约 4–6°。开头约 40–56 ms 有一次约 27° 的朝向偏差。左转那条在最后约 30 ms（307 ms 之后）逐渐偏离，终点偏离 7.1 mm、50°；右转那条终点偏离 2.4 mm、19°。
- **翅膀变化**：原来通用模式下左右翅相关 1.000，现在翻滚角左右明显不同。注意这里的关节角幅度是模型关节量，没有和真实果蝇的拍翅角度做对比。
- **顺带修掉的旧 bug**：原导出把飞行任务里的 ghost 参考果蝇（81 个网格，腿没收起、与真果蝇最多差 1.2 mm）也放进了飞行模型，页面上会多出一副伸着的腿。新导出只含真正的果蝇模型（85 个网格）。
- **对局重跑**（`node dodge/step3_flight.js 120 5`）：6 种起飞方式与 5 个损毁条件的躲开率与运动学回放版完全相同（真实逃逸轨迹 100%，切除巨纤维 0%），因为两份轨迹几乎重合。
- **起跳没有换成真实数据**：
  - 能找到的高速起跳跟踪只有 Card 实验室 FlyPEZ（6,000 帧/秒，Dombrovski et al. 2023 Nature 等），数据声明写的是“合理请求可向作者索取”，公开的 Mendeley 数据只有共聚焦图像。
  - Fontaine et al. 2009 JEB 做过 10 次起飞的三维身体与翅膀跟踪，没有公开数据。
  - 2026 年的全身三维运动学数据集记录的是奔跑与求偶，不含起跳。
  - 所以起飞 20 ms 抬升 5 mm、落地 50 ms 线性下降仍是手写过渡。

## 10. 补齐五项能力（2026-09-14 追加）

在线页面同一链接：[果蝇闪避](https://claude.ai/code/artifact/31fb7608-dd2f-4c63-8cf1-8fc2a955e6c2)（Version 3）。页面大脑换成**子回路 v2**；第 9 节里的对局数字是用第一版子回路测得的，页面上已注明。

### 10.0 先用全脑确认每条通路存在【实测】（`results/v2_ref/`，0.5 s × 4 次**独立**试次；表中数字已按第 17 节的重跑更新，旧版“× 4 次”实为同一次模拟的 4 份拷贝，见 14.0 节）

> **口径说明（2026-09-16 补）**：本节及 11.1 / 11.4 节表里的「活跃神经元」是 **4 个试次的并集**（如 DM1_L 8,541、SUGAR_L 534）；
> 而第 17 节 `rerun_diff.csv` 与 AGENTS.md 里的「约 8,300」是**逐试次均值**（8,333 / 502）。两种口径并存过去没有声明，判据「< 2,000 算不失控」在两种口径下结论相同。

| 刺激 | 全脑结果 | 结论 |
|---|---|---|
| 糖味 LB3 左 | MN9 72.5/106 Hz | ✅ |
| 糖 + 苦（LB1a–d） | MN9 18.5/16 Hz；单独苦味 → 所有下行神经元 0 Hz | ✅ 苦味压制进食；❌ 没有回避输出 |
| JO 左（JO-C/E 各亚型） | aDN1（右）39 Hz | ✅ |
| **JO 右** | **aDN1 0/0 Hz** | ⚠️ 全脑里就左右不对称 |
| LC16 双侧 | MDN 30.5/31 Hz（同时 DNa02 47/38.5、BDN2 43/39） | ✅ 但信号混杂 |
| 双侧 looming | MDN 4.8/5.8 Hz，巨纤维 154/172 Hz | 正面威胁主要触发逃逸 |
| ORN DM1 / DA2 单侧（150 与 50 Hz） | 下行神经元侧化指数 \|LI\| ≤ 0.05；DM1 引发约 8,500 个神经元活动爆发；DA2 在 50 Hz 时 4 次里 3 次无反应、1 次失控 | ❌ 无侧化 |

作为侧化指标的对照（读出神经元按（左 − 右）/（左 + 右）算）：JO 左刺激 → aDN1 只有右侧放电，LI = −1.00；糖味左刺激 → MN9 LI = −0.19。嗅觉刺激下行神经元的 |LI| ≤ 0.05，说明指标本身能测出侧化，是嗅觉真的没有。（旧版这里写的 +0.31 / +0.53 是另一种分组下、单次实现的值，已按重跑重算。）

### 10.1 子回路 v2（`dodge/subcircuit_v2.py`）
- 3 组候选对 9 个全脑条件做了验证。**事先定的规则**是：JSON ≤ 6 MB、JS 引擎 ≥ 3 倍实时、平均偏差最小。按此选中 **wmin=3、K=3**：4,599 个神经元、338,837 条连接，平均偏差 6.4 Hz。
- wmin=5、K=4 这组偏差也小（6.8 Hz），但有 15,934 个神经元、JSON 22 MB，超过发布上限，浏览器里只能跑到约 1 倍实时。
- 修复 `brain.js` 的 bug：原来只把 LC4/LPLC2 当作输入组，新输入设置频率后不生效。现在从子回路元数据读取全部输入组；修复后 JS 与 Python 结果一致。

### 10.2 第 1 项：进食 + 苦味【实测】（`dodge/step_v3.js`，3 局 × 120 s，每种颗粒接触 30 次）

| 条件 | 糖粒吃掉 | 苦粒 | 混合粒 |
|---|---|---|---|
| 完整 | 100% | 0% | 0% |
| 糖味断突触 | 0% | 0% | 0% |
| 苦味断突触 | 100% | 0% | **100%** |
| 切除 MN9 输出 | 0% | 0% | 0% |

- **结论**：进食受 MN9 控制；混合粒不被吃，是连接组里苦味对进食的抑制造成的。
- **苦味只表现为“不吃”，不会绕开**：全脑里单独苦味不驱动任何下行神经元。
- 伸喙是喙部网格的**纯视觉手写旋转**：模型里喙部没有关节。

### 10.3 第 2 项：梳理【实测】
- 72 次落灰 → 42 次梳理（58%），从落灰到开始梳理的中位延迟 0.07 s。
- 切断 JO 或切除 aDN1 输出后都是 0%，通路是因果性的。
- 只有六成是因为**右侧 JO 驱动不了 aDN1，全脑里也一样**。更可能是数据（注释/校对）或 LIF 阈值造成的，而不是生物学事实。
- 梳理姿态：在 NeuroMechFly 上用逆运动学让前足尖触到同侧触角（残差 0.001 mm；该值由 `dodge/export_poses.py` 打印，未存进 `poses.json` 也无日志留存），参照 flybody 梳理姿态数据集（figshare，GPL-3.0+）里的前足梳理类型。

### 10.4 第 3 项：正面威胁时后退【实测 + 探索性】
- **事先设定**（LC16 = 0.5 Hz/(°/s) × 角速度，MDN 阈值 20 Hz，原地起跳模式）：
  - 全场只后退约 0.2 s，正前方来球被击中率 **100%**（16 球）；
  - 切断 LC16 或切除 MDN 前后无差别；
  - 真实逃逸飞行模式下，正前方被击中率 0%：正面威胁靠起飞解决。
- **探索性扫描**（事后加；2 局 × 90 s；正前方每格只有 8 球）：
  - LC16 斜率升到 5 后，整体躲开率 53% → 83%（切除巨纤维时 4% → 83%，但**这两个数口径不同**：4% 是 MDN 阈值 20 那一行，83% 只有阈值 10 的行才对得上；同为阈值 20 时斜率 5 是 **80.6%**）；
  - 切断 LC16 就回落到 47% / 0%；
  - 但正前方来球仍被击中 88–100%。
  - 提升可能来自 LC16 同时驱动的 DNa02 转向，或速度变化打乱了球的瞄准，**不能说明是后退救了命**。

### 10.5 第 4 项：嗅觉导航【实测，阴性】
- 全脑（10.0 节）：单侧气味刺激的侧化指数都在 ±0.05 以内。**口径提醒（2026-09-16 核对时补）**：这个 |LI| 是**全部 167–178 个下行神经元发放率求和**后算的；而 10.0 节拿来对照的「aDN1 LI = −1.00、MN9 LI = −0.19」是**单对读出神经元**，两者不是同一个量。用同一个「全下行求和」口径算，SUGAR_L 是 +0.29、JO_L 是 +0.51。结论不变，但那组对照是苹果比橘子。
- **复现 Fly-Brain-AI 的气味实验**（DM1 吸引 / DM5 厌恶，3 seed + 打乱连接组对照；补建了缺失的 `brain-model/flywire_annotations_matched.csv`）：**4/6 通过**，README 宣称 6/6。
  - DM1 吸引性转向对比 +0.0010，失败；
  - DM5 +0.0198；
  - 所有条件的转向都被约 −0.11 的共同偏置主导。
- **结论**：这个 LIF 连接组做不到双侧嗅觉导航，所以**没有**把嗅觉接进游戏。

### 10.6 第 5 项：接腹神经索、让运动神经元驱动腿【实测，阴性】（`vnc/`）
- **数据**：Codex 公开存储上的 BANC v888 `neurons.csv.gz` 与 `connections_princeton.csv.gz`，无需登录。
- **网络**：取腹神经索子网络 16,407 个神经元（内部 12,851、上行 1,849、下行 1,316、腿部运动神经元 391）、654,258 条连接、641 万个突触。
  - 递质符号：BANC 连接表的 nt_type 列为空，所以按突触前神经元的预测递质定符号（GABA/GLUT 为 −1，其余为 +1），抑制性连接占 52%。
- **下行神经元刺激 1 s（150 Hz）**：

| 刺激 | 活跃腿部运动神经元 | 表现 |
|---|---|---|
| BDN2 | 81 | 主要是持续伸肌放电 |
| BDN2 + oDN1 + P9 | 89 | 同上 |
| MDN | 6 | |
| P9 | 3 | |
| 巨纤维 | **0** | TTMn 未被驱动。BANC 里巨纤维到 TTMn 只有少量化学突触（左 8 个、右 5 个；2026-09-14 复查），真实动物里这条通路主要靠连接组里没有的电突触 |

  - **没有节律**：4–20 Hz 功率占比 ≈ 0.2–0.48，随机噪声水平约 0.33；左右腿相关系数 0.05–0.09。
- **驱动腿**：按 BANC 标注的关节功能（屈/伸），把“伸肌 − 屈肌”发放率差转成 NeuroMechFly（FlyGym 1.2.1，果蝇固定）的关节角偏移，增益为手选：

| 驱动方式 | 腿尖摆幅中位 | 4–30 Hz 节律占比 |
|---|---|---|
| CPG 步态对照 | 1.03 mm | **0.98**，12.2 Hz |
| 运动神经元 · 前进组合 | 0.90 mm | 0.53（噪声约 0.52） |
| 运动神经元 · MDN | 0.12 mm | — |

- **结论**：腿由运动神经元带动了，但只是不规则的姿势变化，**没有交替迈步**。这一点来自运动神经元发放本身，与映射增益无关。没有本体感觉反馈、LIF 没有内在节律机制，是可能的原因。

### 10.7 汇总

| 项目 | 状态 |
|---|---|
| 进食 + 苦味 | ✅ 接入游戏，因果性经损毁验证；苦味只抑制进食，不回避 |
| 梳理 | ✅ 接入游戏；只有左侧触角有效（全脑同样如此） |
| 正面威胁后退 | ⚠️ 接入游戏；事先设定下几乎不起作用，加强 LC16 能提升整体躲避但解决不了正面来球 |
| 嗅觉导航 | ❌ 连接组模型无侧化；Fly-Brain-AI 复现 4/6；未接入游戏 |
| 腹神经索驱动腿 | ⚠️ 已接通并驱动了腿，但没有迈步节律 |

## 11. 第 4 轮：多巴胺、后退重做、嗅觉诊断、腹神经索换模型（2026-09-14 追加）

在线页面同一链接：[果蝇闪避](https://claude.ai/code/artifact/31fb7608-dd2f-4c63-8cf1-8fc2a955e6c2)（Version 4），新增多巴胺卡片、后退重做、嗅觉诊断、腹神经索发放率模型的表格，以及“闻着找”开关。

全脑参考实验 11 组（`results/v2_ref/`，Brian2，每组峰值内存 3.9–4.1 GB，串行运行），分析脚本 `dodge/v4_refs_analysis.py` → `results/v2_ref/v4_analysis.json`。指标和判据都在看结果之前写进脚本开头。另有 2 组探索性沉默实验（11.4 节）。所有仿真都串行运行，并用 `scratch/memguard.sh` 限制内存。

### 11.1 吃到糖，会分泌多巴胺吗？【实测，阴性】

【文献】真实果蝇里，糖的奖赏信号由 PAM 簇多巴胺神经元送到蘑菇体（Liu et al. 2012 *Nature*；Burke et al. 2012 *Nature*），甜味和营养价值由不同的 PAM 亚群编码（Huetteroth et al. 2015 *Curr Biol*）；惩罚信号主要走 PPL1 簇。

全脑模型里有 PAM 307 个、PPL1 16 个、PPL2 8 个。**事先写定的判据**：只有在没有全脑失控（活跃神经元 < 2000）的条件下 PAM 放电，才算“糖味激活了奖赏多巴胺”。

| 刺激 | 全脑活跃神经元 | PAM 放电 | PPL1 放电 |
|---|---|---|---|
| 糖味左 200 Hz · 1 s | 549 | **0/307** | 0/16 |
| 糖味左 200 Hz · 0.5 s | 534 | **0/307** | 0/16 |
| 苦味双侧 200 Hz | 140 | **0/307** | 0/16 |
| 糖味右 200 Hz | 8,848（失控） | 123/307，均值 18 Hz | 14/16，99 Hz |
| 糖味双侧 100 Hz · 1 s | 8,851（失控） | 123/307，均值 9 Hz | 14/16，50 Hz |
| 糖 + 苦 200 Hz | 9,004（失控） | 124/307，均值 18 Hz | 14/16，96 Hz |
| 对照：气味 DM1 左 10 Hz | 8,481（失控） | 124/307，均值 19 Hz | 14/16，103 Hz |
| 对照：LC16 双侧 150 Hz | 983 | **0/307** | 1/16，0 Hz |

- 不失控时，糖味刺激下 PAM **一个都不放电**。
- 多巴胺神经元只在全脑失控时放电，而且 PPL1（惩罚）比 PAM（奖赏）更强；气味引起的失控里也一模一样，所以是**非特异的**。
- 重跑（第 17 节，试次之间互相独立）把这一条测得更干净：**同一个条件的不同试次里**，糖味双侧 100 Hz 有一个试次失控（8,805 个活跃）、PAM 放电 123/307，另一个试次不失控（566 个活跃）、PAM **0/307**；气味 DA2 左 50 Hz 也一样，3 个试次几乎无反应、PAM 0/307，第 4 个试次失控、PAM 120/307。放电与否只取决于有没有失控，与刺激是不是“奖赏”无关。
- 不是没有连线：糖味神经元（LB3）到 PAM 最少 2 跳，全部 307 个都可达（中位 3 跳）；只算 ≥ 5 个突触的连接时，277/307 可达（中位 4 跳）。苦味神经元到 PAM 的跳数完全一样，结构上分不出奖赏和惩罚。
- 【推测】原因：Shiu 模型把多巴胺、章鱼胺都当成普通的快速兴奋突触；真实奖赏通路里，章鱼胺经 G 蛋白偶联受体（OAMB）作用于 PAM（Burke 2012），是慢速神经调质。模型里也没有饥饿状态和突触可塑性。
- 所以游戏里吃糖时**没有**可显示的多巴胺信号。

### 11.2 LC16 剂量 → MDN【实测】

| LC16 刺激 | MDN 左/右 | DNa02 左/右 | 巨纤维 | 发放最高的其他下行神经元 |
|---|---|---|---|---|
| 双侧 25 Hz | 0/0 | 0/0 | 0 | 无 |
| 双侧 50 Hz | 0/0 | 4/0 | 0 | DNa13 5 Hz，DNp18 / DNp71 / DNa01 / DNa02 各 4 Hz |
| 双侧 100 Hz | 11.5/14.0 | **32/15.5** | 0 | DNa13 30–48，DNb09 32，DNge050 26，BDN2（DNg100）**21.5/21.5** |
| 双侧 150 Hz | 30.5/31.0 | **47/38.5** | 0 | DNa13 48–62，DNge050 **54**，DNb09 44，BDN2 **43/39** |
| 只刺激左侧 100 Hz | 0/0 | 0/**18** | 0 | DNp43(l) 24，右侧 DNa01 **20**，DNa13(r) 18–19 |
| 只刺激右侧 100 Hz | 4.2/6.2 | **41/2** | 0 | DNa13 40–42，左侧 DNa01 **33**，DNp71 32，BDN2 28/28 |

> **更正（2026-09-16）**：本表除 MDN 一列外，其余各列长期停留在**第 17 节重跑之前**的旧值
> （旧：双侧 150 Hz DNa02 32/44、双侧 100 Hz 30/18、左侧 0/16、右侧 40/0、BDN2 46 与 28–32）。
> 因此本表和 §10.0 同一条件的数字**互相矛盾**（那里写的 47/38.5 才是重跑后的正确值），却一直没被发现。
> 现已全部改按 `results/v2_ref/v4_analysis.json` 与 `rerun_diff.csv` 的重跑值。结论（MDN 需双侧 ≥ 100 Hz）不受影响。

- MDN 要**双侧** LC16 ≥ 100 Hz 才开始放电；只刺激一侧几乎不行（≤ 5 Hz）。这和“正面威胁才后退”一致：正前方物体同时落在两眼视野里。
- LC16 同时强烈驱动 DNa13、DNa01/DNa02，还有前进指令神经元 BDN2，**不是只管后退**。
- 单侧 LC16 驱动对侧（按注释胞体侧）的 DNa01/DNa02。按游戏的转向映射，左眼 LC16 → 往右转，即背离威胁。
- MDN 左右差很小，所以没有另加“MDN 左右差 → 转向”的映射。

### 11.3 后退实验重做【实测，设计事先写定】（`dodge/backward_v4.js` → `results/dodge/backward_v4.json`）

**设计**（写在脚本开头，跑之前定好）：
- 每次只有一个威胁，从果蝇正前方 40 mm、方位 ±10° 发出。
- 两种威胁：**滚球**是原游戏的球，按“果蝇继续前进”的提前量瞄准，穿过后继续滚；**扑击**瞄准发射时果蝇所在位置，到点停住 0.3 s 后消失。
- 3 档速度（15/30/60 mm/s）× 3 档 LC16 编码斜率（0.5 是第 3 轮事先声明值，另加 2、5）× 5 种切除，每格 3 个种子 × 8 个威胁 = 24 个，共 2,160 个威胁，原地起跳模式。
- 运行前修了 `game_core.js` 的提前量瞄准：球速低于果蝇行走速度（18 mm/s）时，原公式会把球瞄到果蝇身后；现在取最早的正解。页面的球速 35/60/95 mm/s 不受影响。
- 事先写下的物理预期：后退速度 12 mm/s；滚球会继续滚，正面来球时后退只能推迟被击中；扑击要在接触前净退出 ≥ 3.9 mm（球半径 + 果蝇半径）才躲得开。

**击中率**（“只剩后退”一列括号内是出现后退的威胁比例、接触前平均后退距离）：

| 威胁 | 速度 | LC16 斜率 | 完整 | 切巨纤维（后退 + 转向） | + 切 MDN（只剩转向） | + 切 DNa（只剩后退） | + 断 LC16 |
|---|---|---|---|---|---|---|---|
| 滚球 | 15 mm/s | 0.5 | 92% | 100% | 96% | 100%（后退 8%，0.0 mm） | 100% |
| 滚球 | 15 mm/s | 2 | 46% | 33% | 38% | 100%（后退 96%，0.4 mm） | 100% |
| 滚球 | 15 mm/s | 5 | 33% | 29% | 17% | 100%（后退 100%，1.9 mm） | 100% |
| 滚球 | 30 mm/s | 0.5 | 100% | 100% | 100% | 100%（后退 17%，0.0 mm） | 100% |
| 滚球 | 30 mm/s | 2 | 100% | 96% | 75% | 100%（后退 100%，1.0 mm） | 100% |
| 滚球 | 30 mm/s | 5 | 79% | 42% | 21% | 100%（后退 100%，4.6 mm） | 100% |
| 滚球 | 60 mm/s | 0.5 | 100% | 100% | 100% | 100%（后退 29%，0.0 mm） | 100% |
| 滚球 | 60 mm/s | 2 | 100% | 100% | 100% | 100%（后退 100%，1.8 mm） | 100% |
| 滚球 | 60 mm/s | 5 | 92% | 100% | 79% | 100%（后退 100%，5.1 mm） | 100% |
| 扑击 | 15 mm/s | 0.5 | 58% | 54% | 50% | 100%（后退 63%，0.0 mm） | 50% |
| 扑击 | 15 mm/s | 2 | 50% | 46% | 42% | 100%（后退 100%，0.5 mm） | 50% |
| 扑击 | 15 mm/s | 5 | 21% | 17% | 38% | 100%（后退 100%，2.1 mm） | 50% |
| 扑击 | 30 mm/s | 0.5 | 100% | 96% | 96% | 100%（后退 67%，0.0 mm） | 96% |
| 扑击 | 30 mm/s | 2 | 100% | 83% | 79% | 100%（后退 100%，1.0 mm） | 96% |
| 扑击 | 30 mm/s | 5 | 54% | 42% | 38% | 100%（后退 100%，4.1 mm） | 96% |
| 扑击 | 60 mm/s | 0.5 | 100% | 100% | 100% | 100%（后退 46%，0.0 mm） | 100% |
| 扑击 | 60 mm/s | 2 | 100% | 100% | 88% | 100%（后退 100%，1.8 mm） | 100% |
| 扑击 | 60 mm/s | 5 | 100% | 92% | 75% | 100%（后退 100%，5.0 mm） | 100% |

- **单靠后退一次都没躲开**：18 格全部 100% 被击中，包括每个威胁都触发了后退、接触前退了 4–5 mm 的格子。果蝇发现威胁之前一直在往前走，后退只抵消了这段前进；滚球还会继续滚过来。
- **躲开靠的是 LC16 驱动的转向**：只保留转向时，LC16 斜率 5 下击中率降到 17–79%，速度越快越难躲。事先声明的斜率 0.5 下，LC16 太弱，几乎来不及反应（50–100% 被击中）。
- **在转向上再加后退，多数格子没有改善，有的更差**：例如滚球 30 mm/s、斜率 5 时，42% 对比只转向的 21%。只有扑击 15 mm/s、斜率 5 时后退有帮助（17% 对比 38%）。每格只有 24 个威胁，±20 个百分点以内的差异不能当真。
- **断开 LC16 后滚球全部被击中**。慢速扑击（15 mm/s）仍有一半躲开，来自 LC4/LPLC2 驱动的转向或行走中的随机偏转。
- **原地起跳模式下，保留巨纤维常常更容易被击中**：起跳那 0.3 s 里果蝇不能转向。
- **结论**：在这个游戏里，连接组的 LC16 → MDN 后退通路没有带来躲避好处，LC16 → DNa 的转向才是有效成分。页面默认值没有按这些结果去改，仍是事先声明的斜率 0.5。
- 游戏子回路 JS 引擎（node，单线程）：5,916 s 仿真用时 1,091 s，**5.4 倍实时**，峰值内存 194 MB。

### 11.4 嗅觉：降低强度、换读出窗口、找失控源头【实测 + 探索性，阴性】

**降低强度**（事先写定：失控起点 = 5 ms 分箱内活跃神经元首次 ≥ 500 的时刻；比较起点之前的左右脉冲；侧化成立 = 左、右刺激的下行神经元 LI 符号相反且 |LI| ≥ 0.2）。表中脉冲数是每次试验、起点之前的左/右合计：

| 刺激 | 全脑活跃神经元 | 失控起点 | 投射神经元 左/右 | 下行神经元 左/右 |
|---|---|---|---|---|
| DM1 左 10 Hz（35 个受体） | 8,481 | 30 ms | 67 / 27 | 0 / 0 |
| DM1 左 20 Hz | 8,519 | 20 ms | 30 / 7 | 0 / 0 |
| DM1 右 20 Hz | 8,509 | 25 ms | 103 / 40 | 1 / 0 |
| DM1 左 50 Hz | 8,505 | 20 ms | 110 / 53 | 1 / 1 |
| DA2 左 100 Hz（16 个受体） | 8,441 | 65 ms | 156 / 91 | 8 / 5 |
| DA2 左 50 Hz | 8,071（4 个试次里 3 次只有被刺激的 16–17 个神经元活动、1 次失控到 8,071） | 320 ms | 118 / 70 | 4 / 2 |

- 降到 10 Hz 照样失控，而且是全或无：每个试次要么只有被刺激的几十个神经元动，要么直接冲到 8,000 多个，中间状态没有。
- **更正（第 17 节重跑）**：旧数据说“DA2 左 50 Hz 完全无反应”，那只是一个试次。试次独立之后，同样的刺激 4 次里有 1 次失控（8,071 个活跃）、3 次几乎无反应——阈值附近**是概率性的**。糖味双侧 100 Hz 同样，2 次里 1 次失控。失控前下行神经元的脉冲最多也只有个位数（0–8 个），左右差没有稳定符号，**判据仍然不成立**。
- 失控集合与刺激无关：DM1 左 10 Hz 与 DA2 左 100 Hz、DM1 右 20 Hz、糖味双侧 100 Hz 的活跃神经元重叠（Jaccard）分别为 0.97、0.97、0.91。
- **右侧 DM1 刺激时，反而左侧投射神经元更活跃**。查了结构：右侧 DM1 受体 → 左侧 DM1 投射神经元 1,664 个突触，→ 右侧 1,288 个；左侧受体 → 左 2,064、→ 右 1,183。左侧 DM1 投射神经元的输入整体更多，所以左右读出首先受重建数据的左右差影响。【推测】可能与感觉神经元 side 标注的定义或重建完整度有关。

**找失控源头**（探索性，事后提出）：
- 失控前 15 ms 最先放电的是触角叶局部神经元（lLN2T、lLN2P、v2LN30、il3LN6）、侧角神经元（LHCENT12b、LHAV4a1_b）和 DM1 投射神经元；糖味引起的失控则从咽下神经节（CB0700、MNx01 等）开始。
- 5 个失控条件里有 ≥ 4 个共有的“点火”神经元只有 4 个：M_l2PNl20、2 个 lLN2T_b、lLN2X04。lLN2T_b/c 的预测递质是 5-羟色胺、已知递质是乙酰胆碱，模型里两种都按兴奋处理。
- 沉默实验（DM1 左 20 Hz，判据：活跃 < 2,000 才算阻止失控，阻止了才跑右侧）：

| 条件 | 全脑活跃神经元 | 下行神经元 LI | 投射神经元 LI |
|---|---|---|---|
| 原样 | 8,519 | -0.01 | +0.05 |
| 沉默 4 个核心 | 8,248 | -0.03 | +0.02 |
| 沉默 120 个兴奋性局部神经元（乙酰胆碱/5-羟色胺） | 3,414 | +0.14 | +0.53 |

- 沉默兴奋性局部神经元后失控明显减弱（8,519 → 3,414），但仍超过判据，按规则没有跑右侧。而且左侧 LI 只有 +0.14，本来就达不到 0.2。
- **结论**：这个 LIF 连接组里，嗅觉输入是“全或无”的全脑失控，给不出转向信号。游戏里的“闻着找”只能手写（11.6 节）。

### 11.5 腹神经索：换成 Pugliese 2025 发放率模型【社区代码 · 实测】（`vnc/run_pugliese.py`、`vnc/analyze_pugliese.py`、`vnc/drive_legs_pugliese.py`）

- **来源**：【社区】Pugliese et al. 2025 bioRxiv，代码 github.com/smpuglie/Pugliese_cpg_2025 @ `faee4b0`。**仓库没有许可证**，只在本机 import 调用，没有复制代码；新建 conda 环境 `vnc-sim`（JAX 0.9.2、diffrax 0.7.0，只用 CPU）。
- **模型**（作者代码与默认参数，未改）：发放率神经元 τ·dr/dt = −r + max(0, r_max·tanh(a/r_max·(W·r + I − θ)))；τ、a、θ、r_max 每个神经元随机抽样，每组抽样叫一个“副本”。网络是作者发布的 MANC 前足神经节，4,604 个神经元，其中下行 1,318、中间 2,471、左右前腿运动神经元各 72 个。
- **容差**：用作者教程建议的宽松容差（rtol 1e-4、atol 1e-7）。先用 2 个副本和默认容差对比：发放率最大差 0.38 Hz，振荡得分差 ≤ 0.015，频率相同，速度快约 3.6 倍。单个副本 2 s 仿真耗时 0.2–36 s（DNg100 约 9–16 s，MDN 15–36 s），峰值内存 ≤ 2.2 GB。
- **节律判据**：用作者的振荡得分（自相关峰，≥ 0.5 记为振荡）。

| 刺激 | 振荡副本 | 频率中位 | 每副本活跃运动神经元（> 1 Hz） | 主要活跃模块 |
|---|---|---|---|---|
| 不刺激 | 0/16 | — | 0 | — |
| 左 DNg100（前进指令，作者默认实验） | **16/16** | **10.6 Hz** | 1.9 | 左腿 coxa swing |
| 双侧 DNg100 | **16/16** | **11.2 Hz** | 3.1 | 左 coxa swing、右 femur/tr flex |
| 4 个 MDN（后退），I = 250 | 0/16 | — | 83.6 | 两侧屈肌为主，持续放电 |
| MDN，I = 150（事后追加） | 0/8 | — | 90.2 | 同上 |
| MDN，I = 100（事后追加） | 0/8 | — | 94.5 | 同上 |
| 左 DNa02（转向），I = 300 | 1/16 | — | 6.0 | 左 coxa stance、femur reductor、tibia flex |

- **有节律了**：第 3 轮的 BANC LIF 模型没有节律；换成作者的发放率模型后，DNg100 刺激在 16 个副本里全部出现约 11 Hz 的运动神经元振荡。
- **但不是完整步态**：每个副本只有 2–4 个运动神经元参与（共 144 个）。事先写定的指标下，双侧刺激时同一条腿“摆动模块”与“支撑模块”发放率的相关中位是 **+0.73**（同相，不是交替），左右腿相关 +0.06（无关）。
- **MDN 在三档刺激强度下都没有节律**，而是招募 80–95 个运动神经元持续放电。

**驱动前腿**（FlyGym 1.2.1，身体固定，中腿和后腿固定在平均姿态）：
- 模块 → 关节：coxa swing/stance → ThC，femur/tr extend/flex → CTr，tibia extend/flex → FTi。
- 方向取自 FlyGym 预设步态（真实果蝇运动学）在摆动相与支撑相的平均角。
- 目标角 = 支撑极值 + u × (摆动极值 − 支撑极值)，u = 摆动发放率 / (摆动 + 支撑)。

| 驱动方式 | 左前腿 摆幅 · 节律占比 | 右前腿 | 左右相位差 |
|---|---|---|---|
| CPG 三足步态对照 | 0.83 mm · 0.98 @ 12.1 Hz | 0.83 mm · 0.99 | −179°（交替） |
| 左 DNg100 #0 | 0.20 mm · 0.84 @ 11.6 Hz | 基本不动（0.02 mm） | — |
| 双侧 DNg100 #0/#1/#3 | 0.18–0.19 mm · 0.80–0.92 @ 10.5–12.1 Hz | 基本不动（≤ 0.014 mm） | — |
| 双侧 DNg100 #2 | 0.20 mm · 0.75 @ 5.8 Hz | 0.31 mm · 0.25（无节律） | — |
| MDN #0 | 0.94 mm · 0.06（无节律，姿势偏移） | 0.26 mm · 0.22 | — |
| 左 DNa02 #0 / 不刺激 | 不动 | 不动 | — |

- **结论**：从“完全没有节律”进步到“左前腿按 11–12 Hz 节律摆动”。但幅度只有 CPG 的约 1/4，右前腿基本不动，左右不交替，摆动和支撑同相，**还不是迈步**。
- 【推测】原因：网络只有前足神经节，没有中后足和腿间耦合；没有本体感觉反馈；作者论文用了 1,024 个副本和剪枝去找核心回路，这里只随机抽了 16 个。

**当时没做、后来在第 12 节补做的部分**：巨纤维 → TTMn 电突触（12.3 节）、本体感觉闭环（12.4 节）、全腹神经索 6 条腿（12.1–12.2 节）。

### 11.6 游戏里的“闻着找”（手写，非连接组）【实测】（`dodge/odor_v4.js` → `results/dodge/odor_v4.json`）

- **为什么是手写的**：11.4 节说明连接组模型给不出气味转向信号，所以这一步不经过连接组。
- **规则**（`game_core.js` 的 `odorNav`，页面开关“闻着找”，默认关）：
  - 颗粒散发高斯气味场，σ = 15 mm；
  - 左右触角位于胸部前方 1.0 mm、左右相距 0.6 mm，各采一次浓度；
  - 浓度 > 0.01 时，朝浓度高的一侧以 120°/s 转向，叠加在 DNa 转向上；
  - 尝过（碰过）的颗粒不再吸引。
- **吃不吃仍由连接组决定**：碰到颗粒 → 糖/苦味觉神经元 → MN9。
- **检验设计**（事先写定）：每局依次放 6 颗（糖 → 苦 → 混合，各 2 颗），距果蝇 25 mm、方位随机；每颗最多等 20 s；3 个种子。

| 闻着找 | 20 s 内碰到颗粒 | 用时中位 | 糖 吃掉/碰到 | 苦 | 混合 |
|---|---|---|---|---|---|
| 关 | 0/18 | — | 0/0 | 0/0 | 0/0 |
| 开（手写） | 18/18 | 1.9 s | 6/6 | 0/6 | 0/6 |

- 结果符合构造：规则是手写的，找到颗粒是必然的，这**不是**连接组能力的证据。
- 有意思的是分工：手写嗅觉把果蝇带到每一颗颗粒前，连接组只吃糖粒，苦粒和混合粒都不吃。

### 11.7 加上强化训练会怎样？这台电脑能不能跑？【文献 + 实测速度 + 推测】

**先说清楚现状**：现在的连接组模型**不会学习**。突触权重是固定的测量值，没有可塑性；11.1 节也测到，吃糖时奖赏多巴胺神经元根本不放电。所以“强化训练”要么是给模型加上学习机制，要么是在模型外面训练别的东西。

**四条路线**：

| 路线 | 训练什么 | 能回答的问题 | 本机 |
|---|---|---|---|
| ① 蘑菇体多巴胺学习（推荐） | Kenyon 细胞 → 蘑菇体输出神经元（MBON）的突触，由多巴胺神经元门控 | 果蝇能不能在连接组约束下“学会”把气味和糖联系起来 | 能跑，分钟级【推测】 |
| ② 调游戏里手写接口的参数 | 视觉编码斜率、阈值、转向增益等十几个数，连接组不动 | 手写接口最优能躲到多好 | 能跑，小时级【推测】 |
| ③ 训练身体控制器（flybody 路线） | 行走/飞行神经网络策略 | 身体怎么走、怎么飞 | 从零训练很慢（见下），论文训练好的控制器可以下载 |
| ④ 训练连接组权重本身 | 每类突触的强度（符号与连线不变） | 连接组结构能否支持某个任务 | 子回路上能跑；训练后不再是“测得的连接组” |

- **① 为什么推荐**：这是果蝇自己的强化学习机制。【文献】多巴胺神经元把奖赏/惩罚信号送到蘑菇体，与气味同时出现时改变 Kenyon 细胞 → MBON 突触的强度（Hige et al. 2015 *Neuron*）；不同 MBON 分别驱动趋近或回避（Aso et al. 2014 *eLife*）。FlyWire 里有全部 5,177 个 Kenyon 细胞、96 个 MBON、331 个多巴胺神经元。
  - 要手写的部分：一条多巴胺门控的可塑性规则（有文献依据）。另外，因为模型里吃糖激活不了 PAM，只能把“吃到糖”直接接成 PAM 放电，相当于实验里用光遗传激活 PAM 当奖赏。
  - 可以做的实验：气味 A 配糖训练若干次 → 看 MBON 对气味 A 的反应变化 → 游戏里果蝇学会靠近气味 A。
  - 风险：11.4 节里嗅觉输入在全脑会失控，需要先在蘑菇体子回路里验证不失控。
- **② 的限制**：训练出来躲避率更高，只说明手写接口调得好，**不能**当成“果蝇大脑更聪明”的证据。这正是前面几轮一直避免的“为了结果去调手写规则”，只能作为明确标注的工程模式。
- **③ 的数字**：
  - 【官方论文】flybody（Vaxenburg et al. 2025 *Nature*）原文：训练需要约 10⁹ 个仿真步（行走）和 10⁸ 步（飞行），另有 10⁸ / 10⁷ 次策略网络更新；他们用 Ray 做多 CPU + GPU 并行，“把训练时间从几周降到几天或几小时”；训练好的控制网络在 Figshare 公开。
  - 【实测】本机 flybody 环境随机动作步进（`scratch/probe_rl_speed.py`）：walk_on_ball 每秒 345 个控制步（控制步长 2 ms，每步含 10 个物理步）；flight_imitation 每秒 217 个控制步（0.2 ms，每步含 4 个物理步）。
  - 【推测，线性估算，只算仿真、不算网络更新】论文没说“仿真步”指控制步还是物理步，所以给两个数：行走 10⁹ 步单进程约 34 天（按控制步）或 3.4 天（按物理步）；飞行 10⁸ 步约 5.3 天或 1.3 天。本机 6 个性能核理想并行再除以 6。网络更新另算：10⁸ 次更新哪怕每次只要 1 ms，也要约 28 小时。
  - 所以本机从零训练身体控制器按“天到周”计；更实际的是下载论文训练好的控制器直接用。这一点我还没下载验证。
- **本机其他实测速度**，供参考：
  - 全脑 LIF（Brian2）：1 s 大脑时间约 2.6–3.8 s，峰值 4 GB；
  - 腹神经索发放率模型：2 s 仿真 9–36 s，≤ 2.2 GB；
  - 游戏子回路 JS 引擎（4,599 个神经元）：5.4 倍实时，194 MB。路线 ② 里评估一组参数、打一局 60 s，约 11 s；1,000 次评估约 3 小时。

### 11.8 汇总

| 项目 | 状态 |
|---|---|
| 吃到糖分泌多巴胺 | ❌ 模型里没有：不失控时 PAM 0/307 放电；失控时的放电是非特异的；原因推测是模型没有神经调质和可塑性 |
| 正面威胁后退 | ⚠️ MDN 需要双侧 LC16 ≥ 100 Hz；重做实验里单靠后退 18/18 格全被击中，躲开靠 LC16 → DNa 转向 |
| 嗅觉导航 | ❌ 连接组给不出信号：10 Hz 刺激就全或无失控，沉默点火神经元也救不回；✅ 游戏里加了明确标注的手写“闻着找”（18/18 找到，只吃糖粒） |
| 腹神经索驱动腿 | ⚠️ 换成 Pugliese 发放率模型后有约 11 Hz 节律（16/16），左前腿能节律摆动；但只有 2–4 个运动神经元、幅度约 1/4、左右不交替，还不是迈步；MDN 无节律 |
| 强化训练 | 📋 未实施，只给了路线与本机实测速度：推荐蘑菇体多巴胺学习（本机能跑）；身体控制器从零训练按天到周计 |

**本轮新增文件**：
- 分析：`dodge/v4_refs_analysis.py`、`dodge/v4_olfaction_runaway.py`、`dodge/v4_olfaction_silencing.py`
- 对局：`dodge/backward_v4.js`、`dodge/odor_v4.js`
- 腹神经索：`vnc/run_pugliese.py`、`vnc/analyze_pugliese.py`、`vnc/drive_legs_pugliese.py`
- 页面：`dodge/collect_v4_results.py`
- 运行脚本：`scratch/queue_v4.sh`、`scratch/olf_silence.sh`、`scratch/probe_rl_speed.py`
- 改动：`dodge/game_core.js`（扑击威胁、提前量瞄准修正、`odorNav`）、`dodge/fly_dodge.template.html`、`dodge/build.py`
- 结果：`results/v2_ref/{v4_analysis,olfaction_runaway,olfaction_silencing}.json`、`results/vnc/pugliese/`、`results/dodge/{backward_v4,odor_v4,rl_speed,v4_results}.json`


## 12. 腹神经索三项：全腹神经索 6 条腿、巨纤维电突触、本体感觉闭环（2026-09-14 追加）

### 12.0 更正

- 11.8 节之后我在对话里说过“MANC 里巨纤维到 TTMn 的化学突触是 0”，这是错的：读作者矩阵时列号错开了一位。
- 按正确的列重读：MANC 里巨纤维到 TTMn 有化学突触，右 146 个、左 135 个，都是同侧配对。BANC 里只有 8 个（左）和 5 个（右）。巨纤维与 TTMn 之间的电突触，两个连接组里都没有。
- 10.6 节表格和页面里的相应说法已改正。

### 12.1 全腹神经索（MANC，23,532 个神经元）【社区模型 · 实测】（`vnc/manc_full.py`、`vnc/analyze_manc_full.py`）

**做法**：
- 作者的全腹神经索矩阵照作者代码稠密载入要约 9 GB，所以改成稀疏存储：1,372,404 条连接、2,415 万个突触，按列分块转换用时 3 s，峰值 634 MB。
- 方程、参数抽样、求解器与作者一致，只把矩阵乘法换成稀疏版本。
- **先在前足网络上对齐检验**：用自写代码按作者方式抽样，参数与作者 `prepare_neuron_params` 完全相同。稀疏版运动神经元发放率与作者稠密版最大差 0.11–0.15 Hz（判据 ≤ 0.5 Hz），速度还快一倍——**这半句无出处**：只记录了稀疏版的 4.5/4.7 s，没有稠密版计时（最大差 0.11–0.15 Hz 那半句有据可查）。
- 全腹神经索每个副本 **0.4–109.9 s**，峰值内存 1.25 GB。

**刺激强度要重新定**：
- 作者的全腹神经索配置没有公开。作者按“网络里神经元大小的中位数”缩放阈值和增益，全腹神经索的中位数比前足网络小，同样的电流驱动更弱。
- 探针：双侧 DNg100 在 I = 250 时只有 9.5/9.8 Hz，腿部运动神经元一个都不动。
- 所以在看任何节律结果之前，按“DNg100 发放率与前足网络默认实验相同（约 16 Hz）”反推出 I ≈ 350，定为主条件；保留 250/400/600 做剂量对照。

| 条件 | 振荡副本 | 失控副本（全网 ≥ 2,000 个神经元活跃） | 振荡副本的频率 | 振荡副本里活跃的腿部运动神经元 |
|---|---|---|---|---|
| 不刺激 | 0/8 | 0/8 | — | — |
| 双侧 DNg100，I = 250 | 0/8 | 0/8 | — | 0 |
| **双侧 DNg100，I = 350（主条件）** | **12/16** | 3/16 | 8.0–11.5 Hz | 4–18 个 |
| 双侧 DNg100，I = 400 | 3/8 | 4/8 | 7.2–10.8 Hz | 9–26 个 |
| 双侧 DNg100，I = 600 | 0/8 | **8/8** | — | — |
| 左侧 DNg100，I = 350 | 4/8 | 0/8 | 6.6–11.5 Hz | 0–1 个（振荡幅度 < 1 Hz） |
| 4 个 MDN，I = 250 | 0/8 | **8/8** | — | — |
| 4 个 MDN，I = 400 | 0/8 | **8/8** | — | — |

**主条件下每条腿的情况**（16 个副本；“振荡”指该腿运动神经元的作者得分均值 ≥ 0.5）：

| 腿 | 前左 | 前右 | 中左 | 中右 | 后左 | 后右 |
|---|---|---|---|---|---|---|
| 振荡的副本比例 | 31% | 19% | 12% | 44% | 12% | **75%** |
| 频率中位 | 8.4 Hz | 9.5 Hz | — | 9.9 Hz | — | 9.5 Hz |

**腿间相位**（用每条腿的 E1 中间神经元，作者 Extended Data Fig. 8 用的同一类；只在振荡副本里、两条腿都振荡且频率相差 ≤ 1 Hz 时算）：

| 腿对 | 三足步态预期 | 实测圆均值（一致性 R，样本数） |
|---|---|---|
| 前左–前右 | 180° | 49°（0.46，4） |
| 中左–中右 | 180° | 134°（1 个样本） |
| 后左–后右 | 180° | 7°（0.41，3） |
| 中左–后左 | 180° | 12°（0.87，4） |
| 中右–后右 | 180° | 18°（0.93，6） |
| 前右–中右 | 180° | −138°（0.93，3） |
| 前右–后右 | 0° | −136°（0.96，6） |

- **结论**：有了中后足之后，DNg100 的节律会传到 6 条腿的运动神经元，但节律窗口很窄：I = 250 不动，I = 350 多数振荡，I ≥ 400 大多失控。
- 腿间相位与三足步态不符：同侧中–后腿几乎同相（12°、18°，一致性高），前右与后右反相。每对样本只有 1–6 个，只能说“没有看到三足步态”。
- 同一条腿的摆动模块与支撑模块强烈同相（相关 +0.94），不是交替。
- MDN（后退指令）两档强度下 16/16 全部失控，没有节律。

### 12.2 驱动 NeuroMechFly 的 6 条腿【实测】（`vnc/drive_legs_manc.py`）

**映射**：
- 与前足网络的映射相同，推广到 6 条腿。
- 用哪个关节自由度由规则决定：取 FlyGym 真实步态数据里摆动相与支撑相平均角差最大的那个。结果是胸-基节全用 Coxa，基-转节前中腿用 Femur_roll、后腿用 Femur，腿节-胫节用 Tibia。
- 身体固定。

| 驱动方式 | 前左 | 中左 | 后左 | 前右 | 中右 | 后右 |
|---|---|---|---|---|---|---|
| CPG 三足步态对照 | 0.83 mm · 0.98 | 1.07 · 0.96 | 1.03 · 0.98 | 0.83 · 0.99 | 1.07 · 0.97 | 1.03 · 0.98（12.1 Hz） |
| 主条件 #0 | 0.04 | 0.07 | 0.03 | 0.04 | 0.07 | **0.72 mm · 0.89 @ 9.5 Hz** |
| 主条件 #1 | 0.04 | 0.07 | 0.03 | 0.04 | 0.07 | **0.59 · 0.48 @ 8.9 Hz** |
| 主条件 #2 | 0.03 | 0.05 | 0.02 | 0.03 | 0.05 | **0.59 · 0.86 @ 10.0 Hz** |
| 主条件 #3（失控） | 0.45 · 0.14 | 1.27 · 0.08 | 1.33 · 0.21 | 0.29 · 0.13 | 1.20 · 0.05 | 1.58 · 0.42 |
| 双侧 I = 600 #0（失控） | 0.44 · 0.49 | 1.39 · 0.45 | 1.46 · 0.29 | 0.28 · 0.71 | 1.04 · 0.27 | 1.52 · 0.38 |
| MDN I = 400 #0（失控） | 0.63 · 0.41 | 0.52 · 0.49 | 0.62 · 0.36 | 0.42 · 0.25 | 0.42 · 0.29 | 0.85 · 0.15 |
| 左侧 I = 350 #0、不刺激 | 不动 | 不动 | 不动 | 不动 | 不动 | 不动 |

表中数字为腿尖前后摆幅（mm）· 4–30 Hz 节律占比。

- **相位指标本身是可靠的**：CPG 对照测得左右 −179°、同侧相邻 ±155°、同侧前后 −5°，正是三足步态。
- 主条件下，**只有右后腿稳定地按 9–10 Hz 节律摆动**，幅度 0.6–0.7 mm，约为 CPG 的 60–70%；其余 5 条腿摆幅 ≤ 0.07 mm。它们一起抖的频率**各副本并不相同**（rep0 14.2 Hz、rep1 6.3 Hz、rep2 10.0 Hz；原文只写了 rep0 的 14.2 Hz），是身体振动，不是迈步。按事先的 0.05 mm 门槛算出了中左–中右 ±180° 的相位，但这是振动造成的，没有意义。
- 失控时 6 条腿都大幅乱动，但没有节律。
- **结论**：全腹神经索比前足网络多了一条能节律摆动的腿（右后腿），幅度也更大，但仍然没有腿间协调，不是步态。

### 12.3 巨纤维 → TTMn 电突触【实测 + 手写耦合】（`vnc/manc_full.py gap` → `results/vnc/manc_full/gap_summary.json`）

**设计**（运行前写定）：
- 刺激双侧巨纤维（DNp01）两档强度：按副本平均参数反推，让巨纤维发放率达到 16 Hz（I ≈ 1,925）或 100 Hz（I ≈ 9,670）。
- 发放率模型没有膜电位，电突触只能近似为对称的发放率耦合：TTMn 的输入加上 g·(r_巨纤维 − r_TTMn)，巨纤维的输入加上 g·(r_TTMn − r_巨纤维)。
- g = 等效突触数 × 0.03，与化学突触同单位；同侧配对，取 0（只有化学突触）、150（≈ 化学突触数）、1,500 三档。
- 副本 0–3，参数与 12.1 节相同。

**结果**（4 个副本的中位数；TTMn 发放率为 230 ms 之后的平均）：

| 巨纤维刺激 | 电突触 | 实际巨纤维 右/左 | TTMn 右/左 | TTMn 峰值 右/左 | 半峰时间 | 失控副本 |
|---|---|---|---|---|---|---|
| 标定 16 Hz | 无（只有化学突触） | 1.2 / 2.1 Hz | 0 / 0 | 2 / 0 Hz | 75 ms | 4/4 |
| 标定 16 Hz | 150 | 1.2 / 2.0 | 0 / 0 | 5 / 0 | 67 ms | 4/4 |
| 标定 16 Hz | 1,500 | 0.8 / 1.4 | 0 / 0 | 12 / 6 | 27 ms | 4/4 |
| 标定 100 Hz | 无（只有化学突触） | 82 / 82 | 0 / 0 | 14 / 2 | 23 ms | 4/4 |
| 标定 100 Hz | 150 | 79 / 78 | 0 / 0 | 26 / 10 | 22 ms | 4/4 |
| 标定 100 Hz | **1,500** | 66 / 63 | **30 / 25 Hz**（范围 21–36 / 14–31） | 62 / 46 | 17 ms | 4/4 |

- **只有化学突触时，TTMn 不会持续放电**：巨纤维 80 Hz、化学突触 135/146 个，TTMn 也只在刺激后约 20 ms 出现一个短峰，随后被压到 0。它最强的输入是抑制性中间神经元（IN21A026、IN13A022 等）。
- **加上约为化学突触 10 倍的电突触耦合（等效 1,500 个），TTMn 才能跟住巨纤维**，持续 25–30 Hz。这个结果取决于我选的耦合强度，**不能说明真实电突触有多强**。
- **24 次模拟全部让全腹神经索失控**（逐次 **5,165–8,375** 个神经元活跃、中足 **50–92** 个运动神经元一起放电；按 6 个条件各自 4 副本的中位数看是 5,786–7,660 与 65–83。原文的「5,000–7,900 / 65–83」把逐次口径和条件中位数口径混在了一句里，2026-09-16 更正）。“标定 16 Hz”那档，巨纤维自己也被网络反馈压到 1–2 Hz，反推的强度没有达到目标。这个模型给不出“巨纤维 → 只触发跳跃”这样干净的输出。
- 发放率模型的时间常数是 20 ms，表现不了真实电突触毫秒级的快速传递。所以这里只看得到“能不能跟住”，不看时间。
- 没有接身体：MANC 表里 TTMn 没有模块标注，要驱动中足得再手写一套映射。游戏里起跳本来就由巨纤维发放触发。

### 12.4 本体感觉闭环【实测 · 探索性，感受器编码为手写】（`vnc/export_manc_params.py`、`vnc/proprio_loop.py`）

**做法**：
- 两个 conda 环境没法合并（JAX 在 `vnc-sim`，FlyGym 1.2.1 在 `fba`），所以先把重加权后的连接矩阵和副本 0–3 的参数导出成 numpy 文件。闭环里用 numpy 定步长 RK4（0.5 ms），与身体（0.1 ms）每 1 ms 交换一次。
- **先对齐检验**（事先判据：主频相差 ≤ 0.5 Hz 且相关 ≥ 0.8）：不接身体的定步长开环与 12.1 节 Dopri5 结果对比，副本 0–2 主频完全相同（9.0/9.0/10.2 Hz），相关 0.999/0.993/0.999，最大差 0.26–0.68 Hz，**通过**。
- **感受器**：只用经腿神经进入的本体感受器，按入口神经（ProLN/MesoLN/MetaLN）分到 6 条腿，共弦音器 394 个、毛板 78 个、钟形感器 9 个。左右数量不对称，例如前左 27 个、前右 66 个，来自重建数据本身。被编码的感受器发放率直接钳制为编码值。
- **手写编码**（运行前写定）：
  - 弦音器 → 腿节-胫节角：一半偏好大角度、一半偏好小角度，S 形曲线，中点和宽度取自 FlyGym 预设步态；
  - 毛板 → 胸-基节角接近两端；
  - 钟形感器 → 基-转节与腿节-胫节的扭矩，用 CPG 对照的中位数归一化。
- **最高发放率**：16 Hz，与标定后 DNg100 的发放率同量级；另做 50 Hz 敏感性检查。
- **对照**：开环；感受信号整体错位到别的腿（例如前左腿的感受器读中左腿的关节）。

| 条件 | 活跃腿部运动神经元 | 运动神经元总活动 主频 · 节律占比 | 摆幅 ≥ 0.1 mm 的腿（摆幅 mm · 节律占比） | 感受器平均发放率（弦音器 / 毛板 / 钟形感器） |
|---|---|---|---|---|
| 开环 #0 | 12 | 9.0 Hz · 0.99 | 右后 0.72 · 0.89 | — |
| 闭环 16 Hz #0 | 255 | 4.5 Hz · 0.18 | 6 条腿 0.34–1.05 · 0.10–0.33 | 8.0 / 3.2 / 1.6 Hz |
| 信号错位 #0 | 237 | 2.8 Hz · 0.14 | 6 条腿 0.36–1.02 · 0.09–0.31 | 8.0 / 3.5 / 1.4 Hz |
| 开环 #1 | 6 | 9.0 Hz · 1.00 | 右后 0.59 · 0.49 | — |
| 闭环 16 Hz #1 | 257 | 2.3 Hz · 0.21 | 6 条腿 0.73–1.52 · 0.06–0.35 | 8.0 / 5.1 / 1.8 Hz |
| 信号错位 #1 | 244 | 3.4 Hz · 0.27 | 6 条腿 0.38–1.46 · 0.05–0.37 | 8.0 / 5.0 / 2.0 Hz |
| 开环 #2 | 8 | 10.2 Hz · 0.99 | 右后 0.59 · 0.86 | — |
| 闭环 16 Hz #2 | 271 | 2.8 Hz · 0.67 | 6 条腿 0.66–1.41 · 0.05–0.19 | 8.0 / 4.5 / 1.9 Hz |
| 信号错位 #2 | 274 | 2.8 Hz · 0.45 | 6 条腿 0.47–1.53 · 0.07–0.33 | 8.0 / 4.5 / 2.0 Hz |
| 闭环 50 Hz #0 | 244 | 2.8 Hz · 0.11 | 6 条腿 0.25–1.55 · 0.05–0.61 | 25.0 / 9.7 / 4.5 Hz |

- **接上本体感觉后，节律反而没了**：开环时只有右后腿按 9–10 Hz 规律摆动；闭环后 6 条腿都在大幅乱动，活跃的腿部运动神经元从 6–12 个跳到 237–274 个，与 12.1 节失控副本的水平（254–278 个）相当，节律占比降到 0.05–0.35。
- **正确对应和错位的感受信号结果几乎一样**，50 Hz 也一样，说明起作用的不是“哪条腿、什么角度”的反馈信息。
- 【推测】更可能是编码里很大的持续成分：弦音器平均 8 Hz，相当于 394 个弦音器一直在给网络加兴奋，把它推进了失控状态。
- **结论**：按这套手写编码，本体感觉反馈没有帮助形成步态，只是非特异的额外兴奋。这不能说明真实果蝇的本体感觉没用，只说明这套编码不行。
- 下一步可以改成“只在关节运动时放电、平均为零”的相位性编码，但编码形式又多一层手选。这次没有跑。
- 用时：每次闭环 2 s 仿真 42–57 s，峰值内存 1.44 GB。

### 12.4b 本体感觉闭环第二版：相位性编码【实测 · 探索性】（`vnc/proprio_loop.py run_phasic` → `results/vnc/manc_full/proprio_phasic_summary.json`）

**为什么改**：第一版的持续编码让弦音器平均 8 Hz 一直放电，把网络推进失控，而且正确对应与错位对应结果一样。第二版改成“关节动了才放电、静止时为 0”。

**编码**（运行前写定）：
- 弦音器 → 腿节-胫节角速度；毛板 → 胸-基节角速度。两者都按方向分成两半：一半只在正向转动时放电，一半只在反向转动时放电，r = r_max·tanh(速度/ω0)。
- 钟形感器 → 负载增加的速度。
- ω0 等归一化常数取 CPG 步态里的中位数：腿节-胫节 10–21 rad/s，胸-基节 10–14 rad/s。
- 最高发放率 16 Hz，副本 0 另做 50 Hz。开环结果沿用第一版（同一积分器和身体，没有随机性）。

**判据**（运行前写定）：
- A 不破坏节律：活跃腿部运动神经元 < 50，且总活动节律占比 ≥ 0.5。
- B 有改善：节律腿（摆幅 ≥ 0.1 mm 且节律占比 ≥ 0.5）多于开环的 1 条。
- C 反馈信息起作用：同一副本里正确对应与错位对应在 A 或 B 上结论不同，或节律腿数相差 ≥ 2。

| 条件 | 活跃腿部运动神经元 | 总活动 主频 · 节律占比 | 摆幅 ≥ 0.1 mm 的腿（摆幅 mm · 节律占比） | 节律腿数 | A | B | 感受器平均发放率（弦音器 / 毛板 / 钟形） | 感受器活跃时间比例 |
|---|---|---|---|---|---|---|---|---|
| 开环 #0 | 12 | 9.0 Hz · 0.99 | 后右 0.72 · 0.89 | 1 | ✅ | ❌ | — | — |
| 相位性 16 Hz #0 | 12 | 9.0 Hz · 0.99 | 后右 0.99 · 0.86 | 1 | ✅ | ❌ | 0.19 / 0.44 / 0.37 Hz | 2.7% / 5.3% / 3.1% |
| 相位性 16 Hz · 错位 #0 | **274** | 3.4 Hz · 0.10 | 6 条腿乱动（0.28–1.51 mm） | 1 | ❌ | ❌ | 0.30 / 0.25 / 0.24 Hz | 4.9% / 4.8% / 3.9% |
| 开环 #1 | 6 | 9.0 Hz · 1.00 | 后右 0.59 · 0.49 | 0 | ✅ | ❌ | — | — |
| 相位性 16 Hz #1 | 7 | 7.9 Hz · 0.97 | 后右 0.17 · 0.65 | 1 | ✅ | ❌ | 0.05 / 0.30 / 0.22 Hz | 1.4% / 2.2% / 1.8% |
| 相位性 16 Hz · 错位 #1 | 8 | 7.3 Hz · 0.98 | 中右 0.56 · 0.75，后右 0.59 · 0.72 | **2** | ✅ | ✅ | 0.12 / 0.16 / 0.14 Hz | 1.5% / 1.8% / 1.2% |
| 开环 #2 | 8 | 10.2 Hz · 0.99 | 后右 0.59 · 0.86 | 1 | ✅ | ❌ | — | — |
| 相位性 16 Hz #2 | 10 | 9.0 Hz · 0.98 | 后右 0.60 · 0.59 | 1 | ✅ | ❌ | 0.16 / 0.32 / 0.23 Hz | 2.2% / 3.2% / 1.9% |
| 相位性 16 Hz · 错位 #2 | 11 | 8.5 Hz · 0.99 | 后右 0.59 · 0.88 | 1 | ✅ | ❌ | 0.15 / 0.19 / 0.16 Hz | 1.8% / 2.1% / 1.4% |
| 相位性 50 Hz #0 | **261** | 2.3 Hz · 0.08 | 6 条腿乱动（0.42–1.54 mm） | 1 | ❌ | ❌ | 0.91 / 0.98 / 0.70 Hz | 5.6% / 6.1% / 4.4% |

- **编码确实变成了“动了才放电”**：感受器只在 1–6% 的时间里放电，平均 0.05–1 Hz；第一版是弦音器平均 8 Hz。
- **判据 A**：正确对应 3/3 保持节律（第一版 0/3）。错位对应 2/3 保持，副本 0 失控。50 Hz 时副本 0 也失控。
- **判据 B**：正确对应 0/3，仍然只有右后腿按节律摆动。节律频率变化不大（9.0→9.0、9.0→7.9、10.2→9.0 Hz）；右后腿摆幅一次变大（0.72→0.99 mm）、一次变小（0.59→0.17 mm）、一次不变。唯一多出一条节律腿（中右）的是错位对应的副本 1。
- **判据 C**：3 个副本里只有副本 0 成立，而且方向是“错位对应失控”。副本 1 里反而是错位对应多了一条腿。没有一致的证据说明反馈内容（哪条腿、往哪边转）在起作用。
- **结论**：相位性编码解决了“反馈把网络推进失控”的问题（16 Hz 时），但没有带来更多腿的节律或腿间协调。反馈再强一点（50 Hz）又会失控，说明这个网络本身就在失控边缘。
- **局限**：
  - 只有 3 个副本；
  - 身体是固定的，没有地面接触，所以没有真实的支撑相负载；
  - 除右后腿外其他腿几乎不动，它们的感受器也就几乎没有输入，反馈很难“带动”一条不动的腿；
  - 编码仍是手写的。
- 用时：每组 44–46 s，峰值内存 1.18 GB。

### 12.5 汇总

| 项目 | 结果 |
|---|---|
| 全腹神经索 6 条腿 | ⚠️ 节律会传到 6 条腿的运动神经元，但窗口窄（I = 350 时 12/16 振荡，I ≥ 400 大多失控）。腿间相位不是三足步态；驱动身体后只有右后腿稳定摆动（9–10 Hz，0.6–0.7 mm） |
| 巨纤维 → TTMn 电突触 | ⚠️ 只有化学突触时 TTMn 只出约 20 ms 的短峰。手加约 10 倍强的电突触后才持续跟随（25–30 Hz），结果由手选耦合决定。巨纤维刺激 24/24 让全腹神经索失控 |
| 本体感觉闭环 | ❌ 第一版持续编码：反馈把网络推进失控，正确与错位结果相同。⚠️ 第二版相位性编码（12.4b）：16 Hz 时 3/3 保持节律，但仍只有右后腿有节律，错位对照没有一致差别；50 Hz 又失控 |
| 本机资源 | 全部串行；最大峰值内存 1.44 GB；全腹神经索每个副本 **0.4–115.9 s**（含 GF 耦合扫描的 54.9–115.9 s） |

**本节新增文件**：
- 模型与分析：`vnc/manc_full.py`（build/bench/parity/run/gap）、`vnc/analyze_manc_full.py`、`vnc/drive_legs_manc.py`、`vnc/export_manc_params.py`、`vnc/proprio_loop.py`（parity/run/run_phasic）
- 运行脚本：`scratch/queue_vnc6.sh`
- 结果：`results/vnc/manc_full/`（W_csc.npz、summary.json、analysis.json、legs_summary.json、gap_summary.json、proprio_parity.json、proprio_summary.json、proprio_phasic_summary.json 与各条件的 npz）

### 12.6 用作者的全突触数据重跑【实测】（`MANC_DATASET=all`，`scratch/queue_manc_all.sh` → `results/vnc/manc_all/`）

**数据差别**：
- 12.1–12.4 用的是作者较早的 `W_20251006`（23,532 个神经元，137 万条连接）。
- 作者仓库里另有较新的全突触矩阵 `W_20260522_allSynapses`（23,628 个神经元）。它是 4.5 GB 的稠密矩阵，这次从 zip 流里逐列读成稀疏格式：530 万条连接、3,093 万个突触，用时 7.9 s，峰值 266 MB。
- 两份数据里共有的连接，权重完全相同（相关 1.0、符号一致 100%）。全突触版多出 393 万条弱连接，中位只有 1 个突触（原有连接中位 10 个），另多 96 个神经元。

**做法**：
- 方程、参数抽样、判据都不变。标定规则（DNg100 16 Hz）算出 I = 360。
- 条件缩减为和步态相关的 5 个：I = 600 和 MDN 在旧数据里全部失控，这次不重复。
- 矩阵大了 3.9 倍，每个副本 **0.8–318.8 s**。

**腹神经索（主条件：旧数据 I = 350，全突触 I = 360）**：

| 指标 | 旧数据 | 全突触数据 |
|---|---|---|
| 振荡副本 | 12/16 | **14/16** |
| 失控副本 | 3/16 | **1/16** |
| 振荡频率 | 8.0–11.5 Hz | 7.2–12.5 Hz |
| I = 400：振荡 / 失控 | 3/8、4/8 | 3/8、5/8 |
| 左侧刺激：振荡 | 4/8 | 5/8 |
| 各腿振荡副本比例（前左/前右/中左/中右/后左/后右） | 31/19/12/44/12/75% | 50/25/12/**69**/12/**88**% |
| 同一条腿摆动与支撑模块相关 | +0.94 | +0.94 |
| E1 腿间相位 | 不是三足步态 | 仍不是三足步态（中右–后右 40°，一致性 0.76，12 个样本） |

**驱动 NeuroMechFly 6 条腿**（腿尖摆幅 mm · 节律占比）：

| 驱动 | 前左 | 中左 | 后左 | 前右 | 中右 | 后右 |
|---|---|---|---|---|---|---|
| 主条件 #0 | 0.04 | 0.07 | 0.03 | 0.04 | 0.07 | **0.59 · 0.74** |
| 主条件 #1 | 0.06 | 0.12 · 0.83 | 0.05 | 0.06 | **0.59 · 0.90** | **0.80 · 0.74** |
| 主条件 #2（失控） | 0.46 · 0.22 | 0.85 · 0.15 | 1.50 · 0.23 | 0.38 · 0.09 | 1.01 · 0.18 | 1.53 · 0.30 |
| 主条件 #3 | 0.07 | 0.14 · 0.92 | 0.05 | 0.07 | **0.62 · 0.75** | 0.60 · 0.45 |
| I = 400 #0 | 0.26 · 0.79 | 0.13 · 0.92 | 0.80 · 0.90 | 0.07 | 0.61 · 0.90 | 0.68 · 0.72 |

- 旧数据里只有右后腿会摆；全突触数据里，中右腿也常常一起摆（副本 1、3）。副本 1 中右与右后两腿相位差 164°，接近同侧相邻腿交替。
- 中左腿 0.12–0.14 mm 接近身体振动水平。
- I = 400 时有 4–5 条腿在动，但各腿频率不同（6.3/9.5/11.6 Hz），谈不上协调。
- 前左、前右、后左腿仍基本不动，不是步态。

**相位性编码本体感觉闭环**（判据与 12.4b 相同；积分器检验 3/3 通过：主频相同、相关 0.989–1.0，但最大绝对差 3–5 Hz，比旧数据大）：

| 副本 | 开环 | 相位性 16 Hz（正确对应） | 相位性 16 Hz（错位） |
|---|---|---|---|
| #0 | 9 个运动神经元，10.7 Hz；节律腿：后右 | 10 个，9.0 Hz；后右（0.66 mm） | 13 个，7.9 Hz；中左 0.11、中右 0.59、后右 0.60 mm |
| #1 | 9 个，11.3 Hz；中左 0.11、中右 0.58、后右 0.79 mm（中右–后右 168°） | 14 个，11.3 Hz；中左 0.15、中右 0.63、**后右 1.02 mm**（161°） | **失控**（293 个） |
| #2 | **失控**（235 个） | 仍失控（232 个） | 仍失控（235 个） |
| 50 Hz #0 | — | 12 个，9.0 Hz，后右 0.29 mm（未失控） | — |

- 判据 A（不破坏节律）：正确对应在开环不失控的 2 个副本里都保持。副本 2 开环就失控，反馈没能拉回来。
- 判据 B（节律腿多于 1 条）：正确对应只在副本 1 成立，但它的开环本来就有 3 条，没有比开环更多。
- 判据 C（反馈内容起作用）：副本 0、1 成立，但方向相反：副本 0 错位后多出两条腿，副本 1 错位后失控。与旧数据一样，**没有一致证据**说明“哪条腿、往哪边转”的信息在起作用。

**巨纤维 → TTMn**（缩减网格，运行前写定：巨纤维标定 16 Hz 只做无电突触；100 Hz 做无电突触与等效 1,500 个突触两档；各 4 个副本，中位数）：

| 巨纤维刺激 | 电突触 | 实际巨纤维 右/左 | TTMn 右/左（旧数据） | TTMn 右/左（全突触） | 失控 |
|---|---|---|---|---|---|
| 标定 16 Hz | 无 | 0.05 / 0.1 Hz | 0 / 0 | 0 / 0（一个副本 8 Hz，但半峰在 681 ms，是全网失控带起来的） | 4/4 |
| 标定 100 Hz | 无 | 78 / 85 | 0 / 0 | 0.25 / 0（范围 0–1 Hz） | 4/4 |
| 标定 100 Hz | 1,500 | 58 / 61 | 30 / 25 | **23 / 13**（范围 16–36 / 7–16） | 4/4 |

- 结论与旧数据相同：只有化学突触时 TTMn 基本不放电；手加强电突触才能跟随，而且全突触数据里跟得更弱一点；巨纤维刺激每次都让全腹神经索失控。

**结论（用全突触数据会不会更好）**：
- **稍好**：标定强度下失控更少（1/16 对 3/16），更多腿出现节律，常有两条同侧腿（中右、右后）接近交替摆动。
- **没有质变**：仍不是三足步态，同一条腿的摆动与支撑依旧同相。本体感觉反馈（相位性）仍然只是“不破坏”，看不到稳定的改善。网络对扰动依然敏感，错位反馈、较强刺激都会让个别副本失控。
- 巨纤维 → TTMn 电突触的结论不变。
- 用时：整个重跑 2 小时 49 分钟（15:46–18:35），峰值内存 1.53 GB。

## 13. 让果蝇“说中文”，发给 Claude Opus 5（2026-09-14 追加）【实测】（`language/fly_words.py`、`language/ask_claude.py` → `results/language/`）

起因是新闻报道 @chetaslua 把整颗果蝇大脑模拟接入 ChatGPT（用线性读出把放电“翻译”成词）。我们没看到对方代码，按公开描述在本机自己实现了一遍，词和句子都用中文，最后用本机 Claude Code 的登录配置调用 Opus 5。

**先说清楚这是什么、不是什么**：
- 果蝇不会说话。词表、每个词对应哪群感觉神经元、句子模板，都是我们写的。
- “翻译器”是用“给了哪些刺激”当标签训练出来的线性分类器。它能检验的是：刺激信息传到下游（非感觉神经元、下行 / 运动神经元）以后，还能不能被线性地读出来。

**设计**（运行前写进脚本）：
- 12 个中文词，各对应一群感觉神经元，左右两侧都刺激，100 Hz：
  - 味道：甜 = LB3；苦 = LB1a–d。
  - 气味：醋 = ORN_DM1 + VA2；霉味 = ORN_DA2；二氧化碳 = ORN_V。
  - 温湿度：热 = TRN_VP2；冷 = TRN_VP3a/b；干 = HRN_VP4；湿 = HRN_VP5。
  - 光：亮 = R1-6。
  - 触角：声音 = JO-A/B；风 = JO-C/E。
- 300 个试次，每个词独立以 0.2 概率出现，每次刺激 0.25 s、空白 0.25 s。前 240 个训练，后 60 个测试。
- 第 301 个试次固定刺激“醋、甜、热、亮”作为“第一句话”，不参与训练。
- 特征：刺激窗口内的脉冲数。A = 121,706 个非感觉神经元；B = 1,409 个下行 + 运动神经元。
- 读出：每个词一个岭回归，正则强度在训练集内 5 折交叉验证选定。
- 句子：按手写中文模板拼。
- 全脑 Brian2 编译一次，一次跑完 150.75 s 脑内时间，用时 429 s，峰值内存 3.29 GB。每个试次中位约 7,970 个非感觉神经元有放电，气味刺激常引发全脑失控（见 11.4 节）。

**测试集结果**（60 个试次，每个词 7–18 个阳性）：

| 特征 | 平均准确率 | 平均平衡准确率 | 12 个词全对的试次 | 较弱的词（平衡准确率） |
|---|---|---|---|---|
| A 非感觉神经元 | 99.0% | 96.0% | 88.3% | 热 0.94、湿 0.57 |
| B 下行 + 运动神经元 | 85.3% | 76.3% | 15.0% | 亮 0.43、霉味 0.54、热 0.54、醋 0.67、湿 0.67、冷 0.69 |

- 只看下行 + 运动神经元时，甜、苦、声音、风仍然 100%，“亮”却比随机还差。这与第 3 节“光感受器的信号到不了下行神经元”一致。
- **第一句话**：刺激“醋、甜、热、亮”，读出分数为醋 0.94、甜 0.87、热 0.58、亮 0.98，其他词都 ≤ 0.13，四个词全部读对。拼成：

> 我闻到醋味。我尝到甜味。很热，很亮。我该怎么做？

**发给 Opus 5**：
- 调用方式：`claude -p <句子> --model claude-opus-5 --output-format json --no-session-persistence --setting-sources user --system-prompt "你是 Claude。" --disallowedTools <全部工具>`。
- 在项目目录之外的新建空目录里运行，用的是本机 Claude Code 的登录，没有另配 API key。
- **踩坑**：第一次在项目内的空文件夹里运行，Claude Code 往上层目录读到了本项目的 `AGENTS.md`（多出约 2.4 万 token 上下文），回复里出现了本项目的【实测】标注和实验结果，不算“原话对话”。这份回复存档为 `claude_reply_contaminated.json`（花费 0.27 美元），不采用。
- 重发后上下文只剩约 9,500 token，回复用时 26 s，Opus 5 花费 0.06 美元（Claude Code 另用 Haiku 4.5 做了一次约 0.001 美元的后台小调用）。Opus 5 的回复原文：

> 听起来你是一只苍蝇（或者果蝇），而且处境可能很危险。
>
> **醋味加甜味，很可能是陷阱。** 人类常用苹果醋、糖和一滴洗洁精做果蝇陷阱。洗洁精会破坏液体表面的张力，落上去就会沉下去，飞不起来。
> - **别落到液面上。** 如果你在一个杯口或瓶口附近，尤其是盖着保鲜膜、上面有小孔的那种，马上掉头飞走。
> - 真正的烂水果也有酸甜味，但闻起来会有发酵的果香，不会只有醋和糖。
>
> **又热又亮，要小心光源。**
> - 如果亮光是紫蓝色的，还伴随嗡嗡声，那可能是灭蚊灯，别靠近。
> - 如果是灯泡，太热会让你脱水，也会烤伤翅膀。
> - 如果是阳光照着的窗户，窗玻璃你是撞不穿的。沿着边缘找缝隙，或者往阴凉处飞。
>
> **建议你这样做：**
> 1. 立刻飞离又热又亮的地方，去阴凉、有空气流动的角落。
> 2. 离醋味最浓的地方远一点。
> 3. 去找熟透的水果或者垃圾桶边缘，那里的吃的比较安全。
> 4. 注意头顶有没有东西挥下来。
>
> ---
>
> 另外，如果你其实是人，而且突然闻到不存在的醋味、嘴里莫名发甜，还觉得发热、怕光，这可能是偏头痛先兆或神经系统方面的问题。请尽快就医。如果同时出现意识模糊、说话困难或一侧身体无力，请立刻拨打急救电话。

- 【推测】这段回复是 Opus 5 按字面把自己当成在给一只果蝇出主意（醋 + 糖可能是捕蝇陷阱、又热又亮可能是灯），并补了一句“如果你其实是人”的就医提醒。回复内容与模型内部的放电无关，也没有回传给果蝇大脑。
- 与新闻对照：新闻说糖让 MN9 放电 78 Hz、加苦味降到 3 Hz。我们在全脑模型里测到左侧糖味 → MN9 66/114 Hz，糖 + 苦 → 18/18 Hz（10.0 节），方向一致，数值不同。新闻的“16 个词 100% 命中、只用下行和运动神经元 85%”我们没法核实；我们自己的词表下分别是 88%（整句全对）和 15%。


## 14. 虚拟敲除筛选：糖 → MN9，哪些神经元不可缺？（2026-09-14 追加）【实测】（`screen/sugar_mn9_screen.py` → `results/screen/`）

复现并扩展 Shiu et al. 2024 Nature 图 1F 的全脑沉默筛选：刺激右侧唇瓣糖味受体神经元（GRN），逐个沉默网络里的神经元，看伸喙运动神经元 MN9 放电掉多少。论文的补充表（CC BY 4.0，存放在 `external/shiu2024_supp/`）里有它自己对 200 个神经元的筛选结果，以及 10 个细胞类型的真实光遗传沉默实验结论，所以这次既能和论文的模型比，也能和真实实验比。

### 14.0 更正：以前写的“× 4 次试验”其实是同一次模拟的 4 份拷贝

- 发现过程：为这次筛选读 Brian2 源码时看到，C++ standalone 模式把 `b2.seed(x)` 编译成 `main.cpp` 里的常数，于是每次 `device.run()` 都从同一个种子开始。回查旧结果，`results/dodge_ref/`（5 个条件）和 `results/v2_ref/`（29 个条件）里每个条件的 4 个（或 2 个）试次脉冲序列逐位相同。小网络上复现：设种子 → 3 次运行完全相同；不设种子 → 各不相同。
- 影响：第 10.0 节表头的“0.5 s × 4 次”、11.1/11.2/11.4 节用到的全脑参考、以及子回路 v1/v2 选参数时的全脑参考，**都只是 1 次模拟（一个输入噪声实现）**，不是 4 次平均。数值本身没算错（4 份相同拷贝的平均等于那 1 次），但没有试次间变异的信息。差别大的结论（失控与否、MN9 0 Hz 对 66 Hz）【推测】不会因重跑而翻转；差别小的（侧化指数 ±0.05、MDN 6/7 Hz、子回路平均偏差 6.4 Hz）不知道噪声有多大。
- 不受影响：单试次的结果（`sugar_brian2` 等）、第 9.2 节视觉管线（它根本没有调用 `b2.seed()`，40 次运行本来就各自独立——缺的只是每个条件的重复，见第 18 节）、第 13 节（一次连续模拟）、腹神经索（JAX/numpy）、Fly-Brain-AI（Brian2 runtime 模式）。
- 修复：`run_experiment.py` 只在单试次时设种子；多试次时由系统随机源播种，试次彼此独立（代价是不能逐位复现）。本节的筛选换了另一种办法：把 R 个独立输入实现一起编译进程序，运行时选用哪一个——既独立又可复现。
- ~~旧的参考实验没有重跑（约 34 个条件，估计 20–30 min）。~~
  **已重跑（第 17 节）**：34 个条件（`results/v2_ref/` 29 个 + `results/dodge_ref/` 5 个）按原参数重跑、试次互相独立，用时 13 min、峰值 4.1 GB；旧结果原样备份在 `*_seedbug/`。大部分结论没变，但有一条正是种子 bug 掩盖的类型被更正了（详见第 17 节）。（本行 2026-09-19 倒查时发现与第 17 节自相矛盾，已更正。）

### 14.1 做法（运行前写定）

- 模型：官方 `create_model`（Shiu 2024 参数，FlyWire v783，138,639 个神经元），Brian2 cpp_standalone，dt 0.1 ms。论文用的是 v630，补充表里那 200 个神经元有 **184 个 ID 在 v783 中没变**，比较只用这些。
- 刺激：`run_experiment.py` 的 sugar 预设 21 个 GRN。**50 Hz 为主**（论文判定“必需”用的频率），100 Hz 为辅。读出：MN9 `720575940660219265`，每个试次从静息开始 1.000 s 内的脉冲数。
- 沉默：让被沉默的神经元不能放电（下游效果与官方 `silence()` 把传出突触置 0 相同，逐位核对见 14.2）。
- 试次：6 个固定输入实现，所有条件都在同样的实现上跑（配对比较）。原计划 8 个，按事先写好的时间预算规则（只看基线活跃数和实测速度）降到 6 个。
- 判定：比值 = Σ MN9(沉默) / Σ MN9(基线) ≤ 0.8 记为“必需”（论文的“下降超过 20%”）。
- 三个候选集合：**P** = 论文 200 个里 v783 还在的 183 个（去掉读出 MN9 自己），50 与 100 Hz 都筛；**E** = 50 Hz 基线里放过电的全部 313 个神经元（论文只筛了按 200 Hz 反应排前 200 的）；**T** = 论文做过真实沉默实验的 10 个类型，**两侧一起沉默**（真实实验用的 split-GAL4 是两侧都标记的）。
- 工程：一条长模拟切成 2,614 段，每段 1.010 s = 1.000 s 试次 + 10 ms 安静期（清空 1.8 ms 突触延迟里的在途脉冲），段首把 v、g 复位到静息；沉默谁、用哪个输入实现由运行时参数决定，所以只编译一次。总用时 87 min，峰值内存 3.3 GB，2,614 段里**没有一段失控**（活跃神经元最多几百个）。

### 14.2 验证（`results/screen/validation.json`）

| 检查 | 结果 |
|---|---|
| V1 同一实现重复跑 | 逐位相同 ✅ |
| V2 沉默一个基线里不放电的神经元 | 与基线逐位相同 ✅（所以这类条件不必模拟，直接等于基线） |
| V3 阻断放电 vs 官方的“传出突触权重置 0”（Roundup_l 的 255 条传出突触） | 3 个条件逐位相同 ✅（MN9 都是 14 / 7 / 53） |
| 补跑时重新编译的程序 | 重跑主运行里的 20 个段，全部逐位相同 ✅ |
| 基线 MN9 对照论文补充表 1A | 50 Hz：我们 17.3 ± 7.9 Hz（6 个实现），论文 19.4 ± 6.5 Hz（30 次）；100 Hz：70.0 ± 6.0 对 65.7 ± 3.3 ✅ |
| 基线活跃神经元 | 50 Hz 136–266 个，100 Hz 350–360 个 |

### 14.3 复现论文自己的筛选（183 个神经元）

| 频率 | 相关（Pearson / Spearman） | 判为“必需”的个数：我们 / 论文 / 都判 | 判定一致率 | Cohen κ | 归一化值中位绝对差 |
|---|---|---|---|---|---|
| 50 Hz | 0.83 / 0.54 | 31 / 19 / 17 | 91.3% | 0.63 | 0.090 |
| 100 Hz | 0.84 / 0.59 | 2 / 2 / 2 | 100% | 1.00 | 0.057 |

- 效应大的神经元两边一致（Pearson 0.83–0.84）；Spearman 偏低是因为大多数神经元比值都在 1 附近，排序主要在比噪声。
- 50 Hz 下 16 个判定不一致，**几乎全是“我们判必需、论文判不必需”**，其中 8 个是被刺激的糖 GRN 自己。按“论文的值离 0.8 超过 2 个标准误”且“我们去掉任一实现判定不变”两个条件筛，只剩 4 个真正矛盾：sugar_l_17（论文 0.99 / 我们 0.69）、sugar_l_9（0.90 / 0.63）、sugar_l_6（0.94 / 0.70）、CB0030（GABA，论文 1.13 / 我们 0.72，方向相反）。
- 这种系统性偏差有一部分来自我们自己的方法，见下一节。

### 14.4 我们方法自带的一个偏差：网络混沌 + 单条基线轨迹【探索性，事后发现】

- 检查发现：在 50 Hz 下，**沉默任何一个神经元（哪怕它整段只放 1–3 个脉冲）都倾向于把 MN9 往中间拉**。例如基线 MN9 = 29 的那个实现，248 个不同沉默条件的 MN9 中位数是 22；基线 = 22 的实现中位数是 18；而基线 = 7 的实现中位数还是 7。
- 原因【推测】：网络本身没有噪声，但对初值敏感。基线只是“没被扰动的那一条轨迹”，是条件分布里的一个样本；任何扰动都会让轨迹改变，结果向条件均值回归。论文用的是 30 次独立试次分别求平均，基线和沉默都是均值，所以没有这个问题；我们的配对设计换来了低方差，却带来了偏差。
- 大小：把“同一实现里所有单个沉默条件的 MN9 中位数”当作零效应参照，它与基线的比值是 **50 Hz 0.894、100 Hz 0.964**。也就是说 50 Hz 下一个完全无关的神经元平均也会显示出约 11% 的“下降”。这解释了为什么 50 Hz 我们判出 31 个而论文只有 19 个，而 100 Hz 两边都是 2 个。
- 事后修正（筛选里常用的板内中位数归一化）：改用这个参照重算，50 Hz 我们判出 **16 个**（论文 19 个），一致率 92.9%，κ 0.59；100 Hz 不变（2 对 2，κ 1.00）。下文凡标“修正后”的都是这个算法。

### 14.5 和真实实验比：10 个做过光遗传沉默的类型

实验结论取自论文补充表 2 的“沉默后伸喙是否受影响”（Fdg 两篇文献结论相反，按论文补充表 10 的算法记为“否”）。比值 ≤ 0.8 记为模型预测“必需”。

| 类型（v783 注释） | 真实实验 | 论文模型 50 Hz | 我们单个 50 Hz | 我们两侧 50 Hz | 修正后单个 / 两侧 |
|---|---|---|---|---|---|
| Clavicle（AN_GNG_30） | 必需 | 0.66 ✅ | 0.55 ✅ | 0.55 ✅ | 0.61 ✅ / 0.61 ✅ |
| G2N-1（CB0616） | 必需 | 0.62 ✅ | 0.44 ✅ | 0.44 ✅ | 0.50 ✅ / 0.50 ✅ |
| Zorro（CB0192） | 必需 | 0.77 ✅ | 0.76 ✅ | 0.76 ✅ | 0.85 ❌ / 0.85 ❌ |
| Rattle（CB0499） | 必需 | 0.86 ❌ | 0.83 ❌ | 0.83 ❌ | 0.93 ❌ / 0.93 ❌ |
| FMIn（CB0366） | 必需 | 1.31 ❌ | 1.33 ❌ | 1.33 ❌ | 1.48 ❌ / 1.48 ❌ |
| Usnea（CB0008，GABA） | 必需 | 1.23 ❌ | 1.37 ❌ | 1.43 ❌ | 1.53 ❌ / 1.60 ❌ |
| Bract（DNge173 + 174，4 个） | 不必需 | 1.09 ✅ | 0.82 ✅ | 0.81 ✅ | 0.91 ✅ / 0.90 ✅ |
| Phantom（CB0062，GABA） | 不必需 | 1.08 ✅ | 0.87 ✅ | 0.87 ✅ | 0.97 ✅ / 0.97 ✅ |
| Fdg（CB0038） | 不必需 | 0.85 ✅ | 0.95 ✅ | 0.89 ✅ | 1.07 ✅ / 1.00 ✅ |
| Roundup（CB0553） | 不必需 | 0.67 ❌ | 0.74 ❌ | **0.28 ❌** | 0.83 ✅ / 0.31 ❌ |
| **对的个数** | — | **6 / 10** | **6 / 10** | **6 / 10** | 6 / 10 ／ 5 / 10 |

- **我们的单个神经元结果和论文几乎一模一样**（判定集合完全相同：Clavicle、G2N-1、Roundup、Zorro），换了连接组版本（v630 → v783）、换了试次方案，结论没变。
- **“两侧一起沉默”基本没有改变结论**：右侧糖刺激下，大多数类型的对侧神经元根本不放电，沉默它等于什么都没做。唯一例外是 Roundup——它的对侧神经元也在放电，两侧一起沉默把 MN9 压到 28%，**反而让预测更错**（实验说 Roundup 不是必需的）。所以“模型比实验更看重 Roundup”不是单边/双边的问题。
- 模型答错的 4 个仍然是论文指出的那 4 个：Rattle、FMIn、Usnea（实验必需、模型说不必需）和 Roundup（反过来）。论文对 Usnea 的解释是它可能靠神经肽起作用，而模型里只有经典递质。
- **口径标注（2026-09-19 补，用户指出页面与报告对不上）**：上表「我们」各列是 **R=6、未归一化**的比值。
  游戏页面那张同名表用的是**零参照归一化**后的值（报告 14.4 节说明了为什么该归一化），两者对 8 个类型判定一致，
  但 **Roundup 与 Zorro 会翻转**：Roundup 0.74（必需）→ 0.83（不必需）、Zorro 0.76（必需）→ 0.85（不必需）。
  因此归一化口径下我们答错的是 Rattle、FMIn、Usnea、**Zorro**，而不是上面这四个。两种口径都得 6/10，**只是答对的是哪 6 个差一个互换**。
  R=12 未归一化再给第三组数（Roundup 0.747 必需、Zorro 0.829 不必需）。
  这两个类型的比值全部落在 0.74–0.85，紧贴 0.8 判据——**引用它们时必须同时说明实现数与归一化方式**。
  四种口径并排：`python3 screen/recheck_calls.py` → `results/screen/recheck_calls.json`。
- 100 Hz 下只剩 Roundup 一个被判必需（10 个里对 3 个）：糖输入一强，MN9 接近饱和，单个神经元的影响被淹没。**论文选 50 Hz 是有道理的**。

### 14.6 穷举 50 Hz 下全部 313 个活跃神经元：论文漏掉了什么吗？

- 这个模型里静息放电率是 0，**沉默一个不放电的神经元对下游没有任何影响**（V2 已逐位验证）。所以“50 Hz 下放过电的 313 个神经元”就是单个敲除的全集，穷举是完备的。论文筛的是按 200 Hz 反应排前 200 的神经元。
- 结果：修正后 19 个判为必需（未修正 34 个），其中 16 个在论文的 200 个名单里。名单外的 3 个：
  - `720575940639259967`（LB3 糖 GRN）：就是论文的 sugar_l_13，只是 v783 换了 ID，不算新的。
  - **CB0277**（`720575940626835146`，放电 25.7 Hz，修正后 0.43）：效应排第 2，比大多数已知的前运动神经元还强。它不在名单里【推测】是因为论文那 200 个 ID 里有 16 个在 v783 变了 ID；其中一个（`720575940612611301`）在论文里 50 Hz 刺激时放电 24.3 Hz、沉默后归一化 0.58，和 CB0277 很像，很可能就是同一个神经元。
  - CB0190（`720575940637144944`，只放 1–4 个脉冲，修正后 0.785）：贴着门槛，是唯一可能真的被漏掉的，但效应小。
- 反方向（沉默后 MN9 升高 ≥ 20%）修正后 21 个，几乎都是 GABA 能神经元，最强的是 DNge031（升到 3.3 倍；它也不在名单里，论文里对应的 `720575940615041430` 值是 2.65，【推测】同一个神经元换了 ID）。
- 结论：**论文“按 200 Hz 反应取前 200 个”的做法，在 50 Hz 下基本没有漏掉重要的神经元**——穷举没有找出被忽略的关键节点。

### 14.7 不跑模拟，光看连线能不能预测？（事先写定的对照）

在 313 个神经元上，把模拟出的效应（1 − 比值）与三个只用连接组算的指标比：

| 指标 | 与模拟效应的 Spearman | 模拟前 20 名里命中几个 |
|---|---|---|
| G1 直接连到 MN9 的带符号突触数 | 0.14 | 5 / 20 |
| G2 基线放电率 × G1 | 0.14 | 4 / 20 |
| G3 基线放电率 × 长度 1–3 的带符号通路权重和 | **0.34** | **9 / 20** |

- 直接连到 MN9 的突触数几乎没有预测力：最强的几个必需神经元（CB0277、G2N-1、Clavicle、多数糖 GRN）**对 MN9 一条直接突触都没有**，全靠多跳通路。
- 加上活跃度和多跳通路好一些（0.34），但离模拟还很远。**想知道敲掉谁会让伸喙失效，光看连线不够，得跑模型。**

### 14.8 这件事有什么用、以及别当真的部分

- 组合敲除（找备份通路）见第 16 节。
- 用处：这是一个可以真正跑起来的“虚拟敲除筛选”——在 87 min 内把 313 个神经元逐个敲掉、每个 6 次重复，给出一份按效应排序、可以拿去做实验的候选名单，并且能说明哪些是模型和实验已经对上的、哪些是模型的已知失败点。真实实验做同样的事需要每个类型一条 split-GAL4 品系。
- 别当真的部分：
  - 模型只有经典递质、没有神经肽和神经调质，静息放电率为 0；Usnea 这种靠神经肽的神经元模型天生答不对。
  - 判定门槛 0.8 是照搬论文的；离门槛近的（Bract 0.82、Rattle 0.83、Zorro 0.76 在未修正下）去掉任一个输入实现判定就会翻转。
  - 14.4 的偏差说明：**用“一条没被扰动的基线轨迹”做配对参照，在这种对初值敏感的网络里会系统性地高估效应**。要严格比较，应该像论文那样用多次独立试次的均值，或者用这里的中位数归一化。
  - 连接组版本不同（v630 vs v783）、输入实现只有 6 个，这两点都会带来差异。

## 15. 解码器压力测试：像脑机接口那样只看到一部分神经元，还读得出吗？（2026-09-14 追加）【实测 · 离线分析】（`language/decoder_stress.py` → `results/language/stress.json`）

用第 13 节“果蝇说中文”的数据（300 个试次 × 121,706 个非感觉神经元的脉冲数，12 个词），**不再跑脑模拟**，只改“能看到什么”，看线性读出从什么时候开始失灵。设计在运行前写进脚本；全部跑完用时 160 s，峰值内存 1.4 GB。

**做法**
- 解码器与第 13 节相同，只是正则强度固定为第 13 节交叉验证选出的值。另在 30、300、3,000 个神经元上重新交叉验证选正则强度，平衡准确率差 ≤ 0.01，固定值没有让小规模条件吃亏。
- 指标：60 个测试试次上 12 个词的平均平衡准确率（0.5 = 瞎猜）。把训练标签随机打乱 20 次，得到 0.50，整句全对 0%，这就是机会水平。
- 每个条件独立抽样 20 次（噪声条件 10 次），表中是中位数。用全部神经元时复现了第 13 节的结果（0.96，整句全对 88%）。

**一、能看到多少个神经元、看的是哪些**（平衡准确率中位数）

| 采样方式 | 10 个 | 100 个 | 1,000 个 | 3,000 个 | 10,000 个 | 全部 |
|---|---|---|---|---|---|---|
| 随机抽（全部非感觉神经元，像随机插电极） | 0.50 | 0.60 | 0.82 | 0.90 | 0.96 | 0.96（121,706 个） |
| 只抽训练时放过电的（像只留有信号的通道） | 0.59 | 0.82 | **0.95** | 0.96 | 0.96 | 0.96（12,609 个） |
| 只看下行 + 运动神经元（像只记录神经输出） | 0.54 | 0.66 | 0.75 | — | — | 0.76（1,409 个） |
| 局部探针：离随机一点最近的 n 个（像一块电极阵列） | 0.50 | 0.52 | 0.54 | 0.55 | 0.69 | 30,000 个时 0.93 |
| 按训练集方差挑前 n 个（不看标签，参考上限） | 0.54 | 0.79 | 0.93 | **0.99** | 0.98 | — |

- 这些试次里 90% 的神经元一次都不放电。**随机插“电极”要 3,000 个才到 0.9；只留有信号的通道，300 个就有 0.896，1,000 个到 0.95**（整句全对 80%）。按事先定的门槛（中位数 ≥ 0.9），所需最少数量分别是 3,000 个和 1,000 个。
- **局部探针最差**：3,000 个相邻神经元（半径约 49 µm）只有 0.55，接近瞎猜；要 30,000 个（半径约 157 µm）才到 0.93。结果也很看落点：10,000 个时四分位范围是 0.55–0.88。【推测】每个词的信息在各自的感觉通路里，一小块区域只看得到其中一两类。
- 只看输出（下行 + 运动神经元）最高只有 0.76，与第 13 节一致。
- 按方差挑 3,000 个比用全部神经元还好（0.99 对 0.96，整句全对 97% 对 88%）：大量几乎不动的神经元只会给读出加噪声。
- 第一句话“醋、甜、热、亮”要四个词全对：随机 1,000 个时 20 次里只有 15% 做到，只留有信号的 1,000 个时 75%，全部神经元时做到。

**二、记录有噪声**

漏检：每个脉冲只以概率 p 被记到（像钙成像漏掉脉冲）。训练和测试都加同样的噪声。

| 看的神经元 | p = 1 | 0.5 | 0.2 | 0.1 | 0.02 |
|---|---|---|---|---|---|
| 全部 121,706 个 | 0.96 | 0.81 | 0.73 | 0.67 | 0.61 |
| 有信号的 1,000 个 | 0.95 | 0.81 | 0.75 | 0.70 | 0.60 |

假脉冲：每个被记录的神经元每秒额外多出 λ 个随机脉冲（像背景噪声、串扰）。

| 看的神经元 | 0 | 1 Hz | 4 Hz | 16 Hz | 64 Hz |
|---|---|---|---|---|---|
| 全部 121,706 个 | 0.96 | **0.65** | 0.58 | 0.54 | 0.54 |
| 有信号的 1,000 个 | 0.94 | **0.91** | 0.88 | 0.79 | 0.70 |

- 漏掉一半脉冲，准确率就掉约 15 个百分点；整句全对从 88% 降到 37%。
- **通道多不一定好**：全部 121,706 个通道每秒各多 1 个假脉冲，准确率就掉到 0.65；只记 1,000 个有信号的通道，同样的噪声下还有 0.91。原本不放电的 11 万个通道全变成了噪声，把信号淹没了。

**三、通道中途坏掉**（有信号的 1,000 个通道，先用干净数据训练）

| 坏掉比例 | 0 | 10% | 25% | 50% | 75% | 90% |
|---|---|---|---|---|---|---|
| 坏通道读数变 0，不重新训练 | 0.94 | **0.62** | 0.58 | 0.51 | 0.50 | 0.50 |
| 只用剩下的通道重新训练 | 0.94 | 0.94 | 0.95 | 0.91 | 0.90 | 0.81 |
| 【探索性】知道哪些坏了、填上训练均值，不重新训练 | 0.95 | 0.93 | 0.89 | 0.79 | 0.53 | 0.50 |

- **坏 10% 的通道、又不重新校准，准确率就从 0.94 掉到 0.62。** 坏通道读数为 0，对原本活跃的神经元来说是个很大的负值，线性读出整个被带偏。
- 重新训练后，坏一半通道仍有 0.91，坏 90%（剩 100 个）还有 0.81。
- 最后一行是看到“读数变 0”崩得这么快之后才加的（独立随机种子，没有改动前面的结果）：只要知道哪些通道坏了、把它们填成平均值，坏 25% 时还有 0.89。

**这说明什么**（【推测】，只针对这个模型和这个任务）
- 与脑机接口的常识一致：**覆盖面比通道数重要；只留有信号的通道比盲目加通道好；通道坏了要么剔除或填补，要么重新校准。**
- 局限：刺激很强（100 Hz 直接驱动感觉神经元），多数试次伴随全脑失控（第 13 节：每个试次中位约 7,970 个非感觉神经元放电）；标签只是“给没给某种刺激”；只有 240 个训练试次；模型里除输入的泊松噪声外没有别的噪声，真实大脑的变异大得多。所以这些数字只说明趋势，不能换算成真实实验需要的电极数。

## 16. 双敲除：有没有“单独敲都没事、一起敲就断”的备份通路（2026-09-14 追加）【实测 · 探索性】（`screen/double_knockout.py` → `results/screen/double_summary.json`）

单个敲除只能回答“少了它行不行”。真实回路常有冗余：两条通路都能把信号送到 MN9，敲掉任一条都看不出问题，两条一起敲才断。这种组合实验在真实果蝇上要同时做两条 split-GAL4，几乎没人做；在模型里只是多跑几段。

**设计**（运行前写定）：与第 14 节同一个编译好的程序、同样 6 个输入实现、50 Hz 糖刺激。
- **A 组（通路冗余）**：50 Hz 下修正后效应最强的 12 个**非感觉**神经元，两两组合 66 对。
- **B 组（输入冗余）**：随机去掉 k 个糖味受体神经元，k ∈ {2, 3, 5, 8, 13, 21}，每个 k 三个随机子集。
- **C 组（零参照）**：20 对“单独敲都没有效果”的神经元对。因为 14.4 节的偏差，双敲除要用自己的零参照；实测双敲除零参照 / 单敲除零参照 = 0.968（6 个实现；12 个实现是 0.957），即“多敲一个神经元”本身几乎不额外拉低 MN9。
- **判据**：效应 E = 1 − 比值；独立预期 E_exp = 1 − (1 − E_a)(1 − E_b)；协同 = E_ab > E_exp + 0.1，亚可加 = E_ab < E_exp − 0.1。
- 605 段仿真，20 min，峰值内存 3.2 GB。

**两轮结果**：先用 6 个输入实现跑了一遍（协同 7、可加 39、亚可加 20；留一稳定 4、21、13），判定一半会翻，所以又把输入实现加到 **12 个**重算（`screen/double_extend.py`，补跑 837 段、27.5 min；核对过前 6 个实现与原来逐位相同）。12 个实现下：**协同 10 对、可加 45 对、亚可加 11 对，留一稳定 7、28、6**——原来那 20 对“亚可加”里有一半是噪声，而协同反而更多、更稳。下表是 12 个实现、留一稳定的协同。

| 一起敲的两个 | 各自单独敲 | 一起敲 | 独立预期效应 | 实测效应 |
|---|---|---|---|---|
| CB0883 + CB0542 | 0.75 / 0.65 | **0.17** | 0.51 | 0.83 |
| CB0883 + AN_GNG_30（Clavicle） | 0.75 / 0.65 | **0.24** | 0.51 | 0.76 |
| CB0883 + CB0177 | 0.75 / 0.71 | **0.30** | 0.47 | 0.70 |
| CB0883 + DNge080 | 0.75 / 0.79 | **0.36** | 0.41 | 0.64 |
| CB0616（G2N-1）+ CB0883 | 0.60 / 0.75 | **0.25** | 0.55 | 0.75 |
| CB0616 + CB0493 | 0.60 / 0.67 | **0.24** | 0.60 | 0.76 |
| CB0616 + CB0177 | 0.60 / 0.71 | **0.26** | 0.58 | 0.74 |

- **CB0883 是最像“备份”的节点**：单独敲只到 0.75（按 0.8 的门槛算不必需，单个筛选根本不会注意它），但 7 对稳定协同里有 **5 对含它**——和 CB0542、Clavicle、CB0177、DNge080、G2N-1 里任何一个一起敲，MN9 都掉到 0.17–0.36。G2N-1（CB0616）是第二个枢纽，占 3 对。这正是单个敲除筛选会漏掉、而真实实验很难做的那一类。
- **反方向也有**：12 个实现下仍有 2 对稳定的“多敲一个反而回升”——CB0277 单独敲 0.45、加上 CB0177 变成 0.64；Roundup（CB0553）单独敲 0.44、加上 CB0177 变成 0.60。（6 个实现时看起来有 4 对，多出来的两对在 12 个实现下没站住。）
  - 连线上的解释【推测，只看结构、没有单独验证】：CB0177 一边兴奋 Roundup（模型里最强的前运动神经元，权重 +99），一边兴奋一串 GABA 神经元（CB0480 两条共 +243、CB0021 +110，还有 DNg38、CB0890、CB0863）；CB0277 则兴奋 DNge051（GABA，对 MN9 −173）。这条通路同时携带兴奋和前馈抑制：单敲时兴奋占上风，双敲把抑制也一起拿掉，MN9 反而回来。CB0480 本身也在 14.6 节“沉默后 MN9 升高”的名单里（1.9–2.2 倍），与这个解释一致。

**输入端几乎没有冗余**（随机去掉 k 个糖味受体神经元，共 21 个，MN9 比值中位数）：

| 去掉几个 | 2 | 3 | 5 | 8 | 13 | 21 |
|---|---|---|---|---|---|---|
| MN9 比值 | 0.69 | 0.31 | 0.14 | 0.06 | 0.00 | 0.00 |

- 去掉 3 个受体神经元（21 个里的 1/7），MN9 就掉掉三分之二。50 Hz 正处在输入–输出曲线最陡的一段（10 Hz 几乎无反应、100 Hz 已接近饱和），所以这里对输入数量极其敏感。这也与 14.3 节的分歧方向一致：论文认为单个糖 GRN 影响不大，我们测到影响很大。

### 16.1 还有没有别的 CB0883？（`screen/double_hub.py` → `results/screen/double_hub_summary.json`）

上面 7 对稳定协同里 5 对含 CB0883、3 对含 G2N-1（CB0616），所以问题变成：这种“单独看不出来、配对才显形”的神经元还有多少？全部两两组合太贵（前 25 个要 300 对），改成**拿这两个枢纽去配效应排名 13–24 的 12 个神经元**（24 个组合 × 12 个实现 = 354 段，12 min）。这一步是上一轮结果提出来的假设，判据（同样的 ±0.1 缓冲、同样的零参照）在跑之前写定。

结果：24 个组合里协同 5 个（留一稳定 4 个）、可加 13 个、亚可加 6 个。

| 候选（单独敲） | 枢纽（单独敲） | 一起敲 | 独立预期效应 | 实测效应 |
|---|---|---|---|---|
| CB0393（0.84） | CB0883（0.75） | **0.43** | 0.37 | 0.57 |
| **CB0192 = Zorro**（0.83） | CB0883（0.75） | **0.43** | 0.38 | 0.57 |
| CB0799（0.82） | CB0616 = G2N-1（0.60） | **0.32** | 0.51 | 0.68 |
| CB0553 = Roundup（0.75） | CB0883（0.75） | **0.44** | 0.44 | 0.56 |

- **确实还有**：排名 13–24 里至少有 3 个（CB0393、Zorro、CB0799）单独敲都算不上必需，配上枢纽就把 MN9 压到 0.32–0.43。单个敲除筛选系统性地看不见这一类。
- **一个可能的线索**【推测，未验证】：Zorro 在真实实验里是“伸喙必需”的，而这里 R=12 的单敲比值是 0.83，判**不必需**。
  （**口径提醒，2026-09-19 修正**：原文写“我们和论文的单个敲除都判它不必需”，这句话是错的。论文自己的值 0.772 判**必需**；14.5 节的表用 R=6 未归一化，Zorro 0.76 也判必需、算答对；零参照归一化后才是 0.85、判不必需。**Zorro 与 Roundup 是 10 个实验类型里仅有的两个判定随口径翻转的**，其余 8 个在 R=6/12 × 归一化与否四种口径下判定完全一致。四种口径都得 6/10，只是答对的是哪 6 个差一个互换。四口径并排见 `screen/recheck_calls.py` → `results/screen/recheck_calls.json`。）这里它与 CB0883 有稳定协同，说明模型里 Zorro 处在一条有备份的通路上——**模型与实验不符的一部分，可能正是冗余造成的**：单独敲有备份顶上，实验里的 GtACR1 沉默却未必只影响这一个细胞类型。这条线索要验证，需要真实实验同时沉默两条通路。
- 反过来也有 6 个亚可加组合（例如 CB4055 + CB0883：各自 0.87 / 0.75，一起只有 0.79），说明它们共用同一个瓶颈。


### 16.2 CB0883 全扫描：把 312 个活跃神经元都和它一起敲一遍（`screen/hub_scan.py` → `results/screen/hub_scan_summary.json`）

既然 CB0883 是枢纽，那就把 50 Hz 下全部 312 个活跃神经元（去掉 CB0883 自己和 MN9）逐个和它配对，画一张完整的“谁和它互为备份”的图。
两阶段（事先写定）：阶段 A 全部候选 × 前 6 个实现（1,740 段，60 min）；阶段 B 把 Δ ≥ 0.05 的 50 个补到 12 个实现（426 段，14 min）。

**结果**：50 个进入阶段 B 的里，协同 32 个、留一稳定 19 个。但这里要分两类看——

- **12 个可以解释为“备份通路”**（它们单独敲本来就让 MN9 下降，只是下降有限；加上 CB0883 就塌了）：

| 和 CB0883 一起敲 | 自身放电 | 单独敲 | 一起敲 | Δ |
|---|---|---|---|---|
| 糖味受体 LB3 #1 | 45.5 Hz | 0.87 | **0.34** | +0.32 |
| CB0542 | 16.2 Hz | 0.65 | **0.17** | +0.31 |
| 糖味受体 LB3 #2 | 53.8 Hz | 0.78 | **0.29** | +0.30 |
| AN_GNG_30 = Clavicle | 29.2 Hz | 0.65 | **0.24** | +0.25 |
| DNge080 | 7.7 Hz | 0.79 | **0.36** | +0.23 |
| CB0177 | 21.8 Hz | 0.71 | **0.30** | +0.23 |
| 糖味受体 LB3 #3 | 53.0 Hz | 0.59 | **0.24** | +0.21 |
| CB0393 | 29.7 Hz | 0.84 | **0.43** | +0.20 |
| CB0616 = G2N-1 | 38.8 Hz | 0.60 | **0.25** | +0.20 |
| CB0192 = Zorro | 66.5 Hz | 0.83 | **0.43** | +0.19 |
| 糖味受体 LB3 #4 | 51.3 Hz | 0.92 | **0.51** | +0.18 |
| CB0553 = Roundup | 7.3 Hz | 0.75 | **0.44** | +0.12 |

  - 其中 4 个单独敲在 0.8 门槛之上（**单个筛选根本看不见**）：两个糖味受体、CB0393、Zorro。
  - **5 个是糖味受体神经元自己**：输入和 CB0883 也互为备份——少几个受体或者少了 CB0883 都还能撑住，两样一起少就不行。
- **另外 7 个不能算备份**（CB0480、Usnea、FMIn、DNg103、CB0762、CB0853、CB0573）：它们单独敲是让 MN9**升高**的（1.03–1.81 倍），乘性独立预期对这种反向效应本来就不适用，判成“协同”只是算法口径的结果。这一条是分析时才意识到的，写在这里避免误读。
- **多数神经元反而是“共用瓶颈”**：312 个候选的 Δ 中位数是 -0.016，有 108 个 ≤ −0.05（亚可加）、只有 50 个 ≥ +0.05。也就是说，绝大部分神经元和 CB0883 走的是同一条通路，真正互为备份的是上面那一小撮。

**局限**：判据带 ±0.1 的缓冲，12 个实现下“可加”这一档仍有 45 对里 17 对留一会翻（协同和亚可加已经稳多了：7/10 与 6/11）。上面的名单是**模型内的预测**，没有任何实验验证；真实验证需要同时做两条 split-GAL4。

## 17. 把受种子 bug 影响的参考实验重跑一遍（2026-09-14 追加）【实测】（`scratch/rerun_refs.py` → `results/v2_ref/rerun_diff.csv`）

14.0 节发现 Brian2 standalone 把随机种子编译进了程序，旧的“× 4 次试次”其实是同一次模拟的 4 份拷贝。这里把受影响的 **34 个条件**（`results/v2_ref/` 29 个、`results/dodge_ref/` 5 个）按原参数重跑，试次之间互相独立；旧结果原样备份在 `results/v2_ref_seedbug/`、`results/dodge_ref_seedbug/`。用时 13 min，峰值内存 4.1 GB。第 10、11 节里受影响的数字已经就地更新。

**大部分结论没变**：糖味 → MN9、JO 左 → aDN1（右侧 39 Hz，右侧刺激仍然 0/0）、LC16 双侧 ≥ 100 Hz 才驱动 MDN、正面 looming 主要驱动巨纤维、嗅觉无侧化、苦味压制进食——都和原来一样。数值上有 26 个读出的旧值偏离新均值 ≥ 2 个试次标准差，多数是几 Hz 的量级（例如糖味左 MN9 由 66/114 变成 72.5/106，LC16 双侧 MDN 由 32/31 变成 30.5/31）。

**但有一条结论必须更正，而且正是种子 bug 掩盖的那一类**：

| 条件 | 旧（1 次实现） | 新（独立试次） |
|---|---|---|
| 气味 DA2 左 50 Hz | 16 个神经元活跃，“完全无反应” | 4 次里 **3 次无反应（16–17 个）、1 次失控（8,071 个）** |
| 糖味双侧 100 Hz | 8,794 个活跃（失控） | 2 次里 **1 次失控（8,805 个）、1 次不失控（566 个）** |

- 全脑失控在阈值附近**是概率性的**：同样的刺激，有的试次什么都不发生，有的试次冲到 8,000 多个神经元。中间状态没有，所以“全或无”的说法仍然成立，但“DA2 在 50 Hz 不反应”这种单次结论不成立。
- 这反过来让 11.1 节的多巴胺结论更硬：**同一个条件的不同试次**里，失控的试次 PAM 放电 123/307，不失控的试次 0/307（DA2 左 50 Hz 同样：3 次 0/307，失控那次 120/307）。以前只能跨条件比较，现在是同条件内的对照。
- 其余 32 个条件在 4 次试次里失控与否完全一致（要么都失控、要么都不失控）。

**顺带修掉的一个 bug**：`dodge/v4_refs_analysis.py` 会遍历 `results/v2_ref/` 下所有目录，而两个“沉默”条件的 `rates.csv` 只有 silenced 列、没有 baseline 列（它们是这个分析跑完之后才生成的，当时没触发）。现在跳过这类目录。

**没有重跑的部分**：第 13 节的语言实验（一次连续模拟）、腹神经索（JAX / numpy，不经过 Brian2 standalone）。

**更正一处我自己先写错的话**：写 14.0 节时我说视觉管线“40 次运行共用同一个噪声实现”。查 `results/vision/.brian2_build/main.cpp` 后确认不是——`vision/connectome_from_flyvis.py` 从来没有调用 `b2.seed()`，所以每次 `device.run` 由系统随机源播种，40 次运行的噪声本来就互相独立。真正的缺口是**每个条件只跑了一次、没有重复**，这一点在第 18 节补上。

## 18. 视觉管线：补上“每个条件只跑一次”的重复（2026-09-14 追加）【实测】（`vision/connectome_from_flyvis.py --repeats 3`、`vision/repeat_check.py` → `results/vision/repeat_check.json`）

**先更正我自己的一句话**：写 14.0 节时我说视觉管线“40 次运行共用同一个噪声实现”。查 `results/vision/.brian2_build/main.cpp` 后确认不是——`vision/connectome_from_flyvis.py` 从来没有调用 `b2.seed()`，所以每次 `device.run` 都由系统随机源播种，40 次运行的泊松噪声本来就互相独立。真正的缺口是**每个刺激 × 朝向只跑了一次**，没法知道那些“8/8、7/8、0/8”里有多少是噪声。

**做法**：同样 5 个刺激 × 8 种格子朝向，每个条件重复 3 次（共 120 次运行，13 min，峰值 3.6 GB）。判据沿用 9.2 节事先声明的指标：刺激开始后 0.5–0.95 s、左侧 LPLC2 的平均发放率。

| 事先声明的比较（每次重复各在 8 种朝向上数一遍） | 三次重复的计数 | 原来的结论 |
|---|---|---|
| 逼近 > 远离 | 8 / 8 / 8 | 8/8，**稳** |
| 逼近 > 远距平移 | 8 / 7 / 8 | 原写 7/8，其实在 7–8 之间抖，方向不变 |
| 逼近 > 近距平移 | 0 / 0 / 1 | 0/8，**稳**（LPLC2 对近距平移反而更强） |

- **变异主要来自映射，不是噪声**：同一条件跨重复的标准差中位数 0.05 Hz，而同一次重复跨 8 种朝向的标准差中位数 0.18 Hz——**格子对齐方式带来的差异是随机噪声的 3–4 倍**。所以这条管线最不确定的仍然是映射本身。
  > **后续修订（2026-09-19，见 28.20 / 28.20.1）**：这句里「没有文献依据、只能全跑」**已不成立**。
  > 用解剖位置（两视叶质心之差定左右轴、全脑质心→GNG 质心定腹侧、叉积定前后轴）加上实测的 T4/T5 偏好方向，
  > 已把朝向**钉到唯一一种**（旋转 φ=277°，即 `u = −p, v = −q`）。
  > 同时查出**原流程有形变**：`normalize()` 的 PCA + 各轴除以标准差，把 Codex 六边形点阵的基矢夹角
  > **从 60.0° 拉成 122.6°**——这 8 种朝向全都建立在一个已经变形的点阵上。
  > 换成保持点阵几何的映射重跑全脑（150 次）后，**下表「逼近 > 近距平移」那一行从 0/8 翻成成立**
  > （解剖锚定 ×0.6，三次重复全部成立，是十种映射里唯一的）。28.20.1 里列清了不能过度解读的地方。
- **绝对量级很小**：LPLC2 后段平均 0.65 Hz（逼近）、1.14（近距平移）、0.39（远距平移）、0.01（远离）、0.00（右侧逼近）。这些比较是在接近 0 的数值之间做的，这一点比“几比几”更值得记住。
- **巨纤维仍然不可解读**：同一条件跨重复的标准差**中位 4.3 Hz（范围 0–13.1）**、极差**中位 8.7 Hz（范围 0–26.1）**（40 个条件 × 左右两侧，从 `connectome_responses_reps.csv` 重算，存于 `results/vision/gf_repeat_variability.json`）；而且远离刺激下 50.8 Hz 比逼近的 46.1 Hz 还高。与 9.2 节“巨纤维在这条管线里读不出意义”的结论一致。（先前写的“标准差 4–6 Hz、极差 8–12 Hz”是把中位数当成了范围，已更正。）

## 19. 同一套方法换一条通路：水味觉（2026-09-15 追加）【实测】（`screen/water_screen.py` → `results/screen/water/`）

糖那条通路上模型对真实实验只对 6/10。水这条通路论文自己报的是 10/11，而且**表 5 的实验全是这篇论文自己做的**，不是引用旧文献。
同一套方法（同样的段落安排、同样的零参照口径、同样的判据）换一条通路，能看出“对得上多少”是通路特定的，还是碰运气。

**设计**（运行前写定）：刺激右侧 18 个唇瓣水味觉受体神经元、160 Hz（论文表 5 判定“必需”用的频率），读出同一个 MN9。
两阶段：阶段 A 全部候选 × 前 6 个实现（990 段，32 min）；阶段 B 把效应 ≥ 10% 的 104 个补到 12 个实现，并做 66 对双敲除（1,654 段，53 min）。
零参照与糖同口径（50 个随机单敲除的每实现中位数 / 20 对对照对的中位数）。

**基线对得上**：12 个实现的 MN9 是 [12, 8, 9, 7, 5, 6, 14, 7, 9, 9, 7, 13]，平均 8.8 Hz，论文补充表 6A 同频率是 10.0 Hz。

**与论文自己的水筛选（补充表 6C，186 个 ID 在 v783 未变）比——比糖那条通路吻合得多**：

| | 糖（50 Hz） | 水（160 Hz） |
|---|---|---|
| 相关（Pearson） | 0.83 | **0.96** |
| 判定一致率 | 91% | **97%** |
| Cohen κ | 0.59 | **0.87** |
| 判为“必需”：我们 / 论文 | 16 / 19 | 19 / 24 |

**对论文自己做的沉默实验**（比值 ≤ 0.8 判为“必需”）：

| 类型 | 真实实验 | 论文模型 | 我们单个 | 我们两侧 |
|---|---|---|---|---|
| Bract | 必需 | 0.55 | 0.69 | 0.69 |
| Clavicle | 必需 | 0.10 | 0.04 | 0.04 |
| G2N-1 | 不必需 | 0.82 | 0.84 | 0.84 |
| Phantom | 不必需 | 2.80 | 2.93 | 2.95 |
| Rattle | 必需 | 0.53 | 0.59 | 0.59 |
| Roundup | 必需 | 0.00 | 0.03 | 0.02 |
| Tophat | 不必需 | 0.94 | 1.17 | 1.18 |
| Tulip | 不必需 | 2.88 | 1.99 | 3.23 |
| Usnea | 必需 | 1.89 | 2.07 | 2.77 |
| Zorro | 必需 | 0.39 | 0.43 | 0.45 |

- **论文 9/10，我们也 9/10**，而且错的是同一个：**Usnea**——实验里水的伸喙需要它，模型里沉默它反而让 MN9 升到 2 倍以上。论文对 Usnea 的解释是它可能靠神经肽起作用（在糖那条通路上它也是错的），模型里只有经典递质。
- 水通路上模型对得准，糖通路上只对 6/10，**说明“连接组模型能不能预测沉默实验”是通路特定的**：水的读出 MN9 基线低（8.8 Hz）、通路更集中（Roundup 单独敲就把 MN9 打到 0.03），糖的通路则分散、冗余更多。
- 两侧一起沉默几乎不改变结论（只有 Tulip 从 1.99 变到 3.23），原因和糖一样：单侧刺激下对侧神经元基本不放电。

**水通路的双敲除**（效应最强的 12 个非感觉神经元，66 对，12 个实现）：协同 15 对、可加 45 对、亚可加 6 对，留一稳定的协同 10 对。

| 一起敲 | 各自单独敲 | 一起敲 | Δ |
|---|---|---|---|
| DNge173 = Bract + CB0051 | 0.69 / 0.49 | **0.01** | +0.33 |
| CB0501 + CB0051 | 0.64 / 0.49 | **0.01** | +0.30 |
| CB0051 + CB0499 = Rattle | 0.49 / 0.59 | **0.01** | +0.28 |
| CB0872 + CB0051 | 0.83 / 0.49 | **0.16** | +0.25 |
| CB0616 = G2N-1 + CB0360 | 0.84 / 0.95 | **0.60** | +0.20 |
| CB0461 + CB0616 = G2N-1 | 0.95 / 0.84 | **0.62** | +0.18 |
| CB0192 = Zorro + CB0051 | 0.43 / 0.49 | **0.04** | +0.17 |
| CB0051 + CB0360 | 0.49 / 0.95 | **0.29** | +0.17 |

- **水通路也有自己的枢纽：CB0051**，10 对稳定协同里有 7 对含它。它单独敲是 0.49（已经算“必需”），但和 Bract、CB0501、Rattle、Zorro 任一个一起敲，MN9 直接归零（0.01–0.04）。
- 第二个枢纽是 **G2N-1**（3 对）——有意思的是它在真实实验里**不是**水伸喙必需的，模型单独敲也判不必需（0.84），但配对时是关键节点。这与糖通路上的 CB0883 是同一种情况：**单个敲除筛选系统性地漏掉这类"配对才显形"的神经元，而且两条通路上都有**。

## 20. 一次数据体检，以及把“静默降级”改掉（2026-09-15 追加）【工程】（`screen/segments.py`、`screen/audit.py` → `results/screen/audit.json`）

这一轮里“分析要用的段没跑到”出了三次：
1. 类型代表 Bract 不在论文 200 名单里，它 100 Hz 的单敲除段没进计划（分析时直接 KeyError，好在报错了）；
2. `hub_scan` 存盘文件名是 `stageA_*.npz`，读取时却按 `chunk_*.npz` 匹配 —— 312 个候选只读到 23 个，**数据其实都在盘上**；
3. 水通路双敲除前 12 名里的 CB0872 效应只有 4%，没进“补到 12 个实现”的名单，66 对里缺了 11 对。

共同的毛病不是“跑漏了”，而是**分析在缺数据时静默降级**（跳过该条件，或回退成基线），所以缺口不会自己暴露；
第 2 次是偶然发现的，第 3 次是因为我顺手数了一下对数。做法上改两点：

- **把“分析需要哪些段”变成可枚举的清单**（`screen/segments.py`）：`needed_keys(基线, 实现数, 条件集合)` 按“某实现里被沉默的神经元全都不放电 ⇒ 结果等于基线、不需要段”的规则展开；`Repo.need()` 回答缺哪些，`Repo.fill()` 只补缺的。
- **缺段不再静默**：`hub_scan`、`water_screen` 的分析改成记录并打印缺失条件（并写进结果 JSON），而不是 `continue`。

**体检结果**（`python screen/audit.py`，纯读盘，不跑仿真）：报告第 14、16、19 节的全部结论共依赖 **13,515 段**，逐项核对后**一个不缺**：

| 数据集 | 需要的段 | 缺口 |
|---|---|---|
| sugar_P_50Hz | 932 | 0 |
| sugar_P_100Hz | 1,095 | 0 |
| sugar_E_50Hz | 1,401 | 0 |
| sugar_T_50Hz | 115 | 0 |
| sugar_T_100Hz | 120 | 0 |
| double6_A+B+C | 676 | 0 |
| double12_all | 1,636 | 0 |
| double_hub | 426 | 0 |
| hub_scan_stageA(6) | 3,267 | 0 |
| hub_scan_stageB(12) | 1,191 | 0 |
| water_P(6) | 805 | 0 |
| water_T+null(12) | 915 | 0 |
| water_double(12) | 936 | 0 |

改完之后重跑了 `hub_scan analyze` 与 `water_screen analyze`，输出与改动前逐字段一致，说明这次改的只是“缺数据时怎么表现”，没有动结果。

## 21. 糖和水用的是同一批神经元吗？（2026-09-15 追加）【实测 · 只做分析，不跑新仿真】（`screen/pathway_compare.py` → `results/screen/pathway_compare.json`）

同一个读出（MN9），两条输入通路，各自的筛选数据都在盘上，于是可以直接问：网络用的是不是同一批神经元？
口径：两边都用各自的零参照修正后的比值、前 6 个实现、同一个 ≤ 0.8 门槛。

**活跃集合只重叠三分之一**：糖 313 个、水 216 个，共同 139 个（Jaccard 0.356），
糖独有 174 个、水独有 77 个。

| | 共同 139 个 | 糖独有 174 个 | 水独有 77 个 |
|---|---|---|---|
| 中枢神经元 | 77 | 109 | 48 |
| 下行神经元 | 44 | 22 | 8 |
| 运动神经元 | 14 | 14 | 3 |
| 感觉神经元 | 2 | 24 | 18 |

共同的那批以中枢和下行神经元为主（下行 44 个、运动 14 个），也就是靠近输出的一段；
各自独有的以中枢神经元和自己的受体神经元为主。

**就算是同一个神经元，"敲掉它要不要紧"也很不一样**（128 个共同活跃神经元上）：

| 指标 | 值 |
|---|---|
| 效应（1 − 比值）的 Spearman | 0.176 |
| 效应的 Pearson | 0.415 |
| “必需”判定一致率 | 88.3% |
| Cohen κ | 0.152 |

判定一致率看着高（88%），但那是因为绝大多数神经元两边都不必需；κ 只有 0.152，说明**一致得并不比随机分配好多少**。
- 只在糖通路必需的：CB0553、DNge059、CB0616、CB0030、CB0277、DNge080、CB0542、CB0177 等；
- 只在水通路必需的：DNge173、CB0501、CB0192、CB0051、CB0499；
- **两条通路都必需的只有两个类型**：Roundup（CB0553）与 Clavicle（AN_GNG_30）——正好是论文在两条通路上都点名的那两个。

**两个"枢纽"是通路私有的**：

| | 在糖通路 | 在水通路 |
|---|---|---|
| CB0883（糖的枢纽） | 活跃，单独敲 0.759 | **根本不放电**（所以沉默它对水的 MN9 是严格的零效应） |
| CB0051（水的枢纽） | 活跃，单独敲 0.974（等于没影响） | 单独敲 0.489 |

- 糖的枢纽在水通路里连电都不放；水的枢纽在糖通路里放电却完全不重要。**“枢纽”不是网络的固有属性，而是被输入选出来的。**
- 【推测】这也解释了第 19 节的观察：模型在水通路上预测得准（9/10）、在糖通路上只有 6/10——两条通路的结构本来就不同，糖的更分散、备份更多，水的更集中（Roundup 单独敲就把 MN9 打到 0.03）。冗余越多，单个敲除越难预测行为。

### 21.1 水通路也做一次全扫描：CB0051 × 全部活跃神经元（`screen/water_hub_scan.py` → `results/screen/water/hub_scan_summary.json`）

和 16.2 节同口径（两阶段 6 → 12 个实现，Δ ≥ 0.05 进阶段 B），把水通路 215 个活跃神经元逐个和 CB0051 配对。

| | 糖：CB0883 × 312 个 | 水：CB0051 × 215 个 |
|---|---|---|
| 枢纽自己单独敲 | 0.75（算不上必需） | **0.49（本来就必需）** |
| 进入阶段 B（Δ ≥ 0.05） | 50 | **142** |
| 协同 / 留一稳定 | 32 / 19 | 65 / 43 |
| 其中可解释为备份 | 12 | 13 |
| 单独敲反而升高（乘性预期不适用） | 7 | 30 |
| 亚可加（共用瓶颈） | **108** | **6** |

**两条通路的组合结构完全不同**：糖通路上大多数神经元和枢纽共用同一个瓶颈（108 个亚可加），真正互为备份的是一小撮；
水通路几乎没有亚可加（6 个），而是**只要把 CB0051 和几乎任何一个还有作用的神经元一起敲，MN9 就塌到 0**。
【推测】原因是水通路本来就工作在阈值附近（基线 MN9 只有 8.8 Hz，Roundup 单独敲就打到 0.03），
任何叠加的削弱都足以让它掉到零；糖通路基线更高、通路更宽，得同时切中特定的两条才行。

水通路里可解释为备份的 13 个：

| 和 CB0051 一起敲 | 单独敲 | 一起敲 | Δ |
|---|---|---|---|
| DNge173 = Bract | 0.69 | **0.01** | +0.33 |
| CB0501 | 0.64 | **0.01** | +0.30 |
| CB0499 = Rattle | 0.59 | **0.01** | +0.28 |
| CB0872 | 0.83 | **0.16** | +0.25 |
| 水味觉受体 #1 | 0.54 | **0.05** | +0.21 |
| 水味觉受体 #2 | 0.60 | **0.11** | +0.18 |
| CB0192 = Zorro | 0.43 | **0.04** | +0.17 |
| CB0360 | 0.95 | **0.29** | +0.17 |
| CB0461 | 0.95 | **0.30** | +0.16 |
| CB0573 | 0.93 | **0.30** | +0.15 |
| 水味觉受体 #3 | 0.63 | **0.16** | +0.14 |
| 水味觉受体 #4 | 0.76 | **0.23** | +0.14 |
| 水味觉受体 #5 | 0.56 | **0.14** | +0.14 |

- **两条通路都出现同一个模式：输入端的受体神经元和枢纽互为备份**——糖通路 12 个备份里有 4 个是糖味觉受体，水通路 13 个里有 5 个是水味觉受体。
- 注意水通路的比值都很小（很多是 0.01–0.30），而基线每试次只有约 9 个脉冲，所以这些数字的分辨率有限，乘性预期在接近 0 处也被拉伸得厉害。
  这一段的结论只适合读作“方向”，不适合读作精确倍数。

## 22. 什么时候可以不跑模拟？（2026-09-15 追加）【实测 · 只做分析】（`screen/structure_vs_function.py` → `results/screen/structure_vs_function.json`）

14.7 节发现：在糖通路上只看连线预测单敲除效应很差。现在有了第二条通路（水，更集中）和两次枢纽全扫描
（共 516 个带标签的配对），可以把问题问得更准：**哪一部分能靠结构算出来，哪一部分必须跑模型？**
两个假设都在看结果之前写定。

**假设 A：通路越集中，连线越能预测单敲除效应 —— 成立**

| 只用连线的指标 | 糖 50 Hz（313 个） | 水 160 Hz（216 个） |
|---|---|---|
| G1 对 MN9 的带符号直接突触数 | 0.143（前 20 名命中 5） | -0.01（命中 2） |
| G2 放电率 × G1 | 0.143（命中 4） | -0.007（命中 2） |
| G3 放电率 × 1–3 跳带符号通路和 | **0.342（命中 9）** | **0.454（命中 13）** |

- 直接突触数在两条通路上都没用（水通路上甚至是 -0.01），因为效应最强的那些神经元对 MN9 一条直接突触都没有。
- 加上活跃度与多跳通路（G3）在水通路上确实更准（0.454 对 0.342，前 20 名命中 13 对 9），与“水通路更集中”的印象一致。
- 但即使是 0.454，也只能当粗筛：用它挑前 20 个，也会漏掉 7 个真正要紧的。

**假设 B：互为备份 = 各走各的路 —— 不成立**

事先定义的“路径重叠度”是两个神经元到 MN9 的路径画像（经过哪些中间神经元、权重多少）的余弦相似度，
事先声明的方向是“重叠度越低、Δ 越大（越像备份）”。实测：

| | 糖 | 水 |
|---|---|---|
| 重叠度与 Δ 的 Spearman | -0.008 | 0.013 |
| 协同组重叠度中位 | 0.0（n = 50） | 0.0001（n = 137） |
| 亚可加组重叠度中位 | 0.0（n = 108） | 0.0（n = 6） |

**完全没有预测力。** 不是指标退化——枢纽自己的路径画像有 **27**（糖）/ **43**（水）个非零中间节点，
312 个配对里 **83** 个（27%）、204 个里 **99** 个（49%）有非零重叠，最大重叠度到 **0.594 / 0.699**。
只看有重叠的那些，相关是 **−0.26**（糖）和 **−0.04**（水）：糖那边方向与事先声明一致（重叠越高越像共用瓶颈）但很弱，
水那边基本没有。所以这个假设在这个模型里**基本被证伪**，只在糖通路有重叠的子集里留下一点痕迹。

> **更正（2026-09-16）**：本段先前写的是「101 个 / 109 个」与「−0.12 和 +0.03」，**在任何结果文件里都查不到**——
> 这几个量当时只在终端打印过、没有存盘。已改为把它们写入 `structure_vs_function.json`（字段 `pairs.degeneracy_check`）后重算。
> 27/43 与 0.59/0.70 两组数字复核无误。

**结论**：单敲除的效应，部分能用“活跃度 × 多跳通路”粗筛出来（越集中的通路越准）；
但**"两个神经元一起敲会不会塌"——也就是单敲除看不见的那部分——完全看不出结构规律，只能跑模型。**
这恰好是这套虚拟敲除最有价值的地方：它算的正是连线本身答不出的那一半。

【推测】为什么结构预测不了配对效应：备份与否取决于**在给定输入下、动力学上谁在实际承载信号**（哪条路真的在放电、抑制有没有被激活），
而不只是“图上有没有另一条路”。这与 14.4 节看到的“网络对扰动很敏感”是同一件事的两面。

### 22.1 换成“动力学指纹”：弱但方向对（`screen/dynamic_fingerprint.py` → `results/screen/dynamic_fingerprint.json`）

22 节里“图上路径重不重叠”完全预测不了冗余。换一个同样**不用跑新仿真**、但用到动力学的量：
段文件里存的是每段**全部神经元**的脉冲数，所以“敲掉 c 之后全脑哪些神经元变了”这张指纹 Δ(c) 已经在盘上。
事先声明：动力学重叠 = cos(Δ(c), Δ(枢纽))，**重叠越高 → Δ 越负（越像共用瓶颈）**；同时报告“指纹大小”作为对照。

| | 糖 × CB0883（280 个） | 水 × CB0051（182 个） |
|---|---|---|
| 动力学重叠 vs 配对 Δ | **-0.206** | **-0.142** |
| 协同组重叠中位 | 0.379 | -0.1959 |
| 亚可加组重叠中位 | 0.4644 | -0.3469 |
| 对照：指纹大小 vs 配对 Δ | -0.191 | 0.474 |
| 控制幅度后的偏相关 | -0.13 | -0.205 |

- **方向与事先声明一致**，而且比静态连线好一个量级（静态：−0.008 / 0.013；动力学：-0.206 / -0.142）。
  两组的分布中位数也分得开一点（糖：协同 0.379 对亚可加 0.4644）。
- **但仍然很弱，而且有一部分不是"重叠"的功劳**：水通路上“敲掉它在全脑造成多大扰动”这个更简单的量预测得更好（0.474）。
  控制幅度后，重叠度的偏相关只剩 -0.13 / -0.205——有信号，但远不足以替代模拟。
- 【推测】所以“会不会互为备份”确实和动力学有关（指纹比图结构好得多），但**要预测它，需要的信息量已经接近直接把这一对敲掉跑一遍**：
  指纹本身就是每个神经元单独敲的全脑仿真结果。换句话说，**省不掉那一次配对仿真**，只能省掉一部分筛选。

### 22.2 把“通路集中度”算出来（`screen/concentration.py` → `results/screen/concentration.json`）

前面反复说糖通路“分散”、水通路“集中”、JON 通路“只有一个瓶颈”，那是印象。这里把它定义清楚再检验
（指标和方向都写在算之前）：效应 e = max(0, 1 − 修正后比值)，前 6 个实现；
基尼系数（0 = 人人一样，1 = 全压在一个神经元上）、n80（贡献 80% 总效应需要几个神经元）。
**事先声明的方向：越集中 → 只看连线越能预测敲除效应。**

| 通路 | 活跃神经元 | 效应 ≥ 0.2 的个数 | 基尼 | n80 | 最大效应 | 连线 G3 预测力 | 模型对真实实验 |
|---|---|---|---|---|---|---|---|
| 糖 50 Hz | 313 | 26 | 0.783 | 62 | 0.69 | **0.316** | 6/10 |
| 水 160 Hz | 216 | 18 | **0.921** | **15** | 1.00 | **0.485** | 9/10 |
| JON 160 Hz（论文名单） | 596 | 5 | **0.922** | 44 | 1.00 | **0.288** | 1/1 可测 |

三行现在**口径完全一致**：都是该通路全部活跃神经元逐个单敲、零参照中位数修正、前 6 个实现
（JON 这一行为此补跑了 1,319 段、45 分钟，见 `results/screen/jon_paper/concentration_full.json`）。

- **事先声明的方向被自己的数据推翻了一半。** 声明的是「越集中 → 只看连线越能预测」。实际：
  - 基尼：**JON 0.922 ≈ 水 0.921 ≫ 糖 0.783**
  - 连线预测力 G3：**水 0.485 > 糖 0.316 > JON 0.288**
  - **JON 是最集中的（并列第一），却是连线最预测不了的**。三条通路上「集中 → 可预测」并不成立。
- 为什么会这样，可以从 n80 看出来：水 15、JON 44、糖 62。**基尼和 n80 度量的不是同一件事**——
  JON 的基尼高，是因为 596 个神经元里绝大多数效应恰好为 0（aBN1 一个就吃掉全部效应）；
  但真正「扛住 80% 效应」仍需要 44 个神经元，因为剩下的效应摊得很平。
  水通路才是真正的「少数几个各扛一部分」（n80 = 15）。
  换成 n80 也救不回来：n80 排序是 水 15 < JON 44 < 糖 62，而 G3 排序是 水 0.485 > 糖 0.316 > JON 0.288——糖和 JON 仍然是反的。
  **两个集中度指标都解释不了连线预测力的排序。** 事先声明的假设在这三条通路上**不成立**，如实记在这里；
  何况 n = 3，本来也撑不起结论——之前写「三条通路的排序完全一致、事先声明的方向都成立」是错的，
  那是建立在 JON 那一行用了已作废运行、且只给 304 个神经元评分的基础上。
- **JON 通路是最极端的一种集中**：596 个活跃神经元里只有 5 个敲掉会让 aDN1 掉 20% 以上，其中 aBN1（SAD093）一敲就归零。
  所以「集中」至少有两种：水通路是**少数几个神经元各扛一部分**，JON 通路是**一个绝对瓶颈 + 一大片几乎无关的神经元**。
- 模型对实验的准确率：糖 6/10、水 9/10、JON 1/1 可测（样本太小，不能与前两者并列比较）。

> **更正（2026-09-16）**：本表此前有两处问题，都已修。
> (1) JON 那一行原先用的是 24 节「全部 1,091 个 JO-」那次运行（活跃 2,076、必需 1、基尼 0.858、n80 45、G3 0.434），
> 该运行已被 24.3 节宣布作废；现已用论文刺激名单把 596 个活跃神经元**全部**重跑。
> (2) 最后一列 JON 那一格长期写作「2/2（aBN1、aBN2）」，但这是 `screen/concentration.py` 里**手写的字符串**，不是算出来的：
> Hampel et al. 2015 验证的 aBN2，其 v630 编号 `720575940611163610` 在 **v783 模型里不存在**，我们根本没测过它；
> 而且论文自己的补充表 7D 里同一个编号（那里叫「Descending BN2_3」，不叫 aBN2，所以按名字检索漏掉了）160 Hz 比值是 **0.844**，
> 按论文自己的 0.8 门槛也判不出必需。诚实的写法是 **1/1 可测**。这条违反了「绝不报告没真跑过的结果」，已在 23 节错误账本登记。

- 口径提醒：这里的效应做了 max(0, ·) 截断（只看“下降”），所以 G3 的数值与 22 节（不截断）略有差别（糖 0.316 对 0.342，水 0.485 对 0.454），排序不变。

## 23. 这一轮的方法学账本（2026-09-15 追加）

第 14–22 节一共提了 8 个**在跑之前写定**的假设或判据。把它们和结果放在一起，比任何单条结论都更说明这套做法值不值：

| # | 事先写定的东西 | 结果 |
|---|---|---|
| 1 | 判定门槛照搬论文（沉默后读出 ≤ 0.8 记为“必需”） | 三条通路一直没改过 |
| 2 | 时间预算规则：按基线活跃数把重复数从 8 降到 6（只看速度，不看结果） | 执行了；后来发现 6 个不够，又加到 12（16 节） |
| 3 | 协同 / 亚可加判据带 ±0.1 缓冲 + 留一检验 | 6 个实现时一半判定会翻；12 个实现后协同 7/10 稳、亚可加 6/11 稳 |
| 4 | “换一条通路看模型准不准”（19 节） | **成立**：水 9/10、糖 6/10，而且错的是同一个 Usnea |
| 5 | 两侧一起沉默会更贴近真实实验（14.5、19 节） | **基本无效**：单侧刺激下对侧神经元几乎不放电；唯一例外 Roundup 反而让预测更差 |
| 6 | 通路越集中，只看连线越能预测单敲除效应（22 节假设 A） | **两条通路上成立、三条通路上被推翻**：水 0.45（前 20 命中 13）对糖 0.34（命中 9）；但补齐 JON 全量后，JON 最集中（基尼 0.922）却连线最预测不了（G3 0.288 < 糖 0.316）。见 22.2 节 |
| 7 | 互为备份 = 到读出的图上路径各走各的（22 节假设 B） | **被自己的数据证伪**：相关 −0.008 / 0.013，且不是指标退化 |
| 8 | 动力学指纹重叠越高 → 越像共用瓶颈（22.1 节） | **方向对但弱**：−0.21 / −0.14；控制扰动幅度后只剩 −0.13 / −0.21 |

**自己犯过、又自己查出来的错**（都写在相应小节里，没有事后掩盖）：

| 错误 | 怎么发现的 | 影响 |
|---|---|---|
| Brian2 standalone 把随机种子编译进程序，“× 4 试次”其实是同一次的 4 份拷贝 | 设计这次筛选时读 Brian2 源码 | 34 个旧参考实验重跑（17 节），更正了“DA2 50 Hz 无反应”这条结论 |
| 分析在缺段时静默降级（3 次） | 1 次报错、1 次偶然、1 次数对数 | 改成显式报缺口 + 全量体检（20 节），13,515 段 0 缺口 |
| 误判视觉管线“共用同一噪声实现” | 查 main.cpp 后自证 | 更正并补了 3 次重复（18 节） |
| 配对设计在混沌网络里有系统性偏差 | 检查“沉默无关神经元”的结果时 | 事后修正口径（14.4 节），糖通路判定从 31 个降到 16 个 |
| 同进程第二次建 Brian2 网络崩溃 | 新工具第一次使用时 | 修在 `Screen` 里，所有脚本受益 |
| **在三通路对照表里把糖通路的 κ 填成 1.00** | 写完 24.3 节“要看 κ”那段之后，回头核对自己引用的数字 | 已发布的页面上错了两版：1.00 是 100 Hz 那一列（MN9 饱和、两边各只判出 2 个必需神经元的退化情况）；第一次改成 0.633 仍然不对，那是**未做零参照归一化**的值，和水 / JON 两列口径不同；同口径的正确值是 **0.59**。**同一节里刚强调“别只看一个数字”，自己连栽两次**，因此 24.3 节补上了 κ 的反例与口径说明 |
| **把“模型对真实实验 2/2”当成结果报了出去，其实从没测过 aBN2** | 系统核对三通路表里每一个手写数字时（就是查 κ 那次的延伸） | aBN2 的 v630 编号在 v783 模型里不存在，测不了；而且论文表 7D 里它的比值是 0.844，按 0.8 门槛也判不出。**这是“报告了没真跑过的结果”，是本项目最不该犯的错。** 已全部改为“1/1 可测”，并查明原因：该神经元在表 7D 里叫 “Descending BN2_3”，我们按 “aBN” 检索名字时漏掉了 |
| **§11.2 的 LC16 表除 MDN 一列外全是第 17 节重跑前的旧值** | 第二轮核对（§9–13）；它和 §10.0 同一条件的数字直接打架却一直没被发现 | 双侧 150 Hz 的 DNa02 实为 47/38.5（表里写 32/44）、双侧 100 Hz 32/15.5（写 30/18）、BDN2 43/39 与 21.5/21.5（写 46 与 28–32）等，已全部按 `v4_analysis.json` 重写。**教训：局部更新一张表时，必须整表重生成，不能只改被关注的那一列** |
| **§9.2 那对 flyvis 侧化数字（10.9 / 1.8）查无出处** | 第二轮核对 | 复算是 5.3 / 0.9 Hz；「平移能量约 2 倍」实为 1.69–1.75 倍。方向性结论成立，具体数值已删 |
| **§12 三处「每副本耗时」的下界都把某个条件的最大值当成了全局最小值** | 第二轮核对 | 实为 0.4–109.9 s、0.4–115.9 s、0.8–318.8 s（原写 1.5–110 / 1.5–116 / 1.9–319）；而且同一个量在 §12.1 和 §12.5 的上界还不一致 |
| **“子回路只重现水通路”这个结论是口径混用造出来的** | 核对 κ 之后顺手检查同一个脚本，发现糖用未归一化值、水用归一化值 | 统一口径并把样本从 6 个补到 10 个后，糖 Pearson 从 **+0.21 升到 +0.75**，水 +0.89。**原结论不成立**，改写为“水那一侧更贴近一些”。同时发现页面上那列“全脑值”混了至少三种口径（Roundup 未归一化、Phantom 1.08 查无来源、CB0883 来自 12 实现双敲除），已写 `dodge/measure_neurons_fullbrain.py` 统一重算 |
| **页面上那 10 个神经元的敲除比值是临时手测的，没有脚本可复现** | 把结果写进报告时想引用口径，发现无从查起 | 写了 `dodge/measure_neurons.js` 全部重测替换（Clavicle 0.78 → 0.91 等），并顺带发现了 25.2 节那个“子回路只重现水通路”的结果 |

**计算账本**（第 14 节以来的全部筛选；2026-09-16 从盘上全部 `*.npz` 逐块重数，见 `results/screen/compute_ledger.json`）：

| 数据集 | 段数 | 仿真机时 | 秒/段 |
|---|---|---|---|
| 枢纽全扫描（16.2 + 21.1 节，CB0883 与 CB0051） | 4,411 | 2.42 h | 1.97 |
| JON 全部 JO-（24 节，已被 24.3 取代） | 3,357 | 1.97 h | 2.11 |
| 糖主筛选（14 节） | 2,638 | 1.46 h | 2.00 |
| 枢纽全扫描（16.2 + 21.1 节，CB0883 与 CB0051） | 4,389 | 2.42 h | 1.98 |
| JON 论文名单（24.2 + 24.3 节，含集中度段） | 3,519 | 1.99 h | 2.04 |
| JON 全部 JO-（24 节，已作废） | 3,345 | 1.96 h | 2.10 |
| 水通路（19 节） | 2,650 | 1.44 h | 1.95 |
| 双敲除（16 节，6/12 实现 + 枢纽配对） | 1,808 | 1.01 h | 2.01 |
| JON 弱刺激（24.1 节） | 450 | 0.29 h | 2.29 |
| **合计** | **18,799 段** | **10.56 h**（共 5.22 h 果蝇脑内时间） | 2.02 |

> **更正（2026-09-16）**：先前这张表把 JON 那两行写成「1,432 段 / 0.83 h」和「1,750 段 / 0.35 h」，合计 14,743 段 / 7.52 h，
> 都偏低——前者漏了 stageB、后者只算了 fullpairs 那 13 分钟，而且 0.35 h 对应 0.72 秒/段，与其余各行的 ~2.0 秒/段自相矛盾，
> 账本自身就不自洽却没被发现。现在改成从盘上逐块重数，并加一列「秒/段」作为自洽性检查。
>
> **再一次更正（2026-09-19）**：上一版记 17,628 段 / 9.88 h，**又漏了 1,171 段**——主要是 §24.3 之后补跑的 JON 集中度段（`conc_*.npz`，1,307 段），账本写完之后才产生。
> 根因是这张表原本由**报告正文里的一段临时 shell 循环**生成，随时会过期而没人发现。
> 现在改由 `screen/compute_ledger.py` 产出（只读，约 1 分钟），并且**按 key 去重**（重跑造成 64 行重复，只计一次）。秒/段自洽列这次是 2.02，各行 1.95–2.29。

峰值内存始终在 2.9–4.2 GB，没有超过 16 GB 机器的安全线；全部结果 1.3 GB，可断点续跑。

## 24. 第三条通路：触角机械感觉 → 梳理指令 aDN1（2026-09-15 追加）【实测】（`screen/jon_screen.py` → `results/screen/jon/`）

> **⚠️ 本节的数值已被 24.3 节取代**：这里用的刺激名单（全部 1,091 个 JO- 神经元）比论文宽得多。
> 用反推出来的论文名单（146 个）重做后，基线 **24.2 Hz**（12 个实现全用是 23.4；论文 23.3）、κ 从 0.281 升到 0.907、判出 5/6 个必需神经元。（κ 与下面的相关系数都是 **R=6** 口径，基线也要用同口径的 24.2 才是一句话里不混 R。）
> 本节保留作为过程记录；**结论性数字请看 24.3**。唯一不变的结论是“JON → aDN1 是单瓶颈通路、零协同”。

前面所有方法学结论都来自味觉 → MN9。换一条**不同模态、不同读出**的通路：刺激全部 Johnston 器神经元（听觉/机械感觉），
读出梳理指令神经元 aDN1。论文补充表 7D 给了同一条通路上 299 个神经元的沉默筛选，可以直接对照；
真实实验对照来自 Hampel et al. 2015（aBN1、aBN2 是梳理必需的，论文表 10 记为 2/2）。**注意**：我们只能测 aBN1——aBN2 的 v630 编号在 v783 模型里不存在（详见 22.2 节下方的更正）。

**一处偏差要先说明**：论文 notebook 里的 `neu_JON_all` 列表没能提取出来（只找到 JON_CE / JON_F / JON_D_m 三个子集），
所以我们按注释表取了 cell_type 以 "JO-" 开头的**全部 1,091 个**神经元，160 Hz。结果是我们的刺激更强：
aDN1 基线 32.3 Hz，论文同频率 23.3 Hz。归一化后的比较仍然有效，但这点会影响判定门槛附近的结论（见下）。

**与论文补充表 7D 比**（280 个 ID 在 v783 未变）：

| 指标 | 值 | 对比糖 / 水 |
|---|---|---|
| Pearson | **0.915** | 糖 0.83、水 0.96 |
| Spearman | 0.435 | 糖 0.54、水 0.55 |
| 判定一致率 | 98.2% | 糖 91%、水 97% |
| Cohen κ | 0.281 | 糖 0.59、水 0.87 |
| 判为“必需”：我们 / 论文 | **1 / 6** | — |

- **效应大小对得很好（Pearson 0.915），但判定数差很多**（我们 1 个、论文 6 个）。
  5 处不一致全部是同方向的边缘情况：论文 0.68–0.74、我们 0.83–0.90（JO_EVL_1、JO_FDP_5、JO_EDM_7、JO_EDM_14、aDN2）。
  【推测】原因就是上面那处偏差——我们的刺激更强，把 aDN1 推离了阈值，单个神经元的影响被压缩。
  这与 14.5 节看到的现象一致：糖通路在 100 Hz（接近饱和）时也只剩一个神经元被判必需。
- **我们唯一判为必需的是 aBN1（SAD093）：敲掉它 aDN1 完全归零（0.00），论文同样是 0.00。**
  这正是 Hampel et al. 2015 实验里梳理必需的那个神经元。

**这条通路几乎没有可分解的结构**：

| | 糖 50 Hz | 水 160 Hz | JON 160 Hz |
|---|---|---|---|
| 活跃神经元 | 313 | 216 | **2,076** |
| 效应 ≥ 20% 的个数 | 26 | 18 | **1** |
| 双敲除 66 对：协同 / 可加 / 亚可加 | 10 / 45 / 11 | 15 / 45 / 6 | **0 / 66 / 0** |

- 66 对双敲除**没有一对是协同或亚可加**：aBN1 一个人决定一切，其余 11 个（比值 0.96–0.99）加不加都没区别，
  所以每一对都恰好落在“独立相乘”的预期上。
- 三条通路因此构成一个梯度：**糖 = 分散且有备份网络 → 水 = 少数几个各扛一部分、互相之间大量协同 → JON = 单一瓶颈、无冗余可言**。
  连线预测力（22.2 节的 G3）和模型对实验的准确率，都沿着这个梯度变化。

### 24.1 验证“差异来自刺激强度”：把刺激调弱再跑一遍（`screen/jon_weak.py` → `results/screen/jon_weak/`）

24 节的推测是：我们只判 1 个必需、论文判 6 个，是因为我们的 JON 刺激更强、把 aDN1 推离了阈值。
这个推测可以直接验证，而且**两种结果都有信息**：翻过来说明是刺激强度；翻不过来说明另有原因。

事先写定：先只看基线扫 4 个频率，选 aDN1 最接近论文 23.3 Hz 的那个（不看任何敲除结果），
再在该频率下重跑论文表 7D 里效应最强的 30 个（一定覆盖论文判必需的 6 个）+ 50 个随机零参照，6 个实现。
**事先声明的预测：论文判必需的 6 个里，我们应当判出明显多于 1 个。**

- 频率扫描：80 Hz → 1.3 Hz、100 Hz → 6.9 Hz、120 Hz → 17.2 Hz、140 Hz → 25.2 Hz（论文 23.3 Hz）→ 按规则选定 **f\* = 140 Hz**（基线 25.2 Hz）。

| | 我们 160 Hz（24 节） | 我们 140 Hz | 论文 |
|---|---|---|---|
| aDN1 基线 | 32.3 Hz | **25.2 Hz** | 23.3 Hz |
| 论文效应最强的 30 个里判为“必需” | 1 | **3** | 6 |
| 效应大小的相关（Pearson） | 0.915 | **0.981** | — |
| 判定一致率 | 98.2%（全部 280 个） | 90%（这 30 个） | — |

| 神经元 | 论文名称 | 论文 | 我们（140 Hz） |
|---|---|---|---|
| SAD093 | aBN1 | 0.00 | 0.00 |
| DNge078 | aDN2_l | 0.71 | 0.75 |
| JO-FD2 | JO_FDP_5 | 0.68 | 0.77 |
| JO-EV1 | JO_EVL_1 | 0.72 | 0.81 |
| JO-FD2 | JO_FDP_6 | 0.81 | 0.84 |
| JO-ED2_b | JO_EDM_7 | 0.74 | 0.85 |
| JO-FD2 | JO_FDP_1 | 0.87 | 0.86 |
| JO-CM | JO_EDM_14 | 0.74 | 0.89 |

**推测部分成立**：刺激调弱后判定数从 1 个升到 3 个（都与论文重合），效应大小的吻合度也从 0.915 提到 **0.981**——
这是这三条通路里与论文吻合得最好的一次。但论文的 6 个里仍有 3 个我们判不出来（JO_EVL_1 0.81 对 0.72、JO_EDM_7 0.85 对 0.74、JO_EDM_14 0.89 对 0.74），
而且我们的比值**系统性地略高**（效应略小）。

【推测】剩下的差距来自刺激**集合**而不是强度：我们刺激了全部 1,091 个 JO 神经元，论文的 `neu_JON_all` 显然是个更小的集合，
输入端神经元越多、彼此越能互相顶替，单个下游神经元就越不关键（这与 16 节“输入端受体神经元和枢纽互为备份”是同一回事）。
光调频率补不回集合差异。要彻底对齐，需要论文那份具体名单。

### 24.2 把论文的刺激名单反推出来，差异基本闭合（`screen/jon_paper.py` → `results/screen/jon_paper/`）

24.1 节留下的判断是：剩余差异来自**刺激集合**而不是强度。论文 notebook 里 `neu_JON_all` 这个变量提取不到，
但名单其实可以从已发表的数据里反推——**被刺激的神经元，放电率会精确跟随刺激频率**
（补充表 7A 的 20 Hz 列 ≈ 20、100 ≈ 100、200 ≈ 200，因为泊松输入直驱且这些神经元不应期设为 0）。

- 按这个特征筛，得到 **146 个**，其中 145 个注释 cell_type 以 JO 开头（另 1 个无注释），145 个在 v783 模型里。
- **独立核对**：notebook 里 JON_CE(70) + JON_F(60) + JON_D_m(16) 的并集**恰好是同一批 146 个**，两条路径完全一致。
  所以论文的 `neu_JON_all` 就是这三个子集的并集，名单存在 `results/screen/jon_all_paper.json`。

用这份名单、160 Hz 重跑（活跃神经元从 2,076 降到 596）：

| | 全部 1,091 个 JO（24 节） | 调弱到 140 Hz（24.1 节） | **论文名单 146 个 · 160 Hz** | 论文 |
|---|---|---|---|---|
| aDN1 基线（R=12） | 32.3 Hz | 25.2 Hz | **23.4 Hz** | 23.3 Hz |
| 论文效应最强 30 个里判“必需” | 1 | 3 | **5**（全部与论文重合） | 6 |
| 效应相关（Pearson） | 0.915 | 0.981 | **0.986** | — |
| 判定一致率 | — | 90% | **96.7%** | — |

| 神经元 | 论文名称 | 论文 | 我们（论文名单） |
|---|---|---|---|
| SAD093 | aBN1 | 0.00 | 0.00 |
| JO-FD2 | JO_FDP_5 | 0.68 | 0.68 |
| JO-ED2_b | JO_EDM_7 | 0.74 | 0.73 |
| JO-EV1 | JO_EVL_1 | 0.72 | 0.74 |
| DNge078 | aDN2_l | 0.71 | 0.74 |
| JO-CM | JO_EDM_14 | 0.74 | 0.82 |

- **推测两部分都成立**：刺激强度补回一部分（1 → 3），刺激集合补回其余（3 → 5）。
  只剩 JO_EDM_14 一个仍在门槛外（论文 0.74、我们 0.82），差距已经落到连接组版本（v630 vs v783）与试次噪声的量级。
- 方法学上的副产品：**论文没有公开的输入名单，可以从它自己发表的放电率表里认出来**——被直接驱动的神经元在各个刺激频率上都精确跟随。
  这条对复现别人的连接组模拟很实用。

### 24.3 用论文名单把整条通路重做一遍，取代 24 节的数字（`screen/jon_paper.py full` / `full_analyze` → `results/screen/jon_paper/full_summary.json`）

24.2 节只重跑了“论文效应最强的 30 个”。既然确认了刺激名单是差异的主因，24 节里那一整套数字（280 个神经元的对照、66 对双敲除）
就都是用**过宽的刺激**算出来的，必须用论文名单重做。这次跑了 1,758 段（`full` 1,362 段 45.8 min + `fullpairs` 396 段 13.3 min，合计约 59 min，峰值 3.3 GB），
口径与糖 / 水通路、与 24 节逐项一致，**唯一的差别就是刺激名单**（146 个论文 JON vs 1,091 个全部 JO-）。

| 与论文补充表 7D 对照（280 个神经元） | 24 节（全部 1,091 个 JO-） | **24.3（论文名单 146 个）** |
|---|---|---|
| aDN1 基线 | 32.3 Hz | **24.2 Hz**（论文 23.3；这是本节所用的 6 个实现，12 个实现是 23.4） |
| 活跃神经元 | 2,076 | **596** |
| Pearson | 0.915 | **0.945** |
| Spearman | 0.435 | **0.501** |
| 我们判“必需”/论文判“必需” | 1 / 6 | **5 / 6** |
| 判定一致率 | 98.2% | **99.6%** |
| **κ（去掉“都判不必需”的运气成分）** | **0.281** | **0.907** |
| 比值中位绝对差 | 0.02 | 0.024 |

**κ 从 0.281 跳到 0.907** 是这一节最该看的数字：一致率两边都在 98% 以上，只是因为 280 个里 274 个双方都判“不必需”；
去掉这份运气之后，24 节的模型其实**几乎没有复现论文的判定**（κ 0.28 属于“勉强一致”），而换成论文名单后变成“高度一致”。
这也说明：**一致率这个指标在极度不平衡的判定问题上是骗人的**，前面几节凡是报了一致率的地方都应该同时看 κ。
实际的值是（三条通路都用**零参照归一化**后的口径，才可比）：
**糖 50 Hz κ = 0.59**、**水 160 Hz κ = 0.87**、**JON 160 Hz κ = 0.91**。
糖那一列未归一化时是 0.633，14.4 节的混沌偏差修正把它压到 0.59——引用时必须说清是哪一个。

但 κ 也有它自己的陷阱，而且就在我们自己的数据里：**糖通路 100 Hz 的 κ = 1.00**，看着完美，
其实是因为 100 Hz 下 MN9 饱和、两边各自只判出 2 个必需神经元——**正例只有 2 个时 κ 同样不可靠**。
所以糖通路真正有信息量的是 50 Hz 那一列。结论是：一致率、κ 都要连同**正例个数**一起看，任何单个数字都能骗人。

- **单个瓶颈的结论不变，而且更干净**：66 对双敲除里**协同 0 对**，可加 65、亚可加 1（24 节：协同 0、可加 66）。
  Δ 最大的一对只有 +0.07（DNge078 + CB2558），远在 +0.1 的判定门槛之下。
  对比糖通路（CB0883 这样的枢纽、Clavicle+G2N-1 的真协同）和水通路，**JON → aDN1 就是一条单瓶颈通路**：
  切掉 aBN1（SAD093）梳理指令直接归零（比值 0.00），其余任何神经元、任何配对都撼动不了。
- **集中度**（口径同 22.2 节）：基尼 **0.878**、n80 = **34**、最大效应 1.0、必需 5 个。
  注意这里只给 304 个活跃神经元评了分（论文表 7D 的 280 个 + 50 个零参照），不是全部 596 个，
  所以这组数字**不能直接放进 22.2 节的三通路排序表**；要可比需要再跑约 1,750 段（约 1 小时）。
- **24 节的哪些说法要改**：24 节写的“我们只判出 1 个必需、论文判 6 个”“κ 0.281”“基线 32.3 Hz”**全部作废**，
  以本节为准。24 节写的“JON 是单瓶颈通路、零协同”**保持成立**，而且在正确刺激下更干净。
  24 节的方法本身没错，错在刺激名单——这正是 24.1 / 24.2 两节事先声明要检验的那个推测。

---

## 25. 把研究结果搬回游戏里：真实神经元开关、物理世界、水与口渴（2026-09-16 追加）【实测 + 工程】（`dodge/game_core.js`、`dodge/brain.js`、`dodge/fly_dodge.template.html`）

14–24 节做了 18,799 段全脑仿真（见 23 节账本），但游戏页上一版只体现了其中一小部分。这一节把三件事搬进去，并把**搬进去之后发现的不一致**如实记下来。

### 25.1 落地姿态修好了（用户报的 bug）

反馈是“每次都是屁股插入到地面里面去了，这样看起来就非常假”。实测确认（`python dodge/landing_pose_check.py` → `results/flight/landing_pose_check.json`）：
按降落结束时游戏给的终态（`clipPose` 在 landU = 1 时把 z 置 0）+ 轨迹末帧姿态，把 85 个 mesh 的 16,661 个顶点摆好再放大 2 倍，

| 飞行片段 | 末帧俯仰 | 末帧翻滚 | 机体最低点 | 插入地面 |
|---|---|---|---|---|
| `evasion_044` | **抬头 42.0°** | +14.5° | −4.53 mm | **4.53 mm** |
| `evasion_067` | −0.0° | +1.7° | −2.56 mm | **2.56 mm** |

（先前正文写的是「俯仰 −43°、4.74 mm / 2.25 mm」，是当时在 node 里临时量的、没有存盘；现在改成可复现的脚本，
数值基本吻合，俯仰的符号约定相反——这里正号表示抬头。即使 `evasion_067` 姿态近乎水平也会插进去 2.56 mm，
说明问题不只出在抬头姿态上，机体本身就需要抬起来。）
原因是手写的 50 ms 线性降落只移动了高度，没有动姿态——真实逃逸飞行结束时果蝇本来就是抬头姿态，直接落下去自然会插进地里。
修法两步（都在 `clipPose` / `poseFlyer`）：降落进度 `landU` 上用四元数球面插值把姿态转回水平，同时按**当前姿态下机体包围盒的最低点**抬升，保证脚先着地。

### 25.2 敲真实神经元的开关：搬进去才发现模型对不上

页面上多了一排开关，敲的是 14–24 节筛出来的**真实神经元**（Roundup、Clavicle、G2N-1、CB0883、CB0051、aBN1 等 10 个），
切断传出突触的语义与全脑筛选完全一致。但**子回路只有 4,599 个神经元（全脑的 3%），敲除效果与全脑筛选并不一致**——这一点必须写在页面上，也写在这里：

| 神经元 | 全脑（糖） | 子回路（糖） | 子回路（水） | 怎么回事 |
|---|---|---|---|---|
| Roundup (CB0553) | 0.74 | **0.05** | **0.11** | 裁剪后它成了两条通路共用的出口，比全脑更关键 |
| CB0883 | 0.75（配对才塌的枢纽） | **1.07** | 1.00 | 枢纽效应**完全消失**：它依赖的旁路不在子回路里 |
| Clavicle (AN_GNG_30) | 0.61 | 0.91 | **0.01** | 对糖几乎没影响，对水直接归零 |
| CB0051 | 0.97 | 0.80 | **0.02** | 同上；全脑糖通路里它毫无作用（0.97） |
| G2N-1 (CB0616) | 0.50 | **0.67** | 1.07 | 反过来：只管糖，完全不管水 |
| Phantom (CB0062) | 1.08（抑制性） | 0.97 | **2.06** | 敲掉这个 GABA 神经元，水通路的 MN9 翻倍 |
| aBN1 (SAD093) | 梳理 0.00 | 1.00 | 1.00 | 梳理 aDN1 **59.8 → 0 Hz**，与全脑、与 Hampel 2015 三方一致 |

口径可复现：`node dodge/measure_neurons.js`（颗粒钉在头部前方 1.3 mm 持续接触 → 味觉神经元 200 Hz，3 个种子，2.5 s 取后 1.25 s 平均）
→ `results/dodge/neuron_ratios.json`。**这一版之前页面上标的比值是临时手测的、没有脚本可复现，现已全部重测替换。**

- **Clavicle + G2N-1 在子回路里是真协同**：各自 0.91 / 0.67，一起 0.50（独立预期 0.61）。
- **子回路更像哪条通路？【探索性 · 事后分析 · n = 10】**（`dodge/subcircuit_vs_fullbrain_knockouts.py`）：
  10 个神经元、两侧同一口径（全脑用 `dodge/measure_neurons_fullbrain.py` 重算，一起敲 + 零参照归一化 + 6 个实现）。

  | 神经元 | 全脑糖 | 游戏糖 | 全脑水 | 游戏水 |
  |---|---|---|---|---|
  | Roundup | 0.30 | 0.05 | 0.00 | 0.11 |
  | G2N-1 | 0.47 | 0.67 | 0.96 | 1.07 |
  | Clavicle | 0.58 | 0.91 | 0.02 | 0.01 |
  | CB0277 | 0.41 | 0.74 | 0.98 | 1.08 |
  | CB0051 | 0.97 | 0.80 | 0.49 | 0.02 |
  | Zorro | 0.81 | 1.03 | 0.47 | 0.92 |
  | Phantom | 0.92 | 0.97 | 3.02 | 2.06 |
  | Rattle | 0.88 | 1.13 | 0.64 | 0.98 |
  | CB0883 | 0.76 | 1.07 | 1.00 | 1.00 |
  | aBN1 | 1.00 | 1.00 | 1.00 | 1.00 |
  | **Pearson / Spearman** | — | **+0.75 / +0.58** | — | **+0.89 / +0.84** |
  | **中位绝对差** | — | **0.24** | — | **0.11** |

  **水那一侧确实更像，但差距没有第一版说的那么大。** 剔除 Phantom 这个唯一的极端值（3.02）后是糖 +0.74 / 水 +0.85，排序不变。
  Phantom 仍是最漂亮的一行：敲掉这个抑制性神经元，**全脑水通路 MN9 变 3.02 倍、子回路 2.06 倍**，方向和量级都对上了。

  > **更正（2026-09-16）**：本节第一版报的是"糖 +0.21、水 +0.92"，那是错的，原因有二：
  > (1) **口径混用**——糖用了未做零参照归一化的值，水用了归一化的；
  > (2) 只取了论文里有命名的 6 个类型，漏掉 CB0277 / CB0051 / CB0883 / aBN1。
  > 统一口径并补全 10 个后，糖从 +0.21 升到 +0.75。**"子回路只重现水通路、完全重现不了糖通路"这个说法不成立**，
  > 正确的说法是"水那一侧更像一些"。这是本轮第三次自查出的引用错误，已在 23 节错误账本登记。

- 结论（按更正后的数据）：**子回路整体上重现了全脑的敲除模式（糖 +0.75、水 +0.89），水那一侧更贴近**。
  单个神经元上仍有裁剪造成的明显失真，最典型的是 **CB0883**：全脑里它是"单独敲 0.76、配对才塌到 0.24"的枢纽，
  子回路里完全没作用（1.07），配对也只是可加——它依赖的旁路在 wmin ≥ 3、K ≤ 3 的裁剪里被切掉了。
  **"裁剪保住集中通路、毁掉分散通路"这个解释，在 n = 10 的数据上只剩很弱的支持**（Spearman 0.84 对 0.58），不宜当成结论。
  页面上每个开关同时标了糖 / 水两个子回路实测比值，悬停能看到全脑的对应值。

### 25.3 物理世界：阳光、风、重力

用户问“能不能给虚拟世界加物理特性”。加了三样，**各自属于哪一类都标清楚**：

- **风**【连接组 · 半】：游戏的 JO 输入组正是 JO-C/E 亚型，即风觉 / 重力觉神经元（Yorozu et al. 2009），也正是 13 节“果蝇说中文”里“风”那个词对应的那群。
  所以“起风 → 这群神经元放电 → 下游读出”是连接组算的；**风速→频率的换算、触角迎风几何、风把果蝇吹偏的力**全是手写的（没有该模型下的定标数据）。
  风用随机游走（时间常数 6 s）演化，有风向标显示，画面上有随风飘的尘粒。
- **阳光**【手写】：只调节视觉前端增益（暗 → 对比度低 → 逼近检测弱，最低到 35%）与画面明暗。
  **没有假装是连接组算的**——第 3 节实测过：直接刺激光感受器（R1-6/R7/R8）在这个 LIF 模型里驱动不了任何下行神经元。
- **重力**：飞行段本来就在 MuJoCo 物理里跑（flybody 训练好的控制器），重力是真的；地面行走段没有独立的重力模拟。

### 25.4 水滴与口渴：同一个动作，背后两套线路

这是 19 / 21 节结果最直观的体现：**水通路和糖通路用的是两批不同的神经元，只重叠约三分之一**，但读出是同一个 MN9、同一个伸喙动作。

- 水滴刺激的是**真实的水味觉受体**：19 节用的 18 个右侧唇瓣水感 GRN 里，**17 个在游戏子回路中**。
  它们的注释 cell_type 也是 LB3（本来就混在糖味觉组里），所以之前游戏把它们当糖用了；现在单独取出来。
- **实测差别**（颗粒放在头下、3 个种子、取后 1.25 s 平均）：

| | 糖粒（刺激全部 122 个 LB3） | 水滴（只刺激那 17 个） |
|---|---|---|
| MN9 | **82.9 Hz** | **14.1 Hz** |
| 不渴时（阈值 30 Hz）进食时间占比 | 100% | 1% |
| 口渴 0.9 时（阈值 3.6 Hz） | — | 99% |

- **口渴是手写的**，理由写在页面上：口渴度每秒 +0.06、喝水时 −0.5，阈值 = 30 Hz ×（1 − 口渴度，下限 0.12）。
  论文做水味觉实验用的是**脱水果蝇**，这条规则是照着那个做法补的；但这个 LIF 模型**没有内部状态**，所以“渴”完全是外挂上去的。
- 副产品一个真实的 bug：一开始我在 JS 里用**数字字面量**写 FlyWire root ID，而这些 ID（约 7.2×10¹⁷）**超过了 JavaScript 的 2^53 整数精度**，
  查表全部落空，我据此错误地下了“水味觉神经元不在子回路里”的结论。回到 Python 核对才发现 17 个都在。
  **教训：JS 里的 FlyWire ID 必须始终是字符串。**

### 25.5 “果蝇在想什么”气泡

13 节解码出的第一句中文是离线算的，游戏里看不到。现在画面上有气泡，实时显示：

- **触发每个词的量都是真实的**：甜 / 苦 / 水 / 风 / 痒是当前注入那些感觉神经元的频率，吃 / 梳理 / 后退 / 飞是**读出神经元的平滑发放率**。
- **词的阈值与中文句子模板是手写的**。与 13 节的差别：那里是 121,706 个神经元 + 岭回归解码 12 个词，
  这里子回路只有 4,599 个神经元、也没有醋 / 霉味 / 温湿度那些通路，所以只能用游戏里真实存在的这几路输入，且用阈值而非回归。

### 25.6 还有哪些研究结果没进游戏

如实列一下（用户问过“还有哪些没体现”）：

| 结果 | 进游戏了吗 | 为什么 |
|---|---|---|
| 14–24 节虚拟敲除筛选 | ✅ 10 个神经元开关 + 全部表格 | — |
| 19 节水通路 | ✅ 水滴 + 口渴 | — |
| 13 节说中文 | ⚠️ 简化版气泡 | 子回路没有那 12 个词需要的全部通路 |
| 12 节全腹神经索（6 条腿、本体感觉闭环） | ❌ 只有表格 | JAX 模型跑不进浏览器；游戏的腿是录制步态循环 |
| 11 节 Pugliese 腹神经索 + 多巴胺 | ❌ 只有表格 | 同上；且模型里根本没有奖赏信号（PAM 不放电） |
| 嗅觉导航 | ⚠️ 手写“闻着找” | 全脑模型给不出转向信号（11.4 节实测） |

**2026-09-18/19 更新**——这张表的后几行已经过期，补记如下：

| 结果 | 进游戏了吗 | 说明 |
|---|---|---|
| 整套 flyvis 视觉系统（28 节） | ✅ **实时跑在浏览器里** | 上一版写“离线比实时慢 75 倍”。关键发现是 flyvis 是**六边形卷积网络**，45,669 个节点只由 2,355 个抽头决定 → 80 KB JSON、3.4 ms/步。页面上「让果蝇看你的图」用的就是它 |
| 复眼第一人称视窗（28.8–28.15 节） | ✅ 右上角实时，**23 fps** | 原为 3 fps，改用 WebGL2 PBO 异步读回后提速（28.15 节） |
| 视觉回路从像素闭上（28.19 节） | ✅ **可切换对照**「只靠眼睛躲」，默认关 | 实测是**负结果**：45 mm 外完全瞎、走路自造 126 Hz 假逼近。作为演示比写在报告里有力，但不能当默认前端 |
| 论文的打乱接线与参数稳健性对照（30 节） | ✅ **滑块 + 按钮** | 打乱接线后糖 → MN9 掉到 0.043；权重/抑制滑块、谷氨酸开关对应论文表 11B–F |
| 视觉管线（flyvis → **全脑** LIF） | ❌ 仍只有表格和曲线 | 这一条没变：全脑 LIF 跑不进浏览器。游戏里跑的是 4,599 个神经元的子回路 |


---

## 26. 补上一个长期空白：视觉前端修复的验证（2026-09-16）【实测 · 事先写定判据】（`connectome_vision_loop.py --frontend-only`）

第 4 节与 AGENTS.md 里挂着一条一年没动的空白：`connectome_vision_loop.py` 的视觉前端在 0.15 s 冒烟测试里暴露了假阳性
（果蝇自己的腿在下半视野随步态晃动 → “暗面积增长率”误报），**代码改了但从没跑过验证，行为结论一直是空的**。
这一节先把判据写死，再跑。

**旧版前端在冒烟测试里的实际表现**（`results/connectome_loop_smoke/log.csv`，10 个窗口，含全脑）：

| t (s) | 暗面积 左/右 | LC4 左/右 (Hz) | 巨纤维 (Hz) |
|---|---|---|---|
| 0.000–0.030 | 0.010 / 0.007 | 0 / 0 | 0 |
| **0.045** | 0.011 / 0.010 | **200 / 200** | **133** |
| 0.060 | 0.012 / 0.012 | 200 / 200 | 100 |
| 0.075–0.105 | 0.012 / 0.012 | 0 / 0 | 67 → 0 |
| 0.120 | 0.012 / 0.014 | 0 / 200 | 67 |
| 0.135 | 0.014 / 0.014 | 200 / 0 | 67 |

暗面积只涨了 0.1 个百分点，LC4 就直接打满 200 Hz，而且来回闪烁、左右乱跳——球那时还在远处。

**事先写定的判据**（写在运行之前；用 `--frontend-only`，不加载大脑，所以这里只检验前端，不涉及行为）：

- **C1 假阳性**：球还远的阶段（前 0.3 s），LC4 两侧的**最大值应 < 20 Hz**。旧版在 0.045 s 就到 200 Hz。
- **C2 不饱和、不闪烁**：整段里 LC4 打满 200 Hz 的窗口占比应 **< 20%**，且不出现“打满 → 归零 → 又打满”的相邻翻转 ≥ 3 次。旧版 10 个窗口里 4 个饱和、翻转 3 次。
- **C3 真信号还在**：球真正逼近的最后 0.2 s，LC4 均值应**高于**前 0.3 s 的均值。若 C1 达标但 C3 不达标，说明修过头了——把真 looming 也滤掉了，要照实写。
- **C4 暗面积稳定**：球还远的阶段，暗面积的窗口间标准差应低于同阶段的均值的 10%（旧版腿部抖动让它持续爬升）。

**任何一条不达标都照实记录，不调参数去凑。** 前端的参数（天空阈值、地平线 margin、低通时间常数、死区）在跑之前保持代码里现有的值不动。
判定由 `vision/frontend_check.py` **机械执行**，阈值写在脚本顶部，不靠肉眼看曲线。

先用旧版数据验证这个判定脚本本身（若判据写松了，旧版就会"通过"）：**旧版 0/3 条通过**
（C1 最大 200 Hz、C2 饱和 40% 且翻转 3 次、C4 变异系数 19.9%）。
C3 对旧版**不适用**——那次冒烟测试只有 0.135 s，比 C1 的 0.3 s 窗口还短，远近两段会重叠，
所以新版至少要跑满 0.5 s，四条才都能判；实际打算跑 1.0 s。

**结果**（`--frontend-only --duration 1.0`，66 个窗口，峰值 831 MB，身体 6 s；
`results/connectome_loop_frontend_looming/`，判定见同目录 `frontend_check.json`）：

| 判据 | 结果 | 实测 |
|---|---|---|
| **C1 假阳性** | **通过** | 前 0.3 s LC4 最大值 **0.0 Hz**（旧版 200 Hz） |
| **C2 不饱和** | **不通过** | 打满占比 **23%**（门槛 20%）、翻转 **6 次**（门槛 3） |
| **C3 真信号还在** | **通过** | 最后 0.2 s 均值 **21.4 Hz** vs 前 0.3 s **0.0 Hz** |
| **C4 暗面积稳定** | **无法计算** | 前 0.3 s 暗面积**恒为 0**，原式 0/0 无定义；标准差 = 0.000000 |

- **腿的假阳性彻底消失了。** 旧版前端的暗面积基线是 0.010（果蝇自己的腿），随步态抖动到 0.014，LC4 在 0.045 s 就打满。
  新版把上半视野掩膜校准出左 244 / 右 291 个“天空”小眼，**前 0.495 s 暗面积精确为 0**，LC4 全程 0 Hz。C1 与 C4 的意图都达到了。
  C4 按原式算不出来（0/0），**不算作“通过”**：原式是标准差 ÷ 均值，而这里均值恰好是 0；原始标准差为 0，意图以最强形式满足，但指标本身无定义。
- **但这次验证也揪出一个原先没发现的缺陷：LC4 的增益完全没标定。**
  球第一次被看见时暗面积只有 **0.4%**，LC4 就已经打满 200 Hz；之后暗面积一路涨到 99%，LC4 始终是 200 Hz。
  **整段过程里 LC4 只有“0 或 200”两个值，没有任何分级响应**，而且中间还熄灭过（0.495 → 0.570 之间断了，共 6 次翻转）。
  这正是 C2 不通过的原因。`lc4_gain` 这个手写参数当初是拍脑袋定的，从没按真实场景标定过。
- **结论**：前端修好了它当初要修的那个问题（腿造成的假阳性），**但没修好“分级响应”**。
  在标定 `lc4_gain` 之前，这条管线的 LC4 只能当二值开关用，不能当作角速度的编码。
  > **已解决（同日，第 27 节）**：标定后 `gain = 19.8`，LC4 取到 15 个不同值、与 expansion 的 Spearman = 1.000，饱和率 23%→2%、开关翻转 6 次→1 次。这一节列出的缺陷不再成立。
  **不调参数去凑**：本节按事先声明只跑一次、如实记录 2/3 通过。要改增益应当另立一节、重新声明判据再跑。
- 另外，本次场景里球只从左侧接近，**右眼全程暗面积为 0**，所以左右对比没有被检验到。

> 这条空白挂了近一年（第 4 节写着“已改代码但尚未运行验证”“行为结论目前为空”）。现在至少前端部分有了可核对的结论。
> 仍未验证的是**加载大脑之后的行为**——那需要完整闭环跑，按 AGENTS.md 的估算约 2–3 分钟每模拟秒，且渲染任务必须前台跑。

> **数据溯源（2026-09-19 倒查补记）**：本节这次运行的原始产物**已被第 27 节的标定运行覆盖**——
> `results/connectome_loop_frontend_looming/` 里现在只有 `gain = 19.8` 那一版（`frontend_check.json` 的标签就是「标定后 gain=19.8」）。
> 这与本项目此前记过的「参数变体运行覆盖正典结果文件」是同一类问题，当时的对策是「非默认参数写带后缀的文件名」，
> 而 `connectome_vision_loop.py` 没有这道保护。
>
> **好在本节的数字仍然可以反算**，因为第 27.0 节把 `exp_L`/`exp_R` 加进了日志，而 `--frontend-only` 下 LC4 不参与驱动身体
> （日志里 `drive_L = drive_R = 1.0`），所以 expansion 轨迹与 gain 无关。用 `LC4 = clip(gain × expansion, 0, 200)`
> 以 `gain = 4000` 重算这份日志，**本节表格的三个数字逐一复现**：饱和占比 **23%**、开关翻转 **6 次**、
> LC4 只取 **2 个不同值**、前 0.3 s 最大 **0.0 Hz**、暗面积首次非零于 **t = 0.495 s**；
> 末 0.2 s 均值 **42.9 Hz（单眼取大）÷ 2 = 21.4 Hz（两眼平均，右眼全程为 0）**——与表里的 21.4 一致，
> 也顺带确认了这一栏用的是**两眼平均**口径。同法以 `gain = 19.8` 重算得饱和 **2%**、LC4 取 **16 个不同值**（含 0；第 27 节报的 15 个不含 0）。

---

## 27. 标定 `lc4_gain`：把 LC4 从二值开关变成分级编码（2026-09-16）【实测 · 事先写定判据 · 一次通过】（`connectome_vision_loop.py`）

26 节的验证揪出一个此前没发现的缺陷：**`lc4_gain` 从来没有标定过**。
球第一次被看见时暗面积只有 0.4%，LC4 就打满 200 Hz；之后暗面积一路涨到 99%，LC4 始终 200 Hz。
**整段过程里 LC4 只有 0 和 200 两个值**，所以这条管线的 LC4 目前只能当二值开关，不能当角速度编码。
26 节按事先声明没有调参，把问题留到这里单独处理。

### 27.0 先修一个工具缺陷

原来的日志**只记 LC4，不记 expansion**。而 `LC4 = clip(gain × expansion, 0, 200)`——一旦饱和，
从 LC4 反推不出 expansion，也就无从标定 gain。已在 `connectome_vision_loop.py` 里把
`exp_L` / `exp_R` 加进日志。**这本身是个教训：被截断的量必须在截断之前记录。**

### 27.1 事先写定的标定规则（写在跑之前）

`lc4_gain` 现值 **4000 Hz/(暗面积比/秒)**，是当初拍脑袋定的，没有任何依据。候选规则两条，**先声明用哪条**：

- **规则 A（量程标定）**：`gain = 200 Hz ÷ p95(expansion)`，其中 p95 取本场景中 expansion > 0 的窗口的 95 分位数。
  含义：让 LC4 在这条轨迹上刚好用满量程，只在最后逼近的极端时刻才接近饱和。
- **规则 B（跨管线一致）**：把暗面积换算成角尺寸（暗面积 ∝ 角直径²，故 θ ∝ √f），再套用游戏里
  Ache et al. 2019 的 0.5 Hz/(°/s)。好处是两条管线口径一致，代价是引入一个视场立体角常数。

**采用规则 A**。理由：规则 B 的换算依赖"物体在视野里近似圆形"和视场立体角两个额外假设，
在这个场景（球从侧面接近、掩膜只保留上半视野）都不成立；规则 A 只依赖已测量的量，且判据可证伪。
**规则 B 记在这里，作为将来两条管线要对齐时的备选，不在本节使用。**

### 27.2 判据（沿用 26 节，不改门槛）

标定后重跑一次，用**完全相同**的 `vision/frontend_check.py` 与同一组阈值判定：

| | 26 节（gain = 4000） | 标定后应达到 |
|---|---|---|
| C1 假阳性：前 0.3 s LC4 最大值 < 20 Hz | ✅ 0.0 Hz | **仍须通过** |
| C2 不饱和：打满占比 < 20% 且翻转 < 3 | ❌ 23% / 6 次 | **这是本节要修的** |
| C3 真信号还在：末段均值 > 远处均值 | ✅ 21.4 vs 0.0 Hz | **仍须通过** |
| C4 暗面积稳定 | 无法计算（0/0） | 预计仍无法计算 |

**额外一条事先声明的判据（本节新增）**：
- **C5 分级响应**：LC4 在非零窗口上取到的**不同数值个数 ≥ 5**，且与 expansion 的 Spearman 相关 ≥ 0.9。
  26 节只有 2 个值（0 和 200），Spearman 无法定义。这条直接检验"是不是还是个开关"。

**只跑一次，不反复试 gain。** 若 C2 或 C5 仍不通过，如实记录并说明下一步该查什么，
**不得把标定规则换成另一条再跑**——那就变成了挑结果。

### 27.3 结果：一次通过

先用现有增益跑一次，只为取 expansion 的分布（这次日志里有 `exp_L/R` 了）：

| | 值（暗面积比 / 秒） |
|---|---|
| expansion > 0 的窗口 | 15 / 66 |
| 范围 | 0.091 – 10.33 |
| 中位数 / p90 / **p95** | 1.92 / 8.46 / **10.11** |

按规则 A：`gain = 200 ÷ 10.11 = `**`19.8`**。

> **原值 4000 是标定值的 202 倍。** 这解释了 26 节看到的一切——expansion 只要超过 0.05，
> LC4 就打满了，而实际 expansion 的中位数是 1.92。手写参数错了两个数量级，而且一直没人发现，
> 因为在饱和之后它看上去"工作正常"（球来了 LC4 就响）。

用 `gain = 19.8` 重跑一次，同一套判据、同一个脚本、同一组门槛：

| 判据 | gain = 4000（26 节） | **gain = 19.8（本节）** |
|---|---|---|
| C1 假阳性 | ✅ 0.0 Hz | ✅ **0.0 Hz** |
| C2 不饱和 | ❌ 23% / 6 次 | ✅ **2% / 1 次** |
| C3 真信号还在 | ✅ 21.4 vs 0.0 Hz | ✅ **16.2 vs 0.0 Hz** |
| C4 暗面积稳定 | 无法计算（0/0） | 无法计算（0/0） |
| **C5 分级响应** | ❌ 只有 2 个取值（0 / 200） | ✅ **15 个非零窗口取到 15 个不同值，与 expansion 的 Spearman = 1.000** |

**LC4 不再是二值开关。** 它现在从 1.8 Hz 平滑升到接近 200 Hz，与 expansion 严格单调对应
（Spearman 恰为 1.000 是因为在未饱和区间 LC4 就是 expansion 的线性函数——这条只验证了"没被截断"，
不是独立证据）。C3 的均值从 21.4 降到 16.2 Hz 是预期内的：不再有一堆 200 Hz 把均值拉高。

- **这一节真正的收获不是那个数字，是那个工具缺陷**：原来的日志只记被 `clip` 截断之后的 LC4，
  不记截断之前的 expansion。于是"增益错了 200 倍"这件事在数据里**根本不可见**——
  你只会看到 LC4 一直是 200，以为前端很灵敏。**凡是会被截断 / 饱和 / 归一化的量，必须在处理之前也记一份。**
- **仍未验证的**：加载大脑之后的闭环行为。标定只解决了"LC4 的数值合不合理"，
  没有回答"这个 LC4 驱动全脑之后，果蝇会不会真的躲开"。那需要完整闭环跑，按 AGENTS.md
  的估算约 2–3 分钟每模拟秒，且渲染任务必须前台跑。
- **规则 B 仍然没用上**，留作将来要把这条管线和游戏的视觉前端对齐时的备选。

## 28. 让果蝇画出你上传的图：整套视觉系统搬进浏览器（2026-09-18）【实测 + 工程】（`vision/flyvis.js`、`vision/retina.js`、`vision/decoder.js`、`dodge/eye.js`）

游戏页新增一块：**上传一张图，果蝇用它真实的视觉系统看一遍，再画出来**。
链路上没有示意图，每一段都可追溯：

```
你的图 → 450×512 相机画面
      → FlyGym 真实复眼采样表 ommatidia_id_map（含鱼眼畸变 zoom 2.72 / distortion 3.8）→ 721 个小眼
      → flyvis 预训练连接组视觉网络（65 类细胞 × 721 柱）→ 各层活动
      → 六边形卷积解码器 → 重建
```

### 28.1 关键发现：flyvis 是六边形卷积网络，能整个塞进浏览器

原以为要在服务端跑，或者做线性近似。实测不用：

| | |
|---|---|
| 节点 | 45,669 = 65 类 × 每类若干柱 |
| 边 | 1,513,231 条，但只有 **604 种（源类型→目标类型）组合** |
| 每核抽头 | 中位 **2**，总计 **2,355** |
| 浏览器资产 | `flyvis_net.json` **80.6 KB**（gzip 约 25 KB） |
| 速度 | **4.6 ms / 积分步**，72 步扫视共 330 ms |

**"是卷积"这个前提是验证过的，不是假设**：`vision/export_flyvis_js.py` 逐边核对
"同一 (源类型,目标类型,du,dv) 的权重在所有柱上是否一致"，不一致就退出不导出。
bias 和时间常数按类型共享也同样检验。

动力学原样照搬（flyvis `PPNeuronIGRSynapses`，欧拉积分）：

```
v ← v + dt/max(τ,dt) · ( −v + bias + Σ w·ReLU(v_源) + x )      w = sign × syn_count × syn_strength
```

两个必须查清不能猜的约定，都逐条验证过：
- **`du,dv = 目标 − 源`** → 源柱 = (u−du, v−dv)，151 万条边全部核对
- 721 个亮度**同时**送进 R1–R8 八种感受器，柱顺序按 (u,v) lexsort，与 flyvis 内部 `input_index` 一致
- 显示朝向：**相机 x ↔ 六边形 y、相机 y ↔ 六边形 x**（相关系数 1.000，精确转置）；
  不换轴用户会看到自己的图被转了 90°

### 28.2 为什么果蝇必须"扫视"

**T4/T5 是运动检测器，盯着不动的图几乎不响应**——只贴一张静止图，8 个运动类型全是零，
视觉系统有一大半是死的。真果蝇也靠扫视和飞行中的视网膜滑动看世界。
所以让它动不是为了好看，是让视觉系统真正工作起来的**必要条件**。

第一版把图放大到 1.9 倍再大幅扫视，结果果蝇离图太近、721 个小眼只看到几块色块，
重建的 r 反而"好看"（0.67–0.97）——因为那一帧画面本来就平坦、好预测。
典型的指标漂亮但东西是错的。改成整图铺满视野（pad 1.14）、扫视幅度 16 像素（约 3–4 个小眼）后才对。

### 28.3 解码器：六边形卷积，**在没见过的整张图上**测

形式 `R̂(u,v) = b + Σ_类型 Σ_偏移 w[类型,du,dv]·act(u+du,v+dv)`。
用卷积不用全连接有两个理由：前向本身就是卷积，逆向也该平移不变；
全连接要 721×721×层数（每层 2 MB），卷积只要几百个参数。

24 张程序化生成的图（几何块 / 条纹 / 多尺度噪声 / 渐变斜边 / 细线），
**留出整张图做测试**（不是留几帧——同一张图的不同帧太相似，那样的分数是假的）：

| 层 | 参数 | 测试 r（6 张没见过的图） |
|---|---|---|
| 视网膜 R1–R8 | 57 | **0.953** |
| 大单极 L1–L5 | 95 | 0.669 |
| 髓质 Mi/Tm | 133 | 0.809 |
| 运动 T4/T5 | 152 | **0.597** |

只在单张图上训练时这组数是 0.974 / 0.907 / 0.935 / 0.735 —— **那是过拟合**，
已作废。越往下游画面丢得越多：到 T4/T5 只剩大形状，细条纹没了。

### 28.4 界面同时给两种画法，差距本身就是内容

- **神经活动直显**：神经元里确实有的东西，零假设
- **解码重建**：好看得多，但解码器会补出活动里其实没有的细节（它学的是训练图像的统计规律）

这正是 §15 解码器压力测试警告的陷阱，所以页面上两者并排、明确标注。
直显用"扣掉中位数"上色——神经活动有很大直流分量（Mi1 之类整片都是正的），
按 ±max 直接上色会糊成一片。

### 28.5 测试：四层，每层都能独立挂掉

`node --check` 通过不代表页面能跑（这个项目吃过亏，见 CI 注释）。现在 CI 跑：

```bash
node dodge/smoke_test.js        # 不依赖 DOM 的渲染路径，用真实数据执行
node vision/flyvis_parity.js    # JS 前向 vs Python：14 类型 × 12 帧，最大相对差 1.5e-6
node vision/retina_parity.js    # 复眼采样 vs Python：最大绝对差 5e-13
node vision/eye_e2e.js          # 整条链路 + 超分辨；反投影没提升就报错（防止页面上乱吹）
node dodge/browser_test.js      # 真 Chrome 里点一遍，7 个画布必须都画出东西
```

浏览器测试的判据是**像素方差**：全黑或纯色算失败。`CI=1` 时缺 Chrome 直接报错，
不静默跳过——"跳过"是这个项目最不想要的失败模式。

复眼采样表（`retina_map.png` 15 KB / `retina_map.bin` 450 KB）必须在 `.gitignore` 里放行，
否则别人 clone 下来既构建不了页面、parity 也跑不了（和 §25 那次 CI 首跑失败同一个坑）。

### 28.6 高分辨率：朴素平均没用，反投影才有用（2026-09-18 追加）

用户问「果蝇的眼睛不可能这么低画质」。先摆事实：**果蝇单眼就是 721 个小眼**，
角分辨率约 4.5°；人眼约 1.2 亿感光细胞、中央凹 0.008°，差五个数量级。
马赛克不是模拟得糙，就是果蝇眼里的世界。

但果蝇确实靠「动」突破静态采样极限（微扫视超敏锐度）。实测下来这件事有个陷阱：

| 做法 | 与原图逐像素相关（513×584 全分辨率） |
|---|---|
| 单帧 721 个小眼 | 0.851 |
| 96 帧扫视 **朴素平均** | **0.849（提升 −0.2%，毫无用处）** |
| 96 帧扫视 **反投影精修 8 轮** | **0.920** |
| 参考：原图用 σ=8.2 px 高斯模糊 | 0.883 ← 单次接受角决定的天花板 |

**朴素平均不提分辨率**：每次测量本身就是小眼 footprint 的平均，再用一个宽核摊开叠加，
只是把更多张模糊图平均起来。要提分辨率必须解反问题——找一张高分辨图 X，
使得「用小眼去测 X」能复现全部 69,216 次测量（Landweber 反投影迭代）。
精修后 0.920 **超过了 0.883**，证明它真的从多帧里解出了单帧不含的信息。

反投影只用实测值和已知几何，**不引入训练数据的统计**——这点和右边四栏的解码器有本质区别：
解码器会补出神经活动里没有的细节，反投影只是把已经测到的信息解开。

#### 路上修掉的两个错

1. **扫视幅度正好等于小眼间距**（都是 16 像素）→ 每次落在同一相位，永远采同一批点。
   改成大扫视 22 px + 两个非公度频率的细漂移，落点才铺满一个小眼内部。
2. **累积画布按相机尺寸 450×512 开，但投点用的是大图坐标**（ox+cx，范围到 513×584）
   → 越界的点全被丢掉且整体错位，相关从 0.85 掉到 **0.40**。
   这个错很隐蔽：画面看着"变平滑了"，指标却在说谎。
   是拿「把原图用 σ=8.2 模糊后应该得到 0.883」这个**理论天花板**去对照，才发现 0.40 不合理。
   **没有天花板做参照，这个 bug 会一直留在里面**。

### 28.7 颜色：果蝇有色觉，但这条链路上是模型丢了它（2026-09-18 追加）

用户问「为什么是黑白？果蝇没有色彩吗？」。分两半回答，两半都要说清楚。

**果蝇有色觉，而且比人多一维**：

| 感光细胞 | 视蛋白 | 峰值 |
|---|---|---|
| R1–R6 | Rh1 | 宽带，主管运动/亮度 |
| R7 pale / yellow | Rh3 / Rh4 | **紫外** ~345 / ~375 nm |
| R8 pale / yellow | Rh5 / Rh6 | 蓝 ~437 / 绿 ~508 nm |

小眼分 pale / yellow 两型。本项目实测 **216 : 505 ≈ 30% : 70%**，与真果蝇一致。

**黑白有三个原因，只有第一个是我的错**：

1. **我先把上传的图转成了灰度** —— FlyGym 其实带颜色，看它的采样源码：
   ```python
   ch_idx = pale_type_mask[k]                      # 1=pale, 0=yellow
   vals[k, ch_idx] += img_flat[i, ch_idx + 1]      # 通道 1=绿, 2=蓝
   ```
   pale 小眼读蓝、yellow 读绿，像拜耳滤镜。转灰度把这个分型丢在了采样之前。
   **已修**：`retina.js` 增加 `sampleGB()`，按 FlyGym 原样分通道；第二栏按分型上色。
   「色块」预设可直接看到：**红色那块在果蝇眼里几乎是黑的**（绿蓝两路都没有红）。

2. **flyvis 每个小眼只吃一个标量**（`n_input_elements=721`，用光流任务训练）。
   R7/R8 节点存在，但拿到同一个值。**颜色在进网络那一步必然被压成一维**，
   所以后面几栏是黑白——这是模型的限制，不是果蝇的。改不了，除非换一个带颜色的视觉模型。

3. **紫外无法从照片恢复**。sRGB 里根本没有紫外，而那是果蝇最重要的通道之一。
   任何「果蝇眼中的颜色」渲染，紫外那部分只能是编的，所以这里不做。

### 28.8 果蝇第一人称复眼视窗（2026-09-18 追加）（`dodge/eyecam.js`）

游戏舞台右上角新增一个实时小窗：**从果蝇眼睛的位置把 3D 世界再渲一遍**，
走同一张真实采样表成像，直接显示彩色复眼马赛克。

```
three.js 场景 → 眼位摄像机（左右眼各偏前方 50°）→ 450×512 离屏渲染
→ FlyGym 的 ommatidia_id_map → 721 个小眼 → pale 取蓝 / yellow 取绿 → 马赛克
```

为了实时**跳过 flyvis 和解码器**（那两步是给静态图做深度分析的），只到
「视网膜接收到什么」为止。每秒刷 3 次——`readRenderTargetPixels` 会打断
GPU 流水线，每帧做会拖垮帧率。

三个实现上必须处理、否则画面就是错的：

1. **WebGL 读回是自下而上的**，而采样表是按正常图像（自上而下）建的。
   不翻转的话果蝇看到的世界上下颠倒。
2. **游戏的天空是 CSS 渐变，不在 3D 场景里**。离屏渲染时那块是透明的，
   果蝇会「看到」一片纯黑。用舞台的 `--stage-top` 当清屏色补上。
3. **果蝇自己的网格要藏起来**。摄像机在身体前方 0.9 单位，不藏的话
   它自己的头会糊满半个视野（实测右眼那条亮竖纹就是自己的身体）。

诚实标注（页面上也写了）：小眼排布、采样表、pale/yellow 分型（216:505）
是真实的；**视野角度和镜头畸变是近似的**——FlyGym 的鱼眼参数没有照搬，
这里用 130° 透视投影，而真果蝇单眼视野接近 180°，透视投影根本到不了。

### 28.9 复眼视窗按规范重做 + 总审计（2026-09-18 追加）（`dodge/eyecam.js`、`dodge/audit.js`）

用户指出「头明显看着天空，视线却看到下方的球」。查下来实现错得比这更多。
写了**几何自检**（在已知方位放亮标记，核对它出现在视野图的哪个位置）才定位，
一次揪出 7 个错：

| # | 问题 | 后果 |
|---|---|---|
| 1 | 头部网格本地 **+y 才是上**，我假设成 +z（那其实是"右"） | 绕错轴转 63.1°，视线抬到仰角 70.7°，一直在看天 |
| 2 | **鱼眼校正整个漏了**（`fly.py:1098` 采样前必做，zoom 2.72 / distortion 3.8） | 视野边缘全错 |
| 3 | fovy 用了猜的 130°，规范 `fovy_per_eye = 157°` | 视野偏窄 |
| 4 | 光轴用了猜的 ±50°，MuJoCo 里实测 **±63.1°** | 双眼重叠算错 |
| 5 | 飞行组 `flyer` 里**一个具名网格都没有** → `/head/i` 返回 null | **起飞时视窗直接停更** |
| 6 | 刻度线画在**数据画布**上 | 恒亮装饰在归一化后主导差分，测量被它骗 |
| 7 | **测试自己也用了同一个错误轴假设** | 测试"验证"了一个错误的几何 |

**第 7 条最值得记**：同一个错误假设同时污染实现和测试，测试照样通过。
另外改了三次测量指标才绕过全景图的逐帧归一化（标记进视野撑大范围、整幅变暗），
最后改成**直接测小眼读数 + 方向表**，不隔着渲染层测几何。

修完：7 个可见方位平均误差 **1.8°**（小眼间角 4.5°），左右眼归属正确，
180° 盲区确认 0 个小眼亮起。

#### 总审计 `dodge/audit.js`：25 项可证伪的数

不看"有没有内容"，只核对数：

```
flyvis 65 类 / 2355 抽头 · 721 小眼 · 450×512 · pale 216 / yellow 505
fovy 157° · 光轴 ±63.1° · 双眼重叠 30.8° · 总视野 283.2° · 盲区 76.8°
方向表两眼对称（和 0.8°）· 左右眼读数不同（不是同一台相机渲两次）
场地 28:15 · 果蝇出不了场地 · 视野投影三扇区合计 = 283.2°
```

CI 现在跑：smoke → flyvis parity → retina parity → 端到端 → 浏览器 →
几何自检 → 总审计。缺 Chrome 在 CI 里报错而不是跳过。

### 28.10 场地：按 1:87.5 缩小的篮球场（2026-09-18）（`dodge/court.js`）

主场景加了边界：真实球场 28×15 m → **320×172 mm**，带 FIBA 几何的地面线
（中圈 1.8 m、限制区 5.8×4.9、三分弧 6.75 m + 距边线 0.9 m 的直边）、
两个篮架、三级观众席。果蝇横穿全场约 18 秒。

线条用 canvas 贴图不用几何体：几百条线做成网格会拖慢渲染。

边界处理：撞到边界**停在边上，不反弹** —— 反弹要改朝向，会污染
"哪侧 DNa 活跃就往哪侧转"的对照，那正是这个游戏要测的东西。球出界作废、
不计入躲开/击中。

**这一整块是手写的场景装饰**，不来自任何实验数据，只决定果蝇能走到哪，
不改变任何神经计算。

尺度是试出来的：先按 1:50 做成 560×300 mm，结果相机最远只能拉到 160 mm，
画面里只有一段巨大的弧线。缩到 320×172 并把相机上限放到 420 mm 才看得全。

### 28.11 紫外 + 立方体贴图：两个"做不到"都做掉了（2026-09-18）

用户要求把 §28.9 末尾列的两条限制都解决。

#### 视野边缘：换成立方体贴图，不再需要任何畸变补偿

透视投影**天生到不了 180°**，157° 时边缘已被拉得极扁，FlyGym 的鱼眼公式还有个
奇点（半径 0.513 处分母变号，映射翻转到对侧）。改用 `THREE.CubeCamera`：
六个 90° 面覆盖整个球面，每个小眼按自己的视线方向精确采样。

实测开销：**渲 6 面 1.8 ms + 读回 5.9 ms**，比原来的 450×512 单面（230k 像素）
还便宜（6×192² = 221k，但省掉了鱼眼重采样）。两只眼几乎同位（FlyGym 里相距
0.76 mm），**一张立方体贴图两只眼共用**。

小眼方向改为直接按六边形点阵定义：点阵半径 15、小眼间角 **Δφ = 5.7°**，
用**方位等距投影**（把 (hx,hy) 当成偏离光轴的角度向量）：

| | 旧（157° 透视 + 鱼眼） | 新（点阵 15 × 5.7°） |
|---|---|---|
| 单眼视野 | 157° | **171°** |
| 双眼重叠 | 30.8° | **44.8°** |
| 总视野 | 283.2° | **297.2°** |
| 背后盲区 | 76.8° | **62.8°** |
| 几何自检平均误差 | 1.8–2.6° | **0.7°** |

#### 这一轮几何自检又揪出 4 个错

| # | 问题 | 怎么发现的 |
|---|---|---|
| 1 | `update()` 返回**复用缓冲区的引用** | 测试拿到的"上一帧"被下一帧覆盖，差分恒为 0 |
| 2 | 立方体路径里多套了一层 `retina.perm` | 方向表按点阵建，根本不涉及 flygym 序 |
| 3 | 把 (hx,hy) 当成独立的方位角/仰角（等距圆柱投影） | 仰角近 ±85° 的小眼全挤向极点、方位角失去意义 |
| 4 | **立方体贴图读回多翻了一行** | 普通渲染目标是自下而上，立方体的面是自上而下；多翻一次让画面上下颠倒，表现为"小眼报出的方位与实际看到的成镜像" |

第 4 条尤其值得记：我**验证过 cubeLookup**，用 6 个方向全对——但那 6 个方向
**全是面的正中心**，面内镜像在正中心是看不出来的。补了偏心方向的实测才暴露：
实测行 133，而带翻转的预测是 47。**测试用例的取样点选错，等于没测。**

#### 紫外（R7）：手写设定，但结构有依据

R 通道原本空着（pale 读蓝、yellow 读绿），正好拿来装 R7 紫外。渲染前把每个
材质的 `color.r` 换成它的紫外反射率，渲完还原 —— 一次渲染同时得到三路。

**数值是手写的**，没有任何测量依据。但结构有依据：自然界里**天空是压倒性的
紫外源**，绝大多数表面紫外很暗，果蝇正是靠这个对比找开阔空间、判断上下
（背侧边缘区）。所以天空给 1.0、地面 0.06、看台 0.09、球 0.02。
页面上的紫外全景里，天空一片亮、地面和看台全暗 —— 这就是果蝇眼里的紫外世界。

**上传的照片里没有紫外**，那条链路的紫外一路不可用，不做假装。

审计从 25 项扩到 **28 项**，新增：小眼间角、单眼视野、小眼与光轴最大夹角
（方位等距投影的定义性质）、紫外通道与彩色通道确实不同（防止同一路复制）。

### 28.12 「为什么眼睛看到的都是绿色」（2026-09-18）

用户问的。量下来是**两个原因叠加**，一个是我的错，一个是真的：

**① 场景本身几乎没有颜色（我的错）。** 球场原来用页面主题色，地板 `#1a211e`
（R26 G33 B30）。立方体贴图的平均色 G=36.6 / B=32.5 —— 两通道只差 11%，
果蝇眼里等于没有颜色可看。已改成**真实球场配色**（木地板 #b8763a、白线、
蓝红座椅），场景 G/B 变成 **76/49**。

**② 画面按感受器类型上色（我的错）。** 每个小眼只测一路（pale 测蓝、
yellow 测绿），我把类型映射成色相 —— 505 个 yellow 画绿、216 个 pale 画蓝，
**70% 的格子天生是绿的，跟它看到什么无关**。

已加**去马赛克**：每个小眼缺的那一路，用它六个邻居里另一型的平均补上，
和拜耳滤镜的去马赛克是同一回事。**果蝇本身并没有在每个小眼上同时拿到两路**，
这是显示用的插值，界面上可以关掉看原始马赛克。

**③ 但它仍然偏绿，而这是对的。** 实测眼内 G/B = 0.310/0.205（比值 1.52），
721 个小眼里 41 个偏蓝（那是蓝座椅）、347 个偏绿。木地板是橙色，而果蝇
**没有红色感受器**（R1–6 宽带 ~480 nm，R7 紫外，R8 蓝或绿，最长的 Rh6 也只到
~508 nm），橙色只刺激它的绿通道、几乎不刺激蓝通道。
**篮球场在果蝇眼里就是一片暗绿** —— 这不是渲染的毛病，是它的光谱决定的。

这条也说明一件事：**"看起来不对"有时是对的**，得先量清楚是实现错了还是
生物本来如此。这次是两者都有。

### 28.13 固定光源与阴影：一个放射状条纹，两个原因都不是我以为的（2026-09-18）

**要求**：给主场景加几个固定光源覆盖全场，场内物体按光源位置计算阴影；
左右眼合成视野和紫外视线也要支持彩色 + 去马赛克。

**做法**【实测】：`dodge/court.js` 在顶棚 14 m（真实尺度）挂四盏 `DirectionalLight`，
各自 `castShadow`，2048² 阴影图；`renderer.shadowMap.type = PCFSoftShadowMap`。
球场地面从 `MeshBasicMaterial`（完全不吃光）换成 `MeshLambertMaterial`，
两张假阴影贴图删掉。当前 27 个投射体 / 15 个接收面，**帧率仍 59.7**。

**中途出的错，按被发现的顺序**：

| # | 现象 | 我先以为 | 真正原因 |
|---|---|---|---|
| 1 | 球场变亮黄、糊成一片 | 颜色配错 | 加灯后总光强 1.65 → 3.0，**过曝**。hemi 0.95→0.30、sun 0.70→0.20、每盏 0.34→0.25 |
| 2 | 远角落成片条纹 | 阴影 bias 不够 | 阴影相机远裁面写死 `LH*3 = 308`，**远角落根本不在深度范围内** |
| 3 | 果蝇周围放射状扇形条纹 | shadow acne（连调 5 次 bias/normalBias/灯位都没消） | **z-fighting**：外圈装饰地面 z=−0.03、球场 z=+0.004，只差 **0.034 mm**，而相机 near/far = 0.1/800（8000:1），远处深度精度分不开这两层 |

第 3 个是这次最值得记的：**它长得像阴影瑕疵（从物体放射、只在远处、随视角变），
我就一路按阴影调了五轮**。隔离测试（关掉果蝇投影后球场干净）甚至给了假阳性，
因为关掉投影也就关掉了那块区域的重绘。修法是把两层地面拉开 3 mm、
近裁面 0.1→1（比值降到 900:1），条纹一次性全消。

**第二个假设也错了**：修完之后新加的审计题「每盏灯的阴影相机装得下整个场景」
立刻红了（8/8 角落在外）——因为那张半径 600 mm 的外圈装饰地面还挂着 `receiveShadow`。
真按它算，2048 的阴影图每像素 0.59 mm，而果蝇只有 3 mm，影子会碎成块。
正解是它根本不该接收阴影（球场外没有任何投射体）。顺手把阴影相机范围
从手搓系数 `hypot(W*0.72, H*0.91, LH*0.5)` 换成**实测包围球** `Box3.setFromObject(grp)` + 飞行余量。

**三通道合成**【实测】：`drawBrain(cv, readouts, mode, gbs)` 多收一路去马赛克后的 G/B。
合成视野面板现在出果蝇色；原「紫外」面板变成**三通道合成（紫外+蓝+绿）**，
G/B 用自己的 `lo2/hi2` 归一化区间（和紫外通道混在一个区间里会被紫外压平）。
两个面板都跟随「去马赛克」开关。审计实测：合成面板 92% 像素是彩色（R≠G 或 G≠B），紫外面板 92%。

**审计从 28 题加到 56 题**（`node dodge/audit.js`），新增 28 题全部可证伪。

渲染侧（16 题）：阴影贴图是否真的渲染过（只配 `castShadow` 不渲染时它是 `null`）、
把场景包围盒 8 个角投进每盏灯的阴影视锥、大平面层间距 ≥ 1 mm、
相机远近裁面比值 ≤ 1000:1、去马赛克两路 G/B 是否真的不同（不是复制）、
开关切换后画布像素是否真的变了、果蝇眼里饱和像素占比 < 50%。

游戏本体侧（12 题，这次补的空白）：真实神经元开关 10 个、
**ID 全是 18 位字符串**（FlyWire root ID ≈ 7.2×10¹⁷ > 2⁵³，写成数字字面量会静默掉精度——
这个坑踩过一次，曾误判水味觉 GRN 不在子回路里）、
子回路比值与全脑比值不许雷同（只有 1/10 相同，说明是各自实测的不是抄的）、
水味觉 18 个 ID 里 17 个在子回路（§19 实测）、
**损毁真的把突触清零**（Roundup 338,837 → 338,637；LC4 → 330,419）且取消后复原、
输入组来自子回路元数据而非硬编码、给糖它真的说出「尝到甜的」、飞行片段 2 段 845/601 帧。

写这 12 题时我对自己代码的接口连猜错两次（`speech()` 返回对象不是字符串、
飞行片段存在 `G.clips` 不是 `G.flightClips`），两次都是审计当场报红才发现——
**这本身就说明"我记得它是怎样"不能当验证**。

**教训（第三次撞同一堵墙）**：*长得像什么，不等于是什么*。
放射状+只在远处+随视角变，这三条同时指向 z-fighting 和阴影 acne 两种病，
我只顺着先想到的那条查了五轮。可证伪的分辨办法其实一行就够——
把阴影总开关关掉，条纹还在就不是阴影。现在这条已经变成审计里的「大平面层间距」题。

### 28.14 视野扇区「和地板同色等于没画」（2026-09-18）

**用户报的**：右眼那块视野扇区，颜色和地板一样，阳光 100% 时根本看不出区域。

**量出来的原因比"同色相"更硬**【实测】：球场地板 `#b8763a`，阳光 100% 时渲染出来是
**(255, 161, 76)——红通道已经削顶在 255**。右眼扇区原本用金黄 `0xe8b339`，
半透明叠加要抬的正好是 R 和 G，而 R 根本无处可涨，于是扇区内外的 RGB 欧氏距离
只有 **Δ = 8.4**，等于没画。

新建 `dodge/field_contrast.js` 量这件事（果蝇摆场地中心、相机正上方俯视、
按扇区角度范围在半径 15 mm 处采样，和半径 30 mm 的裸地板比）。旧配色三档阳光：

| 阳光 | 裸地板 | 双眼重叠 | 左眼单眼 | 右眼单眼 |
|---|---|---|---|---|
| 0% | 33,21,10 | 50.4 | 18.2 | 19.4 |
| 50% | 145,91,43 | 44.5 | 15.5 | 12.5 |
| 100% | 255,161,76 | 19.6 | 15.7 | **8.4** |

**旧配色其实三档下都不合格**（阈值 20），只是 100% 时右眼最差，所以在那里最先被看出来。

**两步修**：
1. 换能把 R **压下去**的冷色：右眼 `0xe8b339` → `0x2f8dff`（蓝），
   左眼 `0x3fb984` → `0x00e5b0`（青绿），单眼扇区不透明度 0.085 → 0.16。
   → 右眼 8.4 → 46.5。
2. 但截图一看，冷色叠在饱和橙地板上出来的仍只是**"更亮或更暗的橙"，色相身份是丢的**。
   所以每个扇区再描一道**不透明边界线**（`LineLoop`，z=0.06 高于色块的 0.03）——
   线不依赖底色，任何光照下都是它自己的颜色。实测边界线 Δ = **236–272**。

**顺带揪出两个自己的错**：
- 加完边界线后 `eyecam_geom_test` 红了 1/9，重跑又过 —— **偶发比稳定回归更糟**。
  原因是视野扇区**没有进 `selfMeshes`**：这些给玩家看的标注就在果蝇周围 22 mm，
  近乎不透明的边界线会被渲进立方体贴图，污染小眼读数。修掉后连跑 7 次全过。
- `eyecam` 的 `this.selfMeshes = opts.selfMeshes` 是**别名**，而页面会整体重新赋值
  `fs.selfMeshes`，一旦顺序变了这里就悄悄指向旧数组。改成 `.slice()`。

**教训**：*"换个颜色"这种改动也该有数*。如果只靠截图判断，第 1 步（右眼 46.5）
看上去就已经"修好了"，不会发现色相身份仍然是丢的；而旧配色在 0% 阳光下
看着也"能看见"，不会发现它三档全不合格。工具已进 CI 和 `npm test`，
并且把旧配色注回去验证过：7 个（扇区 × 阳光）组合不达标、退出码 1。

### 28.15 复眼视窗提速 3 → 23 fps：瓶颈不是我以为的任何一个（2026-09-18）

为了后面把视觉回路从像素闭上（§28.16 计划），先得把复眼成像的帧率提上去。
原来是 3 fps，注释写的理由是"读回 GPU 像素会打断渲染流水线"——方向对，但**具体是什么在花时间，三次都猜错了**。

**逐段实测**（M1 Pro / ANGLE Metal，真机 GPU 不是软件渲染）：

| 阶段 | ms |
|---|---|
| 渲染立方体贴图（CPU 提交） | 2.13 |
| 读回 6 面（GPU 已空闲） | 0.77 |
| RGBA→RGB 重排 221,184 像素 | 0.52 |
| 按 1,442 个小眼方向采样 | 0.08 |
| 去马赛克 | 0.11 |
| 画两张六边形画布 | 1.23 |
| **各段之和** | **4.85** |
| **整次 update 实测** | **8.88** |

差了 4 ms。挨个排查：紫外材质换色 0.03 ms、隐藏自身网格 0、清屏色 0、
换色后渲染并不更贵（−0.24）。最后定位到**渲染与读回串起来时的 GPU 同步停顿**：
单独计时 `cube.update()` 只量到 CPU 提交，GPU 还在后台跑；`readRenderTargetPixels`
会强制等它画完。串行实测 7.04 ms，而分开量只有 2.93。

**关键一步是量它的标度**——这一步否掉了三条我本来要推荐的优化：

| 试法 | 结果 |
|---|---|
| 读 1 面 vs 读 6 面 | 6.27 vs 6.76 ms —— **几乎一样** |
| 读 16×16 一角 vs 读整个 192² | 7.45 vs 6.27 ms —— **几乎一样** |
| 每面边长 192 → 128 → 96 → 64 → 48（像素少 16 倍） | 9.17 / 10.05 / 8.01 / 8.04 / 9.54 ms —— **没有下降趋势** |

所以那 4–5 ms 是**一次固定的往返同步**，与面数、像素量、贴图分辨率全都无关。
降分辨率、减面数、合成一张图集——全部无效。先把读回挪到渲染之前（读上一帧）也无效
（9.12 vs 8.24 ms），因为主场景渲染只要 0.53 ms，中间没有足够的活能把延迟藏掉。

**真正的解法：WebGL2 的 PBO 异步读回**。`readPixels` 写进 `PIXEL_PACK_BUFFER` 立即返回，
插一个 `fenceSync`，下一帧再 `getBufferSubData` 取。这个 three.js 版本没有
`readRenderTargetPixelsAsync`，自己实现了一套（`_submitAsync` / `_tryCollect`）。

- **正确性【实测】**：与同步读回**逐字节相同**，884,736 字节全等，等待恰好 1 帧。
- **速度【实测】**：单次 10.6 → **2.9 ms**。
- **节流方式改了**：收集**每帧都试**（画面最多晚 1 帧 ≈ 16 ms），提交按 `EYE_FPS` 节流。
  第一版跟着提交频率一起节流，12 fps 下画面就晚 83 ms —— 那才是真的卡。
- 顺手去掉了 RGBA→RGB 重排：6 面合进一块连续 RGBA 缓冲，采样时按 ×4 取偏移。
  原来把 221,184 个像素全搬一遍，而真正采样的只有 1,442 个。

**结果**：目标 30 fps，**实测成像 23 fps**（原 3 fps，7.7 倍），主画面仍 **60 fps**。
上限测过：目标 60 时能到 43 fps 成像且主画面不掉，留了余量给后面的 flyvis 闭环。

**两道新审计题**（共 60 题）：异步读回与同步逐字节相同、成像速率 ≥ 10 fps。
写第一版时这两题都因为**和页面自己的 rAF 循环抢同一个 fence** 而失真
（页面先把 fence 消费掉，`tries` 跑满 60 却仍报"全等"——那个"全等"是巧合）。
测之前先停掉 `window.__eyeTick` 才成立。

**教训**：*"什么慢"和"为什么慢"是两个问题，后者必须量标度*。
"读回 GPU 像素很慢"是对的，但据此去降分辨率会白干——因为代价根本不在像素量上。
分辨这两者的办法就是把参数扫一遍看它怎么变。

### 28.16 视蛋白光谱：补上八个感光细胞里缺的六个（2026-09-18）

**动机不是好看**。核对时发现：flyvis 的输入型是 **R1–R8**，而主力 **R1–R6 用 Rh1（宽带）**，
是运动与亮度的主通道；但 eyecam 至今只产出 R8 那一路（pale 取蓝通道、yellow 取绿通道）
和 R7 紫外，**Rh1 完全没有建模**。八个里缺六个，下一步要把像素接进 flyvis 就没有正确的输入。

**做法**（`vision/opsins.js`，权重由 `node vision/opsin_weights.js` 写进
`results/vision/opsin_weights.json`，报告和页面都从那里取，不手抄）：

- 敏感度曲线用 **Govardovskii et al. 2000 的 A1 视色素模板**（已发表解析式，α 带 + β 带）。【官方】
- λmax 用果蝇已发表值：Rh1 478（R1–6）、Rh3 345（R7p）、Rh4 375（R7y）、Rh5 437（R8p）、Rh6 508（R8y）。【官方】
- 场景是 sRGB 著作的、没有真实光谱：把三个渲染通道当作各自波段内的平均反射率
  （紫外 300–400、蓝 400–500、绿 500–700；果蝇无红受体，600–700 并入绿带）。【推测】
- 光源按等能白处理。【推测】
- 权重 = ∫S(λ)·波段(λ)dλ ÷ ∫S(λ)dλ，所以理想白面每一类响应都是 1。

| 视蛋白 | 细胞 | λmax | 紫外 300–400 | 蓝 400–500 | 绿 500–700 |
|---|---|---|---|---|---|
| Rh1 | R1–R6 | 478 | 0.384 | 0.462 | 0.154 |
| Rh3 | R7p | 345 | 0.998 | 0.002 | 0.000 |
| Rh4 | R7y | 375 | 0.883 | 0.117 | 0.000 |
| Rh5 | R8p | 437 | 0.321 | 0.664 | 0.015 |
| Rh6 | R8y | 508 | 0.169 | 0.397 | 0.434 |

（表中 Rh1 含增感色素项，见下。）

**中途两个错，都是审计当场抓到的**：
- 第一版基函数用**帽函数**（峰值 365/465/550 线性过渡），结果 Rh5（λmax 437，蓝）
  拿到 **46% 的紫外权重** —— 因为紫外帽一路延伸到 465 nm，把 400–465 的紫蓝光算成了紫外。
  那是基函数的错，不是光谱的事实。改成左闭右开的**箱型波段**后降到 32%（β 带真实贡献）。
- 积分写成 `lam <= 700` 而波段是 `[500,700)`，**700 nm 这一个采样点进了总量却不进任何波段**，
  归一化差 1.5e-7。审计里"白面响应 = 1，容差 1e-9"那一题抓到的 —— 容差定松一点就漏了。

**已知缺口写在代码里**：果蝇 R1–6 带一个 3-羟基视黄醇**增感色素**，在 ~350 nm 给第二个峰，
**不在** Govardovskii 模板中。这里做成显式可开关的附加项，幅度是手选的【推测】
（关掉时 Rh1 紫外权重 0.384 → 0.198，即会**低估** R1–6 的紫外敏感度）。两套权重都在 JSON 里。

**附带效果**：几何自检的平均误差从 1.0° 降到 0.6°（同一次运行内）——
因为每一类现在都用上三个通道积分，标记的信噪比更好了。

**新增 11 道审计题**（共 71）：权重归一化、Rh3/Rh4 以紫外为主、Rh5 蓝权重最大、
Rh6 绿权重全场最大、**λmax 越长绿权重越高**（单调性，光谱表算错时这条最先塌）、
R1–6 输出存在且与 R7/R8 都不同（不是复制）、**pale 与 yellow 的紫外响应不再相同**
（Rh3 345 nm vs Rh4 375 nm，改光谱之前这个差恒为 0）。

### 28.17 测 flyvis 的 T4/T5 偏好方向（2026-09-18）

**为什么要测**：下一步想按 Klapoetke et al. 2017 的 LPLC2 模型，汇集「背离感受野中心」的
T4/T5 来做逼近检测。文献里 T4a/T5a 叫"前→后"、b"后→前"、c"上"、d"下"——
但 flyvis 是用**光流任务训练**出来的，它学到的解是否和这套命名在同一套点阵坐标里对齐，
是个经验问题。方向搞反，整个逼近检测就是反的。

**方法**（`node vision/t4t5_directions.js` → `results/vision/t4t5_directions.json`）：
六边形点阵上放漂移正弦光栅（空间周期 4 个小眼 ≈ 22.8°），8 个方向 × 时间频率 2/5/10/20 Hz，
dt = 5 ms（T4/T5 的 τ ≈ 19.8 ms），后 0.6 s 平均，**减去静止光栅的基线**。
角度按点阵平面 atan2(hy, hx)，与 `eyecam.js` 的 `latticeDirs` 同一约定。

**结果**【实测】：

| 亚型 | 最佳 TF | 峰值增量 | 偏好方向 | 方向选择性 | 最贴的六边形方向 |
|---|---|---|---|---|---|
| T4b | 2 Hz | 0.554 | 87° | 0.473 | 90°（差 3.0°） |
| T4c | 5 Hz | 0.213 | 149° | 0.815 | 150°（差 0.7°） |
| T5c | 5 Hz | 0.084 | 199° | 0.891 | 210°（差 11.1°） |
| T4a | 2 Hz | 0.468 | 274° | 0.410 | 270°（差 4.1°） |
| T5a | 2 Hz | 0.166 | 263° | 0.287 | 270°（差 6.7°） |
| T5d | 2 Hz | 0.124 | 333° | 0.706 | 330°（差 3.1°） |
| T4d | — | 0.012 | — | — | 无方向选择性（增量≈0） |
| T5b | — | 0.121 | — | 0.031 | 无方向选择性 |

**三个可以直接用的结论**：
1. **偏好方向落在六边形点阵的「棱」方向族（30°+60°k）上**，不是顶点族（60°k）——
   两族都算过，棱族对每个有选择性的亚型都贴到 0.7–11.1°，顶点族系统性差 25–29°。
   这很合理：flyvis 本来就是六边形卷积网络。
2. **占了 6 个方向里的 5 个**：90°(T4b)、150°(T4c)、210°(T5c)、270°(T4a 与 T5a)、330°(T5d)；
   30° 这一格是空的。T4a 与 T5a 偏好方向一致（274° / 263°），和文献中 T4/T5 同字母配对相符。
3. **T4d 和 T5b 在这个刺激下没有方向选择性**，所以"a/b/c/d = 四个正交方向"的命名惯例
   **在 flyvis 这里不成立**，不能照搬。

**时间频率**：峰在 **2–5 Hz**，10 Hz 时 T4c/T4d/T5c/T5d 的增量已经全为 0，20 Hz 全部塌掉。
这直接约束了闭环的采样率——球的角速度必须落进这个带里才看得见。
运动/静止的整体比值在 2 Hz 时也只有约 1.2×（见 JSON），说明这些细胞的**静息活动很高**。

**另一个教训：参数扫描把权威结果文件覆盖了。**
写完这一节之后，我为了验证 dt=33 ms 下定标还成不成立，用 `TF=2 DT=0.033` 又跑了几轮——
脚本每次都往**同一个** `results/vision/t4t5_directions.json` 写，于是文件里留下的是最后一次
参数变体的结果，和报告里的数字对不上。`lplc2_test.json` 同样被 `DT=0.033` 那轮覆盖。
报告的数字没抄错（是默认参数那次的真值），**但文件已经不能复现它了** ——
而本项目的规矩正是"每个出现在正文里的数字都要有脚本把它写进文件"。
自查脚本逐行比对报告表格与 JSON 时抓到 30 处不一致，才发现是这个原因。
两个脚本现在都加了保护：**只有默认参数才写权威文件，变体自动加后缀**（`_dt33ms_tf2.json`）。

**方法上的教训（差点得出反的结论）**：第一版没减静止基线，直接用平均活动算方向选择性。
T4c/T4d/T5c/T5d 的静止活动本来就有 0.15–0.36，等于把基线当成"对所有方向都响应"，
**T4c 的选择性被压成 0.41，减完基线是 0.815**。同一份数据，两个相反的印象。

### 28.18 LPLC2 逼近检测：能分开，但很弱，而且只在「峰值」上（2026-09-18）

把像素接进 flyvis 之后，缺的最后一环是 **flyvis → LC4/LPLC2**：flyvis 的 65 类里
没有这两类（全是视网膜/板/髓质的柱状细胞），LC4/LPLC2 是下游的小叶投射神经元。
按 Klapoetke et al. 2017 的模型形式做汇集：一个中心在 c 的 LPLC2 收集**背离 c** 的 T4/T5 运动，

E(c) = Σ_j Σ_s a_s[j] · max(0, cos(θ_s − φ_{c→j}))，θ_s 用 §28.17 **实测**的偏好方向。

**诊断实验（独立刺激：全场径向正弦光栅，纯扩张 vs 纯收缩，3 Hz）**【实测】：

| 感受野半径 | 扩张 | 收缩 | 比值 |
|---|---|---|---|
| 8 | 0.329 | 0.295 | 1.11 |
| 12 | 0.351 | 0.275 | 1.28 |
| 15 | 0.383 | 0.260 | 1.47 |
| 20 | 0.437 | 0.258 | **1.69** |

两个结论，都直接改了模型默认值：
- **感受野越大越好**（点阵半径本就是 15，R=20 相当于每个中心看整只眼）。
- **绝不能用 max 统计量**：R=5 时扩张:收缩 = **0.76，是反的**。圆盘收缩时，位于对侧的中心
  会看到盘缘正在"远离自己"，被算作向外；取 max 专挑这种假阳性。改用 mean。
- 六个有方向选择性的亚型全用，好过只留最挑的三个（1.69 vs 1.63）——方向覆盖更全。

**圆盘刺激的三条判据**（`node vision/lplc2_test.js`）【实测】：

| 刺激 | LPLC2 峰值 | 峰值时刻 | LPLC2 均值 |
|---|---|---|---|
| 逼近（加速） | **0.2084** | 1.195 s | 0.1282 |
| 远离（时间倒放） | 0.1573 | 0.30 s | 0.1207 |
| 近距平移 | 0.1653 | 0.85 s | **0.1592** |
| 远距平移 | 0.1234 | 0.895 s | 0.1219 |
| 匀速扩张 | 0.1943 | 1.155 s | 0.1610 |
| 匀速收缩 | 0.1569 | 0.30 s | 0.1414 |

判据 A（匀速扩张 > 匀速收缩）✓ 1.24×；A'（加速逼近 > 时间倒放）✓；
B（逼近 > 两种平移）✓ 1.26× / 1.69×。

**必须如实记录的三件事**：

1. **这不是一次干净的预注册检验**。我在看到失败后改了两次协议：
   (a) 第一版没有静态预呈现，远离/平移的峰值全落在计分窗口第一帧——比的是"谁出场动静大"；
   (b) 第二版发现"远离"是"逼近"的时间倒放，而逼近是加速的，倒过来就**开局收缩最快**，
   恰好撞上运动起始、网络刚脱离静止适应态，和逼近的最快阶段（连续运动 1.2 s 后）不对等。
   两次都是先诊断出混淆因素才改，不是奔着判据调参，但读者有权知道顺序。
   `mean` 和 R=20 也是从上面那个**独立**诊断实验选的，所以 A/B 不是完全独立。
2. **只在峰值上成立，均值上不成立**：近距平移的**均值 0.1592 高于逼近的 0.1282**。
   这和 §18 全脑那条离线链路的结论完全一致（那里用平均发放率，逼近 0.65 Hz < 近距平移 1.14 Hz，
   8 个朝向里 0/8）。逼近检测器本来就该看**峰值**（LPLC2 在接触前才冲起来），
   但这说明"逼近强于平移"这件事在这个模型里**依赖读数方式**，不是稳健的。
3. **裕度很小**：1.24–1.26×。手写的 dθ/dt 前端给出的信号干净得多。
   接进游戏后噪声会明显，这一点在做之前就要说在前面。

**闭环可行性【实测】**：游戏里视觉更新只能到 ~30 Hz，也就是 flyvis 的 dt = 33 ms，
**远大于 T4/T5 的 τ ≈ 20 ms**，动力学会被抹平——定标是在 dt = 5 ms 下做的，必须验证它还成立。

| dt | T4a 偏好 | T4b 偏好 | T4c 偏好 | 判据 A | 判据 B（近距平移） |
|---|---|---|---|---|---|
| 5 ms | 274° | 87° | 149° | ✓ 1.24× | ✓ 1.26× |
| 17 ms | 274° | 87° | 149° | — | — |
| 33 ms | 274° | 87° | 153° | ✓ 1.36× | ✓ 1.15× |

偏好方向基本不动，三条判据在 33 ms 下依然全过（A 还更好一点、B 稍差）。所以**单步 30 Hz 可行**。

单次代价【实测】：flyvis 一步 3.42 ms、LPLC2 汇集 0.94 ms（stride=8，91 个中心）——
双眼合计 8.7 ms，加 eyecam 的 2.9 ms 约 **11.6 ms**；30 Hz 下约占 35% CPU。

**（这里差点栽一次）**：给脚本加 dt 环境变量时，替换字符串没匹配上（那行末尾是分号），
而我的补丁脚本**没加 assert、照样打印了 ok**。结果三个 dt 跑出一模一样的数字——
"完全相同到小数点后四位"才是发现它的线索。补丁脚本必须断言替换真的发生了。

### 28.19 把视觉回路从像素闭上：能闭，但果蝇要等球到 2.5 cm 才看得见（2026-09-19）

游戏里驱动行为的那条视觉前端**从来不看像素**：它直接读球的世界坐标算张角增长率
（`game_core.js` 的 `visualInput`），而且只看球、无视场景里其它一切。
现在把真链路接上：复眼像素 → Rh1（R1–R6，§28.16）→ flyvis → LPLC2 汇集（§28.18）→ 频率。
模块是 `vision/front_end.js`，对比脚本 `node dodge/front_end_compare.js`。

**先算一笔账**（球半径 2.5 mm、小眼间角 5.7°）【实测/几何】：

| 距离 | 角直径 | 占几个小眼 |
|---|---|---|
| 60 mm | 4.8° | **0.8** |
| 30 mm | 9.5° | 1.7 |
| 10 mm | 28.1° | 4.9 |

球在 60 mm 外**还不到一个小眼**。所以"看不见"不是模型差，是分辨率极限。

**实验设计**（噪声与信号分开测；第一版混在一次里，被起飞慢放毁了——
果蝇一起飞页面就 ×0.04 慢放，球停在 55 mm，样本不可比）：
- A「只有自体运动」：场上无球、果蝇自由行走 → 连接组前端读到的全是噪声
- B「只有球」：每帧把位姿钉回原点（既不走也飞不起来），球从 120 mm 逼近 → 信号
- 只取**逼近段**（球过最近点后会远离，手写前端对远离不响应，混进来两边都读错）
- 3 次重复合并（**噪声底本身在波动**，单次 p95 在 39–80 Hz 之间跳）

**结果**【实测】（`results/vision/front_end_compare.json`）：

A 自体运动（264 帧）：连接组前端 中位 **0 Hz**、p95 **80.1 Hz**、峰值 **125.8 Hz**。
也就是说**果蝇光是走路，就会给自己制造最高 126 Hz 的"逼近"信号**。

B 逼近段（141 帧）：

| 距离 mm | 手写 dθ/dt 中位 | 连接组像素 中位 | 高过噪声 p95？ |
|---|---|---|---|
| 90–110 | 3.9 | **0.0** | ✗ |
| 70–90 | 4.4 | **0.0** | ✗ |
| 55–70 | 5.3 | **0.0** | ✗ |
| 45–55 | 6.6 | **0.0** | ✗ |
| 35–45 | 13.9 | 10.9 | ✗ |
| 25–35 | 16.9 | 26.2 | ✗ |
| 0–25 | 11.3 | **87.2** | ✓ |

**结论**：连接组前端在 **45 mm 外完全瞎**（读数恒为 0），
要到 **25 mm 以内**才把球从自体运动的噪声里分出来；手写前端从 110 mm 就在跟。
换算过来就是：**球大约长到 1.5 个小眼，这套真实视觉系统才看得见它。**

两点说明：
- 这不是 LPLC2 模型的失败。§28.18 里它在合成刺激上判据全过，只是裕度小（1.24–1.26×）；
  真实场景里败给的是**分辨率**和**自体运动**两件事，而这两件恰恰是手写前端作弊绕开的。
- 真果蝇面对的捕食者/拍子相对体型大得多，而且有触角/平衡棒的自体运动信息去抵消光流。
  这个模型两样都没有。

**所以没有把它接成游戏的默认前端**：接上去果蝇会一边走路一边被自己吓得起飞。
它作为**可切换的对照**才有意义（"看着果蝇真实的视觉系统直到球逼到 2.5 cm 才发现它"）。

**页面上的实现**（开关「只靠眼睛躲」，默认关）：`game_core.js` 加了 `G.setVisionOverride(o)`，
`visualInput` 在 override 生效时跳过"读球坐标算 dθ/dt"那一段，直接用传入的 Hz。两处细节：
- **不再乘光照增益**。手写版需要补 `CFG.light` 这一项，而像素版的光照已经体现在渲染出来的像素里了，
  再乘一次就是重复计。
- override 期间仍然维护每个球的 `prevTheta`，否则切回手写前端的第一帧会因为 dθ/dt 突变而跳。

威胁方位（起飞时往哪个方向逃）也改成从像素来：取 LPLC2 更强的那只眼、它的**扩张焦点所在柱**，
按方位等距投影换算成眼内方位，再加上该眼光轴的 ±63.1° 和机体朝向。
手写版是直接用球的世界坐标，这一版不知道球在哪。

**（一个我自己的 bug，值得记）**：`front_end.js` 第一版直接拿第一帧当基线。
flyvis 刚 reset 时活动是暂态的（实测 0.366，稳定后只有 0.13），基线被毒化后要几秒才衰减，
这期间 `max(0, 当前 − 基线)` 恒为 0——**前端整段"瞎着"而不报错**。加了预热期才好。
另外表里"手写前端在无球时峰值 17.4 Hz"也是测量瑕疵：我每 50 ms 清一次球，
自动发射的球能存活最多 50 ms，被读进去了。

### 28.20 晶格对齐：解剖能把 8 种朝向钉到 1 种，但也揪出原流程一处形变（2026-09-19）

§18 至今跑**全部 8 种朝向**（交换轴 × 翻 x × 翻 y），因为 flyvis 的点阵是正六边形、
六重对称，几何上没有任何特征可以定向。而 §18 实测**朝向间的标准差是重复间的 3–4 倍**——
主要不确定性来自这里，不是噪声。

**锚点只能是功能性的**。`vision/lattice_anchor.py`（离线、只读）分两步：

**第一步：用解剖位置定出 Codex `(p,q)` 的朝向。**【实测】
三条轴都从数据里量，不靠 FAFB 坐标约定的假设：
- 左右轴 = 左右视叶质心之差（两质心相距 **491 µm**）
- 腹侧 = 全脑质心 → GNG（食道下神经节）质心（1,030 个 GNG 神经元，偏移 **96 µm**）
- 前后轴 = 二者叉积；符号用**触角叶 vs 中央复合体**核对（AL 在 CX 前方 138 µm）

把每个柱的三维质心对 `(p,q)` 做线性回归：

| | +p 的解剖角 | +q 的解剖角 | 基矢夹角 | 回归残差/跨度 |
|---|---|---|---|---|
| 左眼（785 柱） | 110.7° | 173.7° | 63.0° | 17.4 / 61.4 µm |
| 右眼（796 柱） | 116.0° | 167.7° | 51.7° | 15.0 / 62.6 µm |

（角度约定：0° = 前方，90° = 背侧。）两眼独立算出、相差 5°/6°，基矢夹角接近六边形应有的 60°，
且左右分量符号相反——正是两只眼该有的镜像关系。三项都是独立的一致性检验。

**第二步：与 §28.17 实测的 T4/T5 偏好方向联立。**【实测】
文献：T4a/T5a 偏好前→后、T4b 后→前、T4c/T5c 朝背、T5d 朝腹。
对 6 个有方向选择性的亚型拟合「解剖角 = flyvis 角 + φ」，得 **旋转 φ = 277°，RMS 误差 17.2°**
（全部落在半个六边形步长 30° 以内）；**镜像假设被否**。
由此 flyvis 的 −u 在解剖 97°、−v 在 157°，对上 +p(113°)、+q(171°)，即 **u = −p, v = −q**。

**顺带揪出原流程一处形变**【实测】：`normalize()` 做 PCA + 各轴除以标准差，

| | +p 角 | +q 角 | 基矢夹角 | 长宽比 |
|---|---|---|---|---|
| 原始 `cart(p,q)` | 0.0° | 60.0° | **60.0°** | 1.66 |
| `normalize` 之后 | −59.0° | 63.6° | **122.6°** | 1.00 |

真实果蝇眼的柱阵列是 **1.66:1 的长形**（785 柱），flyvis 是正六边形（721 柱，1.00）。
现有流程用各向异性缩放把前者压成后者，代价是**把六边形点阵的基矢夹角从 60.0° 拉成 122.6°**——
映射到的已经不是同一种点阵，8 种符号组合里没有一种救得回来，因为形状在那之前就错了。
左右眼都是 122.6°/122.0°，不是偶然。

**这是个真实的取舍，两边都得说**：
- 原流程：保覆盖（721 个 flyvis 柱全用上），**牺牲角度**（60°→122.6°）
- 解剖锚定 ×1.0：保角度，**牺牲覆盖**（中心 62% 精确落到格点，外围 38% 被夹到六边形边缘）
- 解剖锚定 ×0.6：各向同性缩放（**不改基矢角**），只剩 5.8% 被夹，但 785 个真实柱挤进 282 个
  flyvis 柱（采样变粗，不是几何变形）

三种一起跑，用来把「锚定有没有用」和「夹边缘有没有害」分开。
判据照抄 §18 并在跑之前写进 `results/vision/lattice_prediction.md`：
C1 逼近 > 远离、C2 逼近 > 远距平移、C3 逼近 < 近距平移。
**没有预先声明锚定会让选择性变好**——那等于假设了答案；要报告的是它落在原来 8 个朝向分布里的位置。


### 28.21 页面加仓库入口（2026-09-19）

三个页面（`game.html` / `index.html` / `article.html`）统一加了「源码」和「Star」两个入口，
带实时 star 数。

**一件要说清楚的事**：**GitHub 没有「一键收藏」的直链**——那会是 CSRF 攻击面，官方不提供。
所以 Star 按钮只能直达仓库页上的那个 Star 按钮，这一点写进了 tooltip，没有假装它能一键完成。

star 数是这几个页面**唯一的外部请求**（`api.github.com`，未认证 60 次/小时限流）。
取不到时静默降级：游戏页隐藏数字，另两页保持"支持一下"。审计里为此加了一题——
**star 数缺省时必须保持隐藏**，不能因为一个外部请求失败就在页面上留个空壳。
审计共 6 题：入口数、都指向本仓库、外链带 `rel=noopener`、每个按钮都有图标、缺省降级、键盘可聚焦。

### 28.20.1 跑完之后：朝向不是关键，**缩放**才是（2026-09-19）

全脑跑了 5 刺激 × 10 种映射 × 3 重复 = **150 次**（55 分钟，峰值内存 3.2 GB）。
判据在跑之前写进 `results/vision/lattice_prediction.md`，分析脚本 `vision/lattice_compare.py`。
指标 = LPLC2 左+右在 0.5–0.95 s 的平均发放率。

| 映射 | 输入 Hz | 逼近 | 近距平移 | 远距平移 | 逼近/近距 | C1 | C2 | C3 |
|---|---|---|---|---|---|---|---|---|
| k=0…k=7（PCA 归一化） | 2.90–3.13 | 0.45–0.80 | 0.61–1.54 | 0.09–0.82 | 0.44–0.97 | 8/8 | 7/8 | 8/8 |
| 解剖锚定 ×1.0 | 3.78 | **0.33** | 0.74 | 0.11 | 0.46 | ✓ | ✓ | ✓ |
| 解剖锚定 ×0.6 | 4.33 | **1.53** | 1.17 | 0.77 | **1.31** | ✓ | ✓ | ✗ |

（C3 = 「逼近 < 近距平移」。它成立意味着**「逼近强于平移」不成立**——这正是 §18 报告过的部分失败。）

**结论一：朝向不是主因，缩放才是。**
解剖锚定 ×1.0 和 ×0.6 **朝向完全相同，只差一个各向同性缩放**，却在 C3 上给出相反答案。
×1.0 的逼近响应落在原来 8 个朝向的**第 0 百分位**（0.33，低于全部），×0.6 落在**第 100 百分位**（1.53，高于全部）。
所以"把朝向钉死"本身并没有改变 §18 的任何结论。

**结论二：×0.6 是十种里唯一「逼近 > 近距平移」成立的，而且三次重复全部成立**
（逐次 1.57 / 1.10 / 1.28；次高的 k=4 是 0.87 / 1.23 / 0.85，只有一次越线）。
这条值得注意，因为三族映射的几何代价不同：

| 映射 | 基矢角 | 被夹到边缘 |
|---|---|---|
| PCA 归一化（k=0–7） | **失真 60°→122.6°** | 0% |
| 解剖锚定 ×1.0 | 正确 | **37.8%** |
| 解剖锚定 ×0.6 | 正确 | 5.8% |

**×0.6 是唯一既角度正确、又没被严重截断的映射**，也是唯一让「逼近强于平移」成立的。

**一个预先想到的假象解释，测了之后被否掉**：缩放 0.6 会把外围真实神经元映射到**中央** flyvis 柱，
如果逼近刺激正好落在视野中央，就会被抹到整只眼上、系统性放大。实测各刺激的 T4/T5 活动重心离心率
（点阵半径 15）：**逼近 6.29、近距平移 5.34、远距平移 5.79、远离 5.28**——
逼近反而是**最靠外**的那个，压缩应当偏袒平移才对。所以这个解释不成立。

**不能过度解读的地方，逐条列出**：
- 只有**一种**映射给出这个结果，n=3 重复，比值标准差 0.24。
- 两种锚定映射的**输入强度更高**（3.78 / 4.33 vs 原来的 2.90–3.13），因为多个真实柱共用一个
  flyvis 柱时，采到高活动柱的机会变多。逼近/近距平移是同一映射内的比值，受此影响较小，但不是零。
- 我**没有**为 ×0.6 的效应找到机制。"角度正确 + 不截断"是个合理的故事，但那是事后归因，不是预先声明。
- 要坐实它，至少需要：更多重复、更多刺激、以及一个独立于本次分析的映射检验。

**所以 §18 的结论现在应该这样表述**：那句"逼近强于平移只部分成立"是在**8 种都已经把点阵角度拉变形的映射**
上得到的；换成角度正确且不截断的映射之后它成立了。这是一条**有条件的修正**，不是推翻，
在有更多证据之前两种说法都要摆出来。

---

## 29. 补官方论文的空白：aDN2（2026-09-19）【实测 · 零新仿真】（`screen/jon_adn2.py` → `results/screen/jon_paper/adn2_summary.json`）

论文补充表 7C/7E 是梳理通路的**另一半**：第二个下行指令神经元 aDN2。
§24 系列只做了 aDN1，这一半一直空着。

**为什么不用跑仿真**：段落文件存的是每段**全部活跃神经元**的稀疏 (索引, 计数) 对，
不是只存读出神经元。§24.3 跑那条通路时 aDN2（`720575940629806974`，早就写在
`screen/jon_screen.py` 里并被 watch）的计数就一起存下来了，当时的分析只取了 aDN1。
所以这是纯粹重读存档，几分钟。

口径与 §24.3 **逐项相同**（刺激 = 论文 neu_JON_all 的 145 个、160 Hz、前 6 个实现、
零参照 = 50 个随机活跃神经元单敲的中位数、判据 ≤ 0.8），只换读出神经元，对照论文表 **7E**。

**结果**【实测】：

| | aDN2 | aDN1（同一批段落） |
|---|---|---|
| 基线 | **24.5 Hz**（论文 23.7） | 24.2 Hz（论文 23.3） |
| Pearson | **0.946** | 0.945（§24.3） |
| κ | **0.887** | 0.907（§24.3） |
| 判必需 我们/论文 | **4 / 5** | 5 / 6 |
| 判定一致率 | 0.996 | — |
| 效应差中位 | 0.019 | — |

（论文表 7E 有 280 行带 ID，其中 **1 行因缺段落被跳过**，实际比对 279 行——按项目规矩，跳过计数必须跟着结果一起报。）

**事先写定的三条预测，逐条对答案**：
1. 基线接近论文 23.7 → **24.5**，差 0.8 Hz ✓
2. aDN2 是否也被 aBN1 卡住？**事先不知道，两种结果都要报告** → **也被卡死**：
   aBN1（SAD093）单敲让 aDN2 归零（比值 **0.000**，论文 7E 也是 0.000），
   同一批段落里它对 aDN1 同样是 0.000。**两个梳理指令神经元共用同一个绝对瓶颈。**
3. 相关性与 aDN1 同量级 → Pearson 0.946 vs 0.945 ✓

**唯一一处判定不一致**：JO_EDM_14（JO-CM），我们 **0.810**、论文 0.737 —— 正好卡在 0.8 判据两侧的边缘情况。

我们判必需的 4 个里，除 aBN1 外全是 JON 输入神经元本身
（JO_FDP_5 0.671/论文 0.696、JO_EVL_1 0.734/0.715、JO_EDM_7 0.734/0.747）。

**集中度必须在同一批神经元上算**（§24.3 的 aDN1 只覆盖 304 个打过分的，直接拿来比是错的——
AGENTS.md 记过这一条）。在**同一批 595 个**上重算：

| 读出 | Gini | n80 | 效应 ≥0.2 |
|---|---|---|---|
| aDN1 | 0.921 | 44 | 4 |
| aDN2 | 0.881 | 68 | 4 |

aDN2 的效应稍微分散一些，但两者都只有 4 个神经元效应 ≥0.2，且共用同一个瓶颈。
**§24 那条"单一瓶颈"的结论对两个读出都成立**，不是 aDN1 特有的。

## 30. 把论文的对照实验做成滑块：打乱接线与参数稳健性（2026-09-19）【实测 + 工程】（`dodge/measure_perturb.js`、`dodge/export_nt.py` → `results/dodge/perturb.json`）

论文补充表 **1D**（打乱接线）和 **11A–F**（参数稳健性）我们一直没做。这两项恰好是所有空白里
> **后续（2026-09-19）**：11A–F 已在**全脑**上复现，见第 35 节——`w_syn −30%` 下 MN9_r 34.5 Hz vs 论文 33.47（差 3%），「同侧 MN9 比对侧弱」6/6 成立。1D 仍只在子回路上做过（全脑版需要能换权重的打乱方案，见第 35 节的做法）。

**最适合做成交互**的——游戏的 JS 大脑本来就有 `w0`/`w` 两份权重和 `rebuildWeights()`。

**先说清楚能比什么、不能比什么**：论文在**全脑 138,639 个神经元**上跑，这里是 **4,599 个的子回路**；
而且**论文没有公开打乱的具体做法**（补充表 1D 只给结果，没给方法）。所以下面比的是**定性方向**，
不声称复现论文的定量结果。我们的打乱定义写在 `brain.js` 的 `setShuffle` 里：
**保持每个神经元的出度和它那串权重，只把突触后靶点随机重排**。

### 30.1 打乱接线：信号几乎全没了【实测】

口径与 `dodge/measure_neurons.js` 完全相同（颗粒钉在头前 1.3 mm 持续接触 → 200 Hz，
2.5 s 取后 1.25 s 平均，种子 1/2/3）。打乱做 10 次（论文表 1D 是 100 次）：

| 通路 | 正确接线 | 打乱后（10 次） | 比值 |
|---|---|---|---|
| 糖 → MN9 | 82.9 Hz | **3.5 ± 4.2 Hz** | **0.043** |
| 水 → MN9 | 14.1 Hz | 1.0 ± 2.7 Hz | 0.072 |
| 梳理 → aDN1 | 59.8 Hz | 17.0 ± 18.6 Hz | 0.284 |

与论文同量级：表 1D 里 Zorro_l 是正确接线 102.2 Hz → 100 次打乱后 2.75 ± 7.17 Hz。
（注意那是**单个神经元**的发放率，我们读的是 MN9，不是同一个量，只能比数量级和方向。）

### 30.2 参数扰动：论文的判据是"判定是否翻转"，不是发放率变了多少【实测】

先按发放率看，子回路对参数相当敏感（糖 MN9 比值：权重 −30% → 0.85、抑制 −30% → 2.33、
谷氨酸改兴奋性 → 1.80；水通路更极端，权重 −30% 直接归零、抑制 −30% 涨到 6.85 倍）。

**但这不是论文的判据。** 表 11B–F 每行都有一列 "Same prediction as baseline?" ——
看的是**定性预测是否不变**。按这个口径重测（10 个真实神经元的敲除判定，比值 ≤ 0.8 = 必需）：

| 扰动 | 判定不变 | 翻转的神经元 |
|---|---|---|
| 权重 −30%（表 11B） | **9/10** | Clavicle 0.906 → 0.784 |
| 权重 +30%（表 11C） | **10/10** | — |
| 抑制 −30%（表 11D） | 7/10 | G2N-1 0.674→0.874、CB0277 0.74→0.893、CB0051 0.796→0.91 |
| 抑制 +30%（表 11E） | 9/10 | CB0277 0.74→0.863 |
| 谷氨酸改兴奋性（表 11F） | 7/10 | 同抑制 −30% 的那三个 |

**翻转的全部是贴着 0.8 判据两侧的边缘情况**（0.674→0.874 这种），没有一个是方向性反转。
结论：这个子回路对**突触权重缩放**相当稳健（9–10/10），对**抑制强度和谷氨酸符号**明显更敏感（7/10）。

### 30.3 工程

- `dodge/export_nt.py`（只读）导出子回路每个神经元的递质类型，**不动 `subcircuit_v2.json`**
  （单独写 `subcircuit_nt.json`，这样已发布结果的哈希不变）。子回路里 ACh 2,841 / GABA 1,005 /
  **谷氨酸 635（13.8%）** / 5-HT 80 / DA 24 / OA 12 / 未知 2。
- `brain.js` 新增 `setWeightScale` / `setInhibScale` / `setGlutExcitatory` / `setShuffle`，
  全部在 `rebuildWeights()` 里按固定顺序施加（顺序会影响结果，所以写死）。
- **一个差点漏掉的坑**：`run()` 原来解构的是 `this.post`，打乱后必须换成 `this.postArr`，
  否则开关看着生效、实际跑的还是原接线。审计里专门有一题查这个。
- 页面表格从 `perturb.json` 渲染，不写字面量。

**审计 77 → 89 题**，新增 12 题全部查"真的改了权重数组"而不是"标志位设上了"：
权重缩放系数、抑制只动负权、谷氨酸改后无负权且负权总量下降、打乱后 338,704/338,837 条靶点变了、
打乱保持多重集不变（只重排不增删）、取消后复原、复原按钮还原权重、两张表格已渲染。

## 31. 复核用户指出的数字不一致：Roundup 与 Zorro 卡在判据上（2026-09-19）【只做分析，不跑新仿真】（`screen/recheck_calls.py` → `results/screen/recheck_calls.json`）

用户看页面「除了玩游戏」那张表时指出：论文值与我们的值对不上（点名 FMIn、Roundup、水味觉 Usnea）。
查下来是**三个并存的数字都没标口径**，而且文档自相矛盾。

### 31.1 查出了什么

同一个 Zorro（CB0192），项目里同时存在三个数：

| 出处 | 口径 | 比值 | 判定 |
|---|---|---|---|
| report.md §14.5 的表 | R=6、未归一化 | 0.760 | 必需 ✅ |
| 游戏页面同名表 | R=6、**零参照归一化** | 0.850 | 不必需 ❌ |
| report.md §16.1 / `hub_scan` | R=12、未归一化 | 0.829 | 不必需 ❌ |

三处**都没写自己用的是哪种口径**，于是：
- report.md 自己前后矛盾：§14.5 的表写 Zorro「我们 0.76 必需 ✅」，§16.1 正文却写「我们（和论文）的单个敲除都判它不必需」。
- AGENTS.md 第 332 行说判必需、第 333 行说判不必需。
- 而「我们和论文**都**判它不必需」这句话**在任何口径下都是错的**——论文自己的值是 0.772，判必需。

页面上还有一句硬编码：「模型答错的 4 个（Rattle、FMIn、Usnea、Roundup）」——
那是**论文模型**答错的集合，而页面那一列显示的是**我们的归一化值**，我们答错的是
Rattle、FMIn、Usnea、**Zorro**。这正是本项目记录在案的头号失败模式：**手写的小结不是结果**。

### 31.2 四种口径并排（新脚本，只读）【实测】

`screen/recheck_calls.py` 从权威结果文件取数（不重新实现归一化），把 R∈{6,12} × {未归一化, 归一化}
四种口径并排。判据一律 ≤ 0.8：

| 类型 | 实验 | 论文 | R=6 未归一 | R=6 归一化 | R=12 未归一 |
|---|---|---|---|---|---|
| Clavicle | 必需 | 0.664 ✅ | 0.548 ✅ | 0.613 ✅ | 0.647 ✅ |
| G2N-1 | 必需 | 0.619 ✅ | 0.442 ✅ | 0.495 ✅ | 0.597 ✅ |
| **Roundup** | 不必需 | 0.667 ❌ | 0.740 ❌ | **0.828 ✅** | 0.747 ❌ |
| **Zorro** | 必需 | 0.772 ✅ | 0.760 ✅ | **0.850 ❌** | 0.829 ❌ |
| Rattle | 必需 | 0.864 ❌ | 0.827 ❌ | 0.925 ❌ | — |
| FMIn | 必需 | 1.314 ❌ | 1.327 ❌ | 1.484 ❌ | 1.339 ❌ |
| Usnea | 必需 | 1.230 ❌ | 1.365 ❌ | 1.527 ❌ | 1.089 ❌ |
| Bract / Fdg / Phantom | 不必需 | 全 ✅ | 全 ✅ | 全 ✅ | — |

（R=12 只有 6 个类型有值：`hub_scan` 的 stage B 只把 |1−比值| ≥ 0.05 的补到 12 个实现。）

**结论**：
1. **10 个实验类型里恰好 2 个的判定是口径依赖的：Roundup 与 Zorro。** 另外 8 个在四种口径下判定完全一致。
2. **我们**的比值全部落在 **0.740–0.850**，紧贴 0.8 判据（论文侧分别是 0.667 与 0.772，同样在判据附近但更低）。它们不是"算错了"，是**本来就在判据线上**。
3. **每种可比口径都得 6/10**，差别只在**答对的是哪 6 个**：未归一化答对 Zorro、归一化答对 Roundup，恰好互换一个。
4. 水味觉那张表没有问题：论文和我们都只错 Usnea，各 9/10，页面写的「错的是同一个 Usnea」属实。
   FMIn 也没有问题：论文 1.31、我们 1.33–1.48，两边都判不必需、都与实验不符，是论文自己指出的失败点之一。

### 31.3 改了什么

- **页面**：答错名单改成**从数据算**，不再硬编码；新增一段口径说明，写明「我们」一列是零参照归一化，
  并列出 Roundup/Zorro 在两种口径下的两组值。
- **report.md §14.5**：补口径标注，说明该表是 R=6 未归一化，与页面不同。
- **report.md §16.1**：删掉「我们和论文都判它不必需」这句错话，改为三组口径并列。
- **AGENTS.md**：同上，并加一条硬规矩——**引用 Roundup / Zorro 的比值必须同时说明实现数与归一化方式**。

**教训**：这不是算错，是**同一个量在不同口径下被并排展示而没有标注**。
本项目已经因为"混用归一化"栽过一次（§25.2 的 +0.21 vs +0.92），当时的结论是"引用比值时要说明归一化"——
这次说明还是漏在了页面和 §14.5 的表上。**判据附近的值最容易因口径翻转，那里的标注不能省。**

## 32. 两篇一直"拿不到全文"的文献：查到了什么、还差什么（2026-09-19）【文献 + 实测】

### 32.1 Ache et al. 2019（`vision/check_ache2019.py` → `results/vision/ache2019_check.json`）

以前报告里写的是"全文不可得，参数手选"。这次全网查下来**拿到了三样东西**（全文仍不可得：
cell.com 返回 403、Caltech 库只有元数据）：

**① 模型形式被证实**——该文的 GF 输入模型确实是
「LC4 提供的**角速度线性项** + LPLC2 提供的**角大小高斯项**」，与游戏 `encoding: "ache2019"` 的形式一致。

**② 一个真参数：角大小高斯的峰在 42°**（我们此前手选 45°）。已改成 42°。
实测这个改动的影响**在噪声内**：hop 起飞模式下 5 种子 × 90 s，闪避率 83.3% → 84.7%
（差 1.4 个百分点，二项标准误约 3.6）。**采用它是因为它是已发表值，不是因为它更好用。**
高斯宽度 15° 与峰值 200 Hz **仍是手选**——论文没给到。

**③ 连接组数字可以独立核对**，而且对得很好。论文重建的是**单侧** GF，所以按 GF 所在侧分开比：

| | 论文（单侧 GF） | FlyWire v783 左 / 右 | 比值 |
|---|---|---|---|
| LC4 神经元 | 55 | 54 / 50 | **0.98 / 0.91** |
| LPLC2 神经元 | 108 | 94 / 95 | **0.87 / 0.88** |
| LC4 突触 | 2,442 | 374 / 431 | 0.15 / 0.18 |
| LPLC2 突触 | 1,366 | 458 / 622 | 0.34 / 0.46 |

**神经元数对得很准，突触数低 2–7 倍。**
我本来准备用"连接表做过突触数阈值筛选"来解释后者，**一验就被否掉了**：
连接表 `Connectivity` 的最小值是 **1**，其中 **7,496,016 条边只有 1 个突触**，根本没有阈值。
所以这是**真实的口径差异**（FlyWire 的自动突触检测 vs 论文的人工 EM 重建、以及校对版本不同），
不能用筛选解释。差一点就把一个刚被证伪的解释写进结论。

### 32.2 Card & Dickinson 2008（`dodge/takeoff_timing.js` → `results/dodge/takeoff_timing.json`）

全文同样拿不到（cell.com 403、Caltech 库 metadata-only），但摘要给了**三条可核对的主张**：
1. 真果蝇在**起飞前约 200 ms** 开始一连串姿态调整，把质心摆到"腿一蹬就推离刺激"的位置；
2. 这套动作**不是前馈固定程序**——幅度与方向取决于果蝇当时的初始姿态；
3. 果蝇**即使最终不跳，也会先规划好起飞方向**。

我们的实现只对上了第 0 条（"逃向背离威胁的一侧"）。把差距量出来
（5 种子 × 90 s，**245 次起飞**）：

| | 我们 | 真果蝇（该文） |
|---|---|---|
| 巨纤维越阈 → 起飞的延迟 | **0 ms**（构造如此） | 约 200 ms 的姿态准备 |
| 起飞时最近球的距离 | 中位 27.5 mm | — |
| 起飞时的剩余撞击时间 | 中位 **477 ms** | — |

**时间预算是够的**（477 ms > 200 ms），也就是说加上 200 ms 的准备期在物理上并不会导致来不及躲；
但我们**完全没有建模**准备期、姿态依赖的方向、以及"不跳也规划"。这三条都是**明确的、可补的空白**，
不是模型能力的限制。

## 33. flyvis 集成检验：我们的视觉结论建立在 50 个模型里的 1 个上（2026-09-19）【实测】（`vision/ensemble_check.js` → `results/vision/ensemble_summary.json`）

Lappalainen et al. 2024 的核心主张是关于**集成**的——连接组约束下解不唯一，他们训练了一组网络并强调成员间的差异。
而本项目的 §18、§28.17、§28.18、§28.20 **全部只用了 `flow/0000/000` 这一个成员**，本机其实有 **50 个**（共 5.7 MB）。
所以那些结论可能只是成员 000 的性质。这一节把 50 个全跑一遍。

**做法**：逐成员导出（导出脚本会验证"权重只依赖源型/靶型/位移"这个卷积前提），
再对每个成员重跑 §28.17 的方向测定（8 方向 × 4 个时间频率，减静止基线）与 §28.18 的 LPLC2 三条判据。
**问题跑之前写定，不预设答案**。约 36 分钟，纯 CPU。

### 33.1 唯一站得住的：卷积前提

**50 个成员全部通过**逐成员验证，无一例外。所以「flyvis 是六边形卷积网络、整个视觉系统只有 2,355 个抽头」
这条是**集成层面的性质**，不是某个模型的偶然。§28.1 的结论不变。

### 33.2 「T4d 与 T5b 没有方向选择性」——**只是成员 000 的性质**

| 亚型 | 有方向选择性的成员 | 偏好方向（中位 / 范围） | DSI 中位 | 落在棱族 30°+60°k |
|---|---|---|---|---|
| T4a | 34/50 | 275°（3–357） | 0.481 | 28/34 |
| T4b | 31/50 | 87°（40–342） | 0.412 | 24/31 |
| T4c | 42/50 | 168°（2–277） | 0.842 | **13/42** |
| **T4d** | **37/50** | 203°（0–360） | **0.849** | 7/37 |
| T5a | 26/50 | 271°（95–306） | 0.681 | 16/26 |
| **T5b** | **18/50** | 267°（67–349） | 0.448 | 13/18 |
| T5c | 21/50 | 180°（0–335） | 0.855 | 8/21 |
| T5d | 17/50 | 328°（0–353） | 0.754 | 9/17 |

**T4d 在 37/50 个成员里是有方向选择性的，而且 DSI 中位高达 0.849**——比成员 000 里"选择性最强"的 T4c 还高。
T5b 也有 18/50。**§28.17 那句「文献的 a/b/c/d = 四个正交方向在 flyvis 里不成立」必须限定为「在成员 000 里不成立」。**

**偏好方向的跨成员离散度极大**（T4a 的范围覆盖几乎整个圆周），
「落在六边形棱方向族」这条在成员 000 里对每个选择性亚型都成立（差 0.7–11.1°），
但在集成层面只有 T4a（28/34）和 T4b（24/31）站得住，T4c 只有 13/42、T4d 只有 7/37。

### 33.3 LPLC2 判据：成员 000 属于少数派

| 判据 | 通过的成员 |
|---|---|
| A 匀速扩张 > 匀速收缩 | **17/49** |
| A' 加速逼近 > 时间倒放 | 11/49 |
| B 逼近 > 两种平移 | 11/49 |
| **三条全过** | **8/49** |

**成员 000 是那 8 个之一。** 也就是说 §28.18「按 Klapoetke 形式汇集背离中心的 T4/T5 能把逼近分出来」
这个结论，在集成里只有约 **16%** 的成员成立。

成员 000 的"有方向选择性亚型数"是 6/8，在 50 个里排第 11（同为 6 的并列 11–15 名；中位 5）——它不是极端异常值，
但在 LPLC2 判据上确实落在有利的一侧。

### 33.4 这对前面几节意味着什么

- **§28.1（六边形卷积、80 KB）**：不变，集成层面成立。
- **§28.17（T4/T5 方向）**：「T4d/T5b 无方向选择性」**限定为成员 000**；「偏好方向落在棱族」只在 T4a/T4b 上有集成支持。
- **§28.18（LPLC2 汇集）**：判据全过是 **8/49** 的少数情况，不能当作 flyvis 的普遍性质。
- **§28.20（晶格对齐）**：解剖锚定用的是**成员 000 的 T4/T5 方向**做功能锚点。既然方向在成员间离散度很大，
  这个锚点的稳固性取决于选哪个成员——**这一条现在是有条件的**。解剖那半边（左右轴、腹侧、前后轴）不受影响。
- **§28.20.1（保几何映射让「逼近 > 近距平移」翻转）**：用的是成员 000 的方向表，同样受此限制。

**方法学教训**：这是一个"**用了一个模型，却把结论说成了模型族的性质**"的典型。
flyvis 的论文本身就强调集成差异，而我们从一开始就只下载并使用了成员 000——
`vision/export_flyvis_js.py` 里硬编码着 `flow/0000/000`，一路沿用了十几节。
**凡是"某个预训练模型给出 X"的结论，都必须问一句：这个模型是从几个里挑的？**

## 34. 定掉一条挂了很久的未定论：Fly-Brain-AI 的 turn_drive 符号（2026-09-19）【实测】（`fba_turn_sign.py` → `results/fba_turn_sign.json`）

AGENTS.md 里这条一直记为「未定论」：作者的 `interfaces.py` 与论文草稿都说 `turn_drive > 0` 表示**向右**，
并报告「对侧逃逸」；但 `LocomotionBridge` 的代码是 `left_scale = 1 - 0.3*max(0, turn_drive)`，
正值缩小**左腿**幅度，身体应当转**左**。我们只用 1 个种子测过一次，按项目规矩不算定论。
现在补齐：3 个种子 × {真实, 打乱连接组} × {左注入, 右注入, 不注入}，判据跑之前写定。

**结果**【实测】（净侧移在起点朝向的本体坐标里，+y = 果蝇左侧）：

| 条件 | turn_drive | 净侧移 | 相对对照 |
|---|---|---|---|
| 对照（不注入） | −0.064 | −15.56 mm | — |
| 左 LPLC2，真实连接组 | **+0.352** | −10.74 mm | **+4.82 mm（偏左）** |
| 右 LPLC2，真实连接组 | **−0.533** | −17.16 mm | **−1.60 mm（偏右）** |
| 左 LPLC2，打乱连接组 | +0.011 | −3.48 mm | — |
| 右 LPLC2，打乱连接组 | −0.016 | −3.46 mm | — |

三条事先写定的判据**全部通过**：
- **C1** loom_left 的 turn_drive 为正 **3/3**、loom_right 为负 **3/3**
- **C2** 净侧移 left > right **3/3**
- **C3** 左右侧移差：真实 **+6.42 mm** → 打乱 **−0.02 mm**，效应完全消失

**结论**：`turn_drive > 0` **确实让身体转左**，代码是对的、作者文档写反了。
而且左侧 LPLC2 注入让果蝇转向**被刺激的那一侧（同侧）**，与作者报告的「对侧逃逸」**相反**。

**三条必须同时说明的限制**：
1. **绝对侧移读不出方向**。连不注入的对照都漂了 −15.56 mm——那是步态偏置
   （AGENTS.md 早就记过它们的 `turn=…deg` 指标被步态摇摆主导）。只有**相对对照**的差值才有意义。
2. **打乱连接组同时改变了整个运动**：打乱后的基线漂移只有 −3.47 mm，和真实网络的 −15.56 mm 差很远。
   所以打乱不是「只去掉 looming 反应」的干净对照；**能干净比较的只有左右差**，而那一项确实塌到了 0。
3. n = 3 个种子。

## 35. 复现论文补充表 11：参数扰动下预测还站得住吗（全脑）（2026-09-19）【实测】（`screen/robustness.py` → `results/screen/robustness/summary.json`）

§30 在 4,599 个神经元的子回路上做过这件事，这一节搬到**全脑**。

**先纠正我自己的一个误判**：我原先估这要 3 小时。查了补充表才发现 ST11 的口径是
**「糖 GRN @ 150 Hz 下哪些神经元响应」**（表 11B–F 的 182 行）和**「同侧 MN9 比对侧弱」**（表 11A），
**不需要做敲除**。所以实际是一次编译 + 6 种权重 × 6 个实现 = 36 段，每种扰动 39 s（谷氨酸那种 93 s），
峰值内存 2.3 GB。真正要 3 小时的是第三条预测「哪些神经元是必需的」，那条**没有做**。

权重通过 `device.run(run_args={syn.w: ...})` 逐次替换，**不重复编译**。

**结果**【实测】：

| 扰动 | 活跃神经元 | 保住的基线响应者 | MN9 左 | MN9 右 | P2 同侧弱？ | 与论文表逐个对照 |
|---|---|---|---|---|---|---|
| 基线 | 421 | — | 63.0 | 83.8 | ✓ | — |
| w_syn −30%（11B） | 243 | 242 / 421（58%） | 23.0 | **34.5** | ✓ | 25/38 都响应，r = 0.47 |
| w_syn +30%（11C） | 507 | **421 / 421** | 67.5 | 96.7 | ✓ | 42/48，r = 0.32 |
| 抑制 −30%（11D） | 520 | 420 / 421 | 108.0 | 126.3 | ✓ | 42/48，r = 0.26 |
| 抑制 +30%（11E） | 368 | 366 / 421 | 34.7 | 59.5 | ✓ | 42/48，r = 0.32 |
| 谷氨酸改兴奋性（11F） | **30,475** | 417 / 421 | 92.7 | 115.5 | ✓ | 44/48，r = −0.02 |

**三条结论**：

1. **一个很硬的定量对上**：w_syn −30% 下我们的 MN9_r 是 **34.5 Hz**，论文表 11B 写的是 **33.47 Hz**（差 3%）；
   对侧 23.0 vs 论文 22.0。同一个 ID、同一种扰动、同一个刺激频率，**不经任何拟合**。
2. **P2「同侧 MN9 比对侧弱」在 6/6 种条件下都成立** —— 与论文表 11A 的结论一致。
3. **P1「哪些神经元响应」大体保住，但分档很明显**：基线的 421 个响应者，
   w_syn +30% 保住 **421/421（100%）**、抑制 −30% **420/421（99.8%）**、谷氨酸改兴奋性 **417/421（99.0%）**、
   抑制 +30% **366/421（87%）**、w_syn −30% 只剩 **242/421（57%）**。
   方向上与论文「预测在参数扰动下不变」一致，但**减弱型扰动（权重调小、抑制调大）明显更伤**。
   > 【自查修正 2026-09-19】这里原先写的是「除 w_syn −30% 外其余四种都保住 ≥99.7%」——**错的**，
   > 抑制 +30% 只有 86.9%，同一节的表格里就写着 366/421。这个错数从台账扩散到了 `REPRODUCTION.md`、
   > `results/reproduction.json` 和 `docs/game.html` 共四处。现在这五个比例已在
   > `scripts/reproduction_data.py` 里逐个钉到结果文件上，`reproduction.py --check` 会拦住下一次手打脱节。

**一个论文没有报告、我们看到的现象**：**谷氨酸改兴奋性会让全脑失控**——
活跃神经元从 421 涨到 **30,475**（模型里 19.2% 的突触是谷氨酸能的，2,899,765 条）。
基线那 421 个仍然在响应（417/421），所以"预测不变"这一条形式上还成立，
但网络已经进到完全不同的状态。**这个模型的稳定性依赖谷氨酸是抑制性的。**

**必须说明的两点**：
- **逐个神经元的相关只有 r = 0.26–0.47**（谷氨酸那张是 −0.02）。也就是说"哪些神经元响应"大体对得上，
  但**各自响应多强对不太上**。可能的原因有刺激集合/侧别差异、v630→v783 的 ID 变更、
  以及只有 38–48 个神经元可比——**我没有去分辨是哪一个**，不做解释。
- 补充表 11B–F 的 182 行里**只有 38–48 行带 flyid**，其余是类型级汇总块，无法逐个对应。

**三个自己的 bug，都是当场抓到的**：
- MN9 的注释 `cell_type` 是 **CB0701**，不是 "MN9"。按类型名查会查到空，读数全是 NaN。
- 论文表 11B 给的 MN9_l（`720575940645521262`）是 **v630 的 ID，在 v783 里已变更**，模型里根本没有。
  改用同型 CB0701 的另一侧（`720575940618238523`）。
- 表 11C 的发放率列叫 `sugarR`，其余几张叫 `Firing Rate (Hz)`——解析器只认后者时那一张**静默读失败**。

## 36. 一次从最新往最早的结论倒查（2026-09-19）【工程 + 核对】

用户要求「从最新的结论往前排查，看看之前的结论是否需要更新」。这一节记这次倒查**查出了什么**。
（本项目的文档结构也在这次改了：**复现台账 `REPRODUCTION.md` 成为「复现了什么」的唯一事实源**，
本文件降为过程日志，移到 `docs/log/`。规矩写进 AGENTS.md。）

### 36.1 查出的 12 处

| # | 位置 | 问题 | 性质 |
|---|---|---|---|
| 1 | §0 第 4 条 | 写着「LC4 增益未标定、只有 0/200 两个值」 | **被 §27 推翻却没更新** |
| 2 | §4 表格 | 同一句话的另一处 | 同上 |
| 3 | §9.2 + §18 | 「逼近 > 近距平移 0/8」 | 建立在**已变形的点阵**上（§28.20 查出 `normalize()` 把基矢角 60°→122.6°） |
| 4 | §18 | 「格子对齐没有文献依据、只能全跑」 | §28.20 已用解剖钉死 |
| 5 | §25.6 | 「哪些结果没进游戏」表 | 过期：flyvis 已实时、闭环已做成对照、论文对照已做成滑块 |
| 6 | §23 | 机时账本 **17,628 段 / 9.88 h** | **第三次记少**，真值 18,799 / 10.56 h |
| 7 | §14.5 / §16.1 / AGENTS.md | Roundup 与 Zorro 的判定 | 三处互相矛盾，根因是**口径依赖且都没标注** |
| 8 | §24.3 / AGENTS.md | aDN1 基线 23.4 Hz | **一句话里混了两个实现数**（23.4 是 R=12，同句的 κ 是 R=6 的 24.2） |
| 9 | §28.17 / §28.18 / §28.20 | T4/T5 方向、LPLC2 判据 | **全部建立在 flyvis 50 个模型里的 1 个上**（§33） |
| 10 | §32.1 | 「突触数偏低是阈值筛选造成的」 | 我准备写进结论时**一验就被证伪**（连接表最小值是 1，有 749 万条单突触边） |
| 11 | `embodiment_plan.md` | 「是否有专门的眼平面投影坐标未核实」 | 已被证伪：Codex 的 `column_assignment` 就是，我们后来一直在用 |
| 12 | README / 两个页面 | 17,628 段 | 跟着 #6 一起过期 |

### 36.2 最重的一条：一个模型 vs 一个模型族

第 9 条值得单说。`vision/export_flyvis_js.py` 里硬编码着 `flow/0000/000`，
而 flyvis 自带 **50 个**预训练集成成员（就在本机，5.7 MB）。
把 50 个全跑之后（§33）：「flyvis 是六边形卷积网络」这条 **50/50 成立**，
但「T4d 与 T5b 没有方向选择性」**只是成员 000 的性质**（T4d 在 37/50 个成员里有，DSI 中位 0.849），
LPLC2 的三条判据**只有 8/49 个成员全过**，而成员 000 正是其中之一。

**凡是「某个预训练模型给出 X」的结论，都必须问一句：这个模型是从几个里挑的。**

### 36.3 三个结构性修复

这次没有只改数字，而是改了产生这些错误的机制：

1. **机时账本改成脚本产出**（`screen/compute_ledger.py`）。它原本是**报告正文里的一段临时 shell 循环**，
   所以已经错过三次（12,993 → 14,743 → 17,628）。新脚本按 key 去重，并带一列「秒/段」作自洽检查
   （各行 1.95–2.29，合计 2.02——段数或墙钟记错时这一列就会偏）。
2. **复现台账的数字加机器校验**（`scripts/reproduction.py` 的 `verify`）。台账本身也是手打的，
   同样会脱节。现在有 **27 个数字**逐一对结果文件核对（另有 5 个参数对源代码核对），**第一次跑就抓到第 8 条那个混用实现数的错**。
   这个校验已进 CI。
3. **台账登记阴性结果**。`status` 有 `negative` 与 `blocked` 两种，
   现在有 4 条明确的阴性结论（连线预测不了冗余、模型没有奖赏信号、嗅觉给不出转向、BANC 走不出节律）
   和 1 条「做不了」（Pugliese 的 Extended Data Fig 8，作者仓库里没有那个配置文件）。

### 36.5 倒查续：又查出 7 处（同日）

第一轮倒查收尾后继续往前查 §26–§35 与 README，又查出 8 处。**其中 2 处是结论级的。**

| # | 位置 | 问题 | 性质 |
|---|---|---|---|
| 13 | §35 结论 3 | 「除 w_syn −30% 外，其余四种扰动都保住 **≥99.7%** 的基线响应者」 | **结论级错误**。抑制 +30% 实际只保住 366/421 = **86.9%**，谷氨酸那种 99.0%。**同一节自己的表格里就写着 366/421**，正文与表格互相矛盾。错数已从台账扩散到 `REPRODUCTION.md`、`results/reproduction.json`、`docs/game.html`，共四处 |
| 14 | AGENTS.md §22.2 + 台账 `concentration` 条目 + 游戏页 `nStruct` 卡片 | 仍在引用 §24.3 **已宣布作废**的那版 JON 集中度（基尼 0.858 / G3 0.434 / 只给 326 个打分），并据它宣布「越集中 → 连线越能预测」**成立** | **结论级错误，而且方向相反**：用论文刺激名单重跑的真值是基尼 0.9224 / G3 0.288（596 个全打分），假设是**被推翻**的。报告正文与 README 早就是对的。最难看的一处是**游戏页上两张卡片对同一个事先声明的假设下了相反结论** |
| 15 | `scripts/reproduction.py` | `verify` 只对 `PAPERS` 生效，给 `FINDINGS` 条目加的 `verify` 被**无声吞掉**，`--check` 照样印「通过」 | **检查器自己在静默降级**（第 20 节那条规矩的又一个实例）。修好后当场抓到下一条 |
| 16 | 台账 `olfaction` 条目 | 字段名写成 `status_note`，不是 `status` | 那条阴性结论**一直没有状态**，没人发现——正是第 15 条修好之后第一个跳出来的 |
| 17 | §35 | 「**两个**自己的 bug」下面列了**三条** | 自洽性 |
| 18 | §29 | 没报「论文表 7E 的 280 行里有 1 行因缺段落被跳过」 | 违反第 20 节定的「跳过计数必须跟着结果一起报」 |
| 19 | §31.2 结论 2 | 「它们的比值全部落在 0.74–0.85」 | 同一张表里还有论文侧的 Roundup 0.667，落在区间外。已改成明写「**我们**的比值」 |

| 20 | `results/connectome_loop_frontend_looming/` | §26 那次运行的原始产物**被 §27 的标定运行覆盖**，目录里只剩 `gain = 19.8` 那一版 | **数据溯源缺陷**，与此前记过的「参数变体覆盖正典结果文件」同类，而 `connectome_vision_loop.py` 没有那道后缀保护。所幸 §27.0 加的 `exp_L`/`exp_R` 让 §26 的数字可以反算，**三个数字逐一复现**（见 §26 末的补记），所以是溯源问题、不是数字错 |

（另有 §33.3「成员 000 排第 11」补上并列区间 11–15，不单独计数。）

**这一轮的两条结构性修复**：

1. `scripts/reproduction.py` 的 `verify` 现在对 `PAPERS` 与 `FINDINGS` **都**生效，
   并且**两边都拒绝无法识别的字段名**——写错字段名不再被静默忽略。
2. 第 13 条那五个「保住比例」全部钉进台账的 `verify`，第 14 条的基尼 / G3 / n80 也钉了三个。
   核对的数字从 19 涨到 **27**。

**这一轮最值得记的一条**：第 14 条里，**报告正文是对的，错的是 AGENTS.md、台账和页面**。
以前查出的错几乎都是「正文写错、脚本是对的」；这次反过来——一条结论在报告里已经改写成**相反**的版本，
三个下游副本却停在旧版。**「唯一事实源」只有在下游真的从它渲染时才成立**；
AGENTS.md 那一条和游戏页 `nStruct` 那段都是**手写副本**，所以停在了旧版。
页面上会打架的两张卡片尤其说明问题：它们一张读数据、一张读手写文字。

### 36.4 顺带定掉 / 补上的

- **Fly-Brain-AI 的 turn_drive 符号**（§34）：挂了很久的「未定论」，3 种子 + 打乱对照全过，
  **代码对、文档错**，而且是转向**同侧**、与作者报告的「对侧逃逸」相反。
- **aDN2**（§29）：官方论文梳理通路的另一半，**零新仿真**（段落文件本来就存了全部活跃神经元的计数）。
- **补充表 11 的全脑复现**（§35）：`w_syn −30%` 下 MN9_r **34.5 Hz** vs 论文 **33.47**，差 3%。
- **Ache 2019**（§32.1）：拿到高斯峰 **42°**（此前手选 45°），并独立核对了连接组数字
  （LC4 神经元 55 → 54/50，比 0.98/0.91）。


## 37. 把论文补充表 10 的十行预测逐行对完（2026-09-19）【实测】（`screen/taste_interaction.py`、`screen/taste_grid.py`、`screen/responsive.py`、`screen/sufficiency.py`、`screen/jon_ce_f.py`）

补充表 10 是**论文自己的记分卡**：十类预测、164 项、总正确率 91.5%（去掉图 2 那一大块是 84.5%）。
拿它当清单比拿正文当清单干净——作者已经把"我们预测了什么、对照的是哪个实验"写死在表里了。
这一轮把台账里剩下的空白按这张表补完。

### 37.1 补充表 4：四味及其组合【实测】

台账里挂了很久的一条。论文口径是"把每种刺激标定到 MN9 = 40 Hz"，我先按这半句写了标定，
结果**苦味在 10–220 Hz 全程 MN9 = 0**，脚本悄悄退化成"选最低频"。回头读表头全文才发现是**两套规则**：

> GRN firing rates are chosen to elicit 40 Hz MN9 firing, **or reduce 40 Hz MN9 to 1 Hz**.

糖/水是**驱动型**（单独标到 40 Hz），苦/Ir94e 是**抑制型**（垫在糖上把 MN9 压到 1 Hz）。
改对之后标定是：糖 60 Hz → MN9 35.7、水 220 Hz → 38.3、苦 80 Hz → 0.0、Ir94e 60 Hz → 1.0。

**刺激名单这件事更值得记**。我一开始判断"论文 notebook 没公开苦/Ir94e 的名单"，
于是用 §24.2 对 JON 用过的招数反推了一版（看表 4 里高发放的类型）。后来**在官方 `figures.ipynb`
的 Figure 3 单元格里找到了原始名单**——一直就在仓库里。两版差 1 个 LB1c 与 3 个 LB2d。
现在两版都能跑（`TASTE_LIST=notebook`），共用同一次编译，台账以官方名单版为准。

**与论文比较必须剔除被刺激的 GRN**：它们两边都精确等于刺激频率，留着会把 Pearson 撑高。

| 条件 | 我们 MN9 | 论文 MN9 | 剔除 GRN 后 Pearson | 响应集 Jaccard | （反推名单版 MN9） |
|---|---|---|---|---|---|
| Sugar_only | 35.33 | 40.83 | 0.994 | 0.93 | 35.33 |
| Water_only | 38.33 | 40.4 | 0.999 | 0.866 | 38.33 |
| Bitter_only | 0.0 | 0.0 | 0.987 | 0.688 | 0.0 |
| Ir94e_only | 0.0 | 0.0 | 0.985 | 0.217 | 0.0 |
| Sugar_Bitter | 0.17 | 1.33 | 0.987 | 0.772 | 0.0 |
| Sugar_Ir94e | 0.83 | 1.12 | 0.963 | 0.754 | 1.5 |
| Water_Bitter | 18.83 | 10.07 | 0.991 | 0.685 | 15.67 |
| Water_Ir94e | 10.67 | 2.26 | 0.978 | 0.68 | 12.5 |

组合 ÷ 较强的单独：糖+苦 **0.005**（论文 0.033）、糖+Ir94e **0.023**（0.028）、
水+苦 **0.491**（0.249）、水+Ir94e **0.278**（0.056）。**糖那一侧对得很准，水那一侧我们的抑制明显更弱。**

### 37.2 Fig 3B–C：苦能压住强糖，Ir94e 压不住【实测 · 判据事先写死】

这是补充表 10 第 5 行（论文自报 4/4）。判据在跑之前就写进脚本：
**A. 最强糖下苦把 MN9 压掉 ≥50%；B. 同条件下 Ir94e 压掉 <50%。**

5×6 剂量网格（MN9 Hz，6 个实现）：

| 糖 Hz | 无抑制 | 苦20 | 苦40 | 苦80 | 苦160 | 苦220 | Ir20 | Ir40 | Ir80 | Ir160 | Ir220 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 40 | 2.67 | 0.33 | 0.0 | 0.0 | 0.0 | 0.0 | 0.33 | 0.0 | 0.0 | 0.0 | 0.0 |
| 80 | 57.0 | 47.0 | 31.0 | 5.33 | 0.0 | 0.0 | 54.33 | 38.33 | 7.0 | 1.67 | 0.33 |
| 120 | 83.0 | 67.67 | 58.67 | 33.33 | 1.67 | 0.0 | 75.67 | 62.67 | 55.0 | 18.0 | 10.0 |
| 160 | 83.33 | 80.67 | 71.67 | 59.67 | 11.0 | 1.67 | 83.0 | 80.33 | 73.33 | 59.33 | 43.0 |
| 220 | 93.0 | 90.0 | 88.0 | 77.33 | 35.67 | 16.33 | 94.33 | 92.0 | 84.33 | 78.67 | 67.33 |

糖 220 Hz 时 MN9 = 93.0：苦 220 Hz 压到 **16.3（降 82.4%）**，Ir94e 220 Hz 只压到 **67.3（降 27.6%）**。
**两条判据都成立。** 网格上两者的差距随糖强度单调拉开——糖 120 Hz 时苦 160 Hz 已经压到 1.7 Hz，
而 Ir94e 160 Hz 还剩 18.0 Hz。

诚实说明：两个 50% 的阈值是**我们**定的，论文只说了"苦能、Ir94e 不能"；频率档位受编译限制，
只取了论文 11×11 网格的一个 5×6 子集。

### 37.3 补充表 10 第 2、6 行：哪些神经元响应糖 / 响应水【实测 · 零新仿真】

段落文件里本来就存了**全部神经元**的脉冲计数，所以"某类型在该刺激下放不放电"直接查表就有，
不需要任何新仿真。

- **糖**（表 2 / Fig 1D）：与实验一致 **10/11**，唯一错项 **Usnea**——**和论文点名的错项完全相同**。
- **水**（表 5 / Fig 4A）：一致 **4/6**，两个错项 **G2N-1 与 Roundup**——**也正是论文自己列的那两个**。
- 与论文自己的"预测列"逐条一致（两条通路各 11/11 个类型）。

有个必须写明的口径：模型对这些类型**全部**预测"响应"，所以分数完全由实验侧有几个"不响应"决定。
**论文那一侧也是这样**——它的"Predicted to respond?"一列全是 Yes。这不是我们复现得好，
是这条预测本身就宽松。

### 37.4 Fig 2A / 补充表 3：106 个 SEZ 类型里哪些**足以**引发伸喙【实测 · 判据从论文表自身反查】

这是补充表 10 里最大的一块（论文自报 101/106），也是台账上一直空着的一块。

**判据是反查出来的，不是猜的**。表 10 那一行写着"以 50 Hz 激活 → 预测 MN9 > 0 Hz"，
但表 3 同时给了 10–200 Hz、左右各一列。把四种口径都在**论文自己的数字**上算一遍：

| 口径 | 论文自己 vs 光遗传 |
|---|---|
| **50 Hz，MN9_Left，>0** | **101 / 106** ← 与论文所报完全一致 |
| 50 Hz，左右取大 | 99 / 106 |
| 200 Hz，MN9_Left | 96 / 106 |
| 200 Hz，左右取大 | 92 / 106 |

只有第一行对得上，所以判据就是它。反查完才开跑。

刺激名单是官方的（`external/fly-brain/data/sez_neurons.pickle`，notebook Figure 2 用的就是它）：
106 个类型、372 个 ID，其中 308 个在 v783 模型里；**有 5 个类型在模型里一个神经元都没有**
（TH_VUM、Salivary_MN13、bamboo、gallinule、meteor），所以分母是 **101** 而不是 106。

**这一轮必须改一处框架**：`Screen` 把全部候选刺激神经元一次编译进来，原先照官方 `poi()` 把它们的
不应期一律置 0。糖/水/JON 的筛选里这没问题（候选全是感觉神经元、每段都全体受刺激），
但 SEZ 这 308 个是**中间神经元**——本段没被刺激的那些若也 rfc = 0，全脑动力学就被污染了。
加了 `RFC_GATE`：不应期也逐段门控，只有本段真被刺激的置 0。默认关，不动既有结果。

**结果**【实测】（MN9 左，Hz；每格 3 个实现）：

| 类型 | 我们 50 Hz | 论文 50 Hz | 我们 200 Hz | 论文 200 Hz | 光遗传 |
|---|---|---|---|---|---|
| roundup | 77.33 | 79.5 | 149.67 | 154.7 | 1.0 |
| diatom | 35.33 | 29.1333333333333 | 85.67 | 89.5 | 0.6 |
| bract | 35.0 | 33.6666666666666 | 62.33 | 63.9666666666666 | 0.8 |
| Fdg | 21.67 | 22.5333333333333 | 76.0 | 74.7666666666666 | 0.8 |
| sink_sync | 14.0 | 22.1666666666666 | 90.33 | 84.0666666666666 | 0.2 |
| clavicle | 12.67 | 10.5 | 79.67 | 77.5666666666666 | 0.5 |
| G2N_1 | 9.33 | 12.3666666666666 | 74.67 | 80.2 | 1.0 |
| kitty | 7.0 | 7.3 | 3.0 | 3.13333333333333 | 0.0 |
| rattle | 1.67 | 1.86666666666666 | 40.33 | 39.6 | 0.9 |
| Asteroid | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

- 发放率相关：**Pearson 0.993（50 Hz）/ 0.998（200 Hz）**，Spearman 0.99 / 1.00。
- 判定与论文**逐条一致 100/101**。
- 对光遗传实验：**我们 95/101，论文自己在同一批 101 个上是 96/101**。

**唯一比论文多错的是 FMIn**：我们 0.00，论文 0.37——判据线就在 0，它本来就贴着线。
另外 5 处不一致（kitty、marge、phantom、tentacular、usnea）**论文自己也错**，
而且是同样的方向。**能对到这个程度，说明整条管线（含 RFC_GATE 这个改动）没有走样。**

### 37.5 Fig 5G / 补充表 8：aBN1 只认 JO-CE，不认 JO-F【实测 · 判据事先写死】

判据照表 8 里 aBN1 那一行的数量级定死：**CE > 10 Hz、F < 5 Hz**。

| | 我们 | 论文表 8 |
|---|---|---|
| aBN1 @ JO-CE 150 Hz | **52.0 Hz** | 50.77 |
| aBN1 @ JO-F 150 Hz | **1.67 Hz** | 1.23 |

两条都成立。表 8 的全向量（剔除被刺激的 JON 之后 277 个神经元）两列 **Pearson 都是 0.999**。

顺带一个独立印证：这次的刺激名单直接取自官方 notebook 的 `neu_JON_CE`(70) 与 `neu_JON_F`(60)，
它们与 §24.3 **反推**出来的 146 个 JON 并集**完全相同**——当时那次反推是对的。

### 37.6 这一轮的教训

1. **"论文没公开"要先查完仓库再下结论。** 苦/Ir94e 的刺激名单我判断成"没公开"并反推了一版，
   其实它就在 `figures.ipynb` 里。JON 那次（§24.2）反推是必要的，这次不是。
   代价不大（两版结果接近），但"先假定没有"这个习惯本身要改。
2. **判据可以从论文表自身反查。** Fig 2A 的四种口径里只有一种能重现论文自报的 101/106，
   这比猜一个阈值可靠得多，而且反查过程本身是可核对的。
3. **把候选一次性编译进来是有代价的。** 不应期那一处（RFC_GATE）之前一直是对的，
   只因为过去三条通路的候选恰好都是感觉神经元。换成中间神经元就不对了——
   **"一直没出问题"不等于"这样做是对的"**。

### 37.7 补充表 1D：把打乱接线的对照搬到全脑【实测 · 判据事先写死】

§30.1 只在 4,599 个神经元的子回路上做过这件事。全脑版做法：Brian2 standalone 的拓扑是编译期
固定的，改靶点必须重编译——所以每个打乱版本重建一次模型（建模 + 编译只要 7–14 s），
泊松输入图样在所有版本间复用，差别只来自接线。

打乱做法（论文未公开，沿用 §30.1 那套，两边可比）：**保每个神经元的出度与权重，只把靶点列整体重排**。

刺激条件有独立佐证：论文表 1D 的 MN9_r 是 68.0 Hz，我们在糖 GRN @ 100 Hz 下不打乱时是 62.7 Hz。

| 神经元 | 我们·不打乱 | 我们·打乱（10 次均值） | 论文·不打乱 | 论文·打乱（100 次均值） |
|---|---|---|---|---|
| Zorro_l | 93.333 | 0.0 | 102.2 | 2.754 |
| G2N_1_l | 61.0 | 0.0 | 69.4 | 4.862 |
| rattle_l | 70.667 | 0.0 | 75.4333333333333 | 2.707 |
| usnea_l | 72.0 | 0.0 | 72.6 | 5.389 |
| clavicle_l | 44.0 | 0.0 | 54.0333333333333 | 3.597 |
| FMIn_l | 63.0 | 0.0 | 61.3 | 4.08 |
| MN9_r | 62.667 | 0.0 | 68.0 | 0.004 |
| phantom_l | 54.333 | 0.0 | 57.6 | 4.16 |
| roundup_l | 40.667 | 0.0 | 46.3333333333333 | 0.0 |
| Fdg_l | 37.0 | 0.0 | 38.3 | 0.487 |
| MN6_r | 32.667 | 0.0 | 31.7333333333333 | 0.0 |
| Fudog_l | 0.0 | 0.0 | 0.5 | 3.065 |
| Bract_l | 4.667 | 0.0 | 5.13333333333333 | 0.019 |

- 不打乱时我们与论文的 **Pearson 0.992**。
- 打乱后这 13 个**全部归零**；活跃神经元从 348 掉到 60–95。
- 判据 A（MN9_r 打乱后 < 不打乱的 10%）成立；判据 B（≥12/13 下降）成立。

**一处必须说明的差别**：论文打乱后的均值不是 0，而是 2.7–5.4 Hz，标准差却有 7–11——
也就是说 100 次里大多数是 0，**少数几次出现强响应**。我们只跑 10 次，抽不到这种罕见事件很正常。
所以"我们恒为 0"比论文更干净，**不能当成复现得更好**，只能说明抽样次数不同。

判据 B 的分母也就地改过一次：表 1D 的 15 个 ID 里只有 13 个在 v783 模型中，
按论文 14/15 = 93.3% 的比例折算成 ≥12/13。改动发生在只看到第一个打乱版本的 MN9 之后。

### 37.8 游戏 v7：把筛选结果做成能玩的东西（`dodge/missions.js`、`dodge/mutant_test.js`）

三件新玩法，共同点是**先测，再定规则**：

**① 任务模式**（七关）。每关给一个手术目标，只准动开关。关键在于怎么验证一关设计得对：
`node dodge/mission_test.js` 把每关都跑两遍——**不干预**与**参考解**，各 3 个种子 × 60 秒，
**通过线照实测分布定**。七关全部满足「参考解 3/3 通过、不干预 0/3 通过」。
有两关是照数据改过的：

- 「一个不够，两个才行」原本线画在 8 s，结果单敲也能过。实测逐次：不干预 6.1/8.6/11.2 s、
  单敲 Clavicle 5.4/8.1/5.1、单敲 G2N-1 4.8/6.8/7.9、两个一起 2.8/2.9/2.0。线改到 4 s 之后
  单敲 0/3、双敲 3/3。独立相乘的预期是 4.6 s，实测 2.6 s——**是协同，不只是叠加**。
- 「证明连接组真的在起作用」原本判闪避率，但打乱后逐次是 0.07/0.79/0.43，
  **波动大到有一次跟没打乱差不多**。判据换成起跳次数（打乱 18/5/0 vs 不干预 33/32/33，不重叠），
  也更贴近机制：打乱先打断的是 looming → 巨纤维那一路。

**② 光遗传手指**：点一下给真实神经元 200 Hz、0.6 s 的泊松驱动。实现时发现一个**真 bug**——
`brain.js` 的 `setRateNeurons` 对**非输入组**的神经元只写 `stimProb`，永远不会真的放电，
因为 `_updateStim` 只把输入组收进 `stimList`；而且输入组上的驱动会被每步的 `setRate` 覆盖。
两处都修了。实测：点亮左侧 LC4+LPLC2 → 巨纤维 206–254 Hz → 起飞；糖 GRN → MN9 111 Hz；
JO 左 → aDN1 72 Hz；LC16 双侧 → MDN 84 Hz（单侧不行，与全脑实测一致）。

**③ 盲盒突变体**：随机敲一个真实神经元，靠行为诊断。做之前先问了一个必须问的问题——
**这些敲除行为上真的看得见吗**？`node dodge/mutant_test.js`（60 s × 3 种子，六个指标，
判据是区间完全不重叠）：**10 个里只有 7 个能看出来**。看不出来的三个是 G2N-1、Zorro、CB0883——
**这正是全脑筛选那条结论的行为版**：单敲除常常什么也看不见。CB0883 在全脑里是枢纽
（单独敲 0.76，配上 Clavicle/G2N-1 塌到 0.24），Zorro 是实验证实「伸喙必需」的类型，
可它们单独被敲掉时果蝇看起来完全正常。

**还补了一道更快的关卡**：新加的一段里少写了一个右括号，模板的两条静态检查全过、
`smoke_test.js` 也全过，直到三分钟的真浏览器测试才报 `missing ) after argument list`。
现在 `smoke_test.js` 会把页面的**内联脚本**逐块 `new vm.Script()` 做语法检查——
重新注入那个 bug 验证过：一秒内 exit 1。


## 38. 用户提的三个问题，每个都翻出一处真缺陷（2026-09-19）【实测】

### 38.1 补充表 11 的抑制幅度是 ±50%，不是 ±30%【更正】

表 11A 的**分节标题**写着 "Decrease/Increase Inhibition 50%"，而 11D/11E 那两张表自己的表头
只写 "Neurons that respond to sugar stimulation"，不带幅度。§35 照着 w_syn 那两节的 30% 想当然了。

改成 ±50% 之后两个条件**都更接近论文**：

| | 我们 ±30%（旧） | 我们 ±50%（新） | 论文 |
|---|---|---|---|
| 抑制降低，MN9_r | 126.3 | **154.7** | 143.9 |
| 抑制增强，MN9_r | 59.5 | **36.2** | 19.1 |

### 38.2 「果蝇顶着围栏一直走」——墙从来没有接进任何感觉通路

用户看到果蝇走到场边会一直顶着围栏。查下来**不是"认不出墙"**：
`game_core.js` 的边界只是 step() 末尾的一次几何钳位，而手写视觉前端 `visualInput`
**只读球的世界坐标**算 dθ/dt，场景里其他东西一概不看。实测（无球、120 s × 3 种子）：
**92.8% 的时间贴着墙，最长一次连续 111 秒。**

用户随后指出架构上的问题：**"我们是 3D 空间，按果蝇视角投影出来的画面里肯定有墙"**。
这条批评是对的，而且那条路径**本来就有**——`eyecam.js` 用 `THREE.CubeCamera` 从果蝇头部
渲染**整个 3D 场景**，墙、看台、别的果蝇全在里面，以后加任何物体也都会自动在里面。
它默认关着，理由写在 §28.19：对 **2.5 mm 的球**它在 45 mm 外读数恒为 0。

于是把摄像机的**原始投影**（采样成 721 个小眼之前的那张图）画到页面上，并实测了墙：

| 距离墙 (mm) | LPLC2 中位 | 峰值 |
|---|---|---|
| 100–120 | 35.4 | 85.8 |
| 60–80 | 42.6 | 126.0 |
| 45–60 | 23.1 | 48.1 |
| 15–30 | 10.9 | 200.0 |

**静止时读数恒为 0**（说明前端本身没错），但"朝墙走"（中位 34.2、p95 140.6）
与"背墙走"（23.5 / 111.4）**几乎分不开**。所以真正的缺陷不是"墙没接进去"，而是
**这套 LPLC2 汇集没有对自体运动做补偿**——走路本身就制造全场光流假逼近，把真信号淹掉。
真果蝇有平衡棒与传出拷贝，我们的模型里没有。

### 38.3 「只提供物理量，绝不写死判断逻辑」——这条原则成立，但有前提

用户提出的原则：**"果蝇看到的任何物体都由它大脑自行决策，我们绝不写死任何判断逻辑，
只负责提供必需的物理要素，比如触感、冷热"**。

第一次按这条原则做就失败了：给"触角碰到围栏 → JO"，果蝇**完全没反应**
（贴墙率 85.6% → 85.6%，逐位相同）。原因是 JO 在 v2 子回路里**只通到梳理指令 aDN1**。

`dodge/sensor_reach.py` 在**全脑**上查清了出路（≥3 突触的边，最短跳数）：

| 感觉通道 | 数量 | DNa01 | DNa02 | 巨纤维 | MDN | aDN1 |
|---|---|---|---|---|---|---|
| head bristle | 305 | 2 | 2 | 2 | 2 | 2 |
| thermosensory | 29 | 2 | 2 | 3 | 2 | 2 |
| hygrosensory | 74 | 3 | 3 | 3 | 3 | 2 |
| wind_gravity | 481 | 2 | 2 | 2 | 2 | 2 |
| auditory | 387 | 2 | 2 | 1 | 2 | 2 |

**头部刚毛（真正的触觉感受器，305 个）到转向/逃逸只要 2 跳**，温度 2–3 跳。
通路是有的，只是 v2 裁子回路时没把它们当输入。于是重裁了 **v3**（5,563 神经元，v2 的 1.21 倍），
把 TOUCH（头部刚毛）/ THERMO（温度）/ HYGRO（湿度）三路加进输入。

直接测刚毛驱动：**TOUCH 左 200 Hz → DNa02 左 30 Hz、DNa01 右 9 Hz**——真的驱动转向。

对局实测（无球、60 s × 2 种子）：

| 条件 | 走过的格子 | 路程 (mm) | 贴墙时间 | 起跳 |
|---|---|---|---|---|
| v2 · 什么都不给 | 9 | 156 | 85.6% | 0 |
| v2 · 触感→JO | 9 | 156 | 85.6% | 0 |
| v3 · 触感→头部刚毛 | 31.5 | 603.5 | 85.6% | 0 |
| v3 · 什么都不给 | 9 | 156 | 85.6% | 0 |
| v2 · 围栏视觉（手写） | 16 | 1672 | 0.0% | 16.5 |

- 触感送到 **JO**（v2 唯一的机械感觉）：**完全无效**——没有通路就没有行为。
- 触感送到 **头部刚毛**（v3）：走过的格子 **9 → 31.5**、路程 **156 → 603 mm**，
  **中间没有任何我们写的判断逻辑**。
- 手写的"围栏视觉"路程最长（1672 mm），但走过的格子反而更少（16）——因为它靠起飞解决问题。

**途中还纠正了自己的一个指标错误**：第一版用"贴墙时间占比"，而它**分不出"钉死在一点"
和"贴着墙滑行"**——两者 `S.wall` 都 > 0。按那个指标，触感"没用"（85.6% → 85.6%）；
换成走过的格子数才看出来果蝇其实在沿墙移动。**指标选错，阴性结果就是假的。**

### 38.4 「我能训练它下五子棋吗」——能，而且对照结果是阴性的

用户问能不能训练果蝇下五子棋。能，但**训练一个读出层正是那三个刷屏项目被批评的地方**
（Mineault：读出层足够灵活，连接组有没有起作用就说不清了）。所以做成**水库计算 + 对照实验**：
果蝇脑里一个突触都不训练，只训练最后一层线性读出，然后把同一套训练在四组特征上各做一遍。

数据：老师自对弈 500 局 → 12,270 个局面，**按整局切分**训练/测试（同一局的相邻局面相关）。
规则含黑方禁手（长连 / 四四 / 三三）。

| 用什么特征训练读出层 | 维数 | 测试 top1 | top5 | 中位 r | 训练 top1 |
|---|---|---|---|---|---|
| 随机猜（候选点均匀） | — | 0.017 | — | — | — |
| 直接看棋盘（不经过任何网络） | 450 | **0.1745** | 0.4129 | 0.7206 | 0.2058 |
| 果蝇脑 · 真实连接组 | 3537 | **0.0244** | 0.0774 | 0.0349 | 0.053 |
| 果蝇脑 · 打乱接线 | 3537 | **0.0178** | 0.0983 | 0.1011 | 0.0511 |
| 果蝇脑 · 真实连接组 + 保拓扑编码 | 3537 | **0.0248** | 0.1068 | 0.0401 | 0.0406 |
| 棋盘 + 果蝇脑 拼接 | 3987 | **0.0805** | 0.3433 | 0.5706 | 0.185 |

- **判据 A（真实接线有贡献）不成立**：真实 0.025 vs 打乱 0.018，差 0.007。
- **判据 B（脑子加工出新东西）不成立**：直接看棋盘 0.174，是果蝇脑的 7 倍。
- 拼接反而更差（0.081）——多出来的 3,537 维只是噪声。
- **连"保拓扑编码"也救不回来**（0.025）：按输入神经元的真实胞体位置铺棋盘，
  让相邻格子落到空间相邻的神经元——这是为了排除"随机分配打散了邻接关系"这个我们自己造成的缺陷。

途中修的两个真 bug，都值得记：
1. **水库必须是确定性函数**。不固定泊松随机流的种子时，同一个棋盘每次给的特征都不同
   （269 个神经元读数不同），读出层只能去拟合噪声——第一版训练 0.194 / 测试 0.021。
   `brain.js` 为此加了 `reseed()`。
2. **导出时把 sd 四舍五入到 4 位小数**，1,861/3,537 个从不放电的神经元 sd 变成 0，
   浏览器里除零 → NaN → **一个合法着都选不出来**（棋盘上一子未落）。

**读出层的准确率不等于棋力，所以让它们真下了 40 局**（含执黑执白对调）：

| 黑方 | 白方 | 黑胜 | 白胜 | 平均手数 |
|---|---|---|---|---|
| fly_intact | random | 16 | 4 | 104.1 |
| random | fly_intact | 3 | 17 | 90.3 |
| fly_intact | teacher | 0 | 20 | 9 |
| teacher | fly_intact | 20 | 0 | 8 |
| fly_shuffled | random | 9 | 11 | 95.8 |
| random | fly_shuffled | 5 | 15 | 80.5 |
| fly_intact | fly_shuffled | 0 | 20 | 73.7 |
| fly_shuffled | fly_intact | 2 | 18 | 92.4 |

**两个判据给出了不同答案，两个都记在这里**：
- 按「打随机的胜率」：真实接线 **33/40**、打乱接线 **24/40**，差 22.5 pp，
  越过事先定的 15 pp 线 → 判「连接组对棋力有贡献」**成立**。
- 但正面交锋 **18/40（约五五开）**，而且这 40 局里**执白的一方赢了 38 局**——
  先后手效应（黑方有禁手）**远大于**两个脑之间的差别。

诚实的说法：真实接线可能比打乱版少犯一点错，但这点差别小到被先后手淹没；
而两者都被那个几十行的启发式老师 **0:40** 完胜，平均 8–9 手就输。
**读出层 top1 上（0.0244 vs 0.018）本来就看不出差别，这与对局结论一致。**


## 39. 补上补充表 11 的第三条预测：每种扰动下重做整轮敲除筛选（2026-09-19）【实测】（`screen/robust_knockout.py`）

§35 只做了前两条（响应集、同侧 MN9 更弱），第三条「哪些神经元是伸喙必需的」一直空着，
因为它要在**每种扰动下重做整轮敲除筛选**。这一节把它补完：**6,494 段全脑仿真、3 小时、峰值 3.2 GB**。

**论文口径里有一处最容易漏掉的地方：每种扰动重新标定了刺激频率。**
表 11A 的 "Experiment" 那一列写得很清楚——突触弱了就把输入调高、强了就调低，
让基线回到可比的位置，再看判定翻不翻：

| 扰动 | 刺激频率 | 我们的基线 MN9 | 与默认判定一致（我们） | 论文 | 翻转的类型 |
|---|---|---|---|---|---|
| 默认 | 50 | 17.3 | — | — | — |
| w-30 | 115 | 7.8 | **8/10** | 8/10 | Rattle、Zorro |
| w+30 | 30 | 23.0 | **6/10** | 7/10 | Clavicle、G2N-1、Rattle、Zorro |
| inh-50 | 30 | 21.2 | **8/10** | 8/10 | FMIn、Zorro |
| inh+50 | 100 | 17.5 | **8/10** | 7/10 | Fdg、G2N-1 |
| glut_exc | 45 | 30.2 | **7/10** | 7/10 | Fdg、Rattle、Zorro |

**我们 [8, 6, 8, 8, 7] vs 论文 [8, 7, 8, 7, 7]——5 个里 3 个完全吻合，其余差 1，平均绝对差 0.4。**

做法上值得记的：一次编译（FREQS = 30/45/50/100/115，R = 6，21 个糖 GRN），
权重按扰动用 `device.run(run_args={syn.w: ...})` 逐块替换，**不重复编译**；
某个实现里该神经元本来就不放电时跳过那一段（沉默一个不放电的神经元恒等于基线）。
归一化沿用 §14 的零参照（同一实现下所有敲除的 MN9 中位数）。

**翻转最多的是 Zorro（5 个扰动里翻了 4 次）与 Rattle（3 次）**——
这与 §16 那条「10 个实验类型里恰好 2 个（Roundup 与 Zorro）的判定随口径翻转」**互相印证**：
同一批神经元，在换实现数、换归一化、换参数扰动时都是最先松动的那几个。


## 40. 加了新的感觉通道，就得先量它有没有落点（2026-09-19）【实测】（`dodge/sensor_drive.js`）

§38.3 的教训是「给了物理量，如果子回路里没有那条通路，就不会有行为」。
所以给 v3 加完触感 / 温度 / 湿度之后，第一件事是把**每一路**单独驱动一遍，
看六个运动读出组（DNa01/02、巨纤维、MDN、aDN1、MN9）里有没有哪个被推起来。
判据：任一读出 > 5 Hz。

| 感觉通道 | 左/右神经元数 | 有没有落点 | 最低生效条件 | 驱动到的运动读出（Hz） |
|---|---|---|---|---|
| LC4（视觉·角速度） | 54/50 | ≤200 Hz 就有 | 单侧 100 Hz | DNa01右 20　DNp01左 116　DNp01右 101 |
| LPLC2（视觉·角尺寸） | 108/102 | ≤200 Hz 就有 | 单侧 100 Hz | DNa01右 29　DNa02右 26　DNp01左 123　DNp01右 137 |
| LC16（视觉·后退） | 77/74 | ≤200 Hz 就有 | 单侧 100 Hz | DNa01右 23　DNa02右 22 |
| 糖/水味觉 GRN | 64/58 | ≤200 Hz 就有 | 单侧 100 Hz | MN9左 77　MN9右 132 |
| 苦味 GRN | 21/21 | **没有落点** | — | — |
| 触角 JO | 229/204 | ≤200 Hz 就有 | 单侧 100 Hz | aDN1右 8 |
| 头部刚毛（触感） | 150/155 | ≤200 Hz 就有 | 单侧 100 Hz | DNa01右 16 |
| 温度 | 13/16 | 只有高频才有 | 单侧 400 Hz | DNp01右 7 |
| 湿度 | 39/35 | **没有落点** | — | — |

三条结论：
- **触感在 100–200 Hz 就有落点**（单侧 200 Hz → DNa02 左 30 Hz），这正是它能让果蝇绕开围栏的原因。
- **温度要 400 Hz 以上**才推得动（双侧 400 Hz → DNa02 左 21 Hz），在合理刺激强度下等于没有。
  **湿度完全没有落点**，给到 600 Hz 也推不动任何运动输出。
- **苦味「没有落点」是对的**：它是抑制性的，单独给本来就不该驱动任何东西——
  它的作用是把糖驱动的 MN9 压下去（§37.2 复现过：最强糖下苦压掉 82.4%、Ir94e 只压 27.6%）。

还有一条本身就有意思的：**触感双侧同时给反而更弱**——200 Hz 双侧时六个读出全是 0，
而单侧 200 Hz 能把 DNa02 推到 30 Hz。左右对称的驱动把转向所需的左右差抵消了。
**这不是 bug，是回路本来的样子**，也解释了为什么「顶着墙」时一侧触角先碰到才有用。


## 41. 游戏换到子回路 v3：让「只给物理量」这条原则在页面上真的成立（2026-09-19）【工程 + 实测】

§38.3 查明「触感送到 JO 完全无效，因为 JO 只通到梳理」之后，v3 就一直只在命令行里。
这一节把页面也切过去——但**换子回路等于换掉所有已发布数字的底座**，所以先把该重测的重测一遍。

### 41.1 保真度：v3 与 v2 持平

用 v2 那 9 个全脑参考条件同时跑两版（`python dodge/subcircuit_v3.py compare`）：

| | 神经元 | 连接 | 模式一致 | 平均 MAE |
|---|---|---|---|---|
| v2 | 4,599 | 338,837 | 3/9 | 6.41 Hz |
| v3 | 5,563 | 432,437 | **4/9** | 6.94 Hz |

换句话说：多了三路输入、多了 21% 的神经元，**对原有通路的保真度没有变差**。

### 41.2 敲除比值：两版几乎一样

| 神经元 | v2 糖 | v3 糖 | v2 水 | v3 水 |
|---|---|---|---|---|
| Roundup | 0.05 | 0.07 | 0.11 | 0.09 |
| G2N-1 | 0.67 | 0.53 | 1.07 | 0.89 |
| Clavicle | 0.91 | 0.93 | 0.01 | 0.00 |
| CB0277 | 0.74 | 0.72 | 1.08 | 1.01 |
| CB0051 | 0.80 | 0.87 | 0.02 | 0.00 |
| Zorro | 1.03 | 1.04 | 0.92 | 0.82 |
| Phantom | 0.97 | 0.93 | 2.06 | 1.94 |
| Rattle | 1.13 | 1.11 | 0.98 | 1.00 |
| CB0883 | 1.07 | 1.01 | 1.00 | 1.00 |
| aBN1 | 1.00 | 1.00 | 1.00 | 1.00 |

最大的变化是 G2N-1（糖 0.67 → 0.53）与 Zorro（水 0.92 → 0.82），方向都没变。

### 41.3 七关任务全部仍然成立，突变体从 7/10 变 8/10

`SUB=subcircuit_v3 node dodge/mission_test.js 60 3`：**七关全部「参考解 3/3 通过、不干预 0/3 通过」**，
和 v2 逐关一致。所以切换不会让任何一关失效。

突变体可诊断性从 **7/10 涨到 8/10**，变化的三个是：Zorro（看不出→看得出）、Rattle（看得出→看不出）、CB0883（看不出→看得出）。
**CB0883 变得可诊断值得一提**：它在全脑里是枢纽、在 v2 子回路里完全惰性，
v3 多留下的那部分旁路让它的敲除重新在行为上露了头。

### 41.4 页面上现在能做什么

- **触感**：默认开。触角碰到围栏 → 头部刚毛机械感觉神经元 → 连接组自己决定。
- **温度 / 湿度**：可以在场地中央放热源或潮湿区，强度按高斯衰减直接喂进 29 个温度 / 74 个湿度感受器。
  **但页面上明写着它们推不动**（§40：湿度完全没有落点、温度要 400 Hz 以上）——
  这两个开关的作用就是让人看到「给了物理量不等于有行为」。

### 41.5 这一轮踩到的两个坑

1. **v3 导出时漏了 `validation` 字段**，页面那张「子回路 vs 全脑」的图直接 `SUB.validation.map(...)`，
   于是整段 three.js 初始化被异常打断，复眼装配卡住不动。
   `node --check` 和 smoke 都过——**因为它是运行期的数据缺失，不是语法问题**。
   是浏览器测试的超时把它逼出来的。
2. **gomoku 的读出层是在 v2 特征上训练的**，`col_idx` 指的是 v2 的神经元下标，换子回路就全错位。
   所以整条五子棋管线（特征提取 / 训练 / 对局）都加了 `SUB` 环境变量与文件名后缀，在 v3 上重跑了一遍。
   顺带修正一处口径：特征里的「输入神经元」原来写死成 v2 那 12 组，v3 的三路新输入会被当成下游留在特征里；
   改成从 `SUB.meta.inputs` 读，剔除数从 1,062 变成 1,470。


### 41.6 一次自我推翻：v2 上「连接组对棋力有贡献」在 v3 上翻盘

整条五子棋管线在 v3 上重跑之后，**对局结论完全反过来了**：

| | 真实接线 打随机 | 打乱接线 打随机 | 正面交锋（真实胜） | 打老师 |
|---|---|---|---|---|
| 子回路 v2 | **33/40** | 24/40 | 18/40 | 0/40 |
| 子回路 v3 | 26/40 | **40/40** | **0/40** | 0/40 |

v2 上真实接线比打乱高 22.5 个百分点，越过了事先定的 15 pp 线，当时判「连接组对棋力有贡献」**成立**；
v3 上打乱接线反而全胜，正面交锋真实脑 **0:40** 被完胜。

**换一版子回路就翻盘，说明 v2 上那个差别不可重复，是噪声。**
结论回到最朴素的那个：**连接组对下棋没有贡献**。这与读出层的准确率本来就一致
（真实 0.021 vs 打乱 0.019，两版都看不出差别）——当时是对局胜率那一个指标在给出相反信号，
而它的样本量只有每组 20 局。

这一条值得单独记，因为它推翻的是**我们自己刚写下的判定**。
台账里那条的状态也从「部分复现」改成了「阴性」。

训练侧在 v3 上则完全复现了 v2 的结论：

| 特征 | v2 测试 top1 | v3 测试 top1 |
|---|---|---|
| 直接看棋盘 | 0.1745 | 0.1745 |
| 果蝇脑 · 真实连接组 | 0.0244 | 0.0213 |
| 果蝇脑 · 打乱接线 | 0.0178 | 0.0190 |
| 棋盘 + 果蝇脑 拼接 | 0.0805 | 0.0786 |
| 随机猜 | 0.0171 | 0.0171 |


## 42. 复查 Fly-Brain-AI 气味效价的「4/6」：其实只有 2/6 是实打实的（2026-09-19）【只读，零新仿真】（`fba_odor_recheck.py`）

§10.5 记了「6 条判据复现 4 条，DM1 那两条失败」，但没说为什么，也没检查通过的那四条有多硬。
这一节只读已有的 24 个 checkpoint，不跑任何新仿真。

**问题 1：失败是不是因为 DM1 让全脑失控？**（§11.4 测过 35 个 DM1 ORN @10 Hz 会在 25 ms 内
点着约 8,300 个神经元）——**否掉了**。DM1 与 DM5 条件下读出层的活动几乎一样：
**16.7 Hz vs 16.2 Hz**、活跃读出各约 50 个。
（限制：checkpoint 里只有解码器读出那约 350 个神经元的统计，**不能据此排除全脑层面的失控**，
只能说"读出没被打爆"。）

**问题 2：通过的四条里有两条是「真实 vs 打乱连接组」——这种对照有多硬？**
查出来的结果比预想的严重：**打乱臂的读出完全不放电**——

| 条件（seed 42） | 读出均值 Hz | 活跃读出 | turn_drive |
|---|---|---|---|
| DM1_left_real | 16.42 | 50 | -0.1321 |
| DM1_left_shuffled | 0.0 | 0 | 0.0 |
| DM1_right_real | 16.67 | 51 | -0.1146 |
| DM1_right_shuffled | 0.0 | 0 | 0.0 |
| DM5_left_real | 16.91 | 50 | -0.0595 |
| DM5_left_shuffled | 0.0 | 0 | 0.0 |
| DM5_right_real | 15.81 | 48 | -0.1154 |
| DM5_right_shuffled | 0.0 | 0 | 0.0 |

24 个 checkpoint 里所有 shuffled 条件都是 **0.0 Hz / 0 个活跃**。
**对照组直接死了，那么任何非零效应都能通过这类判据。**
6 条判据里有 3 条属于这一类（`connectome_specificity`、`DM1_connectome_specificity`、
`DM5_connectome_specificity`），其中 2 条算在了「通过」里。

**所以诚实的分数是：原始 4/6，扣掉空对照后实质 2/6**（只剩 `DM5_aversive_turning`
与 `opposite_valence` 两条）。台账里这一条已经按这个口径改写。

顺带印证了 §10.5 里那句「所有条件的转向都被约 −0.11 的共同偏置主导」：
所有真实条件的 turn_drive 中位数是 **−0.10**。

**这一节的方法论意义**：打乱连接组是这个项目最常用的对照，但它有效的前提是
**打乱之后网络还活着**。§34 已经记过一次相近的坑（打乱同时改变了整个运动，
所以不是"只去掉looming响应"的干净对照）；这次是更极端的版本——打乱之后直接不放电。
**以后凡是引用「真实 vs 打乱」的判据，都要先报告打乱臂本身的活动水平。**

