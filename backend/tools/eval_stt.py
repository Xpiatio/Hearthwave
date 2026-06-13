"""Offline STT evaluation: replay WAV files through the production RX
pipeline and score word-error-rate against hand-written references.

The pipeline layer drives the *same* classes the live worker uses
(SquelchDetector, SpeechSegmenter, preprocess_segment, WhisperTranscriber)
with individual stages toggleable, so A/B comparisons measure production
behavior rather than a reimplementation.

Usage (from the repo root):

    python -m backend.tools.eval_stt --audio /data/debug/stt --model small.en
    python -m backend.tools.eval_stt --audio samples/ --no-denoise --json

Each WAV needs a reference transcript: either ``<stem>.txt`` beside the
file, or ``reference.txt`` in the same directory (the debug-capture
utterance layout). See docs/stt-eval.md for the capture workflow.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import wave
from pathlib import Path

import numpy as np

from backend.audio.dsp import lowpass, make_bandpass_sos, make_lowpass_sos
from backend.audio.squelch import SquelchDetector
from backend.stt.preprocess import preprocess_segment
from backend.stt.segmenter import SpeechSegmenter
from backend.stt.worker import STTWorker


@dataclasses.dataclass
class EvalPipelineConfig:
    """Pipeline knobs. Defaults mirror the production STTWorker constants so
    a bare config reproduces live behavior exactly."""

    sample_rate: int = STTWorker.SAMPLE_RATE
    chunk_samples: int = STTWorker.CHUNK_SAMPLES
    lowpass_enabled: bool = True
    denoise_enabled: bool = True
    agc_enabled: bool = True
    prop_decrease: float = 0.7
    squelch_open_threshold: float = STTWorker.SQUELCH_OPEN_THRESHOLD
    squelch_adaptive: bool = False
    min_speech_s: float = STTWorker.MIN_SPEECH_DURATION_S
    pre_roll_s: float = STTWorker.PRE_BUFFER_CHUNKS * STTWorker.CHUNK_SAMPLES / STTWorker.SAMPLE_RATE
    rolling_segment_s: float = STTWorker.ROLLING_SEGMENT_S
    cut_window_s: float = STTWorker.CUT_WINDOW_S
    # Zero-padding appended after the file so VAD can emit its end event.
    flush_silence_s: float = 2.0


def run_pipeline(audio: np.ndarray, cfg: EvalPipelineConfig, transcriber, vad_iter) -> list[dict]:
    """Feed one audio buffer through segmentation + DSP + transcription.

    Returns one dict per finalized utterance: {"utterance_id", "text"} where
    text follows the server's accumulation rule (partials joined by spaces,
    final appended).
    """
    sr = cfg.sample_rate
    chunk_n = cfg.chunk_samples
    to_chunks = lambda seconds: int(seconds * sr / chunk_n)
    squelch = SquelchDetector(
        open_threshold=cfg.squelch_open_threshold,
        open_hold_chunks=STTWorker.SQUELCH_OPEN_HOLD_CHUNKS,
        close_hold_chunks=STTWorker.SQUELCH_CLOSE_HOLD_CHUNKS,
        adaptive=cfg.squelch_adaptive,
    )
    segmenter = SpeechSegmenter(
        vad_iter,
        squelch,
        sample_rate=sr,
        rolling_target_chunks=to_chunks(cfg.rolling_segment_s),
        cut_window_chunks=to_chunks(cfg.cut_window_s),
        pre_buffer_chunks=max(1, to_chunks(cfg.pre_roll_s)),
        squelch_buffer_max_chunks=STTWorker.SQUELCH_BUFFER_MAX_CHUNKS,
        min_speech_duration_s=cfg.min_speech_s,
        silence_reset_chunks=to_chunks(STTWorker.SILENCE_RESET_S),
    )
    bandpass_sos = make_bandpass_sos(sr, STTWorker.BANDPASS_LOW_HZ, STTWorker.BANDPASS_HIGH_HZ)
    lowpass_sos = make_lowpass_sos(sr, cutoff_hz=2700) if cfg.lowpass_enabled else None

    audio = np.asarray(audio, dtype=np.float32)
    flush = np.zeros(int(cfg.flush_silence_s * sr), dtype=np.float32)
    stream = np.concatenate([audio, flush])
    pad = (-len(stream)) % chunk_n
    if pad:
        stream = np.concatenate([stream, np.zeros(pad, dtype=np.float32)])

    partial_texts: dict[int, list[str]] = {}
    results: list[dict] = []
    for start in range(0, len(stream), chunk_n):
        chunk = stream[start:start + chunk_n]
        chunk_for_vad = lowpass(chunk, lowpass_sos) if lowpass_sos is not None else chunk
        peak = float(np.max(np.abs(chunk_for_vad))) if chunk_for_vad.size else 0.0
        segments, _events = segmenter.feed(chunk_for_vad, peak)
        for uid, seg_audio, is_final in segments:
            processed = preprocess_segment(
                seg_audio, sr, bandpass_sos,
                denoise_enabled=cfg.denoise_enabled,
                prop_decrease=cfg.prop_decrease,
                agc_enabled=cfg.agc_enabled,
            )
            text = transcriber.transcribe(processed)
            if not text:
                continue
            if is_final:
                pieces = partial_texts.pop(uid, [])
                pieces.append(text)
                results.append({"utterance_id": uid, "text": " ".join(pieces).strip()})
            else:
                partial_texts.setdefault(uid, []).append(text)
    # Utterances whose final transcribed empty still count: surface partials.
    for uid, pieces in partial_texts.items():
        if pieces:
            results.append({"utterance_id": uid, "text": " ".join(pieces).strip()})
    return results


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — so WER measures
    word recognition, not Whisper's formatting choices."""
    cleaned = "".join(c if c.isalnum() or c.isspace() else " " for c in text.lower())
    return " ".join(cleaned.split())


