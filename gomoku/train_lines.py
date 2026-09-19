#!/usr/bin/env python3
"""
五子棋 v2 的读出层训练：线型 → 果蝇脑 → **线性读出** → 线型价值；落子分 = 4 条进攻线 + 4 条防守线的价值之和。

    落子分(局面, 候选点) = Σ_方向 exp(a[进攻线型]) + λ·Σ_方向 exp(a[防守线型])     防守线型 = 同一条线把我方/对方互换
    logit = log(落子分)          a = Φ̄·w = 每条线的**对数价值**
    Φ̄ = 14,641 种线型 × 果蝇脑下游神经元的发放特征（**不训练**），对 3 个泊松种子取试次平均

**两阶段训练（2026-09-19）**：
  阶段一  蒸馏「落子评分算法」：让 a 去拟合老师对**全部 14,641 种线型**的对数分值（岭回归，闭式解）。
          训练局面里只出现过 6,266 种线型；只用着法标签训练的话，其余 8,375 种不受任何约束、价值随意漂移，
          搜索一走进没见过的局面就崩（实测：成五类的均值被学成 −6.67，想 2 步以上 0:16）。
  阶段二  着法微调：从阶段一出发，用深度 8 老师的最佳着做交叉熵微调；
          加锚定项 μ·mean((a − a_阶段一)²) 把没见过的线型拴住。--anchor 0 --init zero 可关掉两者作对照。

**为什么是「指数之和」而不是「直接相加」（2026-09-19 改，--form sum 保留旧形式作对照）**：
直接相加时一条活四线会被同一个点上另外三条空线稀释。用老师自己的分值取对数做成"理想表"、按直接相加去下，
只看 1 步对旧老师 1–15——形式本身就错。取指数后最强的那条线自动压过其余，与老师、与经典引擎同一形式；
学到的 exp(a) 就是线型价值，可以原样放进搜索的叶子估值，不需要任何手选换算。

**为什么只学一张表（2026-09-19 改）**：第一版学两张表 a、dv。但进攻线型与防守线型一一对应，
读出层真正能被数据约束的只有 a[c] + dv[swap(c)] 这个和——两张表各自是**不可识别**的
（实测：单看进攻表，「成五」均值 −0.68、「无」+0.17）。直觉下法只用和，不受影响；
搜索的叶子估值要单独用进攻表，于是想 3 步反而 0:20 全败。现在只学一张进攻价值表 a，
防守价值 = λ × 对手的进攻价值（λ 是一个学出来的标量）。这也是经典五子棋引擎的做法。
--untied 保留旧的两张表参数化，只作对照。

损失：对每个局面的全部合法候选点做 softmax，交叉熵对准老师 v2（深度 8 搜索）的最佳着。
对 (w_a, w_d) 是凸问题。这正是 ztxz16/renju 的「棋型系数 + 预测准确率」路线，只是棋型特征换成了果蝇脑的放电。

臂（同一份数据、同一个损失、同一套超参扫描）：
  fly_intact    真实连接组的特征
  fly_shuffled  打乱接线（保出度与权重）的特征
  raw24         不经过脑子：24 个输入通道的 0/1（线性读出在没有脑子时能拿到的全部）
  rand_relu     一个与果蝇脑同维度的**随机** ReLU 展开（"随便一个非线性网络"行不行）
  free_table    每种线型一个自由参数（这个架构的上限，14,641×2 个参数）
  teacher_table 不训练：老师自己的线型分值（不含组合加分），当参照

判据（**2026-09-19 写在跑之前**）：
  A 棋力达标   fly_intact 贪心（只看一步）对旧老师胜率 ≥ 50%，对随机 ≥ 95%（旧版：0/40、26/40）   ← 由 play_lines.js 判
  B 脑子有用   fly_intact 的测试 top-1 比 raw24 高 ≥ 5 个百分点
  C 接线有用   fly_intact 的测试 top-1 比 fly_shuffled 高 ≥ 5 个百分点（对弈胜率另判）
  D 不是噪声哈希  换一组**没见过的泊松种子**提特征，top-1 掉幅 ≤ 5 个百分点
    （第一版：单种子、60 ms 窗，掉 32 个点；300 ms 窗，掉 17 个点；3 种子试次平均，掉 5.3 个点——都不过。
     现在：**噪声增广**——读出层训练时每一步随机抽 3 个训练种子（共 6 个）取平均，逼它只用跨种子稳定的成分；
     部署用训练种子的前 3 个的平均，测试用 3 个**从未参与训练**的种子的平均，两边都是 3 个、口径对齐。判据本身没动。）
按整局切分；超参（L2）在训练局的最后 10% 上选。

用法：conda activate flygym && python gomoku/train_lines.py [--label 8] [--arms ...] [--steps 400]
输出：results/gomoku/train_lines.json + results/gomoku/linetable_<arm>.json（线型价值表，供对弈与页面用）
"""
import argparse, base64, json, os, sys, time
import numpy as np
import pyarrow  # noqa: F401  （必须先于 torch）
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(ROOT, "results/gomoku")
ap = argparse.ArgumentParser()
ap.add_argument("--label", type=int, default=8)
ap.add_argument("--arms", nargs="*", default=["fly_intact", "fly_shuffled", "raw24", "rand_relu", "free_table", "teacher_table"])
ap.add_argument("--steps", type=int, default=400)
ap.add_argument("--tag", default="")
ap.add_argument("--ds", default="ds2")
ap.add_argument("--untied", action="store_true")
ap.add_argument("--form", default="lse", choices=["lse", "sum"])
ap.add_argument("--init", default="distill", choices=["distill", "zero"])
ap.add_argument("--init-from", default="")         # 自我迭代：从已有的表（linetable_*.json）的读出权重出发，锚定也拴在它上面
ap.add_argument("--anchor", type=float, default=1.0)
ap.add_argument("--lr", type=float, default=0.003)
ap.add_argument("--train-seeds", nargs="*", type=int, default=[777, 778, 779, 780, 781, 782])
ap.add_argument("--test-seeds", nargs="*", type=int, default=[783, 784, 785])
ap.add_argument("--feat-sets", nargs="*", default=[""])   # 特征集后缀，多个就横向拼接：""=视角1单时间窗，"_v1b3"=视角1分3段，"_v2b3"=视角2分3段
ap.add_argument("--deploy-k", type=int, default=3)     # 部署（页面、对弈）用训练种子的前 K 个做试次平均；测试组也是 K 个 → 口径对齐
ap.add_argument("--no-augment", action="store_true")
ap.add_argument("--feat-dir", default="")          # 特征所在子目录（默认 results/gomoku/ 本身）
ap.add_argument("--l2", nargs="*", type=float, default=[1e-5, 1e-4, 1e-3, 1e-2])
args = ap.parse_args()
torch.manual_seed(0); np.random.seed(0)

