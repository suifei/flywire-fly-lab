#!/usr/bin/env python3
"""汇总「五感 + 自己生活」的全部实测 → results/dodge/life_summary.json（页面的生活模式卡片与台账从这里取数）。只读。"""
import json
from pathlib import Path
R = Path(__file__).resolve().parent.parent / "results/dodge"
rd = lambda f: json.loads((R / f).read_text()) if (R / f).exists() else None
out = {"generated_by": "dodge/collect_life.py"}
sub = rd("subcircuit_v4.json")
if sub: out["subcircuit"] = {"n": sub["meta"]["n"], "n_edges": sub["meta"]["n_edges"], "inputs": {k: [len(sub["groups"][k + "_left"]), len(sub["groups"][k + "_right"])] for k in sub["meta"]["inputs"]}}
sr = rd("sensor_reach_v4.json")
if sr: out["reach"] = {k: {"n": v["n"], "hops": v["hops"], "top_descending": [t["cell_type"] for t in v["top_descending"][:5]]} for k, v in sr["groups"].items()}
sd = rd("sensor_drive_v4.json")
if sd: out["drive_summary"] = sd.get("summary")
for k, f in (("modulation", "sense_modulation.json"), ("sound_priming", "sound_priming.json")):
    d = rd(f)
    if d: out[k] = d
lt = rd("life_test.json")
if lt: out["life_test"] = {"seconds": lt["seconds"], "seeds": lt["seeds"], "H1": lt["H1"], "H2": lt["H2"], "H3": lt["H3"], "conds": {k: v["mean"] for k, v in lt["conds"].items()}}
(R / "life_summary.json").write_text(json.dumps(out, ensure_ascii=False))
print("→ results/dodge/life_summary.json", list(out.keys()))
