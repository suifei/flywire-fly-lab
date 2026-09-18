#!/usr/bin/env python3
"""把果蝇视觉层的活动画成复眼视图（六边形小眼阵列）。

**零仿真**：直接读 results/vision/flyvis_*.npz。那里面除了 30 种细胞类型的
活动 (240帧, 2眼, 721柱)，还存了每根柱的六边形坐标 u/v —— 所以"画出来"
不需要任何重建，只是把已有数据摆回它本来的空间位置。

诚实标注：这画的是 **flyvis 视觉模型**算出的活动，不是连接组 LIF 模型的，
也不是从放电"解码"出来的图像。它是"果蝇视觉系统前端对这个场景的响应"。

用法：
  python3 vision/draw_eye.py loom_L                 # 默认几个代表类型
  python3 vision/draw_eye.py loom_L --types L1,L2,Mi1,T4a,T5a --frames 6
"""
import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
VIS = ROOT / "results/vision"

# 挑这几类做默认：光感受器 → 大单极细胞(ON/OFF分流) → 髓质 → 方向选择
DEFAULT = ["R7", "L1", "L2", "Mi1", "Tm1", "T4a", "T5a", "T4c"]
WHAT = {
    "R7": "光感受器 R7（紫外/颜色）", "R8": "光感受器 R8",
    "L1": "大单极 L1（ON 通道起点）", "L2": "大单极 L2（OFF 通道起点）",
    "L3": "大单极 L3", "L4": "大单极 L4", "L5": "大单极 L5",
    "Mi1": "髓质 Mi1（ON）", "Tm1": "髓质 Tm1（OFF）", "Tm2": "髓质 Tm2（OFF）",
    "Tm9": "髓质 Tm9", "Mi4": "髓质 Mi4", "Mi9": "髓质 Mi9",
    "T4a": "T4a 方向选择（ON·前→后）", "T4b": "T4b（ON·后→前）",
    "T4c": "T4c（ON·上→下）", "T4d": "T4d（ON·下→上）",
    "T5a": "T5a 方向选择（OFF·前→后）", "T5b": "T5b（OFF·后→前）",
    "T5c": "T5c（OFF·上→下）", "T5d": "T5d（OFF·下→上）",
}


def cart(u, v):
    """轴向六边形坐标 → 平面直角坐标（和 connectome_from_flyvis.py 同一套）。"""
    return np.c_[u + v / 2.0, v * np.sqrt(3) / 2.0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stim", help="loom_L / loom_R / recede_L / translate_near_L / translate_far_L")
    ap.add_argument("--types", default=",".join(DEFAULT))
    ap.add_argument("--frames", type=int, default=6, help="沿时间均匀取几帧")
    ap.add_argument("--eye", type=int, default=0, help="0=左眼 1=右眼")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    f = VIS / f"flyvis_{a.stim}.npz"
    if not f.exists():
        sys.exit(f"没有 {f}\n可用：" + " ".join(p.stem[7:] for p in sorted(VIS.glob("flyvis_*.npz"))))
    d = np.load(f)
    t = d["t"]
    types = [x.strip() for x in a.types.split(",") if x.strip()]
    for ty in types:
        if f"act_{ty}" not in d:
            sys.exit(f"没有细胞类型 {ty}")

    xy = cart(d["u_T4a"].astype(float), d["v_T4a"].astype(float))

    # 只画刺激开始之后的帧（t<0 是基线期）
    idx = np.where(t >= 0)[0]
    pick = idx[np.linspace(0, len(idx) - 1, a.frames).round().astype(int)]

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    # matplotlib 默认字体没有 CJK，中文会变成方框且只在 stderr 出一行 warning。
    # 用 macOS 自带的中文字体（按可用性挑第一个存在的）。
    from matplotlib import font_manager
    for fp in ("/System/Library/Fonts/Hiragino Sans GB.ttc",
               "/System/Library/Fonts/STHeiti Medium.ttc"):
        if Path(fp).exists():
            font_manager.fontManager.addfont(fp)
            plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name()
            plt.rcParams["axes.unicode_minus"] = False
            break
    from matplotlib.collections import RegularPolyCollection

    fig, axes = plt.subplots(len(types), len(pick),
                             figsize=(1.55 * len(pick), 1.62 * len(types)))
    axes = np.atleast_2d(axes)
    fig.patch.set_facecolor("#0d1117")

    for r, ty in enumerate(types):
        act = d[f"act_{ty}"][:, a.eye, :].astype(np.float32)
        base = act[t < 0].mean(0)                       # 扣掉基线：画"变化"，不是绝对值
        dv = act - base
        # 全类型统一色标，帧与帧之间才可比；用分位数避免个别柱把色标拉爆
        lim = max(np.percentile(np.abs(dv[pick]), 99), 1e-9)
        for c, k in enumerate(pick):
            ax = axes[r, c]
            ax.set_facecolor("#0d1117")
            col = RegularPolyCollection(
                numsides=6, sizes=(26,), offsets=xy, offset_transform=ax.transData,
                array=dv[k], cmap="RdBu_r", norm=plt.Normalize(-lim, lim),
                linewidths=0, rotation=np.pi / 6)
            ax.add_collection(col)
            ax.set_xlim(xy[:, 0].min() - 1, xy[:, 0].max() + 1)
            ax.set_ylim(xy[:, 1].min() - 1, xy[:, 1].max() + 1)
            ax.set_aspect("equal"); ax.axis("off")
            if r == 0:
                ax.set_title(f"{t[k] * 1000:.0f} ms", color="#8b949e", fontsize=8, pad=4)
        axes[r, 0].text(-0.06, 0.5, WHAT.get(ty, ty), transform=axes[r, 0].transAxes,
                        color="#c9d1d9", fontsize=8, ha="right", va="center")

    fig.suptitle(f"{a.stim} · {'左' if a.eye == 0 else '右'}眼 721 个小眼 · 颜色 = 相对基线的变化"
                 f"（红=变亮/兴奋，蓝=变暗/抑制）",
                 color="#c9d1d9", fontsize=10, y=0.995)
    out = Path(a.out) if a.out else VIS / f"eye_{a.stim}_eye{a.eye}.png"
    fig.tight_layout(rect=[0.06, 0, 1, 0.97])
    fig.savefig(out, dpi=150, facecolor=fig.get_facecolor())
    print(f"写入 {out}")
    print(f"  刺激 {a.stim}，{len(t)} 帧（基线 {int((t < 0).sum())} 帧），画了 {len(pick)} 帧 × {len(types)} 类")
    print(f"  数据来源：flyvis 视觉模型的活动，**不是**连接组 LIF 模型，也不是解码重建")


if __name__ == "__main__":
    main()
