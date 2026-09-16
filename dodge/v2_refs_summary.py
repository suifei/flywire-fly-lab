"""汇总 results/v2_ref/* 全脑参考实验：各输出神经元组的平均发放率（Hz），用于判断每条通路在连接组里是否成立。"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ann = pd.read_csv(ROOT / "external/flywire_annotations/Supplemental_file1_neuron_annotations.tsv", sep="\t",
                  low_memory=False, usecols=["root_id", "cell_type", "side"]).drop_duplicates("root_id")
GROUPS = [("CB0701", "MN9"), ("DNg62", "aDN1"), ("MDN", "MDN"), ("DNa01", "DNa01"), ("DNa02", "DNa02"),
          ("DNp01", "GF"), ("DNg97", "oDN1"), ("DNg100", "BDN2")]
COND = ["SUGAR_L", "SUGAR_R", "BITTER", "SUGAR_BITTER", "JO_L", "DM1_L", "DM1_R", "DA2_L", "DA2_R", "LC16_LR", "FRONT_LOOM"]
rows = []
for c in COND:
    p = ROOT / "results/v2_ref" / c / "rates.csv"
    df = pd.read_csv(p, index_col=0)
    col = [x for x in df.columns if x.startswith("baseline")][0]
    s = json.load(open(ROOT / "results/v2_ref" / c / "summary.json"))
    row = {"cond": c, "n_stim": len(s["exc_ids"]), "active": s["runs"][0]["active_neurons"], "spikes": s["runs"][0]["total_spikes"]}
    for t, name in GROUPS:
        for side in ("left", "right"):
            ids = ann.root_id[(ann.cell_type == t) & (ann.side == side)]
            row[f"{name}_{side[0].upper()}"] = round(float(df[col].reindex(ids).fillna(0).mean()), 1) if len(ids) else float("nan")
    rows.append(row)
out = pd.DataFrame(rows).set_index("cond")
pd.set_option("display.width", 250)
print(out.to_string())
out.to_csv(ROOT / "results/v2_ref/summary.csv")
