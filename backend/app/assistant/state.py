"""State representation for the MOSAIC Assistant LangGraph workflow."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class AssistantState(TypedDict, total=False):
    db: Any
    user_id: str
    conversation_id: str
    question: str
    history: List[Dict[str, str]]
    intent: str
    freshness_class: str          # "current" | "stable" | "mixed"
    current_datetime: Dict[str, str]  # from get_current_datetime()
    query_terms: List[str]
    resolved_entity: Optional[Dict[str, Any]]
    entities_in_context: List[Dict[str, Any]]
    tools_to_call: List[str]
    tool_results: Dict[str, Any]
    sources: List[Dict[str, Any]]
    evidence: List[Dict[str, Any]]
    entities: List[Dict[str, Any]]
    answer: str
    external_brand: Optional[str]
    search_query: Optional[str]
    is_comparison: bool
