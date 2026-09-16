#!/usr/bin/env python
"""
把受"种子编译进程序"影响的全脑参考实验重跑一遍（报告 14.0 节）。

旧结果里每个条件的 n 个"试次"其实是同一次模拟的 n 份拷贝。`run_experiment.py` 已修好（多试次时不设种子，
各试次由系统随机源播种，互相独立）。这里按旧 summary.json 里记录的参数原样重跑，并把旧结果备份到
results/<name>_seedbug/，最后给出新旧对比（每个条件读出神经元的均值 ± 试次标准差，以及旧值落在什么位置）。

用法（brain-fly-cpu 环境）：python scratch/rerun_refs.py [--dry]
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DIRS = [ROOT / "results" / "v2_ref", ROOT / "results" / "dodge_ref"]
GROUPS = [("CB0701", "MN9"), ("DNg62", "aDN1"), ("MDN", "MDN"), ("DNa01", "DNa01"), ("DNa02", "DNa02"),
          ("DNp01", "GF"), ("DNg97", "oDN1"), ("DNg100", "BDN2")]


def conditions():
    out = []
    for d in DIRS:
        for sub in sorted(p for p in d.iterdir() if p.is_dir()):
            f = sub / "summary.json"
            if not f.exists():
                continue
            s = json.loads(f.read_text())
            if (s.get("n_trials") or 1) > 1 and "brian2" in str(s.get("backend_requested", "brian2")):
                out.append((sub, s))
    return out


def cmd_for(sub, s):
    c = [sys.executable, str(ROOT / "run_experiment.py"), "--exc", *[str(i) for i in s["exc_ids"]],
         "--rate", str(s["rate_hz"]), "--t_run", str(s["t_run_s"]), "--n_trials", str(s["n_trials"]),
         "--out", str(sub)]
    if s.get("silence_ids"):
        c += ["--silence", *[str(i) for i in s["silence_ids"]]]
    c += ["--record", *[str(i) for i in s.get("record_ids") or []]]    # 与旧命令一致：--record 不带参数 = 不记膜电位
    return c


def group_rates(sub, ann, cond):
    """按试次算每个读出组的平均发放率。"""
    f = sub / f"spikes_{cond}.parquet"
    if not f.exists():
        return None
    df = pd.read_parquet(f)
    s = json.loads((sub / "summary.json").read_text())
    T = s["t_run_s"]
    out = {}
    for t, name in GROUPS:
        for side in ("left", "right"):
            ids = set(ann.root_id[(ann.cell_type == t) & (ann.side == side)])
            if not ids:
                continue
            sel = df[df.flywire_id.isin(ids)]
            per = [len(sel[sel.trial == k]) / (T * max(len(ids), 1)) for k in sorted(df.trial.unique())]
            out[f"{name}_{side[0].upper()}"] = per
    out["active"] = [int(df[df.trial == k].flywire_id.nunique()) for k in sorted(df.trial.unique())]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    conds = conditions()
    print(f"待重跑 {len(conds)} 个条件", flush=True)
    ann = pd.read_csv(ROOT / "external/flywire_annotations/Supplemental_file1_neuron_annotations.tsv", sep="\t",
                      low_memory=False, usecols=["root_id", "cell_type", "side"]).drop_duplicates("root_id")
    old_rates = {}
    for sub, s in conds:
        for cond in ("baseline", "silenced"):
            g = group_rates(sub, ann, cond)
            if g:
                old_rates[(sub.name, cond)] = {k: v[0] for k, v in g.items()}   # 旧结果 n 份拷贝相同，取第 1 份
    if a.dry:
        for sub, s in conds:
            print(" ".join(cmd_for(sub, s))[:200])
        return
    t0 = time.time()
    for i, (sub, s) in enumerate(conds):
        backup = sub.parent.parent / f"{sub.parent.name}_seedbug" / sub.name
        if not backup.exists():
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(sub, backup)
        r = subprocess.run(cmd_for(sub, s), capture_output=True, text=True)
        ok = r.returncode == 0
        print(f"[{i + 1}/{len(conds)}] {sub.parent.name}/{sub.name} {'OK' if ok else '失败'} "
              f"{time.time() - t0:.0f}s 累计", flush=True)
        if not ok:
            print(r.stdout[-1500:], r.stderr[-1500:], flush=True)
            raise SystemExit(1)
    # 新旧对比
    rows = []
    for sub, s in conds:
        for cond in ("baseline", "silenced"):
            g = group_rates(sub, ann, cond)
            if not g:
                continue
            old = old_rates.get((sub.name, cond), {})
            for k, per in g.items():
                per = np.array(per, float)
                o = old.get(k)
                rows.append(dict(cond=f"{sub.parent.name}/{sub.name}", readout=k, n_trials=len(per),
                                 new_mean=round(float(per.mean()), 2), new_sd=round(float(per.std(ddof=1)), 2),
                                 new_min=round(float(per.min()), 2), new_max=round(float(per.max()), 2),
                                 old=None if o is None else round(float(o), 2),
                                 old_z=None if (o is None or per.std(ddof=1) == 0) else round(float((o - per.mean()) / per.std(ddof=1)), 2),
                                 identical_trials=bool(len(set(np.round(per, 6))) == 1)))
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "results/v2_ref/rerun_diff.csv", index=False)
    big = df[(df.old.notna()) & (df.new_sd > 0) & (df.old_z.abs() >= 2)]
    print(f"\n共 {len(df)} 个读出；旧值偏离新均值 ≥ 2 个标准差的有 {len(big)} 个：", flush=True)
    print(big.to_string(index=False)[:4000])
    print("\n写入 results/v2_ref/rerun_diff.csv", flush=True)


if __name__ == "__main__":
    main()
