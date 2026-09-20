#!/usr/bin/env python
"""条件化实验：把一种气味和多巴胺配对，蘑菇体记得住吗？记的是不是**这一种**气味？约 20 分钟。

回路：蘑菇体（9,001）∪ 子回路 v4（6,296）= 15,055 个神经元，ALLN 取抑制性（mb_odor_coding.py 的主臂）。
可塑性：learn/plasticity.py（多巴胺门控的 KC→MBON 压低；多巴胺去哪个隔室由连接组的 DAN→MBON 突触数决定）。
强化：连接组自己叫不起多巴胺神经元（reinforcement_route.py，阴性），所以这里**直接驱动** PPL1 或 PAM 整簇 30 Hz——
  等价于真果蝇实验里用光遗传激活多巴胺神经元代替电击 / 糖（Claridge-Chang 2009 Cell；Aso 2012 PLoS Genet；Liu 2012 Nature）。

第一次尝试（结果留在 mb_conditioning_v1.json，判据 L1 / L2 / B1 不过）暴露了三个设计问题，第二次（本脚本）在**看新结果之前**改掉：
  ① 多巴胺用全局常数归一 → PAM（307 个）的多巴胺是 PPL1（16 个）的二十多倍，PPL1 几乎学不动。改成按 MBON 归一（plasticity.py）。
  ② eta = 0.02 太大：1 秒配对就把突触压到 7%，任何在配对期间偶然放过一个脉冲的 KC 都被连坐。改成 0.003（5 秒配对 ≈ 压掉 80%）。
  ③ 气味对是各自独立随机抽的 12 个小球，平均有近四分之一的小球重合——那是两种**相似**的气味，泛化是应该的。
     现在主实验用**不重合**的两组小球（不相似的气味），另加一组「一半小球相同」的相似气味，只描述泛化程度、不设判据。
  ④ 指标从「96 个 MBON 总发放」改成「**被强化的那几个隔室**的 MBON 发放」：权重 = 该 MBON 的多巴胺输入里来自这一簇（PAM 或 PPL1）的比例，
     只由连接组决定，和结果无关。总发放会被不相干隔室稀释。
  校准（eta、K、频率）只在另外的种子（5、6、999）上做过，下面的 6 对没有看过。

气味：每对 = 53 个嗅小球随机排列后的前 20 个（A）和接下来 20 个（B），ORN 200 Hz。相似气味对：B 的前 10 个小球换成 A 的前 10 个。
每对 (A = CS+, B = CS−) × 强化物 {PPL1, PAM} × 3 种训练：
  paired    5 ×（A + 多巴胺 1 s → 歇 0.5 s → B 单独 1 s → 歇 0.5 s）
  mock      同上但不给多巴胺 —— 基线。**必须有这一臂**：探索时发现有的气味自己就会叫起 PPL1（KC→DAN 是真实连接），单独闻几次响应就掉。
  unpaired  多巴胺单独给 1 s → 歇 2 s → A、B 各单独 1 s，5 轮 —— 给了多巴胺但不和气味同时
训练后（可塑性关掉）各闻 1 s，读 MBON 总发放和运动读出。

判据（跑之前写死；「比值」= 该训练后被强化隔室的 MBON 发放 ÷ mock 训练后的，取所有不相似气味对的中位数；阈值与第一次相同）：
  L1 学会了：     paired 的 CS+ 比值 ≤ 0.7
  L2 只记这一种： paired 的 CS− 比值 ≥ 0.85
  L3 要同时出现： unpaired 的 CS+ 比值 ≥ 0.85
  L4 隔室分工：   PPL1 配对和 PAM 配对各自压低的 MBON（KC 输入强度比 mock 低 10% 以上）集合，Jaccard < 0.5
  B1 记忆走得到运动输出：paired vs mock，CS+ 下某个运动读出（oDN1 / BDN2 / DNa01 / DNa02 / MDN）的变化 ≥20% 且 ≥ 2 Hz，而 CS− 下同一读出变化 < 10%，在 ≥ 半数气味对里成立
对照臂 shuffle_pn_kc：把 PN→KC 的突触后 KC 随机重排（每个 PN 发出多少突触、权重都不变）。
  预期（写在前面）：**照样学得会**——文献里 PN→KC 的接线本来就接近随机（Caron et al. 2013 Nature），学习靠的是稀疏随机展开，不靠具体哪根线。
输出 results/learn/mb_conditioning.json
"""
import json, sys, time, itertools
import numpy as np
import mb_circuit as mb
from plasticity import DopaminePlasticity

ETA, TAU_E, DAN_HZ, ODOR_HZ, K_GLOM, N_PAIRS, N_SIMILAR, REPS, CHUNK = 0.003, 200.0, 30, 200, 20, 6, 3, 5, 10
READOUTS = {"oDN1": "DNg97", "BDN2": "DNg100", "DNa01": "DNa01", "DNa02": "DNa02", "MDN": "MDN"}


