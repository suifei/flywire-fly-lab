"""蘑菇体学习回路：从 FlyWire v783 取出来的真实接线。
  ORN（嗅觉感受神经元）→ ALPN（投射神经元）/ ALLN（触角叶局部神经元）→ KC（凯尼恩细胞）→ MBON（蘑菇体输出神经元）
  + DAN（多巴胺神经元 PAM / PPL1 / PPL2）+ APL（全局抑制）+ DPM
成员按注释表的 cell_class / cell_type 取，不按跳数裁；成员之间的**全部**连接都保留（与子回路同一口径）。
可选 extra：再并入别的神经元（比如子回路 v4 的 6,296 个，这样 MBON 的输出能一路走到转向 / 后退 / 伸喙）。
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dodge")); sys.path.insert(0, str(ROOT / "learn"))
import subcircuit as v1
from lif import P, Sim

MB_CLASSES = ["olfactory", "ALPN", "ALLN", "Kenyon_Cell", "MBON", "DAN"]
MB_TYPES = ["APL", "DPM"]


def load():
    ann = pd.read_csv(v1.PATH_ANN, sep="\t", low_memory=False, usecols=["root_id", "super_class", "cell_class", "cell_sub_class", "cell_type", "side", "top_nt"]).drop_duplicates("root_id").set_index("root_id")
    comp = pd.read_csv(v1.PATH_COMP, index_col=0); fids = comp.index.to_numpy(np.int64)
    con = pd.read_parquet(v1.PATH_CON, columns=["Presynaptic_Index", "Postsynaptic_Index", "Connectivity", "Excitatory x Connectivity"])
    return ann.reindex(fids), fids, con


class Circuit:
    def __init__(self, ann, fids, con, extra=(), sides=("left", "right", "center", "na"), drop_pairs=(), force_inhibitory=()):
        """drop_pairs: [(pre_tag, post_tag)] 要切掉的连接类别（做对照用），tag 同 self.tag。
        force_inhibitory: 这些 tag 的神经元发出的突触一律取负号（递质预测的纠正，见 mb_odor_coding.py）。"""
        cls = ann.cell_class.fillna("?").to_numpy(); typ = ann.cell_type.fillna("?").to_numpy(); side = ann.side.fillna("?").to_numpy()
        member = (np.isin(cls, MB_CLASSES) | np.isin(typ, MB_TYPES)) & np.isin(side, sides)
        member[np.asarray(list(extra), int)] = True
        sel = np.where(member)[0]; self.sel = sel; self.n = len(sel); loc = np.full(len(fids), -1); loc[sel] = np.arange(self.n); self.loc = loc
        self.cls, self.typ, self.side, self.fids = cls[sel], typ[sel], side[sel], fids[sel]
        self.tag = np.where(np.isin(self.typ, MB_TYPES), self.typ, np.where(np.isin(self.cls, MB_CLASSES), self.cls, "other"))
        pre, post = con.Presynaptic_Index.to_numpy(), con.Postsynaptic_Index.to_numpy(); e = (loc[pre] >= 0) & (loc[post] >= 0)
        pre, post = loc[pre[e]], loc[post[e]]; w = con["Excitatory x Connectivity"].to_numpy()[e].astype(np.float64) * P["w_syn"]; nsyn = con.Connectivity.to_numpy()[e]
        for a, b in drop_pairs:
            k = ~((self.tag[pre] == a) & (self.tag[post] == b)); pre, post, w, nsyn = pre[k], post[k], w[k], nsyn[k]
        for a in force_inhibitory: k = self.tag[pre] == a; w[k] = -np.abs(w[k])
        o = np.argsort(pre, kind="stable"); self.pre, self.post, self.w0, self.nsyn = pre[o], post[o], w[o], nsyn[o]
        self.indptr = np.searchsorted(self.pre, np.arange(self.n + 1))
        self.idx = {t: np.where(self.tag == t)[0] for t in np.unique(self.tag)}

    def of_type(self, types, side=None):
        m = np.isin(self.typ, types if isinstance(types, (list, tuple)) else [types])
        if side: m &= self.side == side
        return np.where(m)[0]

    def sim(self, seed=0):
        return Sim(self.n, self.indptr, self.post, self.w0.copy(), seed)

    def edges(self, pre_tag, post_tag):
        return np.where((self.tag[self.pre] == pre_tag) & (self.tag[self.post] == post_tag))[0]
