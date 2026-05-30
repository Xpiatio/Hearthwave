from backend.ptt.base import PTT


class VoxPTT(PTT):
    """Radio's VOX circuit auto-keys on detected audio. Extra trailing silence
    keeps VOX engaged so the last syllable isn't clipped on dropout."""
    tail_seconds = 0.15

    def key(self) -> None:
        pass

    def unkey(self) -> None:
        pass
