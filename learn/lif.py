"""LIF 仿真核（numba）。方程、参数、每步顺序与 dodge/subcircuit.py / dodge/brain.js 完全一致（Shiu et al. 2024）：
  状态更新 → 阈值 → 突触到达 / Poisson → 重置；延迟 1.8 ms；被刺激神经元不应期 0。
与 subcircuit.py 的区别只有两点：① 可以分段推进（每段之间换刺激频率、改权重——可塑性要用）；② 快（numba）。
"""
import numpy as np
from numba import njit

P = dict(dt=0.1, v0=-52.0, vrst=-52.0, vth=-45.0, t_mbr=20.0, tau=5.0, t_rfc=2.2, t_dly=1.8, w_syn=0.275, f_poi=250)


@njit(cache=True)
def _advance(steps, step0, v, g, last, ring, indptr, post, w, p_stim, rfc, counts, a, b, c, v0, vth, vrst, kick, fired_buf):
    n = v.shape[0]; D = ring.shape[0]; total = 0
    for s in range(step0, step0 + steps):
        nf = 0
        for i in range(n):
            if s - last[i] >= rfc[i]:
                v[i] = v0 + (v[i] - v0) * a + g[i] * c
                g[i] *= b
                if v[i] > vth:
                    fired_buf[nf] = i; nf += 1
        slot = s % D
        for i in range(n):
            if ring[slot, i] != 0.0:
                g[i] += ring[slot, i]; ring[slot, i] = 0.0
        for i in range(n):
            if p_stim[i] > 0.0 and np.random.random() < p_stim[i]:
                v[i] += kick
        for k in range(nf):
            i = fired_buf[k]; counts[i] += 1
            for e in range(indptr[i], indptr[i + 1]):
                ring[slot, post[e]] += w[e]
            v[i] = vrst; g[i] = 0.0; last[i] = s
        total += nf
    return total


@njit(cache=True)
def _seed(x):
    np.random.seed(x)


class Sim:
    """n 个神经元；indptr/post/w 是按突触前排序的 CSR（w 单位 mV，已乘 w_syn）。w 可以在两段之间原地修改。"""

    def __init__(self, n, indptr, post, w, seed=0):
        dt = P["dt"]; self.n = n; self.indptr = indptr.astype(np.int64); self.post = post.astype(np.int64); self.w = w.astype(np.float64)
        self.a = np.exp(-dt / P["t_mbr"]); self.b = np.exp(-dt / P["tau"]); self.c = P["tau"] / (P["tau"] - P["t_mbr"]) * (self.b - self.a)
        self.D = int(round(P["t_dly"] / dt)); self.rfc0 = int(round(P["t_rfc"] / dt)); self.kick = P["w_syn"] * P["f_poi"]
        self.fired_buf = np.zeros(n, np.int64); _seed(seed); self.reset()
        self.always0 = np.zeros(n, bool)   # 这些神经元不应期恒为 0（brain.js 对「输入组」里的神经元就是这么做的，不管当下有没有被驱动）

    def reset(self):
        self.v = np.full(self.n, P["v0"]); self.g = np.zeros(self.n); self.last = np.full(self.n, -10**9, np.int64)
        self.ring = np.zeros((self.D, self.n)); self.step = 0

    def advance(self, ms, rates_hz=None):
        """推进 ms 毫秒。rates_hz: 长度 n 的数组（Hz，0 = 不刺激）。返回这一段里每个神经元的脉冲数。"""
        steps = int(round(ms / P["dt"])); counts = np.zeros(self.n, np.int64)
        p = np.zeros(self.n) if rates_hz is None else np.asarray(rates_hz, float) * P["dt"] / 1000
        rfc = np.where((p > 0) | self.always0, 0, self.rfc0).astype(np.int64)
        _advance(steps, self.step, self.v, self.g, self.last, self.ring, self.indptr, self.post, self.w, p, rfc, counts,
                 self.a, self.b, self.c, P["v0"], P["vth"], P["vrst"], self.kick, self.fired_buf)
        self.step += steps; return counts
