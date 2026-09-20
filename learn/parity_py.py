#!/usr/bin/env python
"""页面引擎 vs Python：同一份 v5 子回路、同一个条件化流程（气味 A 配 PAM 5 次，对照 mock），比统计量。
用法：python learn/parity_py.py protocol → node learn/parity_js.js → python learn/parity_py.py run → python learn/parity_py.py compare
判据（写在跑之前）：4 个种子的均值上，
  P1 未配对气味 B 的 MBON 总发放：两边相差 ≤15%
  P2 paired ÷ mock 的 CS+ 比值（PAM 隔室加权）：两边相差 ≤0.15
  P3 paired 之后各 MBON 的 KC 输入剩余强度：两边的 Pearson r ≥ 0.95
  P4 活跃 KC 数：两边相差 ≤15%
输出 results/learn/parity.json"""
import json, sys
import numpy as np
from mb_circuit import ROOT
from v5_circuit import V5
from plasticity import DopaminePlasticity
PROTO = ROOT / "results/learn/parity_protocol.json"


def protocol():
    c = V5(); gl = sorted(c.glomeruli); perm = np.random.default_rng(4242).permutation(gl).tolist()
    json.dump(dict(A=sorted(perm[:20]), B=sorted(perm[20:40]), dan="PAM", odor_hz=200, dan_hz=30, eta=0.003, tau_e_ms=200.0, reps=5, seeds=[1, 2, 3, 4]), open(PROTO, "w"), ensure_ascii=False, indent=1); print("→", PROTO)


def run():
    pr = json.load(open(PROTO)); c = V5(); mbon = c.idx["MBON"]; kc = c.idx["Kenyon_Cell"]; out = dict(seeds=pr["seeds"], runs=[])
    A = np.concatenate([c.glomeruli[g] for g in pr["A"]]); B = np.concatenate([c.glomeruli[g] for g in pr["B"]]); dan = np.array(c.groups[pr["dan"] + "_left"] + c.groups[pr["dan"] + "_right"])
    for seed in pr["seeds"]:
        for cond in ("mock", "paired"):
            s = c.sim(seed); pl = DopaminePlasticity(c, s, eta=pr["eta"], tau_e_ms=pr["tau_e_ms"])
            def present(odor, da, ms, learn):
                r = np.zeros(c.n)
                if odor is not None: r[odor] = pr["odor_hz"]
                if da: r[dan] = pr["dan_hz"]
                tot = np.zeros(c.n)
                for _ in range(ms // 10):
                    cnt = s.advance(10, r); tot += cnt
                    if learn: pl.step(cnt, 10)
                return tot
            for _ in range(pr["reps"]): present(A, cond == "paired", 1000, True); present(None, False, 500, True); present(B, False, 1000, True); present(None, False, 500, True)
            present(None, False, 1000, False); ta = present(A, False, 1000, False); present(None, False, 1000, False); tb = present(B, False, 1000, False)
            out["runs"].append(dict(seed=seed, cond=cond, mbon_A=ta[mbon].tolist(), mbon_B=tb[mbon].tolist(), kc_active_A=int((ta[kc] > 0).sum()), kc_active_B=int((tb[kc] > 0).sum()), strength=pl.strength()[mbon].tolist()))
            print(f"seed {seed} {cond}: MBON A {ta[mbon].sum():.0f} B {tb[mbon].sum():.0f}", flush=True)
    json.dump(out, open(ROOT / "results/learn/parity_py.json", "w"))


def compare():
    c = V5(); mbon = c.idx["MBON"]; pam = np.array(c.groups["PAM_left"] + c.groups["PAM_right"]); d = c.edges("DAN", "MBON"); d = d[c.nsyn[d] >= 3]
    tot = np.zeros(c.n); part = np.zeros(c.n); np.add.at(tot, c.post[d], c.nsyn[d]); k = np.isin(c.pre[d], pam); np.add.at(part, c.post[d][k], c.nsyn[d][k]); wq = np.divide(part, tot, out=np.zeros(c.n), where=tot > 0)[mbon]
    S = {}
    for side in ("js", "py"):
        runs = json.load(open(ROOT / f"results/learn/parity_{side}.json"))["runs"]; g = lambda cond, key: np.mean([np.array(r[key], float) for r in runs if r["cond"] == cond], axis=0)
        S[side] = dict(mbon_B_mock=float(g("mock", "mbon_B").sum()), ratio_csp=float((wq * g("paired", "mbon_A")).sum() / max((wq * g("mock", "mbon_A")).sum(), 1e-9)),
                       ratio_csm=float((wq * g("paired", "mbon_B")).sum() / max((wq * g("mock", "mbon_B")).sum(), 1e-9)), strength=g("paired", "strength"), kc=float(np.mean([r["kc_active_A"] for r in runs])))
    rel = lambda a, b: abs(a - b) / max(abs(a), abs(b), 1e-9); r = float(np.corrcoef(S["js"]["strength"], S["py"]["strength"])[0, 1])
    crit = dict(P1_mbon_rate=bool(rel(S["js"]["mbon_B_mock"], S["py"]["mbon_B_mock"]) <= 0.15), P2_learning_ratio=bool(abs(S["js"]["ratio_csp"] - S["py"]["ratio_csp"]) <= 0.15),
                P3_strength_r=bool(r >= 0.95), P4_kc_active=bool(rel(S["js"]["kc"], S["py"]["kc"]) <= 0.15))
    out = dict(js={k: v for k, v in S["js"].items() if k != "strength"}, py={k: v for k, v in S["py"].items() if k != "strength"}, strength_pearson=r, criteria=crit, all_pass=bool(all(crit.values())))
    json.dump(out, open(ROOT / "results/learn/parity.json", "w"), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__": {"protocol": protocol, "run": run, "compare": compare}[sys.argv[1]]()
