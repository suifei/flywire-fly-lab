#!/usr/bin/env python
"""
第 2 步 A：复眼 → flyvis。
固定（tethered）的 NeuroMechFly 看一个黑球的几种运动，FlyGym 1.2.1 复眼渲染（200 Hz）
逐帧驱动 Lappalainen et al. 2024 预训练视觉网络（flyvis flow/0000/000），记录柱状细胞活动。

刺激（果蝇朝 +x，+y 为左；球半径 2.5 mm，与游戏一致；前 0.2 s 为无刺激基线期）：
  loom_L / loom_R   方位 ±60°，距离 60 → 3.5 mm（0.95 s 内匀速）
  recede_L          方位 +60°，距离 3.5 → 60 mm
  translate_near_L  距离 8 mm 不变，方位 20° → 100°（80°/s，角尺寸约 35°）
  translate_far_L   距离 20 mm 不变，方位 20° → 100°（角尺寸约 14°）

输出 results/vision/flyvis_<stim>.npz：
  act[type]  (bins, 2 眼, n_columns) float16，每 5 ms 一个 bin（每个复眼帧一个）
  u[type], v[type]  flyvis 六边形柱坐标；t  bin 中心时间（s，含基线期）
用法（fba 环境）：python vision/flyvis_looming.py [刺激名 ...]
"""
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("HDF5_USE_FILE_LOCKING", "FALSE")  # datamate 读 h5 失败会 sleep(0.1) 重试，文件锁是诱因之一
import numpy as np
from torch import Tensor

import flyvis
from flygym import SingleFlySimulation
from flygym.arena import Tethered
from flygym.examples.vision.realistic_vision import RealisticVisionFly

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "vision"
TYPES = ["T4a", "T4b", "T4c", "T4d", "T5a", "T5b", "T5c", "T5d", "T2", "T2a", "T3", "T1",
         "Tm1", "Tm2", "Tm3", "Tm4", "Tm9", "Tm20", "Mi1", "Mi4", "Mi9",
         "L1", "L2", "L3", "L4", "L5", "C2", "C3", "R7", "R8"]
BALL_R, PRE, DUR, BIN_FRAMES = 2.5, 0.2, 1.0, 1
VISION_HZ = 200          # flyvis 积分步长 5 ms（RealTimeVisionNetwork 要求 ≤ 20 ms）；每帧一个 bin


def stim_pos(name, t):
    """刺激开始后 t 秒时球心相对头部的 (方位°, 距离 mm)；t<0 为基线期（球放到远处看不见的位置）。"""
    if t < 0:
        return None
    u = min(1.0, t / 0.95)
    if name.startswith("loom"):
        return (60 if name.endswith("L") else -60), 60 + (3.5 - 60) * u
    if name.startswith("recede"):
        return 60, 3.5 + (60 - 3.5) * u
    if name.startswith("translate_near"):
        return 20 + 80 * min(1.0, t / 1.0), 8.0
    if name.startswith("translate_far"):
        return 20 + 80 * min(1.0, t / 1.0), 20.0
    raise ValueError(name)


class BallArena(Tethered):
    def __init__(self, stim, **kw):
        super().__init__(**kw)
        self.stim, self.t, self.head = stim, -PRE, np.array([0.0, 0.0, 0.0])
        mat = self.root_element.asset.add("material", name="ballmat", reflectance=0.0)
        self.ball = self.root_element.worldbody.add("body", name="ball", mocap=True, pos=(0, 0, -500))
        self.ball.add("geom", type="sphere", size=(BALL_R,), rgba=(0, 0, 0, 1), material=mat,
                      contype=0, conaffinity=0)

    def pos(self):
        p = stim_pos(self.stim, self.t)
        if p is None:
            return (0, 0, -500)
        az, d = np.deg2rad(p[0]), p[1]
        return tuple(self.head + np.array([d * np.cos(az), d * np.sin(az), 0.0]))

    def reset(self, physics):
        self.t = -PRE
        physics.bind(self.ball).mocap_pos = self.pos()

    def step(self, dt, physics):
        self.t += dt
        physics.bind(self.ball).mocap_pos = self.pos()


