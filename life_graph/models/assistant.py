"""Tables for the assistant's non-development work (docs/specs/assistant-capabilities.md).

Documents, money, page monitors, study cards and invoices. Kept apart from
models/db.py, which is already 2,500 lines; every table is tenant-scoped like
the rest. Migrations 045 onward create them.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Numeric, String, Text
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


class MoneyTransaction(Base):
    """One movement of money, from a statement import or a bank alert.

    ``amount`` is always positive; ``direction`` says which way it went.
    ``dedup_hash`` makes re-importing an overlapping statement harmless.
    """

    __tablename__ = "money_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # debit | credit
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    merchant: Mapped[str | None] = mapped_column(String(120), nullable=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="uncategorised")
    category_source: Mapped[str] = mapped_column(String(16), nullable=False, default="rule")
    account_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="csv")
    dedup_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        Index("uq_money_transactions_dedup", "tenant_id", "dedup_hash", unique=True),
        Index("ix_money_transactions_tenant_day", "tenant_id", "occurred_on"),
    )


class MoneyCategoryRule(Base):
    """``pattern`` (lowercase, matched as a substring of the merchant or
    description) files a transaction under ``category``. Written when the
    user corrects a category, so the same merchant is right next time."""

    __tablename__ = "money_category_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    pattern: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (Index("uq_money_rules_pattern", "tenant_id", "pattern", unique=True),)


class MoneyBudget(Base):
    """A monthly spending limit for one category. ``alerts_sent`` maps a
    month (``YYYY-MM``) to the percentages already alerted for it."""

    __tablename__ = "money_budgets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    monthly_limit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    alerts_sent: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (Index("uq_money_budgets_category", "tenant_id", "category", unique=True),)
