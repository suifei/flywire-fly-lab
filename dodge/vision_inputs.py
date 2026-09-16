"""LPLC2 / LC4 / 巨纤维(DNp01) 的突触前细胞类型构成，以及其中有多少来自 flyvis 覆盖的 65 种柱状细胞。"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
FLYVIS = set("R1 R2 R3 R4 R5 R6 R7 R8 L1 L2 L3 L4 L5 Lawf1 Lawf2 Am C2 C3 CT1(Lo1) CT1(M10) Mi1 Mi2 Mi3 Mi4 Mi9 Mi10 Mi11 "
             "Mi12 Mi13 Mi14 Mi15 T1 T2 T2a T3 T4a T4b T4c T4d T5a T5b T5c T5d Tm1 Tm2 Tm3 Tm4 Tm5Y Tm5a Tm5b Tm5c Tm9 "
             "Tm16 Tm20 Tm28 Tm30 TmY3 TmY4 TmY5a TmY9 TmY10 TmY13 TmY14 TmY15 TmY18".split())  # FlyGym advanced_vision 教程列出的 flyvis 节点类型
ann = pd.read_csv(ROOT / "external/flywire_annotations/Supplemental_file1_neuron_annotations.tsv", sep="\t",
                  low_memory=False, usecols=["root_id", "cell_type", "super_class"]).drop_duplicates("root_id").set_index("root_id")
con = pd.read_parquet(ROOT / "external/fly-brain/data/2025_Connectivity_783.parquet",
                      columns=["Presynaptic_ID", "Postsynaptic_ID", "Connectivity", "Excitatory"])
ctype = ann.cell_type
for target in ["LPLC2", "LC4", "DNp01"]:
    ids = set(ann.index[ctype == target])
    e = con[con.Postsynaptic_ID.isin(ids)].copy()
    e["pre_type"] = ctype.reindex(e.Presynaptic_ID).fillna("(未注释)").to_numpy()
    by = e.groupby("pre_type").Connectivity.sum().sort_values(ascending=False)
    tot = by.sum()
    fv = by[by.index.isin(FLYVIS)].sum()
    t45 = by[by.index.str.match(r"^T[45][abcd]$")].sum()
    print(f"\n{target}（{len(ids)} 个）总输入突触 {tot:,}；来自 flyvis 覆盖类型 {fv / tot:.0%}（其中 T4/T5 {t45 / tot:.0%}）")
    print("  主要输入类型：" + "，".join(f"{k} {v / tot:.0%}" for k, v in by.head(10).items()))
