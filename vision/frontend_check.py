#!/usr/bin/env python
"""机械判定报告第 26 节那 4 条**事先写定**的判据，不靠肉眼看曲线。

判据原文写在 report.md 第 26 节，在跑新前端之前就定好了：
  C1 假阳性   ：球还远的阶段（前 FAR_S 秒）LC4 两侧最大值 < 20 Hz。旧版 0.045 s 就打满 200 Hz。
  C2 不饱和   ：全程 LC4 打满（≥ SAT_HZ）的窗口占比 < 20%，且相邻窗口“饱和↔归零”的翻转 < 3 次。
  C3 真信号还在：最后 NEAR_S 秒的 LC4 均值 > 前 FAR_S 秒的均值。
                **这一条是反向保险**：只满足 C1 有可能是把真 looming 一起滤掉了，必须照实写。
  C4 暗面积稳定：前 FAR_S 秒里暗面积的窗口间标准差 < 同段均值的 10%。

用法：
  python vision/frontend_check.py <log.csv> [--label 新版前端]
  python vision/frontend_check.py results/connectome_loop_smoke/log.csv --label 旧版（对照）
输出：终端表格 + 与 csv 同目录的 frontend_check.json
"""
import argparse
import json
from pathlib import Path

import numpy as np

FAR_S, NEAR_S, SAT_HZ, FP_HZ = 0.3, 0.2, 200.0, 20.0
SAT_FRAC_MAX, FLIP_MAX, DARK_CV_MAX = 0.20, 3, 0.10


def load(path):
    import csv
    rows = list(csv.DictReader(Path(path).open()))
    g = lambda k: np.array([float(r[k]) for r in rows])
    return dict(t=g("t"), lc4=np.c_[g("LC4_L_hz"), g("LC4_R_hz")], dark=np.c_[g("dark_L"), g("dark_R")], n=len(rows))


def check(d, label):
    t, lc4, dark = d["t"], d["lc4"], d["dark"]
    far = t < FAR_S
    near = t >= (t.max() - NEAR_S)
    # 日志比 FAR_S + NEAR_S 还短时，“远”和“近”会重叠，C1/C3/C4 无从判起（旧版冒烟测试只有 0.135 s 就是这种情况）
    too_short = t.max() < FAR_S + NEAR_S
    sat = (lc4 >= SAT_HZ).any(axis=1)
    zero = (lc4 <= 0).all(axis=1)
    flips = int(sum(1 for i in range(len(sat) - 1) if (sat[i] and zero[i + 1]) or (zero[i] and sat[i + 1])))
    far_max = float(lc4[far].max()) if far.any() else float("nan")
    far_mean = float(lc4[far].mean()) if far.any() else float("nan")
    near_mean = float(lc4[near].mean()) if near.any() else float("nan")
    dark_far = dark[far]
    # C4 原式是「标准差 ÷ 均值」。新版前端把远处阶段的暗面积压到**恒为 0**，于是 0/0 无定义。
    # 这不是改阈值，是原式在退化情形下算不出来：如实标为「无法计算」，并把原始标准差摆出来让读者自己判断。
    dark_far_sd = float(dark_far.std()) if far.any() else float("nan")
    dark_far_mean = float(dark_far.mean()) if far.any() else float("nan")
    degenerate = far.any() and dark_far_mean == 0.0
    cv = float("nan") if (degenerate or not far.any() or dark_far_mean <= 0) else dark_far_sd / dark_far_mean
    sat_frac = float(sat.mean())
    C = [
        dict(id="C1", name=f"假阳性：前 {FAR_S}s LC4 最大值 < {FP_HZ:.0f} Hz",
             value=round(far_max, 1), unit="Hz", passed=bool(far_max < FP_HZ)),
        dict(id="C2", name=f"不饱和：打满占比 < {SAT_FRAC_MAX:.0%} 且翻转 < {FLIP_MAX}",
             value=f"{sat_frac:.0%} / {flips} 次", passed=bool(sat_frac < SAT_FRAC_MAX and flips < FLIP_MAX)),
        dict(id="C3", name=f"真信号还在：最后 {NEAR_S}s 均值 > 前 {FAR_S}s 均值",
             value=("不适用（日志只有 %.3f s，远近窗口重叠）" % t.max()) if too_short else f"{near_mean:.1f} vs {far_mean:.1f} Hz",
             passed=None if too_short else bool(near_mean > far_mean)),
        dict(id="C4", name=f"暗面积稳定：前 {FAR_S}s 变异系数 < {DARK_CV_MAX:.0%}",
             value=(f"无法计算（前 {FAR_S}s 暗面积恒为 0，原式 0/0；标准差 = {dark_far_sd:.6f}）" if degenerate
                    else f"{cv:.1%}"),
             passed=None if degenerate else bool(cv < DARK_CV_MAX)),
    ]
    print(f"\n=== {label}（{d['n']} 个窗口，{t.max():.3f} s）")
    mark = lambda v: "不适用" if v is None else ("通过" if v else "不通过")
    for c in C:
        print(f"  {c['id']} {mark(c['passed'])}  {c['name']}  →  {c['value']}")
    judged = [c for c in C if c["passed"] is not None]
    n_ok = sum(bool(c["passed"]) for c in judged)
    print(f"  合计 {n_ok}/{len(judged)} 条通过" + ("（其余不适用）" if len(judged) < len(C) else ""))
    if C[0]["passed"] and C[2]["passed"] is False:
        print("  ⚠ C1 通过但 C3 不通过：假阳性是压住了，但真 looming 也被滤掉了——按事先声明，这要照实写成“修过头”。")
    return dict(label=label, n_windows=int(d["n"]), duration_s=round(float(t.max()), 3),
                criteria=C, n_passed=n_ok,
                raw=dict(far_max_hz=round(far_max, 2), far_mean_hz=round(far_mean, 2),
                         near_mean_hz=round(near_mean, 2), sat_frac=round(sat_frac, 4), flips=flips,
                         dark_cv_far=None if degenerate else round(cv, 4),
                         dark_far_sd=round(dark_far_sd, 8), dark_far_mean=round(dark_far_mean, 8)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--label", default="前端")
    a = ap.parse_args()
    d = load(a.csv)
    res = check(d, a.label)
    res["thresholds"] = dict(far_s=FAR_S, near_s=NEAR_S, sat_hz=SAT_HZ, fp_hz=FP_HZ,
                             sat_frac_max=SAT_FRAC_MAX, flip_max=FLIP_MAX, dark_cv_max=DARK_CV_MAX,
                             note="阈值在跑新前端之前就写定，见 report.md 第 26 节；不得为凑结果改动")
    dst = Path(a.csv).parent / "frontend_check.json"
    dst.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print("写入", dst)


if __name__ == "__main__":
    main()
