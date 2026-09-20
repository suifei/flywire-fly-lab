#!/usr/bin/env python
"""记忆走不走得到运动输出？——mb_conditioning.py 的 B1 用的是单次 1 秒的读数，一个 30 Hz 的下行神经元 1 秒里的泊松涨落就有 ±5 Hz，
所以那里的「命中 5/12」分不清是记忆还是噪声。这里重做，带重复。约 10 分钟。

在页面真正跑的 v5 子回路上：每对气味（3 对不相似的）× 强化物（PAM / PPL1）先各训练一次（paired / mock，流程同 mb_conditioning.py），
把训练后的权重存下来，然后**各测 12 次**（不同随机种子，CS+ 1 秒），比较 paired 与 mock 两组的运动读出。
判据（跑之前写死）：
  M1 某个事先指定的读出（oDN1 / BDN2 / DNa01 / DNa02 / MDN，左右合计）在 paired 与 mock 之间：Welch |t| ≥ 3 且 均值差 ≥ 20%。
  M2 同一个读出在 ≥ 半数（3/6）的「气味对 × 强化物」里都满足 M1，且方向一致 —— 才算「记忆稳定地改变了这个运动输出」。
另外（探索性，不设判据）：把回路里全部下行神经元都扫一遍，列出 |t| 最大的。
输出 results/learn/memory_to_motor.json

第二个臂 no_apl_mbon（python memory_to_motor.py no_apl_mbon → memory_to_motor_no_apl_mbon.json），**只跑这一次，过不过都认**：
  第一臂的结果是阴性，追查发现 35 类 MBON 里只有 9 类对气味有响应，有运动落点的那 4 类（MBON12 / 26 / 27 / 35）一个脉冲都没有——
  它们收到的 APL 抑制是 KC 兴奋的 2–7 倍。APL 在真果蝇里是**不放电**的神经元，靠分级电位做局部抑制，文献里它的功能是反馈抑制 KC、维持稀疏编码
  （Lin et al. 2014 Nat Neurosci；Papadopoulou 2011 Science）；而这个 LIF 模型把它当成普通放电神经元，它顶着不应期上限放电（200–450 Hz），
  经 3,833 个 APL→MBON 突触把大多数 MBON 压死。这一臂切掉 APL→MBON（APL→KC 保留，稀疏编码不受影响），其余不变。
  追加判据：A1 对气味有响应（12 种气味平均 ≥5 Hz）的 MBON 类型数比第一臂多；A2 KC 活跃比例仍 <20%；M1 / M2 同上。
  M2 过了，页面的 v5 才采用这一刀（登记进 PARAMETERS）；不过，就到此为止，不再改模型去凑行为。
"""
import json, itertools, sys
import numpy as np
from mb_circuit import ROOT
from v5_circuit import V5
from plasticity import DopaminePlasticity
READOUTS = {"oDN1": "DNg97", "BDN2": "DNg100", "DNa01": "DNa01", "DNa02": "DNa02", "MDN": "MDN"}
N_TEST, N_PAIRS, ETA, REPS = 12, 3, 0.003, 5