def build(ann, fids, con, shuffle=False):
    fid2i = {int(f): i for i, f in enumerate(fids)}; v4 = json.load(open(mb.ROOT / "results/dodge/subcircuit_v4.json"))
    c = mb.Circuit(ann, fids, con, extra=[fid2i[int(f)] for f in v4["fids"]], force_inhibitory=["ALLN"])
    if shuffle:
        e = c.edges("ALPN", "Kenyon_Cell"); rng = np.random.default_rng(7); c.post = c.post.copy(); c.post[e] = rng.permutation(c.post[e])
    return c


class Trial:
    def __init__(self, c, seed):
        self.c = c; self.s = c.sim(seed); self.pl = DopaminePlasticity(c, self.s, eta=ETA, tau_e_ms=TAU_E); self.learn = True

    def run(self, rates, ms):
        tot = np.zeros(self.c.n)
        for _ in range(int(ms / CHUNK)):
            cnt = self.s.advance(CHUNK, rates); tot += cnt
            if self.learn: self.pl.step(cnt, CHUNK)
        return tot / (ms / 1000)


def main():
    arms = sys.argv[1:] or ["connectome", "shuffle_pn_kc"]; ann, fids, con = mb.load(); out = {"params": dict(eta=ETA, tau_e_ms=TAU_E, dan_hz=DAN_HZ, odor_hz=ODOR_HZ, k_glom=K_GLOM, reps=REPS), "arms": {}}
    path = mb.ROOT / "results/learn/mb_conditioning.json"
    if path.exists(): out["arms"] = json.load(open(path)).get("arms", {})
    for arm in arms:
        t0 = time.time(); c = build(ann, fids, con, shuffle=(arm == "shuffle_pn_kc")); mbon = c.idx["MBON"]; dan = c.idx["DAN"]
        drive = {"PPL1": dan[[t.startswith("PPL1") for t in c.typ[dan]]], "PAM": dan[[t.startswith("PAM") for t in c.typ[dan]]]}
        ro = {k: c.of_type(t) for k, t in READOUTS.items()}; gl = sorted({t for t in c.typ[c.idx["olfactory"]] if t.startswith("ORN_")})
        pairs = []
        for k in range(N_PAIRS + N_SIMILAR):
            perm = np.random.default_rng(20260920 + k).permutation(gl).tolist(); A, B = perm[:K_GLOM], perm[K_GLOM:2 * K_GLOM]
            if k >= N_PAIRS: B = A[:K_GLOM // 2] + B[K_GLOM // 2:]
            pairs.append((k, sorted(A), sorted(B), k >= N_PAIRS))
        def rates(gs, da=None):
            r = np.zeros(c.n)
            for g in gs: r[c.of_type(g)] = ODOR_HZ
            if da is not None: r[drive[da]] = DAN_HZ
            return r
        # 隔室权重：MBON j 的多巴胺输入（≥3 突触的边）里来自 PAM / PPL1 的比例
        d = c.edges("DAN", "MBON"); d = d[c.nsyn[d] >= 3]; tot = np.zeros(c.n); part = {da: np.zeros(c.n) for da in drive}; np.add.at(tot, c.post[d], c.nsyn[d])
        for da in drive: k_ = np.isin(c.pre[d], drive[da]); np.add.at(part[da], c.post[d][k_], c.nsyn[d][k_])
        comp_w = {da: np.divide(part[da], tot, out=np.zeros(c.n), where=tot > 0)[mbon] for da in drive}
        rest = np.zeros(c.n)
        print(f"[{arm}] {c.n:,} 神经元；{N_PAIRS} 对不相似气味 + {N_SIMILAR} 对相似气味", flush=True)
        rows = []
        for (ia, A, B, similar), da in itertools.product(pairs, drive):
            ib = ia; rec = {}
            for cond in ("mock", "paired", "unpaired"):
                t = Trial(c, 1)
                for _ in range(REPS):
                    if cond == "unpaired": t.run(rates([], da), 1000); t.run(rest, 2000); t.run(rates(A), 1000); t.run(rest, 500); t.run(rates(B), 1000); t.run(rest, 500)
                    else: t.run(rates(A, da if cond == "paired" else None), 1000); t.run(rest, 500); t.run(rates(B), 1000); t.run(rest, 500)
                t.learn = False; t.run(rest, 1000); st = t.pl.strength()[mbon]; test = {}
                for nm, o in (("A", A), ("B", B)):
                    hz = t.run(rates(o), 1000); t.run(rest, 1000); test[nm] = dict(mbon_sum=float(hz[mbon].sum()), comp={k_: float((comp_w[k_] * hz[mbon]).sum()) for k_ in drive}, mbon=hz[mbon].tolist(), readouts={k: float(hz[i].mean()) for k, i in ro.items()})
                rec[cond] = dict(test=test, strength=st.tolist())
            ratio = lambda cond, o: rec[cond]["test"][o]["comp"][da] / max(rec["mock"]["test"][o]["comp"][da], 1e-9)
            dep = [int(m) for m in np.where(np.array(rec["paired"]["strength"]) < 0.9 * np.array(rec["mock"]["strength"]))[0]]
            motor = {}
            for k in ro:
                pa, ma = rec["paired"]["test"]["A"]["readouts"][k], rec["mock"]["test"]["A"]["readouts"][k]; pb, mb_ = rec["paired"]["test"]["B"]["readouts"][k], rec["mock"]["test"]["B"]["readouts"][k]
                motor[k] = dict(csp_paired=pa, csp_mock=ma, csm_paired=pb, csm_mock=mb_,
                                hit=bool(abs(pa - ma) >= 2 and abs(pa - ma) >= 0.2 * max(ma, 1e-9) and abs(pb - mb_) < 0.1 * max(mb_, 1.0)))
            row = dict(pair=ia, similar=bool(similar), reinforcer=da, mock_A=rec["mock"]["test"]["A"]["comp"][da], mock_B=rec["mock"]["test"]["B"]["comp"][da],
                       total_ratio_csp=rec["paired"]["test"]["A"]["mbon_sum"] / max(rec["mock"]["test"]["A"]["mbon_sum"], 1e-9), total_ratio_csm=rec["paired"]["test"]["B"]["mbon_sum"] / max(rec["mock"]["test"]["B"]["mbon_sum"], 1e-9),
                       ratio_paired_csp=ratio("paired", "A"), ratio_paired_csm=ratio("paired", "B"), ratio_unpaired_csp=ratio("unpaired", "A"),
                       depressed_mbon=dep, depressed_types=sorted({str(c.typ[mbon[m]]) for m in dep}), motor=motor, motor_hit=bool(any(v["hit"] for v in motor.values())))
            rows.append(row)
            print(f"  第 {ia} 对{'（相似）' if similar else ''} {da:4s}: mock A {row['mock_A']:.0f} B {row['mock_B']:.0f} | paired CS+ ×{row['ratio_paired_csp']:.2f} CS− ×{row['ratio_paired_csm']:.2f} | unpaired CS+ ×{row['ratio_unpaired_csp']:.2f} | 压低 {row['depressed_types']} | 运动 { {k: (round(v['csp_mock'], 1), round(v['csp_paired'], 1)) for k, v in motor.items() if v['csp_mock'] + v['csp_paired'] > 0} }", flush=True)
        main_rows = [r for r in rows if not r["similar"]]; sim_rows = [r for r in rows if r["similar"]]
        ok = [r for r in main_rows if r["mock_A"] >= 5 and r["mock_B"] >= 5]   # mock 之后该隔室对这气味本来就不响应的，比值没有意义，单独计数
        med = lambda k: float(np.median([r[k] for r in ok])) if ok else None
        dp = {da: set().union(*[set(r["depressed_mbon"]) for r in rows if r["reinforcer"] == da]) if rows else set() for da in drive}
        jac = len(dp["PPL1"] & dp["PAM"]) / max(len(dp["PPL1"] | dp["PAM"]), 1)
        crit = dict(L1_learned=bool(ok and med("ratio_paired_csp") <= 0.7), L2_specific=bool(ok and med("ratio_paired_csm") >= 0.85), L3_contingent=bool(ok and med("ratio_unpaired_csp") >= 0.85),
                    L4_compartments=bool(jac < 0.5 and len(dp["PPL1"]) > 0 and len(dp["PAM"]) > 0), B1_reaches_motor=bool(main_rows and sum(r["motor_hit"] for r in main_rows) >= len(main_rows) / 2))
        out["arms"][arm] = dict(n=int(c.n), n_edges=int(len(c.w0)), n_rows=len(main_rows), n_rows_usable=len(ok),
                                similar_median_ratio_csp=float(np.median([r["ratio_paired_csp"] for r in sim_rows if r["mock_A"] >= 5 and r["mock_B"] >= 5] or [np.nan])),
                                similar_median_ratio_csm=float(np.median([r["ratio_paired_csm"] for r in sim_rows if r["mock_A"] >= 5 and r["mock_B"] >= 5] or [np.nan])),
                                median_ratio_paired_csp=med("ratio_paired_csp"), median_ratio_paired_csm=med("ratio_paired_csm"), median_ratio_unpaired_csp=med("ratio_unpaired_csp"),
                                depressed_types={da: sorted({str(c.typ[mbon[m]]) for m in dp[da]}) for da in drive}, n_depressed={da: len(dp[da]) for da in drive}, compartment_jaccard=float(jac),
                                n_motor_hit=int(sum(r["motor_hit"] for r in main_rows)), criteria=crit, rows=rows)
        print(f"[{arm}] {time.time() - t0:.0f}s  中位比值 paired CS+ {med('ratio_paired_csp')} · CS− {med('ratio_paired_csm')} · unpaired {med('ratio_unpaired_csp')} · 隔室 Jaccard {jac:.2f} · 运动命中 {out['arms'][arm]['n_motor_hit']}/{len(main_rows)} · 相似气味 CS+ {out['arms'][arm]['similar_median_ratio_csp']:.2f} CS− {out['arms'][arm]['similar_median_ratio_csm']:.2f} · 判据 {crit}", flush=True)
        json.dump(out, open(path, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__": main()
