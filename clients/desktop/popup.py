"""Minimal always-on-top capture window built on tkinter (stdlib)."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass


@dataclass
class CaptureDraft:
    content: str
    tags: list[str]


def _parse_tags(raw: str) -> list[str]:
    return [t.strip() for t in raw.split(",") if t.strip()]


def show_popup(prefill: str = "") -> CaptureDraft | None:
    """Show the capture popup. Returns a CaptureDraft or None if cancelled."""
    result: dict[str, CaptureDraft | None] = {"draft": None}

    root = tk.Tk()
    root.title("Capture to Life Graph")
    root.attributes("-topmost", True)
    root.geometry("460x220")
    root.eval("tk::PlaceWindow . center")

    tk.Label(root, text="Capture").pack(anchor="w", padx=8, pady=(8, 0))
    text = tk.Text(root, height=6, wrap="word")
    text.insert("1.0", prefill)
    text.pack(fill="both", expand=True, padx=8)
    text.focus_set()

    tag_frame = tk.Frame(root)
    tag_frame.pack(fill="x", padx=8, pady=4)
    tk.Label(tag_frame, text="tags:").pack(side="left")
    tag_entry = tk.Entry(tag_frame)
    tag_entry.pack(side="left", fill="x", expand=True)

    def save(_event=None):
        content = text.get("1.0", "end").strip()
        if content:
            result["draft"] = CaptureDraft(content, _parse_tags(tag_entry.get()))
        root.destroy()

    def cancel(_event=None):
        root.destroy()

    btns = tk.Frame(root)
    btns.pack(fill="x", padx=8, pady=(0, 8))
    tk.Button(btns, text="Save  (Ctrl+Enter)", command=save).pack(side="right")
    tk.Button(btns, text="Cancel  (Esc)", command=cancel).pack(side="right", padx=6)

    root.bind("<Control-Return>", save)
    root.bind("<Escape>", cancel)

    root.mainloop()
    return result["draft"]
