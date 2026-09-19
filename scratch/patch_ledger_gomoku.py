#!/usr/bin/env python3
"""一次性：把台账里五子棋 v1 的两条换成 v2 的五条 + 更新打乱对照那一条 + 登记手选参数。
verify 里的数字在打补丁的这一刻从结果 JSON 读出来写成字面量（台账要求字面量，reproduction.py 再逐个核对）——不经过人手。"""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; R = ROOT / "results/gomoku"
J = lambda f: json.loads((R / f).read_text())
T = J("train_lines.json"); A = T["arms"]; P = J("play_lines.json"); RL = J("rl.json"); RS = J("rl_small.json"); OL = J("opto_leak.json")
SC = json.loads((ROOT / "results/shuffle_controls.json").read_text()); DS = J("dataset_summary.json"); TN = J("table_noise.json"); SW = J("search_width.json")
fi, fs_, rw, rr, ft, tt = (A[k] for k in ("fly_intact", "fly_shuffled", "raw24", "rand_relu", "free_table", "teacher_table"))
pct = lambda v: f"{v * 100:.1f}%"; wl = lambda r: f"{r['win']}–{r['loss']}" + (f"–{r['draw']}" if r.get("draw") else "")
E = P["engine"]["fly_intact"]; HH = P["head_to_head"]; cA, cA2, cC2 = P["criterion_A"], P["criterion_A2"], P["criterion_C2"]
status_strength = "reproduced" if (cA["passed"] and cA2["passed"]) else "partial"

