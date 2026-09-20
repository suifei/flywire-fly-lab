"""子回路 v4：把**听觉、嗅觉、内感受（饥渴）**也接成输入——五感补全。

起因（2026-09-20 用户的目标）：「激活果蝇的五感，让它自己生活」。原则不变：我们只提供物理量，不写判断逻辑。
`dodge/sensor_reach_v4.py` 先在全脑上查了通路（≥3 个突触的边）：
  听觉（江氏器的听觉神经元 387 个）→ 巨纤维 DNp01 **1 跳**、转向 DNa01/02 2 跳
  嗅觉（ORN）→ 巨纤维 2 跳、伸喙 MN9 3 跳；还直接接到 DNb05 / DNp32 / DNc01 几类下行神经元
  内感受 ISN（4 个，文献里感知饥渴）→ 梳理 2 跳、伸喙 3 跳
都在 K=3 的裁剪范围内，所以值得裁进来。**选择规则、wmin/K、模型全部沿用 v2/v3**，只是输入变多。

新增输入组：
  AUDIO_*  cell_sub_class = auditory        听觉
  OLFA_*   cell_type = ORN_DM1              嗅觉 · 醋（Or42b，文献里的吸引性气味）
  OLFR_*   cell_type = ORN_DA2              嗅觉 · 土臭素（Or56a，文献里的厌恶性气味）
  ISN_*    cell_type = ISN                  内感受（饥渴）
只取两个嗅小球而不是全部 1,850 个 ORN：全取的话子回路会把整个触角叶 / 蘑菇体卷进来，页面跑不动；
而且全脑里 ORN 稍强就引发约 8,000 个神经元的失控（report §11），子回路本来也复现不了那种副作用。
"吸引 / 厌恶"是**文献给这两个小球的标签，不是我们写进模型的规则**——模型里它们只是两组被驱动的神经元，往哪转由连接组决定。

用法：cd dodge && python subcircuit_v4.py compare && python subcircuit_v4.py export
输出 results/dodge/subcircuit_v4.json、results/dodge_ref/subcircuit_v4_vs_v3.csv
"""
import argparse, json, time
from pathlib import Path
import numpy as np, pandas as pd
import subcircuit as v1, subcircuit_v2 as v2, subcircuit_v3 as v3

ROOT = Path(__file__).resolve().parent.parent
NEW_TYPES = {"OLFA": ["ORN_DM1"], "OLFR": ["ORN_DA2"], "ISN": ["ISN"]}
NEW_SUBCLASS = {"AUDIO": ["auditory"]}


class SubcircuitV4(v3.SubcircuitV3):
    def __init__(self, ann, fids, fid2i, con, wmin, K):
        old_t, old_s = dict(v2.INPUT_TYPES), dict(v3.SUBCLASS_INPUTS)
        v2.INPUT_TYPES.update(NEW_TYPES); v3.SUBCLASS_INPUTS.update(NEW_SUBCLASS)
        try: super().__init__(ann, fids, fid2i, con, wmin, K)
        finally:
            v2.INPUT_TYPES.clear(); v2.INPUT_TYPES.update(old_t); v3.SUBCLASS_INPUTS.clear(); v3.SUBCLASS_INPUTS.update(old_s)


def load():
    ann = v3.load_ann(); comp = pd.read_csv(v1.PATH_COMP, index_col=0)
    fids = comp.index.to_numpy(np.int64); fid2i = {int(f): i for i, f in enumerate(fids)}
    con = pd.read_parquet(v1.PATH_CON, columns=["Presynaptic_Index", "Postsynaptic_Index", "Connectivity", "Excitatory x Connectivity"])
    return ann, fids, fid2i, con


def cmd_compare(a):
    ann, fids, fid2i, con = load(); refs = {k: v2.full_ref(ann, k, f) for k, (_, f) in v2.REFS.items()}; rows = []
    for cls, tag in ((v3.SubcircuitV3, "v3"), (SubcircuitV4, "v4")):
        t0 = time.time(); sc = cls(ann, fids, fid2i, con, a.wmin, a.K)
        print(f"\n### {tag}  wmin={a.wmin} K={a.K}: {sc.n} 神经元, {len(sc.w)} 连接 ({time.time() - t0:.1f}s)", flush=True)
        for name, (rates, _) in v2.REFS.items():
            sub, tot, _ = sc.simulate_groups(rates, 0.5, trials=4, seed=1); ref = refs[name]
            mae = float(np.mean([abs(sub[k] - ref[k]) for k in ref])); sign_ok = all((sub[k] > 5) == (ref[k] > 5) for k in ref)
            rows.append(dict(which=tag, n=sc.n, cond=name, mae_hz=round(mae, 2), pattern_match=bool(sign_ok), **{f"sub_{k}": round(v, 2) for k, v in sub.items()}))
            print(f"  {name:13s} {'✓' if sign_ok else '✗'} MAE {mae:5.1f}", flush=True)
    df = pd.DataFrame(rows); out = ROOT / "results/dodge_ref/subcircuit_v4_vs_v3.csv"; df.to_csv(out, index=False)
    for tag in ("v3", "v4"):
        d = df[df.which == tag]; print(f"\n{tag}：模式一致 {int(d.pattern_match.sum())}/{len(d)} 个条件，平均 MAE {d.mae_hz.mean():.2f} Hz")
    print("写入", out)


