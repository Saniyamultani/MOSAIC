from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

INGEST_CONTRACT_VERSION = "1.0.0"


class PageMedia(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(ge=1)
    path: str
    media_type: str
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    byte_size: int = Field(ge=0)
    checksum: str


class IngestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str
    source_kind: str
    page_count: int = Field(ge=1)
    work_dir: str
    pages: list[PageMedia]
