#!/usr/bin/env python
"""
段仓库：把“分析需要哪些段”和“盘上已经有哪些段”分开管理。

为什么要有这个文件：这一轮里“计划算出来的段集合”和“分析实际要用的段集合”对不上，出了三次问题——
  1. 类型代表神经元 Bract 不在论文 200 名单里，100 Hz 的单敲除段没进计划（分析时 KeyError）；
  2. hub_scan 保存的文件名是 stageA_*.npz，读取时却按 chunk_*.npz 匹配，312 个候选只读到 23 个（数据其实都在盘上）；
  3. 水通路双敲除前 12 名里的 CB0872 效应只有 4%，没进“补到 12 个实现”的名单，66 对里缺了 11 对。
前两次都是偶然发现的，第三次是因为我顺手数了对数。共同的毛病是：分析在缺数据时**静默降级**（跳过、或回退到基线），
所以缺口不会自己冒出来。这里的做法是反过来：分析先声明要用哪些段，仓库负责回答“缺哪些”，缺了就报错并列出来。

用法：
    repo = Repo([dir1, dir2, ...], watch={"mn9": idx})   # 索引所有 *.npz，不限文件名
    repo.need(keys)                                       # 返回缺失的 key（不静默）
    repo.get(key)                                         # 取值；缺了抛 KeyError（除非 default=）
    repo.fill(keys, make_screen, out_dir, tag)            # 只跑缺失的段并存盘
"""
import json
import math
import time
from pathlib import Path

import numpy as np


class Repo:
    def __init__(self, dirs, watch, K=20):
        import sugar_mn9_screen as S
        self.S, self.K, self.watch = S, K, dict(watch)
        self.data, self.files = {}, []
        for d in dirs:
            d = Path(d)
            if not d.exists():
                continue
            for p in sorted(d.glob("*.npz")):
                keys, rows = S.chunk_summary(p, self.watch)
                self.files.append(str(p))
                for k, v in zip(keys, rows):
                    self.data.setdefault(k, v)

    def __contains__(self, key):
        return tuple(key) in self.data

    def get(self, key, field=None, default="__raise__"):
        k = tuple(key)
        if k not in self.data:
            if default == "__raise__":
                raise KeyError(f"缺少段 {k}：分析需要它，但仓库里没有。先用 fill() 补跑，不要跳过。")
            return default
        v = self.data[k]
        return v if field is None else v[field]

    def need(self, keys):
        return [tuple(k) for k in keys if tuple(k) not in self.data]

    def fill(self, keys, make_screen, out_dir, tag, verbose=True):
        need = self.need(keys)
        if not need:
            if verbose:
                print(f"{tag}：无缺口", flush=True)
            return 0
        out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
        if verbose:
            print(f"{tag}：缺 {len(need)} 段，开始补跑（估计 {len(need) * 2.0 / 60:.0f} min）", flush=True)
        sc = self._screen if getattr(self, '_screen', None) is not None else make_screen()
        self._screen = sc            # 同一个仓库多次 fill 时复用同一个已编译的网络
        n_chunks = math.ceil(len(need) / self.K)
        t0 = time.time()
        for c in range(n_chunks):
            part = need[c * self.K:(c + 1) * self.K]
            counts, wall = sc.run_chunk(part)
            path = out_dir / f"{tag}_{c:04d}.npz"
            self.S.save_chunk(path, [self.S.key(*s) for s in part], counts, wall)
            keys_new, rows = self.S.chunk_summary(path, self.watch)
            for k, v in zip(keys_new, rows):
                self.data.setdefault(k, v)
            if verbose:
                el = time.time() - t0
                print(f"  {tag} 块 {c + 1}/{n_chunks}：{wall:.0f} s，累计 {el / 60:.1f} min", flush=True)
        return len(need)


def needed_keys(base, R, conditions, fi=0):
    """把“要比较的条件”翻译成必须存在的段：某个实现里被沉默的神经元全都不放电时，结果等于基线，不需要段。"""
    out = []
    for sil in conditions:
        sil = tuple(sorted(sil))
        for r in range(R):
            if sil and any(base[r][n] > 0 for n in sil):
                out.append((fi, r, sil))
    return list(dict.fromkeys(out))


def report(audits, path):
    total = sum(a["n_missing"] for a in audits)
    Path(path).write_text(json.dumps(dict(total_missing=total, audits=audits), ensure_ascii=False, indent=1))
    print(f"\n合计缺口 {total} 段；明细写入 {path}")
    for a in audits:
        flag = "✅" if a["n_missing"] == 0 else "❌"
        print(f"  {flag} {a['name']:24s} 需要 {a['n_required']:5d} 段，缺 {a['n_missing']}")
    return total
