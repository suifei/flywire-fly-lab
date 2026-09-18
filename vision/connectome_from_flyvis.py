#!/usr/bin/env python
"""
第 2 步 B：flyvis 柱状细胞活动 → FlyWire 全脑 LIF（138,639 神经元）→ LPLC2 / LC4 / 巨纤维 / DNa。

映射（都是手写/推测，逐项声明）：
  * 类型：flyvis 与 FlyWire 同名的柱状细胞（T4a–d、T5a–d、T1、T2、T2a、T3、Tm1–4、Tm9、Tm20、Mi1/4/9、L1–5、C2、C3、R7、R8）；
    FlyWire 神经元的柱坐标来自 Codex column_assignment（Matsliah et al. 2024，v783）。TmY3 等无柱坐标的类型不注入。
  * 眼 → 侧：左眼 → 左侧光学叶（柱状通路不跨中线）。
  * 空间：两套六边形格子换算成笛卡尔坐标后，按中心 + 主轴 + 各轴标准差对齐，再取最近的 flyvis 柱。
    主轴的交换与正负号共 8 种朝向，没有文献依据确定哪一种正确 → 全部运行、全部报告。
  * 活动 → 频率：扣除基线期（刺激前 150–20 ms）均值后半波整流；每种细胞用全部刺激合起来的 99.5 百分位做同一个归一化尺度，
    乘 150 Hz、封顶 200 Hz。逼近与平移刺激共用同一尺度，不偏向任何一方。
  * LIF 模型与注入方式与 run_experiment.py 相同（Shiu et al. 参数；Poisson 事件 v += 68.75 mV，被注入神经元不应期 0）。

注意：脚本没有调用 b2.seed()，所以 standalone 每次 device.run 由系统随机源播种，40 次运行的泊松噪声互相独立
（不同于 run_experiment.py 曾经的问题，见 report.md 14.0 节）。但每个条件默认只跑 1 次，没有重复；用 --repeats N 可以对每个条件重复 N 次，
用来估计运行间的变异（结果写 connectome_responses_reps.csv，rates_*.npz 仍只存第 1 次）。
用法（brain-fly-cpu 环境）：python vision/connectome_from_flyvis.py [--repeats N]
输出：results/vision/connectome_responses.csv（每个刺激 × 朝向的汇总）与 results/vision/rates_<stim>_o<k>.npz（20 ms 发放率曲线）
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT / "external" / "fly-brain"
sys.path.insert(0, str(REPO / "code" / "paper-phil-drosophila"))
VIS = ROOT / "results" / "vision"
REPEATS = 1          # --repeats N：每个条件重复 N 次（估计运行间变异）
STIMS = ["loom_L", "loom_R", "recede_L", "translate_near_L", "translate_far_L"]
TYPES = ["T4a", "T4b", "T4c", "T4d", "T5a", "T5b", "T5c", "T5d", "T2", "T2a", "T3", "T1",
         "Tm1", "Tm2", "Tm3", "Tm4", "Tm9", "Tm20", "Mi1", "Mi4", "Mi9",
         "L1", "L2", "L3", "L4", "L5", "C2", "C3", "R7", "R8"]
READ = [("LPLC2", "left"), ("LPLC2", "right"), ("LC4", "left"), ("LC4", "right"),
        ("DNp01", "left"), ("DNp01", "right"), ("DNa01", "left"), ("DNa01", "right"), ("DNa02", "left"), ("DNa02", "right")]


def cart(a, b):
    return np.c_[a + b / 2.0, b * np.sqrt(3) / 2.0]


def normalize(P):
    """中心化 + 主轴旋转 + 各轴除以标准差；主轴符号固定为“最大分量为正”。"""
    Pc = P - P.mean(0)
    w, V = np.linalg.eigh(np.cov(Pc.T))
    V = V[:, ::-1]
    V *= np.sign(V[np.abs(V).argmax(0), range(2)])
    Z = Pc @ V
    return Z / Z.std(0)


ORIENTS = [(swap, sx, sy) for swap in (False, True) for sx in (1, -1) for sy in (1, -1)]
# 第 9 种：**解剖锚定**（k=8）。前 8 种都建立在 normalize() 的 PCA + 各轴除以标准差之上，
# 而那一步会把六边形点阵拉变形 —— 实测 Codex 的 +p/+q 基矢夹角从 60.0° 变成 122.6°
# （报告 §28.20），映射到的已经不是同一种点阵，符号怎么翻都救不回来。
# 这一种改用**保持点阵几何**的变换 u = −p, v = −q：方向由解剖锚点定
# （vision/lattice_anchor.py：+p 在解剖 113°、+q 在 171°；flyvis 的 −u 在 97°、−v 在 157°），
# 不做 PCA、不做各向异性缩放，超出 flyvis 半径 15 的柱夹到最近的点阵柱。
# 两种变体用来把「锚定有没有用」和「夹边缘有没有害」分开：
#   anchor1.0：u=−p, v=−q 原尺度，中心 62% 精确落到格点，外围 38% 被夹到六边形边缘
#   anchor0.6：整体缩放 0.6（各向同性，**不改基矢角**），只剩 5.8% 被夹，
#              代价是 785 个真实柱挤进 282 个 flyvis 柱（采样变粗，不是几何变形）
ORIENTS = ORIENTS + [("anchor", 1.0, 0), ("anchor", 0.6, 0)]


def build_inputs(fids_model):
    ca = pd.read_csv(ROOT / "external/codex_783/column_assignment.csv.gz")
    ca = ca[ca.type.isin(TYPES) & ca.root_id.isin(fids_model)].reset_index(drop=True)
    fv = np.load(VIS / f"flyvis_{STIMS[0]}.npz")
    uv = cart(fv["u_T4a"].astype(float), fv["v_T4a"].astype(float))   # flyvis 各类型共用同一套柱坐标
    uv_std = uv.std(0).mean()
    tree = cKDTree(uv)
    col_idx = {}  # (orient, side) -> 该侧每个柱（column_id）对应的 flyvis 柱序号
    for side in ("left", "right"):
        cols = ca[ca.hemisphere == side].drop_duplicates("column_id")
        Z = normalize(cart(cols.p.to_numpy(float), cols.q.to_numpy(float)))
        for k, (swap, sx, sy) in enumerate(ORIENTS):
            if swap == "anchor":
                # 保持点阵几何：(p,q) 中心化后取 u=−p, v=−q，按 sx 各向同性缩放（不改基矢角）
                pp = cols.p.to_numpy(float) - np.median(cols.p.to_numpy(float))
                qq = cols.q.to_numpy(float) - np.median(cols.q.to_numpy(float))
                Zo = cart(-pp, -qq) * sx
            else:
                Zo = Z[:, ::-1] if swap else Z
                Zo = Zo * [sx, sy] * uv_std
            _, idx = tree.query(Zo)
            col_idx[(k, side)] = dict(zip(cols.column_id, idx))
    # flyvis 的柱序号 → 各类型数组里的位置（各类型节点顺序一致时为恒等；逐类型核对）
    for t in TYPES:
        assert np.array_equal(fv[f"u_{t}"], fv["u_T4a"]) and np.array_equal(fv[f"v_{t}"], fv["v_T4a"]), t
    return ca, col_idx


def rates_for(ca, col_idx, orient, acts, t, scales):
    """返回 (n_bins, n_inputs) 的频率矩阵（Hz）。"""
    base_mask = (t >= -0.15) & (t <= -0.02)
    R = np.zeros((len(t), len(ca)), np.float64)
    for (ty, side), g in ca.groupby(["type", "hemisphere"]):
        eye = 0 if side == "left" else 1
        a = acts[ty][:, eye, :].astype(np.float32)                    # (bins, 721)
        r = np.maximum(0.0, a - a[base_mask].mean(0))
        idx = np.array([col_idx[(orient, side)][c] for c in g.column_id])
        R[:, g.index.to_numpy()] = np.minimum(200.0, 150.0 * r[:, idx] / scales[ty])
    return R


def main():
    import brian2 as b2
    from brian2 import ms, mV, Hz, Network, PoissonGroup, Synapses, SpikeMonitor, TimedArray
    from model import create_model, default_params

    comp = pd.read_csv(REPO / "data/2025_Completeness_783.csv", index_col=0)
    fids = comp.index.to_numpy(np.int64); fid2i = {int(f): i for i, f in enumerate(fids)}
    ann = pd.read_csv(ROOT / "external/flywire_annotations/Supplemental_file1_neuron_annotations.tsv", sep="\t",
                      low_memory=False, usecols=["root_id", "cell_type", "side"]).drop_duplicates("root_id")
    groups = {f"{t}_{s}": [fid2i[int(r)] for r in ann.root_id[(ann.cell_type == t) & (ann.side == s)] if int(r) in fid2i] for t, s in READ}
    ca, col_idx = build_inputs(set(fids.tolist()))
    inj_idx = np.array([fid2i[int(r)] for r in ca.root_id])
    print(f"注入神经元 {len(ca)} 个（{ca.type.nunique()} 种类型，左 {int((ca.hemisphere == 'left').sum())} / 右 {int((ca.hemisphere == 'right').sum())}）", flush=True)

    data = {s: np.load(VIS / f"flyvis_{s}.npz") for s in STIMS}
    t = data[STIMS[0]]["t"]; dt_bin = float(np.median(np.diff(t)))
    acts = {s: {ty: data[s][f"act_{ty}"] for ty in TYPES} for s in STIMS}
    scales = {}
    for ty in TYPES:
        vals = []
        for s in STIMS:
            a = acts[s][ty].astype(np.float32); bm = (t >= -0.15) & (t <= -0.02)
            vals.append(np.maximum(0, a[t >= 0] - a[bm].mean(0)).ravel())
        scales[ty] = max(float(np.percentile(np.concatenate(vals), 99.5)), 1e-6)

    # —— 建网络一次（standalone），之后每个刺激×朝向只替换 TimedArray 数值 ——
    build_dir = ROOT / "results/vision/.brian2_build"
    b2.set_device("cpp_standalone", build_on_run=False, directory=str(build_dir))
    b2.prefs.devices.cpp_standalone.openmp_threads = 0
    b2.prefs.devices.cpp_standalone.extra_make_args_unix = ["-j4"]
    b2.defaultclock.dt = 0.1 * ms
    params = dict(default_params)
    neu, syn, _ = create_model(str(REPO / "data/2025_Completeness_783.csv"), str(REPO / "data/2025_Connectivity_783.parquet"), params)
    ta = TimedArray(np.zeros((len(t), len(ca))) * Hz, dt=dt_bin * 1000 * ms)
    pg = PoissonGroup(len(ca), rates="ta(t, i)")
    ps = Synapses(pg, neu, on_pre=f"v += {float(params['w_syn'] * params['f_poi'] / mV)}*mV")
    ps.connect(i=np.arange(len(ca)), j=inj_idx)
    rfc = np.full(len(neu), float(params["t_rfc"] / ms)); rfc[inj_idx] = 0.0
    neu.rfc = rfc * ms
    rec = sorted({i for v in groups.values() for i in v})
    mon = SpikeMonitor(neu, record=rec)
    net = Network(neu, syn, pg, ps, mon)
    b2.device.apply_run_args()
    T_run = len(t) * dt_bin
    net.run(T_run * 1000 * ms)
    t0 = time.time()
    b2.device.build(directory=str(build_dir), compile=True, run=False, clean=True)
    print(f"编译完成 {time.time() - t0:.0f}s；仿真时长 {T_run:.2f} s（含 {-t[0] + dt_bin / 2:.2f} s 基线期）", flush=True)

    rows = []
    edges = np.arange(0, T_run + 1e-9, 0.02)
    for s in STIMS:
        for k in range(len(ORIENTS)):
            R = rates_for(ca, col_idx, k, acts[s], t, scales)
            for rep in range(REPEATS):
                t1 = time.time()
                b2.device.run(directory=str(build_dir), with_output=False, run_args={ta: R * Hz})
                st, si = np.asarray(mon.t / b2.second), np.asarray(mon.i[:])
                curves = {}
                row = dict(stim=s, orient=k, rep=rep, swap=str(ORIENTS[k][0]), sx=ORIENTS[k][1], sy=ORIENTS[k][2],
                           input_hz_mean=float(R[t >= 0].mean()), run_s=round(time.time() - t1, 1))
                for g, idx in groups.items():
                    m = np.isin(si, idx)
                    h, _ = np.histogram(st[m], bins=edges)
                    curves[g] = h / (0.02 * len(idx))
                    ts = edges[:-1] - (-t[0] + dt_bin / 2)                 # 以刺激开始为 0
                    late = (ts >= 0.5) & (ts < 0.95)
                    row[f"{g}_late_hz"] = float(curves[g][late].mean())
                    row[f"{g}_peak_hz"] = float(curves[g][ts >= 0].max())
                if rep == 0:
                    np.savez_compressed(VIS / f"rates_{s}_o{k}.npz", t=edges[:-1] - (-t[0] + dt_bin / 2), **curves)
                rows.append(row)
                print(f"{s:17s} 朝向{k} 第{rep + 1}次 输入均值 {row['input_hz_mean']:5.1f} Hz | LPLC2 L/R 后段 {row['LPLC2_left_late_hz']:6.1f}/{row['LPLC2_right_late_hz']:6.1f}"
                      f" | LC4 L/R {row['LC4_left_late_hz']:6.1f}/{row['LC4_right_late_hz']:6.1f} | GF L/R {row['DNp01_left_late_hz']:6.1f}/{row['DNp01_right_late_hz']:6.1f} ({row['run_s']}s)", flush=True)
    out_csv = VIS / ("connectome_responses.csv" if REPEATS == 1 else "connectome_responses_reps.csv")
    pd.DataFrame(rows).to_csv(out_csv, index=False)
    print("写入", out_csv)


if __name__ == "__main__":
    _ap = argparse.ArgumentParser(); _ap.add_argument("--repeats", type=int, default=1)
    REPEATS = _ap.parse_args().repeats
    main()
