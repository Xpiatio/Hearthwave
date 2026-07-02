from backend.config import ServerConfig


def test_default_off():
    assert ServerConfig().fuzzy_callsign_rewrite is False


def test_explicit_true():
    assert ServerConfig({"fuzzy_callsign_rewrite": True}).fuzzy_callsign_rewrite is True


def test_truthy_coerced_to_bool():
    assert ServerConfig({"fuzzy_callsign_rewrite": 1}).fuzzy_callsign_rewrite is True
