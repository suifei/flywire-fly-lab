#!/usr/bin/env python
"""
FlyGym 2.1 + 简化视觉输入 最小闭环 demo（不接连接组，先验证“3D 世界 → 复眼 → 控制 → 身体”）

    3D 世界 (MuJoCo) ──渲染──▶ 左/右复眼 721 个小眼 × 2 通道 (sim.get_ommatidia_readouts)
          ▲                                  │
          │                                  ▼
    身体执行 (HybridTurningController)  ◀── VisualBrain.step()：视觉 → 下行驱动 [left, right]
                                               （这里是 3 行的“玩具大脑”，
                                                之后换成 FlyWire 连接组，接口不变）

场景：平地 + 若干黑色柱子。果蝇天然会朝暗的竖直物体走（stripe fixation / Buridan 范式），
玩具大脑实现的就是这个：哪只眼里“暗”的更多，就往哪边转；看到的暗面积很大（快撞上/looming）就停。

已在本机实测的 API（flygym==2.1.0, mujoco==3.9.0）：
  * fly.add_vision()                 给 NeuroMechFly 加左右眼相机（必须在 world.add_fly 前调用）
  * sim.get_ommatidia_readouts(name) → (2, 721, 2) float32，[眼, 小眼, (yellow, pale)]，值 0–1，
                                        每个小眼只有一个通道非零（pale/yellow 型）
  * sim.get_raw_vision(name)         → (2, 512, 450, 3) 鱼眼校正后的 RGB
  * HybridTurningController.step(np.array([L, R]), obs)
        实测：[1.2, 0.4]（左强右弱）→ 向右转；幅值≈步幅，负值=该侧倒退

用法：
  conda activate flygym
  python flygym_vision_demo.py                       # 2 s 模拟，默认趋向黑柱
  python flygym_vision_demo.py --behavior avoid      # 反过来：躲开黑柱
  python flygym_vision_demo.py --duration 4 --no-video

输出 results/flygym_vision/：
  trajectory.png     俯视轨迹 + 柱子位置 + 左右眼暗度/下行驱动时间曲线
  fly_eye_views.png  若干时刻“果蝇看到的”六边形复眼图像（左/右眼）
  demo.mp4           跟踪相机视频（--no-video 可关）
  log.csv            每个视觉帧：时间、位置、朝向、左右暗度、下行驱动
"""

import argparse
import time
from pathlib import Path

import numpy as np

from flygym import Simulation
from flygym.anatomy import BodySegment, ContactBodiesPreset
from flygym.compose import FlatGroundWorld
from flygym.utils.math import Rotation3D
from flygym.utils.mjcf import GEOM_TYPES
from flygym_demo.complex_terrain import (
    HybridControllerObservation,
    HybridTurningController,
    LocomotionAction,
    PreprogrammedSteps,
    apply_locomotion_action,
    make_locomotion_fly,
)

HERE = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# “大脑”接口：输入复眼读数，输出 2 维下行驱动。以后把它换成连接组模型即可。
# ---------------------------------------------------------------------------
class VisualBrain:
    """玩具视觉大脑（非连接组，纯手写规则）。

    每只眼：darkness = 该眼中“暗”小眼(亮度 < thr)所占比例。
    转向：drive = base ± gain * (dark_L - dark_R)；attract 时往更暗那侧转。
    looming：任一眼暗比例 > stop_frac 视为已贴近物体 → 停下（驱动置 0）。
    """

    def __init__(self, behavior="attract", base=1.0, gain=6.0, thr=0.2, stop_frac=0.35):
        # blind = 对照组：照样渲染复眼，但不用视觉，恒定直行驱动
        self.sign = {"attract": 1.0, "avoid": -1.0, "blind": 0.0}[behavior]
        self.base, self.gain, self.thr, self.stop_frac = base, gain, thr, stop_frac

    def step(self, ommatidia):  # ommatidia: (2, 721, 2)
        brightness = ommatidia.max(axis=2)  # 每个小眼只有一个通道有值，取非零那个
        dark = (brightness < self.thr).mean(axis=1)  # (左, 右)
        if self.sign != 0 and dark.max() > self.stop_frac:
            return np.zeros(2), dark
        turn = np.clip(self.sign * self.gain * (dark[0] - dark[1]), -0.8, 0.8)
        # 想向左转 → 右侧腿步幅大、左侧小（实测 [1.2,0.4] 向右转）
        return np.array([self.base - turn, self.base + turn]), dark


