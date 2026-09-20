#!/usr/bin/env python3
"""生态箱：把 results/eco/ 下各实验的结果汇成一份 summary.json——页面的实测卡、docs/ecobox/RESULTS.md、台账都从它取数，不手抄。
缺哪份结果就缺哪一块（页面对应的卡不显示），不编数字。用法：python3 eco/collect_results.py"""
import json, os, sys
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); D = os.path.join(ROOT, "results/eco")
def load(name):
    p = os.path.join(D, name); return json.load(open(p)) if os.path.exists(p) else None
out = {}
au = load("audit.json")
if au:
    out["audit"] = {"hz": au["hz"], "seeds": au["seeds"], "n_neurons": au["n_neurons"], "realtime_one": au["speed"]["realtime_factor_one_fly"], "realtime_32": au["speed"]["realtime_factor_32_flies"],
                    "flight": au["flight"]["verdict"], "channels": [{"name": s["label"].split("（")[0], "verdict": s["verdict"]} for s in au["senses"].values()]}
sf, sf1 = load("brain_surface.json"), load("surface_fit_v1.json")
if sf:
    out["surface"] = {"n_neurons": au["n_neurons"] if au else None, "n_samples": sf["n_samples"], "n_test": sf["n_test"], "r2_min": sf["criterion"]["r2_hz_min"], "pass": sf["criterion"]["pass"],
                      "features": [{"name": f, "r2": sf["heldout"][f]["r2_hz"], "silent": sf["heldout"][f].get("silent", False)} for f in sf["features"]],
                      "vs_mean": {f: v["model_vs_mean"] for f, v in (sf.get("noise_ceiling_exploratory") or {}).get("per_feature", {}).items()},
                      "ceiling": {f: v["single_vs_rest"] for f, v in (sf.get("noise_ceiling_exploratory") or {}).get("per_feature", {}).items()}}
    if sf1: out["surface"].update({"v1_samples": sf1["n_samples"], "v1_dna": f'{sf1["heldout"]["dnaL"]["r2_hz"]:.2f} / {sf1["heldout"]["dnaR"]["r2_hz"]:.2f}', "v1_pass": sf1["criterion"]["pass"]})
m2, m21 = load("m2_learning.json"), load("m2_learning_v1.json")
if m2:
    P = m2["protocol"]
    out["m2"] = {"train_lives": P["train_lives"], "test_lives": P["test_lives"], "cap_s": P["cap_s"], "C1": m2["criteria"]["C1_all"], "C2": m2["criteria"]["C2_all"], "n_features": m2["n_features"],
                 "individuals": [{"base": i["base"], "off": round(i["arms"]["off"]["test_median_life"]), "on": round(i["arms"]["on"]["test_median_life"]), "ratio_on": i["ratio_on"], "ratio_shuffle": i["ratio_shuffle"],
                                  "ratio_yoked": i["ratio_yoked_posthoc"], "ratio_nobrain": i["ratio_nobrain"], "drinks_per_visit_on": i["arms"]["on"]["drinks_per_water_visit"], "drinks_per_visit_off": i["arms"]["off"]["drinks_per_water_visit"]} for i in m2["individuals"]],
                 "learned": m2["individuals"][0]["learned"], "robust_learned": m2["robustness"]["n_learned"], "robust_n": m2["robustness"]["n"],
                 "drought_off": round(m2["worlds"]["drought"]["off_median"]), "drought_on": round(m2["worlds"]["drought"]["on_median"]), "long_lives30": round(m2["longer_training_drought"]["lives30_median"]), "long_lives120": round(m2["longer_training_drought"]["lives120_median"]),
                 "worlds": {k: {"off": round(w["off_median"]), "on": round(w["on_median"]), "causes": w["on_causes"], "cards": w["on_cards"]} for k, w in m2["worlds"].items()}, "seconds": m2["seconds"]}
    if m21:
        out["m2"].update({"v1_C2": f'{sum(1 for i in m21["individuals"] if i["C2"])}/{len(m21["individuals"])}', "v1_shuffle_ratios": [i["ratio_shuffle"] for i in m21["individuals"]]})
    nd = load("m2_no_decay.json")
    if nd: out["m2"]["no_decay"] = {"learned": f'{nd["n_learned"]}/{nd["n"]}', "wall": nd["n_wall"], "rest": nd["n_rest"]}
