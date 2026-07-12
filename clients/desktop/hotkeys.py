"""Global hotkey registration via pynput."""

from __future__ import annotations

import logging

from pynput import keyboard

logger = logging.getLogger("desktop.hotkeys")


class HotkeyManager:
    def __init__(self, bindings: dict) -> None:
        self._bindings = bindings
        self._enabled = True
        self._listener: keyboard.GlobalHotKeys | None = None

    def _wrap(self, fn):
        def handler():
            if self._enabled:
                try:
                    fn()
                except Exception:
                    logger.exception("Hotkey handler failed")
        return handler

    def start(self) -> None:
        wrapped = {combo: self._wrap(fn) for combo, fn in self._bindings.items()}
        self._listener = keyboard.GlobalHotKeys(wrapped)
        self._listener.start()
        logger.info("Hotkeys active: %s", list(self._bindings))

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
