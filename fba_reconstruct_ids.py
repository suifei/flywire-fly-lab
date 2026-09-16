#!/usr/bin/env python
"""
还原 neilt93/Fly-Brain-AI 缺失的神经元 ID 文件（它们被 .gitignore 忽略，从未提交）。

【推测，但已用仓库自带的旧版本文件验证过规则】
  * readout_ids_*.npy  = decoder_groups_*.json 所有分组 ID 的并集，升序、int64
      验证：readout_ids_v2.npy 与 decoder_groups_v2.json 并集完全一致（204 = 204，且已排序）
  * sensory_ids_*.npy  = channel_map_*.json 所有通道 ID（集合一致）
      验证：sensory_ids_v3.npy 与 channel_map_v3.json 集合一致（275 个），但原文件顺序未知。
      顺序无关：SensoryEncoder 按 ID 查位置（_id_to_idx），Brian2BrainRunner 用同一个数组建输入映射；
      不同顺序只改变 Poisson 随机数分配，统计上等价，不能逐位复现原作者结果。
  * 已知差异：README 称 v4 读出 389 个神经元，JSON 并集只有 350 个。
      多出的 39 个不在任何解码分组里，DescendingDecoder 用不到，不影响转向/前进指令。

用法：python fba_reconstruct_ids.py [版本名，默认 v4_looming]
"""
import json
import sys
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parent / "external" / "Fly-Brain-AI" / "plastic-fly" / "data"


def main(version="v4_looming"):
    cm = json.load(open(DATA / f"channel_map_{version}.json"))
    dg = json.load(open(DATA / f"decoder_groups_{version}.json"))
    sensory = np.array(list(dict.fromkeys(int(x) for v in cm.values() for x in v)), dtype=np.int64)
    readout = np.array(sorted({int(x) for v in dg.values() for x in v}), dtype=np.int64)
    for name, arr in [(f"sensory_ids_{version}.npy", sensory), (f"readout_ids_{version}.npy", readout)]:
        path = DATA / name
        if path.exists():
            old = np.load(path)
            print(f"{name} 已存在（{len(old)} 个），与还原结果集合一致: {set(old.tolist()) == set(arr.tolist())}，不覆盖")
            continue
        np.save(path, arr)
        print(f"写入 {name}: {len(arr)} 个 ID")
    print("通道:", {k: len(v) for k, v in cm.items()})
    print("解码分组:", {k: len(v) for k, v in dg.items()})


if __name__ == "__main__":
    main(*sys.argv[1:])
