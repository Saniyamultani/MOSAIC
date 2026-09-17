"""Agent 8 -- Alert.

Writes the notification the user actually sees, carrying its whole reasoning
chain and evidence list with it.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..llm.factory import get_llm
from ..models import Alert, ExternalItem
from .base import Agent, Trace
from .rag import RagAgent

SEVERITY_LABEL = {
    "critical": "Important",
    "worth_knowing": "Worth knowing",
    "connection": "New connection",
    "info": "Informational",
}


class AlertAgent(Agent):
    name = "Alert Agent"

    def __init__(self, db: Session, trace: Trace | None = None) -> None:
        super().__init__(trace)
        self.db = db
        self.llm = get_llm()
        self.rag = RagAgent(db, self.trace)

    def compose(
        self,
        user_id: str,
        item: ExternalItem,
        candidate: dict,
        skeptic: dict,
        scores: dict,
    ) -> Alert:
        entity = candidate["entity"]
        meta = item.metadata_json or {}

        checks = [
            f"{c['check']}: {c['detail']}"
            for c in skeptic["checks"]
            if c["result"] in ("pass", "partial")
        ]
        composed = self.llm.compose_alert(
            {
                "entity": {
                    "name": entity.name,
                    "type": entity.type,
                    "attributes": entity.attributes or {},
                },
                "item": {
                    "title": item.title,
                    "body": item.body,
                    "category": item.category,
                    "source_name": meta.get("source_name"),
                    "url": item.url,
                },
                "checks": checks,
                "severity": scores["severity"],
                "confidence": scores["confidence"],
            }
        )

        evidence = [
            {
                "kind": "external",
                "title": item.title,
                "source": meta.get("source_name", "External source"),
                "url": item.url,
                "snippet": item.body[:400],
                "trust_tier": meta.get("trust_tier"),
            }
        ]
        evidence += self.rag.evidence_for(user_id, f"{entity.name} {item.title}", k=3)
        # De-duplicate while preserving order.
        seen, unique_evidence = set(), []
        for e in evidence:
            key = (e.get("title"), e.get("ref_id"))
            if key in seen:
                continue
            seen.add(key)
            unique_evidence.append(e)

        why = list(composed.get("why_it_matters") or checks)
        if skeptic["objections"]:
            why += [f"Caveat: {o}" for o in skeptic["objections"][:2]]

        alert = Alert(
            user_id=user_id,
            external_item_id=item.id,
            entity_id=entity.id,
            severity=scores["severity"],
            headline=composed["headline"][:400],
            explanation=composed["explanation"],
            confidence=scores["confidence"],
            reasoning_chain=candidate["path"],
            why_it_matters=why,
            evidence=unique_evidence[:8],
            suggested_action=composed.get("suggested_action", ""),
        )
        self.db.add(alert)
        self.db.flush()
        self.log(
            "compose",
            f"Raised a {SEVERITY_LABEL.get(alert.severity, alert.severity)} alert at "
            f"{int(alert.confidence * 100)}% confidence",
            {"headline": alert.headline},
        )
        return alert

    def connection_alert(self, user_id: str, entity, related, reason: str) -> Alert:
        """The 🔵 'new connection' tier -- MOSAIC noticed two of your own things
        relate to each other."""
        alert = Alert(
            user_id=user_id,
            entity_id=entity.id,
            severity="connection",
            headline=f"{entity.name} is now linked to {related.name}",
            explanation=reason,
            confidence=0.9,
            reasoning_chain=[
                {"step": "Your item", "label": entity.name},
                {"step": "Connected to", "label": related.name},
            ],
            why_it_matters=[reason],
            evidence=[],
            suggested_action="",
        )
        self.db.add(alert)
        self.db.flush()
        return alert
