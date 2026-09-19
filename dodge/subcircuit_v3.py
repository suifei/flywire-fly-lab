"""子回路 v3：把**触感、温度、湿度**也接成输入。

起因（2026-09-19 用户提出的原则）：「果蝇看到的任何物体都该由它大脑自行决策，
我们绝不写死判断逻辑，只负责提供必需的物理量」。

按这条原则做的第一次尝试失败了：给「触角碰到围栏 → JO」之后果蝇**完全没反应**
（贴墙率 85.6% → 85.6%），因为 JO 在 v2 子回路里只通到梳理指令 aDN1。

`dodge/sensor_reach.py` 随后在**全脑**上查清了原因与出路：脑连接组里有
**头部刚毛 305 个（真正的触觉感受器）、温度 29 个、湿度 74 个**，
而且它们到 DNa01/DNa02/DNp01/MDN **只要 2–3 跳**——通路是有的，
只是 v2 裁子回路时没把它们当输入，于是物理量送进去没有落点。

v3 就是把这三类加进输入组重裁一版。**选择规则、wmin/K、模型全部沿用 v2**，只是输入变多。

新增输入组（按注释表的 cell_sub_class / cell_class 选，不是 cell_type）：
  TOUCH_*   head bristle      头部刚毛机械感觉 —— 真正的「碰到东西」
  THERMO_*  thermosensory     温度
  HYGRO_*   hygrosensory      湿度

用法（brain-fly-cpu 或 flygym）：python dodge/subcircuit_v3.py export --wmin 3 --K 3
输出 results/dodge/subcircuit_v3.json
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

import subcircuit as v1
import subcircuit_v2 as v2

ROOT = Path(__file__).resolve().parent.parent
# 新增的三类：按 cell_sub_class（触感）与 cell_class（温湿度）选
SUBCLASS_INPUTS = {"TOUCH": ["head bristle"]}
CLASS_INPUTS = {"THERMO": ["thermosensory"], "HYGRO": ["hygrosensory"]}


def load_ann():
    ann = pd.read_csv(v1.PATH_ANN, sep="\t", low_memory=False,
                      usecols=["root_id", "cell_type", "cell_sub_class", "cell_class", "side", "super_class"])
    return ann.drop_duplicates("root_id").set_index("root_id")


class SubcircuitV3(v2.SubcircuitV2):
    def __init__(self, ann, fids, fid2i, con, wmin, K):
        n = len(fids)
        def pick(mask, side):
            m = mask & (ann.side == side)
            return sorted(fid2i[int(r)] for r in ann.index[m] if int(r) in fid2i)
        self.groups_full = {}
        for g, types in {**v2.INPUT_TYPES, **v2.TARGET_TYPES}.items():
            for side in v2.SIDES:
                self.groups_full[f"{g}_{side}"] = pick(ann.cell_type.isin(types), side)
        for g, subs in SUBCLASS_INPUTS.items():
            for side in v2.SIDES:
                self.groups_full[f"{g}_{side}"] = pick(ann.cell_sub_class.isin(subs), side)
        for g, cls in CLASS_INPUTS.items():
            for side in v2.SIDES:
                self.groups_full[f"{g}_{side}"] = pick(ann.cell_class.isin(cls), side)
        self.input_names = list(v2.INPUT_TYPES) + list(SUBCLASS_INPUTS) + list(CLASS_INPUTS)
        S = sorted({i for g in self.input_names for s in v2.SIDES for i in self.groups_full[f"{g}_{s}"]})
        T = sorted({i for g in v2.TARGET_TYPES for s in v2.SIDES for i in self.groups_full[f"{g}_{s}"]})
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


def cmd_compare(a):
    """与 v2 用同一批全脑参考实验对照——换了子回路就必须重新验一遍保真度，
    否则「页面切到 v3」等于悄悄换掉了所有已发布数字的底座。"""
    ann = load_ann()
    comp = pd.read_csv(v1.PATH_COMP, index_col=0)
    fids = comp.index.to_numpy(np.int64); fid2i = {int(f): i for i, f in enumerate(fids)}
    con = pd.read_parquet(v1.PATH_CON, columns=["Presynaptic_Index", "Postsynaptic_Index", "Connectivity", "Excitatory x Connectivity"])
    refs = {k: v2.full_ref(ann, k, f) for k, (_, f) in v2.REFS.items()}
    rows = []
    for cls, tag in ((v2.SubcircuitV2, "v2"), (SubcircuitV3, "v3")):
        t0 = time.time(); sc = cls(ann, fids, fid2i, con, a.wmin, a.K)
        print(f"\n### {tag}  wmin={a.wmin} K={a.K}: {sc.n} 神经元, {len(sc.w)} 连接 ({time.time() - t0:.1f}s)", flush=True)
        for name, (rates, _) in v2.REFS.items():
            sub, tot, _ = sc.simulate_groups(rates, 0.5, trials=4, seed=1)
            ref = refs[name]
            keys = [k for k in ref if (ref[k] > 1 or sub[k] > 1)]
            mae = float(np.mean([abs(sub[k] - ref[k]) for k in ref]))
            sign_ok = all((sub[k] > 5) == (ref[k] > 5) for k in ref)
            rows.append(dict(which=tag, n=sc.n, cond=name, mae_hz=round(mae, 2), pattern_match=bool(sign_ok),
                             **{f"sub_{k}": round(v, 2) for k, v in sub.items()}))
            short = lambda k: k.replace("_left", "L").replace("_right", "R")
            print(f"  {name:13s} {'✓' if sign_ok else '✗'} MAE {mae:5.1f} | " +
                  "  ".join(f"{short(k)} {ref[k]:.0f}→{sub[k]:.0f}" for k in keys), flush=True)
    df = pd.DataFrame(rows)
    out = ROOT / "results/dodge_ref/subcircuit_v3_vs_v2.csv"
    df.to_csv(out, index=False)
    for tag in ("v2", "v3"):
        d = df[df.which == tag]
        print(f"\n{tag}：模式一致 {int(d.pattern_match.sum())}/{len(d)} 个条件，平均 MAE {d.mae_hz.mean():.2f} Hz")
    print("写入", out)


def cmd_export(a):
    ann = load_ann()
    comp = pd.read_csv(v1.PATH_COMP, index_col=0)
    fids = comp.index.to_numpy(np.int64); fid2i = {int(f): i for i, f in enumerate(fids)}
    con = pd.read_parquet(v1.PATH_CON, columns=["Presynaptic_Index", "Postsynaptic_Index", "Connectivity", "Excitatory x Connectivity"])
    t0 = time.time()
    sc = SubcircuitV3(ann, fids, fid2i, con, a.wmin, a.K)
    print(f"wmin={a.wmin} K={a.K}：{sc.n:,} 个神经元、{len(sc.pre):,} 条边（v2 同参数是 4,599 / 338,837），{time.time() - t0:.0f}s")
    for g in sc.input_names:
        print(f"  {g:8s} 左 {len(sc.groups[g + '_left']):5d}  右 {len(sc.groups[g + '_right']):5d}")
    # validation：页面的「子回路 vs 全脑」那张图直接读它。v3 的对照数据由
    # `python dodge/subcircuit_v3.py compare` 写到 results/dodge_ref/subcircuit_v3_vs_v2.csv，
    # 这里把 v3 那几行取出来，字段名与 v2 保持一致（cond / mae_hz / sub_* / ref_*）。
    validation = []
    cmp_path = ROOT / "results/dodge_ref/subcircuit_v3_vs_v2.csv"
    if cmp_path.exists():
        dv = pd.read_csv(cmp_path).query("which == 'v3'")
        refs = {k: v2.full_ref(ann, k, f) for k, (_, f) in v2.REFS.items()}
        for r in dv.to_dict("records"):
            row = {k: v for k, v in r.items() if k in ("cond", "mae_hz", "pattern_match") or k.startswith("sub_")}
            row.update({f"ref_{k}": round(v, 2) for k, v in refs[r["cond"]].items()})
            validation.append(row)
    meta = ann.reindex([int(f) for f in sc.fids])
    out = dict(meta=dict(wmin=a.wmin, K=a.K, n=int(sc.n), n_edges=int(len(sc.pre)), version=3,
                         params=v1.P,
                         inputs={g: (SUBCLASS_INPUTS.get(g) or CLASS_INPUTS.get(g) or v2.INPUT_TYPES[g])
                                 for g in sc.input_names},
                         targets=v2.TARGET_TYPES,
                         note="v3 在 v2 基础上加了 TOUCH（头部刚毛）/ THERMO（温度）/ HYGRO（湿度）三路输入；"
                              "选择规则与 v2 完全相同",
                         source="FlyWire v783 + flywire_annotations"),
               groups=sc.groups, fids=[str(f) for f in sc.fids],
               types=meta.cell_type.fillna("?").tolist(), sides=meta.side.fillna("?").tolist(),
               supers=meta.super_class.fillna("?").tolist(),
               hops_in=[int(h) if np.isfinite(h) else -1 for h in sc.hops_in],
               hops_out=[int(h) if np.isfinite(h) else -1 for h in sc.hops_out],
               indptr=v1.b64(sc.indptr.astype(np.int32)), post=v1.b64(sc.post.astype(np.int32)),
               w=v1.b64(sc.w.astype(np.float32)), validation=validation)
    p = ROOT / "results/dodge/subcircuit_v3.json"
    p.write_text(json.dumps(out, separators=(",", ":")))
    print(f"→ {p}  {p.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export"); e.add_argument("--wmin", type=int, default=3); e.add_argument("--K", type=int, default=3)
    c = sub.add_parser("compare"); c.add_argument("--wmin", type=int, default=3); c.add_argument("--K", type=int, default=3)
    a = ap.parse_args()
    {"export": cmd_export, "compare": cmd_compare}[a.cmd](a)
