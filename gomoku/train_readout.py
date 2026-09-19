#!/usr/bin/env python
"""训练"果蝇下五子棋"的**线性读出**，并把对照一起做掉。

这件事的全部意义在对照上。其他把连接组接进游戏的项目都在读出端加一层训练网络，
于是"连接组到底有没有在起作用"就说不清了（Mineault 2026-09-14 的批评正是这一条）。
这里用的是**水库计算**的做法：果蝇脑里一个突触都不训练，只训练最后一层线性读出，
然后把同一套训练在三条臂上各做一遍：

  fly_intact    真实 FlyWire 连接组的下游神经元发放计数（3,537 维）
  fly_shuffled  **打乱接线**后的同一套（保出度与权重、只重排靶点）——网络规模与动力学一样，只有接线不同
  board_raw     直接用棋盘编码（450 维），完全不经过任何网络
  fly_topo      真实连接组，但棋盘按输入神经元的**真实胞体位置**铺（相邻格子 → 空间相邻的神经元）。
                随机分配把棋盘的邻接关系打散了，果蝇没理由算得出"连成五"——那样的阴性结果是我们自己造成的。
                这一臂是给它的公平机会。
  board+fly     两者拼在一起——**最锋利的一条**：如果它不比 board_raw 强，
                那这颗脑子在棋盘之外没提供任何东西

**判据事先写死**：
  A. 若 fly_intact ≈ fly_shuffled，说明**真实接线没有贡献**（果蝇脑只是个随机水库）。
  B. 若 fly_intact ≤ board_raw，说明**这颗脑子没有加工出新东西**（不如直接看棋盘）。
  只有 A 与 B 同时被否掉，才谈得上"连接组在下棋里起了作用"。

读出：岭回归，输入是标准化后的发放计数，输出是老师对每个格子的分数（在候选点上做 z 标准化，
非候选点为 0）。评价用**留出的整局**，指标是"与老师最佳着一致的比例"（top-1）与 top-5。

用法（flygym 环境，有 numpy）：python gomoku/train_readout.py
输出 results/gomoku/train.json + readout.json（页面用的权重）
"""
import base64
import json
from pathlib import Path

import numpy as np

import os
ROOT = Path(__file__).resolve().parent.parent
GD = ROOT / "results" / "gomoku"
# 子回路用 SUB 环境变量切换（默认 v2）；特征与输出文件名都带后缀，免得两版互相覆盖
SUF = ("_" + os.environ["SUB"].replace("subcircuit_", "")) if os.environ.get("SUB", "subcircuit_v2") != "subcircuit_v2" else ""
N = 15
SIZE = N * N
ALPHAS = [1e1, 1e2, 1e3, 1e4, 1e5]


def load_dataset():
    ds = json.loads((GD / "dataset.json").read_text())
    return ds


def targets(ds):
    """老师分数 → 每个局面一个 225 维向量（候选点上 z 标准化，其余 0）。"""
    Y = np.zeros((ds["n"], SIZE), np.float32)
    best = np.zeros(ds["n"], np.int32)
    legal = np.zeros((ds["n"], SIZE), bool)
    for k, s in enumerate(ds["samples"]):
        idx = np.array([c[0] for c in s["cand"]], np.int32)
        v = np.array([c[1] for c in s["cand"]], np.float64)
        v = np.log1p(np.maximum(v, 0))                 # 分值跨好几个数量级，取 log 压一下
        z = (v - v.mean()) / (v.std() + 1e-9)
        Y[k, idx] = z
        legal[k, idx] = True
        best[k] = s["best"]
    return Y, best, legal


def board_features(ds):
    """棋盘直接编码：450 维（我方 225 + 对方 225），和注入果蝇的那份信息完全一样。"""
    X = np.zeros((ds["n"], SIZE * 2), np.float32)
    for k, s in enumerate(ds["samples"]):
        b = np.frombuffer(base64.b64decode(s["board"]), np.uint8)
        me = s["me"]
        X[k, :SIZE] = (b == me)
        X[k, SIZE:] = (b != 0) & (b != me)
    return X


