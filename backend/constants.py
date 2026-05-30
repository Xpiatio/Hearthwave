import datetime
import os

CONFIG_FILE = "config.json"
CONTACTS_FILE = "contacts.json"


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


COLOR_RX = "#15803D"
COLOR_TX = "#1D4ED8"
COLOR_ERROR = "#B91C1C"
COLOR_WARN = "#92400E"
PILL_BG = "#FEF3C7"
PILL_TEXT = "#78350F"
PILL_BORDER = "#A16207"

VERIFIED_GLYPH = "✓"
VERIFIED_COLOR = COLOR_RX

VOICE_TEST_TEXT = "Radio-TTY voice test. Radio check, one two three."

DEFAULT_OPERATOR_NAME = "Default User"
UNSET_FIELD = "N/A"


def validate_voice_path(voice_path: str) -> bool:
    return bool(voice_path) and os.path.isfile(voice_path)

HALLUCINATIONS: frozenset[str] = frozenset({
    "you", "thank you", "thanks", "thanks for watching",
    "thank you for watching", "thanks for watching!", "bye", ".",
    "okay", "ok", "yeah", "mm", "hmm",
})
