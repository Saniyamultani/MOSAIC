"""Stable machine error codes shared across layers."""

from __future__ import annotations

# Closed set used in Envelope.error.code
INVALID_INPUT = "invalid_input"
NOT_FOUND = "not_found"
UNSUPPORTED_MEDIA = "unsupported_media"
INGEST_FAILED = "ingest_failed"
ENGINE_UNAVAILABLE = "engine_unavailable"
ENGINE_FAILED = "engine_failed"
NOT_OPENED = "not_opened"
INTERNAL_ERROR = "internal_error"
CONFIG_ERROR = "config_error"
