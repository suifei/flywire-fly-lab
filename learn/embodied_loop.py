#!/usr/bin/env python
"""闭环：连接组大脑（v5，15,055 个神经元，带多巴胺可塑性）↔ 物理仿真的身体（FlyGym 2.1 / NeuroMechFly v2，MuJoCo，六条腿带关节和地面接触）。

每 15 ms 同步一次（和 connectome_vision_loop.py、Eon 的做法一样）：
  身体 → 大脑：果蝇在哪、朝哪（来自物理仿真）→ 两根触角处的气味浓度、脚下有没有糖、周围热不热 → 对应感受神经元的泊松频率
  大脑 → 身体：下行神经元的发放 → HybridTurningController 的 [左, 右] 驱动 → 42 个关节的目标角 → MuJoCo
  身体的事件 → 多巴胺：吃到糖 → PAM 30 Hz；待在热区 → PPL1 30 Hz（**这根线是手接的**，连接组自己叫不起多巴胺神经元，见 reinforcement_route.py）
和页面上「生活」模式的区别：这里的身体是真的物理仿真（腿会打滑、身体会晃），不是运动学；代价是慢，只能离线跑。
手写的部分（如实列出）：气味 / 热的空间分布（高斯）；DN → 驱动的映射（转向 = DNa 左右差，和游戏同号；基础前进驱动是常数——这个模型没有自发活动）；
  MN9 超过阈值且脚下有糖 → 停下来吃；腿的节律和协调来自 FlyGym 的 CPG + 预录步态（腹神经索连接组给不出三足步态，report §12）。

世界：原点出发。两块气味区（A、B，各 20 个互不重合的嗅小球）；A 区中心有糖，B 区中心是热源。
沿 x 方向依次是四条气味带（只随 x 变，高斯，σ = 8 mm）：A（带糖）→ B（带热）→ A（什么都不带）→ B（什么都不带）。它基本只会往前走，所以用带状。
判据（跑之前写死；对照 = --no-reinforcement，同一个种子，别的都一样）：
  E1 在身体里学到了：跑完之后单独测，PAM 隔室对 A 的响应、PPL1 隔室对 B 的响应，各自比对照低 ≥30%
  E2 没学串：PAM 隔室对 B、PPL1 隔室对 A 的响应，与对照相差 <30%
  E3 闭环是真的：把大脑给的转向指令（DNa 左右差）换成 0（--open-loop-turn），走出来的轨迹应当不同——只报告终点差，不设阈值
用法：conda activate flygym && python learn/embodied_loop.py --seconds 45 [--no-reinforcement] [--seed 1]
输出 results/learn/embodied_<tag>.json（轨迹、每个窗口的感觉 / 读出 / 多巴胺、训练前后 MBON 对 A / B 的响应）
"""
import argparse, json, sys, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from v5_circuit import V5
from plasticity import DopaminePlasticity
from mb_circuit import ROOT


