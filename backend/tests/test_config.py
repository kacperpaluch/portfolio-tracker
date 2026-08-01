from app.config import env_enabled


def test_env_enabled_defaults_to_true(monkeypatch):
    monkeypatch.delenv("SCHEDULER_ENABLED", raising=False)
    assert env_enabled("SCHEDULER_ENABLED") is True


def test_env_enabled_accepts_common_boolean_values(monkeypatch):
    for value in ("1", "true", "YES", " on "):
        monkeypatch.setenv("SCHEDULER_ENABLED", value)
        assert env_enabled("SCHEDULER_ENABLED") is True

    for value in ("0", "false", "NO", "off", ""):
        monkeypatch.setenv("SCHEDULER_ENABLED", value)
        assert env_enabled("SCHEDULER_ENABLED") is False
