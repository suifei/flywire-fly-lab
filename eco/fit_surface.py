#!/usr/bin/env python3
"""把真脑采样（eco/sample_surface.js）拟合成「大脑响应面」：27 路输入频率 → 12 个读出特征的发放率。

为什么需要它：真脑 v5 一只果蝇只比实时快 1.18 倍（results/eco/audit.json），32 只同时跑是 0.037 倍，进化跑不动。
响应面是**真脑的蒸馏**，不是另一个模型：训练数据全部来自真脑，留出集 R² 逐特征写进输出文件，页面与文档照实引用。

判据（事先写定）：留出集（20%，按样本整条留出）上，转向（dnaL / dnaR）、巨纤维、MN9 的 R² ≥ 0.85 才允许用于进化；
达不到的特征在输出里标 usable=false，仿真里不许用它做决策输入。

**真脑指数**（2026-09-21 加；判据写在看到新结果之前）。第二版响应面在随机输入上过了线，可是在闭环里最要紧的工作点上不准：
「只尝到水」时 MN9 给 7–9 Hz、真脑 13 Hz，结果真脑闭环里喝水时间是响应面的 4 倍（live_check.json 的 L2 没过）。原因是随机采样在这些点附近样本太少。
第三版把「闭环工况」（eco/collect_manifold.js：果蝇真的活着时大脑收到的输入，按感觉组合分层）也交给真脑作答、一起拟合。四条判据：
  T1  随机输入留出集：转向 / 巨纤维 / MN9 的 R²(Hz) ≥ 0.85（原判据，不动）
  T2  闭环工况留出集（20%，整条留出）：同样四个特征 R²(Hz) ≥ 0.85
  T3  关键工作点（闭环工况留出集里的子集）：只尝到水时的 MN9、只尝到糖时的 MN9、有逼近信号（LPLC2 > 50 Hz）时的巨纤维——预测均值与真脑均值的相对误差 ≤ 15%
  T4  闭环行为（eco/live_check.js 的 L2）：真脑里喝水时间占比在响应面的 0.5–2 倍内。这条要在拟合之后另跑，结果由 collect_results.py 并入
  真脑指数 = 闭环工况留出集上、所有会放电的特征的 R²(Hz) 的平均 × 100（只是一个汇总读数；过不过线看 T1–T4）

用法（flygym 环境）：python eco/fit_surface.py  → results/eco/brain_surface.json
"""
import sys, json, glob, os
sys.dont_write_bytecode = True
import pyarrow  # noqa: F401  必须先于 torch
import numpy as np, torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
files = sorted(glob.glob(os.path.join(ROOT, "results/eco/surface_samples_*.json")))
assert files, "先跑 eco/sample_surface.js"
X, Y, meta = [], [], None
for f in files:
    d = json.load(open(f)); meta = meta or d; X += d["X"]; Y += d["Y"]
X, Y = np.array(X, np.float32), np.array(Y, np.float32)
n_random = len(X)
mfiles = sorted(glob.glob(os.path.join(ROOT, "results/eco/surface_manifold_*.json")))
MX, MY = [], []
for f in mfiles:
    d = json.load(open(f)); MX += d["X"]; MY += d["Y"]
MX, MY = np.array(MX, np.float32).reshape(-1, X.shape[1]), np.array(MY, np.float32).reshape(-1, Y.shape[1])
sys.path.insert(0, os.path.join(ROOT, "eco"))
inputs, feats = meta["inputs"], meta["features"]
maxhz = np.array([320.0 if n in ("sugar", "water", "bitter") else 200.0 for n in inputs], np.float32)
Xn, Yl = X / maxhz, np.sqrt(Y)          # sqrt：泊松计数的方差稳定变换。第一版用 log1p，反变换把误差放大，转向的留出 R² 只有 0.67 / 0.79（见 surface_fit_v1.json）

