
FROM python:3.11-slim

WORKDIR /workspace

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# CPU version of PyTorch
RUN pip install --no-cache-dir \
    torch torchvision \
    --index-url https://download.pytorch.org/whl/cpu

# YOLO framework
RUN pip install --no-cache-dir ultralytics

RUN mkdir -p \
    /workspace/scripts \
    /workspace/output/datasets \
    /workspace/output/runs \
    /data/source \
    /data/predict

CMD ["python", "/workspace/scripts/train.py"]
