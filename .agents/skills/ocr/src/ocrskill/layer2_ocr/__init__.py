"""Layer 2: OCR engines."""

from __future__ import annotations

from .. import config, errors
from ..envelope import OcrSkillError
from .adapters.deepseek import DeepSeekEngine
from .adapters.llamacpp import LlamaCppEngine
from .adapters.mock import MockEngine
from .models import OCR_CONTRACT_VERSION, OcrPageResult
from .modes import DEEPSEEK_PROMPTS, MODES
from .port import OCREngine

__all__ = [
    "OCR_CONTRACT_VERSION",
    "OCREngine",
    "OcrPageResult",
    "MODES",
    "DEEPSEEK_PROMPTS",
    "MockEngine",
    "DeepSeekEngine",
    "LlamaCppEngine",
    "build_engine",
]


def build_engine(name: str | None = None) -> OCREngine:
    """Resolve OCR_BACKEND (or override) to an engine instance.

    Preference for ``auto``:
    1. ``llamacpp`` if a llama-server answers /health (Vulkan GGUF stack)
    2. ``deepseek`` if torch/transformers are importable
    3. else error with install/start hints (never silently use mock for real work)
    """
    chosen = (name or config.backend_name()).strip().lower()
    if chosen == "mock":
        return MockEngine()
    if chosen == "deepseek":
        return DeepSeekEngine()
    if chosen == "llamacpp":
        return LlamaCppEngine()
    if chosen == "auto":
        llama = LlamaCppEngine()
        ok, detail = llama.available()
        if ok:
            return llama
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401

            return DeepSeekEngine()
        except ImportError:
            pass
        raise OcrSkillError(
            errors.ENGINE_UNAVAILABLE,
            "no OCR engine available (auto)",
            hint=(
                "Start the Vulkan stack: "
                "`docker compose -f docker/docker-compose.yml --env-file docker/.env up -d` "
                "then OCR_BACKEND=llamacpp, or install `uv sync --extra deepseek`, "
                f"or OCR_BACKEND=mock for tests. llamacpp: {detail}"
            ),
        )
    raise OcrSkillError(
        errors.CONFIG_ERROR,
        f"unknown OCR_BACKEND: {chosen}",
        hint="Use auto, mock, deepseek, or llamacpp.",
    )
