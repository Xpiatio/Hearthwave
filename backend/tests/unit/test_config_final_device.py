from backend.config import ServerConfig


def test_default_is_auto():
    assert ServerConfig().stt_final_device == "auto"


def test_explicit_gpu():
    assert ServerConfig({"stt_final_device": "gpu"}).stt_final_device == "gpu"


def test_explicit_cpu():
    assert ServerConfig({"stt_final_device": "cpu"}).stt_final_device == "cpu"


def test_unknown_coerced_to_auto():
    assert ServerConfig({"stt_final_device": "tpu"}).stt_final_device == "auto"


def test_case_insensitive():
    assert ServerConfig({"stt_final_device": "GPU"}).stt_final_device == "gpu"
