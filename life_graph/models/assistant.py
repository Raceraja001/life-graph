"""Tables for the assistant's non-development work (docs/specs/assistant-capabilities.md).

Documents, money, page monitors, study cards and invoices. Kept apart from
models/db.py, which is already 2,500 lines; every table is tenant-scoped like
the rest. Migrations 045 onward create them.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Float, Index, Integer, Numeric, String, Text
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


class PageMonitor(Base):
    """A page the user asked to watch (services/page_monitors.py).

    ``last_value`` holds the last price for ``price_below`` and 1/0 for
    ``contains`` (present/absent), so alerts fire on transitions only.
    """

    __tablename__ = "page_monitors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="change")
    selector: Mapped[str | None] = mapped_column(Text, nullable=True)
    threshold: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    pattern: Mapped[str | None] = mapped_column(String(200), nullable=True)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=180)
    paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    last_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (Index("ix_page_monitors_tenant", "tenant_id"),)


class ReviewCard(Base):
    """A spaced-repetition study card (services/study.py, SM-2 scheduling).

    ``dedup_key`` is a hash of the normalised front, so generating cards from
    the same notes twice does not make duplicates.
    """

    __tablename__ = "review_cards"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    deck: Mapped[str] = mapped_column(String(80), nullable=False, default="general")
    front: Mapped[str] = mapped_column(Text, nullable=False)
    back: Mapped[str] = mapped_column(Text, nullable=False)
    source_memory_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    ease: Mapped[float] = mapped_column(Float, nullable=False, default=2.5)
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    repetitions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    due_on: Mapped[date] = mapped_column(Date, nullable=False)
    last_grade: Mapped[str | None] = mapped_column(String(8), nullable=True)
    reviews: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dedup_key: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        Index("uq_review_cards_dedup", "tenant_id", "dedup_key", unique=True),
        Index("ix_review_cards_due", "tenant_id", "due_on"),
    )


class Invoice(Base):
    """An invoice the user issues to a client (services/invoices.py).

    ``items`` is a list of ``{description, quantity, unit_price}``; the totals
    are computed by the service and stored, so a later edit to the tax rule
    cannot silently change an invoice already sent. ``number`` is unique per
    tenant (``INV-2026-0001``).
    """

    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    number: Mapped[str] = mapped_column(String(32), nullable=False)
    client_name: Mapped[str] = mapped_column(String(200), nullable=False)
    client_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    client_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    tax: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="draft")
    issued_on: Mapped[date] = mapped_column(Date, nullable=False)
    due_on: Mapped[date] = mapped_column(Date, nullable=False)
    sent_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    paid_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_reminded_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index("uq_invoices_number", "tenant_id", "number", unique=True),
        Index("ix_invoices_tenant_status", "tenant_id", "status", "due_on"),
    )


class LlmOffer(Base):
    """A free LLM model, tier, credit or promotion found (services/llm_offers.py).

    ``terms`` holds what the reader found out (limits, expires_on, needs_signup,
    needs_card, trains_on_prompts, commercial_use; each may be "unknown");
    ``evaluation`` the smoke test and benchmark result. Status moves
    new -> evaluating -> passed | failed, then adopted | rejected via the
    ``model_adoption`` approval; needs_signup when no key reaches it; gone when
    a catalog no longer lists it.
    """

    __tablename__ = "llm_offers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    dedup_key: Mapped[str] = mapped_column(String(500), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str | None] = mapped_column(String(300), nullable=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    terms: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="new")
    evaluation: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index("uq_llm_offers_key", "tenant_id", "dedup_key", unique=True),
        Index("ix_llm_offers_tenant_status", "tenant_id", "status"),
    )


class LlmCatalogSnapshot(Base):
    """One provider's free-model ids on one day: the catalog diff's memory.

    A public catalog, not tenant data, so there is no tenant column.
    """

    __tablename__ = "llm_catalog_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    taken_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    model_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    __table_args__ = (Index("ix_llm_catalog_snapshots_provider", "provider", "taken_at"),)


class TopicFinding(Base):
    """Something new on a tech-watch topic, with its source (services/web_research.py).

    One row per item per source page per topic (``dedup_key``); ``sent_at``
    is set when it goes out in the Monday digest, so each is sent once.
    """

    __tablename__ = "topic_findings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    topic: Mapped[str] = mapped_column(String(120), nullable=False)
    dedup_key: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    published_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    found_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("uq_topic_findings_key", "tenant_id", "topic", "dedup_key", unique=True),
        Index("ix_topic_findings_tenant_found", "tenant_id", "found_at"),
    )


class Device(Base):
    """A phone paired with Jarvis (services/devices.py). Only the token's
    SHA-256 is kept; ``revoked_at`` set means it no longer signs in."""

    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("uq_devices_token_hash", "token_hash", unique=True),
        Index("ix_devices_tenant", "tenant_id"),
    )


class DevicePairingCode(Base):
    """A one-time six-digit code that pairs a phone (ten minutes, spent once)."""

    __tablename__ = "device_pairing_codes"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (Index("ix_device_pairing_codes_expires", "expires_at"),)
