"""Grab the current selection and active-window context.

The pure logic (clipboard save/restore, selection-vs-clipboard decision,
window normalization) is separated from OS calls so it is unit-testable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class WindowInfo:
    app: str
    title: str


def normalize_window(title, app) -> WindowInfo:
    return WindowInfo(app=(app or "").strip(), title=(title or "").strip())


def grab_selection(*, copy_fn, read_clipboard, write_clipboard, sleep_fn) -> tuple[str, str]:
    """Copy the current selection to the clipboard, read it, then restore.

    Returns (text, source). source is "selection" if the copy changed the
    clipboard, else "clipboard" (nothing was selected; we use prior contents).
    """
    prior = read_clipboard() or ""
    try:
        # Sentinel so we can detect whether Ctrl+C actually replaced the clipboard.
        write_clipboard("")
        copy_fn()
        # Poll the clipboard instead of a single fixed wait — apps service the
        # simulated Ctrl+C at very different speeds, and a fixed sleep loses the
        # selection (falling back to stale clipboard) whenever the copy is slow.
        grabbed = ""
        for _ in range(12):  # up to ~0.6s
            sleep_fn(0.05)
            grabbed = read_clipboard() or ""
            if grabbed:
                break
        if grabbed:
            return grabbed, "selection"
        return prior, "clipboard"
    finally:
        write_clipboard(prior)  # always restore the user's clipboard


# ── Real OS wiring (Windows; manual verification) ─────────────────────


def read_active_window() -> WindowInfo:  # pragma: no cover - OS call
    import pygetwindow

    win = pygetwindow.getActiveWindow()
    title = getattr(win, "title", "") if win else ""
    app = _active_process_name()
    return normalize_window(title, app)


def _active_process_name() -> str:  # pragma: no cover - OS call
    try:
        import win32gui
        import win32process
        import psutil

        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return psutil.Process(pid).name()
    except Exception:
        return ""


def grab_current() -> tuple[str, str]:  # pragma: no cover - OS call
    import pyperclip
    from pynput.keyboard import Controller, Key

    kb = Controller()

    def copy_fn():
        # The global hotkey fires while its own modifiers (Ctrl+Alt) and trigger
        # key are still physically held. If we simulate Ctrl+C now, the still-held
        # Alt turns it into Ctrl+Alt+C and nothing gets copied. Release the held
        # keys first, let the OS settle, then send a clean Ctrl+C.
        for key in (Key.alt_l, Key.alt_r, Key.ctrl_l, Key.ctrl_r, "c", Key.space):
            try:
                kb.release(key)
            except Exception:
                pass
        time.sleep(0.05)
        with kb.pressed(Key.ctrl):
            kb.press("c")
            kb.release("c")

    return grab_selection(
        copy_fn=copy_fn,
        read_clipboard=pyperclip.paste,
        write_clipboard=pyperclip.copy,
        sleep_fn=time.sleep,
    )
