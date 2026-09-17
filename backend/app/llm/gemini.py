"""Google Gemini provider (REST, no SDK pin to fight with).

Subclasses OfflineProvider so that any API failure degrades to the deterministic
implementation instead of taking the pipeline down.
"""
from __future__ import annotations

import logging

import httpx

from ..config import settings
from .base import LLMProvider, parse_json_loose
from .offline import OfflineProvider

log = logging.getLogger("mosaic.llm.gemini")

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"

EXTRACTION_SYSTEM = """You are MOSAIC's Ingestion Agent.
Extract structured facts from a personal document (receipt, warranty, bill,
subscription confirmation, calendar note or free text).
Return ONLY JSON with this shape:
{
  "kind": "receipt|warranty|bill|subscription|calendar_event|note",
  "summary": "one short human sentence",
  "confidence": 0.0-1.0,
  "fields": {
    "product": str|null, "brand": str|null, "model": str|null, "model_code": str|null,
    "seller": str|null, "price": number|null, "currency": str|null,
    "purchase_date": "YYYY-MM-DD"|null, "payment_method": str|null, "category": str|null,
    "warranty_months": number|null, "provider": str|null, "start_date": "YYYY-MM-DD"|null,
    "expiry_date": "YYYY-MM-DD"|null, "subscription_name": str|null,
    "billing_cycle": "monthly|yearly"|null, "renewal_date": "YYYY-MM-DD"|null,
    "amount": number|null, "biller": str|null, "due_date": "YYYY-MM-DD"|null,
    "event_title": str|null, "event_date": "YYYY-MM-DD"|null
  }
}
Omit fields you cannot support from the text. Never invent values."""

ALERT_SYSTEM = """You are MOSAIC's Alert Agent.
You write calm, specific, non-alarmist notifications about how an outside-world
change affects something the user owns. Return ONLY JSON:
{"headline": str, "explanation": str, "why_it_matters": [str, ...], "suggested_action": str}
The headline is under 90 characters. The explanation is 1-2 plain sentences and
must reference the user's own item. why_it_matters is the verification checklist,
one short line per check."""

SKEPTIC_SYSTEM = """You are MOSAIC's Skeptic Agent.
Your job is to DISPROVE a proposed match between an external announcement and a
user's item. Look for model mismatches, region mismatches, date mismatches and
vague wording. Return ONLY JSON:
{"refuted": bool, "objections": [str, ...], "surviving_reason": str}"""


