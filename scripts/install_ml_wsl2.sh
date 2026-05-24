#!/bin/bash
# Install vLLM + TensorRT in WSL2 Ubuntu 22.04
# GPU: RTX 2080 SUPER (sm_75), CUDA driver 566.14 (supports up to CUDA 12.7)
# Installs: CUDA 12.4 toolkit, Miniconda, PyTorch 2.4 CUDA, TensorRT 10.x, vLLM
set -e
LOG=/tmp/ml_install.log
exec > >(tee -a "$LOG") 2>&1

echo "======================================================"
echo "  LPAS ML Stack Install — $(date)"
echo "======================================================"

# ── 1. CUDA 12.4 toolkit ──────────────────────────────────
echo ""
echo "[1/5] Installing CUDA 12.4 toolkit..."
if ! dpkg -l cuda-toolkit-12-4 2>/dev/null | grep -q '^ii'; then
    wget -qO /tmp/cuda-keyring.deb \
        https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
    dpkg -i /tmp/cuda-keyring.deb
    apt-get update -q
    apt-get install -y cuda-toolkit-12-4 libcudnn8 libcudnn8-dev
    echo 'export PATH=/usr/local/cuda-12.4/bin:$PATH' >> ~/.bashrc
    echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.4/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
    echo "CUDA 12.4 installed."
else
    echo "CUDA 12.4 already installed, skipping."
fi
export PATH=/usr/local/cuda-12.4/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda-12.4/lib64:$LD_LIBRARY_PATH

# ── 2. Miniconda ──────────────────────────────────────────
echo ""
echo "[2/5] Installing Miniconda..."
if [ ! -f ~/miniconda3/bin/conda ]; then
    wget -qO /tmp/miniconda.sh \
        https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
    bash /tmp/miniconda.sh -b -p ~/miniconda3
    ~/miniconda3/bin/conda init bash
    echo "Miniconda installed."
else
    echo "Miniconda already installed, skipping."
fi
source ~/miniconda3/etc/profile.d/conda.sh

# ── 3. Python 3.11 env ────────────────────────────────────
echo ""
echo "[3/5] Creating conda env 'ml' (Python 3.11)..."
if ! conda env list | grep -q '^ml '; then
    conda create -n ml python=3.11 -y
    echo "Env 'ml' created."
else
    echo "Env 'ml' already exists, skipping."
fi
conda activate ml

# ── 4. PyTorch 2.4 with CUDA 12.4 ────────────────────────
echo ""
echo "[4/5] Installing PyTorch 2.4 + CUDA 12.4..."
pip install torch==2.4.1 torchvision==0.19.1 torchaudio==2.4.1 \
    --index-url https://download.pytorch.org/whl/cu124
python -c "import torch; print('PyTorch', torch.__version__, '| CUDA available:', torch.cuda.is_available(), '| GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"

# ── 5a. TensorRT ──────────────────────────────────────────
echo ""
echo "[5a/5] Installing TensorRT 10.x..."
pip install tensorrt==10.6.0 tensorrt-cu12==10.6.0 tensorrt-cu12-bindings==10.6.0 tensorrt-cu12-libs==10.6.0
python -c "import tensorrt as trt; print('TensorRT', trt.__version__)"

# ── 5b. vLLM ─────────────────────────────────────────────
echo ""
echo "[5b/5] Installing vLLM (this takes a few minutes)..."
pip install vllm
python -c "import vllm; print('vLLM', vllm.__version__)"

# ── Done ──────────────────────────────────────────────────
echo ""
echo "======================================================"
echo "  Install complete! $(date)"
echo ""
echo "  To use:"
echo "    conda activate ml"
echo "    python -c \"import torch; print(torch.cuda.is_available())\""
echo "    python -m vllm.entrypoints.openai.api_server --model meta-llama/Llama-3.2-1B"
echo "======================================================"
