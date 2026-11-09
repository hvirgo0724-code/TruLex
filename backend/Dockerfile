# 法律智慧大脑 —— 后端服务
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 系统依赖（pdfplumber 需要的 libffi 等已内置于 slim；psycopg-binary 无需编译）
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# 国内镜像源（阿里云），避免直连 PyPI 的 SSL 中断；可用 --build-arg 覆盖
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ENV PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_TRUSTED_HOST=mirrors.aliyun.com

RUN pip install --upgrade pip -i ${PIP_INDEX_URL} \
    && pip install -r requirements.txt -i ${PIP_INDEX_URL}

COPY . .

EXPOSE 8000

# 无状态可水平扩展：直接启动 FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]