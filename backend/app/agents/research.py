"""Agent 3 -- Research.

Pulls from approved external sources only, in the spec's trust order:
official > government > manufacturer > retailer > reputable publication > web.

Three source kinds:
  fixture  -- a local JSON feed (always available; drives the offline demo)
  rss      -- official RSS/Atom feeds, when ENABLE_NETWORK_RESEARCH=true
  newsapi  -- optional dev-tier supplement, needs NEWSAPI_KEY
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import DATA_DIR, settings
from ..models import ExternalItem, Source, utcnow
from ..rag.store import EXTERNAL, get_vector_store
from .base import Agent, Trace

log = logging.getLogger("mosaic.research")
FIXTURE_PATH = Path(DATA_DIR) / "external_feed.json"


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


class ResearchAgent(Agent):
    name = "Research Agent"

    def __init__(self, db: Session, trace: Trace | None = None) -> None:
        super().__init__(trace)
        self.db = db
        self.vectors = get_vector_store(db)

    # --- sources ------------------------------------------------------------
    def ensure_sources(self) -> list[Source]:
        """Register the fixture feed's sources on first run."""
        if not FIXTURE_PATH.exists():
            return list(self.db.execute(select(Source)).scalars())
        payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        for spec in payload.get("sources", []):
            existing = self.db.execute(
                select(Source).where(Source.name == spec["name"])
            ).scalar_one_or_none()
            if existing is None:
                self.db.add(
                    Source(
                        name=spec["name"],
                        kind=spec.get("kind", "fixture"),
                        url=spec.get("url"),
                        category=spec.get("category", "external_update"),
                        trust_tier=int(spec.get("trust_tier", 3)),
                    )
                )
        self.db.flush()
        return list(self.db.execute(select(Source)).scalars())

    # --- freshness helpers --------------------------------------------------
    @staticmethod
    def _is_stale(item: ExternalItem, max_age_days: int = 90) -> bool:
        """Return True when the item's published_at (or retrieved_at fallback) is older than max_age_days.

        Used by the Radar/monitoring pipeline to skip or flag stale evidence
        so time-sensitive alerts are only raised from fresh data.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        # Prefer retrieved_at (when we fetched it) over published_at (when it was written)
        retrieved_str = (item.metadata_json or {}).get("retrieved_at")
        if retrieved_str:
            try:
                retrieved = datetime.fromisoformat(retrieved_str.replace("Z", "+00:00"))
                return retrieved < cutoff
            except ValueError:
                pass
        if item.published_at:
            pub = item.published_at
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            return pub < cutoff
        return False

    # --- polling ------------------------------------------------------------
    def poll(self) -> list[ExternalItem]:
        sources = self.ensure_sources()
        new_items: list[ExternalItem] = []
        stale_count = 0
        for source in sources:
            if not source.enabled:
                continue
            try:
                if source.kind == "fixture":
                    new_items += self._poll_fixture(source)
                elif source.kind == "rss":
                    new_items += self._poll_rss(source)
                elif source.kind == "newsapi":
                    new_items += self._poll_newsapi(source)
                elif source.kind == "tavily":
                    new_items += self._poll_tavily(source)
                elif source.kind == "firecrawl":
                    new_items += self._poll_firecrawl(source)
            except Exception as exc:  # noqa: BLE001
                log.warning("source %s failed: %s", source.name, exc)
                self.log("poll_error", f"{source.name} could not be polled: {exc}")
            source.last_polled_at = utcnow()
        self.db.flush()
        stale_count = sum(1 for i in new_items if self._is_stale(i))
        self.log(
            "poll",
            f"Polled {len(sources)} approved sources, found {len(new_items)} new items "
            f"({stale_count} flagged as stale >90 days)",
            [i.title for i in new_items],
        )
        return new_items

    def _poll_fixture(self, source: Source) -> list[ExternalItem]:
        if not FIXTURE_PATH.exists():
            return []
        payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        key_by_name = {s["name"]: s.get("key", s["name"]) for s in payload.get("sources", [])}
        source_key = key_by_name.get(source.name)
        out = []
        for raw in payload.get("items", []):
            if raw.get("source") != source_key:
                continue
            item = self.record_item(
                source,
                external_id=raw["external_id"],
                title=raw["title"],
                body=raw.get("body", ""),
                url=raw.get("url"),
                category=raw.get("category", source.category),
                published_at=_parse_dt(raw.get("published_at")),
                metadata={
                    k: v
                    for k, v in raw.items()
                    if k in ("affected_models", "affected_brands", "region", "deadline",
                             "action_url", "severity_hint", "product_hint")
                },
            )
            if item is not None:
                out.append(item)
        return out

    def _poll_rss(self, source: Source) -> list[ExternalItem]:
        if not settings.enable_network_research or not source.url:
            return []
        import feedparser

        headers = {"User-Agent": settings.research_user_agent}
        with httpx.Client(timeout=20.0, headers=headers, follow_redirects=True) as client:
            raw = client.get(source.url).content
        feed = feedparser.parse(raw)
        out = []
        for entry in feed.entries[:25]:
            item = self.record_item(
                source,
                external_id=entry.get("id") or entry.get("link") or entry.get("title", "")[:200],
                title=entry.get("title", "")[:500],
                body=(entry.get("summary") or entry.get("description") or "")[:8000],
                url=entry.get("link"),
                category=source.category,
                published_at=_parse_dt(entry.get("published")),
                metadata={},
            )
            if item is not None:
                out.append(item)
        return out

    def _poll_newsapi(self, source: Source) -> list[ExternalItem]:
        if not settings.newsapi_key or not settings.enable_network_research:
            return []
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(
                "https://newsapi.org/v2/everything",
                params={"q": source.url or "product recall", "pageSize": 20, "language": "en"},
                headers={"X-Api-Key": settings.newsapi_key},
            )
            resp.raise_for_status()
            data = resp.json()
        out = []
        for article in data.get("articles", []):
            item = self.record_item(
                source,
                external_id=article.get("url", "")[:280],
                title=(article.get("title") or "")[:500],
                body=(article.get("description") or "") + "\n" + (article.get("content") or ""),
                url=article.get("url"),
                category=source.category,
                published_at=_parse_dt(article.get("publishedAt")),
                metadata={"author": article.get("author")},
            )
            if item is not None:
                out.append(item)
        return out

    def _poll_tavily(self, source: Source) -> list[ExternalItem]:
        tavily_key = settings.tavily_api_key or os.getenv("TAVILY_API_KEY")
        if not tavily_key or not settings.enable_network_research:
            return []
        query = source.url or "product recall security advisory warranty recall"
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                "https://api.tavily.com/search",
                json={"api_key": tavily_key, "query": query, "max_results": 10, "include_answer": True},
            )
            resp.raise_for_status()
            data = resp.json()
        out = []
        for res in data.get("results", []):
            item = self.record_item(
                source,
                external_id=res.get("url", "")[:280],
                title=(res.get("title") or "")[:500],
                body=res.get("content") or "",
                url=res.get("url"),
                category=source.category,
                published_at=datetime.now(timezone.utc),
                metadata={"score": res.get("score"), "answer": data.get("answer")},
            )
            if item is not None:
                out.append(item)
        return out

    def _poll_firecrawl(self, source: Source) -> list[ExternalItem]:
        import os
        import subprocess
        firecrawl_key = settings.firecrawl_api_key or os.getenv("FIRECRAWL_API_KEY")
        if not settings.enable_network_research:
            return []
        query = source.url or "product recall security advisory warranty recall"
        out = []

        # 1. Firecrawl API
        if firecrawl_key:
            try:
                with httpx.Client(timeout=20.0) as client:
                    resp = client.post(
                        "https://api.firecrawl.dev/v1/search",
                        json={"query": query, "limit": 10},
                        headers={"Authorization": f"Bearer {firecrawl_key}"},
                    )
                    if resp.status_code == 200:
                        data = resp.json().get("data", [])
                        for res in data:
                            item = self.record_item(
                                source,
                                external_id=res.get("url", "")[:280],
                                title=(res.get("title") or "")[:500],
                                body=res.get("markdown") or res.get("description") or "",
                                url=res.get("url"),
                                category=source.category,
                                published_at=datetime.now(timezone.utc),
                                metadata={"score": res.get("score")},
                            )
                            if item is not None:
                                out.append(item)
                        return out
            except Exception as exc:  # noqa: BLE001
                log.warning("Firecrawl API search failed: %s", exc)

        # 2. Firecrawl CLI
        import shutil
        firecrawl_bin = shutil.which("firecrawl")
        if firecrawl_bin:
            try:
                res = subprocess.run(
                    [firecrawl_bin, "search", query, "--json"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if res.returncode == 0 and res.stdout.strip():
                    import json
                    payload = json.loads(res.stdout)
                    results = payload.get("data", []) if isinstance(payload, dict) else []
                    for r in results:
                        item = self.record_item(
                            source,
                            external_id=r.get("url", "")[:280],
                            title=(r.get("title") or "")[:500],
                            body=r.get("description") or r.get("markdown") or "",
                            url=r.get("url"),
                            category=source.category,
                            published_at=datetime.now(timezone.utc),
                            metadata={"provider": "firecrawl-cli"},
                        )
                        if item is not None:
                            out.append(item)
            except Exception as exc:  # noqa: BLE001
                log.warning("Firecrawl CLI search failed: %s", exc)

        return out

    # --- shared -------------------------------------------------------------
    def record_item(
        self,
        source: Source,
        external_id: str,
        title: str,
        body: str,
        url: str | None,
        category: str,
        published_at: datetime | None,
        metadata: dict | None = None,
    ) -> ExternalItem | None:
        existing = self.db.execute(
            select(ExternalItem).where(
                ExternalItem.source_id == source.id, ExternalItem.external_id == external_id
            )
        ).scalar_one_or_none()
        if existing is not None:
            return None
        # Stamp exactly when this item was fetched (retrieved_at) so the
        # freshness system can tell the difference between "published a year ago"
        # and "we just fetched this now".
        retrieved_at_iso = datetime.now(timezone.utc).isoformat()
        enriched_meta = {**(metadata or {}), "retrieved_at": retrieved_at_iso}
        item = ExternalItem(
            source_id=source.id,
            external_id=external_id,
            title=title,
            body=body,
            url=url,
            category=category,
            published_at=published_at or datetime.now(timezone.utc),
            metadata_json=enriched_meta,
        )
        self.db.add(item)
        self.db.flush()
        self.vectors.upsert(
            EXTERNAL,
            ref_type="external_item",
            ref_id=item.id,
            text=f"{title}\n{body}",
            meta={
                "title": title,
                "url": url,
                "source_name": source.name,
                "trust_tier": source.trust_tier,
                "category": category,
                "external_item_id": item.id,
                "retrieved_at": retrieved_at_iso,
            },
        )
        return item
