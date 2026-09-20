#!/usr/bin/env python3
"""把 learn/ 各实验的关键数字汇成一个小文件 results/learn/learn_summary.json——页面卡片、日志 §48、台账都从这里读，不手抄。只用标准库。"""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; R = ROOT / "results/learn"
J = lambda f: json.loads((R / f).read_text())
oc, rr, c2, c1, mm, ma, par, fb, gl = J("mb_odor_coding.json"), J("reinforcement_route.json"), J("mb_conditioning.json"), J("mb_conditioning_v1.json"), J("memory_to_motor.json"), J("memory_to_motor_no_apl_mbon.json"), J("parity.json"), J("fullbrain_alln.json"), J("game_learning.json")
legs = json.loads((ROOT / "results/dodge/legs_test.json").read_text()); v5 = json.loads((ROOT / "results/dodge/subcircuit_v5.json").read_text())["meta"]
arm = lambda d, a: {k: v for k, v in d["arms"][a].items() if k != "rows"}
emb = {}
for tag in ("main_s1", "noreinf_s1", "openloop_s1"):
    e = J(f"embodied_{tag}.json"); emb[tag] = {k: e[k] for k in ("seconds", "before", "after", "eat_seconds", "ppl1_seconds", "end", "path_mm", "n_mbon_depressed", "wall_brain_s", "wall_body_s")}
    emb[tag]["track"] = [[round(l["x"], 1), round(l["y"], 1)] for l in e["log"][::5]]
    hot = [l for l in e["log"] if l["heat"] > 0.3]; emb[tag]["max_heat"] = max((l["heat"] for l in e["log"]), default=0); emb[tag]["heat_seconds"] = round(len(hot) * 4 * e["window_ms"] / 1000, 2)
    yaw = [l["yaw"] for l in e["log"]]; emb[tag]["turned_back"] = bool(any(abs(y) > 2.0 for y in yaw))
m, n = emb["main_s1"], emb["noreinf_s1"]; rel = lambda a, b: a / b if b else None
emb["E1_A_pam_vs_control"] = rel(m["after"]["A"]["PAM"], n["after"]["A"]["PAM"]); emb["E1_B_ppl1_vs_control"] = rel(m["after"]["B"]["PPL1"], n["after"]["B"]["PPL1"])
emb["E2_B_pam_vs_control"] = rel(m["after"]["B"]["PAM"], n["after"]["B"]["PAM"]); emb["E2_A_ppl1_vs_control"] = rel(m["after"]["A"]["PPL1"], n["after"]["A"]["PPL1"])
emb["criteria"] = dict(E1_learned_in_body=bool(emb["E1_A_pam_vs_control"] <= 0.7 and emb["E1_B_ppl1_vs_control"] <= 0.7), E1a_reward=bool(emb["E1_A_pam_vs_control"] <= 0.7), E1b_punish=bool(emb["E1_B_ppl1_vs_control"] <= 0.7),
                       E2_no_crosstalk=bool(abs(emb["E2_B_pam_vs_control"] - 1) < 0.3 and abs(emb["E2_A_ppl1_vs_control"] - 1) < 0.3))