# ── 数据 ─────────────────────────────────────────────────────────────────
meta = json.load(open(f"{R}/{args.ds}/dataset2.json"))
S = meta["samples"]; n = len(S)
off = np.fromfile(f"{R}/{args.ds}/cand_off.u32", dtype=np.uint32).astype(np.int64)
cell = np.fromfile(f"{R}/{args.ds}/cand_cell.u8", dtype=np.uint8)
codes = np.fromfile(f"{R}/{args.ds}/cand_codes.u16", dtype=np.uint16).reshape(-1, 4).astype(np.int64)
NC = len(cell)
seg = np.repeat(np.arange(n), np.diff(off))                      # 候选点 → 局面
label_cell = np.array([s["best"][str(args.label)] for s in S])
label8 = np.array([s["best"]["8"] for s in S])
game = np.array([s["g"] for s in S])
def pos_of(lbl):                                                  # 每个局面里标签对应的候选点下标（全局）
    out = np.full(n, -1, dtype=np.int64)
    for k in range(n):
        w = np.nonzero(cell[off[k]:off[k + 1]] == lbl[k])[0]
        if len(w): out[k] = off[k] + w[0]
    return out
tgt, tgt8 = pos_of(label_cell), pos_of(label8)
ok = (tgt >= 0) & (tgt8 >= 0)
test = (game >= meta["test_from_game"]) & ok
tr_all = (game < meta["test_from_game"]) & ok
val_from = int(meta["test_from_game"] * 0.9)
val = tr_all & (game >= val_from); tr = tr_all & (game < val_from)
print(f"局面 {n}（标签不在候选里的 {int((~ok).sum())} 个已剔除）：训练 {tr.sum()} / 验证 {val.sum()} / 测试 {test.sum()}；候选点 {NC}")

