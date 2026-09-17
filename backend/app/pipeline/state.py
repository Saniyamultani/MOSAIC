from __future__ import annotations

from typing import Any, TypedDict


class MonitorState(TypedDict, total=False):
    """State carried through the LangGraph monitoring cycle."""

    user_id: str
    item_id: str
    candidates: list[dict]
    candidate: dict | None
    evidence: list[dict]
    skeptic: dict
    scores: dict
    alert_id: str | None
    outcome: str
    reason: str
    steps: list[dict]


class IngestionState(TypedDict, total=False):
    """State carried through the ingestion graph.

    The graph deliberately halts before `commit` -- that pause is the single
    ✓ Confirm the user performs.
    """

    user_id: str
    input_type: str          # text | file | url
    payload: dict[str, Any]
    document_id: str
    extraction: dict
    overrides: dict
    result: dict
    steps: list[dict]