emb["E3_end_distance_closed_vs_open_mm"] = ((m["end"][0] - emb["openloop_s1"]["end"][0]) ** 2 + (m["end"][1] - emb["openloop_s1"]["end"][1]) ** 2) ** 0.5
top = lambda d: [dict(pair=r["pair"], reinforcer=r["reinforcer"], top=[{k: (round(x[k], 1) if isinstance(x[k], float) else x[k]) for k in ("type", "side", "mock", "paired", "t")} for x in r["top_descending"][:3]]) for r in d["rows"]]
out = dict(
    v5=dict(n=v5["n"], n_edges=v5["n_edges"], n_v4=v5["n_v4"], n_tag=v5["n_tag"], mb_wmin=v5["mb_wmin"], n_glomeruli=len(v5["glomeruli"]), odors={k: len(g) for k, g in v5["odors"].items()}),
    odor_coding={a: {k: v for k, v in d.items() if k != "odors"} for a, d in oc["arms"].items()} | {"main_arm": oc["main_arm"]},
    fullbrain={a: {k: v for k, v in d.items() if k != "rows"} for a, d in fb["arms"].items()} | {"prediction_holds": fb["prediction_holds"], "n": fb["n"],
               "lateralization": {k: ({kk: vv for kk, vv in v.items() if kk != "rows"} if isinstance(v, dict) else v) for k, v in fb.get("lateralization", {}).items()}},
    reinforcement=dict(n=rr["n"], n_conditions=len(rr["conditions"]), any_route=rr["any_route"], max_dan=rr["max_dan_ge5hz_without_runaway"], max_active=max(c["active_others"] for c in rr["conditions"])),
    conditioning=dict(params=c2["params"], connectome=arm(c2, "connectome"), shuffle=arm(c2, "shuffle_pn_kc"), v1=arm(c1, "connectome"), v1_params=c1["params"]),
    memory_to_motor=dict(v5=dict(summary=mm["summary"], M2=mm["M2_any_stable"], n_rows=mm["n_rows"], max_hits=mm["max_hits"], n_test=mm["n_test"], top=top(mm)),
                         no_apl_mbon=dict(summary=ma["summary"], M2=ma["M2_any_stable"], n_rows=ma["n_rows"], max_hits=ma["max_hits"], n_responsive=ma["n_mbon_types_responsive"], n_types=ma["n_mbon_types"], motor_mbon=ma["motor_mbon_mean_hz"], max_kc_frac=ma["max_kc_frac"], top=top(ma))),
    parity=par, legs=dict(all_pass=legs["all_pass"], tests={k: {kk: vv for kk, vv in t.items() if kk in ("path_speed", "yaw_deg_s", "signed_x", "min_stance", "unstable_frac", "pass")} | ({"left_yaw": t["left"]["yaw_deg_s"], "right_yaw": t["right"]["yaw_deg_s"]} if "left" in t else {}) for k, t in legs["tests"].items()},
                          explore={k: dict(speed=t["path_speed"], yaw=t["yaw_deg_s"], unstable=t["unstable_frac"]) for k, t in legs["explore"].items()}),
    game=gl, embodied=emb)
# v5 保不保得住 v4 上量过的东西：同一脚本在两份子回路上各跑一遍
D = ROOT / "results/dodge"; cmpv = {}
if (D / "sense_modulation_v5.json").exists():
    a, b = json.loads((D / "sense_modulation.json").read_text()), json.loads((D / "sense_modulation_v5.json").read_text())
    cmpv["modulation"] = [dict(base=x["base"], mod=x["mod"], readout=x["readout"], v4=x["hz"]["mean"], v5=y["hz"]["mean"], v4_base=x["base_hz"]["mean"], v5_base=y["base_hz"]["mean"], v4_mod=x["modulates"], v5_mod=y["modulates"]) for x, y in zip(a["rows"], b["rows"])]
    cmpv["modulation_same_calls"] = int(sum(r["v4_mod"] == r["v5_mod"] for r in cmpv["modulation"])); cmpv["modulation_n"] = len(cmpv["modulation"])
if (D / "sound_priming_v5.json").exists():
    a, b = json.loads((D / "sound_priming.json").read_text()), json.loads((D / "sound_priming_v5.json").read_text())
    cmpv["sound_priming"] = {k: dict(v4_lead=a["groups"][k]["lead_ms_median"], v5_lead=b["groups"][k]["lead_ms_median"], v4_dodged=a["groups"][k]["dodged"], v5_dodged=b["groups"][k]["dodged"]) for k in a["groups"]}; cmpv["sound_priming_n"] = b["n"]
out["v5_vs_v4"] = cmpv
if (R / "court_five.json").exists(): cf = J("court_five.json"); out["court_five"] = {"seconds": cf["seconds"], "seeds": cf["seeds"], **{k: v["mean"] for k, v in cf["worlds"].items()}}
if (R / "uturn_cause.json").exists(): u = J("uturn_cause.json"); out["uturn"] = {k: {kk: vv for kk, vv in v.items() if kk != "rows"} for k, v in u["conds"].items()} | {"seeds": u["seeds"]}
if "n_mbon_types_responsive" in mm: out["memory_to_motor"]["v5"].update(n_responsive=mm["n_mbon_types_responsive"], n_types=mm["n_mbon_types"], motor_mbon=mm["motor_mbon_mean_hz"])
(R / "learn_summary.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":"))); print("→ results/learn/learn_summary.json", (R / "learn_summary.json").stat().st_size, "字节")
print(json.dumps(emb["criteria"]), {k: round(v, 3) for k, v in emb.items() if k.startswith("E") and isinstance(v, float)})
