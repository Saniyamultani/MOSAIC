"""Deterministic OCR backend for tests and offline runs."""

from __future__ import annotations

import time
from pathlib import Path

from ... import errors
from ...envelope import OcrSkillError
from ..models import OcrPageResult


class MockEngine:
    name = "mock"

    def available(self) -> tuple[bool, str]:
        return True, "mock engine always available"

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

        # Prefer a sibling .expected.md for fixture-driven tests.
        expected = path.with_suffix(".expected.md")
        if not expected.is_file():
            # Also check same stem next to source fixtures.
            expected = path.parent / f"{path.stem}.expected.md"
        if expected.is_file():
            body = expected.read_text(encoding="utf-8")
        else:
            stem = path.stem
            if mode == "free":
                body = f"Mock OCR page {page} of {stem}"
            elif mode == "figure":
                body = (
                    f"# Mock figure parse\n\n"
                    f"- page: {page}\n"
                    f"- source: `{stem}`\n"
                    f"- mode: figure\n"
                )
            elif mode == "ocr":
                body = f"Mock grounded OCR page {page} ({stem})"
            else:
                body = (
                    f"# Mock OCR\n\n"
                    f"- page: {page}\n"
                    f"- source: `{stem}`\n"
                    f"- mode: markdown\n"
                )

        return OcrPageResult(
            page=page,
            markdown=body,
            mode=mode,
            backend=self.name,
            elapsed_ms=(time.perf_counter() - started) * 1000,
            warnings=[],
        )
