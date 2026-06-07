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


VOICE_TEST_TEXT = "Radio-TTY voice test. Radio check, one two three."

DEFAULT_OPERATOR_NAME = "Default User"
UNSET_FIELD = "N/A"


def validate_voice_path(voice_path: str) -> bool:
    return bool(voice_path) and os.path.isfile(voice_path)

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
