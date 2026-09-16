#!/usr/bin/env python
"""
第 5 步 A：从 BANC v888（同一只雌蝇的脑 + 腹神经索连接组，Codex 公开下载）取出腹神经索子网络，
转成与 eonsystemspbc/fly-brain 相同的文件格式，好让 Shiu et al. 的 LIF 代码（run_experiment.py）直接运行。

保留的神经元（BANC “Super Class”）：ventral_nerve_cord_intrinsic、descending、ascending，以及 Class = leg_motor_neuron。
  —— 下行神经元的上游（大脑）被去掉：实验里直接用 Poisson 刺激下行神经元；感觉传入也被去掉：没有本体感觉反馈。
突触符号（沿用 Shiu et al. 的约定，BANC 连接表的 nt_type 列为空，所以用突触前神经元的预测递质）：
  GABA、GLUT → −1；其余（ACH、DA、SER、OCT、HIST、未知）→ +1。
输出（模仿 fly-brain 仓库目录，run_experiment.py 通过 FLY_BRAIN_REPO 环境变量读取）：
  external/banc_vnc/data/2025_Completeness_783.csv    （文件名沿用，内容为 BANC root_id）
  external/banc_vnc/data/2025_Connectivity_783.parquet
  external/banc_vnc/code → external/fly-brain/code（符号链接，复用 Shiu 模型代码）
  external/banc_vnc/neurons_vnc.csv                   （保留神经元的 BANC 注释）
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "external" / "banc_888"
DST = ROOT / "external" / "banc_vnc"

n = pd.read_csv(SRC / "neurons.csv.gz", low_memory=False)
keep = n["Super Class"].isin(["ventral_nerve_cord_intrinsic", "descending", "ascending"]) | (n["Class"] == "leg_motor_neuron")
nv = n[keep].copy().reset_index(drop=True)
ids = nv["Root ID"].astype(np.int64).to_numpy()
id2i = {int(r): i for i, r in enumerate(ids)}

c = pd.read_csv(SRC / "connections_princeton.csv.gz", usecols=["pre_root_id", "post_root_id", "syn_count"])
c = c[c.pre_root_id.isin(id2i) & c.post_root_id.isin(id2i)]
c = c.groupby(["pre_root_id", "post_root_id"], as_index=False).syn_count.sum()   # 同一对神经元跨 neuropil 的多行合并
nt = dict(zip(n["Root ID"].astype(np.int64), n["Predicted NT type"]))
sign = np.where(c.pre_root_id.map(nt).isin(["GABA", "GLUT"]), -1, 1)
con = pd.DataFrame({
    "Presynaptic_ID": c.pre_root_id.astype(np.int64), "Postsynaptic_ID": c.post_root_id.astype(np.int64),
    "Presynaptic_Index": c.pre_root_id.map(id2i).astype(np.int32), "Postsynaptic_Index": c.post_root_id.map(id2i).astype(np.int32),
    "Connectivity": c.syn_count.astype(np.int32), "Excitatory": sign.astype(np.int8),
    "Excitatory x Connectivity": (c.syn_count.to_numpy() * sign).astype(np.int32),
})
(DST / "data").mkdir(parents=True, exist_ok=True)
pd.DataFrame({"Completed": True}, index=pd.Index(ids, name="")).to_csv(DST / "data" / "2025_Completeness_783.csv")
con.to_parquet(DST / "data" / "2025_Connectivity_783.parquet")
nv.to_csv(DST / "neurons_vnc.csv", index=False)
link = DST / "code"
if not link.exists():
    link.symlink_to(ROOT / "external" / "fly-brain" / "code")
print(f"腹神经索子网络：{len(ids)} 神经元（" + "，".join(f"{k} {v}" for k, v in nv["Super Class"].value_counts().items()) + f"），"
      f"{len(con)} 条连接，{int(con.Connectivity.sum())} 个突触，抑制性连接 {float((con.Excitatory < 0).mean()):.0%}")
legmn = nv[nv["Class"] == "leg_motor_neuron"]
print("腿部运动神经元", len(legmn), "按功能：", legmn["Function"].value_counts().to_dict())
