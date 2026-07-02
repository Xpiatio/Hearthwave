from backend.config import ServerConfig


def test_default_is_auto():
    """Fresh installs auto-resolve the final-pass model from what's staged."""
    assert ServerConfig().whisper_model_final == "auto"


def test_persisted_empty_string_stays_off():
    """Installs that ever saved server config have "" persisted (the frontend
    always sends the key). That's deliberate-off — never migrate it to auto."""
    assert ServerConfig({"whisper_model_final": ""}).whisper_model_final == ""


def test_explicit_name_passes_through():
    assert ServerConfig({"whisper_model_final": "distil-large-v3"}).whisper_model_final == "distil-large-v3"
