#!/usr/bin/env python3
"""
五子棋 v2 的**估值头**：局面 → 轮到走的一方最终会不会赢。给搜索的叶子节点用。

    logit(局面) = Σ_{全部候选空点} Σ_{4 个方向} g[线型] + b          g = Φ̄·w_v（Φ̄ 同策略头：果蝇脑特征的试次平均，不训练）
    损失：二元交叉熵（逻辑回归，对 w_v 是凸的）。这就是国际象棋引擎里的 Texel 调参，只是特征来自果蝇脑。

为什么需要它（2026-09-19）：策略头学的是「哪一步更值得下」的相对偏好，不是「谁占优」。
拿它手搓叶子估值试了三版（直接相减 / 点内相加再取指数 / 逐线取指数），想 2–4 步的棋力都**不如只看 1 步**
（对老师 v2 深度 4：直觉 7–9，想 4 步 3–13）。局面估值必须单独学。
只需要一张表：「我方线型」与「对方线型」一一对应（互换视角），两张表不可识别（同策略头的教训）。

标签：深度 8 搜索算出必胜/必败的局面用确定结果；其余用所在那一局的终局胜负（重放核对过，见 replay_outcomes.js）；
     未分胜负且没有确定结果的局面剔除。按整局切分，与策略头同一套切分。

用法：conda activate flygym && python gomoku/train_value.py
输出：results/gomoku/train_value.json；并把 value/value_bias 写进各臂的 linetable_<arm>.json
"""
import argparse, base64, json, os, time
import numpy as np
import pyarrow  # noqa: F401
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); R = os.path.join(ROOT, "results/gomoku")
ap = argparse.ArgumentParser()
ap.add_argument("--arms", nargs="*", default=["fly_intact", "fly_shuffled", "raw24", "rand_relu", "free_table"])
ap.add_argument("--steps", type=int, default=400)
ap.add_argument("--l2", nargs="*", type=float, default=[1e-4, 1e-3, 1e-2])
ap.add_argument("--train-seeds", nargs="*", type=int, default=[777, 778, 779])
ap.add_argument("--test-seeds", nargs="*", type=int, default=[780, 781, 782])
ap.add_argument("--tag", default="")
args = ap.parse_args(); torch.manual_seed(0)
WIN = 1e9

meta = json.load(open(f"{R}/ds2/dataset2.json")); S = meta["samples"]; n = len(S)
outc = json.load(open(f"{R}/ds2/outcomes.json"))["winner"]
off = np.fromfile(f"{R}/ds2/cand_off.u32", dtype=np.uint32).astype(np.int64)
codes = np.fromfile(f"{R}/ds2/cand_codes.u16", dtype=np.uint16).reshape(-1, 4).astype(np.int64)
seg = torch.from_numpy(np.repeat(np.arange(n), np.diff(off)))
game = np.array([s["g"] for s in S]); me = np.array([s["me"] for s in S])
best8 = np.array([max(v for _, v in s["s8"]) if s["s8"] else 0 for s in S], dtype=np.float64)
forced = np.abs(best8) >= WIN / 2
w = np.array([outc[g] for g in game])
y = np.where(forced, best8 > 0, w == me).astype(np.float32)
use = forced | (w != 0)
test = (game >= meta["test_from_game"]) & use; tr_all = (game < meta["test_from_game"]) & use
val_from = int(meta["test_from_game"] * 0.9); val = tr_all & (game >= val_from); tr = tr_all & (game < val_from)
print(f"局面 {n}：确定结果 {int(forced.sum())}，用终局胜负 {int((use & ~forced).sum())}，剔除 {int((~use).sum())}；训练 {tr.sum()} / 验证 {val.sum()} / 测试 {test.sum()}；正例占比 {y[use].mean():.3f}")

lm = json.load(open(f"{R}/linefeat_intact_s777.json")); allc = np.array(lm["codes"], dtype=np.int64)
row = np.full(65536, -1, dtype=np.int64); row[allc] = np.arange(len(allc)); NP = len(allc)
A_idx = torch.from_numpy(row[codes]); yt = torch.from_numpy(y)
def load_feat(a, s): return np.sqrt(np.fromfile(f"{R}/linefeat_{a}_s{s}.bin", dtype=np.uint8).reshape(NP, -1).astype(np.float32))
def raw24():
    X = np.zeros((NP, 24), dtype=np.float32)
    for k in range(8):
        v = (allc >> (2 * k)) & 3
        for s in (1, 2, 3): X[:, k * 3 + s - 1] = (v == s)
    return X