m3 = load("m3_evolution.json")
if m3 and len(m3["worlds"]) == 3:
    out["m3"] = {"seconds": m3["protocol"]["seconds"], "n_seeds": len(m3["protocol"]["seeds"]), "pass": m3["criterion"]["pass"], "labels": m3["criterion"]["labels"],
                 "worlds": [{"key": k, "name": w["name"], "label": w["label"], "deltas": [round(r["delta_flight"], 2) for r in w["runs"]], "delta_mean": w["delta_mean"], "n_up": w["n_up"], "n_down": w["n_down"],
                             "life_head": round(sum(r["mean_life_head"] for r in w["runs"]) / len(w["runs"])), "life_tail": round(sum(r["mean_life_tail"] for r in w["runs"]) / len(w["runs"])),
                             "drink": round(sum(r["genes_tail"]["innateTurn2"] for r in w["runs"]) / len(w["runs"]), 2), "learnRate": round(sum(r["genes_tail"]["learnRate"] for r in w["runs"]) / len(w["runs"]), 4),
                             "odorTurn": round(sum(r["genes_tail"]["innateTurn3"] for r in w["runs"]) / len(w["runs"]), 2), "immigrants": [r["immigrants"] for r in w["runs"]], "gen_max": [r["gen_max"] for r in w["runs"]],
                             "flights_tail": [r["flights_per_fly_min_tail"] for r in w["runs"]]} for k, w in m3["worlds"].items()]}
m4 = load("m4_save_test.json")
if m4:
    NAMES = {"S1_resume_bit_identical": "续跑逐位相同", "S2_format_stable": "存档格式稳定", "S3_challenge_roundtrip": "挑战码来回无损", "S4_bad_input_rejected": "坏输入被拒绝"}
    out["m4"] = {"pass": m4["pass"], "checks": [{"name": NAMES.get(k, k), "pass": c["pass"]} for k, c in m4["checks"].items()], "fingerprint": m4["checks"]["S1_resume_bit_identical"]["resumed"], "save_bytes": m4["checks"]["S1_resume_bit_identical"]["save_bytes"], "code_chars": m4["checks"]["S3_challenge_roundtrip"]["code_chars"]}
lg = load("train_long.json")
if lg:
    out["long"] = {"n": lg["n"], "n_learned": lg["n_learned"], "n_retest_ok": lg["n_retest_ok"], "goal_met": lg["goal_met"], "total_lives": lg["total_lives"], "baseline": round(lg["baseline_median"]), "need": round(lg["need_s"]),
                   "lives_per_round": lg["rule"]["lives_per_round"], "max_rounds": lg["rule"]["max_rounds"], "test_worlds": lg["rule"]["test_worlds"], "rounds_to_learn": lg["rounds_to_learn"],
                   "individuals": [{"k": d["k"], "rounds": d["rounds"], "learned": d["learned"], "median": round(d["last"]["median"]) if d["last"] else None, "wall": d["last"]["wall"] if d["last"] else None, "rest": d["last"]["rest"] if d["last"] else None,
                                    "retest": round(d["retest"]["median"]) if d["retest"] else None, "retest_ok": bool(d["retest"] and d["retest"]["ok"])} for d in lg["individuals"]]}
lv = load("live_check.json")
if lv: out["live"] = lv["summary"]
json.dump(out, open(os.path.join(D, "summary.json"), "w"), ensure_ascii=False, indent=1)
print("写了 results/eco/summary.json：", "、".join(out.keys()))
