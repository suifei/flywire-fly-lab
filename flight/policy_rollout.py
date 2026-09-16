#!/usr/bin/env python
"""
用 flybody 论文公开的训练好的飞行控制器（Vaxenburg et al. 2025 Nature；figshare 10.25378/janelia.25309105
trained-fly-policies.zip → flight/，TensorFlow SavedModel，数据许可 GPL-3.0+）在 MuJoCo 里真实地“飞”一遍，
替换游戏里原来的运动学回放（身体按记录摆位 + 通用拍翅模式）。

与原导出（flight/export_flight.py）的区别：
  * 身体：不再直接摆到记录的位置，而是物理仿真——控制器输出翅膀与“用户”动作，流体力推动身体去跟踪记录轨迹；
    跟踪误差逐帧记录并报告。
  * 翅膀：flybody 飞行任务里，控制器的“用户”动作设定拍翅频率（218 Hz × (1 ± 相对范围)），拍翅模式发生器按这个频率给出
    目标角，控制器另外给每个翅膀关节加一份力控制修正；实际翅膀角度由物理引擎算出，左右可以不同。
  * 轨迹：与原导出同一规则选出的两条原始逃逸轨迹（左转 067、右转 044），环境参数用 flybody 默认值（与训练一致），
    只把 randomize_start_step 关掉；控制器取分布均值（不采样）。
导出格式与 flight_clips.json 相同，另加跟踪误差与翅膀不对称统计。网格只取真正的果蝇模型（walker），不含任务里的 ghost 参考模型。
用法（flybody-tf 环境）：MUJOCO_GL=glfw python flight/policy_rollout.py
"""
import json
from pathlib import Path

import sys

import mujoco
import numpy as np
import tensorflow as tf

from flybody.fly_envs import flight_imitation

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tfp_compat import load_policy  # noqa: E402  TFP 0.16 → 0.24 的 TypeSpec 名映射
from export_flight import simplify_mesh, b64  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "external" / "flybody_data"
REF = D / "flight-dataset_saccade-evasion_augmented.hdf5"
WPG = D / "wing_pattern_fmech.npy"
POLICY = D / "trained-fly-policies" / "flight"
OLD = ROOT / "results" / "flight" / "flight_clips.json"
OUT = ROOT / "results" / "flight" / "flight_clips_policy.json"
FRAME_EVERY = 2
CM2MM = 10.0
TRAJ = [("left", 67), ("right", 44)]       # 与 export_flight.py 的事先规则选出的轨迹相同


def mat2quat(mat9):
    q = np.zeros(4); mujoco.mju_mat2Quat(q, mat9); return q


def rel_pose(p_parent, R_parent, p, R):
    return np.r_[R_parent.T @ (p - p_parent), mat2quat((R_parent.T @ R).ravel())]


def quat_angle_deg(q1, q2):
    return float(np.degrees(2 * np.arccos(min(1.0, abs(float(np.dot(q1, q2)))))))


