#!/usr/bin/env python3
"""台账：五感 + 自己生活（§47）的几条发现与手选参数。可重复执行；verify 的数字在打补丁时从结果 JSON 读出。"""
import json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; R = ROOT / "results/dodge"
J = lambda f: json.loads((R / f).read_text())
SP, MOD, LT, SD, WL = J("sound_priming.json"), J("sense_modulation.json"), J("life_test.json"), J("sensor_drive_v4.json"), J("wall_limits.json")
g = SP["groups"]; no, yes, deaf = g["无声"], g["有声"], g["有声但聋（AUDIO 断突触）"]
row = lambda base, mod: next(r for r in MOD["rows"] if r["base"].startswith(base) and mod in r["mod"])
isn = row("吃糖", "ISN"); idx_isn = MOD["rows"].index(isn)
C = {k: v["mean"] for k, v in LT["conds"].items()}; W = {k: v["mean"] for k, v in WL["arenas"].items()}
new = f'''    dict(id="hearing_priming", what="给它听觉之后，声音在行为上有没有用（听觉神经元 1 跳到巨纤维）",
         status="reproduced",
         result="**有，但不是「听到就跑」**。声音单独驱动不了起飞（听觉神经元 200 Hz 时巨纤维读出约 80 Hz，起飞阈值 90）；"
                "它让**逼近反应提前**：同一颗慢球，起飞提前量中位 **{no['lead_ms_median']} → {yes['lead_ms_median']} ms**，躲开 **{no['dodged']} → {yes['dodged']} / {SP['n']}**；"
                "切断听觉神经元的传出突触之后回到 {deaf['lead_ms_median']} ms、{deaf['dodged']} / {SP['n']}",
         caveat="探索性：这个对照是看过生活模式的初跑（声音一次也没把它惊飞）之后才想到的。事先写好的判据 H1「声音后 1 s 内起飞 ≥ 20%」**不成立**（{C['intact']['startle_rate'] * 100:.0f}%，失聪 {C['deaf']['startle_rate'] * 100:.0f}%）。"
                "没有为了让它被吓飞去调起飞阈值或声音强度。声强随距离的衰减与左右耳差是手写的；效应本身（声音 + 逼近在巨纤维上相加）来自连接组",
         script="dodge/sound_priming.js", result_file="results/dodge/sound_priming.json", log="§47.4",
         verify=[("groups.无声.lead_ms_median", {no['lead_ms_median']}, 0), ("groups.有声.lead_ms_median", {yes['lead_ms_median']}, 0), ("groups.有声.dodged", {yes['dodged']}, 0), ("groups.无声.dodged", {no['dodged']}, 0)]),
    dict(id="olfaction_no_pathway", what="给它嗅觉之后（醋 DM1、土臭素 DA2 两个嗅小球），闻得到的东西会让它走过去或躲开吗",
         status="negative",
         result="**不会**。两路单独驱动各能激活上百个神经元，但没有落到六个运动读出的任何一个上；自己过日子的 10 分钟里，碰到糖的次数完整 {C['intact']['sugar_contacts']}、失嗅 {C['anosmic']['sugar_contacts']}，没有差别",
         caveat="事先写好的判据 H2 不成立。与 §10 全脑上「嗅觉没有左右偏侧化」一致。只取了两个嗅小球（全取 1,850 个 ORN 会把触角叶和蘑菇体都卷进子回路）。"
                "唯一测到的作用是调制：醋味会压低碰触引起的转向（DNa 6.0 → 0.7 Hz）。「吸引 / 厌恶」是文献给这两个小球的标签，不是写进模型的规则",
         script="dodge/life_test.js", result_file="results/dodge/life_test.json", log="§47.2 + §47.5",
         verify=[("H2.passed", {LT['H2']['passed']}, 0), ("conds.intact.mean.sugar_contacts", {C['intact']['sugar_contacts']}, 0.001), ("conds.anosmic.mean.sugar_contacts", {C['anosmic']['sugar_contacts']}, 0.001)]),
    dict(id="isn_sign", what="用真实的内感受神经元 ISN（感知饥渴）代替手写的口渴规则，行不行",
         status="negative",
         result="**不行：模型里 ISN 的作用方向与文献相反**。文献（González-Segarra 2023）：ISN 活动增强 → 吃糖增多、喝水减少。"
                "模型里驱动 ISN（200 Hz）把吃糖的 MN9 从 **{isn['base_hz']['mean']} Hz 压到 {isn['hz']['mean']} Hz**；它是一个对伸喙的通用抑制",
         caveat="ISN 用的是神经肽 dILP3，LIF 模型只有预测的快递质符号（与 Usnea 那条同类）。**没有为了得到「饿了想吃」去翻转它的符号。**"
                "页面上留了一个默认关闭的「ISN 通路」开关。身体状态改由感受器灵敏度体现（见下一条）",
         script="dodge/sense_modulation.js", result_file="results/dodge/sense_modulation.json", log="§47.3",
         verify=[("rows.{idx_isn}.base_hz.mean", {isn['base_hz']['mean']}, 0.01), ("rows.{idx_isn}.hz.mean", {isn['hz']['mean']}, 0.01), ("rows.{idx_isn}.modulates", True, 0)]),
    dict(id="body_state", what="身体状态（能量 / 水分）只调味觉感受器的灵敏度、不写任何「饿了就吃」的规则，够不够",
         status="reproduced",
         result="**够**。碰到糖后开吃的比例：饿着 **{LT['H3']['starved'] * 100:.0f}%**、饱着 **{LT['H3']['sated'] * 100:.0f}%**（判据 H3：≥ 1.5 倍，成立）。"
                "还出现了没人写过的饱腹感：完整条件下几乎每次碰到糖都开吃（{C['intact']['sugar_feeds']} / {C['intact']['sugar_contacts']}），却一块也没吃完——吃一两秒能量上来，糖感受器变钝，MN9 掉到阈值以下，它就走开了",
         caveat="「缺什么对什么更敏感」有文献依据（Inagaki et al. 2012：饥饿经多巴胺提高糖感受器的敏感度），但增益范围（0.1–1.6）与能量 / 水分的消耗速率全部手选。"
                "「MN9 超过多少算开吃」在生活模式里统一为 10 Hz（手选）：原来的 30 Hz 水永远过不了，水感受器开到 320 Hz，MN9 也只有 22 Hz",
         script="dodge/life_test.js", result_file="results/dodge/life_test.json", log="§47.5–47.6",
         verify=[("H3.passed", {LT['H3']['passed']}, 0), ("H3.starved", {LT['H3']['starved']}, 0.001), ("H3.sated", {LT['H3']['sated']}, 0.001)]),
    dict(id="touch_cannot_avoid_walls", what="只靠触感（加不加围栏视觉），这颗脑子避得开墙吗",
         status="negative",
         result="**避不开**。3 分钟（走满是 3,240 mm）：矩形场地 + 触感只走了 {W['rect_touch']['path_mm']:.0f} mm、{W['rect_touch']['wall_frac'] * 100:.0f}% 的时间贴墙（卡死在墙角：两根触角同时压墙，转向差为 0）；"
                "圆形场地 {W['round_touch']['path_mm']:.0f} mm、贴墙 {W['round_touch']['wall_frac'] * 100:.0f}%；打开围栏视觉不贴墙了，但没有任何来球也起飞 {W['rect_vision']['jumps']:.0f} 次",
         caveat="脑子里没有腹神经索的腿部反射。**没有用「卡住就掉头」的规则去掩盖**：生活模式改成没有墙的开放世界（同样 3 分钟走 {W['open']['path_mm']:.0f} mm）。§38 里「触感让它沿墙走」的结论不变，这里量的是它走不走得开",
         script="dodge/wall_limits.js", result_file="results/dodge/wall_limits.json", log="§47.6",
         verify=[("arenas.rect_touch.mean.path_mm", {W['rect_touch']['path_mm']}, 0.5), ("arenas.round_touch.mean.wall_frac", {W['round_touch']['wall_frac']}, 0.001), ("arenas.open.mean.path_mm", {W['open']['path_mm']}, 0.5)]),
'''
p = ROOT / "scripts/reproduction_data.py"; s = p.read_text()
s = re.sub(r'    dict\(id="hearing_priming".*?log="§47\.6",\n         verify=\[[^\n]*\]\),\n', "", s, flags=re.S)
k = s.index('    dict(id="touch_pathway"'); s = s[:k] + new + s[k:]
params = '''    dict(name="生活模式：声音与气味的物理换算", value="听觉神经元上限 200 Hz、声强半衰距离 60 mm、左右耳差 ±25%；嗅觉上限 200 Hz、气味羽流为高斯", source="**手选**",
         code_check=("dodge/game_core.js", r"audioRate: (\\d+), soundRef: (\\d+), earBias: ([\\d.]+)", "200/60/0.25"),
         note="没有该模型下的声强 / 气味浓度定标数据。上限 200 Hz 与味觉、温湿度那几路取同一个值。没有为了让它被声音吓飞去调这些数或起飞阈值",
         script="dodge/game_core.js", log="§47.4"),
    dict(name="生活模式：身体状态", value="味觉感受器灵敏度增益 0.1–1.6（缺什么对什么更敏感）；MN9 > 10 Hz 算开吃；能量 / 水分的消耗与补充速率", source="方向有文献依据（Inagaki 2012），**幅度与速率手选**",
         code_check=("dodge/game_core.js", r"gainMin: ([\\d.]+), gainMax: ([\\d.]+)", "0.1/1.6"),
         note="身体状态不直接决定任何行为，只改感受器灵敏度与走路速度。开吃阈值从球场模式的 30 Hz 降到 10 Hz：水感受器开到 320 Hz，MN9 也只有 22 Hz（实测），30 Hz 水永远过不了",
         script="dodge/game_core.js", log="§47.6"),
'''
s = re.sub(r'    dict\(name="生活模式：声音与气味的物理换算".*?script="dodge/game_core\.js", log="§47\.6"\),\n', "", s, flags=re.S)
k2 = s.index("]\n\n# ── 本项目自己的结果"); s = s[:k2] + params + s[k2:]
p.write_text(s); print("台账已加 5 条发现 + 2 个手选参数（五感 + 生活）")
