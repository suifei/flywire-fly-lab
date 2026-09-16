#!/usr/bin/env bash
# =============================================================================
# 赛博果蝇复现环境：Eon fly-brain（数字大脑） + FlyGym 2.1（3D 身体/复眼视觉）
#
#   bash setup.sh            # 自动判断：Linux+NVIDIA → 官方 GPU 环境；否则 → CPU 环境
#   bash setup.sh cpu        # 强制 CPU 环境（macOS / 无 GPU Linux）        【已在 M1 Pro 实测】
#   bash setup.sh gpu        # 官方 brain-fly 环境（Linux + NVIDIA CUDA 12.x）【未实测，照官方 README】
#   bash setup.sh flygym     # 只装 FlyGym 身体环境                           【已在 M1 Pro 实测】
#
# 会创建两个 conda 环境（Python 版本要求冲突，不能合并成一个 conda-forge 环境）：
#   brain-fly-cpu / brain-fly : Python 3.10, numpy 1.26（官方 environment.yml 锁定）
#   flygym                    : Python 3.12, numpy 2.x（flygym 2.1.0 要求 >=3.12）
#
# 硬件：16 GB 内存可舒适运行；单次实验实测峰值 3–4 GB。无需 GPU。
# =============================================================================
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
MODE="${1:-auto}"
FLY_BRAIN_COMMIT=a3db62f9436074e485c0278290c2164ed6150808   # 2026-08-29 "add LICENSE"，本次实测版本

source "$(conda info --base)/etc/profile.d/conda.sh"

if [[ "$MODE" == auto ]]; then
  if [[ "$(uname)" == Linux ]] && command -v nvidia-smi >/dev/null; then MODE=gpu; else MODE=cpu; fi
fi

# ---------------------------------------------------------------- 1. 代码与数据
mkdir -p "$ROOT/external" "$ROOT/logs" "$ROOT/results"
if [[ ! -d "$ROOT/external/fly-brain" ]]; then
  # 仓库 ~380 MB（含 97 MB 连接组 parquet），下载需要几分钟
  git clone https://github.com/eonsystemspbc/fly-brain.git "$ROOT/external/fly-brain"
  git -C "$ROOT/external/fly-brain" checkout "$FLY_BRAIN_COMMIT"
fi
# 公开细胞类型注释（Schlegel et al. 2024，与 FlyWire Codex 同源；Codex 本身下载需要 Google 登录）
ANN="$ROOT/external/flywire_annotations/Supplemental_file1_neuron_annotations.tsv"
if [[ ! -f "$ANN" ]]; then
  mkdir -p "$(dirname "$ANN")"
  curl -L -o "$ANN" \
    https://raw.githubusercontent.com/flyconnectome/flywire_annotations/main/supplemental_files/Supplemental_file1_neuron_annotations.tsv
fi

# ---------------------------------------------------------------- 2. 大脑环境
if [[ "$MODE" == cpu ]]; then
  # macOS 需要 Xcode Command Line Tools（Brian2 C++ standalone 要编译）：xcode-select --install
  # Linux 需要 g++：sudo apt-get install -y build-essential
  conda create -y -n brain-fly-cpu -c conda-forge \
    python=3.10 numpy=1.26.4 pandas pyarrow scipy matplotlib joblib tqdm brian2 pip cxx-compiler
  # 注意：不要 pip install torch！会和 conda-forge 的 llvm-openmp 冲突
  #   OMP: Error #15: Initializing libomp.dylib, but found libomp.dylib already initialized.
  # 用 conda-forge 的 pytorch（实测 2.13.0，可用 MPS）
  conda install -y -n brain-fly-cpu -c conda-forge pytorch
  conda run -n brain-fly-cpu python -c "import pyarrow, torch, brian2; print('torch', torch.__version__, 'brian2', brian2.__version__)"
elif [[ "$MODE" == gpu ]]; then
  # 官方路线（README: Ubuntu 22.04/WSL2 + RTX 4070 + CUDA 12.x 测试）
  sudo apt-get install -y pkg-config libffi-dev build-essential   # PyGeNN 源码编译需要
  export CUDA_PATH=${CUDA_PATH:-/usr/local/cuda-12.5}; export CUDA_HOME=$CUDA_PATH; export PATH=$CUDA_PATH/bin:$PATH
  conda env create -f "$ROOT/external/fly-brain/environment.yml"   # 环境名 brain-fly（brian2cuda 1.0a7 + torch cu126 + PyGeNN 5.4.0）
  # 可选：NEST GPU 需要按官方 README 从源码编译并拷贝 user_m1 模型；Brian2GeNN 用单独的 environment-brian2genn.yml
fi

# ---------------------------------------------------------------- 3. 身体环境（FlyGym 2.1 + MuJoCo 3.9）
if [[ "$MODE" == cpu || "$MODE" == gpu || "$MODE" == flygym ]]; then
  conda create -y -n flygym python=3.12
  # flygym 2.1.0 与 1.x API 不兼容（没有 SingleFlySimulation / Gymnasium 接口）；
  # 社区项目若写的是 1.x API，请改用 pip install flygym-gymnasium
  conda run -n flygym pip install "flygym==2.1.0"
  # 闭环原型 connectome_vision_loop.py 需要在同一进程里跑官方 TorchModel（这个环境里 pip torch 没有 OMP 冲突，实测 2.14.0）
  conda run -n flygym pip install torch pandas pyarrow
  # 无显示器的 Linux 服务器渲染复眼需要：export MUJOCO_GL=egl（或 osmesa）
  conda run -n flygym python -c "import flygym, mujoco, torch; print('mujoco', mujoco.__version__, 'torch', torch.__version__)"
fi

cat <<'EOF'

安装完成。最短上手路径：
  conda activate brain-fly-cpu
  python run_experiment.py --preset sugar --t_run 1          # 激活糖味神经元，看 MN9（进食）是否放电
  open results/sugar_brian2/figure.png

  conda activate flygym
  python flygym_vision_demo.py --duration 2                  # 3D 世界 + 复眼 + 行走
EOF
