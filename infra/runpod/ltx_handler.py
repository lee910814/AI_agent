"""RunPod Serverless handler for LTX-Video 13B (v0.9.7) video generation.

Loads the LTX-Video 13B pipeline at worker startup and generates videos
from text prompts and optional keyframe images.

Supports two modes:
  - Text-to-Video: prompt only
  - Image-to-Video: prompt + keyframe image(s)

Model repos (diffusers format, each ~48 GB):
  - dev:       Lightricks/LTX-Video-0.9.7-dev
  - distilled: Lightricks/LTX-Video-0.9.7-distilled

Environment variables:
    MODEL_VARIANT   — 'dev' (default) or 'distilled'
    TORCH_DTYPE     — Torch dtype (default: bfloat16)
    HF_TOKEN        — HuggingFace token for gated models (optional)
    HF_HOME         — HuggingFace cache directory (default: /app/hf_cache)
"""

import base64
import io
import logging
import os
import random
import time
from pathlib import Path

import requests
import runpod
import torch
from PIL import Image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ltx_handler")

# ── Configuration ──

MODEL_VARIANT = os.environ.get("MODEL_VARIANT", "dev")
TORCH_DTYPE_STR = os.environ.get("TORCH_DTYPE", "bfloat16")
TORCH_DTYPE = getattr(torch, TORCH_DTYPE_STR, torch.bfloat16)

# 실제 HuggingFace 레포 ID (diffusers 형식, 별도 레포)
_MODEL_REPOS = {
    "dev": "Lightricks/LTX-Video-0.9.7-dev",
    "distilled": "Lightricks/LTX-Video-0.9.7-distilled",
}

# 다운로드 시 필요한 파일만 명시적으로 지정 (200GB 사고 방지)
_ALLOW_PATTERNS = [
    "model_index.json",
    "transformer/*.json",
    "transformer/*.safetensors",
    "text_encoder/*.json",
    "text_encoder/*.safetensors",
    "vae/*.json",
    "vae/*.safetensors",
    "tokenizer/*",
    "scheduler/*",
]

# 절대 받지 않을 파일 (안전장치)
_IGNORE_PATTERNS = [
    "*.bin",             # safetensors만 사용
    "*.ckpt",
    "*.pt",
    "*.msgpack",
    "*.h5",
    "*.onnx",
    "*.mp4",
    "*.png",
    "*.jpg",
    "*.gif",
    "model-*",           # transformers 형식 중복 웨이트 제외
    "*.md",
    "LICENSE*",
    ".gitattributes",
]

# Global pipeline reference (loaded once at startup)
_pipe = None


# ── Model Download ──

def _download_model(repo_id: str, cache_dir: str) -> str:
    """모델을 allow_patterns로 필터링하여 다운로드. 이미 캐시되어 있으면 스킵."""
    from huggingface_hub import snapshot_download

    logger.info("Downloading model: %s (allow_patterns=%s)", repo_id, _ALLOW_PATTERNS)
    logger.info("Ignore patterns: %s", _IGNORE_PATTERNS)

    local_dir = snapshot_download(
        repo_id=repo_id,
        allow_patterns=_ALLOW_PATTERNS,
        ignore_patterns=_IGNORE_PATTERNS,
        cache_dir=cache_dir,
        resume_download=True,
    )

    # 다운로드 결과 크기 확인
    total_size = sum(
        f.stat().st_size for f in Path(local_dir).rglob("*") if f.is_file()
    )
    logger.info(
        "Model cached at %s (total size: %.1f GB)",
        local_dir,
        total_size / (1024**3),
    )

    return local_dir


# ── Pipeline Loading ──

def load_pipeline():
    """Load LTX-Video 13B pipeline onto GPU. Called once at worker startup."""
    global _pipe  # noqa: PLW0603

    repo_id = _MODEL_REPOS.get(MODEL_VARIANT)
    if not repo_id:
        raise ValueError(
            f"Unknown MODEL_VARIANT: {MODEL_VARIANT}. "
            f"Must be one of: {list(_MODEL_REPOS.keys())}"
        )

    cache_dir = os.environ.get("HF_HOME", "/app/hf_cache")
    logger.info(
        "Loading LTX-Video 13B pipeline: %s (dtype=%s, cache=%s)",
        repo_id, TORCH_DTYPE_STR, cache_dir,
    )

    start = time.monotonic()

    # Step 1: 필요한 파일만 정확히 다운로드
    local_dir = _download_model(repo_id, cache_dir)

    # Step 2: 로컬 캐시에서 파이프라인 로드 (추가 다운로드 없음)
    try:
        from diffusers import LTXPipeline

        _pipe = LTXPipeline.from_pretrained(
            local_dir,
            torch_dtype=TORCH_DTYPE,
            local_files_only=True,  # 추가 다운로드 차단
        )
    except (ImportError, Exception) as exc:
        logger.warning("LTXPipeline failed (%s), trying DiffusionPipeline", exc)
        from diffusers import DiffusionPipeline

        _pipe = DiffusionPipeline.from_pretrained(
            local_dir,
            torch_dtype=TORCH_DTYPE,
            local_files_only=True,
        )

    # A40 48GB: CPU offload로 메모리 효율적 사용
    # transformer(26GB) + text_encoder(19GB) + VAE(2.5GB) = 47.5GB
    # offload 시 GPU에는 한 컴포넌트만 올라감
    _pipe.enable_model_cpu_offload()

    elapsed = time.monotonic() - start
    logger.info("Pipeline loaded in %.1fs (variant=%s)", elapsed, MODEL_VARIANT)


