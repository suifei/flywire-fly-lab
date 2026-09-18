#!/usr/bin/env python3
"""视网膜采样的 parity 参考：Python 采一次，JS 采一次，必须逐值对上。

测试画面用**纯整数算式**生成（i*2654435761 % 65536），两边逐位一致，
这样比对失败一定是采样逻辑的问题，不会是浮点噪声。

用法：conda activate fba && python vision/retina_parity.py
"""
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results/vision"


def main():
    meta = json.loads((OUT / "retina.json").read_text())
    w, h = meta["width"], meta["height"]
    idmap = np.frombuffer((OUT / "retina_map.bin").read_bytes(), "<u2").astype(int)
    assert idmap.size == w * h, (idmap.size, w, h)
    npx = np.asarray(meta["pixels_per_ommatidium"], float)
    perm = np.asarray(meta["flygym_to_flyvis"], int)

    i = np.arange(w * h, dtype=np.int64)
    frame = ((i * 2654435761) % 65536) / 65536.0        # 整数 → 精确

    s = np.bincount(idmap, weights=frame, minlength=722)[1:]
    gym = s / npx
    hexv = gym[perm]

    doc = dict(width=w, height=h,
               frame_formula="frame[i] = ((i*2654435761) % 65536) / 65536",
               hex=np.round(hexv, 12).tolist())
    f = OUT / "retina_parity.json"
    f.write_text(json.dumps(doc, separators=(",", ":")))
    print(f"写入 {f}  {f.stat().st_size/1024:.0f} KB")
    print(f"  画面 {w}×{h}，721 个小眼亮度 范围 [{hexv.min():.6f}, {hexv.max():.6f}] 均值 {hexv.mean():.6f}")


if __name__ == "__main__":
    main()
