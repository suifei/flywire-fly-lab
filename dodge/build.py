"""把子回路数据、步态数据和 brain.js 内联进 fly_dodge.template.html → results/dodge/fly_dodge.html"""
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
for key, text in [("/*__SUBCIRCUIT__*/", (ROOT / "results/dodge/subcircuit_v2.json").read_text()),
                  ("/*__GAIT__*/", (ROOT / "results/dodge/gait.json").read_text()),
                  ("/*__RESULTS__*/", json.dumps({**{k: json.loads((ROOT / f"results/dodge/{k}_{n}.json").read_text()) for k, n in [("step1", "encoding"), ("step3", "flight")]},
                                                 "step2": {**json.loads((ROOT / "results/vision/summary.json").read_text()),
                                                           "figure_png": base64.b64encode((ROOT / "results/vision/lplc2_looming_vs_translation.png").read_bytes()).decode()}})),
                  ("/*__FLIGHT__*/", (ROOT / "results/flight/flight_clips.json").read_text()),
                  ("/*__POSES__*/", (ROOT / "results/dodge/poses.json").read_text()),
                  ("/*__V3__*/", (ROOT / "results/dodge/v3_results.json").read_text()),
                  ("/*__V4__*/", (ROOT / "results/dodge/v4_results.json").read_text()),
                  ("/*__V6__*/", (ROOT / "results/dodge/v6_results.json").read_text()),
                  ("/*__BRAIN_JS__*/", (D / "brain.js").read_text()),
                  ("/*__GAME_CORE_JS__*/", (D / "game_core.js").read_text())]:
    assert key in html, key
    html = html.replace(key, esc(text))
out = ROOT / "results/dodge/fly_dodge.html"
out.write_text(html)
print(out, f"{out.stat().st_size / 1e6:.2f} MB")
