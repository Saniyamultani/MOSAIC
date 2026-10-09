"""Pytest automated test runner for the full MOSAIC evaluation suite.

Run with: python -m pytest tests/test_evaluation_suite.py -v
"""
from __future__ import annotations

import os
import tempfile
import pytest

os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test_eval_suite.db")
os.environ.setdefault("LLM_PROVIDER", "offline")
os.environ.setdefault("ENABLE_SCHEDULER", "false")

from app.db import SessionLocal, init_db
from app.evals.dataset import EVAL_DATASET, EvalTestCase
from app.evals.evaluator import SystemEvaluator
from app.models import Base


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    session = SessionLocal()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    session.close()


@pytest.mark.parametrize("case", EVAL_DATASET, ids=[c.id for c in EVAL_DATASET])
def test_evaluation_case(case: EvalTestCase):
    session = SessionLocal()
    try:
        evaluator = SystemEvaluator(session)
        res = evaluator.run_case(case)
        assert res.passed, (
            f"Evaluation case '{case.id}' failed!\n"
            f"Expected: {res.expected_result}\n"
            f"Actual:   {res.actual_result}\n"
            f"Evidence: {res.evidence}"
        )
    finally:
        session.close()
