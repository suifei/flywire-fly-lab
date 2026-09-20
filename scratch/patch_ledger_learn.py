#!/usr/bin/env python3
"""台账：学习 / 多巴胺 / 闭环 / 六条腿（§48）的发现与手选参数。可重复执行；verify 的数字在打补丁时从结果 JSON 读出。"""
import json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; R = ROOT / "results/learn"
J = lambda f: json.loads((R / f).read_text())
OC, FB, RR, C2, MM, MA, PAR, GL = J("mb_odor_coding.json"), J("fullbrain_alln.json"), J("reinforcement_route.json"), J("mb_conditioning.json"), J("memory_to_motor.json"), J("memory_to_motor_no_apl_mbon.json"), J("parity.json"), J("game_learning.json")
S = J("learn_summary.json"); E = S["embodied"]; LG = json.loads((ROOT / "results/dodge/legs_test.json").read_text())
raw, inh = OC["arms"]["raw"], OC["arms"]["alln_inh"]; fr, fi = FB["arms"]["raw"], FB["arms"]["alln_inh"]; lat = FB["lateralization"]
cc, sh = C2["arms"]["connectome"], C2["arms"]["shuffle_pn_kc"]; g = GL; em = E["main_s1"]
new = f'''    dict(id="olfactory_runaway_source", what="嗅觉输入在这个模型里为什么一给就全脑失控（§11.4 挂了六天的问题）",
         status="reproduced",
         result="**源头是触角叶局部神经元（ALLN）的递质符号**。把它们发出的突触改成抑制性（文献里它们绝大多数是 GABA / 谷氨酸能）："
                "蘑菇体回路里活跃的凯尼恩细胞从 **{raw['max_kc_frac'] * 100:.1f}% 降到 {inh['max_kc_frac'] * 100:.1f}%**（真果蝇约 5–10%），不同气味的 KC 集合几乎不重合（Jaccard {inh['cross_odor_jaccard_median']:.3f}）；"
                "**回到全脑复核**：原样 {fr['n_runaway']} / {fr['n_runs']} 次失控（其他活跃神经元中位 {fr['median_active']:.0f}），改后 **{fi['n_runaway']} / {fi['n_runs']}**（中位 {fi['median_active']:.0f}）。事先写下的预测成立",
         caveat="这是对递质符号的纠正（手选的建模决定，登记在 PARAMETERS），不是行为规则。全脑复核用的是自写的 numba LIF（方程、参数、每步顺序与 Brian2 版相同），不是 Brian2 本身。"
                "不失控之后单侧气味仍然**没有左右偏侧**（LI {lat['left']['LI']:+.2f} / {lat['right']['LI']:+.2f}，判据 |LI| ≥ 0.2 且符号相反）",
         script="learn/fullbrain_alln.py", result_file="results/learn/fullbrain_alln.json", log="§48.1",
         verify=[("arms.raw.n_runaway", {fr['n_runaway']}, 0), ("arms.alln_inh.n_runaway", {fi['n_runaway']}, 0), ("arms.alln_inh.median_active", {fi['median_active']}, 0.5), ("prediction_holds", True, 0), ("lateralization.lateralized", {lat['lateralized']}, 0)]),
    dict(id="dopamine_not_recruited", what="糖 / 苦 / 热 / 湿这些感觉，能不能靠真实接线把多巴胺神经元（PAM / PPL1）叫起来",
         status="negative",
         result="**不能**。专门为这个问题裁的回路（{RR['n']:,} 个神经元：蘑菇体 ∪ v4 ∪ 所有「感觉 → DAN」≤3 跳路径）里，四种感觉各三档强度共 {len(RR['conditions'])} 个条件，没有一个失控，"
                "而发放 ≥5 Hz 的多巴胺神经元**最多 {RR['max_dan_ge5hz_without_runaway']} 个**。与 §11.1 的全脑结果一致，并补上了热和湿",
         caveat="结构上是通的（最少 2–3 跳）。推测原因同 §11.1：真实的奖赏通路走章鱼胺 / 神经肽等慢调质，模型只有快递质符号。"
                "所以学习实验和页面里的强化信号是**手接的一根线**（吃到糖 → PAM、烫 / 苦 → PPL1），等价于实验里用光遗传激活多巴胺神经元",
         script="learn/reinforcement_route.py", result_file="results/learn/reinforcement_route.json", log="§48.2",
         verify=[("any_route", False, 0), ("max_dan_ge5hz_without_runaway", {RR['max_dan_ge5hz_without_runaway']}, 0)]),
    dict(id="mushroom_body_learning", what="给连接组的蘑菇体加一条文献里的突触规则（多巴胺门控的 KC→MBON 压低），它学得会吗",
         status="partial",
         result="**学得会，特异性差一点**。训练后被强化隔室的 MBON 对配对气味的响应降到对照的 **{cc['median_ratio_paired_csp']:.2f}**（L1 ≤ 0.7 成立）；多巴胺与气味错开给则不变（{cc['median_ratio_unpaired_csp']:.2f}，L3 成立）；"
                "PAM 与 PPL1 各压低 {cc['n_depressed']['PAM']} / {cc['n_depressed']['PPL1']} 个 MBON、重合 {cc['compartment_jaccard']:.2f}（L4 成立，MBON11 落在 PPL1 一侧，与解剖一致）；"
                "**没配对的气味也掉到 {cc['median_ratio_paired_csm']:.2f}（L2 ≥ 0.85 不成立）**",
         caveat="这是第二次尝试：第一次（mb_conditioning_v1.json）三条判据不过，原因是设计（多巴胺全局归一、学习率过大、气味对本身相似、指标被无关隔室稀释），在看新结果之前改掉、阈值不变。"
                "打乱 ALPN→KC 接线后照样学得会（{sh['median_ratio_paired_csp']:.2f}，事先写下的预期），特异性更差（{sh['median_ratio_paired_csm']:.2f}）：连接组的贡献在隔室，不在这一层的具体接线。"
                "强化信号手接；学习率 / 资格迹时间常数手选，只在另外的种子上校准过；气味是合成的（各 20 个嗅小球）",
         script="learn/mb_conditioning.py", result_file="results/learn/mb_conditioning.json", log="§48.3",
         verify=[("arms.connectome.median_ratio_paired_csp", {cc['median_ratio_paired_csp']}, 0.001), ("arms.connectome.median_ratio_paired_csm", {cc['median_ratio_paired_csm']}, 0.001), ("arms.connectome.median_ratio_unpaired_csp", {cc['median_ratio_unpaired_csp']}, 0.001),
                 ("arms.connectome.criteria.L2_specific", False, 0), ("arms.connectome.compartment_jaccard", {cc['compartment_jaccard']}, 0.001), ("arms.shuffle_pn_kc.criteria.L1_learned", True, 0)]),
    dict(id="memory_to_motor", what="蘑菇体里形成的记忆，走不走得到运动输出（前进 oDN1 / BDN2、转向 DNa01 / 02、后退 MDN）",
         status="negative",
         result="**走不到**。训练后各测 {MM['n_test']} 次，{MM['n_rows']} 组（气味对 × PAM / PPL1）里，五个读出满足「Welch |t| ≥ 3 且差 ≥ 20%」的组数最多 **{MM['max_hits']}**。"
                "原因：有运动落点的四类 MBON（12 / 26 / 27 / 35）对气味一个脉冲都没有，被 APL 压死——APL 在真果蝇里不放电，LIF 把它当放电神经元、顶着不应期上限放电",
         caveat="事先声明只试一次的一刀（切掉 APL→MBON）：有响应的 MBON 类型增到 {MA['n_mbon_types_responsive']} / {MA['n_mbon_types']}，记忆传到了一些别的下行神经元（探索性），但五个读出仍是 {MA['max_hits']} 组，判据不成立；**这一刀没有采用**。"
                "所以页面上的「记忆 → 转向的桥」是手写的、默认关",
         script="learn/memory_to_motor.py", result_file="results/learn/memory_to_motor.json", log="§48.4",
         verify=[("M2_any_stable", False, 0), ("max_hits", {MM['max_hits']}, 0), ("n_rows", {MM['n_rows']}, 0)]),
    dict(id="learning_engine_parity", what="页面引擎（brain.js 稀疏推进 + plasticity.js）与 Python 在同一份 v5 回路上学到的一样吗",
         status="reproduced",
         result="**一样**。同一个条件化流程、4 个种子：未配对气味的 MBON 总发放 {PAR['js']['mbon_B_mock']:.1f} 对 {PAR['py']['mbon_B_mock']:.1f} Hz；各 MBON 的突触剩余强度相关 r = {PAR['strength_pearson']:.4f}；四条事先写好的判据全过",
         caveat="页面引擎那一半是 learn/parity_js.js。两边随机数不同，比的是统计量。稀疏推进不逐位等于稠密推进（回静息用了阈值、同一步内求和顺序不同），所以球场 / 五子棋（v3）不开它",
         script="learn/parity_py.py", result_file="results/learn/parity.json", log="§48.5",
         verify=[("all_pass", True, 0), ("strength_pearson", {PAR['strength_pearson']}, 0.0001)]),
    dict(id="six_leg_body", what="让身体由六条腿推着走（支撑脚的运动学解出身体位移），而不是按速度滑行",
         status="reproduced",
         result="四条事先写好的判据全过：直行 {LG['tests']['T1_straight']['path_speed']:.2f} mm/s（指令 18）、转向 {LG['tests']['T2_turn']['left']['yaw_deg_s']:+.1f} / {LG['tests']['T2_turn']['right']['yaw_deg_s']:+.1f} °/s（指令 ±60）、后退 {LG['tests']['T3_back']['signed_x']:.2f} mm/s（指令 −12）、任何时刻着地 ≥ {LG['tests']['T4_support']['min_stance']} 条腿。"
                "截掉左前腿：速度 {LG['explore']['amputate_LF']['path_speed']:.1f} mm/s、偏航 {LG['explore']['amputate_LF']['yaw_deg_s']:+.0f} °/s",
         caveat="运动学，没有动力学和打滑；推进相按匀速直线理想化（直接回放录制的足尖轨迹会凭空转出 ±15° 的摆动）。**腿的节律与腿间协调是手写的**——腹神经索连接组给不出三足步态（§12）；大脑给的只是几个下行神经元的发放。截肢后没有适应",
         script="dodge/legs_test.js", result_file="results/dodge/legs_test.json", log="§48.6",
         verify=[("all_pass", True, 0), ("tests.T1_straight.path_speed", {LG['tests']['T1_straight']['path_speed']}, 0.01), ("tests.T4_support.min_stance", {LG['tests']['T4_support']['min_stance']}, 0)]),
    dict(id="embodied_learning", what="大脑 + 身体闭环之后，它在身体里学得会吗（页面引擎的六条腿身体；物理仿真的 NeuroMechFly）",
         status="partial",
         result="**奖赏记忆两个身体里都成立**：页面引擎里 A 在奖赏隔室的输入剩 {g['trained']['memA']['PAM'] * 100:.0f}%（对照 {g['control']['memA']['PAM'] * 100:.0f}%）；物理身体里 MBON 响应 {em['after']['A']['PAM']:.0f} 对 {E['noreinf_s1']['after']['A']['PAM']:.0f} Hz。"
                "**惩罚记忆在物理身体里不成立**（只到对照的 {E['E1_B_ppl1_vs_control'] * 100:.0f}%，判据 ≤ 70%）：它走到 B 味的热源跟前就自己掉头走了，PPL1 只放了 {em['ppl1_seconds']:.1f} s。"
                "二选一（互换设计，每组 {g['choice']['bridge_off']['naive']['n']} 只，走向 A 的比例，「A 配糖」组 vs「B 配糖」组）：桥关着 {g['choice']['bridge_off']['A_rewarded']['to_A'] * 100:.0f}% vs {g['choice']['bridge_off']['B_rewarded']['to_A'] * 100:.0f}%；打开手写的桥 {g['choice']['bridge_on']['A_rewarded']['to_A'] * 100:.0f}% vs {g['choice']['bridge_on']['B_rewarded']['to_A'] * 100:.0f}%",
         caveat="那个掉头没有人写，两个身体里都出现；分开测（learn/uturn_cause.js）主要是**气味 B** 引起的（只放 B：左侧 DNa {S['uturn']['odorB_only']['mean_max_dna_left']:.0f} Hz、{S['uturn']['odorB_only']['n_passed_through']}/{S['uturn']['seeds']} 走穿；只放热 {S['uturn']['heat_only']['n_passed_through']}/{S['uturn']['seeds']} 走穿；只放 A 毫无反应）——两种合成气味在连接组里天生不一样。把转向指令置 0 它就一路走穿、被烫 {E['openloop_s1']['ppl1_seconds']:.1f} s、惩罚记忆很强——身体的行为决定了它学到什么。"
                "物理闭环（learn/embodied_loop.py）只跑了 1 个种子、30 s。桥是手写的（第一版不起作用，见 game_learning_bridge_v1.json），默认关。二选一的第一轮设计（训练过 vs 没训练过、每组 12 只）因天花板效应和样本太小作废，留在 game_learning_choice_v1.json",
         script="learn/game_learning.js", result_file="results/learn/game_learning.json", log="§48.7",
         verify=[("criteria.G1_reward_memory", True, 0), ("criteria.G2_punish_memory", True, 0), ("criteria.G3_control_flat", True, 0), ("criteria.G4_no_behavior_without_bridge", {g['criteria']['G4_no_behavior_without_bridge']}, 0), ("criteria.G5_bridge_works", {g['criteria']['G5_bridge_works']}, 0),
                 ("trained.memA.PAM", {g['trained']['memA']['PAM']}, 0.001)]),
'''
p = ROOT / "scripts/reproduction_data.py"; s = p.read_text()
s = re.sub(r'    dict\(id="olfactory_runaway_source".*?log="§48\.7",\n         verify=\[[^\n]*\n?[^\n]*\]\),\n', "", s, flags=re.S)
k = s.index('    dict(id="hearing_priming"'); s = s[:k] + new + s[k:]
params = '''    dict(name="蘑菇体回路：两处建模决定", value="触角叶局部神经元（ALLN，429 个）发出的突触一律取抑制性；页面用的 v5 里碰到蘑菇体的边只留 ≥2 个突触的", source="①有文献依据（Wilson & Laurent 2005；Olsen & Wilson 2008；Liu & Wilson 2013），**但属于手选的建模决定**；②工程取舍",
         code_check=("dodge/subcircuit_v5.py", r"MB_WMIN = (\\d+)", "2"),
         note="①不改的话一闻到气味整个回路就失控；三个臂（原样 / 改抑制性 / 去掉）都跑了，按事先规则取改动最小且判据全过的。②全留是 129 万条边，页面装不下；裁完之后的回路与 Python 做过一致性检验（learning_engine_parity）",
         script="learn/mb_odor_coding.py", log="§48.1 + §48.5"),
    dict(name="可塑性规则与强化信号", value="学习率 0.003、KC 资格迹 200 ms、不遗忘；强化 = PAM 或 PPL1 整簇 30 Hz；气味 = 20 个嗅小球的 ORN 200 Hz；热到 0.5 以上算烫", source="规则形式来自文献（Hige 2015；Cohn 2015；Handler 2019），**数值手选**",
         code_check=("dodge/game_core.js", r"danRate: (\\d+), painThermo: ([\\d.]+), plastEta: ([\\d.]+), plastTauE: (\\d+)", "30/0.5/0.003/200"),
         note="学习率、气味宽度、频率只在另外的种子（5、6、999）上校准过，判据用的 6 对气味没有看过。第一次尝试的学习率 0.02 太大（1 秒配对压到 7%）。「糖 / 烫 → 多巴胺」这根线是手接的，因为连接组自己叫不起多巴胺神经元",
         script="learn/plasticity.py", log="§48.3"),
    dict(name="六条腿的身体", value="腿间相位耦合 8、失稳拖行的虚拟脚权重 0.6、着地判据足尖高 < 0.12 mm、重心在胸部原点后 0.2 mm", source="**手选**",
         code_check=("dodge/legs.js", r"coupling: (\\d+), drag: ([\\d.]+)", "8/0.6"),
         note="足尖轨迹与步幅来自 NeuroMechFly 录制的步态周期；「步幅差 → 偏航」的增益在创建时用同一套运动学数值标定，不是手调的",
         script="dodge/legs.js", log="§48.6"),
    dict(name="记忆 → 转向的桥（默认关）", value="价 = 奖赏隔室被压掉的比例 − 惩罚隔室被压掉的比例；转向 = 价 × 150 °/s × 两根触角浓度差的符号", source="**整个是手写的**",
         code_check=("dodge/game_core.js", r"memoryNav: (false), memoryTurn: (\\d+)", "false/150"),
         note="实测记忆走不到运动输出（memory_to_motor，阴性），这座桥只是让页面上能看到「学了之后会怎样」，默认关、单独标着。第一版用 MBON 的瞬时发放，不起作用",
         script="dodge/game_core.js", log="§48.7"),
'''
s = re.sub(r'    dict\(name="蘑菇体回路：两处建模决定".*?script="dodge/game_core\.js", log="§48\.7"\),\n', "", s, flags=re.S)
k2 = s.index("]\n\n# ── 本项目自己的结果"); s = s[:k2] + params + s[k2:]
p.write_text(s); print("台账已加 7 条发现 + 4 个手选参数（学习 / 多巴胺 / 闭环 / 六条腿）")
