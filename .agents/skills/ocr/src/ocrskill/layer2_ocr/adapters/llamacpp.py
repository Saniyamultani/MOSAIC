"""llama.cpp server backend (Vulkan GGUF OCR via OpenAI multimodal API).

Talks to a running ``llama-server`` (see docker/docker-compose.yml), typically
``ghcr.io/ggml-org/llama.cpp:server-vulkan`` with DeepSeek-OCR-2 GGUF + mmproj.
No torch in this process; the GPU lives in the container.
"""

from __future__ import annotations

import base64
import mimetypes
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ... import config, errors
from ...envelope import OcrSkillError
from ..models import OcrPageResult
from ..modes import DEEPSEEK_PROMPTS, MODES


def _text_prompt(mode: str) -> str:
    """Map skill mode to the text half of a multimodal request.

    DeepSeek GGUF prompts still use the official family, but the ``<image>``
    token is supplied by the server when content includes image_url, so we
    strip a leading ``<image>\\n`` if present.
    """
    raw = DEEPSEEK_PROMPTS.get(mode, DEEPSEEK_PROMPTS["markdown"])
    if raw.startswith("<image>\n"):
        return raw[len("<image>\n") :].strip()
    return raw.strip()


class LlamaCppEngine:
    name = "llamacpp"

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout_s: float | None = None,
    ):
        self.base_url = (base_url or config.llama_url()).rstrip("/")
        self.model = model or config.llama_model()
        self.timeout_s = timeout_s if timeout_s is not None else config.llama_timeout_s()

    def available(self) -> tuple[bool, str]:
        health = f"{self.base_url}/health"
        try:
            req = Request(health, method="GET")
            with urlopen(req, timeout=min(self.timeout_s, 5.0)) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            return True, f"health ok at {health} ({body[:80]})"
        except Exception as exc:
            return (
                False,
                f"llama-server not reachable at {health}: {exc}. "
                "Start docker/ (see docker/README.md) or set OCR_LLAMA_URL.",
            )

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

        mime, _ = mimetypes.guess_type(str(path))
        if mime is None:
            mime = "image/png"
        data_b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        data_url = f"data:{mime};base64,{data_b64}"
        prompt = _text_prompt(mode)

        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.0,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }

        url = f"{self.base_url}/v1/chat/completions"
        try:
            import json

            body = json.dumps(payload).encode("utf-8")
            req = Request(
                url,
                data=body,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlopen(req, timeout=self.timeout_s) as resp:
                raw = resp.read().decode("utf-8")
            parsed = json.loads(raw)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
            raise OcrSkillError(
                errors.ENGINE_FAILED,
                f"llama-server HTTP {exc.code}: {detail[:500]}",
                retriable=exc.code >= 500,
            ) from exc
        except URLError as exc:
            raise OcrSkillError(
                errors.ENGINE_UNAVAILABLE,
                f"llama-server request failed: {exc}",
                retriable=True,
                hint=(
                    "Is ocr-llm up? "
                    "docker compose -f docker/docker-compose.yml "
                    "--env-file docker/.env up -d"
                ),
            ) from exc
        except Exception as exc:
            raise OcrSkillError(
                errors.ENGINE_FAILED,
                f"llama-server OCR failed: {exc}",
                retriable=True,
            ) from exc

        markdown = _message_content(parsed)
        return OcrPageResult(
            page=page,
            markdown=markdown,
            mode=mode,
            backend=self.name,
            elapsed_ms=(time.perf_counter() - started) * 1000,
            warnings=[],
        )


def _message_content(parsed: dict[str, Any]) -> str:
    try:
        content = parsed["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise OcrSkillError(
            errors.ENGINE_FAILED,
            f"unexpected llama-server response shape: {str(parsed)[:300]}",
        ) from exc
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)
