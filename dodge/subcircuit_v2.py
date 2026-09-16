"""
子回路 v2：在 v1（looming → 转向/逃逸）基础上加入 进食、苦味抑制、梳理、后退 通路。
选择规则、模型与参考仿真器与 subcircuit.py 完全相同（直接复用其 Subcircuit.simulate 的数值方案），
只把输入/输出组推广为“多个细胞类型 × 侧别”的组合。

输入组（注释表 cell_type × side）：
  LC4_*, LPLC2_*           looming（v1）
  LC16_*                   后退相关视觉投射神经元（全脑实测：双侧 LC16 150 Hz → MDN 32/31 Hz）
  SUGAR_*  = LB3           糖/水味觉（全脑：左侧 → MN9 66/114 Hz）
  BITTER_* = LB1a,LB1d / LB1b / LB1c   苦味（全脑：与糖同时给 → MN9 降到 18/18 Hz）
  JO_*     = JO-CA1/CA2/CL/CM/ED1/ED2_a–c/EV1–6   触角 JO（全脑：左侧 → aDN1 右 40 Hz）
输出组：DNa01/DNa02/DNp01(GF)/CB0701(MN9)/DNg62(aDN1)/MDN，各分左右

用法（brain-fly-cpu）：
  python dodge/subcircuit_v2.py compare     # 多组 (wmin,K) vs 全脑参考（results/dodge_ref 与 results/v2_ref）
  python dodge/subcircuit_v2.py export --wmin 5 --K 3
"""
import argparse
import base64
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

import subcircuit as v1

ROOT = Path(__file__).resolve().parent.parent
JO_TYPES = ["JO-CA1", "JO-CA2", "JO-CL", "JO-CM", "JO-ED1", "JO-ED2_a", "JO-ED2_b", "JO-ED2_c",
            "JO-EV1", "JO-EV2", "JO-EV3", "JO-EV4", "JO-EV5", "JO-EV6"]
INPUT_TYPES = {"LC4": ["LC4"], "LPLC2": ["LPLC2"], "LC16": ["LC16"], "SUGAR": ["LB3"],
               "BITTER": ["LB1a,LB1d", "LB1b", "LB1c"], "JO": JO_TYPES}
TARGET_TYPES = {"DNa01": ["DNa01"], "DNa02": ["DNa02"], "DNp01": ["DNp01"], "MN9": ["CB0701"],
                "aDN1": ["DNg62"], "MDN": ["MDN"]}
SIDES = ("left", "right")

# 参考实验：名称 → ({输入组: Hz}, 目录)；与 run_experiment.py --exc_type 选的神经元一致
REFS = {
    "LOOM_L_100": ({"LC4_left": 100, "LPLC2_left": 100}, "dodge_ref"),
    "LOOM_R_100": ({"LC4_right": 100, "LPLC2_right": 100}, "dodge_ref"),
    "SUGAR_L": ({"SUGAR_left": 200}, "v2_ref"),
    "SUGAR_R": ({"SUGAR_right": 200}, "v2_ref"),
    "BITTER": ({"BITTER_left": 200, "BITTER_right": 200}, "v2_ref"),
    "SUGAR_BITTER": ({"SUGAR_left": 200, "SUGAR_right": 200, "BITTER_left": 200, "BITTER_right": 200}, "v2_ref"),
    "JO_L": ({"JO_left": 200}, "v2_ref"),
    "LC16_LR": ({"LC16_left": 150, "LC16_right": 150}, "v2_ref"),
    "FRONT_LOOM": ({"LC4_left": 100, "LC4_right": 100, "LPLC2_left": 100, "LPLC2_right": 100}, "v2_ref"),
}


