#!/usr/bin/env python
"""
把全腹神经索模型导出成纯 numpy 可用的文件，供 fba 环境（FlyGym 1.2.1）里的本体感觉闭环使用（两个环境无法合并）。
  * Wt_csr.npz：重加权后的 Wᵀ（行 = 突触后，列 = 突触前，值 = 突触数 × 符号 × 0.03，float32）
  * params_reps0-3.npz：副本 0–3 的 τ、a、θ、r_max（与 vnc/manc_full.py 同一抽样：seed 1、一次抽 16 组）
  * sensors.json：腿神经入口的本体感受器（弦音器 / 毛板 / 钟形感器），按 腿 × 类型 分组的行号
    腿 = instance 里的入口神经：ProLN → 前腿，MesoLN → 中腿，MetaLN → 后腿；_L/_R → 左/右
用法（vnc-sim 环境）：python vnc/export_manc_params.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import manc_full as mf  # noqa: E402


def main():
    W, wt = mf.load_full()
    Wt = W.T.tocsr().astype(np.float32)
    Wt.data = np.where(Wt.data > 0, Wt.data * 0.03, Wt.data * 0.03).astype(np.float32)
    sp.save_npz(mf.OUT / "Wt_csr.npz", Wt)
    npcfg = yaml.safe_load(open(mf.PUG / "configs/neuron_params/default.yaml"))
    tau, a_, thr, frcap = mf.sample_params(wt["size"].values, 16, 1, npcfg)
    np.savez_compressed(mf.OUT / "params_reps0-3.npz", tau=np.asarray(tau)[:4], a=np.asarray(a_)[:4], thr=np.asarray(thr)[:4], frcap=np.asarray(frcap)[:4])
    nerve_leg = {"ProLN": "F", "MesoLN": "M", "MetaLN": "H"}
    sn = wt[wt["class"].isin(["sensory neuron", "sensory ascending"]) & wt.subclass.isin(["chordotonal organ", "hair plate", "campaniform sensilla"])]
    groups = {}
    for i, inst in sn.instance.fillna("").items():
        parts = inst.split("_")
        if len(parts) < 3 or parts[-2] not in nerve_leg or parts[-1] not in ("L", "R"):
            continue
        leg = parts[-1] + nerve_leg[parts[-2]]
        groups.setdefault(leg, {}).setdefault(sn.subclass[i], []).append(int(i))
    counts = {leg: {k: len(v) for k, v in g.items()} for leg, g in sorted(groups.items())}
    (mf.OUT / "sensors.json").write_text(json.dumps(dict(groups=groups, counts=counts), indent=1))
    print("Wt nnz", Wt.nnz, "；本体感受器（腿神经）：", counts)


if __name__ == "__main__":
    main()
