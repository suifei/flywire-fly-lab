"""
探索性（事后提出、结果看过之前写定判据）：沉默“点火”神经元能否阻止嗅觉刺激引发的全脑失控？若能，左右气味是否出现下行侧化？
  集合 A：4 个核心神经元（dodge/v4_olfaction_runaway.py 找到的，在 ≥4 个失控条件的点火集合里都出现）
  集合 B：触角叶全部兴奋性局部神经元（注释 cell_class = ALLN 且预测递质为乙酰胆碱或 5-羟色胺，模型内 120 个）
  刺激：DM1 受体神经元 20 Hz，0.5 s × 4 次（与 DM1_L_20 / DM1_R_20 相同），沉默 = 切断传出突触（与 run_experiment.py 相同）。
  判据：活跃神经元 < 2000 记为“未失控”；侧化成立 = 左、右刺激的下行神经元 LI 符号相反且 |LI| ≥ 0.2。
  另记：下行神经元里发放最高的 5 个（类型 + 侧别），以及投射神经元（ALPN）LI。
用法（flygym 环境）：python dodge/v4_olfaction_silencing.py
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "results" / "v2_ref"
ann = pd.read_csv(ROOT / "external/flywire_annotations/Supplemental_file1_neuron_annotations.tsv", sep="\t", low_memory=False,
                  usecols=["root_id", "cell_type", "side", "super_class", "cell_class"]).drop_duplicates("root_id").set_index("root_id")
RUNS = [("DM1_L_20", "baseline"), ("DM1_R_20", "baseline"), ("DM1_L_20_silA", "silenced"), ("DM1_R_20_silA", "silenced"),
        ("DM1_L_20_silB", "silenced"), ("DM1_R_20_silB", "silenced")]


def metrics(cond, col):
    p = REF / cond / "rates.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p, index_col=0)
    r = df[[c for c in df.columns if c.startswith(col)][0]]
    s = json.load(open(REF / cond / "summary.json"))["runs"][-1]
    out = dict(cond=cond, active=s["active_neurons"], runaway=s["active_neurons"] >= 2000)
    for g, ids in (("DN", ann.index[ann.super_class == "descending"]), ("ALPN", ann.index[ann.cell_class == "ALPN"])):
        sub = ann.loc[ann.index.intersection(ids)]
        L = float(r.reindex(sub.index[sub.side == "left"]).fillna(0).sum()); Rr = float(r.reindex(sub.index[sub.side == "right"]).fillna(0).sum())
        out[f"{g}_L_Hz_sum"], out[f"{g}_R_Hz_sum"] = round(L, 1), round(Rr, 1)
        out[f"{g}_LI"] = round((L - Rr) / (L + Rr), 3) if L + Rr else None
    dn = r.reindex(ann.index[ann.super_class == "descending"]).fillna(0).sort_values(ascending=False).head(5)
    out["top_DN"] = [f"{ann.cell_type.get(i)}({str(ann.side.get(i))[0]}) {v:.0f}" for i, v in dn.items() if v > 0]
    return out


rows = [m for m in (metrics(c, col) for c, col in RUNS) if m]
for m in rows:
    print(f"{m['cond']:15s} 活跃 {m['active']:5d} {'失控' if m['runaway'] else '未失控'}  下行 LI {m['DN_LI']}（L {m['DN_L_Hz_sum']} / R {m['DN_R_Hz_sum']} Hz）"
          f"  投射神经元 LI {m['ALPN_LI']}  最高下行：{m['top_DN']}")
by = {m["cond"]: m for m in rows}
verdict = {}
for tag in ("", "_silA", "_silB"):
    L, Rr = by.get(f"DM1_L_20{tag}"), by.get(f"DM1_R_20{tag}")
    if L and Rr:
        ok = (L["DN_LI"] is not None and Rr["DN_LI"] is not None and L["DN_LI"] * Rr["DN_LI"] < 0 and min(abs(L["DN_LI"]), abs(Rr["DN_LI"])) >= 0.2)
        verdict[tag or "intact"] = dict(no_runaway=not (L["runaway"] or Rr["runaway"]), lateralized=bool(ok))
print("判定：", verdict)
(REF / "olfaction_silencing.json").write_text(json.dumps(dict(rows=rows, verdict=verdict), ensure_ascii=False, indent=1))
