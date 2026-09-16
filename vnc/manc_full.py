#!/usr/bin/env python
"""
全腹神经索（MANC，23,532 个神经元，6 条腿）上的 Pugliese 2025 发放率模型。

作者代码（github.com/smpuglie/Pugliese_cpg_2025 @ faee4b0，无许可证，只 import 调用）用稠密矩阵；
全腹神经索稠密矩阵要约 9 GB，本机放不下。这里只把连接矩阵换成稀疏存储，方程、参数抽样、求解器都保持一致：
  τ·dr/dt = −r + max(0, r_max·tanh(a/r_max·(Wᵀ·r + I·[t ∈ 刺激窗] − θ)))
  Wᵀ 重加权：兴奋 × 0.03，抑制 × 0.03（作者 reweight_connectivity）
  τ、a、θ、r_max：作者 sample_trunc_normal 按同样的随机键顺序抽样，再用 set_sizes 按神经元大小缩放
  求解：diffrax Dopri5 + PIDController，保存 1 ms 分辨率（作者 run_single_simulation 的设置）
先在 T1 网络上与作者稠密版对比（parity），通过后才用于全腹神经索。

用法（vnc-sim 环境）：
  python vnc/manc_full.py build                   # feather 按列分块 → results/vnc/manc_full/W_csc.npz
  python vnc/manc_full.py bench                   # 稀疏乘法速度
  python vnc/manc_full.py parity                  # T1：稀疏版 vs 作者稠密版（DNg100_L 副本 0、1）
  python vnc/manc_full.py run --conds ...         # 全腹神经索条件（见 CONDITIONS）
  python vnc/manc_full.py gap                     # 第 2 项：巨纤维 → TTMn 电突触（见 GAP_*）
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parent.parent
PUG = ROOT / "external" / "Pugliese_cpg_2025"
OUT = ROOT / "results" / "vnc" / "manc_full"
sys.path.insert(0, str(PUG))

# 数据集：MANC_DATASET=20251006（默认，作者较早的全腹神经索矩阵）或 all（作者较新的全突触矩阵 W_20260522_allSynapses，23,628 个神经元）
import os  # noqa: E402
DATASET = os.environ.get("MANC_DATASET", "20251006")
if DATASET == "all":
    FULL_W = PUG / "data/manc full vnc data/W_20260522_allSynapses.npz"
    FULL_T = PUG / "data/manc full vnc data/wTable_20260522_allSynapses.feather"
    OUT = ROOT / "results" / "vnc" / "manc_all"
else:
    FULL_W = PUG / "data/manc full vnc data/W_20251006.feather"
    FULL_T = PUG / "data/manc full vnc data/wTable_20251006.feather"


def build_from_npz():
    """全突触矩阵是 23,628² 的稠密 float64（Fortran 顺序，4.5 GB）：从 zip 流里逐列读，每次只占一列内存。"""
    import zipfile
    wt = pd.read_feather(FULL_T)
    N = len(wt)
    data, indices, indptr = [], [], [0]
    t0 = time.time()
    with zipfile.ZipFile(FULL_W) as z, z.open("arr_0.npy") as f:
        np.lib.format.read_magic(f)
        shape, fortran, dtype = np.lib.format.read_array_header_1_0(f)
        assert shape == (N, N) and fortran and dtype == np.float64
        for j in range(N):
            c = np.frombuffer(f.read(N * 8), dtype=np.float64)
            nz = np.nonzero(c)[0]
            indices.append(nz.astype(np.int32)); data.append(c[nz].astype(np.float32)); indptr.append(indptr[-1] + len(nz))
    W = sp.csc_matrix((np.concatenate(data), np.concatenate(indices), np.array(indptr, dtype=np.int64)), shape=(N, N))
    return W, time.time() - t0


def cmd_build(a):
    import pyarrow as pa
    import pyarrow.ipc as ipc
    OUT.mkdir(parents=True, exist_ok=True)
    if str(FULL_W).endswith(".npz"):
        W, dt = build_from_npz()
        sp.save_npz(OUT / "W_csc.npz", W)
        meta = dict(n=W.shape[0], nnz=int(W.nnz), exc_nnz=int((W.data > 0).sum()), inh_nnz=int((W.data < 0).sum()),
                    abs_synapses=float(np.abs(W.data).sum()), build_s=round(dt, 1), source=str(FULL_W.name))
        (OUT / "W_meta.json").write_text(json.dumps(meta, indent=1))
        print(meta)
        return
    names = ipc.open_file(pa.memory_map(str(FULL_W))).schema.names
    wt = pd.read_feather(FULL_T)
    N = len(wt)
    assert names[:-1] == [str(b) for b in wt.bodyId] and names[-1] == "bodyId_pre"
    rows = ipc.open_file(pa.memory_map(str(FULL_W)), options=ipc.IpcReadOptions(included_fields=[N])).get_batch(0).column(0).to_numpy()
    assert (rows.astype(np.int64) == wt.bodyId.to_numpy()).all()
    data, indices, indptr = [], [], [0]
    t0 = time.time()
    for s in range(0, N, 1000):
        cols = list(range(s, min(N, s + 1000)))
        b = ipc.open_file(pa.memory_map(str(FULL_W)), options=ipc.IpcReadOptions(included_fields=cols)).get_batch(0)
        for k in range(b.num_columns):
            c = b.column(k).to_numpy(zero_copy_only=False)
            nz = np.nonzero(c)[0]
            indices.append(nz.astype(np.int32)); data.append(c[nz].astype(np.float32)); indptr.append(indptr[-1] + len(nz))
    W = sp.csc_matrix((np.concatenate(data), np.concatenate(indices), np.array(indptr, dtype=np.int64)), shape=(N, N))  # W[pre, post]
    sp.save_npz(OUT / "W_csc.npz", W)
    meta = dict(n=N, nnz=int(W.nnz), exc_nnz=int((W.data > 0).sum()), inh_nnz=int((W.data < 0).sum()),
                abs_synapses=float(np.abs(W.data).sum()), build_s=round(time.time() - t0, 1), source=str(FULL_W.name))
    (OUT / "W_meta.json").write_text(json.dumps(meta, indent=1))
    print(meta)


def load_full():
    W = sp.load_npz(OUT / "W_csc.npz").tocsr()
    wt = pd.read_feather(FULL_T)
    return W, wt


def to_bcoo_transposed(W, exc_mult=0.03, inh_mult=0.03):
    """作者：Wt = Wᵀ；exc_mult·max(Wt,0) + inh_mult·min(Wt,0)。返回 JAX BCOO（行 = 突触后）。"""
    import jax.numpy as jnp
    from jax.experimental import sparse as jsparse
    Wt = W.T.tocoo()
    vals = np.where(Wt.data > 0, Wt.data * exc_mult, Wt.data * inh_mult).astype(np.float32)
    order = np.lexsort((Wt.col, Wt.row))
    idx = np.stack([Wt.row[order], Wt.col[order]], axis=1).astype(np.int32)
    return jsparse.BCOO((jnp.asarray(vals[order]), jnp.asarray(idx)), shape=Wt.shape, indices_sorted=True, unique_indices=True)


def cmd_bench(a):
    import jax
    import jax.numpy as jnp
    W, wt = load_full()
    print("N", W.shape[0], "nnz", W.nnz)
    Wt = W.T.tocsr().astype(np.float32) * np.float32(0.03)
    r = np.random.rand(W.shape[0]).astype(np.float32)
    t0 = time.time()
    for _ in range(20):
        Wt @ r
    print(f"scipy CSR matvec: {(time.time() - t0) / 20 * 1000:.1f} ms")
    B = to_bcoo_transposed(W)
    f = jax.jit(lambda v: B @ v)
    rv = jnp.asarray(r); f(rv)
    t0 = time.time()
    for _ in range(20):
        f(rv).block_until_ready() if hasattr(f(rv), "block_until_ready") else None
    print(f"JAX BCOO matvec (jit, 含两次调用/轮): {(time.time() - t0) / 40 * 1000:.1f} ms")
    rows, cols = np.asarray(B.indices[:, 0]), np.asarray(B.indices[:, 1])
    vals = B.data
    g = jax.jit(lambda v: jax.ops.segment_sum(vals * v[cols], rows, num_segments=W.shape[0], indices_are_sorted=True))
    g(rv)
    t0 = time.time()
    for _ in range(20):
        g(rv)
    print(f"JAX segment_sum matvec: {(time.time() - t0) / 20 * 1000:.1f} ms",
          "max diff vs scipy", float(np.abs(np.asarray(g(rv)) - Wt @ r).max()))


def make_rhs():
    import jax
    import jax.numpy as jnp

    def rhs(t, R, args):
        inputs, pulse_start, pulse_end, tau, vals, rows, cols, threshold, a, fr_cap, n = args
        pulse_active = (t >= pulse_start) & (t <= pulse_end)
        rec = jax.ops.segment_sum(vals * R[cols], rows, num_segments=R.shape[0], indices_are_sorted=True)
        total = inputs * pulse_active + rec
        act = jnp.maximum(fr_cap * jnp.tanh((a / fr_cap) * (total - threshold)), 0)
        return (act - R) / tau
    return rhs


_TERM = None


def simulate(Wt_parts, tau, a_, thr, frcap, inputs, T, dt, pulse_start, pulse_end, rtol, atol):
    """同作者 run_single_simulation 的求解设置（Dopri5、PIDController、SaveAt 1 ms、max_steps 100000、throw=False），只换矩阵乘法。"""
    import jax.numpy as jnp
    from diffrax import Dopri5, ODETerm, PIDController, SaveAt, diffeqsolve
    global _TERM
    vals, rows, cols = Wt_parts
    N = tau.shape[0]
    t_axis = jnp.arange(0, T + dt / 2, dt, dtype=jnp.float32)
    if _TERM is None:
        _TERM = ODETerm(make_rhs())
    sol = diffeqsolve(_TERM, Dopri5(), 0, T, dt, jnp.zeros(N),
                      args=(inputs, pulse_start, pulse_end, tau, vals, rows, cols, thr, a_, frcap, N),
                      saveat=SaveAt(ts=t_axis), stepsize_controller=PIDController(rtol=rtol, atol=atol), max_steps=100000, throw=False)
    R = jnp.transpose(sol.ys)
    R = jnp.where(jnp.isinf(R) | jnp.isnan(R), 0.0, R)
    return jnp.clip(R, 0.0, 1000.0), int(sol.stats["num_steps"])


def parts_from_dense_or_sparse(W, exc=0.03, inh=0.03):
    import jax.numpy as jnp
    Wt = sp.csr_matrix(W).T.tocoo()
    order = np.lexsort((Wt.col, Wt.row))
    v = Wt.data[order].astype(np.float32)
    v = np.where(v > 0, v * exc, v * inh).astype(np.float32)
    return jnp.asarray(v), jnp.asarray(Wt.row[order].astype(np.int32)), jnp.asarray(Wt.col[order].astype(np.int32))


def sample_params(size, n_reps, seed, npcfg):
    """复现作者 prepare_neuron_params 的抽样顺序（不建 W_mask），函数从作者代码 import。"""
    import jax
    from src.utils.sim_utils import sample_trunc_normal, set_sizes
    N = len(size)
    keys = jax.random.split(jax.random.PRNGKey(seed), 5)
    tau = sample_trunc_normal(keys[0], npcfg["tauMean"], npcfg["tauStdv"], (n_reps, N))
    a_ = sample_trunc_normal(keys[1], npcfg["aMean"], npcfg["aStdv"], (n_reps, N))
    thr = sample_trunc_normal(keys[2], npcfg["thresholdMean"], npcfg["thresholdStdv"], (n_reps, N))
    frcap = sample_trunc_normal(keys[3], npcfg["frcapMean"], npcfg["frcapStdv"], (n_reps, N))
    a_, thr = set_sizes(np.asarray(size), a_, thr)
    return tau, a_, thr, frcap


def cmd_parity(a):
    """T1 网络：作者 prepare_neuron_params（16 副本、seed 1）得到的参数 + 稀疏求解，对比 results/vnc/pugliese/DNg100_L.npz。"""
    import jax.numpy as jnp
    sys.path.insert(0, str(ROOT / "vnc"))
    from run_pugliese import make_cfg
    from src.simulation.vnc_sim import prepare_neuron_params
    from src.utils.sim_utils import load_wTable
    cfg = make_cfg(16, [31], [250.0], 1e-4, 1e-7)
    wt = load_wTable(cfg.experiment.dfPath)
    npar = prepare_neuron_params(cfg, wt)
    ref = np.load(ROOT / "results/vnc/pugliese/DNg100_L.npz")
    mn = ref["mn_index"]
    parts = parts_from_dense_or_sparse(np.asarray(npar.W))
    # 用自己的抽样再算一遍参数，检查与作者 prepare_neuron_params 一致
    npcfg = dict(cfg.neuron_params)
    tau, a_, thr, frcap = sample_params(wt["size"].values, 16, int(cfg.experiment.seed), npcfg)
    same = all(np.allclose(np.asarray(x), np.asarray(y)) for x, y in [(tau, npar.tau), (a_, npar.a), (thr, npar.threshold), (frcap, npar.fr_cap)])
    print("自写抽样 == 作者 prepare_neuron_params:", same)
    res = []
    for rep in (0, 1):
        t0 = time.time()
        R, steps = simulate(parts, npar.tau[rep], npar.a[rep], npar.threshold[rep], npar.fr_cap[rep], npar.input_currents[0, rep],
                            2.0, 0.001, 0.02, 1.999, 1e-4, 1e-7)
        Rm = np.asarray(R)[mn]
        d = float(np.abs(Rm - ref["R_mn"][rep].astype(np.float32)).max())
        res.append(dict(rep=rep, max_abs_diff_hz=round(d, 3), max_rate_hz=round(float(Rm.max()), 2), steps=steps, sim_s=round(time.time() - t0, 1)))
        print(res[-1])
    (OUT / "parity_T1.json").write_text(json.dumps(dict(sampling_identical=bool(same), runs=res), indent=1))


# —— 全腹神经索实验（运行前写定）——
# 参数：seed 1（作者默认），一次抽 16 组副本参数，第 k 个副本在所有条件里参数相同；容差 rtol 1e-4 / atol 1e-7（T1 上已验证）。
# 刺激强度：作者全腹神经索的配置未公开。探针（DNg100 双侧 I = 250，副本 0）：DNg100 只有 9.5/9.8 Hz，全网 21 个神经元活跃、
#   腿部运动神经元 0 个——作者按“网络中位神经元大小”缩放阈值和增益，全腹神经索的中位大小比 T1 网络小，同样的 I 驱动更弱。
#   所以在看任何节律结果之前加一档标定强度：让 DNg100 的发放率与 T1 默认实验相同（约 16 Hz），
#   按 r = r_max·tanh(a/r_max·(I − θ)) 用副本平均参数反推得 I ≈ 350；另保留 250 / 400 / 600 做剂量对照。
CONDITIONS = {
    "none":           ([], 0.0, 8),
    "DNg100_LR_250":  (["DNg100"], 250.0, 8),
    "DNg100_LR_350":  (["DNg100"], 350.0, 16),   # 主条件：按 T1 的 DNg100 发放率标定
    "DNg100_LR_400":  (["DNg100"], 400.0, 8),
    "DNg100_LR_600":  (["DNg100"], 600.0, 8),
    "DNg100_L_350":   (["DNg100:L"], 350.0, 8),
    "MDN_250":        (["MDN"], 250.0, 8),
    "MDN_400":        (["MDN"], 400.0, 8),
}
# 全突触数据（MANC_DATASET=all，运行前写定）：与 20251006 只差 3,929,165 条新增的弱连接（中位 1 个突触；原有连接权重完全相同）。
#   标定规则不变（DNg100 发放率 16 Hz，副本平均参数反推，取整到 10）→ I = 360；
#   条件缩减为与步态相关的 5 个（I = 600 与 MDN 在旧数据里 100% 失控，不重复）。
if DATASET == "all":
    CONDITIONS = {
        "none":           ([], 0.0, 8),
        "DNg100_LR_250":  (["DNg100"], 250.0, 8),
        "DNg100_LR_360":  (["DNg100"], 360.0, 16),   # 主条件
        "DNg100_LR_400":  (["DNg100"], 400.0, 8),
        "DNg100_L_360":   (["DNg100:L"], 360.0, 8),
    }
SAVE_TYPES = ["DNg100", "IN17A001", "INXXX466", "IN16B036", "IN19A007", "DNp01", "MDN"]


def stim_index(wt, specs):
    idx = []
    for sp_ in specs:
        t, _, side = sp_.partition(":")
        m = wt.type == t
        if side:
            m &= wt.instance.fillna("").str.endswith("_" + side)
        idx += wt.index[m].tolist()
    return idx


def cmd_run(a):
    import jax.numpy as jnp
    from src.utils.sim_utils import neuron_oscillation_score
    import jax
    ap = argparse.ArgumentParser()
    ap.add_argument("--conds", default=",".join(CONDITIONS))
    ap.add_argument("--rtol", type=float, default=1e-4)
    ap.add_argument("--atol", type=float, default=1e-7)
    ap.add_argument("--probe", action="store_true", help="只跑第一个条件的 1 个副本测速度，不写结果")
    b = ap.parse_args(sys.argv[2:])
    W, wt = load_full()
    N = len(wt)
    parts = parts_from_dense_or_sparse(W)
    import yaml
    npcfg = yaml.safe_load(open(PUG / "configs/neuron_params/default.yaml"))
    tau, a_, thr, frcap = sample_params(wt["size"].values, 16, 1, npcfg)
    legmn = np.where((wt["class"] == "motor neuron").to_numpy() & wt.somaNeuromere.isin(["T1", "T2", "T3"]).to_numpy())[0]
    sel = np.unique(np.concatenate([np.where((wt["class"] == "motor neuron").to_numpy())[0], wt.index[wt.type.isin(SAVE_TYPES)].to_numpy()]))
    score_all = jax.jit(jax.vmap(neuron_oscillation_score, in_axes=(0, None)))
    path = OUT / "summary.json"
    summary = json.loads(path.read_text()) if path.exists() else {}
    for name in b.conds.split(","):
        specs, I, reps = CONDITIONS[name]
        if b.probe:
            reps = 1
        si = stim_index(wt, specs)
        inputs = np.zeros(N, np.float32); inputs[si] = I
        R_sel, runs = [], []
        t_start = time.time()
        for rep in range(reps):
            t0 = time.time()
            R, steps = simulate(parts, tau[rep], a_[rep], thr[rep], frcap[rep], jnp.asarray(inputs), 2.0, 0.001, 0.02, 1.999, b.rtol, b.atol)
            R = np.asarray(R)
            Rm = R[legmn, 230:]
            act = Rm.max(axis=1) > 0.01
            sc, fr = score_all(jnp.asarray(Rm), 0.05)
            sc, fr = np.asarray(sc), np.asarray(fr) / 0.001
            net = float(sc[act].mean()) if act.any() else 0.0
            runs.append(dict(rep=rep, steps=steps, sim_s=round(time.time() - t0, 1), n_active_all_1hz=int((R[:, 230:].max(axis=1) > 1).sum()),
                             n_active_legmn_1hz=int((Rm.max(axis=1) > 1).sum()), net_score=round(net, 3), oscillating=bool(net >= 0.5),
                             mean_freq_hz=(round(float(np.nanmean(np.where(act & (fr > 0), fr, np.nan))), 2) if (act & (fr > 0)).any() else None),
                             stim_rate_hz=[round(float(R[i, 230:].mean()), 1) for i in si]))
            R_sel.append(R[sel].astype(np.float16))
            del R
            r = runs[-1]
            print(f"  {name} 副本 {rep}: {r['sim_s']} s（{steps} 步），全网活跃 {r['n_active_all_1hz']}，腿部运动神经元活跃 {r['n_active_legmn_1hz']}，"
                  f"振荡得分 {net:.2f}，频率 {r['mean_freq_hz']} Hz，刺激神经元 {r['stim_rate_hz']} Hz", flush=True)
        if b.probe:
            return
        np.savez_compressed(OUT / f"{name}.npz", R_sel=np.stack(R_sel), sel_index=sel)
        summary[name] = dict(stim=specs, stim_index=si, stim_I=I, reps=reps, rtol=b.rtol, atol=b.atol,
                             frac_oscillating=round(float(np.mean([r["oscillating"] for r in runs])), 3),
                             median_net_score=round(float(np.median([r["net_score"] for r in runs])), 3),
                             median_freq_hz=(round(float(np.median([r["mean_freq_hz"] for r in runs if r["mean_freq_hz"]])), 2)
                                             if any(r["mean_freq_hz"] for r in runs) else None),
                             wall_s=round(time.time() - t_start, 1), runs=runs)
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=1))
        s_ = summary[name]
        print(f"{name}: 振荡副本 {s_['frac_oscillating']}，得分中位 {s_['median_net_score']}，频率中位 {s_['median_freq_hz']} Hz，用时 {s_['wall_s']} s", flush=True)


# —— 第 2 项：巨纤维 → TTMn 电突触（运行前写定）——
# MANC 化学连接里巨纤维已有突触：GF_R(行 0) → TTMn_R(行 74) 146 个、GF_L(行 2) → TTMn_L(行 41) 135 个；电突触不在连接组里。
# 发放率模型没有膜电位，电突触近似为对称的发放率耦合：I_gap,TTMn = g·(r_GF − r_TTMn)，I_gap,GF = g·(r_TTMn − r_GF)，
#   g = n_eq × 0.03（与化学突触同单位，n_eq = “等效突触数”），同侧配对（与化学突触配对一致）。
# 刺激双侧巨纤维，强度按“巨纤维发放率 16 Hz / 100 Hz”用副本平均参数反推（I ≈ 1,925 / 9,670）；
# 耦合 n_eq ∈ {0, 150, 1500}；副本 0–3（参数与第 1 项相同）。
# 读出：巨纤维与 TTMn 左右发放率（230 ms 之后平均与峰值）、TTMn 达到自身峰值一半的时间、中足/全部腿部运动神经元活跃数、全网活跃数。
GAP_PAIRS = [(0, 74), (2, 41)]      # (GF 行, TTMn 行)；20251006 表中的行号，other 数据集按类型与侧别查找
GAP_STIM = {"GF16": 1925.0, "GF100": 9670.0}
GAP_NEQ = [0, 150, 1500]
# 全突触数据（MANC_DATASET=all）的缩减网格（运行前写定）：GF16 只做无电突触；GF100 做无电突触与 1,500 两档；强度按同一规则重新反推
GAP_GRID_ALL = [("GF16", 0), ("GF100", 0), ("GF100", 1500)]


def gap_pairs(wt):
    gf = {s_: int(wt.index[(wt.type == "DNp01") & wt.instance.fillna("").str.endswith("_" + s_)][0]) for s_ in ("R", "L")}
    tt = {s_: int(wt.index[(wt.type == "TTMn") & (wt.somaSide == ("RHS" if s_ == "R" else "LHS"))][0]) for s_ in ("R", "L")}
    return [(gf["R"], tt["R"]), (gf["L"], tt["L"])]


def calibrate_I(a_, thr, frcap, rows, target):
    A, TH, F = (np.asarray(x).mean(axis=0)[rows] for x in (a_, thr, frcap))
    return float(np.round(np.mean(TH + F / A * np.arctanh(target / F)), -1))


def add_gap(W, n_eq, pairs=None):
    if n_eq == 0:
        return W
    r, c, v = [], [], []
    for g, t in (pairs or GAP_PAIRS):
        r += [g, t, t, g]; c += [t, g, t, g]; v += [n_eq, n_eq, -n_eq, -n_eq]
    return (W + sp.csr_matrix((np.array(v, np.float32), (r, c)), shape=W.shape)).tocsr()


def cmd_gap(a):
    import jax.numpy as jnp
    import yaml
    W0, wt = load_full()
    N = len(wt)
    npcfg = yaml.safe_load(open(PUG / "configs/neuron_params/default.yaml"))
    tau, a_, thr, frcap = sample_params(wt["size"].values, 16, 1, npcfg)
    legmn = (wt["class"] == "motor neuron").to_numpy() & wt.somaNeuromere.isin(["T1", "T2", "T3"]).to_numpy()
    t2mn = legmn & (wt.somaNeuromere == "T2").to_numpy()
    pairs = gap_pairs(wt)
    (gR, tR), (gL, tL) = pairs
    if DATASET == "all":
        stims = {k: calibrate_I(a_, thr, frcap, [gR, gL], t) for k, t in (("GF16", 16.0), ("GF100", 100.0))}
        grid = [(st, n) for st, n in GAP_GRID_ALL]
    else:
        stims = GAP_STIM
        grid = [(st, n) for n in GAP_NEQ for st in GAP_STIM]
    print("巨纤维/TTMn 行：", pairs, "；刺激强度：", stims, flush=True)
    rows = []
    path = OUT / "gap_summary.json"
    for stim, n_eq in grid:
        parts = parts_from_dense_or_sparse(add_gap(W0, n_eq, pairs))
        I = stims[stim]
        if True:
            inputs = np.zeros(N, np.float32); inputs[[gR, gL]] = I
            for rep in range(4):
                t0 = time.time()
                R, steps = simulate(parts, tau[rep], a_[rep], thr[rep], frcap[rep], jnp.asarray(inputs), 2.0, 0.001, 0.02, 1.999, 1e-4, 1e-7)
                R = np.asarray(R)
                post = R[:, 230:]
                def half_t(i):
                    x = R[i]; m = x.max()
                    return None if m < 1 else int(np.argmax(x >= m / 2)) - 20
                row = dict(stim=stim, n_eq=n_eq, rep=rep, steps=steps, sim_s=round(time.time() - t0, 1),
                           stim_I=I, GF_R=round(float(post[gR].mean()), 1), GF_L=round(float(post[gL].mean()), 1),
                           TTMn_R=round(float(post[tR].mean()), 1), TTMn_L=round(float(post[tL].mean()), 1),
                           TTMn_R_peak=round(float(R[tR].max()), 1), TTMn_L_peak=round(float(R[tL].max()), 1),
                           TTMn_R_half_ms=half_t(tR), TTMn_L_half_ms=half_t(tL),
                           t2_mn_active=int((post[t2mn].max(axis=1) > 1).sum()), leg_mn_active=int((post[legmn].max(axis=1) > 1).sum()),
                           active_all=int((post.max(axis=1) > 1).sum()))
                rows.append(row)
                print(f"  {stim} 耦合 {n_eq}: 副本 {rep} {row['sim_s']} s；巨纤维 R/L {row['GF_R']}/{row['GF_L']} Hz → TTMn R/L {row['TTMn_R']}/{row['TTMn_L']} Hz"
                      f"（峰值 {row['TTMn_R_peak']}/{row['TTMn_L_peak']}，半峰时间 {row['TTMn_R_half_ms']}/{row['TTMn_L_half_ms']} ms）；"
                      f"中足运动神经元 {row['t2_mn_active']}，腿部运动神经元 {row['leg_mn_active']}，全网 {row['active_all']}", flush=True)
                del R
                path.write_text(json.dumps(rows, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "bench", "parity", "run", "gap"])
    a, rest = ap.parse_known_args()
    {"build": cmd_build, "bench": cmd_bench, "parity": cmd_parity, "run": cmd_run, "gap": cmd_gap}[a.cmd](a)