# 线型编码 → 行号；防守线 = 互换视角
FD = os.path.join(R, args.feat_dir) if args.feat_dir else R
lm = json.load(open(f"{FD}/linefeat_intact{args.feat_sets[0]}_s777.json"))
allc = np.array(lm["codes"], dtype=np.int64); row = np.full(65536, -1, dtype=np.int64); row[allc] = np.arange(len(allc))
def swap(c):
    o = np.zeros_like(c)
    for k in range(8):
        v = (c >> (2 * k)) & 3
        o |= np.where(v == 1, 2, np.where(v == 2, 1, v)) << (2 * k)
    return o
A_idx = torch.from_numpy(row[codes]); D_idx = torch.from_numpy(row[swap(codes)])
assert (A_idx >= 0).all() and (D_idx >= 0).all(), "数据里出现了不在 14,641 表里的线型"
seg_t = torch.from_numpy(seg); NP = len(allc)

FEAT_META = []
def load_feat(arm, seed):
    parts = []; metas = []
    for fs_ in args.feat_sets:
        m = json.load(open(f"{FD}/linefeat_{arm}{fs_}_s{seed}.json"))
        assert m["codes"] == lm["codes"]
        parts.append(np.sqrt(np.fromfile(f"{FD}/linefeat_{arm}{fs_}_s{seed}.bin", dtype=np.uint8).reshape(m["rows"], m["cols"]).astype(np.float32)))
        metas.append(dict(view=m.get("view", 1), bins=m["bins"], cols=m["cols"], hz=m["hz"], ms=m["ms"]))
    if not FEAT_META: FEAT_META.extend(metas)
    return np.concatenate(parts, axis=1) if len(parts) > 1 else parts[0]

def raw24():
    X = np.zeros((NP, 24), dtype=np.float32)
    for k in range(8):
        v = (allc >> (2 * k)) & 3
        for s in (1, 2, 3): X[:, k * 3 + s - 1] = (v == s)
    return X

_ATT = np.array([0, 1, 10, 100, 120, 1500, 2000, 1e5, 1e7])
_cls = np.array(json.load(open(f"{R}/ds2/teacher_cls.json")))[allc]
PRIOR = torch.from_numpy(np.log(_ATT[_cls] + 1).astype(np.float32))          # 每种线型的目标对数价值（老师的评分算法）
ONES = torch.ones(NP, 1); CLS_T = torch.from_numpy(_cls.astype(np.int64))

AUG = not args.no_augment
def feats(arm):
    """返回 P = {"train": 部署用的 Φ̄（训练种子前 K 个的平均）, "test": 测试种子的 Φ̄, "per_seed": [每个训练种子的 Φ]}（已标准化），
    以及 (mu, sd, 保留的列)。统计量只用训练种子。"""
    per = None
    if arm in ("fly_intact", "fly_shuffled"):
        a = arm.split("_")[1]
        raw = [load_feat(a, s) for s in args.train_seeds]
        allm = np.mean(raw, axis=0); keep = allm.sum(0) > 0
        tr_ = np.mean(raw[:args.deploy_k], axis=0)
        te_ = np.mean([load_feat(a, s) for s in args.test_seeds], axis=0)
        mu = allm[:, keep].mean(0); sd = allm[:, keep].std(0) + 1e-6
        per = [torch.from_numpy(((r[:, keep] - mu) / sd).astype(np.float16)) for r in raw]   # 半精度存：4 个视角 × 6 个种子用 float32 要 2.6 GB
        del raw
    else:
        if arm == "raw24": tr_ = raw24(); keep = np.ones(24, bool)
        else:
            dim = int((np.mean([load_feat("intact", s) for s in args.train_seeds], axis=0).sum(0) > 0).sum())
            g = np.random.default_rng(20260919); W = g.normal(size=(24, dim)).astype(np.float32); b = g.normal(size=dim).astype(np.float32)
            tr_ = np.maximum(raw24() @ W + b, 0); keep = np.ones(dim, bool)
        te_ = tr_; mu = tr_[:, keep].mean(0); sd = tr_[:, keep].std(0) + 1e-6
    return {"train": torch.from_numpy((tr_[:, keep] - mu) / sd), "test": torch.from_numpy((te_[:, keep] - mu) / sd), "per_seed": per}, mu, sd, np.nonzero(keep)[0]

