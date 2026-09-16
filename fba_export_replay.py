#!/usr/bin/env python
"""
重跑 neilt93/Fly-Brain-AI 的 looming 实验，并导出 three.js 回放数据（身体 3D 位姿 + 大脑读出）。

与原作者 experiments/looming.py 保持一致的部分（参数取其 CLI 默认值 / 我们上一轮实测用的值）：
  LPLC2 注入：loom_left / loom_right / control 三个条件，seed 42；
  brain_dt 50 ms、每窗 500 个身体步、warmup 500 步、body_steps 5000（0.5 s）、rate_scale 12；
  传感/读出 ID：channel_map_v4_looming.json + 还原的 *_v4_looming.npy（见 fba_reconstruct_ids.py）；
  SensoryEncoder / Brian2BrainRunner / DescendingDecoder / LocomotionBridge 全部直接 import 原代码。
额外做的事：每 25 个身体步记录 69 个网格部件的世界位姿；每个大脑窗口记录各解码分组发放率、
LPLC2 输入、LocomotionCommand；网格做顶点聚类简化后一并写入 JSON。

Fly-Brain-AI 仓库没有许可证：本脚本只在本地调用它，不复制其代码；导出数据仅供本地查看。

用法（fba 环境，峰值内存约 4–5 GB，约 1–2 分钟）：
  python fba_export_replay.py [--conditions loom_left loom_right control] [--out results/fba_replay/replay.json]
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

import flygym  # noqa: E402  flygym 1.2.1
import mujoco  # noqa: E402
from bridge.config import BridgeConfig  # noqa: E402
from bridge.interfaces import LocomotionCommand  # noqa: E402
from bridge.sensory_encoder import SensoryEncoder  # noqa: E402
from bridge.brain_runner import create_brain_runner  # noqa: E402
from bridge.descending_decoder import DescendingDecoder  # noqa: E402
from bridge.locomotion_bridge import LocomotionBridge  # noqa: E402
from bridge.flygym_adapter import FlyGymAdapter  # noqa: E402

CONDITIONS = {"loom_left": (1.0, 0.0), "loom_right": (0.0, 1.0), "control": (0.0, 0.0)}


def simplify_mesh(verts, faces, bins=14):
    """顶点聚类简化：把顶点吸附到 bins³ 网格，合并同格顶点，去掉退化三角形。"""
    lo, hi = verts.min(0), verts.max(0)
    cell = np.maximum((hi - lo) / bins, 1e-9)
    key = np.floor((verts - lo) / cell).astype(np.int64)
    key = key[:, 0] * (bins + 1) ** 2 + key[:, 1] * (bins + 1) + key[:, 2]
    uniq, inv = np.unique(key, return_inverse=True)
    counts = np.bincount(inv)
    new_v = np.stack([np.bincount(inv, weights=verts[:, k]) / counts for k in range(3)], 1)
    f = inv[faces]
    f = f[(f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])]
    f = np.unique(np.sort(f, axis=1), axis=0) if len(f) else f  # 去重（丢失朝向，前端双面渲染）
    return new_v.astype(np.float32), f.astype(np.int32)


def export_meshes(m):
    geoms = []
    for g in range(m.ngeom):
        if m.geom_type[g] != mujoco.mjtGeom.mjGEOM_MESH:
            continue
        mid = m.geom_dataid[g]
        va, vn = m.mesh_vertadr[mid], m.mesh_vertnum[mid]
        fa, fn = m.mesh_faceadr[mid], m.mesh_facenum[mid]
        v = np.array(m.mesh_vert[va:va + vn], dtype=np.float64)
        f = np.array(m.mesh_face[fa:fa + fn], dtype=np.int64)
        sv, sf = simplify_mesh(v, f)
        name = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, g) or f"geom{g}"
        geoms.append(dict(id=int(g), name=name.split("/")[-1], group=int(m.geom_group[g]),
                          verts=np.round(sv, 4).ravel().tolist(), faces=sf.ravel().tolist()))
    return geoms


def run_trial(cond, seed, a, cfg, sensory_ids, channel_map, readout_ids, decoder_path, record_meshes):
    loom_l, loom_r = CONDITIONS[cond]
    encoder = SensoryEncoder(sensory_neuron_ids=sensory_ids, channel_map=channel_map,
                             max_rate_hz=cfg.max_rate_hz, baseline_rate_hz=cfg.baseline_rate_hz)
    decoder = DescendingDecoder.from_json(decoder_path, rate_scale=a.rate_scale)
    locomotion = LocomotionBridge(seed=seed)
    adapter = FlyGymAdapter()
    brain = create_brain_runner(sensory_ids=sensory_ids, readout_ids=readout_ids, use_fake=False,
                                warmup_ms=cfg.brain_warmup_ms, shuffle_seed=None)

    fly = flygym.Fly(enable_adhesion=True, init_pose="stretch", control="position")
    sim = flygym.SingleFlySimulation(fly=fly, arena=flygym.arena.FlatTerrain(), timestep=1e-4)
    obs, info = sim.reset()
    locomotion.warmup(0)
    locomotion.cpg.reset(init_phases=np.array([0, np.pi, 0, np.pi, 0, np.pi]), init_magnitudes=np.zeros(6))
    for _ in range(a.warmup_steps):
        obs, *_ = sim.step(locomotion.step(LocomotionCommand(forward_drive=1.0)))

    m, d = sim.physics.model.ptr, sim.physics.data.ptr
    mesh_ids = [g for g in range(m.ngeom) if m.geom_type[g] == mujoco.mjtGeom.mjGEOM_MESH]
    meshes = export_meshes(m) if record_meshes else None

    bspb = int(a.brain_dt_ms / (1e-4 * 1000))
    ch = encoder._channels  # 通道 → sensory 向量里的位置（原代码私有属性）
    cmd = LocomotionCommand(forward_drive=1.0)
    frames, brain_log = [], []
    q = np.zeros(4)
    t0 = time.time()
    for step in range(a.body_steps):
        if step % bspb == 0:
            bo = adapter.extract_body_observation(obs)
            bo.looming_intensity = np.array([loom_l, loom_r])
            bi = encoder.encode(bo)
            out = brain.step(bi, sim_ms=a.brain_dt_ms)
            cmd = decoder.decode(out)
            rates = decoder.get_group_rates(out)
            brain_log.append(dict(
                t=round(step * 1e-4, 4),
                lplc2_left_hz=float(np.mean(bi.firing_rates_hz[ch["lplc2_left"]])),
                lplc2_right_hz=float(np.mean(bi.firing_rates_hz[ch["lplc2_right"]])),
                **{f"{k}_hz": round(v, 3) for k, v in rates.items()},
                forward_drive=round(cmd.forward_drive, 4), turn_drive=round(cmd.turn_drive, 4),
                step_frequency=round(cmd.step_frequency, 4), stance_gain=round(cmd.stance_gain, 4),
                readout_active=int(np.sum(out.firing_rates_hz > 0))))
        obs, _, term, trunc, _ = sim.step(locomotion.step(cmd))
        if step % a.frame_every == 0:
            poses = []
            for g in mesh_ids:
                mujoco.mju_mat2Quat(q, d.geom_xmat[g])
                poses.extend(np.round(d.geom_xpos[g], 4).tolist() + np.round(q, 4).tolist())
            frames.append(dict(t=round(step * 1e-4, 4), pose=poses,
                               thorax=np.round(obs["fly"][0], 4).tolist()))
        if term or trunc:
            break
    sim.close()
    turn = [b["turn_drive"] for b in brain_log]
    p = np.array([f["thorax"] for f in frames])
    print(f"  {cond}: mean turn_drive {np.mean(turn):+.4f}，终点位移 x={p[-1, 0] - p[0, 0]:+.2f} "
          f"y={p[-1, 1] - p[0, 1]:+.2f} mm，用时 {time.time() - t0:.1f}s", flush=True)
    return dict(condition=cond, loom_left=loom_l, loom_right=loom_r, frames=frames, brain=brain_log,
                mean_turn_drive=float(np.mean(turn))), meshes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conditions", nargs="+", default=list(CONDITIONS))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--body_steps", type=int, default=5000)
    ap.add_argument("--warmup_steps", type=int, default=500)
    ap.add_argument("--brain_dt_ms", type=float, default=50.0)
    ap.add_argument("--rate_scale", type=float, default=12.0)
    ap.add_argument("--frame_every", type=int, default=25, help="每多少个身体步记录一帧（25 = 2.5 ms）")
    ap.add_argument("--out", type=Path, default=HERE / "results" / "fba_replay" / "replay.json")
    a = ap.parse_args()

    cfg = BridgeConfig()
    channel_map = json.load(open(cfg.data_dir / "channel_map_v4_looming.json"))
    sensory_ids = np.load(cfg.data_dir / "sensory_ids_v4_looming.npy")
    readout_ids = np.load(cfg.data_dir / "readout_ids_v4_looming.npy")
    decoder_path = cfg.data_dir / "decoder_groups_v4_looming.json"

    trials, meshes = [], None
    for cond in a.conditions:
        tr, ms = run_trial(cond, a.seed, a, cfg, sensory_ids, channel_map, readout_ids, decoder_path,
                           record_meshes=meshes is None)
        meshes = meshes or ms
        trials.append(tr)

    a.out.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(
        meta=dict(source="neilt93/Fly-Brain-AI @ 64bdbaf (plastic-fly/experiments/looming.py logic)",
                  flygym="1.2.1", seed=a.seed, body_steps=a.body_steps, brain_dt_ms=a.brain_dt_ms,
                  frame_dt_s=a.frame_every * 1e-4, rate_scale=a.rate_scale,
                  axes="MuJoCo world: +x forward (initial heading), +y fly's left, +z up (mm)",
                  turn_sign_note="LocomotionBridge: turn_drive>0 shrinks LEFT leg amplitude → body turns LEFT; "
                                 "interfaces.py comment and paper say '+ = right'"),
        meshes=meshes, trials=trials)
    a.out.write_text(json.dumps(payload, separators=(",", ":")))
    nv = sum(len(g["verts"]) // 3 for g in meshes); nf = sum(len(g["faces"]) // 3 for g in meshes)
    print(f"写入 {a.out}（{a.out.stat().st_size / 1e6:.1f} MB）：{len(meshes)} 个网格，简化后 {nv} 顶点 / {nf} 面；"
          f"每个条件 {len(trials[0]['frames'])} 帧")


if __name__ == "__main__":
    main()
