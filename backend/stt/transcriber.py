import os

from backend.stt._prompt import build_prompt, is_hallucination, MAX_PROMPT_TOKENS


class WhisperTranscriber:
    """Offline STT via faster-whisper (CTranslate2, int8 CPU).

    Loads a Whisper model from a local directory (no network) and exposes
    a single transcribe() entry point. Drops common Whisper hallucinations
    on silence so the chat doesn't fill up with stray 'you' / 'thank you'
    lines between transmissions.
    """

    def __init__(
        self,
        model,
        saved_phrases=(),
        *,
        decode_options=None,
        word_confidence_min=None,
        prompt_style="list",
    ):
        self.model = model
        self._count_tokens = self._make_token_counter(model)
        # Selects the initial_prompt rendering: "list" (production default) or
        # "transcript" (eval-only A/B variant). See backend/stt/_prompt.py.
        self.prompt_style = prompt_style
        self.initial_prompt = self._build_prompt(
            saved_phrases, count_tokens=self._count_tokens, style=self.prompt_style
        )
        # Extra/override kwargs merged into the transcribe() call below, for
        # A/B-testing decode parameters (beam size, repetition penalty, ...)
        # from the offline eval CLI without touching production call sites.
        self.decode_options = decode_options
        # When set, rebuilds each kept segment's text from its word-level
        # confidences instead of trusting Whisper's segment-level text, so a
        # few garbled words don't drag a whole segment's reading down.
        self.word_confidence_min = word_confidence_min

    @classmethod
    def load(
        cls,
        model_path,
        saved_phrases=(),
        *,
        cpu_threads=None,
        decode_options=None,
        word_confidence_min=None,
        prompt_style="list",
    ):
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
            decode_options=decode_options,
            word_confidence_min=word_confidence_min,
            prompt_style=prompt_style,
        )

    # Segments where Whisper's own confidence that speech is present falls
    # below this threshold are discarded. 0.6 is the commonly recommended
    # value — above it the model is more confident the audio is silence/noise
    # than speech.
    _NO_SPEECH_THRESHOLD = 0.6

    # Segments with average log-probability below this value have very low
    # token confidence and are almost always noise hallucinations.
    _AVG_LOGPROB_THRESHOLD = -1.0

    # Kept as a class attribute alias for backward compatibility (tests import it).
    _MAX_PROMPT_TOKENS = MAX_PROMPT_TOKENS

    @staticmethod
    def _make_token_counter(model):
        """Return a callable(str)->int. Uses the model's Whisper tokenizer when
        available; falls back to a coarse char/4 heuristic (e.g. in unit tests
        with no model)."""
        tok = getattr(model, "hf_tokenizer", None)
        if tok is not None:
            return lambda s: len(tok.encode(s).ids)
        return lambda s: max(1, len(s) // 4)

    @staticmethod
    def _build_prompt(phrases, *, count_tokens, style="list") -> str:
        return build_prompt(phrases, count_tokens=count_tokens, style=style)

    def update_prompt(self, saved_phrases=()) -> None:
        """Rebuild the initial_prompt from a new phrase list (thread-safe via GIL)."""
        self.initial_prompt = self._build_prompt(
            saved_phrases, count_tokens=self._count_tokens, style=self.prompt_style
        )

    def transcribe(self, audio, *, vad_filter=True, drop_low_confidence=True):
        """Return transcribed text, or None when the output is empty or
        matches a known Whisper-on-silence hallucination.

        The fast streaming path keeps the defaults: VAD re-gating plus a
        low-confidence segment drop weed out hallucinations on short slices.
        The whole-utterance final pass passes ``vad_filter=False,
        drop_low_confidence=False`` — its audio is already a squelch-bounded
        utterance, so re-gating it with VAD or dropping quieter tail segments
        only truncates long messages.
        """
        kwargs = {
            "language": "en",
            "beam_size": 5,
            # Don't let a hallucination in one segment condition the next.
            "condition_on_previous_text": False,
        }
        if self.decode_options:
            # vad_filter and initial_prompt are managed by this class (the
            # former is a call-site argument, the latter tracks saved
            # phrases) — silently drop any attempt to override them so
            # eval-harness decode_options can never desync production wiring.
            kwargs.update(
                (k, v) for k, v in self.decode_options.items()
                if k not in ("vad_filter", "initial_prompt")
            )
        kwargs["vad_filter"] = vad_filter
        kwargs["initial_prompt"] = self.initial_prompt
        if self.word_confidence_min is not None:
            kwargs["word_timestamps"] = True
        segments, _ = self.model.transcribe(audio, **kwargs)
        kept = []
        for seg in segments:
            if seg.no_speech_prob > self._NO_SPEECH_THRESHOLD:
                continue
            if drop_low_confidence and seg.avg_logprob < self._AVG_LOGPROB_THRESHOLD:
                continue
            if self.word_confidence_min is None:
                kept.append(seg.text.strip())
                continue
            # Rebuild the segment's text from its words, dropping any below
            # the confidence floor. A segment where every word is dropped
            # contributes nothing (not even a stray space).
            words = seg.words or []
            confident_text = "".join(
                w.word for w in words if w.probability >= self.word_confidence_min
            ).strip()
            if confident_text:
                kept.append(confident_text)
        text = " ".join(kept).strip()
        if is_hallucination(text):
            return None
        return text