# ---------------------------------------------------------------------------
def build(pillars, record_video):
    fly = make_locomotion_fly(name="fly", add_adhesion=True, colorize=True)
    fly.add_vision()  # 左右复眼相机
    cam = None
    if record_video:
        cam = fly.add_tracking_camera(name="topcam", pos_offset=(0.0, 0.0, 22.0),
                                      rotation=Rotation3D("euler", (0.0, 0.0, 0.0)), fovy=60.0)
    world = FlatGroundWorld()
    # 默认地面棋盘格是 0.3/0.4 灰，经复眼后亮度 <0.2，会被当成“暗物体”（实测踩坑），
    # 所以把地面改亮，让黑柱子成为视野里唯一的暗目标
    tex = next(t for t in world.mjcf_root.textures if t.name == "checker")
    tex.rgb1, tex.rgb2 = [0.85, 0.85, 0.85], [0.95, 0.95, 0.95]
    for k, (x, y, r) in enumerate(pillars):  # 世界里放黑色柱子（只做视觉，不参与碰撞）
        world.mjcf_root.worldbody.add_geom(
            type=GEOM_TYPES["cylinder"], name=f"pillar{k}", pos=(x, y, 15.0),
            size=(r, 15.0, 0), rgba=(0.03, 0.03, 0.03, 1), contype=0, conaffinity=0)
    world.add_fly(fly, [0, 0, 0.8], Rotation3D("quat", [1, 0, 0, 0]),
                  bodysegs_with_ground_contact=ContactBodiesPreset.TIBIA_TARSUS_ONLY,
                  add_ground_contact_sensors=False)
    sim = Simulation(world)
    if cam is not None:
        sim.set_renderer([cam], camera_res=(360, 360), playback_speed=0.25, output_fps=25)
    return fly, sim, cam


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=2.0, help="模拟时长 (s)")
    ap.add_argument("--behavior", choices=["attract", "avoid", "blind"], default="attract")
    ap.add_argument("--vision_dt", type=float, default=0.015,
                    help="每隔多少秒读一次复眼并更新驱动（Eon 官网称其脑-身同步周期为 15 ms）")
    ap.add_argument("--no-video", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    a.out = a.out or HERE / "results" / f"flygym_vision_{a.behavior}"
    a.out.mkdir(parents=True, exist_ok=True)

    # 柱子放在果蝇左前方（果蝇初始朝 +x，+y 是左边）
    pillars = [(14.0, 7.0, 1.2), (14.0, -14.0, 1.2)]
    fly, sim, cam = build(pillars, not a.no_video)
    brain = VisualBrain(a.behavior)

    steps = PreprogrammedSteps()
    order = fly.get_actuated_jointdofs_order("position")
    ctrl = HybridTurningController(timestep=sim.timestep, preprogrammed_steps=steps,
                                   output_dof_order=order)
    sim.reset(); ctrl.reset(seed=0)
    apply_locomotion_action(sim, fly.name, LocomotionAction(
        joint_angles=steps.default_pose_by_dof_order(order), adhesion_onoff=np.ones(6, bool)))
    sim.warmup()

    th = fly.get_bodysegs_order().index(BodySegment("c_thorax"))
    n_steps = int(a.duration / sim.timestep)
    every = max(1, int(round(a.vision_dt / sim.timestep)))
    snap_times = set(int(f * (n_steps // every - 1)) for f in (0, 0.33, 0.66, 1.0))
    log, snaps = [], []
    drive = np.array([brain.base, brain.base])
    t0 = time.perf_counter()
    for i in range(n_steps):
        if i % every == 0:  # —— 感知 → 大脑 ——
            omm = sim.get_ommatidia_readouts(fly.name)
            drive, dark = brain.step(omm)
            obs = HybridControllerObservation.from_sim(sim, fly.name)
            pos = sim.get_body_positions(fly.name)[th]
            log.append([i * sim.timestep, pos[0], pos[1], obs.fly_heading[0], obs.fly_heading[1],
                        dark[0], dark[1], drive[0], drive[1]])
            if len(log) - 1 in snap_times:
                snaps.append((i * sim.timestep, omm.max(axis=2)))
        # —— 大脑 → 行动 ——
        obs = HybridControllerObservation.from_sim(sim, fly.name)
        apply_locomotion_action(sim, fly.name, ctrl.step(drive, obs))
        sim.step()
        if cam is not None:
            sim.render_as_needed()
    wall = time.perf_counter() - t0
    log = np.array(log)
    print(f"模拟 {a.duration}s，墙钟 {wall:.1f}s（{a.duration / wall:.3f}× 实时），视觉帧 {len(log)}")
    print(f"起点 {log[0, 1:3].round(2)} → 终点 {log[-1, 1:3].round(2)} mm；"
          f"到柱子0 距离 {np.hypot(*(log[0, 1:3] - pillars[0][:2])):.2f} → "
          f"{np.hypot(*(log[-1, 1:3] - pillars[0][:2])):.2f} mm；"
          f"轨迹上离柱子0 最近 {np.hypot(*(log[:, 1:3] - pillars[0][:2]).T).min():.2f} mm "
          f"(柱半径 {pillars[0][2]} mm)")

    np.savetxt(a.out / "log.csv", log, delimiter=",", fmt="%.5f",
               header="t,x,y,heading_x,heading_y,dark_L,dark_R,drive_L,drive_R", comments="")
    if cam is not None:
        sim.renderer.save_video(a.out / "demo.mp4")

    # —— 画图 ——
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(12, 5))
    ax[0].plot(log[:, 1], log[:, 2], "-", lw=2, label="thorax path")
    ax[0].plot(*log[0, 1:3], "go", label="start")
    for x, y, r in pillars:
        ax[0].add_patch(plt.Circle((x, y), r, color="k"))
    ax[0].set_aspect("equal"); ax[0].set_xlabel("x (mm)"); ax[0].set_ylabel("y (mm, +left)")
    ax[0].set_title(f"behavior={a.behavior}"); ax[0].legend()
    ax[1].plot(log[:, 0], log[:, 5], label="dark_L"); ax[1].plot(log[:, 0], log[:, 6], label="dark_R")
    ax2 = ax[1].twinx()
    ax2.plot(log[:, 0], log[:, 7], "--", label="drive_L"); ax2.plot(log[:, 0], log[:, 8], "--", label="drive_R")
    ax[1].set_xlabel("t (s)"); ax[1].set_ylabel("dark fraction"); ax2.set_ylabel("descending drive")
    ax[1].legend(loc="upper left"); ax2.legend(loc="upper right")
    fig.tight_layout(); fig.savefig(a.out / "trajectory.png", dpi=120); plt.close(fig)

    retina = sim.retina  # get_ommatidia_readouts 时已懒加载
    fig, axs = plt.subplots(len(snaps), 2, figsize=(6, 3 * len(snaps)), squeeze=False)
    for r, (t, b) in enumerate(snaps):
        for e, name in enumerate(["left eye", "right eye"]):
            img = retina.hex_pxls_to_human_readable(b[e][:, None], default_value=1.0)[..., 0]
            axs[r, e].imshow(img, cmap="gray", vmin=0, vmax=1)
            axs[r, e].set_title(f"t={t:.2f}s {name}"); axs[r, e].axis("off")
    fig.tight_layout(); fig.savefig(a.out / "fly_eye_views.png", dpi=110); plt.close(fig)
    print(f"输出目录: {a.out}")


if __name__ == "__main__":
    main()
