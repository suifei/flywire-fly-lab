#!/usr/bin/env python3
"""原型：果蝇扫视一张图，把它"画"出来。先在 Python 验证效果，再移植到浏览器。

链路（每一步都是真的）：
  上传图 → 512×450 相机画面 → FlyGym 真实 ommatidia_id_map 采样 → 721 个小眼
        → flyvis（65 类 × 721 柱，预训练连接组约束网络）→ 各层活动
        → 六边形卷积解码器 → 重建
  果蝇做扫视：图像在视网膜上滑动。**T4/T5 是运动检测器，不动就不响应**，
  所以"动起来"不是为了好看，是让视觉系统真正工作的必要条件。

拼图用的是果蝇自己的运动指令（efference copy —— 它知道自己转了多少），
不是从图像里反推的。没扫到的地方就是空的。

用法：
  conda activate fba
  python vision/draw_proto.py <图片> [--steps 60] [--out results/vision/draw]
"""
import argparse
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
VIS = ROOT / "results/vision"


def hex_xy(u, v):
    return np.c_[u + v / 2.0, v * np.sqrt(3) / 2.0]


def saccade_path(n, amp=90.0):
    """扫视轨迹：快速转 + 停顿，果蝇真实的看世界方式（不是匀速平移）。
    返回每步的 (dx, dy)，单位=相机像素。"""
    t = np.arange(n)
    # 三段扫视：右上 → 左下 → 右下，段间有停顿（停顿时 T4/T5 会衰减，这是真的）
    keys = [(0, 0.0, 0.0), (0.18, 1.0, 0.45), (0.30, 1.0, 0.45),
            (0.52, -1.0, -0.5), (0.64, -1.0, -0.5), (0.86, 0.9, -0.55), (1.0, 0.9, -0.55)]
    ts = np.array([k[0] for k in keys]) * (n - 1)
    xs = np.array([k[1] for k in keys]) * amp
    ys = np.array([k[2] for k in keys]) * amp
    return np.c_[np.interp(t, ts, xs), np.interp(t, ts, ys)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--steps", type=int, default=60)
    ap.add_argument("--dt", type=float, default=1 / 100)
    ap.add_argument("--pad", type=float, default=1.14, help="图比视野大多少（留扫视余量）")
    ap.add_argument("--amp", type=float, default=16.0, help="扫视幅度，相机像素")
    ap.add_argument("--out", default=str(VIS / "draw"))
    a = ap.parse_args()

    import torch
    import flyvis
    from flygym import Fly
    from flygym.examples.vision.vision_network import RetinaMapper
    from PIL import Image

    retina = Fly(enable_vision=True).retina
    idmap = np.asarray(retina.ommatidia_id_map).astype(int)     # (512,450) 0=背景
    npx = np.asarray(retina.num_pixels_per_ommatidia).astype(float)
    H, W = idmap.shape
    perm = RetinaMapper().flygym_to_flyvis(np.arange(721, dtype=np.float32)[None, :]).ravel().astype(int)

    # 原图放大一圈，扫视时才有"画外"的内容可看
    img = Image.open(a.image).convert("L")
    # 整张图要铺满果蝇视野：只留一点余量给扫视。
    # 上一版用 1.9 倍，结果果蝇离图太近，721 个小眼只看到几块色块。
    pad = a.pad
    big = img.resize((int(W * pad), int(H * pad)), Image.LANCZOS)
    B = np.asarray(big, np.float32) / 255.0
    cx, cy = (B.shape[1] - W) / 2, (B.shape[0] - H) / 2

    def sample(dx, dy):
        """把大图在 (dx,dy) 处截出相机画面，再按真实小眼表求平均 → 721 个亮度。"""
        x0 = int(np.clip(cx + dx, 0, B.shape[1] - W)); y0 = int(np.clip(cy + dy, 0, B.shape[0] - H))
        frame = B[y0:y0 + H, x0:x0 + W]
        s = np.bincount(idmap.ravel(), weights=frame.ravel(), minlength=722)[1:]
        return s / npx, frame

    nvw = flyvis.NetworkView("flow/0000/000")
    net = nvw.init_network()
    c = net.connectome
    ntype = np.array([s.decode() for s in c.nodes.type[:]])
    nu = np.asarray(c.nodes.u[:]).astype(int); nvv = np.asarray(c.nodes.v[:]).astype(int)
    order = {}
    for t in set(ntype.tolist()):
        m = ntype == t
        uv = np.stack([nu[m], nvv[m]], 1)
        order[t] = np.where(m)[0][np.lexsort((uv[:, 1], uv[:, 0]))]

    path = saccade_path(a.steps, amp=a.amp)
    retina_seq, act_seq, frames = [], [], []
    with torch.no_grad():
        state = None
        for k in range(a.steps):
            hexg, frame = sample(*path[k])
            hexv = hexg[perm]                       # flygym 序 → flyvis 柱序
            retina_seq.append(hexv); frames.append(frame)
            x = torch.tensor(hexv, dtype=torch.float32).reshape(1, 1, 1, 721)
            st = net.simulate(x, dt=a.dt, initial_state=state, as_states=True)
            st = st[-1] if isinstance(st, list) else st
            state = st
            act_seq.append(st.nodes.activity.detach().cpu().numpy().reshape(-1).copy())
    R = np.array(retina_seq)                        # (steps, 721) 视网膜真值
    A = np.array(act_seq)                           # (steps, 45669)
    print(f"扫视 {a.steps} 步，视网膜 {R.shape}，全网活动 {A.shape}")

    np.savez_compressed(Path(a.out).with_suffix(".npz"),
                        retina=R, act=A, path=path, ntype=ntype, nu=nu, nv=nvv,
                        frames=np.array(frames[::max(1, a.steps // 6)]))
    print(f"写入 {Path(a.out).with_suffix('.npz')}")

    # 各层还剩多少信息：用最简单的逐柱线性回归（无空间核）先探一下上限
    print(f"\n{'类型':8s} {'与视网膜的逐柱相关':>18s}")
    for t in ["R1", "L1", "L2", "Mi1", "Tm1", "T4a", "T4c", "T5a", "TmY3"]:
        if t not in order: continue
        X = A[:, order[t]]
        cc = [np.corrcoef(X[:, j], R[:, j])[0, 1] for j in range(min(721, X.shape[1]))]
        cc = np.array(cc)[~np.isnan(cc)]
        print(f"{t:8s} {np.nanmedian(np.abs(cc)):18.3f}")


if __name__ == "__main__":
    main()
