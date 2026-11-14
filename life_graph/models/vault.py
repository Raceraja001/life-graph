"""The vault: secrets the agent may fill in on the owner's behalf, encrypted at rest.

A browser agent that fills a bank login needs the password, but nothing that
reads the database — a backup, a dump, a stray ``SELECT *``, the agent's own
transcript — should ever see it. So a vault secret is stored only as
ciphertext (``encrypted_value``, AES-256-GCM in ``services/vault.py``) and is
referred to everywhere else by an opaque handle: ``vault://<handle>`` is what
a plan, a tool call or a log line carries.

Two rules make a handle safe to hand around:

* ``allowed_origins`` — the sites this secret may be typed into. A handle
  leaked into the wrong page resolves to nothing, because
  :func:`~life_graph.services.vault.resolve_for_origin` refuses an origin the
  owner did not name.
* ``one_use`` — set for an OTP or a single payment authorisation: ``used_at``
  is stamped the first time it resolves and every later attempt fails.

Migration 058 creates the table. Tenant-scoped like every other table
(CHARTER invariant 4); the tenant also acts as additional authenticated data
in the cipher, so a row copied to another tenant cannot be decrypted.
"""

from __future__ import annotations

import uuid
from datetime import datetime  # noqa: TC003

from sqlalchemy import Boolean, DateTime, Index, Integer, LargeBinary, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from life_graph.models.base import Base, _utcnow


class VaultSecret(Base):
    """One encrypted secret, reachable only through its ``vault://`` handle.

    ``handle`` is a random token, not derived from the label, so it says
    nothing about what it protects. ``revoked_at`` set means the secret is
    gone: revoking also blanks ``encrypted_value``, so the plaintext is
    unrecoverable even from a backup taken afterwards.
    """

    __tablename__ = "vault_secrets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # The opaque token in vault://<handle>. Unique across tenants: it is
    # random, and a collision would make one tenant's handle name another's row.
    handle: Mapped[str] = mapped_column(String(64), nullable=False)
    # What the owner calls it ("HDFC net banking password"). Shown in lists;
    # deliberately never the secret itself.
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    # password | otp | card | token | note — a hint for the filler, not an enum
    # the core depends on (CHARTER invariant 1: schema-less).
    secret_type: Mapped[str] = mapped_column(String(32), nullable=False, default="generic")
    # Origins (scheme://host[:port]) this secret may be sent to; "*.bank.com"
    # covers subdomains. Empty means nowhere, which is why it is never a default.
    allowed_origins: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default="{}"
    )
    encrypted_value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    one_use: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Audit: where it went last, so an unexpected site is visible afterwards.
    last_used_origin: Mapped[str | None] = mapped_column(String(255), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index("uq_vault_secrets_handle", "handle", unique=True),
        Index("ix_vault_secrets_tenant", "tenant_id"),
        Index("ix_vault_secrets_tenant_label", "tenant_id", "label"),
    )

    def __repr__(self) -> str:
        # No value, not even its length: reprs end up in logs and tracebacks.
        return f"<VaultSecret(id={self.id!s:.8}, label={self.label!r}, type={self.secret_type})>"
