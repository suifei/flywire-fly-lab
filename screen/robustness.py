#!/usr/bin/env python
"""复现论文补充表 11：参数扰动下，预测还站得住吗？（全脑）

论文 Shiu et al. 2024 补充表 11A–F 测的是：把模型参数改掉之后，论文自己的定性预测是否不变。
表 11A 是汇总（65 行，逐条预测 + "Number consistent with default w_syn"），
表 11B–F 是每种扰动下**对糖刺激有反应的 182 个神经元**（图 1D）的发放率与
"Same prediction as baseline?" 一列。刺激口径见 11A：**糖 GRN @ 150 Hz**。

**这一节只复现「不需要敲除」的两条预测**（成本几分钟，而不是几小时）：
  P1 哪些神经元对糖刺激有反应（图 1D / 表 11B–F 的 182 行）
  P2 同侧 MN9 比对侧弱（图 1C）
第三条「哪些神经元是必需的」要在每种扰动下重做整轮敲除筛选（约 5,460 段 / 3 h），没有在这里做。

扰动（对应论文各表）：
  baseline  不改
  11B  w_syn −30%      11C  w_syn +30%
  11D  抑制 −30%       11E  抑制 +30%     （只缩放负权重）
  11F  谷氨酸改兴奋性   （谷氨酸能神经元的传出突触取绝对值）

做法：一次编译（FREQS=(150,)），6 种权重设定各跑 R 个输入实现，
每次用 `device.run(run_args={syn.w: ...})` 换权重——**不重复编译**。

用法（brain-fly-cpu，套 memguard）：python screen/robustness.py run|analyze
输出 results/screen/robustness/
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

FREQ, R = 150, 6
WDIR = S.OUT / "robustness"
PERTURB = ["baseline", "w-30", "w+30", "inh-30", "inh+30", "glut_exc"]


def setup():
    S.FREQS = (FREQ,)
    S.R_MAX = R
    S.BUILD = S.OUT / ".brian2_build_robust"
    S.CHUNKS = WDIR / "chunks"
    WDIR.mkdir(parents=True, exist_ok=True)
    (WDIR / "chunks").mkdir(exist_ok=True)


def weights(kind, nt_of_pre, w0, pre_idx):
    """返回该扰动下的权重数组（mV 数值，不带单位）。"""
    w = w0.copy()
    if kind == "baseline":
        return w
    if kind == "w-30":
        return w * 0.7
    if kind == "w+30":
        return w * 1.3
    if kind == "inh-30":
        w[w < 0] *= 0.7; return w
    if kind == "inh+30":
        w[w < 0] *= 1.3; return w
    if kind == "glut_exc":
        m = nt_of_pre == 1                       # 1 = 谷氨酸
        w[m] = np.abs(w[m]); return w
    raise ValueError(kind)


def cmd_run():
    from brian2 import mV
    setup()
    fids, fid2i = S.load_ids()
    N = len(fids)
    sc = S.Screen()
    con = pd.read_parquet(S.PATH_CON, columns=["Presynaptic_Index", "Excitatory x Connectivity"])
    pre = con["Presynaptic_Index"].to_numpy()
    w0 = con["Excitatory x Connectivity"].to_numpy(dtype=float) * float(sc.params["w_syn"] / mV)
    del con
    ann = pd.read_csv(S.ANNOT, sep="\t", low_memory=False,
                      usecols=["root_id", "top_nt"]).drop_duplicates("root_id").set_index("root_id")
    nt = np.full(N, 6, np.int8)
    code = {"acetylcholine": 0, "glutamate": 1, "gaba": 2, "dopamine": 3, "serotonin": 4, "octopamine": 5}
    for i, f in enumerate(fids):
        v = ann.top_nt.get(int(f))
        if isinstance(v, str):
            nt[i] = code.get(v.lower(), 6)
    nt_of_pre = nt[pre]
    print(f"突触 {len(w0):,} 条；其中谷氨酸能突触前 {int((nt_of_pre == 1).sum()):,} 条", flush=True)

    segs = [(0, r, ()) for r in range(R)]
    for kind in PERTURB:
        f = WDIR / "chunks" / f"{kind}.npz"
        if f.exists():
            print(f"  {kind}：已有，跳过", flush=True)
            continue
        w = weights(kind, nt_of_pre, w0, pre)
        t0 = time.time()
        counts, wall = sc.run_chunk(segs, extra_args=None if kind == "baseline" else {sc.syn.w: w * mV})
        S.save_chunk(f, [S.key(*s) for s in segs], counts, wall)
        print(f"  {kind}：{R} 个实现跑完，{time.time() - t0:.0f}s", flush=True)
        del w
    print("→", WDIR / "chunks")


def paper_11(sheet):
    X = read_xlsx(str(S.SUPP))
    t = [v for k, v in X.items() if k.startswith(sheet)][0]
    hdr = next(r for r in t if any(str(c).strip() == "flyid" for c in r if c))
    c = [i for i, v in enumerate(hdr) if str(v).strip() == "flyid"][0]
    # 11C 的发放率列叫 "sugarR"，其余几张叫 "Firing Rate (Hz)" —— 两种都要认，
    # 否则那一张会静默读失败（第一版就是这样，w+30 那行显示「表读取失败」）。
    cand = [i for i, v in enumerate(hdr) if "Firing Rate" in str(v) or str(v).strip() == "sugarR"]
    assert cand, f"{sheet}：找不到发放率列，表头是 {[str(x)[:20] for x in hdr[:6]]}"
    fr = cand[0]
    same = [i for i, v in enumerate(hdr) if "Same prediction" in str(v)]
    out = []
    for r in t:
        if len(r) > max(c, fr) and str(r[c]).isdigit():
            out.append(dict(fid=int(r[c]), hz=float(r[fr]),
                            same=(int(r[same[0]]) if same and str(r[same[0]]).strip() in "01" else None)))
    return out


def cmd_analyze():
    setup()
    fids, fid2i = S.load_ids()
    N = len(fids)
    # MN9 的注释 cell_type 是 **CB0701**，不是 "MN9"（按类型名查会查到空，第一版就是这么挂的）。
    # 论文补充表 11B 直接给了两个 ID 与命名：MN9_r / MN9_l。沿用论文的命名，
    # 注意 CLAUDE.md 记过：官方 notebook 的左右命名与注释表的 side 相反。
    # 论文表 11B 给的 MN9_l = 720575940645521262 是 **v630 的 ID，在 v783 里已变更**，
    # 模型里查不到（CLAUDE.md 记过：论文 Fig 1F 的 200 个里 184 个未变）。
    # 按 cell_type=CB0701 找到 v783 的对侧同型：720575940618238523（side=left）。
    # 注意官方 notebook 的左右命名与注释表 side 相反，所以这里按**注释表 side** 命名，
    # 并在输出里同时给出论文的 MN9_r / MN9_l 对照值。
    MN9_R_PAPER = 720575940660219265          # 论文叫 MN9_r，注释表 side=right
    MN9_OTHER = 720575940618238523            # 同型 CB0701 的另一侧，注释表 side=left
    mn9r = [fid2i[MN9_R_PAPER]]
    mn9l = [fid2i[MN9_OTHER]] if MN9_OTHER in fid2i else []
    assert mn9r and mn9l, "MN9 两侧在模型里找不到"
    cnt = {}
    for kind in PERTURB:
        f = WDIR / "chunks" / f"{kind}.npz"
        if not f.exists():
            print(f"缺 {kind}，先跑 run"); return
        _, c, _ = S.load_chunk(f, N)
        cnt[kind] = np.array(c[:R])                     # (R, N) 每秒计数 = Hz
    base = cnt["baseline"]
    resp_base = set(np.nonzero(base.mean(0) > 0)[0].tolist())
    print(f"基线（糖 GRN @ {FREQ} Hz，{R} 个实现）：活跃神经元 {len(resp_base):,} 个")
    print(f"  MN9_l {base[:, mn9l].mean():.1f} Hz / MN9_r {base[:, mn9r].mean():.1f} Hz"
          f"（论文表 11B 的 w−30% 值：MN9_r 33.47、MN9_l 22.0；注意论文 MN9_l 的 ID 在 v783 已变更，这里用同型 CB0701 的另一侧）")
    # 基线对照：先确认「同一刺激下发放率」这件事本身对得上，否则扰动对照没有意义
    try:
        rows0 = paper_11("Supp Table 11B")
        o0 = {int(fids[i]): float(base[:, i].mean()) for i in resp_base}
        pr0 = [(x["hz"], o0.get(x["fid"], 0.0)) for x in rows0 if x["fid"] in fid2i]
        pa, oa = np.array([a for a, _ in pr0]), np.array([b for _, b in pr0])
        print(f"  （注：表 11B 的 182 行里只有 {len(rows0)} 行带 flyid，其余是类型级汇总块，无法逐个对应）")
    except Exception as e:
        print("  基线对照失败：", e)
    SHEET = {"w-30": "Supp Table 11B", "w+30": "Supp Table 11C", "inh-30": "Supp Table 11D",
             "inh+30": "Supp Table 11E", "glut_exc": "Supp Table 11F"}
    out = dict(design=dict(freq_hz=FREQ, R=R, perturbations=PERTURB,
                           note="只复现不需要敲除的两条预测（P1 哪些神经元响应、P2 同侧 vs 对侧 MN9）；"
                                "「哪些神经元必需」需在每种扰动下重做整轮敲除筛选（约 5,460 段 / 3 h），未做"),
               baseline=dict(n_active=len(resp_base), mn9_left=round(float(base[:, mn9l].mean()), 2),
                             mn9_right=round(float(base[:, mn9r].mean()), 2)), perturbations={})
    print(f"\n{'扰动':10s}{'活跃数':>8s}{'与基线交集':>11s}{'MN9左':>8s}{'MN9右':>8s}{'P2 同侧弱?':>11s}{'论文表对照':>26s}")
    for kind in PERTURB:
        c = cnt[kind]
        resp = set(np.nonzero(c.mean(0) > 0)[0].tolist())
        keep = len(resp & resp_base)
        l, r = float(c[:, mn9l].mean()), float(c[:, mn9r].mean())
        p2 = l < r
        rec = dict(n_active=len(resp), kept_from_baseline=keep,
                   frac_baseline_kept=round(keep / max(len(resp_base), 1), 4),
                   mn9_left=round(l, 2), mn9_right=round(r, 2), P2_ipsi_weaker=bool(p2))  # 论文的 P2：同侧 MN9 比对侧弱
        cmpstr = ""
        if kind in SHEET:
            try:
                rows = paper_11(SHEET[kind])
                ours = {int(fids[i]): float(c[:, i].mean()) for i in resp}
                pair = [(x["hz"], ours.get(x["fid"], 0.0)) for x in rows if x["fid"] in fid2i]
                if pair:
                    p_, o_ = np.array([a for a, _ in pair]), np.array([b for _, b in pair])
                    both = int(((p_ > 0) & (o_ > 0)).sum())
                    rec["paper_table"] = dict(sheet=SHEET[kind], n=len(pair), both_respond=both,
                                              pearson=round(float(np.corrcoef(p_, o_)[0, 1]), 3) if len(pair) > 2 else None)
                    cmpstr = f"{SHEET[kind][-4:]}：{both}/{len(pair)} 都响应，r={rec['paper_table']['pearson']}"
            except Exception as e:
                rec["paper_table_error"] = str(e)[:80]
                cmpstr = "（表读取失败）"
        out["perturbations"][kind] = rec
        print(f"{kind:10s}{len(resp):8,d}{keep:11,d}{l:8.1f}{r:8.1f}{'✓' if p2 else '✗':>11s}{cmpstr:>26s}")
    (WDIR / "summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"\n→ {WDIR / 'summary.json'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["run", "analyze"])
    {"run": cmd_run, "analyze": cmd_analyze}[ap.parse_args().cmd]()
