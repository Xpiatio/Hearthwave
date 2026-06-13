import os

from backend.constants import HALLUCINATIONS


class WhisperTranscriber:
    """Offline STT via faster-whisper (CTranslate2, int8 CPU).

    Loads a Whisper model from a local directory (no network) and exposes
    a single transcribe() entry point. Drops common Whisper hallucinations
    on silence so the chat doesn't fill up with stray 'you' / 'thank you'
    lines between transmissions.
    """

    def __init__(self, model, saved_phrases=()):
        self.model = model
        self.initial_prompt = self._build_prompt(saved_phrases)

    @classmethod
    def load(cls, model_path, saved_phrases=(), *, cpu_threads=None):
        from faster_whisper import WhisperModel

        # Leave at least one core free for the asyncio event loop.
        # faster-whisper's default cpu_threads=0 means "use all cores",
        # which saturates the CPU during inference and starves the event loop.
        # Callers may pass a smaller count (the background final-pass model
        # runs with fewer threads so it never crowds out the fast path).
        if cpu_threads is None:
            cpu_threads = max(1, (os.cpu_count() or 2) - 1)
        return cls(
            WhisperModel(
                model_path,
                device="cpu",
                compute_type="int8",
                cpu_threads=cpu_threads,
            ),
            saved_phrases=saved_phrases,
        )

    # Segments where Whisper's own confidence that speech is present falls
    # below this threshold are discarded. 0.6 is the commonly recommended
    # value — above it the model is more confident the audio is silence/noise
    # than speech.
    _NO_SPEECH_THRESHOLD = 0.6

    # Segments with average log-probability below this value have very low
    # token confidence and are almost always noise hallucinations.
    _AVG_LOGPROB_THRESHOLD = -1.0

    @staticmethod
    def _build_prompt(phrases) -> str:
        base = "GMRS radio."
        if phrases:
            return f"{base} Phrases: {', '.join(phrases)}."
        return base

    def update_prompt(self, saved_phrases=()) -> None:
        """Rebuild the initial_prompt from a new phrase list (thread-safe via GIL)."""
        self.initial_prompt = self._build_prompt(saved_phrases)

    def transcribe(self, audio):
        """Return transcribed text, or None when the output is empty or
        matches a known Whisper-on-silence hallucination."""
        segments, _ = self.model.transcribe(
            audio,
            language="en",
            beam_size=5,
            vad_filter=True,
            # Don't let a hallucination in one segment condition the next.
            condition_on_previous_text=False,
            initial_prompt=self.initial_prompt,
        )
        kept = []
        for seg in segments:
            if seg.no_speech_prob > self._NO_SPEECH_THRESHOLD:
                continue
            if seg.avg_logprob < self._AVG_LOGPROB_THRESHOLD:
                continue
            kept.append(seg.text.strip())
        text = " ".join(kept).strip()
        normalized = text.lower().strip(".,!?;: ")
        if not text or normalized in HALLUCINATIONS:
            return None
        return text
