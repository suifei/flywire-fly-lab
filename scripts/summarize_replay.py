#!/usr/bin/env python3
"""results/fba_replay/replay.json（5 MB，含网格与逐帧位姿，不进仓库）→ replay_summary.json（元信息 + 每个试次的摘要，进仓库）。
台账引用的是这个小文件：CI 里没有 5 MB 的原始回放，引用它会让台账校验一直是红的。只读。"""
import json
from pathlib import Path
R = Path(__file__).resolve().parent.parent / "results/fba_replay"
d = json.loads((R / "replay.json").read_text())
def brief(t):
    return {k: (v if not isinstance(v, (list, dict)) else (len(v) if isinstance(v, list) else {kk: vv for kk, vv in v.items() if not isinstance(vv, (list, dict))})) for k, v in t.items()}
out = {"source": "results/fba_replay/replay.json（由 fba_export_replay.py 生成，未入库）", "meta": d["meta"], "n_meshes": len(d["meshes"]), "trials": [brief(t) for t in d["trials"]]}
(R / "replay_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1)); print("→ results/fba_replay/replay_summary.json", (R / "replay_summary.json").stat().st_size, "B")
