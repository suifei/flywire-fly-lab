#!/usr/bin/env python
"""补充表 11 的**第三条预测**：参数扰动之后，"哪些神经元是伸喙必需的"还站得住吗？

§35 只做了前两条（响应集、同侧 MN9 更弱），这一条要在**每种扰动下重做整轮敲除筛选**，
所以一直空着。这里把它补上。

**论文的口径有一个容易漏掉的地方：每种扰动重新标定了刺激频率。**（表 11A 的
"30% Decrease Experiment" 那一列）：

| 扰动 | 刺激频率 | 论文「与默认 w_syn 判定一致」的个数 |
|---|---|---|
| 默认 | 50 Hz（§14 的口径） | — |
| w_syn −30%（11B） | **115 Hz** | 8 / 10 |
| w_syn +30%（11C） | **30 Hz**  | 7 / 10 |
| 抑制 −50%（11D）  | **30 Hz**  | 8 / 10 |
| 抑制 +50%（11E）  | **100 Hz** | 7 / 10 |
| 谷氨酸→兴奋（11F）| **45 Hz**  | 7 / 10 |

也就是说论文并不是在同一个刺激强度下比较——突触弱了就把输入调高、强了就调低，
让基线回到可比的位置，再看**判定**（≤ 0.8 判"必需"）翻不翻。

**比较对象是模型自己的默认判定，不是实验**（表头就是 "Number consistent with default w_syn"）。

做法：一次编译，FREQS = (30, 45, 50, 100, 115)，R = 6，21 个糖 GRN；
权重按扰动用 `device.run(run_args={syn.w: ...})` 逐块替换，**不重复编译**。
神经元名单 = 论文表 1C 的 200 个（与 §14 完全相同），逐个单敲。
某个实现里该神经元本来就不放电时跳过那一段（沉默一个不放电的神经元恒等于基线）。

归一化沿用 §14：**比值 = 该敲除的 MN9 ÷ 同一实现下所有敲除的 MN9 中位数**
（零参照 / plate-median），因为这个网络对初值敏感，敲任何一个会放电的神经元都会让 MN9 略降。

用法（brain-fly-cpu，套 memguard）：python screen/robust_knockout.py run|analyze
输出 results/screen/robust_knockout/
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import sugar_mn9_screen as S  # noqa: E402
import robustness as RB  # noqa: E402

FREQS = (30, 45, 50, 100, 115)
R = 6
CALL = 0.8
WDIR = S.OUT / "robust_knockout"
# 扰动 → (刺激频率, 论文表, 论文「与默认一致」个数)
COND = {"baseline": (50, None, None), "w-30": (115, "11B", 8), "w+30": (30, "11C", 7),
        "inh-50": (30, "11D", 8), "inh+50": (100, "11E", 7), "glut_exc": (45, "11F", 7)}


def setup():
    S.FREQS = FREQS
    S.R_MAX = R
    S.BUILD = S.OUT / ".brian2_build_rk"
    S.CHUNKS = WDIR / "chunks"
    WDIR.mkdir(parents=True, exist_ok=True)
    (WDIR / "chunks").mkdir(exist_ok=True)


def weight_arrays(sc):
    """每种扰动的权重数组（mV 数值）。与 robustness.py 用的是同一套定义。"""
    from brian2 import mV
    fids, fid2i = S.load_ids()
    con = pd.read_parquet(S.PATH_CON, columns=["Presynaptic_Index", "Excitatory x Connectivity"])
    pre = con["Presynaptic_Index"].to_numpy()
    w0 = con["Excitatory x Connectivity"].to_numpy(dtype=float) * float(sc.params["w_syn"] / mV)
    del con
    ann = pd.read_csv(S.ANNOT, sep="\t", low_memory=False,
                      usecols=["root_id", "top_nt"]).drop_duplicates("root_id").set_index("root_id")
    nt = np.full(len(fids), 6, np.int8)
    code = {"acetylcholine": 0, "glutamate": 1, "gaba": 2, "dopamine": 3, "serotonin": 4, "octopamine": 5}
    for i, f in enumerate(fids):
        v = ann.top_nt.get(int(f))
        if isinstance(v, str):
            nt[i] = code.get(v.lower(), 6)
    nt_of_pre = nt[pre]
    return {k: (None if k == "baseline" else RB.weights(k, nt_of_pre, w0, pre)) for k in COND}


def targets(fid2i):
    # paper_table_1c() 按 S.FREQS 去表 1C 里定位列，而我们的 FREQS 含 30/45/115 这些表里没有的档，
    # 所以取名单时临时把它换回 (50,)——我们只要那 200 个 ID，不要它的数值。
    old = S.FREQS
    S.FREQS = (50,)
    try:
        rows, _ = S.paper_table_1c()
    finally:
        S.FREQS = old
    return [r["fid"] for r in rows if r["fid"] in fid2i and r["fid"] != S.MN9]


def cmd_run():
    from brian2 import mV
    setup()
    fids, fid2i = S.load_ids()
    N = len(fids)
    mn9i = fid2i[S.MN9]
    tg = targets(fid2i)
    print(f"名单：论文表 1C 的 {len(tg)} 个（模型内，去掉 MN9 自身）；{len(COND)} 种扰动 × {R} 个实现", flush=True)
    sc = S.Screen()
    W = weight_arrays(sc)
    fi_of = {f: i for i, f in enumerate(FREQS)}

    for cond, (hz, _, _) in COND.items():
        fi = fi_of[hz]
        wargs = {} if W[cond] is None else {sc.syn.w: W[cond] * mV}
        # 1) 基线（不沉默任何神经元）：既是参照，也用来判断哪些神经元在该实现里根本不放电
        bf = WDIR / "chunks" / f"{cond}_base.npz"
        if not bf.exists():
            segs = [(fi, r, ()) for r in range(R)]
            cnt, wall = sc.run_chunk(segs, extra_args=wargs)
            S.save_chunk(bf, [S.key(*s) for s in segs], cnt, wall)
            print(f"{cond} @ {hz} Hz 基线：MN9 {[int(cnt[r][mn9i]) for r in range(R)]}，"
                  f"活跃 {[int((cnt[r] > 0).sum()) for r in range(R)]}", flush=True)
        _, bc, _ = S.load_chunk(bf, N)
        base = np.array(bc[:R])

        # 2) 单敲除：该实现里不放电的跳过（沉默一个不放电的神经元 = 基线，见 §20 的 needed_keys）
        jobs = [(fi, r, (fid2i[f],)) for f in tg for r in range(R) if base[r][fid2i[f]] > 0]
        done = set()
        for p in sorted((WDIR / "chunks").glob(f"{cond}_k*.npz")):
            done.update(tuple(k) for k in [(a, b, tuple(c)) for a, b, c in S.chunk_keys(p)])
        todo = [j for j in jobs if (j[0], j[1], tuple(j[2])) not in done]
        print(f"{cond} @ {hz} Hz：需要 {len(jobs)} 段，已有 {len(jobs) - len(todo)}，待跑 {len(todo)}", flush=True)
        for c0 in range(0, len(todo), S.K):
            blk = todo[c0:c0 + S.K]
            f = WDIR / "chunks" / f"{cond}_k{c0 + len(jobs) - len(todo):05d}.npz"
            if f.exists():
                continue
            t0 = time.time()
            cnt, wall = sc.run_chunk(blk, extra_args=wargs)
            S.save_chunk(f, [S.key(*s) for s in blk], cnt, wall)
            if (c0 // S.K) % 10 == 0:
                print(f"  {cond} {c0:5d}/{len(todo)}  {time.time() - t0:.0f}s", flush=True)
    print("→", WDIR / "chunks")


def cmd_analyze():
    setup()
    fids, fid2i = S.load_ids()
    N = len(fids)
    mn9i = fid2i[S.MN9]
    tg = targets(fid2i)
    members = S.type_members(fid2i)
    out = dict(design=dict(freqs={k: v[0] for k, v in COND.items()}, R=R, call=CALL,
                           n_targets=len(tg), normalization="零参照：同一实现下所有敲除的 MN9 中位数",
                           note="论文对每种扰动重新标定了刺激频率（表 11A 的 Experiment 一列）；"
                                "比较对象是**模型自己的默认判定**，不是实验"),
               conditions={})
    for cond, (hz, sheet, paper_n) in COND.items():
        bf = WDIR / "chunks" / f"{cond}_base.npz"
        if not bf.exists():
            print(f"缺 {cond} 基线"); continue
        _, bc, _ = S.load_chunk(bf, N)
        base = np.array(bc[:R])
        got = {}
        for p in sorted((WDIR / "chunks").glob(f"{cond}_k*.npz")):
            keys, cnt = S.chunk_summary(p, {"mn9": mn9i})
            for (fi, r, sil), v in zip(keys, cnt):
                got[(r, sil[0])] = v["mn9"]
        per = {}                                    # 神经元 → 每个实现的 MN9 计数
        miss = 0
        for f in tg:
            i = fid2i[f]
            vals = []
            for r in range(R):
                if base[r][i] == 0:
                    vals.append(int(base[r][mn9i]))          # 不放电 → 等于基线
                elif (r, i) in got:
                    vals.append(got[(r, i)])
                else:
                    miss += 1
            per[f] = vals
        if miss:
            print(f"{cond}：缺 {miss} 段，跳过分析"); continue
        # 零参照：每个实现下所有敲除的中位数
        null = [float(np.median([per[f][r] for f in tg if len(per[f]) == R])) for r in range(R)]
        ratio = {f: float(np.median([per[f][r] / null[r] if null[r] > 0 else np.nan for r in range(R)])) for f in per}
        calls = {}
        for t, ids in members.items():
            vs = [ratio[f] for f in ids if f in ratio]
            calls[t] = dict(ratio=None if not vs else round(float(np.min(vs)), 4),
                            required=bool(vs and min(vs) <= CALL))
        out["conditions"][cond] = dict(hz=hz, paper_sheet=sheet, paper_n_consistent=paper_n,
                                       mn9_baseline=[int(base[r][mn9i]) for r in range(R)],
                                       null_median=null, n_scored=len(ratio), calls=calls,
                                       top=[dict(fid=str(f), ratio=round(ratio[f], 4))
                                            for f in sorted(ratio, key=lambda x: ratio[x])[:12]])
    if "baseline" not in out["conditions"]:
        print("没有默认条件，无法比较"); return
    b = out["conditions"]["baseline"]["calls"]
    print(f"{'扰动':10s}{'Hz':>5s}{'基线 MN9':>10s}{'与默认判定一致':>16s}{'论文':>6s}  翻转的类型")
    for cond, d in out["conditions"].items():
        same = sum(1 for t in b if d["calls"][t]["required"] == b[t]["required"])
        flip = [t for t in b if d["calls"][t]["required"] != b[t]["required"]]
        d["n_consistent_with_default"] = same
        d["flipped"] = flip
        print(f"{cond:10s}{d['hz']:5d}{np.mean(d['mn9_baseline']):10.1f}{same:12d}/10"
              f"{(d['paper_n_consistent'] if d['paper_n_consistent'] else 0):6d}  " + "、".join(flip))
    ours = [out["conditions"][c]["n_consistent_with_default"] for c in COND if c != "baseline" and c in out["conditions"]]
    paper = [COND[c][2] for c in COND if c != "baseline" and c in out["conditions"]]
    out["ours_consistent"] = ours
    out["paper_consistent"] = paper
    out["mean_abs_diff"] = round(float(np.mean(np.abs(np.array(ours) - np.array(paper)))), 2) if ours else None
    print(f"\n我们 {ours} vs 论文 {paper}，平均绝对差 {out['mean_abs_diff']}")
    (WDIR / "summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("→", WDIR / "summary.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["run", "analyze"])
    {"run": cmd_run, "analyze": cmd_analyze}[ap.parse_args().cmd]()