class SubcircuitV2(v1.Subcircuit):
    def __init__(self, ann, fids, fid2i, con, wmin, K):
        n = len(fids)
        def idx(types, side):
            m = ann.cell_type.isin(types) & (ann.side == side)
            return sorted(fid2i[int(r)] for r in ann.index[m] if int(r) in fid2i)
        self.groups_full = {}
        for g, types in {**INPUT_TYPES, **TARGET_TYPES}.items():
            for side in SIDES:
                self.groups_full[f"{g}_{side}"] = idx(types, side)
        S = sorted({i for g in INPUT_TYPES for s in SIDES for i in self.groups_full[f"{g}_{s}"]})
        T = sorted({i for g in TARGET_TYPES for s in SIDES for i in self.groups_full[f"{g}_{s}"]})
        pre, post = con.Presynaptic_Index.to_numpy(), con.Postsynaptic_Index.to_numpy()
        strong = con.Connectivity.to_numpy() >= wmin
        A = sp.csr_matrix((np.ones(strong.sum(), np.float32), (pre[strong], post[strong])), shape=(n, n))
        dS, dT = v1.bfs_hops(A, S), v1.bfs_hops(A.T.tocsr(), T)
        sel = np.union1d(np.where(dS + dT <= K)[0], np.array(S + T))
        self.sel = sel
        loc = np.full(n, -1); loc[sel] = np.arange(len(sel))
        e = (loc[pre] >= 0) & (loc[post] >= 0)
        self.pre, self.post = loc[pre[e]], loc[post[e]]
        self.w = con["Excitatory x Connectivity"].to_numpy()[e].astype(np.float32) * v1.P["w_syn"]
        order = np.argsort(self.pre, kind="stable")
        self.pre, self.post, self.w = self.pre[order], self.post[order], self.w[order]
        self.indptr = np.searchsorted(self.pre, np.arange(len(sel) + 1)).astype(np.int32)
        self.n = len(sel)
        self.groups = {k: loc[v].tolist() for k, v in self.groups_full.items()}
        self.fids = fids[sel]
        self.hops_in, self.hops_out = dS[sel], dT[sel]
        self.wmin, self.K = wmin, K

    def simulate_groups(self, rates, t_run_s, trials=4, seed=0):
        """rates: {组名: Hz}；复用 v1 的数值方案（把组名临时包装成 v1 期望的 (type, side) 键）。"""
        wrapped = {}
        for gname, hz in rates.items():
            base, side = gname.rsplit("_", 1)
            self.groups[f"{base}_{side}"] = self.groups[gname]
            wrapped[(base, side)] = hz
        saved = v1.TARGETS
        v1.TARGETS = [(t, s) for t in TARGET_TYPES for s in SIDES]
        try:
            out, total, rate = self.simulate(wrapped, t_run_s, trials=trials, seed=seed)
        finally:
            v1.TARGETS = saved
        return out, total, rate


def load_ann_groups():
    ann = pd.read_csv(v1.PATH_ANN, sep="\t", low_memory=False, usecols=["root_id", "cell_type", "side", "super_class"])
    return ann.drop_duplicates("root_id").set_index("root_id")


def full_ref(ann, name, folder):
    df = pd.read_csv(ROOT / "results" / folder / name / "rates.csv", index_col=0)
    col = [c for c in df.columns if c.startswith("baseline")][0]
    return {f"{g}_{s}": float(df[col].reindex(ann.index[ann.cell_type.isin(types) & (ann.side == s)]).fillna(0).mean())
            for g, types in TARGET_TYPES.items() for s in SIDES}


