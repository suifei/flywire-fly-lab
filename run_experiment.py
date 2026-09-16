#!/usr/bin/env python
"""
最小实验：在 FlyWire v783 全脑 LIF 模型（Shiu et al. 2024 / eonsystemspbc/fly-brain）中
激活 / 沉默指定神经元，记录 spike 与膜电位，保存数据与图。

设计原则
--------
* 不重新发明模型：
  - backend=torch  直接 import 官方仓库 code/run_pytorch.py 里的 TorchModel（与 Brian2 同参数）
  - backend=brian2 直接 import 官方仓库 code/paper-phil-drosophila/model.py 的
    create_model / poi / silence（Shiu et al. 原始 Brian2 实现，官方称其为 ground truth）
* 数据直接用官方仓库自带的 data/2025_Completeness_783.csv 与 data/2025_Connectivity_783.parquet
* “沉默”语义与官方 Brian2 代码一致：把该神经元的 *传出* 突触权重置 0
  （注意：官方 README 写的是 “to and from”，但代码 silence() 只置零 i==pre 的突触）

用法示例
--------
  # 1) 激活左右 P9（前进行走相关下行通路）100 Hz，1 s，CPU 即可
  python run_experiment.py --preset p9 --t_run 1

  # 2) 激活 21 个糖味 GRN 200 Hz，看 MN9（进食/伸喙运动神经元）是否被驱动
  python run_experiment.py --preset sugar --t_run 1

  # 3) 同样刺激，但同时沉默某些神经元，并与基线对比（自动跑两遍）
  python run_experiment.py --preset sugar --silence 720575940660219265 --compare

  # 4) 任意 FlyWire root ID（v783）
  python run_experiment.py --exc 720575940627652358 --rate 150 --record 720575940626730883

输出（--out 目录，默认 results/<实验名>/）
------------------------------------------
  spikes_<cond>.parquet   每行一个 spike: time_ms, trial, neuron_index, flywire_id
  rates.csv               各条件下每个神经元的平均发放率（Hz）
  readout.csv             官方 notebook 中列出的下行/运动“控制把手”神经元发放率
  voltage_<cond>.npz      被记录神经元的膜电位轨迹
  figure.png              raster + 群体发放率 + 膜电位 + 读出神经元柱状图
  summary.json            参数、版本、耗时、spike 统计
"""

import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow  # noqa: F401  官方代码注释：需先于 torch import，避免 libarrow 冲突

HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("FLY_BRAIN_REPO", HERE / "external" / "fly-brain"))
PATH_COMP = REPO / "data" / "2025_Completeness_783.csv"
PATH_CON = REPO / "data" / "2025_Connectivity_783.parquet"
# 可选：github.com/flyconnectome/flywire_annotations 的公开注释表，用于给结果加 cell_type
PATH_ANNOT = HERE / "external" / "flywire_annotations" / "Supplemental_file1_neuron_annotations.tsv"

# ---------------------------------------------------------------------------
# 神经元 ID —— 全部直接抄自官方仓库，不是我编的：
#   * sugar / p9 预设：code/benchmark.py 的 EXPERIMENTS
#   * READOUT：code/paper-phil-drosophila/example.ipynb 中的 output_neurons
# ---------------------------------------------------------------------------
PRESETS = {
    "sugar": dict(rate=200.0, exc=[
        720575940624963786, 720575940630233916, 720575940637568838, 720575940638202345,
        720575940617000768, 720575940630797113, 720575940632889389, 720575940621754367,
        720575940621502051, 720575940640649691, 720575940639332736, 720575940616885538,
        720575940639198653, 720575940639259967, 720575940617937543, 720575940632425919,
        720575940633143833, 720575940612670570, 720575940628853239, 720575940629176663,
        720575940611875570]),
    "p9": dict(rate=100.0, exc=[720575940627652358, 720575940635872101]),
}

READOUT = {
    720575940626730883: "P9_oDN1_left",   # 前进速度
    720575940620300308: "P9_oDN1_right",
    720575940627652358: "P9_left",
    720575940635872101: "P9_right",
    720575940627787609: "DNa01_right",    # 转向
    720575940644438551: "DNa01_left",
    720575940629327659: "DNa02_right",
    720575940604737708: "DNa02_left",
    720575940616026939: "MDN_1",          # 后退 / moonwalker
    720575940631082808: "MDN_2",
    720575940640331472: "MDN_3",
    720575940610236514: "MDN_4",
    720575940622838154: "Giant_Fiber_1",  # 逃逸
    720575940632499757: "Giant_Fiber_2",
    720575940660219265: "MN9_left",       # 伸喙 / 进食
    720575940618238523: "MN9_right",
    720575940616185531: "aDN1_right",     # 触角梳理
    720575940624319124: "aDN1_left",
}

