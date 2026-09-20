#!/usr/bin/env python
"""蘑菇体能不能给不同气味不同的稀疏编码？——学习的前提。约 3 分钟。

背景：report §11.4 里嗅觉输入在全脑 LIF 里是「全或无」的失控（~8,000 个神经元），当时没找到源头。
这里在蘑菇体回路（9,001 个神经元）里分三个臂重做：
  raw        原样（Shiu 模型的递质符号）
  no_alln    去掉触角叶局部神经元（ALLN，429 个）
  alln_inh   ALLN 发出的突触一律改成抑制性
为什么动 ALLN：文献里果蝇触角叶的局部神经元绝大多数是 GABA 能或谷氨酸能，两者在触角叶里都是抑制性的
（Wilson & Laurent 2005 J Neurosci；Olsen & Wilson 2008 Nature；Liu & Wilson 2013 PNAS——谷氨酸经 GluClα 抑制）。
而模型用的递质预测把它们发出的突触有一半标成了乙酰胆碱 / 5-羟色胺 / 多巴胺，按 Shiu 的规则一律当兴奋。
这是对**递质符号**的纠正，不是行为规则；属于手选的建模决定，登记在台账 PARAMETERS 里。

气味是物理刺激：一种气味 = 一组嗅小球的感受神经元被驱动。面板 = 3 种有文献标签的 + 8 种合成气味（53 个小球里随机 6 个，种子固定）。

判据（跑之前写死）：
  C1 不失控：每种气味下活跃的凯尼恩细胞（KC）< 20%。
  C2 稀疏且有响应：合成气味下活跃 KC 的比例中位数在 1%–15%（真果蝇约 5–10%，Honegger 2011；Lin 2014）。
  C3 气味特异：不同气味的活跃 KC 集合，Jaccard 中位数 < 0.5；同一气味换随机种子，Jaccard 中位数 > 不同气味的。
  主臂 = 三条全过、且改动最小的那个（raw 优先，其次 alln_inh，再次 no_alln）。
输出 results/learn/mb_odor_coding.json
"""
import json, itertools, time
import numpy as np
import mb_circuit as mb

RATE, T_SETTLE, T_READ, N_SYN_ODORS, K_GLOM = 100, 100, 400, 8, 6
LABELED = {"醋（DM1+VA2）": ["ORN_DM1", "ORN_VA2"], "土臭素（DA2）": ["ORN_DA2"], "二氧化碳（V）": ["ORN_V"]}


def panel(c):
    gl = sorted({t for t in c.typ[c.idx["olfactory"]] if t.startswith("ORN_")}); rng = np.random.default_rng(20260920)
    od = dict(LABELED)
    for k in range(N_SYN_ODORS): od[f"合成{k + 1}"] = sorted(rng.choice(gl, K_GLOM, replace=False).tolist())
    return od


def respond(c, gloms, seed, rate=RATE):
    s = c.sim(seed); r = np.zeros(c.n)
    for g in gloms: r[c.of_type(g)] = rate
    s.advance(T_SETTLE, r); return s.advance(T_READ, r)


def jac(a, b):
    u = (a | b).sum(); return float((a & b).sum() / u) if u else float("nan")


def main():
    ann, fids, con = mb.load(); tags = ["ALLN", "ALPN", "APL", "DAN", "DPM", "Kenyon_Cell", "MBON", "olfactory"]
    arms = {"raw": {}, "alln_inh": dict(force_inhibitory=["ALLN"]),
            "no_alln": dict(drop_pairs=[("ALLN", t) for t in tags] + [(t, "ALLN") for t in tags if t != "ALLN"])}
    out = {"rate_hz": RATE, "read_ms": T_READ, "arms": {}}
    for arm, kw in arms.items():
        t0 = time.time(); c = mb.Circuit(ann, fids, con, **kw); od = panel(c); kc = c.idx["Kenyon_Cell"]; res = {}; act = {}
        for name, gl in od.items():
            cnt = [respond(c, gl, seed) for seed in (1, 2)]; a = [x[kc] > 0 for x in cnt]; act[name] = a
            res[name] = dict(gloms=gl, kc_frac=float(a[0].mean()), kc_frac_seed2=float(a[1].mean()), same_odor_jaccard=jac(a[0], a[1]),
                             active={t: int((cnt[0][i] > 0).sum()) for t, i in c.idx.items()}, rate_hz={t: float(cnt[0][i].sum() / len(i) / (T_READ / 1000)) for t, i in c.idx.items()})
        syn = [k for k in od if k.startswith("合成")]; responsive = [k for k in od if res[k]["kc_frac"] > 0]
        cross = [jac(act[a][0], act[b][0]) for a, b in itertools.combinations(responsive, 2)]; same = [res[k]["same_odor_jaccard"] for k in responsive]
        fr = [res[k]["kc_frac"] for k in od]; med_syn = float(np.median([res[k]["kc_frac"] for k in syn]))
        crit = dict(C1_no_runaway=bool(max(fr) < 0.20), C2_sparse=bool(0.01 <= med_syn <= 0.15),
                    C3_specific=bool(len(cross) > 0 and np.nanmedian(cross) < 0.5 and np.nanmedian(same) > np.nanmedian(cross)))
        out["arms"][arm] = dict(n=int(c.n), n_edges=int(len(c.w0)), odors=res, max_kc_frac=float(max(fr)), median_kc_frac_synthetic=med_syn,
                                cross_odor_jaccard_median=float(np.nanmedian(cross)) if cross else None, same_odor_jaccard_median=float(np.nanmedian(same)) if same else None,
                                n_responsive_odors=len(responsive), criteria=crit, all_pass=bool(all(crit.values())))
        print(f"[{arm}] {time.time() - t0:.0f}s  KC 活跃比例 max {max(fr):.1%} · 合成气味中位 {med_syn:.1%} · 不同气味 Jaccard {out['arms'][arm]['cross_odor_jaccard_median']} · 同气味 {out['arms'][arm]['same_odor_jaccard_median']} · 判据 {crit}", flush=True)
    out["main_arm"] = next((a for a in ("raw", "alln_inh", "no_alln") if out["arms"][a]["all_pass"]), None)
    print("主臂：", out["main_arm"])
    json.dump(out, open(mb.ROOT / "results/learn/mb_odor_coding.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__": main()
