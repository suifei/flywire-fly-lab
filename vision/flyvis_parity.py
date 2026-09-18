#!/usr/bin/env python3
"""生成 JS 复现 flyvis 所需的参考输出（parity fixture）。

规矩和 dodge/parity_test.js 一样：**JS 端必须和 Python 逐值对上**，
否则后面"果蝇画出来的图"只是一个看起来像那么回事的近似。

初态统一用 flyvis 自己的 write_initial_state（= bias），
这样初态不会成为比对时的干扰项；稳态另行处理。

用法：conda activate fba && python vision/flyvis_parity.py
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results/vision/flyvis_parity.json"
N_FRAMES = 12
DT = 1 / 100


def main():
    import flyvis
    import torch

    nv = flyvis.NetworkView("flow/0000/000")
    net = nv.init_network()
    c = net.connectome
    ntype = np.array([s.decode() for s in c.nodes.type[:]])
    nu = np.asarray(c.nodes.u[:]).astype(int)
    nvv = np.asarray(c.nodes.v[:]).astype(int)

    # 固定种子的"图像"序列：每帧 721 个小眼的亮度 ∈ [0,1]
    rng = np.random.default_rng(20260918)
    movie = rng.random((1, N_FRAMES, 1, 721)).astype(np.float32)

    with torch.no_grad():
        # initial_state=None → 走 write_initial_state（state = bias），JS 能复现
        # as_states=True 返回每帧一个 state（list），取出 nodes.activity 堆起来
        states = net.simulate(torch.tensor(movie), dt=DT,
                              initial_state=None, as_states=True)
        if isinstance(states, list):
            act = np.stack([s.nodes.activity.detach().cpu().numpy().reshape(-1)
                            for s in states])
        else:
            act = np.asarray(states.nodes.activity.detach().cpu().numpy()).reshape(N_FRAMES, -1)
    print(f"仿真 {N_FRAMES} 帧 dt={DT}  输出形状 {act.shape}")

    # 只导出几个代表类型的逐柱值，够比对又不会让 fixture 太大
    probe = ["R1", "R8", "L1", "L2", "L5", "Mi1", "Mi9", "Tm1", "Tm9", "T4a", "T4c", "T5a", "T5c", "TmY3"]
    ref = {}
    for t in probe:
        m = ntype == t
        uv = np.stack([nu[m], nvv[m]], 1)
        order = np.lexsort((uv[:, 1], uv[:, 0]))          # 和导出器同一套排序
        ref[t] = np.round(act[:, np.where(m)[0][order]], 6).tolist()

    doc = dict(dt=DT, n_frames=N_FRAMES,
               movie=np.round(movie.reshape(N_FRAMES, 721), 6).tolist(),
               initial_state="bias",
               probe=probe, activity=ref,
               note="movie 是每帧 721 个小眼的亮度；activity[type] 形状 (帧, 柱)，"
                    "柱顺序 = 按 (u,v) lexsort，与 export_flyvis_js.py 一致")
    OUT.write_text(json.dumps(doc, separators=(",", ":")))
    print(f"写入 {OUT}  {OUT.stat().st_size/1024:.0f} KB")
    for t in probe:
        a = np.array(ref[t])
        print(f"  {t:5s} 末帧 均值 {a[-1].mean():+.4f}  范围 [{a[-1].min():+.3f}, {a[-1].max():+.3f}]")


if __name__ == "__main__":
    main()
