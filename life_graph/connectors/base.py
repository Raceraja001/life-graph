"""The connector contract: what a data-source plugin implements.

A connector is a plugin (``plugins/<name>/__init__.py`` exporting ``CONNECTOR``)
that knows how to talk to one kind of source (a calendar feed, a mailbox).
It never touches the database, the tool registry or a model: it returns plain
``Item`` objects and the core runtime (``connectors/runtime.py``) stores them,
decides what any caller may see (``connectors/exposure.py``) and renders them.

That split is the point of the design (docs/specs/connectors.md): a buggy or
careless plugin cannot leak a mail body to a cloud model, because it never
chooses who sees what.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime

# Item kinds the core knows how to store, filter and render.
KIND_EVENT = "event"
KIND_EMAIL = "email"
KIND_CONTACT = "contact"
KIND_CODE = "code"  # pull requests and issues on a code host
KIND_TASK = "task"  # the user's own to-do items

# Directions. Events: the user's own vs an invitation from someone else.
# Mail: received vs sent by the user. Trust tiers are derived from these.
DIR_OWN = "own"
DIR_INVITE = "invite"
DIR_INBOUND = "inbound"
DIR_SENT = "sent"

AUTH_APP_PASSWORD = "app_password"
AUTH_OAUTH = "oauth"
AUTH_NONE = "none"  # e.g. a calendar feed URL is itself the secret
AUTH_FILE = "file"  # data arrives by import (a vCard file), not by sync
AUTH_TOKEN = "token"  # a read-only access token (a GitHub fine-grained token)


@dataclass(frozen=True)
class Account:
    """One configured account, as the runtime hands it to a connector."""

    id: str
    tenant_id: str
    connector: str
    account_key: str
    display_name: str
    auth_method: str
    settings: dict[str, Any] = field(default_factory=dict)  # host, username, …


@dataclass
class Item:
    """One event or message, as a connector returns it.

    ``external_id`` must be stable across syncs (the upsert key). Fields that
    do not apply to a kind stay empty. ``detail`` holds text that must never be
    cloud-bound (an event description, meeting links); ``body`` is filled only
    by ``fetch_body`` for local callers and is never stored.
    """

    kind: str
    external_id: str
    direction: str
    occurred_at: datetime
    title: str = ""
    thread_key: str | None = None
    sender_name: str | None = None
    sender_addr: str | None = None
    to_me: bool | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    all_day: bool = False
    location: str | None = None
    attendees: list[str] = field(default_factory=list)
    # Addresses of the people the item involves, never the user's own: a
    # contact's addresses, an event's attendees, a mail's sender and recipients.
    emails: list[str] = field(default_factory=list)
    detail: str | None = None
    flags: dict[str, Any] = field(default_factory=dict)
    # Text handed to the local summariser (mail); never stored, never rendered.
    summary_source: str | None = None


@dataclass
class SyncResult:
    """What one ``sync()`` call produced."""

    items: list[Item] = field(default_factory=list)
    # external_ids the source says are gone (a cancelled event, a deleted mail).
    deleted: list[str] = field(default_factory=list)
    cursor: dict[str, Any] = field(default_factory=dict)
    # True when ``items`` is the complete current set for the account's window
    # (a full ICS download): the runtime then deletes stored items not in it.
    complete: bool = False


class ConnectorError(Exception):
    """A sync failed for a reason worth showing the user (auth, network, …)."""


class ReauthRequiredError(ConnectorError):
    """The credential was rejected or revoked; the user must reconnect."""


@runtime_checkable
class Connector(Protocol):
    """What a plugin's ``CONNECTOR`` object provides.

    Optional extras the runtime looks for with ``getattr``: ``account_fields``,
    ``validate_settings(auth_method, raw)``, ``default_interval_min``,
    ``cloud_field_options``, ``import_file(account, text) -> SyncResult`` and
    ``async verify_credential(auth_method, settings, secret) -> dict`` (checked
    when a credential is added; returns settings to store, e.g. the login).
    """

    name: str
    display_name: str
    item_kinds: frozenset[str]
    auth_methods: tuple[str, ...]

    async def sync(
        self, account: Account, secret: dict[str, Any], cursor: dict[str, Any]
    ) -> SyncResult:
        """Fetch changes since ``cursor``. Raise ConnectorError / ReauthRequiredError."""
        ...

    async def fetch_body(
        self, account: Account, secret: dict[str, Any], external_id: str
    ) -> str | None:
        """Full text of one item, fetched live and read-only. None if unsupported."""
        ...
