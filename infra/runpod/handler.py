"""RunPod Serverless handler for SGLang inference.

Runs an SGLang OpenAI-compatible server as a subprocess at worker startup,
then proxies incoming RunPod requests to it. This lets RunPod's infrastructure
call our handler while SGLang manages GPU memory, KV cache, and batching.

Environment variables:
    MODEL_ID      — HuggingFace model ID (default: meta-llama/Meta-Llama-3-70B-Instruct)
    QUANTIZATION  — Quantization method (default: awq)
    TP_SIZE       — Tensor-parallel GPU count (default: 1)
    SGLANG_PORT   — Localhost port for the SGLang server (default: 30000)
    MAX_MODEL_LEN — Maximum sequence length override (optional)
"""

import json
import logging
import os
import subprocess
import sys
import time

import requests
import runpod

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("runpod_handler")

# ── Configuration from environment ──────────────────────────────────────────

MODEL_ID = os.environ.get("MODEL_ID", "meta-llama/Meta-Llama-3-70B-Instruct")
QUANTIZATION = os.environ.get("QUANTIZATION", "awq")
TP_SIZE = int(os.environ.get("TP_SIZE", "1"))
SGLANG_PORT = int(os.environ.get("SGLANG_PORT", "30000"))
MAX_MODEL_LEN = os.environ.get("MAX_MODEL_LEN", "")

SGLANG_BASE_URL = f"http://127.0.0.1:{SGLANG_PORT}"
COMPLETIONS_URL = f"{SGLANG_BASE_URL}/v1/chat/completions"

# Health-check settings
_STARTUP_TIMEOUT_SEC = 600  # 10 minutes max for model loading
_HEALTH_POLL_INTERVAL_SEC = 5

# Global reference to the SGLang subprocess
_sglang_process: subprocess.Popen | None = None


# ── SGLang Engine Lifecycle ─────────────────────────────────────────────────

def _build_sglang_cmd() -> list[str]:
    """Build the command to launch the SGLang server."""
    cmd = [
        sys.executable, "-m", "sglang.launch_server",
        "--model-path", MODEL_ID,
        "--port", str(SGLANG_PORT),
        "--host", "127.0.0.1",
        "--tp", str(TP_SIZE),
        # RadixAttention cache is enabled by default in SGLang
        "--trust-remote-code",
    ]

    if QUANTIZATION:
        cmd.extend(["--quantization", QUANTIZATION])

    if MAX_MODEL_LEN:
        cmd.extend(["--max-model-len", MAX_MODEL_LEN])

    return cmd


def _wait_for_server_ready() -> None:
    """Block until the SGLang server responds to health checks."""
    start = time.monotonic()
    while time.monotonic() - start < _STARTUP_TIMEOUT_SEC:
        try:
            resp = requests.get(f"{SGLANG_BASE_URL}/health", timeout=5)
            if resp.status_code == 200:
                logger.info("SGLang server is ready (took %.1fs)", time.monotonic() - start)
                return
        except requests.ConnectionError:
            pass
        except Exception as exc:
            logger.warning("Health check unexpected error: %s", exc)

        time.sleep(_HEALTH_POLL_INTERVAL_SEC)

    raise RuntimeError(
        f"SGLang server did not become ready within {_STARTUP_TIMEOUT_SEC}s"
    )


