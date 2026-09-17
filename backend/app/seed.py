"""Demo seed -- reproduces the reference walkthrough end to end.

    python -m app.seed --reset

Day 1  phone receipt + warranty
Day 2  television receipt
Day 3  subscription + broadband bill
Day 7  approved sources publish; the pipeline decides what deserves an alert.
"""
from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import text as sql_text

from .config import DATA_DIR, settings
from .db import SessionLocal, engine, init_db
from .models import Base
from .services import (
    confirm_ingestion,
    get_or_create_demo_user,
    run_monitoring,
    start_ingestion,
)

log = logging.getLogger("mosaic.seed")

DOCUMENTS: list[tuple[str, str]] = [
    (
        "receipt",
        "Order confirmation from Amazon.in. I bought a Samsung Galaxy S26 Ultra "
        "(model SM-S926B, Titanium Grey, 512GB) for Rs 1,29,999 on 12 May 2026. "
        "Paid with my HDFC Millennia credit card. Order number 408-2213445-9921003. "
        "Includes 1 year standard manufacturer warranty.",
    ),
    (
        "warranty",
        "Samsung Care+ extended warranty certificate. Product: Galaxy S26 Ultra, "
        "model SM-S926B. Coverage: 24 months of accidental and liquid damage "
        "protection from 12 May 2026. Provider: Samsung India Electronics. "
        "Plan number SCP-IN-88213. Service through Samsung authorised service centres.",
    ),
    (
        "receipt",
        "Croma tax invoice. Purchased a Sony BRAVIA XR-65A80K 65-inch OLED "
        "television for Rs 1,89,990 on 20 May 2026, paid with HDFC Millennia credit "
        "card. 2 year comprehensive warranty included. Delivery and wall mount "
        "installation completed.",
    ),
    (
        "subscription",
        "Netflix subscription confirmation. Your Netflix Premium plan is Rs 649 per "
        "month and renews on 18 September 2026. Payment method: HDFC Millennia "
        "credit card ending 4412.",
    ),
    (
        "bill",
        "Airtel broadband bill for August 2026. Amount due Rs 1,299, due date "
        "15 September 2026. Account 1082294401. Autopay is set up on the HDFC "
        "Millennia credit card.",
    ),
]


def reset_database() -> None:
    Base.metadata.drop_all(bind=engine)
    if settings.database_url.startswith("sqlite"):
        # Close pooled handles before removing the file, or SQLite keeps writing
        # to the deleted inode.
        engine.dispose()
        db_path = DATA_DIR / "mosaic.db"
        if db_path.exists():
            db_path.unlink()
    else:
        with engine.begin() as conn:
            conn.execute(sql_text("SELECT 1"))
    init_db()
    log.info("database reset")


def seed(reset: bool = False, monitor: bool = True) -> dict:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
    if reset:
        reset_database()
    else:
        init_db()

    db = SessionLocal()
    try:
        user = get_or_create_demo_user(db)
        db.commit()
        print(f"\nUser: {user.name} <{user.email}>")
        print(f"LLM provider: {settings.resolved_llm_provider}\n")

        print("── Capture ────────────────────────────────────────────────")
        for kind, body in DOCUMENTS:
            document, _trace, thread_id = start_ingestion(
                db, user.id, "text", {"text": body, "kind_hint": kind}
            )
            extraction = document.extraction or {}
            print(f"  • {extraction.get('summary', document.title)}")
            print(
                f"    kind={extraction.get('kind')} "
                f"fields={list((extraction.get('fields') or {}).keys())}"
            )
            result = confirm_ingestion(db, thread_id, document.id)
            print(
                f"    ✓ confirmed → {result['created']} new node(s), "
                f"{result['merged']} merged, {result['edges']} relationship(s)"
            )
            for connection in result.get("connections", []):
                print(f"    🔗 new connection: {connection['entity']} ↔ {connection['related']}")

        if not monitor:
            return {}

        print("\n── Personal Radar ─────────────────────────────────────────")
        summary = run_monitoring(db, user.id)
        for run in summary["runs"]:
            mark = {"alerted": "🚨", "refuted": "🛑", "below_threshold": "🔕", "no_match": "·"}.get(
                run["outcome"], "?"
            )
            print(f"  {mark} {run['outcome']:<16} {run['item'][:70]}")
        print(
            f"\n  {summary['alerts']} alert(s) raised · "
            f"{summary['suppressed']} suppressed by verification · "
            f"{summary['no_match']} irrelevant\n"
        )
        return summary
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the MOSAIC demo")
    parser.add_argument("--reset", action="store_true", help="drop and recreate all tables first")
    parser.add_argument("--no-monitor", action="store_true", help="capture only, skip the radar")
    args = parser.parse_args()
    seed(reset=args.reset, monitor=not args.no_monitor)
    return 0


if __name__ == "__main__":
    sys.exit(main())