class FastVisionFly(RealisticVisionFly):
    """与 RealisticVisionFly 相同的视觉计算，但每帧不构造 flyvis LayerActivity。
    原实现每个视觉帧都新建 LayerActivity，会反复经 datamate 读连接组 h5 文件（失败则 sleep 0.1 s 重试），
    实测占总耗时约 60%。这里只返回 (2 眼, 全部节点) 的原始活动数组，按类型索引在外面一次性算好。"""

    def _get_visual_nn_activities(self, vision_obs):
        visual_input = self.retina_mapper.flygym_to_flyvis(vision_obs.max(axis=-1))
        arr = self.vision_network.forward_one_step(Tensor(visual_input).to(flyvis.device)).cpu().numpy()
        return None, arr


def run(stim):
    arena = BallArena(stim)
    # 与 flygym 官方示例 record_baseline_response.py 相同的构造方式
    contacts = [f"{leg}{seg}" for leg in ["LF", "LM", "LH", "RF", "RM", "RH"]
                for seg in ["Tibia", "Tarsus1", "Tarsus2", "Tarsus3", "Tarsus4", "Tarsus5"]]
    fly = FastVisionFly(contact_sensor_placements=contacts, enable_adhesion=True,
                        vision_refresh_rate=VISION_HZ, neck_kp=1000)
    sim = SingleFlySimulation(fly=fly, arena=arena, timestep=1e-4)
    obs, info = sim.reset()
    head_id = [i for i in range(sim.physics.model.nbody) if sim.physics.model.id2name(i, "body").endswith("Head")][0]
    arena.head = np.array(sim.physics.data.xpos[head_id])
    arena.reset(sim.physics)
    conn = fly.vision_network.connectome
    node_type = np.array([s.decode() for s in conn.nodes.type[:]])
    uv = {t: (np.asarray(conn.nodes.u[:])[node_type == t], np.asarray(conn.nodes.v[:])[node_type == t]) for t in TYPES}
    type_idx = {t: np.where(node_type == t)[0] for t in TYPES}   # 与 LayerActivity(use_central=False)[t] 的节点顺序一致

    frames = {t: [] for t in TYPES}; buf = {t: [] for t in TYPES}; times = []
    n_steps = int(round((PRE + DUR) / sim.timestep))
    t0 = time.time()
    for i in range(n_steps):
        obs, _, _, _, info = sim.step(np.array([0.0, 0.0]))          # 零下行驱动：腿不动，只看
        if info["vision_updated"]:
            arr = obs["nn_activities_arr"]                              # (2 眼, 全部节点)
            for t in TYPES:
                buf[t].append(arr[:, type_idx[t]].astype(np.float32))  # (2 眼, n_columns)
            if len(buf[TYPES[0]]) == BIN_FRAMES:
                for t in TYPES:
                    frames[t].append(np.mean(buf[t], axis=0).astype(np.float16)); buf[t] = []
                times.append(i * sim.timestep - PRE)
    sim.close()
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT / f"flyvis_{stim}.npz", t=np.array(times),
                        **{f"act_{t}": np.stack(frames[t]) for t in TYPES},
                        **{f"u_{t}": uv[t][0] for t in TYPES}, **{f"v_{t}": uv[t][1] for t in TYPES},
                        head=arena.head)
    a = np.stack(frames["T4a"]).astype(np.float32)
    print(f"{stim}: {len(times)} bins，T4a 形状 {a.shape}，用时 {time.time() - t0:.0f}s，头部位置 {np.round(arena.head, 2)}", flush=True)


if __name__ == "__main__":
    stims = sys.argv[1:] or ["loom_L", "loom_R", "recede_L", "translate_near_L", "translate_far_L"]
    for s in stims:
        run(s)
