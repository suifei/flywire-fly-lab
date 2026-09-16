#!/usr/bin/env python
"""
解码器压力测试（脑机接口类比）：“果蝇说中文”的线性读出，在只看得到一部分神经元、记录有噪声、通道中途失效时，什么时候开始失灵？

数据：results/language/dataset.npz（language/fly_words.py 的全脑模拟：300 个试次 × 121,706 个非感觉神经元的脉冲数，12 个词；
      前 240 训练、后 60 测试，与原解码器相同的划分；第 301 个“第一句话”试次只用来看句子是否还能完整读出）。
      只做离线分析，不再跑脑模拟。

事先写定的设计（运行前写好，结果出来后不改）：
  解码器：与 fly_words.decode 相同（log1p → 用训练集均值/标准差标准化，去掉训练集里恒定的神经元 → 对偶岭回归，输出 > 0.5 判为有这个词），
          但 λ 固定为 0.1 × mean(diag(K))（原解码器交叉验证选出的值），不在每个条件里重选。
          另在 3 个规模上用原来的 5 折交叉验证重选 λ（候选 0.01/0.1/1/10），检查“固定 λ”是否让小规模条件吃亏。
  指标：测试集 12 个词的平均平衡准确率（0.5 = 瞎猜）；整句全对比例；第一句话 {醋, 甜, 热, 亮} 是否完整读出。
        失效门槛：中位数平衡准确率 ≥ 0.9 记为“可用”，≥ 0.75 记为“勉强”；报告各采样方式达到门槛所需的最少神经元数。
        经验机会水平：全部神经元、训练标签随机打乱 20 次。
  一、能看到多少神经元（每个条件 20 次独立抽样，种子 20260915）：
    random_all     从全部非感觉神经元里随机抽 n 个（像随机插电极，多数神经元根本不放电）；
    random_active  只从训练集里放过电的神经元中随机抽（像只保留有信号的通道）；
    output_only    只从下行 + 运动神经元（1,409 个）里随机抽（像只记录神经/肌肉输出）；
    local_probe    以随机一个非感觉神经元的胞体为中心，取最近的 n 个（像一块局部电极阵列或一个成像视野；没有位置信息的神经元不参与）；
    top_variance   按训练集方差挑前 n 个（参考上限：能自由挑选记录对象时；确定性，只算 1 次）。
    n ∈ {10, 30, 100, 300, 1000, 3000, 10000, 30000}（不超过该集合大小），外加该集合全部。
  二、记录噪声（在“全部 121,706 个”与“random_active 抽 1,000 个”两种规模上，各 10 次）：
    漏检：每个脉冲以概率 p 被记到，p ∈ {1, 0.5, 0.2, 0.1, 0.05, 0.02}（像钙成像漏掉脉冲）；
    假脉冲：每个被记录的神经元在 0.25 s 窗口里额外加 Poisson(λ·0.25) 个，λ ∈ {0, 1, 4, 16, 64} Hz（像背景噪声、串扰）。
    训练和测试都加同样强度的噪声（相当于在噪声条件下重新校准）。
  三、通道失效（random_active 抽 1,000 个，20 次）：用干净数据训练，测试时比例 q 的通道读数变成 0 且不重新训练，
    q ∈ {0, 0.1, 0.25, 0.5, 0.75, 0.9}；对照：只用剩下的通道重新训练。
输出 results/language/stress.json
用法（flygym 环境）：python language/decoder_stress.py
"""
import json
import os
import time

os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "2")   # 同时有全脑模拟在跑，限制 BLAS 线程
os.environ.setdefault("OMP_NUM_THREADS", "2")
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "results" / "language" / "dataset.npz"
OUT = ROOT / "results" / "language" / "stress.json"
N_TRAIN, N_TRIALS = 240, 300
LAM = 0.1
SEED = 20260915
REPS, NOISE_REPS, DROP_REPS, SHUFFLE_REPS = 20, 10, 20, 20
SIZES = [10, 30, 100, 300, 1000, 3000, 10000, 30000]
THIN = [1.0, 0.5, 0.2, 0.1, 0.05, 0.02]
FALSE_HZ = [0, 1, 4, 16, 64]
DROP = [0, 0.1, 0.25, 0.5, 0.75, 0.9]
WINDOW_S = 0.25
FIRST = ["醋", "甜", "热", "亮"]


