#!/usr/bin/env python
"""把挂了很久的一条定论清掉：Fly-Brain-AI 的 turn_drive 符号到底朝哪边？

背景（CLAUDE.md 里记为"未定论"）：
  作者的 `interfaces.py` 与论文草稿都说 `turn_drive > 0` 表示**向右**，并报告"对侧逃逸"。
  但 `LocomotionBridge` 的代码是 `left_scale = 1 - 0.3*max(0, turn_drive)` ——
  正值缩小**左腿**幅度，身体应当转**左**。我们上一轮只用 1 个种子测过一次
  （左 LPLC2 注入 → turn_drive ≈ +0.35、侧移 y ≈ +4 mm，即转向被刺激的那一侧），
  按规矩"多种子 + 打乱对照确认之前不能当事实"。这个脚本就是来确认的。

── 跑之前写定的判据 ──────────────────────────────────────
  H  代码读出来的符号（正值转左）是对的，作者文档写反了；
     因此左 LPLC2 注入会转向**同侧**（左），与作者报告的"对侧逃逸"相反。
  C1 loom_left 的平均 turn_drive 为正、loom_right 为负，各自 ≥ 2/3 种子成立。
  C2 净侧移：loom_left 比 loom_right 更偏左（本体坐标 +y），≥ 2/3 种子成立。
  C3 打乱连接组之后，左右差异明显变小（若差异来自连接组而非步态偏置）。
  对照 control（不注入）：turn_drive ≈ 0，无系统性侧偏。
────────────────────────────────────────────────────────

不复制作者代码，只 import。仓库无许可证，结果仅供本地。
用法（fba 环境，套 memguard；约 15 分钟、峰值 ~4.5 GB）：
  python fba_turn_sign.py [--seeds 42 43 44] [--body-steps 5000]
输出 results/fba_turn_sign.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PF = HERE / "external" / "Fly-Brain-AI" / "plastic-fly"
sys.path.insert(0, str(PF))

import flygym  # noqa: E402
from bridge.config import BridgeConfig  # noqa: E402
from bridge.interfaces import LocomotionCommand  # noqa: E402
from bridge.sensory_encoder import SensoryEncoder  # noqa: E402
from bridge.brain_runner import create_brain_runner  # noqa: E402
from bridge.descending_decoder import DescendingDecoder  # noqa: E402
from bridge.locomotion_bridge import LocomotionBridge  # noqa: E402
from bridge.flygym_adapter import FlyGymAdapter  # noqa: E402


def load_ids(cfg):
    """与 fba_export_replay.py 同源（那边写在 main 里，这里抽出来）。"""
    channel_map = json.load(open(cfg.data_dir / "channel_map_v4_looming.json"))
    sensory_ids = np.load(cfg.data_dir / "sensory_ids_v4_looming.npy")
    readout_ids = np.load(cfg.data_dir / "readout_ids_v4_looming.npy")
    return sensory_ids, channel_map, readout_ids, cfg.data_dir / "decoder_groups_v4_looming.json"

CONDITIONS = {"loom_left": (1.0, 0.0), "loom_right": (0.0, 1.0), "control": (0.0, 0.0)}


def trial(cond, seed, shuffle_seed, a, cfg, sensory_ids, channel_map, readout_ids, decoder_path):
    loom_l, loom_r = CONDITIONS[cond]
    encoder = SensoryEncoder(sensory_neuron_ids=sensory_ids, channel_map=channel_map,
                             max_rate_hz=cfg.max_rate_hz, baseline_rate_hz=cfg.baseline_rate_hz)
    decoder = DescendingDecoder.from_json(decoder_path, rate_scale=a.rate_scale)
    locomotion = LocomotionBridge(seed=seed)
    adapter = FlyGymAdapter()
    brain = create_brain_runner(sensory_ids=sensory_ids, readout_ids=readout_ids, use_fake=False,
                                warmup_ms=cfg.brain_warmup_ms, shuffle_seed=shuffle_seed)
    fly = flygym.Fly(enable_adhesion=True, init_pose="stretch", control="position")
    sim = flygym.SingleFlySimulation(fly=fly, arena=flygym.arena.FlatTerrain(), timestep=1e-4)
    obs, _ = sim.reset()
    locomotion.warmup(0)
    locomotion.cpg.reset(init_phases=np.array([0, np.pi, 0, np.pi, 0, np.pi]), init_magnitudes=np.zeros(6))
    for _ in range(a.warmup_steps):
        obs, *_ = sim.step(locomotion.step(LocomotionCommand(forward_drive=1.0)))

    p0 = np.array(obs["fly"][0], float)
    yaw0 = float(obs["fly"][2][2])           # 朝向（弧度），warmup 之后的起点
    bspb = int(a.brain_dt_ms / (1e-4 * 1000))
    ch = encoder._channels
    cmd = LocomotionCommand(forward_drive=1.0)
    turns = []
    t0 = time.time()
    for step in range(a.body_steps):
        if step % bspb == 0:
            bo = adapter.extract_body_observation(obs)
            bo.looming_intensity = np.array([loom_l, loom_r])
            out = brain.step(encoder.encode(bo), sim_ms=a.brain_dt_ms)
            cmd = decoder.decode(out)
            turns.append(float(cmd.turn_drive))
        obs, _, term, trunc, _ = sim.step(locomotion.step(cmd))
        if term or trunc:
            break
    p1 = np.array(obs["fly"][0], float)
    yaw1 = float(obs["fly"][2][2])
    sim.close()
    # 本体坐标下的净位移：按**起点朝向**旋转，+y = 果蝇左侧
    d = p1 - p0
    fwd = d[0] * np.cos(-yaw0) - d[1] * np.sin(-yaw0)
    lat = d[0] * np.sin(-yaw0) + d[1] * np.cos(-yaw0)
    dyaw = float(np.degrees((yaw1 - yaw0 + np.pi) % (2 * np.pi) - np.pi))
    r = dict(condition=cond, seed=seed, shuffled=shuffle_seed is not None,
             mean_turn_drive=round(float(np.mean(turns)), 4),
             net_forward_mm=round(float(fwd), 3), net_lateral_mm=round(float(lat), 3),
             net_yaw_deg=round(dyaw, 2), secs=round(time.time() - t0, 1))
    print(f"  {cond:11s} seed {seed} {'打乱' if shuffle_seed else '真实'}："
          f"turn_drive {r['mean_turn_drive']:+.4f}  净侧移 {r['net_lateral_mm']:+.2f} mm"
          f"  净转角 {r['net_yaw_deg']:+.1f}°  ({r['secs']}s)", flush=True)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    ap.add_argument("--body-steps", type=int, default=5000)
    ap.add_argument("--warmup-steps", type=int, default=500)
    ap.add_argument("--brain-dt-ms", type=float, default=50.0)
    ap.add_argument("--rate-scale", type=float, default=12.0)
    a = ap.parse_args()
    cfg = BridgeConfig()
    sensory_ids, channel_map, readout_ids, decoder_path = load_ids(cfg)
    rows = []
    for seed in a.seeds:
        for cond in ("loom_left", "loom_right"):
            for shuf in (None, 999):
                rows.append(trial(cond, seed, shuf, a, cfg, sensory_ids, channel_map, readout_ids, decoder_path))
        rows.append(trial("control", seed, None, a, cfg, sensory_ids, channel_map, readout_ids, decoder_path))

    def sel(cond, shuf):
        return [r for r in rows if r["condition"] == cond and r["shuffled"] == shuf]
    out = dict(design=dict(seeds=a.seeds, body_steps=a.body_steps, brain_dt_ms=a.brain_dt_ms,
                           note="净侧移在**起点朝向**的本体坐标里，+y = 果蝇左侧；打乱用作者自己的 shuffle_seed=999"),
               hypothesis="代码 left_scale=1-0.3*max(0,turn_drive) → 正值转左；作者文档说正值转右",
               criteria={"C1": "loom_left 的 turn_drive 为正、loom_right 为负，各 ≥2/3 种子",
                         "C2": "净侧移 loom_left > loom_right，≥2/3 种子",
                         "C3": "打乱后左右差异明显变小"},
               trials=rows)
    n = len(a.seeds)
    c1a = sum(1 for r in sel("loom_left", False) if r["mean_turn_drive"] > 0)
    c1b = sum(1 for r in sel("loom_right", False) if r["mean_turn_drive"] < 0)
    L = {r["seed"]: r for r in sel("loom_left", False)}
    R = {r["seed"]: r for r in sel("loom_right", False)}
    c2 = sum(1 for s in a.seeds if L[s]["net_lateral_mm"] > R[s]["net_lateral_mm"])
    dReal = float(np.mean([L[s]["net_lateral_mm"] - R[s]["net_lateral_mm"] for s in a.seeds]))
    Ls = {r["seed"]: r for r in sel("loom_left", True)}
    Rs = {r["seed"]: r for r in sel("loom_right", True)}
    dShuf = float(np.mean([Ls[s]["net_lateral_mm"] - Rs[s]["net_lateral_mm"] for s in a.seeds]))
    ctrl = sel("control", False)
    out["result"] = dict(C1_left_positive=f"{c1a}/{n}", C1_right_negative=f"{c1b}/{n}",
                         C2_left_more_left=f"{c2}/{n}",
                         lateral_diff_real_mm=round(dReal, 3), lateral_diff_shuffled_mm=round(dShuf, 3),
                         C3_shuffled_smaller=bool(abs(dShuf) < abs(dReal)),
                         control_mean_turn_drive=round(float(np.mean([r["mean_turn_drive"] for r in ctrl])), 4),
                         control_mean_lateral_mm=round(float(np.mean([r["net_lateral_mm"] for r in ctrl])), 3))
    print("\n判据对答案：")
    print(f"  C1 loom_left turn_drive 为正 {c1a}/{n}；loom_right 为负 {c1b}/{n}")
    print(f"  C2 净侧移 left > right：{c2}/{n}")
    print(f"  C3 左右侧移差：真实 {dReal:+.2f} mm，打乱 {dShuf:+.2f} mm → "
          f"{'打乱后确实变小 ✓' if abs(dShuf) < abs(dReal) else '打乱后没变小 ✗'}")
    print(f"  对照 control：turn_drive {out['result']['control_mean_turn_drive']:+.4f}，"
          f"净侧移 {out['result']['control_mean_lateral_mm']:+.2f} mm")
    Path(HERE / "results").mkdir(exist_ok=True)
    (HERE / "results/fba_turn_sign.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("\n→ results/fba_turn_sign.json")


if __name__ == "__main__":
    main()
