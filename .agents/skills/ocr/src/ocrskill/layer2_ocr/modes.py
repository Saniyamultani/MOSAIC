"""OCR mode identifiers and DeepSeek prompt strings.

Modes are the agent-facing contract. Prompt strings are engine implementation
details for the DeepSeek adapter; mock uses the mode id only.
"""

from __future__ import annotations

# Order is stable for help text and error hints.
MODES: tuple[str, ...] = ("markdown", "free", "figure", "ocr")

# Official DeepSeek-OCR / OCR-2 prompt family (HF card + upstream examples).
# Trailing spaces match upstream samples; do not invent free-form prompts here.
DEEPSEEK_PROMPTS: dict[str, str] = {
    "markdown": "<image>\n<|grounding|>Convert the document to markdown. ",
    "ocr": "<image>\n<|grounding|>OCR this image. ",
    "free": "<image>\nFree OCR. ",
    "figure": "<image>\nParse the figure. ",
}

assert set(MODES) == set(DEEPSEEK_PROMPTS.keys())
