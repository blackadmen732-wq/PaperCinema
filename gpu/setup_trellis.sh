#!/usr/bin/env bash
# Runs ON the GPU pod: installs Microsoft TRELLIS (MIT) the way that worked (RTX 4090 / CUDA 12.1 / torch 2.4).
# Learned the hard way: nvdiffrast needs --no-build-isolation, kaolin needs --ignore-installed blinker,
# and libEGL/libusb come from apt. Writes /workspace/TRELLIS_OK when done.
set -e
(sleep 3600; runpodctl remove pod $RUNPOD_POD_ID) >/dev/null 2>&1 &     # self-destruct timer (AGENTS.md rule 1)
python -c 'import torch; torch.zeros(1).cuda()' || { echo 'BAD GPU: CUDA does not start. Terminate this pod and start another.'; exit 3; }
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/dev/null 2>&1
apt-get install -y -qq libegl1 libgl1 libgomp1 libusb-1.0-0 libx11-6 libxrender1 libxext6 libsm6 >/dev/null 2>&1
cd /workspace
[ -d TRELLIS ] || git clone --recursive -q https://github.com/microsoft/TRELLIS.git
cd TRELLIS
pip install -q torch==2.4.0 torchvision==0.19.0 --index-url https://download.pytorch.org/whl/cu121
export TORCH_CUDA_ARCH_LIST='8.9'
. ./setup.sh --basic --xformers --diffoctreerast --spconv --mipgaussian --kaolin --nvdiffrast || true
pip install -q xformers==0.0.27.post2 --index-url https://download.pytorch.org/whl/cu121
mkdir -p /tmp/extensions && cd /tmp/extensions
[ -d nvdiffrast ] || git clone -q https://github.com/NVlabs/nvdiffrast.git
[ -d diffoctreerast ] || git clone -q --recurse-submodules https://github.com/JeffreyXiang/diffoctreerast.git
[ -d mip-splatting ] || git clone -q https://github.com/autonomousvision/mip-splatting.git
pip install -q --no-build-isolation ./nvdiffrast ./diffoctreerast ./mip-splatting/submodules/diff-gaussian-rasterization/
cd /workspace/TRELLIS
pip install -q spconv-cu120
pip install -q --ignore-installed blinker kaolin -f https://nvidia-kaolin.s3.us-east-2.amazonaws.com/torch-2.4.0_cu121.html
pip install -q transformers==4.46.3 imageio imageio-ffmpeg easydict opencv-python-headless scipy ninja trimesh open3d xatlas pyvista pymeshfix igraph rembg onnxruntime
python -c "import torch; torch.zeros(1).cuda(); print(\"GPU OK\")" || { echo "BAD GPU: terminate this pod and start another"; exit 3; }
python -c 'import xformers, spconv, kaolin, nvdiffrast.torch, diff_gaussian_rasterization, diffoctreerast, transformers, rembg; print("TRELLIS deps OK")'
touch /workspace/TRELLIS_OK
