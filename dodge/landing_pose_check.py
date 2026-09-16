#!/usr/bin/env python
"""量出逃逸飞行轨迹末帧的姿态与机体最低点——报告 25.1 节那个「屁股插进地面」bug 的原始测量。

背景：用户反馈「每次都是屁股插入到地面里面去了」。这个脚本把当时在 node 里临时量的数字固化下来，
因为 2026-09-16 的数字核对发现它没有任何结果文件支撑（审计第 12 项）。

做法：把 85 个 mesh 的顶点按 `static_pose`（每个 mesh 相对机体的位姿）摆好，
再按轨迹**末帧**的机体四元数旋转，平移到**降落结束时游戏给的位置**（`clipPose` 在 landU = 1 时把 z 设为 0），
取全部顶点的最低 z——这正是修复前玩家在最后一帧看到的几何。
顶点在 JSON 里是 base64 打包的 float32（`flight/export_flight.py:b64`）。
页面把果蝇放大 2 倍显示（`FLY_SCALE = 2`），所以按放大后算——这正是玩家看到的几何。
负的最低点 = 插进地面。
输出 results/flight/landing_pose_check.json
用法：python dodge/landing_pose_check.py
"""
import base64
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
FLY_SCALE = 2          # 与 dodge/fly_dodge.template.html 的 FLY_SCALE 一致


def qmat(w, x, y, z):                     # MuJoCo 四元数 (w,x,y,z) → 旋转矩阵
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def main():
    d = json.loads((ROOT / "results/flight/flight_clips.json").read_text())
    static = d["static_pose"]                                   # 85 × (x,y,z,qw,qx,qy,qz)
    body = []                                                   # 机体坐标系下的全部顶点
    for mesh, sp in zip(d["meshes"], static):
        v = np.frombuffer(base64.b64decode(mesh["verts"]), np.float32).reshape(-1, 3).astype(float)
        body.append((qmat(*sp[3:7]) @ v.T).T + np.asarray(sp[:3], float))
    body = np.vstack(body) * FLY_SCALE
    print(f"机体顶点 {len(body)} 个（{len(d['meshes'])} 个 mesh，已放大 {FLY_SCALE} 倍）\n")

    rows = []
    for c in d["clips"]:
        root = np.asarray(c["root"], float).reshape(c["n_frames"], 7)
        q = root[-1, 3:7]
        pos = np.array([0.0, 0.0, 0.0])      # clipPose 在降落结束（landU = 1）时 z = 0
        R = qmat(*q)
        fwd, up = R @ np.array([1.0, 0, 0]), R @ np.array([0, 0, 1.0])
        world = (R @ body.T).T + pos
        lo = float(world[:, 2].min())
        row = dict(clip=c["name"], n_frames=int(c["n_frames"]),
                   final_pitch_deg=round(math.degrees(math.asin(np.clip(fwd[2], -1, 1))), 1),
                   final_roll_deg=round(math.degrees(math.atan2((R @ np.array([0, 1.0, 0]))[2], up[2])), 1),
                   clip_end_root_z_mm=round(float(root[-1, 2]), 3),
                   body_min_z_mm=round(lo, 3), below_ground_mm=round(max(0.0, -lo), 3))
        rows.append(row)
        print(f"{row['clip']:22s} 末帧俯仰 {row['final_pitch_deg']:+6.1f}°  翻滚 {row['final_roll_deg']:+6.1f}°  "
              f"机体最低点 {row['body_min_z_mm']:+7.2f} mm  → 插入地面 {row['below_ground_mm']:.2f} mm")
    out = dict(note="轨迹末帧（修复前的落地姿态）。机体顶点 = 85 个 mesh 按 static_pose 摆好 × FLY_SCALE(2)，"
                    "再按末帧四元数旋转平移。below_ground_mm > 0 表示机体插进地面——这就是 25.1 节要修的 bug。"
                    "修复后页面在降落进度上把姿态球面插值回水平，并按当前姿态的包围盒最低点抬升，所以实际渲染不会插进地面。",
               fly_scale=FLY_SCALE, n_body_verts=int(len(body)), clips=rows)
    dst = ROOT / "results/flight/landing_pose_check.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("\n写入", dst)


if __name__ == "__main__":
    main()