def start_engine() -> None:
    """Start the SGLang server subprocess and wait until it is ready.

    Called once at worker startup via module-level execution, NOT per request.
    """
    global _sglang_process  # noqa: PLW0603

    if _sglang_process is not None:
        logger.warning("SGLang process already running (pid=%d)", _sglang_process.pid)
        return

    cmd = _build_sglang_cmd()
    logger.info("Starting SGLang server: %s", " ".join(cmd))

    _sglang_process = subprocess.Popen(
        cmd,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    _wait_for_server_ready()
    logger.info(
        "SGLang engine loaded — model=%s, quantization=%s, tp=%d",
        MODEL_ID, QUANTIZATION, TP_SIZE,
    )


# ── Request Handling ────────────────────────────────────────────────────────

def _parse_input(event: dict) -> dict:
    """Extract and validate generation parameters from the RunPod event."""
    job_input = event.get("input", {})

    messages = job_input.get("messages")
    if not messages or not isinstance(messages, list):
        raise ValueError("'messages' is required and must be a non-empty list")

    return {
        "model": job_input.get("model", MODEL_ID),
        "messages": messages,
        "max_tokens": int(job_input.get("max_tokens", 1024)),
        "temperature": float(job_input.get("temperature", 0.7)),
        "top_p": float(job_input.get("top_p", 1.0)),
        "frequency_penalty": float(job_input.get("frequency_penalty", 0.0)),
        "presence_penalty": float(job_input.get("presence_penalty", 0.0)),
        "stream": bool(job_input.get("stream", False)),
    }


def _call_sglang(params: dict) -> dict:
    """Forward a non-streaming request to the local SGLang server."""
    payload = {
        "model": params["model"],
        "messages": params["messages"],
        "max_tokens": params["max_tokens"],
        "temperature": params["temperature"],
        "top_p": params["top_p"],
        "frequency_penalty": params["frequency_penalty"],
        "presence_penalty": params["presence_penalty"],
        "stream": False,
    }

    resp = requests.post(COMPLETIONS_URL, json=payload, timeout=300)
    resp.raise_for_status()
    data = resp.json()

    choice = data["choices"][0]
    usage = data.get("usage", {})

    return {
        "content": choice["message"]["content"],
        "finish_reason": choice.get("finish_reason", "stop"),
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }


def _stream_sglang(params: dict):
    """Forward a streaming request to the local SGLang server.

    Yields partial results using RunPod's generator protocol so that the
    caller receives incremental chunks.
    """
    payload = {
        "model": params["model"],
        "messages": params["messages"],
        "max_tokens": params["max_tokens"],
        "temperature": params["temperature"],
        "top_p": params["top_p"],
        "frequency_penalty": params["frequency_penalty"],
        "presence_penalty": params["presence_penalty"],
        "stream": True,
    }

    with requests.post(COMPLETIONS_URL, json=payload, stream=True, timeout=300) as resp:
        resp.raise_for_status()

        collected_content = ""
        finish_reason = "stop"
        last_chunk = {}

        for raw_line in resp.iter_lines(decode_unicode=True):
            if not raw_line or not raw_line.startswith("data: "):
                continue

            data_str = raw_line[6:].strip()
            if data_str == "[DONE]":
                break

            try:
                last_chunk = json.loads(data_str)
            except (ValueError, KeyError):
                continue

            delta = last_chunk.get("choices", [{}])[0].get("delta", {})
            content_piece = delta.get("content", "")

            if content_piece:
                collected_content += content_piece
                yield {"text": content_piece}

            chunk_finish = last_chunk.get("choices", [{}])[0].get("finish_reason")
            if chunk_finish:
                finish_reason = chunk_finish

        # SGLang may include usage in the final chunk before [DONE]
        usage = last_chunk.get("usage", {})
        yield {
            "done": True,
            "content": collected_content,
            "finish_reason": finish_reason,
            "usage": {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            },
        }


# ── RunPod Handler ──────────────────────────────────────────────────────────

def handler(event: dict):
    """RunPod serverless handler entry point.

    Non-streaming requests return a dict.
    Streaming requests return a generator that yields chunks
    via RunPod's generator protocol.
    """
    try:
        params = _parse_input(event)
    except (ValueError, TypeError, KeyError) as exc:
        return {"error": f"Invalid input: {exc}"}

    try:
        if params["stream"]:
            # RunPod generator protocol: yield dicts, the last one signals completion
            return _stream_sglang(params)
        else:
            result = _call_sglang(params)
            return result
    except requests.HTTPError as exc:
        logger.error("SGLang HTTP error: %s — %s", exc, exc.response.text if exc.response else "")
        return {"error": f"Inference engine error: {exc.response.status_code if exc.response else 'unknown'}"}
    except requests.ConnectionError:
        logger.error("Cannot connect to SGLang server at %s", SGLANG_BASE_URL)
        return {"error": "Inference engine unavailable — SGLang server is not responding"}
    except Exception as exc:
        logger.error("Unexpected error in handler: %s", exc, exc_info=True)
        return {"error": f"Internal error: {type(exc).__name__}: {exc}"}


# ── Worker Startup ──────────────────────────────────────────────────────────

# Start the SGLang engine once when the worker process loads this module.
# RunPod Serverless workers call the handler repeatedly; the engine stays warm.
logger.info("Initializing RunPod worker — loading SGLang engine...")
start_engine()

# Register the handler with runpod and start the worker loop.
# `return_aggregate_stream=True` lets RunPod collect generator yields properly.
runpod.serverless.start(
    {"handler": handler, "return_aggregate_stream": True}
)
