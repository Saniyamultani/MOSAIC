"""Evaluation Suite Runner generating markdown evaluation report with empirical evidence."""
from __future__ import annotations

import logging
import os
import sys
import tempfile
from datetime import datetime, timezone
from typing import List

# Enforce isolated eval database
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/mosaic_eval.db"
os.environ["LLM_PROVIDER"] = "offline"
os.environ["ENABLE_SCHEDULER"] = "false"

from ..db import SessionLocal, init_db
from ..models import Base
from .dataset import EVAL_DATASET
from .evaluator import EvalResult, SystemEvaluator

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
log = logging.getLogger("mosaic.eval_runner")


def run_evaluation_suite(report_filepath: str = "evaluation_report.md") -> List[EvalResult]:
    log.info("Starting MOSAIC System Evaluation Suite...")
    init_db()

    results: List[EvalResult] = []

    print("\n================================================================================")
    print(" MOSAIC SYSTEM EVALUATION SUITE RUN")
    print(" Time: ", datetime.now(timezone.utc).isoformat())
    print("================================================================================\n")

    for case in EVAL_DATASET:
        print(f"Running [{case.category.upper()}] {case.id}: {case.title}...", end="", flush=True)
        session = SessionLocal()
        try:
            for table in reversed(Base.metadata.sorted_tables):
                session.execute(table.delete())
            session.commit()
            evaluator = SystemEvaluator(session)
            res = evaluator.run_case(case)
        finally:
            session.close()
        results.append(res)
        status_mark = res.details.get("status", "PASS" if res.passed else "FAIL")
        print(f" -> [{status_mark}] ({res.latency_ms:.1f}ms)")

    total = len(results)
    passed_count = sum(1 for r in results if r.passed)
    error_count = sum(1 for r in results if r.details.get("status") == "ERROR")
    failed_count = total - passed_count - error_count

    print("\n--------------------------------------------------------------------------------")
    print(f" RESULTS: {passed_count} passed | {failed_count} failed | {error_count} errors | {total} total")
    print("--------------------------------------------------------------------------------\n")

    write_evaluation_report(results, report_filepath)
    return results


def write_evaluation_report(results: List[EvalResult], filepath: str) -> None:
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    total = len(results)
    passed_count = sum(1 for r in results if r.passed)
    error_count = sum(1 for r in results if r.details.get("status") == "ERROR")
    failed_count = total - passed_count - error_count

    def table_cell(value: str) -> str:
        return str(value).replace("|", "&#124;").replace("\n", "<br>")

    lines = [
        "# MOSAIC System Evaluation Report",
        "",
        f"Generated at: {now_str}",
        "",
        "This is one deterministic local evaluation run, not an accuracy estimate. "
        "The assistant uses the configured offline provider. Web research routing and source "
        "propagation are exercised with a local deterministic search fixture; no live web "
        "results are represented as real. Each case runs against a clean SQLite database.",
        "",
        f"Measured test outcomes: {passed_count} passed, {failed_count} failed, {error_count} errors "
        f"({total} total cases).",
        "",
        "Run from `backend/` with `python -m app.evals.runner evaluation_report.md`.",
        "",
        "| Test case | Expected result | Actual result | Pass/Fail | Relevant evidence |",
        "|---|---|---|---|---|",
    ]

    for result in results:
        status = result.details.get("status", "PASS" if result.passed else "FAIL")
        evidence = "<br>".join(table_cell(item) for item in result.evidence)
        lines.append(
            f"| `{table_cell(result.test_case_id)}` — {table_cell(result.title)} "
            f"({table_cell(result.category)}) | {table_cell(result.expected_result)} "
            f"| {table_cell(result.actual_result)} | **{status}** | {evidence} |"
        )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    log.info("Evaluation report written to %s", filepath)


if __name__ == "__main__":
    out_path = sys.argv[1] if len(sys.argv) > 1 else "evaluation_report.md"
    suite_results = run_evaluation_suite(out_path)
    sys.exit(1 if any(not result.passed for result in suite_results) else 0)
