#!/usr/bin/env python3
"""把 flyvis 的果蝇视觉网络导出成浏览器能跑的 JSON。

为什么可行：flyvis 不是一张任意的大网，是**六边形卷积网络**——
45,669 个节点 = 65 种细胞类型 × 每类若干柱，1,513,231 条边却只有 604 种
(源类型→目标类型) 组合，每种是一个共享的卷积核（中位 2 个抽头，共 2,355 个）。
所以整个视觉系统的参数约 28 KB，能完整塞进网页实时跑。

**这个脚本会先验证"卷积"这个前提**：同一 (源类型,目标类型,du,dv) 的边，
权重必须在所有柱上一致。不一致就报错退出，不会悄悄导出一个错的近似。

动力学（flyvis PPNeuronIGRSynapses，欧拉积分）：
    dv/dt = 1/max(τ,dt) · ( −v + bias + Σ w·ReLU(v_源) + x_t )
    w = sign × syn_count × syn_strength

用法：conda activate fba && python vision/export_flyvis_js.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results/vision/flyvis_net.json"


def main():
    import flyvis
    import torch

    nv = flyvis.NetworkView("flow/0000/000")
    net = nv.init_network()
    c = net.connectome
    p = net._param_api()

    ntype = np.array([s.decode() for s in c.nodes.type[:]])
    nu = np.asarray(c.nodes.u[:]).astype(int)
    nv_ = np.asarray(c.nodes.v[:]).astype(int)
    bias = p["nodes"].bias.detach().cpu().numpy().astype(np.float64)
    tau = p["nodes"].time_const.detach().cpu().numpy().astype(np.float64)

    si = np.asarray(c.edges.source_index[:]).astype(int)
    ti = np.asarray(c.edges.target_index[:]).astype(int)
    stype = np.array([s.decode() for s in c.edges.source_type[:]])
    ttype = np.array([s.decode() for s in c.edges.target_type[:]])
    du = np.asarray(c.edges.du[:]).astype(int)
    dv = np.asarray(c.edges.dv[:]).astype(int)

    # 最终权重（dynamics.write_derived_params 的定义）
    e = p["edges"]
    w = (e.sign * e.syn_count * e.syn_strength).detach().cpu().numpy().astype(np.float64)

    types = sorted(set(ntype.tolist()))
    print(f"节点 {len(ntype):,}  类型 {len(types)}  边 {len(si):,}")

    # ── 前提①：bias / τ 按类型共享 ────────────────────────────
    bad = [t for t in types if bias[ntype == t].std() > 1e-9 or tau[ntype == t].std() > 1e-9]
    if bad:
        sys.exit(f"✗ 这些类型的 bias/τ 在柱之间不一致，不能按类型压缩：{bad[:5]}")
    print("✓ bias / 时间常数 按细胞类型共享")

    # ── 前提②：权重只依赖 (源类型,目标类型,du,dv) ──────────────
    key = np.stack([du, dv], 1)
    kern = {}
    viol = []
    for s in types:
        for t in types:
            m = (stype == s) & (ttype == t)
            if not m.any():
                continue
            taps = {}
            for (a, b), ww in zip(key[m], w[m]):
                taps.setdefault((int(a), int(b)), []).append(ww)
            row = []
            for (a, b), vals in sorted(taps.items()):
                arr = np.array(vals)
                rel = arr.std() / max(abs(arr.mean()), 1e-12)
                if rel > 1e-6:
                    viol.append((s, t, a, b, float(rel), len(arr)))
                row.append([a, b, float(arr.mean())])
            kern[f"{s}>{t}"] = row
    if viol:
        print(f"✗ {len(viol)} 个 (类型对,偏移) 的权重在柱之间不一致 —— **不是卷积**，导出中止")
        for v in viol[:6]:
            print(f"    {v[0]}→{v[1]} 偏移({v[2]},{v[3]}) 相对离散度 {v[4]:.2e}（{v[5]} 条边）")
        sys.exit(2)
    ntaps = sum(len(v) for v in kern.values())
    print(f"✓ 权重只依赖 (源类型,目标类型,du,dv) —— 确认是卷积")
    print(f"  {len(kern)} 个核，共 {ntaps} 个抽头")

    # ── 每类占据哪些柱（不是所有类型都铺满 721 个）────────────
    cols, nodes_of = {}, {}
    for t in types:
        m = ntype == t
        uv = np.stack([nu[m], nv_[m]], 1)
        order = np.lexsort((uv[:, 1], uv[:, 0]))       # 固定顺序，JS 要能复现
        cols[t] = uv[order].tolist()
        nodes_of[t] = np.where(m)[0][order].tolist()

    sizes = {t: len(v) for t, v in cols.items()}
    full = [t for t, n in sizes.items() if n == 721]
    print(f"  铺满 721 柱的类型 {len(full)}/{len(types)}；其余最小 {min(sizes.values())} 柱")

    # 63/65 个类型共用同一套 721 柱格子 —— 存一份，其余只记例外，
    # 资产从 412 KB 降到 ~40 KB（浏览器要下载，值得省）。
    from collections import Counter
    canon = Counter(tuple(map(tuple, v)) for v in cols.values()).most_common(1)[0][0]
    lattice = [list(x) for x in canon]
    exc = {t: v for t, v in cols.items() if tuple(map(tuple, v)) != canon}
    print(f"  柱格子去重：主格子 {len(lattice)} 柱，例外 {len(exc)} 个类型"
          f"（{', '.join(f'{t}:{len(v)}' for t, v in exc.items())}）")

    doc = dict(
        source="flyvis flow/0000/000 (pretrained, connectome-constrained)",
        equation="dv/dt = 1/max(tau,dt) * (-v + bias + sum_in w*relu(v_src) + x_t); w=sign*syn_count*syn_strength; Euler",
        activation="relu",
        types=types,
        bias={t: float(bias[ntype == t][0]) for t in types},
        tau={t: float(tau[ntype == t][0]) for t in types},
        lattice=lattice,             # 主格子 [[u,v], ...]，绝大多数类型用它
        columns_exc=exc,             # 例外类型 -> [[u,v], ...]
        kernels=kern,                # "源>目标" -> [[du,dv,w], ...]
        input_types=[t for t in types if t.startswith("R") and t[1:].isdigit()],
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, separators=(",", ":")))
    kb = OUT.stat().st_size / 1024
    print(f"\n写入 {OUT}  {kb:.1f} KB")

    print("\n下一步：python vision/flyvis_parity.py 生成 JS 比对用的参考输出")


if __name__ == "__main__":
    main()
