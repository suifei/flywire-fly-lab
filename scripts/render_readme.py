#!/usr/bin/env python3
"""README 的中英两版。

- `README.md`（中文，主版本）：本脚本负责顶部的语言切换、导言与主要结论第 1–4 条（<!-- intro -->）、
  「它做不到什么」表（<!-- limits -->）、「作者自查出的错误」（<!-- audit -->）；其余几节仍由 scratch/patch_readme_*.py 渲染。
- `README.en.md`（英文）：**整份**由本脚本渲染。数字与中文版取自同一批结果文件，不经人手。

用法：python3 scripts/render_readme.py            写两份
      python3 scripts/render_readme.py --check    只核对：两份 README 与结果文件脱节就退出码 1（CI 里跑）
改了任何结果文件、或跑过 scratch/patch_readme_*.py 之后，再跑一次本脚本。
"""
import csv, json, re, sys
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
J = lambda p: json.loads((ROOT / p).read_text())
pct = lambda v: f"{v * 100:.1f}%"
wl = lambda r: f"{r['win']}–{r['loss']}" + (f"–{r['draw']}" if r.get("draw") else "")
PAGES = "https://suifei.github.io/flywire-fly-lab"

# ───────────────────────── 数据：全部取自结果文件 ─────────────────────────
LEDGER = J("results/screen/compute_ledger.json")
SUGAR = J("results/screen/summary.json"); WATER = J("results/screen/water/summary.json"); JON = J("results/screen/jon_paper/full_summary.json")
CONC = J("results/screen/concentration.json"); CONC_JON = J("results/screen/jon_paper/concentration_full.json")
SVF = J("results/screen/structure_vs_function.json")
NR = J("results/dodge/neuron_ratios_fullbrain.json"); PHANTOM = next(n for n in NR["neurons"] if n["key"] == "Phantom")
V3 = J("results/dodge/subcircuit_v3.json")["meta"]; V5 = J("results/dodge/subcircuit_v5.json")["meta"]
# 快速开始的示例输出：原始结果 results/sugar_brian2/ 不入库（里面有本机路径），只把要用的几个数抽进入库的 results/readme_quickstart.json；CI 里读后者
QS = ROOT / "results/readme_quickstart.json"
if (ROOT / "results/sugar_brian2/summary.json").exists():
    _r = J("results/sugar_brian2/summary.json"); _run = _r["runs"][0]; _ro = {r["name"]: float(r["baseline"]) for r in csv.DictReader((ROOT / "results/sugar_brian2/readout.csv").open())}
    _q = {"source": "results/sugar_brian2/（" + _r["cmd"] + "）", "n_neurons": _run["n_neurons"], "sim_s": _run["sim_s"], "active_neurons": _run["active_neurons"], "MN9_left": _ro["MN9_left"], "MN9_right": _ro["MN9_right"],
          "other_readouts_all_zero": all(v == 0 for k, v in _ro.items() if not k.startswith("MN9"))}
    _txt = json.dumps(_q, ensure_ascii=False, indent=1) + "\n"
    if "--check" not in sys.argv and (not QS.exists() or QS.read_text() != _txt): QS.write_text(_txt)
Q = json.loads(QS.read_text()); RUN = {"n_neurons": Q["n_neurons"], "sim_s": Q["sim_s"], "active_neurons": Q["active_neurons"]}; READOUT = {"MN9_left": Q["MN9_left"], "MN9_right": Q["MN9_right"]}
FEC = J("results/vision/front_end_compare.json")["摘要"]
LEARN = J("results/learn/learn_summary.json")
GOM = J("results/gomoku/lines_summary.json")
LIFE = J("results/dodge/life_summary.json")
NT = J("results/dodge/nature_test.json")["tests"]; NL = J("results/learn/nature_life.json")["worlds"]["nature"]["mean"]
ECO = J("results/eco/summary.json")
EXP_JON = next(r for r in CONC if r["name"].startswith("JON"))["experiment"]          # 「1/1 可测…」——对实验的得分与刺激名单无关（aBN1 两版都判对）

k_sugar = SUGAR["exploratory_null_normalized"]["by_freq"]["50Hz"]["kappa"]; k_water = WATER["paper_comparison"]["kappa"]; k_jon = JON["paper_comparison"]["kappa"]
e_sugar = SUGAR["experiment_score"]["ours_single_50Hz"]; e_water = WATER["experiment_score"]["ours_single"]
g3_sugar = next(r for r in CONC if r["name"].startswith("糖"))["g3_spearman"]
first_zero = min(   # 连接组读数恒为 0 的最近那一段的起点（mm）
    int(b["距离"].split("–")[0]) for b in FEC["球逼近分箱"] if b["连接组中位"] == 0)
LAT = LEARN["fullbrain"]["lateralization"]; FB = LEARN["fullbrain"]; RF = LEARN["reinforcement"]; MM = LEARN["memory_to_motor"]["v5"]; EMB = LEARN["embodied"]
TR = ECO.get("transfer"); M2 = ECO["m2"]
# 错误账本总数：与 scripts/reproduction.py 同一算法（前两轮 28 处是历史值 + 报告里第三轮「倒查」表格的编号行数）；reproduction.py --check 会拿它对账
_rep = (ROOT / "docs/log/report.md").read_text(); _r3 = {int(m.group(1)) for m in re.finditer(r"^\|\s*(\d+)\s*\|\s*[^|]+\|[^|]+\|[^|]+\|\s*$", _rep, re.M) if 1 <= int(m.group(1)) <= 99 and "倒查" in _rep[max(0, m.start() - 3000):m.start()]}
ERR_TOTAL, ERR_R3 = 28 + len(_r3), len(_r3)
WATER_MN9 = next(q for q in ECO["surface"]["manifold"]["points"] if q["name"] == "只尝到水")["true_hz"]      # 真脑在「只尝到水」时 MN9 的均值（闭环工况留出集）
_n, _m = RF["n_conditions"], RF["max_dan"]
DAN_EN = f"across {_n} conditions, not a single dopamine neuron fires ≥ 5 Hz" if _m == 0 else f"across {_n} conditions at most {_m} dopamine neurons fire ≥ 5 Hz"
DAN_EN_B = f"Across {_n} sugar / bitter / heat / humidity conditions, **not a single** dopamine neuron fires ≥ 5 Hz" if _m == 0 else f"Across {_n} sugar / bitter / heat / humidity conditions, at most **{_m}** dopamine neurons fire ≥ 5 Hz"
_mm = LEARN["memory_to_motor"]["v5"]
MOT_EN = f"none of the {_mm['n_rows']} groups of motor readouts changes significantly after training" if _mm["max_hits"] == 0 else f"at most {_mm['max_hits']} / {_mm['n_rows']} groups of motor readouts change significantly after training"
MOT_EN_S = f"none of {_mm['n_rows']} groups changes" if _mm["max_hits"] == 0 else f"at most {_mm['max_hits']} / {_mm['n_rows']}"

