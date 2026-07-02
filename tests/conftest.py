"""Top-level conftest — mock heavy optional dependencies before they're imported.

pgvector is only needed at database runtime, not for unit-testing pure
Python logic like the query router or extraction pipeline. We patch
sys.modules before any life_graph import so SQLAlchemy can build its
models without the real pgvector driver installed.
"""

import sys
from unittest.mock import MagicMock

import sqlalchemy


class _FakeVector(sqlalchemy.types.UserDefinedType):
    """Minimal Vector stand-in so SQLAlchemy can map Mapped[list[float]] columns."""

    cache_ok = True

    def __init__(self, dim: int | None = None) -> None:
        self.dim = dim

    def get_col_spec(self) -> str:
        if self.dim:
            return f"VECTOR({self.dim})"
        return "VECTOR"

    def bind_processor(self, dialect):  # noqa: ANN001
        return None

    def result_processor(self, dialect, coltype):  # noqa: ANN001
        return None


# Only patch if pgvector isn't actually installed
if "pgvector" not in sys.modules:
    _pgvector_mock = MagicMock()
    _sa_mock = MagicMock()
    _sa_mock.Vector = _FakeVector
    _pgvector_mock.sqlalchemy = _sa_mock

    sys.modules["pgvector"] = _pgvector_mock
    sys.modules["pgvector.sqlalchemy"] = _sa_mock
