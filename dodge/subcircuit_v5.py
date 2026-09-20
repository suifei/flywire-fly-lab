"""子回路 v5 = 子回路 v4（6,296 个，原样）＋ 蘑菇体学习回路（嗅觉感受神经元 ORN、投射神经元 ALPN、局部神经元 ALLN、
凯尼恩细胞 KC、蘑菇体输出神经元 MBON、多巴胺神经元 DAN、APL、DPM）。只给「生活」模式用；球场 / 五子棋仍是 v3，已发布的数字不动。

和 v4 的关系：前 6,296 个神经元的编号、分组、它们之间的连接与 v4 逐位相同；蘑菇体的神经元接在后面。
两处建模决定（都登记在台账 PARAMETERS，依据见 learn/mb_odor_coding.py）：
  ① ALLN 发出的突触一律取抑制性——不改的话一闻到气味整个回路就失控（KC 76% 同时放电）。
  ② 凡是碰到蘑菇体神经元的边，只保留 ≥2 个突触的（v4 内部的边不动）。全留是 129 万条，页面装不下；
     砍掉的主要是 KC↔KC 之间只有 1 个突触的接触（29 万条里的 23 万条）。砍完之后气味编码和条件化的判据是否照样成立，由 learn/v5_check.py 验。

新增分组：
  ORN_left / ORN_right / ORN_na    全部嗅觉感受神经元（已经在 v4 的 OLFA / OLFR 组里的 DM1、DA2 除外）；meta.glomeruli 给出每个嗅小球的神经元下标
  PAM_left/right、PPL1_left/right   多巴胺神经元（强化信号从这里注入——连接组自己叫不起它们，见 learn/reinforcement_route.py）
  另有逐神经元的 mb_tag（KC / MBON / DAN / APL / DPM / ALPN / ALLN / ORN / ""）

用法：conda activate flygym && python dodge/subcircuit_v5.py   → results/dodge/subcircuit_v5.json
"""
import json, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "learn")); sys.path.insert(0, str(ROOT / "dodge"))
import mb_circuit as mb, subcircuit as v1

MB_WMIN = 2
TAG = {"Kenyon_Cell": "KC", "MBON": "MBON", "DAN": "DAN", "APL": "APL", "DPM": "DPM", "ALPN": "ALPN", "ALLN": "ALLN", "olfactory": "ORN"}


