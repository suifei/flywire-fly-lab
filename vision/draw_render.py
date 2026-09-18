#!/usr/bin/env python3
"""画出"果蝇画画"的对照图：原图 / 复眼接收 / 神经活动直显 / 解码重建 / 扫视拼图。

用法：conda activate fba && python vision/draw_render.py results/vision/draw.npz <原图>
"""
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
VIS = ROOT / "results/vision"
sys.path.insert(0, str(ROOT / "vision"))
from fit_decoder import LAYERS, hex_offsets   # noqa: E402


def hex_xy(uv):
    return np.c_[uv[:, 0] + uv[:, 1] / 2.0, uv[:, 1] * np.sqrt(3) / 2.0]


def build_X(A, order, uv, idx, types, taps, N):
    F = len(types) * len(taps)
    T = A.shape[0]
    X = np.zeros((T, N, F), np.float32)
    for ai, t in enumerate(types):
        act = A[:, order[t]]
        if act.shape[1] != N:
            continue
        for bi, (du, dv) in enumerate(taps):
            src = np.array([idx.get((int(u) + du, int(v) + dv), -1) for u, v in uv])
            X[:, :, ai * len(taps) + bi] = np.where(src[None, :] >= 0, act[:, np.clip(src, 0, N - 1)], 0.0)
    return X


def main():
    npz = sys.argv[1] if len(sys.argv) > 1 else str(VIS / "draw.npz")
    orig = sys.argv[2] if len(sys.argv) > 2 else None
    d = np.load(npz, allow_pickle=True)
    R, A, path = d["retina"], d["act"], d["path"]
    ntype = np.array([str(x) for x in d["ntype"]]); nu, nv = d["nu"], d["nv"]

    order, uv = {}, None
    for t in set(ntype.tolist()):
        m = ntype == t
        c = np.stack([nu[m], nv[m]], 1); o = np.lexsort((c[:, 1], c[:, 0]))
        order[t] = np.where(m)[0][o]
        if len(o) == 721 and uv is None:
            uv = c[o]
    idx = {(int(u), int(v)): i for i, (u, v) in enumerate(uv)}
    taps = hex_offsets(2); T, N = R.shape; ntr = int(T * 2 / 3)

    recon = {}
    for name, types in LAYERS.items():
        types = [t for t in types if t in order]
        X = build_X(A, order, uv, idx, types, taps, N)
        Xtr = X[:ntr].reshape(-1, X.shape[2]); ytr = R[:ntr].reshape(-1)
        mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-8
        Z = (Xtr - mu) / sd
        w = np.linalg.solve(Z.T @ Z + 1.0 * len(Z) * np.eye(X.shape[2]), Z.T @ (ytr - ytr.mean()))
        recon[name] = (((X.reshape(-1, X.shape[2]) - mu) / sd) @ w + ytr.mean()).reshape(T, N)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    for fp in ("/System/Library/Fonts/Hiragino Sans GB.ttc",):
        if Path(fp).exists():
            font_manager.fontManager.addfont(fp)
            plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name()
    from matplotlib.collections import RegularPolyCollection
    xy = hex_xy(uv.astype(float))

    def hexplot(ax, val, cmap="gray", lim=None, title=None):
        lim = lim or (float(np.percentile(val, 1)), float(np.percentile(val, 99)))
        ax.add_collection(RegularPolyCollection(
            numsides=6, sizes=(30,), offsets=xy, offset_transform=ax.transData,
            array=val, cmap=cmap, norm=plt.Normalize(*lim), linewidths=0, rotation=np.pi / 6))
        ax.set_xlim(xy[:, 0].min() - 1, xy[:, 0].max() + 1)
        ax.set_ylim(xy[:, 1].min() - 1, xy[:, 1].max() + 1)
        ax.set_aspect("equal"); ax.axis("off"); ax.set_facecolor("#0d1117")
        if title: ax.set_title(title, color="#c9d1d9", fontsize=9, pad=5)

    k = T - 3                                  # 用测试集里的一帧（解码器没见过）
    cols = ["原图（真值）", "721 个小眼接收到的"] + [f"{n}\n解码重建" for n in LAYERS]
    fig, axes = plt.subplots(2, len(cols), figsize=(2.3 * len(cols), 5.2))
    fig.patch.set_facecolor("#0d1117")

    if orig and Path(orig).exists():
        from PIL import Image
        axes[0, 0].imshow(np.asarray(Image.open(orig).convert("L")), cmap="gray")
    axes[0, 0].axis("off"); axes[0, 0].set_title(cols[0], color="#c9d1d9", fontsize=9)
    hexplot(axes[0, 1], R[k], title=cols[1])
    for i, (name, types) in enumerate(LAYERS.items()):
        hexplot(axes[0, 2 + i], recon[name][k], title=cols[2 + i])

    # 第二行：同一层的**神经活动直显**（没有解码器参与）
    axes[1, 0].axis("off")
    axes[1, 0].text(0.5, 0.5, "下排 =\n神经活动直接显示\n（没有解码器）",
                    color="#8b949e", fontsize=9, ha="center", va="center",
                    transform=axes[1, 0].transAxes)
    axes[1, 1].axis("off")
    for i, (name, types) in enumerate(LAYERS.items()):
        t0 = [t for t in types if t in order][0]
        v = A[k, order[t0]]
        hexplot(axes[1, 2 + i], v, cmap="RdBu_r",
                lim=(-np.abs(v).max(), np.abs(v).max()), title=f"{t0} 活动")

    fig.suptitle("果蝇扫视这张图 · 上排=解码重建（会补细节）  下排=神经元里真有的活动",
                 color="#c9d1d9", fontsize=11, y=0.99)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    out = VIS / "draw_compare.png"
    fig.savefig(out, dpi=150, facecolor=fig.get_facecolor())
    print(f"写入 {out}")
    print(f"  展示的是第 {k} 帧（测试集，解码器没训练过）")


if __name__ == "__main__":
    main()
