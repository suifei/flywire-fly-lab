#!/usr/bin/env python
"""
腹神经索发放率模型：在本机调用 Pugliese et al. 2025（bioRxiv，“Connectome simulations identify a central pattern
generator circuit for fly walking”）作者代码 github.com/smpuglie/Pugliese_cpg_2025 @ faee4b0。
该仓库没有许可证：只 import 调用，不复制其代码进交付物。

模型（作者代码与默认参数，未改）：τ·dr/dt = −r + max(0, r_max·tanh(a/r_max·(W·r + I − θ)))，
τ、a、θ、r_max 每个神经元按作者默认分布抽样（每个“副本”一组，θ 与 a 按神经元大小缩放）；
权重 = 突触数 × 递质符号 × 0.03；Dopri5 自适应步长；T = 2 s，1 ms 输出；刺激电流 20–1999 ms。
网络：作者发布的 MANC T1（前足神经节）DN→MN 网络，4,604 个神经元，含前足运动神经元 144 个（左右各 72）。

条件（事先定）：
  none        无刺激
  DNg100_L    左 DNg100（索引 31），I = 250 —— 作者默认实验
  DNg100_LR   双侧 DNg100（31, 132），I = 250
  MDN         4 个 MDN，I = 250（后退相关）
  DNa02_L     左 DNa02（bodyId 10126），I = 300 —— 作者教程示例 3（转向）
  MDN_I100 / MDN_I150  事后追加：MDN 在 I = 250 下无节律，检查更弱刺激（8 个副本）
节律判据用作者的 neuron_oscillation_score / compute_oscillation_score：丢弃前 230 ms，活跃 = 最大发放率 > 0.01，
网络得分 = 活跃运动神经元得分均值，≥ 0.5 记为“振荡”（作者 oscillation_threshold）。频率单位换算成 Hz。
输出：results/vnc/pugliese/<条件>.npz（运动神经元发放率 float16）、mn_table.csv、summary.json
用法（vnc-sim 环境）：python vnc/run_pugliese.py --reps 16 [--conds DNg100_L,none] [--rtol 2e-6 --atol 5e-9]
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
PUG = ROOT / "external" / "Pugliese_cpg_2025"
sys.path.insert(0, str(PUG))

import jax  # noqa: E402
import jax.numpy as jnp  # noqa: E402
from omegaconf import OmegaConf  # noqa: E402
from src.simulation.vnc_sim import prepare_neuron_params, prepare_sim_params, run_single_simulation, reweight_connectivity  # noqa: E402
from src.utils.sim_utils import load_wTable, neuron_oscillation_score  # noqa: E402

OUT = ROOT / "results" / "vnc" / "pugliese"
CLIP = 230
EXP_YAML = PUG / "configs/experiment/DNg100_Stim.yaml"


def make_cfg(reps, stim_neurons, stim_i, rtol, atol):
    load = lambda p: OmegaConf.to_container(OmegaConf.load(p))
    cfg = OmegaConf.create({"paths": {"data_dir": str(PUG / "data")}, "experiment": load(EXP_YAML),
                            "neuron_params": load(PUG / "configs/neuron_params/default.yaml"), "sim": load(PUG / "configs/sim/default.yaml")})
    cfg.experiment.n_replicates = reps
    cfg.experiment.stimNeurons = [list(map(int, stim_neurons))]
    cfg.experiment.stimI = [list(map(float, stim_i))]
    cfg.sim.rtol, cfg.sim.atol = rtol, atol
    return cfg


def conditions(wt):
    mdn = wt.index[wt["type"] == "MDN"].tolist()
    # MDN_I100 / MDN_I150：MDN 在 I = 250 下没有节律之后追加的剂量检查（8 个副本，判据不变）
    return {"none": ([31], [0.0]), "DNg100_L": ([31], [250.0]), "DNg100_LR": ([31, 132], [250.0, 250.0]),
            "MDN": (mdn, [250.0] * len(mdn)), "DNa02_L": (wt.index[wt["bodyId"] == 10126].tolist(), [300.0]),
            "MDN_I100": (mdn, [100.0] * len(mdn)), "MDN_I150": (mdn, [150.0] * len(mdn))}


score_all = jax.jit(jax.vmap(neuron_oscillation_score, in_axes=(0, None)))


def run_condition(name, wt, stim, reps, rtol, atol):
    cfg = make_cfg(reps, *stim, rtol, atol)
    npar = prepare_neuron_params(cfg, wt)
    N = npar.W.shape[0]
    spar = prepare_sim_params(cfg, 1, N)
    mn = np.where(wt["class"].to_numpy() == "motor neuron")[0]
    dt = float(cfg.sim.dt)
    R_mn, reps_out = [], []
    for rep in range(reps):
        t0 = time.time()
        Wr = reweight_connectivity(npar.W * npar.W_mask[rep], spar.exc_multiplier, spar.inh_multiplier)
        R = run_single_simulation(Wr, npar.tau[rep], npar.a[rep], npar.threshold[rep], npar.fr_cap[rep],
                                  npar.input_currents[0, rep], spar.noise_stdv, spar.t_axis, spar.T, spar.dt,
                                  spar.pulse_start, spar.pulse_end, spar.r_tol, spar.a_tol, jax.random.PRNGKey(rep))
        R = np.asarray(R)
        Rm = R[mn]
        act = Rm[:, CLIP:].max(axis=1) > 0.01
        sc, fr = score_all(jnp.asarray(Rm[:, CLIP:]), 0.05)
        sc, fr = np.asarray(sc), np.asarray(fr) / dt
        net = float(sc[act].mean()) if act.any() else 0.0
        reps_out.append(dict(rep=rep, sim_s=round(time.time() - t0, 1), n_active_all_1hz=int((R[:, CLIP:].max(axis=1) > 1).sum()),
                             n_active_mn=int(act.sum()), n_active_mn_1hz=int((Rm[:, CLIP:].max(axis=1) > 1).sum()),
                             net_score=round(net, 3), oscillating=bool(net >= 0.5),
                             mean_freq_hz=round(float(np.nanmean(np.where(act & (fr > 0), fr, np.nan))), 2) if (act & (fr > 0)).any() else None,
                             stim_rate_hz=[round(float(R[i, CLIP:].mean()), 1) for i in stim[0]],
                             mn_score=sc.round(3).tolist(), mn_freq_hz=np.where(act, fr, 0).round(2).tolist()))
        R_mn.append(Rm.astype(np.float16))
        print(f"  {name} 副本 {rep}: {reps_out[-1]['sim_s']} s，活跃 MN {reps_out[-1]['n_active_mn_1hz']}（>1 Hz），"
              f"网络振荡得分 {net:.2f}，频率 {reps_out[-1]['mean_freq_hz']} Hz，刺激神经元 {reps_out[-1]['stim_rate_hz']} Hz", flush=True)
    np.savez_compressed(OUT / f"{name}.npz", R_mn=np.stack(R_mn), t=np.asarray(spar.t_axis), mn_index=mn)
    return reps_out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=16)
    ap.add_argument("--conds", default="none,DNg100_L,DNg100_LR,MDN,DNa02_L")
    ap.add_argument("--rtol", type=float, default=2e-6)
    ap.add_argument("--atol", type=float, default=5e-9)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    cfg0 = make_cfg(1, [31], [0.0], a.rtol, a.atol)
    wt = load_wTable(cfg0.experiment.dfPath)
    wt[wt["class"] == "motor neuron"][["bodyId", "type", "somaSide", "motor module", "step contribution"]].to_csv(OUT / "mn_table.csv")
    conds = conditions(wt)
    path = OUT / f"summary{a.tag}.json"
    summary = json.loads(path.read_text()) if path.exists() else {}
    for name in a.conds.split(","):
        t0 = time.time()
        reps = run_condition(name + a.tag, wt, conds[name], a.reps, a.rtol, a.atol)
        summary[name + a.tag] = dict(stim_index=conds[name][0], stim_I=conds[name][1], reps=len(reps), rtol=a.rtol, atol=a.atol,
                                     frac_oscillating=round(np.mean([r["oscillating"] for r in reps]), 3),
                                     median_net_score=round(float(np.median([r["net_score"] for r in reps])), 3),
                                     median_freq_hz=(round(float(np.median([r["mean_freq_hz"] for r in reps if r["mean_freq_hz"]])), 2)
                                                     if any(r["mean_freq_hz"] for r in reps) else None),
                                     wall_s=round(time.time() - t0, 1), runs=reps)
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=1))
        s = summary[name + a.tag]
        print(f"{name}{a.tag}: 振荡副本比例 {s['frac_oscillating']}，得分中位 {s['median_net_score']}，频率中位 {s['median_freq_hz']} Hz，用时 {s['wall_s']} s", flush=True)


if __name__ == "__main__":
    main()
