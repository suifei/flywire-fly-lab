#!/usr/bin/env python3
"""README 的「学习 / 多巴胺 / 六条腿」一节（<!-- learn:begin/end -->），数字取自 results/learn/learn_summary.json。可重复执行。"""
import json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; L = json.loads((ROOT / "results/learn/learn_summary.json").read_text())
oc, fb, rf, C, M, P, LG, G, E, V = L["odor_coding"], L["fullbrain"], L["reinforcement"], L["conditioning"], L["memory_to_motor"], L["parity"], L["legs"], L["game"], L["embodied"], L["v5"]
cc = C["connectome"]; em = E["main_s1"]; p0 = lambda v: f"{v * 100:.0f}%"; yn = lambda b: "成立" if b else "**不成立**"
sec = f"""<!-- learn:begin （本节由 scratch/patch_readme_learn.py 从 results/learn/learn_summary.json 渲染）-->
## 学习、多巴胺、闭环、六条腿

「生活」模式的果蝇现在用子回路 v5：**{V['n']:,} 个神经元、{V['n_edges']:,} 条边** = v4 ＋ 连接组里的蘑菇体学习回路（凯尼恩细胞 {V['n_tag']['KC']:,}、蘑菇体输出神经元 {V['n_tag']['MBON']}、多巴胺神经元 {V['n_tag']['DAN']}）。
接线全部来自 FlyWire；唯一会变的是凯尼恩细胞 → MBON 这一层突触：凯尼恩细胞刚放过电、同一隔室里又有多巴胺，突触就被压低（文献里果蝇嗅觉记忆的位置与规则）。哪个多巴胺神经元管哪个隔室由连接组决定。
身体由**六条腿**推着走（支撑脚的运动学解出身体的位移和转角），可以截腿、可以按住按钮直接遥控某几个神经元。
**在 3D 篮球场里也能用它**：「篮球场」控件最上面的「大脑」开关切到「五感全开」，球场里那只 3D 果蝇就换成这颗 15,055 个神经元的大脑（同一只、同一份记忆），气味、热源、声音画进球场，六条腿各按自己的相位走；任务 / 突变体 / 光遗传仍属于 5,563 个神经元的球场版。判据都写在跑之前：

| 问题 | 结果 |
|---|---|
| 嗅觉为什么一给就全脑失控（§11.4 的老问题） | **源头是触角叶局部神经元的递质符号**。改成抑制性（文献依据）后，活跃的凯尼恩细胞 {oc['raw']['max_kc_frac'] * 100:.0f}% → {oc['alln_inh']['max_kc_frac'] * 100:.1f}%；**全脑复核**：失控 {fb['raw']['n_runaway']}/{fb['raw']['n_runs']} → {fb['alln_inh']['n_runaway']}/{fb['alln_inh']['n_runs']} |
| 糖 / 苦 / 热 / 湿能靠真实接线叫起多巴胺神经元吗 | **阴性**：{rf['n_conditions']} 个条件里发放 ≥5 Hz 的多巴胺神经元{'一个都没有' if rf['max_dan'] == 0 else '最多 ' + str(rf['max_dan']) + ' 个'}。所以「吃到糖 → PAM、烫 → PPL1」这根线是手接的（等价于实验里的光遗传激活） |
| 它学得会吗 | **学得会，特异性差一点**：配对过的气味在被强化隔室的响应降到对照的 {cc['median_ratio_paired_csp']:.2f}；多巴胺与气味错开给则不变（{cc['median_ratio_unpaired_csp']:.2f}）；PAM 与 PPL1 压低的 MBON 互不重合（{cc['compartment_jaccard']:.2f}），与解剖一致；没配对的气味也掉到 {cc['median_ratio_paired_csm']:.2f}（判据 ≥ 0.85，不成立） |
| 打乱 投射神经元 → 凯尼恩细胞 的接线还学得会吗 | 学得会（{C['shuffle']['median_ratio_paired_csp']:.2f}；事先写下的预期）。连接组的贡献在隔室，不在这一层的具体接线 |
| 记住了，会改变行为吗 | **阴性**：训练后各测 {M['v5']['n_test']} 次，{'6 组运动读出没有一组显著变化'.replace('6', str(M['v5']['n_rows'])) if M['v5']['max_hits'] == 0 else '五个运动读出显著变化的组数最多 ' + str(M['v5']['max_hits']) + ' / ' + str(M['v5']['n_rows'])}。有运动落点的那几类 MBON 被 APL 压死（APL 在真果蝇里不放电，模型把它当放电神经元）。页面上的「记忆 → 转向的桥」是手写的、默认关 |
| 页面引擎与 Python 学到的一样吗 | 一样：突触剩余强度相关 r = {P['strength_pearson']:.4f}，四条判据全过 |
| 六条腿推得动身体吗 | 四条判据全过：直行 {LG['tests']['T1_straight']['path_speed']:.1f} mm/s（指令 18）、转向 {LG['tests']['T2_turn']['left_yaw']:+.0f} / {LG['tests']['T2_turn']['right_yaw']:+.0f} °/s（指令 ±60）。腿的节律与协调是手写的（腹神经索连接组给不出三足步态） |
| 大脑 + 物理身体闭环（NeuroMechFly，MuJoCo） | 奖赏记忆成立（MBON 响应 {em['after']['A']['PAM']:.0f} 对 {E['noreinf_s1']['after']['A']['PAM']:.0f} Hz）；惩罚记忆{yn(E['criteria']['E1b_punish'])}——它走到 B 味的热源跟前就**自己掉头走了**，只被烫了 {em['ppl1_seconds']:.1f} s。这个掉头没人写，两个身体里都出现；分开测主要是气味 B 引起的（B 会推动左侧转向神经元，A 完全不会） |

细节、第一次失败的尝试、只试一次没采用的那一刀：[docs/log/report.md §48](docs/log/report.md)。复现：`learn/` 下每个脚本开头的文档字符串写了用法和判据；`node dodge/legs_test.js`、`node learn/parity_js.js` + `python learn/parity_py.py compare`。
<!-- learn:end -->
"""
p = ROOT / "README.md"; s = p.read_text()
if "<!-- learn:begin" in s: s = re.sub(r"<!-- learn:begin.*?<!-- learn:end -->\n", lambda m: sec, s, flags=re.S)
else: ANCHOR = "<!-- limits:begin" if "<!-- limits:begin" in s else "## 它做不到什么（同样重要）"; s = s.replace(ANCHOR, sec + "\n" + ANCHOR, 1)
if "| `learn/` |" not in s: s = s.replace("| `language/` |", "| `learn/` | 蘑菇体学习回路：气味编码、强化通路、条件化、记忆→运动、全脑复核、页面引擎一致性、物理身体闭环 |\n| `language/` |", 1)
p.write_text(s); print("README 已更新（学习一节）")
