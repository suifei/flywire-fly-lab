#!/usr/bin/env python
"""强化信号走不走得通连接组？——糖 / 苦 / 热 / 湿 这些感觉，能不能靠真实接线把多巴胺神经元（DAN）叫起来。约 2 分钟。

背景：report §11.1 在全脑上测过：不失控时，糖味下 PAM 0/307 放电。那次只测了糖和苦。
这里在一个专门为这个问题裁的回路里重测，并加上热和湿：
  成员 = 蘑菇体回路（9,001）∪ 子回路 v4（6,296）∪ 所有落在「感觉 → DAN」≤3 跳路径上的神经元（边 ≥3 突触）
  ALLN 取抑制性（mb_odor_coding.py 选出的主臂）。

判据（跑之前写死）：
  「这一路感觉能叫起多巴胺」= 不失控（活跃神经元 < 2,000）且 某一簇（PAM 或 PPL1）里 ≥5 个神经元发放 ≥5 Hz。
  只要糖→PAM 或 热/苦→PPL1 有一条成立，学习实验的教学信号就走连接组；都不成立，就得手接一根线并如实登记。
输出 results/learn/reinforcement_route.json
"""
import json, numpy as np, scipy.sparse as sp
import mb_circuit as mb, subcircuit as v1

RATES, T_SETTLE, T_READ = (50, 100, 200), 100, 400


def build(ann, fids, con):
    N = len(fids); fid2i = {int(f): i for i, f in enumerate(fids)}
    v4 = json.load(open(mb.ROOT / "results/dodge/subcircuit_v4.json")); extra = {fid2i[int(f)] for f in v4["fids"]}
    pre, post = con.Presynaptic_Index.to_numpy(), con.Postsynaptic_Index.to_numpy(); strong = con.Connectivity.to_numpy() >= 3
    A = sp.csr_matrix((np.ones(strong.sum(), np.float32), (pre[strong], post[strong])), shape=(N, N)); AT = A.T.tocsr()
    cls = ann.cell_class.fillna("?").to_numpy(); typ = ann.cell_type.fillna("?").to_numpy()
    S = {"糖 SUGAR": np.where(typ == "LB3")[0], "苦 BITTER": np.where(np.isin(typ, ["LB1a,LB1d", "LB1b", "LB1c"]))[0],
         "热 THERMO": np.where(cls == "thermosensory")[0], "湿 HYGRO": np.where(cls == "hygrosensory")[0]}
    dT = v1.bfs_hops(AT, np.where(cls == "DAN")[0])
    for s in S.values(): extra |= set(np.where(v1.bfs_hops(A, s) + dT <= 3)[0].tolist()) | set(s.tolist())
    return mb.Circuit(ann, fids, con, extra=sorted(extra), force_inhibitory=["ALLN"]), S


def main():
    ann, fids, con = mb.load(); c, S = build(ann, fids, con); print(f"回路：{c.n:,} 个神经元、{len(c.w0):,} 条连接", flush=True)
    dan = c.idx["DAN"]; cluster = np.array([t[:4] if t.startswith("PPL") else t[:3] for t in c.typ[dan]]); out = {"n": int(c.n), "n_edges": int(len(c.w0)), "conditions": []}
    for name, full in S.items():
        idx = c.loc[full]; idx = idx[idx >= 0]
        for rate in RATES:
            s = c.sim(1); r = np.zeros(c.n); r[idx] = rate; s.advance(T_SETTLE, r); cnt = s.advance(T_READ, r); hz = cnt / (T_READ / 1000)
            active = int((cnt > 0).sum()) - len(idx); row = dict(sense=name, rate_hz=rate, n_stim=int(len(idx)), active_others=active, runaway=bool(active >= 2000))
            for cl in ("PAM", "PPL1", "PPL2"):
                h = hz[dan[cluster == cl]]; row[cl] = dict(n=int(len(h)), firing_ge5hz=int((h >= 5).sum()), any_spike=int((h > 0).sum()), mean_hz=float(h.mean()))
            row["recruits_dan"] = bool(not row["runaway"] and max(row["PAM"]["firing_ge5hz"], row["PPL1"]["firing_ge5hz"]) >= 5)
            out["conditions"].append(row)
            print(f"  {name} {rate:3d} Hz：其他活跃 {active:5d}  PAM ≥5Hz {row['PAM']['firing_ge5hz']}/{row['PAM']['n']}  PPL1 ≥5Hz {row['PPL1']['firing_ge5hz']}/{row['PPL1']['n']}  → {'成立' if row['recruits_dan'] else '不成立'}", flush=True)
    out["any_route"] = bool(any(r["recruits_dan"] for r in out["conditions"]))
    out["max_dan_ge5hz_without_runaway"] = int(max([max(r["PAM"]["firing_ge5hz"], r["PPL1"]["firing_ge5hz"]) for r in out["conditions"] if not r["runaway"]] or [0]))
    json.dump(out, open(mb.ROOT / "results/learn/reinforcement_route.json", "w"), ensure_ascii=False, indent=1); print("有没有一条走得通：", out["any_route"])


if __name__ == "__main__": main()
