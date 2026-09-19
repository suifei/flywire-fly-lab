#!/usr/bin/env python
"""我们自己用过的每一处「打乱连接组」对照，打乱之后网络还活着吗？

起因（§42）：Fly-Brain-AI 气味效价那 6 条判据里有 3 条是「真实 vs 打乱」，
而打乱臂的读出**完全不放电**——对照组死了，任何非零效应都能通过。
这条教训必须立刻回头套在自己身上，否则就是双标。

查三处：
  1. 全脑打乱（§37.7 / 补充表 1D）——活跃神经元数
  2. 五子棋水库（§38.4 / §41）——打乱特征里的活跃神经元与总脉冲
  3. 游戏子回路打乱（任务「证明连接组真的在起作用」）——起跳次数与闪避率

用法：python3 scripts/check_shuffle_controls.py（只读，几秒）→ results/shuffle_controls.json
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
out = {"note": "判据：打乱之后如果网络基本不放电，那么「真实 vs 打乱」的比较就是空的（见报告 §42）"}

# ① 全脑打乱
sf = json.loads((ROOT / "results/screen/shuffle_full/summary.json").read_text())
intact_act = sf["intact_n_active"]
shuf_act = [a for run in sf["shuffled_n_active"] for a in run]
out["full_brain"] = dict(
    intact_active=intact_act, shuffled_active_median=int(np.median(shuf_act)),
    shuffled_active_range=[int(min(shuf_act)), int(max(shuf_act))],
    ratio=round(float(np.median(shuf_act)) / float(np.median(intact_act)), 3),
    alive=bool(np.median(shuf_act) > 10))

# ② 五子棋水库：直接数特征矩阵里非零的神经元
def feat_stats(arm, suf="_v3"):
    meta = json.loads((ROOT / f"results/gomoku/feat_{arm}{suf}.json").read_text())
    X = np.fromfile(ROOT / f"results/gomoku/feat_{arm}{suf}.bin", np.float32).reshape(meta["rows"], meta["cols"])
    return dict(cols=meta["cols"], ever_active=int((X.max(0) > 0).sum()),
                mean_active_per_position=round(float((X > 0).sum(1).mean()), 1),
                mean_total_spikes=round(float(X.sum(1).mean()), 1))
out["gomoku"] = {arm: feat_stats(arm) for arm in ("intact", "shuffled")}
g = out["gomoku"]
g["alive"] = bool(g["shuffled"]["mean_active_per_position"] > 10)
g["ratio_active"] = round(g["shuffled"]["mean_active_per_position"] / max(g["intact"]["mean_active_per_position"], 1e-9), 3)

# ③ 游戏子回路打乱（任务关卡里那一关）
ms = json.loads((ROOT / "results/dodge/missions_v3.json").read_text())
sc = [m for m in ms["missions"] if m["id"] == "shuffle_control"][0]
out["game_subcircuit"] = dict(
    intact_jump=sc["arms"]["none"]["mean"]["jump"], shuffled_jump=sc["arms"]["ref"]["mean"]["jump"],
    intact_dodge=sc["arms"]["none"]["mean"]["dodgeRate"], shuffled_dodge=sc["arms"]["ref"]["mean"]["dodgeRate"],
    alive=bool(sc["arms"]["ref"]["mean"]["jump"] > 0))

print(f"{'对照':16s}{'完整':>14s}{'打乱':>14s}{'还活着?':>9s}")
f = out["full_brain"]
print(f"{'全脑（活跃数）':16s}{np.median(f['intact_active']):14.0f}{f['shuffled_active_median']:14.0f}{'是' if f['alive'] else '否':>9s}")
print(f"{'五子棋（活跃/局面）':16s}{g['intact']['mean_active_per_position']:14.1f}{g['shuffled']['mean_active_per_position']:14.1f}{'是' if g['alive'] else '否':>9s}")
gs = out["game_subcircuit"]
print(f"{'游戏子回路（起跳）':16s}{gs['intact_jump']:14.1f}{gs['shuffled_jump']:14.1f}{'是' if gs['alive'] else '否':>9s}")
out["all_alive"] = bool(f["alive"] and g["alive"] and gs["alive"])
print(f"\n三处打乱对照{'全部' if out['all_alive'] else '并非全部'}仍有明显活动——"
      f"{'所以这些「真实 vs 打乱」的比较不是空的' if out['all_alive'] else '有对照是空的，必须重新审视相应结论'}")
p = ROOT / "results/shuffle_controls.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=1))
print("→", p)
