from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

OCR_CONTRACT_VERSION = "1.0.0"


class OcrPageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(ge=1)
    markdown: str
    mode: str
    backend: str
    elapsed_ms: float = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)
