#!/usr/bin/env python
"""全脑复核：report §11.4 里「嗅觉一给就全脑失控（~8,000 个神经元），找不到源头」——把 ALLN 改成抑制性之后，全脑还失控吗？约 3 分钟，峰值内存约 2 GB。

在蘑菇体回路里已经查到源头是触角叶局部神经元（ALLN）的递质符号（mb_odor_coding.py）。这里回到**全脑**（138,639 个神经元、全部连接）验证，
用的是和 §11.4 同一个刺激（DM1 左侧 ORN，20 Hz 与 100 Hz），同一个判据。仿真核是 learn/lif.py（与 Brian2 同方程同参数；不是 Brian2 本身）。
判据（§11.4 原话，跑之前已定）：被刺激神经元之外活跃的神经元 < 2,000 才算不失控。
  预测：raw 失控（复现 §11.4）；alln_inh 三个种子都不失控。
第二步（python fullbrain_alln.py lateral，结果并进同一个 JSON）：不失控之后，§11.4 当时没法回答的那个问题就能问了——
  单侧给气味，下行神经元有没有左右偏侧？判据沿用 §11.4 原话：LI =（左侧下行神经元脉冲 − 右侧）÷ 总数，
  「左刺激与右刺激的 LI 符号相反，且 |LI| 都 ≥ 0.2」才算有偏侧。DM1 100 Hz、500 ms、3 个种子取均值。另外单独报 DNa01+DNa02（转向）的左右脉冲。
输出 results/learn/fullbrain_alln.json
"""
import json, sys, time
import numpy as np
import mb_circuit as mb

T_MS, SEEDS, RATES = 500, (1, 2, 3), (20, 100)


def main():
    ann, fids, con = mb.load(); N = len(fids); out = {"t_ms": T_MS, "n": int(N), "arms": {}}
    for arm, kw in (("raw", {}), ("alln_inh", dict(force_inhibitory=["ALLN"]))):
        t0 = time.time(); c = mb.Circuit(ann, fids, con, extra=range(N), **kw); stim = c.of_type("ORN_DM1", "left"); rows = []
        print(f"[{arm}] {c.n:,} 神经元、{len(c.w0):,} 条连接（{time.time() - t0:.0f}s）", flush=True)
        for rate in RATES:
            for seed in SEEDS:
                s = c.sim(seed); r = np.zeros(c.n); r[stim] = rate; cnt = s.advance(T_MS, r); act = cnt > 0; act[stim] = False
                row = dict(rate_hz=rate, seed=seed, active_others=int(act.sum()), kc_frac=float(act[c.idx["Kenyon_Cell"]].mean()), runaway=bool(act.sum() >= 2000),
                           dn_active=int(act[np.where(ann.super_class.fillna("?").to_numpy()[c.sel] == "descending")[0]].sum()))
                rows.append(row); print(f"   DM1 左 {rate:3d} Hz 种子 {seed}：其他活跃 {row['active_others']:6d} · KC {row['kc_frac']:.1%} · 下行神经元 {row['dn_active']} → {'失控' if row['runaway'] else '不失控'}", flush=True)
        out["arms"][arm] = dict(rows=rows, n_runaway=int(sum(r["runaway"] for r in rows)), n_runs=len(rows), max_active=int(max(r["active_others"] for r in rows)), median_active=float(np.median([r["active_others"] for r in rows])))
        del c
    out["prediction_holds"] = bool(out["arms"]["raw"]["n_runaway"] > 0 and out["arms"]["alln_inh"]["n_runaway"] == 0)
    json.dump(out, open(mb.ROOT / "results/learn/fullbrain_alln.json", "w"), ensure_ascii=False, indent=1); print("预测成立：", out["prediction_holds"])


def lateral():
    ann, fids, con = mb.load(); N = len(fids); path = mb.ROOT / "results/learn/fullbrain_alln.json"; out = json.load(open(path))
    c = mb.Circuit(ann, fids, con, extra=range(N), force_inhibitory=["ALLN"]); sup = ann.super_class.fillna("?").to_numpy()[c.sel]; dn = sup == "descending"
    L, R = np.where(dn & (c.side == "left"))[0], np.where(dn & (c.side == "right"))[0]; dna = {sd: np.concatenate([c.of_type(t, sd) for t in ("DNa01", "DNa02")]) for sd in ("left", "right")}; res = {}
    for stim_side in ("left", "right"):
        rows = []
        for seed in SEEDS:
            s = c.sim(seed); r = np.zeros(c.n); r[c.of_type("ORN_DM1", stim_side)] = 100; cnt = s.advance(T_MS, r)
            rows.append(dict(dn_left=int(cnt[L].sum()), dn_right=int(cnt[R].sum()), dna_left=int(cnt[dna["left"]].sum()), dna_right=int(cnt[dna["right"]].sum()), active=int((cnt > 0).sum())))
        l, rr = sum(x["dn_left"] for x in rows), sum(x["dn_right"] for x in rows); res[stim_side] = dict(rows=rows, LI=float((l - rr) / max(l + rr, 1)), dn_left=l, dn_right=rr, dna_left=sum(x["dna_left"] for x in rows), dna_right=sum(x["dna_right"] for x in rows))
        print(f"DM1 {stim_side} 100 Hz：下行神经元脉冲 左 {l} / 右 {rr} → LI {res[stim_side]['LI']:+.2f}；DNa01+02 左 {res[stim_side]['dna_left']} / 右 {res[stim_side]['dna_right']}", flush=True)
    res["lateralized"] = bool(np.sign(res["left"]["LI"]) != np.sign(res["right"]["LI"]) and min(abs(res["left"]["LI"]), abs(res["right"]["LI"])) >= 0.2)
    out["lateralization"] = res; json.dump(out, open(path, "w"), ensure_ascii=False, indent=1); print("有偏侧：", res["lateralized"])


if __name__ == "__main__": lateral() if len(sys.argv) > 1 and sys.argv[1] == "lateral" else main()
