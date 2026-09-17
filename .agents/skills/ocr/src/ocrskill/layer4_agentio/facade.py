"""Agent facade: extract / open. Always returns an Envelope."""

from __future__ import annotations

import shutil
import time
from collections.abc import Callable
from typing import Any

from .. import config, errors
from ..envelope import Envelope, OcrSkillError, error_envelope, ok_envelope
from ..layer1_ingest import ingest_path
from ..layer1_ingest.models import INGEST_CONTRACT_VERSION
from ..layer2_ocr import OCR_CONTRACT_VERSION, build_engine
from ..layer2_ocr.port import OCREngine
from ..layer3_format import FORMAT_CONTRACT_VERSION, DocumentStore, assemble, paginate

AGENTIO_CONTRACT_VERSION = "1.0.0"


def build_agent(
    *,
    engine: OCREngine | None = None,
    store: DocumentStore | None = None,
) -> OcrAgent:
    return OcrAgent(engine=engine, store=store)


class OcrAgent:
    def __init__(
        self,
        *,
        engine: OCREngine | None = None,
        store: DocumentStore | None = None,
        engine_name: str | None = None,
    ):
        self._engine = engine
        self._engine_name = engine_name
        self._store = store or DocumentStore()

    def _engine_or_build(self) -> OCREngine:
        if self._engine is None:
            self._engine = build_engine(self._engine_name)
        return self._engine

    def _run(
        self,
        layer: str,
        contract: str,
        work: Callable[[], Any],
        backend: str | None = None,
    ) -> Envelope:
        started = time.perf_counter()
        try:
            data = work()
        except OcrSkillError as exc:
            return error_envelope(
                contract,
                code=exc.code,
                message=exc.message,
                retriable=exc.retriable,
                hint=exc.hint,
                layer=layer,
                backend=backend,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
        except Exception as exc:
            return error_envelope(
                contract,
                code=errors.INTERNAL_ERROR,
                message=f"{layer} failed: {type(exc).__name__}: {exc}",
                retriable=False,
                layer=layer,
                backend=backend,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
        return ok_envelope(
            contract,
            data,
            layer=layer,
            backend=backend,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )

    def extract(
        self,
        paths: list[str],
        *,
        mode: str = "markdown",
        fence: bool = True,
        page: int = 1,
        page_size_tokens: int = config.DEFAULT_PAGE_SIZE_TOKENS,
        keep_work: bool = False,
    ) -> Envelope:
        def work() -> Any:
            if not paths:
                raise OcrSkillError(errors.INVALID_INPUT, "no paths given")
            from ..layer2_ocr.modes import MODES

            if mode not in MODES:
                raise OcrSkillError(
                    errors.INVALID_INPUT,
                    f"unknown mode: {mode}",
                    hint=f"Use one of: {', '.join(MODES)}",
                )

            engine = self._engine_or_build()
            documents = []
            for raw in paths:
                ingested = ingest_path(raw)
                ocr_pages = []
                try:
                    for media in ingested.pages:
                        ocr_pages.append(
                            engine.extract_page(
                                media.path,
                                page=media.page,
                                mode=mode,
                            )
                        )
                finally:
                    if not keep_work:
                        shutil.rmtree(ingested.work_dir, ignore_errors=True)

                doc = assemble(
                    source_path=ingested.source_path,
                    source_kind=ingested.source_kind,
                    page_count=ingested.page_count,
                    mode=mode,
                    ocr_pages=ocr_pages,
                    fence=fence,
                    page=page,
                    page_size_tokens=page_size_tokens,
                )
                self._store.put(doc)
                documents.append(doc.model_dump(mode="json"))
            return {"documents": documents}

        backend = None
        try:
            backend = self._engine_or_build().name
        except OcrSkillError:
            backend = config.backend_name()
        return self._run("agentio", AGENTIO_CONTRACT_VERSION, work, backend=backend)

    def open(
        self,
        handle: str,
        *,
        page: int = 1,
        page_size_tokens: int = config.DEFAULT_PAGE_SIZE_TOKENS,
        fence: bool = True,
    ) -> Envelope:
        def work() -> Any:
            stored = self._store.get(handle)
            # Re-paginate from stored full markdown.
            doc = paginate(
                handle=stored.handle,
                source_path=stored.source_path,
                source_kind=stored.source_kind,
                page_count=stored.page_count,
                mode=stored.mode,
                markdown=stored.markdown,
                fence=fence,
                page=page,
                page_size_tokens=page_size_tokens,
                backend=stored.backend,
                warnings=stored.warnings,
            )
            # Keep store entry current for subsequent opens.
            self._store.put(doc)
            return doc.model_dump(mode="json")

        return self._run("agentio", AGENTIO_CONTRACT_VERSION, work, backend=None)


# Re-export versions for doctor lockstep tests.
__all__ = [
    "AGENTIO_CONTRACT_VERSION",
    "OcrAgent",
    "build_agent",
    "INGEST_CONTRACT_VERSION",
    "OCR_CONTRACT_VERSION",
    "FORMAT_CONTRACT_VERSION",
]