# ───────────────────────── 中文：导言 / 做不到什么 / 错误账本 ─────────────────────────
ZH_SWITCH = "**中文** · [English](README.en.md)\n"
zh_intro = f"""<!-- intro:begin （本节由 scripts/render_readme.py 从结果文件渲染）-->
**把果蝇全脑连接组跑在一台 16 GB 笔记本上，接上身体，做成游戏，再对它做 {LEDGER['total_segments']:,} 次虚拟手术。**
完整记录能做到什么、**做不到什么**，以及作者自查出的每一处错误。

[**▶ 在线试玩（浏览器里 {V5['n']:,} 个真实神经元实时放电，生活在一个 3D 大自然里）**]({PAGES}/game.html) · [**▶ 生态箱**]({PAGES}/ecobox.html) · [**完整报告 docs/log/report.md**](docs/log/report.md) · [**数据许可 ⚠**](DATA_LICENSE.md)
<!-- intro:end -->
"""
zh_what = f"""<!-- what:begin （本节由 scripts/render_readme.py 从结果文件渲染）-->
## 这是什么

2024 年，FlyWire 公布了果蝇成虫大脑的完整连接组；Shiu、Sterne 等人在其上建立了一个全脑漏积分发放（LIF）模型；Eon Systems 把它开源。

本仓库是**一次完整的复现 + 延伸**，全部在一台 16 GB M1 Pro MacBook 上完成：

| | |
|---|---|
| 模型规模 | {RUN['n_neurons']:,} 个神经元、15,091,983 条带权连接，dt = 0.1 ms |
| 跑一秒大脑 | {RUN['sim_s']:.1f} 秒（Brian2，糖刺激 1 s） |
| 虚拟敲除筛选 | **{LEDGER['total_segments']:,} 段**全脑仿真，{LEDGER['total_wall_h']} 小时机时，3 条感觉通路 |
| 浏览器里的子回路 | 球场版 {V3['n']:,} 个神经元 / {V3['n_edges']:,} 条连接；生活与大自然 {V5['n']:,} 个 / {V5['n_edges']:,} 条（含蘑菇体） |

## 主要结论

**1. "这个模型准不准"这个问法是错的——它的可信度是局部的。**
同一套参数、同一个判定门槛，在三条通路上与论文的一致性（Cohen κ，已去掉蒙对成分；三条都按零假设中位数归一化）差别很大：

| 通路 | κ | 对真实光遗传实验 |
|---|---|---|
| 糖味觉 → 伸喙 | {k_sugar:.2f} | {e_sugar['correct']} / {e_sugar['of']} |
| 水味觉 → 伸喙 | **{k_water:.2f}** | **{e_water['correct']} / {e_water['of']}** |
| 触角机械感觉 → 梳理 | **{k_jon:.2f}** | {' / '.join(re.match(r'(\d+)/(\d+)', EXP_JON).groups())}（可测） |

**2. 冗余结构光看连线图预测不出来。**
事先声明的假设是"互为备份 = 到输出的图上路径各走各的"。实测相关系数 **{SVF['sugar']['pairs']['spearman_overlap_vs_delta']:+.3f}（糖）/ {SVF['water']['pairs']['spearman_overlap_vs_delta']:+.3f}（水）**——不是弱相关，是零，且已排除指标退化。**要知道两个神经元是不是互为备份，只能真的一起敲掉跑一遍。**

**3. 同一个动作，背后是两套线路。**
糖和水都通过同一个运动神经元 MN9 引发伸喙，但活跃神经元只重叠三分之一，枢纽各自私有：`CB0883` 在水通路里根本不放电，`CB0051` 在糖通路里敲了毫无影响。抑制性神经元 `Phantom` 敲掉后水通路输出**翻 {PHANTOM['full_water']:.1f} 倍**（全脑，零假设中位数归一化）。

**4. 事先声明的"集中度 → 可预测性"假设，被自己的数据推翻。**
JON 通路最集中（基尼 {CONC_JON['gini']:.3f}），却是只看连线**最预测不了**的（G3 {CONC_JON['g3_spearman']:.3f} < 糖的 {g3_sugar:.3f}）。详见 [docs/log/report.md §22.2](docs/log/report.md)。

<!-- what:end -->
"""
dan_max, dan_n = RF["max_dan"], RF["n_conditions"]
# 值为 0 时换一种说法（「最多 0 个」读起来别扭）；数字照样取自文件
DAN_ZH = f"糖 / 苦 / 热 / 湿 {dan_n} 个条件里，发放 ≥ 5 Hz 的多巴胺神经元**一个都没有**" if dan_max == 0 else f"糖 / 苦 / 热 / 湿 {dan_n} 个条件里，发放 ≥ 5 Hz 的多巴胺神经元最多 **{dan_max} 个**"
MOT_ZH = f"训练后 {MM['n_rows']} 组运动读出**没有一组**显著变化" if MM["max_hits"] == 0 else f"训练后五个运动读出显著变化的组数最多 {MM['max_hits']} / {MM['n_rows']}"
zh_limits = f"""<!-- limits:begin （本节由 scripts/render_readme.py 从结果文件渲染）-->
## 它做不到什么（同样重要）

| 想做的事 | 实际结果 |
|---|---|
| 从感光细胞（R1-6/R7/R8）驱动行为 | 下行神经元**全部 0 Hz**，信号传不过去；必须从 LC4 这类视觉投射神经元注入 |
| 吃到糖产生奖赏信号 | {DAN_ZH}。蘑菇体学习用的强化信号是手接的线（等价于光遗传激活）；生态箱里的奖励是身体的内生奖励，在连接组外面算 |
| 腹神经索产生走路节律 | 有节律，但凑不出三角步态；六条腿里实际只有一条在动。页面上六条腿的节律是手写的 |
| 闻到气味往哪边转 | 单侧刺激给不出左右差异（全脑，偏侧指数 {LAT['left']['LI']:+.3f} / {LAT['right']['LI']:+.3f}）。原来一给气味就上万个神经元失控，已查清是触角叶局部神经元的递质符号（改正后失控 {FB['raw']['n_runaway']}/{FB['raw']['n_runs']} → {FB['alln_inh']['n_runaway']}/{FB['alln_inh']['n_runs']}），但左右差异仍然没有 |
| 记住了就改变行为 | 蘑菇体里记忆**形成得了**（§48），但**走不到运动输出**：{MOT_ZH}。生态箱里学会生存，靠的是连接组旁边手写的可塑性层，不是连接组本身 |
| 闭环行为（大脑 + 身体） | 做了，**但行为映射是手写的**（DNa → 转向、巨纤维 → 起跳、MN9 → 进食的阈值与增益）。物理身体闭环里奖赏记忆成立、惩罚记忆不成立（§48）；生态箱学成的个体搬进 3D 大自然：{'喝得更久 ' + TR['X1']['more_drink_time'] + '、更不渴 ' + TR['X2']['lower_mean_thirst'] if TR else '（未跑）'}（§50） |
| 让果蝇只靠眼睛躲球 | 做了，**是负结果且可量化**：真实像素 → flyvis → LPLC2 这条链路在 **{first_zero} mm 外读数恒为 0**，{FEC['连接组可分辨的最远距离mm']} mm 以内才把球从噪声里分出来；而果蝇**光是走路**，自体运动的光流就造出峰值 **{FEC['自体运动噪声']['峰值']:.0f} Hz** 的假逼近（[§28.19](docs/log/report.md)） |
<!-- limits:end -->
"""
zh_audit = f"""<!-- audit:begin （本节由 scripts/render_readme.py 渲染）-->
## 作者自查出的错误

[docs/log/report.md §23](docs/log/report.md) 里有一份**错误账本**，记录所有自己发现、又自己改掉的错误，不删。三轮逐数字核对（对照结果文件）共查出 **{ERR_TOTAL} 处**问题（第三轮从最新结论倒查到最早，新查出 {ERR_R3} 处）。典型的有：

- 机时账本记少了**不止一次**：它一直由报告正文里的临时 shell 循环生成，每加一批实验就过期（现在由 `screen/compute_ledger.py` 写进文件，本 README 从文件读）；
- 同一个比值在页面用归一化、在报告用未归一化、两处都不标口径，导致文档自相矛盾；
- 游戏页上两张卡片对同一个事先声明的假设下了相反结论（一张从数据渲染、一张是手写副本，停在了被推翻前的版本）；
- 最重的一条：**我们所有视觉结论都建立在 flyvis 50 个预训练模型里的 1 个上**；
- 仿真软件把随机种子编译进程序，导致"跑了 4 次"其实是同一次的 4 份拷贝 → 34 个实验重跑；
- 一张表里的 "2/2 准确率" 是**手写的字符串**，其中一个神经元**从来没有被测过** → 改为 "1/1 可测"；
- 刚写完"一致率是骗人的、要看 κ"，自己引用的 κ 就连填错两次（口径混用）；
- 生态箱里真脑与响应面的闭环喝水时间差 4 倍，均值和决策概率都一样，差在噪声的时间结构（§50.7a）。

由脚本自动产出的数字没有查出错——**错误几乎全部集中在手写的汇总与跨章节引用上**。所以网页上的表格与这份 README 一律从结果文件读取，不写死（`python3 scripts/render_readme.py --check` 在 CI 里核对）。
<!-- audit:end -->
"""

