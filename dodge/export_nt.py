#!/usr/bin/env python3
"""导出子回路里每个神经元的递质类型，供游戏做「谷氨酸改兴奋性」这一档扰动。

对应论文补充表 **11F**（Glut excitatory）：默认模型把谷氨酸当抑制性，
表 11F 测的是把它改成兴奋性之后预测还成不成立。游戏里做成一个开关。

只读：不改 `results/dodge/subcircuit_v2.json`，单独写一个与 `fids` 同序的数组，
这样子回路文件的哈希不变，已发布的结果不受影响。

编码：0=乙酰胆碱 1=谷氨酸 2=GABA 3=多巴胺 4=血清素 5=章胺 6=未知
用法：python3 dodge/export_nt.py   → results/dodge/subcircuit_nt.json
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CODE = {"acetylcholine": 0, "glutamate": 1, "gaba": 2, "dopamine": 3, "serotonin": 4, "octopamine": 5}

sub = json.loads((ROOT / "results/dodge/subcircuit_v2.json").read_text())
fids = [str(f) for f in sub["fids"]]
ann = pd.read_csv(ROOT / "external/flywire_annotations/Supplemental_file1_neuron_annotations.tsv",
                  sep="\t", low_memory=False, usecols=["root_id", "top_nt"]).drop_duplicates("root_id")
m = {str(r): (str(t).lower() if pd.notna(t) else None) for r, t in zip(ann.root_id, ann.top_nt)}
nt = [CODE.get(m.get(f) or "", 6) for f in fids]

counts = {}
inv = {v: k for k, v in CODE.items()}
for c in nt:
    counts[inv.get(c, "unknown")] = counts.get(inv.get(c, "unknown"), 0) + 1
print(f"子回路 {len(fids)} 个神经元的递质分布：")
for k, v in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"  {k:15s} {v:5d}  ({v / len(fids) * 100:.1f}%)")

out = {"说明": "与 subcircuit_v2.json 的 fids 同序；0=ACh 1=Glut 2=GABA 3=DA 4=5HT 5=OA 6=未知",
       "来源": "FlyWire 注释表 top_nt（预测值）", "n": len(fids), "counts": counts, "nt": nt}
(ROOT / "results/dodge/subcircuit_nt.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
print(f"\n→ results/dodge/subcircuit_nt.json（{(ROOT / 'results/dodge/subcircuit_nt.json').stat().st_size / 1024:.1f} KB）")
