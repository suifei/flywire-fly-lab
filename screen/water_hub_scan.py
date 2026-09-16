#!/usr/bin/env python
"""
水通路的 CB0051 全扫描：160 Hz 水刺激下全部活跃神经元，每个都和 CB0051 一起敲。

由来：糖通路上 CB0883 是“单独敲看不出来、配对才显形”的枢纽（16.2 节全扫描）；水通路的双敲除里 CB0051 扮演同样的角色
（10 对稳定协同里 7 对含它）。把同一套全扫描搬到水通路，能回答一个更一般的问题：**“枢纽”是这两条通路各自的偶然，
还是连接组里反复出现的结构？**

事先写定（运行前写好，与 16.2 节 CB0883 全扫描同口径）：
  刺激 160 Hz 水，读出同一个 MN9，段落安排与 screen/water_screen.py 相同；输入实现 r = 0…11。
  两阶段：阶段 A 全部候选 × 前 6 个实现；阶段 B 把 Δ = 实测效应 − 独立预期效应 ≥ 0.05 的候选补到 12 个实现。
  零参照沿用水通路的两条（50 个随机单敲除的每实现中位数 / 20 对对照对的中位数）。
  判据：E = 1 − 比值；独立预期 E_exp = 1 − (1 − E_a)(1 − E_hub)；协同 = E_ab > E_exp + 0.1；留一 = 去掉任一实现判定不变。
  报告时把“单独敲本来就降低 MN9”（可解释为备份通路）与“单独敲反而升高”（乘性预期不适用）分开列——这是 16.2 节的教训。
输出 results/screen/water/hub_scan_summary.json
用法（brain-fly-cpu 环境，套 scratch/memguard.sh）：python screen/water_hub_scan.py run|analyze
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import sugar_mn9_screen as S  # noqa: E402
import water_screen as W  # noqa: E402
import segments as SEG  # noqa: E402

HUB = 720575940622010964      # 占位，run 时按 cell_type 查 CB0051
HUB_TYPE = "CB0051"
STAGE_A_R, STAGE_B_R = 6, 12
PICK_DELTA, MARGIN = 0.05, 0.1
DIR = W.WDIR / "hub_scan"
FI = 0


def ctx():
    W.setup()
    fids, fid2i, N, mn9, base, _res = W.load_state()
    repo = SEG.Repo([W.WDIR / "chunks", DIR], watch={"mn9": mn9})
    plan = json.loads((W.WDIR / "plan.json").read_text())
    ann = pd.read_csv(S.ANNOT, sep="\t", low_memory=False, usecols=["root_id", "cell_type", "top_nt", "super_class"]).drop_duplicates("root_id").set_index("root_id")
    hub_fid = next(int(f) for f in ann.index[ann.cell_type == HUB_TYPE] if int(f) in fid2i and base[0][fid2i[int(f)]] > 0)
    return fids, fid2i, mn9, base, repo, plan, ann, fid2i[hub_fid], hub_fid


def med(repo, base, mn9, sils, R):
    return [float(np.median([_counts(repo, base, mn9, s, R)[r] for s in sils])) for r in range(R)]


def _counts(repo, base, mn9, sil, R):
    out = []
    for r in range(R):
        if any(base[r][n] > 0 for n in sil):
            out.append(repo.get((FI, r, tuple(sorted(sil))), field="mn9", default=None))
        else:
            out.append(int(base[r][mn9]))
    return out


def verdict(e_ab, e_exp):
    return "协同" if e_ab > e_exp + MARGIN else ("亚可加" if e_ab < e_exp - MARGIN else "可加")


def cmd_run():
    DIR.mkdir(parents=True, exist_ok=True)
    fids, fid2i, mn9, base, repo, plan, ann, hub, hub_fid = ctx()
    active = sorted({int(n) for r in range(STAGE_A_R) for n in np.nonzero(base[r])[0]} - {mn9, hub})
    print(f"枢纽 {HUB_TYPE} = {hub_fid}；候选 {len(active)} 个（水 160 Hz 下活跃）", flush=True)
    keys_a = SEG.needed_keys(base, STAGE_A_R, [[n] for n in active] + [[n, hub] for n in active] + [[hub]], fi=FI)
    repo.fill(keys_a, lambda: S.Screen(), DIR, "stageA")
    med_s = med(repo, base, mn9, [[fid2i[f]] for f in plan["null_single"]], STAGE_A_R)
    med_d = med(repo, base, mn9, [tuple(sorted((fid2i[a], fid2i[b]))) for a, b in plan["null_pairs"]], STAGE_A_R)
    mh = _counts(repo, base, mn9, [hub], STAGE_A_R)
    rh = sum(mh) / sum(med_s)
    picks, rows = [], []
    for n in active:
        mc, mab = _counts(repo, base, mn9, [n], STAGE_A_R), _counts(repo, base, mn9, [n, hub], STAGE_A_R)
        assert None not in mc and None not in mab, f"阶段 A 缺段：{int(fids[n])}"
        rc, rab = sum(mc) / sum(med_s), sum(mab) / sum(med_d)
        d = (1 - rab) - (1 - rc * rh)
        rows.append(dict(fid=int(fids[n]), ratio_single=round(rc, 4), ratio_pair=round(rab, 4), delta=round(d, 4)))
        if d >= PICK_DELTA:
            picks.append(n)
    print(f"阶段 A：{len(rows)} 个候选全部算出（枢纽自身 {rh:.2f}），Δ ≥ {PICK_DELTA} 的 {len(picks)} 个进入阶段 B", flush=True)
    (W.WDIR / "hub_scan_stageA.json").write_text(json.dumps(dict(hub=str(hub_fid), hub_type=HUB_TYPE, hub_ratio=round(rh, 4),
                                                                 picks=[int(fids[n]) for n in picks],
                                                                 rows=sorted(rows, key=lambda x: -x["delta"])), ensure_ascii=False, indent=1))
    keys_b = SEG.needed_keys(base, STAGE_B_R, [[n] for n in picks + [hub]] + [[n, hub] for n in picks]
                             + [[fid2i[f]] for f in plan["null_single"]]
                             + [tuple(sorted((fid2i[a], fid2i[b]))) for a, b in plan["null_pairs"]], fi=FI)
    repo.fill(keys_b, lambda: S.Screen(), DIR, "stageB")
    print("全部完成", flush=True)


def cmd_analyze():
    fids, fid2i, mn9, base, repo, plan, ann, hub, hub_fid = ctx()
    stageA = json.loads((W.WDIR / "hub_scan_stageA.json").read_text())
    picks = [fid2i[f] for f in stageA["picks"]]
    R = STAGE_B_R
    med_s = med(repo, base, mn9, [[fid2i[f]] for f in plan["null_single"]], R)
    med_d = med(repo, base, mn9, [tuple(sorted((fid2i[a], fid2i[b]))) for a, b in plan["null_pairs"]], R)
    mh = _counts(repo, base, mn9, [hub], R)
    rh = sum(mh) / sum(med_s)
    rows, missing = [], []
    for n in picks:
        mc, mab = _counts(repo, base, mn9, [n], R), _counts(repo, base, mn9, [n, hub], R)
        if None in mc or None in mab:
            missing.append(int(fids[n])); continue
        rc, rab = sum(mc) / sum(med_s), sum(mab) / sum(med_d)
        e_exp, e_ab = 1 - rc * rh, 1 - rab
        v = verdict(e_ab, e_exp)
        loo = [verdict(1 - (sum(mab) - mab[j]) / (sum(med_d) - med_d[j]),
                       1 - ((sum(mc) - mc[j]) / (sum(med_s) - med_s[j])) * ((sum(mh) - mh[j]) / (sum(med_s) - med_s[j]))) for j in range(R)]
        f = int(fids[n])
        a = ann.loc[f] if f in ann.index else None
        rows.append(dict(fid=str(f), cell_type=None if a is None else a.cell_type, nt=None if a is None else a.top_nt,
                         super_class=None if a is None else a.super_class, ratio_single=round(rc, 4), ratio_with_hub=round(rab, 4),
                         effect_expected=round(e_exp, 4), effect_observed=round(e_ab, 4), delta=round(e_ab - e_exp, 4),
                         verdict=v, loo_stable=bool(all(x == v for x in loo))))
    if missing:
        print(f"⚠️ {len(missing)} 个候选缺段，未计入：{missing[:10]}", flush=True)
    rows.sort(key=lambda x: -x["delta"])
    syn = [r for r in rows if r["verdict"] == "协同"]
    stable = [r for r in syn if r["loo_stable"]]
    backup = [r for r in stable if r["ratio_single"] < 1]
    out = dict(design=dict(hub=HUB_TYPE, hub_fid=str(hub_fid), freq=W.FREQ, R=R, stage_a_R=STAGE_A_R, pick_delta=PICK_DELTA, margin=MARGIN),
               hub_ratio_single=round(rh, 4), n_candidates=len(stageA["rows"]), n_stage_b=len(rows),
               n_missing=len(missing),
               summary=dict(n_synergy=len(syn), n_stable=len(stable), n_backup=len(backup),
                            n_opposite=len(stable) - len(backup),
                            n_subadditive_all=sum(1 for r in stageA["rows"] if r["delta"] <= -0.05),
                            n_hidden=sum(1 for r in backup if r["ratio_single"] > 0.8)),
               rows=rows)
    (W.WDIR / "hub_scan_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"{HUB_TYPE} 单独敲 {rh:.2f}；{len(stageA['rows'])} 个候选里 {len(rows)} 个进入阶段 B："
          f"协同 {len(syn)}（留一稳定 {len(stable)}；其中可解释为备份的 {len(backup)}，单独敲反而升高的 {len(stable) - len(backup)}）")
    print(f"全部候选里亚可加（Δ ≤ −0.05）{out['summary']['n_subadditive_all']} 个\n")
    PN = {"CB0192": "Zorro", "CB0553": "Roundup", "CB0616": "G2N-1", "AN_GNG_30": "Clavicle", "CB0499": "Rattle",
          "DNge173": "Bract", "CB0008": "Usnea", "CB0579": "Tulip", "Z_vPNml1": "Tophat", "CB0062": "Phantom"}
    for r in backup:
        nm = r["cell_type"] or r["fid"]
        nm = f"{nm} = {PN[nm]}" if nm in PN else nm
        print(f"  {nm:20s} {str(r['nt'])[:4]:5s} | 单独 {r['ratio_single']:.2f} → 加 {HUB_TYPE} {r['ratio_with_hub']:.2f} | Δ {r['delta']:+.2f} {'留一稳' if r['loo_stable'] else ''}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "analyze"])
    (cmd_run if ap.parse_args().cmd == "run" else cmd_analyze)()
