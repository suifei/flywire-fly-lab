"""汇总第 6 轮（虚拟敲除筛选、双敲除、解码器压力测试）→ results/dodge/v6_results.json（供页面渲染）"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "results"
CALL = 0.8


def load(p):
    p = R / p
    return json.loads(p.read_text()) if p.exists() else None


s = load("screen/summary.json")
st = load("language/stress.json")
dk = load("screen/double_summary.json")
dk12 = load("screen/double12_summary.json")     # 12 个输入实现重算的版本，优先用它
expl = s["exploratory_null_normalized"]
corr = 1.0 / expl["null_over_baseline"]["50"]          # 未修正比值 → 修正后比值

TYPE_CT = {"Bract": "DNge173 + DNge174", "Clavicle": "AN_GNG_30", "Fdg": "CB0038", "FMIn": "CB0366", "G2N-1": "CB0616",
           "Phantom": "CB0062", "Rattle": "CB0499", "Roundup": "CB0553", "Usnea": "CB0008", "Zorro": "CB0192"}
types = []
for t, v in s["types"].items():
    types.append(dict(name=t, cell_type=TYPE_CT[t],
                      experiment="必需" if v["experiment_required"] else "不必需",
                      paper=round(v["paper_single_ratio_50Hz"], 2),
                      ours=round(v["50Hz"]["single"]["ratio"] * corr, 2),
                      ours_bilateral=round(v["50Hz"]["bilateral"]["ratio"] * corr, 2),
                      ours_100=round(v["100Hz"]["single"]["ratio"] / expl["null_over_baseline"]["100"], 2),
                      n_members=len(v["members"])))

top = [dict(fid=x["fid"], cell_type=x["cell_type"], nt=x["nt"], rate=x["rate_hz"], ratio=x["ratio_corrected"],
            in_paper=x["in_paper_200"]) for x in expl["exhaustive_50Hz"]["required"][:12]]
inc = [dict(fid=x["fid"], cell_type=x.get("cell_type"), nt=x.get("nt"), rate=x["rate_hz"], ratio=round(x["ratio"] * corr, 2))
       for x in s["exhaustive_50Hz"]["top_increase"][:5]]

out = dict(
    screen=dict(
        design=dict(n_segments=s["plan"]["n_segments"], R=s["plan"]["R"], minutes=round(s["plan"]["n_segments"] * s["plan"]["sec_per_seg"] / 60),
                    n_exhaustive=s["exhaustive_50Hz"]["n"], n_paper=s["plan"]["n_P"], call=CALL),
        baseline=s["V4_baseline_vs_paper"], validation=s["validation"],
        paper=dict(hz50=s["paper_comparison"]["50Hz"], hz100=s["paper_comparison"]["100Hz"], corrected=expl["by_freq"],
                   null_ratio=expl["null_over_baseline"]),
        types=types, top=top, increase=inc,
        counts=dict(required_raw=s["exhaustive_50Hz"]["n_required"], required_corrected=expl["exhaustive_50Hz"]["n_required"],
                    increase_corrected=expl["exhaustive_50Hz"]["n_increase_ge_20pct"],
                    not_in_paper=s["exhaustive_50Hz"]["n_required_not_in_paper_200"]),
        score={k: dict(correct=v["correct"], required=v["predicted_required"]) for k, v in s["experiment_score"].items()},
        score_corrected={k: dict(correct=v["correct"], required=v["predicted_required"]) for k, v in expl["experiment_score"].items()},
        graph=s["exhaustive_50Hz"]["graph_baselines"]),
    stress=dict(full=st["full"], chance=st["chance_shuffled_labels"], n_features=st["n_features"], n_active=st["n_active_train"],
                sampling={k: {n: dict(bal=v["bal_median"], exact=v["exact_median"], first=v["first_sentence_ok_frac"],
                                      radius=v.get("probe_radius_um_median")) for n, v in c.items()} for k, c in st["sampling"].items()},
                min_n=st["min_n_for"],
                noise={sc: {kind: {lvl: v["bal_median"] for lvl, v in d.items()} for kind, d in v.items()} for sc, v in st["noise"].items()},
                dropout={k: {q: v["bal_median"] for q, v in d.items()} for k, d in st["dropout_active_1000"].items()},
                dropout_impute={q: v["bal_median"] for q, v in st["exploratory_dropout_mean_impute"].items()}),
)
if dk12 and dk:
    ct = {x["fid"]: x["cell_type"] for x in json.loads((R / "screen/exhaustive_50Hz.json").read_text())}
    nm = lambda f: ct.get(str(f), str(f))
    s12 = dk12["summary"]
    keep = ("ratio_a", "ratio_b", "ratio_ab", "delta")
    out["double"] = dict(
        design=dict(R=dk12["design"]["R"], n_top=dk["design"]["n_top"], synergy_margin=dk12["design"]["margin"]),
        summary=dict(n_pairs=sum(s12["counts"].values()), n_synergy=s12["counts"]["协同"], n_additive=s12["counts"]["可加"],
                     n_subadditive=s12["counts"]["亚可加"], grn_dose_median=dk["summary"]["grn_dose_median"]),
        stable=s12["loo_stable"], null_ratio=dk12["double_null_over_single_null"],
        synergy=[dict(a_type=nm(x["a"]), b_type=nm(x["b"]), **{k: x[k] for k in keep}) for x in s12["synergy"] if x["loo_stable"]],
        reversal=[dict(a_type=nm(x["a"]), b_type=nm(x["b"]), **{k: x[k] for k in keep}) for x in s12["reversal"] if x["loo_stable"]],
        grn=dk["grn_dose"], top=dk["top"])
    scan = load("screen/hub_scan_summary.json")
    if scan:
        st = [r for r in scan["rows"] if r["verdict"] == "协同" and r["loo_stable"]]
        out["double"]["scan"] = dict(
            n_candidates=len(load("screen/hub_scan_stageA.json")["rows"]), n_stage_b=scan["n_stage_b"],
            hub_ratio=scan["hub_ratio_single"], n_synergy=scan["summary"]["n_synergy"], n_stable=scan["summary"]["n_synergy_stable"],
            backup=[dict(cell_type=r["cell_type"], rate=r["rate_hz"], single=r["ratio_single"], with_hub=r["ratio_with_hub"], delta=r["delta"])
                    for r in st if r["ratio_single"] < 1],
            n_opposite=sum(1 for r in st if r["ratio_single"] >= 1),
            n_subadditive=sum(1 for r in load("screen/hub_scan_stageA.json")["rows"] if r["delta"] <= -0.05))
    hub = load("screen/double_hub_summary.json")
    if hub:
        out["double"]["hub"] = dict(summary=hub["summary"], design=hub["design"],
                                    synergy=[{k: p[k] for k in ("candidate_type", "hub", "ratio_candidate", "ratio_hub", "ratio_pair", "delta", "loo_stable")}
                                             for p in sorted(hub["pairs"], key=lambda x: -x["delta"]) if p["verdict"] == "协同"])
elif dk:
    med2 = dk["null_median_double"]
    R2 = len(med2)
    stable = {"协同": 0, "可加": 0, "亚可加": 0}
    for pr in dk["pairs"]:                      # 留一：去掉任一输入实现后判定是否不变
        e_exp, m = pr["effect_expected"], pr["mn9"]
        vs = []
        for j in range(R2):
            e = 1 - (sum(m) - m[j]) / (sum(med2) - med2[j])
            vs.append("协同" if e > e_exp + 0.1 else ("亚可加" if e < e_exp - 0.1 else "可加"))
        pr["loo_stable"] = all(v == pr["verdict"] for v in vs)
        stable[pr["verdict"]] += pr["loo_stable"]
    syn = sorted([pr for pr in dk["pairs"] if pr["verdict"] == "协同" and pr["loo_stable"]], key=lambda x: -x["delta"])
    rev = sorted([pr for pr in dk["pairs"] if pr["verdict"] == "亚可加" and pr["loo_stable"]
                  and pr["ratio_ab"] > min(pr["ratio_a"], pr["ratio_b"]) + 0.05], key=lambda x: x["delta"])
    out["double"] = dict(summary=dk["summary"], design=dk["design"], top=dk["top"], grn=dk["grn_dose"],
                         null_ratio=dk["double_null_over_single_null"], stable=stable,
                         synergy=[{k: pr[k] for k in ("a_type", "b_type", "ratio_a", "ratio_b", "ratio_ab", "delta")} for pr in syn],
                         reversal=[{k: pr[k] for k in ("a_type", "b_type", "ratio_a", "ratio_b", "ratio_ab", "delta")} for pr in rev])
w = load("screen/water/summary.json")
wl = load("screen/water/double_loo.json")
if w:
    syn = sorted([r for r in (wl or {}).get("pairs", []) if r["verdict"] == "协同" and r["loo_stable"]], key=lambda r: -r["delta"])
    out["water"] = dict(design=w["design"], baseline=w["baseline_mn9"], paper=w["paper_comparison"],
                        types=w["types"], score={k: v["correct"] for k, v in w["experiment_score"].items()},
                        double=dict(n_synergy=w["double"]["n_synergy"], n_additive=w["double"]["n_additive"],
                                    n_subadditive=w["double"]["n_subadditive"], n_stable=len(syn),
                                    synergy=[{k: r[k] for k in ("a", "b", "ra", "rb", "rab", "delta")} for r in syn[:8]]))
jon = load("screen/jon/summary.json")
conc = load("screen/concentration.json")
if jon and conc:
    out["three_pathways"] = dict(
        concentration=conc,
        jon=dict(baseline=jon["baseline"], paper=jon["paper_comparison"],
                 required=jon["required"], double={k: jon["double"][k] for k in ("n_pairs", "n_synergy", "n_additive", "n_subadditive")}))
jp = load("screen/jon_paper/summary.json")
jw = load("screen/jon_weak/summary.json")
if jw and "three_pathways" in out:
    out["three_pathways"]["jon_weak"] = dict(chosen=jw["design"]["chosen"], baseline=jw["design"]["baseline_stats"],
                                             comparison=jw["comparison"], items=jw["items"][:8])
if jp and "three_pathways" in out:
    out["three_pathways"]["jon_paper"] = dict(baseline=jp["design"]["baseline_stats"][str(jp["design"]["chosen"])]["mean"],
                                              comparison=jp["comparison"], items=jp["items"][:6])
# §31：四种口径并排（R=6/12 × 归一化与否）。页面那段「换成未归一化会怎样」以前是**写死**的数字，
# 用户点名过一次，所以改成从这里渲染。
rc = load("screen/recheck_calls.json")
if rc:
    out["recheck_calls"] = rc

jf = load("screen/jon_paper/full_summary.json")   # 24.3 节：用论文名单把整条通路重做，取代 24 节的数字
jc = load("screen/jon_paper/concentration_full.json")   # 22.2 节：全部 596 个活跃神经元的集中度（与糖/水同口径）
if jf and "three_pathways" in out:
    out["three_pathways"]["jon_full"] = dict(design=jf["design"], baseline=jf["baseline"],
                                             paper=jf["paper_comparison"], required=jf["required"],
                                             concentration=jf.get("concentration"),
                                             double={k: jf["double"][k] for k in ("n_pairs", "n_synergy", "n_additive", "n_subadditive")})
if jc and "three_pathways" in out:
    out["three_pathways"]["jon_concentration_full"] = jc
fp = load("screen/dynamic_fingerprint.json")
if fp:
    out["fingerprint"] = {k: {kk: v[kk] for kk in ("n", "spearman_overlap_vs_delta", "spearman_magnitude_vs_delta",
                                                   "partial_overlap_vs_delta_controlling_magnitude",
                                                   "median_overlap_synergy", "median_overlap_subadditive")} for k, v in fp.items()}
sf = load("screen/structure_vs_function.json")
if sf:
    out["structure"] = {k: dict(singles=v["singles"], pairs=v["pairs"], label=v["label"]) for k, v in sf.items()}
pc = load("screen/pathway_compare.json")
ws = load("screen/water/hub_scan_summary.json")
ss = load("screen/hub_scan_summary.json")
sa = load("screen/hub_scan_stageA.json")
if pc and ws and ss and sa:
    st = [r for r in ss["rows"] if r["verdict"] == "协同" and r["loo_stable"]]
    out["pathway"] = dict(
        compare=dict(n_active=pc["n_active"], jaccard=pc["jaccard"], effects=pc["effects_on_common"], hubs=pc["hubs"]),
        scans=dict(
            sugar=dict(hub="CB0883", n_cand=len(sa["rows"]), n_stage_b=ss["n_stage_b"], hub_ratio=ss["hub_ratio_single"],
                       n_syn=ss["summary"]["n_synergy"], n_stable=ss["summary"]["n_synergy_stable"],
                       n_backup=sum(1 for r in st if r["ratio_single"] < 1), n_opposite=sum(1 for r in st if r["ratio_single"] >= 1),
                       n_sub=sum(1 for r in sa["rows"] if r["delta"] <= -0.05)),
            water=dict(hub="CB0051", n_cand=ws["n_candidates"], n_stage_b=ws["n_stage_b"], hub_ratio=ws["hub_ratio_single"],
                       n_syn=ws["summary"]["n_synergy"], n_stable=ws["summary"]["n_stable"], n_backup=ws["summary"]["n_backup"],
                       n_opposite=ws["summary"]["n_opposite"], n_sub=ws["summary"]["n_subadditive_all"])))
(R / "dodge/v6_results.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
print(R / "dodge/v6_results.json", (R / "dodge/v6_results.json").stat().st_size / 1e3, "KB", "双敲除：", "有" if dk else "还没跑完")