DT_MS = 0.1  # 与官方所有后端一致
MAX_POISSONINPUT = 50  # 超过这个数就不用官方的逐神经元 PoissonInput（见 run_brian2 注释）


# ---------------------------------------------------------------------------
def load_ids():
    df_comp = pd.read_csv(PATH_COMP, index_col=0)
    flyid2i = {int(f): i for i, f in enumerate(df_comp.index)}
    i2flyid = np.array(df_comp.index, dtype=np.int64)
    return flyid2i, i2flyid


def ids_by_type(specs):
    """'LC4:left' → 注释表中 cell_type==LC4 且 side==left 的 root_id 列表。"""
    if not PATH_ANNOT.exists():
        sys.exit(f"[错误] --exc_type 需要注释表 {PATH_ANNOT}（见 setup.sh）")
    ann = pd.read_csv(PATH_ANNOT, sep="\t", low_memory=False, usecols=["root_id", "cell_type", "side"])
    out = []
    for spec in specs:
        ctype, _, side = spec.partition(":")
        m = ann["cell_type"] == ctype
        if side:
            m &= ann["side"] == side
        ids = ann.loc[m, "root_id"].astype("int64").tolist()
        print(f"  --exc_type {spec}: {len(ids)} 个神经元")
        if not ids:
            sys.exit(f"[错误] 注释表里没有 {spec}")
        out += ids
    return list(dict.fromkeys(out))


def to_index(ids, flyid2i, what):
    missing = [i for i in ids if i not in flyid2i]
    if missing:
        sys.exit(f"[错误] {what} 中这些 ID 不在 FlyWire v783 神经元表里: {missing}")
    return [flyid2i[i] for i in ids]


