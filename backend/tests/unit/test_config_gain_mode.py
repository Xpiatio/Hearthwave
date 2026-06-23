from backend.config import ServerConfig


def test_default_is_agc():
    assert ServerConfig().stt_gain_mode == "agc"


def test_explicit_rms():
    assert ServerConfig({"stt_gain_mode": "rms"}).stt_gain_mode == "rms"


def test_explicit_off():
    assert ServerConfig({"stt_gain_mode": "off"}).stt_gain_mode == "off"


def test_unknown_coerced_to_agc():
    assert ServerConfig({"stt_gain_mode": "loud"}).stt_gain_mode == "agc"


def test_case_insensitive():
    assert ServerConfig({"stt_gain_mode": "RMS"}).stt_gain_mode == "rms"
