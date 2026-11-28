"""The environment a run on one account gets: the host allowlist plus a strict overlay.

``drivers/host_exec.host_driver_env`` builds the allowlisted base (PATH, HOME,
locale, ``driver_host_env_passthrough``...). For an account run:

1. every credential variable of that driver is removed from the base
   (``catalog.CREDENTIAL_ENV``), so a key the operator passes through for the
   default login cannot leak into, or silently bill, another account's run;
2. the overlay is added: the account's home variable, its API key for an
   ``api_key`` account, the Vertex trio for a ``vertex`` account;
3. the overlay is checked against ``catalog.allowed_env_names``: a name not
   listed for that driver and kind is refused, not dropped.

The overlay holds a secret for an api_key account: it lives in memory for one
process start and is never logged, put in metadata or returned.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from life_graph.services.agent_accounts.catalog import (
    API_KEY_ENV,
    CREDENTIAL_ENV,
    HOME_ENV,
    VERTEX_ENV,
    AccountError,
    allowed_env_names,
)


@dataclass
class AccountEnv:
    """What applying an account to a run's environment means."""

    driver: str
    kind: str
    overlay: dict[str, str] = field(default_factory=dict, repr=False)
    remove: tuple[str, ...] = ()

    def apply(self, env: dict[str, str]) -> dict[str, str]:
        """A copy of *env* with the credentials removed and the overlay set."""
        out = {k: v for k, v in env.items() if k not in self.remove}
        out.update(self.overlay)
        return out

    def names(self) -> list[str]:
        """The variable names set (safe to log; never the values)."""
        return sorted(self.overlay)


def build_account_env(
    driver: str,
    kind: str,
    *,
    home: str | None,
    api_key: str | None = None,
    properties: dict | None = None,
) -> AccountEnv:
    """The overlay for one account. Raises AccountError on anything off-list."""
    overlay: dict[str, str] = {}
    if driver in HOME_ENV:
        if not home:
            raise AccountError(f"{driver} account has no home directory")
        overlay[HOME_ENV[driver]] = home
    if kind == "api_key":
        if not api_key:
            raise AccountError("api_key account has no key set (PUT .../secret)")
        if driver not in API_KEY_ENV:
            raise AccountError(f"{driver} has no API-key variable")
        overlay[API_KEY_ENV[driver]] = api_key
    elif kind == "vertex":
        if driver not in VERTEX_ENV:
            raise AccountError(f"{driver} has no Vertex mode")
        props = properties or {}
        if not props.get("project") or not props.get("region"):
            raise AccountError("vertex account needs properties.project and .region")
        (flag, value), project_var, region_var = VERTEX_ENV[driver]
        overlay[flag] = value
        overlay[project_var] = str(props["project"])
        overlay[region_var] = str(props["region"])
    allowed = allowed_env_names(driver, kind)
    extra = sorted(set(overlay) - allowed)
    if extra:
        raise AccountError(f"variables not allowed for {driver}/{kind}: {extra}")
    remove = tuple(n for n in CREDENTIAL_ENV.get(driver, ()) if n not in overlay)
    return AccountEnv(driver=driver, kind=kind, overlay=overlay, remove=remove)