LSE = args.form == "lse"
def scores(a, dv, A=None, D=None):                               # 每个候选点的 logit
    A = A_idx if A is None else A; D = D_idx if D is None else D
    if LSE: return torch.logsumexp(torch.cat([a[A], dv[D]], dim=1), dim=1)     # dv = a + ln λ
    return a[A].sum(1) + dv[D].sum(1)
def seg_logsumexp(z):
    m = torch.full((n,), -1e30).scatter_reduce(0, seg_t, z, "amax")
    return m + torch.log(torch.zeros(n).scatter_add(0, seg_t, torch.exp(z - m[seg_t])))
def metrics(z, mask, t=tgt8):
    """top-1 / top-3：与**深度 8** 老师的最佳着一致（不管训练用的是哪个深度的标签）。向量化：名次 = 同局面里分数更高的候选数"""
    z = z.detach(); tt = torch.from_numpy(np.where(t >= 0, t, 0))
    rank = torch.zeros(n).scatter_add(0, seg_t, (z > z[tt][seg_t]).float()).numpy()[mask]
    return round(float((rank == 0).mean()), 4), round(float((rank < 3).mean()), 4)

tgt_t = torch.from_numpy(np.where(tgt >= 0, tgt, 0))
def loss_on(z, mask):
    m = torch.from_numpy(mask)
    return (seg_logsumexp(z) - z[tgt_t])[m].mean()

