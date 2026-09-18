#!/usr/bin/env python
"""复现论文补充表 10 的另外两行：**哪些神经元响应糖 / 响应水**（Fig 1D / 4A，论文 12/14 与 8/10）。

零新仿真：糖与水筛选的基线段落里本来就存了**全部神经元**的脉冲计数，
所以「某个类型在该刺激下放不放电」直接查表就有。

判据（论文表 1A / 6A 的口径，事先定死）：该类型的任一神经元平均发放率 > 0 Hz 即判「响应」。
实验侧取自表 2 / 表 5 的第一列（Yes / No / No significant response / Not tested），
「Not tested」不计分——这也是论文自己只数 14 项和 10 项的原因。

用法：python screen/responsive.py（只读，约 10 s）→ results/screen/responsive.json
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import sugar_mn9_screen as S  # noqa: E402
import water_screen as W  # noqa: E402

# 表 2 / 表 5 第一列的实验结论。None = 未测（不计分）
EXP_SUGAR = {"Bract": True, "Clavicle": True, "Fdg": True, "FMIn": True, "G2N-1": True, "MN9": True,
             "Phantom": True, "Rattle": True, "Roundup": True, "Usnea": False, "Zorro": True}
EXP_WATER = {"Bract": None, "Clavicle": True, "G2N-1": False, "MN9": None, "Phantom": None,
             "Rattle": True, "Roundup": False, "Tophat": None, "Tulip": None, "Usnea": True, "Zorro": True}
TRIAL_S = S.TRIAL_STEPS * S.DT_MS * 1e-3


def members(types, fid2i):
    ann = pd.read_csv(S.ANNOT, sep="\t", low_memory=False, usecols=["root_id", "cell_type"]).drop_duplicates("root_id")
    out = {}
    for t, cts in types.items():
        ids = sorted(int(x) for x in ann.root_id[ann.cell_type.isin(cts)] if int(x) in fid2i)
        out[t] = ids
    out["MN9"] = [S.MN9]
    return out


def paper_pred(sheet_prefix):
    """表 2 / 表 5 的「Predicted to respond?」一列——论文自己的模型判定，用来逐条对齐。"""
    from xlsx_lite import read_xlsx
    t = S.sheet(read_xlsx(str(S.SUPP)), sheet_prefix)
    out = {}
    for r in t[1:]:
        nm = str(r[0]).strip()
        if nm and nm != "Neuron Name":
            out[nm] = str(r[2]).strip().lower().startswith("yes")
    return out


def one(label, base_file, R, freq_hz, types, exp, fid2i, pp):
    _, cnt, _ = S.load_chunk(base_file, len(fid2i))
    cnt = np.array(cnt[:R])
    mem = members(types, fid2i)
    rows, correct, total = [], 0, 0
    for t in sorted(mem):
        ids = mem[t]
        if not ids:
            rows.append(dict(type=t, n=0, hz=None, ours=None, exp=exp.get(t), scored=False, note="模型里没有这个类型"))
            continue
        idx = [fid2i[f] for f in ids]
        per = cnt[:, idx].mean(0) / TRIAL_S            # 每个成员的平均发放率
        hz = float(per.max())
        ours = hz > 0
        e = exp.get(t)
        scored = e is not None
        if scored:
            total += 1
            correct += int(ours == e)
        rows.append(dict(type=t, n=len(ids), hz=round(hz, 2), n_firing=int((per > 0).sum()),
                         ours=ours, exp=e, paper_pred=pp.get(t), scored=scored,
                         agree=None if not scored else ours == e,
                         same_as_paper=None if pp.get(t) is None else ours == pp[t]))
    same = sum(1 for r in rows if r.get("same_as_paper"))
    npp = sum(1 for r in rows if r.get("paper_pred") is not None)
    print(f"\n{label}（{freq_hz} Hz，{R} 个实现）：与实验一致 {correct}/{total}；与论文自己的预测列一致 {same}/{npp}")
    print(f"  {'类型':10s}{'成员':>5s}{'放电成员':>9s}{'最高 Hz':>9s}{'我们':>6s}{'实验':>8s}")
    for r in rows:
        e = {True: "响应", False: "不响应", None: "未测"}[r["exp"]]
        print(f"  {r['type']:10s}{r['n']:5d}{r.get('n_firing', 0):9d}{(r['hz'] or 0):9.2f}"
              f"{('响应' if r['ours'] else '不响应') if r['ours'] is not None else '—':>6s}{e:>8s}"
              + ("" if r["agree"] in (None, True) else "   ← 不一致"))
    return dict(freq_hz=freq_hz, R=R, correct=correct, total=total,
                same_as_paper=same, n_paper_pred=npp, types=rows)


def main():
    fids, fid2i = S.load_ids()
    out = {}
    out["sugar"] = one("糖（表 2 / Fig 1D）", S.CHUNKS.parent / "chunks" / "baseline.npz", S.R_MAX, S.FREQS[0],
                       S.TYPES, EXP_SUGAR, fid2i, paper_pred("Supplemental Table 2"))
    out["water"] = one("水（表 5 / Fig 4A）", W.WDIR / "baseline.npz", W.R_ALL, W.FREQ, W.TYPES, EXP_WATER, fid2i,
                       paper_pred("Supplemental Table 5"))
    out["note"] = ("论文自己数的是 14 项（糖）和 10 项（水），比我们多出的是 MN6 / Fudog / TH-VUM 等"
                   "没有把名字对到 v783 cell_type 的神经元；我们只对表 2 / 表 5 里列出的类型计分。"
                   "判据 > 0 Hz 用的是**该类型发放最强的那个成员**。")
    (S.OUT / "responsive.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("\n→", S.OUT / "responsive.json")


if __name__ == "__main__":
    main()
