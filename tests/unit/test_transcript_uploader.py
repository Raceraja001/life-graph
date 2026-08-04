"""Unit tests for the local transcript uploader's pure helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "transcript_uploader",
    Path(__file__).parent.parent.parent / "scripts" / "transcript_uploader.py",
)
up = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(up)


def test_new_lines_from_zero():
    data = b'{"a":1}\n{"b":2}\n'
    lines, offset = up.new_lines(data, 0)
    assert lines == ['{"a":1}', '{"b":2}']
    assert offset == len(data)


def test_new_lines_holds_back_partial_trailing_line():
    data = b'{"a":1}\n{"b":2}\n{"partial'
    lines, offset = up.new_lines(data, 0)
    assert lines == ['{"a":1}', '{"b":2}']
    # offset stops after the last complete newline, not at EOF.
    assert offset == len(b'{"a":1}\n{"b":2}\n')


def test_new_lines_resumes_from_offset():
    data = b'{"a":1}\n{"b":2}\n'
    start = len(b'{"a":1}\n')
    lines, offset = up.new_lines(data, start)
    assert lines == ['{"b":2}']
    assert offset == len(data)


def test_new_lines_truncation_resets():
    data = b'{"a":1}\n'
    lines, offset = up.new_lines(data, 9999)  # offset past EOF → treat as reset
    assert lines == ['{"a":1}']
    assert offset == len(data)


def test_batched():
    assert list(up.batched([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]


def test_session_id_for():
    assert up.session_id_for("/x/y/5db24295-1788.jsonl") == "5db24295-1788"