def fly_features(arm, n):
    meta = json.loads((GD / f"feat_{arm}{SUF}.json").read_text())
    X = np.fromfile(GD / f"feat_{arm}{SUF}.bin", np.float32).reshape(meta["rows"], meta["cols"])
    assert meta["rows"] == n, (meta["rows"], n)
    return X, meta


def ridge_fit(Xtr, Ytr, alpha):
    """样本数 < 特征数时用对偶形式（核岭），快很多。"""
    n, d = Xtr.shape
    if d <= n:
        A = Xtr.T @ Xtr + alpha * np.eye(d)
        return np.linalg.solve(A, Xtr.T @ Ytr)
    K = Xtr @ Xtr.T + alpha * np.eye(n)
    return Xtr.T @ np.linalg.solve(K, Ytr)


def evaluate(P, best, legal, Y=None):
    Pm = np.where(legal, P, -1e9)
    top1 = float((Pm.argmax(1) == best).mean())
    order = np.argsort(-Pm, 1)[:, :5]
    top5 = float(np.mean([best[i] in order[i] for i in range(len(best))]))
    out = dict(top1=round(top1, 4), top5=round(top5, 4))
    if Y is not None:
        # 每个局面在其候选点上算一次 Pearson，再取中位数——top1 太苛刻，
        # 弱信号也该看得见（这一项是探索性的，不是事先声明的判据）
        rs = []
        for i in range(len(best)):
            m = legal[i]
            if m.sum() < 4:
                continue
            a_, b_ = P[i][m], Y[i][m]
            if a_.std() < 1e-9 or b_.std() < 1e-9:
                continue
            rs.append(float(np.corrcoef(a_, b_)[0, 1]))
        out["median_r"] = round(float(np.median(rs)), 4) if rs else None
    return out


def run_arm(name, X, Y, best, legal, tr, te, out):
    mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-6
    Xs = ((X - mu) / sd).astype(np.float32)
    Xs = np.c_[Xs, np.ones(len(Xs), np.float32)]
    rows = []
    bestrec = None
    for a in ALPHAS:
        W = ridge_fit(Xs[tr], Y[tr], a)
        r_tr = evaluate(Xs[tr] @ W, best[tr], legal[tr])
        r_te = evaluate(Xs[te] @ W, best[te], legal[te], Y[te])
        rows.append(dict(alpha=a, train=r_tr, test=r_te))
        if bestrec is None or r_te["top1"] > bestrec[1]["test"]["top1"]:
            bestrec = (W, rows[-1], mu, sd)
        print(f"  {name:14s} α={a:<8g} 训练 top1 {r_tr['top1']:.3f}  测试 top1 {r_te['top1']:.3f}  "
              f"top5 {r_te['top5']:.3f}  中位 r {r_te.get('median_r')}")
    out[name] = dict(dim=int(X.shape[1]), sweep=rows, best=bestrec[1])
    return bestrec