# ---------------------------------------------------------------------------
# 后端 1：PyTorch（官方 TorchModel）
# ---------------------------------------------------------------------------
def run_torch(exc, slnc, rate_hz, t_run_s, n_trials, record_idx, seed, device):
    sys.path.insert(0, str(REPO / "code"))
    import torch
    from run_pytorch import TorchModel, MODEL_PARAMS  # 官方实现

    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else \
            ("mps" if torch.backends.mps.is_available() else "cpu")
    torch.manual_seed(seed)

    # 自己从 parquet 构建稀疏矩阵（不写官方那 ~580MB 的 pkl 缓存），
    # 形状 (post, pre)，值 = 'Excitatory x Connectivity'（带符号的突触数）
    t0 = time.perf_counter()
    con = pd.read_parquet(PATH_CON)
    n = len(pd.read_csv(PATH_COMP, index_col=0))
    pre = con["Presynaptic_Index"].to_numpy()
    post = con["Postsynaptic_Index"].to_numpy()
    w = con["Excitatory x Connectivity"].to_numpy().astype(np.float32)
    if slnc:  # 沉默 = 传出突触置 0（与官方 Brian2 silence() 一致）
        w[np.isin(pre, np.asarray(slnc))] = 0.0
    coo = torch.sparse_coo_tensor(np.vstack([post, pre]), w, (n, n)).coalesce()
    t_setup = time.perf_counter() - t0

    if device == "mps":
        # MPS 不支持 CSR（实测报 NotImplementedError: new_compressed_tensor），
        # 但支持 COO 的 torch.sparse.mm。只替换官方 forward 里那一次稀疏乘法，其余逻辑不变。
        class TorchModelMPS(TorchModel):
            def forward(self, rates, conductance, delay_buffer, spikes, v, refrac, generator=None):
                voltage_stim = self.scale * self.poisson(rates, generator=generator)
                recurrent_input = self.scale * torch.sparse.mm(self.weights, spikes.T).T
                return self.neurons(recurrent_input, voltage_stim, conductance,
                                    delay_buffer, spikes, v, refrac)
        model = TorchModelMPS(n_trials, n, DT_MS, MODEL_PARAMS, coo.to(device),
                              exc_indices=exc, device=device)
    else:
        model = TorchModel(n_trials, n, DT_MS, MODEL_PARAMS, coo.to_sparse_csr().to(device),
                           exc_indices=exc, device=device)
    cond, dbuf, spikes, v, refrac = model.state_init()
    rates = torch.zeros(n_trials, n, device=device)
    rates[:, exc] = rate_hz

    n_steps = int(round(t_run_s * 1000 / DT_MS))
    rec = torch.as_tensor(record_idx, dtype=torch.long, device=device)
    v_trace = np.zeros((n_steps, n_trials, len(record_idx)), dtype=np.float32)
    sb, sn, st = [], [], []

    t1 = time.perf_counter()
    with torch.no_grad():
        for step in range(n_steps):
            cond, dbuf, spikes, v, refrac = model(rates, cond, dbuf, spikes, v, refrac)
            if len(record_idx):
                v_trace[step] = v[:, rec].cpu().numpy()
            b, j = (spikes > 0).nonzero(as_tuple=True)
            if len(b):
                sb.append(b.cpu()); sn.append(j.cpu())
                st.append(torch.full((len(b),), step, dtype=torch.long))
            if n_steps >= 2000 and (step + 1) % (n_steps // 10) == 0:
                print(f"  [torch/{device}] {100*(step+1)//n_steps}%  "
                      f"{time.perf_counter()-t1:.1f}s", flush=True)
    t_sim = time.perf_counter() - t1

    if sb:
        trial = torch.cat(sb).numpy(); idx = torch.cat(sn).numpy()
        tms = torch.cat(st).numpy() * DT_MS
    else:
        trial = idx = np.array([], dtype=np.int64); tms = np.array([], dtype=float)
    # 官方 TorchModel 的膜电位在 spike 当步已被 reset，所以轨迹上看不到尖峰，用 spike 时间补标记
    return dict(trial=trial, idx=idx, time_ms=tms, v_trace=v_trace,
                v_time_ms=(np.arange(n_steps) + 1) * DT_MS,
                t_setup=t_setup, t_sim=t_sim, device=device, backend="torch")


# ---------------------------------------------------------------------------
# 后端 2：Brian2（官方 paper 代码，runtime 模式，CPU）
# ---------------------------------------------------------------------------
def run_brian2(exc, slnc, rate_hz, t_run_s, n_trials, record_idx, seed, device):
    """C++ standalone 模式（与官方 --brian2-cpu 相同）：生成 C++ → 编译一次 → 运行 n_trials 次。
    实测 M1 Pro 上比官方 PyTorch-CPU 路径快 ~30 倍。需要 C++ 编译器（macOS: Xcode CLT；Linux: g++）。"""
    sys.path.insert(0, str(REPO / "code" / "paper-phil-drosophila"))
    import brian2 as b2
    from brian2 import Hz, ms, mV, Network, StateMonitor
    from model import create_model, poi, silence, default_params  # 官方实现

    b2.device.reinit(); b2.device.activate()          # 允许同一进程里先后跑多个条件
    build_dir = HERE / "results" / ".brian2_build"
    b2.set_device("cpp_standalone", build_on_run=False)
    b2.prefs.devices.cpp_standalone.openmp_threads = 0  # macOS clang 默认无 OpenMP
    # 踩坑记录：Brian2 默认 `make -j`（不限并行），配合下面“每个神经元一个 PoissonInput”，
    # 激活 ~4000 个 R1-6 时生成了 8248 个 C++ 文件、同时起几千个 clang，把 16GB 内存吃光导致死机。
    b2.prefs.devices.cpp_standalone.extra_make_args_unix = ["-j4"]
    b2.defaultclock.dt = DT_MS * ms

    params = dict(default_params)
    params["r_poi"] = rate_hz * Hz
    params["t_run"] = t_run_s * 1000 * ms

    t0 = time.perf_counter()
    # 踩坑记录（2026-09-14 发现）：standalone 把 b2.seed(x) 编译成 main.cpp 里的常数，之后每次 device.run 都从同一个种子开始，
    # 于是 n_trials 个“试次”是同一次模拟的逐位复制（results/dodge_ref、v2_ref 等旧结果都是这样，实为 1 个试次）。
    # 现在：只跑 1 个试次时照旧用 seed（可复现）；多试次时不设种子，每次运行由系统随机源播种，试次彼此独立，但不能逐位复现。
    if n_trials == 1:
        b2.seed(seed)
    neu, syn, spk_mon = create_model(str(PATH_COMP), str(PATH_CON), params)
    if len(exc) <= MAX_POISSONINPUT:
        pois, neu = poi(neu, exc, [], params)  # 官方写法：每个神经元一个 PoissonInput
    else:
        # 大批量激活：1 个 PoissonGroup + 一对一突触，统计上等价于 N=1 的 PoissonInput
        # （每个 Poisson 事件给 v 加 w_syn*f_poi），但代码对象数量与神经元数无关
        from brian2 import PoissonGroup, Synapses
        pg = PoissonGroup(len(exc), rates=params["r_poi"])
        ps = Synapses(pg, neu, on_pre=f"v += {float(params['w_syn'] * params['f_poi'] / mV)}*mV")
        ps.connect(i=np.arange(len(exc)), j=np.asarray(exc))
        # standalone 不支持 neu.rfc[index_array] = ...，只能整体赋值
        rfc = np.full(len(neu), float(params["t_rfc"] / ms)); rfc[np.asarray(exc)] = 0.0
        neu.rfc = rfc * ms
        pois = [pg, ps]
    if len(slnc) > MAX_POISSONINPUT:  # 官方 silence() 每个神经元一次字符串索引，批量时改成一次
        # standalone 模式在 build 前读不到 syn.i，所以直接从 parquet 重算权重（与 create_model 同顺序）
        con = pd.read_parquet(PATH_CON, columns=["Presynaptic_Index", "Excitatory x Connectivity"])
        w = con["Excitatory x Connectivity"].to_numpy(dtype=float) * float(params["w_syn"] / mV)
        w[np.isin(con["Presynaptic_Index"].to_numpy(), np.asarray(slnc))] = 0.0
        syn.w = w * mV
    else:
        syn = silence(slnc, syn)
    objs = [neu, syn, spk_mon, *pois]
    vmon = StateMonitor(neu, "v", record=list(record_idx)) if len(record_idx) else None
    if vmon is not None:
        objs.append(vmon)
    net = Network(*objs)
    net.run(params["t_run"])
    b2.device.build(directory=str(build_dir), compile=True, run=False, clean=True)
    t_setup = time.perf_counter() - t0

    trials, idxs, times, vtr = [], [], [], []
    t_sim = 0.0
    for k in range(n_trials):
        # 多试次时没有编译进种子，每次 run 的随机数不同（见上方踩坑记录）
        t1 = time.perf_counter()
        b2.device.run(directory=str(build_dir), with_output=False)
        t_sim += time.perf_counter() - t1
        i = np.asarray(spk_mon.i[:]); t = np.asarray(spk_mon.t / ms)
        trials.append(np.full(len(i), k)); idxs.append(i); times.append(t)
        if vmon is not None:
            vtr.append((vmon.v / mV).T.astype(np.float32))  # (steps, n_rec)
            v_time = np.asarray(vmon.t / ms)
    v_trace = np.stack(vtr, axis=1) if vtr else np.zeros((0, n_trials, 0))
    return dict(trial=np.concatenate(trials), idx=np.concatenate(idxs),
                time_ms=np.concatenate(times), v_trace=v_trace,
                v_time_ms=v_time if vtr else np.array([]),
                t_setup=t_setup, t_sim=t_sim, device="cpu",
                backend=f"brian2 {b2.__version__} cpp_standalone")


# ---------------------------------------------------------------------------
def summarize(res, i2flyid, n_total, t_run_s, n_trials, cond, out):
    df = pd.DataFrame({"time_ms": res["time_ms"], "trial": res["trial"].astype(int),
                       "neuron_index": res["idx"].astype(int)})
    df["flywire_id"] = i2flyid[df["neuron_index"].to_numpy()]
    df.to_parquet(out / f"spikes_{cond}.parquet")
    rate = (df.groupby("flywire_id").size() / (t_run_s * n_trials)).rename(cond)
    np.savez_compressed(out / f"voltage_{cond}.npz", v_mV=res["v_trace"],
                        time_ms=res["v_time_ms"])
    stats = dict(condition=cond, backend=res["backend"], device=res["device"],
                 setup_s=round(res["t_setup"], 2), sim_s=round(res["t_sim"], 2),
                 realtime_factor=round(t_run_s * n_trials / max(res["t_sim"], 1e-9), 5),
                 total_spikes=int(len(df)), active_neurons=int(df["flywire_id"].nunique()),
                 n_neurons=int(n_total))
    return df, rate, stats


def plot(dfs, rates, vres, record_ids, exc_ids, slnc_ids, t_run_s, n_trials, title, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    conds = list(dfs)
    fig, axes = plt.subplots(len(conds) + 2, 1, figsize=(11, 3.2 * (len(conds) + 2)))
    exc_set, sl_set = set(exc_ids), set(slnc_ids)
    for ax, c in zip(axes, conds):
        d = dfs[c][dfs[c]["trial"] == 0]
        # y 轴：按首次发放时间排序的神经元，直观看到“激活从刺激点向外传播”
        first = d.groupby("flywire_id")["time_ms"].min().sort_values()
        order = {f: k for k, f in enumerate(first.index)}
        y = d["flywire_id"].map(order)
        col = np.where(d["flywire_id"].isin(exc_set), "tab:red",
                       np.where(d["flywire_id"].isin(READOUT), "tab:green", "k"))
        ax.scatter(d["time_ms"], y, s=1.5, c=col, linewidths=0)
        ax.set_title(f"[{c}] raster, trial 0 — {len(first)} active neurons "
                     f"(red=stimulated, green=DN/MN readout)")
        ax.set_ylabel("neuron (sorted by 1st spike)")
        ax.set_xlim(0, t_run_s * 1000)
    ax = axes[len(conds)]
    for c in conds:
        h, e = np.histogram(dfs[c]["time_ms"], bins=np.arange(0, t_run_s * 1000 + 10, 10))
        ax.plot(e[:-1], h / (0.01 * n_trials), label=f"{c}: population spikes/s")
    ax.set_yscale("symlog"); ax.set_xlabel("time (ms)"); ax.legend(); ax.set_title("population activity (10 ms bins)")
    ax = axes[-1]
    names = [READOUT[f] for f in READOUT]
    x = np.arange(len(names)); wdt = 0.8 / len(conds)
    for k, c in enumerate(conds):
        vals = [rates[c].get(f, 0.0) for f in READOUT]
        ax.bar(x + k * wdt, vals, wdt, label=c)
    ax.set_xticks(x + 0.4 - wdt / 2); ax.set_xticklabels(names, rotation=60, ha="right", fontsize=8)
    ax.set_ylabel("rate (Hz)"); ax.legend(); ax.set_title("descending / motor 'control-handle' neurons")
    fig.suptitle(title); fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)

    if record_ids and any(v["v_trace"].size for v in vres.values()):
        fig, axs = plt.subplots(len(record_ids), 1, figsize=(11, 2.2 * len(record_ids)), squeeze=False)
        for r, fid in enumerate(record_ids):
            ax = axs[r, 0]
            for c, v in vres.items():
                ax.plot(v["v_time_ms"], v["v_trace"][:, 0, r], lw=0.6, label=c)
                st = dfs[c][(dfs[c]["trial"] == 0) & (dfs[c]["flywire_id"] == fid)]["time_ms"]
                ax.plot(st, np.full(len(st), -44.0), "|", ms=6)
            ax.axhline(-45, ls=":", c="gray")
            ax.set_ylabel("V (mV)"); ax.set_title(f"{READOUT.get(fid, fid)}  (ticks = spikes)", fontsize=9)
        axs[0, 0].legend(fontsize=8); axs[-1, 0].set_xlabel("time (ms)")
        fig.tight_layout(); fig.savefig(path.with_name("voltage.png"), dpi=130); plt.close(fig)


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preset", choices=list(PRESETS), help="官方预设刺激集")
    ap.add_argument("--exc", type=int, nargs="*", default=[], help="要激活的 FlyWire v783 root ID")
    ap.add_argument("--exc_type", nargs="*", default=[],
                    help="按细胞类型激活，格式 cell_type[:side]，如 LC4:left R8 DNa02:right"
                         "（需要 external/flywire_annotations 注释表）")
    ap.add_argument("--rate", type=float, default=None, help="Poisson 激活频率 Hz")
    ap.add_argument("--silence", type=int, nargs="*", default=[], help="要沉默的 root ID")
    ap.add_argument("--compare", action="store_true", help="同时跑一遍不沉默的基线用于对比")
    ap.add_argument("--record", type=int, nargs="*", default=None,
                    help="记录膜电位的 root ID（默认：前 2 个刺激神经元 + MN9 + P9_oDN1）")
    ap.add_argument("--t_run", type=float, default=1.0, help="模拟时长（秒）")
    ap.add_argument("--n_trials", type=int, default=1)
    ap.add_argument("--backend", choices=["torch", "brian2"], default="brian2",
                    help="brian2=官方 ground truth，CPU 首选；torch=有 NVIDIA GPU / Apple MPS 时用")
    ap.add_argument("--device", default="auto", help="torch: auto/cpu/cuda/mps")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()

    exc_ids = list(a.exc); rate = a.rate
    if a.preset:
        exc_ids = PRESETS[a.preset]["exc"] + exc_ids
        rate = rate or PRESETS[a.preset]["rate"]
    if a.exc_type:
        exc_ids += ids_by_type(a.exc_type)
    if not exc_ids:
        ap.error("需要 --preset、--exc 或 --exc_type")
    rate = rate or 150.0
    record_ids = a.record if a.record is not None else \
        exc_ids[:2] + [720575940660219265, 720575940618238523, 720575940626730883]
    name = (a.preset or "custom") + ("_silenced" if a.silence else "")
    out = a.out or HERE / "results" / f"{name}_{a.backend}"
    out.mkdir(parents=True, exist_ok=True)

    flyid2i, i2flyid = load_ids()
    dropped = [i for i in exc_ids if i not in flyid2i]
    if a.exc_type and dropped:  # 注释表(139k)比模型神经元表(138,639)略大，丢弃模型里没有的
        print(f"  [提示] {len(dropped)} 个按类型选出的神经元不在模型中，已忽略")
        exc_ids = [i for i in exc_ids if i in flyid2i]
    exc = to_index(exc_ids, flyid2i, "--exc")
    slnc = to_index(a.silence, flyid2i, "--silence")
    rec = to_index(record_ids, flyid2i, "--record")

    runner = run_torch if a.backend == "torch" else run_brian2
    conditions = [("baseline", [])] if not a.silence else \
        ([("baseline", [])] if a.compare else []) + [("silenced", slnc)]

    dfs, rates, vres, stats = {}, {}, {}, []
    for cond, sl in conditions:
        print(f"\n=== {cond}: 激活 {len(exc)} 个神经元 @ {rate} Hz，沉默 {len(sl)} 个，"
              f"{a.t_run}s × {a.n_trials} trial，backend={a.backend}", flush=True)
        res = runner(exc, sl, rate, a.t_run, a.n_trials, rec, a.seed, a.device)
        df, r, s = summarize(res, i2flyid, len(i2flyid), a.t_run, a.n_trials, cond, out)
        dfs[cond], rates[cond], vres[cond] = df, r, res
        stats.append(s); print(json.dumps(s, ensure_ascii=False))

    rate_tab = pd.concat(rates.values(), axis=1).fillna(0.0)
    rate_tab.insert(0, "name", [READOUT.get(int(f), "") for f in rate_tab.index])
    if PATH_ANNOT.exists():  # 公开细胞类型注释（Schlegel et al. 2024，与 Codex 同源）
        ann = pd.read_csv(PATH_ANNOT, sep="\t", low_memory=False,
                          usecols=["root_id", "super_class", "cell_class", "cell_type", "side"]
                          ).drop_duplicates("root_id").set_index("root_id")
        rate_tab = rate_tab.join(ann, how="left")
    rate_tab.sort_values(rate_tab.columns[1], ascending=False).to_csv(out / "rates.csv")
    ro = rate_tab.reindex(list(READOUT))[["name", *rates.keys()]]
    ro[list(rates)] = ro[list(rates)].fillna(0.0); ro["name"] = list(READOUT.values())
    ro.to_csv(out / "readout.csv")
    print("\n下行/运动读出神经元发放率 (Hz):\n", ro.to_string())

    plot(dfs, rates, vres, record_ids, exc_ids, a.silence, a.t_run, a.n_trials,
         f"{name}: {len(exc)} neurons @ {rate} Hz, backend={a.backend}", out / "figure.png")

    import importlib.metadata as md
    vers = {p: md.version(p) for p in ["numpy", "pandas", "torch", "brian2"]
            if importlib_has(md, p)}
    json.dump(dict(cmd=" ".join(sys.argv), repo=str(REPO), exc_ids=exc_ids, rate_hz=rate,
                   silence_ids=a.silence, record_ids=record_ids, t_run_s=a.t_run,
                   n_trials=a.n_trials, seed=a.seed, python=platform.python_version(),
                   platform=platform.platform(), versions=vers, runs=stats),
              open(out / "summary.json", "w"), indent=2, ensure_ascii=False)
    print(f"\n完成，输出目录: {out}")


def importlib_has(md, p):
    try:
        md.version(p); return True
    except md.PackageNotFoundError:
        return False


if __name__ == "__main__":
    main()