def main():
    arm = sys.argv[1] if len(sys.argv) > 1 else "v5"; c = V5()
    if arm == "no_apl_mbon": e = c.edges("APL", "MBON"); c.w0[e] = 0; print(f"切掉 APL→MBON {len(e)} 条边")
    d = json.load(open(ROOT / "results/dodge/subcircuit_v5.json")); sup = np.array(d["supers"]); dn = np.where(sup == "descending")[0]; gl = sorted(c.glomeruli)
    ro = {k: c.of_type(t) for k, t in READOUTS.items()}; out = dict(arm=arm, n_test=N_TEST, rows=[])
    # 气味响应普查：12 种气味（6 对）下各类 MBON 的平均发放、KC 活跃比例
    acc = {}; kcf = []; mbon = c.idx["MBON"]; kc = c.idx["Kenyon_Cell"]
    for k in range(6):
        perm = np.random.default_rng(20260920 + k).permutation(gl).tolist()
        for od in (perm[:20], perm[20:40]):
            s = c.sim(1); r = np.zeros(c.n)
            for g in od: r[c.glomeruli[g]] = 200
            s.advance(100, r); cnt = s.advance(1000, r); kcf.append(float((cnt[kc] > 0).mean()))
            for m in mbon: acc.setdefault(str(c.typ[m]), []).append(float(cnt[m]))
    out["mbon_type_mean_hz"] = {t: float(np.mean(v)) for t, v in acc.items()}; out["n_mbon_types"] = len(acc); out["n_mbon_types_responsive"] = int(sum(np.mean(v) >= 5 for v in acc.values()))
    out["motor_mbon_mean_hz"] = {t: out["mbon_type_mean_hz"][t] for t in ("MBON12", "MBON26", "MBON27", "MBON35")}; out["max_kc_frac"] = max(kcf)
    print(f"[{arm}] 有响应的 MBON 类型 {out['n_mbon_types_responsive']}/{len(acc)}；有运动落点的四类 {out['motor_mbon_mean_hz']}；KC 活跃比例最大 {max(kcf):.1%}", flush=True)
    def rates(gs, da=None):
        r = np.zeros(c.n)
        for g in gs: r[c.glomeruli[g]] = 200
        if da: r[np.array(c.groups[da + "_left"] + c.groups[da + "_right"])] = 30
        return r
    rest = np.zeros(c.n)
    def present(s, pl, r, ms, learn):
        tot = np.zeros(c.n)
        for _ in range(ms // 10):
            cnt = s.advance(10, r); tot += cnt
            if learn: pl.step(cnt, 10)
        return tot / (ms / 1000)
    for k, da in itertools.product(range(N_PAIRS), ("PAM", "PPL1")):
        perm = np.random.default_rng(20260920 + k).permutation(gl).tolist(); A, B = perm[:20], perm[20:40]; W = {}
        for cond in ("mock", "paired"):
            s = c.sim(1); pl = DopaminePlasticity(c, s, eta=ETA)
            for _ in range(REPS): present(s, pl, rates(A, da if cond == "paired" else None), 1000, True); present(s, pl, rest, 500, True); present(s, pl, rates(B), 1000, True); present(s, pl, rest, 500, True)
            W[cond] = s.w.copy()
        T = {}
        for cond in ("mock", "paired"):
            runs = []
            for seed in range(100, 100 + N_TEST): s = c.sim(seed); s.w[:] = W[cond]; s.advance(100, rates(A)); runs.append(s.advance(1000, rates(A)).astype(float))
            T[cond] = np.array(runs)
        def welch(idx):
            a, b = T["paired"][:, idx].sum(1), T["mock"][:, idx].sum(1); se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
            return float(a.mean()), float(b.mean()), float((a.mean() - b.mean()) / se) if se > 0 else 0.0
        row = dict(pair=k, reinforcer=da, readouts={})
        for name, idx in ro.items():
            pa, mo, t = welch(idx); row["readouts"][name] = dict(paired=pa, mock=mo, t=t, hit=bool(abs(t) >= 3 and abs(pa - mo) >= 0.2 * max(mo, 1e-9)), direction=int(np.sign(pa - mo)))
        scan = []
        for i in dn:
            pa, mo, t = welch(np.array([i]))
            if pa + mo >= 2: scan.append(dict(type=str(c.typ[i]), side=str(c.side[i]), paired=pa, mock=mo, t=t))
        row["top_descending"] = sorted(scan, key=lambda x: -abs(x["t"]))[:8]; out["rows"].append(row)
        print(f"第 {k} 对 {da}: " + " ".join(f"{n} {v['mock']:.1f}→{v['paired']:.1f}(t={v['t']:+.1f}{'*' if v['hit'] else ''})" for n, v in row["readouts"].items()) + " | 扫描最强: " + ", ".join(f"{x['type']}{x['side'][0]} {x['mock']:.0f}→{x['paired']:.0f}(t={x['t']:+.1f})" for x in row["top_descending"][:4]), flush=True)
    summ = {}
    for name in READOUTS:
        hits = [r["readouts"][name] for r in out["rows"] if r["readouts"][name]["hit"]]; dirs = {h["direction"] for h in hits}
        summ[name] = dict(n_hit=len(hits), consistent=bool(len(dirs) == 1), stable=bool(len(hits) >= len(out["rows"]) / 2 and len(dirs) == 1))
    out["summary"] = summ; out["M2_any_stable"] = bool(any(v["stable"] for v in summ.values())); out["n_rows"] = len(out["rows"]); out["max_hits"] = max(v["n_hit"] for v in summ.values())
    json.dump(out, open(ROOT / ("results/learn/memory_to_motor.json" if arm == "v5" else f"results/learn/memory_to_motor_{arm}.json"), "w"), ensure_ascii=False, indent=1); print(summ, "M2:", out["M2_any_stable"])


if __name__ == "__main__": main()