def main():
    ds = load_dataset()
    Y, best, legal = targets(ds)
    g = np.array([s["g"] for s in ds["samples"]])
    te = g >= ds["test_from_game"]
    tr = ~te
    print(f"{ds['n']} 个局面：训练 {tr.sum()}（{len(set(g[tr]))} 局） / 测试 {te.sum()}（{len(set(g[te]))} 局）")
    # 随机基线：在候选点里瞎猜
    rnd = float(np.mean([1.0 / max(len(s["cand"]), 1) for k, s in enumerate(ds["samples"]) if te[k]]))
    out = dict(n=ds["n"], n_train=int(tr.sum()), n_test=int(te.sum()),
               n_games=ds["n_games"], test_from_game=ds["test_from_game"],
               random_baseline_top1=round(rnd, 4),
               criterion="A：fly_intact ≈ fly_shuffled → 真实接线无贡献；B：fly_intact ≤ board_raw → 这颗脑子没加工出新东西",
               arms={})
    print(f"随机猜（候选点均匀）top1 = {rnd:.4f}\n")
    keep = {}
    B = board_features(ds)
    keep["board_raw"] = run_arm("board_raw", B, Y, best, legal, tr, te, out["arms"])
    XI = None
    for arm in ("intact", "shuffled", "topo"):
        f = GD / f"feat_{arm}{SUF}.bin"
        if not f.exists():
            print(f"  （缺 {f.name}，跳过）"); continue
        X, meta = fly_features(arm, ds["n"])
        X = np.sqrt(X)                                  # 计数数据先开方，稳定方差（标准做法）
        out["arms"].setdefault("_meta", {})[arm] = {k: meta[k] for k in ("hz", "ms", "cols", "n_inputs_excluded")}
        out["arms"]["_meta"][arm]["nonconstant_cols"] = int((X[tr].std(0) > 1e-9).sum())
        keep["fly_" + arm] = run_arm("fly_" + arm, X, Y, best, legal, tr, te, out["arms"])
        if arm == "intact":
            XI = X
        else:
            del X
    if XI is not None:
        keep["board+fly"] = run_arm("board+fly", np.c_[B, XI], Y, best, legal, tr, te, out["arms"])
        del XI
    a = out["arms"]
    if "fly_intact" in a and "fly_shuffled" in a:
        d = a["fly_intact"]["best"]["test"]["top1"] - a["fly_shuffled"]["best"]["test"]["top1"]
        out["intact_minus_shuffled"] = round(d, 4)
        out["criterion_A_connectome_matters"] = bool(d > 0.02)
    if "fly_intact" in a:
        d2 = a["fly_intact"]["best"]["test"]["top1"] - a["board_raw"]["best"]["test"]["top1"]
        out["intact_minus_board"] = round(d2, 4)
        out["criterion_B_brain_adds"] = bool(d2 > 0)
    if "board+fly" in a:
        d3 = a["board+fly"]["best"]["test"]["top1"] - a["board_raw"]["best"]["test"]["top1"]
        out["boardfly_minus_board"] = round(d3, 4)
        out["criterion_C_brain_adds_on_top"] = bool(d3 > 0.01)
    (GD / f"train{SUF}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    # 权重导出：真实接线**与打乱接线各存一份**。
    # 打乱那一份不是备份，是对局时的对照——只有让"打乱脑"也真的下几盘，
    # 才能回答"连接组对下棋有没有贡献"这个问题（读出层的 top1 只说明学到多少，不等于棋力）。
    for armk, fname in (("fly_intact", f"readout{SUF}.json"), ("fly_shuffled", f"readout_shuffled{SUF}.json")):
        if armk not in keep:
            continue
        W, rec, mu, sd = keep[armk]
        meta = json.loads((GD / f"feat_{armk.split('_')[1]}{SUF}.json").read_text())
        (GD / fname).write_text(json.dumps(dict(
            arm=armk.split("_")[1], alpha=rec["alpha"], test=rec["test"], hz=meta["hz"], ms=meta["ms"],
            # sd 不能四舍五入到 4 位：从不放电的神经元 sd = 1e-6，舍完变成 0，
            # 浏览器那边除零 → NaN → 一个合法着都选不出来（2026-09-19 实测踩过）
            col_idx=meta["col_idx"], mu=[round(float(x), 4) for x in mu],
            sd=[float(f"{float(x):.6g}") for x in sd],
            W=[[round(float(v), 5) for v in row] for row in W]), separators=(",", ":")))
        print(f"→ results/gomoku/{fname}")
    print("\n" + json.dumps({k: v for k, v in out.items() if k.startswith("criterion") or k.startswith("intact")},
                            ensure_ascii=False))
    print("→ results/gomoku/train.json")


if __name__ == "__main__":
    main()