def main():
    ann, fids, con = mb.load(); fid2i = {int(f): i for i, f in enumerate(fids)}
    v4 = json.load(open(ROOT / "results/dodge/subcircuit_v4.json")); v4i = np.array([fid2i[int(f)] for f in v4["fids"]]); n4 = len(v4i)
    c = mb.Circuit(ann, fids, con, extra=v4i.tolist(), force_inhibitory=["ALLN"])
    # 重排：v4 的神经元在前（保持 v4 的顺序），蘑菇体独有的在后
    in4 = np.zeros(len(fids), bool); in4[v4i] = True; rest = [g for g in c.sel if not in4[g]]; order = np.concatenate([v4i, np.array(rest, int)])
    new = np.full(len(fids), -1); new[order] = np.arange(len(order)); old2new = new[c.sel]; n = len(order)
    pre, post, w, nsyn = old2new[c.pre], old2new[c.post], c.w0, c.nsyn
    keep = ((pre < n4) & (post < n4)) | (nsyn >= MB_WMIN); pre, post, w = pre[keep], post[keep], w[keep]
    w = np.round(w / mb.P["w_syn"]).astype(np.float32) * np.float32(mb.P["w_syn"])     # 与 v1–v4 相同的 float32 算法（突触数 × 0.275），页面的 Int16 压缩要求逐位还原
    o = np.lexsort((post, pre)); pre, post, w = pre[o], post[o], w[o]; indptr = np.searchsorted(pre, np.arange(n + 1)).astype(np.int32)
    # v4 内部的边必须逐位不变
    ip4 = np.frombuffer(__import__("base64").b64decode(v4["indptr"]), np.int32); po4 = np.frombuffer(__import__("base64").b64decode(v4["post"]), np.int32); w4 = np.frombuffer(__import__("base64").b64decode(v4["w"]), np.float32)
    m = (pre < n4) & (post < n4); a = sorted(zip(pre[m].tolist(), post[m].tolist(), np.round(w[m].astype(float) / 0.275).astype(int).tolist()))
    pre4 = np.repeat(np.arange(n4), np.diff(ip4)); b = sorted(zip(pre4.tolist(), po4.tolist(), np.round(w4.astype(float) / 0.275).astype(int).tolist()))
    # ALLN 在 v4 里的那几个也被改成了抑制性——那部分允许不同，单独数出来
    tag_new = np.array([""] * n, dtype=object); tnew = c.tag[np.argsort(old2new)]; 
    for i in range(n): tag_new[i] = TAG.get(tnew[i], "")
    alln4 = {i for i in range(n4) if tag_new[i] == "ALLN"}; diff = [x for x, y in zip(a, b) if x != y] if len(a) == len(b) else None
    assert diff is not None and all(x[0] in alln4 for x in diff), "v4 内部的边变了（ALLN 之外）"
    print(f"v5：{n:,} 个神经元、{len(w):,} 条边（v4 {n4:,} / {len(w4):,}）；v4 内部的边逐位相同，除了 {len(alln4)} 个本来就在 v4 里的 ALLN 发出的 {len(diff)} 条边改成了抑制性")
    meta = ann.iloc[order]; typ = meta.cell_type.fillna("?").tolist(); side = meta.side.fillna("?").tolist()
    groups = dict(v4["groups"]); in_olf = set(sum((groups[g] for g in groups if g.startswith(("OLFA_", "OLFR_"))), []))
    for s in ("left", "right", "na"): groups[f"ORN_{s}"] = [i for i in range(n) if tag_new[i] == "ORN" and side[i] == s and i not in in_olf]
    for cl in ("PAM", "PPL1"):
        for s in ("left", "right"): groups[f"{cl}_{s}"] = [i for i in range(n) if tag_new[i] == "DAN" and typ[i].startswith(cl) and side[i] == s]
    glom = {}
    for i in range(n):
        if tag_new[i] == "ORN" and typ[i].startswith("ORN_"): glom.setdefault(typ[i][4:], []).append(i)
    inputs = dict(v4["meta"]["inputs"]); inputs["ORN"] = ["ORN_*（DM1、DA2 除外）"]
    # 两种可学的合成气味：53 个嗅小球随机排列（种子 4242，与 learn/parity_py.py、embodied_loop.py 相同），前 20 个 = A，接着 20 个 = B，互不重合。
    # 「气味」在这里就是「哪些嗅小球的感受神经元被驱动」；没有用真实气味的受体谱（DoOR），所以叫 A / B 而不叫具体的化学名。
    perm = np.random.default_rng(4242).permutation(sorted(glom)).tolist(); odors = {"A": sorted(perm[:20]), "B": sorted(perm[20:40]), "vinegar": ["DM1"], "geosmin": ["DA2"]}
    out = dict(meta=dict(n=int(n), n_edges=int(len(w)), n_v4=int(n4), version=5, params=v4["meta"]["params"], inputs=inputs, targets=v4["meta"]["targets"], mb_wmin=MB_WMIN, alln_inhibitory=True,
                         glomeruli=glom, odors=odors, n_tag={t: int((tag_new == t).sum()) for t in sorted(set(tag_new)) if t},
                         note="v5 = v4 + 蘑菇体学习回路；碰到蘑菇体的边只留 ≥2 突触，ALLN 取抑制性", source="FlyWire v783 + flywire_annotations"),
               groups=groups, fids=[str(int(fids[g])) for g in order], types=typ, sides=side, supers=meta.super_class.fillna("?").tolist(), mb_tag=tag_new.tolist(),
               hops_in=list(v4["hops_in"]) + [-1] * (n - n4), hops_out=list(v4["hops_out"]) + [-1] * (n - n4),
               indptr=v1.b64(indptr), post=v1.b64(post.astype(np.int32)), w=v1.b64(w.astype(np.float32)), validation=[])
    p = ROOT / "results/dodge/subcircuit_v5.json"; p.write_text(json.dumps(out, separators=(",", ":"))); print(f"→ {p}  {p.stat().st_size / 1e6:.1f} MB；嗅小球 {len(glom)} 个；分组 {', '.join(f'{k} {len(v)}' for k, v in groups.items() if k.startswith(('ORN', 'PAM', 'PPL1')))}")


if __name__ == "__main__": main()