def train(arm, l2, steps):
    """返回 table(which) → (a, dv)。lse + tied：a = [Φ̄,1]·w，dv = a + ln λ。"""
    tied = not args.untied
    lam = torch.tensor(0.5 if LSE else 0.9, requires_grad=True)
    info = {}
    if arm == "free_table":
        a = (PRIOR.clone() if args.init == "distill" else torch.zeros(NP)).requires_grad_(True)
        a0 = a.detach().clone(); params = [a, lam]
        A_of = lambda which: a
    else:
        P, mu, sd, keep = FE[arm]; D = P["train"].shape[1]
        X = {k: torch.cat([v, ONES], 1) for k, v in P.items() if k != "per_seed"}  # 末列 = 偏置
        per = P["per_seed"] if (AUG and P.get("per_seed")) else None
        rng = np.random.default_rng(7)
        def draw():                                                            # 噪声增广：随机抽 K 个训练种子取平均
            idx = rng.choice(len(per), size=args.deploy_k, replace=False)
            acc = per[idx[0]].float()
            for i in idx[1:]: acc = acc + per[i].float()
            return torch.cat([acc / len(idx), ONES], 1)
        if args.init == "distill":                                             # 阶段一：岭回归闭式解（增广时把 8 次抽样叠起来一起解）
            reg = 10.0 * torch.eye(D + 1); reg[D, D] = 0
            if per:
                XtX = torch.zeros(D + 1, D + 1); Xty = torch.zeros(D + 1); M = 8
                for _ in range(M): Xd = draw(); XtX += Xd.T @ Xd / M; Xty += Xd.T @ PRIOR / M
                w0 = torch.linalg.solve(XtX + reg, Xty)
            else: w0 = torch.linalg.solve(X["train"].T @ X["train"] + reg, X["train"].T @ PRIOR)
            Xt = X["train"]
            fit = Xt @ w0; info["distill_r2"] = round(float(1 - ((fit - PRIOR) ** 2).sum() / ((PRIOR - PRIOR.mean()) ** 2).sum()), 4)
            info["distill_r2_newseeds"] = round(float(1 - ((X["test"] @ w0 - PRIOR) ** 2).sum() / ((PRIOR - PRIOR.mean()) ** 2).sum()), 4)
        else: w0 = torch.zeros(D + 1)
        if args.init_from:
            jj = json.load(open(f"{R}/{args.init_from}")); assert jj["keep"] == keep.tolist(), "保留的特征列不一致"
            w0 = torch.from_numpy(np.concatenate([np.frombuffer(base64.b64decode(jj["w_a"]), dtype=np.float32), [jj["bias"]]]).astype(np.float32))
            lam = torch.tensor(float(jj["lam"]), requires_grad=True)
        wa = w0.clone().requires_grad_(True); a0 = (X["train"] @ w0).detach(); params = [wa, lam]
        A_of = lambda which: (draw() if (which == "step" and per) else X["train" if which == "step" else which]) @ wa
    def table(which):
        aa = A_of(which)
        return (aa, aa + torch.log(lam.clamp_min(1e-3))) if LSE else (aa, lam * aa)
    with torch.no_grad():
        z0 = scores(*table("train")); info["stage1_val_top1"] = metrics(z0, val)[0]; info["stage1_test_top1"] = metrics(z0, test)[0]
        if EXT_READY(): info["stage1_wine_top1"] = EXT.top(*table("train"))[0]
    lr0 = 0.05 if arm == "free_table" else args.lr
    opt = torch.optim.Adam(params, lr=lr0)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=steps, eta_min=lr0 * 0.05)
    curve = []
    def snap(step, loss):
        with torch.no_grad():
            ad, dd = table("train"); zd = scores(ad, dd)
            curve.append(dict(step=step, loss=loss, train_top1=metrics(zd, tr)[0], val_top1=metrics(zd, val)[0], lam=round(float(lam), 4),
                              cls_logmean=[round(float(ad[CLS_T == c].mean()), 3) for c in range(9)]))   # 页面"播放训练过程"用：9 类棋形的平均对数价值
    snap(0, None)                                                # 第 0 步 = 只做完阶段一
    for it in range(steps):
        opt.zero_grad()
        aa, dv = table("step"); z = scores(aa, dv)                # "step" = 这一步用的特征（增广时是随机抽样的平均）
        loss = loss_on(z, tr) + l2 * (params[0] ** 2).sum() + args.anchor * ((aa - a0) ** 2).mean()
        loss.backward(); opt.step(); sched.step()
        if (it + 1) % 20 == 0 or it == steps - 1: snap(it + 1, round(float(loss), 4))
    return table, params, curve, float(lam), info

def EXT_READY(): return "EXT" in globals() and EXT is not None

# ── 外部考卷：Wine 引擎的着法（与我们的老师无关，只考不训）──────────────────
class Ext:
    def __init__(self, d):
        m = json.load(open(f"{R}/{d}/dataset2.json")); self.n = len(m["samples"])
        self.off = np.fromfile(f"{R}/{d}/cand_off.u32", dtype=np.uint32).astype(np.int64)
        cell_ = np.fromfile(f"{R}/{d}/cand_cell.u8", dtype=np.uint8)
        cd = np.fromfile(f"{R}/{d}/cand_codes.u16", dtype=np.uint16).reshape(-1, 4).astype(np.int64)
        self.A = torch.from_numpy(row[cd]); self.D = torch.from_numpy(row[swap(cd)])
        lbl = [s_["best"]["wine"] for s_ in m["samples"]]
        self.t = np.array([self.off[k] + np.nonzero(cell_[self.off[k]:self.off[k + 1]] == lbl[k])[0][0] for k in range(self.n)])
        self.random_top1 = round(float(np.mean(1 / np.diff(self.off))), 4)
        self.seg = torch.from_numpy(np.repeat(np.arange(self.n), np.diff(self.off))); self.tt = torch.from_numpy(self.t)
    def top(self, a, dv):
        z = scores(a, dv, self.A, self.D).detach()
        rank = torch.zeros(self.n).scatter_add(0, self.seg, (z > z[self.tt][self.seg]).float()).numpy()
        return round(float((rank == 0).mean()), 4), round(float((rank < 3).mean()), 4)
