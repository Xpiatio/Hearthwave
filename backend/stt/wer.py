"""Word-error-rate scoring shared by the offline eval CLI (backend.tools.eval_stt)
and the in-app STT calibration wizard (backend.stt.calibration), so both score
transcripts identically."""
from __future__ import annotations


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
