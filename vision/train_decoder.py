#!/usr/bin/env python3
"""训练"果蝇画画"的解码器，并导出成浏览器用的 JSON。

关键：**必须在多张图上训练**。只用一张图训练的解码器会把那张图的统计背下来，
换一张上传图就崩。这里生成 N 张风格各异的图，**留出整张图做测试**
（不是留几帧——同一张图的不同帧太相似，那样测出来的分数是假的）。

解码器形式：六边形卷积（平移不变），
    R̂(u,v) = b + Σ_类型 Σ_偏移 w[类型,du,dv] · act_类型(u+du,v+dv)
参数只有几百个，能进浏览器；全连接要 721×721×层数，每层 2 MB。

用法：conda activate fba && python vision/train_decoder.py [--n 24] [--steps 40]
"""
import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
VIS = ROOT / "results/vision"

LAYERS = {
    "retina": ("视网膜 R1–R8", ["R1", "R7", "R8"]),
    "lamina": ("大单极 L1–L5", ["L1", "L2", "L3", "L4", "L5"]),
    "medulla": ("髓质 Mi/Tm", ["Mi1", "Mi4", "Mi9", "Tm1", "Tm2", "Tm3", "Tm9"]),
    "motion": ("运动 T4/T5", ["T4a", "T4b", "T4c", "T4d", "T5a", "T5b", "T5c", "T5d"]),
}


def hex_offsets(radius):
    return [(du, dv) for du in range(-radius, radius + 1)
            for dv in range(-radius, radius + 1) if abs(du + dv) <= radius]


