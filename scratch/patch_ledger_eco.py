#!/usr/bin/env python3
"""台账：生态箱（§50）。可重复执行；status 与 verify 的数字在打补丁时从 results/eco/summary.json 读出。"""
import json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
S = json.loads((ROOT / "results/eco/summary.json").read_text()); sf, m2, m3, m4, lv, au = (S[k] for k in ("surface", "m2", "m3", "m4", "live", "audit"))
r2 = {f["name"]: f["r2"] for f in sf["features"]}; i0 = m2["individuals"][0]; lg = S["long"]; nd = m2.get("no_decay"); tr = S["transfer"]; mf = sf["manifold"] or {"learned": "?", "wall": "?", "rest": "?"}
m3w = "；".join(f"{w['name']} {w['label']}（Δ 均值 {w['delta_mean']:+.2f}，寿命 {w['life_head']} → {w['life_tail']} s，先天喝水 {w['drink']:+.2f}）" for w in m3["worlds"])
new = f'''    dict(id="eco_surface", what="生态箱：把 15,055 个神经元的真脑蒸馏成响应面（27 路输入 → 12 个读出），好让 32 只果蝇的进化跑得动",
         status="{'reproduced' if sf['pass'] else 'partial'}",
         result="真脑一只 {au['realtime_one']} 倍实时、32 只 {au['realtime_32']} 倍。用真脑跑 {sf['n_samples']:,} 组输入拟合；留出集（单次试验、原始 Hz）R²：左转 {r2['dnaL']:.3f}、右转 {r2['dnaR']:.3f}、巨纤维 {r2['gf']:.3f}、MN9 {r2['mn9']:.3f}（事先定的线 ≥ {sf['r2_min']}）。"
                "第一版（{sf['v1_samples']:,} 个样本、log1p 目标）转向只有 {sf['v1_dna']}，没过线，留档在 surface_fit_v1.json",
         caveat="响应面没有记忆（真脑在两次决策之间保留状态），给的是 300 ms 窗的平均发放率，单次试验的噪声按泊松加回去。PAM 在全部样本里从不放电，响应面里恒为 0。判据没动，动的是目标变换（log1p → sqrt）和样本量",
         script="eco/fit_surface.py", result_file="results/eco/summary.json", log="§50.3",
         verify=[("surface.pass", {1 if sf['pass'] else 0}, 0), ("surface.n_samples", {sf['n_samples']}, 0), ("surface.features.0.r2", {r2['dnaL']}, 0.0001), ("surface.features.2.r2", {r2['gf']}, 0.0001)]),
    dict(id="eco_m2_learning", what="生态箱 M2：只给物理量和内生奖励（身体不适的减少），接在固定连接组旁边的可塑性层能不能自己学会活得更久",
         status="partial",
         result="3 个个体各连续 {m2['train_lives']} 条命后冻结学习，在 {m2['test_lives']} 个没见过的世界上测：不学习 {i0['off']} s，学习 ≥ {i0['on']} s（截尾，× {i0['ratio_on']}）；C1（≥ 1.5 ×）{'3/3 通过' if m2['C1'] else '未通过'}，C2（打乱奖励不提升）{'3/3 通过' if m2['C2'] else '未通过'}；另换 10 个个体 {m2['robust_learned']}/{m2['robust_n']} 学成；长期训练任务（eco/train_long.js，又 10 个新个体，学成即毕业）{lg['n_learned']}/{lg['n']} 学成、换新世界复测 {lg['n_retest_ok']}/{lg['n']}，共 {lg['total_lives']} 条命。"
                "学到的是「碰到水就停下来喝」（连接组里水味先天不够伸喙）和「湿度上升时少拐弯」",
         caveat="标 partial 的原因：**远距离找水 / 找食物没学会**（干旱世界不学习 {m2['drought_off']} s、学习 {m2['drought_on']} s，训练 120 条命 {m2['long_lives120']} s）；可塑性层看不到大脑输出时学得一样好（× {i0['ratio_nobrain']}）——连接组在这里给的是身体和反射，不是学习信号。"
                "第一版 C2 只过了 {m2['v1_C2']}（打乱对照是漏的：奖励只延后 20–60 s，与持续几十秒的喝水仍相关；事后加的轭式对照不提升）。关掉「不用就忘」10 个个体只有 {nd['learned']} 学成（{nd['wall']} 个贴墙、{nd['rest']} 个躺平）。寿命在 {m2['cap_s']:,} s 截尾，倍数是下限",
         script="eco/m2_learning.js", result_file="results/eco/summary.json", log="§50.4",
         verify=[("m2.C1", {1 if m2['C1'] else 0}, 0), ("m2.C2", {1 if m2['C2'] else 0}, 0), ("m2.individuals.0.ratio_on", {i0['ratio_on']}, 0.001), ("m2.robust_learned", {m2['robust_learned']}, 0), ("long.n_learned", {lg['n_learned']}, 0), ("long.n_retest_ok", {lg['n_retest_ok']}, 0), ("m2.drought_on", {m2['drought_on']}, 0)]),
    dict(id="eco_m3_evolution", what="生态箱 M3：32 只果蝇、10 个可遗传参数、没有适应度函数——不同的世界规则会不会把「飞行倾向」推向不同方向",
         status="{'reproduced' if m3['pass'] else 'negative'}",
         result="三个世界各 {m3['n_seeds']} 个种子 × {m3['seconds']:,} s：{m3w}。事先写定的判据（至少两个世界标签不同）{'通过' if m3['pass'] else '**未通过**'}",
         caveat="飞行是固定的 1.2 s / 72 mm 弹道，能进化 / 能学的只有「起不起飞」（飞行控制没接进连接组，见 docs/ecobox/AUDIT.md）。3 小时箱内时间只有几到十几代，种群 32 只，漂变不小。可塑性层不遗传；种群快灭绝时从名人堂补进来的个体单独计数（迁入）。变异幅度手选",
         script="eco/m3_evolution.js", result_file="results/eco/summary.json", log="§50.5",
         verify=[("m3.pass", {1 if m3['pass'] else 0}, 0), ("m3.worlds.0.delta_mean", {m3['worlds'][0]['delta_mean']}, 0.001), ("m3.worlds.1.delta_mean", {m3['worlds'][1]['delta_mean']}, 0.001), ("m3.worlds.2.delta_mean", {m3['worlds'][2]['delta_mean']}, 0.001)]),
    dict(id="eco_live_check", what="生态箱：在响应面上学成的个体，放回真的 15,055 神经元脉冲网络里还管不管用",
         status="{'reproduced' if lv['L1'] and lv['L2'] else 'partial' if lv['L1'] or lv['L2'] else 'negative'}",
         result="{lv['lives']} 个世界种子、上限 {lv['cap_s']} s：真脑 {lv['live_median']} s，响应面 {lv['surface_median']} s，白纸 {lv['naive_median']} s。L1（真脑 ≥ 1.5 × 白纸）{'通过' if lv['L1'] else '未通过'}（× {lv['ratio_live_vs_naive']}）；L2（喝水时间占比在响应面的 0.5–2 倍内）{'通过' if lv['L2'] else '未通过'}（{lv['drink_live']} 对 {lv['drink_surface']}）",
         caveat="只有 3 条命、上限 {lv['cap_s']} s（真脑约 1.2 倍实时）。真脑的读出按约 300 ms 平滑以对齐响应面的噪声窗口",
         script="eco/live_check.js", result_file="results/eco/summary.json", log="§50.7",
         verify=[("live.live_median", {lv['live_median']}, 0), ("live.naive_median", {lv['naive_median']}, 0)]),
    dict(id="eco_transfer", what="生态箱学成的个体搬进 3D 大自然（真脑 + 有重力天气甲虫的世界）还管不管用；训练条件先对齐到大自然",
         status="{'reproduced' if tr['pass'] else 'partial' if tr['X1']['pass'] or tr['X2']['pass'] else 'negative'}",
         result="5 个世界种子 × 900 s，同种子对比白纸，权重冻结；有信息的种子 {tr['n_informative']} 个。X1（喝得更久 {tr['X1']['more_drink_time']}，每次碰到水喝 {tr['X1']['drinks_per_visit_trained']} 对 {tr['X1']['drinks_per_visit_naive']} 次）{'通过' if tr['X1']['pass'] else '未通过'}；X2（更不渴 {tr['X2']['lower_mean_thirst']}）{'通过' if tr['X2']['pass'] else '未通过'}。"
                "响应面第三版加了闭环工况（{mf['n']:,} 组，含大自然里记下的 9,000 组）：只尝到水的 MN9 误差 {100 * mf['points'][0]['rel_err']:.1f}%（第二版约 40%），真脑指数 {mf['index']}",
         caveat="学成的只是「碰到水就喝」与趋湿；大自然里能喝的水（洼地）少，5 个种子里有的臂整条命没碰到水。响应面 T2 未通过（左转 DNa {mf['features'][0]['r2']:.3f}，闭环工况上它的噪声天花板实测 {mf['dnaL_ceiling']}，线定得高于真脑的可重复性，照原线登记）。旧感觉编码下的 M2 / M3 / 长期训练结果留在本机 old_senses/，不入库",
         script="eco/nature_transfer.js", result_file="results/eco/summary.json", log="§50.7b",
         verify=[("transfer.pass", {1 if tr['pass'] else 0}, 0), ("transfer.n_informative", {tr['n_informative']}, 0), ("surface.manifold.index", {mf['index']}, 0.01)]),
    dict(id="eco_m4_save", what="生态箱 M4：存档 → 清空 → 读回 → 接着跑，是否与不中断逐位相同",
         status="{'reproduced' if m4['pass'] else 'partial'}",
         result="四项全过：续跑状态指纹相同（{m4['fingerprint']}）、存档格式稳定、挑战码（{m4['code_chars']} 个字符）来回无损、坏输入被拒绝。页面里再验一次（eco/page_test.js）",
         caveat="「逐位相同」指同一份页面代码、同一个 JS 引擎；存档约 {m4['save_bytes'] / 1e6:.1f} MB，超出本机存储配额时要用导出文件。云端保存没做",
         script="eco/m4_save_test.js", result_file="results/eco/summary.json", log="§50.6",
         verify=[("m4.pass", {1 if m4['pass'] else 0}, 0)]),
'''
p = ROOT / "scripts/reproduction_data.py"; s = p.read_text()
s = re.sub(r'    dict\(id="eco_surface".*?log="§50\.6",\n         verify=\[[^\n]*\]\),\n', "", s, flags=re.S)
k = s.index('    dict(id="nature_world"'); s = s[:k] + new + s[k:]
params = '''    dict(name="生态箱：身体常数（奖励的来源）", value="不吃不喝时饥饿 600 s、口渴 480 s 到极限；drive 权重 饥 1 / 渴 1 / 体力 0.25 / 健康 3 / 气味 0.12 / 体温 0.6；被咬一口 −0.12 健康", source="**全部手选**；形式（drive reduction）取自 Keramati & Gutkin 2014",
         code_check=("eco/physiology.js", r"hungerTime: (\\d+), thirstTime: (\\d+)", "600/480"),
         note="这些常数就是奖励函数。它们写死在身体里，不对玩家开放；玩家能改的只有 eco/world.js 的 RULES。走路的代谢代价第一版设成静息的 1.5 倍，导致躺平成了理性选择，已按「昆虫步行只比静息高一两成」改正",
         script="eco/physiology.js", log="§50.1"),
    dict(name="生态箱：可塑性层的结构与超参", value="演员 - 评论家、线性、63 个特征；γ 0.995、λ 0.9、评论家学习率 0.03、演员 0.012（可遗传）、吃喝那一路 ×6、运动策略每步衰减 1e-4、权重上限 6", source="**全部手选**；超参在另一批种子（20000 起）上定，不在测试种子上",
         code_check=("eco/plastic.js", r"gamma: ([\\d.]+), lambda: ([\\d.]+), alphaV: ([\\d.]+), ingestGain: (\\d+)", "0.995/0.9/0.03/6"),
         note="特征里有三类：感觉神经元群的发放率（带群体泊松噪声）、大脑输出、身体内部状态。左右对称性是结构先验：往哪边转只读分侧信号。基因的变异幅度（eco/evolve.js 的 MUT）同样手选",
         script="eco/plastic.js", log="§50.4"),
'''
s = re.sub(r'    dict\(name="生态箱：身体常数（奖励的来源）".*?script="eco/plastic\.js", log="§50\.4"\),\n', "", s, flags=re.S)
k2 = s.index("]\n\n# ── 本项目自己的结果"); s = s[:k2] + params + s[k2:]
p.write_text(s); print("台账已加 5 条发现 + 2 组手选参数（生态箱）")
