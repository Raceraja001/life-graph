"""The memory quality report's own rules (scripts/memory_quality_report.py)."""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "memory_quality_report.py"
_spec = importlib.util.spec_from_file_location("memory_quality_report", _PATH)
mqr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mqr)


@pytest.mark.parametrize(
    ("said", "question"),
    [
        ("we can use n8n for this? is that the best way?", True),
        ("can we build mockups first", True),
        ("tools like dify can do this? or we build them ourselves?", True),
        ("for now we can focus on the mobile app", False),
        ("I prefer tea in the evening", False),
    ],
)
def test_question_shapes(said, question):
    assert bool(mqr.QUESTION.search(said)) is question


def test_pasted_shape():
    assert mqr.PASTED.search('<pasted_content id="x">spec</pasted_content> do this')
    assert not mqr.PASTED.search("I pasted it earlier")


def test_the_hook_queue_is_reported(tmp_path):
    db = tmp_path / "spool.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE pending (id INTEGER PRIMARY KEY, payload TEXT, created_at REAL)")
    c.executemany("INSERT INTO pending (payload, created_at) VALUES ('{}', ?)", [(1.7e9,)] * 60)
    c.commit()

    (line,) = mqr.spool_lines(db)
    assert "60 waiting" in line and "STUCK" in line
    assert "no " in mqr.spool_lines(tmp_path / "missing.db")[0]