new = f'''    dict(id="gomoku_v1_retracted", what="五子棋 v1（把整盘棋铺进果蝇脑）的结论还算数吗",
         status="negative",
         result="**不算数，全部作废**。`brain.setOpto` 换一批神经元时不清上一批的刺激，输入一个接一个叠上去："
                "线型 A 单独喂是 **{OL['fixed']['A_first']}** 个脉冲，先喂过 B 再喂 A 得到 **{OL['old_behaviour']['A_after_B']}** 个，"
                "逐神经元与真正的 A 相差 {OL['old_behaviour']['abs_diff_vs_true_A']}。v1 的每个棋盘喂进去几乎是同一个输入，读出层学的是噪声",
         caveat="作废的数字：一致率 0.021 / 打乱 0.019 / 直接看棋盘 0.175、对随机 26/40、正面交锋 0:40、"
                "以及「连接组对下棋没有贡献」这句话——那个实验本身是坏的，它既不支持也不否定任何说法。"
                "**游戏不受影响**：`game_core` 每步用 `setRate` 整组重写输入；修复前后 7 个任务 + 10 个突变体的结果逐项相同。"
                "教训：一个「几乎等于随机」的阴性结果，第一反应应该是查输入有没有真的送进去",
         script="gomoku/test_engine.js", result_file="results/gomoku/opto_leak.json", log="§46.1",
         verify=[("fixed.A_first", {OL['fixed']['A_first']}, 0), ("old_behaviour.A_after_B", {OL['old_behaviour']['A_after_B']}, 0),
                 ("old_behaviour.abs_diff_vs_true_A", {OL['old_behaviour']['abs_diff_vs_true_A']}, 0), ("fixed.abs_diff_A_first_vs_again", 0, 0)]),
    dict(id="gomoku_lines", what="线型版：果蝇脑 + 一层线性读出，能学会给五子棋的每条线估价吗",
         status="reproduced",
         result="**能**。14,641 种线型每一种都在果蝇脑里跑一遍（脑里一个突触都不训练），线性读出给出每条线的对数价值。"
                "测试一致率 **{pct(fi['test_top1'])}**（随机 {pct(T['random_top1'])}、不经过脑子 {pct(rw['test_top1'])}）；"
                "外部考卷 Wine（别人的引擎，只考不训）**{pct(fi['wine_top1'])}**；换一组从未见过的泊松种子只掉 {fi['seed_drop'] * 100:.1f} 个百分点。"
                "它从没见过棋形类别，自己排出的价值顺序（成五 > 活四 > 冲四、活三 > …）全部正确",
         caveat="事先写好的判据 B（比不经过脑子高 ≥ 5 个点）与 D（换种子掉 ≤ 5 个点）成立。"
                "D 是改了三次训练才过的：单种子 60 ms 窗掉 32 个点、300 ms 掉 17、3 种子平均掉 5.3，加噪声增广才到 {fi['seed_drop'] * 100:.1f}，代价是一致率少约 3 个点。"
                "这条路能成靠的是线型可以**全部枚举**——泛化到没见过的线型很差（留出 20% 线型认棋形只有 0.72，活四召回 0.02）。"
                "架构上限（每种线型一个自由参数）也只有 {pct(ft['test_top1'])}，老师自己的手写分值 {pct(tt['test_top1'])}",
         script="gomoku/train_lines.py", result_file="results/gomoku/train_lines.json", log="§46.2–46.5",
         verify=[("arms.fly_intact.test_top1", {fi['test_top1']}, 0.0005), ("arms.fly_intact.wine_top1", {fi['wine_top1']}, 0.0005),
                 ("arms.fly_intact.seed_drop", {fi['seed_drop']}, 0.0005), ("arms.raw24.test_top1", {rw['test_top1']}, 0.0005),
                 ("arms.fly_intact.distill_r2", {fi['distill_r2']}, 0.0005),
                 ("criterion_B_brain_helps", {T['criterion_B_brain_helps']}, 0), ("criterion_D_not_noise_hash", {T['criterion_D_not_noise_hash']}, 0)]),
    dict(id="gomoku_wiring", what="真实接线比打乱接线、比随便一个随机网络更会下棋吗",
         status="negative",
         result="**不**。测试一致率：真实接线 {pct(fi['test_top1'])}、打乱接线 **{pct(fs_['test_top1'])}**、同维度随机 ReLU 网络 **{pct(rr['test_top1'])}**；"
                "正面交锋（同一个引擎）直觉 {wl(HH['d1'])}、想 4 步 {wl(HH['d4'])}、想 6 步 {wl(HH['d6'])}",
         caveat="事先写好的判据 C（一致率高 ≥ 5 个点）与 C2（想 4 步正面交锋 ≥ 60%）都不成立。"
                "打乱之后活跃的神经元多一倍（读出维度 {fs_['dim'] - 1} 对 {fi['dim'] - 1}），给读出层的特征更丰富——"
                "所以能说的是「这颗脑子是一个够用的非线性展开」，不能说「真实接线对下棋有特殊贡献」",
         script="gomoku/play_lines.js", result_file="results/gomoku/play_lines.json", log="§46.5–46.6",
         verify=[("head_to_head.d4.win", {HH['d4']['win']}, 0), ("head_to_head.d4.loss", {HH['d4']['loss']}, 0), ("criterion_C2.passed", {cC2['passed']}, 0)]),
    dict(id="gomoku_strength", what="放进搜索之后，它下得怎么样（用户的目标：棋力）",
         status="{status_strength}",
         result="想 6 步：对旧老师（v1 的对手，v1 是 0:40）**{wl(E['d6']['old_teacher'])}**，对老师搜 4 步 **{wl(E['d6']['teacher2_d4'])}**，对搜 6 步 {wl(E['d6']['teacher2_d6'])}，对搜 8 步 {wl(E['d6']['teacher2_d8'])}；"
                "想 10 步：对搜 6 步 {wl(E['d10']['teacher2_d6'])}、对搜 8 步 **{wl(E['d10']['teacher2_d8'])}**。只凭直觉：对随机 {wl(E['d1']['random'])}、对旧老师 {wl(E['d1']['old_teacher'])}",
         caveat="判据 A（直觉对旧老师 ≥ 50%）{'成立' if cA['passed'] else '**不成立**'}（{pct(cA['vs_old_teacher'])}）；A2（想 6 步对老师搜 4 步 ≥ 50%）{'成立' if cA2['passed'] else '不成立'}（{pct(cA2['d6_vs_teacher2_d4'])}）。"
                "**棋力主要来自搜索深度，不是来自果蝇**：向前推演是 alpha-beta 做的，搜索只懂规则（成五、必须挡五、禁手）、不含棋形分值；"
                "每多搜一步节点数约 ×2.2。每组 40 局（深度 8 的老师 20 局），标准差约 8 个百分点。"
                "表的精度也值棋力（给老师的表加噪声到 R² 0.85，同深度胜率从 {pct(TN['rows'][0]['win_rate'])} 掉到 {pct([r for r in TN['rows'] if r['r2'] == 0.85][0]['win_rate'])}），但这颗脑子可靠的精度上限在 R² ≈ 0.85–0.88",
         script="gomoku/play_lines.js", result_file="results/gomoku/play_lines.json", log="§46.6",
         verify=[("engine.fly_intact.d6.old_teacher.win", {E['d6']['old_teacher']['win']}, 0), ("engine.fly_intact.d6.teacher2_d4.win", {E['d6']['teacher2_d4']['win']}, 0),
                 ("engine.fly_intact.d10.teacher2_d8.win", {E['d10']['teacher2_d8']['win']}, 0), ("engine.fly_intact.d1.old_teacher.win", {E['d1']['old_teacher']['win']}, 0),
                 ("criterion_A.passed", {cA['passed']}, 0), ("criterion_A2.passed", {cA2['passed']}, 0)]),
    dict(id="gomoku_rl", what="自对弈强化（「多巴胺」式三因子规则）能让它更强吗",
         status="negative",
         result="**不能**。Δw = 学习率 × δ × 资格迹，δ = 这一局的结果 − 近期平均。强化后的表对监督版（同一个引擎都想 4 步，200 局）"
                "**{wl(RL['final']['d4_vs_supervised_d4'])}（{pct(RL['win_rate_vs_supervised'])}）**，事先定的线是 55%；换更小的步长、更多的局数再跑一次是 {wl(RS['final']['d4_vs_supervised_d4'])}（{pct(RS['win_rate_vs_supervised'])}）",
         caveat="**δ 是在连接组外面算的**：这个模型自己的多巴胺神经元在非失控条件下不放电（§11，PAM 0/307），不存在「果蝇自己的奖励信号」。"
                "每轮几十局的胜负太吵，推不动一个 {fi['dim']} 维的读出层。页面上的果蝇用的是监督训练的表",
         script="gomoku/selfplay_rl.js", result_file="results/gomoku/rl.json", log="§46.7",
         verify=[("final.d4_vs_supervised_d4.win", {RL['final']['d4_vs_supervised_d4']['win']}, 0), ("criterion_passed", {RL['criterion_passed']}, 0),
                 ("win_rate_vs_supervised", {RL['win_rate_vs_supervised']}, 0.0005)]),
'''
p = ROOT / "scripts/reproduction_data.py"; s = p.read_text()
a = s.index('    dict(id="gomoku_reservoir"'); b = s.index('    dict(id="touch_pathway"')
s = s[:a] + new + s[b:]
# 打乱对照那一条
gi, gs = SC["gomoku"]["intact"]["mean_active_per_position"], SC["gomoku"]["shuffled"]["mean_active_per_position"]
s = re.sub(r'"五子棋水库\*\*反而更活跃\*\*——每个局面活跃神经元 1795 → \*\*3055\*\*"', f'"五子棋水库**反而更活跃**——每种线型活跃神经元 {gi:.0f} → **{gs:.0f}**（线型版特征；v1 的 1795 / 3055 随 v1 一起作废）"', s)
s = s.replace('"五子棋那一行还顺带解释了 §41.6 的翻盘：打乱脑下棋「更强」很可能只是因为"\n                "**它给读出层的特征更丰富**（打乱破坏抑制的特异性 → 整体更易兴奋），而不是它更懂棋"',
              '"五子棋那一行也解释了 §46 里打乱接线为什么不输：**它给读出层的特征更丰富**"\n                "（打乱破坏抑制的特异性 → 整体更易兴奋，读出维度多一倍），而不是它更懂棋"')
