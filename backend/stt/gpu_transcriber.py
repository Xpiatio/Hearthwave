"""GPU final-pass transcriber: transformers Whisper on ROCm (fp16).

Mirrors the public interface of WhisperTranscriber that the STTWorker final
pass uses (load / transcribe / update_prompt) so the worker can swap backends
behind one seam. Used only for the whole-utterance final pass, which always
calls transcribe(vad_filter=False, drop_low_confidence=False) — so per-segment
confidence filtering is not implemented here.

torch/transformers are imported lazily so this module imports without them
present (unit tests stub both).
"""
import logging

from backend.stt._prompt import build_prompt, is_hallucination

logger = logging.getLogger(__name__)

_SR = 16000


class GpuWhisperTranscriber:
    # decode_options keys that map onto HF generate() kwargs (transcribe()
    # below). Any other key (e.g. faster-whisper-only ones like "hotwords" or
    # "temperature") is silently ignored, since it has no HF equivalent here.
    _DECODE_OPTION_MAP = {
        "repetition_penalty": "repetition_penalty",
        "no_repeat_ngram_size": "no_repeat_ngram_size",
        "beam_size": "num_beams",
    }

    def __init__(self, model, processor, saved_phrases=(), *, decode_options=None, word_confidence_min=None):
        self.model = model
        self.processor = processor
        self._count_tokens = self._make_token_counter(processor)
        self.initial_prompt = build_prompt(saved_phrases, count_tokens=self._count_tokens)
        self._prompt_ids = self._encode_prompt(self.initial_prompt)
        # Extra/override kwargs merged into generate()'s kwargs below, mapped
        # via _DECODE_OPTION_MAP (see transcribe()). Mirrors WhisperTranscriber's
        # decode_options for the eval-harness seam; keys with no HF equivalent
        # are dropped rather than raising, so the same decode_options dict can
        # be reused across both backends.
        self.decode_options = decode_options
        # Accepted for interface parity with WhisperTranscriber but not
        # implemented here: the GPU path's generate() call has no per-word
        # probability output in the current flow, so this is a no-op.
        self.word_confidence_min = word_confidence_min

    @staticmethod
    def _make_token_counter(processor):
        tok = getattr(processor, "tokenizer", None)
        if tok is not None:
            return lambda s: len(tok(s).input_ids)
        return lambda s: max(1, len(s) // 4)

    def _encode_prompt(self, prompt):
        try:
            return self.processor.get_prompt_ids(prompt, return_tensors="pt")
        except Exception as exc:
            logger.warning("Could not encode prompt_ids: %s", exc)
            return None

    @classmethod
    def load(cls, model, saved_phrases=(), *, cpu_threads=None, decode_options=None, word_confidence_min=None):
        """Load an HF Whisper model onto the GPU in fp16 and pre-warm it.
        cpu_threads is accepted for interface parity and ignored."""
        import torch
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

        processor = AutoProcessor.from_pretrained(model)
        m = AutoModelForSpeechSeq2Seq.from_pretrained(
            model, torch_dtype=torch.float16, low_cpu_mem_usage=True
        ).to("cuda")
        inst = cls(
            m,
            processor,
            saved_phrases=saved_phrases,
            decode_options=decode_options,
            word_confidence_min=word_confidence_min,
        )
        inst._prewarm()
        return inst

    def _prewarm(self):
        """Absorb first-call kernel-compile latency with one silent generate."""
        import numpy as np
        try:
            self.transcribe(np.zeros(_SR, dtype=np.float32))
        except Exception as exc:
            logger.info("GPU pre-warm skipped: %s", exc)

    def update_prompt(self, saved_phrases=()) -> None:
        self.initial_prompt = build_prompt(saved_phrases, count_tokens=self._count_tokens)
        self._prompt_ids = self._encode_prompt(self.initial_prompt)

    def transcribe(self, audio, *, vad_filter=False, drop_low_confidence=False):
        """Transcribe a whole utterance. vad_filter/drop_low_confidence are
        accepted for interface parity (final pass passes both False)."""
        import torch

        # truncation=False -> full-length features so generate() uses Whisper's
        # native sequential long-form algorithm for utterances > 30s.
        inputs = self.processor(
            audio, sampling_rate=_SR, return_tensors="pt", truncation=False,
            padding="longest", return_attention_mask=True,
        )
        feats = inputs.input_features.to("cuda", torch.float16)
        attn = getattr(inputs, "attention_mask", None)
        gen_kw = dict(
            language="en", task="transcribe", num_beams=5, return_timestamps=True,
        )
        if self.decode_options:
            gen_kw.update(
                (self._DECODE_OPTION_MAP[k], v)
                for k, v in self.decode_options.items()
                if k in self._DECODE_OPTION_MAP
            )
        if attn is not None:
            gen_kw["attention_mask"] = attn.to("cuda")
        if self._prompt_ids is not None:
            gen_kw["prompt_ids"] = self._prompt_ids.to("cuda")
        with torch.no_grad():
            ids = self.model.generate(feats, **gen_kw)
        text = self.processor.batch_decode(ids, skip_special_tokens=True)[0].strip()
        if is_hallucination(text):
            return None
        return text
