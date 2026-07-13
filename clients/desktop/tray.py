"""System tray icon + menu via pystray."""

from __future__ import annotations

from PIL import Image, ImageDraw
import pystray


def _icon_image() -> Image.Image:
    img = Image.new("RGB", (64, 64), (30, 30, 40))
    d = ImageDraw.Draw(img)
    d.ellipse((14, 14, 50, 50), fill=(90, 200, 160))
    return img


class Tray:
    def __init__(self, on_pause_toggle, on_quit, on_settings) -> None:
        self._on_pause_toggle = on_pause_toggle
        self._on_quit = on_quit
        self._on_settings = on_settings
        self._paused = False
        self._icon = pystray.Icon(
            "life-graph-capture", _icon_image(), "Life Graph Capture",
            menu=self._menu(),
        )

    def _menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(
                lambda item: "Resume" if self._paused else "Pause",
                self._toggle_pause,
            ),
            pystray.MenuItem("Open settings folder", lambda: self._on_settings()),
            pystray.MenuItem("Quit", self._quit),
        )

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        self._on_pause_toggle(self._paused)

    def _quit(self) -> None:
        self._on_quit()
        self._icon.stop()

    def notify(self, title: str, message: str) -> None:
        from clients.desktop.notify import toast

        toast(title, message, icon_fallback=self._icon)

    def run(self) -> None:
        self._icon.run()
