from backend.config import ServerConfig


def test_default_off():
    assert ServerConfig().stt_noise_profile is False


def test_explicit_true():
    assert ServerConfig({"stt_noise_profile": True}).stt_noise_profile is True


def test_truthy_coerced_to_bool():
    assert ServerConfig({"stt_noise_profile": 1}).stt_noise_profile is True
