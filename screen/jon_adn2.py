#!/usr/bin/env python
"""aDN2：论文补充表 7C/7E 那一半，我们一直没做——而且**不用跑任何新仿真**。

为什么零仿真：段落文件 `results/screen/jon_paper/chunks/*.npz` 存的是每段**全部活跃神经元**
的稀疏 (索引, 计数) 对，不是只存读出神经元。§24.3 跑那条通路时 aDN2
（`720575940629806974`，已写在 `screen/jon_screen.py` 里并被 watch）的计数就一起存下来了，
只是当时的分析只取了 aDN1。所以这里纯粹是重新读一遍存档。

口径与 §24.3（`jon_paper.py full_analyze`）**逐项相同**，只换读出神经元：
  刺激 = 论文 neu_JON_all 的 146 个里在 v783 模型中的 145 个，160 Hz；前 6 个输入实现；
  归一化 = 每实现 50 个随机活跃神经元单敲后的中位数；判据 比值 ≤ 0.8 记为"必需"。
  论文对照 = 补充表 **7E**（aDN2 在 140–180 Hz 下被逐个沉默后的发放率），取 160 Hz 列。

事先写定的预测（跑之前写）：
  1. aDN2 基线应接近论文的 **23.7 Hz**（我们 aDN1 得到 23.4 vs 论文 23.3，同一批段落）。
  2. aDN1 那条通路的结论是"单一瓶颈 aBN1"。aDN2 **是否也被 aBN1 卡住**，事先不知道——
     两种结果都要如实报告，不预设。
  3. 效应大小与论文的相关性，预期与 aDN1 同量级（Pearson 0.945、κ 0.907）。

用法：python screen/jon_adn2.py     （只读，几分钟，不跑仿真）
输出 results/screen/jon_paper/adn2_summary.json
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import sugar_mn9_screen as S  # noqa: E402
import jon_screen as J  # noqa: E402
import jon_paper as JP  # noqa: E402
import segments as SEG  # noqa: E402
from xlsx_lite import read_xlsx  # noqa: E402

CALL, R_A = JP.CALL, JP.R_A
WDIR = JP.WDIR


def paper_7e():
    """补充表 7E：逐个沉默后 aDN2 的发放率，列是刺激频率 140–180。"""
    X = read_xlsx(str(S.SUPP))
    hits = [v for k, v in X.items() if k.startswith("Supp Table 7E")]
    assert hits, "补充材料里找不到 7E"
    t = hits[0]
    assert 160 in t[0], f"7E 表头里没有 160 Hz：{t[0][:8]}"
    c = t[0].index(160)
    return [dict(fid=int(r[0]), name=str(r[1]), adn2_160=float(r[c]))
            for r in t[1:] if str(r[0]).isdigit() and r[c] not in (None, "")]


def main():
    fids, fid2i, ids = JP.setup()
    fi, base, meta = JP.load_base(fid2i)
    i1, i2 = fid2i[J.ADN1], fid2i[J.ADN2]
    plan = json.loads((WDIR / "plan.json").read_text())
    repo = SEG.Repo([WDIR / "chunks"], watch={"aDN1": i1, "aDN2": i2})
    rows7e = paper_7e()
    ann = pd.read_csv(S.ANNOT, sep="\t", low_memory=False,
                      usecols=["root_id", "cell_type", "super_class", "top_nt"]).drop_duplicates("root_id").set_index("root_id")

    def cnt(sil, field, idx):
        return [repo.get((fi, r, tuple(sorted(sil))), field=field, default=None)
                if any(base[r][n] > 0 for n in sil) else int(base[r][idx]) for r in range(R_A)]

    med2 = [float(np.median([cnt([fid2i[f]], "aDN2", i2)[r] for f in plan["null"]])) for r in range(R_A)]

    def ratio2(sil):
        m = cnt(sil, "aDN2", i2)
        return None if None in m else sum(m) / sum(med2)

    base2 = [int(base[r][i2]) for r in range(R_A)]
    base1 = [int(base[r][i1]) for r in range(R_A)]
    print(f"aDN2 基线各实现 {base2}，平均 {np.mean(base2):.1f} Hz（论文 {J.PAPER_160['aDN2']} Hz）")
    print(f"aDN1 基线（同一批段落）平均 {np.mean(base1):.1f} Hz（论文 {J.PAPER_160['aDN1']} Hz）")

    items, skipped = [], 0
    for r in rows7e:
        if r["fid"] not in fid2i or r["fid"] == J.ADN2:
            continue
        v = ratio2([fid2i[r["fid"]]])
        if v is None:
            skipped += 1
            continue
        items.append(dict(fid=str(r["fid"]), name=r["name"],
                          paper=round(r["adn2_160"] / J.PAPER_160["aDN2"], 4), ours=round(v, 4),
                          cell_type=ann.loc[r["fid"]].cell_type if r["fid"] in ann.index else None))
    assert items, "没有一条能对上：检查 7E 的 ID 是否都是 v630"
    o = np.array([x["ours"] for x in items]); pp = np.array([x["paper"] for x in items])
    comp = dict(n=len(items), n_skipped_missing_segments=skipped,
                spearman=S.spearman(o, pp), pearson=round(float(np.corrcoef(o, pp)[0, 1]), 3),
                calls_ours=int((o <= CALL).sum()), calls_paper=int((pp <= CALL).sum()),
                call_agreement=round(float(((o <= CALL) == (pp <= CALL)).mean()), 3),
                kappa=S.kappa(o <= CALL, pp <= CALL),
                median_abs_diff=round(float(np.median(np.abs(o - pp))), 3))
    print(f"\n对照论文表 7E：{comp['n']} 个可比（跳过缺段 {skipped}）")
    print(f"  Pearson {comp['pearson']}  Spearman {comp['spearman']}  κ {comp['kappa']}")
    print(f"  判必需：我们 {comp['calls_ours']} 个，论文 {comp['calls_paper']} 个，一致率 {comp['call_agreement']}")

    req = sorted([x for x in items if x["ours"] <= CALL], key=lambda x: x["ours"])[:25]
    # 判定不一致的逐个列出 —— "4 vs 5" 这种数字不点名就等于没说
    disagree = sorted([x for x in items if (x["ours"] <= CALL) != (x["paper"] <= CALL)],
                      key=lambda x: abs(x["ours"] - x["paper"]), reverse=True)
    print(f"\n判定不一致 {len(disagree)} 个：")
    for x in disagree:
        who = "只有论文判必需" if x["paper"] <= CALL else "只有我们判必需"
        print(f"  {x['name']:22s} {x['cell_type'] or '':10s} 我们 {x['ours']:.3f}  论文 {x['paper']:.3f}   {who}")
    print("\n我们判为 aDN2 必需的：")
    for x in req[:12]:
        print(f"  {x['name']:22s} {x['cell_type'] or '':10s} 我们 {x['ours']:.3f}  论文 {x['paper']:.3f}")

    # aBN1 是不是 aDN2 的瓶颈？（aDN1 那条通路的结论）
    med1 = [float(np.median([cnt([fid2i[f]], "aDN1", i1)[r] for f in plan["null"]])) for r in range(R_A)]
    ab = ratio2([fid2i[J.ABN1]])
    ab1 = None
    m1 = cnt([fid2i[J.ABN1]], "aDN1", i1)
    if None not in m1:
        ab1 = sum(m1) / sum(med1)
    pr = [x for x in rows7e if x["fid"] == J.ABN1]
    print(f"\naBN1（SAD093）：对 aDN2 比值 {ab if ab is None else round(ab,4)}"
          f"（论文 7E {round(pr[0]['adn2_160'] / J.PAPER_160['aDN2'], 4) if pr else '表中无'}）；"
          f"同一批段落里对 aDN1 是 {None if ab1 is None else round(ab1,4)}")

    # 集中度，口径同 §22.2。**aDN1 与 aDN2 必须在同一批被打分的神经元上算**——
    # §24.3 的 aDN1 集中度只覆盖 304 个打过分的神经元，直接拿来和这里比是错的
    # （AGENTS.md 记过这一条）。所以这里两个读出都在同一集合上重算。
    active = sorted({int(n) for r in range(R_A) for n in np.nonzero(base[r])[0]} - {i1, i2})

    def ratio1(sil):
        m = cnt(sil, "aDN1", i1)
        return None if None in m else sum(m) / sum(med1)

    import concentration as C
    conc = {}
    for nm, fn in (("aDN2", ratio2), ("aDN1", ratio1)):
        eff = []
        for n in active:
            v = fn([n])
            if v is not None:
                eff.append(max(0.0, 1 - v))
        e = np.array(eff)
        conc[nm] = dict(n_scored=len(eff), n_required=int((e >= 0.2).sum()),
                        gini=round(C.gini(e), 4), n80=C.n80(e),
                        max_effect=round(float(e.max()), 3), median_effect=round(float(np.median(e)), 4))
    conc["note"] = "两个读出在**同一批**被打分的神经元上算，可直接比较；与 §24.3 的数字不可比（那里只覆盖 304 个）"
    for nm in ("aDN2", "aDN1"):
        c = conc[nm]
        print(f"\n集中度 {nm}：{c['n_scored']} 个打分，Gini {c['gini']}，n80 {c['n80']}，效应 ≥0.2 的 {c['n_required']} 个")

    out = dict(design=dict(readout="aDN2", freq=meta["chosen"], R=R_A, call=CALL, n_stim=len(ids),
                           note="零新仿真：复用 §24.3 的段落（存的是全部活跃神经元的稀疏计数）"),
               baseline=dict(aDN2=base2, mean=round(float(np.mean(base2)), 1), paper=J.PAPER_160["aDN2"],
                             aDN1_same_segments=round(float(np.mean(base1)), 1), aDN1_paper=J.PAPER_160["aDN1"]),
               null_median_single=med2, paper_comparison=comp, required=req, disagreements=disagree,
               aBN1=dict(ratio_aDN2=None if ab is None else round(ab, 4),
                         ratio_aDN1=None if ab1 is None else round(ab1, 4),
                         paper_7e=round(pr[0]["adn2_160"] / J.PAPER_160["aDN2"], 4) if pr else None),
               concentration=conc)
    (WDIR / "adn2_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("\n→ results/screen/jon_paper/adn2_summary.json")


if __name__ == "__main__":
    main()