s = s.replace('("gomoku.shuffled.mean_active_per_position", 3055.2, 0.1),', f'("gomoku.shuffled.mean_active_per_position", {gs}, 0.1),')
s = s.replace('("gomoku.intact.mean_active_per_position", 1795.3, 0.1),', f'("gomoku.intact.mean_active_per_position", {gi}, 0.1),')
# 手选参数
params = '''    dict(name="五子棋老师的线型分值", value="成五 1e7 / 活四 1e5 / 冲四 2000 / 活三 1500 / 眠三 120 / 活二 100 / 眠二 10 / 单子 1", source="**手选**",
         code_check=("gomoku/teacher2.js", r"const ATT = \\[0, 1, 10, 100, 120, (1500), 2000, 1e5, 1e7\\]", "1500"),
         note="不是任何论文或引擎的值；老师的棋力主要来自搜索深度。它也是果蝇读出层阶段一的拟合目标（取 ln(分值+1)），所以果蝇学到的价值顺序是老师给的，不是它自己发现的",
         script="gomoku/teacher2.js", log="§46.3"),
    dict(name="五子棋线型的驱动", value="160 Hz × 300 ms，每通道约 61 个输入神经元，3 个泊松种子取平均", source="本项目按实测选定",
         code_check=("gomoku/line_map.js", r"const ms = opt\\.ms \\?\\? (\\d+), hz = opt\\.hz \\?\\? (\\d+)", "60/160"),
         note="窗口长度按「特征跨种子的相关」选：60 ms 中位 0.44、150 ms 0.77、300 ms 0.87（代码里的缺省 60 ms 只是缺省，流水线显式传 300）。通道→神经元的分配是固定种子的随机洗牌，是任意的",
         script="gomoku/line_features.js", log="§46.4"),
    dict(name="五子棋搜索引擎", value="每层宽度 K = 6（根 16）、先手系数 1.2", source="K 实测选定；先手系数**手选**",
         code_check=("gomoku/engine.js", r"const K = o\\.K \\?\\? (\\d+), K0", "6"),
         note="同等节点预算下 K=6 对 K=10 是 62–38（100 局）；先手系数 1.0 / 1.5 / 2.0 对 1.2 都在噪声里（46–54、55–45、51–48）。这两个属于搜索，不属于果蝇",
         script="gomoku/engine.js", log="§46.6"),
'''
if "五子棋老师的线型分值" not in s:
    k = s.index("]\n\n# ── 本项目自己的结果"); s = s[:k] + params + s[k:]
p.write_text(s); print("台账已打补丁；gomoku_strength 的状态 =", status_strength)
