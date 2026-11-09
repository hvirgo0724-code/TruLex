# 法律智慧大脑 —— 训练镜像（GPU）
# 基座：PyTorch 官方 CUDA 12.1 + cuDNN 8 开发镜像（Unsloth 官方推荐 CUDA 12.1）
# 构建：docker build -t trullex-training ./training
FROM pytorch/pytorch:2.4.1-cuda12.1-cudnn8-devel

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    WANDB_DISABLED=true \
    OUTPUT_ROOT=/models

# git 供 Unsloth 拉取依赖；libgomp1 供 bitsandbytes 运行时使用
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        libgomp1 \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# 先装依赖以复用构建缓存
COPY requirements.txt /workspace/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝训练代码（config / scripts / data）
COPY . /workspace

# 模型产物目录（docker-compose 以 model_repo 卷挂载到 /models）
RUN mkdir -p /models && chmod 777 /models

CMD ["bash"]