"""Cheap token estimate for pagination only (not a model tokenizer)."""

from __future__ import annotations

from ..config import CHARS_PER_TOKEN


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN)


def split_pages(text: str, page_size_tokens: int) -> list[str]:
    """Split text into chunks of roughly page_size_tokens. Never drops content.

    page_size_tokens <= 0 means one page with the whole document.
    """
    if page_size_tokens <= 0:
        return [text]
    if not text:
        return [""]

    char_budget = max(page_size_tokens * CHARS_PER_TOKEN, 1)
    pages: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        end = min(i + char_budget, n)
        if end < n:
            # Prefer breaking on a newline near the end of the window.
            window = text[i:end]
            nl = window.rfind("\n")
            if nl >= char_budget // 4:
                end = i + nl + 1
        pages.append(text[i:end])
        i = end
    return pages or [""]
