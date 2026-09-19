"""Connector runtime: discovery, accounts, sync, summaries, retention.

Plugins supply ``CONNECTOR`` objects (``connectors/base.py``); this module is
everything around them that must not be left to a plugin:

- discovery of ``plugins/*/`` packages that export ``CONNECTOR`` — done by the
  API *and* the worker, independently of the event-plugin ``PluginManager``, so
  the worker can sync without also running every plugin's event handlers;
- accounts and their credentials (``connectors/secrets.py``);
- running a sync, storing the result, backing off on failure, and marking an
  account ``reauth_needed`` when its credential is refused;
- local-model mail summaries and local embeddings for search.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import re
import sys
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select

from life_graph.config import settings
from life_graph.connectors import secrets, store
from life_graph.connectors.base import (
    AUTH_FILE,
    AUTH_OAUTH,
    KIND_CODE,
    KIND_CONTACT,
    KIND_EMAIL,
    Account,
    Connector,
    ConnectorError,
    ReauthRequiredError,
)
from life_graph.connectors.exposure import EXPOSURES
from life_graph.connectors.models import ConnectorAccount, ConnectorItem
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

PLUGINS_DIR = Path(__file__).resolve().parents[2] / "plugins"
SYNC_TIMEOUT_SECONDS = 600
MAX_BACKOFF = timedelta(hours=6)


class AccountError(ValueError):
    """A request to create or change an account is invalid."""


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:100] or "account"


def discover(plugins_dir: Path = PLUGINS_DIR) -> dict[str, Connector]:
    """Import every ``plugins/<name>`` package that exports ``CONNECTOR``."""
    found: dict[str, Connector] = {}
    if not plugins_dir.is_dir():
        return found
    parent = str(plugins_dir.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    for child in sorted(plugins_dir.iterdir()):
        if not (child / "__init__.py").exists():
            continue
        try:
            module = importlib.import_module(f"{plugins_dir.name}.{child.name}")
        except Exception:
            logger.exception("Could not import plugin %s", child.name)
            continue
        connector = getattr(module, "CONNECTOR", None)
        if connector is None:
            continue
        if not isinstance(connector, Connector):
            logger.error("Plugin %s exports a CONNECTOR that is not a Connector", child.name)
            continue
        found[connector.name] = connector
    logger.info("Connectors available: %s", sorted(found) or "none")
    return found


@dataclass
class SyncOutcome:
    status: str
    fetched: int = 0
    new: int = 0
    deleted: int = 0
    summarized: int = 0
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v not in (None, {})}


def account_view(row: ConnectorAccount) -> Account:
    return Account(
        id=str(row.id),
        tenant_id=row.tenant_id,
        connector=row.connector,
        account_key=row.account_key,
        display_name=row.display_name,
        auth_method=row.auth_method,
        settings=dict(row.settings or {}),
    )


def account_public(row: ConnectorAccount, counts: dict[str, int] | None = None) -> dict[str, Any]:
    """An account as the API shows it. Never includes the credential."""
    return {
        "id": str(row.id),
        "connector": row.connector,
        "account_key": row.account_key,
        "display_name": row.display_name,
        "auth_method": row.auth_method,
        "settings": dict(row.settings or {}),
        "exposure": row.exposure,
        "enabled": row.enabled,
        "sync_interval_min": row.sync_interval_min,
        "status": row.status,
        "last_sync_at": row.last_sync_at.isoformat() if row.last_sync_at else None,
        "next_sync_at": row.next_sync_at.isoformat() if row.next_sync_at else None,
        "last_error": row.last_error,
        "has_credential": secrets.has_secret(row.tenant_id, str(row.id)),
        "items": counts or {},
    }


class ConnectorRuntime:
    def __init__(self, connectors: dict[str, Connector] | None = None) -> None:
        self.connectors = connectors if connectors is not None else discover()

    # ── Accounts ──────────────────────────────────────────────

    def catalogue(self) -> list[dict[str, Any]]:
        return [
            {
                "name": c.name,
                "display_name": c.display_name,
                "item_kinds": sorted(c.item_kinds),
                "auth_methods": list(c.auth_methods),
                "fields": list(getattr(c, "account_fields", ())),
                "cloud_field_options": list(getattr(c, "cloud_field_options", ())),
            }
            for c in self.connectors.values()
        ]

    async def list_accounts(self, tenant_id: str) -> list[dict[str, Any]]:
        async with async_session() as session:
            rows = (
                await session.execute(
                    select(ConnectorAccount)
                    .where(ConnectorAccount.tenant_id == tenant_id)
                    .order_by(ConnectorAccount.connector, ConnectorAccount.display_name)
                )
            ).scalars()
            counts = await store.counts_by_account(session, tenant_id)
            return [account_public(r, counts.get(str(r.id))) for r in rows]

    async def create_account(
        self,
        tenant_id: str,
        *,
        connector: str,
        display_name: str,
        auth_method: str,
        account_settings: dict[str, Any] | None = None,
        exposure: str = "standard",
        secret: dict[str, Any] | None = None,
        account_key: str | None = None,
    ) -> dict[str, Any]:
        impl = self.connectors.get(connector)
        if impl is None:
            raise AccountError(f"unknown connector {connector!r}")
        if auth_method not in impl.auth_methods:
            raise AccountError(f"{connector} does not support auth method {auth_method!r}")
        if exposure not in EXPOSURES:
            raise AccountError(f"exposure must be one of {EXPOSURES}")
        validate = getattr(impl, "validate_settings", None)
        clean_settings = (
            validate(auth_method, account_settings or {}) if validate else (account_settings or {})
        )
        clean_settings = {
            **clean_settings,
            **await self._verify(impl, auth_method, clean_settings, secret),
        }
        row = ConnectorAccount(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            connector=connector,
            account_key=_slug(account_key or display_name),
            display_name=display_name.strip()[:128] or connector,
            auth_method=auth_method,
            settings=clean_settings,
            exposure=exposure,
            enabled=True,
            sync_interval_min=getattr(
                impl, "default_interval_min", settings.connector_sync_minutes
            ),
            status="never_synced",
            # An imported source has nothing to fetch on a schedule.
            next_sync_at=None if auth_method == AUTH_FILE else datetime.now(UTC),
        )
        async with async_session() as session:
            existing = await session.execute(
                select(ConnectorAccount.id).where(
                    ConnectorAccount.tenant_id == tenant_id,
                    ConnectorAccount.connector == connector,
                    ConnectorAccount.account_key == row.account_key,
                )
            )
            if existing.first():
                raise AccountError(f"an account named {row.account_key!r} already exists")
            session.add(row)
            await session.commit()
        if secret:
            secrets.write_secret(tenant_id, str(row.id), {"method": auth_method, **secret})
        return account_public(row)

    @staticmethod
    async def _verify(
        impl: Connector, auth_method: str, account_settings: dict[str, Any], secret: dict | None
    ) -> dict[str, Any]:
        """Let the plugin check a new credential before it is stored (e.g. read-only)."""
        verify = getattr(impl, "verify_credential", None)
        if verify is None or not secret:
            return {}
        try:
            return dict(await verify(auth_method, account_settings, secret) or {})
        except ConnectorError as exc:
            raise AccountError(str(exc)) from exc

    async def _get(self, session, tenant_id: str, account_id: str) -> ConnectorAccount:
        try:
            aid = uuid.UUID(str(account_id))
        except ValueError as exc:
            raise AccountError("invalid account id") from exc
        row = (
            await session.execute(
                select(ConnectorAccount).where(
                    ConnectorAccount.id == aid, ConnectorAccount.tenant_id == tenant_id
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise AccountError("account not found")
        return row

    async def update_account(self, tenant_id: str, account_id: str, **changes: Any) -> dict:
        async with async_session() as session:
            row = await self._get(session, tenant_id, account_id)
            if "exposure" in changes and changes["exposure"] is not None:
                if changes["exposure"] not in EXPOSURES:
                    raise AccountError(f"exposure must be one of {EXPOSURES}")
                row.exposure = changes["exposure"]
            if changes.get("display_name"):
                row.display_name = changes["display_name"].strip()[:128]
            if changes.get("enabled") is not None:
                row.enabled = bool(changes["enabled"])
                if row.enabled and row.auth_method != AUTH_FILE:
                    row.next_sync_at = datetime.now(UTC)
            if changes.get("sync_interval_min"):
                row.sync_interval_min = max(5, min(int(changes["sync_interval_min"]), 1440))
            if changes.get("settings") is not None:
                impl = self.connectors.get(row.connector)
                validate = getattr(impl, "validate_settings", None)
                row.settings = (
                    validate(row.auth_method, changes["settings"])
                    if validate
                    else changes["settings"]
                )
            await session.commit()
            await session.refresh(row)
            if row.enabled is False:
                # Disabling hides the account at once; its rows go in the nightly purge.
                pass
            return account_public(row)

    async def set_credential(
        self, tenant_id: str, account_id: str, auth_method: str, secret: dict[str, Any]
    ) -> dict:
        """Store a new credential (and possibly a new method); schedule a sync now."""
        async with async_session() as session:
            row = await self._get(session, tenant_id, account_id)
            impl = self.connectors.get(row.connector)
            if impl is None or auth_method not in impl.auth_methods:
                raise AccountError(f"{row.connector} does not support {auth_method!r}")
            learned = await self._verify(impl, auth_method, dict(row.settings or {}), secret)
            if learned:
                row.settings = {**(row.settings or {}), **learned}
            secrets.write_secret(tenant_id, str(row.id), {"method": auth_method, **secret})
            if auth_method != row.auth_method:
                # Sources key items differently (IMAP Message-ID vs Gmail id):
                # re-index from scratch rather than hold duplicates.
                await session.execute(
                    delete(ConnectorItem).where(ConnectorItem.account_id == row.id)
                )
            row.auth_method = auth_method
            row.status = "never_synced"
            row.consecutive_failures = 0
            row.last_error = None
            row.next_sync_at = datetime.now(UTC)
            # A new method may mean a new source (IMAP vs Gmail API): its
            # cursor means nothing to the other one.
            row.cursor = {}
            await session.commit()
            await session.refresh(row)
            return account_public(row)

    async def mark_reconnected(self, tenant_id: str, account_id: str) -> None:
        """After a Google sign-in: clear the error state and sync soon."""
        async with async_session() as session:
            row = await self._get(session, tenant_id, account_id)
            row.status = "never_synced" if row.last_sync_at is None else "ok"
            row.consecutive_failures = 0
            row.last_error = None
            row.next_sync_at = datetime.now(UTC)
            await session.commit()

    async def delete_account(self, tenant_id: str, account_id: str) -> None:
        async with async_session() as session:
            row = await self._get(session, tenant_id, account_id)
            await session.delete(row)  # items cascade
            await session.commit()
        secrets.delete_secret(tenant_id, str(row.id))

    # ── Sync ──────────────────────────────────────────────────

    async def _secret_for(self, row: ConnectorAccount) -> dict[str, Any]:
        if row.auth_method == AUTH_FILE:
            return {}  # imported data: there is no credential
        secret = secrets.read_secret(row.tenant_id, str(row.id))
        if row.auth_method == AUTH_OAUTH:
            from life_graph.connectors import google_oauth

            secret = {**secret, "access_token": await google_oauth.access_token(row, secret)}
        return secret

    async def sync_account(self, tenant_id: str, account_id: str) -> SyncOutcome:
        async with async_session() as session:
            row = await self._get(session, tenant_id, account_id)
            impl = self.connectors.get(row.connector)
            view = account_view(row)
            cursor = dict(row.cursor or {})
            interval = row.sync_interval_min

        if impl is None:
            return await self._record_failure(
                tenant_id,
                account_id,
                f"connector plugin {row.connector!r} is not installed",
                reauth=False,
                interval=interval,
            )
        try:
            secret = await self._secret_for(row)
            result = await asyncio.wait_for(
                impl.sync(view, secret, cursor), timeout=SYNC_TIMEOUT_SECONDS
            )
        except ReauthRequiredError as exc:
            return await self._record_failure(
                tenant_id,
                account_id,
                str(exc) or "credential rejected",
                reauth=True,
                interval=interval,
            )
        except (secrets.SecretError, ConnectorError) as exc:
            return await self._record_failure(
                tenant_id, account_id, str(exc), reauth=False, interval=interval
            )
        except TimeoutError:
            return await self._record_failure(
                tenant_id,
                account_id,
                f"sync timed out after {SYNC_TIMEOUT_SECONDS}s",
                reauth=False,
                interval=interval,
            )
        except Exception as exc:  # a plugin bug must not take the worker down
            logger.exception("Connector %s sync crashed", view.connector)
            return await self._record_failure(
                tenant_id,
                account_id,
                f"{type(exc).__name__}: {exc}",
                reauth=False,
                interval=interval,
            )

        now = datetime.now(UTC)
        async with async_session() as session:
            row = await self._get(session, tenant_id, account_id)
            new_ids = await store.upsert_items(session, row, result.items)
            deleted = await store.delete_external(session, row, result.deleted)
            if result.complete:
                for kind in impl.item_kinds:
                    keep = {i.external_id for i in result.items if i.kind == kind}
                    deleted += await store.delete_missing(session, row, kind, keep)
            row.cursor = result.cursor
            row.status = "ok"
            row.last_error = None
            row.consecutive_failures = 0
            row.last_sync_at = now
            row.next_sync_at = now + timedelta(minutes=row.sync_interval_min)
            await session.commit()

        outcome = SyncOutcome(
            status="ok", fetched=len(result.items), new=len(new_ids), deleted=deleted
        )
        if KIND_EMAIL in impl.item_kinds:
            sources = {i.external_id: i.summary_source for i in result.items if i.summary_source}
            outcome.summarized = await self._summarize_pending(row, impl, secret, sources)
        await self._embed_missing(row)
        logger.info(
            "Connector %s/%s synced: %s", view.connector, view.account_key, outcome.as_dict()
        )
        return outcome

    async def import_file(self, tenant_id: str, account_id: str, text: str) -> SyncOutcome:
        """Replace an import-based account's items with the contents of a file."""
        async with async_session() as session:
            row = await self._get(session, tenant_id, account_id)
        impl = self.connectors.get(row.connector)
        importer = getattr(impl, "import_file", None)
        if row.auth_method != AUTH_FILE or importer is None:
            raise AccountError("this account does not take file imports")
        try:
            result = importer(account_view(row), text)
        except ConnectorError as exc:
            raise AccountError(str(exc)) from exc
        now = datetime.now(UTC)
        async with async_session() as session:
            row = await self._get(session, tenant_id, account_id)
            new_ids = await store.upsert_items(session, row, result.items)
            deleted = 0
            for kind in impl.item_kinds:
                keep = {i.external_id for i in result.items if i.kind == kind}
                deleted += await store.delete_missing(session, row, kind, keep)
            row.status = "ok"
            row.last_error = None
            row.consecutive_failures = 0
            row.last_sync_at = now
            await session.commit()
        outcome = SyncOutcome(
            status="ok", fetched=len(result.items), new=len(new_ids), deleted=deleted
        )
        logger.info(
            "Connector %s/%s imported: %s", row.connector, row.account_key, outcome.as_dict()
        )
        return outcome

    async def _record_failure(
        self, tenant_id: str, account_id: str, error: str, *, reauth: bool, interval: int
    ) -> SyncOutcome:
        now = datetime.now(UTC)
        async with async_session() as session:
            row = await self._get(session, tenant_id, account_id)
            row.consecutive_failures += 1
            row.last_error = error[:1000]
            if reauth:
                row.status = "reauth_needed"
                row.next_sync_at = None  # nothing to gain by retrying a refused credential
            else:
                row.status = "error"
                backoff = timedelta(minutes=interval) * (2 ** min(row.consecutive_failures, 6))
                row.next_sync_at = now + min(backoff, MAX_BACKOFF)
            await session.commit()
        logger.warning("Connector account %s sync failed: %s", account_id, error)
        return SyncOutcome(status="reauth_needed" if reauth else "error", error=error)

    async def _summarize_pending(
        self,
        row: ConnectorAccount,
        impl: Connector,
        secret: dict[str, Any],
        sources: dict[str, str],
    ) -> int:
        from life_graph.connectors.summarize import summarize_email

        done = 0
        async with async_session() as session:
            pending = await store.pending_summaries(
                session, row, settings.connector_summaries_per_sync
            )
            for item in pending:
                text = sources.get(item.external_id)
                if text is None:
                    try:
                        text = await impl.fetch_body(account_view(row), secret, item.external_id)
                    except Exception:
                        logger.debug("fetch_body failed for %s", item.external_id, exc_info=True)
                        text = None
                result = await summarize_email(
                    subject=item.title,
                    sender=item.sender_name or item.sender_addr,
                    text=text or "",
                    automated=bool((item.flags or {}).get("automated")),
                    sent=item.direction == "sent",
                    sent_at=item.occurred_at,
                )
                item.summary = result.summary
                item.category = result.category
                flags = {
                    **(item.flags or {}),
                    "asks_me": result.asks_me,
                    "suspicious": result.suspicious,
                }
                if result.commitment:
                    flags["commitment"] = result.commitment
                    if result.commitment_due:
                        flags["commitment_due"] = result.commitment_due.isoformat()
                item.flags = flags
                item.summary_state = "done" if result.ok else "failed"
                item.embedding = None  # re-embed with the summary included
                # Per message: each summary costs seconds of local-model time,
                # so a restart mid-batch keeps what was already done.
                await session.commit()
                done += 1
        return done

    async def _embed_missing(self, account: ConnectorAccount, limit: int = 200) -> None:
        from life_graph.api.dependencies import get_embedding_service

        async with async_session() as session:
            rows = list(
                (
                    await session.execute(
                        select(ConnectorItem)
                        .where(
                            ConnectorItem.tenant_id == account.tenant_id,
                            ConnectorItem.account_id == account.id,
                            ConnectorItem.embedding.is_(None),
                            ConnectorItem.summary_state != "pending",
                            # Contacts and code items are found by name, not meaning.
                            ConnectorItem.kind.not_in([KIND_CONTACT, KIND_CODE]),
                        )
                        .limit(limit)
                    )
                ).scalars()
            )
            if not rows:
                return
            texts = [
                " — ".join(p for p in (r.title, r.summary, r.sender_name, r.location) if p)[:1000]
                or "(empty)"
                for r in rows
            ]
            try:
                vectors = await get_embedding_service().embed_batch_async(texts)
            except Exception:
                logger.warning("Embedding connector items failed", exc_info=True)
                return
            for r, v in zip(rows, vectors, strict=False):
                if v:
                    r.embedding = v
            await session.commit()

    async def due_accounts(self, now: datetime | None = None) -> list[tuple[str, str]]:
        now = now or datetime.now(UTC)
        async with async_session() as session:
            rows = await session.execute(
                select(ConnectorAccount.tenant_id, ConnectorAccount.id).where(
                    ConnectorAccount.enabled.is_(True),
                    ConnectorAccount.status != "reauth_needed",
                    ConnectorAccount.next_sync_at.is_not(None),
                    ConnectorAccount.next_sync_at <= now,
                )
            )
            return [(t, str(i)) for t, i in rows.all()]

    async def sync_due(self) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for tenant_id, account_id in await self.due_accounts():
            from life_graph.core.tenant import set_tenant_context

            set_tenant_context(tenant_id, "system")
            results[account_id] = (await self.sync_account(tenant_id, account_id)).as_dict()
        return results

    async def purge(self) -> int:
        async with async_session() as session:
            n = await store.purge_expired(session)
            await session.commit()
        return n


_runtime: ConnectorRuntime | None = None


def get_runtime() -> ConnectorRuntime:
    global _runtime
    if _runtime is None:
        _runtime = ConnectorRuntime()
    return _runtime
