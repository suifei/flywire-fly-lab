"""
looming → 下行神经元 连接组子回路：构建 + 参考仿真器（numpy）+ 与全脑 Brian2 结果对比 + 导出给浏览器。

模型与 Shiu et al. / eonsystemspbc/fly-brain 的 Brian2 实现逐项对齐：
  dv/dt = (v0 - v + g)/t_mbr,  dg/dt = -g/tau   （不应期内两者冻结）
  阈值 v > -45 mV → 重置 v = -52 mV、g = 0，不应期 2.2 ms（被刺激神经元不应期 0）
  突触 on_pre: g += w_syn * (Excitatory x Connectivity)，延迟 1.8 ms（18 步）
  Poisson 刺激: 每个事件 v += w_syn * f_poi = 68.75 mV
  dt = 0.1 ms，线性 ODE 精确离散化；每步顺序：状态更新 → 阈值 → 突触/Poisson → 重置（Brian2 默认调度）

子回路选择：在 突触数 ≥ wmin 的边上，满足 “离 LC4/LPLC2 的跳数 + 到目标下行神经元的跳数 ≤ K” 的所有神经元，
再取这些神经元之间的全部连接（不再按 wmin 过滤）。回路外神经元被当作永远不放电。

用法（brain-fly-cpu 环境）：
  python dodge/subcircuit.py compare            # 各 (wmin, K) 组合 vs 全脑参考（results/dodge_ref/*）
  python dodge/subcircuit.py export --wmin 3 --K 3
"""
import argparse
import base64
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parent.parent
PATH_COMP = ROOT / "external/fly-brain/data/2025_Completeness_783.csv"
PATH_CON = ROOT / "external/fly-brain/data/2025_Connectivity_783.parquet"
PATH_ANN = ROOT / "external/flywire_annotations/Supplemental_file1_neuron_annotations.tsv"

P = dict(dt=0.1, v0=-52.0, vrst=-52.0, vth=-45.0, t_mbr=20.0, tau=5.0, t_rfc=2.2, t_dly=1.8, w_syn=0.275, f_poi=250)
TARGETS = [("DNa01", "left"), ("DNa01", "right"), ("DNa02", "left"), ("DNa02", "right"), ("DNp01", "left"), ("DNp01", "right")]
INPUTS = [("LC4", "left"), ("LC4", "right"), ("LPLC2", "left"), ("LPLC2", "right")]

# 参考实验：results/dodge_ref/<name>，由 run_experiment.py 生成（brian2，0.5 s × 4 trial）
REFS = {
    "LC4_L_100": ({("LC4", "left"): 100}, 0.5),
    "LPLC2_L_100": ({("LPLC2", "left"): 100}, 0.5),
    "LOOM_L_100": ({("LC4", "left"): 100, ("LPLC2", "left"): 100}, 0.5),
    "LOOM_R_100": ({("LC4", "right"): 100, ("LPLC2", "right"): 100}, 0.5),
    "LOOM_L_40": ({("LC4", "left"): 40, ("LPLC2", "left"): 40}, 0.5),
}


def load():
    ann = pd.read_csv(PATH_ANN, sep="\t", low_memory=False, usecols=["root_id", "cell_type", "side", "super_class"])
    ann = ann.drop_duplicates("root_id").set_index("root_id")
    comp = pd.read_csv(PATH_COMP, index_col=0)
    fids = comp.index.to_numpy(dtype=np.int64)
    fid2i = {int(f): i for i, f in enumerate(fids)}
    con = pd.read_parquet(PATH_CON, columns=["Presynaptic_Index", "Postsynaptic_Index", "Connectivity", "Excitatory x Connectivity"])
    return ann, fids, fid2i, con


def group_idx(ann, fid2i, ctype, side):
    m = (ann.cell_type == ctype) & (ann.side == side)
    return sorted(fid2i[int(r)] for r in ann.index[m] if int(r) in fid2i)


def bfs_hops(A, sources, limit=6):
    dist = np.full(A.shape[0], np.inf)
    frontier = np.zeros(A.shape[0], bool); frontier[sources] = True
    dist[frontier] = 0
    for h in range(1, limit + 1):
        nxt = ((A.T @ frontier.astype(np.float32)) > 0) & np.isinf(dist)
        if not nxt.any():
            break
        dist[nxt] = h
        frontier = nxt
    return dist


