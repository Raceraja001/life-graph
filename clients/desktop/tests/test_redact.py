from clients.desktop.redact import redact


def test_redacts_key_value_secret():
    assert "hunter2" not in redact("password=hunter2")
    assert "abc123" not in redact("API_KEY: abc123")


def test_keeps_key_name_hides_value():
    out = redact("api_key=sk-abcdefghijklmnop1234")
    assert "api_key" in out and "[REDACTED]" in out
    assert "sk-abcdefghijklmnop1234" not in out


def test_redacts_token_shapes():
    assert "AKIAIOSFODNN7EXAMPLE" not in redact("k AKIAIOSFODNN7EXAMPLE")
    assert "ghp_" not in redact("t ghp_0123456789abcdefghijklmnopqrstuv")


def test_plain_text_untouched():
    assert redact("git commit -m 'fix'") == "git commit -m 'fix'"


def test_empty_is_safe():
    assert redact("") == ""
    assert redact(None) is None
