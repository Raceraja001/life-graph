"""Tables for the assistant's non-development work (docs/specs/assistant-capabilities.md).

Documents, money, page monitors, study cards and invoices. Kept apart from
models/db.py, which is already 2,500 lines; every table is tenant-scoped like
the rest. Migrations 045 onward create them.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from life_graph.models.db import Base, _utcnow


class Document(Base):
    """An identity or ownership document the user keeps: passport, policy, warranty.

    Only the last four characters of a document number are kept: enough to
    tell two cards apart, useless to anyone who reads the table.
    ``reminders_sent`` lists the day thresholds already notified for the
    current ``expires_on``; changing the expiry clears it.
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="other")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    issuer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    number_last4: Mapped[str | None] = mapped_column(String(8), nullable=True)
    holder: Mapped[str | None] = mapped_column(String(120), nullable=True)
    issued_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="api")
    reminders_sent: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (Index("ix_documents_tenant_expiry", "tenant_id", "expires_on"),)
