"""多巴胺门控的突触可塑性：只作用在 KC → MBON 突触上（文献里果蝇嗅觉记忆的位置）。

规则（三因子，Hige et al. 2015 Neuron；Cohn et al. 2015 Cell；Handler et al. 2019 Cell）：
  KC 最近放过电（资格迹 e_i，时间常数 tau_e）+ 同一个隔室里有多巴胺（D_j）→ 这条 KC_i → MBON_j 突触被**压低**：
      Δw_ij = −eta · e_i · D_j · w_ij          （乘性，权重不会变号）
  遗忘：w_ij 以时间常数 tau_forget 回到原值 w0_ij。
多巴胺到哪（norm="per_mbon"，第二版起的默认）：D_j = Σ_d n(d→j) · (DAN d 这一段的脉冲数) / Σ_d n(d→j)，
  即「接到 MBON j 上的那些多巴胺神经元，按突触数加权的平均发放」；n(d→j) 是连接组里 DAN d → MBON j 的突触数（只算 ≥3 个突触的边）。
  第一版（norm="global"）用全局常数归一，结果 PAM（307 个）给出的多巴胺是 PPL1（16 个）的二十多倍，PPL1 配对几乎学不动——见 mb_conditioning_v1.json。
也就是说「哪个多巴胺神经元管哪个隔室」**完全由连接组决定**，我们没有写 PAM→哪个 MBON 的表。
规则对 PAM 和 PPL1 一视同仁（都是压低）。文献里的「奖赏记忆 / 惩罚记忆」之分来自它们各自管的 MBON 往下接到哪——那也是连接组的事。
eta / tau_e / tau_forget 是手选参数（台账 PARAMETERS）。
"""
import numpy as np


class DopaminePlasticity:
    def __init__(self, circuit, sim, eta=0.003, tau_e_ms=200.0, tau_forget_s=0.0, norm="per_mbon"):
        c = circuit; self.sim = sim; self.eta = eta; self.tau_e = tau_e_ms; self.tau_f = tau_forget_s
        self.e_idx = c.edges("Kenyon_Cell", "MBON"); self.kc_of = c.pre[self.e_idx]; self.mbon_of = c.post[self.e_idx]; self.w0 = c.w0[self.e_idx].copy()
        d = c.edges("DAN", "MBON"); self.dan_pre = c.pre[d]; self.dan_post = c.post[d]; self.dan_n = c.nsyn[d].astype(float)
        if norm == "per_mbon": k = self.dan_n >= 3; self.dan_pre, self.dan_post, self.dan_n = self.dan_pre[k], self.dan_post[k], self.dan_n[k]
        tot = np.zeros(c.n); np.add.at(tot, self.dan_post, self.dan_n)
        self.n_ref = np.where(tot > 0, tot, 1.0) if norm == "per_mbon" else float(np.median(tot[tot > 0]))
        self.trace = np.zeros(c.n); self.D = np.zeros(c.n); self.n = c.n

    def step(self, counts, ms):
        """counts: 这一段（ms 毫秒）里每个神经元的脉冲数。在 sim.advance 之后调用。"""
        self.trace *= np.exp(-ms / self.tau_e); self.trace += counts
        self.D[:] = 0; np.add.at(self.D, self.dan_post, self.dan_n * counts[self.dan_pre]); self.D /= self.n_ref
        w = self.sim.w; we = w[self.e_idx]
        dep = self.eta * self.trace[self.kc_of] * self.D[self.mbon_of]
        if dep.any(): we = we * np.exp(-dep)
        if self.tau_f > 0: we = we + (self.w0 - we) * (1 - np.exp(-ms / 1000 / self.tau_f))
        w[self.e_idx] = we

    def strength(self):
        """每个 MBON 的 KC 输入还剩原来的多少（1 = 没学过）。"""
        cur = np.zeros(self.n); ori = np.zeros(self.n); np.add.at(cur, self.mbon_of, self.sim.w[self.e_idx]); np.add.at(ori, self.mbon_of, self.w0)
        return np.divide(cur, ori, out=np.ones(self.n), where=ori > 0)
