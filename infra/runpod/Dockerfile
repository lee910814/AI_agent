# RunPod Serverless Worker — SGLang Inference Engine
#
# Base: RunPod's PyTorch image with CUDA pre-installed.
# This image runs on RunPod Serverless GPU workers (A100 80GB).
#
# Build:
#   docker build -t runpod-sglang-worker -f infra/runpod/Dockerfile .
#
# Environment variables (set in RunPod template):
#   MODEL_ID       — HuggingFace model ID (default: meta-llama/Meta-Llama-3-70B-Instruct)
#   QUANTIZATION   — Quantization method (default: awq)
#   TP_SIZE        — Tensor-parallel GPU count (default: 1)
#   HF_TOKEN       — HuggingFace token for gated models
#   SGLANG_PORT    — Internal server port (default: 30000)
#   MAX_MODEL_LEN  — Maximum sequence length override (optional)

FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

WORKDIR /app

# System dependencies for building native extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY infra/runpod/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy the handler
COPY infra/runpod/handler.py /app/handler.py

# Default environment variables
ENV MODEL_ID="meta-llama/Meta-Llama-3-70B-Instruct" \
    QUANTIZATION="awq" \
    TP_SIZE="1" \
    SGLANG_PORT="30000" \
    HF_HOME="/app/hf_cache" \
    PYTHONUNBUFFERED="1"

# RunPod serverless workers execute the handler module directly
CMD ["python", "-u", "/app/handler.py"]
