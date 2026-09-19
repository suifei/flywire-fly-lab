"""把子回路数据、步态数据和 brain.js 内联进 fly_dodge.template.html → results/dodge/fly_dodge.html

**2026-09-19 起页面用子回路 v3**（5,563 神经元，比 v2 多了触感 / 温度 / 湿度三路输入）。
所有跟着子回路走的结果文件都取 _v3 那一份：任务关卡、突变体、胞体坐标、递质标签。
v2 的对应文件全部留在原处备查，两版数值很接近（见 docs/log/report.md §41）。
"""
import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "dodge"
esc = lambda s: s.replace("</", "<\\/")
html = (D / "fly_dodge.template.html").read_text()


def lint(src):
    """构建前拦住两类**语法合法、但行为错误**的写法——`node --check` 抓不到它们。

    1. 相邻模板字符串 `a``b`：JS 把它解析成**标签模板调用**，运行时报
       "... is not a function"。2026-09-16 因为漏写 `+` 真的线上炸过 3 处。
    2. 模板字符串里的 markdown 粗体 `**…**`：这些串最终进 textContent，
       星号会原样显示给用户。同样犯过两次。
    """
    bad = []
    for i, line in enumerate(src.split("\n"), 1):
        if "``" in line:
            bad.append((i, "相邻模板字符串（缺 `+`，会被当成标签模板调用）", line.strip()[:90]))
        if "`" in line and "**" in line and "<b>" not in line:
            bad.append((i, "模板字符串里有 markdown ** **（textContent 会原样显示星号）", line.strip()[:90]))
    if bad:
        print("构建中止：模板里有会在运行时出错的写法\n")
        for i, why, txt in bad:
            print(f"  第 {i} 行  {why}\n      {txt}\n")
        raise SystemExit(1)


lint(html)
for key, text in [("/*__SUBCIRCUIT__*/", (ROOT / "results/dodge/subcircuit_v3.json").read_text()),
                  ("/*__SUB_NT__*/", (ROOT / "results/dodge/subcircuit_nt_v3.json").read_text()),
                  ("/*__PERTURB__*/", (ROOT / "results/dodge/perturb.json").read_text()),
                  ("/*__REPRO__*/", (ROOT / "results/reproduction.json").read_text()),
                  ("/*__GAIT__*/", (ROOT / "results/dodge/gait.json").read_text()),
                  ("/*__RESULTS__*/", json.dumps({**{k: json.loads((ROOT / f"results/dodge/{k}_{n}.json").read_text()) for k, n in [("step1", "encoding"), ("step3", "flight")]},
                                                 "step2": {**json.loads((ROOT / "results/vision/summary.json").read_text()),
                                                           "figure_png": base64.b64encode((ROOT / "results/vision/lplc2_looming_vs_translation.png").read_bytes()).decode()}})),
                  ("/*__FLIGHT__*/", (ROOT / "results/flight/flight_clips.json").read_text()),
                  ("/*__POSES__*/", (ROOT / "results/dodge/poses.json").read_text()),
                  ("/*__V3__*/", (ROOT / "results/dodge/v3_results.json").read_text()),
                  ("/*__V4__*/", (ROOT / "results/dodge/v4_results.json").read_text()),
                  ("/*__V6__*/", (ROOT / "results/dodge/v6_results.json").read_text()),
                  # 「让果蝇看你的图」：真实复眼几何 + flyvis 预训练视觉网络 + 六边形卷积解码器
                  ("/*__FLYVIS_NET__*/", (ROOT / "results/vision/flyvis_net.json").read_text()),
                  ("/*__RETINA_META__*/", (ROOT / "results/vision/retina.json").read_text()),
                  ("/*__DECODERS__*/", (ROOT / "results/vision/decoders.json").read_text()),
                  ("/*__RETINA_PNG_B64__*/",
                   base64.b64encode((ROOT / "results/vision/retina_map.png").read_bytes()).decode()),
                  ("/*__FLYVIS_JS__*/", (ROOT / "vision/flyvis.js").read_text()),
                  ("/*__RETINA_JS__*/", (ROOT / "vision/retina.js").read_text()),
                  ("/*__DECODER_JS__*/", (ROOT / "vision/decoder.js").read_text()),
                  ("/*__COURT_JS__*/", (D / "court.js").read_text()),
                  ("/*__T4T5__*/", (ROOT / "results/vision/t4t5_directions.json").read_text()),
                  ("/*__OPSINS_JS__*/", (ROOT / "vision/opsins.js").read_text()),
                  ("/*__LPLC2_JS__*/", (ROOT / "vision/lplc2.js").read_text()),
                  ("/*__FRONTEND_JS__*/", (ROOT / "vision/front_end.js").read_text()),
                  ("/*__EYECAM_JS__*/", (D / "eyecam.js").read_text()),
                  ("/*__EYE_JS__*/", (D / "eye.js").read_text()),
                  ("/*__BRAIN_JS__*/", (D / "brain.js").read_text()),
                  ("/*__GAME_CORE_JS__*/", (D / "game_core.js").read_text()),
                  ("/*__MISSIONS_JS__*/", (D / "missions.js").read_text()),
                  ("/*__MISSIONS__*/", (ROOT / "results/dodge/missions_v3.json").read_text()),
                  ("/*__MUTANTS__*/", (ROOT / "results/dodge/mutants_v3.json").read_text()),
                  ("/*__SOMA__*/", (ROOT / "results/dodge/soma_v3.json").read_text()),
                  ("/*__GOMOKU_READOUT__*/", (ROOT / "results/gomoku/readout.json").read_text()),
                  ("/*__GOMOKU_TRAIN__*/", (ROOT / "results/gomoku/train.json").read_text()),
                  ("/*__GOMOKU_PLAY__*/", (ROOT / "results/gomoku/play.json").read_text()),
                  ("/*__TOUCH__*/", (ROOT / "results/dodge/touch.json").read_text()),
                  ("/*__SENSOR_DRIVE__*/", (ROOT / "results/dodge/sensor_drive.json").read_text()),
                  ("/*__GOMOKU_RULES_JS__*/", (ROOT / "gomoku/rules.js").read_text()),
                  ("/*__GOMOKU_TEACHER_JS__*/", (ROOT / "gomoku/teacher.js").read_text()),
                  ("/*__GOMOKU_FEATURES_JS__*/", (ROOT / "gomoku/features.js").read_text()),
                  ("/*__GOMOKU_FLY_JS__*/", (ROOT / "gomoku/fly.js").read_text()),
                  ("/*__GOMOKU_BOARD3D_JS__*/", (ROOT / "gomoku/board3d.js").read_text()),
                  ("/*__COMPANIONS_JS__*/", (D / "companions.js").read_text())]:
    assert key in html, key
    html = html.replace(key, esc(text))
out = ROOT / "results/dodge/fly_dodge.html"
out.write_text(html)
print(out, f"{out.stat().st_size / 1e6:.2f} MB")
