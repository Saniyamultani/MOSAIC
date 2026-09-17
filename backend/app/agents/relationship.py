"""Agent 5 -- Relationship.

Given one piece of outside-world information, does it touch anything in this
user's Life Graph?  Combines lexical entity lookup, vector retrieval over the
private store, and graph traversal to build the reasoning path.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from .. import textutils as T
from ..graphstore.factory import get_graph_store
from ..models import Entity, ExternalItem
from .base import Agent, Trace
from .rag import RagAgent

# Signal weights -> match strength.
WEIGHTS = {
    "identity": 0.45,
    "model_code": 0.45,
    "model_name": 0.25,
    "brand": 0.15,
    "product_name": 0.20,
    "vector": 0.15,
    "category": 0.05,
}


class RelationshipAgent(Agent):
    name = "Relationship Agent"

    def __init__(self, db: Session, trace: Trace | None = None) -> None:
        super().__init__(trace)
        self.db = db
        self.graph = get_graph_store(db)
        self.rag = RagAgent(db, self.trace)

    # --- terms --------------------------------------------------------------
    def terms_from_item(self, item: ExternalItem) -> list[str]:
        text = f"{item.title}\n{item.body}"
        meta = item.metadata_json or {}
        terms: list[str] = []
        terms += T.find_all(text, T.BRANDS)
        terms += T.find_all(text, T.SUBSCRIPTION_BRANDS)
        terms += T.find_all(text, T.RETAILERS)
        terms += list(meta.get("affected_brands") or [])
        terms += list(meta.get("affected_models") or [])
        if meta.get("product_hint"):
            terms.append(meta["product_hint"])
        name = T.extract_model_name(text)
        if name:
            terms.append(name)
        terms += T.extract_model_codes(text)
        return sorted({t for t in terms if t})

    # --- candidate generation ----------------------------------------------
    def find_candidates(self, user_id: str, item: ExternalItem) -> list[dict]:
        terms = self.terms_from_item(item)
        self.log("terms", f"Pulled {len(terms)} entities out of the announcement", terms)

        lexical = {e.id: e for e in self.graph.search_entities(user_id, terms)}
        vector_hits = self.rag.retrieve_private(
            user_id, f"{item.title}\n{item.body[:1500]}", k=6
        )
        vector_entity_ids = {
            c.meta.get("entity_id") for c in vector_hits if c.ref_type == "entity"
        }
        vector_scores = {
            c.meta.get("entity_id"): c.score for c in vector_hits if c.ref_type == "entity"
        }
        for eid in vector_entity_ids:
            if eid and eid not in lexical:
                entity = self.graph.get_entity(eid)
                if entity is not None:
                    lexical[eid] = entity

        candidates = []
        for entity in lexical.values():
            if entity.type not in ("product", "subscription", "warranty", "bill"):
                continue
            scored = self._score(entity, item, terms, vector_scores.get(entity.id, 0.0))
            if scored["match_strength"] > 0:
                candidates.append(scored)

        candidates.sort(key=lambda c: -c["match_strength"])
        self.log(
            "candidates",
            f"{len(candidates)} item(s) in your Life Graph could be affected",
            [{"entity": c["entity"].name, "strength": round(c["match_strength"], 2)} for c in candidates],
        )
        return candidates

    def _score(self, entity: Entity, item: ExternalItem, terms: list[str], vector_score: float) -> dict:
        attrs = entity.attributes or {}
        text = f"{item.title}\n{item.body}".lower()
        meta = item.metadata_json or {}
        affected = [str(m).upper() for m in (meta.get("affected_models") or [])]

        signals: dict[str, float] = {}
        reasons: list[str] = []

        # Verbatim identity match: for a subscription or a bill the service name
        # *is* the identifying key, the way a model code is for a device.
        if T.normalize_key(entity.name) and T.normalize_key(entity.name) in T.normalize_key(text):
            signals["identity"] = 1.0
            reasons.append(f"The announcement names '{entity.name}' directly")

        codes = {str(c).upper() for c in ([attrs.get("model_code")] + list(attrs.get("model_codes") or [])) if c}
        if codes and affected:
            if codes & set(affected):
                signals["model_code"] = 1.0
                reasons.append(f"Model code {sorted(codes & set(affected))[0]} is on the affected list")
        model = attrs.get("model")
        if model and model.lower() in text:
            signals["model_name"] = 1.0
            reasons.append(f"The announcement names the {model}")
        brand = attrs.get("brand") or attrs.get("provider")
        if brand and brand.lower() in text:
            signals["brand"] = 1.0
            reasons.append(f"The source is about {brand}, the maker of your {entity.name}")
        overlap = T.token_overlap(entity.name, item.title)
        if overlap > 0.15:
            signals["product_name"] = min(1.0, overlap * 2)
            reasons.append(f"Your '{entity.name}' overlaps the announcement title")
        if vector_score > 0.15:
            signals["vector"] = min(1.0, vector_score)
            reasons.append("Semantic search linked this to your stored documents")
        category = attrs.get("category")
        if category and category.lower() in text:
            signals["category"] = 1.0

        strength = sum(WEIGHTS[k] * v for k, v in signals.items())
        strength = min(1.0, strength)

        path = self._path(entity, item)
        return {
            "entity": entity,
            "signals": signals,
            "reasons": reasons,
            "match_strength": strength,
            "path": path,
            "affected_models": affected,
        }

    def _path(self, entity: Entity, item: ExternalItem) -> list[dict]:
        """The reasoning chain rendered in 'Why am I seeing this?'."""
        source_name = (item.metadata_json or {}).get("source_name") or "External source"
        chain = [
            {"step": "External update", "label": item.title[:120]},
            {"step": "Source", "label": source_name},
        ]
        attrs = entity.attributes or {}
        if attrs.get("brand"):
            chain.append({"step": "Brand", "label": attrs["brand"]})
        if attrs.get("model") or attrs.get("model_code"):
            chain.append(
                {"step": "Affected model", "label": attrs.get("model") or attrs.get("model_code")}
            )
        chain.append(
            {
                "step": "Your item",
                "label": entity.name
                + (f" (added {attrs['purchase_date']})" if attrs.get("purchase_date") else ""),
            }
        )
        for hop in self.graph.neighbors(entity.id, depth=1)[:4]:
            chain.append(
                {
                    "step": hop["relationship"].replace("_", " ").title(),
                    "label": hop["entity"].name,
                }
            )
        return chain
