"""An in-memory to-do list: the logic the unit tests cover."""

from __future__ import annotations


class Store:
    def __init__(self) -> None:
        self._items: list[dict] = []

    def add(self, title: str) -> dict:
        clean = (title or "").strip()
        if not clean:
            raise ValueError("title is required")
        item = {"id": len(self._items) + 1, "title": clean, "done": False}
        self._items.append(item)
        return item

    def list(self) -> list[dict]:
        return [dict(i) for i in self._items]
