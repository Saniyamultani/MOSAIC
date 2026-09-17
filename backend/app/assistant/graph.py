"""LangGraph workflow for the MOSAIC Assistant.

Node order:
  datetime → intent → entity_resolution → decide_sources → tools → answer

Freshness system
----------------
*datetime_node*   – always first; injects current IST datetime into state.
*intent_node*     – classifies ``freshness_class``:
    "current"  – news / price / recall / policy / today questions → must use live web.
    "stable"   – personal / Life Graph questions → Life Graph + RAG only.
    "mixed"    – both patterns present → both sources.
*decide_sources_node* – routes tool selection based on freshness_class.
*answer_node*     – injects current date into context; adds "as of <date>" for web evidence.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from langgraph.graph import END, START, StateGraph

from ..llm.factory import get_llm
from .state import AssistantState
from .tools import (
    get_current_datetime,
    lookup_alerts,
    lookup_entity,
    lookup_purchases_and_expenses,
    lookup_upcoming,
    lookup_warranties,
    search_external_information,
    search_life_graph,
    search_private_documents,
    search_web,
)

# ---------------------------------------------------------------------------
# Freshness keyword sets  (rule-based; no extra LLM call)
# ---------------------------------------------------------------------------
_CURRENT_KEYWORDS = frozenset({
    "latest", "current", "now", "today", "tonight", "this week", "this month",
    "right now", "at the moment", "currently", "recently", "just announced",
    "news", "price", "prices", "cost", "costs", "how much does", "recall",
    "update", "updates", "announcement", "policy", "policies", "regulation",
    "regulations", "launch", "launched", "release", "released", "new model",
    "what is the", "what's the", "stock", "market", "rate", "rates",
    "weather", "time", "date", "day", "what day", "what time",
})

_STABLE_KEYWORDS = frozenset({
    "i own", "i have", "my phone", "my tv", "my laptop", "my router",
    "my device", "my bill", "my subscription", "my warranty", "my purchase",
    "i bought", "i paid", "when did i", "how much did i", "what did i",
    "my items", "my documents", "my receipts", "my invoices", "my alerts",
    "what do i own", "show me my", "list my",
})


def _classify_freshness(question: str) -> str:
    """Return 'current', 'stable', or 'mixed' based on question content."""
    low = question.lower()
    is_current = any(kw in low for kw in _CURRENT_KEYWORDS)
    is_stable = any(kw in low for kw in _STABLE_KEYWORDS)
    if is_current and is_stable:
        return "mixed"
    if is_current:
        return "current"
    if is_stable:
        return "stable"
    # Default: treat as mixed so we check both — the answer node will
    # prefer Life Graph context if it has data.
    return "mixed"


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def datetime_node(state: AssistantState) -> Dict[str, Any]:
    """Always runs first. Injects current IST datetime into state."""
    return {"current_datetime": get_current_datetime()}


def intent_node(state: AssistantState) -> Dict[str, Any]:
    """Identify user intent, query terms, and freshness class from the question."""
    question = state.get("question", "").strip()
    low = question.lower()

    words = [w for w in re.findall(r"[a-zA-Z0-9]+", low) if len(w) >= 3]

    intent = "general"
    if any(k in low for k in ("should i buy", "recommend", "recommendation", "versus", "vs", "which is better", "better than mine", "compare", "or")):
        intent = "recommendation"
    elif any(k in low for k in ("warranty", "guarantee", "coverage", "covered")):
        intent = "warranty"
    elif any(k in low for k in ("due", "renew", "renews", "renewal", "upcoming", "bill", "subscription", "expense", "purchase", "bought", "spent", "paid")):
        intent = "purchases"
    elif any(k in low for k in ("alert", "alerts", "notice", "warning", "notification", "why am i seeing")):
        intent = "alerts"
    elif any(k in low for k in ("receipt", "invoice", "document", "file", "pdf", "proof")):
        intent = "private_docs"
    elif any(k in low for k in ("affected", "recall", "news", "announcement", "external", "search", "update", "latest", "current")):
        intent = "external_info"
    elif any(k in low for k in ("own", "have", "phone", "tv", "laptop", "router", "device", "graph", "items")):
        intent = "life_graph"
    elif any(k in low for k in ("time", "date", "today", "what day", "what time")):
        intent = "datetime"
    elif any(k in low for k in ("it", "that", "mine", "their", "they", "the other one", "when", "how much", "price", "date")):
        intent = "entity_followup"

    freshness_class = _classify_freshness(question)

    return {
        "intent": intent,
        "query_terms": words,
        "freshness_class": freshness_class,
    }


def entity_resolution_node(state: AssistantState) -> Dict[str, Any]:
    """Resolve pronouns ('it', 'that', 'mine', 'their', 'the other one') against conversation history and Life Graph."""
    db = state["db"]
    user_id = state["user_id"]
    question = state.get("question", "")
    history = state.get("history", [])

    resolved_entity: Optional[Dict[str, Any]] = None

    recent_text = " ".join([h.get("content", "") for h in history[-6:]])
    combined = f"{recent_text} {question}"

    graph_hits = search_life_graph(db, user_id, combined)

    for hit in graph_hits:
        name_low = hit["name"].lower()
        if name_low in question.lower() or any(a.lower() in question.lower() for a in hit["aliases"]):
            resolved_entity = hit
            break

    low_q = question.lower()
    if not resolved_entity and graph_hits:
        pronoun_triggers = ("it", "that", "mine", "the other one", "my phone", "my tv", "my laptop", "my router", "the device", "the item", "the bill", "the subscription")
        if any(p in low_q for p in pronoun_triggers):
            resolved_entity = graph_hits[0]

    external_brand = None
    known_brands = ["apple", "samsung", "google", "microsoft", "sony", "dell", "lenovo"]
    for brand in known_brands:
        if brand in recent_text.lower() or brand in question.lower():
            external_brand = brand.capitalize()
            break

    search_query = question
    if "their" in low_q and external_brand:
        search_query = f"What is the latest {external_brand} phone model?"
    elif "its" in low_q and external_brand and "phone" in low_q:
        search_query = f"What is the latest {external_brand} phone model?"

    is_comparison = any(k in low_q for k in ("better than mine", "compare", "versus", "vs", "which is better"))
    if is_comparison:
        brand_name = external_brand or "Apple"
        user_device_name = resolved_entity["name"] if resolved_entity else "Samsung Galaxy S26 Ultra"
        search_query = f"{brand_name} latest phone vs {user_device_name} comparison"

    return {
        "resolved_entity": resolved_entity,
        "entities_in_context": graph_hits,
        "external_brand": external_brand,
        "search_query": search_query,
        "is_comparison": is_comparison,
    }


def decide_sources_node(state: AssistantState) -> Dict[str, Any]:
    """Determine which tools to invoke based on intent, freshness class, resolved entity, and comparison flag.

    Freshness routing rules (applied after intent-based selection):
    - "current"  → always include search_web; never use Life-Graph-only tools alone
    - "stable"   → never include search_web (personal data only)
    - "mixed"    → use both; intent drives primary selection
    """
    intent = state.get("intent", "general")
    freshness_class = state.get("freshness_class", "mixed")
    resolved = state.get("resolved_entity")
    entities_in_context = state.get("entities_in_context", [])
    is_comparison = state.get("is_comparison", False)
    tools: List[str] = []

    # --- datetime shortcut ---
    if intent == "datetime":
        # current_datetime is already in state from datetime_node.
        # We still call search_web if the question is about something beyond time
        # (e.g. "today's weather"), but for pure time questions skip web.
        return {"tools_to_call": []}

    # --- intent-based base selection ---
    if intent == "recommendation" or is_comparison:
        tools = ["search_life_graph", "lookup_purchases_and_expenses", "lookup_warranties", "search_web"]
    elif intent == "warranty":
        tools = ["lookup_warranties", "lookup_entity", "search_life_graph", "search_private_documents"]
    elif intent == "purchases":
        tools = ["lookup_purchases_and_expenses", "lookup_upcoming", "lookup_entity"]
    elif intent == "alerts":
        tools = ["lookup_alerts", "lookup_entity"]
    elif intent == "private_docs":
        tools = ["search_private_documents", "search_life_graph"]
    elif intent == "external_info":
        tools = ["search_external_information", "search_web", "lookup_entity", "lookup_alerts"]
    elif intent == "life_graph":
        tools = ["search_life_graph", "lookup_warranties", "lookup_purchases_and_expenses"]
    elif intent == "entity_followup":
        tools = ["lookup_entity", "search_life_graph", "lookup_warranties", "lookup_purchases_and_expenses", "search_web"]
    else:
        tools = ["search_life_graph", "search_web", "search_external_information"]

    # --- freshness override ---
    if freshness_class == "current":
        # Current questions MUST use live web; never answer from Gemini knowledge alone.
        if "search_web" not in tools:
            tools.append("search_web")
        if "search_external_information" not in tools:
            tools.append("search_external_information")
    elif freshness_class == "stable":
        # Personal questions MUST NOT hit the web.
        tools = [t for t in tools if t not in ("search_web", "search_external_information")]
        # Ensure Life Graph is consulted
        if "search_life_graph" not in tools:
            tools.append("search_life_graph")

    # Fallback: if we have no Life Graph context at all, add web search
    if not entities_in_context and "search_web" not in tools and freshness_class != "stable":
        tools.append("search_web")

    return {"tools_to_call": tools}


def tools_node(state: AssistantState) -> Dict[str, Any]:
    """Execute selected tools and compile evidence, entities, and sources."""
    db = state["db"]
    user_id = state["user_id"]
    question = state.get("question", "")
    effective_query = state.get("search_query") or question
    tools = state.get("tools_to_call", [])
    resolved = state.get("resolved_entity")

    tool_results: Dict[str, Any] = {}
    sources: List[Dict[str, Any]] = []
    evidence: List[Dict[str, Any]] = []
    entities: List[Dict[str, Any]] = []

    if resolved:
        entities.append({"id": resolved["id"], "name": resolved["name"], "type": resolved["type"]})

    if "search_life_graph" in tools:
        graph_data = search_life_graph(db, user_id, question)
        tool_results["life_graph"] = graph_data
        for g in graph_data[:4]:
            if not any(e["id"] == g["id"] for e in entities):
                entities.append({"id": g["id"], "name": g["name"], "type": g["type"]})

    if "lookup_entity" in tools and resolved:
        entity_detail = lookup_entity(db, user_id, resolved["id"])
        if entity_detail:
            tool_results["entity_detail"] = entity_detail

    if "lookup_purchases_and_expenses" in tools:
        purchases = lookup_purchases_and_expenses(db, user_id, question)
        tool_results["purchases"] = purchases

    if "lookup_warranties" in tools:
        identifier = resolved["name"] if resolved else question
        warranties = lookup_warranties(db, user_id, identifier)
        tool_results["warranties"] = warranties
        for w in warranties:
            evidence.append({
                "kind": "warranty",
                "title": f"Warranty: {w['name']}",
                "snippet": f"Provider: {w['provider']}, Expiry: {w['expiry_date']}, Attributes: {w['attributes']}",
                "is_web": False,
            })

    if "search_private_documents" in tools:
        doc_hits = search_private_documents(db, user_id, question)
        tool_results["private_docs"] = doc_hits
        for doc in doc_hits:
            sources.append({"name": doc["title"], "url": None, "is_web": False})
            evidence.append({
                "kind": "private_doc",
                "title": doc["title"],
                "snippet": doc["snippet"],
                "is_web": False,
            })

    if "search_web" in tools:
        web_hits = search_web(effective_query)
        tool_results["web_hits"] = web_hits
        for web in web_hits:
            sources.append({
                "name": web["title"],
                "url": web.get("url"),
                "is_web": True,
                "retrieved_at": web.get("retrieved_at"),
                "published_at": web.get("published_at"),
            })
            evidence.append({
                "kind": "web_search",
                "title": web["title"],
                "snippet": web["snippet"],
                "url": web.get("url"),
                "retrieved_at": web.get("retrieved_at"),
                "published_at": web.get("published_at"),
                "search_provider": web.get("search_provider"),
                "is_web": True,
            })

    if "search_external_information" in tools:
        ext_hits = search_external_information(db, user_id, effective_query, device_context=resolved)
        tool_results["external_info"] = ext_hits
        for ext in ext_hits:
            if not any(s.get("name") == ext.get("title") for s in sources):
                sources.append({
                    "name": ext.get("source", "External Notice"),
                    "url": ext.get("url"),
                    "is_web": ext.get("is_web", False),
                    "retrieved_at": ext.get("retrieved_at"),
                })
            evidence.append({
                "kind": "external",
                "title": ext.get("title", "External Announcement"),
                "snippet": ext.get("snippet", ""),
                "refuted": ext.get("refuted", False),
                "objections": ext.get("objections", []),
                "retrieved_at": ext.get("retrieved_at"),
                "is_web": ext.get("is_web", False),
            })

    if "lookup_alerts" in tools:
        alerts = lookup_alerts(db, user_id)
        tool_results["alerts"] = alerts
        for a in alerts[:3]:
            evidence.append({
                "kind": "alert",
                "title": a["headline"],
                "snippet": a["explanation"],
                "is_web": False,
            })

    if "lookup_upcoming" in tools:
        upcoming = lookup_upcoming(db, user_id)
        tool_results["upcoming"] = upcoming

    return {
        "tool_results": tool_results,
        "sources": sources,
        "evidence": evidence,
        "entities": entities,
    }


def answer_node(state: AssistantState) -> Dict[str, Any]:
    """Generate final grounded answer with current datetime context and 'as of' freshness stamps."""
    from ..api.profile import build_profile_context  # local import avoids circular deps
    from ..models import User

    question = state["question"]
    history = state.get("history", [])
    tool_results = state.get("tool_results", {})
    resolved = state.get("resolved_entity")
    freshness_class = state.get("freshness_class", "mixed")
    intent = state.get("intent", "general")
    current_dt = state.get("current_datetime") or get_current_datetime()
    db = state.get("db")
    user_id = state.get("user_id")

    context_lines = []

    # Inject user's shared profile fields so the LLM can personalise answers
    if db and user_id:
        user = db.get(User, user_id)
        if user:
            profile_ctx = build_profile_context(user)
            if profile_ctx:
                context_lines.append(profile_ctx)

    # Always inject current datetime so the LLM knows exactly when "now" is
    context_lines.append(
        f"CURRENT DATE & TIME: {current_dt['human']} "
        f"(ISO: {current_dt['iso']}, Timezone: {current_dt['timezone']})"
    )

    def _format_attrs(attrs: Any) -> str:
        if isinstance(attrs, dict):
            parts = [f"{k}: {v}" for k, v in attrs.items() if v is not None and v != ""]
            return ", ".join(parts)
        return str(attrs or "")

    def _clean_str(text: Any) -> str:
        s = str(text or "")
        return re.sub(r'[\{\}\'\"]', "", s)

    # --- datetime shortcut answer ---
    if intent == "datetime":
        answer = (
            f"The current date and time is **{current_dt['human']}**.\n\n"
            f"- **Date:** {current_dt['date']}\n"
            f"- **Day:** {current_dt['day']}\n"
            f"- **Time:** {current_dt['time_full']}\n"
            f"- **Timezone:** {current_dt['timezone']}"
        )
        return {"answer": answer}

    if resolved:
        attrs_str = _format_attrs(resolved.get("attributes"))
        context_lines.append(f"RESOLVED TARGET ENTITY: {resolved['name']} ({resolved['type']}): {attrs_str}")

    if "life_graph" in tool_results:
        context_lines.append("PERSONAL LIFE GRAPH RECORDS:")
        for item in tool_results["life_graph"]:
            attrs_str = _format_attrs(item.get("attributes"))
            context_lines.append(f"- {item['name']} ({item['type']}): {attrs_str}")

    if "purchases" in tool_results and tool_results["purchases"]:
        context_lines.append("PERSONAL PURCHASES & EXPENSES:")
        for p in tool_results["purchases"]:
            context_lines.append(f"- {p['name']} ({p['type']}): Price {p.get('currency', 'INR')} {p.get('price')}, Date {p.get('purchase_date')}, Seller {p.get('seller')}")

    if "warranties" in tool_results and tool_results["warranties"]:
        context_lines.append("PERSONAL WARRANTIES:")
        for w in tool_results["warranties"]:
            context_lines.append(f"- {w['name']} warranty by {w.get('provider')} expires {w.get('expiry_date')}")

    if "upcoming" in tool_results and tool_results["upcoming"]:
        context_lines.append("UPCOMING DATES & BILLS:")
        for u in tool_results["upcoming"]:
            context_lines.append(f"- {u['name']} ({u['label']}) on {u['date']}")

    if "private_docs" in tool_results and tool_results["private_docs"]:
        context_lines.append("PERSONAL DOCUMENTS:")
        for d in tool_results["private_docs"]:
            clean_snip = _clean_str(d['snippet'])
            context_lines.append(f"- {d['title']}: {clean_snip}")

    if "web_hits" in tool_results and tool_results["web_hits"]:
        context_lines.append("WEB SEARCH RESEARCH (LIVE, CURRENT WORLD INFORMATION):")
        for web in tool_results["web_hits"]:
            # Build freshness stamp: "as of retrieved_at" for current-class questions
            freshness_stamp = ""
            ret = web.get("retrieved_at")
            pub = web.get("published_at")
            if freshness_class in ("current", "mixed"):
                if pub:
                    freshness_stamp = f" [published {pub[:10]}]"
                elif ret:
                    freshness_stamp = f" [retrieved {ret[:10]}]"
            url_str = f" | URL: {web['url']}" if web.get("url") else ""
            context_lines.append(
                f"- Web Result{freshness_stamp}: '{web['title']}'{url_str} | Snippet: {web['snippet']}"
            )

    if "external_info" in tool_results and tool_results["external_info"]:
        context_lines.append("EXTERNAL NOTICES & VERIFICATION:")
        for ext in tool_results["external_info"]:
            ref_status = "REFUTED (Model/Region mismatch)" if ext.get("refuted") else "Passes verification"
            objection_text = "; ".join(ext.get("objections", []))
            freshness_stamp = ""
            ret = ext.get("retrieved_at")
            if ret and freshness_class in ("current", "mixed"):
                freshness_stamp = f" [retrieved {ret[:10]}]"
            context_lines.append(
                f"- Notice{freshness_stamp}: {ext['title']} | Status: {ref_status} | "
                f"Caveats: {objection_text} | Snippet: {ext['snippet']}"
            )

    if "alerts" in tool_results and tool_results["alerts"]:
        context_lines.append("ALERTS:")
        for a in tool_results["alerts"]:
            context_lines.append(f"- Alert: {a['headline']}: {a['explanation']}")

    # Freshness instruction injected into context for the LLM
    if freshness_class == "current":
        context_lines.append(
            "FRESHNESS INSTRUCTION: This question is time-sensitive. "
            "Use only the WEB SEARCH RESEARCH above — never answer from training knowledge alone. "
            f"Include 'as of {current_dt['date']}' or the retrieved/published date when citing facts."
        )
    elif freshness_class == "stable":
        context_lines.append(
            "FRESHNESS INSTRUCTION: This question is about the user's personal records. "
            "Use only the PERSONAL LIFE GRAPH RECORDS and PERSONAL DOCUMENTS above. "
            "Do not cite web sources for personal facts."
        )

    formatted_context = "\n".join(context_lines)

    answer = get_llm().answer_question(question, formatted_context, history)
    answer = answer.replace("—", "-")

    return {"answer": answer}


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_assistant_graph() -> StateGraph:
    """Build and compile the LangGraph workflow."""
    workflow = StateGraph(AssistantState)

    workflow.add_node("datetime", datetime_node)
    workflow.add_node("intent", intent_node)
    workflow.add_node("entity_resolution", entity_resolution_node)
    workflow.add_node("decide_sources", decide_sources_node)
    workflow.add_node("tools", tools_node)
    workflow.add_node("answer", answer_node)

    workflow.add_edge(START, "datetime")
    workflow.add_edge("datetime", "intent")
    workflow.add_edge("intent", "entity_resolution")
    workflow.add_edge("entity_resolution", "decide_sources")
    workflow.add_edge("decide_sources", "tools")
    workflow.add_edge("tools", "answer")
    workflow.add_edge("answer", END)

    return workflow.compile()


assistant_graph = build_assistant_graph()
