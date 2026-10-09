"""Run deterministic evaluation cases against MOSAIC modules and record evidence."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import patch

from sqlalchemy.orm import Session

from ..assistant import graph as assistant_graph
from ..agents.research import ResearchAgent
from ..assistant.graph import _classify_freshness
from ..assistant.service import run_assistant_chat
from ..graphstore.factory import get_graph_store
from ..models import Alert, Document
from ..rag.store import PRIVATE, get_vector_store
from ..services import (
    confirm_ingestion,
    get_or_create_demo_user,
    publish_external_item,
    run_monitoring,
    start_ingestion,
)
from .dataset import EvalTestCase

log = logging.getLogger("mosaic.evals")


@dataclass
class EvalResult:
    test_case_id: str
    category: str
    title: str
    passed: bool
    expected_result: str
    actual_result: str
    evidence: List[str]
    latency_ms: float
    details: Dict[str, Any] = field(default_factory=dict)


class SystemEvaluator:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.user = get_or_create_demo_user(db)
        self.db.commit()

    def run_case(self, case: EvalTestCase) -> EvalResult:
        start_t = time.perf_counter()
        evidence: List[str] = []
        passed = False
        expected_str = ""
        actual_str = ""
        details: Dict[str, Any] = {}

        try:
            self._seed_case_documents(case)
            if case.category == "doc_extraction":
                passed, expected_str, actual_str, evidence, details = self._eval_doc_extraction(case)
            elif case.category == "life_graph":
                passed, expected_str, actual_str, evidence, details = self._eval_life_graph(case)
            elif case.category == "rag_retrieval":
                passed, expected_str, actual_str, evidence, details = self._eval_rag_retrieval(case)
            elif case.category == "assistant_reasoning":
                passed, expected_str, actual_str, evidence, details = self._eval_assistant_reasoning(case)
            elif case.category == "web_research":
                passed, expected_str, actual_str, evidence, details = self._eval_web_research(case)
            elif case.category == "radar_monitoring":
                passed, expected_str, actual_str, evidence, details = self._eval_radar_monitoring(case)
            elif case.category == "hallucination_safety":
                passed, expected_str, actual_str, evidence, details = self._eval_hallucination_safety(case)
            else:
                passed = False
                expected_str = "Known category"
                actual_str = f"Unknown category {case.category}"
                evidence = ["Invalid evaluation case category."]
        except Exception as exc:
            log.error("Evaluation case %s error: %s", case.id, exc, exc_info=True)
            passed = False
            expected_str = str(case.expected_output)
            actual_str = f"Execution error: {type(exc).__name__}: {exc}"
            evidence = [
                "ERROR: Evaluation could not complete; this is not a measured capability failure.",
                f"Exception: {type(exc).__name__}: {exc}",
            ]
            details["status"] = "ERROR"

        duration_ms = (time.perf_counter() - start_t) * 1000.0
        return EvalResult(
            test_case_id=case.id,
            category=case.category,
            title=case.title,
            passed=passed,
            expected_result=expected_str,
            actual_result=actual_str,
            evidence=evidence,
            latency_ms=round(duration_ms, 2),
            details=details,
        )

    def _seed_case_documents(self, case: EvalTestCase) -> None:
        for item in case.input_data.get("seed_documents", []):
            doc, _trace, thread_id = start_ingestion(
                self.db,
                self.user.id,
                "text",
                {"text": item["text"], "kind_hint": item["kind"]},
            )
            confirm_ingestion(self.db, thread_id, doc.id)

    # -----------------------------------------------------------------------
    # Evaluators for each dimension
    # -----------------------------------------------------------------------

    def _eval_doc_extraction(self, case: EvalTestCase) -> tuple[bool, str, str, List[str], Dict[str, Any]]:
        text = case.input_data["text"]
        kind_hint = case.input_data.get("kind_hint", "receipt")

        doc, trace, thread_id = start_ingestion(self.db, self.user.id, "text", {"text": text, "kind_hint": kind_hint})
        extraction = doc.extraction or {}
        fields = extraction.get("fields") or {}

        exp = case.expected_output
        evidence = [
            f"Extracted document kind: '{extraction.get('kind')}'",
            f"Extracted fields: {fields}",
            f"Trace steps: {len(trace)}",
        ]

        passed = True
        failures = []

        if exp.get("kind") and extraction.get("kind") != exp["kind"]:
            passed = False
            failures.append(f"Kind mismatch: expected {exp['kind']}, got {extraction.get('kind')}")

        if exp.get("product") and exp["product"].lower() not in str(fields.get("product", "")).lower():
            passed = False
            failures.append(f"Product mismatch: expected {exp['product']}, got {fields.get('product')}")

        if exp.get("price") is not None:
            actual_price = fields.get("price")
            if actual_price != exp["price"]:
                passed = False
                failures.append(f"Price mismatch: expected {exp['price']}, got {actual_price}")

        if exp.get("purchase_date") and fields.get("purchase_date") != exp["purchase_date"]:
            passed = False
            failures.append(f"Purchase date mismatch: expected {exp['purchase_date']}, got {fields.get('purchase_date')}")

        if exp.get("seller") and exp["seller"].lower() not in str(fields.get("seller", "")).lower():
            passed = False
            failures.append(f"Seller mismatch: expected {exp['seller']}, got {fields.get('seller')}")

        if exp.get("payment_method"):
            exp_pm = exp["payment_method"].lower()
            act_pm = str(fields.get("payment_method", "")).lower()
            if exp_pm not in act_pm:
                passed = False
                failures.append(f"Payment method mismatch: expected {exp['payment_method']}, got {fields.get('payment_method')}")

        if exp.get("warranty_months") is not None:
            actual_months = fields.get("warranty_months") or fields.get("duration_months")
            if actual_months != exp["warranty_months"]:
                passed = False
                failures.append(
                    f"Warranty mismatch: expected {exp['warranty_months']} months, got {actual_months}"
                )

        expected_str = (
            f"Product: {exp.get('product')}; Price: {exp.get('price')}; "
            f"Purchase date: {exp.get('purchase_date')}; Merchant: {exp.get('seller')}; "
            f"Payment method: {exp.get('payment_method')}; Warranty: {exp.get('warranty_months')} months"
        )
        actual_str = (
            f"Product: {fields.get('product')}; Price: {fields.get('price')}; "
            f"Purchase date: {fields.get('purchase_date')}; Merchant: {fields.get('seller')}; "
            f"Payment method: {fields.get('payment_method')}; "
            f"Warranty: {fields.get('warranty_months') or fields.get('duration_months')} months"
        )

        if not passed:
            evidence.extend([f"FAIL: {f}" for f in failures])
        else:
            evidence.append("PASS: All structured fields accurately extracted.")

        return passed, expected_str, actual_str, evidence, {"fields": fields}

    def _eval_life_graph(self, case: EvalTestCase) -> tuple[bool, str, str, List[str], Dict[str, Any]]:
        graph = get_graph_store(self.db)

        if case.id == "graph_entity_relationships":
            doc, trace, thread_id = start_ingestion(self.db, self.user.id, "text", {"text": case.input_data["text"], "kind_hint": "receipt"})
            confirm_ingestion(self.db, thread_id, doc.id)

            view = graph.view(self.user.id)
            nodes_by_name = {n["name"].casefold(): n for n in view.nodes}
            nodes_by_id = {n["id"]: n for n in view.nodes}
            node_types = {n["type"] for n in view.nodes}
            edges = {
                (
                    nodes_by_id.get(e["source"], {}).get("type"),
                    e["type"],
                    nodes_by_id.get(e["target"], {}).get("type"),
                )
                for e in view.edges
            }
            product = nodes_by_name.get("samsung galaxy s26 ultra")
            required_edges = {
                ("product", "PURCHASED_FROM", "retailer"),
                ("product", "PAID_WITH", "payment_method"),
                ("product", "MANUFACTURED_BY", "brand"),
                ("product", "COVERED_BY", "warranty"),
            }

            evidence = [
                f"Graph nodes: {[(n['type'], n['name']) for n in view.nodes]}",
                f"Graph relationships: {sorted(edges)}",
            ]

            required_nodes = {"product", "brand", "retailer", "payment_method", "warranty"}
            passed = (
                product is not None
                and required_nodes <= node_types
                and required_edges <= edges
            )
            expected_str = (
                "Product, brand, merchant, payment, and warranty entities; "
                "PURCHASED_FROM, PAID_WITH, MANUFACTURED_BY, and COVERED_BY links"
            )
            actual_str = f"Node types: {sorted(node_types)}; relationships: {sorted(edges)}"
            if passed:
                evidence.append("PASS: All required entities and directed relationships were present.")
            else:
                missing_nodes = sorted(required_nodes - node_types)
                missing_edges = sorted(required_edges - edges)
                evidence.append(f"FAIL: Missing node types={missing_nodes}; missing relationships={missing_edges}.")
            return passed, expected_str, actual_str, evidence, {"nodes": len(view.nodes), "edges": len(view.edges)}

        elif case.id == "graph_duplicate_prevention":
            # Test multi-document ingestion into same entity
            doc1, trace1, thread1 = start_ingestion(self.db, self.user.id, "text", {"text": case.input_data["text1"], "kind_hint": "receipt"})
            confirm_ingestion(self.db, thread1, doc1.id)

            doc2, trace2, thread2 = start_ingestion(self.db, self.user.id, "text", {"text": case.input_data["text2"], "kind_hint": "warranty"})
            res2 = confirm_ingestion(self.db, thread2, doc2.id)

            product_entities = graph.entities(self.user.id, types=["product"])
            relationships = graph.relationships(self.user.id)
            relationship_keys = [
                (rel.source_id, rel.target_id, rel.type.upper())
                for rel in relationships
            ]
            duplicate_relationships = len(relationship_keys) - len(set(relationship_keys))
            resolved_product = product_entities[0] if len(product_entities) == 1 else None
            model_code = (resolved_product.attributes or {}).get("model_code") if resolved_product else None
            model_codes = (resolved_product.attributes or {}).get("model_codes", []) if resolved_product else []
            evidence = [
                f"Product entities count: {len(product_entities)}",
                f"Resolved model code: {model_code or model_codes}",
                f"Duplicate relationship triples: {duplicate_relationships}",
                f"Confirmation 2 result: created={res2.get('created')}, merged={res2.get('merged')}",
            ]

            passed = (
                len(product_entities) == 1
                and ("SM-S926B" == model_code or "SM-S926B" in model_codes)
                and duplicate_relationships == 0
            )
            expected_str = "One Galaxy S26 Ultra product entity, model code SM-S926B merged, no duplicate relationship triples"
            actual_str = (
                f"Product entities: {len(product_entities)}; model code: {model_code or model_codes}; "
                f"duplicate relationship triples: {duplicate_relationships}"
            )

            if passed:
                evidence.append("PASS: The warranty document resolved to the existing product and graph links stayed unique.")
            else:
                evidence.append("FAIL: Entity resolution or relationship uniqueness did not meet the expected result.")

            return passed, expected_str, actual_str, evidence, {
                "product_entities": len(product_entities),
                "duplicate_relationships": duplicate_relationships,
            }

        return False, "Known test case", "Unknown subcase", ["Invalid test case"], {}

    def _eval_rag_retrieval(self, case: EvalTestCase) -> tuple[bool, str, str, List[str], Dict[str, Any]]:
        # Seed documents first if empty
        existing_docs = self.db.query(Document).filter(Document.user_id == self.user.id).all()
        if not existing_docs:
            doc, trace, thread_id = start_ingestion(
                self.db,
                self.user.id,
                "text",
                {
                    "text": "Bought a Samsung Galaxy S26 Ultra (SM-S926B) from Amazon for Rs 1,29,999 on 12 May 2026.",
                    "kind_hint": "receipt",
                },
            )
            confirm_ingestion(self.db, thread_id, doc.id)

        vstore = get_vector_store(self.db)
        query = case.input_data["query"]
        hits = vstore.search(PRIVATE, query, user_id=self.user.id, k=5)

        evidence = [f"RAG search query: '{query}'", f"Hits retrieved: {len(hits)}"]
        for i, hit in enumerate(hits[:3]):
            evidence.append(f"Hit {i+1}: ref={hit.ref_type}:{hit.ref_id}, score={hit.score:.3f}, text='{hit.text[:60]}...'")

        expected_terms = case.expected_output.get("excluded_terms", [])
        hit_text = "\n".join(hit.text for hit in hits).casefold()

        if case.id == "rag_relevant_personal_retrieval":
            relevant_hits = [
                hit for hit in hits
                if "samsung galaxy s26 ultra" in hit.text.casefold()
                and "129999" in hit.text
            ]
            excluded_hits = [term for term in expected_terms if term.casefold() in hit_text]
            passed = bool(relevant_hits) and not excluded_hits
            expected_str = "Retrieve the Galaxy S26 Ultra purchase and price without Netflix or broadband records"
            actual_str = (
                f"Retrieved {len(hits)} hits; relevant purchase hits={len(relevant_hits)}; "
                f"unrelated records present={excluded_hits}"
            )
            details = {
                "hit_count": len(hits),
                "relevant_hit_count": len(relevant_hits),
                "excluded_terms_found": excluded_hits,
            }
        else:
            excluded_hits = [term for term in expected_terms if term.casefold() in hit_text]
            passed = not hits
            expected_str = "Do not retrieve unrelated device, subscription, or bill records for an unrecorded car query"
            actual_str = f"Retrieved {len(hits)} hits; unrelated records present={excluded_hits}"
            details = {"hit_count": len(hits), "excluded_terms_found": excluded_hits}

        evidence.extend(
            f"Excluded unrelated term '{term}': {'FOUND' if term in excluded_hits else 'not found'}"
            for term in expected_terms
        )

        if passed:
            evidence.append("PASS: Retrieval satisfied the case's relevance and exclusion criteria.")
        else:
            evidence.append("FAIL: Retrieval missed required personal context or included unrelated records.")

        return passed, expected_str, actual_str, evidence, details

    def _eval_assistant_reasoning(self, case: EvalTestCase) -> tuple[bool, str, str, List[str], Dict[str, Any]]:
        if case.id == "assistant_personal_answer":
            # Ensure receipt exists
            existing_docs = self.db.query(Document).filter(Document.user_id == self.user.id).all()
            if not existing_docs:
                doc, trace, thread_id = start_ingestion(
                    self.db,
                    self.user.id,
                    "text",
                    {
                        "text": "Bought a Samsung Galaxy S26 Ultra (SM-S926B) from Amazon for Rs 1,29,999 on 12 May 2026.",
                        "kind_hint": "receipt",
                    },
                )
                confirm_ingestion(self.db, thread_id, doc.id)

            res = run_assistant_chat(self.db, self.user.id, case.input_data["question"])
            answer = res.get("answer", "")
            evidence = [f"Question: '{case.input_data['question']}'", f"Answer: '{answer}'", f"Entities count: {len(res.get('entities', []))}"]

            expected_device = case.expected_output["answer_contains"][0].casefold()
            excluded = case.expected_output["answer_excludes"]
            answer_lower = answer.casefold()
            passed = expected_device in answer_lower and not any(
                term.casefold() in answer_lower for term in excluded
            )
            expected_str = "Answer identifies Samsung Galaxy S26 Ultra and does not substitute another model"
            actual_str = f"Answer: '{answer}'"

            if passed:
                evidence.append("PASS: Assistant answered accurately from Life Graph context.")
            else:
                evidence.append("FAIL: Answer did not mention the personal device.")

            return passed, expected_str, actual_str, evidence, {"answer": answer}

        elif case.id == "assistant_multi_turn_followup":
            # Ensure receipt exists
            existing_docs = self.db.query(Document).filter(Document.user_id == self.user.id).all()
            if not existing_docs:
                doc, trace, thread_id = start_ingestion(
                    self.db,
                    self.user.id,
                    "text",
                    {
                        "text": "Bought a Samsung Galaxy S26 Ultra (SM-S926B) from Amazon for Rs 1,29,999 on 12 May 2026.",
                        "kind_hint": "receipt",
                    },
                )
                confirm_ingestion(self.db, thread_id, doc.id)

            # Turn 1
            res1 = run_assistant_chat(self.db, self.user.id, case.input_data["turn1"])
            cid = res1["conversation_id"]

            # Turn 2
            res2 = run_assistant_chat(self.db, self.user.id, case.input_data["turn2"], conversation_id=cid)
            answer2 = res2.get("answer", "")

            evidence = [
                f"Turn 1 ('{case.input_data['turn1']}'): cid={cid}",
                f"Turn 2 ('{case.input_data['turn2']}'): answer='{answer2}'",
            ]

            expected_dates = case.expected_output["turn2_contains"]
            excluded_dates = case.expected_output["turn2_excludes"]
            answer_lower = answer2.casefold()
            passed = (
                res2["conversation_id"] == cid
                and any(date.casefold() in answer_lower for date in expected_dates)
                and not any(date.casefold() in answer_lower for date in excluded_dates)
            )
            expected_str = "Turn 2 resolves 'it' to the Galaxy S26 Ultra and gives its purchase date as May 12, 2026"
            actual_str = f"Turn 2 Answer: '{answer2}'"

            if passed:
                evidence.append("PASS: Multi-turn follow-up pronoun 'it' correctly resolved.")
            else:
                evidence.append("FAIL: Failed to resolve follow-up context.")

            return passed, expected_str, actual_str, evidence, {"answer2": answer2}

        return False, "Known test case", "Unknown subcase", ["Invalid test case"], {}

    def _eval_web_research(self, case: EvalTestCase) -> tuple[bool, str, str, List[str], Dict[str, Any]]:
        q = case.input_data["question"]
        freshness = _classify_freshness(q)
        calls: List[str] = []
        external_calls: List[str] = []
        published_at = (
            case.expected_output.get("source_published_at")
            or "2026-10-01"
        )

        def mock_web_search(query: str) -> List[Dict[str, Any]]:
            calls.append(query)
            return [{
                "title": "Python release/security information",
                "url": "https://docs.python.org/3/",
                "snippet": "Official Python documentation and release information.",
                "published_at": published_at,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "search_provider": "evaluation transport fixture",
            }]

        def mock_external_search(
            _db: Session,
            _user_id: str,
            query: str,
            device_context: Optional[Dict[str, Any]] = None,
        ) -> List[Dict[str, Any]]:
            external_calls.append(query)
            return []

        with (
            patch.object(assistant_graph, "search_web", side_effect=mock_web_search),
            patch.object(
                assistant_graph,
                "search_external_information",
                side_effect=mock_external_search,
            ),
        ):
            res = run_assistant_chat(self.db, self.user.id, q)

        sources = res.get("sources", [])
        web_sources = [source for source in sources if source.get("is_web")]
        answer = res.get("answer", "")
        evidence = [
            f"Question: '{q}'",
            f"Freshness classification: '{freshness}'",
            f"Web search calls: {len(calls)}",
            f"External-notice search calls: {len(external_calls)}",
            f"Web sources returned: {web_sources}",
            f"Answer: '{answer}'",
            "External search transport: deterministic local fixture; no live web was queried.",
        ]

        if case.id == "web_freshness_current_trigger":
            passed = (
                freshness in ("current", "mixed")
                and len(calls) > 0
                and bool(web_sources)
                and all(source.get("url") and source.get("retrieved_at") for source in web_sources)
            )
            expected_str = "Current question invokes web search and returns a cited source with URL and retrieval timestamp"
            actual_str = (
                f"Freshness: {freshness}; search calls: {len(calls)}; "
                f"web sources with URL and timestamp: "
                f"{sum(bool(s.get('url') and s.get('retrieved_at')) for s in web_sources)}"
            )
        elif case.id == "web_freshness_stable_personal":
            expected_fact = case.expected_output["personal_answer_contains"].casefold()
            passed = (
                freshness == "stable"
                and not calls
                and not external_calls
                and expected_fact in answer.casefold()
            )
            expected_str = "Stable personal question uses the saved asset record and invokes no external research"
            actual_str = (
                f"Freshness: {freshness}; web calls: {len(calls)}; "
                f"external calls: {len(external_calls)}; personal fact present: "
                f"{expected_fact in answer.casefold()}; answer: '{answer}'"
            )
        elif case.id == "web_stale_source_date_disclosure":
            old_publication_date = case.expected_output["source_published_at"]
            published_sources = [
                source for source in web_sources
                if source.get("published_at") == old_publication_date
            ]
            passed = (
                freshness in ("current", "mixed")
                and len(calls) > 0
                and bool(published_sources)
                and all(source.get("retrieved_at") for source in published_sources)
            )
            expected_str = (
                f"Web source metadata preserves publication date {old_publication_date} "
                "and includes the retrieval timestamp"
            )
            actual_str = f"Matching stale sources: {published_sources}; answer: '{answer}'"
        else:
            return False, "Known web research case", "Unknown case", ["Invalid evaluation case"], {}

        evidence.append("PASS: Web research behavior matched the check." if passed else "FAIL: Web research behavior did not match the check.")
        return passed, expected_str, actual_str, evidence, {
            "freshness": freshness,
            "web_search_calls": calls,
            "external_search_calls": external_calls,
            "web_sources": web_sources,
        }


    def _eval_radar_monitoring(self, case: EvalTestCase) -> tuple[bool, str, str, List[str], Dict[str, Any]]:
        # Seed user product
        graph = get_graph_store(self.db)
        product = graph.upsert_node(
            self.user.id,
            type="product",
            name="Samsung Galaxy S26 Ultra",
            attributes={"model_code": "SM-S926B"},
        )
        self.db.commit()

        item_data = case.input_data["external_item"]
        item = publish_external_item(
            self.db,
            source_name=item_data["source"],
            title=item_data["title"],
            body=item_data["body"],
            category=item_data["category"],
            metadata=item_data.get("metadata"),
        )

        # Keep the suite deterministic: exercise monitor matching on the case's
        # supplied item without polling configured production/news feeds.
        with patch.object(ResearchAgent, "poll", return_value=None):
            summary = run_monitoring(self.db, self.user.id)
        runs = summary.get("runs", [])
        matched_run = next((r for r in runs if r["item"] == item_data["title"]), None)

        outcome = matched_run["outcome"] if matched_run else "no_match"
        evidence = [
            f"External Item: '{item_data['title']}'",
            f"User Model Code: SM-S926B",
            f"Radar Monitor Outcome: '{outcome}'",
            f"Summary Alerts: {summary.get('alerts')}, Suppressed: {summary.get('suppressed')}",
        ]
        item_alerts = (
            self.db.query(Alert)
            .filter(Alert.user_id == self.user.id, Alert.external_item_id == item.id)
            .all()
        )
        evidence.append(
            f"Alerts tied to this external item: "
            f"{[(alert.entity_id, alert.headline) for alert in item_alerts]}"
        )

        if case.id == "radar_relevant_alert":
            passed = (
                outcome == "alerted"
                and any(alert.entity_id == product.id for alert in item_alerts)
            )
            expected_str = "Monitor outcome: alerted for the tracked Galaxy S26 Ultra entity"
            actual_str = f"Monitor outcome: {outcome}; tied alerts: {len(item_alerts)}"
            if passed:
                evidence.append("PASS: Relevant device alert successfully generated.")
            else:
                evidence.append("FAIL: Relevant device alert was not generated.")
            return passed, expected_str, actual_str, evidence, {"outcome": outcome}

        elif case.id == "radar_mismatched_model_suppression":
            passed = (
                outcome in ("refuted", "below_threshold", "no_match")
                and not item_alerts
            )
            expected_str = "Monitor outcome: refuted / no_match (Alert suppressed)"
            actual_str = f"Monitor outcome: {outcome}; alerts: {summary.get('alerts', 0)}"
            if passed:
                evidence.append("PASS: Mismatched model recall notice was correctly refuted and suppressed.")
            else:
                evidence.append("FAIL: False positive alert was generated for mismatched model.")
            return passed, expected_str, actual_str, evidence, {"outcome": outcome}

        elif case.id == "radar_irrelevant_news_suppression":
            passed = outcome == "no_match" and not item_alerts
            expected_str = "Monitor outcome: no_match; no alert for unrelated market news"
            actual_str = f"Monitor outcome: {outcome}; alerts: {summary.get('alerts', 0)}"
            if passed:
                evidence.append("PASS: Irrelevant general news produced no personal alert.")
            else:
                evidence.append("FAIL: Irrelevant news generated an alert or unexpected monitor outcome.")
            return passed, expected_str, actual_str, evidence, {"outcome": outcome}

        return False, "Known test case", "Unknown subcase", ["Invalid test case"], {}

    def _eval_hallucination_safety(self, case: EvalTestCase) -> tuple[bool, str, str, List[str], Dict[str, Any]]:
        q = case.input_data["question"]
        graph = get_graph_store(self.db)
        before_relationships = {
            (rel.source_id, rel.target_id, rel.type.upper())
            for rel in graph.relationships(self.user.id)
        }
        res = run_assistant_chat(self.db, self.user.id, q)
        answer = res.get("answer", "")
        after_relationships = {
            (rel.source_id, rel.target_id, rel.type.upper())
            for rel in graph.relationships(self.user.id)
        }
        added_relationships = after_relationships - before_relationships

        evidence = [
            f"Question: '{q}'",
            f"Assistant Answer: '{answer}'",
            f"Relationships added by answering: {sorted(added_relationships)}",
        ]

        if case.id == "safety_missing_personal_data":
            # Expect answer to indicate no car record found without inventing a brand (BMW, Toyota, Honda, etc.)
            low = answer.lower()
            indicates_missing = any(kw in low for kw in ["don't", "don't have", "no record", "not found", "haven't", "cannot find", "no information"])
            hallucinated = any(brand in low for brand in ["bmw", "mercedes", "audi", "toyota", "honda", "ford", "tesla", "hyundai"])

            passed = indicates_missing and not hallucinated
            expected_str = "Indicates missing car record; zero hallucinated car make/model"
            actual_str = f"Answer: '{answer}'"

            if passed:
                evidence.append("PASS: System safely disclosed missing information without hallucinating.")
            else:
                evidence.append("FAIL: System hallucinated unrecorded personal asset or failed missing disclosure.")

            return passed, expected_str, actual_str, evidence, {"answer": answer}

        elif case.id == "safety_unsupported_relationships":
            low = answer.lower()
            states_unknown = any(
                phrase in low
                for phrase in (
                    "not specified",
                    "no record",
                    "don't know",
                    "do not know",
                    "can't determine",
                    "cannot determine",
                    "not in",
                    "no information",
                    "unable to",
                )
            )
            passed = states_unknown and not added_relationships
            expected_str = "Assistant says the issuing bank is not recorded and creates no new graph relationship"
            actual_str = f"Answer: '{answer}'"

            if passed:
                evidence.append("PASS: Missing relationship was disclosed and the graph remained unchanged.")
            else:
                evidence.append("FAIL: The answer asserted an unsupported relationship or did not disclose missing evidence.")

            return passed, expected_str, actual_str, evidence, {
                "answer": answer,
                "relationships_added": sorted(added_relationships),
            }

        return False, "Known test case", "Unknown subcase", ["Invalid test case"], {}
