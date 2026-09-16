#!/usr/bin/env python
"""
果蝇“说中文”：全脑 LIF（Shiu et al. 2024，FlyWire v783，138,639 个神经元）→ 线性读出 → 中文词 → 中文句子。
思路参照新闻里 @chetaslua 的做法（我们没有看到对方代码，这里按公开描述自行实现，参数都是自己事先定的）。

必须先说清楚：这不是果蝇“会说话”。词表、每个词对应哪群感觉神经元、句子模板，都是我们写的；
线性读出是用“给了哪些刺激”当标签训练出来的分类器。它能检验的只是：刺激信息传到下游（非感觉神经元、下行/运动神经元）之后，
还能不能被线性地读出来。

设计（运行前写定）：
  词表（12 个，刺激对应的感觉神经元类型，左右两侧都给）：
    甜   LB3                          糖味觉神经元（本项目前面实验用过：左侧 → MN9 放电）
    苦   LB1a,LB1d / LB1b / LB1c      苦味觉神经元（前面实验：抑制 MN9）
    醋   ORN_DM1 + ORN_VA2            醋味相关嗅球（Semmelhack & Wang 2009）
    霉味 ORN_DA2                      土臭素（Stensmyr et al. 2012）
    二氧化碳 ORN_V                    CO2（Suh et al. 2004）
    热   TRN_VP2                      触角热感受细胞（Gallio et al. 2011）
    冷   TRN_VP3a + TRN_VP3b          触角冷感受细胞（Gallio et al. 2011）
    干   HRN_VP4                      干燥感受（Enjin 2016；Knecht 2017）
    湿   HRN_VP5                      湿润感受（同上）
    亮   R1-6                         光感受器
    声音 JO-A* + JO-B*               Johnston 器振动/声音亚群（Kamikouchi et al. 2009）
    风   JO-C* + JO-E*               Johnston 器风/重力亚群（Yorozu et al. 2009）
  刺激：选中的词对应神经元全部给 100 Hz 泊松输入；每个试次 0.25 s 刺激 + 0.25 s 空白。
  试次：300 个训练/测试试次，每个词独立以 0.2 概率出现（至少 1 个），随机种子 20260914；
        前 240 个训练、后 60 个测试；第 301 个是“第一句话”试次，固定刺激 {醋、甜、热、亮}（模仿新闻里的场景），不参与训练。
  特征：刺激窗口内每个神经元的脉冲数，log1p 后标准化。
    A = 全部非感觉神经元（去掉 super_class 为 sensory / sensory_ascending 的）；
    B = 只用下行 + 运动神经元。
  读出：每个词一个线性岭回归（对偶形式），λ 在训练集内 5 折交叉验证从 {0.1, 1, 10, 100}×mean(diag(XXᵀ)) 里选，
        输出 > 0.5 判为“有这个词”。报告测试集每个词的准确率、平衡准确率、整句全对的比例。
  句子：只用 A 的读出结果，按固定中文模板拼句（模板是手写的）。
输出 results/language/{dataset.npz, decoder.json, first_sentence.json}
用法（brain-fly-cpu 环境）：python language/fly_words.py
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT / "external" / "fly-brain"
OUT = ROOT / "results" / "language"
sys.path.insert(0, str(REPO / "code" / "paper-phil-drosophila"))

WORDS = {
    "甜": ["LB3"], "苦": ["LB1a,LB1d", "LB1b", "LB1c"], "醋": ["ORN_DM1", "ORN_VA2"], "霉味": ["ORN_DA2"], "二氧化碳": ["ORN_V"],
    "热": ["TRN_VP2"], "冷": ["TRN_VP3a", "TRN_VP3b"], "干": ["HRN_VP4"], "湿": ["HRN_VP5"], "亮": ["R1-6"],
    "声音": ["JO-A*", "JO-B*"], "风": ["JO-C*", "JO-E*"],
}
RATE_HZ, STIM_S, REST_S = 100.0, 0.25, 0.25
N_TRIALS, N_TRAIN, P_WORD, SEED = 300, 240, 0.2, 20260914
FIRST = ["醋", "甜", "热", "亮"]


def type_mask(ct, spec):
    return ct.str.startswith(spec[:-1]) if spec.endswith("*") else (ct == spec)


def main():
    import brian2 as b2
    from brian2 import ms, mV, Hz, second, Network, NeuronGroup, PoissonGroup, Synapses, StateMonitor, TimedArray
    from model import create_model, default_params

    OUT.mkdir(parents=True, exist_ok=True)
    comp = pd.read_csv(REPO / "data/2025_Completeness_783.csv", index_col=0)
    fids = comp.index.to_numpy(np.int64); fid2i = {int(f): i for i, f in enumerate(fids)}
    ann = pd.read_csv(ROOT / "external/flywire_annotations/Supplemental_file1_neuron_annotations.tsv", sep="\t", low_memory=False,
                      usecols=["root_id", "super_class", "cell_type"]).drop_duplicates("root_id")
    ann = ann[ann.root_id.isin(fid2i)]
    ct = ann.cell_type.fillna("")
    pops = {w: sorted({fid2i[int(r)] for spec in specs for r in ann.root_id[type_mask(ct, spec)]}) for w, specs in WORDS.items()}
    print("每个词的刺激神经元数：", {w: len(v) for w, v in pops.items()}, flush=True)
    inputs = sorted({i for v in pops.values() for i in v})
    col = {i: k for k, i in enumerate(inputs)}
    sc = pd.Series(ann.super_class.values, index=[fid2i[int(r)] for r in ann.root_id])
    sensory = set(sc.index[sc.isin(["sensory", "sensory_ascending"])])
    feat_A = np.array([i for i in range(len(fids)) if i not in sensory])
    feat_B = np.array(sorted(sc.index[sc.isin(["descending", "motor"])]))
    print(f"特征 A 非感觉神经元 {len(feat_A)} 个；特征 B 下行 + 运动神经元 {len(feat_B)} 个；输入神经元 {len(inputs)} 个", flush=True)

    rng = np.random.default_rng(SEED)
    words = list(WORDS)
    labels = np.zeros((N_TRIALS + 1, len(words)), np.int8)
    for t in range(N_TRIALS):
        while True:
            row = (rng.random(len(words)) < P_WORD).astype(np.int8)
            if row.any():
                break
        labels[t] = row
    labels[N_TRIALS] = [1 if w in FIRST else 0 for w in words]
    n_all = N_TRIALS + 1
    rates = np.zeros((2 * n_all + 1, len(inputs)), np.float32)          # 偶数行刺激，奇数行空白，最后一行收尾
    for t in range(n_all):
        for k, w in enumerate(words):
            if labels[t, k]:
                rates[2 * t, [col[i] for i in pops[w]]] = RATE_HZ

    b2.set_device("cpp_standalone", build_on_run=False, directory=str(OUT / ".brian2_build"))
    b2.prefs.devices.cpp_standalone.openmp_threads = 0
    b2.prefs.devices.cpp_standalone.extra_make_args_unix = ["-j4"]
    b2.defaultclock.dt = 0.1 * ms
    params = dict(default_params)
    b2.seed(SEED)
    neu, syn, _ = create_model(str(REPO / "data/2025_Completeness_783.csv"), str(REPO / "data/2025_Connectivity_783.parquet"), params)
    ta = TimedArray(rates * Hz, dt=STIM_S * second)
    pg = PoissonGroup(len(inputs), rates="ta(t, i)")
    ps = Synapses(pg, neu, on_pre=f"v += {float(params['w_syn'] * params['f_poi'] / mV)}*mV")
    ps.connect(i=np.arange(len(inputs)), j=np.array(inputs))
    rfc = np.full(len(neu), float(params["t_rfc"] / ms)); rfc[inputs] = 0.0
    neu.rfc = rfc * ms
    counter = NeuronGroup(len(feat_A), "count : 1")                        # 只数非感觉神经元（B 是 A 的子集）
    cs = Synapses(neu, counter, on_pre="count_post += 1")
    cs.connect(i=feat_A, j=np.arange(len(feat_A)))
    mon = StateMonitor(counter, "count", record=True, dt=STIM_S * second)
    net = Network(neu, syn, pg, ps, counter, cs, mon)
    T = n_all * (STIM_S + REST_S) + STIM_S
    net.run(T * second)
    t0 = time.time()
    b2.device.build(directory=str(OUT / ".brian2_build"), compile=True, run=True, clean=True)
    print(f"编译 + 仿真 {T:.2f} s 用时 {time.time() - t0:.0f} s", flush=True)
    C = np.asarray(mon.count).astype(np.float32)                          # (神经元, 采样)
    starts = np.arange(n_all) * 2
    counts = (C[:, starts + 1] - C[:, starts]).T                          # (试次, 非感觉神经元)
    np.savez_compressed(OUT / "dataset.npz", counts=counts.astype(np.float32), labels=labels, words=np.array(words),
                        feat_A=feat_A, feat_B=feat_B)
    pos_B = np.searchsorted(feat_A, feat_B)
    report = dict(words=words, populations={w: len(v) for w, v in pops.items()}, n_features=dict(A=len(feat_A), B=len(feat_B)),
                  active_per_trial_median=int(np.median((counts > 0).sum(1))), sim_s=T)
    first = {}
    for name, cols in (("A", np.arange(len(feat_A))), ("B", pos_B)):
        res, pred_first = decode(np.log1p(counts[:, cols]), labels, words)
        report[name] = res
        first[name] = pred_first
        print(f"特征 {name}：测试集平均准确率 {res['mean_acc']:.3f}，平均平衡准确率 {res['mean_bal_acc']:.3f}，整句全对 {res['exact_match']:.3f}，λ×{res['lambda_scale']}", flush=True)
        print("   每个词：", {w: round(v, 2) for w, v in res["per_word_bal_acc"].items()}, flush=True)
    (OUT / "decoder.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    decoded = [w for w, s in zip(words, first["A"]) if s > 0.5]
    sentence = compose(decoded)
    fs = dict(stimulus=FIRST, scores_A={w: round(float(s), 3) for w, s in zip(words, first["A"])},
              scores_B={w: round(float(s), 3) for w, s in zip(words, first["B"])}, decoded_A=decoded, sentence=sentence)
    (OUT / "first_sentence.json").write_text(json.dumps(fs, ensure_ascii=False, indent=1))
    print("第一句话试次：刺激", FIRST, "→ 读出", decoded, "→", sentence, flush=True)


def decode(X, Y, words):
    n_tr = N_TRAIN
    Xtr, Xte, Xf = X[:n_tr], X[n_tr:N_TRIALS], X[N_TRIALS:N_TRIALS + 1]
    mu, sd = Xtr.mean(0), Xtr.std(0)
    keep = sd > 0
    z = lambda A: (A[:, keep] - mu[keep]) / sd[keep]
    Ztr, Zte, Zf = z(Xtr), z(Xte), z(Xf)
    Ytr, Yte = Y[:n_tr].astype(np.float64), Y[n_tr:N_TRIALS]
    K = Ztr @ Ztr.T
    base = float(np.mean(np.diag(K))) or 1.0
    scales = [0.1, 1, 10, 100]
    folds = np.array_split(np.arange(n_tr), 5)

    def fit_predict(Ka, ya, Kb, lam):
        yb = ya.mean(0)
        alpha = np.linalg.solve(Ka + lam * np.eye(len(Ka)), ya - yb)
        return Kb @ alpha + yb

    def bal_acc(y, p):
        pos, neg = y == 1, y == 0
        tpr = ((p > 0.5) & pos).sum() / max(pos.sum(), 1); tnr = ((p <= 0.5) & neg).sum() / max(neg.sum(), 1)
        return (tpr + tnr) / 2

    cv = {}
    for s in scales:
        accs = []
        for f in folds:
            tr = np.setdiff1d(np.arange(n_tr), f)
            P = fit_predict(K[np.ix_(tr, tr)], Ytr[tr], K[np.ix_(f, tr)], s * base)
            accs.append(np.mean([bal_acc(Ytr[f, k], P[:, k]) for k in range(len(words))]))
        cv[s] = float(np.mean(accs))
    s_best = max(cv, key=cv.get)
    Kte, Kf = Zte @ Ztr.T, Zf @ Ztr.T
    P = fit_predict(K, Ytr, Kte, s_best * base)
    Pf = fit_predict(K, Ytr, Kf, s_best * base)[0]
    per_acc = {w: float(((P[:, k] > 0.5) == (Yte[:, k] == 1)).mean()) for k, w in enumerate(words)}
    per_bal = {w: float(bal_acc(Yte[:, k], P[:, k])) for k, w in enumerate(words)}
    exact = float(np.mean(np.all((P > 0.5) == (Yte == 1), axis=1)))
    return dict(lambda_scale=s_best, cv_bal_acc=cv, per_word_acc=per_acc, per_word_bal_acc=per_bal,
                mean_acc=float(np.mean(list(per_acc.values()))), mean_bal_acc=float(np.mean(list(per_bal.values()))), exact_match=exact,
                n_test=int(len(Yte)), test_positives={w: int(Yte[:, k].sum()) for k, w in enumerate(words)}), Pf


def compose(decoded):
    """固定的中文模板（手写）：按感觉类别把读出的词拼成句子。"""
    smell = [w for w in ("醋", "霉味", "二氧化碳") if w in decoded]
    taste = [w for w in ("甜", "苦") if w in decoded]
    feel = [w for w in ("热", "冷", "干", "湿") if w in decoded]
    other = [{"亮": "很亮", "声音": "听到声音", "风": "有风吹来"}[w] for w in ("亮", "声音", "风") if w in decoded]
    parts = []
    if smell:
        parts.append("我闻到" + "和".join({"醋": "醋味", "霉味": "霉味", "二氧化碳": "二氧化碳"}[w] for w in smell) + "。")
    if taste:
        parts.append("我尝到" + "和".join({"甜": "甜味", "苦": "苦味"}[w] for w in taste) + "。")
    if feel:
        parts.append(("又" + "又".join(feel) if len(feel) > 1 else "很" + feel[0]) + ("，" + "，".join(other) if other else "") + "。")
    elif other:
        parts.append("，".join(other) + "。")
    parts.append("我该怎么做？")
    return "".join(parts)


if __name__ == "__main__":
    main()