class Subcircuit:
    def __init__(self, ann, fids, fid2i, con, wmin, K):
        n = len(fids)
        self.groups_full = {f"{t}_{s}": group_idx(ann, fid2i, t, s) for t, s in INPUTS + TARGETS}
        S = sum((self.groups_full[f"{t}_{s}"] for t, s in INPUTS), [])
        T = sum((self.groups_full[f"{t}_{s}"] for t, s in TARGETS), [])
        pre, post = con.Presynaptic_Index.to_numpy(), con.Postsynaptic_Index.to_numpy()
        strong = con.Connectivity.to_numpy() >= wmin
        A = sp.csr_matrix((np.ones(strong.sum(), np.float32), (pre[strong], post[strong])), shape=(n, n))
        dS, dT = bfs_hops(A, S), bfs_hops(A.T.tocsr(), T)
        sel = np.union1d(np.where(dS + dT <= K)[0], np.array(S + T))
        self.sel = sel                                    # 全脑索引
        loc = np.full(n, -1); loc[sel] = np.arange(len(sel))
        e = (loc[pre] >= 0) & (loc[post] >= 0)
        self.pre, self.post = loc[pre[e]], loc[post[e]]
        self.w = con["Excitatory x Connectivity"].to_numpy()[e].astype(np.float32) * P["w_syn"]
        order = np.argsort(self.pre, kind="stable")        # 按突触前排序 → CSR，便于事件驱动传播
        self.pre, self.post, self.w = self.pre[order], self.post[order], self.w[order]
        self.indptr = np.searchsorted(self.pre, np.arange(len(sel) + 1)).astype(np.int32)
        self.n = len(sel)
        self.groups = {k: loc[v].tolist() for k, v in self.groups_full.items()}
        self.fids = fids[sel]
        self.hops_in, self.hops_out = dS[sel], dT[sel]
        self.wmin, self.K = wmin, K

    def simulate(self, rates, t_run_s, trials=4, seed=0, silence=()):
        """rates: {(type, side): Hz}；返回 {目标名: 平均发放率 Hz}，以及每个 trial 的总 spike 数。"""
        dt = P["dt"]; steps = int(round(t_run_s * 1000 / dt)); D = int(round(P["t_dly"] / dt))
        a = np.exp(-dt / P["t_mbr"]); b = np.exp(-dt / P["tau"]); c = P["tau"] / (P["tau"] - P["t_mbr"]) * (b - a)
        rng = np.random.default_rng(seed)
        stim_idx = np.concatenate([np.array(self.groups[f"{t}_{s}"]) for (t, s) in rates]) if rates else np.array([], int)
        stim_p = np.concatenate([np.full(len(self.groups[f"{t}_{s}"]), r * dt / 1000) for (t, s), r in rates.items()]) if rates else np.array([])
        rfc_steps = np.full(self.n, int(round(P["t_rfc"] / dt))); rfc_steps[stim_idx] = 0
        w = self.w.copy()
        for g in silence:  # 与官方一致：沉默 = 该组神经元的传出突触置 0
            for i in self.groups[g]:
                w[self.indptr[i]:self.indptr[i + 1]] = 0
        counts = np.zeros(self.n); total = []
        for tr in range(trials):
            v = np.full(self.n, P["v0"]); g = np.zeros(self.n)
            last = np.full(self.n, -10**9)
            ring = np.zeros((D, self.n), np.float32); spikes_total = 0
            for s in range(steps):
                active = (s - last) >= rfc_steps                 # 非不应期
                v = np.where(active, P["v0"] + (v - P["v0"]) * a + g * c, v)
                g = np.where(active, g * b, g)
                fired = np.where(active & (v > P["vth"]))[0]
                g += ring[s % D]; ring[s % D] = 0               # 18 步前发出的 spike 现在到达
                if len(stim_idx):
                    hit = stim_idx[rng.random(len(stim_idx)) < stim_p]
                    np.add.at(v, hit, P["w_syn"] * P["f_poi"])
                if len(fired):
                    spikes_total += len(fired); counts[fired] += 1
                    starts, ends = self.indptr[fired], self.indptr[fired + 1]
                    idx = np.concatenate([np.arange(st, en) for st, en in zip(starts, ends)])
                    if len(idx):
                        np.add.at(ring[s % D], self.post[idx], w[idx])   # s%D 槽位在 D 步后被读取
                    v[fired] = P["vrst"]; g[fired] = 0; last[fired] = s
            total.append(spikes_total)
        rate = counts / (trials * t_run_s)
        out = {f"{t}_{s}": float(rate[self.groups[f"{t}_{s}"]].mean()) for t, s in TARGETS}
        return out, total, rate