def patch_zh(s):
    s = re.sub(r"^(# flywire-fly-lab\n)(\n?\*\*中文\*\*[^\n]*\n)?", lambda m: m.group(1) + "\n" + ZH_SWITCH, s, count=1, flags=re.M)
    # 导言：旧版是一段手写文字 + 一段英文摘要；英文现在有自己的 README
    if "<!-- intro:begin" in s: s = re.sub(r"<!-- intro:begin.*?<!-- intro:end -->\n", lambda m: zh_intro, s, flags=re.S)
    else: s = re.sub(r"\*\*把果蝇全脑连接组跑在.*?\(DATA_LICENSE\.md\)\n", lambda m: zh_intro, s, count=1, flags=re.S)
    if "<!-- what:begin" in s: s = re.sub(r"<!-- what:begin.*?<!-- what:end -->\n", lambda m: zh_what, s, flags=re.S)
    else: s = re.sub(r"## 这是什么\n.*?(?=\*\*5\. 训练它下五子棋)", lambda m: zh_what + "\n", s, count=1, flags=re.S)
    if "<!-- limits:begin" in s: s = re.sub(r"<!-- limits:begin.*?<!-- limits:end -->\n", lambda m: zh_limits, s, flags=re.S)
    else: s = re.sub(r"## 它做不到什么（同样重要）\n.*?(?=\n## 作者自查出的错误)", lambda m: zh_limits, s, count=1, flags=re.S)
    if "<!-- audit:begin" in s: s = re.sub(r"<!-- audit:begin.*?<!-- audit:end -->\n", lambda m: zh_audit, s, flags=re.S)
    else: s = re.sub(r"## 作者自查出的错误\n.*?(?=\n## 快速开始)", lambda m: zh_audit, s, count=1, flags=re.S)
    # 快速开始里的示例输出
    s = re.sub(r"#   → [\d,]+ 个活跃神经元；MN9[^\n]*", f"#   → {RUN['active_neurons']} 个活跃神经元；MN9 左 {READOUT['MN9_left']:.0f} Hz / 右 {READOUT['MN9_right']:.0f} Hz（官方笔记本的左右命名）；其余下行神经元全 0", s)
    if "| `eco/` |" not in s: s = s.replace("| `screen/` |", "| `eco/` | 生态箱：世界、身体与内生奖励、可塑性层、响应面、进化、存档、迁移到 3D 大自然 |\n| `screen/` |", 1)
    s = s.replace("# 1. 环境（三个 conda 环境不能合并，见 AGENTS.md）", "# 1. 环境（几个 conda 环境不能合并，见 setup.sh）").replace("# FlyWire 注释表、Shiu 补充材料等的获取方式见 AGENTS.md", "# FlyWire 注释表、Shiu 补充材料等的获取方式见 DATA_LICENSE.md 与 docs/log/report.md")
    return s

