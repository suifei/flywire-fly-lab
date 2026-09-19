#!/usr/bin/env python
"""
虚拟敲除筛选：糖味 → MN9（复现并扩展 Shiu et al. 2024 Nature 图 1F，补充表 1C / 2 / 10；补充表 CC BY 4.0，
存放在 external/shiu2024_supp/）

问题：给右侧唇瓣糖味受体神经元（GRN）泊松刺激，逐个“沉默”网络里的神经元，伸喙运动神经元 MN9 的放电下降多少？
哪些神经元被预测为“伸喙必需”？这些预测和论文自己的模型预测、和论文引用的真实光遗传沉默实验，各对得上多少？

事先写定的设计（运行前写好，结果出来后不改）：
  模型：官方 create_model（Shiu 2024 参数，FlyWire v783，138,639 个神经元），Brian2 cpp_standalone，dt 0.1 ms。
        论文用的是 v630，补充表里 200 个神经元有 184 个 ID 在 v783 里没变，比较只用这 184 个。
  刺激：run_experiment.py 的 sugar 预设 21 个 GRN（论文 notebook 的列表，其中 1 个换成了 v783 的新 ID）。
        50 Hz 为主（论文表 2 判定“必需”用的频率），100 Hz 为辅。
  读出：MN9 720575940660219265（论文 notebook 的 id_mn9）；每个试次从静息开始 1.000 s 内的脉冲数（= Hz）。
  沉默：让被沉默的神经元不能放电。下游效果与官方 silence()（传出突触权重置 0）相同，验证步骤里逐位核对。
  试次：R 个固定的输入实现（第 r 个：每个 GRN 每 0.1 ms 以 p = f·dt 放电，numpy 种子 20260914 + r；50 与 100 Hz 共用同一组随机数），
        所有条件都在同样的 R 个实现上跑，做配对比较。R = 8；如果按基线活跃神经元数估算的总时长超过 100 min，
        R 降到放得下的最大值（不低于 5）。这条规则只看基线活跃数和实测速度，不看任何沉默结果。
  确定性：网络本身没有噪声。某个神经元在第 r 个实现的基线里一次都没放电，沉默它的结果与基线逐位相同，不必模拟（验证步骤里核对）。
  实现：一条长模拟分成若干段。每段 1.010 s = 1.000 s 试次 + 10 ms 安静期（安静期里所有神经元禁止放电，1.8 ms 突触延迟内在途的脉冲随之清空）。
        每段开头把全部神经元的 v、g 复位到静息，相当于重新开始一个试次。每段沉默谁、用哪个输入实现，由运行时传入的 TimedArray 决定，
        所以只编译一次；每块 20 段调用一次 device.run，逐块存盘，可断点续跑。
  候选集合：
    P（论文集合）：补充表 1C 的 200 个神经元里 v783 中 ID 未变的（去掉读出本身 MN9），50 与 100 Hz 都筛；
    E（穷举集合）：50 Hz 基线里在任一实现中放过电的全部神经元（去掉 MN9）。论文只筛了按 200 Hz 反应排前 200 的；
    T（细胞类型）：论文表 2 里做过真实沉默实验的 10 个类型。真实实验沉默的是整个类型，所以这里两侧一起沉默
        （按注释表 cell_type 找两侧的神经元；Bract 两个亚型共 4 个），50 与 100 Hz。
  判定：比值 = Σ_r MN9(沉默, r) / Σ_r MN9(基线, r)，≤ 0.8 判为“必需”（论文用的是“下降超过 20%”）。
  比较（analyze）：
    (a) 与论文补充表 1C 同频率的归一化值比：Spearman ρ；判定一致率与 Cohen κ。
    (b) 10 个类型对真实实验（表 2 “Required for proboscis extension to 50 mM Sucrose?”；Fdg 两篇文献结果相反，按表 10 的算法记为“否”）：
        论文单个神经元的预测、我们单个神经元、我们两侧一起沉默，各对几个。
    (c) 连线指标能不能代替模拟（只算、不跑）：在 E 上，
        G1 = 对 MN9 的带符号直接突触数；G2 = 基线放电率 × G1；
        G3 = 基线放电率 × 只经过 50 Hz 基线活跃神经元、长度 1–3 的带符号通路权重和（每个突触折算为 w_syn / (v_th − v_0) = 0.275/7）。
        分别与模拟效应（1 − 比值）求 Spearman ρ，并看与模拟前 20 名重合几个。
  失控：每段记录全部神经元的脉冲数；活跃神经元 ≥ 2,000 的段记为失控（报告，不剔除）。

用法（brain-fly-cpu 环境，套 scratch/memguard.sh）：
  python screen/sugar_mn9_screen.py run       # 编译 → 基线 → 验证 → 筛选，逐块存盘
  python screen/sugar_mn9_screen.py analyze   # → results/screen/summary.json
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from xlsx_lite import read_xlsx  # noqa: E402

REPO = ROOT / "external" / "fly-brain"
PATH_COMP = REPO / "data" / "2025_Completeness_783.csv"
PATH_CON = REPO / "data" / "2025_Connectivity_783.parquet"
ANNOT = ROOT / "external" / "flywire_annotations" / "Supplemental_file1_neuron_annotations.tsv"
SUPP = ROOT / "external" / "shiu2024_supp" / "41586_2024_7763_MOESM2_ESM.xlsx"
OUT = ROOT / "results" / "screen"
BUILD = OUT / ".brian2_build"
CHUNKS = OUT / "chunks"

MN9 = 720575940660219265
FREQS = (50, 100)
R_MAX, R_MIN, BUDGET_MIN = 8, 5, 100
DT_MS = 0.1
TRIAL_STEPS, QUIET_STEPS = 10000, 100
SEG_STEPS = TRIAL_STEPS + QUIET_STEPS
GUARD_MS = 5.0              # 查表时间提前 5 ms（落在上一段的安静期里），避免段边界的浮点取整
K = 20                      # 每块段数（编译时固定）
N_SLOTS = 129               # 每块最多沉默 128 个不同神经元
SEED = 20260914
RUNAWAY_ACTIVE = 2000
CALL = 0.8
PARTIAL = False             # analyze --partial：跑完之前调试分析代码用
RFC_GATE = False            # True：不应期也逐段门控（见下方 Screen.__init__ 的注释）

# 论文表 2 的 10 个类型 → v783 注释 cell_type（名字与 ID 的对应取自补充表 1A/1C/4 的 “xxx_l / xxx_r”，再查注释表）
TYPES = {"Bract": ["DNge173", "DNge174"], "Clavicle": ["AN_GNG_30"], "Fdg": ["CB0038"], "FMIn": ["CB0366"], "G2N-1": ["CB0616"],
         "Phantom": ["CB0062"], "Rattle": ["CB0499"], "Roundup": ["CB0553"], "Usnea": ["CB0008"], "Zorro": ["CB0192"]}
# 论文表 2 “Change to MN9 as a result of silencing, 50 Hz Sugar” 用的单个神经元（与补充表 1C 的 _l 行数值一致；Bract 不在 1C 里）
PAPER_SINGLE = {"Bract": 720575940610001220, "Clavicle": 720575940655014049, "Fdg": 720575940631997032, "FMIn": 720575940614763666,
                "G2N-1": 720575940620874757, "Phantom": 720575940616103218, "Rattle": 720575940638103349, "Roundup": 720575940623211725,
                "Usnea": 720575940632648612, "Zorro": 720575940629888530}
# 表 2 “Required for proboscis extension to 50 mM Sucrose?”；Fdg 为 “Yes (Flood 2013) No (Shiu, Sterne 2022)”，表 10 按“否”计
EXPERIMENT_REQUIRED = {"Bract": False, "Clavicle": True, "Fdg": False, "FMIn": True, "G2N-1": True, "Phantom": False, "Rattle": True,
                       "Roundup": False, "Usnea": True, "Zorro": True}


def sheet(S, prefix):
    k = [k for k in S if k.startswith(prefix)]
    assert len(k) == 1, (prefix, k)
    return S[k[0]]


def load_ids():
    comp = pd.read_csv(PATH_COMP, index_col=0)
    fids = comp.index.to_numpy(np.int64)
    return fids, {int(f): i for i, f in enumerate(fids)}


def sugar_ids():
    from run_experiment import PRESETS
    return list(PRESETS["sugar"]["exc"])


def paper_table_1c():
    S = read_xlsx(SUPP)
    t = sheet(S, "ST 1C")
    hdr = t[0]
    norm_col = {f: 19 + 1 + [50, 60, 70, 80, 90, 100, 110, 120].index(f) for f in FREQS}
    assert all(hdr[norm_col[f]] == f"{f} Hz" for f in FREQS) and hdr[19] == "Normalized" and hdr[28] == "Stdev"
    rows = [dict(fid=int(r[0]), name=str(r[1]), **{f"norm_{f}": float(r[norm_col[f]]) for f in FREQS},
                 **{f"sdnorm_{f}": float(r[norm_col[f] + 9]) for f in FREQS}) for r in t[1:]]   # Stdev 块 = 试次标准差 / 基线（已核对）
    return rows, S


def type_members(fid2i):
    ann = pd.read_csv(ANNOT, sep="\t", low_memory=False, usecols=["root_id", "cell_type", "side"]).drop_duplicates("root_id")
    ann = ann[ann.root_id.isin(fid2i)]
    out = {}
    for t, cts in TYPES.items():
        m = ann[ann.cell_type.isin(cts)]
        out[t] = sorted(int(x) for x in m.root_id)
        assert PAPER_SINGLE[t] in out[t], (t, out[t])
    return out


# ---------------------------------------------------------------------------
def patterns(n_grn):
    """每个实现 r：(GRN, 步) 上的均匀随机数；频率 f 下 u < f·dt 即放电。"""
    U = np.empty((R_MAX, n_grn, TRIAL_STEPS), np.float32)
    for r in range(R_MAX):
        U[r] = np.random.default_rng(SEED + r).random((n_grn, TRIAL_STEPS), dtype=np.float32)
    idx, steps = [], []
    for fi, f in enumerate(FREQS):
        p = f * DT_MS * 1e-3
        for r in range(R_MAX):
            g, s = np.nonzero(U[r] < p)
            idx.append((fi * R_MAX + r) * n_grn + g)
            steps.append(s)
    return np.concatenate(idx), np.concatenate(steps), len(FREQS) * R_MAX * n_grn


class Screen:
    def __init__(self):
        import brian2 as b2
        from brian2 import ms, mV, Network, Synapses, SpikeGeneratorGroup, StateMonitor, TimedArray
        sys.path.insert(0, str(REPO / "code" / "paper-phil-drosophila"))
        from model import create_model, default_params

        if getattr(b2.device, "build_on_run", None) is not None and getattr(Screen, "_built_once", False):
            b2.device.reinit(); b2.device.activate()      # 同一进程里第二次建网必须先重置设备（run_experiment.py 也是这样做的）
        Screen._built_once = True
        self.b2 = b2
        self.fids, self.fid2i = load_ids()
        self.N = len(self.fids)
        self.sugar = [self.fid2i[f] for f in sugar_ids()]
        src_idx, src_steps, self.n_src = patterns(len(self.sugar))
        b2.set_device("cpp_standalone", build_on_run=False, directory=str(BUILD))
        b2.prefs.devices.cpp_standalone.openmp_threads = 0
        b2.prefs.devices.cpp_standalone.extra_make_args_unix = ["-j4"]   # 见 AGENTS.md：不限并行的 make 曾导致死机
        b2.defaultclock.dt = DT_MS * ms
        seg_dt = SEG_STEPS * DT_MS * ms
        params = dict(default_params)
        self.gate = TimedArray(np.zeros((K, N_SLOTS)), dt=seg_dt, name="gate")
        self.ingate = TimedArray(np.zeros((K, self.n_src)), dt=seg_dt, name="ingate")
        params["gate"] = self.gate
        # 官方 poi() 只把**本次实验真正被刺激**的神经元的不应期设为 0。本框架把全部候选刺激
        # 神经元一次性编译进来，如果照旧一律置 0，那些本段没被刺激的候选（若是中间神经元）
        # 就会以 rfc=0 参与全脑动力学——是个偏离。RFC_GATE=True 时不应期也逐段门控：
        # 只有本段真的被刺激的那些置 0，其余保持 t_rfc。糖/水/JON 的筛选里候选全是感觉神经元
        # 且每段都全体受刺激，两种写法等价，所以保持默认 False，不动既有结果。
        if RFC_GATE:
            self.rfcon = TimedArray(np.zeros((K, len(self.sugar) + 1)), dt=seg_dt, name="rfcon")
            params["rfcon"] = self.rfcon
        params["eqs"] = default_params["eqs"] + "slot : integer (constant)\nblocked : 1\nnspk : 1\n"
        if RFC_GATE:
            params["eqs"] += "sslot : integer (constant)\n"
        params["eq_th"] = f"v > v_th and blocked < 0.5 and (t_in_timesteps % {SEG_STEPS}) < {TRIAL_STEPS}"
        params["eq_rst"] = default_params["eq_rst"] + "; nspk += 1"
        self.params = params
        t0 = time.time()
        neu, syn, self._unused_spk_mon = create_model(str(PATH_COMP), str(PATH_CON), params)   # 不放进网络，但要留住引用，否则 device.run 遇到已回收的弱引用会报错
        rfc = np.full(self.N, float(params["t_rfc"] / ms))
        if not RFC_GATE:
            rfc[self.sugar] = 0.0                                          # 与官方 poi() 相同：受刺激神经元无不应期
        neu.rfc = rfc * ms
        self.t_rfc_ms = float(params["t_rfc"] / ms)
        if RFC_GATE:
            sslot = np.zeros(self.N, np.int32)
            sslot[self.sugar] = np.arange(1, len(self.sugar) + 1)
            neu.sslot = sslot
        neu.slot = np.zeros(self.N, dtype=np.int32)
        neu.blocked = 0
        neu.nspk = 0
        reset_code = f"v = v_0\ng = 0*mV\nblocked = gate(t + {GUARD_MS}*ms, slot)"
        if RFC_GATE:
            reset_code += f"\nrfc = (1 - rfcon(t + {GUARD_MS}*ms, sslot)) * {self.t_rfc_ms}*ms"
        neu.run_regularly(reset_code, dt=seg_dt, when="start", name="segment_reset")
        sgg = SpikeGeneratorGroup(self.n_src, src_idx, src_steps * DT_MS * ms, period=seg_dt, name="sugar_patterns")
        ps = Synapses(sgg, neu, "w_in : volt (constant)\non : 1", on_pre="v_post += w_in * on", namespace={"ingate": self.ingate}, name="sugar_input")
        ps.connect(i=np.arange(self.n_src), j=np.tile(self.sugar, self.n_src // len(self.sugar)))
        ps.w_in = params["w_syn"] * params["f_poi"]                        # 与官方 PoissonInput 的 weight 相同
        ps.on = 0
        ps.run_regularly(f"on = ingate(t + {GUARD_MS}*ms, i)", dt=seg_dt, when="start", name="input_switch")
        self.mon = StateMonitor(neu, "nspk", record=True, dt=seg_dt, when="start", name="segment_counts")
        self.neu, self.syn = neu, syn
        net = Network(neu, syn, sgg, ps, self.mon)
        net.run(K * seg_dt)
        b2.device.build(directory=str(BUILD), compile=True, run=False, clean=True)
        print(f"建模 + 编译 {time.time() - t0:.0f} s；输入源 {self.n_src} 个，输入脉冲 {len(src_idx)} 个", flush=True)

    def run_chunk(self, segs, extra_args=None):
        """segs: [(fi, r, (被沉默的模型下标, ...)), ...] 最多 K 个，不足补基线。返回 (段 × 神经元) 计数 int32 与用时。"""
        segs = list(segs) + [(0, 0, ())] * (K - len(segs))
        slots = {}
        for _, _, sil in segs:
            for n in sil:
                slots.setdefault(n, len(slots) + 1)
        assert len(slots) < N_SLOTS
        slot_arr = np.zeros(self.N, np.int32)
        for n, s in slots.items():
            slot_arr[n] = s
        gate = np.zeros((K, N_SLOTS))
        ingate = np.zeros((K, self.n_src))
        G = len(self.sugar)
        for k, (fi, r, sil) in enumerate(segs):
            for n in sil:
                gate[k, slots[n]] = 1.0
            ingate[k, (fi * R_MAX + r) * G:(fi * R_MAX + r + 1) * G] = 1.0
        args = {self.neu.slot: slot_arr, self.gate: gate, self.ingate: ingate}
        args.update(extra_args or {})
        t0 = time.time()
        self.b2.device.run(directory=str(BUILD), with_output=False, run_args=args)
        wall = time.time() - t0
        for name in list(self.b2.device.run_args_arrays):                  # 运行参数文件按内容哈希命名，用完即删
            (BUILD / "static_arrays" / name).unlink(missing_ok=True)
        C = np.asarray(self.mon.nspk)                                      # (神经元, K) 每段开头的累计数
        fin = np.asarray(self.neu.nspk)
        counts = np.diff(np.c_[C, fin], axis=1).T.astype(np.int32)         # (K, 神经元)
        return counts, wall


def save_chunk(path, keys, counts, wall):
    ptr, idx, cnt = [0], [], []
    for row in counts[:len(keys)]:
        nz = np.nonzero(row)[0]
        idx.append(nz.astype(np.int32)); cnt.append(row[nz].astype(np.int32)); ptr.append(ptr[-1] + len(nz))
    np.savez_compressed(path, keys=json.dumps(keys), ptr=np.array(ptr), idx=np.concatenate(idx), cnt=np.concatenate(cnt), wall=wall)


def load_chunk(path, N):
    z = np.load(path)
    keys = [tuple([k[0], k[1], tuple(k[2])]) for k in json.loads(str(z["keys"]))]
    rows = []
    for s in range(len(keys)):
        v = np.zeros(N, np.int32)
        a, b = z["ptr"][s], z["ptr"][s + 1]
        v[z["idx"][a:b]] = z["cnt"][a:b]
        rows.append(v)
    return keys, np.array(rows), float(z["wall"])


def chunk_keys(path):
    return [(k[0], k[1], tuple(k[2])) for k in json.loads(str(np.load(path)["keys"]))]


def chunk_summary(path, watch):
    """不展开成稠密矩阵：每段只取 watch 里神经元的计数和活跃神经元数。"""
    z = np.load(path)
    keys = [(k[0], k[1], tuple(k[2])) for k in json.loads(str(z["keys"]))]
    out = []
    for s in range(len(keys)):
        a, b = z["ptr"][s], z["ptr"][s + 1]
        d = dict(zip(z["idx"][a:b].tolist(), z["cnt"][a:b].tolist()))
        out.append(dict(n_active=int(b - a), **{w: int(d.get(n, 0)) for w, n in watch.items()}))
    return keys, out


def key(fi, r, sil):
    return [int(fi), int(r), sorted(int(n) for n in sil)]


# ---------------------------------------------------------------------------
def cmd_run():
    OUT.mkdir(parents=True, exist_ok=True); CHUNKS.mkdir(exist_ok=True)
    rows_1c, _ = paper_table_1c()
    fids, fid2i = load_ids()
    members = type_members(fid2i)
    mn9 = fid2i[MN9]
    sc = Screen()
    N = sc.N

    # 1) 基线：2 个频率 × 8 个实现，外加 4 段重复（确定性核对 V1）
    base_path = CHUNKS / "baseline.npz"
    base_segs = [(fi, r, ()) for fi in range(len(FREQS)) for r in range(R_MAX)] + [(0, 0, ()), (1, 0, ()), (0, 1, ()), (1, 1, ())]
    if not base_path.exists():
        counts, wall = sc.run_chunk(base_segs)
        save_chunk(base_path, [key(*s) for s in base_segs], counts, wall)
    _, bc, bwall = load_chunk(base_path, N)
    sec_per_seg = bwall / K
    base = {(fi, r): bc[fi * R_MAX + r] for fi in range(len(FREQS)) for r in range(R_MAX)}
    v1 = all(np.array_equal(bc[16 + j], base[(fi, r)]) for j, (fi, r, _) in enumerate(base_segs[16:]))
    print(f"基线：每段 {sec_per_seg:.2f} s；V1 同一实现重复运行逐位相同：{v1}", flush=True)
    for fi, f in enumerate(FREQS):
        m = [int(base[(fi, r)][mn9]) for r in range(R_MAX)]
        act = [int((base[(fi, r)] > 0).sum()) for r in range(R_MAX)]
        print(f"  {f} Hz：MN9 各实现 {m}；活跃神经元 {act}", flush=True)

    # 2) 验证：V2 沉默基线不放电的神经元 = 基线；V3 阻断放电 = 传出权重置 0（逐位）
    val_path, v3_path = CHUNKS / "validation.npz", CHUNKS / "validation_weights.npz"
    roundup, g2n, phantom = fid2i[PAPER_SINGLE["Roundup"]], fid2i[PAPER_SINGLE["G2N-1"]], fid2i[PAPER_SINGLE["Phantom"]]
    p_ids = [fid2i[r["fid"]] for r in rows_1c if r["fid"] in fid2i and r["fid"] != MN9]
    silent = next(n for n in p_ids if base[(0, 0)][n] == 0)
    val_segs = [(0, 0, ()), (0, 0, (silent,)), (0, 0, (roundup,)), (0, 1, (roundup,)), (1, 0, (roundup,)), (0, 0, (g2n,)), (0, 0, (phantom,)),
                (0, 0, tuple(fid2i[f] for f in members["Roundup"]))] + [(0, r, ()) for r in range(2, 8)] + [(1, r, ()) for r in range(1, 7)]
    if not val_path.exists():
        counts, wall = sc.run_chunk(val_segs)
        save_chunk(val_path, [key(*s) for s in val_segs], counts, wall)
    if not v3_path.exists():
        from brian2 import mV
        con = pd.read_parquet(PATH_CON, columns=["Presynaptic_Index", "Excitatory x Connectivity"])
        w = con["Excitatory x Connectivity"].to_numpy(dtype=float) * float(sc.params["w_syn"] / mV)
        n_zero = int((con["Presynaptic_Index"].to_numpy() == roundup).sum())
        w[con["Presynaptic_Index"].to_numpy() == roundup] = 0.0
        del con
        segs_open = [(fi, r, ()) for fi, r, _ in val_segs]
        counts, wall = sc.run_chunk(segs_open, extra_args={sc.syn.w: w * mV})
        del w
        save_chunk(v3_path, [key(*s) for s in segs_open], counts, wall)
        print(f"V3：Roundup_l 传出突触 {n_zero} 条置 0 的对照块已跑完", flush=True)
    _, vc, _ = load_chunk(val_path, N)
    _, wc, _ = load_chunk(v3_path, N)
    others = np.ones(N, bool); others[roundup] = False
    v2 = bool(np.array_equal(vc[1], vc[0]) and np.array_equal(vc[0], base[(0, 0)]))
    v3 = [bool(np.array_equal(vc[k][others], wc[k][others])) for k in (2, 3, 4)]
    v1b = all(np.array_equal(vc[8 + j], base[(0, r)]) for j, r in enumerate(range(2, 8))) and \
        all(np.array_equal(vc[14 + j], base[(1, r)]) for j, r in enumerate(range(1, 7)))
    validation = dict(V1_repeat_identical=bool(v1 and v1b), V2_silencing_silent_neuron_equals_baseline=v2,
                      V3_block_equals_zero_weights=v3, silent_neuron=int(fids[silent]),
                      roundup_mn9_blocked=[int(vc[k][mn9]) for k in (2, 3, 4)], roundup_mn9_zero_weights=[int(wc[k][mn9]) for k in (2, 3, 4)])
    print("验证：", validation, flush=True)
    (OUT / "validation.json").write_text(json.dumps(validation, indent=1))
    if not (validation["V1_repeat_identical"] and v2 and all(v3)):
        raise SystemExit("验证未通过，停止")

    # 3) 计划：T、P（两个频率）、E（50 Hz），只模拟“被沉默者在该实现基线里放过电”的段
    def plan_for(R):
        segs = {}
        def add(fi, r, sil):
            if any(base[(fi, r)][n] > 0 for n in sil):
                segs[json.dumps(key(fi, r, sil))] = (fi, r, tuple(sorted(sil)))
        for t, mem in members.items():
            for fi in range(len(FREQS)):
                for r in range(R):
                    add(fi, r, [fid2i[f] for f in mem])
        for fi in range(len(FREQS)):
            for n in p_ids:
                for r in range(R):
                    add(fi, r, [n])
        e_ids = sorted({int(n) for r in range(R) for n in np.nonzero(base[(0, r)])[0]} - {mn9})
        for n in e_ids:
            for r in range(R):
                add(0, r, [n])
        return list(segs.values()), e_ids
    R = R_MAX
    segs, e_ids = plan_for(R)
    while len(segs) * sec_per_seg / 60 > BUDGET_MIN and R > R_MIN:
        R -= 1
        segs, e_ids = plan_for(R)
    segs.sort(key=lambda s: (len(s[2]) == 1, s[0], s[2], s[1]))
    n_chunks = math.ceil(len(segs) / K)
    plan = dict(R=R, n_segments=len(segs), n_chunks=n_chunks, sec_per_seg=round(sec_per_seg, 3),
                projected_min=round(len(segs) * sec_per_seg / 60, 1), n_E=len(e_ids), n_P=len(p_ids),
                type_members={t: m for t, m in members.items()})
    (OUT / "plan.json").write_text(json.dumps(plan, indent=1))
    print("计划：", {k: v for k, v in plan.items() if k != "type_members"}, flush=True)

    # 4) 逐块运行
    t_start = time.time(); done = 0
    for c in range(n_chunks):
        path = CHUNKS / f"chunk_{c:04d}.npz"
        part = segs[c * K:(c + 1) * K]
        if path.exists() and chunk_keys(path) == [(fi, r, tuple(s)) for fi, r, s in part]:
            continue
        counts, wall = sc.run_chunk(part)
        save_chunk(path, [key(*s) for s in part], counts, wall)
        done += 1
        el = time.time() - t_start
        print(f"块 {c + 1}/{n_chunks}：{wall:.0f} s；本次已跑 {done} 块 {el / 60:.1f} min，预计还需 {el / done * (n_chunks - c - 1) / 60:.0f} min", flush=True)
    print("全部完成", flush=True)


def cmd_fill():
    """补跑：计划漏掉了“论文单个神经元不在补充表 1C 里”时 100 Hz 的单个沉默段（只有 Bract），比较 (b) 需要它们。设计与参数不变。"""
    fids, fid2i = load_ids()
    N = len(fids)
    plan = json.loads((OUT / "plan.json").read_text())
    R = plan["R"]
    _, bc, _ = load_chunk(CHUNKS / "baseline.npz", N)
    base = {(fi, r): bc[fi * R_MAX + r] for fi in range(len(FREQS)) for r in range(R_MAX)}
    have = set()
    for p in sorted(CHUNKS.glob("chunk_*.npz")) + [CHUNKS / "validation.npz"]:
        have.update(chunk_keys(p))
    need = []
    for t, mem in plan["type_members"].items():
        for fi in range(len(FREQS)):
            for sil in ([fid2i[PAPER_SINGLE[t]]], [fid2i[x] for x in mem]):
                for r in range(R):
                    k = (fi, r, tuple(sorted(sil)))
                    if any(base[(fi, r)][n] > 0 for n in sil) and k not in have and k not in need:
                        need.append(k)
    print("补跑段：", need, flush=True)
    if not need:
        return
    sc = Screen()
    for c in range(math.ceil(len(need) / K)):
        part = need[c * K:(c + 1) * K]
        counts, wall = sc.run_chunk(part)
        save_chunk(CHUNKS / f"chunk_fill_{c:04d}.npz", [key(*s) for s in part], counts, wall)
        print(f"补跑块 {c + 1}：{wall:.0f} s", flush=True)


# ---------------------------------------------------------------------------
def spearman(a, b):
    from scipy.stats import spearmanr
    r = spearmanr(a, b)
    return round(float(r.statistic if hasattr(r, "statistic") else r.correlation), 3)


def kappa(x, y):
    x, y = np.asarray(x, bool), np.asarray(y, bool)
    po = float((x == y).mean())
    pe = float(x.mean() * y.mean() + (1 - x.mean()) * (1 - y.mean()))
    return round((po - pe) / (1 - pe), 3) if pe < 1 else None


def cmd_analyze():
    plan = json.loads((OUT / "plan.json").read_text())
    R = plan["R"]
    fids, fid2i = load_ids()
    N = len(fids)
    mn9 = fid2i[MN9]
    rows_1c, S = paper_table_1c()
    members = plan["type_members"]
    # 读全部结果（基线保留全部神经元；其余每段只留 MN9 计数与活跃数）
    _, bc, _ = load_chunk(CHUNKS / "baseline.npz", N)
    base = {(fi, r): bc[fi * R_MAX + r] for fi in range(len(FREQS)) for r in range(R_MAX)}
    res = {}
    for p in sorted(CHUNKS.glob("chunk_*.npz")) + [CHUNKS / "validation.npz"]:
        keys, summ = chunk_summary(p, {"mn9": mn9})
        for k, v in zip(keys, summ):
            res.setdefault(k, v)
    ann = pd.read_csv(ANNOT, sep="\t", low_memory=False, usecols=["root_id", "cell_type", "side", "top_nt", "super_class"]).drop_duplicates("root_id").set_index("root_id")

    missing = []

    def mn9_counts(fi, sil):
        out, runaway = [], 0
        for r in range(R):
            if any(base[(fi, r)][n] > 0 for n in sil):
                k = (fi, r, tuple(sorted(sil)))
                if k not in res and PARTIAL:                               # 只用于跑完之前调试分析代码
                    missing.append(k)
                    v = dict(mn9=int(base[(fi, r)][mn9]), n_active=int((base[(fi, r)] > 0).sum()))
                else:
                    v = res[k]
                out.append(v["mn9"]); runaway += int(v["n_active"] >= RUNAWAY_ACTIVE)
            else:
                out.append(int(base[(fi, r)][mn9])); runaway += int((base[(fi, r)] > 0).sum() >= RUNAWAY_ACTIVE)
        return out, runaway

    base_mn9 = {fi: [int(base[(fi, r)][mn9]) for r in range(R)] for fi in range(len(FREQS))}

    def ratio(fi, sil):
        m, run = mn9_counts(fi, sil)
        b = sum(base_mn9[fi])
        d = np.array(m) - np.array(base_mn9[fi])
        full = sum(m) / b
        loo = [(sum(m) - m[j]) / (b - base_mn9[fi][j]) for j in range(R)]       # 探索性（跑完前加的）：去掉任一个输入实现后判定是否不变
        return dict(ratio=round(full, 4), mn9=m, runaway_segments=run,
                    paired_diff_mean=round(float(d.mean()), 2), paired_diff_sd=round(float(d.std(ddof=1)), 2),
                    loo_same_call=bool(all((x <= CALL) == (full <= CALL) for x in loo)))

    def label(fid):
        if fid not in ann.index:
            return dict(cell_type=None, side=None, nt=None)
        a = ann.loc[fid]
        return dict(cell_type=a.cell_type if isinstance(a.cell_type, str) else None, side=a.side, nt=a.top_nt if isinstance(a.top_nt, str) else None,
                    super_class=a.super_class)

    # V4：基线 MN9 与论文表 1A 的均值 ± SD
    t1a = sheet(S, "Supplemental Table 1A")
    row = next(r for r in t1a if str(r[0]) == str(MN9))
    col = {f: t1a[0].index(f"sugarR_{f}Hz") for f in FREQS}
    sd_col = {f: len(t1a[0]) - 1 - t1a[0][::-1].index(f"sugarR_{f}Hz") for f in FREQS}
    v4 = {f"{f}Hz": dict(ours=base_mn9[fi], ours_mean=round(float(np.mean(base_mn9[fi])), 2), ours_sd=round(float(np.std(base_mn9[fi], ddof=1)), 2),
                         paper_mean=round(float(row[col[f]]), 2), paper_sd=round(float(row[sd_col[f]]), 2)) for fi, f in enumerate(FREQS)}
    active = {f"{f}Hz": [int((base[(fi, r)] > 0).sum()) for r in range(R)] for fi, f in enumerate(FREQS)}

    # (a) P：与论文 1C 比较
    comp = {}
    for fi, f in enumerate(FREQS):
        items = []
        for r1 in rows_1c:
            if r1["fid"] not in fid2i or r1["fid"] == MN9:
                continue
            q = ratio(fi, [fid2i[r1["fid"]]])
            se = r1[f"sdnorm_{f}"] / math.sqrt(30)                              # 论文每个条件 30 个试次
            items.append(dict(fid=str(r1["fid"]), name=r1["name"], paper=round(r1[f"norm_{f}"], 4), paper_se=round(se, 4),
                              paper_call_clear=bool(abs(r1[f"norm_{f}"] - CALL) > 2 * se),
                              ours=q["ratio"], ours_loo_same_call=q["loo_same_call"], runaway=q["runaway_segments"], **label(r1["fid"])))
        ours = np.array([x["ours"] for x in items]); paper = np.array([x["paper"] for x in items])
        dis = [x for x in items if (x["ours"] <= CALL) != (x["paper"] <= CALL)]
        comp[f"{f}Hz"] = dict(n=len(items), spearman=spearman(ours, paper), pearson=round(float(np.corrcoef(ours, paper)[0, 1]), 3),
                              calls_ours=int((ours <= CALL).sum()), calls_paper=int((paper <= CALL).sum()), calls_both=int(((ours <= CALL) & (paper <= CALL)).sum()),
                              call_agreement=round(float(((ours <= CALL) == (paper <= CALL)).mean()), 3), kappa=kappa(ours <= CALL, paper <= CALL),
                              median_abs_diff=round(float(np.median(np.abs(ours - paper))), 3),
                              n_disagreements=len(dis), n_disagreements_both_clear=int(sum(x["paper_call_clear"] and x["ours_loo_same_call"] for x in dis)),
                              disagreements=dis, items=items)

    # (b) 10 个类型 vs 实验
    t2 = sheet(S, "Supplemental Table 2")
    paper_t2 = {r[0]: float(r[6]) for r in t2[1:] if len(r) > 6 and r[6] != ""}
    types = {}
    for t in TYPES:
        e = {}
        for fi, f in enumerate(FREQS):
            single = ratio(fi, [fid2i[PAPER_SINGLE[t]]])
            both = ratio(fi, [fid2i[x] for x in members[t]])
            e[f"{f}Hz"] = dict(single=single, bilateral=both)
        types[t] = dict(members=[str(x) for x in members[t]], experiment_required=EXPERIMENT_REQUIRED[t],
                        paper_single_ratio_50Hz=paper_t2.get(t), **e)
    score = {}
    for name, get in [("paper_single_50Hz", lambda t: types[t]["paper_single_ratio_50Hz"]),
                      ("ours_single_50Hz", lambda t: types[t]["50Hz"]["single"]["ratio"]),
                      ("ours_bilateral_50Hz", lambda t: types[t]["50Hz"]["bilateral"]["ratio"]),
                      ("ours_single_100Hz", lambda t: types[t]["100Hz"]["single"]["ratio"]),
                      ("ours_bilateral_100Hz", lambda t: types[t]["100Hz"]["bilateral"]["ratio"])]:
        correct = [t for t in TYPES if (get(t) <= CALL) == EXPERIMENT_REQUIRED[t]]
        score[name] = dict(correct=len(correct), of=len(TYPES), correct_types=correct,
                           predicted_required=[t for t in TYPES if get(t) <= CALL])

    # (c) E：穷举 + 连线指标
    e_rows = []
    fi = 0
    e_ids = sorted({int(n) for r in range(R) for n in np.nonzero(base[(0, r)])[0]} - {mn9})
    rate = {n: float(np.mean([base[(0, r)][n] for r in range(R)])) for n in e_ids}
    for n in e_ids:
        q = ratio(0, [n])
        e_rows.append(dict(fid=str(fids[n]), idx=n, rate_hz=round(rate[n], 2), ratio=q["ratio"], runaway=q["runaway_segments"],
                           paired_diff_sd=q["paired_diff_sd"], in_paper_200=any(r1["fid"] == int(fids[n]) for r1 in rows_1c), **label(int(fids[n]))))
    import scipy.sparse as sp
    con = pd.read_parquet(PATH_CON, columns=["Presynaptic_Index", "Postsynaptic_Index", "Excitatory x Connectivity"])
    A = np.array(sorted(set(e_ids) | {mn9}))
    pos = -np.ones(N, np.int64); pos[A] = np.arange(len(A))
    m = (pos[con.Presynaptic_Index.to_numpy()] >= 0) & (pos[con.Postsynaptic_Index.to_numpy()] >= 0)
    sub = con[m]
    scale = 0.275 / 7.0
    M = sp.csr_matrix((sub["Excitatory x Connectivity"].to_numpy(float) * scale,
                       (pos[sub.Presynaptic_Index.to_numpy()], pos[sub.Postsynaptic_Index.to_numpy()])), shape=(len(A), len(A)))
    to_mn9 = con[(con.Postsynaptic_Index == mn9)].groupby("Presynaptic_Index")["Excitatory x Connectivity"].sum()
    col1 = M[:, pos[mn9]].toarray().ravel()
    col2 = M @ col1
    col3 = M @ col2
    for x in e_rows:
        n = x["idx"]
        x["G1_direct_syn_to_mn9"] = int(to_mn9.get(n, 0))
        x["G2_rate_x_direct"] = round(rate[n] * x["G1_direct_syn_to_mn9"], 3)
        x["G3_rate_x_paths123"] = round(rate[n] * float(col1[pos[n]] + col2[pos[n]] + col3[pos[n]]), 5)
    effect = np.array([1 - x["ratio"] for x in e_rows])
    top20 = set(np.argsort(-effect)[:20])
    graph = {}
    for g in ("G1_direct_syn_to_mn9", "G2_rate_x_direct", "G3_rate_x_paths123"):
        v = np.array([x[g] for x in e_rows], float)
        graph[g] = dict(spearman_vs_effect=spearman(v, effect), top20_overlap=len(top20 & set(np.argsort(-v)[:20])))
    # 探索性（跑完后才发现、事先没写的修正）：网络是确定性的，但对初值敏感，任何扰动都会让轨迹偏离，
    # 结果向“给定输入下的条件均值”回归。基线只是一次没被扰动的轨迹，所以配对比值有系统性偏低。
    # 用同一实现里“所有单个沉默条件的 MN9 中位数”当参照（筛选里常用的板内中位数归一化）重算一遍。
    null_med, null_ratio = {}, {}
    for fi, f in enumerate(FREQS):
        med = []
        for r in range(R):
            vals = [v["mn9"] for k, v in res.items() if k[0] == fi and k[1] == r and len(k[2]) == 1]
            med.append(float(np.median(vals)) if vals else float(base_mn9[fi][r]))
        null_med[f] = med
        null_ratio[f] = round(sum(med) / sum(base_mn9[fi]), 4)

    def ratio_corr(fi, sil):
        m, _ = mn9_counts(fi, sil)
        return round(sum(m) / sum(null_med[FREQS[fi]]), 4)

    expl = dict(note="事后加的偏差修正，不是事先写定的判据", null_median_mn9=null_med, null_over_baseline=null_ratio, by_freq={}, types={}, exhaustive_50Hz={})
    for fi, f in enumerate(FREQS):
        oc, pp = [], []
        for r1 in rows_1c:
            if r1["fid"] not in fid2i or r1["fid"] == MN9:
                continue
            oc.append(ratio_corr(fi, [fid2i[r1["fid"]]])); pp.append(r1[f"norm_{f}"])
        oc, pp = np.array(oc), np.array(pp)
        expl["by_freq"][f"{f}Hz"] = dict(spearman=spearman(oc, pp), pearson=round(float(np.corrcoef(oc, pp)[0, 1]), 3),
                                         calls_ours=int((oc <= CALL).sum()), calls_paper=int((pp <= CALL).sum()),
                                         call_agreement=round(float(((oc <= CALL) == (pp <= CALL)).mean()), 3), kappa=kappa(oc <= CALL, pp <= CALL),
                                         median_abs_diff=round(float(np.median(np.abs(oc - pp))), 3))
    for t in TYPES:
        expl["types"][t] = {f"{f}Hz": dict(single=ratio_corr(fi, [fid2i[PAPER_SINGLE[t]]]), bilateral=ratio_corr(fi, [fid2i[x] for x in members[t]]))
                            for fi, f in enumerate(FREQS)}
    for name, get in [("ours_single_50Hz", lambda t: expl["types"][t]["50Hz"]["single"]), ("ours_bilateral_50Hz", lambda t: expl["types"][t]["50Hz"]["bilateral"]),
                      ("ours_single_100Hz", lambda t: expl["types"][t]["100Hz"]["single"]), ("ours_bilateral_100Hz", lambda t: expl["types"][t]["100Hz"]["bilateral"])]:
        correct = [t for t in TYPES if (get(t) <= CALL) == EXPERIMENT_REQUIRED[t]]
        expl.setdefault("experiment_score", {})[name] = dict(correct=len(correct), of=len(TYPES), correct_types=correct,
                                                             predicted_required=[t for t in TYPES if get(t) <= CALL])
    corr_e = [dict(fid=x["fid"], cell_type=x.get("cell_type"), nt=x.get("nt"), rate_hz=x["rate_hz"], ratio_corrected=ratio_corr(0, [x["idx"]]),
                   ratio_vs_baseline=x["ratio"], in_paper_200=x["in_paper_200"]) for x in e_rows]
    expl["exhaustive_50Hz"] = dict(n_required=int(sum(x["ratio_corrected"] <= CALL for x in corr_e)),
                                   n_increase_ge_20pct=int(sum(x["ratio_corrected"] >= 1.2 for x in corr_e)),
                                   required=sorted([x for x in corr_e if x["ratio_corrected"] <= CALL], key=lambda x: x["ratio_corrected"]))

    e_sorted = sorted(e_rows, key=lambda x: x["ratio"])
    for x in e_rows:
        x.pop("idx")
    summary = dict(design=dict(freqs=FREQS, R=R, call_threshold=CALL, trial_s=TRIAL_STEPS * DT_MS / 1000, runaway_active=RUNAWAY_ACTIVE),
                   plan={k: v for k, v in plan.items() if k != "type_members"},
                   validation=json.loads((OUT / "validation.json").read_text()),
                   V4_baseline_vs_paper=v4, active_neurons=active,
                   paper_comparison={f: {k: v for k, v in d.items() if k != "items"} for f, d in comp.items()},
                   types=types, experiment_score=score,
                   exhaustive_50Hz=dict(n=len(e_rows), required=[x for x in e_sorted if x["ratio"] <= CALL],
                                        n_required=int(sum(x["ratio"] <= CALL for x in e_rows)),
                                        n_required_not_in_paper_200=int(sum(x["ratio"] <= CALL and not x["in_paper_200"] for x in e_rows)),
                                        n_increase_ge_20pct=int(sum(x["ratio"] >= 1.2 for x in e_rows)),
                                        top_increase=sorted(e_rows, key=lambda x: -x["ratio"])[:15], graph_baselines=graph),
                   exploratory_null_normalized=expl)
    if PARTIAL:
        print(f"调试模式：{len(missing)} 个段缺失，用基线代替；结果写到 summary_partial.json，不能当结论")
        (OUT / "summary_partial.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
        return
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    (OUT / "exhaustive_50Hz.json").write_text(json.dumps(e_sorted, ensure_ascii=False, indent=0))
    (OUT / "paper_items.json").write_text(json.dumps({f: d["items"] for f, d in comp.items()}, ensure_ascii=False))
    print(json.dumps({k: summary[k] for k in ("validation", "V4_baseline_vs_paper", "active_neurons", "paper_comparison", "experiment_score")},
                     ensure_ascii=False, indent=1)[:6000])
    print("穷举：", {k: v for k, v in summary["exhaustive_50Hz"].items() if k in ("n", "n_required", "n_required_not_in_paper_200", "n_increase_ge_20pct", "graph_baselines")})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "fill", "analyze"])
    ap.add_argument("--partial", action="store_true")
    a = ap.parse_args()
    PARTIAL = a.partial
    dict(run=cmd_run, fill=cmd_fill, analyze=cmd_analyze)[a.cmd]()
