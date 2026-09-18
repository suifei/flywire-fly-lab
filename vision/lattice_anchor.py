#!/usr/bin/env python3
"""用解剖位置把 flyvis 点阵与 FlyWire 柱坐标的朝向**定下来**（离线，只读）。

问题：`vision/connectome_from_flyvis.py` 至今跑全部 8 种朝向（交换轴 × 翻 x × 翻 y），
因为 flyvis 的点阵是**正六边形、六重对称**，几何上没有任何特征可以定向。
而 §18 实测「朝向间的标准差是重复间的 3–4 倍」——不确定性主要来自这里，不是噪声。

锚点只能是功能性的。§28.17 实测 flyvis 的 T4a 与 T5a 偏好方向都在 **270°**
（点阵平面 atan2(hy,hx)），T4b 在 90°。文献中 T4a/T5a 偏好**前→后**（progressive）运动，
T4b 偏好后→前。所以 flyvis 点阵的 90°/270° 轴 = 眼睛的**前后轴**。

于是只要知道 Codex 的 (p,q) 里哪个方向是前后，对齐就定了。本脚本用**解剖位置**求它：

  · 左右轴  = 左视叶质心 → 右视叶质心（定义性的，不需要假设 FAFB 轴向约定）
  · 腹侧    = 全脑质心 → GNG（食道下神经节）质心（GNG 在腹侧，是解剖事实）
  · 前后轴  = 上面两者的叉积（右手系下取符号后再核对）

然后把每个柱的 (p,q) 与其神经元三维质心做线性回归，得到 +p、+q 在三维里的方向，
投影到前后轴上，就知道 (p,q) 平面里哪个方向指向前方。

用法：python3 vision/lattice_anchor.py
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOX = np.array([4.0, 4.0, 40.0])          # 注释表位置是体素，4×4×40 nm

ann = pd.read_csv(ROOT / "external/flywire_annotations/Supplemental_file1_neuron_annotations.tsv",
                  sep="\t", low_memory=False)
ca = pd.read_csv(ROOT / "external/codex_783/column_assignment.csv.gz")

def nm(df, pre="pos"):
    return df[[f"{pre}_x", f"{pre}_y", f"{pre}_z"]].to_numpy(float) * VOX

# ── 1. 左右轴：两个视叶的质心之差 ──────────────────────────────
opt = ann[ann.super_class.astype(str).str.contains("optic", case=False, na=False)]
have = opt.dropna(subset=["pos_x", "pos_y", "pos_z"])
cL = nm(have[have.side == "left"]).mean(0)
cR = nm(have[have.side == "right"]).mean(0)
e_LR = cR - cL
e_LR /= np.linalg.norm(e_LR)

# ── 2. 腹侧：全脑质心 → GNG 质心 ───────────────────────────────
allpos = nm(ann.dropna(subset=["pos_x", "pos_y", "pos_z"]))
c_all = allpos.mean(0)
gng = ann[ann.cell_class.astype(str).str.contains("GNG", case=False, na=False) |
          ann.supertype.astype(str).str.contains("GNG", case=False, na=False) |
          ann.cell_type.astype(str).str.contains("GNG", case=False, na=False)]
gng = gng.dropna(subset=["pos_x", "pos_y", "pos_z"])
c_gng = nm(gng).mean(0)
e_V = c_gng - c_all
e_V -= e_V.dot(e_LR) * e_LR                 # 去掉左右分量
e_V /= np.linalg.norm(e_V)

# ── 3. 前后轴 = 叉积（方向先不定，下一步用解剖核对）──────────────
e_AP = np.cross(e_LR, e_V)
e_AP /= np.linalg.norm(e_AP)

print("解剖轴（FlyWire 纳米坐标下的单位向量）")
print(f"  左→右  {np.round(e_LR,3)}   两视叶质心相距 {np.linalg.norm(cR-cL)/1000:.0f} µm")
print(f"  背→腹  {np.round(e_V,3)}    GNG 神经元 {len(gng):,} 个，质心离全脑质心 {np.linalg.norm(c_gng-c_all)/1000:.0f} µm")
print(f"  前后轴 {np.round(e_AP,3)}   （= 左右 × 背腹）")

# 核对前后轴指向：触角叶(AL)在前、视叶在后侧方 —— 用 AL vs 中央复合体(CX) 定符号
al = ann[ann.cell_class.astype(str).str.contains("ALPN|ALLN|olfactory", case=False, na=False)]
al = al.dropna(subset=["pos_x", "pos_y", "pos_z"])
cx = ann[ann.cell_class.astype(str).str.contains("CX", case=False, na=False)]
cx = cx.dropna(subset=["pos_x", "pos_y", "pos_z"])
if len(al) and len(cx):
    d = (nm(al).mean(0) - nm(cx).mean(0)).dot(e_AP)
    print(f"  符号核对：触角叶质心 − 中央复合体质心 在前后轴上的投影 = {d/1000:+.0f} µm"
          f" → {'前后轴已指向前方' if d > 0 else '前后轴指向后方，取反'}（AL 在 CX 前方）")
    if d < 0:
        e_AP = -e_AP
else:
    print("  ⚠ 找不到 AL 或 CX 神经元，前后轴符号未核对")

# ── 4. 每个柱的三维质心 → (p,q) 在三维里的方向 ──────────────────
ann_pos = ann.dropna(subset=["pos_x", "pos_y", "pos_z"]).set_index("root_id")
out = {}
for side in ("left", "right"):
    d = ca[ca.hemisphere == side]
    d = d[d.root_id.isin(ann_pos.index)]
    P = nm(ann_pos.loc[d.root_id])
    g = pd.DataFrame({"column_id": d.column_id.to_numpy(), "p": d.p.to_numpy(), "q": d.q.to_numpy(),
                      "X": P[:, 0], "Y": P[:, 1], "Z": P[:, 2]}).groupby("column_id").mean()
    # 线性回归：三维位置 ≈ a + b_p·p + b_q·q
    A = np.column_stack([np.ones(len(g)), g.p.to_numpy(), g.q.to_numpy()])
    B, *_ = np.linalg.lstsq(A, g[["X", "Y", "Z"]].to_numpy(), rcond=None)
    bp, bq = B[1], B[2]
    # 残差：回归解释得好不好
    pred = A @ B
    resid = np.linalg.norm(g[["X", "Y", "Z"]].to_numpy() - pred, axis=1).mean()
    span = np.linalg.norm(g[["X", "Y", "Z"]].to_numpy() - g[["X", "Y", "Z"]].to_numpy().mean(0), axis=1).mean()
    # 投影到解剖轴
    def proj(v):
        return dict(前后=float(v @ e_AP), 背腹=float(-v @ e_V), 左右=float(v @ e_LR))
    ang_p = np.degrees(np.arctan2(bp @ (-e_V), bp @ e_AP))     # 在「前后-背腹」平面里的角度
    ang_q = np.degrees(np.arctan2(bq @ (-e_V), bq @ e_AP))
    out[side] = dict(柱数=int(len(g)), 每柱残差nm=float(resid), 柱间跨度nm=float(span),
                     p方向=proj(bp), q方向=proj(bq),
                     p角度_前为0背为90=float(ang_p), q角度_前为0背为90=float(ang_q),
                     p步长nm=float(np.linalg.norm(bp)), q步长nm=float(np.linalg.norm(bq)))
    print(f"\n{side} 眼：{len(g)} 个柱，回归残差 {resid/1000:.1f} µm / 跨度 {span/1000:.1f} µm")
    print(f"  +p 方向 → 前后 {bp@e_AP/1000:+.2f} 背腹 {-bp@e_V/1000:+.2f} 左右 {bp@e_LR/1000:+.2f} µm/步"
          f"   在前-背平面里 {ang_p:+.1f}°")
    print(f"  +q 方向 → 前后 {bq@e_AP/1000:+.2f} 背腹 {-bq@e_V/1000:+.2f} 左右 {bq@e_LR/1000:+.2f} µm/步"
          f"   在前-背平面里 {ang_q:+.1f}°")

(ROOT / "results/vision").mkdir(parents=True, exist_ok=True)
(ROOT / "results/vision/lattice_anchor.json").write_text(
    json.dumps({"解剖轴": {"左右": e_LR.tolist(), "背腹": e_V.tolist(), "前后": e_AP.tolist()},
                "说明": "角度约定：0° = 前方，90° = 背侧，在「前后-背腹」平面内",
                "结果": out}, ensure_ascii=False, indent=1))
print("\n→ results/vision/lattice_anchor.json")

# ══════════════════════════════════════════════════════════════════
# 5. 把解剖朝向和 §28.17 的 T4/T5 方向接起来，算出 8 种 ORIENT 里哪个对
# ══════════════════════════════════════════════════════════════════
# §28.17 实测（results/vision/t4t5_directions.json）：flyvis 点阵平面里
#   T4b 87°、T4c 149°、T4a 274°、T5a 263°、T5c 199°、T5d 333°
# 文献：T4a/T5a 偏好前→后（在视网膜上即朝**后方**），T4b 偏好后→前（朝前方），
#       T4c/T5c 朝上（背侧），T4d/T5d 朝下（腹侧）。
# 以「解剖角 = flyvis 角 + φ」拟合这四条约束，φ 取使总误差最小者；
# 同时检验**镜像**假设（解剖角 = c − flyvis 角），两者比较后取胜者。
def nearest(tree_pts, Q):
    """最近邻（721 个点，直接算，不引 scipy）"""
    d2 = ((Q[:, None, :] - tree_pts[None, :, :]) ** 2).sum(-1)
    return d2.argmin(1)

t4 = json.loads((ROOT / "results/vision/t4t5_directions.json").read_text())["定标"]
# 文献偏好方向（解剖角：0°=前，90°=背）
LIT = {"T4a": 180, "T5a": 180, "T4b": 0, "T4c": 90, "T5c": 90, "T5d": 270}
obs = {k: t4[k]["偏好方向"] for k in LIT if t4.get(k) and t4[k]["偏好方向"] is not None
       and (t4[k]["方向选择性"] or 0) >= 0.2}
def circ_err(pred, targ):
    return abs((pred - targ + 180) % 360 - 180)
best = None
for mode in ("旋转", "镜像"):
    for phi in range(0, 360):
        e = 0.0
        for k, o in obs.items():
            pred = (o + phi) % 360 if mode == "旋转" else (phi - o) % 360
            e += circ_err(pred, LIT[k]) ** 2
        e = (e / len(obs)) ** 0.5
        if best is None or e < best[2]:
            best = (mode, phi, e)
mode, phi, rms = best
print(f"\nflyvis 点阵 → 解剖方向：{mode} φ={phi}°，对 {len(obs)} 个有方向选择性的亚型 RMS 误差 {rms:.1f}°")
for k, o in sorted(obs.items()):
    pred = (o + phi) % 360 if mode == "旋转" else (phi - o) % 360
    print(f"    {k:4s} flyvis {o:6.1f}° → 解剖 {pred:5.1f}°   文献 {LIT[k]:3d}°   差 {circ_err(pred, LIT[k]):5.1f}°")

# 解剖角 → flyvis 角 的逆变换
def an2fv(a):
    return (a - phi) % 360 if mode == "旋转" else (phi - a) % 360

fv = np.load(ROOT / "results/vision/flyvis_loom_L.npz")
uv = np.c_[fv["u_T4a"].astype(float) + fv["v_T4a"].astype(float) / 2.0,
           fv["v_T4a"].astype(float) * np.sqrt(3) / 2.0]
uv_std = uv.std(0).mean()
ORIENTS = [(sw, sx, sy) for sw in (False, True) for sx in (1, -1) for sy in (1, -1)]

def normalize_like_code(P):
    Pc = P - P.mean(0)
    w, V = np.linalg.eigh(np.cov(Pc.T))
    V = V[:, ::-1]
    V *= np.sign(V[np.abs(V).argmax(0), range(2)])
    Q = Pc @ V
    return Q / Q.std(0)

agree = {k: [] for k in range(8)}
for side in ("left", "right"):
    d = ca[ca.hemisphere == side]
    d = d[d.root_id.isin(ann_pos.index)]
    P3 = nm(ann_pos.loc[d.root_id])
    g = pd.DataFrame({"column_id": d.column_id.to_numpy(), "p": d.p.to_numpy(), "q": d.q.to_numpy(),
                      "X": P3[:, 0], "Y": P3[:, 1], "Z": P3[:, 2]}).groupby("column_id").mean()
    C = g[["X", "Y", "Z"]].to_numpy()
    C = C - C.mean(0)
    # 解剖平面坐标（前=x，背=y）→ 转成 flyvis 点阵平面 → 缩放到与 uv 同量级
    A = np.c_[C @ e_AP, C @ (-e_V)]
    th = np.degrees(np.arctan2(A[:, 1], A[:, 0]))
    r = np.linalg.norm(A, axis=1)
    thf = np.radians(np.array([an2fv(t) for t in th]))
    Afv = np.c_[np.cos(thf), np.sin(thf)] * r[:, None]
    Afv = Afv / Afv.std(0).mean() * uv_std
    idxA = nearest(uv, Afv)                       # 解剖锚定给出的对应
    Z = normalize_like_code(np.c_[g.p.to_numpy() + g.q.to_numpy() / 2.0,
                                  g.q.to_numpy() * np.sqrt(3) / 2.0])
    for k, (sw, sx, sy) in enumerate(ORIENTS):
        Zo = Z[:, ::-1] if sw else Z
        Zo = Zo * [sx, sy] * uv_std
        idxk = nearest(uv, Zo)
        agree[k].append(np.linalg.norm(uv[idxk] - uv[idxA], axis=1).mean())

print("\n8 种 ORIENT 与解剖锚定的偏差（点阵单位，越小越对）")
print("  k  swap  sx  sy    左眼    右眼    平均")
rows = []
for k, (sw, sx, sy) in enumerate(ORIENTS):
    L, R = agree[k]
    rows.append((k, sw, sx, sy, L, R, (L + R) / 2))
    print(f"  {k}  {str(sw):5s} {sx:+d}  {sy:+d}  {L:7.2f} {R:7.2f} {(L+R)/2:7.2f}")
bestk = min(rows, key=lambda r: r[6])
second = sorted(rows, key=lambda r: r[6])[1]
print(f"\n→ 解剖锚定选出 ORIENT k={bestk[0]}（swap={bestk[1]}, sx={bestk[2]:+d}, sy={bestk[3]:+d}），"
      f"偏差 {bestk[6]:.2f}；次优 k={second[0]} 偏差 {second[6]:.2f}（相差 {second[6]/bestk[6]:.2f}×）")

res = json.loads((ROOT / "results/vision/lattice_anchor.json").read_text())
res["T4T5拟合"] = {"模式": mode, "phi": phi, "RMS误差度": round(rms, 1),
                   "用到的亚型": {k: {"flyvis": obs[k], "文献": LIT[k]} for k in obs}}
res["ORIENT偏差"] = [{"k": r[0], "swap": r[1], "sx": r[2], "sy": r[3],
                      "左眼": round(r[4], 3), "右眼": round(r[5], 3), "平均": round(r[6], 3)} for r in rows]
res["选定ORIENT"] = {"k": bestk[0], "swap": bestk[1], "sx": bestk[2], "sy": bestk[3],
                     "偏差": round(bestk[6], 3), "次优k": second[0], "次优偏差": round(second[6], 3)}
(ROOT / "results/vision/lattice_anchor.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
print("→ results/vision/lattice_anchor.json（已追加）")

# ── 5b. 量一下 normalize() 对点阵形状做了什么 ──────────────────────
# 这组数字出现在报告 §28.20 正文里，必须由脚本写进文件，不能是临时算的。
def basis_angle(Z, pv, qv):
    A = np.column_stack([np.ones(len(pv)), pv, qv])
    B, *_ = np.linalg.lstsq(A, Z, rcond=None)
    a1 = np.degrees(np.arctan2(B[1][1], B[1][0]))
    a2 = np.degrees(np.arctan2(B[2][1], B[2][0]))
    return a1, a2, abs((a2 - a1 + 180) % 360 - 180)

def cart2(a, b):
    return np.c_[a + b / 2.0, b * np.sqrt(3) / 2.0]

distort = {}
print("\nnormalize() 对点阵形状做了什么（报告 §28.20 的表）")
print("           +p角    +q角   基矢夹角  长宽比")
for side in ("left", "right"):
    d = ca[ca.hemisphere == side].drop_duplicates("column_id")
    pv, qv = d.p.to_numpy(float), d.q.to_numpy(float)
    P = cart2(pv, qv)
    rec = {}
    for nm_, M in (("原始cart", P), ("normalize后", normalize_like_code(P))):
        a1, a2, ang = basis_angle(M, pv, qv)
        sd = M.std(0)
        rec[nm_] = dict(p角=round(float(a1), 1), q角=round(float(a2), 1),
                        基矢夹角=round(float(ang), 1), 长宽比=round(float(sd.max() / sd.min()), 2))
        print(f"{side:5s} {nm_:12s} {a1:7.1f} {a2:7.1f} {ang:8.1f}° {sd.max()/sd.min():7.2f}")
    distort[side] = rec
fv_sd = uv.std(0)
distort["flyvis点阵长宽比"] = round(float(fv_sd.max() / fv_sd.min()), 2)
print(f"      flyvis 点阵长宽比 {fv_sd.max()/fv_sd.min():.2f}（正六边形应为 1.00）")

# 两种锚定映射的覆盖代价（报告里也引用了）
cover = {}
for sc in (1.0, 0.6):
    acc = []
    for side in ("left", "right"):
        d = ca[ca.hemisphere == side].drop_duplicates("column_id")
        pp = d.p.to_numpy(float) - np.median(d.p.to_numpy(float))
        qq = d.q.to_numpy(float) - np.median(d.q.to_numpy(float))
        Z = cart2(-pp, -qq) * sc
        idx = nearest(uv, Z)
        dist = np.linalg.norm(Z - uv[idx], axis=1)
        acc.append([float((dist < 1e-6).mean()), float((dist > 0.6).mean()),
                    len(set(idx.tolist())), len(d) / len(set(idx.tolist()))])
    m = np.array(acc).mean(0)
    cover[f"anchor×{sc}"] = dict(精确落格点=round(m[0] * 100, 1), 夹到边缘=round(m[1] * 100, 1),
                                 用到flyvis柱=int(round(m[2])), 每柱挤入真实柱=round(m[3], 2))
    print(f"      anchor×{sc}: 精确落格点 {m[0]*100:.1f}%  夹到边缘 {m[1]*100:.1f}%  "
          f"用到 {int(round(m[2]))}/721 个 flyvis 柱")

res = json.loads((ROOT / "results/vision/lattice_anchor.json").read_text())
res["normalize形变"] = distort
res["锚定映射覆盖"] = cover
(ROOT / "results/vision/lattice_anchor.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))

# ── 6. 更干净的判据：比**基矢方向**，而不是比对应关系 ────────────────
# 上面那个指标把朝向和形状归一化混在一起了（代码的 normalize 做 PCA + 各轴除以
# 标准差，是各向异性缩放，会改角度）。这里直接问：在每种 ORIENT 下，
# Codex 的 +p、+q 被送到 flyvis 平面的哪个方向？再换算回解剖角，和实测的
# +p≈113°、+q≈171° 比。四个数，噪声小得多。
print("\n基矢方向判据：每种 ORIENT 下 +p/+q 落到的解剖角（实测 +p≈%.0f° +q≈%.0f°）"
      % (np.mean([out[s]["p角度_前为0背为90"] for s in out]),
         np.mean([out[s]["q角度_前为0背为90"] for s in out])))
tgt_p = np.mean([out[s]["p角度_前为0背为90"] for s in out])
tgt_q = np.mean([out[s]["q角度_前为0背为90"] for s in out])
print("  k  swap  sx  sy     +p解剖角  +q解剖角    误差")
rows2 = []
for k, (sw, sx, sy) in enumerate(ORIENTS):
    errs = []
    ang = {}
    for side in ("left", "right"):
        d = ca[ca.hemisphere == side].drop_duplicates("column_id")
        Z = normalize_like_code(np.c_[d.p.to_numpy(float) + d.q.to_numpy(float) / 2.0,
                                      d.q.to_numpy(float) * np.sqrt(3) / 2.0])
        Zo = Z[:, ::-1] if sw else Z
        Zo = Zo * [sx, sy] * uv_std
        A = np.column_stack([np.ones(len(d)), d.p.to_numpy(float), d.q.to_numpy(float)])
        B, *_ = np.linalg.lstsq(A, Zo, rcond=None)
        for nm_, v in (("p", B[1]), ("q", B[2])):
            fvang = np.degrees(np.arctan2(v[1], v[0]))
            anang = (fvang + phi) % 360 if mode == "旋转" else (phi - fvang) % 360
            ang.setdefault(nm_, []).append(anang)
    ap = np.degrees(np.arctan2(np.mean(np.sin(np.radians(ang["p"]))), np.mean(np.cos(np.radians(ang["p"]))))) % 360
    aq = np.degrees(np.arctan2(np.mean(np.sin(np.radians(ang["q"]))), np.mean(np.cos(np.radians(ang["q"]))))) % 360
    e = (circ_err(ap, tgt_p % 360) ** 2 + circ_err(aq, tgt_q % 360) ** 2) ** 0.5 / 2 ** 0.5
    rows2.append((k, sw, sx, sy, ap, aq, e))
    print(f"  {k}  {str(sw):5s} {sx:+d}  {sy:+d}  {ap:10.1f} {aq:10.1f} {e:8.1f}°")
b2 = min(rows2, key=lambda r: r[6]); s2 = sorted(rows2, key=lambda r: r[6])[1]
print(f"\n→ 基矢判据选出 ORIENT k={b2[0]}（swap={b2[1]}, sx={b2[2]:+d}, sy={b2[3]:+d}），"
      f"误差 {b2[6]:.1f}°；次优 k={s2[0]} 误差 {s2[6]:.1f}°（相差 {s2[6]-b2[6]:.1f}°）")
res = json.loads((ROOT / "results/vision/lattice_anchor.json").read_text())
res["基矢判据"] = {"实测p角": round(float(tgt_p), 1), "实测q角": round(float(tgt_q), 1),
                   "各ORIENT": [{"k": r[0], "swap": r[1], "sx": r[2], "sy": r[3],
                                 "p解剖角": round(float(r[4]), 1), "q解剖角": round(float(r[5]), 1),
                                 "误差度": round(float(r[6]), 1)} for r in rows2],
                   "选定": {"k": b2[0], "误差度": round(float(b2[6]), 1),
                            "次优k": s2[0], "次优误差度": round(float(s2[6]), 1)}}
(ROOT / "results/vision/lattice_anchor.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
