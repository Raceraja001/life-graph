import pytest

from clients.desktop.grab import WindowInfo, grab_selection, normalize_window


def test_normalize_window_defaults_none():
    assert normalize_window(None, None) == WindowInfo(app="", title="")


def test_normalize_window_trims():
    assert normalize_window("  Title  ", " Code.exe ") == WindowInfo(
        app="Code.exe", title="Title"
    )


def test_grab_selection_returns_copied_text_as_selection():
    clip = {"v": "OLD"}
    copied = {"done": False}

    def copy_fn():
        clip["v"] = "SELECTED TEXT"  # simulate Ctrl+C replacing clipboard
        copied["done"] = True

    text, source = grab_selection(
        copy_fn=copy_fn,
        read_clipboard=lambda: clip["v"],
        write_clipboard=lambda v: clip.__setitem__("v", v),
        sleep_fn=lambda _s: None,
    )
    assert text == "SELECTED TEXT"
    assert source == "selection"
    assert clip["v"] == "OLD"  # prior clipboard restored


def test_grab_selection_falls_back_to_clipboard_when_no_selection():
    clip = {"v": "CLIP ONLY"}

    def copy_fn():
        pass  # nothing selected → clipboard unchanged

    text, source = grab_selection(
        copy_fn=copy_fn,
        read_clipboard=lambda: clip["v"],
        write_clipboard=lambda v: clip.__setitem__("v", v),
        sleep_fn=lambda _s: None,
    )
    assert text == "CLIP ONLY"
    assert source == "clipboard"
    assert clip["v"] == "CLIP ONLY"  # prior clipboard restored on fallback path


def test_grab_selection_restores_clipboard_on_error():
    clip = {"v": "IMPORTANT"}

    def copy_fn():
        raise RuntimeError("clipboard access denied")

    with pytest.raises(RuntimeError):
        grab_selection(
            copy_fn=copy_fn,
            read_clipboard=lambda: clip["v"],
            write_clipboard=lambda v: clip.__setitem__("v", v),
            sleep_fn=lambda _s: None,
        )
    assert clip["v"] == "IMPORTANT"  # restored despite the error