def main():
    policy, aliases = load_policy(POLICY)
    print("策略已加载；TypeSpec 名映射：", aliases, flush=True)
    sig = policy.__call__.concrete_functions[0].structured_input_signature[0][0]
    obs_keys = {k: tuple(v.shape[1:]) for k, v in sig.items()}
    old = json.loads(OLD.read_text())
    out = dict(source=dict(body="TuragaLab/flybody fruitfly (Apache-2.0)",
                           trajectories=old["source"]["trajectories"],
                           controller="flybody trained flight policy (figshare 10.25378/janelia.25309105, trained-fly-policies.zip/flight, GPL-3.0+)",
                           wings="physics simulation: controller sets wingbeat frequency and adds per-joint force corrections on top of the flybody base pattern"),
               units="mm", meshes=None, static_pose=None, clips=[],
               note="只含真正的果蝇模型（walker）网格；旧导出 flight_clips.json 误把任务里的 ghost 参考模型（81 个网格、腿未收起）也放进了飞行模型")
    for turn, traj_id in TRAJ:
        env = flight_imitation(ref_path=str(REF), wpg_pattern_path=str(WPG), traj_indices=[traj_id], randomize_start_step=False)
        ts = env.reset()
        task, phys = env.task, env.physics
        m, d = phys.model.ptr, phys.data.ptr
        name = lambda t, i: mujoco.mj_id2name(m, t, i) or ""
        vis = [g for g in range(m.ngeom) if m.geom_group[g] == 1 and m.geom_type[g] == mujoco.mjtGeom.mjGEOM_MESH]
        walker_bodies = [b for b in range(m.nbody) if name(mujoco.mjtObj.mjOBJ_BODY, b).startswith("walker/")]
        thorax = [b for b in walker_bodies if name(mujoco.mjtObj.mjOBJ_BODY, b).endswith("thorax")][0]
        vis = [g for g in vis if m.geom_bodyid[g] in walker_bodies]          # 不要“幽灵”参考模型的网格
        part = lambda g: ("wing_left" if "wing_left" in name(mujoco.mjtObj.mjOBJ_BODY, m.geom_bodyid[g]) else
                          "wing_right" if "wing_right" in name(mujoco.mjtObj.mjOBJ_BODY, m.geom_bodyid[g]) else "static")
        ref_wing = {side: next(i for i, g in enumerate(vis) if part(g) == side) for side in ("wing_left", "wing_right")}
        if out["meshes"] is None:                                              # 网格与相对胸部的静态位姿：重置后第 0 帧
            mujoco.mj_kinematics(m, d)
            pr0, Rr0 = d.xpos[thorax].copy(), d.xmat[thorax].reshape(3, 3).copy()
            meshes, static = [], []
            for g in vis:
                mid = m.geom_dataid[g]
                v = np.array(m.mesh_vert[m.mesh_vertadr[mid]:m.mesh_vertadr[mid] + m.mesh_vertnum[mid]], float)
                f_ = np.array(m.mesh_face[m.mesh_faceadr[mid]:m.mesh_faceadr[mid] + m.mesh_facenum[mid]], np.int64)
                sv, sf = simplify_mesh(v, f_, bins=10 if len(v) > 2000 else 6)
                rgba = m.mat_rgba[m.geom_matid[g]] if m.geom_matid[g] >= 0 else m.geom_rgba[g]
                meshes.append(dict(name=name(mujoco.mjtObj.mjOBJ_GEOM, g).split("/")[-1], part=part(g), rgba=np.round(rgba, 3).tolist(),
                                   verts=b64(sv * CM2MM), faces=b64(sf)))
                rp = rel_pose(pr0, Rr0, d.geom_xpos[g], d.geom_xmat[g].reshape(3, 3))
                static.append(np.r_[rp[:3] * CM2MM, rp[3:]].round(5).tolist())
            out["meshes"], out["static_pose"] = meshes, static
            print("飞行模型网格：", len(meshes), "（翅膀", sum(x["part"] != "static" for x in meshes), "）", flush=True)
        wing_jnt = {side: [j for j in range(m.njnt) if name(mujoco.mjtObj.mjOBJ_JOINT, j).startswith("walker/wing_") and name(mujoco.mjtObj.mjOBJ_JOINT, j).endswith(side.split("_")[1])]
                    for side in ("wing_left", "wing_right")}               # wing_yaw/roll/pitch_left|right
        ref = task._ref_qpos                                                   # 根位姿（cm）
        v0 = ref[min(25, len(ref) - 1), :2] - ref[0, :2]
        a0 = -np.arctan2(v0[1], v0[0])
        Rz = np.array([[np.cos(a0), -np.sin(a0), 0], [np.sin(a0), np.cos(a0), 0], [0, 0, 1]])
        qz = np.array([np.cos(a0 / 2), 0, 0, np.sin(a0 / 2)])
        env_shapes = {k: tuple(np.shape(v)) for k, v in ts.observation.items()}
        mismatch = {k: (shape, env_shapes.get(k)) for k, shape in obs_keys.items() if env_shapes.get(k) != shape}
        print("环境观测与策略输入不匹配的项：", mismatch or "无", "；环境多出的项：", sorted(set(env_shapes) - set(obs_keys)), "；动作维度", env.action_spec().shape, flush=True)
        assert not mismatch and env.action_spec().shape == (12,)
        root_frames, wl, wr, pos_err, ang_err, user_act, wing_q, wing_act = [], [], [], [], [], [], [], []
        step = 0
        while not ts.last():
            obs = {k: tf.expand_dims(tf.convert_to_tensor(ts.observation[k], dtype=tf.float32), 0) for k in obs_keys}
            dist = policy(obs)
            action = dist.mean()[0].numpy()
            user_act.append(float(action[task._user_idx_action]))
            wing_act.append(action[task._wing_inds_action].copy())
            ts = env.step(action)
            step += 1
            pr, Rr = d.xpos[thorax].copy(), d.xmat[thorax].reshape(3, 3).copy()
            k = min(step, len(ref) - 1)
            pos_err.append(float(np.linalg.norm(pr - ref[k, :3]) * CM2MM))
            ang_err.append(quat_angle_deg(mat2quat(Rr.ravel()), ref[k, 3:]))
            wing_q.append([float(d.qpos[m.jnt_qposadr[j]]) for j in wing_jnt["wing_left"] + wing_jnt["wing_right"]])
            if step % FRAME_EVERY:
                continue
            qr = np.zeros(4); mujoco.mju_mulQuat(qr, qz, mat2quat(Rr.ravel()))
            root_frames.append(np.r_[Rz @ pr * CM2MM, qr])
            for side, lst in (("wing_left", wl), ("wing_right", wr)):
                g = vis[ref_wing[side]]
                rp = rel_pose(pr, Rr, d.geom_xpos[g], d.geom_xmat[g].reshape(3, 3))
                lst.append(np.r_[rp[:3] * CM2MM, rp[3:]])
        root_frames = np.array(root_frames); root_frames[:, :3] -= root_frames[0, :3]
        n_ref = len(ref) - task._future_steps - 1
        wq = np.array(wing_q); nL = len(wing_jnt["wing_left"])
        corr = [float(np.corrcoef(wq[:, i], wq[:, nL + i])[0, 1]) for i in range(nL)]
        dt = task.control_timestep
        f = np.fft.rfftfreq(len(wq), dt); P = np.abs(np.fft.rfft(wq[:, 0] - wq[:, 0].mean()))
        freq = float(f[1:][np.argmax(P[1:])])
        stats = dict(steps=step, ref_steps=n_ref, completed=bool(step >= n_ref - 1),
                     pos_err_mm_median=round(float(np.median(pos_err)), 3), pos_err_mm_max=round(float(np.max(pos_err)), 3),
                     ang_err_deg_median=round(float(np.median(ang_err)), 2), ang_err_deg_max=round(float(np.max(ang_err)), 2),
                     wingbeat_hz=round(freq, 1), user_action_range=[round(min(user_act), 3), round(max(user_act), 3)],
                     wing_joint_names=[name(mujoco.mjtObj.mjOBJ_JOINT, j).split("/")[-1] for j in wing_jnt["wing_left"]],
                     left_right_joint_corr=[round(c, 3) for c in corr],
                     left_right_joint_amp_deg=[[round(float(np.degrees(np.ptp(wq[:, i]))), 1), round(float(np.degrees(np.ptp(wq[:, nL + i]))), 1)] for i in range(nL)],
                     policy_wing_action_abs_median=round(float(np.median(np.abs(np.array(wing_act)))), 4),
                     policy_wing_action_lr_diff_median=round(float(np.median(np.abs(np.array(wing_act)[:, :3] - np.array(wing_act)[:, 3:]))), 4))
        print(f"{turn}（轨迹 {traj_id}）：{stats}", flush=True)
        out["clips"].append(dict(name=f"evasion_{traj_id:03d}_policy", turn=turn, dt=FRAME_EVERY * dt, n_frames=len(root_frames),
                                 root=np.round(root_frames, 5).ravel().tolist(), wing_left=np.round(np.array(wl), 5).ravel().tolist(),
                                 wing_right=np.round(np.array(wr), 5).ravel().tolist(), tracking=stats))
        env.close()
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print("写入", OUT, f"{OUT.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
