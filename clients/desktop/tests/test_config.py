import pytest

from clients.desktop.config import Config, ConfigError, load_config


class FakeKeyring:
    def __init__(self, secret=None):
        self._secret = secret
        self.set_calls = []

    def get_password(self, service, user):
        return self._secret

    def set_password(self, service, user, secret):
        self.set_calls.append((service, user, secret))


def _write(tmp_path, body):
    p = tmp_path / "config.toml"
    p.write_text(body, encoding="utf-8")
    return p


def test_loads_minimal_config(tmp_path):
    p = _write(tmp_path, 'backend_url = "http://localhost:8000"\ntenant_id = "default"\n')
    cfg = load_config(p, keyring_module=FakeKeyring(secret="key-123"))
    assert isinstance(cfg, Config)
    assert cfg.backend_url == "http://localhost:8000"
    assert cfg.tenant_id == "default"
    assert cfg.api_key == "key-123"
    # defaults
    assert cfg.hotkeys.popup == "<ctrl>+<alt>+space"
    assert cfg.hotkeys.instant == "<ctrl>+<alt>+c"
    assert cfg.replay_interval_seconds == 30
    assert cfg.redact is True


def test_overrides_hotkeys_and_behavior(tmp_path):
    p = _write(
        tmp_path,
        'backend_url = "http://x"\ntenant_id = "t"\n'
        '[hotkeys]\npopup = "<ctrl>+1"\ninstant = "<ctrl>+2"\n'
        '[behavior]\nreplay_interval_seconds = 5\nredact = false\n',
    )
    cfg = load_config(p, keyring_module=FakeKeyring(secret="k"))
    assert cfg.hotkeys.popup == "<ctrl>+1"
    assert cfg.replay_interval_seconds == 5
    assert cfg.redact is False


def test_missing_api_key_raises(tmp_path):
    p = _write(tmp_path, 'backend_url = "http://x"\ntenant_id = "t"\n')
    with pytest.raises(ConfigError):
        load_config(p, keyring_module=FakeKeyring(secret=None))


def test_config_repr_hides_api_key(tmp_path):
    p = _write(tmp_path, 'backend_url = "http://x"\ntenant_id = "t"\n')
    cfg = load_config(p, keyring_module=FakeKeyring(secret="topsecretkey"))
    assert "topsecretkey" not in repr(cfg)


def test_set_api_key_stores_in_keyring():
    from clients.desktop.config import KEYRING_SERVICE, set_api_key

    kr = FakeKeyring()
    set_api_key("tenant-x", "the-key", keyring_module=kr)
    assert kr.set_calls == [(KEYRING_SERVICE, "tenant-x", "the-key")]
