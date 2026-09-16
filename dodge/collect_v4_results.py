"""汇总第 4 轮（多巴胺、LC16 剂量与后退重做、低强度嗅觉与失控诊断、腹神经索发放率模型与腿）→ results/dodge/v4_results.json（供页面渲染）"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "results"


def load(p):
    p = R / p
    return json.loads(p.read_text()) if p.exists() else None


ana = load("v2_ref/v4_analysis.json")
DOP_ROWS = [("SUGAR_L_1s", "糖味左 200 Hz · 1 s"), ("SUGAR_L", "糖味左 200 Hz"), ("BITTER", "苦味双侧 200 Hz"),
            ("SUGAR_R", "糖味右 200 Hz"), ("SUGAR_LR_100", "糖味双侧 100 Hz"), ("SUGAR_BITTER", "糖 + 苦 200 Hz"),
            ("DM1_L_10", "对照：气味 DM1 左 10 Hz"), ("LC16_LR", "对照：LC16 双侧 150 Hz")]
dop = {r["cond"]: r for r in ana["dopamine"]}
out = dict(
    dopamine=dict(rows=[dict(label=l, cond=c, active=dop[c]["active"], runaway=dop[c]["runaway"],
                             PAM_n=dop[c]["PAM_n"], PAM_mean=dop[c]["PAM_mean"], PPL1_n=dop[c]["PPL1_n"], PPL1_mean=dop[c]["PPL1_mean"])
                        for c, l in DOP_ROWS if c in dop],
                  timing=ana["dopamine_timing"], paths=ana["dopamine_paths"]),
    lc16=ana["lc16"],
    olfaction=dict(rows=ana["olfaction"], runaway=ana["olfaction_runaway"], diagnosis=load("v2_ref/olfaction_runaway.json"),
                   silencing=load("v2_ref/olfaction_silencing.json"),
                   odor_nav={k: v for k, v in (load("dodge/odor_v4.json") or {}).items()} or None),
    vnc_rate=dict(summary={k: {kk: v[kk] for kk in ("frac_oscillating", "median_net_score", "median_freq_hz", "reps", "stim_I")}
                           for k, v in (load("vnc/pugliese/summary.json") or {}).items()},
                  analysis=load("vnc/pugliese/analysis.json"), legs=load("vnc/pugliese/legs_summary.json")),
    vnc_full=dict(meta=load("vnc/manc_full/W_meta.json"), parity_T1=load("vnc/manc_full/parity_T1.json"),
                  analysis=load("vnc/manc_full/analysis.json"),
                  osc_ranges={k: dict(freq=[min(f), max(f)] if (f := [r["mean_freq_hz"] for r in v["runs"] if r["oscillating"] and r["mean_freq_hz"]]) else None,
                                      n_osc=sum(r["oscillating"] for r in v["runs"]), n_runaway=sum(r["n_active_all_1hz"] >= 2000 for r in v["runs"]), reps=v["reps"])
                              for k, v in (load("vnc/manc_full/summary.json") or {}).items()},
                  legs=load("vnc/manc_full/legs_summary.json"), gap=load("vnc/manc_full/gap_summary.json"),
                  proprio_parity=load("vnc/manc_full/proprio_parity.json"), proprio=load("vnc/manc_full/proprio_summary.json"),
                  proprio_phasic=load("vnc/manc_full/proprio_phasic_summary.json")),
    vnc_all=dict(meta=load("vnc/manc_all/W_meta.json"), analysis=load("vnc/manc_all/analysis.json"),
                 osc_ranges={k: dict(freq=[min(f), max(f)] if (f := [r["mean_freq_hz"] for r in v["runs"] if r["oscillating"] and r["mean_freq_hz"]]) else None,
                                     n_osc=sum(r["oscillating"] for r in v["runs"]), n_runaway=sum(r["n_active_all_1hz"] >= 2000 for r in v["runs"]), reps=v["reps"])
                             for k, v in (load("vnc/manc_all/summary.json") or {}).items()},
                 legs=load("vnc/manc_all/legs_summary.json"), gap=load("vnc/manc_all/gap_summary.json"),
                 proprio_parity=load("vnc/manc_all/proprio_parity.json"), proprio_phasic=load("vnc/manc_all/proprio_phasic_summary.json")),
    backward_v4=load("dodge/backward_v4.json"),
    rl_speed=load("dodge/rl_speed.json"),
)
p = R / "dodge" / "v4_results.json"
p.write_text(json.dumps(out, ensure_ascii=False))
print("写入", p, f"{p.stat().st_size / 1e3:.0f} KB", {k: v is not None for k, v in out.items()})
