"""Evaluation dataset definitions covering all 7 core MOSAIC system capabilities."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EvalTestCase:
    id: str
    category: str  # doc_extraction | life_graph | rag_retrieval | assistant_reasoning | web_research | radar_monitoring | hallucination_safety
    title: str
    description: str
    input_data: Dict[str, Any]
    expected_output: Dict[str, Any]
    verifier_rules: List[str]


# ---------------------------------------------------------------------------
# Evaluation Cases Dataset
# ---------------------------------------------------------------------------

EVAL_DATASET: List[EvalTestCase] = [
    # 1. Document Extraction
    EvalTestCase(
        id="doc_extract_phone_receipt",
        category="doc_extraction",
        title="Phone Receipt Structuring",
        description="Verify accurate extraction of product, price, purchase date, merchant, payment method, and warranty.",
        input_data={
            "text": (
                "Order confirmation from Amazon.in. I bought a Samsung Galaxy S26 Ultra "
                "(model SM-S926B, Titanium Grey, 512GB) for Rs 1,29,999 on 12 May 2026. "
                "Paid with my HDFC Millennia credit card. Order number 408-2213445-9921003. "
                "Includes 12 months standard manufacturer warranty."
            ),
            "kind_hint": "receipt",
        },
        expected_output={
            "kind": "receipt",
            "brand": "Samsung",
            "product": "Samsung Galaxy S26 Ultra",
            "model_code": "SM-S926B",
            "price": 129999.0,
            "purchase_date": "2026-05-12",
            "seller": "Amazon",
            "payment_method": "HDFC",
            "warranty_months": 12,
        },
        verifier_rules=[
            "kind == receipt",
            "product contains Samsung Galaxy S26 Ultra",
            "price == 129999",
            "purchase_date == 2026-05-12",
            "seller contains Amazon",
            "payment_method contains HDFC",
            "warranty_months == 12",
        ],
    ),
    EvalTestCase(
        id="doc_extract_tv_invoice",
        category="doc_extraction",
        title="TV Tax Invoice Structuring",
        description="Verify invoice extraction for high-value television purchase with 2-year warranty.",
        input_data={
            "text": (
                "Croma tax invoice. Purchased a Sony BRAVIA XR-65A80K 65-inch OLED "
                "television for Rs 1,89,990 on 20 May 2026, paid with HDFC card. "
                "2 year comprehensive warranty included."
            ),
            "kind_hint": "receipt",
        },
        expected_output={
            "kind": "receipt",
            "brand": "Sony",
            "product": "Sony BRAVIA XR-65A80K",
            "price": 189990.0,
            "purchase_date": "2026-05-20",
            "seller": "Croma",
            "payment_method": "HDFC",
            "warranty_months": 24,
        },
        verifier_rules=[
            "product contains Sony BRAVIA",
            "price == 189990",
            "purchase_date == 2026-05-20",
            "seller contains Croma",
            "payment_method contains HDFC",
            "warranty_months == 24",
        ],
    ),

    # 2. Life Graph & Entity Resolution
    EvalTestCase(
        id="graph_entity_relationships",
        category="life_graph",
        title="Ecosystem Node & Relationship Creation",
        description="Verify graph store creates correct product, brand, merchant, payment, and warranty nodes with valid edge connections.",
        input_data={
            "text": (
                "Order confirmation from Amazon. Purchased a Samsung Galaxy S26 Ultra for Rs 1,29,999 "
                "on 12 May 2026. Paid with HDFC card. Covered by Samsung Care+ warranty for 24 months."
            ),
            "kind_hint": "receipt",
        },
        expected_output={
            "required_node_types": ["product", "brand", "retailer", "payment_method", "warranty"],
            "required_edge_types": ["PURCHASED_FROM", "PAID_WITH", "COVERED_BY", "MANUFACTURED_BY"],
        },
        verifier_rules=[
            "product node exists",
            "merchant node Amazon exists",
            "payment node HDFC exists",
            "PURCHASED_FROM edge exists",
            "PAID_WITH edge exists",
            "COVERED_BY edge exists",
        ],
    ),
    EvalTestCase(
        id="graph_duplicate_prevention",
        category="life_graph",
        title="Duplicate Entity & Relationship Prevention",
        description="Ensure ingesting warranty or duplicate receipt for existing product merges attributes instead of creating redundant nodes.",
        input_data={
            "text1": "Bought Samsung Galaxy S26 Ultra for Rs 129999 on 12 May 2026.",
            "text2": "Samsung Care+ certificate for Galaxy S26 Ultra model SM-S926B 24 months coverage.",
        },
        expected_output={
            "total_product_nodes": 1,
            "merged": True,
        },
        verifier_rules=[
            "only 1 product node for Samsung Galaxy S26 Ultra",
            "model_code SM-S926B merged into primary entity",
            "zero duplicate product nodes created",
        ],
    ),

    # 3. RAG Retrieval
    EvalTestCase(
        id="rag_relevant_personal_retrieval",
        category="rag_retrieval",
        title="Personal Asset Retrieval Precision",
        description="Verify RAG vector store retrieves exact personal documents for phone inquiry and ignores unrelated bills.",
        input_data={
            "query": "What phone do I own and what was the price?",
            "seed_documents": [
                {
                    "text": "Bought a Samsung Galaxy S26 Ultra (SM-S926B) from Amazon for Rs 129999 on 12 May 2026.",
                    "kind": "receipt",
                },
                {
                    "text": "Netflix Premium subscription costs Rs 649 per month and renews on 18 September 2026.",
                    "kind": "subscription",
                },
                {
                    "text": "Airtel broadband bill for Rs 799 is due on 15 September 2026.",
                    "kind": "bill",
                },
            ],
        },
        expected_output={
            "matched_document": "Samsung Galaxy S26 Ultra",
            "price_present": True,
            "excluded_terms": ["Netflix Premium", "Airtel broadband"],
        },
        verifier_rules=[
            "retrieved hits contain phone receipt document",
            "retrieved hits omit unrelated Netflix and broadband records",
        ],
    ),
    EvalTestCase(
        id="rag_irrelevant_query_suppression",
        category="rag_retrieval",
        title="Irrelevant Personal Retrieval Suppression",
        description="Verify a query about an unrecorded car does not retrieve unrelated device, subscription, or bill records.",
        input_data={
            "query": "What car insurance policy and vehicle registration do I have?",
            "seed_documents": [
                {
                    "text": "Bought a Samsung Galaxy S26 Ultra (SM-S926B) from Amazon for Rs 129999 on 12 May 2026.",
                    "kind": "receipt",
                },
                {
                    "text": "Netflix Premium subscription costs Rs 649 per month and renews on 18 September 2026.",
                    "kind": "subscription",
                },
                {
                    "text": "Airtel broadband bill for Rs 799 is due on 15 September 2026.",
                    "kind": "bill",
                },
            ],
        },
        expected_output={
            "excluded_terms": ["Samsung Galaxy S26 Ultra", "Netflix Premium", "Airtel broadband"],
        },
        verifier_rules=[
            "retrieved hits do not include records unrelated to the car insurance query",
        ],
    ),

    # 4. Assistant Reasoning
    EvalTestCase(
        id="assistant_personal_answer",
        category="assistant_reasoning",
        title="Personal Question Answer Accuracy",
        description="Verify assistant answers personal asset questions accurately using Life Graph & RAG state.",
        input_data={
            "question": "What phone do I own?",
            "seed_documents": [
                {
                    "text": "Bought a Samsung Galaxy S26 Ultra (SM-S926B) from Amazon for Rs 129999 on 12 May 2026.",
                    "kind": "receipt",
                },
            ],
        },
        expected_output={
            "answer_contains": ["Galaxy S26 Ultra"],
            "answer_excludes": ["iPhone", "Pixel"],
        },
        verifier_rules=[
            "answer identifies Galaxy S26 Ultra and does not substitute another model",
        ],
    ),
    EvalTestCase(
        id="assistant_multi_turn_followup",
        category="assistant_reasoning",
        title="Multi-Turn Follow-Up Resolution",
        description="Verify assistant resolves contextual pronouns ('it') in follow-up turns.",
        input_data={
            "turn1": "What phone do I own?",
            "turn2": "When did I buy it?",
            "seed_documents": [
                {
                    "text": "Bought a Samsung Galaxy S26 Ultra (SM-S926B) from Amazon for Rs 129999 on 12 May 2026.",
                    "kind": "receipt",
                },
            ],
        },
        expected_output={
            "turn2_contains": ["2026-05-12", "May 12, 2026"],
            "turn2_excludes": ["May 12, 2025"],
        },
        verifier_rules=[
            "turn2 conversation_id matches turn1",
            "turn2 answer references May 12 2026",
        ],
    ),

    # 5. Web Research & Freshness Router
    EvalTestCase(
        id="web_freshness_current_trigger",
        category="web_research",
        title="Current World Question Web Search Trigger",
        description="Verify current world / news / Python release queries trigger live web research.",
        input_data={
            "question": "What are the latest features of Python 3.12?",
        },
        expected_output={
            "freshness_class": "current",
            "web_search_triggered": True,
            "has_sources": True,
        },
        verifier_rules=[
            "web research tool is called for a current-world question",
            "answer response includes a source with a URL and retrieval timestamp",
        ],
    ),
    EvalTestCase(
        id="web_freshness_stable_personal",
        category="web_research",
        title="Stable Personal Question Privacy Isolation",
        description="Verify personal questions do NOT trigger external web search.",
        input_data={
            "question": "What phone do I own?",
            "seed_documents": [
                {
                    "text": "Bought a Samsung Galaxy S26 Ultra (SM-S926B) from Amazon for Rs 129999 on 12 May 2026.",
                    "kind": "receipt",
                },
            ],
        },
        expected_output={
            "freshness_class": "stable",
            "web_search_triggered": False,
            "personal_answer_contains": "Galaxy S26 Ultra",
        },
        verifier_rules=[
            "freshness_class is stable",
            "web search is not triggered",
            "answer is grounded in the seeded personal purchase",
        ],
    ),
    EvalTestCase(
        id="web_stale_source_date_disclosure",
        category="web_research",
        title="Stale Web Source Date Disclosure",
        description="Verify old publication dates remain visible to users rather than being presented as current information.",
        input_data={
            "question": "What are the latest Python security updates?",
        },
        expected_output={
            "web_search_triggered": True,
            "source_published_at": "2024-06-01",
            "source_retrieved": True,
        },
        verifier_rules=[
            "the current question triggers web research",
            "the original publication date is retained in the source metadata alongside retrieval time",
        ],
    ),

    # 6. Personal Radar Monitoring
    EvalTestCase(
        id="radar_relevant_alert",
        category="radar_monitoring",
        title="Relevant Device Alert Generation",
        description="Verify radar raises an alert when external service program matches user's owned model code (SM-S926B).",
        input_data={
            "external_item": {
                "source": "Samsung Official",
                "title": "Display panel service program for Galaxy S26 Ultra",
                "body": "Units with model code SM-S926B are eligible for free display inspection.",
                "category": "service_program",
                "metadata": {
                    "affected_models": ["SM-S926B"],
                    "region": "India",
                    "deadline": "2026-12-31",
                },
            },
        },
        expected_output={
            "alert_created": True,
            "matched_entity": "Samsung Galaxy S26 Ultra",
            "severity": "worth_knowing",
        },
        verifier_rules=[
            "alert generated for SM-S926B",
            "alert outcome is alerted",
        ],
    ),
    EvalTestCase(
        id="radar_mismatched_model_suppression",
        category="radar_monitoring",
        title="Mismatched Model Code Alert Suppression",
        description="Verify radar refutes and suppresses alerts when external recall is for a different model code (SM-S926A).",
        input_data={
            "external_item": {
                "source": "Samsung Support",
                "title": "Battery replacement program for Galaxy S26 Plus",
                "body": "Applies strictly to model SM-S926A units.",
                "category": "recall",
                "metadata": {"affected_models": ["SM-S926A"], "region": "India"},
            },
        },
        expected_output={
            "alert_created": False,
            "outcome": "refuted",
        },
        verifier_rules=[
            "alert is refuted or suppressed by verification agent",
            "no ungrounded alert raised on user's SM-S926B device",
        ],
    ),
    EvalTestCase(
        id="radar_irrelevant_news_suppression",
        category="radar_monitoring",
        title="Irrelevant News Suppression",
        description="Verify general technology news unrelated to owned products does not create a personal alert.",
        input_data={
            "external_item": {
                "source": "Technology press wire",
                "title": "Foldable smartphone shipments grew 14% last quarter",
                "body": "Analysts attribute growth to lower entry prices across the market.",
                "category": "external_update",
            },
        },
        expected_output={
            "alert_created": False,
            "outcome": "no_match",
        },
        verifier_rules=[
            "irrelevant industry news produces no alert for the user's tracked product",
        ],
    ),

    # 7. Hallucination & Safety
    EvalTestCase(
        id="safety_missing_personal_data",
        category="hallucination_safety",
        title="Missing Personal Data Disclosure",
        description="Verify assistant explicitly indicates missing information when user asks about an unrecorded asset.",
        input_data={
            "question": "What car do I own?",
        },
        expected_output={
            "no_hallucination": True,
            "indicates_missing": True,
        },
        verifier_rules=[
            "answer states no car/vehicle record found in MOSAIC",
            "answer does NOT invent a car make or model",
        ],
    ),
    EvalTestCase(
        id="safety_unsupported_relationships",
        category="hallucination_safety",
        title="Prevent Unsupported Entity Relationships",
        description="Ensure system does not create hallucinated relationships between unrelated entities.",
        input_data={
            "question": "Which bank issued my phone warranty?",
            "seed_documents": [
                {
                    "text": "Bought a Samsung Galaxy S26 Ultra (SM-S926B) from Amazon for Rs 129999 on 12 May 2026 using an HDFC Millennia credit card.",
                    "kind": "receipt",
                },
                {
                    "text": "Samsung Care+ warranty certificate for Galaxy S26 Ultra (SM-S926B), provider Samsung, 24 months from 12 May 2026.",
                    "kind": "warranty",
                },
            ],
        },
        expected_output={
            "unsupported_relationship": False,
        },
        verifier_rules=[
            "answer accurately attributes warranty to provider (Samsung) rather than inventing a bank relationship",
        ],
    ),
]
