"""Agent 7 -- Relevance.

Turns a surviving match into four scores and one severity tier.  Anything under
the confidence floor never becomes an alert.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from ..config import settings
from ..models import ExternalItem
from .base import Agent, Trace

IMPORTANCE = {
    "recall": 1.0,
    "security_update": 0.85,
    "service_program": 0.8,
    "warranty": 0.7,
    "regulatory": 0.65,
    "price_change": 0.55,
    "subscription": 0.5,
    "firmware": 0.6,
    "external_update": 0.35,
}

ACTIONABILITY = {
    "recall": 1.0,
    "service_program": 0.9,
    "security_update": 0.85,
    "warranty": 0.7,
    "price_change": 0.8,
    "regulatory": 0.5,
    "external_update": 0.3,
}


def _days_until(value) -> int | None:
    if not value:
        return None
    try:
        target = date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None
    return (target - datetime.now(timezone.utc).date()).days


class RelevanceAgent(Agent):
    name = "Relevance Agent"

    def score(self, item: ExternalItem, candidate: dict, skeptic: dict) -> dict:
        meta = item.metadata_json or {}
        category = item.category or "external_update"

        match_strength = max(0.0, candidate["match_strength"] - skeptic["penalty"])
        importance = IMPORTANCE.get(category, 0.35)
        actionability = ACTIONABILITY.get(category, 0.3)

        deadline_days = _days_until(meta.get("deadline"))
        expiry_days = _days_until((candidate["entity"].attributes or {}).get("expiry_date"))
        horizon = min([d for d in (deadline_days, expiry_days) if d is not None], default=None)
        if horizon is None:
            urgency = 0.35
        elif horizon < 0:
            urgency = 0.1
        elif horizon <= 7:
            urgency = 1.0
        elif horizon <= 30:
            urgency = 0.75
        elif horizon <= 90:
            urgency = 0.5
        else:
            urgency = 0.3

        trust = int(meta.get("trust_tier", 3))
        trust_factor = {1: 1.0, 2: 0.97, 3: 0.9, 4: 0.82, 5: 0.72, 6: 0.6}.get(trust, 0.8)

        confidence = (
            0.55 * match_strength + 0.25 * importance + 0.20 * urgency
        ) * trust_factor
        confidence = round(min(0.99, max(0.0, confidence)), 2)

        if confidence >= 0.7 and importance >= 0.7:
            severity = "critical"
        elif confidence >= settings.alert_confidence_floor:
            severity = "worth_knowing"
        elif confidence >= 0.35:
            severity = "info"
        else:
            severity = "suppressed"

        result = {
            "match_strength": round(match_strength, 2),
            "importance": round(importance, 2),
            "urgency": round(urgency, 2),
            "actionability": round(actionability, 2),
            "trust_factor": trust_factor,
            "confidence": confidence,
            "severity": severity,
            "deadline_days": horizon,
        }
        self.log(
            "score",
            f"match {result['match_strength']:.2f} · importance {importance:.2f} · "
            f"urgency {urgency:.2f} → {int(confidence * 100)}% confidence ({severity})",
            result,
        )
        return result