rng = np.random.default_rng(20260920); perm = rng.permutation(len(X)); nte = len(X) // 5
te, tr = perm[:nte], perm[nte:]
mperm = rng.permutation(len(MX)); mte, mtr = mperm[:len(MX) // 5], mperm[len(MX) // 5:]        # 闭环工况：20% 留出，其余并入训练
MXn, MYl = MX / maxhz, np.sqrt(MY)
H = 128
torch.manual_seed(20260920)
net = torch.nn.Sequential(torch.nn.Linear(len(inputs), H), torch.nn.SiLU(), torch.nn.Linear(H, H), torch.nn.SiLU(), torch.nn.Linear(H, len(feats)))
opt = torch.optim.Adam(net.parameters(), lr=3e-3, weight_decay=1e-5)
xt, yt = torch.tensor(np.concatenate([Xn[tr], MXn[mtr]])), torch.tensor(np.concatenate([Yl[tr], MYl[mtr]])); xe, ye = torch.tensor(Xn[te]), torch.tensor(Yl[te])
ysd = yt.std(0).clamp_min(0.05)
for step in range(14000):
    idx = torch.randint(0, len(xt), (256,))
    loss = (((net(xt[idx]) - yt[idx]) / ysd) ** 2).mean()
    opt.zero_grad(); loss.backward(); opt.step()
    if step == 9000:
        for g in opt.param_groups: g["lr"] = 5e-4
with torch.no_grad():
    pe = net(xe).numpy()
def r2(a, b): return float(1 - ((a - b) ** 2).sum() / max(((a - a.mean()) ** 2).sum(), 1e-9))
# 两种口径都报：对数尺度（训练目标）与原始 Hz
rep = {}
for j, f in enumerate(feats):
    hz_true, hz_pred = Y[te][:, j], np.clip(pe[:, j], 0, None) ** 2
    rep[f] = {"r2_t": round(r2(Yl[te][:, j], pe[:, j]), 4), "r2_hz": round(r2(hz_true, hz_pred), 4),
              "mean_hz": round(float(Y[:, j].mean()), 3), "frac_nonzero": round(float((Y[:, j] > 0).mean()), 4),
              "mae_hz": round(float(np.abs(hz_true - hz_pred).mean()), 3)}
    rep[f]["silent"] = bool(rep[f]["frac_nonzero"] < 0.01)               # 采样里几乎从不放电（PAM：连接组招募不到多巴胺神经元，§48 的阴性结果）→ 恒为 0，不算「拟合得好」
    rep[f]["usable"] = bool(rep[f]["r2_hz"] >= 0.85 and not rep[f]["silent"])
need = ["dnaL", "dnaR", "gf", "mn9"]
# ── 噪声天花板（**看到上面的判据没过之后才加的**，探索性）：另一份测试集，同一组输入换 4 个种子各跑一遍。
#    single_vs_rest = 单次试验 对 其余 3 次的均值 的 R²：一个**完美**预测均值的模型，拿单次试验来考，最多也就这个分数；
#    model_vs_mean  = 响应面 对 4 次均值 的 R²：响应面离「真脑的平均反应」有多远。仿真里的噪声由泊松采样另外加回去。
tfiles = sorted(glob.glob(os.path.join(ROOT, "results/eco/surface_test_*.json")))
ceiling = None
if tfiles:
    TX, TR = [], []
    for f in tfiles:
        d = json.load(open(f)); TX += d["X"]; TR += d["YREP"]
    TX, TR = np.array(TX, np.float32) / maxhz, np.array(TR, np.float32)            # TR: [样本, 种子, 特征]
    with torch.no_grad(): tp = np.clip(net(torch.tensor(TX)).numpy(), 0, None) ** 2
    R = TR.shape[1]; ceiling = {"n_inputs": int(len(TX)), "reps": int(R), "per_feature": {}}
    for j, f in enumerate(feats):
        svr = float(np.mean([r2(TR[:, r, j], np.delete(TR[:, :, j], r, axis=1).mean(1)) for r in range(R)]))
        ceiling["per_feature"][f] = {"single_vs_rest": round(svr, 4), "model_vs_mean": round(r2(TR[:, :, j].mean(1), tp[:, j]), 4),
                                     "model_vs_single": round(float(np.mean([r2(TR[:, r, j], tp[:, j]) for r in range(R)])), 4)}
# ── 真脑指数：闭环工况留出集 ──
manifold = None
if len(MX):
    with torch.no_grad(): mp = np.clip(net(torch.tensor(MXn[mte])).numpy(), 0, None) ** 2
    mt, mx = MY[mte], MX[mte]; ix = {n: i for i, n in enumerate(inputs)}; fj = {f: j for j, f in enumerate(feats)}
    per = {f: {"r2_hz": round(r2(mt[:, j], mp[:, j]), 4), "mean_true": round(float(mt[:, j].mean()), 3), "mean_pred": round(float(mp[:, j].mean()), 3), "silent": bool((mt[:, j] > 0).mean() < 0.01)} for j, f in enumerate(feats)}
    def point(name, mask, f):
        n = int(mask.sum()); t = float(mt[mask, fj[f]].mean()) if n else float("nan"); q = float(mp[mask, fj[f]].mean()) if n else float("nan")
        return {"name": name, "feature": f, "n": n, "true_hz": round(t, 2), "pred_hz": round(q, 2), "rel_err": round(abs(q - t) / t, 4) if n and t > 0 else None}
    pts = [point("只尝到水", (mx[:, ix["water"]] > 0) & (mx[:, ix["sugar"]] == 0) & (mx[:, ix["bitter"]] == 0), "mn9"), point("只尝到糖", (mx[:, ix["sugar"]] > 0) & (mx[:, ix["water"]] == 0) & (mx[:, ix["bitter"]] == 0), "mn9"),
           point("有逼近信号", (np.maximum(mx[:, ix["lplc2_L"]], mx[:, ix["lplc2_R"]]) > 50), "gf")]
    live = [f for f in feats if not per[f]["silent"]]
    # 事后补的读数（不改判据）：T2 在 dnaL 上差 0.02，而闭环工况上 dnaL 的单次试验噪声天花板实测只有 0.827（scratch，150 个 DNa 活跃的输入 × 4 个种子）——
    # 0.85 这条线定得高于真脑自己的可重复性。照原线登记「未通过」，另报每个特征相对天花板（随机输入测试集上量的）的比值
    rel = {f: round(per[f]["r2_hz"] / ceiling["per_feature"][f]["single_vs_rest"], 3) for f in feats if ceiling and not per[f]["silent"]} if ceiling else None
    manifold = {"n": int(len(MX)), "r2_over_ceiling": rel, "dnaL_manifold_ceiling_scratch": 0.827, "n_train": int(len(mtr)), "n_test": int(len(mte)), "per_feature": per, "points": pts, "index": round(100 * float(np.mean([per[f]["r2_hz"] for f in live])), 1),
                "T2": bool(all(per[f]["r2_hz"] >= 0.85 for f in need)), "T3": bool(all(p["rel_err"] is not None and p["rel_err"] <= 0.15 for p in pts))}
out = {"inputs": inputs, "features": feats, "maxhz": maxhz.tolist(), "hidden": H, "act": "silu", "target": "sqrt(Hz)",
       "layers": [{"W": l.weight.detach().numpy().round(5).tolist(), "b": l.bias.detach().numpy().round(5).tolist()} for l in net if isinstance(l, torch.nn.Linear)],
       "n_samples": int(len(X)), "n_train": int(len(tr)), "n_test": int(len(te)), "settle_ms": meta["settle_ms"], "read_ms": meta["read_ms"],
       "heldout": rep, "criterion": {"features": need, "r2_hz_min": 0.85, "pass": bool(all(rep[f]["usable"] for f in need)),
                     "note": "事先写定的口径：留出集单次试验、原始 Hz。"}, "noise_ceiling_exploratory": ceiling, "n_random": int(n_random), "manifold": manifold}
# 噪声模型（eco/measure_fano.js 从真脑量的）：每个特征的等效单元数与 Fano 因子——响应面按它加噪声，不再一律按单个泊松单元（那样高估一倍，l2_diagnosis.js）
rn_path = os.path.join(ROOT, "results/eco/readout_noise.json")
if os.path.exists(rn_path):
    rn = json.load(open(rn_path)); out["noise"] = {"window_s": rn["window_s"], "units": rn["units"], "fano": {f: (rn["fano"][f] if rn["fano"][f] is not None and rn["n_used"][f] >= 3 else 0.5) for f in feats}, "source": "eco/measure_fano.js（真脑，0.1 s 计数）；样本 < 3 的特征取 0.5"}
json.dump(out, open(os.path.join(ROOT, "results/eco/brain_surface.json"), "w"))
print(f"样本 {len(X)}（训练 {len(tr)} / 留出 {len(te)}）")
for f in feats: print(f"  {f:11s} R²(Hz) {rep[f]['r2_hz']:+.3f}  R²(变换后) {rep[f]['r2_t']:+.3f}  均值 {rep[f]['mean_hz']:7.2f} Hz  非零 {rep[f]['frac_nonzero']:.2f}  MAE {rep[f]['mae_hz']:.2f}  {'从不放电' if rep[f]['silent'] else '可用' if rep[f]['usable'] else '不可用'}")
if manifold:
    print(f"闭环工况留出集（{manifold['n_test']} 个）：真脑指数 {manifold['index']}")
    for f in feats: print(f"  {f:11s} R²(Hz) {manifold['per_feature'][f]['r2_hz']:+.3f}  真脑均值 {manifold['per_feature'][f]['mean_true']:7.2f}  预测均值 {manifold['per_feature'][f]['mean_pred']:7.2f}")
    for q in manifold["points"]: print(f"  工作点「{q['name']}」{q['feature']}: 真脑 {q['true_hz']} Hz  预测 {q['pred_hz']} Hz  相对误差 {q['rel_err']}  (n={q['n']})")
    print("T2", "通过" if manifold["T2"] else "未通过", " T3", "通过" if manifold["T3"] else "未通过")
print("判据（事先写定，单次试验口径）：", "通过" if out["criterion"]["pass"] else "未通过")
if ceiling:
    print(f"噪声天花板（探索性，{ceiling['n_inputs']} 组输入 × {ceiling['reps']} 个种子）：")
    for f in feats:
        c = ceiling["per_feature"][f]; print(f"  {f:11s} 单次对其余均值 {c['single_vs_rest']:+.3f}   响应面对单次 {c['model_vs_single']:+.3f}   响应面对 4 次均值 {c['model_vs_mean']:+.3f}")
