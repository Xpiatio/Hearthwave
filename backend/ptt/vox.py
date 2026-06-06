from backend.ptt.base import PTT


class VoxPTT(PTT):
    """Radio's VOX circuit auto-keys on detected audio. Extra trailing silence
    keeps VOX engaged so the last syllable isn't clipped on dropout."""
    tail_seconds = 0.15

    def __init__(self, lead_in_ms: int = 350):
        self.lead_in_seconds = lead_in_ms / 1000.0

    def key(self) -> None:
        pass

    def unkey(self) -> None:
        pass
