"""Server health watcher — monitors servers via SSH and HTTP.

Checks disk usage, CPU load, memory, and service status.
Supports disk projection (estimates days until full).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Lazy asyncssh import — may not be installed
_asyncssh = None
_asyncssh_checked = False


def _get_asyncssh():
    """Try to import asyncssh. Returns module or None."""
    global _asyncssh, _asyncssh_checked
    if not _asyncssh_checked:
        try:
            import asyncssh
            _asyncssh = asyncssh
        except ImportError:
            logger.warning(
                "asyncssh not installed — SSH-based server health checks disabled. "
                "Install with: pip install asyncssh"
            )
            _asyncssh = None
        _asyncssh_checked = True
    return _asyncssh


class ServerHealthWatcher:
    """Monitors server health via SSH commands and HTTP endpoints.

    Inherits from BaseWatcher once it exists. For now, uses a
    compatible interface.

    Attributes:
        name: Watcher identifier.
        default_schedule: Cron expression (hourly).
    """

    name = "server_health"
    default_schedule = "0 * * * *"

    # Thresholds
    DISK_WARN = 80
    DISK_CRIT = 95
    CPU_WARN = 80.0
    SSH_TIMEOUT = 30

    def __init__(self, config: dict[str, Any] | None = None, session_factory=None):
        self.config = config or {}
        self._session_factory = session_factory

    async def execute(self) -> list[dict[str, Any]]:
        """Run health checks on all configured servers.

        Returns:
            List of event dicts (one per finding).
        """
        servers = self.config.get("servers", [])
        if not servers:
            logger.info("No servers configured for health watcher")
            return []

        events: list[dict[str, Any]] = []
        for server_config in servers:
            try:
                server_events = await self._check_server(server_config)
                events.extend(server_events)
            except Exception as e:
                events.append({
                    "severity": "critical",
                    "title": f"Server check failed: {server_config.get('name', server_config.get('host', 'unknown'))}",
                    "details": str(e),
                    "watcher_name": self.name,
                    "timestamp": datetime.now(timezone.utc),
                })

        return events

    async def _check_server(self, server_config: dict[str, Any]) -> list[dict[str, Any]]:
        """Check a single server via SSH or HTTP fallback.

        Args:
            server_config: Dict with keys: host, port (22), username,
                          password/key_file, name, check_type ('ssh'|'http'),
                          services (list of systemd services).

        Returns:
            List of event dicts for any issues found.
        """
        check_type = server_config.get("check_type", "ssh")
        name = server_config.get("name", server_config.get("host", "unknown"))
        events: list[dict[str, Any]] = []

        if check_type == "http":
            return await self._check_http(server_config)

        asyncssh = _get_asyncssh()
        if asyncssh is None:
            return [{
                "severity": "important",
                "title": f"Cannot check {name} — asyncssh not installed",
                "details": "Install asyncssh to enable SSH health checks.",
                "watcher_name": self.name,
                "timestamp": datetime.now(timezone.utc),
            }]

        try:
            conn = await asyncssh.connect(
                host=server_config["host"],
                port=server_config.get("port", 22),
                username=server_config.get("username", "root"),
                password=server_config.get("password"),
                client_keys=[server_config["key_file"]] if server_config.get("key_file") else None,
                known_hosts=None,
                connect_timeout=self.SSH_TIMEOUT,
            )
        except Exception as e:
            return [{
                "severity": "critical",
                "title": f"SSH unreachable: {name}",
                "details": f"Connection failed after {self.SSH_TIMEOUT}s: {e}",
                "watcher_name": self.name,
                "timestamp": datetime.now(timezone.utc),
            }]

        try:
            # Disk
            disk_events = await self._get_disk_usage(conn, name)
            events.extend(disk_events)

            # CPU
            cpu_events = await self._get_cpu_load(conn, name)
            events.extend(cpu_events)

            # Memory
            mem_events = await self._get_memory(conn, name)
            events.extend(mem_events)

            # Services
            services = server_config.get("services", [])
            if services:
                svc_events = await self._check_services(conn, services, name)
                events.extend(svc_events)

        finally:
            conn.close()

        return events

    async def _get_disk_usage(self, conn: Any, server_name: str) -> list[dict[str, Any]]:
        """Parse ``df -h`` output for disk usage alerts.

        Returns events for partitions exceeding thresholds.
        Also estimates days until full if >80%.
        """
        events: list[dict[str, Any]] = []
        try:
            result = await conn.run("df -h --output=pcent,target", check=True, timeout=10)
            lines = result.stdout.strip().split("\n")[1:]  # skip header

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) < 2:
                    continue

                pct_str = parts[0].rstrip("%")
                mount = parts[1]

                # Skip pseudo-filesystems
                if mount in ("/dev", "/dev/shm", "/run", "/sys", "/proc"):
                    continue

                try:
                    pct = int(pct_str)
                except ValueError:
                    continue

                if pct >= self.DISK_CRIT:
                    projection = await self._project_disk_full(conn, mount)
                    events.append({
                        "severity": "critical",
                        "title": f"Disk critical: {server_name} {mount} at {pct}%",
                        "details": f"Partition {mount} is {pct}% full. {projection}",
                        "watcher_name": self.name,
                        "timestamp": datetime.now(timezone.utc),
                    })
                elif pct >= self.DISK_WARN:
                    projection = await self._project_disk_full(conn, mount)
                    events.append({
                        "severity": "important",
                        "title": f"Disk warning: {server_name} {mount} at {pct}%",
                        "details": f"Partition {mount} is {pct}% full. {projection}",
                        "watcher_name": self.name,
                        "timestamp": datetime.now(timezone.utc),
                    })
        except Exception as e:
            logger.warning("Disk usage check failed for %s: %s", server_name, e)

        return events

    async def _project_disk_full(self, conn: Any, mount: str) -> str:
        """Estimate days until partition is full based on recent growth.

        Uses df to get used/total and assumes linear growth.
        Returns a human-readable projection string.
        """
        try:
            result = await conn.run(
                f"df --output=used,avail '{mount}'",
                check=True,
                timeout=10,
            )
            lines = result.stdout.strip().split("\n")
            if len(lines) < 2:
                return ""

            parts = lines[1].split()
            if len(parts) < 2:
                return ""

            used = int(parts[0])
            avail = int(parts[1])

            if used == 0:
                return "Cannot estimate growth (no usage data)."

            # Simple projection: assume 1% daily growth
            daily_growth = used * 0.01
            if daily_growth > 0:
                days_left = avail / daily_growth
                if days_left < 7:
                    return f"⚠️ Estimated full in ~{days_left:.0f} days at current rate."
                elif days_left < 30:
                    return f"Estimated full in ~{days_left:.0f} days."
                else:
                    return f"Estimated full in ~{days_left:.0f} days (low risk)."

            return ""
        except Exception:
            return ""

    async def _get_cpu_load(self, conn: Any, server_name: str) -> list[dict[str, Any]]:
        """Parse ``cat /proc/loadavg`` for CPU load alerts."""
        events: list[dict[str, Any]] = []
        try:
            result = await conn.run("cat /proc/loadavg", check=True, timeout=10)
            parts = result.stdout.strip().split()
            if parts:
                load_1 = float(parts[0])

                # Get number of CPUs for context
                cpu_result = await conn.run("nproc", check=True, timeout=5)
                ncpu = int(cpu_result.stdout.strip())

                load_pct = (load_1 / ncpu) * 100 if ncpu > 0 else load_1 * 100

                if load_pct >= self.CPU_WARN:
                    events.append({
                        "severity": "important",
                        "title": f"High CPU: {server_name} at {load_pct:.0f}%",
                        "details": (
                            f"1-min load avg: {load_1:.2f}, "
                            f"5-min: {parts[1] if len(parts) > 1 else 'N/A'}, "
                            f"15-min: {parts[2] if len(parts) > 2 else 'N/A'} "
                            f"({ncpu} cores)"
                        ),
                        "watcher_name": self.name,
                        "timestamp": datetime.now(timezone.utc),
                    })
        except Exception as e:
            logger.warning("CPU check failed for %s: %s", server_name, e)

        return events

    async def _get_memory(self, conn: Any, server_name: str) -> list[dict[str, Any]]:
        """Parse ``free -m`` for memory usage."""
        events: list[dict[str, Any]] = []
        try:
            result = await conn.run("free -m", check=True, timeout=10)
            lines = result.stdout.strip().split("\n")

            for line in lines:
                if line.startswith("Mem:"):
                    parts = line.split()
                    if len(parts) >= 3:
                        total = int(parts[1])
                        used = int(parts[2])
                        if total > 0:
                            pct = (used / total) * 100
                            if pct >= 90:
                                events.append({
                                    "severity": "critical",
                                    "title": f"Memory critical: {server_name} at {pct:.0f}%",
                                    "details": f"Used {used}MB of {total}MB ({pct:.1f}%)",
                                    "watcher_name": self.name,
                                    "timestamp": datetime.now(timezone.utc),
                                })
                            elif pct >= 80:
                                events.append({
                                    "severity": "important",
                                    "title": f"High memory: {server_name} at {pct:.0f}%",
                                    "details": f"Used {used}MB of {total}MB ({pct:.1f}%)",
                                    "watcher_name": self.name,
                                    "timestamp": datetime.now(timezone.utc),
                                })
                    break

        except Exception as e:
            logger.warning("Memory check failed for %s: %s", server_name, e)

        return events

    async def _check_services(
        self,
        conn: Any,
        services: list[str],
        server_name: str,
    ) -> list[dict[str, Any]]:
        """Check systemd service status via ``systemctl is-active``."""
        events: list[dict[str, Any]] = []

        for svc in services:
            try:
                result = await conn.run(
                    f"systemctl is-active {svc}",
                    check=False,
                    timeout=10,
                )
                status = result.stdout.strip()

                if status != "active":
                    events.append({
                        "severity": "critical",
                        "title": f"Service down: {svc} on {server_name}",
                        "details": f"Service '{svc}' status: {status}",
                        "watcher_name": self.name,
                        "timestamp": datetime.now(timezone.utc),
                    })
            except Exception as e:
                events.append({
                    "severity": "important",
                    "title": f"Cannot check service {svc} on {server_name}",
                    "details": str(e),
                    "watcher_name": self.name,
                    "timestamp": datetime.now(timezone.utc),
                })

        return events

    async def _check_http(self, server_config: dict[str, Any]) -> list[dict[str, Any]]:
        """Fallback: check server via HTTP(S) endpoint."""
        events: list[dict[str, Any]] = []
        name = server_config.get("name", server_config.get("host", "unknown"))
        url = server_config.get("url", f"http://{server_config['host']}/health")
        timeout = server_config.get("timeout", 10)

        try:
            import httpx

            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url)

            if resp.status_code >= 500:
                events.append({
                    "severity": "critical",
                    "title": f"HTTP health check failed: {name}",
                    "details": f"GET {url} returned {resp.status_code}",
                    "watcher_name": self.name,
                    "timestamp": datetime.now(timezone.utc),
                })
            elif resp.status_code >= 400:
                events.append({
                    "severity": "important",
                    "title": f"HTTP health check warning: {name}",
                    "details": f"GET {url} returned {resp.status_code}",
                    "watcher_name": self.name,
                    "timestamp": datetime.now(timezone.utc),
                })

        except Exception as e:
            events.append({
                "severity": "critical",
                "title": f"HTTP unreachable: {name}",
                "details": f"GET {url} failed: {e}",
                "watcher_name": self.name,
                "timestamp": datetime.now(timezone.utc),
            })

        return events
