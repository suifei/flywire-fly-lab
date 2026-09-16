"""
从 results/fba_replay/replay.json（FlyGym 1.2.1 物理仿真的对照组直行数据）提取一个步态周期，
转换到果蝇自身坐标系，供游戏里的行走动画循环播放。网格顶点/面编码为 base64 二进制以减小体积。

输出 results/dodge/gait.json：
  meshes: [{name, verts(b64 Float32), faces(b64 Uint32)}]
  frames: 一个周期内每帧每个网格的 [x,y,z,qw,qx,qy,qz]（胸部原点、朝向 +x）
  cycle_s: 周期时长；stride_mm: 一个周期内前进距离（用于步态速度与移动速度同步）
"""
import base64
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
src = json.loads((ROOT / "results/fba_replay/replay.json").read_text())
trial = next(t for t in src["trials"] if t["condition"] == "control")
dt = src["meta"]["frame_dt_s"]
F = np.array([f["pose"] for f in trial["frames"]]).reshape(len(trial["frames"]), -1, 7)   # (帧, 网格, 7)
th = np.array([f["thorax"] for f in trial["frames"]])
names = [m["name"] for m in src["meshes"]]
thorax_i = names.index("Thorax")


def quat_mul(a, b):
    w1, x1, y1, z1 = np.moveaxis(a, -1, 0); w2, x2, y2, z2 = np.moveaxis(b, -1, 0)
    return np.stack([w1*w2 - x1*x2 - y1*y2 - z1*z2, w1*x2 + x1*w2 + y1*z2 - z1*y2,
                     w1*y2 - x1*z2 + y1*w2 + z1*x2, w1*z2 + x1*y2 - y1*x2 + z1*w2], -1)


# 朝向：用 ±12 帧的位移方向（抵消步态左右晃动）
idx = np.arange(len(th))
a, b = th[np.maximum(idx - 12, 0)], th[np.minimum(idx + 12, len(th) - 1)]
yaw = np.unwrap(np.arctan2(b[:, 1] - a[:, 1], b[:, 0] - a[:, 0]))

# 找周期：后半段里，与第 i 帧最相似（相对位姿）的 i+L，L 取 12–24 帧（30–60 ms，约 17–33 Hz）
def local(i):
    c, s = np.cos(-yaw[i]), np.sin(-yaw[i])
    p = F[i, :, :3] - [th[i, 0], th[i, 1], 0]
    p = np.stack([c * p[:, 0] - s * p[:, 1], s * p[:, 0] + c * p[:, 1], p[:, 2]], 1)
    qz = np.array([np.cos(-yaw[i] / 2), 0, 0, np.sin(-yaw[i] / 2)])
    q = quat_mul(np.broadcast_to(qz, F[i, :, 3:].shape), F[i, :, 3:])
    q *= np.sign(q[:, :1] + 1e-9)
    return p, q

best = None
for i in range(100, 160):
    pi, _ = local(i)
    for L in range(12, 25):
        if i + L >= len(th):
            break
        pj, _ = local(i + L)
        err = np.abs(pi - pj).mean()
        if best is None or err < best[0]:
            best = (err, i, L)
err, i0, L = best
frames = []
for i in range(i0, i0 + L):
    p, q = local(i)
    frames.append(np.round(np.concatenate([p, q], 1), 4).ravel().tolist())
stride = float(np.hypot(*(th[i0 + L, :2] - th[i0, :2])))

b64 = lambda arr: base64.b64encode(np.ascontiguousarray(arr).tobytes()).decode()
meshes = [dict(name=m["name"], verts=b64(np.array(m["verts"], np.float32)), faces=b64(np.array(m["faces"], np.uint32)))
          for m in src["meshes"]]
out = ROOT / "results/dodge/gait.json"
out.write_text(json.dumps(dict(meshes=meshes, frames=frames, cycle_s=L * dt, stride_mm=stride,
                               source="FlyGym 1.2.1 NeuroMechFly (Apache-2.0), control trial of fba_export_replay.py",
                               loop_error_mm=float(err)), separators=(",", ":")))
print(f"周期 {L} 帧 = {L * dt * 1000:.1f} ms（{1 / (L * dt):.1f} Hz），起点帧 {i0}，首尾位姿误差 {err:.4f} mm，"
      f"每周期前进 {stride:.2f} mm（{stride / (L * dt):.1f} mm/s）；写入 {out}（{out.stat().st_size / 1e6:.2f} MB）")
