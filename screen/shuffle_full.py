#!/usr/bin/env python
"""复现论文补充表 1D：**打乱接线**的对照，这一次在全脑上做（§30.1 只在 4,599 个神经元的子回路上做过）。

论文口径：同样刺激糖味觉 GRN，把连接组打乱后重跑 100 次，看表 1D 那 15 个神经元的发放率。
论文的"打乱"具体做法没公开，我们用的是**保每个神经元的出度与权重、只把靶点整体重排**
（与 §30.1 子回路版同一套做法，这样两边可比）。

**判据事先写死**（照表 1D 自己的数字）：
  A. 打乱后 MN9_r 的均值 < 不打乱的 10%（论文：68.0 → 0.004）。
  B. 表 1D 的 15 个神经元里，打乱后均值低于不打乱的 ≥ 13 个（论文是 14/15——唯一升高的是 Fudog）。

**判据 B 的分母就地改过一次，记在这里**：表 1D 的 15 个 ID 里只有 **13 个**在 v783 模型中，
所以"≥13/15"无法原样套用。按论文同样的比例（14/15 = 93.3%）折算，改成 **≥12/13（92.3%）**。
这次改动发生在只看到第一个打乱版本的 MN9 之后、看到其余结果之前。

刺激：官方 notebook 的 21 个右侧唇瓣糖味觉 GRN @ 100 Hz
（这一条有独立佐证：论文表 1D 的 MN9_r 是 68.0 Hz，我们全脑不打乱时是 69 Hz）。

做法：每个打乱版本重新建一次模型（Brian2 standalone 的拓扑是编译期固定的，改靶点必须重编译），
同一套泊松输入图样在所有版本间复用，所以差别只来自接线。

用法（brain-fly-cpu，套 memguard）：python screen/shuffle_full.py run [--n 10] | analyze
输出 results/screen/shuffle_full/
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
from xlsx_lite import read_xlsx  # noqa: E402

FREQS = (100,)
R = 3
SEED_SHUF = 20260919
WDIR = S.OUT / "shuffle_full"
TRIAL_S = S.TRIAL_STEPS * S.DT_MS * 1e-3


def paper_1d():
    t = read_xlsx(str(S.SUPP))["ST 1D Shuffled Connectivity"]
    out = []
    for r in t[1:]:
        sid = str(r[0]).strip()
        if sid.isdigit():
            out.append(dict(fid=int(sid), name=str(r[1]), intact=float(r[2]),
                            shuf_mean=float(r[3]), shuf_sd=float(r[4])))
    return out


def shuffled_parquet(k):
    """第 k 个打乱版本：保留每条边的源与权重，把靶点列整体随机重排。"""
    out = WDIR / "con" / f"shuf_{k:02d}.parquet"
    if out.exists():
        return out
    df = pd.read_parquet(S.PATH_CON)
    rng = np.random.default_rng(SEED_SHUF + k)
    post = df["Postsynaptic_Index"].to_numpy().copy()
    rng.shuffle(post)                       # 全局重排：出度与权重不变，靶点随机
    df["Postsynaptic_Index"] = post
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out)
    return out


def setup(con_path=None):
    fids, fid2i = S.load_ids()
    ids = [f for f in json.loads((S.OUT / "taste" / "notebook_lists.json").read_text())["neu_sugar"]]
    ids = [int(x) for x in ids if int(x) in fid2i]
    S.FREQS = FREQS
    S.R_MAX = R
    S.BUILD = S.OUT / ".brian2_build_shuffle"
    S.sugar_ids = lambda: list(ids)
    if con_path is not None:
        S.PATH_CON = con_path
    WDIR.mkdir(parents=True, exist_ok=True)
    return fids, fid2i, ids


def run_one(tag, con_path, watch):
    f = WDIR / f"{tag}.json"
    if f.exists():
        return json.loads(f.read_text())
    orig = S.PATH_CON
    setup(con_path)
    t0 = time.time()
    sc = S.Screen()
    segs = [(0, r, ()) for r in range(R)]
    cnt, _ = sc.run_chunk(segs)
    S.PATH_CON = orig
    rec = dict(tag=tag, seconds=round(time.time() - t0, 1),
               rates={str(fid): round(float(np.mean([cnt[r][i] for r in range(R)])) / TRIAL_S, 3)
                      for fid, i in watch.items()},
               n_active=[int((cnt[r] > 0).sum()) for r in range(R)])
    f.write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    print(f"  {tag}：{rec['seconds']:.0f}s，活跃 {rec['n_active']}，MN9_r {rec['rates'][str(S.MN9)]}", flush=True)
    return rec


def cmd_run(n):
    fids, fid2i, ids = setup()
    watch = {r["fid"]: fid2i[r["fid"]] for r in paper_1d() if r["fid"] in fid2i}
    print(f"糖 GRN {len(ids)} 个 @ {FREQS[0]} Hz，{R} 个实现；表 1D 的 15 个里模型内有 {len(watch)} 个", flush=True)
    run_one("intact", None, watch)
    for k in range(n):
        run_one(f"shuf_{k:02d}", shuffled_parquet(k), watch)
    print("→", WDIR)


def cmd_analyze():
    fids, fid2i, ids = setup()
    rows = paper_1d()
    intact = json.loads((WDIR / "intact.json").read_text())
    shufs = [json.loads(p.read_text()) for p in sorted(WDIR.glob("shuf_*.json"))]
    if not shufs:
        print("还没有打乱的结果"); return
    out = dict(design=dict(freq_hz=FREQS[0], R=R, n_shuffles=len(shufs), n_grn=len(ids),
                           method="保每个神经元的出度与权重，只把靶点列整体重排",
                           criterion="A：打乱后 MN9_r 均值 < 不打乱的 10%；"
                                     "B：表 1D 的 15 个里在模型中的 13 个，≥12 个下降（论文 14/15 = 93.3%，按比例折算）"),
               neurons=[], intact_n_active=intact["n_active"],
               shuffled_n_active=[s["n_active"] for s in shufs])
    down = 0
    print(f"\n{'神经元':12s}{'我们·不打乱':>12s}{'我们·打乱均值':>14s}{'±SD':>8s}{'论文·不打乱':>12s}{'论文·打乱':>10s}")
    for r in rows:
        k = str(r["fid"])
        if k not in intact["rates"]:
            continue
        v0 = intact["rates"][k]
        vs = [s["rates"][k] for s in shufs]
        m, sd = float(np.mean(vs)), float(np.std(vs))
        down += int(m < v0)
        out["neurons"].append(dict(name=r["name"], fid=k, ours_intact=v0, ours_shuf_mean=round(m, 3),
                                   ours_shuf_sd=round(sd, 3), paper_intact=r["intact"],
                                   paper_shuf_mean=round(r["shuf_mean"], 3), went_down=bool(m < v0)))
        print(f"{r['name']:12s}{v0:12.1f}{m:14.2f}{sd:8.2f}{r['intact']:12.1f}{r['shuf_mean']:10.2f}")
    mn9 = [x for x in out["neurons"] if x["fid"] == str(S.MN9)][0]
    A = mn9["ours_shuf_mean"] < 0.1 * mn9["ours_intact"]
    B = down >= 12                      # 15 个里只有 13 个在模型中；按论文 14/15 的比例折算
    a = np.array([x["ours_intact"] for x in out["neurons"]]); b = np.array([x["paper_intact"] for x in out["neurons"]])
    out["pearson_intact_vs_paper"] = round(float(np.corrcoef(a, b)[0, 1]), 3)
    out["n_down"] = down
    out["n_total"] = len(out["neurons"])
    out["criterion_A_mn9_collapses"] = bool(A)
    out["criterion_B_most_go_down"] = bool(B)
    out["both_pass"] = bool(A and B)
    out["mn9_r"] = mn9
    print(f"\n判据 A：MN9_r {mn9['ours_intact']} → 打乱后 {mn9['ours_shuf_mean']}"
          f"（要求 < {0.1 * mn9['ours_intact']:.1f}）→ {'成立' if A else '不成立'}")
    print(f"判据 B：{down}/{len(out['neurons'])} 个下降（要求 ≥12，论文 14/15）→ {'成立' if B else '不成立'}")
    print(f"不打乱时我们与论文的 Pearson：{out['pearson_intact_vs_paper']}")
    print(f"活跃神经元：不打乱 {intact['n_active']}，打乱 {out['shuffled_n_active'][:3]}…")
    (WDIR / "summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("→", WDIR / "summary.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["run", "analyze"]); ap.add_argument("--n", type=int, default=10)
    a = ap.parse_args()
    (cmd_run if a.cmd == "run" else cmd_analyze)(*( [a.n] if a.cmd == "run" else []))