def score(references: list[str], hypotheses: list[str]) -> dict:
    """Corpus-level WER over normalized text."""
    import jiwer

    refs = [normalize_text(r) for r in references]
    hyps = [normalize_text(h) for h in hypotheses]
    return {"wer": jiwer.wer(refs, hyps), "count": len(refs)}


def find_reference(wav_path: Path) -> str | None:
    """Locate the reference transcript for a WAV: ``<stem>.txt`` sibling, or
    ``reference.txt`` in the same directory (debug-capture layout)."""
    sibling = wav_path.with_suffix(".txt")
    if sibling.exists():
        return sibling.read_text().strip()
    ref = wav_path.parent / "reference.txt"
    if ref.exists():
        return ref.read_text().strip()
    return None


def _read_wav(path: Path, target_sr: int) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        n_ch = w.getnchannels()
        width = w.getsampwidth()
        frames = w.readframes(w.getnframes())
    if width != 2:
        raise ValueError(f"{path}: only 16-bit PCM WAV supported (got {width * 8}-bit)")
    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32767.0
    if n_ch > 1:
        audio = audio.reshape(-1, n_ch).mean(axis=1)
    if sr != target_sr:
        from scipy.signal import resample_poly
        from math import gcd
        g = gcd(sr, target_sr)
        audio = resample_poly(audio, target_sr // g, sr // g).astype(np.float32)
    return audio


def _discover_wavs(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    # Debug-capture utterance dirs are evaluated on their raw (pre-DSP) audio.
    wavs = sorted(root.rglob("raw.wav"))
    if not wavs:
        wavs = sorted(p for p in root.rglob("*.wav"))
    return wavs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audio", required=True, help="WAV file, directory of WAVs, or debug-capture directory")
    ap.add_argument("--model", default="small.en", help="Whisper model for transcription")
    ap.add_argument("--no-denoise", action="store_true")
    ap.add_argument("--no-agc", action="store_true")
    ap.add_argument("--no-lowpass", action="store_true")
    ap.add_argument("--prop-decrease", type=float, default=0.7)
    ap.add_argument("--vad-threshold", type=float, default=0.5)
    ap.add_argument("--squelch-threshold", type=float, default=STTWorker.SQUELCH_OPEN_THRESHOLD)
    ap.add_argument("--adaptive-squelch", action="store_true")
    ap.add_argument("--min-speech-s", type=float, default=STTWorker.MIN_SPEECH_DURATION_S)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    cfg = EvalPipelineConfig(
        lowpass_enabled=not args.no_lowpass,
        denoise_enabled=not args.no_denoise,
        agc_enabled=not args.no_agc,
        prop_decrease=args.prop_decrease,
        squelch_open_threshold=args.squelch_threshold,
        squelch_adaptive=args.adaptive_squelch,
        min_speech_s=args.min_speech_s,
    )

    from backend.audio.vad import load_vad_model, make_vad_iterator
    from backend.stt.transcriber import WhisperTranscriber

    transcriber = WhisperTranscriber.load(str(STTWorker._MODELS_DIR / args.model))
    vad_model = load_vad_model()

    wavs = _discover_wavs(Path(args.audio))
    if not wavs:
        print(f"No WAV files found under {args.audio}", file=sys.stderr)
        return 2

    per_file = []
    refs, hyps = [], []
    skipped = 0
    for wav in wavs:
        reference = find_reference(wav)
        if reference is None:
            skipped += 1
            continue
        audio = _read_wav(wav, cfg.sample_rate)
        # Fresh VAD state per file so utterances don't bleed across files.
        vad_iter = make_vad_iterator(vad_model, sample_rate=cfg.sample_rate, threshold=args.vad_threshold)
        results = run_pipeline(audio, cfg, transcriber, vad_iter)
        hypothesis = " ".join(r["text"] for r in results).strip()
        file_score = score([reference], [hypothesis]) if reference else None
        per_file.append({
            "file": str(wav),
            "reference": reference,
            "hypothesis": hypothesis,
            "wer": file_score["wer"],
        })
        refs.append(reference)
        hyps.append(hypothesis)

    if not refs:
        print("No labelled files found (need <stem>.txt or reference.txt).", file=sys.stderr)
        return 2

    corpus = score(refs, hyps)
    if args.json:
        print(json.dumps({"corpus": corpus, "skipped_unlabelled": skipped, "files": per_file}, indent=2))
    else:
        for f in per_file:
            print(f"{f['wer']:6.1%}  {f['file']}")
            print(f"        ref: {f['reference']}")
            print(f"        hyp: {f['hypothesis']}")
        print(f"\nCorpus WER: {corpus['wer']:.1%} over {corpus['count']} file(s); {skipped} unlabelled skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
