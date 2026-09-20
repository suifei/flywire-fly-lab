#!/usr/bin/env python3
"""日志 §48（学习 / 多巴胺 / 闭环 / 六条腿）从 results/learn/learn_summary.json 渲染进 docs/log/report.md 的 <!-- §48:begin/end --> 之间。叙述手写，数字全部取自 JSON。"""
import json, re, sys
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
L = json.loads((ROOT / "results/learn/learn_summary.json").read_text())
oc, fb, rf, C, M, P, LG, G, E, V = L["odor_coding"], L["fullbrain"], L["reinforcement"], L["conditioning"], L["memory_to_motor"], L["parity"], L["legs"], L["game"], L["embodied"], L["v5"]
yn = lambda b: "成立" if b else "**不成立**"; pc = lambda v: f"{v * 100:.1f}%"; p0 = lambda v: f"{v * 100:.0f}%"
AN = dict(raw="原样（Shiu 模型的递质符号）", alln_inh="ALLN 改成抑制性", no_alln="去掉 ALLN")
oc_rows = "\n".join(f"| {AN[a]} | {pc(oc[a]['max_kc_frac'])} | {pc(oc[a]['median_kc_frac_synthetic'])} | {oc[a]['cross_odor_jaccard_median']:.3f} | {oc[a]['same_odor_jaccard_median']:.3f} | {yn(oc[a]['criteria']['C1_no_runaway'])} / {yn(oc[a]['criteria']['C2_sparse'])} / {yn(oc[a]['criteria']['C3_specific'])} |" for a in ("raw", "alln_inh", "no_alln"))
fb_rows = "\n".join(f"| {AN[a]} | {fb[a]['n_runaway']} / {fb[a]['n_runs']} | {fb[a]['median_active']:.0f} | {fb[a]['max_active']} |" for a in ("raw", "alln_inh"))
lat = fb.get("lateralization") or {}
CR = [("L1_learned", "L1 学会了：配对过的气味 ≤ 0.7", "median_ratio_paired_csp"), ("L2_specific", "L2 只记这一种：没配对的 ≥ 0.85", "median_ratio_paired_csm"), ("L3_contingent", "L3 要同时出现：错开给 ≥ 0.85", "median_ratio_unpaired_csp"), ("L4_compartments", "L4 隔室分工：PAM / PPL1 压低的 MBON 重合 < 0.5", "compartment_jaccard")]
cell = lambda a, k, f: f"{a[f]:.2f} · {yn(a['criteria'][k])}"
c_rows = "\n".join(f"| {nm} | {cell(C['connectome'], k, f)} | {cell(C['shuffle'], k, f)} | {cell(C['v1'], k, f)} |" for k, nm, f in CR)
RD = dict(oDN1="oDN1（前进）", BDN2="BDN2（前进）", DNa01="DNa01（转向）", DNa02="DNa02（转向）", MDN="MDN（后退）")
m_rows = "\n".join(f"| {RD[k]} | {M['v5']['summary'][k]['n_hit']} / {M['v5']['n_rows']} | {M['no_apl_mbon']['summary'][k]['n_hit']} / {M['no_apl_mbon']['n_rows']} |" for k in RD)
tops = sorted((dict(x, r=r["reinforcer"], pair=r["pair"]) for r in M["no_apl_mbon"]["top"] for x in r["top"]), key=lambda x: -abs(x["t"]))[:4]
top_txt = "；".join(f"{x['type']}（{x['side'][0]}）{x['mock']} → {x['paired']} Hz，t = {x['t']:+.1f}（第 {x['pair']} 对，{x['r']}）" for x in tops)
em, en, eo = E["main_s1"], E["noreinf_s1"], E["openloop_s1"]
NM = dict(LF="左前", LM="左中", LH="左后", RF="右前", RM="右中", RH="右后")
leg_rows = "\n".join(f"| {'截掉' + NM[k[9:]] + '腿' if k.startswith('amputate_') else '按住左中腿不放'} | {t['speed']:.1f} | {t['yaw']:+.0f} | {p0(t['unstable'])} |" for k, t in LG["explore"].items())
T = LG["tests"]
U = L["uturn"]; VV = L.get("v5_vs_v4") or {}; v5v4 = ""
if VV.get("modulation") and VV.get("sound_priming"):
    mrows = "\n".join(f"| {r['base']} {r['mod']} | {r['readout']} | {r['v4_base']} → {r['v4']}{'（有调制）' if r['v4_mod'] else ''} | {r['v5_base']} → {r['v5']}{'（有调制）' if r['v5_mod'] else ''} |" for r in VV["modulation"] if r["v4_mod"] or r["v5_mod"])
    srows = "\n".join(f"| {k} | {v['v4_lead']} ms · 躲开 {v['v4_dodged']} | {v['v5_lead']} ms · 躲开 {v['v5_dodged']} |" for k, v in VV["sound_priming"].items())
    v5v4 = f"""**换到 v5 之后，§47 在 v4 上量过的东西还在不在**（同一个脚本、`SUBCIRCUIT=v5` 重跑，输出另存为 `*_v5.json`）。调制实验 {VV['modulation_n']} 行里「有 / 无调制」的判定有 {VV['modulation_same_calls']} 行相同；有调制的几行：

| 条件 | 读出 | v4（Hz） | v5（Hz） |
|---|---|---|---|
{mrows}

声音让逼近反应提前（每组 {VV['sound_priming_n']} 次，起飞提前量中位 · 躲开次数）：

| | v4 | v5 |
|---|---|---|
{srows}
"""
text = f"""<!-- §48:begin （本节由 scripts/render_report48.py 从 results/learn/learn_summary.json 渲染；不要手改数字）-->
## 48. 学习 / 记忆 / 可塑性、多巴胺神经元、大脑 + 身体的闭环、六条腿（2026-09-20）【实测】（`learn/`、`dodge/plasticity.js`、`dodge/legs.js`、子回路 v5）

用户的目标原话：「实现：学习 / 记忆 / 可塑性，闭环行为（大脑 + 身体），多巴胺神经元，六条腿 + 身体 + 神经元的全面掌控」。
§11.7 里我自己推荐过这条路（蘑菇体的多巴胺学习），也写下了风险：「嗅觉输入在全脑会失控，需要先在蘑菇体子回路里验证不失控」。所以顺序是：先解决失控 → 再加可塑性 → 再问记忆到不到得了行为 → 最后接上身体。
原则不变：我们只提供物理量和有文献依据的突触规则，不写「闻到 A 就过去」这类判断；做不到的如实记阴性。

### 48.1 先解决一个挂了六天的问题：嗅觉失控的源头（`learn/mb_odor_coding.py`、`learn/fullbrain_alln.py`）

蘑菇体回路 = 注释表里的嗅觉感受神经元（ORN）、投射神经元（ALPN）、触角叶局部神经元（ALLN）、凯尼恩细胞（KC）、蘑菇体输出神经元（MBON）、多巴胺神经元（DAN）、APL、DPM，
共 {oc['raw']['n']:,} 个神经元、{oc['raw']['n_edges']:,} 条连接，成员之间的连接全部保留。气味 = 一组嗅小球的 ORN 被驱动；面板 = 3 种有文献标签的 + 8 种合成气味（53 个小球里随机 6 个）。
判据（跑之前写死）：C1 不失控（活跃 KC < 20%）；C2 稀疏（合成气味下活跃 KC 中位 1–15%；真果蝇约 5–10%）；C3 气味特异（不同气味的活跃 KC 集合 Jaccard 中位 < 0.5，且小于同一气味换种子的）。

| 接线 | 活跃 KC 最大 | 合成气味中位 | 不同气味 Jaccard | 同一气味换种子 | C1 / C2 / C3 |
|---|---|---|---|---|---|
{oc_rows}

- **源头是 ALLN 的递质符号**。文献里触角叶局部神经元绝大多数是 GABA 能或谷氨酸能，两者在触角叶里都是抑制性的（Wilson & Laurent 2005；Olsen & Wilson 2008；Liu & Wilson 2013）；
  模型用的递质预测把它们发出的突触约一半标成了乙酰胆碱 / 5-羟色胺 / 多巴胺，Shiu 的规则一律当兴奋。原样跑，单个小球 100 Hz 就让 {pc(oc['raw']['max_kc_frac'])} 的 KC 同时放电。
- 按「改动最小且三条全过」的事先规则，主臂 = **{AN[oc['main_arm']]}**。这是对递质符号的纠正，不是行为规则；登记在台账 PARAMETERS 里。

**回到全脑复核**（{fb['n']:,} 个神经元、全部连接；刺激与判据沿用 §11.4：左侧 DM1，20 / 100 Hz，其他活跃神经元 < 2,000 才算不失控；事先写下的预测：原样失控、改后三个种子都不失控）：

| 接线 | 失控次数 | 其他活跃神经元（中位） | 最大 |
|---|---|---|---|
{fb_rows}

预测**{'成立' if fb['prediction_holds'] else '不成立'}**。§11.4 当时的结论「沉默兴奋性局部神经元后失控明显减弱，但仍超过判据」现在有了完整的解释：不是要沉默它们，而是它们本来就该是抑制性的。
仿真核是 `learn/lif.py`（numba；方程、参数、每步顺序与 Brian2 版相同，但不是 Brian2 本身）；全脑 0.5 s 约 10 s，峰值内存 2.6 GB。
{f"不失控之后，回头问 §11.4 当时问不了的问题——单侧给气味，下行神经元有没有左右偏侧（判据原话：左、右刺激的 LI 符号相反且 |LI| ≥ 0.2）：左刺激 LI {lat['left']['LI']:+.2f}、右刺激 {lat['right']['LI']:+.2f} → **{'有' if lat['lateralized'] else '没有'}**。DNa01+02 的脉冲两种刺激下都是左侧占多数（左刺激 {lat['left']['dna_left']} / {lat['left']['dna_right']}，右刺激 {lat['right']['dna_left']} / {lat['right']['dna_right']}）：气味推动转向神经元，但推的方向与气味在哪一侧无关。" if lat else ""}

### 48.2 强化信号走不走得通连接组——阴性（`learn/mb_reach.py`、`learn/reinforcement_route.py`）

结构上通：糖、苦、热、湿、触这几类感受神经元到 PAM / PPL1 最少 2–3 跳，3 跳之内几乎全部可达。动力学上不通：在一个专门裁的回路里（蘑菇体 ∪ v4 ∪ 所有「感觉 → DAN」≤3 跳路径上的神经元，{rf['n']:,} 个），
糖 / 苦 / 热 / 湿各三档强度共 {rf['n_conditions']} 个条件，没有一个失控（其他活跃最多 {rf['max_active']} 个），而多巴胺神经元发放 ≥5 Hz 的**最多 {rf['max_dan']} 个**。与 §11.1 在全脑上测到的一致，并补上了热和湿。
所以下面的强化信号是**手接的一根线**：直接驱动 PAM 或 PPL1 整簇 30 Hz——等价于真果蝇实验里用光遗传激活多巴胺神经元代替糖 / 电击（Claridge-Chang 2009；Aso 2012；Liu 2012）。

### 48.3 可塑性规则与条件化实验（`learn/plasticity.py`、`learn/mb_conditioning.py`）

规则只作用在 KC → MBON 突触上：KC 最近放过电（资格迹，时间常数 {C['params']['tau_e_ms']:.0f} ms）＋ 同一隔室里有多巴胺 → 突触被乘性压低（Hige 2015；Cohn 2015；Handler 2019）。
某个 MBON 处的多巴胺 = 接到它上面的那些 DAN 的脉冲数，按连接组里 DAN → MBON 的突触数加权平均。**哪个多巴胺神经元管哪个隔室完全由连接组决定**；规则对 PAM 和 PPL1 一视同仁。
每对气味（A = 配对的，B = 不配对的）× 强化物 {{PAM, PPL1}} × 三种训练（paired / mock 不给多巴胺 / unpaired 多巴胺与气味错开），读数 = 训练后被强化隔室的 MBON 响应 ÷ mock 训练后的，取 {C['connectome']['n_rows']} 组的中位数。

| 判据（跑之前写死） | 连接组 | 打乱 ALPN → KC 的接线 | 第一次尝试（留作记录） |
|---|---|---|---|
{c_rows}

- **第一次尝试三条判据不过，原因是设计而不是生物学**：① 多巴胺用全局常数归一，PAM（307 个）给的多巴胺是 PPL1（16 个）的二十多倍；② 学习率 {C['v1_params']['eta']} 太大，1 秒配对就把突触压到 7%，配对期间偶然放过一个脉冲的 KC 全被连坐；
  ③ 两种气味各自独立随机抽小球，近四分之一重合，本来就是相似气味；④ 用 96 个 MBON 的总发放当指标，被不相干的隔室稀释。第二次在看新结果之前改掉这四处（学习率 {C['params']['eta']}；气味对用不重合的小球；指标改成被强化隔室的 MBON），阈值不变。
- 第二次：学会了、要同时出现、隔室分工三条成立。**「只记这一种」差一点**（{C['connectome']['median_ratio_paired_csm']:.2f} 对 0.85）：没配对的气味也掉了约两成；相似气味（一半小球相同）掉得更多（{C['connectome']['similar_median_ratio_csm']:.2f}）。没有为了过线再调第三次。
- 隔室分工与解剖一致：PPL1 配对压低的是 {'、'.join(C['connectome']['depressed_types']['PPL1'][:5])} 等 {C['connectome']['n_depressed']['PPL1']} 个 MBON（MBON11 = MBON-γ1pedc，文献里正是 PPL1-γ1pedc 管的惩罚隔室），PAM 配对压低的是 {'、'.join(C['connectome']['depressed_types']['PAM'][:5])} 等 {C['connectome']['n_depressed']['PAM']} 个，两组重合 {C['connectome']['compartment_jaccard']:.2f}。
- **打乱 ALPN → KC 的接线之后照样学得会**（事先写下的预期）：这一层在真果蝇里本来就接近随机（Caron 2013），学习靠的是稀疏展开。打乱后特异性更差（{C['shuffle']['median_ratio_paired_csm']:.2f}）。连接组的贡献在隔室，不在这一层的具体接线。
- 一个没人写的现象：有的气味自己就会叫起某几个 PPL1（KC → DAN 是真实连接，探索时见到 PPL106 到 100 Hz），单独闻几次响应就掉——所以必须有 mock 这一臂。方向上像文献里 α′3 隔室的「熟悉化」（Hattori 2017），但这里幅度大得多，不当作复现。

### 48.4 记住了，会改变行为吗——阴性（`learn/memory_to_motor.py`）

条件化实验里的运动读出是单次 1 秒的读数，一个 30 Hz 的下行神经元 1 秒的泊松涨落就有 ±5 Hz，分不清记忆和噪声。重做：在页面真正跑的 v5 回路上，训练后各测 {M['v5']['n_test']} 次（换种子）。
判据：M1 某个事先指定的读出 Welch |t| ≥ 3 且均值差 ≥ 20%；M2 同一个读出在 ≥ 半数的组里都满足且同向。

| 运动读出 | v5：显著变化的组数 | 切掉 APL → MBON（只试这一次） |
|---|---|---|
{m_rows}

- **M2 不成立**：记忆形成了，但走不到我们接了身体的那五个下行神经元。
- 追查：{f"35 类 MBON 里只有 {M['v5']['n_responsive']} 类对气味有响应；" if M['v5'].get('n_responsive') is not None else ""}有运动落点的四类（MBON12 / 26 / 27 / 35，单独驱动 100 Hz 能推动 oDN1 / BDN2 / DNa02）一个脉冲都没有——它们收到的 APL 抑制是 KC 兴奋的 2–7 倍。
  APL 在真果蝇里**不放电**，靠分级电位做局部抑制（Papadopoulou 2011；Lin 2014）；LIF 模型把它当普通放电神经元，它顶着不应期上限放电（200–450 Hz）。
- 事先写明「只试这一次，过不过都认」的一刀：切掉 APL → MBON（APL → KC 保留）。有响应的 MBON 类型增加到 {M['no_apl_mbon']['n_responsive']} / {M['no_apl_mbon']['n_types']}，KC 活跃比例最大 {pc(M['no_apl_mbon']['max_kc_frac'])}，记忆也确实传到了一些下行神经元
  （探索性：{top_txt}）——但不是那五个，M2 仍不成立。**这一刀不采用，也不再改模型去凑行为。**

### 48.5 搬进页面：子回路 v5、稀疏推进、两边一致（`dodge/subcircuit_v5.py`、`dodge/plasticity.js`、`learn/parity_js.js` + `learn/parity_py.py`）

v5 = v4（{V['n_v4']:,} 个，编号与内部连接逐位不变，除了本来就在 v4 里的 49 个 ALLN 改成抑制性）＋ 蘑菇体，共 **{V['n']:,} 个神经元、{V['n_edges']:,} 条边**（KC {V['n_tag']['KC']:,}、MBON {V['n_tag']['MBON']}、DAN {V['n_tag']['DAN']}、ORN {V['n_tag']['ORN']:,}）。
碰到蘑菇体的边只留 ≥{V['mb_wmin']} 个突触的（全留 129 万条页面装不下；砍掉的主要是 KC ↔ KC 之间只有 1 个突触的接触）。球场和五子棋仍用 v3，已发布的数字不动。
`brain.js` 加了具名驱动通道，和一条可选的稀疏推进（只更新不在静息态的神经元；不逐位相同，统计一致）——**后者实测反而更慢**：每步只有 3–4 个神经元放电，但每个脉冲扇出几十个靶点、每个靶点要 160 ms 才衰减回阈值以内，活动表里常驻约 11,700 个，所以页面用稠密推进（这条路径留着，是因为一致性检验和页面引擎的学习实验是开着它跑的）；输入频率的 setter 改成只标脏、在 `run()` 里统一重建刺激表（逐位不变，五子棋的「活脑核对」照过）。

{v5v4}
同一份 v5、同一个条件化流程（气味 A 配 PAM 5 次，对照 mock），4 个种子：

| | 页面引擎（JS） | Python |
|---|---|---|
| 未配对气味的 MBON 总发放 | {P['js']['mbon_B_mock']:.1f} Hz | {P['py']['mbon_B_mock']:.1f} Hz |
| 配对气味在 PAM 隔室的比值 | {P['js']['ratio_csp']:.2f} | {P['py']['ratio_csp']:.2f} |
| 未配对气味在 PAM 隔室的比值 | {P['js']['ratio_csm']:.2f} | {P['py']['ratio_csm']:.2f} |
| 活跃 KC 数 | {P['js']['kc']:.0f} | {P['py']['kc']:.0f} |

各 MBON 的突触剩余强度两边相关 r = {P['strength_pearson']:.4f}；四条事先写好的判据{'全过' if P['all_pass'] else '**没有全过**'}。

### 48.6 六条腿：身体是被腿推着走的（`dodge/legs.js`、`dodge/legs_test.js`）

原来身体按速度滑行、腿只循环播放录好的步态。现在每条腿有自己的相位；支撑相的脚钉在地上，身体每一步的位移和转角由所有支撑脚做一次二维刚体最小二乘解出来；转向 = 左右步幅不等，是算出来的。
足尖轨迹来自 FlyGym / NeuroMechFly 物理仿真录下的一个步态周期。**直接回放录制的足尖轨迹不行**：物理仿真里脚会打滑，同一时刻各腿的速度差到 6 倍，刚体拟合会凭空转出 ±15° 的摆动；所以推进相按匀速直线理想化。
下行神经元 → 「步频 + 左右步幅」的映射、以及六条腿之间锁回三足关系的相位耦合，都是手写的——腹神经索连接组给不出三足步态（§12）。

| 判据（跑之前写死） | 实测 | |
|---|---|---|
| T1 直行 18 mm/s：速度误差 ≤10%、偏航 ≤2 °/s | {T['T1_straight']['path_speed']:.2f} mm/s、{T['T1_straight']['yaw_deg_s']:+.2f} °/s | {yn(T['T1_straight']['pass'])} |
| T2 转向 ±60 °/s：符号正确、误差 ≤25% | {T['T2_turn']['left_yaw']:+.1f} / {T['T2_turn']['right_yaw']:+.1f} °/s | {yn(T['T2_turn']['pass'])} |
| T3 后退 −12 mm/s：误差 ≤10% | {T['T3_back']['signed_x']:.2f} mm/s | {yn(T['T3_back']['pass'])} |
| T4 任何时刻着地的腿 ≥3、重心在支撑多边形内 | 最少 {T['T4_support']['min_stance']} 条、失稳 {p0(T['T4_support']['unstable_frac'])} | {yn(T['T4_support']['pass'])} |

只报告、不设判据（指令都是 18 mm/s 直行）：

| | 实际速度 mm/s | 偏航 °/s | 失稳拖行的时间 |
|---|---|---|---|
{leg_rows}

没有适应：真果蝇截肢后会重新调整步态，这里不会。失稳时的「拖行」是一只粘在地上的虚拟脚，权重手选。

### 48.7 在身体里学：页面引擎与物理仿真（`learn/game_learning.js`、`learn/embodied_loop.py`）

两个身体、同一颗大脑、同一条规则。世界：正前方先是 A 味的烂果子（吃到糖 → PAM），再往前是 B 味的热源（烫 → PPL1）。

| | 页面引擎（六条腿的运动学身体） | 物理仿真（NeuroMechFly v2，MuJoCo，每 15 ms 同步） |
|---|---|---|
| 吃了 / PAM / PPL1 | {G['trained']['fed_s']} s / {G['trained']['pam_s']} s / {G['trained']['ppl1_s']} s | {em['eat_seconds']:.1f} s / — / {em['ppl1_seconds']:.1f} s |
| A 在奖赏隔室（训练 vs 不给多巴胺的对照） | 输入剩 {p0(G['trained']['memA']['PAM'])} vs {p0(G['control']['memA']['PAM'])} | MBON 响应 {em['after']['A']['PAM']:.0f} vs {en['after']['A']['PAM']:.0f} Hz（训练前 {em['before']['A']['PAM']:.0f}） |
| B 在惩罚隔室 | 输入剩 {p0(G['trained']['memB']['PPL1'])} vs {p0(G['control']['memB']['PPL1'])} | MBON 响应 {em['after']['B']['PPL1']:.0f} vs {en['after']['B']['PPL1']:.0f} Hz |
| 没学串（A 在惩罚隔室 / B 在奖赏隔室） | {p0(G['trained']['memA']['PPL1'])} / {p0(G['trained']['memB']['PAM'])} | 与对照之比 {E['E2_A_ppl1_vs_control']:.2f} / {E['E2_B_pam_vs_control']:.2f} |
| 终点 | x = {G['trained']['end_x']:.0f} mm | x = {em['end'][0]:.0f} mm；转向指令置 0 时 x = {eo['end'][0]:.0f} mm |

- 页面引擎：G1 奖赏记忆 {yn(G['criteria']['G1_reward_memory'])}、G2 惩罚记忆 {yn(G['criteria']['G2_punish_memory'])}、G3 对照不变 {yn(G['criteria']['G3_control_flat'])}。
- 物理身体：E1 奖赏记忆 {yn(E['criteria']['E1a_reward'])}；惩罚记忆 {yn(E['criteria']['E1b_punish'])}（只到对照的 {p0(E['E1_B_ppl1_vs_control'])}，判据 ≤ 70%）；E2 没学串 {yn(E['criteria']['E2_no_crosstalk'])}。
  惩罚记忆弱的原因是它**走到 B 味的热源跟前就自己掉头走了**，PPL1 只放了 {em['ppl1_seconds']:.1f} 秒。这个掉头没有人写，运动学身体和物理身体里都出现了。
  起初我以为是热把它转走的，分开测了才知道**主要是气味 B**（`learn/uturn_cause.js`，页面引擎，各 {U['seeds']} 个种子，源头在正前方 60 mm）：只放 B——左侧 DNa 最高 {U['odorB_only']['mean_max_dna_left']:.0f} Hz、总共转了 {U['odorB_only']['mean_total_turn_deg']:.0f}°、{U['odorB_only']['n_passed_through']} / {U['seeds']} 只走穿；
  只放热——{U['heat_only']['mean_max_dna_left']:.0f} Hz、{U['heat_only']['mean_total_turn_deg']:.0f}°、{U['heat_only']['n_passed_through']} / {U['seeds']} 只走穿；热 + B——{U['heat_and_B']['mean_max_dna_left']:.0f} Hz、{U['heat_and_B']['mean_total_turn_deg']:.0f}°、{U['heat_and_B']['n_passed_through']} / {U['seeds']} 只走穿；**只放 A——{U['odorA_only']['mean_max_dna_left']:.0f} Hz、{U['odorA_only']['mean_total_turn_deg']:.0f}°，和什么都不放一样**。
  也就是说，这两种合成气味在连接组里天生不一样：B 那 20 个嗅小球会推动左侧的转向神经元（总是左侧，和气味在哪边无关——与 48.1 全脑上「没有左右偏侧」一致），A 完全不会。§47 说「嗅觉没有通到转向」，那是只取了 DM1、DA2 两个小球的结论；小球取得多了，有的组合是通的。把大脑的转向指令换成 0（E3），它一路走穿四条气味带，终点与闭环相差 {E['E3_end_distance_closed_vs_open_mm']:.0f} mm，被烫 {eo['ppl1_seconds']:.1f} 秒，B 在惩罚隔室的响应掉到 {eo['after']['B']['PPL1']:.0f} Hz——闭环是真的，而且身体的行为决定了它学到什么。
- 二选一用**互换设计**（一组「A 配奖赏、B 配惩罚」，另一组反过来；两组用经典条件化训练——气味源跟着它走 5 秒、同时喷 PAM 或 PPL1，和 T 型迷宫一样由实验者控制；训练后 A 在奖赏隔室的输入：A 配奖赏组剩 {p0(G['classical']['A_rewarded']['memA']['PAM'])}、B 配奖赏组剩 {p0(G['classical']['B_rewarded']['memA']['PAM'])}。测试时 A、B 分在左前 / 右前，左右对调各一半；每组 {G['choice']['bridge_off']['naive']['n']} 只），比两组走向 A 的比例：
  **桥关着 {p0(G['choice']['bridge_off']['A_rewarded']['to_A'])} vs {p0(G['choice']['bridge_off']['B_rewarded']['to_A'])}**（G4 相差 < 20 个百分点，即记忆不改变选择：{yn(G['criteria']['G4_no_behavior_without_bridge'])}）；
  **打开手写的桥 {p0(G['choice']['bridge_on']['A_rewarded']['to_A'])} vs {p0(G['choice']['bridge_on']['B_rewarded']['to_A'])}**（G5 相差 ≥ 40 个百分点：{yn(G['criteria']['G5_bridge_works'])}——差 {(G['choice']['bridge_on']['A_rewarded']['to_A'] - G['choice']['bridge_on']['B_rewarded']['to_A']) * 100:.0f} 个百分点，有效果，但没到事先定的线；没有再去调桥的增益）。没训练过的有 {p0(G['choice']['bridge_off']['naive']['to_A'])} 走向 A——B 天生会把它转走（见上），所以必须互换。
  这一问走了三次弯路，都留了档：自由行走的互换训练做不成——B 味的果子它根本走不到（B 会把它转走，一口没吃上，`game_learning_choice_v2_failed.json`），所以互换两组改用经典条件化；第一轮比的是「训练过 vs 没训练过」、每组 12 只——没训练过的九成已经走向 A，判据没法成立，而且 12 只的标准误有 ±13 个百分点（`game_learning_choice_v1.json`；
  同一批种子只因为权重的浮点舍入变了一次，没训练过那组就从 75% 跳到 92%，可见单只的选择基本是噪声）；桥的第一版用 MBON 此刻的发放算「价」，MBON 只在羽流核心才放电，离远了价恒为 0（`game_learning_bridge_v1.json`）。
  第二版直接读突触里的记忆。这座桥整个是手写的，所以页面上默认关、单独标着。
- 速度：页面引擎（node 单线程）约 {G['realtime_factor']} × 实时；物理闭环 30 s 模拟 = 大脑 {em['wall_brain_s']:.0f} s + 身体 {em['wall_body_s']:.0f} s 墙钟。

### 48.8 能说什么、不能说什么

- **能说**：嗅觉失控的源头是局部神经元的递质符号，全脑上复核成立；加一条有文献依据的突触规则之后，连接组的蘑菇体会形成气味特异、需要时间重合、按隔室分工的记忆，隔室归属与解剖一致；
  这套东西在浏览器里接近实时地跑，与 Python 一致；大脑与一个六条腿的物理身体闭环之后，身体的行为（走到 B 跟前自己掉头）决定了它学到什么。
- **不能说**：「它靠记忆找到了食物」——记忆走不到运动输出，页面上能看到的趋近来自一座手写的、默认关着的桥。「多巴胺神经元被糖激活」——那根线是手接的。「六条腿由神经元控制」——大脑给的是几个下行神经元的发放，
  腿的节律与协调是手写的。气味 A / B 是合成的，不对应任何真实气味。可塑性规则的三个数是手选的，只在另外的种子上校准过。
<!-- §48:end -->"""
p = ROOT / "docs/log/report.md"; s = p.read_text()
if "<!-- §48:begin" in s: s = re.sub(r"<!-- §48:begin.*?<!-- §48:end -->", lambda m: text, s, flags=re.S)
else: s = s.rstrip("\n") + "\n\n" + text + "\n"
p.write_text(s); print("§48 已渲染", len(text), "字")
