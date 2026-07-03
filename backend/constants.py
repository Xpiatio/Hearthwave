import datetime
import os


def utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


SERVICE_GMRS = "GMRS"
SERVICE_FRS = "FRS"
DEFAULT_SERVICE = SERVICE_GMRS


def normalize_service(value):
    if not value:
        return DEFAULT_SERVICE
    upper = str(value).strip().upper()
    if upper == SERVICE_FRS:
        return SERVICE_FRS
    return SERVICE_GMRS


VOICE_TEST_TEXT = "Hearthwave voice test. Radio check, one two three."

DEFAULT_OPERATOR_NAME = "Default User"
UNSET_FIELD = "N/A"


def validate_voice_path(voice_path: str) -> bool:
    return bool(voice_path) and os.path.isfile(voice_path)

GAIN_MODES: tuple[str, ...] = ("agc", "rms", "off")

# Whisper variants the config UI may select; must match bootstrap_models.py.
VALID_WHISPER_MODELS: frozenset[str] = frozenset({
    "tiny.en", "base.en", "small.en", "medium.en", "large-v3", "distil-large-v3",
})
# Final-pass-only additions: turbo is too slow for the 2 s streaming slices,
# so it must never be selectable as the fast model; "auto" resolves to the
# best staged model at worker construction.
VALID_FINAL_MODELS: frozenset[str] = VALID_WHISPER_MODELS | {"large-v3-turbo", "auto"}

HALLUCINATIONS: frozenset[str] = frozenset({
    # Common single-word/phrase Whisper hallucinations on silence
    "you", "thank you", "thanks", "thanks for watching",
    "thank you for watching", "thanks for watching!", "bye", ".",
    "okay", "ok", "yeah", "mm", "hmm", "uh", "um", "uh-huh", "mhm",
    # Noise/static artifacts
    "...", ". . .", "- - -", "–", "—",
    # Music/media markers Whisper hallucinates on carrier tones or CTCSS
    "(soft music)", "(music)", "[music]", "♪ ♪", "♪♪", "♫",
    # Subtitle/transcript artifacts
    "subtitles by", "transcript by", "captioned by",
})
