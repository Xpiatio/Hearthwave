from abc import ABC, abstractmethod


class PTT(ABC):
    """PTT interface. Modes share lead-in/tail silence padding so the radio's
    keying ramp or VOX hang time doesn't clip audio."""
    lead_in_seconds = 0.0
    tail_seconds = 0.0

    @abstractmethod
    def key(self) -> None: ...

    @abstractmethod
    def unkey(self) -> None: ...

    def close(self) -> None:
        pass