# ───────────────────────── English：整份 ─────────────────────────
A = GOM["train"]["arms"]; P = GOM["play"]; E = P["engine"]["fly_intact"]; HH = P["head_to_head"]; RL = GOM["rl"]; OL = GOM["opto_leak"]; DM = GOM.get("depth_models"); FI = A["fly_intact"]; NV = len(GOM["train"].get("feat_sets", [""]))
dm_en = ""
if DM:
    dm_en = "\n| Reasoning depth (which readout) | Agrees with depth-8 search | vs random | vs old teacher | vs teacher (1-ply) | vs teacher (2-ply) |\n|---|---|---|---|---|---|\n" + "\n".join(
        f"| {d} | {pct(DM['train'][d]['agree_depth8'])} | {wl(v['random'])} | {wl(v['old_teacher'])} | {wl(v['teacher2_d1'])} | {wl(v['teacher2_d2'])} |" for d, v in DM["vs"].items()) + \
        f"\n\nPre-registered criterion \"model trained on depth-8 labels beats model trained on depth-1 labels, ≥ 55% over 200 games\" → **{'holds' if DM['criterion']['passed'] else 'does not hold'}** ({pct(DM['criterion']['win_rate'])}).\n"
sp = LIFE["sound_priming"]["groups"]; lt = LIFE["life_test"]; C = lt["conds"]; nsp = LIFE["sound_priming"]["n"]
isn = next(r for r in LIFE["modulation"]["rows"] if r["base"].startswith("吃糖") and "ISN" in r["mod"]); wlim = LIFE.get("wall_limits")
oc, rf, CC, MMv, PAR, LG, EMm, VV = LEARN["odor_coding"], LEARN["reinforcement"], LEARN["conditioning"]["connectome"], LEARN["memory_to_motor"], LEARN["parity"], LEARN["legs"], LEARN["embodied"]["main_s1"], LEARN["v5"]
au, sf, m3, m4, lv, lg = ECO["audit"], ECO["surface"], ECO["m3"], ECO["m4"], ECO["live"], ECO["long"]; i0 = M2["individuals"][0]; mf = sf.get("manifold")
WORLD_EN = {"甲虫横行": "Beetle swarm", "风平浪静": "Calm", "地广物稀": "Sparse"}; LABEL_EN = {"升": "rises", "降": "falls", "平": "flat"}
yn = lambda b: "passes" if b else "**fails**"

