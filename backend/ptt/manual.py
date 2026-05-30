from backend.ptt.base import PTT


class ManualPTT(PTT):
    """User keys the radio themselves; app just plays audio."""

    def key(self) -> None:
        pass

    def unkey(self) -> None:
        pass
