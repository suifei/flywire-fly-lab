"""
让新版 TensorFlow Probability（0.24）能加载 flybody 论文用 TF 2.8 / TFP 0.16 保存的策略（SavedModel 输出是 TFP 分布）。
TFP 0.16 注册的 TypeSpec 名是完整模块路径（tensorflow_probability.python.distributions.independent.Independent_ACTTypeSpec），
0.24 改成了短名（tfp.distributions.Independent_ACTTypeSpec）。这里在加载前把缺失的旧名逐个映射到同名类的新 TypeSpec。
只做名字映射；序列化字段若不兼容，加载会直接报错而不是静默出错。
"""
import re

import tensorflow as tf
import tensorflow_probability as tfp  # noqa: F401
from tensorflow.python.framework import type_spec_registry


def _touch_all():
    for mod in (tfp.distributions, tfp.bijectors):
        for n in dir(mod):
            try:
                getattr(mod, n)
            except Exception:
                pass


def load_policy(path, max_aliases=50):
    _touch_all()
    reg = type_spec_registry._NAME_TO_TYPE_SPEC
    aliased = []
    for _ in range(max_aliases):
        try:
            return tf.saved_model.load(str(path)), aliased
        except ValueError as e:
            m = re.search(r"'(tensorflow_probability\.python\.[\w.]+\.(\w+_ACTTypeSpec))'", str(e))
            if not m:
                raise
            old, short = m.group(1), m.group(2)
            cands = [n for n in reg if n.endswith("." + short)]
            if not cands or old in reg:
                raise
            reg[old] = reg[cands[0]]
            aliased.append((old, cands[0]))
    raise RuntimeError("TypeSpec 映射次数过多")
