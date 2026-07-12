"""Desktop Capture Agent entry point — wires all modules together."""

from __future__ import annotations

import argparse
import getpass
import logging
import os
import subprocess
import sys
import threading
import time

from clients.desktop.client import CaptureClient, SendStatus, build_payload
from clients.desktop.config import (
    ConfigError,
    default_config_path,
    load_config,
    set_api_key,
)
from clients.desktop.grab import grab_current, read_active_window
from clients.desktop.hotkeys import HotkeyManager
from clients.desktop.popup import show_popup
from clients.desktop.queue import CaptureQueue
from clients.desktop.tray import Tray

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("desktop.app")


class Agent:
    def __init__(self, config) -> None:
        self._cfg = config
        self._client = CaptureClient(
            config.backend_url, config.api_key, config.tenant_id
        )
        self._queue = CaptureQueue(default_config_path().parent / "queue.db")
        self._tray: Tray | None = None

    # ── capture flows ────────────────────────────────────────
    def _deliver(self, payload: dict, ok_msg: str) -> None:
        result = self._client.send(payload)
        if result.status == SendStatus.SENT:
            self._notify("Life Graph", ok_msg)
            self._queue.replay(self._client.send)
        elif result.status == SendStatus.AUTH:
            self._notify("Life Graph", "Auth failed — check settings")
        elif result.status == SendStatus.BAD:
            logger.warning("Dropped bad capture: %s", result.detail)
        else:  # TRANSIENT
            self._queue.enqueue(payload)
            self._notify("Life Graph", "Queued (offline)")

    def capture_popup(self) -> None:
        text, source = grab_current()
        draft = show_popup(prefill=text)
        if draft is None:
            return
        win = read_active_window()
        payload = build_payload(
            content=draft.content, app=win.app, window_title=win.title,
            source=source if draft.content == text else "note",
            tags=draft.tags, do_redact=self._cfg.redact,
        )
        self._deliver(payload, "Saved")

    def capture_instant(self) -> None:
        text, source = grab_current()
        if not text.strip():
            self._notify("Life Graph", "Nothing selected")
            return
        win = read_active_window()
        payload = build_payload(
            content=text, app=win.app, window_title=win.title,
            source=source, do_redact=self._cfg.redact,
        )
        self._deliver(payload, "✓ Saved")

    # ── infra ────────────────────────────────────────────────
    def _notify(self, title: str, msg: str) -> None:
        if self._tray:
            self._tray.notify(title, msg)
        logger.info("%s: %s", title, msg)

    def _replay_loop(self) -> None:
        while True:
            try:
                self._queue.replay(self._client.send)
            except Exception:
                logger.exception("Replay loop error")
            time.sleep(self._cfg.replay_interval_seconds)

    def run(self) -> None:
        hotkeys = HotkeyManager({
            self._cfg.hotkeys.popup: self.capture_popup,
            self._cfg.hotkeys.instant: self.capture_instant,
        })
        hotkeys.start()
        threading.Thread(target=self._replay_loop, daemon=True).start()

        self._tray = Tray(
            on_pause_toggle=hotkeys.set_enabled_inverted,
            on_quit=hotkeys.stop,
            on_settings=lambda: _open_folder(default_config_path().parent),
        )
        self._tray.run()  # blocks


def _open_folder(path) -> None:
    try:
        os.startfile(str(path))  # noqa: S606 - Windows only
    except Exception:
        subprocess.Popen(["explorer", str(path)])


def install_autostart() -> None:
    """Register the agent to launch on login via the Startup folder shortcut."""
    startup = os.path.join(
        os.environ["APPDATA"],
        r"Microsoft\Windows\Start Menu\Programs\Startup",
    )
    target = f'"{sys.executable}" -m clients.desktop.app'
    bat = os.path.join(startup, "life-graph-capture.bat")
    with open(bat, "w", encoding="utf-8") as f:
        f.write(f"@echo off\nstart \"\" {target}\n")
    logger.info("Autostart installed: %s", bat)


def _cmd_set_key() -> None:
    cfg_path = default_config_path()
    tenant = input("tenant_id [default]: ").strip() or "default"
    key = getpass.getpass("service API key: ").strip()
    set_api_key(tenant, key)
    print(f"Stored API key for tenant {tenant!r}. Ensure {cfg_path} sets tenant_id = \"{tenant}\".")


def main() -> None:
    parser = argparse.ArgumentParser(prog="clients.desktop.app")
    parser.add_argument("--set-key", action="store_true", help="store API key in keyring")
    parser.add_argument("--install-autostart", action="store_true")
    args = parser.parse_args()

    if args.set_key:
        _cmd_set_key()
        return
    if args.install_autostart:
        install_autostart()
        return

    try:
        config = load_config()
    except ConfigError as e:
        print(e)
        return
    Agent(config).run()


if __name__ == "__main__":
    main()