def bal_acc(y, p):
    pos, neg = y == 1, y == 0
    return (((p > 0.5) & pos).sum() / max(pos.sum(), 1) + ((p <= 0.5) & neg).sum() / max(neg.sum(), 1)) / 2


class Decoder:
    def __init__(self, Y, words):
        self.Y, self.words = Y, list(words)
        self.Ytr = Y[:N_TRAIN].astype(np.float64)
        self.Yte = Y[N_TRAIN:N_TRIALS]
        self.first = np.array([1 if w in FIRST else 0 for w in self.words])

    def prep(self, X, Xtest_override=None):
        """X：(301, n) 原始计数。返回训练 / 测试 / 第一句话的标准化特征（与 fly_words.decode 相同的处理）。"""
        L = np.log1p(X)
        mu, sd = L[:N_TRAIN].mean(0), L[:N_TRAIN].std(0)
        keep = sd > 0
        if Xtest_override is not None:
            L = L.copy()
            L[N_TRAIN:] = np.log1p(Xtest_override[N_TRAIN:])
        Z = (L[:, keep] - mu[keep]) / sd[keep]
        return Z[:N_TRAIN], Z[N_TRAIN:N_TRIALS], Z[N_TRIALS:N_TRIALS + 1], int(keep.sum())

    def evaluate(self, Ztr, Zte, Zf, lam_scale=LAM, Ytr=None):
        Ytr = self.Ytr if Ytr is None else Ytr
        yb = Ytr.mean(0)
        if Ztr.shape[1] == 0:
            P, Pf = np.tile(yb, (len(self.Yte), 1)), yb
        else:
            K = Ztr @ Ztr.T
            base = float(np.mean(np.diag(K))) or 1.0
            alpha = np.linalg.solve(K + lam_scale * base * np.eye(len(K)), Ytr - yb)
            P = Zte @ (Ztr.T @ alpha) + yb
            Pf = (Zf @ (Ztr.T @ alpha) + yb)[0]
        bal = float(np.mean([bal_acc(self.Yte[:, k], P[:, k]) for k in range(len(self.words))]))
        exact = float(np.mean(np.all((P > 0.5) == (self.Yte == 1), axis=1)))
        return dict(bal=round(bal, 4), exact=round(exact, 4), first_ok=bool(np.array_equal((Pf > 0.5).astype(int), self.first)))

    def cv_lambda(self, Ztr, scales=(0.01, 0.1, 1, 10)):
        K = Ztr @ Ztr.T
        base = float(np.mean(np.diag(K))) or 1.0
        folds = np.array_split(np.arange(N_TRAIN), 5)
        cv = {}
        for s in scales:
            accs = []
            for f in folds:
                tr = np.setdiff1d(np.arange(N_TRAIN), f)
                yb = self.Ytr[tr].mean(0)
                a = np.linalg.solve(K[np.ix_(tr, tr)] + s * base * np.eye(len(tr)), self.Ytr[tr] - yb)
                P = K[np.ix_(f, tr)] @ a + yb
                accs.append(np.mean([bal_acc(self.Ytr[f, k], P[:, k]) for k in range(len(self.words))]))
            cv[s] = float(np.mean(accs))
        return max(cv, key=cv.get), cv


def summarize(vals):
    b = np.array([v["bal"] for v in vals]); e = np.array([v["exact"] for v in vals])
    return dict(n_reps=len(vals), bal_median=round(float(np.median(b)), 4), bal_q25=round(float(np.quantile(b, 0.25)), 4),
                bal_q75=round(float(np.quantile(b, 0.75)), 4), exact_median=round(float(np.median(e)), 4),
                first_sentence_ok_frac=round(float(np.mean([v["first_ok"] for v in vals])), 3))


