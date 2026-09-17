"""Process-local configuration from env. Every CLI invocation re-reads this."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_MODEL_ID = "deepseek-ai/DeepSeek-OCR-2"
DEFAULT_PAGE_SIZE_TOKENS = 4000
# Rough chars-per-token for pagination only (not a model tokenizer).
CHARS_PER_TOKEN = 4


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def backend_name() -> str:
    """auto | mock | deepseek | llamacpp"""
    return (env("OCR_BACKEND", "auto") or "auto").strip().lower()


def llama_url() -> str:
    return (env("OCR_LLAMA_URL", "http://127.0.0.1:8090") or "http://127.0.0.1:8090").rstrip(
        "/"
    )


def llama_model() -> str:
    return env("OCR_LLAMA_MODEL", "ocr") or "ocr"


def llama_timeout_s() -> float:
    raw = env("OCR_LLAMA_TIMEOUT_S", "300") or "300"
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 300.0


def model_id() -> str:
    # Prefer local path under ~/models if the user set OCR_MODEL_PATH.
    path = env("OCR_MODEL_PATH")
    if path:
        return path
    return env("OCR_MODEL_ID", DEFAULT_MODEL_ID) or DEFAULT_MODEL_ID


def device() -> str:
    return (env("OCR_DEVICE", "auto") or "auto").strip().lower()


def cache_dir() -> Path:
    raw = env("OCR_CACHE_DIR")
    if raw:
        path = Path(raw).expanduser()
    else:
        xdg = env("XDG_CACHE_HOME")
        base = Path(xdg) if xdg else Path.home() / ".cache"
        path = base / "ocr-skill"
    path.mkdir(parents=True, exist_ok=True)
    return path


def work_root() -> Path:
    root = cache_dir() / "work"
    root.mkdir(parents=True, exist_ok=True)
    return root


def store_path() -> Path:
    return cache_dir() / "documents.sqlite"
