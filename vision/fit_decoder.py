#!/usr/bin/env python3
"""拟合"果蝇画画"的解码器，并画出四栏对照。

解码器是**六边形卷积**，不是全连接矩阵：
    R̂(u,v) = b + Σ_类型 Σ_偏移 w[类型,du,dv] · act_类型(u+du, v+dv)
理由有二：
  ① 前向就是卷积（604 个核），逆向也该是平移不变的；
  ② 全连接要 721×721×层数 个参数（每层 2 MB），卷积只要几百个 —— 能进浏览器。

诚实性：卷积解码器仍会"补"细节（它学的是训练数据的统计），所以最终展示
**必须同时给出"直接显示的神经活动"**，让人看到重建比真实信号漂亮多少。

用法：conda activate fba && python vision/fit_decoder.py results/vision/draw.npz
"""
import argparse
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
VIS = ROOT / "results/vision"

# 解码用哪些类型：光感受器 + ON/OFF 两路 + 运动四路
LAYERS = {
    "视网膜 R1–R8": ["R1", "R7", "R8"],
    "大单极 L1/L2/L3": ["L1", "L2", "L3"],
    "髓质 Mi/Tm": ["Mi1", "Mi4", "Mi9", "Tm1", "Tm2", "Tm3", "Tm9"],
    "运动 T4/T5": ["T4a", "T4b", "T4c", "T4d", "T5a", "T5b", "T5c", "T5d"],
}


def hex_offsets(radius):
    out = []
    for du in range(-radius, radius + 1):
        for dv in range(-radius, radius + 1):
            if abs(du + dv) <= radius:
                out.append((du, dv))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("npz", nargs="?", default=str(VIS / "draw.npz"))
    ap.add_argument("--radius", type=int, default=2)
    ap.add_argument("--alpha", type=float, default=1.0)
    a = ap.parse_args()

    d = np.load(a.npz, allow_pickle=True)
    R, A = d["retina"], d["act"]
    ntype = np.array([str(x) for x in d["ntype"]]); nu, nv = d["nu"], d["nv"]

    order, uv = {}, None
    for t in set(ntype.tolist()):
        m = ntype == t
        c = np.stack([nu[m], nv[m]], 1)
        o = np.lexsort((c[:, 1], c[:, 0]))
        order[t] = np.where(m)[0][o]
        if len(o) == 721 and uv is None:
            uv = c[o]
    idx = {(int(u), int(v)): i for i, (u, v) in enumerate(uv)}
    taps = hex_offsets(a.radius)
    T, N = R.shape
    print(f"{T} 步 × {N} 柱；卷积半径 {a.radius} → {len(taps)} 个抽头")

    # 留后 1/3 做测试：解码器绝不能在自己训练过的帧上自吹
    ntr = int(T * 2 / 3)
    print(f"训练 {ntr} 步 / 测试 {T-ntr} 步（时间上分开，不是随机划分）")

    results, models = {}, {}
    for name, types in LAYERS.items():
        types = [t for t in types if t in order]
        F = len(types) * len(taps)
        X = np.zeros((T, N, F), np.float32)
        for a_i, t in enumerate(types):
            act = A[:, order[t]]
            if act.shape[1] != N:
                continue
            for b_i, (du, dv) in enumerate(taps):
                src = np.array([idx.get((int(u) + du, int(v) + dv), -1) for u, v in uv])
                col = np.where(src[None, :] >= 0, act[:, np.clip(src, 0, N - 1)], 0.0)
                X[:, :, a_i * len(taps) + b_i] = col
        Xtr = X[:ntr].reshape(-1, F); ytr = R[:ntr].reshape(-1)
        Xte = X[ntr:].reshape(-1, F); yte = R[ntr:].reshape(-1)
        mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-8
        Z = (Xtr - mu) / sd
        w = np.linalg.solve(Z.T @ Z + a.alpha * len(Z) * np.eye(F), Z.T @ (ytr - ytr.mean()))
        b = ytr.mean()
        pr_te = ((Xte - mu) / sd) @ w + b
        r = np.corrcoef(pr_te, yte)[0, 1]
        results[name] = r
        models[name] = dict(types=types, taps=taps, w=w, mu=mu, sd=sd, b=float(b))
        print(f"  {name:16s} 测试集重建相关 r = {r:.3f}")

    np.savez_compressed(VIS / "decoders.npz",
                        **{f"{k}|{kk}": np.asarray(vv, dtype=object) if kk == "types" else np.asarray(vv)
                           for k, m in models.items() for kk, vv in m.items()})
    print(f"\n写入 {VIS/'decoders.npz'}")
    print("  注：r 是在**没训练过的帧**上算的；卷积解码器参数少，但仍会补细节")


if __name__ == "__main__":
    main()