def main():
    t0 = time.time()
    z = np.load(DATA)
    C = z["counts"]                      # float32 (301, 121706)
    Y, words = z["labels"], [str(w) for w in z["words"]]
    feat_A, feat_B = z["feat_A"], z["feat_B"]
    dec = Decoder(Y, words)
    rng = np.random.default_rng(SEED)
    nA = C.shape[1]
    active = np.nonzero(C[:N_TRAIN].max(0) > 0)[0]
    posB = np.searchsorted(feat_A, feat_B)
    assert np.array_equal(feat_A[posB], feat_B)
    # 胞体位置（没有胞体坐标时用注释表里的 pos_x/y/z）
    comp = pd.read_csv(ROOT / "external/fly-brain/data/2025_Completeness_783.csv", index_col=0)
    fids = comp.index.to_numpy(np.int64)[feat_A]
    ann = pd.read_csv(ROOT / "external/flywire_annotations/Supplemental_file1_neuron_annotations.tsv", sep="\t", low_memory=False,
                      usecols=["root_id", "soma_x", "soma_y", "soma_z", "pos_x", "pos_y", "pos_z"]).drop_duplicates("root_id").set_index("root_id")
    ann = ann.reindex(fids)
    xyz = np.where(ann[["soma_x", "soma_y", "soma_z"]].notna().all(1).to_numpy()[:, None],
                   ann[["soma_x", "soma_y", "soma_z"]].to_numpy(float), ann[["pos_x", "pos_y", "pos_z"]].to_numpy(float))
    xyz = xyz * np.array([4.0, 4.0, 40.0]) / 1000.0          # 注释表坐标是 4×4×40 nm 体素 → µm
    has_pos = np.isfinite(xyz).all(1)
    pos_idx = np.nonzero(has_pos)[0]
    print(f"特征 {nA}；训练集里放过电的 {len(active)}；下行+运动 {len(posB)}；有位置的 {len(pos_idx)}", flush=True)

    out = dict(design=dict(lambda_scale=LAM, reps=REPS, sizes=SIZES, thin=THIN, false_hz=FALSE_HZ, drop=DROP, seed=SEED, window_s=WINDOW_S),
               n_features=nA, n_active_train=int(len(active)), n_output=int(len(posB)), n_with_position=int(len(pos_idx)))

    # 参照：全部神经元（与 decoder.json 的 A 对照）与标签打乱的机会水平
    full = dec.prep(C)
    out["full"] = dec.evaluate(*full[:3])
    perm = []
    for _ in range(SHUFFLE_REPS):
        Ysh = dec.Ytr[rng.permutation(N_TRAIN)]
        perm.append(dec.evaluate(*full[:3], Ytr=Ysh))
    out["chance_shuffled_labels"] = summarize(perm)
    print("全部神经元：", out["full"], "；打乱标签：", out["chance_shuffled_labels"], flush=True)

    # 一、采样方式 × 规模
    def pools():
        return dict(random_all=np.arange(nA), random_active=active, output_only=posB)
    curves = {}
    for name, pool in pools().items():
        curves[name] = {}
        for n in [s for s in SIZES if s < len(pool)] + [len(pool)]:
            reps = 1 if n == len(pool) else REPS
            vals = []
            for _ in range(reps):
                cols = pool if n == len(pool) else rng.choice(pool, n, replace=False)
                vals.append(dec.evaluate(*dec.prep(C[:, cols])[:3]))
            curves[name][n] = summarize(vals)
        print(name, {n: v["bal_median"] for n, v in curves[name].items()}, f"{time.time() - t0:.0f}s", flush=True)
    curves["local_probe"] = {}
    for n in [s for s in SIZES if s < len(pos_idx)]:
        vals, radius = [], []
        for _ in range(REPS):
            c = xyz[rng.choice(pos_idx)]
            d = np.linalg.norm(xyz[pos_idx] - c, axis=1)
            near = np.argpartition(d, n - 1)[:n]
            cols = pos_idx[near]
            radius.append(float(d[near].max()))
            vals.append(dec.evaluate(*dec.prep(C[:, cols])[:3]))
        curves["local_probe"][n] = summarize(vals)
        curves["local_probe"][n]["probe_radius_um_median"] = round(float(np.median(radius)), 1)
    print("local_probe", {n: v["bal_median"] for n, v in curves["local_probe"].items()}, f"{time.time() - t0:.0f}s", flush=True)
    L = np.log1p(C[:N_TRAIN]); var_order = np.argsort(-L.var(0)); del L
    curves["top_variance"] = {}
    for n in SIZES:
        curves["top_variance"][n] = summarize([dec.evaluate(*dec.prep(C[:, var_order[:n]])[:3])])
    print("top_variance", {n: v["bal_median"] for n, v in curves["top_variance"].items()}, flush=True)

    def threshold_n(curve, thr):
        ok = [int(n) for n, v in sorted(curve.items(), key=lambda kv: int(kv[0])) if v["bal_median"] >= thr]
        return min(ok) if ok else None
    out["sampling"] = curves
    out["min_n_for"] = {name: {"0.9": threshold_n(c, 0.9), "0.75": threshold_n(c, 0.75)} for name, c in curves.items()}

    # 固定 λ 的检查：3 个规模上重选 λ
    lam_check = []
    for n in (30, 300, 3000):
        vals_fixed, vals_cv, chosen = [], [], []
        for _ in range(5):
            cols = rng.choice(active, n, replace=False)
            Ztr, Zte, Zf, _k = dec.prep(C[:, cols])
            s, _cv = dec.cv_lambda(Ztr)
            chosen.append(s)
            vals_fixed.append(dec.evaluate(Ztr, Zte, Zf)); vals_cv.append(dec.evaluate(Ztr, Zte, Zf, lam_scale=s))
        lam_check.append(dict(pool="random_active", n=n, fixed=summarize(vals_fixed), cv=summarize(vals_cv), chosen=chosen))
    out["lambda_check"] = lam_check
    print("λ 检查：", [(x["n"], x["fixed"]["bal_median"], x["cv"]["bal_median"], x["chosen"]) for x in lam_check], flush=True)

    # 二、噪声
    noise = {}
    for scale in ("all", "active_1000"):
        noise[scale] = dict(thin={}, false_spikes={})
        for p in THIN:
            vals = []
            for _ in range(1 if (p == 1.0 and scale == "all") else NOISE_REPS):
                cols = np.arange(nA) if scale == "all" else rng.choice(active, 1000, replace=False)
                X = C[:, cols]
                if p < 1.0:
                    X = rng.binomial(X.astype(np.int64), p).astype(np.float32)
                vals.append(dec.evaluate(*dec.prep(X)[:3]))
            noise[scale]["thin"][p] = summarize(vals)
        for hz in FALSE_HZ:
            vals = []
            for _ in range(1 if (hz == 0 and scale == "all") else NOISE_REPS):
                cols = np.arange(nA) if scale == "all" else rng.choice(active, 1000, replace=False)
                X = C[:, cols]
                if hz > 0:
                    X = X + rng.poisson(hz * WINDOW_S, size=X.shape).astype(np.float32)
                vals.append(dec.evaluate(*dec.prep(X)[:3]))
            noise[scale]["false_spikes"][hz] = summarize(vals)
        print("噪声", scale, {k: {kk: vv["bal_median"] for kk, vv in v.items()} for k, v in noise[scale].items()}, f"{time.time() - t0:.0f}s", flush=True)
    out["noise"] = noise

    # 三、通道失效
    drop = {"no_retrain": {}, "retrain_survivors": {}}
    for q in DROP:
        a_vals, b_vals = [], []
        for _ in range(DROP_REPS):
            cols = rng.choice(active, 1000, replace=False)
            X = C[:, cols]
            dead = rng.random(1000) < q
            Xt = X.copy(); Xt[:, dead] = 0.0
            Ztr, Zte, Zf, _k = dec.prep(X, Xtest_override=Xt)
            a_vals.append(dec.evaluate(Ztr, Zte, Zf))
            b_vals.append(dec.evaluate(*dec.prep(X[:, ~dead])[:3]))
        drop["no_retrain"][q] = summarize(a_vals)
        drop["retrain_survivors"][q] = summarize(b_vals)
    out["dropout_active_1000"] = drop
    print("通道失效", {k: {kk: vv["bal_median"] for kk, vv in v.items()} for k, v in drop.items()}, flush=True)

    # 探索性（看到“读数变 0”崩得很快之后加的，独立随机种子，不影响上面的结果）：知道哪些通道坏了，用训练集均值填补（标准化后 = 0），不重新训练
    rng2 = np.random.default_rng(SEED + 1)
    imp = {}
    for q in DROP:
        vals = []
        for _ in range(DROP_REPS):
            cols = rng2.choice(active, 1000, replace=False)
            X = C[:, cols]
            dead = rng2.random(1000) < q
            Ztr, Zte, Zf, _k = dec.prep(X)
            keep = X[:N_TRAIN].std(0) > 0          # 与 prep 里去掉恒定神经元的规则相同（log1p 单调，恒定性不变）
            dk = dead[keep]
            Zte, Zf = Zte.copy(), Zf.copy()
            Zte[:, dk] = 0.0; Zf[:, dk] = 0.0
            vals.append(dec.evaluate(Ztr, Zte, Zf))
        imp[q] = summarize(vals)
    out["exploratory_dropout_mean_impute"] = imp
    print("探索性：坏通道用均值填补", {k: v["bal_median"] for k, v in imp.items()}, flush=True)
    out["elapsed_s"] = round(time.time() - t0, 1)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("写入", OUT, f"用时 {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
