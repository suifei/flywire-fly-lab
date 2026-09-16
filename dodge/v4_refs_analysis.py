"""
第 4 轮全脑参考实验分析（results/v2_ref/*，brian2 全脑 LIF）。指标在看结果之前写定：

A. 多巴胺（“吃到爱吃的会不会分泌多巴胺”）
   * 组：注释 cell_type 前缀 PAM / PPL1 / PPL2 / PPM1 / PAL，分左右。
   * 每个条件报告：组内放电神经元数（≥1 个脉冲）、组平均发放率（沉默的计 0）、最大发放率。
   * 特异性判据（事先定）：只有在“非失控”条件（活跃神经元 < 2000）下 PAM 有放电，才算“糖味激活奖赏多巴胺”；
     失控条件（活跃 ≥ 2000）里的放电记为非特异。
   * 结构：糖味 GRN（LB3）→ PAM、苦味 GRN（LB1*）→ PPL1 的最短突触跳数（边权 ≥1 与 ≥5 两档）。
   * 时间：SUGAR_LR_100 里全脑失控起点（见 C）与第一个多巴胺神经元脉冲的先后。
B. LC16 剂量 → MDN（后退）
   * 条件 LC16_LR_25/50/100/150（150 = 旧的 LC16_LR），单侧 LC16_L_100 / LC16_R_100。
   * 读出：MDN 左右、GF、DNa01/DNa02 左右、全部下行神经元左右总和的侧化指数 LI=(L−R)/(L+R)，
     以及发放最高的 8 个下行神经元（类型 + 侧别）。
C. 低强度嗅觉
   * 条件 DM1_L_10 / DM1_L_20 / DM1_R_20 / DA2_L_100（及旧的 50/200 Hz）。
   * 失控起点：试次平均后，5 ms 分箱内“有脉冲的不同神经元数”首次 ≥ 500 的时刻。
   * 起点之前的窗口：投射神经元 ALPN、侧角 LHLN/LHCENT、MBON、下行神经元 的左右脉冲数与 LI。
     判据（事先定）：DM1_L 与 DM1_R 的下行 LI 符号相反且 |LI| ≥ 0.2 才算“有侧化信号”。
   * 失控组成：活跃神经元的 super_class 分布；DM1_L_10 与 DA2_L_100 / SUGAR_LR_100 活跃集合的 Jaccard 重叠。
输出 results/v2_ref/v4_analysis.json
用法（flygym 环境，需要 pyarrow）：python dodge/v4_refs_analysis.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "results" / "v2_ref"
RUNAWAY = 2000
ann = pd.read_csv(ROOT / "external/flywire_annotations/Supplemental_file1_neuron_annotations.tsv", sep="\t", low_memory=False,
                  usecols=["root_id", "cell_type", "side", "super_class", "cell_class"]).drop_duplicates("root_id").set_index("root_id")
ct = ann.cell_type.fillna("")
DAN_GROUPS = {g: ann.index[ct.str.startswith(g)] for g in ["PAM", "PPL1", "PPL2", "PPM1", "PAL"]}
pd.set_option("display.width", 250)


def load(cond):
    df = pd.read_csv(REF / cond / "rates.csv", index_col=0)
    cols = [c for c in df.columns if c.startswith("baseline")]
    if not cols:                      # 只有 silenced 列的条件（嗅觉沉默实验），这里不看
        return None, None
    col = cols[0]
    s = json.load(open(REF / cond / "summary.json"))
    return df[col], s


def side_sum(r, ids):
    sub = ann.loc[ann.index.intersection(ids)]
    return {s: float(r.reindex(sub.index[sub.side == s]).fillna(0).sum()) for s in ("left", "right")}


def li(d):
    t = d["left"] + d["right"]
    return (d["left"] - d["right"]) / t if t else 0.0


# ---------------- A. 多巴胺 ----------------
def dopamine():
    conds = sorted(p.name for p in REF.iterdir() if (p / "rates.csv").exists())
    rows = []
    for c in conds:
        r, s = load(c)
        if r is None:
            continue
        row = {"cond": c, "active": s["runs"][0]["active_neurons"], "runaway": s["runs"][0]["active_neurons"] >= RUNAWAY}
        for g, ids in DAN_GROUPS.items():
            v = r.reindex(ids).fillna(0)
            row[f"{g}_n"] = f"{int((v > 0).sum())}/{len(ids)}"
            row[f"{g}_mean"] = round(float(v.mean()), 2)
            row[f"{g}_max"] = round(float(v.max()), 1)
        rows.append(row)
    t = pd.DataFrame(rows).set_index("cond")
    print("\n[A] 多巴胺神经元（n = 放电数/总数，mean/max = Hz）")
    print(t[["active", "runaway"] + [f"{g}_{k}" for g in DAN_GROUPS for k in ("n", "mean", "max")]].to_string())
    clean_pam = t[(~t.runaway) & (t.PAM_max > 0)].index.tolist()
    return t.reset_index().to_dict("records"), clean_pam


def dopamine_paths():
    comp = pd.read_csv(ROOT / "external/fly-brain/data/2025_Completeness_783.csv", index_col=0)
    fids = comp.index.to_numpy(dtype=np.int64)
    fid2i = {int(f): i for i, f in enumerate(fids)}
    con = pd.read_parquet(ROOT / "external/fly-brain/data/2025_Connectivity_783.parquet",
                          columns=["Presynaptic_Index", "Postsynaptic_Index", "Connectivity"])
    n = len(fids)

    def idx(ids):
        return [fid2i[int(x)] for x in ids if int(x) in fid2i]

    sugar = idx(ann.index[ct == "LB3"])
    bitter = idx(ann.index[ct.isin(["LB1a,LB1d", "LB1b", "LB1c"])])
    out = {}
    for wmin in (1, 5):
        m = con.Connectivity.to_numpy() >= wmin
        A = sp.csr_matrix((np.ones(m.sum(), np.float32), (con.Presynaptic_Index.to_numpy()[m], con.Postsynaptic_Index.to_numpy()[m])), shape=(n, n))
        for src_name, src in (("sugar_LB3", sugar), ("bitter_LB1", bitter)):
            dist = np.full(n, np.inf)
            frontier = np.zeros(n, bool); frontier[src] = True; dist[frontier] = 0
            for h in range(1, 8):
                nxt = ((A.T @ frontier.astype(np.float32)) > 0) & np.isinf(dist)
                if not nxt.any():
                    break
                dist[nxt] = h; frontier = nxt
            for g in ("PAM", "PPL1"):
                d = dist[idx(DAN_GROUPS[g])]
                fin = d[np.isfinite(d)]
                out[f"{src_name}->{g}@w{wmin}"] = dict(min_hops=float(fin.min()) if len(fin) else None,
                                                     median_hops=float(np.median(fin)) if len(fin) else None,
                                                     reachable=f"{len(fin)}/{len(d)}")
    print("\n[A] 结构：味觉 GRN → 多巴胺神经元最短跳数")
    for k, v in out.items():
        print(f"  {k:28s} 最少 {v['min_hops']} 跳，中位 {v['median_hops']} 跳，可达 {v['reachable']}")
    return out


# ---------------- C 的工具：失控起点 ----------------
def timecourse(cond, bin_ms=5):
    s = json.load(open(REF / cond / "summary.json"))
    sp_ = pd.read_parquet(REF / cond / "spikes_baseline.parquet")
    T = s["t_run_s"] * 1000
    sp_["bin"] = (sp_.time_ms // bin_ms).astype(int)
    per = sp_.groupby(["trial", "bin"]).flywire_id.nunique().unstack(fill_value=0)
    curve = per.reindex(columns=range(int(T // bin_ms)), fill_value=0).mean(axis=0)
    hit = np.where(curve.to_numpy() >= 500)[0]
    onset = float(hit[0] * bin_ms) if len(hit) else None
    return sp_, curve, onset


# ---------------- B. LC16 剂量 ----------------
def lc16():
    dn = ann.index[ann.super_class == "descending"]
    rows = []
    for c, hz in [("LC16_LR_25", 25), ("LC16_LR_50", 50), ("LC16_LR_100", 100), ("LC16_LR", 150), ("LC16_L_100", 100), ("LC16_R_100", 100)]:
        r, s = load(c)
        mdn = {sd: float(r.reindex(ann.index[(ct == "MDN") & (ann.side == sd)]).fillna(0).mean()) for sd in ("left", "right")}
        grp = lambda t, sd: float(r.reindex(ann.index[(ct == t) & (ann.side == sd)]).fillna(0).mean())
        dsum = side_sum(r, dn)
        top = r.reindex(dn).fillna(0).sort_values(ascending=False).head(8)
        rows.append(dict(cond=c, lc16_hz=hz, active=s["runs"][0]["active_neurons"], MDN_L=round(mdn["left"], 1), MDN_R=round(mdn["right"], 1),
                         GF=round((grp("DNp01", "left") + grp("DNp01", "right")) / 2, 1),
                         DNa02_L=round(grp("DNa02", "left"), 1), DNa02_R=round(grp("DNa02", "right"), 1),
                         DNa01_L=round(grp("DNa01", "left"), 1), DNa01_R=round(grp("DNa01", "right"), 1),
                         DN_LI=round(li(dsum), 3),
                         top_DN=[f"{ann.cell_type.get(i)}({str(ann.side.get(i))[0]}) {v:.0f}" for i, v in top.items() if v > 0]))
    t = pd.DataFrame(rows)
    print("\n[B] LC16 剂量 → 下行神经元（Hz）")
    print(t.drop(columns="top_DN").to_string(index=False))
    for row in rows:
        print(f"  {row['cond']:12s} 发放最高的下行神经元：{', '.join(row['top_DN'])}")
    return rows


# ---------------- C. 嗅觉 ----------------
def olfaction():
    groups = {"ALPN": ann.index[ann.cell_class == "ALPN"], "LH": ann.index[ann.cell_class.isin(["LHLN", "LHCENT"])],
              "MBON": ann.index[ann.cell_class == "MBON"], "DN": ann.index[ann.super_class == "descending"]}
    res, active_sets = [], {}
    for c in ["DM1_L_10", "DM1_L_20", "DM1_R_20", "DM1_L_50", "DM1_R_50", "DM1_L", "DM1_R", "DA2_L_100", "DA2_L_50", "SUGAR_LR_100", "SUGAR_L_1s"]:
        if not (REF / c / "spikes_baseline.parquet").exists():
            continue
        sp_, curve, onset = timecourse(c)
        active_sets[c] = set(sp_.flywire_id.unique())
        win = sp_[sp_.time_ms < (onset if onset is not None else 1e9)]
        n_tr = json.load(open(REF / c / "summary.json"))["n_trials"]
        row = dict(cond=c, active=len(active_sets[c]), onset_ms=onset)
        for g, ids in groups.items():
            cnt = win[win.flywire_id.isin(ids)].flywire_id.map(ann.side).value_counts()
            L, R = float(cnt.get("left", 0)) / n_tr, float(cnt.get("right", 0)) / n_tr
            row[f"{g}_L"], row[f"{g}_R"] = round(L, 1), round(R, 1)
            row[f"{g}_LI"] = round((L - R) / (L + R), 2) if L + R else None
        res.append(row)
    t = pd.DataFrame(res)
    print("\n[C] 嗅觉：失控起点（ms）与起点之前各群左右脉冲数（每试次）")
    print(t.to_string(index=False))
    comp = {}
    if "DM1_L_10" in active_sets:
        a = active_sets["DM1_L_10"]
        for other in ("DA2_L_100", "SUGAR_LR_100", "DM1_R_20"):
            if other in active_sets:
                b = active_sets[other]
                comp[f"DM1_L_10~{other}"] = round(len(a & b) / len(a | b), 3)
        sc = ann.super_class.reindex(list(a)).fillna("unannotated").value_counts()
        comp["DM1_L_10_super_class"] = sc.head(10).to_dict()
    print("  活跃集合重叠（Jaccard）与失控组成：", comp)
    return res, comp


def dopamine_timing():
    sp_, curve, onset = timecourse("SUGAR_LR_100")
    dan_ids = set(np.concatenate([DAN_GROUPS[g].to_numpy() for g in ("PAM", "PPL1", "PPL2")]))
    d = sp_[sp_.flywire_id.isin(dan_ids)]
    first = float(d.time_ms.min()) if len(d) else None
    print(f"\n[A] SUGAR_LR_100：失控起点 {onset} ms，第一个多巴胺神经元脉冲 {first} ms")
    return dict(runaway_onset_ms=onset, first_dan_spike_ms=first)


if __name__ == "__main__":
    dop, clean_pam = dopamine()
    print("  非失控条件下 PAM 有放电的条件：", clean_pam or "无")
    out = dict(dopamine=dop, dopamine_clean_pam_conditions=clean_pam, dopamine_timing=dopamine_timing())
    out["lc16"] = lc16()
    out["olfaction"], out["olfaction_runaway"] = olfaction()
    out["dopamine_paths"] = dopamine_paths()
    (REF / "v4_analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    print("写入", REF / "v4_analysis.json")
