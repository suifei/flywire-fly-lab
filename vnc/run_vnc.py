#!/usr/bin/env python
"""
第 5 步 B：在 BANC 腹神经索 LIF 子网络里刺激下行神经元，记录腿部运动神经元，检验是否出现行走节律。

条件（每个 1 s，双侧刺激，Poisson 150 Hz；复用 run_experiment.py 的 Brian2 standalone 路径）：
  BDN2   = DNg100 L/R        （Bidaye et al. 2020：前进行走指令神经元）
  oDN1   = DNg97 L/R
  P9     = DNp09 L/R
  FWD    = BDN2 + oDN1 + P9
  MDN    = MDN ×4            （后退）
  GF     = DNp01 L/R         （逃逸；真实动物中 GF→TTMn 主要是电突触，化学突触连接组里未必体现）
分析（10 ms 分箱，1 s）：每条腿 × 每类关节运动神经元（屈/伸）的平均发放率；
  节律：去均值后的功率谱在 4–20 Hz 的峰值占比；屈伸反相：同一关节屈、伸群发放率的相关系数；
  左右相位：同节段左右腿股胫屈肌群发放率的相关系数。
用法（brain-fly-cpu）：python vnc/run_vnc.py
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
VNC = ROOT / "external" / "banc_vnc"
OUT = ROOT / "results" / "vnc"
DN = json.load(open(ROOT / "vnc" / "dn_ids.json"))
CONDS = {
    "BDN2": DN["DNg100"], "oDN1": DN["DNg97"], "P9": DN["DNp09"],
    "FWD": DN["DNg100"] + DN["DNg97"] + DN["DNp09"], "MDN": DN["MDN"], "GF": DN["DNp01"],
}
LEGS = {"prothoracic": "前", "mesothoracic": "中", "metathoracic": "后"}
JOINTS = {  # BANC Function → (关节, 屈/伸)
    "flex_coxa_trochanter_joint": ("CTr", "flex"), "extend_coxa_trochanter_joint": ("CTr", "ext"),
    "flex_femur_tibia_joint": ("FTi", "flex"), "extend_femur_tibia_joint": ("FTi", "ext"),
    "flex_tibia_tarsus_joint": ("TiTa", "flex"), "extend_tibia_tarsus_joint": ("TiTa", "ext"),
    "move_coxa_anterior": ("ThC", "ext"), "move_coxa_posterior": ("ThC", "flex"),
}


def mn_table():
    n = pd.read_csv(VNC / "neurons_vnc.csv", low_memory=False)
    mn = n[n["Class"] == "leg_motor_neuron"].copy()
    def leg(row):
        nerve = str(row["Nerve"]); side = "L" if nerve.startswith("left") else "R" if nerve.startswith("right") else str(row["Soma side"])[0].upper()
        seg = next((v for k, v in LEGS.items() if k in nerve), None)
        return f"{seg}{side}" if seg else None
    mn["leg"] = mn.apply(leg, axis=1)
    def joint(f):
        for k, v in JOINTS.items():
            if isinstance(f, str) and k in f: return v
        return (None, None)
    mn[["joint", "dir"]] = mn["Function"].apply(lambda f: pd.Series(joint(f)))
    return mn


def run(cond, ids, rate=150.0, t_run=1.0):
    out = OUT / cond
    if (out / "spikes_baseline.parquet").exists():
        return out
    env = dict(os.environ, FLY_BRAIN_REPO=str(VNC))
    cmd = [sys.executable, str(ROOT / "run_experiment.py"), "--exc", *map(str, ids), "--rate", str(rate), "--t_run", str(t_run),
           "--n_trials", "1", "--record", "--out", str(out)]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-1500:], r.stderr[-1500:]); raise SystemExit(f"{cond} 失败")
    return out


def analyze(cond, out, mn, t_run=1.0):
    sp = pd.read_parquet(out / "spikes_baseline.parquet")
    edges = np.arange(0, t_run * 1000 + 1e-9, 10)
    rows = {}
    for (leg, jt, d), g in mn.dropna(subset=["leg", "joint"]).groupby(["leg", "joint", "dir"]):
        ids = set(g["Root ID"].astype(np.int64))
        s = sp[sp.flywire_id.isin(ids)]
        h, _ = np.histogram(s.time_ms, bins=edges)
        rows[(leg, jt, d)] = h / (0.01 * len(ids))
    def rhythm(x):
        x = x[10:] - x[10:].mean()                                      # 去掉前 100 ms 起始瞬态
        if x.std() < 1e-9: return 0.0, None
        P = np.abs(np.fft.rfft(x)) ** 2; f = np.fft.rfftfreq(len(x), 0.01)
        band = (f >= 4) & (f <= 20)
        return float(P[band].sum() / P[1:].sum()), float(f[band][P[band].argmax()])
    summ = dict(cond=cond, total_spikes=int(len(sp)), active_neurons=int(sp.flywire_id.nunique()),
                legmn_active=int(sp.flywire_id.isin(set(mn["Root ID"].astype(np.int64))).sum() and sp[sp.flywire_id.isin(set(mn["Root ID"].astype(np.int64)))].flywire_id.nunique()))
    per = []
    for leg in ["前L", "前R", "中L", "中R", "后L", "后R"]:
        for jt in ["ThC", "CTr", "FTi", "TiTa"]:
            fl, ex = rows.get((leg, jt, "flex")), rows.get((leg, jt, "ext"))
            rf = fl[10:].mean() if fl is not None else np.nan
            re_ = ex[10:].mean() if ex is not None else np.nan
            corr = float(np.corrcoef(fl[10:], ex[10:])[0, 1]) if fl is not None and ex is not None and fl[10:].std() > 0 and ex[10:].std() > 0 else np.nan
            rp, rfreq = rhythm(fl) if fl is not None else (np.nan, None)
            per.append(dict(cond=cond, leg=leg, joint=jt, flex_hz=rf, ext_hz=re_, flex_ext_corr=corr, rhythm_power=rp, rhythm_freq=rfreq))
    lr = {}
    for seg in "前中后":
        a, b = rows.get((f"{seg}L", "FTi", "flex")), rows.get((f"{seg}R", "FTi", "flex"))
        lr[seg] = float(np.corrcoef(a[10:], b[10:])[0, 1]) if a is not None and b is not None and a[10:].std() > 0 and b[10:].std() > 0 else None
    summ["left_right_FTi_flex_corr"] = lr
    np.savez_compressed(out / "mn_rates.npz", t_ms=edges[:-1], **{f"{l}|{j}|{d}": v for (l, j, d), v in rows.items()})
    return summ, per


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    mn = mn_table()
    print("腿部运动神经元映射到 (腿, 关节, 屈/伸)：", int(mn.dropna(subset=["leg", "joint"]).shape[0]), "/", len(mn))
    summaries, pers = [], []
    for cond, ids in CONDS.items():
        out = run(cond, ids)
        s, per = analyze(cond, out, mn)
        summaries.append(s); pers += per
        P = pd.DataFrame(per)
        act = P[(P.flex_hz > 0) | (P.ext_hz > 0)]
        print(f"\n== {cond}（刺激 {len(ids)} 个下行神经元）：全网 spike {s['total_spikes']}，活跃 {s['active_neurons']}，活跃腿部运动神经元 {s['legmn_active']}")
        if len(act):
            print("   有活动的 (腿,关节)：" + "；".join(f"{r.leg}{r.joint} 屈{r.flex_hz:.0f}/伸{r.ext_hz:.0f}Hz" + (f" 节律功率{r.rhythm_power:.2f}@{r.rhythm_freq:.0f}Hz" if r.rhythm_freq else "") for r in act.itertuples()))
        print("   左右同节段股胫屈肌相关：", s["left_right_FTi_flex_corr"])
    pd.DataFrame(pers).to_csv(OUT / "mn_joint_summary.csv", index=False)
    json.dump(summaries, open(OUT / "summary.json", "w"), ensure_ascii=False, indent=1)
    print("\n写入", OUT / "mn_joint_summary.csv", OUT / "summary.json")


if __name__ == "__main__":
    main()
