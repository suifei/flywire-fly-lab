#!/usr/bin/env python3
"""导出 FlyGym 的**真实复眼采样几何**，供浏览器使用。

不是我编的近似：FlyGym 把场景渲染成 512×450 的图，再用 ommatidia_id_map
把每个像素归到 721 个小眼之一（每个小眼约 239 个像素，含真实的鱼眼畸变
zoom=2.72 / distortion=3.8）。这里把那张表原样导出。

产物：
  results/vision/retina_map.png   512×450，小眼编号编在 R(高字节)+G(低字节)
  results/vision/retina.json      flygym→flyvis 排列、每小眼像素数、尺寸

浏览器端：把上传的图画进 512×450 canvas → 按表累加求平均 → 得到 721 个亮度
→ 用排列换成 flyvis 的柱顺序 → 喂进 flyvis.js。

用法：conda activate fba && python vision/export_retina_js.py
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results/vision"


def main():
    from flygym import Fly
    from flygym.examples.vision.vision_network import RetinaMapper
    from PIL import Image

    r = Fly(enable_vision=True).retina
    m = np.asarray(r.ommatidia_id_map).astype(np.uint16)      # 0 = 背景，1..721 = 小眼
    npx = np.asarray(r.num_pixels_per_ommatidia).astype(int)
    h, w = m.shape

    # flygym 小眼序号 → flyvis 柱位置：perm[j] = 落在 flyvis 第 j 柱的 flygym 序号
    perm = RetinaMapper().flygym_to_flyvis(
        np.arange(721, dtype=np.float32)[None, :]).ravel().astype(int)
    assert sorted(perm.tolist()) == list(range(721)), "不是一个排列"

    # 编号塞进 PNG 的 R/G 通道（PNG 自带压缩，浏览器原生解码）
    rgb = np.zeros((h, w, 3), np.uint8)
    rgb[:, :, 0] = (m >> 8).astype(np.uint8)
    rgb[:, :, 1] = (m & 0xFF).astype(np.uint8)
    png = OUT / "retina_map.png"
    Image.fromarray(rgb).save(png, optimize=True)

    doc = dict(
        source="flygym Retina.ommatidia_id_map（真实采样几何，含 zoom=%.2f / distortion=%.1f）"
               % (r.zoom, r.distortion_coefficient),
        width=int(w), height=int(h), n_ommatidia=721,
        encoding="retina_map.png 的 R 通道=编号高字节，G 通道=低字节；0 表示背景",
        pixels_per_ommatidium=npx.tolist(),
        flygym_to_flyvis=perm.tolist(),
        display_swap_xy=True,
        display_note="六边形坐标画图时要交换 x/y：相机x↔hex_y、相机y↔hex_x（实测相关 1.000）",
        note="hexFlyvis[j] = hexFlygym[flygym_to_flyvis[j]]；"
             "flyvis 柱顺序 = 按 (u,v) lexsort，与 flyvis_net.json 的 lattice 一致",
    )
    # 再存一份原始二进制：浏览器用 PNG（15 KB，原生解码），
    # Node 做 parity 时直接读这个，省掉在 Node 里解 PNG 的麻烦。
    binf = OUT / "retina_map.bin"
    binf.write_bytes(m.astype("<u2").tobytes())

    # 朝向：实测 相机x ↔ 六边形y、相机y ↔ 六边形x，相关系数 1.000（精确转置）。
    # 显示时要交换两轴，否则用户会看到自己的图被转了 90°。
    js = OUT / "retina.json"
    js.write_text(json.dumps(doc, separators=(",", ":")))

    print(f"写入 {png}  {png.stat().st_size/1024:.0f} KB   （{w}×{h}，背景占 {(m==0).mean():.0%}）")
    print(f"写入 {js}  {js.stat().st_size/1024:.0f} KB")
    print(f"写入 {binf}  {binf.stat().st_size/1024:.0f} KB（Node parity 用）")
    print(f"  721 个小眼，每个 {npx.min()}–{npx.max()} 像素（中位 {int(np.median(npx))}）")


if __name__ == "__main__":
    main()
