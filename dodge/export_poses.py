#!/usr/bin/env python
"""
梳理动画关键帧：在 FlyGym 1.2.1 NeuroMechFly（与步态帧同一模型、同一网格顺序）上做运动学逆解，
让两条前足尖分别落到同侧触角附近，生成 2 个关键帧，游戏里来回插值。

依据与手写部分：
  * 参照 flybody 梳理姿态数据集（figshare fly-grooming-poses，392 个姿态）中 “T1”（前足梳理）类型：前足抬到头部、足尖在触角处；
  * 目标点（手写）：关键帧 A = 同侧 Pedicel（触角第二节）上方 0.05 mm；关键帧 B = 同侧 Funiculus（触角第三节）；
  * 只改前腿 7 个关节（Coxa yaw/pitch/roll、Femur pitch/roll、Tibia、Tarsus1），其余关节保持中性；
    最小二乘拟合 + 关节角偏离中性的正则项（0.02），无碰撞检测。
输出 results/dodge/poses.json：{groom: [frameA, frameB]}，每帧 = 69 个网格 × [x,y,z,qw,qx,qy,qz]（相对胸部水平位置，mm）
用法（fba 环境）：python dodge/export_poses.py
"""
import json
from pathlib import Path

import mujoco
import numpy as np
from scipy.optimize import least_squares

import flygym

ROOT = Path(__file__).resolve().parent.parent


def main():
    fly = flygym.Fly(enable_adhesion=False, init_pose="stretch", control="position", actuated_joints=flygym.preprogrammed.all_leg_dofs)
    sim = flygym.SingleFlySimulation(fly=fly, arena=flygym.arena.Tethered(), timestep=1e-4)
    sim.reset()
    m, d = sim.physics.model.ptr, sim.physics.data.ptr
    name = lambda t, i: mujoco.mj_id2name(m, t, i) or ""
    jid = {name(mujoco.mjtObj.mjOBJ_JOINT, i).split("/")[-1]: i for i in range(m.njnt)}
    bid = {name(mujoco.mjtObj.mjOBJ_BODY, i).split("/")[-1]: i for i in range(m.nbody)}
    mesh_geoms = [g for g in range(m.ngeom) if m.geom_type[g] == mujoco.mjtGeom.mjGEOM_MESH]
    q0 = d.qpos.copy()
    mujoco.mj_kinematics(m, d)
    thorax = d.xpos[bid["Thorax"]].copy()

    def solve(leg, side, target):
        js = [f"joint_{leg}Coxa_yaw", f"joint_{leg}Coxa", f"joint_{leg}Coxa_roll", f"joint_{leg}Femur", f"joint_{leg}Femur_roll", f"joint_{leg}Tibia", f"joint_{leg}Tarsus1"]
        adr = [m.jnt_qposadr[jid[j]] for j in js]
        x0 = q0[adr].copy()
        def resid(x):
            d.qpos[:] = q_cur; d.qpos[adr] = x
            mujoco.mj_kinematics(m, d)
            return np.r_[d.xpos[bid[f"{leg}Tarsus5"]] - target, 0.02 * (x - x0)]
        r = least_squares(resid, x0, bounds=(x0 - 2.5, x0 + 2.5))
        return adr, r.x, float(np.linalg.norm(resid(r.x)[:3]))

    frames, errs = [], []
    for key, (tgt_body, dz) in {"A": ("Pedicel", 0.05), "B": ("Funiculus", 0.0)}.items():
        q_cur = q0.copy()
        mujoco.mj_kinematics(m, d)
        targets = {side: d.xpos[bid[f"{side}{tgt_body}"]].copy() + [0, 0, dz] for side in ("L", "R")}
        for leg, side in (("LF", "L"), ("RF", "R")):
            adr, x, err = solve(leg, side, targets[side])
            q_cur[adr] = x; errs.append((key, leg, round(err, 3)))
        d.qpos[:] = q_cur; mujoco.mj_kinematics(m, d)
        q = np.zeros(4); pose = []
        for g in mesh_geoms:
            mujoco.mju_mat2Quat(q, d.geom_xmat[g])
            p = d.geom_xpos[g] - [thorax[0], thorax[1], 0]
            pose.extend(np.round(p, 4).tolist() + np.round(q, 4).tolist())
        frames.append(pose)
    out = ROOT / "results" / "dodge" / "poses.json"
    out.write_text(json.dumps({"groom": frames, "n_meshes": len(mesh_geoms),
                               "note": "IK: front tarsus tips to ipsilateral Pedicel (A) / Funiculus (B); flygym 1.2.1 NeuroMechFly"}))
    print("足尖到目标的残差（mm）：", errs, "；网格数", len(mesh_geoms), "；写入", out)
    sim.close()


if __name__ == "__main__":
    main()
