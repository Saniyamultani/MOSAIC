"""Cross-cutting Envelope (mirrors contracts/envelope.schema.json)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

ENVELOPE_CONTRACT_VERSION = "1.0.0"


class EnvelopeError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    retriable: bool
    hint: str | None = None


class Meta(BaseModel):
    model_config = ConfigDict(extra="allow")

    layer: str
    backend: str | None = None
    elapsed_ms: float = 0.0
    trace_id: str | None = None


class Envelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str
    ok: bool
    data: Any = None
    error: EnvelopeError | None = None
    meta: Meta


def ok_envelope(
    contract_version: str,
    data: Any,
    *,
    layer: str,
    backend: str | None = None,
    elapsed_ms: float = 0.0,
    trace_id: str | None = None,
    **meta_extra: Any,
) -> Envelope:
    return Envelope(
        contract_version=contract_version,
        ok=True,
        data=data,
        error=None,
        meta=Meta(
            layer=layer,
            backend=backend,
            elapsed_ms=elapsed_ms,
            trace_id=trace_id,
            **meta_extra,
        ),
    )


def error_envelope(
    contract_version: str,
    *,
    code: str,
    message: str,
    retriable: bool,
    layer: str,
    hint: str | None = None,
    backend: str | None = None,
    elapsed_ms: float = 0.0,
    trace_id: str | None = None,
    **meta_extra: Any,
) -> Envelope:
    return Envelope(
        contract_version=contract_version,
        ok=False,
        data=None,
        error=EnvelopeError(code=code, message=message, retriable=retriable, hint=hint),
        meta=Meta(
            layer=layer,
            backend=backend,
            elapsed_ms=elapsed_ms,
            trace_id=trace_id,
            **meta_extra,
        ),
    )


class OcrSkillError(Exception):
    """Failure with a contract error code. Layers raise; CLI turns into Envelope."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retriable: bool = False,
        hint: str | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retriable = retriable
        self.hint = hint