EN = f"""# flywire-fly-lab

[中文](README.md) · **English**

<p align="center"><a href="{PAGES}/game.html"><img src="media/cover.jpg" alt="flywire-fly-lab: a connectome-lit fruit fly flying over a night-time landscape" width="100%"></a></p>

> **Start with [`REPRODUCTION.md`](REPRODUCTION.md)** (Chinese): every claim of each paper we checked, what we got, and what we could not do.
> The full lab notebook is [`docs/log/report.md`](docs/log/report.md) (Chinese).

**Running the whole *Drosophila* brain connectome on a 16 GB laptop, wiring it to a body, shipping it as a browser game — and doing {LEDGER['total_segments']:,} virtual surgeries on it.**
It documents what works, **what does not**, and every mistake the author caught in their own work.

[**▶ Play online ({V5['n']:,} real neurons firing in your browser, living in a 3D landscape)**]({PAGES}/game.html) · [**▶ Ecobox**]({PAGES}/ecobox.html) · [**Full report**](docs/log/report.md) · [**Data license ⚠**](DATA_LICENSE.md)

> The code, the lab notebook and the in-game text are in Chinese. This English README is generated by `scripts/render_readme.py` from the same result files as the Chinese one, so the numbers match. Issues in English are welcome.

## 🎬 Videos

<a href="https://github.com/suifei/flywire-fly-lab/blob/main/media/nature_open_world.mp4"><img src="media/nature_open_world.gif" alt="The fly in the open-world landscape (click for the full video)" width="100%"></a>

| | | | |
|---|---|---|---|
| [**▶ Open-world nature**](https://github.com/suifei/flywire-fly-lab/blob/main/media/nature_open_world.mp4)<br><sub>A 3D world with gravity and weather and no edges, inhabited by the {V5['n']:,}-neuron fly</sub> | [**▶ All five senses**](https://github.com/suifei/flywire-fly-lab/blob/main/media/five_senses.mp4)<br><sub>Vision, hearing, smell, taste, touch, temperature, humidity; mushroom-body learning, dopamine, six legs</sub> | [**▶ Gomoku against a fly brain**](https://github.com/suifei/flywire-fly-lab/blob/main/media/gomoku.mp4)<br><sub>Line patterns → fly brain → one linear readout; its thinking drawn on the board</sub> | [**▶ Brain + physics body**](https://github.com/suifei/flywire-fly-lab/blob/main/media/embodied_physics_body.mp4)<br><sub>The same brain drives NeuroMechFly (MuJoCo): stops to eat at fruit, turns away from a warm "odor B" source by itself</sub> |

---

## What this is

In 2024 FlyWire published the complete connectome of the adult fruit-fly brain; Shiu, Sterne et al. built a whole-brain leaky integrate-and-fire (LIF) model on top of it; Eon Systems open-sourced that model.

This repository is **a complete reproduction plus extensions**, all done on one 16 GB M1 Pro MacBook:

| | |
|---|---|
| Model size | {RUN['n_neurons']:,} neurons, 15,091,983 weighted connections, dt = 0.1 ms |
| One second of brain time | {RUN['sim_s']:.1f} s wall-clock (Brian2, 1 s sugar stimulus) |
| Virtual knockout screen | **{LEDGER['total_segments']:,} whole-brain segments**, {LEDGER['total_wall_h']} machine-hours, three sensory pathways |
| Sub-circuits in the browser | Court version {V3['n']:,} neurons / {V3['n_edges']:,} connections; life & nature {V5['n']:,} / {V5['n_edges']:,} (incl. mushroom body) |

## Key findings

**1. "Is the model accurate?" is the wrong question — its reliability is local.**
Same parameters, same decision threshold, three pathways; agreement with the paper (Cohen's κ, chance-corrected, all three normalized to the null median) differs a lot:

| Pathway | κ | vs real optogenetic experiments |
|---|---|---|
| Sugar taste → proboscis extension | {k_sugar:.2f} | {e_sugar['correct']} / {e_sugar['of']} |
| Water taste → proboscis extension | **{k_water:.2f}** | **{e_water['correct']} / {e_water['of']}** |
| Antennal mechanosensation → grooming | **{k_jon:.2f}** | {' / '.join(re.match(r'(\d+)/(\d+)', EXP_JON).groups())} (testable) |

**2. Redundancy cannot be predicted from the wiring diagram.**
The pre-registered hypothesis was "backup = disjoint paths to the output". Measured correlation: **{SVF['sugar']['pairs']['spearman_overlap_vs_delta']:+.3f} (sugar) / {SVF['water']['pairs']['spearman_overlap_vs_delta']:+.3f} (water)** — not weak, zero, with metric degeneracy ruled out. **To know whether two neurons back each other up, you have to knock both out and run it.**

**3. One behaviour, two circuits.**
Sugar and water both trigger proboscis extension through the same motor neuron MN9, but their active neurons overlap by only a third and their hubs are private: `CB0883` never fires in the water pathway, and knocking out `CB0051` does nothing in the sugar pathway. Knocking out the inhibitory neuron `Phantom` **multiplies water-pathway output by {PHANTOM['full_water']:.1f}** (whole brain, null-median normalized).

**4. Our own pre-registered "concentration → predictability" hypothesis was refuted by our data.**
The JON pathway is the most concentrated (Gini {CONC_JON['gini']:.3f}) yet the **least** predictable from wiring alone (G3 {CONC_JON['g3_spearman']:.3f} < sugar's {g3_sugar:.3f}). See [docs/log/report.md §22.2](docs/log/report.md).

**5. It can learn Gomoku — but give credit where it is due.**
A fly brain (not a single synapse trained) plus one linear readout learns to value every line on a Gomoku board: all 14,641 line patterns are run through the brain. The ordering it discovers by itself (five > open four > four, open three > …) is entirely correct, and its first choice agrees with a depth-8 search **{pct(FI['test_top1'])}** of the time (random {pct(GOM['train']['random_top1'])}, no brain {pct(A['raw24']['test_top1'])}).
Given to a rules-only search, it beats the hand-written teacher **{wl(E['d6']['teacher2_d4'])}** (6-ply vs 4-ply) and **{wl(E['d10']['teacher2_d8'])}** (10-ply vs 8-ply).
**But** a shuffled connectome ({pct(A['fly_shuffled']['test_top1'])}) and a random network of the same size ({pct(A['rand_relu']['test_top1'])}) do no worse; head to head {wl(HH['d4'])} —
**the real connectome contributes nothing special to Gomoku**; the look-ahead is done by the search, not the fly. See [docs/log/report.md §46](docs/log/report.md).

## Gomoku: playing against a fly brain

The game page ([Digital Fly Lab]({PAGES}/game.html)) has a **Gomoku** tab: a 15×15 board, and the live spike / descending-neuron / sensory panels show **the fly that is playing**.

- Three match types: **you vs the fly** (you play black, with renju forbidden moves), **fly vs fly** (each side has its own {V3['n']:,}-neuron brain), **fly vs teacher**.
- **Reasoning depth** (1–6, 8) can be switched at any time. Each depth is a **trained readout** whose labels were "the best move found by an N-ply search"; **no search runs while playing**, only model inference.
- **Its thinking is drawn on the board**: orange circles = the model's probability for each candidate; numbered ghost stones = the continuation it expects.
- **Real-brain check**: each move's line patterns are re-run through the real fly brain and compared with the trained value table.
- **External search** (off by default): hands the fly's value table to an alpha-beta search. **That is an algorithm, not the fly**, and the page says so.

How it plays: for a candidate point, take one line in each of 4 directions (4 cells on each side; each cell empty / mine / theirs / edge). There are only 14,641 such patterns, few enough to **run every one through the brain**: 8 cells × 3 states = 24 channels, each wired to about 61 real sensory neurons, Poisson-driven for 300 ms; downstream spikes are counted ({NV} input assignments × 3 random seeds, averaged). A move's score = 4 attacking lines + λ × 4 defending lines.

| | |
|---|---|
| First choice agrees with depth-8 search | **{pct(FI['test_top1'])}** (random {pct(GOM['train']['random_top1'])}, no brain {pct(A['raw24']['test_top1'])}) |
| External test set (25,146 positions from the Wine engine, never trained on) | {pct(FI['wine_top1'])} |
| Unseen Poisson seeds | drops only {FI['seed_drop'] * 100:.1f} percentage points |
| External search, 6-ply vs teacher at 4 / 6 / 8 ply | {wl(E['d6']['teacher2_d4'])} / {wl(E['d6']['teacher2_d6'])} / {wl(E['d6']['teacher2_d8'])} |
| External search, 10-ply vs teacher at 8 ply | {wl(E['d10']['teacher2_d8'])} |
{dm_en}
Equally important: (1) **the real connectome contributes nothing special** (shuffled {pct(A['fly_shuffled']['test_top1'])}, random network {pct(A['rand_relu']['test_top1'])}); (2) **self-play reinforcement ("dopamine"-style three-factor rule) is a negative result**: {wl(RL['final']['d4_vs_supervised_d4'])} against the pre-reinforcement table, and the reward-prediction error is computed outside the connectome; (3) **every number of Gomoku v1 is void**: stimuli were not cleared between inputs (pattern A alone = {OL['fixed']['A_first']} spikes, A after B = {OL['old_behaviour']['A_after_B']:,}). Details: [§46](docs/log/report.md).

## Life mode: the five senses go to real receptors; the connectome does the rest

A single fly (sub-circuit v4: {LIFE['subcircuit']['n']:,} neurons, adding **hearing**, two **olfactory glomeruli** and 4 **interoceptive neurons**) lives in an open world where day and night, fruit, puddles, odours, buzzing, heat, wind, dust and incoming balls just happen. Each one reaches the fly **only as a physical quantity at its real receptors** — **there is no "smell it, go there" or "hear it, run" rule.**

| | Measured |
|---|---|
| **Hearing** | Reaches the giant fibre in one hop. Sound alone never triggers takeoff, but it advances the looming response: takeoff lead **{sp['无声']['lead_ms_median']} → {sp['有声']['lead_ms_median']} ms**, dodges {sp['无声']['dodged']} → {sp['有声']['dodged']} / {nsp}; deafened, back to {sp['有声但聋（AUDIO 断突触）']['lead_ms_median']} ms |
| **Smell** | **Negative**: reaches no motor readout; sugar contacts in 10 min, intact {C['intact']['sugar_contacts']}, anosmic {C['anosmic']['sugar_contacts']} |
| **Interoceptive ISN** | **Negative, and opposite to the literature**: driving it lowers MN9 while eating sugar from {isn['base_hz']['mean']} to {isn['hz']['mean']} Hz (it promotes feeding in real flies). It signals via a neuropeptide the LIF model lacks; off by default, sign not flipped to fit |
| **Body state** | Only modulates taste-receptor gain: starts eating on sugar contact {lt['H3']['starved'] * 100:.0f}% of the time when starved, {lt['H3']['sated'] * 100:.0f}% when sated — and an unprogrammed **satiety** emerges |
""" + (f"| **Walls** | **Negative**: touch alone cannot avoid walls — {wlim['arenas']['rect_touch']['mean']['path_mm']:.0f} mm travelled in 3 min in a rectangle (stuck in a corner), {wlim['arenas']['round_touch']['mean']['wall_frac'] * 100:.0f}% of the time on the wall of a round arena; hence this world has no walls |\n" if wlim else "") + f"""
Details: [§47](docs/log/report.md).

## Ecobox: you design the world; it learns and evolves by itself

**[Open the Ecobox →]({PAGES}/ecobox.html)** ([docs/ecobox.html](docs/ecobox.html), a single offline-capable file)

An unattended round terrarium: food that rots, puddles that dry up, day and night, wind, rain, beetles. You **give the fly no task** and **cannot change its reward** — the reward is only that its body's six internal states (hunger, thirst, stamina, health, scent, body temperature) got closer to comfortable. All you can change is the world.

| Layer | What it is | Who can change it |
|---|---|---|
| World rules | food, water, temperature, wind and rain, beetles, terrain | you |
| Genes (10 numbers) | learning rate, exploration, flight tendency, preferred temperature, metabolism, caution, four innate biases | evolution |
| Plastic layer | adjustable weights beside the brain that bias its innate reflexes | this fly's lifetime; **not inherited** |
| Connectome | {au['n_neurons']:,} neurons; escape, proboscis extension, steering and backing-up are built-in reflexes | **nobody** |

- **Single-fly learning**: after {M2['train_lives']} consecutive lives, learning is frozen and the fly is tested in unseen worlds — no learning {i0['off']} s, learned ≥ {i0['on']} s (× {i0['ratio_on']}, censored); a time-shuffled-reward control does not improve; {M2['robust_learned']} of {M2['robust_n']} other individuals learn; **a long-term training task with 10 fresh individuals: {lg['n_learned']}/{lg['n']} learn, {lg['n_retest_ok']}/{lg['n']} on a re-test in new worlds** (`node eco/train_long.js`, {lg['total_lives']} lives).
  What it learns: "stop and drink when you touch water" (in the connectome, water taste drives the proboscis motor neuron MN9 to only {WATER_MN9:.0f} Hz in the real brain — not enough innately) and "turn less while humidity is rising". It does **not** learn to find water from a distance: {M2['drought_on']} s vs {M2['drought_off']} s in a drought world.
- **Evolution with 32 flies**: no fitness function — only well-fed, well-watered flies accumulate eggs. {'; '.join(f"{WORLD_EN.get(w['name'], w['name'])}: lifespan {w['life_head']} → {w['life_tail']} s, flight tendency {LABEL_EN.get(w['label'], w['label'])}" for w in m3['worlds'])}. Pre-registered criterion (different worlds push flight tendency in different directions) {yn(m3['pass'])}. Flight is a **decision**, not a controlled skill: whether to take off is up to the fly, the flight itself is a fixed trajectory — flight control is not wired into the connectome, and we do not pretend it can learn to fly.
- **Discovery cards**: lying flat, hugging the glass, spinning in place, camping on food… reward hacking and failures are detected with evidence. You choose: accept its current way of life, or change the world to force another.
- **A save is a training result**: world rules + generation timeline + every fly's weights + cards + replays. Resuming is bit-identical to never stopping; a {m4['code_chars']}-character challenge code lets someone else start in the same world.
- The page runs a **response surface** of the real brain (the real brain runs at only {au['realtime_one']}× real time per fly), fitted on {sf['n_samples']:,} real-brain samples{f" plus {mf['n']:,} closed-loop samples (real-brain index {mf['index']})" if mf else ""}. Put back into the real brain, a trained fly survives {lv['live_median']} s vs {lv['naive_median']} s for a naive one; drinking time in the real brain is {lv['drink_ratio']}× the surface's, and the pre-registered "same behavioural magnitude" criterion (0.5–2×) {yn(lv['L2'])}.
""" + (f"""- **Moved into the 3D landscape**: the training conditions were first aligned with the landscape (same sensory encoding; closed-loop samples in the surface), then a trained fly with frozen weights was put into the lab page's landscape with the real brain: over {TR['n_informative']} informative seeds it drinks longer in {TR['X1']['more_drink_time']} and is less thirsty in {TR['X2']['lower_mean_thirst']}; pre-registered criterion {yn(TR['pass'])}. In the lab page's life mode, the landscape has a **Load ecobox save** button.
""" if TR else "") + f"""
Honestly: not one synapse of the connectome changes; learning happens in a hand-written plastic layer, and a control that cannot see the brain's outputs learns just as well — in this task the connectome supplies the body and its reflexes, not the learning signal. Plan, audit and all measurements: [docs/ecobox/](docs/ecobox/), report [§50](docs/log/report.md).

## Nature: a 3D world with gravity, weather and no edges

The game page now opens in a **nature** world (the "world" switch still goes back to the basketball court): seeded, endless rolling terrain with rocks, dark slabs, mushrooms, flowers, grass, berry bushes and puddles; day and night, wind and rain.
Physics uses real units: gravity 9,810 mm/s² — ripe berries fall from the branch (30 mm in {NT['N1_free_fall']['t_sim']} s; analytic {NT['N1_free_fall']['t_analytic']} s), bounce off the terrain normal, roll downhill and ferment when they stop; rocks are solid; uphill is slower; the sun heats the slabs; hollows fill with rain and evaporate; wind carries odour downwind.
The inhabitant is the {V5['n']:,}-neuron fly, and **it knows the world only through real receptors**. No behavioural rule was added. All nine pre-registered physics checks pass (`node dodge/nature_test.js`); in 3 minutes it walks {NL['path_mm']:.0f} mm, is blocked for {NL['blocked_s']:.1f} s, sees {NL['berries']:.1f} berries fall and touches sugar {NL['sugar_contacts']:.1f} times.
It plays like a sandbox (Minecraft-style tools, naturalistic look): place fruit, dig puddles, place rocks, plant mushrooms / bushes / flowers, add beetles, raise or lower terrain; `C` switches camera, `A` `D` `S` and space drive the real steering / backing / giant-fibre neurons, `F` fills the window.
Honestly: the default visual front end is still a hand-written looming detector — rocks and grass are not in its vision (the real-pixel path exists, off by default); the fly's own body is kinematic and cannot fall over. Details: [§49](docs/log/report.md).

## Learning, dopamine, closed loop, six legs

The life-mode fly uses sub-circuit v5: **{VV['n']:,} neurons, {VV['n_edges']:,} edges** = v4 plus the connectome's mushroom-body learning circuit (Kenyon cells {VV['n_tag']['KC']:,}, mushroom-body output neurons {VV['n_tag']['MBON']}, dopaminergic neurons {VV['n_tag']['DAN']}). All wiring is from FlyWire; the only thing that changes is the Kenyon-cell → MBON synapse, depressed when a Kenyon cell has just fired and dopamine arrives in the same compartment. Pre-registered criteria:

| Question | Result |
|---|---|
| Why does any odour make the whole brain run away? | **The sign of the antennal-lobe local neurons' transmitter.** Made inhibitory (as in the literature): active Kenyon cells {oc['raw']['max_kc_frac'] * 100:.0f}% → {oc['alln_inh']['max_kc_frac'] * 100:.1f}%; **whole-brain check**: runaway {FB['raw']['n_runaway']}/{FB['raw']['n_runs']} → {FB['alln_inh']['n_runaway']}/{FB['alln_inh']['n_runs']} |
| Can sugar / bitter / heat / humidity recruit dopamine neurons through real wiring? | **Negative**: {DAN_EN}. So "sugar → PAM, heat → PPL1" is hand-wired (like optogenetic activation) |
| Does it learn? | **Yes, slightly unspecific**: the paired odour's response in the reinforced compartment drops to {CC['median_ratio_paired_csp']:.2f} of control; unpaired dopamine leaves it unchanged ({CC['median_ratio_unpaired_csp']:.2f}); PAM- and PPL1-depressed MBONs do not overlap ({CC['compartment_jaccard']:.2f}); the unpaired odour also drops to {CC['median_ratio_paired_csm']:.2f} (criterion ≥ 0.85, fails) |
| Does the memory change behaviour? | **Negative**: {MOT_EN}. The "memory → steering bridge" on the page is hand-written and off by default |
| Does the browser engine learn the same as Python? | Yes: remaining synaptic strength correlates r = {PAR['strength_pearson']:.4f} |
| Can six legs push the body? | All four criteria pass: straight {LG['tests']['T1_straight']['path_speed']:.1f} mm/s (command 18), turning {LG['tests']['T2_turn']['left_yaw']:+.0f} / {LG['tests']['T2_turn']['right_yaw']:+.0f} °/s (command ±60). Leg rhythm and coordination are hand-written |
| Brain + physics body (NeuroMechFly, MuJoCo) | Reward memory holds (MBON response {EMm['after']['A']['PAM']:.0f} vs {LEARN['embodied']['noreinf_s1']['after']['A']['PAM']:.0f} Hz); punishment memory {'holds' if LEARN['embodied']['criteria']['E1b_punish'] else '**does not**'} — it walks up to the warm odour-B source and **turns away by itself**, burned for only {EMm['ppl1_seconds']:.1f} s; nobody wrote that U-turn |

Details: [§48](docs/log/report.md).

## What it cannot do (just as important)

| Goal | Actual result |
|---|---|
| Drive behaviour from photoreceptors (R1-6 / R7 / R8) | Descending neurons stay at **0 Hz**; visual input must enter at projection neurons such as LC4 |
| A reward signal from eating sugar | {DAN_EN_B}. The mushroom-body reinforcement is hand-wired; the Ecobox reward is the body's own, computed outside the connectome |
| A walking rhythm from the ventral nerve cord | A rhythm, but no tripod gait; effectively one of six legs moves. The page's leg rhythm is hand-written |
| Turn toward an odour | Unilateral stimulation gives no left/right difference (whole brain, lateralization index {LAT['left']['LI']:+.3f} / {LAT['right']['LI']:+.3f}). The old runaway is fixed (transmitter sign; {FB['raw']['n_runaway']}/{FB['raw']['n_runs']} → {FB['alln_inh']['n_runaway']}/{FB['alln_inh']['n_runs']}), the missing lateralization is not |
| Memories that change behaviour | Memories **form** in the mushroom body but **do not reach** the motor outputs ({MOT_EN_S}). The Ecobox fly survives thanks to a hand-written plastic layer beside the connectome, not the connectome itself |
| Closed-loop behaviour (brain + body) | Done, **but the behavioural mapping is hand-written** (DNa → steering, giant fibre → takeoff, MN9 → feeding thresholds and gains) |
| Dodge balls with its eyes alone | Done, and **a quantified negative**: real pixels → flyvis → LPLC2 reads exactly 0 beyond **{first_zero} mm** and separates the ball from noise only within {FEC['连接组可分辨的最远距离mm']} mm, while merely walking produces spurious looming of up to **{FEC['自体运动噪声']['峰值']:.0f} Hz** ([§28.19](docs/log/report.md)) |

## Mistakes the author caught

[docs/log/report.md §23](docs/log/report.md) keeps an **error ledger** of every mistake found and fixed, never deleted. Three rounds of number-by-number checks against the result files found **{ERR_TOTAL}** problems ({ERR_R3} of them in the third round, which traced from the newest conclusions back to the oldest), among others: a compute ledger that went stale more than once (it was generated by an ad-hoc shell loop in the report text); the same ratio normalized on the page and un-normalized in the report with neither labelled; two cards on the game page reaching opposite conclusions about one pre-registered hypothesis; **every vision conclusion resting on 1 of flyvis's 50 pretrained models**; a simulator that compiled the random seed into the binary, so "4 runs" were 4 copies of one run; a "2/2 accuracy" that was a hand-typed string for a neuron never tested; and, in the Ecobox, a 4× closed-loop drinking gap between the real brain and its response surface that came from the time structure of the noise, not from the mean.

No error was found in numbers produced by scripts — **the errors were almost all in hand-written summaries and cross-references**. That is why the web page and both READMEs read their numbers from result files (`python3 scripts/render_readme.py --check` runs in CI).

## Quick start

```bash
# 1. Environments (several conda envs that cannot be merged; see setup.sh)
bash setup.sh cpu        # brain-fly-cpu: Brian2 + numpy 1.26
bash setup.sh flygym     # flygym: FlyGym 2.1 + torch

# 2. Upstream code (not redistributed here; see DATA_LICENSE.md §4)
git clone https://github.com/eonsystemspbc/fly-brain external/fly-brain

# 3. Smallest experiment: stimulate sugar taste neurons, watch the proboscis motor neuron MN9
conda activate brain-fly-cpu
python run_experiment.py --preset sugar --t_run 1
#   → {RUN['active_neurons']} active neurons; MN9 left {READOUT['MN9_left']:.0f} Hz / right {READOUT['MN9_right']:.0f} Hz (official notebook's left/right naming); all other descending neurons 0

# 4. Open the game locally
python3 dodge/build.py && open results/dodge/fly_dodge.html
python3 eco/build.py && open docs/ecobox.html
```

Every script's docstring documents its usage and pre-registered criteria.

## Layout

| Path | Contents |
|---|---|
| `run_experiment.py` | Smallest experiment: activate / silence / record, Brian2 and PyTorch backends |
| `dodge/` | Sub-circuit extraction, real-time JS brain engine, game logic and page |
| `eco/` | Ecobox: world, body and intrinsic reward, plastic layer, response surface, evolution, saves, transfer to the 3D landscape |
| `screen/` | Virtual knockout screens (three pathways, double knockouts, hub scans, concentration analysis) |
| `vnc/` | Ventral nerve cord: BANC LIF, Pugliese rate model, full MANC, proprioceptive loop |
| `vision/` | Compound eye → flyvis → whole-brain connectome, offline |
| `gomoku/` | Gomoku: line patterns → fly brain → linear readout; search engine, teacher, data, training, regression tests |
| `learn/` | Mushroom-body learning: odour coding, reinforcement, conditioning, memory → motor, whole-brain checks, engine parity, physics-body loop |
| `language/` | "The fly speaks": a 12-word decoder and BCI stress tests |
| `flight/` | flybody flight-controller replay, real escape-flight trajectories |
| `docs/log/report.md` | **Full report** (Chinese), including every negative result and the error ledger |

## License

- **Code**: [GPL-3.0-or-later](LICENSE) (it imports Eon's GPL-2.0-or-later code).
- **Data under `results/`**: **not GPL**. It includes data derived from the FlyWire connectome and is **treated as CC BY-NC 4.0 — no commercial use**. See [**DATA_LICENSE.md**](DATA_LICENSE.md) before using it.
- Please cite the original papers, not just this repository; the list is in [DATA_LICENSE.md §3](DATA_LICENSE.md).

## In one sentence

> Having the complete wiring diagram of a brain and knowing how to drive it are two different things.
> This repository records how many walls I drove it into.
"""

def main():
    check = "--check" in sys.argv; bad = []
    zp = ROOT / "README.md"; z0 = zp.read_text(); z1 = patch_zh(z0)
    ep = ROOT / "README.en.md"; e0 = ep.read_text() if ep.exists() else ""
    if check:
        if z1 != z0: bad.append("README.md 与结果文件脱节（重跑 python3 scripts/render_readme.py）")
        if EN != e0: bad.append("README.en.md 与结果文件脱节（重跑 python3 scripts/render_readme.py）")
        for m in re.findall(r"\{[a-zA-Z_][^{}\n]{0,40}\}", EN): bad.append("README.en.md 里有没替换的占位：" + m)
        for b in bad: print("✗", b)
        if not bad: print("✓ README.md / README.en.md 与结果文件一致")
        sys.exit(1 if bad else 0)
    zp.write_text(z1); ep.write_text(EN); print("→ README.md（中文，导言 / 结论 1–4 / 做不到什么 / 错误账本）\n→ README.en.md（英文，整份）")

if __name__ == "__main__":
    main()
