"""OCR engine port. Adapters implement this; nothing above Layer 2 imports torch."""

from __future__ import annotations

from typing import Protocol

from .models import OcrPageResult


class OCREngine(Protocol):
    name: str

    def extract_page(
        self,
        image_path: str,
        *,
        page: int = 1,
        mode: str = "markdown",
    ) -> OcrPageResult: ...

    def available(self) -> tuple[bool, str]:
        """Return (ok, detail) for doctor/init without running inference."""
        ...
