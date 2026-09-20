#!/usr/bin/env python3
"""把真脑采样（eco/sample_surface.js）拟合成「大脑响应面」：27 路输入频率 → 12 个读出特征的发放率。

为什么需要它：真脑 v5 一只果蝇只比实时快 1.18 倍（results/eco/audit.json），32 只同时跑是 0.037 倍，进化跑不动。
响应面是**真脑的蒸馏**，不是另一个模型：训练数据全部来自真脑，留出集 R² 逐特征写进输出文件，页面与文档照实引用。

判据（事先写定）：留出集（20%，按样本整条留出）上，转向（dnaL / dnaR）、巨纤维、MN9 的 R² ≥ 0.85 才允许用于进化；
达不到的特征在输出里标 usable=false，仿真里不许用它做决策输入。

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
sys.path.insert(0, os.path.join(ROOT, "eco"))
inputs, feats = meta["inputs"], meta["features"]
maxhz = np.array([320.0 if n in ("sugar", "water", "bitter") else 200.0 for n in inputs], np.float32)
Xn, Yl = X / maxhz, np.sqrt(Y)          # sqrt：泊松计数的方差稳定变换。第一版用 log1p，反变换把误差放大，转向的留出 R² 只有 0.67 / 0.79（见 surface_fit_v1.json）

rng = np.random.default_rng(20260920); perm = rng.permutation(len(X)); nte = len(X) // 5
te, tr = perm[:nte], perm[nte:]
H = 128
torch.manual_seed(20260920)
net = torch.nn.Sequential(torch.nn.Linear(len(inputs), H), torch.nn.SiLU(), torch.nn.Linear(H, H), torch.nn.SiLU(), torch.nn.Linear(H, len(feats)))
opt = torch.optim.Adam(net.parameters(), lr=3e-3, weight_decay=1e-5)
xt, yt = torch.tensor(Xn[tr]), torch.tensor(Yl[tr]); xe, ye = torch.tensor(Xn[te]), torch.tensor(Yl[te])
ysd = yt.std(0).clamp_min(0.05)
for step in range(8000):
    idx = torch.randint(0, len(xt), (256,))
    loss = (((net(xt[idx]) - yt[idx]) / ysd) ** 2).mean()
    opt.zero_grad(); loss.backward(); opt.step()
    if step == 5000:
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
out = {"inputs": inputs, "features": feats, "maxhz": maxhz.tolist(), "hidden": H, "act": "silu", "target": "sqrt(Hz)",
       "layers": [{"W": l.weight.detach().numpy().round(5).tolist(), "b": l.bias.detach().numpy().round(5).tolist()} for l in net if isinstance(l, torch.nn.Linear)],
       "n_samples": int(len(X)), "n_train": int(len(tr)), "n_test": int(len(te)), "settle_ms": meta["settle_ms"], "read_ms": meta["read_ms"],
       "heldout": rep, "criterion": {"features": need, "r2_hz_min": 0.85, "pass": bool(all(rep[f]["usable"] for f in need)),
                     "note": "事先写定的口径：留出集单次试验、原始 Hz。"}, "noise_ceiling_exploratory": ceiling}
json.dump(out, open(os.path.join(ROOT, "results/eco/brain_surface.json"), "w"))
print(f"样本 {len(X)}（训练 {len(tr)} / 留出 {len(te)}）")
for f in feats: print(f"  {f:11s} R²(Hz) {rep[f]['r2_hz']:+.3f}  R²(变换后) {rep[f]['r2_t']:+.3f}  均值 {rep[f]['mean_hz']:7.2f} Hz  非零 {rep[f]['frac_nonzero']:.2f}  MAE {rep[f]['mae_hz']:.2f}  {'从不放电' if rep[f]['silent'] else '可用' if rep[f]['usable'] else '不可用'}")
print("判据（事先写定，单次试验口径）：", "通过" if out["criterion"]["pass"] else "未通过")
if ceiling:
    print(f"噪声天花板（探索性，{ceiling['n_inputs']} 组输入 × {ceiling['reps']} 个种子）：")
    for f in feats:
        c = ceiling["per_feature"][f]; print(f"  {f:11s} 单次对其余均值 {c['single_vs_rest']:+.3f}   响应面对单次 {c['model_vs_single']:+.3f}   响应面对 4 次均值 {c['model_vs_mean']:+.3f}")