def full_brain_ref(ann, name):
    df = pd.read_csv(ROOT / "results/dodge_ref" / name / "rates.csv", index_col=0)
    col = [c for c in df.columns if c.startswith("baseline")][0]
    res = {}
    for t, s in TARGETS:
        rid = ann.index[(ann.cell_type == t) & (ann.side == s)]
        res[f"{t}_{s}"] = float(df[col].reindex(rid).fillna(0).mean())
    return res, df[col]


def cmd_compare(a):
    ann, fids, fid2i, con = load()
    refs = {k: full_brain_ref(ann, k) for k in REFS}
    rows = []
    for wmin, K in [(10, 3), (5, 3), (3, 3), (5, 4)]:
        t0 = time.time(); sc = Subcircuit(ann, fids, fid2i, con, wmin, K)
        print(f"\n### wmin={wmin} K={K}: {sc.n} 神经元, {len(sc.w)} 连接 (构建 {time.time() - t0:.1f}s)", flush=True)
        for name, (rates, T) in REFS.items():
            t0 = time.time(); sub, tot, _ = sc.simulate(rates, T, trials=4, seed=1)
            ref, _ = refs[name]
            err = np.mean([abs(sub[k] - ref[k]) for k in sub])
            rows.append(dict(wmin=wmin, K=K, n=sc.n, cond=name, mae_hz=err, **{f"sub_{k}": v for k, v in sub.items()}, **{f"ref_{k}": v for k, v in ref.items()}))
            print(f"  {name:12s} 全脑 " + " ".join(f"{k.replace('_left','L').replace('_right','R')}={ref[k]:5.1f}" for k in ref)
                  + f"\n  {'':12s} 子回路 " + " ".join(f"{k.replace('_left','L').replace('_right','R')}={sub[k]:5.1f}" for k in sub)
                  + f"   MAE={err:.1f}Hz ({time.time() - t0:.0f}s)", flush=True)
    out = ROOT / "results/dodge_ref/subcircuit_vs_fullbrain.csv"
    pd.DataFrame(rows).to_csv(out, index=False); print("\n写入", out)


def b64(arr):
    return base64.b64encode(np.ascontiguousarray(arr).tobytes()).decode()


def cmd_export(a):
    ann, fids, fid2i, con = load()
    sc = Subcircuit(ann, fids, fid2i, con, a.wmin, a.K)
    meta = ann.reindex(sc.fids)
    types = meta.cell_type.fillna("?").tolist(); sides = meta.side.fillna("?").tolist()
    supers = meta.super_class.fillna("?").tolist()
    # 各目标/输入组在全脑参考中的发放率，供页面上的“子回路 vs 全脑”对照图
    cmp_path = ROOT / "results/dodge_ref/subcircuit_vs_fullbrain.csv"
    validation = pd.read_csv(cmp_path).query("wmin == @a.wmin and K == @a.K").to_dict("records") if cmp_path.exists() else []
    payload = dict(
        meta=dict(wmin=a.wmin, K=a.K, n=sc.n, n_edges=len(sc.w), params=P,
                  source="FlyWire v783 (eonsystemspbc/fly-brain data) + flyconnectome/flywire_annotations"),
        groups=sc.groups, fids=[str(f) for f in sc.fids], types=types, sides=sides, supers=supers,
        hops_in=[int(h) if np.isfinite(h) else -1 for h in sc.hops_in],
        hops_out=[int(h) if np.isfinite(h) else -1 for h in sc.hops_out],
        indptr=b64(sc.indptr.astype(np.int32)), post=b64(sc.post.astype(np.int32)), w=b64(sc.w.astype(np.float32)),
        validation=validation)
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"写入 {out}（{out.stat().st_size / 1e6:.2f} MB）：{sc.n} 神经元，{len(sc.w)} 连接")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("compare")
    e = sub.add_parser("export"); e.add_argument("--wmin", type=int, default=3); e.add_argument("--K", type=int, default=3)
    e.add_argument("--out", default=str(ROOT / "results/dodge/subcircuit.json"))
    a = ap.parse_args()
    {"compare": cmd_compare, "export": cmd_export}[a.cmd](a)
