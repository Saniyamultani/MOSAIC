"""LLM provider abstraction.

Nothing above this layer knows which model is running.  `GeminiProvider` talks to
the Google Generative Language API; `OfflineProvider` is a deterministic
rule-based stand-in so the whole system (including the demo) runs with no API key
and no network.  Swapping in OpenAI/Anthropic/Ollama later means adding one file.
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def parse_json_loose(raw: str) -> Any:
    """Best-effort JSON extraction from a model response."""
    if raw is None:
        raise ValueError("empty response")
    text = raw.strip()
    fence = JSON_FENCE.search(text)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = min(
        [i for i in (text.find("{"), text.find("[")) if i != -1] or [-1]
    )
    if start == -1:
        raise ValueError(f"no JSON found in response: {raw[:200]}")
    end = max(text.rfind("}"), text.rfind("]"))
    return json.loads(text[start : end + 1])


class LLMProvider(ABC):
    """Every capability MOSAIC needs from a language model."""

    name: str = "base"
    available: bool = True

    # --- raw primitives -----------------------------------------------------
    @abstractmethod
    def generate(self, prompt: str, system: str | None = None) -> str: ...

    @abstractmethod
    def generate_json(self, prompt: str, system: str | None = None) -> Any: ...

    def extract_document(
        self,
        text: str,
        kind_hint: str | None = None,
        image_bytes: bytes | None = None,
        mime_type: str | None = None,
    ) -> dict:
        raise NotImplementedError

    def resolve_entity(self, candidate: dict, existing: list[dict]) -> dict:
        raise NotImplementedError

    def assess_connection(self, item: dict, entity: dict, evidence: list[dict]) -> dict:
        raise NotImplementedError

    def skeptic_review(self, item: dict, entity: dict, claim: dict, evidence: list[dict]) -> dict:
        raise NotImplementedError

    def compose_alert(self, context: dict) -> dict:
        raise NotImplementedError

    def answer_question(
        self, question: str, context: str, history: list[dict[str, str]] | None = None
    ) -> str:
        """Answer a user question using only the context supplied by MOSAIC."""
        normalized_question = re.sub(r"[^a-z\s]", "", question.lower()).strip()
        if normalized_question in {"hi", "hello", "hey", "good morning", "good afternoon", "good evening"}:
            return "Hello! How can I help you today?"

        history_text = "\n".join(
            f"{message['role'].upper()}: {message['content']}"
            for message in (history or [])
        )
        prompt = (
            f"CONVERSATION HISTORY:\n{history_text or '(no previous messages)'}\n\n"
            f"CURRENT QUESTION:\n{question}\n\nMOSAIC CONTEXT:\n{context}"
        )
        return self.generate(
            prompt,
            "You are MOSAIC Assistant, an intelligent, live, warm, and helpful conversational agent. "
            "Continue the conversation naturally: resolve references such as 'that bill', 'it', 'their', 'mine', or 'what about it' from conversation history. "
            "FORMATTING & RESPONSE INSTRUCTIONS:\n"
            "1. Answer the user's question directly in the very first sentence.\n"
            "2. Return clean Markdown format: use **bold** for key facts, bullet/numbered lists for details, headings, and Markdown comparison tables when comparing devices or options.\n"
            "3. Keep paragraphs short and readable.\n"
            "4. NEVER output raw debug context, unformatted search chunks, or chain-of-thought.\n"
            "5. For missing personal data, explain politely that they haven't logged this activity in MOSAIC yet.\n"
            "6. Never invent false details and do NOT use em dashes (—).\n"
            "7. NEVER use meta-preambles like 'According to web search', 'Based on current web research', or 'According to MOSAIC'. Answer the user directly and plain.\n"
            "8. When web search results are available, synthesize a complete, comprehensive, and detailed explanation covering all facts, specs, prices, and features.\n"
            "9. Always include clickable Markdown links [Source Title](URL) for web results whenever URLs are present in the context.",
        )
