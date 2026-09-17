from __future__ import annotations

import logging
from functools import lru_cache

from ..config import settings
from .base import LLMProvider
from .gemini import GeminiProvider
from .offline import OfflineProvider

log = logging.getLogger("mosaic.llm")


@lru_cache
def get_llm() -> LLMProvider:
    choice = settings.resolved_llm_provider
    if choice == "gemini":
        provider = GeminiProvider()
        if provider.available:
            log.info("LLM provider: gemini (%s)", settings.gemini_model)
            return provider
        log.warning("GOOGLE_API_KEY missing; falling back to the offline provider")
    log.info("LLM provider: offline (deterministic rule-based)")
    return OfflineProvider()


def reset_llm_cache() -> None:
    get_llm.cache_clear()
