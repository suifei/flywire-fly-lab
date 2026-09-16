#!/usr/bin/env python
"""
第 3 步：flybody 飞行动画数据导出（运动学回放，不是强化学习控制）。

来源：
  * 身体模型：TuragaLab/flybody（Apache-2.0）fruitfly，飞行姿态（腿收起）
  * 轨迹：figshare 10.25378/janelia.25309105 datasets_flight-imitation（GPL-3.0+），
    真实果蝇躲避逼近目标的逃逸飞行，Muijres et al. 2014 Science 344:172；质心轨迹经 flybody 的 com2root 换算
  * 翅膀：flybody WingBeatPatternGenerator + wing_pattern_fmech.npy，218 Hz 基础频率

轨迹选择（事先定好的规则，不按效果挑）：在 92 条 evasion_original 里按净偏航角正负分成左转 / 右转两组，
每组取净偏航角最接近该组中位数的一条。

导出 results/flight/flight_clips.json（单位 mm；时间 s）：
  meshes: 可视网格（顶点聚类简化），每个带颜色、所属部件（static / wing_left / wing_right）
  static_pose: 静态网格相对胸部（根）坐标系的位姿
  clips[]: {name, turn: "left"|"right", yaw_change_deg, dt, root: (帧, 7) 世界位姿（起点平移到原点、初始水平速度方向转到 +x），
           wing_left / wing_right: (帧, 7) 翅膀网格组相对根的位姿（每组一个参考网格，组内网格共用刚体变换）}
用法（flybody 环境）：MUJOCO_GL=glfw python flight/export_flight.py
"""
import base64
import json
from pathlib import Path

import h5py
import mujoco
import numpy as np

from flybody.fly_envs import flight_imitation

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "external" / "flybody_data"
REF = D / "flight-dataset_saccade-evasion_augmented.hdf5"
WPG = D / "wing_pattern_fmech.npy"
FRAME_EVERY = 2          # 每 2 个控制步（0.4 ms）记录一帧
CM2MM = 10.0


def quat_yaw(q):  # MuJoCo (w,x,y,z) → 绕 z 的偏航角
    w, x, y, z = q
    return np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def choose_trajectories():
    with h5py.File(REF, "r") as h:
        tr = h["trajectories"]
        rows = []
        for k in tr.keys():
            ttype = tr[k]["trajectory_type"][()]
            ttype = ttype.decode() if isinstance(ttype, bytes) else str(ttype)
            if ttype != "evasion_original":
                continue
            q = tr[k]["com_qpos"][:]
            yaw = np.unwrap([quat_yaw(x) for x in q[:, 3:]])
            rows.append((int(k), float(np.degrees(yaw[-1] - yaw[0])), len(q)))
    keys = sorted(tr_k for tr_k, _, _ in rows)
    left = [r for r in rows if r[1] > 0]; right = [r for r in rows if r[1] < 0]
    pick = lambda g: min(g, key=lambda r: abs(r[1] - np.median([x[1] for x in g])))
    print(f"evasion_original {len(rows)} 条：左转 {len(left)}、右转 {len(right)}；"
          f"净偏航中位 左 {np.median([r[1] for r in left]):.0f}°、右 {np.median([r[1] for r in right]):.0f}°")
    return [("left", pick(left)), ("right", pick(right))], keys


def mat2quat(mat9):
    q = np.zeros(4); mujoco.mju_mat2Quat(q, mat9); return q


def rel_pose(p_parent, R_parent, p, R):
    Rrel = R_parent.T @ R
    return np.r_[R_parent.T @ (p - p_parent), mat2quat(Rrel.ravel())]


def simplify_mesh(verts, faces, bins):
    lo, hi = verts.min(0), verts.max(0)
    cell = np.maximum((hi - lo) / bins, 1e-9)
    key = np.floor((verts - lo) / cell).astype(np.int64)
    key = key[:, 0] * (bins + 1) ** 2 + key[:, 1] * (bins + 1) + key[:, 2]
    _, inv = np.unique(key, return_inverse=True)
    cnt = np.bincount(inv)
    nv = np.stack([np.bincount(inv, weights=verts[:, i]) / cnt for i in range(3)], 1)
    f = inv[faces]
    f = f[(f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])]
    return nv.astype(np.float32), f.astype(np.uint32)


def b64(a):
    return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode()


