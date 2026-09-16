#!/usr/bin/env python
"""
原型：真实 FlyWire 全脑 LIF（138,639 神经元）在环的“视觉 → 大脑 → 身体”闭环

    FlyGym 3D 世界 ──复眼(2×721)──▶ [手写视觉前端] 每侧 looming 强度 → LC4 左/右 Poisson 频率
        ▲                                                   │
        │                                                   ▼
    HybridTurningController ◀── [手写映射] ◀── 全脑 LIF（官方 TorchModel，15 ms 一窗）
        [左驱动, 右驱动]          DNa01/DNa02 左右差 → 转向          读出 DNa01/02、P9_oDN1、Giant Fiber
                                  P9_oDN1 → 前进；GF 高频 → 冻结

哪些是连接组，哪些是我手写的（重要）：
  * 连接组部分：LC4 → … → DNa01/DNa02/GF/oDN1 之间的所有传播，完全由 FlyWire v783 连接 + Shiu LIF 参数决定
  * 手写（推测/占位）：
      - 视觉前端：用“每只眼暗面积的增长率”近似 looming，再线性变成 LC4 频率。
        不是 LC4 的真实感受野模型，也没有用 flyvis。
      - 行走基线：给左右 P9 恒定 100 Hz（与官方 notebook 的 “P9 + LC4” 实验一致）
      - 下行神经元 → 腿：频率到 [L, R] 驱动的线性映射和系数，是拍脑袋定的。
        Eon 官网也说他们的映射是 “somewhat arbitrarily chosen by hand”
      - 左右侧：统一用 FlyWire 注释表的 side 字段（胞体侧）。官方 notebook 的 left/right 命名与之相反
  * 为什么不直接把复眼灌进 R1-6/R7/R8：已实测（results/vis_R1-6_left、vis_R7R8_left），
    激活 4044 个 R1-6 或 1330 个 R7/R8，0.2 s 内所有下行神经元都是 0 Hz；激活 54 个左 LC4，
    Giant Fiber 85/40 Hz。LIF 模型没有光感受器的分级电位和运动检测所需的时间滤波。

用法（flygym 环境，需要 torch；Apple GPU 用 mps，NVIDIA 用 cuda）：
  python connectome_vision_loop.py --duration 1.0              # 黑球从左前方逼近
  python connectome_vision_loop.py --duration 1.0 --no-looming # 对照：没有球
  python connectome_vision_loop.py --duration 1.0 --frontend-only  # 不加载大脑，只检验视觉前端给 LC4 的输入（快、省内存）
耗时参考（M1 Pro, MPS）：1 s 模拟 ≈ 2–3 分钟；内存峰值 ≈ 3–4 GB
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow  # noqa: F401  （官方注释：先于 torch import）
import torch

from flygym import Simulation
from flygym.anatomy import BodySegment, ContactBodiesPreset
from flygym.compose import FlatGroundWorld
from flygym.utils.math import Rotation3D
from flygym.utils.mjcf import GEOM_TYPES
from flygym_demo.complex_terrain import (
    HybridControllerObservation, HybridTurningController, LocomotionAction,
    PreprogrammedSteps, apply_locomotion_action, make_locomotion_fly,
)

HERE = Path(__file__).resolve().parent
REPO = HERE / "external" / "fly-brain"
sys.path.insert(0, str(REPO / "code"))
from run_pytorch import TorchModel, MODEL_PARAMS  # noqa: E402  官方 GPL-2.0-or-later 实现

PATH_COMP = REPO / "data" / "2025_Completeness_783.csv"
PATH_CON = REPO / "data" / "2025_Connectivity_783.parquet"
PATH_ANNOT = HERE / "external" / "flywire_annotations" / "Supplemental_file1_neuron_annotations.tsv"
DT_MS = 0.1
P9 = [720575940627652358, 720575940635872101]  # 官方 benchmark.py 的 p9 预设


# ---------------------------------------------------------------------------
class ConnectomeBrain:
    """官方 TorchModel 的逐窗推进包装：set_rates → run_window → 读出各组发放率。"""

    def __init__(self, device, groups):
        comp = pd.read_csv(PATH_COMP, index_col=0)
        self.fid2i = {int(f): i for i, f in enumerate(comp.index)}
        n = len(comp)
        con = pd.read_parquet(PATH_CON, columns=["Presynaptic_Index", "Postsynaptic_Index",
                                                 "Excitatory x Connectivity"])
        coo = torch.sparse_coo_tensor(
            np.vstack([con["Postsynaptic_Index"].to_numpy(), con["Presynaptic_Index"].to_numpy()]),
            con["Excitatory x Connectivity"].to_numpy().astype(np.float32), (n, n)).coalesce()
        self.device = device
        self.groups = {k: [self.fid2i[f] for f in v if f in self.fid2i] for k, v in groups.items()}
        stim = sorted({i for k in ("P9", "LC4_left", "LC4_right") for i in self.groups[k]})
        if device == "mps":  # MPS 不支持 CSR，只替换稀疏乘法那一行（同 run_experiment.py）
            class M(TorchModel):
                def forward(s, rates, c, d, spk, v, r, generator=None):
                    stim_v = s.scale * s.poisson(rates, generator=generator)
                    rec = s.scale * torch.sparse.mm(s.weights, spk.T).T
                    return s.neurons(rec, stim_v, c, d, spk, v, r)
            self.model = M(1, n, DT_MS, MODEL_PARAMS, coo.to(device), exc_indices=stim, device=device)
        else:
            self.model = TorchModel(1, n, DT_MS, MODEL_PARAMS, coo.to_sparse_csr().to(device),
                                    exc_indices=stim, device=device)
        self.state = self.model.state_init()
        self.rates = torch.zeros(1, n, device=device)
        self.readout = {k: torch.as_tensor(v, device=device) for k, v in self.groups.items()}

    def set_rate(self, group, hz):
        self.rates[0, self.groups[group]] = float(hz)

    @torch.no_grad()
    def run_window(self, n_steps):
        counts = {k: torch.zeros((), device=self.device) for k in self.readout}
        c, d, spk, v, r = self.state
        for _ in range(n_steps):
            c, d, spk, v, r = self.model(self.rates, c, d, spk, v, r)
            for k, idx in self.readout.items():
                counts[k] += spk[0, idx].sum()  # 留在 GPU 上累加，窗口末尾才同步
        self.state = (c, d, spk, v, r)
        win_s = n_steps * DT_MS / 1000
        return {k: float(x) / (len(self.groups[k]) * win_s) for k, x in counts.items()}  # Hz/神经元


def groups_from_annotations():
    ann = pd.read_csv(PATH_ANNOT, sep="\t", low_memory=False, usecols=["root_id", "cell_type", "side"])
    g = lambda t, s: ann.root_id[(ann.cell_type == t) & (ann.side == s)].astype("int64").tolist()
    return {
        "P9": P9,
        "LC4_left": g("LC4", "left"), "LC4_right": g("LC4", "right"),
        "DNa01_left": g("DNa01", "left"), "DNa01_right": g("DNa01", "right"),
        "DNa02_left": g("DNa02", "left"), "DNa02_right": g("DNa02", "right"),
        "oDN1_left": g("DNg97", "left"), "oDN1_right": g("DNg97", "right"),  # P9_oDN1 = DNg97
        "GF": ann.root_id[ann.cell_type == "DNp01"].astype("int64").tolist(),
    }


# ---------------------------------------------------------------------------
class LoomingFrontEnd:
    """手写视觉前端（非连接组）：只看上半视野的 looming 检测。

    旧版用整只眼的暗面积增长率：果蝇自己的腿在下半视野里随步态晃动，
    冒烟测试中远处的球还没来 LC4 就被打满 200 Hz。修正：
      1. 校准：场景里没有物体时拍一帧，亮度 > sky_thr 的小眼算“天空”
      2. 地平线：每只眼里非天空小眼的最高（行坐标最小）位置；只保留在其上方 margin_px 以上的天空小眼
         → 腿、地面、随身体俯仰上下抖动的地平线附近小眼都被排除
      3. 暗面积比例做指数低通，增长率加死区，只把“持续变大”的暗区当 looming
    小眼的行坐标来自 flygym Retina.ommatidia_id_map（鱼眼校正后 512×450 的图像坐标，行越小越靠上）。
    """

    def __init__(self, retina, sky_thr=0.97, dark_thr=0.2, margin_px=40, tau_s=0.03, deadband=0.05):
        idmap = retina.ommatidia_id_map.astype(int)
        rows = np.nonzero(idmap)[0]
        ids = idmap[idmap > 0] - 1
        self.row = np.bincount(ids, weights=rows) / np.bincount(ids)  # 每个小眼的平均行坐标
        self.sky_thr, self.dark_thr, self.margin_px = sky_thr, dark_thr, margin_px
        self.tau_s, self.deadband = tau_s, deadband
        self.mask = None
        self.smooth = None

    def calibrate(self, ommatidia):
        bright = ommatidia.max(axis=2)  # (2, 721)
        masks = []
        for e in range(2):
            sky = bright[e] > self.sky_thr
            if sky.all() or not sky.any():
                raise RuntimeError(f"眼 {e} 校准失败：天空小眼数 {sky.sum()}/721，检查场景亮度或 sky_thr")
            horizon = self.row[~sky].min()
            masks.append(sky & (self.row < horizon - self.margin_px))
        self.mask = np.array(masks)
        if (self.mask.sum(axis=1) < 20).any():
            raise RuntimeError(f"上半视野小眼太少 {self.mask.sum(axis=1)}，调小 margin_px")
        return self.mask

    def step(self, ommatidia, dt):
        dark_px = ommatidia.max(axis=2) < self.dark_thr
        dark = np.array([dark_px[e, self.mask[e]].mean() for e in range(2)])  # 上半视野暗面积比例
        if self.smooth is None:
            self.smooth, expansion = dark.copy(), np.zeros(2)
        else:
            alpha = dt / (self.tau_s + dt)
            new = self.smooth + alpha * (dark - self.smooth)
            expansion = (new - self.smooth) / dt  # 比例/秒
            self.smooth = new
        expansion = np.where(np.abs(expansion) < self.deadband, 0.0, expansion)
        return dark, expansion


def build_world(looming):
    fly = make_locomotion_fly(name="fly", add_adhesion=True, colorize=True)
    fly.add_vision()
    cam = fly.add_tracking_camera(name="topcam", pos_offset=(0.0, 0.0, 30.0),
                                  rotation=Rotation3D("euler", (0.0, 0.0, 0.0)), fovy=60.0)
    world = FlatGroundWorld()
    tex = next(t for t in world.mjcf_root.textures if t.name == "checker")
    tex.rgb1, tex.rgb2 = [0.85, 0.85, 0.85], [0.95, 0.95, 0.95]  # 亮地面，见 flygym_vision_demo.py
    if looming:  # mocap 黑球：每个窗口手动更新位置，只做视觉不碰撞
        ball = world.mjcf_root.worldbody.add_body(name="looming_ball", mocap=True, pos=(8, 25, 2.5))
        ball.add_geom(type=GEOM_TYPES["sphere"], size=(2.5, 0, 0), rgba=(0.02, 0.02, 0.02, 1),
                      contype=0, conaffinity=0)
    world.add_fly(fly, [0, 0, 0.8], Rotation3D("quat", [1, 0, 0, 0]),
                  bodysegs_with_ground_contact=ContactBodiesPreset.TIBIA_TARSUS_ONLY,
                  add_ground_contact_sensors=False)
    sim = Simulation(world)
    sim.set_renderer([cam], camera_res=(400, 400), playback_speed=0.2, output_fps=25)
    return fly, sim, cam


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=1.0)
    ap.add_argument("--window_ms", type=float, default=15.0, help="脑-身同步周期")
    ap.add_argument("--no-looming", action="store_true")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--lc4_gain", type=float, default=19.8,
                    help="Hz / (暗面积比例/秒)。19.8 = 200 Hz ÷ p95(expansion)，"
                         "按报告 §27 事先写定的规则 A 标定。旧默认值 4000 高了 202 倍，"
                         "导致 LC4 全程饱和、只有 0 和 200 两个值。")
    ap.add_argument("--turn_gain", type=float, default=0.02, help="每 Hz 的 DNa 左右差 → 驱动差")
    ap.add_argument("--frontend-only", action="store_true",
                    help="不加载大脑（省内存、快），恒定直行驱动，只检验视觉前端给 LC4 的输入")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    looming = not a.no_looming
    tag = ("frontend_" if a.frontend_only else "") + ("looming" if looming else "control")
    a.out = a.out or HERE / "results" / f"connectome_loop_{tag}"
    a.out.mkdir(parents=True, exist_ok=True)
    device = a.device if a.device != "auto" else (
        "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")

    brain = None
    if not a.frontend_only:
        t0 = time.perf_counter()
        brain = ConnectomeBrain(device, groups_from_annotations())
        brain.set_rate("P9", 100.0)
        print(f"大脑就绪 ({device}) {time.perf_counter() - t0:.1f}s；各组神经元数:",
              {k: len(v) for k, v in brain.groups.items()})

    fly, sim, cam = build_world(looming)
    steps = PreprogrammedSteps(); order = fly.get_actuated_jointdofs_order("position")
    ctrl = HybridTurningController(timestep=sim.timestep, preprogrammed_steps=steps, output_dof_order=order)
    sim.reset(); ctrl.reset(seed=0)
    apply_locomotion_action(sim, fly.name, LocomotionAction(
        joint_angles=steps.default_pose_by_dof_order(order), adhesion_onoff=np.ones(6, bool)))
    sim.warmup()
    th = fly.get_bodysegs_order().index(BodySegment("c_thorax"))

    # 校准视觉前端：先把球藏到地下，拍一帧只有天空和地面的图
    BALL_START = np.array([8.0, 25.0, 2.5])
    if looming:
        sim.mj_data.mocap_pos[0] = [0.0, 0.0, -100.0]
    sim.get_ommatidia_readouts(fly.name)  # 第一次调用会懒加载 Retina
    frontend = LoomingFrontEnd(sim.retina)
    mask = frontend.calibrate(sim.get_ommatidia_readouts(fly.name))
    print(f"视觉前端校准：上半视野小眼 左 {mask[0].sum()} / 右 {mask[1].sum()}（每眼共 721）")
    if looming:
        sim.mj_data.mocap_pos[0] = BALL_START

    phys_per_win = int(round(a.window_ms / 1000 / sim.timestep))
    brain_per_win = int(round(a.window_ms / DT_MS))
    n_win = int(a.duration * 1000 / a.window_ms)
    drive, freeze_until, log = np.zeros(2), -1.0, []
    t_brain = t_body = 0.0
    for w in range(n_win):
        t = w * a.window_ms / 1000
        pos = sim.get_body_positions(fly.name)[th].copy()
        if looming:  # 球从左前方以 ~25 mm/s 朝果蝇当前位置飞来，t=0.9s 左右到达
            frac = min(1.0, t / 0.9)
            sim.mj_data.mocap_pos[0] = BALL_START + frac * (np.r_[pos[:2], 2.5] - BALL_START)

        # —— 感知：复眼 → 上半视野暗面积（低通）→ 增长率（looming）→ LC4 频率（手写前端）——
        dark, expansion = frontend.step(sim.get_ommatidia_readouts(fly.name), a.window_ms / 1000)
        lc4 = np.clip(a.lc4_gain * expansion, 0, 200)

        if brain is None:  # --frontend-only：不跑大脑，恒定直行，只记录前端输出
            r = {k: 0.0 for k in ["P9", "LC4_left", "LC4_right", "DNa01_left", "DNa01_right",
                                  "DNa02_left", "DNa02_right", "oDN1_left", "oDN1_right", "GF"]}
            r["oDN1_left"] = r["oDN1_right"] = 15.0
        else:
            brain.set_rate("LC4_left", lc4[0]); brain.set_rate("LC4_right", lc4[1])
            # —— 大脑：全脑 LIF 推进一个窗口 ——
            tb = time.perf_counter(); r = brain.run_window(brain_per_win); t_brain += time.perf_counter() - tb

        # —— 行动：下行神经元 → [左, 右] 驱动（手写映射）——
        fwd = np.clip((r["oDN1_left"] + r["oDN1_right"]) / 2 / 15.0, 0.0, 1.2)
        dna_l = r["DNa01_left"] + r["DNa02_left"]; dna_r = r["DNa01_right"] + r["DNa02_right"]
        # 推测：某侧 DNa 活跃 → 向该侧转（Rayshubskiy et al. 2020 对 DNa02 的描述）；
        # 实测 [1.2,0.4]（左强）→ 右转，所以右侧 DNa 活跃 → 左驱动加大
        turn = np.clip(a.turn_gain * (dna_r - dna_l), -0.8, 0.8)
        drive = np.array([fwd + turn, fwd - turn])
        if r["GF"] > 50:  # Giant Fiber 高频 = 逃逸指令。FlyGym 行走模型没有起飞，这里只能冻结 100 ms 占位
            freeze_until = t + 0.1
        if t < freeze_until:
            drive = np.zeros(2)

        tb = time.perf_counter()
        for _ in range(phys_per_win):
            obs = HybridControllerObservation.from_sim(sim, fly.name)
            apply_locomotion_action(sim, fly.name, ctrl.step(drive, obs))
            sim.step(); sim.render_as_needed()
        t_body += time.perf_counter() - tb
        # exp_L/R = 前端算出的暗面积增长率（低通 + 死区之后），单位「暗面积比 / 秒」。
        # 必须单独记：LC4 = clip(gain × expansion, 0, 200)，一旦饱和就再也反推不出 expansion，
        # 也就无从标定 gain（2026-09-16 补记，见报告 §26–27）。
        log.append(dict(t=t, x=pos[0], y=pos[1], dark_L=dark[0], dark_R=dark[1],
                        exp_L=expansion[0], exp_R=expansion[1], LC4_L_hz=lc4[0],
                        LC4_R_hz=lc4[1], drive_L=drive[0], drive_R=drive[1], **{k + "_hz": v for k, v in r.items()}))
        if w % 10 == 0:
            print(f"t={t:.3f}s LC4={lc4.round(0)} GF={r['GF']:.0f}Hz DNa L/R={dna_l:.0f}/{dna_r:.0f} "
                  f"oDN1={fwd * 15:.0f}Hz drive={drive.round(2)} pos={pos[:2].round(2)} "
                  f"[brain {t_brain:.0f}s body {t_body:.0f}s]", flush=True)

    df = pd.DataFrame(log); df.to_csv(a.out / "log.csv", index=False)
    sim.renderer.save_video(a.out / "loop.mp4")
    print(f"完成：{a.duration}s 模拟，大脑 {t_brain:.0f}s + 身体 {t_body:.0f}s；"
          f"GF 窗口数(>50Hz) {(df.GF_hz > 50).sum()}；终点 {df[['x', 'y']].iloc[-1].round(2).tolist()} mm")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(4, 1, figsize=(9, 11), sharex=True)
    ax[0].plot(df.t, df.dark_L, label="dark L"); ax[0].plot(df.t, df.dark_R, label="dark R"); ax[0].legend()
    ax[0].set_title("vision: dark fraction in upper visual field (calibrated mask)")
    ax[1].plot(df.t, df.LC4_L_hz, label="LC4 L input"); ax[1].plot(df.t, df.LC4_R_hz, label="LC4 R input")
    ax[1].plot(df.t, df.GF_hz, "k", label="Giant Fiber (brain)"); ax[1].legend(); ax[1].set_ylabel("Hz")
    for k in ["DNa01_left", "DNa01_right", "DNa02_left", "DNa02_right", "oDN1_left", "oDN1_right"]:
        ax[2].plot(df.t, df[k + "_hz"], label=k)
    ax[2].legend(ncols=3, fontsize=8); ax[2].set_ylabel("Hz"); ax[2].set_title("descending neurons (connectome output)")
    ax[3].plot(df.t, df.drive_L, label="drive L"); ax[3].plot(df.t, df.drive_R, label="drive R")
    ax[3].legend(); ax[3].set_xlabel("t (s)")
    fig.tight_layout(); fig.savefig(a.out / "loop_signals.png", dpi=110)
    fig, ax = plt.subplots(figsize=(5, 5)); ax.plot(df.x, df.y); ax.plot(df.x[0], df.y[0], "go")
    ax.set_aspect("equal"); ax.set_xlabel("x (mm)"); ax.set_ylabel("y (mm, +left)")
    fig.savefig(a.out / "trajectory.png", dpi=110)

    # 校准得到的上半视野掩膜（白 = 参与 looming 计算的小眼），用于人工检查
    fig, axs = plt.subplots(1, 2, figsize=(6, 3.4))
    for e, name in enumerate(["left eye", "right eye"]):
        img = sim.retina.hex_pxls_to_human_readable(mask[e].astype(float)[:, None], default_value=0.5)[..., 0]
        axs[e].imshow(img, cmap="gray", vmin=0, vmax=1); axs[e].set_title(f"{name}: {mask[e].sum()} used")
        axs[e].axis("off")
    fig.tight_layout(); fig.savefig(a.out / "frontend_mask.png", dpi=110)


if __name__ == "__main__":
    main()