EXT = Ext("ds_wine") if os.path.exists(f"{R}/ds_wine/dataset2.json") else None
if EXT: print(f"外部考卷 Wine：{EXT.n} 个局面，随机水平 top-1 {EXT.random_top1}")

def teacher_table():
    ATT = [0, 1, 10, 100, 120, 1500, 2000, 1e5, 1e7]; DEF = [0, 1, 8, 80, 90, 1200, 300, 2e4, 1e6]
    cls = np.array(json.load(open(f"{R}/{args.ds}/teacher_cls.json")))   # 由 play_lines.js --dump-cls 导出
    a_ = torch.tensor([ATT[c] for c in cls[allc]], dtype=torch.float32); d_ = torch.tensor([DEF[c] for c in cls[allc]], dtype=torch.float32)
    return (torch.log(a_ + 1e-3), torch.log(d_ + 1e-3)) if LSE else (a_, d_)

out = dict(feat_sets=args.feat_sets, form=args.form, train_seeds=args.train_seeds, test_seeds=args.test_seeds, deploy_k=args.deploy_k, augment=AUG, label_depth=args.label, feat=dict(dir=args.feat_dir or ".", hz=lm["hz"], ms=lm["ms"], bins=lm["bins"]), wine_random_top1=(EXT.random_top1 if EXT else None), wine_n=(EXT.n if EXT else None), n_train=int(tr.sum()), n_val=int(val.sum()), n_test=int(test.sum()),
           random_top1=round(float(np.mean(1 / np.diff(off)[test])), 4), criteria=__doc__.split("判据")[1].split("训练用种子")[0].strip(), arms={})
