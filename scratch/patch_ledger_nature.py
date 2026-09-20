#!/usr/bin/env python3
"""台账：大自然（§49）。可重复执行；verify 的数字在打补丁时从结果 JSON 读出。"""
import json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
T = json.loads((ROOT / "results/dodge/nature_test.json").read_text()); t = T["tests"]; NL = json.loads((ROOT / "results/learn/nature_life.json").read_text()); n = NL["worlds"]["nature"]["mean"]; f = NL["worlds"]["flat"]["mean"]
new = f'''    dict(id="nature_world", what="把篮球场换成一个有重力、有天气、没有边界的 3D 大自然，物理对不对、果蝇在里面过得怎么样",
         status="reproduced",
         result="九条事先写好的物理判据全过：30 mm 自由落体 {t['N1_free_fall']['t_sim']} s（解析值 {t['N1_free_fall']['t_analytic']} s）；弹起高度 {' → '.join(str(p) for p in t['N2_no_energy_gain']['peaks_mm'])} mm，不生能量；"
                "坡度 {t['N4_rolls_downhill_only_when_steep']['steep_slope']} 的陡坡上 1 秒滚落 {t['N4_rolls_downhill_only_when_steep']['dropped_mm']} mm、缓坡上停得住；石头不可穿透；风把气味吹向下风（下风 {t['N8_wind_plume']['downwind']} 对上风 {t['N8_wind_plume']['upwind']}）；闭环里走 60 秒从不穿进实心物件。"
                "在里面过 3 分钟（3 个种子均值）：走 {n['path_mm']:.0f} mm、被石头之类挡住 {n['blocked_s']:.1f} s、起飞 {n['jumps']:.1f} 次、掉下来 {n['berries']:.1f} 颗浆果、碰到糖 {n['sugar_contacts']:.1f} 次（平地开放世界 {f['sugar_contacts']:.1f} 次）",
         caveat="世界只通过已有的感觉通道进到脑子里，没有新增行为规则；**默认的视觉前端仍是手写的逼近检测，石头、草、地形不在它的视觉里**（真实像素那条通路可选，默认关）。"
                "果蝇自己的身体仍是运动学，不会摔倒；受重力支配的是浆果。水洼是水位不是流体。地形、物件密度、恢复系数、滚动阻力、坡度系数、天气节奏全部手选（PARAMETERS）。"
                "威胁从飞来的球换成了爬过来的甲虫：毫米尺度上 60 mm/s 的抛体 0.1 秒就落地，「慢慢滚过来的球」不物理",
         script="dodge/nature_test.js", result_file="results/dodge/nature_test.json", log="§49",
         verify=[("all_pass", True, 0), ("tests.N1_free_fall.t_sim", {t['N1_free_fall']['t_sim']}, 0.0001), ("tests.N4_rolls_downhill_only_when_steep.dropped_mm", {t['N4_rolls_downhill_only_when_steep']['dropped_mm']}, 0.01), ("tests.N9_closed_loop_walk.max_penetration_mm", {t['N9_closed_loop_walk']['max_penetration_mm']}, 1e-6)]),
'''
p = ROOT / "scripts/reproduction_data.py"; s = p.read_text()
s = re.sub(r'    dict\(id="nature_world".*?log="§49",\n         verify=\[[^\n]*\]\),\n', "", s, flags=re.S)
k = s.index('    dict(id="olfactory_runaway_source"'); s = s[:k] + new + s[k:]
params = '''    dict(name="大自然：物理常数与世界的手选量", value="恢复系数 0.35、滚动阻力 0.15 g、低于 4 mm/s 且静摩擦兜得住就停、坡度对步速的系数 1.2（夹在 0.45–1.25）；地形三层值噪声（幅度 7 / 2.2 / 0.5 mm，波长 160 / 55 / 18 mm）；石板升温时间常数 20 s；约每 3–6 分钟一场雨", source="重力 9,810 mm/s²、自由落体、纯滚动的 5/7 是物理；**其余手选**",
         code_check=("dodge/nature.js", r"restitution: ([\\d.]+), crr: ([\\d.]+), restSpeed: (\\d+), slopeK: ([\\d.]+)", "0.35/0.15/4/1.2"),
         note="没有果蝇尺度下浆果在土面上的恢复系数 / 滚动阻力数据，取的是「软而粗糙的地面」的量级。物件种类与密度、天气节奏、雨点砸中的频率、甲虫出现的节奏都是为了让世界有东西可感受，不来自任何测量",
         script="dodge/nature.js", log="§49.4"),
'''
s = re.sub(r'    dict\(name="大自然：物理常数与世界的手选量".*?script="dodge/nature\.js", log="§49\.4"\),\n', "", s, flags=re.S)
k2 = s.index("]\n\n# ── 本项目自己的结果"); s = s[:k2] + params + s[k2:]
p.write_text(s); print("台账已加 1 条发现 + 1 组手选参数（大自然）")