def cmd_export(a):
    ann, fids, fid2i, con = load(); t0 = time.time()
    sc = SubcircuitV4(ann, fids, fid2i, con, a.wmin, a.K)
    print(f"wmin={a.wmin} K={a.K}：{sc.n:,} 个神经元、{len(sc.pre):,} 条边（v3 同参数是 5,563 / 432,437），{time.time() - t0:.0f}s")
    for g in sc.input_names: print(f"  {g:8s} 左 {len(sc.groups[g + '_left']):5d}  右 {len(sc.groups[g + '_right']):5d}")
    # 有 17 个神经元既属于 JO（风/重力/梳理那几类）又被注释成 auditory。一个神经元只能有一个驱动频率，
    # 所以把它们留在原来的 JO 组（已发布的梳理数字都建立在那个分组上），从 AUDIO 里剔掉。
    for side in v2.SIDES:
        jo = set(sc.groups[f"JO_{side}"]); before = len(sc.groups[f"AUDIO_{side}"])
        sc.groups[f"AUDIO_{side}"] = [i for i in sc.groups[f"AUDIO_{side}"] if i not in jo]
        print(f"  AUDIO_{side}: {before} → {len(sc.groups[f'AUDIO_{side}'])}（剔掉与 JO 重叠的）")
    validation = []; cmp_path = ROOT / "results/dodge_ref/subcircuit_v4_vs_v3.csv"
    if cmp_path.exists():
        dv = pd.read_csv(cmp_path).query("which == 'v4'"); refs = {k: v2.full_ref(ann, k, f) for k, (_, f) in v2.REFS.items()}
        for r in dv.to_dict("records"):
            row = {k: v for k, v in r.items() if k in ("cond", "mae_hz", "pattern_match") or k.startswith("sub_")}
            row.update({f"ref_{k}": round(v, 2) for k, v in refs[r["cond"]].items()}); validation.append(row)
    meta = ann.reindex([int(f) for f in sc.fids])
    inputs = {g: (NEW_SUBCLASS.get(g) or NEW_TYPES.get(g) or v3.SUBCLASS_INPUTS.get(g) or v3.CLASS_INPUTS.get(g) or v2.INPUT_TYPES[g]) for g in sc.input_names}
    out = dict(meta=dict(wmin=a.wmin, K=a.K, n=int(sc.n), n_edges=int(len(sc.pre)), version=4, params=v1.P, inputs=inputs, targets=v2.TARGET_TYPES,
                         note="v4 在 v3 基础上加了 AUDIO（听觉）/ OLFA（嗅觉·醋 DM1）/ OLFR（嗅觉·土臭素 DA2）/ ISN（内感受）四路输入；选择规则与 v2/v3 完全相同",
                         source="FlyWire v783 + flywire_annotations"),
               groups=sc.groups, fids=[str(f) for f in sc.fids], types=meta.cell_type.fillna("?").tolist(), sides=meta.side.fillna("?").tolist(),
               supers=meta.super_class.fillna("?").tolist(),
               hops_in=[int(h) if np.isfinite(h) else -1 for h in sc.hops_in], hops_out=[int(h) if np.isfinite(h) else -1 for h in sc.hops_out],
               indptr=v1.b64(sc.indptr.astype(np.int32)), post=v1.b64(sc.post.astype(np.int32)), w=v1.b64(sc.w.astype(np.float32)), validation=validation)
    p = ROOT / "results/dodge/subcircuit_v4.json"; p.write_text(json.dumps(out, separators=(",", ":")))
    print(f"→ {p}  {p.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    for nm in ("export", "compare"): e = sub.add_parser(nm); e.add_argument("--wmin", type=int, default=3); e.add_argument("--K", type=int, default=3)
    a = ap.parse_args(); {"export": cmd_export, "compare": cmd_compare}[a.cmd](a)