class GeminiProvider(OfflineProvider):
    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.google_api_key
        self.model = model or settings.gemini_model
        self.available = bool(self.api_key and len(self.api_key.strip()) > 5)

    # --- primitives ---------------------------------------------------------
    def _call(self, prompt: str | list[dict], system: str | None, json_mode: bool) -> str:
        if isinstance(prompt, list):
            parts = prompt
        else:
            parts = [{"text": str(prompt)}]
        payload: dict = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048},
        }
        if json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        url = f"{API_ROOT}/{self.model}:generateContent"
        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            resp = client.post(url, params={"key": self.api_key}, json=payload)
            resp.raise_for_status()
            data = resp.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError(f"gemini returned no candidates: {str(data)[:200]}")
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts)

    def generate(self, prompt: str | list[dict], system: str | None = None) -> str:
        return self._call(prompt, system, json_mode=False)

    def generate_json(self, prompt: str | list[dict], system: str | None = None):
        return parse_json_loose(self._call(prompt, system, json_mode=True))

    def answer_question(
        self, question: str, context: str, history: list[dict[str, str]] | None = None
    ) -> str:
        try:
            return LLMProvider.answer_question(self, question, context, history)
        except (httpx.HTTPError, RuntimeError) as exc:
            log.warning("gemini answer failed, using offline response: %s", exc)
            return super().answer_question(question, context, history)

    # --- capabilities -------------------------------------------------------
    def extract_document(
        self,
        text: str,
        kind_hint: str | None = None,
        image_bytes: bytes | None = None,
        mime_type: str | None = None,
    ) -> dict:
        import base64

        baseline = super().extract_document(text, kind_hint, image_bytes=image_bytes, mime_type=mime_type)
        if not self.available:
            return baseline

        data = None
        # Multimodal Gemini image processing if image bytes are provided
        if image_bytes and len(image_bytes) > 0 and (mime_type or "").startswith("image/"):
            try:
                img_b64 = base64.b64encode(image_bytes).decode("ascii")
                multimodal_prompt = [
                    {
                        "inlineData": {
                            "mimeType": mime_type or "image/png",
                            "data": img_b64,
                        }
                    },
                    {
                        "text": f"Document kind hint: {kind_hint or 'unknown'}\n\n"
                        "Extract all structured details from this image document (such as product, brand, model, price, currency, seller, purchase_date, warranty_months, billing_cycle, etc.)."
                    },
                ]
                data = self.generate_json(multimodal_prompt, EXTRACTION_SYSTEM)
            except Exception as exc:  # noqa: BLE001
                log.warning("gemini multimodal image extraction failed: %s", exc)

        if not data:
            prompt = f"Document kind hint: {kind_hint or 'unknown'}\n\nDOCUMENT:\n{text[:12000]}"
            try:
                data = self.generate_json(prompt, EXTRACTION_SYSTEM)
            except Exception as exc:  # noqa: BLE001
                log.warning("gemini extraction failed, using offline extractor: %s", exc)
                return baseline

        if not isinstance(data, dict) or "fields" not in data:
            return baseline
        fields = {k: v for k, v in (data.get("fields") or {}).items() if v not in (None, "", [])}
        merged = {**baseline["fields"], **fields}
        return {
            "kind": data.get("kind") or baseline["kind"],
            "summary": data.get("summary") or baseline["summary"],
            "fields": merged,
            "confidence": float(data.get("confidence") or baseline["confidence"]),
            "extractor": self.name,
        }

    def skeptic_review(self, item: dict, entity: dict, claim: dict, evidence: list[dict]) -> dict:
        baseline = super().skeptic_review(item, entity, claim, evidence)
        if not self.available:
            return baseline
        prompt = (
            f"EXTERNAL ANNOUNCEMENT:\ntitle: {item.get('title')}\nbody: {item.get('body', '')[:4000]}\n"
            f"affected models: {item.get('affected_models')}\n\n"
            f"USER'S ITEM:\n{entity.get('name')} — attributes: {entity.get('attributes')}\n\n"
            f"DETERMINISTIC CHECKS ALREADY RUN:\n{claim}\n"
        )
        try:
            data = self.generate_json(prompt, SKEPTIC_SYSTEM)
        except Exception as exc:  # noqa: BLE001
            log.warning("gemini skeptic failed: %s", exc)
            return baseline
        objections = list(baseline["objections"]) + [
            o for o in (data.get("objections") or []) if isinstance(o, str)
        ]
        return {
            # A deterministic refutation is authoritative; the model may only add
            # objections, never overturn a hard model-code mismatch.
            "refuted": bool(baseline["refuted"] or data.get("refuted")),
            "objections": objections,
            "surviving_reason": data.get("surviving_reason") or baseline["surviving_reason"],
        }

    def compose_alert(self, context: dict) -> dict:
        baseline = super().compose_alert(context)
        if not self.available:
            return baseline
        entity = context.get("entity", {})
        item = context.get("item", {})
        prompt = (
            f"USER ITEM: {entity.get('name')} ({entity.get('type')}) "
            f"attributes: {entity.get('attributes')}\n"
            f"EXTERNAL ITEM: {item.get('title')} from {item.get('source_name')} "
            f"({item.get('category')})\nBODY: {item.get('body', '')[:3000]}\n"
            f"VERIFICATION CHECKS: {context.get('checks')}\n"
            f"SEVERITY: {context.get('severity')}  CONFIDENCE: {context.get('confidence')}\n"
        )
        try:
            data = self.generate_json(prompt, ALERT_SYSTEM)
        except Exception as exc:  # noqa: BLE001
            log.warning("gemini alert composition failed: %s", exc)
            return baseline
        return {
            "headline": data.get("headline") or baseline["headline"],
            "explanation": data.get("explanation") or baseline["explanation"],
            "why_it_matters": data.get("why_it_matters") or baseline["why_it_matters"],
            "suggested_action": data.get("suggested_action") or baseline["suggested_action"],
        }
