"""DeepSeek-OCR-2 adapter.

Heavy deps (torch, transformers) load only when this backend is selected.
Inference uses the official `model.infer` entry when present.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from ... import config, errors
from ...envelope import OcrSkillError
from ..models import OcrPageResult
from ..modes import DEEPSEEK_PROMPTS, MODES


class DeepSeekEngine:
    name = "deepseek"

    def __init__(
        self,
        model_id: str | None = None,
        device: str | None = None,
    ):
        self.model_id = model_id or config.model_id()
        self.device_pref = device or config.device()
        self._model = None
        self._tokenizer = None
        self._device: str | None = None

    def available(self) -> tuple[bool, str]:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except ImportError:
            return (
                False,
                "torch/transformers not installed; `uv sync --extra deepseek` or OCR_BACKEND=mock",
            )

        mid = self.model_id
        path = Path(mid)
        if path.exists():
            return True, f"local model path: {path}"
        return True, f"model id (will download on first use): {mid}"

    def _resolve_device(self) -> str:
        import torch

        pref = self.device_pref
        if pref == "cpu":
            return "cpu"
        if pref == "cuda":
            if not torch.cuda.is_available():
                raise OcrSkillError(
                    errors.ENGINE_UNAVAILABLE,
                    "OCR_DEVICE=cuda but CUDA is not available",
                    hint="Set OCR_DEVICE=cpu or install a CUDA torch build.",
                )
            return "cuda"
        # auto
        return "cuda" if torch.cuda.is_available() else "cpu"

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:
            raise OcrSkillError(
                errors.ENGINE_UNAVAILABLE,
                "DeepSeek backend requires torch and transformers",
                hint="Install with: uv sync --extra deepseek",
            ) from exc

        device = self._resolve_device()
        self._device = device
        model_id = self.model_id

        try:
            tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
            # Prefer flash attention when on CUDA; fall back if missing.
            attn = "flash_attention_2" if device == "cuda" else "eager"
            try:
                model = AutoModel.from_pretrained(
                    model_id,
                    _attn_implementation=attn,
                    trust_remote_code=True,
                    use_safetensors=True,
                )
            except Exception:
                model = AutoModel.from_pretrained(
                    model_id,
                    trust_remote_code=True,
                    use_safetensors=True,
                )
            model = model.eval()
            if device == "cuda":
                model = model.cuda().to(torch.bfloat16)
            else:
                model = model.to(torch.float32)
        except OcrSkillError:
            raise
        except Exception as exc:
            raise OcrSkillError(
                errors.ENGINE_UNAVAILABLE,
                f"failed to load DeepSeek-OCR-2: {exc}",
                retriable=True,
                hint="Check OCR_MODEL_PATH / OCR_MODEL_ID and GPU memory.",
            ) from exc

        self._tokenizer = tokenizer
        self._model = model

    def extract_page(
        self,
        image_path: str,
        *,
        page: int = 1,
        mode: str = "markdown",
    ) -> OcrPageResult:
        started = time.perf_counter()
        path = Path(image_path)
        if not path.is_file():
            raise OcrSkillError(errors.NOT_FOUND, f"page image not found: {path}")
        if mode not in MODES:
            raise OcrSkillError(
                errors.INVALID_INPUT,
                f"unknown mode: {mode}",
                hint=f"Use one of: {', '.join(MODES)}",
            )

        self._load()
        assert self._model is not None and self._tokenizer is not None
        prompt = DEEPSEEK_PROMPTS[mode]
        warnings: list[str] = []

        try:
            with tempfile.TemporaryDirectory(prefix="ocr-dpsk-") as tmp:
                # Official API writes artifacts under output_path when save_results=True.
                # We only need the returned text.
                if hasattr(self._model, "infer"):
                    res = self._model.infer(
                        self._tokenizer,
                        prompt=prompt,
                        image_file=str(path),
                        output_path=tmp,
                        base_size=1024,
                        image_size=768,
                        crop_mode=True,
                        save_results=False,
                    )
                    markdown = _coerce_text(res)
                else:
                    raise OcrSkillError(
                        errors.ENGINE_FAILED,
                        "loaded model has no infer() method; wrong checkpoint?",
                    )
        except OcrSkillError:
            raise
        except Exception as exc:
            raise OcrSkillError(
                errors.ENGINE_FAILED,
                f"DeepSeek inference failed: {exc}",
                retriable=True,
            ) from exc

        return OcrPageResult(
            page=page,
            markdown=markdown,
            mode=mode,
            backend=self.name,
            elapsed_ms=(time.perf_counter() - started) * 1000,
            warnings=warnings,
        )


def _coerce_text(res: object) -> str:
    if res is None:
        return ""
    if isinstance(res, str):
        return res
    if isinstance(res, dict):
        for key in ("markdown", "text", "result", "output"):
            if key in res and res[key] is not None:
                return str(res[key])
        return str(res)
    return str(res)