def feats(arm):
    if arm in ("fly_intact", "fly_shuffled"):
        a = arm.split("_")[1]; tr_ = np.mean([load_feat(a, s) for s in args.train_seeds], axis=0)
        have = [s for s in args.test_seeds if os.path.exists(f"{R}/linefeat_{a}_s{s}.bin")]
        te_ = np.mean([load_feat(a, s) for s in have], axis=0) if have else tr_; keep = tr_.sum(0) > 0
    elif arm == "raw24": tr_ = te_ = raw24(); keep = np.ones(24, bool)
    else:
        dim = int((np.mean([load_feat("intact", s) for s in args.train_seeds], axis=0).sum(0) > 0).sum())
        g = np.random.default_rng(20260919); W = g.normal(size=(24, dim)).astype(np.float32); b = g.normal(size=dim).astype(np.float32)
        tr_ = te_ = np.maximum(raw24() @ W + b, 0); keep = np.ones(dim, bool)
    mu = tr_[:, keep].mean(0); sd = tr_[:, keep].std(0) + 1e-6
    return {"train": torch.from_numpy((tr_[:, keep] - mu) / sd), "test": torch.from_numpy((te_[:, keep] - mu) / sd)}

def logit(g, b): return torch.zeros(n).scatter_add(0, seg, g[A_idx].sum(1)) + b
def auc(z, mask):
    s = z[mask]; t = y[mask]; o = np.argsort(s); r = np.empty(len(s)); r[o] = np.arange(1, len(s) + 1)
    n1 = t.sum(); n0 = len(t) - n1
    return round(float((r[t == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)), 4)
def report(z, mask):
    zz = z.detach().numpy(); acc = float(((zz[mask] > 0) == (y[mask] > 0.5)).mean())
    ll = float(torch.nn.functional.binary_cross_entropy_with_logits(z[torch.from_numpy(mask)], yt[torch.from_numpy(mask)]))
    return dict(acc=round(acc, 4), auc=auc(zz, mask), logloss=round(ll, 4))

out = dict(n_train=int(tr.sum()), n_val=int(val.sum()), n_test=int(test.sum()), n_forced=int(forced.sum()),
           majority_acc=round(float(max(y[test].mean(), 1 - y[test].mean())), 4), arms={})
trm, vam = torch.from_numpy(tr), torch.from_numpy(val)
for arm in args.arms:
    t0 = time.time(); P = None if arm == "free_table" else feats(arm); best = None
    for l2 in (args.l2 if arm != "free_table" else [1e-5, 1e-4]):
        wv = torch.zeros(NP if P is None else P["train"].shape[1], requires_grad=True); b = torch.zeros(1, requires_grad=True)
        G_ = (lambda which: wv) if P is None else (lambda which: P[which] @ wv)
        lr0 = 0.02 if P is None else 0.003
        opt = torch.optim.Adam([wv, b], lr=lr0); sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.steps, eta_min=lr0 * 0.05)
        curve = []
        for it in range(args.steps):
            opt.zero_grad(); z = logit(G_("train"), b)
            loss = torch.nn.functional.binary_cross_entropy_with_logits(z[trm], yt[trm]) + l2 * (wv ** 2).sum()
            loss.backward(); opt.step(); sch.step()
            if it % 40 == 0 or it == args.steps - 1:
                with torch.no_grad(): curve.append(dict(step=it, loss=round(float(loss), 4), val_acc=report(z, val)["acc"]))
        with torch.no_grad():
            v = report(logit(G_("train"), b), val)
            print(f"  {arm} l2={l2:g}  验证 准确率 {v['acc']:.3f}  AUC {v['auc']:.3f}", flush=True)
            if best is None or v["logloss"] < best[0]: best = (v["logloss"], l2, wv.detach().clone(), b.detach().clone(), curve, G_)
    _, l2, wv, b, curve, G_ = best
    with torch.no_grad():
        res = dict(l2=l2, dim=int(wv.shape[0]), curve=curve, test=report(logit(P["train"] @ wv if P else wv, b), test))
        if P: res["test_newseeds"] = report(logit(P["test"] @ wv, b), test)
        g_tab = (P["train"] @ wv if P else wv).numpy().astype(np.float32)
    f = f"{R}/linetable_{arm}{args.tag}.json"
    if os.path.exists(f):
        j = json.load(open(f)); j["value"] = base64.b64encode(g_tab.tobytes()).decode(); j["value_bias"] = float(b)
        if P and arm.startswith("fly"): j["w_v"] = base64.b64encode(wv.numpy().astype(np.float32).tobytes()).decode()
        json.dump(j, open(f, "w"))
    res["seconds"] = round(time.time() - t0, 1); out["arms"][arm] = res
    print(f"{arm:14} 维度 {res['dim']:5d}  测试 准确率 {res['test']['acc']:.3f}  AUC {res['test']['auc']:.3f}" + (f"（换一组种子：{res['test_newseeds']['acc']:.3f}）" if P else "") + f"   {res['seconds']} s", flush=True)
json.dump(out, open(f"{R}/train_value{args.tag}.json", "w"), ensure_ascii=False, indent=1)
print(f"多数类基线 {out['majority_acc']}  → results/gomoku/train_value{args.tag}.json")
