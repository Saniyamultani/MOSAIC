"""Layer 1: image/PDF path → ordered page images."""

from .ingest import INGEST_CONTRACT_VERSION, ingest_path

__all__ = ["INGEST_CONTRACT_VERSION", "ingest_path"]