FE = {}
for arm in args.arms:
    t0 = time.time()
    if arm == "teacher_table":
        a, dv = teacher_table(); z = scores(a, dv)
        out["arms"][arm] = dict(test_top1=metrics(z, test)[0], test_top3=metrics(z, test)[1], trained=False)
        if EXT: out["arms"][arm]["wine_top1"], out["arms"][arm]["wine_top3"] = EXT.top(a, dv)
        print(f"{arm:14} 测试 top-1 {out['arms'][arm]['test_top1']:.3f}  top-3 {out['arms'][arm]['test_top3']:.3f}  Wine top-1 {out['arms'][arm].get('wine_top1')}（不训练）"); continue
    if arm != "free_table": FE[arm] = feats(arm)
    sweep = []
    for l2 in (args.l2 if arm != "free_table" else [1e-6, 1e-5]):
        table, params, curve, lam, info = train(arm, l2, args.steps)
        sweep.append((curve[-1]["val_top1"], l2, table, params, curve, lam, info))
        print(f"  {arm} l2={l2:g}  训练 {curve[-1]['train_top1']:.3f}  验证 {curve[-1]['val_top1']:.3f}  λ={lam:.3f}", flush=True)
    _, l2, table, params, curve, lam, info = max(sweep, key=lambda x: x[0])
    with torch.no_grad():
        res = dict(l2=l2, dim=int(params[0].shape[0]), tied=not args.untied, lam=round(lam, 4), **info, curve=curve, sweep=[dict(l2=s_[1], val_top1=s_[0]) for s_ in sweep])
        for which in ("train", "test"):
            a, dv = table(which); z = scores(a, dv); t1, t3 = metrics(z, test)
            res[f"test_top1_{which}seeds"] = t1; res[f"test_top3_{which}seeds"] = t3
        res["test_top1"] = res["test_top1_trainseeds"]; res["seed_drop"] = round(res["test_top1_trainseeds"] - res["test_top1_testseeds"], 4)
        a, dv = table("train")
        if EXT: res["wine_top1"], res["wine_top3"] = EXT.top(a, dv)
        if EXT: res["wine_top1_testseeds"] = EXT.top(*table("test"))[0]
        full_a = np.zeros(65536, dtype=np.float32); full_d = np.zeros(65536, dtype=np.float32)
        if LSE:   # 导出的是**线性尺度**的线型价值：JS 里 att[c] + def[swap(c)] 逐线相加就是模型的落子分
            full_a[allc] = torch.exp(a.clamp(max=30)).numpy(); full_d[allc] = torch.exp(dv.clamp(max=30)).numpy()
        else:
            full_a[allc] = a.numpy(); full_d[allc] = dv.numpy()
        tab = dict(arm=arm, form=args.form, label_depth=args.label, l2=l2, tied=not args.untied, lam=lam, test_top1=res["test_top1"],
                   att=base64.b64encode(full_a[allc].tobytes()).decode(), deff=base64.b64encode(full_d[allc].tobytes()).decode(), codes=allc.tolist())
        if arm in ("fly_intact", "fly_shuffled"):                 # 读出权重：页面现场跑果蝇脑时用，结果必须与表一致
            P, mu, sd, keep = FE[arm]
            wfull = params[0].detach().numpy().astype(np.float32)
            tab.update(w_a=base64.b64encode(wfull[:-1].tobytes()).decode(), bias=float(wfull[-1]),
                       mu=base64.b64encode(mu.astype(np.float32).tobytes()).decode(), sd=base64.b64encode(sd.astype(np.float32).tobytes()).decode(),
                       keep=keep.tolist(), hz=lm["hz"], ms=lm["ms"], bins=lm["bins"], views=FEAT_META, seeds=args.train_seeds[:args.deploy_k],
                       trained_on_seeds=args.train_seeds, augment=AUG)
        json.dump(tab, open(f"{R}/linetable_{arm}{args.tag}.json", "w"))
        if arm == "fly_intact":   # "另一只个体"：同一套读出权重，表来自测试种子那一组的试次平均（页面上的白蝇）
            a2, d2 = table("test"); fa = np.zeros(65536, dtype=np.float32); fd = np.zeros(65536, dtype=np.float32)
            fa[allc] = (torch.exp(a2.clamp(max=30)) if LSE else a2).numpy(); fd[allc] = (torch.exp(d2.clamp(max=30)) if LSE else d2).numpy()
            json.dump(dict(att=base64.b64encode(fa[allc].tobytes()).decode(), deff=base64.b64encode(fd[allc].tobytes()).decode(), seeds=args.test_seeds),
                      open(f"{R}/linetable_{arm}_white{args.tag}.json", "w"))
    FE.pop(arm, None)
    res["seconds"] = round(time.time() - t0, 1); out["arms"][arm] = res
    print(f"{arm:14} 维度 {res['dim']:5d}  测试 top-1 {res['test_top1']:.3f}（换一组种子：{res['test_top1_testseeds']:.3f}）  top-3 {res['test_top3_trainseeds']:.3f}  Wine top-1 {res.get('wine_top1')}  λ={res['lam']}   {res['seconds']} s", flush=True)

A = out["arms"]
if all(k in A for k in ("fly_intact", "raw24", "fly_shuffled")):
    out["criterion_B_brain_helps"] = bool(A["fly_intact"]["test_top1"] - A["raw24"]["test_top1"] >= 0.05)
    out["criterion_C_wiring_helps_top1"] = bool(A["fly_intact"]["test_top1"] - A["fly_shuffled"]["test_top1"] >= 0.05)
    out["criterion_D_not_noise_hash"] = bool(A["fly_intact"]["seed_drop"] <= 0.05)
    print("判据 B 脑子有用:", out["criterion_B_brain_helps"], " C 接线有用(top-1):", out["criterion_C_wiring_helps_top1"], " D 不是噪声哈希:", out["criterion_D_not_noise_hash"])
json.dump(out, open(f"{R}/train_lines{args.tag}.json", "w"), ensure_ascii=False, indent=1)
print("→ results/gomoku/train_lines%s.json" % args.tag)
