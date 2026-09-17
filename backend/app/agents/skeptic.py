"""Agent 6 -- Skeptic.

Actively tries to kill the match.  This is the agent that stops MOSAIC becoming
a panic machine: a recall for Model A must not fire on a user who owns Model B.

Deterministic checks run first and are authoritative; the LLM may only pile on
additional doubts, never overturn a hard mismatch.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from ..llm.factory import get_llm
from ..models import ExternalItem
from .base import Agent, Trace


def _as_date(value) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


class SkepticAgent(Agent):
    name = "Skeptic Agent"

    def __init__(self, db: Session, trace: Trace | None = None) -> None:
        super().__init__(trace)
        self.db = db
        self.llm = get_llm()

    def review(self, item: ExternalItem, candidate: dict) -> dict:
        entity = candidate["entity"]
        attrs = entity.attributes or {}
        meta = item.metadata_json or {}
        affected = [str(m).upper() for m in (meta.get("affected_models") or [])]
        codes = {
            str(c).upper()
            for c in ([attrs.get("model_code")] + list(attrs.get("model_codes") or []))
            if c
        }

        objections: list[str] = []
        checks: list[dict] = []
        refuted = False

        # 1. Model check -- the decisive one.
        if affected and codes:
            matched = sorted(codes & set(affected))
            if matched:
                checks.append({"check": "Model match", "result": "pass",
                               "detail": f"Your unit ({matched[0]}) is on the affected list"})
            else:
                refuted = True
                own = sorted(codes)[0]
                objections.append(
                    f"The notice affects {', '.join(affected[:4])}; your unit is {own}."
                )
                checks.append({"check": "Model match", "result": "fail",
                               "detail": f"Affected: {', '.join(affected[:4])} — yours: {own}"})
        elif affected and not codes:
            objections.append(
                "The notice lists specific model codes but your record has none, so the match is by name only."
            )
            checks.append({"check": "Model match", "result": "partial",
                           "detail": "Matched by product name; exact model code unknown"})
        else:
            checks.append({"check": "Model match", "result": "n/a",
                           "detail": "The notice does not restrict itself to specific models"})

        # 2. Region check.
        region = meta.get("region")
        user_region = attrs.get("region")
        if region and user_region and region.lower() not in user_region.lower():
            refuted = True
            objections.append(f"The notice applies to {region}, your item is registered in {user_region}.")
            checks.append({"check": "Region", "result": "fail", "detail": f"{region} vs {user_region}"})
        elif region:
            checks.append({"check": "Region", "result": "pass", "detail": f"Applies to {region}"})

        # 3. Purchase-window check.
        window_start = _as_date(meta.get("purchased_after"))
        window_end = _as_date(meta.get("purchased_before"))
        purchased = _as_date(attrs.get("purchase_date"))
        if purchased and (window_start or window_end):
            if (window_start and purchased < window_start) or (window_end and purchased > window_end):
                refuted = True
                objections.append(
                    f"The programme covers units bought between {window_start or 'any'} and "
                    f"{window_end or 'any'}; yours is from {purchased}."
                )
                checks.append({"check": "Purchase window", "result": "fail",
                               "detail": f"Bought {purchased}, window {window_start}–{window_end}"})
            else:
                checks.append({"check": "Purchase window", "result": "pass",
                               "detail": f"Bought {purchased}, inside the covered window"})

        # 4. Ownership evidence.
        if entity.document_id:
            checks.append({"check": "Ownership evidence", "result": "pass",
                           "detail": "Backed by a document you uploaded"})
        else:
            objections.append("No uploaded document backs this item; it was inferred.")
            checks.append({"check": "Ownership evidence", "result": "partial",
                           "detail": "Inferred entity, no source document"})

        # 5. Source trust.
        trust = meta.get("trust_tier", 3)
        if trust <= 2:
            checks.append({"check": "Source trust", "result": "pass",
                           "detail": f"{meta.get('source_name', 'Source')} is an official/manufacturer source"})
        elif trust >= 5:
            objections.append("The source is general web/press rather than an official channel.")
            checks.append({"check": "Source trust", "result": "partial",
                           "detail": f"{meta.get('source_name', 'Source')} is a secondary source"})
        else:
            checks.append({"check": "Source trust", "result": "pass",
                           "detail": f"{meta.get('source_name', 'Source')} is an approved source"})

        # 6. Weak-signal check.
        if candidate["match_strength"] < 0.3:
            objections.append("Only weak, indirect signals connect this announcement to your item.")

        verdict = self.llm.skeptic_review(
            {
                "title": item.title,
                "body": item.body,
                "affected_models": affected,
                "source_name": meta.get("source_name"),
            },
            {"name": entity.name, "attributes": attrs},
            {"refuted": refuted, "objections": objections, "reason": "; ".join(candidate["reasons"])},
            [],
        )
        refuted = bool(refuted or verdict.get("refuted"))
        objections = list(dict.fromkeys(verdict.get("objections", objections)))

        penalty = min(0.45, 0.12 * len(objections))
        self.log(
            "review",
            ("Refuted the match: " + objections[0]) if refuted
            else f"Match survived {len(checks)} checks with {len(objections)} caveat(s)",
            {"checks": checks, "objections": objections},
        )
        return {
            "refuted": refuted,
            "objections": objections,
            "checks": checks,
            "penalty": penalty,
        }