def cmd_compare(a):
    ann = load_ann_groups()
    comp = pd.read_csv(v1.PATH_COMP, index_col=0)
    fids = comp.index.to_numpy(np.int64); fid2i = {int(f): i for i, f in enumerate(fids)}
    con = pd.read_parquet(v1.PATH_CON, columns=["Presynaptic_Index", "Postsynaptic_Index", "Connectivity", "Excitatory x Connectivity"])
    refs = {k: full_ref(ann, k, f) for k, (_, f) in REFS.items()}
    rows = []
    for wmin, K in [(5, 3), (3, 3), (5, 4)]:
        t0 = time.time(); sc = SubcircuitV2(ann, fids, fid2i, con, wmin, K)
        print(f"\n### wmin={wmin} K={K}: {sc.n} 神经元, {len(sc.w)} 连接 ({time.time() - t0:.1f}s)", flush=True)
        for name, (rates, _) in REFS.items():
            t0 = time.time(); sub, tot, _ = sc.simulate_groups(rates, 0.5, trials=4, seed=1)
            ref = refs[name]
            keys = [k for k in ref if (ref[k] > 1 or sub[k] > 1)]
            mae = float(np.mean([abs(sub[k] - ref[k]) for k in ref]))
            sign_ok = all((sub[k] > 5) == (ref[k] > 5) for k in ref)
            rows.append(dict(wmin=wmin, K=K, n=sc.n, cond=name, mae_hz=mae, pattern_match=sign_ok,
                             **{f"sub_{k}": v for k, v in sub.items()}, **{f"ref_{k}": v for k, v in ref.items()}))
            short = lambda k: k.replace("_left", "L").replace("_right", "R")
            print(f"  {name:13s} {'✓' if sign_ok else '✗'} MAE {mae:5.1f} | " + "  ".join(f"{short(k)} {ref[k]:.0f}→{sub[k]:.0f}" for k in keys) + f"  ({time.time() - t0:.0f}s)", flush=True)
    out = ROOT / "results/dodge_ref/subcircuit_v2_vs_fullbrain.csv"
    pd.DataFrame(rows).to_csv(out, index=False); print("\n写入", out)


def cmd_export(a):
    ann = load_ann_groups()
    comp = pd.read_csv(v1.PATH_COMP, index_col=0)
    fids = comp.index.to_numpy(np.int64); fid2i = {int(f): i for i, f in enumerate(fids)}
    con = pd.read_parquet(v1.PATH_CON, columns=["Presynaptic_Index", "Postsynaptic_Index", "Connectivity", "Excitatory x Connectivity"])
    sc = SubcircuitV2(ann, fids, fid2i, con, a.wmin, a.K)
    meta = ann.reindex(sc.fids)
    cmp_path = ROOT / "results/dodge_ref/subcircuit_v2_vs_fullbrain.csv"
    validation = pd.read_csv(cmp_path).query("wmin == @a.wmin and K == @a.K").to_dict("records") if cmp_path.exists() else []
    payload = dict(
        meta=dict(wmin=a.wmin, K=a.K, n=sc.n, n_edges=len(sc.w), params=v1.P, version=2,
                  inputs=INPUT_TYPES, targets=TARGET_TYPES,
                  source="FlyWire v783 (eonsystemspbc/fly-brain data) + flyconnectome/flywire_annotations"),
        groups=sc.groups, fids=[str(f) for f in sc.fids], types=meta.cell_type.fillna("?").tolist(),
        sides=meta.side.fillna("?").tolist(), supers=meta.super_class.fillna("?").tolist(),
        hops_in=[int(h) if np.isfinite(h) else -1 for h in sc.hops_in],
        hops_out=[int(h) if np.isfinite(h) else -1 for h in sc.hops_out],
        indptr=v1.b64(sc.indptr.astype(np.int32)), post=v1.b64(sc.post.astype(np.int32)), w=v1.b64(sc.w.astype(np.float32)),
        validation=validation)
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"写入 {out}（{out.stat().st_size / 1e6:.2f} MB）：{sc.n} 神经元，{len(sc.w)} 连接")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("compare")
    e = sub.add_parser("export"); e.add_argument("--wmin", type=int, default=5); e.add_argument("--K", type=int, default=3)
    e.add_argument("--out", default=str(ROOT / "results/dodge/subcircuit_v2.json"))
    a = ap.parse_args()
    {"compare": cmd_compare, "export": cmd_export}[a.cmd](a)