def main():
    chosen, keys = choose_trajectories()
    out = dict(source=dict(body="TuragaLab/flybody fruitfly (Apache-2.0)",
                           trajectories="Muijres et al. 2014 Science 344:172 via flybody figshare 10.25378/janelia.25309105 (GPL-3.0+)",
                           wings="flybody WingBeatPatternGenerator + wing_pattern_fmech.npy, 218 Hz"),
               units="mm", meshes=None, static_pose=None, clips=[])
    for turn, (traj_id, yaw_deg, n) in chosen:
        idx = keys.index(traj_id)  # traj_indices 按排序后的轨迹序号
        env = flight_imitation(ref_path=str(REF), wpg_pattern_path=str(WPG), traj_indices=[traj_id],
                               randomize_start_step=False, terminal_com_dist=float("inf"))
        env.reset()
        task, phys = env.task, env.physics
        m, d = phys.model.ptr, phys.data.ptr
        walker = task._walker
        ref = task._ref_qpos                                # 根关节位姿（cm），已由 com2root 换算
        wing_joints = phys.bind(task._wing_joints)
        task._wbpg.reset(initial_phase=0.0)
        body_name = lambda b: mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, b) or ""
        vis = [g for g in range(m.ngeom) if m.geom_group[g] == 1 and m.geom_type[g] == mujoco.mjtGeom.mjGEOM_MESH]
        root_body = [b for b in range(m.nbody) if body_name(b).endswith("thorax")][0]
        part = lambda g: ("wing_left" if "wing_left" in body_name(m.geom_bodyid[g]) else
                          "wing_right" if "wing_right" in body_name(m.geom_bodyid[g]) else "static")

        # 起点平移到原点，并把初始水平速度方向旋到 +x（游戏里再按“背离威胁”方向旋转）
        v0 = ref[min(25, len(ref) - 1), :2] - ref[0, :2]
        a0 = -np.arctan2(v0[1], v0[0])
        Rz = np.array([[np.cos(a0), -np.sin(a0), 0], [np.sin(a0), np.cos(a0), 0], [0, 0, 1]])
        qz = np.array([np.cos(a0 / 2), 0, 0, np.sin(a0 / 2)])
        root_frames, wl, wr = [], [], []
        ref_wing = {}
        for t in range(len(ref)):
            walker.set_pose(phys, ref[t, :3], ref[t, 3:])
            wing_joints.qpos = task._wbpg.step(ctrl_freq=task._wbpg.base_beat_freq)
            mujoco.mj_kinematics(m, d)
            if out["meshes"] is None and t == 0:
                meshes, static = [], []
                pr, Rr = d.xpos[root_body].copy(), d.xmat[root_body].reshape(3, 3).copy()
                for g in vis:
                    mid = m.geom_dataid[g]
                    v = np.array(m.mesh_vert[m.mesh_vertadr[mid]:m.mesh_vertadr[mid] + m.mesh_vertnum[mid]], float)
                    f = np.array(m.mesh_face[m.mesh_faceadr[mid]:m.mesh_faceadr[mid] + m.mesh_facenum[mid]], np.int64)
                    sv, sf = simplify_mesh(v, f, bins=10 if len(v) > 2000 else 6)
                    rgba = m.mat_rgba[m.geom_matid[g]] if m.geom_matid[g] >= 0 else m.geom_rgba[g]
                    meshes.append(dict(name=mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, g).split("/")[-1], part=part(g),
                                       rgba=np.round(rgba, 3).tolist(), verts=b64(sv * CM2MM), faces=b64(sf)))
                    rp = rel_pose(pr, Rr, d.geom_xpos[g], d.geom_xmat[g].reshape(3, 3))
                    static.append(np.r_[rp[:3] * CM2MM, rp[3:]].round(5).tolist())
                out["meshes"], out["static_pose"] = meshes, static
            if not ref_wing:
                # 每个翅膀组选第一个网格作参考；组内其他网格相对参考网格的变换是固定的
                for side in ("wing_left", "wing_right"):
                    ref_wing[side] = next(i for i, g in enumerate(vis) if part(g) == side)
            if t % FRAME_EVERY:
                continue
            pr, Rr = d.xpos[root_body].copy(), d.xmat[root_body].reshape(3, 3).copy()
            pw = Rz @ pr
            qr = np.zeros(4); mujoco.mju_mulQuat(qr, qz, mat2quat(Rr.ravel()))
            root_frames.append(np.r_[pw * CM2MM, qr])
            for side, lst in (("wing_left", wl), ("wing_right", wr)):
                g = vis[ref_wing[side]]
                rp = rel_pose(pr, Rr, d.geom_xpos[g], d.geom_xmat[g].reshape(3, 3))
                lst.append(np.r_[rp[:3] * CM2MM, rp[3:]])
        root_frames = np.array(root_frames); root_frames[:, :3] -= root_frames[0, :3]
        out["clips"].append(dict(name=f"evasion_{traj_id:03d}", turn=turn, yaw_change_deg=round(yaw_deg, 1),
                                 dt=FRAME_EVERY * task.control_timestep, n_frames=len(root_frames),
                                 root=np.round(root_frames, 5).ravel().tolist(),
                                 wing_left=np.round(np.array(wl), 5).ravel().tolist(),
                                 wing_right=np.round(np.array(wr), 5).ravel().tolist()))
        sp = np.linalg.norm(np.diff(root_frames[:, :3], axis=0), axis=1).sum() / (len(root_frames) * FRAME_EVERY * task.control_timestep)
        print(f"{turn} 转：轨迹 {traj_id}，净偏航 {yaw_deg:+.0f}°，{len(root_frames)} 帧 × {FRAME_EVERY * task.control_timestep * 1000:.1f} ms，"
              f"平均速度 {sp:.0f} mm/s，终点位移 {np.round(root_frames[-1, :3], 1)} mm", flush=True)
        env.close()
    # 组内网格相对参考翅膀网格的固定变换：由 static_pose 推出（第 0 帧）
    outp = ROOT / "results" / "flight" / "flight_clips.json"
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(out, separators=(",", ":")))
    nv = sum(len(base64.b64decode(x["verts"])) // 12 for x in out["meshes"])
    print(f"网格 {len(out['meshes'])} 个，简化后 {nv} 顶点；写入 {outp}（{outp.stat().st_size / 1e6:.2f} MB）")


if __name__ == "__main__":
    main()
