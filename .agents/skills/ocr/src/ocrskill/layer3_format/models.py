from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

FORMAT_CONTRACT_VERSION = "1.0.0"


class FenceInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nonce: str
    open_marker: str
    close_marker: str


class FormatDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handle: str
    source_path: str
    source_kind: str
    page_count: int = Field(ge=1)
    mode: str
    markdown: str
    fenced: bool
    content: str
    page: int = Field(ge=1)
    total_pages: int = Field(ge=1)
    has_more: bool
    page_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    untrusted: bool
    fence: FenceInfo | None = None
    backend: str | None = None
    warnings: list[str] = Field(default_factory=list)