def make_image(rng, W, H):
    """造一张训练图。风格要杂，否则解码器只学会一种图案。"""
    from PIL import Image, ImageDraw, ImageFilter
    kind = rng.integers(0, 5)
    im = Image.new("L", (W, H), int(rng.integers(10, 80)))
    d = ImageDraw.Draw(im)
    if kind == 0:                                   # 几何块
        for _ in range(rng.integers(3, 9)):
            x, y = rng.integers(0, W), rng.integers(0, H)
            s = int(rng.integers(W // 12, W // 3))
            f = int(rng.integers(60, 255))
            (d.ellipse if rng.random() < .5 else d.rectangle)([x, y, x + s, y + s], fill=f)
    elif kind == 1:                                 # 条纹（考验分辨率）
        p = int(rng.integers(6, 40)); ang = rng.random() < .5
        for i in range(0, max(W, H), p):
            box = [i, 0, i + p // 2, H] if ang else [0, i, W, i + p // 2]
            d.rectangle(box, fill=int(rng.integers(120, 255)))
    elif kind == 2:                                 # 多尺度噪声
        a = rng.random((int(rng.integers(4, 40)),) * 2) * 255
        im = Image.fromarray(a.astype(np.uint8)).resize((W, H), Image.BICUBIC)
    elif kind == 3:                                 # 渐变 + 斜边
        a = np.add.outer(np.linspace(0, 255, H), np.linspace(0, 120, W)) / 1.5
        im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(im)
        for _ in range(rng.integers(1, 4)):
            pts = [(int(rng.integers(0, W)), int(rng.integers(0, H))) for _ in range(3)]
            d.polygon(pts, fill=int(rng.integers(0, 255)))
    else:                                           # 细线 + 文字状结构
        for _ in range(rng.integers(6, 20)):
            d.line([int(rng.integers(0, W)), int(rng.integers(0, H)),
                    int(rng.integers(0, W)), int(rng.integers(0, H))],
                   fill=int(rng.integers(100, 255)), width=int(rng.integers(1, 6)))
    if rng.random() < .35:
        im = im.filter(ImageFilter.GaussianBlur(float(rng.random() * 2)))
    return im


def saccade(n, amp):
    keys = [(0, 0, 0), (.18, 1, .45), (.30, 1, .45), (.52, -1, -.5),
            (.64, -1, -.5), (.86, .9, -.55), (1, .9, -.55)]
    t = np.arange(n); ts = np.array([k[0] for k in keys]) * (n - 1)
    return np.c_[np.interp(t, ts, [k[1] * amp for k in keys]),
                 np.interp(t, ts, [k[2] * amp for k in keys])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=24, help="训练+测试图片总数")
    ap.add_argument("--steps", type=int, default=40)
    ap.add_argument("--radius", type=int, default=2)
    ap.add_argument("--alpha", type=float, default=1.0)
    a = ap.parse_args()

    import torch, flyvis
    from flygym import Fly
    from flygym.examples.vision.vision_network import RetinaMapper
    from PIL import Image

    retina = Fly(enable_vision=True).retina
    idmap = np.asarray(retina.ommatidia_id_map).astype(int)
    npx = np.asarray(retina.num_pixels_per_ommatidia).astype(float)
    H, W = idmap.shape
    perm = RetinaMapper().flygym_to_flyvis(np.arange(721, dtype=np.float32)[None, :]).ravel().astype(int)

    net = flyvis.NetworkView("flow/0000/000").init_network()
    c = net.connectome
    ntype = np.array([s.decode() for s in c.nodes.type[:]])
    nu = np.asarray(c.nodes.u[:]).astype(int); nv = np.asarray(c.nodes.v[:]).astype(int)
    order, uv = {}, None
    for t in set(ntype.tolist()):
        m = ntype == t
        cc = np.stack([nu[m], nv[m]], 1); o = np.lexsort((cc[:, 1], cc[:, 0]))
        order[t] = np.where(m)[0][o]
        if len(o) == 721 and uv is None:
            uv = cc[o]
    idx = {(int(u), int(v)): i for i, (u, v) in enumerate(uv)}
    taps = hex_offsets(a.radius)
    rng = np.random.default_rng(7)
    path = saccade(a.steps, 16.0)

    Rs, As, gid = [], [], []
    for g in range(a.n):
        img = make_image(rng, 400, 400)
        big = img.resize((int(W * 1.14), int(H * 1.14)), Image.LANCZOS)
        B = np.asarray(big, np.float32) / 255.0
        cx, cy = (B.shape[1] - W) / 2, (B.shape[0] - H) / 2
        with torch.no_grad():
            state = None
            for k in range(a.steps):
                x0 = int(np.clip(cx + path[k, 0], 0, B.shape[1] - W))
                y0 = int(np.clip(cy + path[k, 1], 0, B.shape[0] - H))
                fr = B[y0:y0 + H, x0:x0 + W]
                hexg = np.bincount(idmap.ravel(), weights=fr.ravel(), minlength=722)[1:] / npx
                hv = hexg[perm]
                st = net.simulate(torch.tensor(hv, dtype=torch.float32).reshape(1, 1, 1, 721),
                                  dt=1 / 100, initial_state=state, as_states=True)
                st = st[-1] if isinstance(st, list) else st
                state = st
                Rs.append(hv); As.append(st.nodes.activity.detach().cpu().numpy().reshape(-1))
                gid.append(g)
        print(f"  图 {g+1}/{a.n} 完成", flush=True)
    R = np.array(Rs, np.float32); A = np.array(As, np.float32); gid = np.array(gid)
    print(f"数据：{R.shape[0]} 帧（{a.n} 张图 × {a.steps} 步）")

    ntest = max(2, a.n // 4)
    test_g = set(range(a.n - ntest, a.n))
    tr = ~np.isin(gid, list(test_g)); te = ~tr
    print(f"训练 {a.n-ntest} 张图 / 测试 {ntest} 张图（**整张图留出**，不是留帧）")

    out = {}
    print(f"\n{'层':16s}{'测试集 r':>10s}{'参数':>8s}")
    for keyname, (label, types) in LAYERS.items():
        types = [t for t in types if t in order and len(order[t]) == 721]
        F = len(types) * len(taps)
        X = np.zeros((R.shape[0], 721, F), np.float32)
        for ai, t in enumerate(types):
            act = A[:, order[t]]
            for bi, (du, dv) in enumerate(taps):
                src = np.array([idx.get((int(u) + du, int(v) + dv), -1) for u, v in uv])
                X[:, :, ai * len(taps) + bi] = np.where(src[None, :] >= 0, act[:, np.clip(src, 0, 720)], 0.0)
        Xtr = X[tr].reshape(-1, F); ytr = R[tr].reshape(-1)
        Xte = X[te].reshape(-1, F); yte = R[te].reshape(-1)
        mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-8
        Z = (Xtr - mu) / sd
        w = np.linalg.solve(Z.T @ Z + a.alpha * len(Z) * np.eye(F), Z.T @ (ytr - ytr.mean()))
        b = float(ytr.mean())
        r = float(np.corrcoef(((Xte - mu) / sd) @ w + b, yte)[0, 1])
        print(f"{label:16s}{r:10.3f}{F:8d}")
        out[keyname] = dict(label=label, types=types, taps=taps,
                            w=np.round(w, 6).tolist(), mu=np.round(mu, 6).tolist(),
                            sd=np.round(sd, 6).tolist(), b=round(b, 6), test_r=round(r, 4))

    doc = dict(radius=a.radius, alpha=a.alpha, n_images=a.n, n_test_images=ntest,
               steps=a.steps, layers=out,
               note="六边形卷积解码器。test_r 是在**完全没见过的整张图**上算的。"
                    "解码器仍会补细节，展示时必须同时给出未解码的神经活动。")
    f = VIS / "decoders.json"
    f.write_text(json.dumps(doc, separators=(",", ":")))
    print(f"\n写入 {f}  {f.stat().st_size/1024:.0f} KB")


if __name__ == "__main__":
    main()