def build_body(video=False, bands=()):
    from flygym import Simulation
    from flygym.anatomy import BodySegment, ContactBodiesPreset
    from flygym.compose import FlatGroundWorld
    from flygym.utils.math import Rotation3D
    from flygym_demo.complex_terrain import (HybridTurningController, HybridControllerObservation, LocomotionAction, PreprogrammedSteps, apply_locomotion_action, make_locomotion_fly)
    fly = make_locomotion_fly(name="fly", add_adhesion=True, colorize=bool(video)); world = FlatGroundWorld(); cam = None
    if video:                       # 录像：跟拍相机 + 地上的色带（只是给人看的标记，不碰撞；果蝇没有接视觉）
        from flygym.utils.mjcf import GEOM_TYPES
        cam = fly.add_tracking_camera(name="topcam", pos_offset=(0.0, -24.0, 20.0), rotation=Rotation3D("euler", (0.85, 0.0, 0.0)), fovy=45.0)
        tex = next(t for t in world.mjcf_root.textures if t.name == "checker"); tex.rgb1, tex.rgb2 = [0.85, 0.85, 0.85], [0.95, 0.95, 0.95]
        COL = {"A": (0.92, 0.47, 0.67, 0.55), "B": (0.35, 0.27, 0.63, 0.55)}
        for bx, od, what in bands:
            world.mjcf_root.worldbody.add_geom(type=GEOM_TYPES["box"], pos=(bx, 0, 0.01), size=(8, 60, 0.01), rgba=COL[od], contype=0, conaffinity=0)
            if what: world.mjcf_root.worldbody.add_geom(type=GEOM_TYPES["box"], pos=(bx, 0, 0.03), size=(3, 60, 0.01), rgba=(0.81, 0.47, 0.16, 0.9) if what == "sugar" else (0.89, 0.29, 0.2, 0.9), contype=0, conaffinity=0)
    world.add_fly(fly, [0, 0, 0.8], Rotation3D("quat", [1, 0, 0, 0]), bodysegs_with_ground_contact=ContactBodiesPreset.TIBIA_TARSUS_ONLY, add_ground_contact_sensors=False)
    sim = Simulation(world)
    if video: sim.set_renderer([cam], camera_res=(640, 480), playback_speed=0.5, output_fps=25)
    steps = PreprogrammedSteps(); order = fly.get_actuated_jointdofs_order("position")
    ctrl = HybridTurningController(timestep=sim.timestep, preprogrammed_steps=steps, output_dof_order=order); sim.reset(); ctrl.reset(seed=0)
    apply_locomotion_action(sim, fly.name, LocomotionAction(joint_angles=steps.default_pose_by_dof_order(order), adhesion_onoff=np.ones(6, bool))); sim.warmup()
    th = fly.get_bodysegs_order().index(BodySegment("c_thorax"))
    def step(drive, n):
        for _ in range(n):
            apply_locomotion_action(sim, fly.name, ctrl.step(drive, HybridControllerObservation.from_sim(sim, fly.name))); sim.step()
            if video: sim.render_as_needed()
    def pose():
        p = sim.get_body_positions(fly.name)[th]; q = sim.get_body_rotations(fly.name)[th] if hasattr(sim, "get_body_rotations") else None
        return np.array(p[:2], float), q
    return sim, step, pose


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--seconds", type=float, default=20); ap.add_argument("--window_ms", type=float, default=15.0); ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--no-learning", action="store_true"); ap.add_argument("--turn_gain", type=float, default=0.02); ap.add_argument("--tag", default=None); ap.add_argument("--probe-body", action="store_true"); ap.add_argument("--no-reinforcement", action="store_true"); ap.add_argument("--open-loop-turn", action="store_true")
    ap.add_argument("--video", action="store_true", help="录像（必须前台跑：macOS 会把后台的 OpenGL 渲染限到 10% CPU）")
    a = ap.parse_args(); t0 = time.time(); BANDS = [(40, "A", "sugar"), (90, "B", "heat"), (140, "A", None), (190, "B", None)]; sim, body_step, pose = build_body(a.video, BANDS); print(f"身体就绪 {time.time() - t0:.1f}s，物理步长 {sim.timestep * 1000:.2f} ms", flush=True)
    if a.probe_body:
        t1 = time.time(); p0, _ = pose(); body_step(np.array([1.0, 1.0]), int(0.3 / sim.timestep)); p1, q = pose(); print(f"0.3 s 直行：{time.time() - t1:.1f}s 墙钟，位移 {np.round(p1 - p0, 2)} mm，朝向四元数 {q}"); return
    c = V5(); s = c.sim(a.seed); pl = DopaminePlasticity(c, s, eta=0.003); gl = sorted(c.glomeruli); perm = np.random.default_rng(4242).permutation(gl).tolist(); OD = {"A": perm[:20], "B": perm[20:40]}
    side = {sd: {k: np.concatenate([c.glomeruli[g][c.side[c.glomeruli[g]] == sd] for g in v]) for k, v in OD.items()} for sd in ("left", "right")}
    grp = lambda name: np.array(c.groups[name + "_left"] + c.groups[name + "_right"]); G = {k: grp(k) for k in ("PAM", "PPL1", "SUGAR", "THERMO")}
    ro = {k: np.array(c.groups[k]) for k in ("DNa01_left", "DNa01_right", "DNa02_left", "DNa02_right", "DNp01_left", "DNp01_right", "MN9_left", "MN9_right", "MDN_left", "MDN_right")}
    mbon = c.idx["MBON"]; d = c.edges("DAN", "MBON"); d = d[c.nsyn[d] >= 3]; tot = np.zeros(c.n); np.add.at(tot, c.post[d], c.nsyn[d]); comp = {}
    for k in ("PAM", "PPL1"): part = np.zeros(c.n); m = np.isin(c.pre[d], G[k]); np.add.at(part, c.post[d][m], c.nsyn[d][m]); comp[k] = np.divide(part, tot, out=np.zeros(c.n), where=tot > 0)[mbon]
    def probe():                     # 单独测：同一份权重，另开一个仿真器，可塑性关着
        out = {}
        for k, gs in OD.items():
            q = c.sim(99); q.w[:] = s.w; r = np.zeros(c.n)
            for g in gs: r[c.glomeruli[g]] = 200
            q.advance(100, r); hz = q.advance(1000, r).astype(float); out[k] = {cl: float((comp[cl] * hz[mbon]).sum()) for cl in comp} | {"total": float(hz[mbon].sum())}
        return out
    before = probe(); print("训练前 MBON 响应：", before, flush=True)
    SIG = 8.0; sugar_left = {0: 2.0}   # 第 0 条带里的糖够吃 2 秒
    n_win = int(a.seconds * 1000 / a.window_ms); phys = int(round(a.window_ms / 1000 / sim.timestep)); ema = {k: 0.0 for k in ro}; log = []; tb = tp = 0.0; eat_s = 0.0
    for w in range(n_win):
        t = w * a.window_ms / 1000; (x, y), q = pose(); yaw = float(np.arctan2(2 * (q[0] * q[3] + q[1] * q[2]), 1 - 2 * (q[2] ** 2 + q[3] ** 2)))
        ant = {sd: (x + 1.0 * np.cos(yaw) - sg * 0.3 * np.sin(yaw)) for sd, sg in (("left", 1), ("right", -1))}   # 触角的 x 坐标（气味只随 x 变）
        r = np.zeros(c.n); conc = {"A": 0.0, "B": 0.0}; sugar = heat = 0.0
        for bi, (bx, od, what) in enumerate(BANDS):
            for sd in ("left", "right"):
                cc = float(np.exp(-(ant[sd] - bx) ** 2 / (2 * SIG ** 2))); r[side[sd][od]] = np.maximum(r[side[sd][od]], 200 * cc); conc[od] = max(conc[od], cc)
            here = float(np.exp(-(x - bx) ** 2 / (2 * SIG ** 2)))
            if what == "sugar" and sugar_left.get(bi, 0) > 0 and abs(x - bx) < 3: sugar = 1.0; cur = bi
            if what == "heat": heat = max(heat, here)
        r[G["SUGAR"]] = 150 * sugar; r[G["THERMO"]] = 150 * heat
        eating = sugar > 0 and (ema["MN9_left"] + ema["MN9_right"]) / 2 > 10
        da = {"PAM": bool(eating), "PPL1": bool(heat > 0.5)}
        if not a.no_reinforcement:
            for k in da:
                if da[k]: r[G[k]] = 30
        t1 = time.time(); cnt = s.advance(a.window_ms, r); tb += time.time() - t1
        if not a.no_learning: pl.step(cnt, a.window_ms)
        for k, idx in ro.items(): ema[k] += (a.window_ms / (50 + a.window_ms)) * (cnt[idx].mean() / (a.window_ms / 1000) - ema[k])
        turn = 0.0 if a.open_loop_turn else float(np.clip(a.turn_gain * ((ema["DNa01_left"] + ema["DNa02_left"]) - (ema["DNa01_right"] + ema["DNa02_right"])), -0.8, 0.8))
        fwd = 0.0 if eating else 1.0; drive = np.array([fwd - turn, fwd + turn])     # 左 DNa 强 → 左转 = 右侧驱动更大
        if eating: sugar_left[cur] -= a.window_ms / 1000; eat_s += a.window_ms / 1000
        t1 = time.time(); body_step(drive, phys); tp += time.time() - t1
        log.append(dict(t=round(t, 3), x=float(x), y=float(y), yaw=yaw, concA=conc["A"], concB=conc["B"], sugar=sugar, heat=heat, eating=bool(eating), pam=da["PAM"] and not a.no_reinforcement, ppl1=da["PPL1"] and not a.no_reinforcement,
                        turn=turn, mbon_hz=float(cnt[mbon].sum() / (a.window_ms / 1000)), kc_active=int((cnt[c.idx["Kenyon_Cell"]] > 0).sum()), **{k: round(v, 2) for k, v in ema.items()}))
        if w % 200 == 0: print(f"t={t:5.1f}s x={x:6.1f} y={y:5.1f} yaw={np.degrees(yaw):5.0f}° A={conc['A']:.2f} B={conc['B']:.2f} 吃={eating} 热={heat:.2f} MBON={log[-1]['mbon_hz']:.0f}Hz turn={turn:+.2f} [脑 {tb:.0f}s 身 {tp:.0f}s]", flush=True)
    after = probe(); st = pl.strength()[mbon]; print("训练后 MBON 响应：", after)
    tag = a.tag or ("noreinf" if a.no_reinforcement else "openloop" if a.open_loop_turn else "nolearn" if a.no_learning else "main") + f"_s{a.seed}"
    out = dict(tag=tag, seconds=a.seconds, window_ms=a.window_ms, seed=a.seed, reinforcement=not a.no_reinforcement, learning=not a.no_learning, open_loop_turn=a.open_loop_turn, bands=BANDS, before=before, after=after,
               eat_seconds=eat_s, ppl1_seconds=float(sum(l["ppl1"] for l in log) * a.window_ms / 1000), end=[log[-1]["x"], log[-1]["y"]], path_mm=float(sum(np.hypot(log[i + 1]["x"] - log[i]["x"], log[i + 1]["y"] - log[i]["y"]) for i in range(len(log) - 1))),
               n_mbon_depressed=int((st < 0.9).sum()), wall_brain_s=tb, wall_body_s=tp, log=log[::4])
    if a.video: sim.renderer.save_video(ROOT / f"results/learn/embodied_{tag}.mp4"); print("→", ROOT / f"results/learn/embodied_{tag}.mp4")
    json.dump(out, open(ROOT / f"results/learn/embodied_{tag}.json", "w"), ensure_ascii=False); print(f"完成：走了 {out['path_mm']:.0f} mm，终点 {np.round(out['end'], 1)}，吃了 {eat_s:.1f}s，PPL1 {out['ppl1_seconds']:.1f}s；大脑 {tb:.0f}s + 身体 {tp:.0f}s 墙钟")


if __name__ == "__main__": main()
