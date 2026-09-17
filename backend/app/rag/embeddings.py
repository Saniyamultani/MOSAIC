"""Embeddings.

Default is a dependency-free hashing embedder: deterministic, instant, no model
download, good enough for the small per-user corpora MOSAIC deals with.  Set
EMBEDDING_BACKEND=sentence-transformers to swap in a real model.
"""
from __future__ import annotations

import hashlib
import logging
import math
import re
from functools import lru_cache

import numpy as np

from ..config import settings

log = logging.getLogger("mosaic.rag.embeddings")

WORD_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "at", "is", "are", "was",
    "with", "by", "from", "this", "that", "it", "as", "be", "has", "have", "you", "your",
}


class Embedder:
    dim: int = 384
    name: str = "base"

    def embed(self, text: str) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError

    def embed_many(self, texts: list[str]) -> np.ndarray:
        return np.vstack([self.embed(t) for t in texts]) if texts else np.zeros((0, self.dim))


class HashingEmbedder(Embedder):
    """Signed feature hashing over words + character 4-grams, TF-weighted."""

    name = "local-hashing"

    def __init__(self, dim: int | None = None) -> None:
        self.dim = dim or settings.embedding_dim

    @staticmethod
    def _bucket(token: str, dim: int) -> tuple[int, float]:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        return value % dim, 1.0 if (value >> 63) & 1 else -1.0

    def _features(self, text: str) -> list[str]:
        low = (text or "").lower()
        words = [w for w in WORD_RE.findall(low) if w not in STOPWORDS]
        feats = list(words)
        feats += [f"{a}_{b}" for a, b in zip(words, words[1:])]
        compact = "".join(words)
        feats += [compact[i : i + 4] for i in range(0, max(0, len(compact) - 3))]
        return feats

    def embed(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        feats = self._features(text)
        if not feats:
            return vec
        counts: dict[str, int] = {}
        for f in feats:
            counts[f] = counts.get(f, 0) + 1
        for feat, count in counts.items():
            idx, sign = self._bucket(feat, self.dim)
            vec[idx] += sign * (1.0 + math.log(count))
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm else vec


class SentenceTransformerEmbedder(Embedder):
    name = "sentence-transformers"

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer  # lazy, optional

        self.model = SentenceTransformer(model_name)
        self.dim = int(self.model.get_sentence_embedding_dimension())

    def embed(self, text: str) -> np.ndarray:
        return np.asarray(
            self.model.encode(text or "", normalize_embeddings=True), dtype=np.float32
        )

    def embed_many(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.asarray(
            self.model.encode(texts, normalize_embeddings=True), dtype=np.float32
        )


@lru_cache
def get_embedder() -> Embedder:
    if settings.embedding_backend == "sentence-transformers":
        try:
            embedder = SentenceTransformerEmbedder(settings.embedding_model)
            log.info("Embedder: %s (dim=%d)", settings.embedding_model, embedder.dim)
            return embedder
        except Exception as exc:  # noqa: BLE001
            log.warning("sentence-transformers unavailable (%s); using hashing embedder", exc)
    return HashingEmbedder()
