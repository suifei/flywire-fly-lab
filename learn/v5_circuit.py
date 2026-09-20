"""把导出给页面的 results/dodge/subcircuit_v5.json 读回来，包成和 mb_circuit.Circuit 同样的接口——
这样 Python 这边验的就是页面真正在跑的那一份（≥2 突触的裁剪、ALLN 抑制性都已经在里面）。"""
import base64, json
import numpy as np
from lif import P, Sim
from mb_circuit import ROOT
NAME = {"KC": "Kenyon_Cell", "ORN": "olfactory"}


class V5:
    def __init__(self, path=None):
        d = json.load(open(path or ROOT / "results/dodge/subcircuit_v5.json")); self.meta = d["meta"]; self.n = d["meta"]["n"]; self.groups = d["groups"]
        dec = lambda k, t: np.frombuffer(base64.b64decode(d[k]), t)
        self.indptr = dec("indptr", np.int32).astype(np.int64); self.post = dec("post", np.int32).astype(np.int64); self.w0 = dec("w", np.float32).astype(np.float64)
        self.pre = np.repeat(np.arange(self.n), np.diff(self.indptr)); self.nsyn = np.round(np.abs(self.w0) / P["w_syn"]).astype(int)
        self.typ = np.array(d["types"]); self.side = np.array(d["sides"]); self.tag = np.array([NAME.get(t, t) if t else "other" for t in d["mb_tag"]])
        self.idx = {t: np.where(self.tag == t)[0] for t in np.unique(self.tag)}; self.glomeruli = {k: np.array(v) for k, v in d["meta"]["glomeruli"].items()}
        self.input_mask = np.zeros(self.n, bool)
        for g, v in self.groups.items():
            if any(g.startswith(p + "_") for p in d["meta"]["inputs"]): self.input_mask[v] = True

    def of_type(self, types, side=None):
        m = np.isin(self.typ, types if isinstance(types, (list, tuple)) else [types])
        if side: m &= self.side == side
        return np.where(m)[0]

    def sim(self, seed=0, js_like=True):
        s = Sim(self.n, self.indptr, self.post, self.w0.copy(), seed)
        if js_like: s.always0 = self.input_mask.copy()
        return s

    def edges(self, a, b):
        return np.where((self.tag[self.pre] == a) & (self.tag[self.post] == b))[0]