# ── Image Helpers ──

def _download_image(url: str) -> Image.Image:
    """Download an image from a URL and return as PIL Image."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("RGB")


def _encode_video_base64(frames: list, fps: int) -> str:
    """Encode frames to MP4 and return base64 string."""
    import tempfile

    try:
        import imageio.v3 as iio
    except ImportError:
        import imageio as iio

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        import numpy as np

        np_frames = []
        for frame in frames:
            if isinstance(frame, Image.Image):
                np_frames.append(np.array(frame))
            elif hasattr(frame, "numpy"):
                np_frames.append(frame.numpy())
            elif isinstance(frame, np.ndarray):
                np_frames.append(frame)
            else:
                np_frames.append(np.array(frame))

        iio.imwrite(tmp_path, np_frames, fps=fps, codec="libx264")

        with open(tmp_path, "rb") as f:
            video_bytes = f.read()
        return base64.b64encode(video_bytes).decode("ascii")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ── Generation ──

def _generate(params: dict) -> dict:
    """Run the LTX-Video pipeline with the given parameters."""
    prompt = params["prompt"]
    negative_prompt = params.get("negative_prompt", "")
    width = params.get("width", 768)
    height = params.get("height", 512)
    num_frames = params.get("num_frames", 97)
    frame_rate = params.get("frame_rate", 24)
    num_inference_steps = params.get("num_inference_steps", 40)
    guidance_scale = params.get("guidance_scale", 3.0)
    seed = params.get("seed")
    keyframes = params.get("keyframes", [])

    if seed is None:
        seed = random.randint(0, 2**32 - 1)

    generator = torch.Generator("cuda").manual_seed(seed)

    logger.info(
        "Generating: %dx%d, %d frames, %d steps, guidance=%.1f, seed=%d, keyframes=%d",
        width, height, num_frames, num_inference_steps, guidance_scale, seed, len(keyframes),
    )

    start = time.monotonic()

    gen_kwargs = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "width": width,
        "height": height,
        "num_frames": num_frames,
        "num_inference_steps": num_inference_steps,
        "guidance_scale": guidance_scale,
        "generator": generator,
    }

    # Image-to-video: use first keyframe as conditioning image
    if keyframes and len(keyframes) >= 1:
        first_kf = keyframes[0]
        image = _download_image(first_kf["image_url"])
        image = image.resize((width, height))
        gen_kwargs["image"] = image

    output = _pipe(**gen_kwargs)

    elapsed = time.monotonic() - start
    logger.info("Generation completed in %.1fs", elapsed)

    # Extract frames
    if hasattr(output, "frames"):
        frames = output.frames
        if isinstance(frames, list) and len(frames) > 0:
            if isinstance(frames[0], list):
                frames = frames[0]
    else:
        frames = output.images if hasattr(output, "images") else []

    video_b64 = _encode_video_base64(frames, frame_rate)

    file_size = len(base64.b64decode(video_b64))
    duration = num_frames / frame_rate

    return {
        "video_base64": video_b64,
        "metadata": {
            "seed": seed,
            "duration": round(duration, 2),
            "file_size": file_size,
            "num_frames": num_frames,
            "resolution": f"{width}x{height}",
            "model_variant": MODEL_VARIANT,
            "elapsed_seconds": round(elapsed, 1),
        },
    }


# ── RunPod Handler ──

def handler(event: dict) -> dict:
    """RunPod serverless handler entry point."""
    try:
        params = event.get("input", {})

        if not params.get("prompt"):
            return {"error": "Missing required field: prompt"}

        result = _generate(params)
        return result

    except Exception as exc:
        logger.error("Handler error: %s", exc, exc_info=True)
        return {"error": f"{type(exc).__name__}: {exc}"}


# ── Worker Startup ──

logger.info("Initializing LTX-Video 13B worker (variant=%s)...", MODEL_VARIANT)
load_pipeline()

runpod.serverless.start({"handler": handler})
