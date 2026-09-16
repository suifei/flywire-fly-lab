"""汇总第 1–5 项（进食/苦味、梳理、后退、嗅觉、腹神经索）的实测结果 → results/dodge/v3_results.json（供页面渲染表格）"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "results"
ann = pd.read_csv(ROOT / "external/flywire_annotations/Supplemental_file1_neuron_annotations.tsv", sep="\t",
                  low_memory=False, usecols=["root_id", "cell_type", "side", "super_class"]).drop_duplicates("root_id").set_index("root_id")


def dn_lateralization(cond):
    df = pd.read_csv(R / "v2_ref" / cond / "rates.csv", index_col=0)
    col = [c for c in df.columns if c.startswith("baseline")][0]
    dn = ann[ann.super_class == "descending"]
    r = df[col].reindex(dn.index).fillna(0)
    L, Rr = float(r[dn.side == "left"].sum()), float(r[dn.side == "right"].sum())
    s = json.load(open(R / "v2_ref" / cond / "summary.json"))["runs"][0]
    return dict(cond=cond, dn_left=L, dn_right=Rr, li=(L - Rr) / (L + Rr) if L + Rr else 0.0,
                active_neurons=s["active_neurons"], total_spikes=s["total_spikes"])


summary = pd.read_csv(R / "v2_ref" / "summary.csv", index_col=0)
full_brain = {c: {k: (None if pd.isna(v) else float(v)) for k, v in summary.loc[c].items()} for c in summary.index}
jor = pd.read_csv(R / "v2_ref" / "JO_R" / "rates.csv", index_col=0)
col = [c for c in jor.columns if c.startswith("baseline")][0]
full_brain["JO_R"] = {f"aDN1_{s[0].upper()}": float(jor[col].reindex(ann.index[(ann.cell_type == "DNg62") & (ann.side == s)]).fillna(0).mean()) for s in ("left", "right")}

olf = [dn_lateralization(c) for c in ["DM1_L", "DM1_R", "DA2_L", "DA2_R", "DM1_L_50", "DM1_R_50", "DA2_L_50", "DA2_R_50", "SUGAR_L", "JO_L"]]
fba = json.load(open(R / "fba_odor_valence" / "valence_results.json"))

vnc = json.load(open(R / "vnc" / "summary.json"))
mnj = pd.read_csv(R / "vnc" / "mn_joint_summary.csv")
vnc_rows = []
for s in vnc:
    g = mnj[mnj.cond == s["cond"]]
    active = g[(g.flex_hz.fillna(0) > 0) | (g.ext_hz.fillna(0) > 0)]
    vnc_rows.append(dict(cond=s["cond"], active_neurons=s["active_neurons"], legmn_active=s["legmn_active"],
                         mean_flex_hz=float(active.flex_hz.fillna(0).mean()) if len(active) else 0.0,
                         mean_ext_hz=float(active.ext_hz.fillna(0).mean()) if len(active) else 0.0,
                         rhythm_power_median=float(active.rhythm_power.dropna().median()) if active.rhythm_power.notna().any() else None,
                         lr_corr=s["left_right_FTi_flex_corr"]))
legs = json.load(open(R / "vnc" / "legs_summary.json"))
legs_rows = [dict(cond=k, span_mm_median=float(np.median([v["ap_span_mm"] for v in d.values()])),
                  rhythm_median=float(np.median([v["rhythm_power"] for v in d.values()]))) for k, d in legs.items()]

out = dict(
    v3=json.load(open(R / "dodge" / "step_v3.json")),
    backward_sweep=json.load(open(R / "dodge" / "backward_sweep.json")),
    full_brain=full_brain,
    olfaction=dict(lateralization=olf, fba_valence=dict(real=fba["real"]["summary"] if "summary" in fba.get("real", {}) else fba.get("real"),
                                                         tests=fba.get("tests"))),
    vnc=dict(conditions=vnc_rows, legs=legs_rows,
             network=dict(neurons=16407, connections=654258, synapses=6410451, inhibitory_frac=0.52, leg_mn=391)),
)
p = R / "dodge" / "v3_results.json"
p.write_text(json.dumps(out, ensure_ascii=False, default=lambda o: None))
print("写入", p, f"{p.stat().st_size / 1e3:.0f} KB")
print("FBA 气味检验：", [(t["name"], t["passed"]) for t in fba.get("tests", [])])
